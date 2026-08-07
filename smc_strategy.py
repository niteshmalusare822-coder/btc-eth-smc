"""
smc_strategy.py — Sweep -> Shift entry model, structure-based stops.

Built from the three price-action courses, but be clear about what is and is
not from them:

  FROM THE VIDEOS (mechanical, stated):
    - A liquidity sweep is a wick through a prior swing that CLOSES back
      inside it. Explicitly stated in all three sources.
    - After the sweep, wait for structure to shift the other way before
      entering. Stated in NB1 and NB3 ("micro market structure break").
    - The stop goes beyond the swept extreme, not at a fixed distance.
    - The target is the opposite side's liquidity, not a fixed multiple.
    - Do not trade choppy / directionless conditions.

  INVENTED HERE (the videos never quantified these):
    - SWING_LOOKBACK      : how many bars define a swing point
    - SL_BUFFER_PCT       : how far beyond the swept extreme the stop sits
    - SHIFT_MAX_BARS      : how long after a sweep the shift still counts
    - MIN_RR              : minimum target-to-stop ratio worth taking
    - TIMEOUT_BARS        : when to give up on an unresolved trade

    Five numbers. That is the entire tuning surface, and it is listed here
    so it cannot quietly grow. Every one of them is a place this strategy
    can be overfitted, so change them one at a time and re-measure.

WHAT THIS DELIBERATELY DOES NOT DO:
    - No composite score. A setup either forms or it does not.
    - No ATR-derived stop or target. The videos place both on structure;
      an ATR stop is a different strategy wearing the same name.
    - No confluence stacking. Adding factors until the backtest improves is
      how the existing scanner ended up with sixteen bugs and no edge.

Usage:
    from smc_strategy import backtest_smc
    print(backtest_smc("BTC/USDT:USDT", "15m"))

    python3 smc_strategy.py                  # BTC 15m
    python3 smc_strategy.py ETH/USDT:USDT 5m
"""

import sys

import numpy as np
import pandas as pd

from scanner import fetch_ohlcv_failover, round_trip_cost_pct, _px


# ── The five invented numbers. Everything else comes from price. ────────
PARAMS = {
    "SWING_LOOKBACK": 5,      # bars either side that define a swing point
    "SL_BUFFER_PCT": 0.05,    # stop sits this % beyond the swept extreme
    "SHIFT_MAX_BARS": 6,      # sweep is stale after this many bars
    "MIN_RR": 1.5,            # skip anything paying less than this
    "TIMEOUT_BARS": 40,       # close at market if unresolved by here
}


# ══════════════════════════════════════════════════════════════════════
# STRUCTURE
# ══════════════════════════════════════════════════════════════════════
def swing_points(df, lookback=None):
    """Confirmed swing highs and lows.

    A bar is a swing high if its high is the maximum of the `lookback` bars
    on each side. That means it is only KNOWABLE `lookback` bars later, so
    both series are shifted forward by that amount. Skipping this shift is
    the classic swing-detection lookahead: the backtest sees a pivot the
    moment it prints, which in live trading is impossible.
    """
    lb = lookback or PARAMS["SWING_LOOKBACK"]
    high, low = df["high"], df["low"]

    is_high = high == high.rolling(lb * 2 + 1, center=True).max()
    is_low = low == low.rolling(lb * 2 + 1, center=True).min()

    # Value of the last confirmed swing, as known at each bar.
    sh = high.where(is_high).shift(lb).ffill()
    sl = low.where(is_low).shift(lb).ffill()
    return sh, sl


def detect_sweeps(df, lookback=None):
    """Wick through a prior swing that closes back inside it.

    Returns two boolean series:
        high_sweep — took buy-side liquidity, rejected. Bearish.
        low_sweep  — took sell-side liquidity, rejected. Bullish.

    This is the one definition all three sources agree on and the only one
    they state without an adjective.
    """
    sh, sl = swing_points(df, lookback)
    prior_sh, prior_sl = sh.shift(1), sl.shift(1)

    high_sweep = (df["high"] > prior_sh) & (df["close"] < prior_sh)
    low_sweep = (df["low"] < prior_sl) & (df["close"] > prior_sl)
    return high_sweep.fillna(False), low_sweep.fillna(False), prior_sh, prior_sl


def structure_shift(df, lookback=None):
    """Close beyond the last confirmed swing on the opposite side.

    This is the confirmation the videos ask for after a sweep — price has to
    prove intent, not merely print a wick.
    """
    sh, sl = swing_points(df, lookback)
    shift_up = df["close"] > sh.shift(1)
    shift_down = df["close"] < sl.shift(1)
    return shift_up.fillna(False), shift_down.fillna(False)


# ══════════════════════════════════════════════════════════════════════
# SETUP CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════
def build_setups(df, params=None):
    """Every sweep -> shift setup in the frame, with structural SL and TP.

    Long:  low sweep, then a close above the last swing high within
           SHIFT_MAX_BARS. Stop below the swept low. Target the swing high
           above.
    Short: mirror image.

    Nothing here is scored or weighted. The setup exists or it does not.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)

    high_sweep, low_sweep, prior_sh, prior_sl = detect_sweeps(df, p["SWING_LOOKBACK"])
    shift_up, shift_down = structure_shift(df, p["SWING_LOOKBACK"])
    sh, sl = swing_points(df, p["SWING_LOOKBACK"])

    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    buf = p["SL_BUFFER_PCT"] / 100.0

    setups = []

    # Track the most recent unconsumed sweep on each side.
    pending_long = None    # (bar_index, swept_low_price)
    pending_short = None

    for i in range(p["SWING_LOOKBACK"] * 2 + 2, n):
        if low_sweep.iloc[i]:
            pending_long = (i, lows[i])
        if high_sweep.iloc[i]:
            pending_short = (i, highs[i])

        # Expire stale sweeps rather than letting them fire days later.
        if pending_long and (i - pending_long[0]) > p["SHIFT_MAX_BARS"]:
            pending_long = None
        if pending_short and (i - pending_short[0]) > p["SHIFT_MAX_BARS"]:
            pending_short = None

        # ── LONG: swept the lows, now closed above structure ──
        if pending_long and shift_up.iloc[i] and i > pending_long[0]:
            swept_low = pending_long[1]
            target = sh.iloc[i]
            if pd.notna(target):
                stop = swept_low * (1 - buf)
                setups.append({
                    "signal_bar": i, "direction": "BUY",
                    "sweep_bar": pending_long[0],
                    "stop": stop, "target": float(target),
                    "ref_close": closes[i],
                })
            pending_long = None

        # ── SHORT: swept the highs, now closed below structure ──
        if pending_short and shift_down.iloc[i] and i > pending_short[0]:
            swept_high = pending_short[1]
            target = sl.iloc[i]
            if pd.notna(target):
                stop = swept_high * (1 + buf)
                setups.append({
                    "signal_bar": i, "direction": "SELL",
                    "sweep_bar": pending_short[0],
                    "stop": stop, "target": float(target),
                    "ref_close": closes[i],
                })
            pending_short = None

    return setups


# ══════════════════════════════════════════════════════════════════════
# BACKTEST
# ══════════════════════════════════════════════════════════════════════
def backtest_smc(symbol, timeframe="15m", candles=3000, params=None):
    """Sweep -> shift, structural stops, next-bar-open fills, stop-first exits.

    The execution rules mirror scanner.py v3 on purpose, so the two are
    comparable:
      - entry at the OPEN of the bar after the signal
      - the stop wins any candle that spans both levels
      - unresolved trades close at market and are counted, not deleted
      - round-trip cost charged once per trade
    """
    p = dict(PARAMS)
    if params:
        p.update(params)

    df, src = fetch_ohlcv_failover(symbol, timeframe, candles)
    if df is None or len(df) < 200:
        return {"error": f"no usable data for {symbol} {timeframe}"}

    setups = build_setups(df, p)
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)
    cost = round_trip_cost_pct()

    trades = []
    skipped_rr = 0
    skipped_cost = 0
    last_exit_bar = -1

    for s in setups:
        i = s["signal_bar"]
        if i + 1 >= n:
            continue
        # One position at a time. Overlapping entries would compound the same
        # move and flatter the equity curve.
        if i <= last_exit_bar:
            continue

        entry = float(opens[i + 1])
        stop = float(s["stop"])
        target = float(s["target"])
        direction = s["direction"]

        # Target must sit the right side of entry; after a shift bar it
        # sometimes does not.
        if direction == "BUY" and not (stop < entry < target):
            continue
        if direction == "SELL" and not (target < entry < stop):
            continue

        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk <= 0:
            continue

        rr = reward / risk
        if rr < p["MIN_RR"]:
            skipped_rr += 1
            continue

        # The target has to clear the toll, not just the stop.
        if (reward / entry * 100.0) < 2.0 * cost:
            skipped_cost += 1
            continue

        outcome, exit_px, exit_bar = None, None, None
        for j in range(i + 1, min(i + 1 + p["TIMEOUT_BARS"], n)):
            if direction == "BUY":
                if lows[j] <= stop:
                    outcome, exit_px, exit_bar = "LOSS", stop, j
                    break
                if highs[j] >= target:
                    outcome, exit_px, exit_bar = "WIN", target, j
                    break
            else:
                if highs[j] >= stop:
                    outcome, exit_px, exit_bar = "LOSS", stop, j
                    break
                if lows[j] <= target:
                    outcome, exit_px, exit_bar = "WIN", target, j
                    break

        if outcome is None:
            exit_bar = min(i + p["TIMEOUT_BARS"], n - 1)
            outcome, exit_px = "TIMEOUT", float(closes[exit_bar])

        gross = ((exit_px - entry) / entry * 100.0 if direction == "BUY"
                 else (entry - exit_px) / entry * 100.0)
        net = gross - cost
        last_exit_bar = exit_bar

        trades.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction,
            "entry": _px(entry), "sl": _px(stop), "tp": _px(target),
            "rr_planned": round(rr, 2),
            "outcome": outcome,
            "pnl_pct": round(net, 4),
            "bars_held": exit_bar - i,
        })

    return _summarise(trades, symbol, timeframe, len(df), src, p,
                      skipped_rr, skipped_cost)


def _summarise(trades, symbol, timeframe, candles, src, p, skipped_rr, skipped_cost):
    base = {
        "symbol": symbol, "timeframe": timeframe,
        "candles_tested": candles, "source": src,
        "params": p,
        "round_trip_cost_pct": round_trip_cost_pct(),
        "skipped_low_rr": skipped_rr,
        "skipped_target_too_small": skipped_cost,
    }

    if not trades:
        base.update({"total_trades": 0, "verdict": "NO SETUPS — nothing to judge"})
        return base

    total = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    timeouts = [t for t in trades if t["outcome"] == "TIMEOUT"]

    gp = sum(t["pnl_pct"] for t in wins)
    gl = abs(sum(t["pnl_pct"] for t in losses))
    exp = sum(t["pnl_pct"] for t in trades) / total
    wr = len(wins) / total * 100
    pf = round(gp / gl, 2) if gl > 0 else None

    base.update({
        "total_trades": total,
        "wins": len(wins), "losses": len(losses), "timeouts": len(timeouts),
        "win_rate": round(wr, 1),
        "profit_factor": pf,
        "expectancy_pct": round(exp, 4),
        "avg_win_pct": round(gp / len(wins), 4) if wins else 0.0,
        "avg_loss_pct": round(gl / len(losses), 4) if losses else 0.0,
        "avg_rr_planned": round(np.mean([t["rr_planned"] for t in trades]), 2),
        "avg_bars_held": round(np.mean([t["bars_held"] for t in trades]), 1),
        "total_pct": round(sum(t["pnl_pct"] for t in trades), 2),
        "recent_trades": trades[-10:],
        "verdict": _verdict(total, exp, pf),
    })
    return base


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
    res = backtest_smc(sym, tf)
    res.pop("recent_trades", None)
    print(json.dumps(res, indent=2, default=str))
