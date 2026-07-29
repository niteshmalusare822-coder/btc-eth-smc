"""
blowoff.py — Parabolic Blow-Off / Distribution detector.

Catches the pattern where price runs vertically, prints a climax candle with a
long upper wick on heavy volume, and then breaks that candle's low.

Design note — this is the important part:

    Everything is computed ONCE, vectorized, in blowoff_series(). Both the live
    path (analyze) and the backtest path (run_backtest) read from that same
    series. There is no second implementation to drift out of sync.

    Every feature is causal — rolling / ewm / shift only. Bar i never sees data
    from bar i+1. So calling this on the full df inside a backtest loop does NOT
    introduce lookahead bias.

Usage — live:
    from blowoff import detect_blowoff, blowoff_gate
    bo = detect_blowoff(df_entry, symbol=symbol)
    ok, why = blowoff_gate(direction, bo)
    if not ok:
        return {"signal": "WAIT", "reason": why}

Usage — backtest (precompute once, outside the loop):
    bo_df = blowoff_series(df, symbol=symbol)
    ...
    if not blowoff_gate_row(direction, bo_df, i)[0]:
        continue
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

DEFAULT_CFG = {
    "roc_lookback": 6,          # bars in the vertical leg
    "roc_min_pct": 60.0,        # min % run (leg high vs close N bars back)
    "accel_ratio_min": 1.4,     # second half of leg steeper than first half

    "wick_ratio_min": 0.45,     # upper wick / full range
    "close_pos_max": 0.40,      # close sits in lower 40% of range

    "vol_lookback": 20,
    "vol_mult_min": 2.0,

    "ext_ema_len": 20,
    "ext_mult_min": 1.25,       # bar high / EMA20

    "min_score": 60,            # 0-100 internal scale
    "stale_bars": 12,           # flag stays live this long after the climax

    "block_longs": True,        # hard veto on BUY while active
    "allow_shorts_only_confirmed": True,
}

# Majors never run 70%. Low-caps do it in an afternoon. Tune per asset.
PER_ASSET_CFG = {
    "BTC/USDT":  {"roc_min_pct": 18.0, "ext_mult_min": 1.08, "wick_ratio_min": 0.40},
    "ETH/USDT":  {"roc_min_pct": 22.0, "ext_mult_min": 1.10, "wick_ratio_min": 0.40},
    "DEXE/USDT": {"roc_min_pct": 45.0, "ext_mult_min": 1.20},
    "BANK/USDT": {"roc_min_pct": 70.0, "ext_mult_min": 1.30},
}


def build_cfg(symbol: str | None = None, overrides: dict | None = None) -> dict:
    cfg = dict(DEFAULT_CFG)
    if symbol:
        key = symbol.replace(":USDT", "").upper()
        if key in PER_ASSET_CFG:
            cfg.update(PER_ASSET_CFG[key])
    if overrides:
        cfg.update(overrides)
    return cfg


# --------------------------------------------------------------------------
# Vectorized core — single source of truth
# --------------------------------------------------------------------------

def blowoff_series(
    df: pd.DataFrame,
    symbol: str | None = None,
    cfg: dict | None = None,
) -> pd.DataFrame:
    """
    Return a DataFrame aligned to df.index with columns:

        bo_score      0-100 exhaustion score for that bar
        bo_climax     True on the climax bar itself
        bo_active     True while a recent climax is still in force
        bo_confirmed  True once price closes below the climax bar's low
        bo_climax_low the low of the governing climax bar (NaN when inactive)

    Safe on short or malformed frames — returns all-False rather than raising.
    """
    cfg = cfg or build_cfg(symbol)
    idx = df.index if df is not None else pd.RangeIndex(0)
    empty = pd.DataFrame(
        {
            "bo_score": pd.Series(0.0, index=idx),
            "bo_climax": pd.Series(False, index=idx),
            "bo_active": pd.Series(False, index=idx),
            "bo_confirmed": pd.Series(False, index=idx),
            "bo_climax_low": pd.Series(np.nan, index=idx),
        }
    )

    need = cfg["roc_lookback"] + cfg["vol_lookback"] + 5
    if df is None or len(df) < need:
        return empty
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            return empty

    o = pd.to_numeric(df["open"], errors="coerce")
    h = pd.to_numeric(df["high"], errors="coerce")
    l = pd.to_numeric(df["low"], errors="coerce")
    c = pd.to_numeric(df["close"], errors="coerce")
    v = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)

    n = cfg["roc_lookback"]
    half = max(1, n // 2)

    # --- candle geometry -------------------------------------------------
    rng = (h - l).replace(0, np.nan)
    upper_wick = h - np.maximum(o, c)
    wick_ratio = (upper_wick / rng).fillna(0.0)
    close_pos = ((c - l) / rng).fillna(0.5)

    # --- parabolic run ---------------------------------------------------
    base = c.shift(n)
    leg_high = h.rolling(n + 1, min_periods=n + 1).max()
    run_pct = ((leg_high - base) / base.replace(0, np.nan) * 100.0).fillna(0.0)

    mid = c.shift(half)
    first_leg = ((mid - base) / base.replace(0, np.nan) * 100.0)
    second_leg = ((leg_high - mid) / mid.replace(0, np.nan) * 100.0)
    accel = np.where(
        first_leg > 0,
        second_leg / first_leg.replace(0, np.nan),
        np.where(second_leg > 0, 3.0, 0.0),
    )
    accel = pd.Series(accel, index=df.index).fillna(0.0)

    # --- volume + extension ----------------------------------------------
    vol_ma = v.rolling(cfg["vol_lookback"], min_periods=5).mean()
    vol_mult = (v / vol_ma.replace(0, np.nan)).fillna(0.0)

    ema_ext = c.ewm(span=cfg["ext_ema_len"], adjust=False).mean()
    ext_mult = (h / ema_ext.replace(0, np.nan)).fillna(0.0)

    # --- weighted score ---------------------------------------------------
    score = (
        (run_pct >= cfg["roc_min_pct"]).astype(float) * 25
        + (accel >= cfg["accel_ratio_min"]).astype(float) * 10
        + (wick_ratio >= cfg["wick_ratio_min"]).astype(float) * 25
        + (close_pos <= cfg["close_pos_max"]).astype(float) * 15
        + (vol_mult >= cfg["vol_mult_min"]).astype(float) * 15
        + (ext_mult >= cfg["ext_mult_min"]).astype(float) * 10
    )

    climax = (score >= cfg["min_score"]) & (run_pct >= cfg["roc_min_pct"])

    # --- propagate the climax forward, causally ---------------------------
    # bars_since uses only past climax flags, so no lookahead.
    pos = pd.Series(np.arange(len(df)), index=df.index)
    last_climax_pos = pos.where(climax).ffill()
    bars_since = pos - last_climax_pos
    active = bars_since.notna() & (bars_since <= cfg["stale_bars"])

    climax_low = l.where(climax).ffill()
    climax_low = climax_low.where(active)

    confirmed = active & (c < climax_low)
    # once confirmed within a window it stays confirmed for that window
    confirmed = (confirmed.astype(int).groupby(last_climax_pos).cummax() > 0) & active

    return pd.DataFrame(
        {
            "bo_score": score,
            "bo_climax": climax.fillna(False),
            "bo_active": active.fillna(False),
            "bo_confirmed": confirmed.fillna(False),
            "bo_climax_low": climax_low,
        }
    )


# --------------------------------------------------------------------------
# Live wrapper
# --------------------------------------------------------------------------

def detect_blowoff(df: pd.DataFrame, symbol: str | None = None, cfg: dict | None = None) -> dict:
    """Blow-off state at the most recent bar, plus a retrace map."""
    cfg = cfg or build_cfg(symbol)
    out = {
        "blowoff": False, "confirmed": False, "score": 0.0,
        "bias": "neutral", "levels": {}, "reason": "",
    }

    s = blowoff_series(df, symbol=symbol, cfg=cfg)
    if len(s) == 0 or not bool(s["bo_active"].iloc[-1]):
        return out

    out["blowoff"] = True
    out["score"] = float(s["bo_score"].max())
    out["confirmed"] = bool(s["bo_confirmed"].iloc[-1])
    out["bias"] = "short" if out["confirmed"] else "exhaustion"
    out["reason"] = (
        "BLOCKED (blow-off exhaustion — parabolic run, climax wick"
        + (", climax low broken)" if out["confirmed"] else ")")
    )

    tail = df.tail(cfg["stale_bars"] + cfg["roc_lookback"] + 1)
    lo = float(pd.to_numeric(tail["low"], errors="coerce").min())
    hi = float(pd.to_numeric(tail["high"], errors="coerce").max())
    span = hi - lo
    if span > 0:
        out["levels"] = {
            "leg_low": lo,
            "leg_high": hi,
            "fib_50": hi - span * 0.50,
            "fib_618": hi - span * 0.618,
            "fib_786": hi - span * 0.786,
            "invalidation": hi,
        }
    return out


# --------------------------------------------------------------------------
# Gates — the only thing the scanner needs to call
# --------------------------------------------------------------------------

def blowoff_gate(direction: str | None, bo: dict, cfg: dict | None = None) -> tuple[bool, str]:
    """Live gate. Returns (allowed, reason_if_blocked)."""
    cfg = cfg or DEFAULT_CFG
    if not bo or not bo.get("blowoff") or not direction:
        return True, ""
    d = str(direction).upper()
    if d in ("BUY", "LONG") and cfg["block_longs"]:
        return False, bo.get("reason") or "BLOCKED (blow-off exhaustion)"
    if d in ("SELL", "SHORT") and cfg["allow_shorts_only_confirmed"] and not bo.get("confirmed"):
        return False, "BLOCKED (blow-off active, climax low not broken yet)"
    return True, ""


def blowoff_gate_row(direction: str | None, bo_df: pd.DataFrame, i: int,
                     cfg: dict | None = None) -> tuple[bool, str]:
    """Backtest gate — same logic, reading row i of the precomputed series."""
    cfg = cfg or DEFAULT_CFG
    if bo_df is None or len(bo_df) <= i or not direction:
        return True, ""
    if not bool(bo_df["bo_active"].iloc[i]):
        return True, ""
    d = str(direction).upper()
    if d in ("BUY", "LONG") and cfg["block_longs"]:
        return False, "blowoff_veto_long"
    if d in ("SELL", "SHORT") and cfg["allow_shorts_only_confirmed"] \
            and not bool(bo_df["bo_confirmed"].iloc[i]):
        return False, "blowoff_unconfirmed_short"
    return True, ""
