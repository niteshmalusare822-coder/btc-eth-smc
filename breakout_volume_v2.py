"""Breakout + Volume V2 signal engine.

Research-only module.  It is intentionally separate from SMC and from the V1
breakout module.

Structure:
  1H completed-bar regime
  15M completed-bar consolidation/range
  5M close breakout + volume confirmation
  5M retest confirmation
  structure + ATR stop

All higher-timeframe values are derived from completed 5M candles and joined
back to 5M by the higher-timeframe CLOSE timestamp, so a 5M bar never sees a
still-forming 15M/1H candle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    "setup_bars_15m": 8,
    "setup_max_range_atr": 4.0,
    "volume_window": 20,
    "volume_factor": 1.5,
    "breakout_buffer_atr": 0.05,
    "retest_bars": 6,
    "retest_tolerance_atr": 0.15,
    "atr_window_5m": 14,
    "atr_window_15m": 14,
    "ema_fast_1h": 20,
    "ema_slow_1h": 50,
    "stop_atr": 0.50,
    "min_reward_after_cost_r": 2.0,
}


def _atr(df: pd.DataFrame, window: int) -> pd.Series:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev).abs(), (low - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / window, adjust=False).mean()


def _complete_resample(df5: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Build only complete HTF candles from 5M bars."""
    x = df5.copy()
    x["ts"] = pd.to_datetime(x["ts"], errors="coerce")
    x = x.dropna(subset=["ts"]).set_index("ts").sort_index()

    rule = f"{minutes}min"
    grouped = x.resample(rule, label="right", closed="right")
    out = grouped.agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    counts = grouped["close"].count()
    out = out[counts == minutes // 5].dropna().reset_index()
    return out


def _asof_join(df5: pd.DataFrame, htf: pd.DataFrame, columns) -> pd.DataFrame:
    left = df5[["ts"]].copy()
    left["ts"] = pd.to_datetime(left["ts"])
    right = htf[["ts", *columns]].copy()
    right["ts"] = pd.to_datetime(right["ts"])
    return pd.merge_asof(
        left.sort_values("ts"),
        right.sort_values("ts"),
        on="ts",
        direction="backward",
    )


def build_features(df5: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    p = {**DEFAULT_PARAMS, **(params or {})}
    x = df5.reset_index(drop=True).copy()
    x["ts"] = pd.to_datetime(x["ts"], errors="coerce")
    x["atr5"] = _atr(x, int(p["atr_window_5m"]))

    # ----------------------------- 15M setup -----------------------------
    df15 = _complete_resample(x, 15)
    df15["atr15"] = _atr(df15, int(p["atr_window_15m"]))
    n15 = int(p["setup_bars_15m"])

    # Shift the range and compression test so the breakout bar only sees
    # completed 15M candles that closed before it.
    df15["prior_high"] = (
        df15["high"].rolling(n15, min_periods=n15).max().shift(1)
    )
    df15["prior_low"] = (
        df15["low"].rolling(n15, min_periods=n15).min().shift(1)
    )
    df15["prior_atr15"] = df15["atr15"].shift(1)
    df15["range_atr"] = (
        (df15["prior_high"] - df15["prior_low"])
        / df15["prior_atr15"].replace(0, np.nan)
    )
    df15["consolidating"] = (
        df15["prior_high"].notna()
        & df15["prior_low"].notna()
        & df15["prior_atr15"].gt(0)
        & (df15["range_atr"] <= float(p["setup_max_range_atr"]))
    )

    # ------------------------------ 1H regime -----------------------------
    df1h = _complete_resample(x, 60)
    fast = int(p["ema_fast_1h"])
    slow = int(p["ema_slow_1h"])
    df1h["ema_fast"] = df1h["close"].ewm(span=fast, adjust=False).mean()
    df1h["ema_slow"] = df1h["close"].ewm(span=slow, adjust=False).mean()
    df1h["regime"] = np.select(
        [
            df1h["ema_fast"] > df1h["ema_slow"],
            df1h["ema_fast"] < df1h["ema_slow"],
        ],
        ["bull", "bear"],
        default="flat",
    )

    j15 = _asof_join(
        x,
        df15,
        ["prior_high", "prior_low", "range_atr", "consolidating"],
    )
    j1h = _asof_join(x, df1h, ["regime", "ema_fast", "ema_slow"])

    for c in ["prior_high", "prior_low", "range_atr", "consolidating"]:
        x[c] = j15[c].to_numpy()
    for c in ["regime", "ema_fast", "ema_slow"]:
        x[c] = j1h[c].to_numpy()

    # --------------------------- 5M breakout ------------------------------
    prior_vol = (
        pd.to_numeric(x["volume"], errors="coerce")
        .rolling(int(p["volume_window"]), min_periods=int(p["volume_window"]))
        .median()
        .shift(1)
    )
    x["volume_ratio"] = (
        pd.to_numeric(x["volume"], errors="coerce")
        / prior_vol.replace(0, np.nan)
    )

    atr = x["atr5"]
    buffer = atr * float(p["breakout_buffer_atr"])
    long_break = (
        x["consolidating"]
        & (x["regime"] == "bull")
        & (x["close"] > x["prior_high"] + buffer)
        & (x["volume_ratio"] >= float(p["volume_factor"]))
    )
    short_break = (
        x["consolidating"]
        & (x["regime"] == "bear")
        & (x["close"] < x["prior_low"] - buffer)
        & (x["volume_ratio"] >= float(p["volume_factor"]))
    )

    body = (x["close"] - x["open"]).abs()
    span = (x["high"] - x["low"]).replace(0, np.nan)
    close_location_long = (x["close"] - x["low"]) / span
    close_location_short = (x["high"] - x["close"]) / span

    # Avoid very weak breakout candles without adding a large parameter grid.
    long_break &= (x["close"] > x["open"]) & (close_location_long >= 0.65)
    short_break &= (x["close"] < x["open"]) & (close_location_short >= 0.65)
    x["body_ratio"] = body / span

    x["breakout"] = np.where(long_break, "bull", np.where(short_break, "bear", None))
    x["breakout_level"] = np.where(
        long_break, x["prior_high"],
        np.where(short_break, x["prior_low"], np.nan),
    )

    # ---------------------------- retest ----------------------------------
    # A breakout is not an entry. Search only future bars for a retest of the
    # broken level. The confirmation bar itself is used as the signal bar;
    # the shared engine still fills from the NEXT 5M open.
    x["signal"] = False
    x["side"] = None
    x["level"] = np.nan
    x["stop_level"] = np.nan
    x["breakout_i"] = np.nan
    x["retest_i"] = np.nan

    max_retest = int(p["retest_bars"])
    tol_mult = float(p["retest_tolerance_atr"])
    used_until = -1

    for i in range(len(x)):
        direction = x.at[i, "breakout"]
        if direction not in ("bull", "bear") or i <= used_until:
            continue

        level = float(x.at[i, "breakout_level"])
        if not np.isfinite(level):
            continue

        found = None
        for j in range(i + 1, min(i + max_retest, len(x) - 1) + 1):
            atr_j = float(x.at[j, "atr5"])
            if not np.isfinite(atr_j) or atr_j <= 0:
                continue
            tol = tol_mult * atr_j

            if direction == "bull":
                touched = float(x.at[j, "low"]) <= level + tol
                confirmed = (
                    touched
                    and float(x.at[j, "close"]) > level
                    and float(x.at[j, "close"]) > float(x.at[j, "open"])
                )
            else:
                touched = float(x.at[j, "high"]) >= level - tol
                confirmed = (
                    touched
                    and float(x.at[j, "close"]) < level
                    and float(x.at[j, "close"]) < float(x.at[j, "open"])
                )

            if confirmed:
                found = j
                break

        if found is None:
            continue

        j = found
        atr_j = float(x.at[j, "atr5"])
        if direction == "bull":
            structure = min(float(x.at[i, "low"]), float(x.at[j, "low"]))
            stop = structure - float(p["stop_atr"]) * atr_j
        else:
            structure = max(float(x.at[i, "high"]), float(x.at[j, "high"]))
            stop = structure + float(p["stop_atr"]) * atr_j

        x.at[j, "signal"] = True
        x.at[j, "side"] = direction
        x.at[j, "level"] = level
        x.at[j, "stop_level"] = stop
        x.at[j, "breakout_i"] = i
        x.at[j, "retest_i"] = j
        used_until = j

    return x
