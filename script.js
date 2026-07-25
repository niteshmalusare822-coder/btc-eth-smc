const API_URL       = "https://crypto-scanner-api-xnwd.onrender.com/api/dashboard";
const BACKTEST_URL  = "https://crypto-scanner-api-xnwd.onrender.com/api/backtest";

function signalClass(signal) {
    if (signal === "BUY")  return "signal-buy";
    if (signal === "SELL") return "signal-sell";
    return "signal-wait";
}

function renderCoin(data) {
    let html = "";
    for (const tf in data) {
        const d = data[tf];

        if (d.error) {
            html += `<div class="timeframe"><h3>${tf}</h3><p class="signal-wait">No data</p></div>`;
            continue;
        }

        // RSI color
        let rsiStyle = "";
        let rsiTag   = "";
        if (d.rsi !== null && d.rsi !== undefined) {
            if (d.rsi > 75) { rsiStyle = "color:#ff4d4d;font-weight:bold"; rsiTag = " ⚠️ OB"; }
            else if (d.rsi < 25) { rsiStyle = "color:#00e676;font-weight:bold"; rsiTag = " ⚠️ OS"; }
        }

        // Entry / TP / SL — only on BUY or SELL
        let tradeRow = "";
        if (d.signal === "BUY" || d.signal === "SELL") {
            const age = d.signal_age_seconds;
            let ageText = "🆕 Just triggered";
            let ageColor = "#00e676";
            if (age !== null && age !== undefined && age > 0) {
                if (age < 60) { ageText = `⏱️ Active ${Math.round(age)}s`; ageColor = "#00e676"; }
                else { ageText = `⏱️ Active ${Math.floor(age / 60)}m ${Math.round(age % 60)}s`; ageColor = age > 300 ? "#ffd600" : "#00e676"; }
            }
            tradeRow = `
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid #444;">
                <p class="meta" style="color:${ageColor};font-weight:bold">${ageText}</p>
                <p class="meta">📍 Entry: <b>$${d.entry ?? "-"}</b></p>
                <p class="meta">🎯 TP: <b style="color:#00e676">$${d.tp ?? "-"}</b> &nbsp; 🛑 SL: <b style="color:#ff4d4d">$${d.sl ?? "-"}</b></p>
                <p class="meta">📊 ATR: ${d.atr ?? "-"}</p>
                <p class="meta">💰 Target: ₹${d.target_profit_range_inr?.[0] ?? "-"}–₹${d.target_profit_range_inr?.[1] ?? "-"} → qty ${d.suggested_qty_for_min_profit ?? "-"}–${d.suggested_qty_for_max_profit ?? "-"}</p>
            </div>`;
        }

        // NEW: momentum awareness — always shown, even on WAIT, so "market is
        // moving" is visible separately from the filtered trade signal.
        let momColor = "#888";
        if (d.momentum_pct !== null && d.momentum_pct !== undefined) {
            if (Math.abs(d.momentum_pct) >= 1.0) momColor = d.momentum_pct > 0 ? "#00e676" : "#ff4d4d";
            else if (Math.abs(d.momentum_pct) >= 0.3) momColor = d.momentum_pct > 0 ? "#8bc34a" : "#ff8a65";
        }

        html += `
        <div class="timeframe">
            <h3>${tf}</h3>
            <p>Price: $${d.price}</p>
            <p style="${rsiStyle}">RSI: ${d.rsi ?? "-"}${rsiTag}</p>
            <p class="${signalClass(d.signal)}">${d.signal}</p>
            <p class="meta">Bias: ${d.htf_bias ?? "-"} | Regime: ${d.regime ?? "-"}</p>
            <p class="meta">Score: BUY ${d.buy_score ?? "-"} / SELL ${d.sell_score ?? "-"}</p>
            <p class="meta" style="color:${momColor}">${d.momentum_note ?? ""} (${d.momentum_pct ?? "-"}%) &nbsp; | &nbsp; This candle: ${d.last_candle_direction ?? "-"} (${d.last_candle_pct ?? "-"}%)</p>
            <p class="reason">${d.reason ?? ""}</p>
            ${tradeRow}
        </div>`;
    }
    return html;
}

// ── Backtest ─────────────────────────────────────────────
async function runBacktest(symbol, timeframe) {
    const box = document.getElementById("backtest-result");
    box.innerHTML = "⏳ Running backtest...";
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 60000);
        const res = await fetch(`${BACKTEST_URL}/${symbol}/${timeframe}`, { signal: controller.signal });
        clearTimeout(timeout);
        const data = await res.json();

        if (data.error) {
            box.innerHTML = `❌ Error: ${data.error}`;
            return;
        }

        const trades = (data.recent_trades || []).map(t => {
            const color = t.outcome === "WIN" ? "#00e676" : "#ff4d4d";
            const icon  = t.outcome === "WIN" ? "✅" : "❌";
            return `<p style="color:${color};margin:2px 0;">${icon} ${t.time} | ${t.direction} @ $${t.entry} → TP $${t.tp} | SL $${t.sl}</p>`;
        }).join("");

        const wrColor = data.win_rate >= 55 ? "#00e676" : data.win_rate >= 45 ? "#ffd600" : "#ff4d4d";

        box.innerHTML = `
        <div style="padding:12px;">
            <p><b>${data.symbol} ${data.timeframe} — Last ${data.candles_tested} candles</b></p>
            <p>Total Trades: <b>${data.total_trades}</b> &nbsp;|&nbsp;
               ✅ Wins: <b style="color:#00e676">${data.wins}</b> &nbsp;|&nbsp;
               ❌ Losses: <b style="color:#ff4d4d">${data.losses}</b></p>
            <p>Win Rate: <b style="color:${wrColor};font-size:1.2em">${data.win_rate}%</b></p>
            <p>Profit Factor: <b>${data.profit_factor ?? "-"}</b> &nbsp;|&nbsp; Expectancy: <b style="color:${data.expectancy_pct >= 0 ? '#00e676' : '#ff4d4d'}">${data.expectancy_pct}%</b> &nbsp;|&nbsp; Avg R:R: <b>${data.avg_rr ?? "-"}</b></p>
            <hr style="border-color:#444;margin:8px 0;">
            <p><b>Recent Trades:</b></p>
            ${trades || "<p>No trades found</p>"}
        </div>`;
    } catch (err) {
        if (err.name === "AbortError") {
            box.innerHTML = "⏳ Timeout — try again";
        } else {
            box.innerHTML = `❌ ${err.message}`;
        }
    }
}

// ── Dashboard ────────────────────────────────────────────
async function loadDashboard() {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 25000);
        const response = await fetch(API_URL, { signal: controller.signal });
        clearTimeout(timeout);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        document.getElementById("btc-content").innerHTML = renderCoin(data.btc);
        document.getElementById("eth-content").innerHTML = renderCoin(data.eth);
        document.getElementById("dexe-content").innerHTML = renderCoin(data.dexe);
        document.getElementById("status").innerHTML = "🟢 Live";
    } catch (err) {
        if (err.name === "AbortError") {
            document.getElementById("status").innerHTML = "⏳ Loading...";
        } else {
            console.error("Fetch error:", err);
            document.getElementById("status").innerHTML = "🔴 Disconnected";
        }
    }
}

loadDashboard();
setInterval(loadDashboard, 15000);
