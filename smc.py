"""
smc.py — Sweep -> Shift. Standalone. No imports from scanner.py.

Everything this file needs is inside it: data fetch, structure detection,
signal generation, position sizing and backtest.

────────────────────────────────────────────────────────────────────────
WHAT CAME FROM THE THREE COURSES (stated, not inferred)
────────────────────────────────────────────────────────────────────────
  Entry model
    A liquidity sweep is a wick through a prior swing that CLOSES back
    inside it. After the sweep, wait for structure to shift the other way
    before entering — "micro market structure break". All three sources.

  Stops and targets
    The stop goes beyond the swept extreme. The target is the opposite
    side's liquidity. Neither is a fixed distance.

  Risk and reward           (NB2 and NB3, explicit)
    Risk 1% of capital per trade.
    Target 1.5R to 2R. NB3: "not being a 10R hero".

  When NOT to trade         (NB1, NB2, NB3, explicit)
    Consolidation / sideways price action.
    Choppy directionless days with no clear bias.
    Low-liquidity markets.
    When no clear target exists — "if the price has no purpose to move
    up or down why would you even trade".

  Expected frequency        (NB3, explicit)
    One or two trades a day at most. One to five per week.
    If this file fires more often than that on a given symbol, the
    settings are wrong, not the market.

────────────────────────────────────────────────────────────────────────
WHAT IS INVENTED HERE — the videos never gave a number for these
────────────────────────────────────────────────────────────────────────
    SWING_LOOKBACK    bars either side that define a swing point
    SL_BUFFER_PCT     how far past the swept extreme the stop sits
    SHIFT_MAX_BARS    how long a sweep stays valid
    RANGE_MIN_PCT     how wide a range must be to not count as consolidation
    TIMEOUT_BARS      when to give up on an unresolved trade

    Five numbers, all in PARAMS below. That is the entire tuning surface
    and it is written down so it cannot quietly grow. Change one at a
    time and re-measure, or you are fitting noise.

────────────────────────────────────────────────────────────────────────
USAGE
    python3 smc.py                        BTC 15m backtest
    python3 smc.py ETH/USDT:USDT 15m
    python3 smc.py BTC/USDT:USDT 15m live

    from smc import signal, backtest
    signal("BTC/USDT:USDT", "15m")
    backtest("BTC/USDT:USDT", "15m")

⚠️  Educational tool. A backtest is not a forecast. Paper-trade first.
"""

import sys
import time as _t

import numpy as np
import pandas as pd
import requests

try:
    import ccxt
except ImportError:
    ccxt = None


# ══════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════
PARAMS = {
    # ── invented (see header) ──
    "SWING_LOOKBACK": 5,
    "SL_BUFFER_PCT": 0.05,
    "SHIFT_MAX_BARS": 6,
    "RANGE_MIN_PCT": 0.8,
    "TIMEOUT_BARS": 40,

    # ── from the sources ──
    "MIN_RR": 1.5,            # NB3: 1.5R to 2R
    "OTE_RETRACE": 0.70,      # NB3: enter on the 70-80% retracement
    "FILL_MAX_BARS": 12,      # invented: how long a limit order stays live
    "RISK_PCT": 1.0,          # NB2 and NB3: 1% of capital
    "ROUND_TRIP_COST_PCT": 0.10,   # taker both sides + spread. VERIFY on CoinDCX.
}

CAPITAL_INR = 3000.0
USDT_INR = 102.0
MAX_LEVERAGE = 5.0

COINDCX_PAIR = {
    "BTC/USDT:USDT": "B-BTC_USDT",
    "ETH/USDT:USDT": "B-ETH_USDT",
    "DEXE/USDT:USDT": "B-DEXE_USDT",
    "BANK/USDT:USDT": "B-BANK_USDT",
}
COINDCX_RES = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240"}
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


# ══════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════
def _from_coindcx(ticker, timeframe, limit):
    pair = COINDCX_PAIR.get(ticker)
    res = COINDCX_RES.get(timeframe)
    secs = TF_SECONDS.get(timeframe)
    if not (pair and res and secs):
        return None, None
    to_t = int(_t.time())
    try:
        r = requests.get(
            "https://public.coindcx.com/market_data/candlesticks",
            params={"pair": pair, "from": to_t - secs * (limit + 5),
                    "to": to_t, "resolution": res, "pcode": "f"},
            timeout=15)
        r.raise_for_status()
        data = r.json()
        candles = data.get("data", data) if isinstance(data, dict) else data
        if not candles or len(candles) < 100:
            return None, None
        rows = []
        for c in candles:
            ts = c.get("time", c.get("t"))
            o, h = c.get("open", c.get("o")), c.get("high", c.get("h"))
            l, cl = c.get("low", c.get("l")), c.get("close", c.get("c"))
            v = c.get("volume", c.get("v", 0))
            if None in (ts, o, h, l, cl):
                continue
            rows.append([ts, o, h, l, cl, v])
        if len(rows) < 100:
            return None, None
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        unit = "ms" if df["timestamp"].iloc[0] > 10 ** 12 else "s"
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit=unit)
        df = df.set_index("timestamp").astype(float).sort_index()
        return df.tail(limit), "coindcx"
    except Exception:
        return None, None


def _from_ccxt(ticker, timeframe, limit):
    if ccxt is None:
        return None, None
    for ex_id in ("mexc", "bybit", "okx", "gateio"):
        try:
            ex = getattr(ccxt, ex_id)({"enableRateLimit": True, "timeout": 15000})
            raw = ex.fetch_ohlcv(ticker, timeframe, limit=limit)
            if not raw or len(raw) < 100:
                continue
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp").astype(float).sort_index()
            return df.tail(limit), ex_id
        except Exception:
            continue
    return None, None


def fetch(ticker, timeframe, limit=3000):
    """CoinDCX first — that is where the trade actually happens."""
    df, src = _from_coindcx(ticker, timeframe, limit)
    if df is not None:
        return df, src
    return _from_ccxt(ticker, timeframe, limit)


# ══════════════════════════════════════════════════════════════════════
# STRUCTURE
# ══════════════════════════════════════════════════════════════════════
def swing_points(df, lb):
    """Last confirmed swing high and low, as known at each bar.

    A swing high needs `lb` bars on BOTH sides, so it is only knowable lb
    bars after it prints. The shift(lb) is what enforces that. Without it
    the backtest sees pivots that live trading cannot, and every number
    this file produces would be fiction.
    """
    high, low = df["high"], df["low"]
    win = lb * 2 + 1
    is_h = high == high.rolling(win, center=True).max()
    is_l = low == low.rolling(win, center=True).min()
    return (high.where(is_h).shift(lb).ffill(),
            low.where(is_l).shift(lb).ffill())


def swing_lists(df, lb):
    """Every confirmed swing, as (bar_it_became_knowable, price).

    swing_points() only ever hands back the MOST RECENT swing. That is not
    enough to pick a target: after price closes above the last swing high,
    that high is behind us, and aiming at it means aiming below the entry.
    The target has to be the next pool of liquidity that has NOT been taken
    yet, which means searching further back through the confirmed swings.
    """
    high, low = df["high"], df["low"]
    win = lb * 2 + 1
    is_h = (high == high.rolling(win, center=True).max()).fillna(False)
    is_l = (low == low.rolling(win, center=True).min()).fillna(False)

    hs, ls = [], []
    hv, lv = high.values, low.values
    for k in range(len(df)):
        if is_h.iloc[k]:
            hs.append((k + lb, float(hv[k])))     # knowable lb bars later
        if is_l.iloc[k]:
            ls.append((k + lb, float(lv[k])))
    return hs, ls


def _next_liquidity_above(swing_highs, bar, price):
    """Nearest confirmed swing high sitting ABOVE price. None if there is
    no untaken liquidity overhead — which is itself a reason not to trade:
    'if the price has no purpose to move up or down why would you even
    trade' (NB3)."""
    cands = [v for (b, v) in swing_highs if b <= bar and v > price]
    return min(cands) if cands else None


def _next_liquidity_below(swing_lows, bar, price):
    """Mirror image: nearest confirmed swing low below price."""
    cands = [v for (b, v) in swing_lows if b <= bar and v < price]
    return max(cands) if cands else None


def sweeps(df, sh, sl):
    """Wick through a prior swing, close back inside it."""
    psh, psl = sh.shift(1), sl.shift(1)
    hi_sweep = ((df["high"] > psh) & (df["close"] < psh)).fillna(False)
    lo_sweep = ((df["low"] < psl) & (df["close"] > psl)).fillna(False)
    return hi_sweep, lo_sweep


def shifts(df, sh, sl):
    """Close beyond the opposite swing — price proving intent."""
    up = (df["close"] > sh.shift(1)).fillna(False)
    dn = (df["close"] < sl.shift(1)).fillna(False)
    return up, dn


def is_consolidation(df, lb, min_pct):
    """The videos all say the same thing: do not trade sideways price.

    Measured as the recent swing range expressed as a percentage of price.
    A range narrower than min_pct has nowhere to go, so there is no target
    worth paying fees to reach.
    """
    win = lb * 4
    hi = df["high"].rolling(win).max()
    lo = df["low"].rolling(win).min()
    width = (hi - lo) / df["close"] * 100
    return (width < min_pct).fillna(True)


# ══════════════════════════════════════════════════════════════════════
# SETUPS
# ══════════════════════════════════════════════════════════════════════
def find_setups(df, p):
    """Every sweep -> shift setup, with structural stop and target."""
    lb = p["SWING_LOOKBACK"]
    sh, sl = swing_points(df, lb)
    hi_sw, lo_sw = sweeps(df, sh, sl)
    up, dn = shifts(df, sh, sl)
    flat = is_consolidation(df, lb, p["RANGE_MIN_PCT"])
    swing_highs, swing_lows = swing_lists(df, lb)

    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    buf = p["SL_BUFFER_PCT"] / 100.0
    n = len(df)

    out = []
    pend_long = pend_short = None

    for i in range(lb * 4 + 2, n):
        if lo_sw.iloc[i]:
            pend_long = (i, lows[i])
        if hi_sw.iloc[i]:
            pend_short = (i, highs[i])

        if pend_long and i - pend_long[0] > p["SHIFT_MAX_BARS"]:
            pend_long = None
        if pend_short and i - pend_short[0] > p["SHIFT_MAX_BARS"]:
            pend_short = None

        if flat.iloc[i]:
            continue

        if pend_long and up.iloc[i] and i > pend_long[0]:
            # The shift bar closed ABOVE the last swing high, so that high is
            # already taken. Aim at the next one that is not.
            tgt = _next_liquidity_above(swing_highs, i, closes[i])
            leg_low = pend_long[1]
            leg_high = float(highs[pend_long[0]:i + 1].max())
            if tgt is not None and leg_high > leg_low:
                out.append({"bar": i, "dir": "BUY", "sweep_bar": pend_long[0],
                            "stop": leg_low * (1 - buf), "target": tgt,
                            "leg_low": leg_low, "leg_high": leg_high})
            pend_long = None

        if pend_short and dn.iloc[i] and i > pend_short[0]:
            tgt = _next_liquidity_below(swing_lows, i, closes[i])
            leg_high = pend_short[1]
            leg_low = float(lows[pend_short[0]:i + 1].min())
            if tgt is not None and leg_high > leg_low:
                out.append({"bar": i, "dir": "SELL", "sweep_bar": pend_short[0],
                            "stop": leg_high * (1 + buf), "target": tgt,
                            "leg_low": leg_low, "leg_high": leg_high})
            pend_short = None

    return out


def entry_level(setup, p):
    """Where the limit order goes — the OTE retracement, not the break.

    NB3 states this outright: enter on the 70-80% Fibonacci retracement of
    the impulse leg. Every setup in that course is a RETEST entry, never a
    market fill on the break bar.

    This is not a detail. Filling at the shift bar puts the entry at the far
    end of the leg from the stop, which is why the first version of this
    file produced R:R between 0.02 and 0.9 and took zero trades. Waiting for
    the pullback cuts the risk to roughly a third of the leg while leaving
    the target untouched.
    """
    lo, hi = setup["leg_low"], setup["leg_high"]
    span = hi - lo
    if span <= 0:
        return None
    r = p["OTE_RETRACE"]
    return hi - r * span if setup["dir"] == "BUY" else lo + r * span


def _validate(entry, stop, target, direction, p):
    """Shared gate. Returns (ok, rr, reason)."""
    if direction == "BUY" and not (stop < entry < target):
        return False, None, "target/stop on wrong side of entry"
    if direction == "SELL" and not (target < entry < stop):
        return False, None, "target/stop on wrong side of entry"

    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        return False, None, "zero stop distance"

    rr = reward / risk
    if rr < p["MIN_RR"]:
        return False, rr, f"R:R {rr:.2f} below {p['MIN_RR']}"

    # NB3: no clear target = no trade. Here that means a target that cannot
    # clear its own toll.
    if reward / entry * 100.0 < 2.0 * p["ROUND_TRIP_COST_PCT"]:
        return False, rr, "target too small to clear fees"

    return True, rr, "ok"


# ══════════════════════════════════════════════════════════════════════
# SIZING — 1% risk, per the sources
# ══════════════════════════════════════════════════════════════════════
def size(entry, stop, capital_inr=CAPITAL_INR, risk_pct=None):
    """How big can I be so that being wrong costs 1% of the account.

    Never 'how big to make X rupees'. That question has no upper bound.
    """
    risk_pct = risk_pct or PARAMS["RISK_PCT"]
    dist = abs(entry - stop)
    if dist <= 0 or entry <= 0:
        return None

    fee_per_unit = entry * (PARAMS["ROUND_TRIP_COST_PCT"] / 100.0)
    risk_inr = capital_inr * risk_pct / 100.0
    qty = risk_inr / ((dist + fee_per_unit) * USDT_INR)

    notional_inr = qty * entry * USDT_INR
    lev = notional_inr / capital_inr if capital_inr else float("inf")
    capped = lev > MAX_LEVERAGE
    if capped:
        notional_inr = capital_inr * MAX_LEVERAGE
        qty = notional_inr / (entry * USDT_INR)
        lev = MAX_LEVERAGE
        risk_inr = qty * (dist + fee_per_unit) * USDT_INR

    return {
        "qty": float(f"{qty:.4g}"),
        "risk_inr": round(risk_inr, 2),
        "notional_inr": round(notional_inr, 2),
        "leverage": round(lev, 2),
        "leverage_capped": capped,
    }


# ══════════════════════════════════════════════════════════════════════
# LIVE SIGNAL
# ══════════════════════════════════════════════════════════════════════
def signal(symbol, timeframe="15m", params=None):
    """Is there a setup on the LAST CLOSED bar? Returns entry, SL, TP, size.

    The forming bar is dropped before anything is computed. Reading it is
    what makes a signal appear and vanish between refreshes.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)

    df, src = fetch(symbol, timeframe, 500)
    if df is None or len(df) < 120:
        return {"symbol": symbol, "timeframe": timeframe, "signal": "NO DATA"}

    df = df.iloc[:-1]                     # drop the forming candle
    setups = find_setups(df, p)
    last = len(df) - 1
    price = float(df["close"].iloc[-1])

    base = {"symbol": symbol, "timeframe": timeframe, "source": src,
            "price": round(price, 8), "bar_time": str(df.index[-1])}

    if not setups or setups[-1]["bar"] != last:
        base.update({"signal": "WAIT", "reason": "no sweep->shift on the last closed bar"})
        return base

    s = setups[-1]
    stop, target = s["stop"], s["target"]
    entry = entry_level(s, p)
    if entry is None:
        base.update({"signal": "WAIT", "reason": "no measurable impulse leg"})
        return base

    ok, rr, why = _validate(entry, stop, target, s["dir"], p)
    if not ok:
        base.update({"signal": "WAIT", "reason": why})
        return base

    base.update({
        "signal": s["dir"],
        "entry": round(entry, 8),
        "sl": round(stop, 8),
        "tp": round(target, 8),
        "rr": round(rr, 2),
        "entry_type": "LIMIT",
        "distance_to_entry_pct": round((entry - price) / price * 100, 3),
        "risk_pct_of_price": round(abs(entry - stop) / entry * 100, 3),
        "sizing": size(entry, stop),
        "reason": (f"{s['dir']} — swept at bar {s['sweep_bar']}, shift at {s['bar']}, "
                   f"limit at the {int(p['OTE_RETRACE']*100)}% retracement"),
        "note": ("Place a LIMIT order at 'entry'. Do NOT chase at market. "
                 f"If it has not filled within {p['FILL_MAX_BARS']} bars, or the "
                 "stop is reached first, the setup is dead — skip it."),
    })
    return base


# ══════════════════════════════════════════════════════════════════════
# BACKTEST
# ══════════════════════════════════════════════════════════════════════
def backtest(symbol, timeframe="15m", candles=3000, params=None):
    """Next-bar-open fills. Stop wins ambiguous candles. Timeouts counted."""
    p = dict(PARAMS)
    if params:
        p.update(params)

    df, src = fetch(symbol, timeframe, candles)
    if df is None or len(df) < 200:
        return {"error": f"no usable data for {symbol} {timeframe}"}

    setups = find_setups(df, p)
    opens, highs = df["open"].values, df["high"].values
    lows, closes = df["low"].values, df["close"].values
    n = len(df)
    cost = p["ROUND_TRIP_COST_PCT"]

    trades, skipped, unfilled, last_exit = [], 0, 0, -1

    for s_ in setups:
        i = s_["bar"]
        if i + 1 >= n or i <= last_exit:      # one position at a time
            continue

        entry = entry_level(s_, p)
        if entry is None:
            continue
        stop, target, d = float(s_["stop"]), float(s_["target"]), s_["dir"]

        ok, rr, _ = _validate(entry, stop, target, d, p)
        if not ok:
            skipped += 1
            continue

        # Wait for the limit to fill. If the stop is reached before the entry
        # is, the setup is dead and was never a trade — counting it as a loss
        # would invent trades that could not have been taken.
        fill_bar = None
        for j in range(i + 1, min(i + 1 + p["FILL_MAX_BARS"], n)):
            if d == "BUY":
                if lows[j] <= stop:
                    break
                if lows[j] <= entry:
                    fill_bar = j
                    break
            else:
                if highs[j] >= stop:
                    break
                if highs[j] >= entry:
                    fill_bar = j
                    break
        if fill_bar is None:
            unfilled += 1
            continue

        outcome = exit_px = exit_bar = None
        for j in range(fill_bar, min(fill_bar + p["TIMEOUT_BARS"], n)):
            if d == "BUY":
                if lows[j] <= stop:
                    outcome, exit_px, exit_bar = "LOSS", stop, j; break
                if highs[j] >= target:
                    outcome, exit_px, exit_bar = "WIN", target, j; break
            else:
                if highs[j] >= stop:
                    outcome, exit_px, exit_bar = "LOSS", stop, j; break
                if lows[j] <= target:
                    outcome, exit_px, exit_bar = "WIN", target, j; break

        if outcome is None:
            exit_bar = min(fill_bar + p["TIMEOUT_BARS"], n - 1)
            outcome, exit_px = "TIMEOUT", float(closes[exit_bar])

        gross = ((exit_px - entry) / entry * 100 if d == "BUY"
                 else (entry - exit_px) / entry * 100)
        last_exit = exit_bar

        trades.append({
            "time": df.index[i].strftime("%m-%d %H:%M"), "dir": d,
            "entry": round(entry, 8), "sl": round(stop, 8), "tp": round(target, 8),
            "rr": round(rr, 2), "outcome": outcome,
            "pnl_pct": round(gross - cost, 4), "bars": exit_bar - i,
        })

    return _report(trades, symbol, timeframe, len(df), src, p, skipped, unfilled)


def _report(trades, symbol, timeframe, candles, src, p, skipped, unfilled=0):
    days = candles * TF_SECONDS.get(timeframe, 900) / 86400.0
    out = {"symbol": symbol, "timeframe": timeframe, "source": src,
           "candles_tested": candles, "days_covered": round(days, 1),
           "params": p, "skipped_low_rr": skipped, "never_filled": unfilled}

    if not trades:
        out.update({"total_trades": 0, "verdict": "NO SETUPS — nothing to judge"})
        return out

    total = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    gp = sum(t["pnl_pct"] for t in wins)
    gl = abs(sum(t["pnl_pct"] for t in losses))
    exp = sum(t["pnl_pct"] for t in trades) / total
    pf = round(gp / gl, 2) if gl > 0 else None
    wr = len(wins) / total * 100
    per_week = total / (days / 7.0) if days > 0 else 0

    out.update({
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "timeouts": len([t for t in trades if t["outcome"] == "TIMEOUT"]),
        "win_rate": round(wr, 1), "profit_factor": pf,
        "expectancy_pct": round(exp, 4),
        "total_pct": round(sum(t["pnl_pct"] for t in trades), 2),
        "avg_rr": round(np.mean([t["rr"] for t in trades]), 2),
        "avg_bars_held": round(np.mean([t["bars"] for t in trades]), 1),
        "trades_per_week": round(per_week, 1),
        "expectancy_inr_at_1pct_risk": round(
            exp / 100 * CAPITAL_INR * MAX_LEVERAGE, 2),
        "recent_trades": trades[-10:],
        "verdict": _verdict(total, exp, pf),
        "frequency_check": (
            "MATCHES the sources (1-5 trades/week)" if 0.5 <= per_week <= 6
            else f"OFF — {per_week:.1f} trades/week vs the 1-5 the sources describe"),
    })
    return out


def _verdict(total, exp, pf):
    if total < 30:
        return f"SAMPLE TOO SMALL ({total} trades) — conclude nothing"
    if exp <= 0:
        return "LOSES MONEY after costs — do not deploy"
    if pf is None or pf < 1.2:
        return "EDGE TOO THIN to survive live slippage"
    return "WORTH FORWARD-TESTING — still not proof"


if __name__ == "__main__":
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT:USDT"
    tf = sys.argv[2] if len(sys.argv) > 2 else "15m"
    mode = sys.argv[3] if len(sys.argv) > 3 else "backtest"

    if mode == "live":
        print(json.dumps(signal(sym, tf), indent=2, default=str))
    else:
        r = backtest(sym, tf)
        r.pop("recent_trades", None)
        print(json.dumps(r, indent=2, default=str))
