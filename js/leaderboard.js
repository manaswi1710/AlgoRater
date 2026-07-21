console.log("Leaderboard JS loaded");

function getRatingClass(rating){

    if(rating < 1200)
        return "rating-gray";

    if(rating < 1400)
        return "rating-green";

    if(rating < 1600)
        return "rating-cyan";

    if(rating < 1900)
        return "rating-blue";

    if(rating < 2200)
        return "rating-violet";

    return "rating-orange";
}

async function loadLeaderboard(){


let response = await fetch("/api/leaderboard");


let data = await response.json();



let table =
document.getElementById("leaderboardBody");



if(data.length === 0){

table.innerHTML =
`
<tr>
<td colspan="5">
No users found
</td>
</tr>
`;

return;

}



data.forEach(user=>{


table.innerHTML +=
`

<tr>

<td>${user.rank}</td>

<td>${user.username}</td>

<td>${user.cf_handle}</td>

<td class="${getRatingClass(user.rating)}">
${user.rating}
</td>

<td>
${user.peak}
</td>


</tr>


`;

});


}



loadLeaderboard();