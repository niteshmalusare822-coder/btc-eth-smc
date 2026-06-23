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

        // RSI color — red if overbought/oversold
        let rsiColor = "";
        if (d.rsi !== null) {
            if (d.rsi > 80) rsiColor = "color:#ff4d4d;font-weight:bold";
            else if (d.rsi < 20) rsiColor = "color:#00e676;font-weight:bold";
        }

        // Entry / TP / SL row — only show when signal is BUY or SELL
        let tradeRow = "";
        if (d.signal === "BUY" || d.signal === "SELL") {
            tradeRow = `
            <p class="meta" style="margin-top:6px;border-top:1px solid #444;padding-top:6px;">
                📍 Entry: <b>$${d.entry ?? "-"}</b> &nbsp;
                🎯 TP: <b style="color:#00e676">$${d.tp ?? "-"}</b> &nbsp;
                🛑 SL: <b style="color:#ff4d4d">$${d.sl ?? "-"}</b>
            </p>
            <p class="meta">ATR: ${d.atr ?? "-"}</p>`;
        }

        html += `
        <div class="timeframe">
            <h3>${tf}</h3>
            <p>Price: $${d.price}</p>
            <p style="${rsiColor}">RSI: ${d.rsi ?? "-"}${d.rsi > 80 ? " ⚠️ OB" : d.rsi < 20 ? " ⚠️ OS" : ""}</p>
            <p class="${signalClass(d.signal)}">${d.signal}</p>
            <p class="meta">Bias: ${d.htf_bias ?? "-"} | Regime: ${d.regime ?? "-"}</p>
            <p class="meta">Score: BUY ${d.buy_score ?? "-"} / SELL ${d.sell_score ?? "-"}</p>
            <p class="reason">${d.reason ?? ""}</p>
            ${tradeRow}
        </div>
        `;
    }
    return html;
}

async function loadDashboard() {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 25000);

        const response = await fetch(API_URL, { signal: controller.signal });
        clearTimeout(timeout);

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        document.getElementById("btc-content").innerHTML = renderCoin(data.btc);
        document.getElementById("eth-content").innerHTML = renderCoin(data.eth);
        document.getElementById("status").innerHTML = "🟢 Live";

    } catch (err) {
        if (err.name === "AbortError") {
            console.warn("Timeout — API slow hai");
            document.getElementById("status").innerHTML = "⏳ Loading...";
        } else {
            console.error("Fetch error:", err);
            document.getElementById("status").innerHTML = "🔴 Disconnected";
        }
    }
}

loadDashboard();
setInterval(loadDashboard, 15000);
