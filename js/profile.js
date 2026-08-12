async function loadStats(){


let userId =
localStorage.getItem("userId");


let res =
await fetch(`/profile-stats/${userId}`);


let data =
await res.json();



document.getElementById("matches")
.innerText=data.total;


document.getElementById("wins")
.innerText=data.wins;


document.getElementById("winrate")
.innerText=data.winrate+"%";



let table =
document.getElementById("history");



data.matches.forEach(m=>{


table.innerHTML +=`

<tr>

<td>${m.problem}</td>

<td>${m.verdict}</td>

<td>${m.delta}</td>

</tr>

`;

});


}



loadStats();


async function loadProfile(){


let userId =
localStorage.getItem("userId");



let response =
await fetch(`/user/${userId}`);



let user =
await response.json();



document.getElementById("username")
.innerText=user.username;


document.getElementById("cf")
.innerText=user.cf_handle;


document.getElementById("rating")
.innerText=user.rating;


document.getElementById("peak")
.innerText=user.peak_rating;


document.getElementById("rank")
.innerText="#"+user.rank;


document.getElementById("solved")
.innerText=user.solved;


}


loadProfile();

async function loadRatingGraph(){

    const userId = localStorage.getItem("userId");

    const res = await fetch(`/rating-history/${userId}`);

    const data = await res.json();


    const labels = data.map(x => {

        let d = new Date(x.date);

        return d.toLocaleDateString(
            "default",
            {
                day:"numeric",
                month:"short"
            }
        );

    });


    const ratings = data.map(x => x.rating);


    const ctx = document.getElementById("ratingChart");


    new Chart(ctx,{

        type:"line",

        data:{

            labels:labels,

            datasets:[{

                label:"Rating",

                data:ratings,

                borderColor:"#3b82f6",

                backgroundColor:"rgba(59,130,246,0.2)",

                fill:true,

                tension:0.35,

                pointRadius:5

            }]

        },


        options:{

            responsive:true,


            plugins:{

                legend:{
                    display:false
                }

            },


            scales:{


                x:{

                    ticks:{

                        autoSkip:true,

                        maxTicksLimit:8

                    }

                },


                y:{

                    beginAtZero:false

                }


            }


        }

    });

}

loadRatingGraph();

async function loadHeatmap(){

    console.log("Heatmap function started");

    const userId = localStorage.getItem("userId");

    const res = await fetch(`/heatmap/${userId}`);

    const data = await res.json();

    console.log("Heatmap Data:", data);


    const grid = document.getElementById("heatmap");

    grid.innerHTML="";
    data.sort((a, b) => new Date(a.date) - new Date(b.date));

if (data.length > 0) {
        // Find the day of the week for the very first date (0 = Sunday, 1 = Monday, etc.)
        const firstDate = new Date(data[0].date);
        let dayOfWeek = firstDate.getDay(); // Adjust if your grid starts on Monday instead of Sunday (e.g., (firstDate.getDay() + 6) % 7)

        // Prepend empty placeholder cells to align the calendar grid correctly by weekday
        for (let i = 0; i < dayOfWeek; i++) {
            const emptyCell = document.createElement("div");
            emptyCell.className = "heat-cell";
            emptyCell.style.opacity = "0"; // Make alignment padding invisible
            emptyCell.style.pointerEvents = "none";
            grid.appendChild(emptyCell);
        }
    }

    // Create heatmap cells first
    data.forEach(day=>{

        const cell=document.createElement("div");

        cell.className="heat-cell";


        if(day.count>=1)
            cell.classList.add("level1");

        if(day.count>=2)
            cell.classList.add("level2");

        if(day.count>=4)
            cell.classList.add("level3");

        if(day.count>=7)
            cell.classList.add("level4");

        // Format tooltip nicely
        let dFormatted = new Date(day.date).toLocaleDateString("default", {
            day: "numeric",
            month: "short",
            year: "numeric"
        });

        cell.title = `${dFormatted} : ${day.count} solved`;


        grid.appendChild(cell);

    });



    
}

loadHeatmap();