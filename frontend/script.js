const API_URL =
“https://dashboard.render.com”;

function signalClass(signal){

if(signal==="BUY")
    return "signal-buy";
if(signal==="SELL")
    return "signal-sell";
return "signal-wait";

}

function renderCoin(data){

let html = "";
for(const tf in data){
    html += `
    <div class="timeframe">
        <h3>${tf}</h3>
        <p>
        Price:
        $${data[tf].price}
        </p>
        <p>
        RSI:
        ${data[tf].rsi}
        </p>
        <p class="${signalClass(data[tf].signal)}">
        ${data[tf].signal}
        </p>
    </div>
    `;
}
return html;

}

async function loadDashboard(){

try{
    const response =
    await fetch(API_URL);
    const data =
    await response.json();
    document.getElementById(
        "btc-content"
    ).innerHTML =
    renderCoin(data.btc);
    document.getElementById(
        "eth-content"
    ).innerHTML =
    renderCoin(data.eth);
    document.getElementById(
        "status"
    ).innerHTML =
    "Live";
}catch(err){
    document.getElementById(
        "status"
    ).innerHTML =
    "Disconnected";
}

}

loadDashboard();

setInterval(
loadDashboard,
10000
);
