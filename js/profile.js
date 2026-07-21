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