```javascript
/* script.js — SMC Multi-Timeframe Dashboard
 *
 * Existing index.html ke saath wired.
 *
 * Timeframes:
 *   1H  = Bias
 *   15M = Setup
 *   5M  = Entry
 *
 * API:
 *   /api/signals
 *   /api/report/ETH
 *
 * Market Sentiment:
 *   Alternative.me Fear & Greed Index
 */

const API = "https://crypto-scanner-api-xnwd.onrender.com";

const SYMBOLS = [
  "BTC",
  "ETH",
  "SOL",
  "XRP",
  "AVAX",
  "LINK",
  "DOGE",
  "ADA",
  "DEXE",
  "BANK"
];

const REFRESH_MS = 120000; // 2 minutes


/* =========================================================
   CSS
   ========================================================= */

const CSS = `
.sig {
  font-size: 13px;
  line-height: 1.55;
}

.sig .act {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .05em;
  margin-bottom: 8px;
}

.sig .act.buy {
  background: #2ea043;
  color: #fff;
}

.sig .act.sell {
  background: #da3633;
  color: #fff;
}

.sig .act.flat {
  background: #484f58;
  color: #fff;
}

.sig .px {
  font-size: 20px;
  font-weight: 600;
  margin: 4px 0 8px;
}

.sig .chips {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.sig .chip {
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 4px;
  border: 1px solid #3a3a4e;
  color: #8b949e;
}

.sig .chip.on {
  color: #e6edf3;
  border-color: #5c6bc0;
}

.sig table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.sig td {
  padding: 4px 3px;
  border-bottom: 1px solid #2a2a3e;
  font-size: 12px;
}

.sig tr.sl td {
  color: #da3633;
}

.sig tr.dead {
  opacity: .4;
}

.sig .kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin: 8px 0;
}

.sig .kv label {
  display: block;
  color: #8b949e;
  font-size: 10px;
  text-transform: uppercase;
}

.sig .kv b {
  font-size: 13px;
}

.sig .why {
  color: #8b949e;
  font-size: 12px;
  margin-top: 8px;
}

.sig .src {
  color: #484f58;
  font-size: 10px;
  margin-top: 5px;
}

.sig .warn {
  background: rgba(210, 153, 34, .12);
  border: 1px solid #d29922;
  color: #d29922;
  padding: 7px;
  border-radius: 6px;
  font-size: 11px;
  margin: 8px 0;
}

.verdict {
  padding: 14px;
  border-radius: 10px;
  border: 1px solid;
}

.verdict.good {
  background: rgba(46, 160, 67, .1);
  border-color: #2ea043;
}

.verdict.bad {
  background: rgba(218, 54, 51, .1);
  border-color: #da3633;
}

.verdict.wait {
  background: rgba(92, 107, 192, .1);
  border-color: #5c6bc0;
}

.verdict b {
  font-size: 14px;
  letter-spacing: .04em;
  color: #fff;
}

.verdict p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #ccc;
}

.arms {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 10px 0;
}

.arms th {
  color: #8b949e;
  font-size: 10px;
  text-transform: uppercase;
  text-align: left;
  padding: 5px 4px;
  border-bottom: 1px solid #333;
}

.arms td {
  padding: 5px 4px;
  border-bottom: 1px solid #2a2a3e;
}

.arms tr.hero td {
  color: #e6edf3;
  font-weight: 600;
}

.mtf-meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: #8b949e;
  font-size: 11px;
  margin-top: 8px;
}

.fine {
  color: #484f58;
  font-size: 11px;
  margin-top: 10px;
}

.lbl {
  color: #8b949e;
  font-size: 10px;
  text-transform: uppercase;
  margin: 12px 0 4px;
}
`;


/* =========================================================
   CSS INJECTION
   ========================================================= */

function injectCss() {
  if (document.getElementById("sig-css")) {
    return;
  }

  const style = document.createElement("style");

  style.id = "sig-css";
  style.textContent = CSS;

  document.head.appendChild(style);
}


/* =========================================================
   FORMATTERS
   ========================================================= */

function inr(n) {
  if (
    n === null ||
    n === undefined ||
    Number.isNaN(Number(n))
  ) {
    return "—";
  }

  return (
    "₹" +
    Number(n).toLocaleString("en-IN", {
      maximumFractionDigits: 0
    })
  );
}


function px(n) {
  if (
    n === null ||
    n === undefined ||
    Number.isNaN(Number(n))
  ) {
    return "—";
  }

  return Number(n).toLocaleString("en-US", {
    maximumFractionDigits: 6
  });
}


function pc(n) {
  if (
    n === null ||
    n === undefined ||
    Number.isNaN(Number(n))
  ) {
    return "—";
  }

  return Number(n).toFixed(2) + "%";
}


/* =========================================================
   STATUS
   ========================================================= */

function setStatus(text, colour) {
  const el = document.getElementById("status");

  if (!el) {
    return;
  }

  el.textContent = text;
  el.style.color = colour || "#8b949e";
}


/* =========================================================
   CHIP
   ========================================================= */

function chip(label, value, on) {
  const displayValue =
    value === null ||
    value === undefined ||
    value === ""
      ? "—"
      : value;

  return `
    <span class="chip ${on ? "on" : ""}">
      ${label} ${displayValue}
    </span>
  `;
}


/* =========================================================
   NO TRADE
   ========================================================= */

function renderFlat(s) {
  const bias = s.htf_bias_1h || "—";
  const trigger = s.trigger_5m || "none";

  return `
    <div class="sig">

      <span class="act flat">
        NO TRADE
      </span>

      <div class="px">
        ${px(s.price)}
      </div>

      <div class="chips">

        ${chip(
          "1H",
          bias,
          bias === "BULLISH" ||
          bias === "BEARISH"
        )}

        ${chip(
          "15M",
          s.setup_15m
            ? "setup"
            : "none",
          Boolean(s.setup_15m)
        )}

        ${chip(
          "5M",
          trigger,
          trigger !== "none" &&
          trigger !== ""
        )}

      </div>

      <div class="why">
        ${
          s.reason ||
          s.error ||
          "no alignment"
        }
      </div>

      <div class="src">
        ${s.source || ""}
      </div>

    </div>
  `;
}


/* =========================================================
   TAKE PROFIT ROW
   ========================================================= */

function tpRow(tp) {
  if (!tp) {
    return "";
  }

  const reachable = Boolean(tp.reachable);

  const deadClass =
    reachable
      ? ""
      : "dead";

  const note = reachable
    ? `${tp.r_multiple ?? "—"}R`
    : `
      <span style="color:#8b949e">
        ${tp.note || "not reachable"}
      </span>
    `;

  return `
    <tr class="${deadClass}">

      <td>
        ${tp.level || "TP"}
      </td>

      <td>
        ${px(tp.price)}
      </td>

      <td>
        ${inr(tp.target_inr)}
      </td>

      <td>
        ${note}
      </td>

    </tr>
  `;
}


/* =========================================================
   TRADE TICKET
   ========================================================= */

function renderTicket(s) {
  const direction =
    s.action === "BUY"
      ? "buy"
      : "sell";

  const costInR =
    Number(s.cost_in_r);

  const warning =
    s.tradeable === false
      ? `
        <div class="warn">
          Fee is ${
            Number.isFinite(costInR)
              ? (costInR * 100).toFixed(0)
              : "—"
          }% of the stop distance —
          above the 40% limit.
          Flagged not tradeable.
        </div>
      `
      : "";

  const zone =
    s.zone && s.zone.has_fvg
      ? "OB+FVG"
      : "OB";

  return `
    <div class="sig">

      <span class="act ${direction}">
        ${s.action || "—"}
      </span>

      <div class="px">
        ${px(s.price)}
      </div>

      <div class="chips">

        ${chip(
          "1H",
          s.htf_bias_1h || "—",
          true
        )}

        ${chip(
          "15M",
          zone,
          true
        )}

        ${chip(
          "5M",
          s.trigger_5m || "—",
          true
        )}

      </div>

      ${warning}

      <table>

        <tr>
          <td>Entry</td>
          <td>${px(s.entry)}</td>
          <td colspan="2">
            limit at OTE
          </td>
        </tr>

        <tr class="sl">
          <td>SL</td>
          <td>${px(s.sl)}</td>
          <td>${inr(s.risk_inr)}</td>
          <td>${pc(s.sl_distance_pct)}</td>
        </tr>

        ${tpRow(s.tp1)}
        ${tpRow(s.tp2)}
        ${tpRow(s.tp3)}

      </table>

      <div class="kv">

        <div>
          <label>Size</label>
          <b>
            ${px(s.position_size_qty)}
          </b>
        </div>

        <div>
          <label>Notional</label>
          <b>
            ${inr(s.notional_inr)}
          </b>
        </div>

        <div>
          <label>Margin</label>
          <b>
            ${inr(s.margin_inr)}
          </b>
        </div>

        <div>
          <label>Leverage</label>
          <b>
            ${s.leverage_used ?? "—"}x
          </b>
        </div>

        <div>
          <label>Risk</label>
          <b>
            ${inr(s.risk_inr)}
          </b>
        </div>

        <div>
          <label>R:R</label>
          <b>
            ${s.risk_reward ?? "—"}
          </b>
        </div>

        <div>
          <label>Fees</label>
          <b>
            ${inr(s.fees_inr)}
          </b>
        </div>

        <div>
          <label>Slippage</label>
          <b>
            ${inr(s.slippage_inr)}
          </b>
        </div>

      </div>

      <div class="why">
        ${s.reason || ""}
      </div>

      <div class="src">
        ${s.source || ""}
        ${
          s.last_closed
            ? " · " +
              s.last_closed +
              " UTC"
            : ""
        }
      </div>

    </div>
  `;
}


/* =========================================================
   SIGNAL API
   ========================================================= */

async function loadSignals() {
  const targets = {};

  SYMBOLS.forEach((symbol) => {

    const element =
      document.getElementById(
        symbol.toLowerCase() +
        "-content"
      );

    targets[symbol] = element;

    if (
      element &&
      !element.innerHTML.trim()
    ) {
      element.innerHTML = `
        <div class="sig">
          <div class="why">
            Loading…
          </div>
        </div>
      `;
    }

  });


  try {

    const response = await fetch(
      `${API}/api/signals`,
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        "HTTP " + response.status
      );
    }

    const data =
      await response.json();

    const results =
      Array.isArray(data.results)
        ? data.results
        : [];


    results.forEach((signal) => {

      const element =
        targets[signal.symbol];

      if (!element) {
        return;
      }

      if (
        signal.action === "BUY" ||
        signal.action === "SELL"
      ) {

        element.innerHTML =
          renderTicket(signal);

      } else {

        element.innerHTML =
          renderFlat(signal);

      }

    });


    const actionable =
      Number(
        data.actionable ?? 0
      );

    const currentTime =
      new Date().toLocaleTimeString(
        "en-IN"
      );

    setStatus(
      `🟢 Live · ${actionable} actionable · ${currentTime}`,
      actionable > 0
        ? "#2ea043"
        : "#8b949e"
    );


  } catch (error) {

    console.error(
      "Signals load error:",
      error
    );

    setStatus(
      `🔴 Disconnected (${error.message}) — retrying`,
      "#da3633"
    );


    SYMBOLS.forEach((symbol) => {

      const element =
        targets[symbol];

      if (!element) {
        return;
      }

      element.innerHTML = `
        <div class="sig">
          <div class="why">
            API unreachable
          </div>
        </div>
      `;

    });

  }
}


/* =========================================================
   VIABILITY / EDGE REPORT
   ========================================================= */

async function loadViability() {
  const element =
    document.getElementById(
      "viability"
    );

  if (!element) {
    return;
  }


  element.innerHTML = `
    <div class="verdict wait">

      <b>MEASURING</b>

      <p>
        Running three arms on ETH.
        The first run after a cold start
        may take a minute.
      </p>

    </div>
  `;


  const controller =
    new AbortController();

  const timeoutId =
    setTimeout(
      () => controller.abort(),
      120000
    );


  try {

    const response =
      await fetch(
        `${API}/api/report/ETH`,
        {
          signal:
            controller.signal,

          cache:
            "no-store"
        }
      );


    if (!response.ok) {
      throw new Error(
        "HTTP " +
        response.status
      );
    }


    const data =
      await response.json();

    const verdict =
      data.verdict || {};


    element.innerHTML = `
      <div class="verdict ${
        verdict.profitable
          ? "good"
          : "bad"
      }">

        <b>
          ${
            verdict.profitable
              ? "EDGE FOUND"
              : "NO EDGE"
          }
        </b>

        <p>
          ${
            verdict.statement ||
            "No verdict returned"
          }
        </p>

      </div>
    `;


  } catch (error) {

    console.error(
      "Viability load error:",
      error
    );


    element.innerHTML = `
      <div class="verdict wait">

        <b>UNMEASURED</b>

        <p>
          Could not reach the report endpoint
          (
          ${
            error.name ===
            "AbortError"
              ? "timed out after 120s"
              : error.message
          }
          ).
          Last recorded result:
          pooled OOS, 25 symbols,
          374 trades,
          NO EDGE vs matched random.
        </p>

      </div>
    `;


  } finally {

    clearTimeout(timeoutId);

  }
}


/* =========================================================
   ARM ROW
   ========================================================= */

function armRow(m) {

  if (
    !m ||
    !m.trades
  ) {

    return `
      <tr>

        <td>
          ${m ? m.arm : "—"}
        </td>

        <td colspan="7">
          no trades
        </td>

      </tr>
    `;

  }


  const hero =
    m.arm === "SMC_MTF"
      ? "hero"
      : "";


  return `
    <tr class="${hero}">

      <td>
        ${m.arm}
      </td>

      <td>
        ${m.trades}
      </td>

      <td>
        ${m.win_rate_pct ?? "—"}%
      </td>

      <td>
        ${m.profit_factor ?? "—"}
      </td>

      <td>
        ${inr(m.expectancy_inr)}
      </td>

      <td>
        ${inr(m.net_pnl_inr)}
      </td>

      <td>
        ${inr(m.max_drawdown_inr)}
      </td>

      <td>
        ${m.median_cost_in_r ?? "—"}
      </td>

    </tr>
  `;
}


/* =========================================================
   MARKET SENTIMENT
   ========================================================= */

async function loadMarketSentiment() {

  const element =
    document.getElementById(
      "sentiment-text"
    );

  if (!element) {

    console.warn(
      "sentiment-text element not found"
    );

    return;
  }


  try {

    const response =
      await fetch(
        "https://api.alternative.me/fng/",
        {
          cache: "no-store"
        }
      );


    if (!response.ok) {
      throw new Error(
        "HTTP " +
        response.status
      );
    }


    const result =
      await response.json();


    if (
      result &&
      Array.isArray(result.data) &&
      result.data.length > 0
    ) {

      const sentiment =
        result.data[0]
          .value_classification ||
        "Unknown";

      const value =
        result.data[0].value ??
        "—";


      element.innerText =
        `${sentiment} (${value}/100)`;


    } else {

      element.innerText =
        "Unavailable";

    }


  } catch (error) {

    console.error(
      "Sentiment load error:",
      error
    );

    element.innerText =
      "Unavailable";

  }
}


/* =========================================================
   TIMEFRAME SELECTOR
   ========================================================= */

function setupTimeframeSelector() {

  const timeframe =
    document.getElementById(
      "bt-tf"
    );

  if (!timeframe) {
    return;
  }


  timeframe.innerHTML = `
    <option>
      1H bias · 15M setup · 5M entry
    </option>
  `;

  timeframe.disabled = true;
}


/* =========================================================
   INITIAL LOAD
   ========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    console.log(
      "SMC Dashboard starting..."
    );

    injectCss();

    setupTimeframeSelector();


    /* Initial API calls */

    loadSignals();

    loadViability();

    loadMarketSentiment();


    /* =====================================================
       SINGLE REFRESH LOOP
       ===================================================== */

    setInterval(
      () => {

        console.log(
          "Refreshing dashboard..."
        );

        loadSignals();

        loadViability();

        loadMarketSentiment();

      },
      REFRESH_MS
    );

  }
);
```
