"""
signal_engine.py — signal generation, and nothing else.

DELIBERATELY COST-BLIND. There is no fee, no round-trip cost, no cost gate,
no TP, no SL and no breakeven win rate anywhere in this file. A signal here
answers exactly one question: is structure, trend and momentum currently
lined up in one direction.

That separation is the point. Signal generation and execution viability are
different jobs and mixing them made both harder to reason about — a card
would read "BLOCKED (edge ...)" and it was impossible to tell whether the
setup was bad or merely too small to pay for itself.

WHAT THIS MEANS IN PRACTICE: a BUY here is a statement about the chart, not
a recommendation to buy. Whether that move is large enough to survive fees
is a separate question, answered separately by /api/cost-check-all. Both
numbers are real; they just are not the same number.

Signal logic, per timeframe:

    BUY  = htf_bias BULLISH
           and structure BULLISH
           and EMA alignment BULLISH
           and adx >= adx_min
           and adx rising
           and buy_score >= min_score
           and 40 <= rsi <= 68

    SELL = the mirror, with rsi between 32 and 60

RSI is a CONFIRMATION, never a trigger. The bands exclude entries taken into
exhaustion — buying at RSI 80 or selling at RSI 20 — without ever generating
a signal on their own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scanner import (
    fetch_ohlcv_failover, _drop_forming_candle,
    calc_ema, calc_rsi, calc_adx,
    detect_structure_live_pro, detect_candle_patterns_vectorized,
    detect_pro_divergence_vectorized, compute_active_fvg_series,
    detect_bsl_ssl_zones, calc_equal_level_density, detect_inducement,
    detect_liquidity_sweep, calc_volume_profile, calc_session_vwap,
    detect_market_regime, analyze_timeframe, get_htf_bias, get_ltf_scores,
    get_effective_config, TIMEFRAME_CONFIRM_MAP, HTF_BIAS_TIMEFRAME,
    SUPPORTED_TIMEFRAMES, CONFIG, _px,
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

SIGNAL_CONFIG = {
    "5m": {
        "adx_min": 20,
        "require_adx_rising": True,
        "min_score": 6.0,
        "atr_period": 14,
        "buy_rsi": (40, 68),
        "sell_rsi": (32, 60),
    },
    "15m": {
        "adx_min": 18,
        "require_adx_rising": True,
        "min_score": 6.0,
        "atr_period": 14,
        "buy_rsi": (40, 68),
        "sell_rsi": (32, 60),
    },
    "1h": {
        "adx_min": 18,
        "require_adx_rising": True,
        "min_score": 6.0,
        "atr_period": 14,
        "buy_rsi": (40, 68),
        "sell_rsi": (32, 60),
    },
    "4h": {
        "adx_min": 18,
        "require_adx_rising": True,
        "min_score": 6.0,
        "atr_period": 14,
        "buy_rsi": (40, 68),
        "sell_rsi": (32, 60),
    },
}

SIGNAL_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT",
                  "DEXE/USDT:USDT", "BANK/USDT:USDT"]


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def _closed_frame(symbol, timeframe, limit=None):
    """Candles with the still-forming bar removed.

    Same rule as scanner.py's F2. Without it every component below is
    recomputed from a bar that is still moving, and the signal flips between
    polls for no reason other than an unfinished wick.
    """
    df, src = fetch_ohlcv_failover(symbol, timeframe, limit or CONFIG['LIMIT'])
    if df is None or len(df) < 60:
        return None, None
    return _drop_forming_candle(df), src


def _adx_state(df, period=14):
    """Current ADX and whether it is rising.

    Rising is measured bar over bar on closed candles only. ADX says how
    strong a trend is, never which way it points — direction comes from
    structure and EMA, and this only gates on strength.
    """
    a = calc_adx(df, period)
    if len(a) < 2:
        return None, None, False
    cur, prev = a.iloc[-1], a.iloc[-2]
    if pd.isna(cur) or pd.isna(prev):
        return (None if pd.isna(cur) else float(cur)), None, False
    return float(cur), float(prev), bool(cur > prev)


def _structure_state(df):
    """BULLISH / BEARISH / NONE from the running structure trend.

    structure_trend is the carried-forward state of the last confirmed
    break, so it answers "which way did structure last break" rather than
    "did it break on this exact bar" — the latter is true on a handful of
    bars and would make signals almost unreachable.
    """
    d = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    t = d["structure_trend"].iloc[-1]
    ev = d["structure_event"].iloc[-1]
    if t == "BULL":
        return "BULLISH", ev
    if t == "BEAR":
        return "BEARISH", ev
    return "NONE", ev


def _ema_alignment(df_entry, df_confirm):
    """Both frames agreeing on EMA direction, or NONE.

    Requiring agreement is what makes this a filter rather than a restatement
    of the entry frame's own trend.
    """
    def side(d):
        f = calc_ema(d["close"], CONFIG['EMA_FAST']).iloc[-1]
        s = calc_ema(d["close"], CONFIG['EMA_SLOW']).iloc[-1]
        if pd.isna(f) or pd.isna(s):
            return None
        return "BULLISH" if f > s else "BEARISH"

    a, b = side(df_entry), side(df_confirm)
    if a is None or b is None or a != b:
        return "NONE"
    return a


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

def signal(symbol, timeframe="15m"):
    """One signal for one symbol on one timeframe. No cost logic anywhere."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return {"symbol": symbol, "timeframe": timeframe,
                "error": f"unsupported timeframe — engine trades {SUPPORTED_TIMEFRAMES}"}

    cfg = SIGNAL_CONFIG.get(timeframe, SIGNAL_CONFIG["15m"])
    eff = get_effective_config(symbol)
    confirm_tf = TIMEFRAME_CONFIRM_MAP.get(timeframe, "1h")

    df_entry, src = _closed_frame(symbol, timeframe)
    if df_entry is None:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}
    df_confirm, _ = _closed_frame(symbol, confirm_tf)
    if df_confirm is None:
        df_confirm = df_entry

    # ── components ──────────────────────────────────────────────────────
    snap_entry = analyze_timeframe(df_entry, closed_only=False, eff_cfg=eff)
    snap_confirm = analyze_timeframe(df_confirm, closed_only=False, eff_cfg=eff)

    df_htf, _ = _closed_frame(symbol, HTF_BIAS_TIMEFRAME)
    htf_bias = get_htf_bias(analyze_timeframe(df_htf, closed_only=False, eff_cfg=eff)) \
        if df_htf is not None else "NEUTRAL"

    structure, structure_event = _structure_state(df_entry)
    ema_align = _ema_alignment(df_entry, df_confirm)
    adx, adx_prev, adx_rising = _adx_state(df_entry, cfg["atr_period"])
    buy_score, sell_score = get_ltf_scores(snap_entry, snap_confirm)

    price = float(df_entry["close"].iloc[-1])
    rsi = calc_rsi(df_entry["close"], CONFIG['RSI_PERIOD']).iloc[-1]
    rsi = None if pd.isna(rsi) else float(rsi)

    # ── gates ───────────────────────────────────────────────────────────
    adx_ok = adx is not None and adx >= cfg["adx_min"]
    rising_ok = (not cfg["require_adx_rising"]) or adx_rising

    lo_b, hi_b = cfg["buy_rsi"]
    lo_s, hi_s = cfg["sell_rsi"]
    buy_rsi_ok = rsi is not None and lo_b <= rsi <= hi_b
    sell_rsi_ok = rsi is not None and lo_s <= rsi <= hi_s

    buy_ok = (htf_bias == "BULLISH" and structure == "BULLISH"
              and ema_align == "BULLISH" and adx_ok and rising_ok
              and buy_score >= cfg["min_score"] and buy_rsi_ok)

    sell_ok = (htf_bias == "BEARISH" and structure == "BEARISH"
               and ema_align == "BEARISH" and adx_ok and rising_ok
               and sell_score >= cfg["min_score"] and sell_rsi_ok)

    sig = "BUY" if buy_ok else ("SELL" if sell_ok else "WAIT")

    # Which conditions held, so a WAIT is readable rather than opaque. This
    # is reporting only — nothing here gates anything.
    checks = {
        "htf_bias": htf_bias,
        "structure": structure,
        "ema_alignment": ema_align,
        "adx_ok": bool(adx_ok),
        "adx_rising": bool(adx_rising),
        "score_ok": bool(max(buy_score, sell_score) >= cfg["min_score"]),
        "rsi_ok": bool(buy_rsi_ok if buy_score >= sell_score else sell_rsi_ok),
    }
    missing = [k for k, v in checks.items()
               if v in (False, "NONE", "NEUTRAL")]

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": sig,
        "price": _px(price),
        "score": round(max(buy_score, sell_score), 2),
        "buy_score": buy_score,
        "sell_score": sell_score,
        "bias": htf_bias,
        "adx": round(adx, 2) if adx is not None else None,
        "adx_prev": round(adx_prev, 2) if adx_prev is not None else None,
        "adx_rising": bool(adx_rising),
        "structure": structure,
        "structure_event": structure_event,
        "ema": ema_align,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "confirm_timeframe": confirm_tf,
        "bias_timeframe": HTF_BIAS_TIMEFRAME,
        "exchange": src,
        "thresholds": {"adx_min": cfg["adx_min"], "min_score": cfg["min_score"],
                       "buy_rsi": list(cfg["buy_rsi"]), "sell_rsi": list(cfg["sell_rsi"])},
        "checks": checks,
        "waiting_on": missing if sig == "WAIT" else [],
    }


def scan(timeframes=("5m", "15m"), symbols=None):
    """Every symbol on the given timeframes."""
    out = {}
    for sym in (symbols or SIGNAL_SYMBOLS):
        key = sym.split("/")[0].lower()
        out[key] = {}
        for tf in timeframes:
            try:
                out[key][tf] = signal(sym, tf)
            except Exception as e:
                out[key][tf] = {"symbol": sym, "timeframe": tf, "error": str(e)}
    return out


if __name__ == "__main__":
    import json
    tf = sys.argv[1] if len(sys.argv) > 1 else "15m"
    print(json.dumps(scan(timeframes=(tf,)), indent=2))
