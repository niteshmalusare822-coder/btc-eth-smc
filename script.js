const API_URL = "https://crypto-scanner-api-xnwd.onrender.com/api/dashboard";

function signalClass(signal) {
    if (signal === "BUY") return "signal-buy";
    if (signal === "SELL") return "signal-sell";
    return "signal-wait";
}

function renderCoin(data) {
    let html = "";
    for (const tf in data) {
        const d = data[tf];

        if (d.error) {
            html += `
            <div class="timeframe">
                <h3>${tf}</h3>
                <p class="signal-wait">No data</p>
            </div>
            `;
            continue;
        }

        html += `
        <div class="timeframe">
            <h3>${tf}</h3>
            <p>Price: $${d.price}</p>
            <p>RSI: ${d.rsi ?? "-"}</p>
            <p class="${signalClass(d.signal)}">${d.signal}</p>
            <p class="meta">Bias: ${d.htf_bias ?? "-"} | Regime: ${d.regime ?? "-"}</p>
            <p class="meta">Score: BUY ${d.buy_score ?? "-"} / SELL ${d.sell_score ?? "-"}</p>
            <p class="reason">${d.reason ?? ""}</p>
        </div>
        `;
    }
    return html;
}

async function loadDashboard() {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 25000); // 25s timeout

        const response = await fetch(API_URL, { signal: controller.signal });
        clearTimeout(timeout);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        document.getElementById("btc-content").innerHTML = renderCoin(data.btc);
        document.getElementById("eth-content").innerHTML = renderCoin(data.eth);
        document.getElementById("status").innerHTML = "🟢 Live";

    } catch (err) {
        if (err.name === "AbortError") {
            console.warn("Request timeout — API slow hai");
            document.getElementById("status").innerHTML = "⏳ Loading...";
        } else {
            console.error("Fetch error:", err);
            document.getElementById("status").innerHTML = "🔴 Disconnected";
        }
    }
}

loadDashboard();
setInterval(loadDashboard, 15000);
