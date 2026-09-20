"""Breakout + volume strategy.

This module is intentionally independent from the existing SMC engine.
Signals use only information available at the close of the signal bar:
- previous N-bar high/low (shifted by one bar)
- previous rolling volume median (also shifted)
- current closed-bar volume confirmation
The execution/backtest layer decides the fill, stop, costs and exits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    "lookback": 20,
    "volume_window": 20,
    "volume_factor": 1.5,
    "breakout_buffer": 0.0,
    "atr_window": 14,
    "stop_atr": 1.0,
}


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """ATR using only current/past OHLC bars."""
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def signals(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """Return breakout signals aligned to the input 5M bars.

    side is bull / bear / None. level is the prior range boundary that was
    broken. No future bar is read by this function.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    lookback = int(p["lookback"])
    vol_window = int(p["volume_window"])
    factor = float(p["volume_factor"])
    buffer = float(p["breakout_buffer"])

    out = pd.DataFrame(index=df.index)
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")

    # Shift first: the breakout level and volume baseline cannot include the
    # signal candle itself.
    prior_high = high.rolling(
        lookback, min_periods=lookback
    ).max().shift(1)
    prior_low = low.rolling(
        lookback, min_periods=lookback
    ).min().shift(1)
    prior_vol_median = volume.rolling(
        vol_window, min_periods=vol_window
    ).median().shift(1)

    vol_ok = volume >= prior_vol_median * factor
    long_break = close > prior_high * (1.0 + buffer)
    short_break = close < prior_low * (1.0 - buffer)

    # Only one side can be true on a normal bar. If bad input creates both,
    # suppress the signal rather than inventing a direction.
    long_ok = long_break & vol_ok
    short_ok = short_break & vol_ok
    both = long_ok & short_ok

    out["side"] = np.select(
        [long_ok & ~both, short_ok & ~both],
        ["bull", "bear"],
        default=None,
    )
    out["level"] = np.select(
        [long_ok & ~both, short_ok & ~both],
        [prior_high, prior_low],
        default=np.nan,
    )
    out["volume_ratio"] = volume / prior_vol_median.replace(0, np.nan)
    out["prior_high"] = prior_high
    out["prior_low"] = prior_low
    out["atr"] = atr(df, int(p["atr_window"]))
    out["signal"] = out["side"].notna()
    return out
