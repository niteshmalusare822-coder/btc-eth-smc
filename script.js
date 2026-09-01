/* script.js — wired to the SMC multi-timeframe API.
 *
 * Written against the EXISTING index.html, so no HTML or CSS changes are
 * needed. Element ids used: #status, #viability, #btc-content, #eth-content,
 * #dexe-content, #bank-content.
 *
 * Styles are injected from here, so style.css does not need touching either.
 *
 * NOTE on the timeframe dropdown: the engine is now fixed multi-timeframe
 * (1H bias, 15M setup, 5M entry). A single-timeframe selector no longer means
 * anything, so it is disabled on load rather than silently ignored.
 */

const API = "https://crypto-scanner-api-xnwd.onrender.com";
const SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "AVAX", "LINK", "DOGE", "ADA", "DEXE", "BANK"];
const REFRESH_MS = 120000;

const CSS = `
.sig{font-size:13px;line-height:1.55}
.sig .act{display:inline-block;padding:3px 10px;border-radius:20px;
  font-size:11px;font-weight:700;letter-spacing:.05em;margin-bottom:8px}
.sig .act.buy{background:#2ea043;color:#fff}
.sig .act.sell{background:#da3633;color:#fff}
.sig .act.flat{background:#484f58;color:#fff}
.sig .px{font-size:20px;font-weight:600;margin:4px 0 8px}
.sig .chips{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px}
.sig .chip{font-size:10px;padding:3px 7px;border-radius:4px;
  border:1px solid #3a3a4e;color:#8b949e}
.sig .chip.on{color:#e6edf3;border-color:#5c6bc0}
.sig table{width:100%;border-collapse:collapse;margin:8px 0}
.sig td{padding:4px 3px;border-bottom:1px solid #2a2a3e;font-size:12px}
.sig tr.sl td{color:#da3633}
.sig tr.dead{opacity:.4}
.sig .kv{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}
.sig .kv label{display:block;color:#8b949e;font-size:10px;text-transform:uppercase}
.sig .kv b{font-size:13px}
.sig .why{color:#8b949e;font-size:12px;margin-top:8px}
.sig .src{color:#484f58;font-size:10px;margin-top:5px}
.sig .warn{background:rgba(210,153,34,.12);border:1px solid #d29922;
  color:#d29922;padding:7px;border-radius:6px;font-size:11px;margin:8px 0}
.verdict{padding:14px;border-radius:10px;border:1px solid}
.verdict.good{background:rgba(46,160,67,.1);border-color:#2ea043}
.verdict.bad{background:rgba(218,54,51,.1);border-color:#da3633}
.verdict.wait{background:rgba(92,107,192,.1);border-color:#5c6bc0}
.verdict b{font-size:14px;letter-spacing:.04em;color:#fff}
.verdict p{margin:6px 0 0;font-size:13px;color:#ccc}
.arms{width:100%;border-collapse:collapse;font-size:12px;margin:10px 0}
.arms th{color:#8b949e;font-size:10px;text-transform:uppercase;
  text-align:left;padding:5px 4px;border-bottom:1px solid #333}
.arms td{padding:5px 4px;border-bottom:1px solid #2a2a3e}
.arms tr.hero td{color:#e6edf3;font-weight:600}
.mtf-meta{display:flex;gap:14px;flex-wrap:wrap;color:#8b949e;font-size:11px;margin-top:8px}
.fine{color:#484f58;font-size:11px;margin-top:10px}
.lbl{color:#8b949e;font-size:10px;text-transform:uppercase;margin:12px 0 4px}
`;

function injectCss() {
  if (document.getElementById("sig-css")) return;
  const s = document.createElement("style");
  s.id = "sig-css";
  s.textContent = CSS;
  document.head.appendChild(s);
}

const inr = n => (n === null || n === undefined || isNaN(n)) ? "—" :
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const px = n => (n === null || n === undefined || isNaN(n)) ? "—" :
  Number(n).toLocaleString("en-US", { maximumFractionDigits: 6 });
const pc = n => (n === null || n === undefined || isNaN(n)) ? "—" :
  Number(n).toFixed(2) + "%";

function setStatus(text, colour) {
  const el = document.getElementById("status");
  if (el) { el.textContent = text; el.style.color = colour || "#8b949e"; }
}

function chip(label, value, on) {
  return `<span class="chip ${on ? "on" : ""}">${label} ${value}</span>`;
}

/* A NO_TRADE renders with its reason attached. Which timeframe disagreed is
   the useful part — a blank card tells you nothing. */
function renderFlat(s) {
  const bias = s.htf_bias_1h || "—";
  const trig = s.trigger_5m || "none";
  return `<div class="sig">
    <span class="act flat">NO TRADE</span>
    <div class="px">${px(s.price)}</div>
    <div class="chips">
      ${chip("1H", bias, bias === "BULLISH" || bias === "BEARISH")}
      ${chip("15M", s.setup_15m ? "setup" : "none", !!s.setup_15m)}
      ${chip("5M", trig, trig !== "none" && trig !== "")}
    </div>
    <div class="why">${s.reason || s.error || "no alignment"}</div>
    <div class="src">${s.source || ""}</div>
  </div>`;
}

function tpRow(tp) {
  if (!tp) return "";
  const dead = tp.reachable ? "" : "dead";
  const note = tp.reachable ? `${tp.r_multiple}R` :
    `<span style="color:#8b949e">${tp.note}</span>`;
  return `<tr class="${dead}"><td>${tp.level}</td><td>${px(tp.price)}</td>
    <td>${inr(tp.target_inr)}</td><td>${note}</td></tr>`;
}

function renderTicket(s) {
  const dir = s.action === "BUY" ? "buy" : "sell";
  const warn = s.tradeable ? "" :
    `<div class="warn">Fee is ${(s.cost_in_r * 100).toFixed(0)}% of the stop
     distance — above the 40% limit. Flagged not tradeable.</div>`;

  return `<div class="sig">
    <span class="act ${dir}">${s.action}</span>
    <div class="px">${px(s.price)}</div>
    <div class="chips">
      ${chip("1H", s.htf_bias_1h, true)}
      ${chip("15M", s.zone && s.zone.has_fvg ? "OB+FVG" : "OB", true)}
      ${chip("5M", s.trigger_5m, true)}
    </div>
    ${warn}
    <table>
      <tr><td>Entry</td><td>${px(s.entry)}</td><td colspan="2">limit at OTE</td></tr>
      <tr class="sl"><td>SL</td><td>${px(s.sl)}</td>
        <td>${inr(s.risk_inr)}</td><td>${pc(s.sl_distance_pct)}</td></tr>
      ${tpRow(s.tp1)}${tpRow(s.tp2)}${tpRow(s.tp3)}
    </table>
    <div class="kv">
      <div><label>Size</label><b>${px(s.position_size_qty)}</b></div>
      <div><label>Notional</label><b>${inr(s.notional_inr)}</b></div>
      <div><label>Margin</label><b>${inr(s.margin_inr)}</b></div>
      <div><label>Leverage</label><b>${s.leverage_used}x</b></div>
      <div><label>Risk</label><b>${inr(s.risk_inr)}</b></div>
      <div><label>R:R</label><b>${s.risk_reward ?? "—"}</b></div>
      <div><label>Fees</label><b>${inr(s.fees_inr)}</b></div>
      <div><label>Slippage</label><b>${inr(s.slippage_inr)}</b></div>
    </div>
    <div class="why">${s.reason || ""}</div>
    <div class="src">${s.source || ""} · ${s.last_closed || ""} UTC</div>
  </div>`;
}

async function loadSignals() {
  const targets = {};
  SYMBOLS.forEach(s => {
    const el = document.getElementById(s.toLowerCase() + "-content");
    targets[s] = el;
    if (el && !el.innerHTML.trim()) {
      el.innerHTML = `<div class="sig"><div class="why">Loading…</div></div>`;
    }
  });

  try {
    const r = await fetch(`${API}/api/signals`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();

    (d.results || []).forEach(s => {
      const el = targets[s.symbol];
      if (!el) return;
      el.innerHTML = (s.action === "BUY" || s.action === "SELL")
        ? renderTicket(s) : renderFlat(s);
    });

    const n = d.actionable ?? 0;
    setStatus(`🟢 Live · ${n} actionable · ${new Date().toLocaleTimeString("en-IN")}`,
      n > 0 ? "#2ea043" : "#8b949e");
  } catch (e) {
    setStatus(`🔴 Disconnected (${e.message}) — retrying`, "#da3633");
    SYMBOLS.forEach(s => {
      const el = targets[s];
      if (el) el.innerHTML = `<div class="sig"><div class="why">API unreachable</div></div>`;
    });
  }
}

/* The verdict panel loads first and sits above the signals, because whether
   the system has an edge matters more than what it happens to say today. */
async function loadViability() {
  const el = document.getElementById("viability");
  if (!el) return;
  el.innerHTML = `<div class="verdict wait"><b>MEASURING</b>
    <p>Running three arms on ETH. The first run after a cold start takes a minute.</p></div>`;
  try {
    // No timeout meant a hung request sat on MEASURING forever: fetch
    // neither resolved nor rejected, so the catch below never ran.
    const ctrl = new AbortController();
    const killer = setTimeout(() => ctrl.abort(), 120000);
    let r;
    try {
      r = await fetch(`${API}/api/report/ETH`, { signal: ctrl.signal });
    } finally {
      clearTimeout(killer);
    }
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    const v = d.verdict || {};
    el.innerHTML = `<div class="verdict ${v.profitable ? "good" : "bad"}">
      <b>${v.profitable ? "EDGE FOUND" : "NO EDGE"}</b>
      <p>${v.statement || "no verdict returned"}</p></div>`;
  } catch (e) {
    el.innerHTML = `<div class="verdict wait"><b>UNMEASURED</b>
      <p>Could not reach the report endpoint (${e.name === "AbortError" ? "timed out after 120s" : e.message}). Last recorded result: pooled OOS, 25 symbols, 374 trades, NO EDGE vs matched random.</p></div>`;
  }
}

function armRow(m) {
  if (!m || !m.trades) {
    return `<tr><td>${m ? m.arm : "—"}</td><td colspan="7">no trades</td></tr>`;
  }
  const hero = m.arm === "SMC_MTF" ? "hero" : "";
  return `<tr class="${hero}">
    <td>${m.arm}</td><td>${m.trades}</td><td>${m.win_rate_pct}%</td>
    <td>${m.profit_factor ?? "—"}</td><td>${inr(m.expectancy_inr)}</td>
    <td>${inr(m.net_pnl_inr)}</td><td>${inr(m.max_drawdown_inr)}</td>
    <td>${m.median_cost_in_r}</td></tr>`;
}

/* Called by the button in index.html. The timeframe argument is accepted for
   backward compatibility and ignored: the engine is fixed 1H/15M/5M. */
document.addEventListener("DOMContentLoaded", () => {
  injectCss();

  // the engine is fixed multi-timeframe now, so a single-TF selector is a lie
  const tf = document.getElementById("bt-tf");
  if (tf) {
    tf.innerHTML = `<option>1H bias · 15M setup · 5M entry</option>`;
    tf.disabled = true;
  }

  loadSignals();
  loadViability();
  setInterval(function() { window.location.reload(); }, 60000);
});
