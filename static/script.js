let currentMatchId = null;
let timerInterval = null; 

document.getElementById('mode').addEventListener('change', function() {
    document.getElementById('focusSettings').style.display = this.value === 'chill' ? 'none' : 'block';
});

function getRatingColorClass(rating) {
    if (rating < 1200) return 'rating-gray';
    if (rating < 1400) return 'rating-green';
    if (rating < 1600) return 'rating-cyan';
    if (rating < 1900) return 'rating-blue';
    if (rating < 2100) return 'rating-purple';
    if (rating < 2400) return 'rating-orange';
    return 'rating-red';
}

function formatTime(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// Helper to get ID from local storage securely
function getUserId() {
    const storedId = localStorage.getItem('userId');
    if (!storedId) {
        window.location.href = "/static/login.html"; 
        return null;
    }
    return storedId;
}

async function startMatch() {
    // Automatically retrieve the ID from local storage
    const userId = getUserId(); 
    if (!userId) return; // Stop if not logged in

    const mode = document.getElementById("mode").value;
    const statusText = document.getElementById("statusMessage");
    
    document.getElementById("welcomeArea").style.display = "none";
    document.getElementById("matchArea").style.display = "none";
    document.getElementById("resultArea").style.display = "none";
    document.getElementById("browserArea").style.display = "none";

    if (mode === "chill") {
        statusText.innerText = "Fetching your unsolved problems...";
        statusText.style.color = "#1a73e8";
        await loadProblemBrowser(userId);
    } else {
        statusText.innerText = "Requesting random problem...";
        statusText.style.color = "#1a73e8";
        const targetRating = document.getElementById("targetRating").value;
        await executeMatchmaking(userId, mode, null, targetRating);
    }
}

async function loadProblemBrowser(userId) {
    const statusText = document.getElementById("statusMessage");
    try {
        const response = await fetch(`/unsolved-problems?user_id=${userId}&limit=50`);
        const data = await response.json();

        if (response.ok) {
            const tbody = document.getElementById("problemsTableBody");
            tbody.innerHTML = ""; 

            data.forEach(p => {
                const row = document.createElement("tr");
                // Use the userId from the parameter, which is now secure
                row.innerHTML = `
                    <td style="font-weight: bold;">${p.title}</td>
                    <td class="${getRatingColorClass(p.difficulty)}">${p.difficulty}</td>
                    <td>${p.hard_time} mins</td>
                    <td><button class="btn-primary" onclick="executeMatchmaking(${userId}, 'chill', ${p.problem_id})">Attempt</button></td>
                `;
                tbody.appendChild(row);
            });

            document.getElementById("browserArea").style.display = "block";
            statusText.innerText = "";
        }
    } catch (error) {
        statusText.innerText = "Failed to fetch problems.";
    }
}

async function executeMatchmaking(userId, mode, problemId, targetRating = "") {
    const statusText = document.getElementById("statusMessage");
    statusText.innerText = "Setting up the arena...";
    
    let url = `/start-match?user_id=${userId}&mode=${mode}`;
    if (problemId) url += `&problem_id=${problemId}`;
    if (targetRating !== "") url += `&target_rating=${targetRating}`;

    try {
        const response = await fetch(url, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            currentMatchId = data.match_id;
            
            window.open(data.codeforces_url, '_blank');
            
            document.getElementById("browserArea").style.display = "none";
            document.getElementById("matchArea").style.display = "block";
            statusText.innerText = "";
            document.getElementById("matchStatus").innerText = "";
            
            const linkEl = document.getElementById("ui-prob-link");
            linkEl.innerText = data.problem_name;
            linkEl.href = data.codeforces_url;
            
            const diffEl = document.getElementById("ui-diff");
            diffEl.innerText = data.difficulty;
            diffEl.className = getRatingColorClass(data.difficulty);
            
            startVisualTimer(data.server_start_time, data.expected_time_minutes, data.hard_time_minutes);
            
        } else {
            statusText.innerText = `Error: ${data.detail}`;
            statusText.style.color = "#d93025";
        }
    } catch (error) {
        statusText.innerText = "Server connection failed.";
        statusText.style.color = "#d93025";
    }
}

function startVisualTimer(startTimeISO, expectedMins, hardMins) {
    const startTime = new Date(startTimeISO).getTime();
    const expectedMs = expectedMins * 60 * 1000;
    const hardMs = hardMins * 60 * 1000;
    const timeEl = document.getElementById("ui-time");

    if (timerInterval) clearInterval(timerInterval);

    timerInterval = setInterval(() => {
        const now = new Date().getTime();
        const elapsed = now - startTime;

        if (elapsed < expectedMs) {
            const remaining = expectedMs - elapsed;
            timeEl.style.color = "#1e8e3e"; 
            timeEl.innerText = `${formatTime(remaining)} (Expected limit)`;
        } 
        else if (elapsed < hardMs) {
            const remaining = hardMs - elapsed;
            const seconds = Math.floor(remaining / 1000);
            timeEl.style.color = (seconds % 2 === 0) ? "#d93025" : "#202124"; 
            timeEl.innerText = `${formatTime(remaining)} (HARD LIMIT!)`;
        } 
        else {
            clearInterval(timerInterval);
            timeEl.innerText = "00:00 (TIMEOUT)";
            timeEl.style.color = "#d93025";
        }
    }, 1000);
}

async function finishMatch(gaveUp) {
    const cfHandle = document.getElementById("cfHandle").value;
    const statusText = document.getElementById("matchStatus");

    if (!gaveUp && !cfHandle) {
        statusText.innerText = "Error: Enter your Codeforces Handle in the sidebar to verify!";
        statusText.style.color = "#d93025";
        return;
    }

    statusText.innerText = gaveUp ? "Processing penalty..." : "Connecting to Codeforces API for live verification...";
    statusText.style.color = "#1a73e8";

    try {
        const response = await fetch(`/submit?match_id=${currentMatchId}&gave_up=${gaveUp}&cf_handle=${cfHandle}`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            if (timerInterval) clearInterval(timerInterval);
            
            document.getElementById("matchArea").style.display = "none";
            document.getElementById("resultArea").style.display = "block";
            
            const verdictEl = document.getElementById("res-verdict");
            verdictEl.innerText = data.verdict;
            verdictEl.style.color = data.verdict === "Accepted" ? "#1e8e3e" : "#d93025";
            
            document.getElementById("res-time").innerText = `${data.time_taken_minutes} mins`;
            
            const deltaEl = document.getElementById("res-delta");
            const sign = data.rating_change >= 0 ? "+" : "";
            deltaEl.innerText = `${sign}${data.rating_change}`;
            deltaEl.style.color = data.rating_change >= 0 ? "#1e8e3e" : "#d93025";
            
            const newRatingEl = document.getElementById("res-new");
            newRatingEl.innerText = data.new_rating;
            newRatingEl.className = getRatingColorClass(data.new_rating);

        } else {
            statusText.innerText = `❌ ${data.detail}`;
            statusText.style.color = "#d93025";
        }
    } catch (error) {
        statusText.innerText = "Failed to connect to backend server.";
        statusText.style.color = "#d93025";
    }
}