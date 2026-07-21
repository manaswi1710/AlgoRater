async function loadContests(){

let res = await fetch("/api/contests");

let contests = await res.json();


let table =
document.getElementById("contestTable");


if(contests.length===0){

table.innerHTML =
`
<tr>
<td colspan="4">
No upcoming contests
</td>
</tr>
`;

return;

}


contests.forEach(c=>{


table.innerHTML +=
`

<tr>

<td>${c.name}</td>

<td>${c.startTime}</td>

<td>${c.duration} hrs</td>

<td>

<a target="_blank"
href="https://codeforces.com/contest/${c.id}">
Open
</a>

</td>

</tr>

`;

});


}


loadContests();