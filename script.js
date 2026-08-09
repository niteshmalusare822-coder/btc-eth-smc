const API_URL       = "https://crypto-scanner-api-xnwd.onrender.com/api/dashboard";
const BACKTEST_URL  = "https://crypto-scanner-api-xnwd.onrender.com/api/backtest";

function signalClass(signal) {
    if (signal === "BUY")  return "signal-buy";
    if (signal === "SELL") return "signal-sell";
    return "signal-wait";
}

const VIABILITY_URL = "https://crypto-scanner-api-xnwd.onrender.com/api/viability";

// The panel that answers "is this worth trading yet?". Deliberately sits at
// the top of the page: on a Rs.3,000 account the scanner's job is to prove
// or disprove itself, not to hand out trades.
async function loadViability() {
    const el = document.getElementById("viability");
    if (!el) return;
    try {
        const res = await fetch(VIABILITY_URL, { cache: "no-store" });
        const v = await res.json();
        if (v.error) { el.innerHTML = ""; return; }

        const colour = { COLLECTING: "#ff9100", INCONCLUSIVE: "#ff9100",
                         DISPROVEN: "#ff4d4d", CONFIRMED: "#00e676" }[v.stage] || "#888";

        let body = `<p style="margin:6px 0 0;font-size:13px;">${v.verdict}</p>`;

        if (v.stage === "COLLECTING") {
            const pct = v.progress_pct || 0;
            body += `<div style="margin-top:8px;height:8px;background:#333;border-radius:4px;overflow:hidden;">
                        <div style="width:${pct}%;height:100%;background:${colour};"></div>
                     </div>
                     <p style="margin:4px 0 0;font-size:12px;color:#888;">
                        ${v.resolved_signals} / ${v.signals_needed_for_verdict} signals · ${pct}%
                     </p>`;
        }

        if (v.stage === "CONFIRMED" && v.projection_at_current_capital) {
            const p = v.projection_at_current_capital;
            body += `<p style="margin:6px 0 0;font-size:13px;">
                        At ₹${v.capital_inr.toLocaleString("en-IN")}: <b>₹${p.expectancy_per_trade_inr}</b>/trade,
                        <b>₹${p.per_month_inr.toLocaleString("en-IN")}</b>/month at ${p.trades_per_day} trade/day
                     </p>`;
            if (v.capital_needed_for_target) {
                body += `<p style="margin:4px 0 0;font-size:12px;color:#888;">
                            ₹${v.target_monthly_inr.toLocaleString("en-IN")}/month would need
                            ₹${Number(v.capital_needed_for_target).toLocaleString("en-IN")} capital.
                         </p>`;
            }
        }

        el.innerHTML = `<div style="padding:10px;border:1px solid ${colour};border-radius:6px;margin-bottom:12px;">
            <p style="margin:0;font-weight:bold;color:${colour};">${v.stage}
               <span style="font-weight:normal;color:#888;font-size:12px;">
                 · breakeven ${v.breakeven_win_rate_pct}% · R:R ${v.reward_risk}
               </span></p>
            ${body}
        </div>`;
    } catch (err) {
        console.error("viability fetch failed:", err);
    }
}

// Risk-first sizing. The only quantity shown is the one whose downside is
// capped. The old "qty for ₹500 profit" line is deliberately gone — it had no
// upper bound and was the thing recommending 4x-oversized positions.
function renderConfluence(d) {
    const detail = d.confluence_detail;

    if (!detail) return "";

    const labels = {
        candle_pattern: "Candle Pattern",
        structure_break: "Structure Break",
        divergence: "Divergence",
        sweep_with_equal_levels: "Liquidity Sweep + Equal Levels",
        fvg_proximity: "FVG Proximity",
        inducement: "Inducement",
        htf_ema_alignment: "HTF EMA Alignment"
    };

    const rows = Object.entries(detail).map(([key, value]) => {
        const status = value.fired ? "✓" : "—";
        const contribution = Number(value.contributed ?? 0).toFixed(1);

        return `<div style="font-size:12px;color:${value.fired ? "#ddd" : "#777"};">
            ${status} ${labels[key] ?? key}: ${contribution}
        </div>`;
    }).join("");

    return `
        <div style="margin-top:6px;padding:7px;border:1px solid #333;border-radius:4px;">
            <p class="meta" style="margin:0 0 4px;">
                <b>Confluence:</b>
                ${d.confluence_score ?? "-"} / ${d.confluence_threshold ?? "-"}
            </p>
            ${rows}
        </div>
    `;
}

    const levColor = s.leverage_needed > 3 ? "#ff9100" : "#00e676";
    const need = d.capital_needed_for_500;
    const needLine = (need && need > s.capital_inr)
        ? `<p class="meta" style="color:#888;margin:4px 0 0;">₹500/trade would need ₹${Number(need).toLocaleString("en-IN")} capital at this risk level.</p>`
        : "";

    return `<div style="margin-top:8px;padding:8px;border:1px solid #444;border-radius:4px;">
        <p class="meta" style="margin:0;">📦 Qty: <b>${s.qty}</b> &nbsp; (notional ₹${s.notional_inr.toLocaleString("en-IN")})</p>
        <p class="meta" style="margin:4px 0 0;">🛑 Risk: <b style="color:#ff4d4d">₹${s.risk_inr}</b> (${s.risk_pct_of_capital}% of ₹${s.capital_inr})
           &nbsp;|&nbsp; ⚙️ <b style="color:${levColor}">${s.leverage_needed}x</b></p>
        <p class="meta" style="margin:4px 0 0;">🎯 If TP hits: <b style="color:#00e676">₹${s.profit_at_tp_inr}</b> &nbsp; (R:R ${s.reward_risk}, fees ₹${s.fee_cost_inr})</p>
        <p class="meta" style="margin:4px 0 0;color:#888;">${s.note}</p>
        ${needLine}
    </div>`;
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
                ${renderSize(d)}
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
            <p class="meta">Bias: ${d.htf_bias ?? "-"} | Regime: ${d.regime_entry ?? d.regime ?? "-"} | Confirm: ${d.regime_confirm ?? "-"}</p>
            <p class="meta">Score: BUY ${d.buy_score ?? "-"} / SELL ${d.sell_score ?? "-"}</p>
            <p class="meta" style="color:${momColor}">${d.momentum_note ?? ""} (${d.momentum_pct ?? "-"}%) &nbsp; | &nbsp; This candle: ${d.last_candle_direction ?? "-"} (${d.last_candle_pct ?? "-"}%)</p>
            ${boRow}
            ${renderConfluence(d)}
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
            // If we already had data, the backend just restarted. The numbers
            // still on screen are now orphaned, so age-label them rather than
            // leaving them looking current.
            if (lastGood) {
                const secs = Math.round((Date.now() - lastGoodAt) / 1000);
                statusEl.innerHTML = `⏳ Backend restarted, rescanning${detail} — numbers below are ${secs}s old`;
            } else {
                statusEl.innerHTML = `⏳ First scan running${detail}`;
            }
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
// Journal stats move slowly; polling this as often as prices would just burn
// the free tier's CPU for numbers that change a few times an hour.
loadViability();
setInterval(loadViability, 120000);
