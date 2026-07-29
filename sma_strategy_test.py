"""
sma_strategy_test.py — Does the SMA8/50 setup actually work?

Run this BEFORE adding anything to scanner.py.

Tests the exact rule you've been eyeballing on TradingView:
    LONG  when price closes above SMA8 and SMA8 > SMA50
    SHORT when price closes below SMA8 and SMA8 < SMA50
    Exit on ATR-based TP/SL, or on the opposite signal.

Two things this checks that your eye cannot:
  1. Every occurrence, not the ones you happened to scroll to.
  2. The losers, which are invisible in hindsight.

Usage:
    python3 test_sma_strategy.py
    python3 test_sma_strategy.py BANK/USDT:USDT 5m
"""

import sys
import numpy as np
import pandas as pd

from scanner import fetch_ohlcv_failover, CONFIG

FAST, SLOW = 8, 50
ATR_LEN = 14
TP_MULT, SL_MULT = 2.0, 1.0     # 2:1 reward-to-risk
FEE_PCT = 0.10                  # round-trip taker fee + slippage, %


def atr(df, n=ATR_LEN):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def backtest_sma(symbol, timeframe, candles=1000):
    df, src = fetch_ohlcv_failover(symbol, timeframe, candles)
    if df is None:
        return {"error": f"no data for {symbol}"}

    df = df.reset_index(drop=True)
    df["sma_f"] = df["close"].rolling(FAST).mean()
    df["sma_s"] = df["close"].rolling(SLOW).mean()
    df["atr"] = atr(df)

    trades = []
    i = SLOW + ATR_LEN
    while i < len(df) - 1:
        row = df.iloc[i]
        if pd.isna(row["sma_s"]) or pd.isna(row["atr"]) or row["atr"] <= 0:
            i += 1
            continue

        long_sig = row["close"] > row["sma_f"] and row["sma_f"] > row["sma_s"]
        short_sig = row["close"] < row["sma_f"] and row["sma_f"] < row["sma_s"]
        if not (long_sig or short_sig):
            i += 1
            continue

        # only fire on the bar the condition turns on, not every bar it stays on
        prev = df.iloc[i - 1]
        was_long = prev["close"] > prev["sma_f"] and prev["sma_f"] > prev["sma_s"]
        was_short = prev["close"] < prev["sma_f"] and prev["sma_f"] < prev["sma_s"]
        if (long_sig and was_long) or (short_sig and was_short):
            i += 1
            continue

        direction = "LONG" if long_sig else "SHORT"
        entry = float(df["open"].iloc[i + 1])      # next-bar open, no lookahead
        a = float(row["atr"])
        if direction == "LONG":
            tp, sl = entry + TP_MULT * a, entry - SL_MULT * a
        else:
            tp, sl = entry - TP_MULT * a, entry + SL_MULT * a

        outcome, exit_px, bars = None, None, 0
        for j in range(i + 1, len(df)):
            hi, lo = float(df["high"].iloc[j]), float(df["low"].iloc[j])
            bars = j - i
            if direction == "LONG":
                if lo <= sl: outcome, exit_px = "LOSS", sl; break
                if hi >= tp: outcome, exit_px = "WIN", tp; break
            else:
                if hi >= sl: outcome, exit_px = "LOSS", sl; break
                if lo <= tp: outcome, exit_px = "WIN", tp; break

        if outcome is None:
            i += 1
            continue

        gross = (exit_px - entry) / entry * 100
        if direction == "SHORT":
            gross = -gross
        trades.append({"dir": direction, "outcome": outcome,
                       "pct": gross - FEE_PCT, "bars": bars})
        i += bars + 1

    if not trades:
        return {"symbol": symbol, "timeframe": timeframe, "trades": 0,
                "note": "no signals fired"}

    t = pd.DataFrame(trades)
    wins, losses = t[t.outcome == "WIN"], t[t.outcome == "LOSS"]
    gp = wins["pct"].sum()
    gl = abs(losses["pct"].sum())

    result = {
        "symbol": symbol, "timeframe": timeframe, "source": src,
        "candles": len(df), "trades": len(t),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(t) * 100, 1),
        "expectancy_pct": round(t["pct"].mean(), 3),
        "total_pct": round(t["pct"].sum(), 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
        "avg_bars_held": round(t["bars"].mean(), 1),
        "worst_trade": round(t["pct"].min(), 2),
        "max_consec_losses": int(
            (t.outcome == "LOSS").groupby((t.outcome != "LOSS").cumsum()).sum().max()
        ),
    }
    result["verdict"] = _verdict(result)
    return result


def _verdict(r):
    if r.get("trades", 0) < 20:
        return "SAMPLE TOO SMALL — do not conclude anything"
    if r.get("expectancy_pct", 0) <= 0:
        return "LOSES MONEY — do not add to scanner"
    if (r.get("profit_factor") or 0) < 1.2:
        return "EDGE TOO THIN — will not survive real slippage"
    return "WORTH INVESTIGATING — still needs forward testing"
