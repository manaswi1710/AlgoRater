function showRegister(){

document.getElementById("loginForm").style.display="none";

document.getElementById("registerForm").style.display="block";

}

function showLogin(){

document.getElementById("registerForm").style.display="none";

document.getElementById("loginForm").style.display="block";

}




async function handleLogin()
{

let username=
document.getElementById("loginUsername").value;

let password =
document.getElementById("loginPassword").value;

let res=
await fetch(
`/login?username=${username}&password=${password}`,
{
method:"POST"
});


let data=
await res.json();



if(res.ok)
{

localStorage.setItem(
"userId",
data.user_id
);


window.location.href="/arena";

}

else
{

document.getElementById("authStatus")
.innerText=data.detail;

}


}






async function handleRegister()
{

let username=
document.getElementById("regUsername").value;

let password=document.getElementById("regPassword").value;

let cf=
document.getElementById("regCfHandle").value;



let res=
await fetch(
`/register?username=${username}&password=${password}&cf_handle=${cf}`,
{
method:"POST"
});



let data=
await res.json();



if(res.ok)
{

localStorage.setItem(
"userId",
data.user_id
);


window.location.href="/arena";

}

else
{

document.getElementById("authStatus")
.innerText=data.detail;

}


}