const API_URL       = "https://crypto-scanner-api-xnwd.onrender.com/api/dashboard";
const BACKTEST_URL  = "https://crypto-scanner-api-xnwd.onrender.com/api/backtest";

function signalClass(signal) {
    if (signal === "BUY")  return "signal-buy";
    if (signal === "SELL") return "signal-sell";
    return "signal-wait";
}

function renderCoin(data) {
    // A missing ticker used to silently render as an empty string, which is
    // why the page could look completely blank while reporting "Live".
    if (!data || typeof data !== "object" || Object.keys(data).length === 0) {
        return `<div class="timeframe"><p class="signal-wait">⏳ Waiting for first scan…</p></div>`;
    }

    let html = "";
    for (const tf in data) {
        const d = data[tf];

        if (!d) {
            html += `<div class="timeframe"><h3>${tf}</h3><p class="signal-wait">⏳ Waiting…</p></div>`;
            continue;
        }

        if (d.pending) {
            html += `<div class="timeframe"><h3>${tf}</h3><p class="signal-wait">⏳ Scanning…</p></div>`;
            continue;
        }

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

        // NEW: blow-off exhaustion banner
        let boRow = "";
        if (d.blowoff && d.blowoff.active) {
            const lv = d.blowoff.levels || {};
            const tag = d.blowoff.confirmed ? "CONFIRMED — climax low broken" : "ACTIVE — not confirmed yet";
            boRow = `<p class="meta" style="color:#ff9100;font-weight:bold;">
                🚫 BLOW-OFF ${tag} (score ${d.blowoff.score ?? "-"})<br>
                <span style="font-weight:normal">invalidation $${lv.invalidation?.toFixed?.(5) ?? "-"} &nbsp;|&nbsp; 0.618 $${lv.fib_618?.toFixed?.(5) ?? "-"}</span>
            </p>`;
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
            ${boRow}
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
let inFlight = false;          // stops overlapping polls piling up on the server
let lastGood = null;           // last successful payload
let lastGoodAt = null;         // when we received it

function paint(data) {
    document.getElementById("btc-content").innerHTML  = renderCoin(data.btc);
    document.getElementById("eth-content").innerHTML  = renderCoin(data.eth);
    document.getElementById("dexe-content").innerHTML = renderCoin(data.dexe);
    document.getElementById("bank-content").innerHTML = renderCoin(data.bank);
}

// A failed poll should never wipe the screen. Repaint what we had and label
// it clearly as stale so it is obvious the numbers are not current.
function paintStale(reason) {
    const statusEl = document.getElementById("status");
    if (!lastGood) {
        statusEl.innerHTML = `🔴 ${reason} — no data yet, retrying`;
        return;
    }
    paint(lastGood);
    const secs = Math.round((Date.now() - lastGoodAt) / 1000);
    statusEl.innerHTML = `🟠 ${reason} — showing data from ${secs}s ago`;
}

async function loadDashboard() {
    if (inFlight) return;      // previous request still running - skip this tick
    inFlight = true;

    const statusEl = document.getElementById("status");
    try {
        const controller = new AbortController();
        // 90s, not 40s: a cold Render instance needs ~60s to answer the very
        // first request. Once warm the response is near-instant anyway.
        const timeout = setTimeout(() => controller.abort(), 90000);
        const response = await fetch(API_URL, { signal: controller.signal, cache: "no-store" });
        clearTimeout(timeout);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        if (data.warming) {
            const detail = data.progress ? ` — ${data.progress}` : "";
            statusEl.innerHTML = `⏳ First scan running${detail}`;
            if (data.error) statusEl.innerHTML += `<br><span style="color:#ff4d4d">backend error: ${data.error}</span>`;
            return;
        }

        lastGood = data;
        lastGoodAt = Date.now();
        paint(data);

        const now = new Date().toLocaleTimeString();
        const age = data._age_seconds;
        // The scanner now rests ~60s+ between passes, so 45s was flagging
        // healthy data as stale on every other poll.
        const stale = age > 180;
        statusEl.innerHTML = stale
            ? `🟡 Live (updated ${now}) — scan data ${age}s old`
            : `🟢 Live (updated ${now})`;
        if (data._error) {
            statusEl.innerHTML += `<br><span style="color:#ff9100">last pass warning: ${data._error}</span>`;
        }
    } catch (err) {
        if (err.name === "AbortError") {
            paintStale("Server slow to respond");
        } else {
            console.error("Fetch error:", err);
            paintStale(`Disconnected (${err.message})`);
        }
    } finally {
        inFlight = false;
    }
}

loadDashboard();
setInterval(loadDashboard, 15000);
