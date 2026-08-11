"""poi_factors.py - mechanizable SMC/ICT rules.
No hardcoded thresholds. No look-ahead. One factor at a time.
Columns needed: open, high, low, close (lowercase), index 0..n-1.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd


def add_candle_metrics(df, median_window=100):
    out = df.copy()
    body = (out["close"] - out["open"]).abs()
    rng = (out["high"] - out["low"]).replace(0.0, np.nan)
    out["body"] = body
    out["body_dominance"] = (body / rng).fillna(0.0)
    prev = body.shift(1).replace(0.0, np.nan)
    out["body_vs_prev"] = (body / prev).fillna(0.0)
    med = body.shift(1).rolling(median_window, min_periods=20).median()
    out["body_vs_median"] = (body / med.replace(0.0, np.nan)).fillna(0.0)
    up = out["high"] - out[["open", "close"]].max(axis=1)
    dn = out[["open", "close"]].min(axis=1) - out["low"]
    out["upper_wick_ratio"] = (up / rng).fillna(0.0)
    out["lower_wick_ratio"] = (dn / rng).fillna(0.0)
    out["is_bull"] = out["close"] > out["open"]
    out["is_bear"] = out["close"] < out["open"]
    return out


def calibrate_body_threshold(df, target_pct=0.85, metric="body_vs_median"):
    """Replaces the hardcoded 2x rule. Training slice only."""
    if metric not in df.columns:
        df = add_candle_metrics(df)
    v = df[metric].replace([np.inf, -np.inf], np.nan).dropna()
    v = v[v > 0]
    if len(v) < 100:
        return 2.0
    return float(np.quantile(v, target_pct))


@dataclass
class Swing:
    idx: int
    price: float
    kind: str
    confirmed_idx: int


def find_swings(df, left=2, right=2):
    hs = df["high"].to_numpy()
    ls = df["low"].to_numpy()
    out = []
    for i in range(left, len(df) - right):
        if hs[i] > hs[i - left:i].max() and hs[i] > hs[i + 1:i + right + 1].max():
            out.append(Swing(i, float(hs[i]), "high", i + right))
        if ls[i] < ls[i - left:i].min() and ls[i] < ls[i + 1:i + right + 1].min():
            out.append(Swing(i, float(ls[i]), "low", i + right))
    out.sort(key=lambda s: s.confirmed_idx)
    return out


def find_equal_levels(swings, kind, tolerance, tolerance_mode="pct", max_gap_bars=100):
    """Sources give no tolerance, so it is a sweep parameter."""
    pool = [s for s in swings if s.kind == kind]
    pairs = []
    for a, b in zip(pool, pool[1:]):
        if b.idx - a.idx > max_gap_bars:
            continue
        den = a.price if tolerance_mode == "pct" else 1.0
        if abs(b.price - a.price) / abs(den) <= tolerance:
            pairs.append((a, b))
    return pairs


@dataclass
class BOS:
    idx: int
    side: str
    level: float
    swing_idx: int
    body_vs_median: float
    is_sweep: bool


def find_bos(df, swings, body_threshold=2.0, max_wick_ratio=0.5, require_displacement=True):
    """Body close beyond a confirmed swing = BOS. Wick only = sweep."""
    if "body_vs_median" not in df.columns:
        df = add_candle_metrics(df)
    cl = df["close"].to_numpy()
    hs = df["high"].to_numpy()
    ls = df["low"].to_numpy()
    bv = df["body_vs_median"].to_numpy()
    uw = df["upper_wick_ratio"].to_numpy()
    lw = df["lower_wick_ratio"].to_numpy()
    ev = []
    hi_sw = None
    lo_sw = None
    hi_swept = False
    lo_swept = False
    p = 0
    for i in range(len(df)):
        while p < len(swings) and swings[p].confirmed_idx <= i:
            s = swings[p]
            if s.kind == "high":
                hi_sw = s
                hi_swept = False
            else:
                lo_sw = s
                lo_swept = False
            p += 1
        if hi_sw is not None and hs[i] > hi_sw.price:
            ok = (not require_displacement) or bv[i] >= body_threshold
            broke = cl[i] > hi_sw.price
            if broke and ok and uw[i] <= max_wick_ratio:
                ev.append(BOS(i, "bull", hi_sw.price, hi_sw.idx, float(bv[i]), False))
                hi_sw = None
                hi_swept = False
            elif not broke and not hi_swept:
                ev.append(BOS(i, "bull", hi_sw.price, hi_sw.idx, float(bv[i]), True))
                hi_swept = True
        if lo_sw is not None and ls[i] < lo_sw.price:
            ok = (not require_displacement) or bv[i] >= body_threshold
            broke = cl[i] < lo_sw.price
            if broke and ok and lw[i] <= max_wick_ratio:
                ev.append(BOS(i, "bear", lo_sw.price, lo_sw.idx, float(bv[i]), False))
                lo_sw = None
                lo_swept = False
            elif not broke and not lo_swept:
                ev.append(BOS(i, "bear", lo_sw.price, lo_sw.idx, float(bv[i]), True))
                lo_swept = True
    return ev


@dataclass
class Zone:
    kind: str
    side: str
    top: float
    bottom: float
    formed_idx: int
    confirmed_idx: int
    tests: int = 0
    half_idx: Optional[int] = None
    dead_idx: Optional[int] = None
    meta: dict = field(default_factory=dict)

    @property
    def mid(self):
        return (self.top + self.bottom) / 2.0

    def ote(self, low=0.618, high=0.79):
        d = self.top - self.bottom
        if self.side == "bull":
            return (self.top - d * high, self.top - d * low)
        return (self.bottom + d * low, self.bottom + d * high)


def find_fvgs(df, body_threshold=2.0, require_displacement=True, min_gap_frac=0.0):
    """Three-candle imbalance. Confirmed at close of the third candle."""
    if "body_vs_median" not in df.columns:
        df = add_candle_metrics(df)
    hs = df["high"].to_numpy()
    ls = df["low"].to_numpy()
    bv = df["body_vs_median"].to_numpy()
    rg = (df["high"] - df["low"]).to_numpy()
    z = []
    for i in range(2, len(df)):
        if require_displacement and bv[i - 1] < body_threshold:
            continue
        mr = rg[i - 1] if rg[i - 1] > 0 else np.nan
        g = ls[i] - hs[i - 2]
        if g > 0 and (np.isnan(mr) or g / mr >= min_gap_frac):
            z.append(Zone("fvg", "bull", float(ls[i]), float(hs[i - 2]), i - 1, i,
                          meta={"displacement": float(bv[i - 1])}))
        g = ls[i - 2] - hs[i]
        if g > 0 and (np.isnan(mr) or g / mr >= min_gap_frac):
            z.append(Zone("fvg", "bear", float(ls[i - 2]), float(hs[i]), i - 1, i,
                          meta={"displacement": float(bv[i - 1])}))
    return z


def find_order_blocks(df, bos_events, lookback=30, body_dominance_cut=0.6):
    """Last opposite-colour candle before the leg that caused a BOS.
    confirmed_idx = the BOS bar, not the candle's own bar."""
    if "body_dominance" not in df.columns:
        df = add_candle_metrics(df)
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    dm = df["body_dominance"].to_numpy()
    z = []
    for e in bos_events:
        if e.is_sweep:
            continue
        start = max(0, e.idx - lookback)
        want_bear = e.side == "bull"
        f = None
        for j in range(e.idx - 1, start - 1, -1):
            if want_bear and c[j] < o[j]:
                f = j
                break
            if not want_bear and c[j] > o[j]:
                f = j
                break
        if f is None:
            continue
        if dm[f] >= body_dominance_cut:
            top, bot = max(o[f], c[f]), min(o[f], c[f])
        else:
            top, bot = h[f], l[f]
        z.append(Zone("ob", e.side, float(top), float(bot), f, e.idx,
                      meta={"bos_idx": e.idx, "displacement": e.body_vs_median}))
    return z


def update_zones(zones, df, i, kill_on="full"):
    """Streaming mitigation. Once per bar, in order. Never vectorise."""
    hi = float(df["high"].iat[i])
    lo = float(df["low"].iat[i])
    for z in zones:
        if z.dead_idx is not None or z.confirmed_idx > i:
            continue
        if hi < z.bottom or lo > z.top:
            continue
        z.tests += 1
        if z.half_idx is None:
            if (z.side == "bull" and lo <= z.mid) or (z.side == "bear" and hi >= z.mid):
                z.half_idx = i
        if kill_on == "touch":
            z.dead_idx = i
        elif kill_on == "half" and z.half_idx is not None:
            z.dead_idx = i
        elif kill_on == "full":
            if (z.side == "bull" and lo <= z.bottom) or (z.side == "bear" and hi >= z.top):
                z.dead_idx = i


def zones_active_at(zones, i, max_tests=1, max_age=None):
    """The only safe way to read zones inside a backtest loop."""
    out = []
    for z in zones:
        if z.confirmed_idx > i:
            continue
        if z.dead_idx is not None and z.dead_idx < i:
            continue
        if max_tests is not None and z.tests > max_tests:
            continue
        if max_age is not None and (i - z.confirmed_idx) > max_age:
            continue
        out.append(z)
    return out


def equilibrium(swing_low, swing_high):
    return (swing_low + swing_high) / 2.0


def dragon_fruit(ob, fvg, max_gap_frac=0.1):
    """OB and FVG touching or overlapping."""
    if ob.side != fvg.side:
        return False
    h = max(ob.top - ob.bottom, 1e-12)
    if fvg.bottom <= ob.top and fvg.top >= ob.bottom:
        return True
    g = min(abs(fvg.bottom - ob.top), abs(ob.bottom - fvg.top))
    return g / h <= max_gap_frac


def confluence_score(flags, weights=None):
    keys = ["displacement", "fvg", "order_block", "sweep_before",
            "discount_premium", "htf_aligned", "key_level"]
    w = weights or {k: 1.0 for k in keys}
    tot = sum(w.get(k, 1.0) for k in keys)
    hit = sum(w.get(k, 1.0) for k in keys if flags.get(k, False))
    return hit / tot if tot else 0.0


SOURCE_CONTRADICTION_GRID = {
    "entry_mode": ["limit_mid", "limit_ote", "confirm_close"],
    "target_mode": ["fixed_r", "next_liquidity"],
    "target_r": [1.5, 2.0, 3.0],
    "stop_mode": ["zone_edge", "nearest_wick", "deep_swing"],
    "max_tests": [1, 2, None],
    "body_pct": [0.70, 0.80, 0.85, 0.90],
    "require_displacement": [True, False],
}

MODULE_COMPLETE = True
