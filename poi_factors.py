"""
poi_factors.py
==============
Mechanizable rules extracted from SMC/ICT source material (NotebookLM pass).

Design rules followed here:

1. NO HARDCODED THRESHOLDS. Every number the sources gave (2x body, 0.705 OTE,
   0.5 equilibrium) is a *parameter with a default*, not a constant.

2. NO LOOK-AHEAD. Every zone carries `confirmed_idx` = the first bar at whose
   CLOSE the zone is knowable. Backtests must call zones_active_at(zones, i).

3. ONE FACTOR AT A TIME. Each detector is independent and returns plain data.

CHANGE LOG
----------
v2  find_bos(): a swept level fired one event per subsequent bar instead of
    one event total, because `last_high` was never cleared on the sweep
    branch. On a trending series that inflated sample counts roughly 4x and
    every downstream statistic with them. Fixed with high_swept/low_swept
    flags. A level is now also consumed when price closes beyond it but the
    displacement filter rejects the break, otherwise the same repeat firing
    came back through the other branch.

Expected DataFrame columns: open, high, low, close, volume (lowercase).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Candle metrics
# ---------------------------------------------------------------------------


def add_candle_metrics(df: pd.DataFrame, median_window: int = 100) -> pd.DataFrame:
    """Attach body/wick metrics used by every downstream rule."""
    out = df.copy()

    body = (out["close"] - out["open"]).abs()
    rng = (out["high"] - out["low"]).replace(0.0, np.nan)

    out["body"] = body
    out["body_dominance"] = (body / rng).fillna(0.0)

    prev_body = body.shift(1).replace(0.0, np.nan)
    out["body_vs_prev"] = (body / prev_body).fillna(0.0)

    # shift(1) so the median window never includes the current bar
    med = body.shift(1).rolling(median_window, min_periods=20).median()
    out["body_vs_median"] = (body / med.replace(0.0, np.nan)).fillna(0.0)

    upper = out["high"] - out[["open", "close"]].max(axis=1)
    lower = out[["open", "close"]].min(axis=1) - out["low"]
    out["upper_wick_ratio"] = (upper / rng).fillna(0.0)
    out["lower_wick_ratio"] = (lower / rng).fillna(0.0)

    out["is_bull"] = out["close"] > out["open"]
    out["is_bear"] = out["close"] < out["open"]
    return out


def calibrate_body_threshold(
    df: pd.DataFrame,
    target_pct: float = 0.85,
    metric: str = "body_vs_median",
) -> float:
    """Replace the hardcoded 2x rule with a data-derived threshold.

    Run it on a training slice only. Never on the slice you report results on.
    """
    if metric not in df.columns:
        df = add_candle_metrics(df)
    vals = df[metric].replace([np.inf, -np.inf], np.nan).dropna()
    vals = vals[vals > 0]
    if len(vals) < 100:
        return 2.0  # fall back to the literal source value
    return float(np.quantile(vals, target_pct))


# ---------------------------------------------------------------------------
# Swings
# ---------------------------------------------------------------------------


@dataclass
class Swing:
    idx: int
    price: float
    kind: str  # 'high' | 'low'
    confirmed_idx: int  # idx + right


def find_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[Swing]:
    """Fractal swings. left/right are sweep parameters."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    swings: list[Swing] = []

    for i in range(left, n - right):
        h = highs[i]
        if h > highs[i - left: i].max() and h > highs[i + 1: i + right + 1].max():
            swings.append(Swing(i, float(h), "high", i + right))
        lo = lows[i]
        if lo < lows[i - left: i].min() and lo < lows[i + 1: i + right + 1].min():
            swings.append(Swing(i, float(lo), "low", i + right))

    swings.sort(key=lambda s: s.confirmed_idx)
    return swings


def find_equal_levels(
    swings: list[Swing],
    kind: str,
    tolerance: float,
    tolerance_mode: str = "pct",
    max_gap_bars: int = 100,
) -> list[tuple[Swing, Swing]]:
    """Equal highs / equal lows. tolerance is a required sweep parameter."""
    pool = [s for s in swings if s.kind == kind]
    pairs: list[tuple[Swing, Swing]] = []
    for a, b in zip(pool, pool[1:]):
        if b.idx - a.idx > max_gap_bars:
            continue
        denom = a.price if tolerance_mode == "pct" else 1.0
        if abs(b.price - a.price) / abs(denom) <= tolerance:
            pairs.append((a, b))
    return pairs


# ---------------------------------------------------------------------------
# Break of structure
# ---------------------------------------------------------------------------


@dataclass
class BOS:
    idx: int
    side: str  # 'bull' | 'bear'
    level: float
    swing_idx: int
    body_vs_median: float
    is_sweep: bool  # wick beyond, no body close beyond


def find_bos(
    df: pd.DataFrame,
    swings: list[Swing],
    body_threshold: float = 2.0,
    max_wick_ratio: float = 0.5,
    require_displacement: bool = True,
) -> list[BOS]:
    """Body close beyond a confirmed swing = BOS. Wick only = sweep.

    v2 FIX. Each swing level now produces at most one sweep event and at most
    one break event, and is retired the moment either resolves it. Previously
    the sweep branch left `last_high` in place, so every subsequent bar that
    poked above the same level emitted another BOS. In a trend that is dozens
    of duplicate events off a single level.
    """
    if "body_vs_median" not in df.columns:
        df = add_candle_metrics(df)

    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    bvm = df["body_vs_median"].to_numpy()
    uw = df["upper_wick_ratio"].to_numpy()
    lw = df["lower_wick_ratio"].to_numpy()
    n = len(df)

    events: list[BOS] = []
    last_high: Optional[Swing] = None
    last_low: Optional[Swing] = None
    high_swept = False
    low_swept = False
    ptr = 0

    for i in range(n):
        # promote only swings already confirmed at or before this bar
        while ptr < len(swings) and swings[ptr].confirmed_idx <= i:
            s = swings[ptr]
            if s.kind == "high":
                last_high, high_swept = s, False
            else:
                last_low, low_swept = s, False
            ptr += 1

        if last_high is not None and highs[i] > last_high.price:
            broke = closes[i] > last_high.price
            if broke:
                body_ok = (not require_displacement) or bvm[i] >= body_threshold
                wick_ok = uw[i] <= max_wick_ratio
                if body_ok and wick_ok:
                    events.append(
                        BOS(i, "bull", last_high.price, last_high.idx, float(bvm[i]), False)
                    )
                # consumed either way: the level is gone once price closes past it
                last_high = None
            elif not high_swept:
                events.append(
                    BOS(i, "bull", last_high.price, last_high.idx, float(bvm[i]), True)
                )
                high_swept = True

        if last_low is not None and lows[i] < last_low.price:
            broke = closes[i] < last_low.price
            if broke:
                body_ok = (not require_displacement) or bvm[i] >= body_threshold
                wick_ok = lw[i] <= max_wick_ratio
                if body_ok and wick_ok:
                    events.append(
                        BOS(i, "bear", last_low.price, last_low.idx, float(bvm[i]), False)
                    )
                last_low = None
            elif not low_swept:
                events.append(
                    BOS(i, "bear", last_low.price, last_low.idx, float(bvm[i]), True)
                )
                low_swept = True

    return events


# ---------------------------------------------------------------------------
# Zones: FVG, Order Block, Breaker
# ---------------------------------------------------------------------------


@dataclass
class Zone:
    kind: str  # 'fvg' | 'ob' | 'breaker'
    side: str  # 'bull' | 'bear'
    top: float
    bottom: float
    formed_idx: int
    confirmed_idx: int  # first bar at whose close this zone is knowable
    tests: int = 0
    half_idx: Optional[int] = None
    dead_idx: Optional[int] = None
    meta: dict = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    def ote(self, low: float = 0.618, high: float = 0.79) -> tuple[float, float]:
        """OTE band inside the zone, measured from the entry-side edge."""
        depth = self.top - self.bottom
        if self.side == "bull":
            return (self.top - depth * high, self.top - depth * low)
        return (self.bottom + depth * low, self.bottom + depth * high)


def find_fvgs(
    df: pd.DataFrame,
    body_threshold: float = 2.0,
    require_displacement: bool = True,
    min_gap_frac: float = 0.0,
) -> list[Zone]:
    """Three-candle imbalance. Confirmed at the close of the third candle."""
    if "body_vs_median" not in df.columns:
        df = add_candle_metrics(df)

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    bvm = df["body_vs_median"].to_numpy()
    rng = (df["high"] - df["low"]).to_numpy()
    zones: list[Zone] = []

    for i in range(2, len(df)):
        mid_ok = (not require_displacement) or bvm[i - 1] >= body_threshold
        if not mid_ok:
            continue
        mid_range = rng[i - 1] if rng[i - 1] > 0 else np.nan

        gap = lows[i] - highs[i - 2]
        if gap > 0 and (np.isnan(mid_range) or gap / mid_range >= min_gap_frac):
            zones.append(
                Zone("fvg", "bull", float(lows[i]), float(highs[i - 2]), i - 1, i,
                     meta={"displacement": float(bvm[i - 1])})
            )

        gap = lows[i - 2] - highs[i]
        if gap > 0 and (np.isnan(mid_range) or gap / mid_range >= min_gap_frac):
            zones.append(
                Zone("fvg", "bear", float(lows[i - 2]), float(highs[i]), i - 1, i,
                     meta={"displacement": float(bvm[i - 1])})
            )

    return zones


def find_order_blocks(
    df: pd.DataFrame,
    bos_events: list[BOS],
    lookback: int = 30,
    body_dominance_cut: float = 0.6,
) -> list[Zone]:
    """Last opposite-colour candle before the leg that caused a BOS.

    confirmed_idx = the BOS bar. The block did not exist as a tradeable object
    before the break happened.
    """
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    lo = df["low"].to_numpy()
    if "body_dominance" not in df.columns:
        df = add_candle_metrics(df)
    dom = df["body_dominance"].to_numpy()

    zones: list[Zone] = []
    for ev in bos_events:
        if ev.is_sweep:
            continue
        start = max(0, ev.idx - lookback)
        want_bear = ev.side == "bull"
        found = None
        for j in range(ev.idx - 1, start - 1, -1):
            if want_bear and c[j] < o[j]:
                found = j
                break
            if not want_bear and c[j] > o[j]:
                found = j
                break
        if found is None:
            continue

        if dom[found] >= body_dominance_cut:
            top, bottom = max(o[found], c[found]), min(o[found], c[found])
        else:
            top, bottom = h[found], lo[found]

        zones.append(
            Zone("ob", ev.side, float(top), float(bottom), found, ev.idx,
                 meta={"bos_idx": ev.idx, "displacement": ev.body_vs_median})
        )
    return zones


def update_zones(zones: list[Zone], df: pd.DataFrame, i: int, kill_on: str = "full") -> None:
    """Streaming mitigation update. Call once per bar, in order, never vectorised."""
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


def zones_active_at(zones: list[Zone], i: int, max_tests: Optional[int] = 1,
                    max_age: Optional[int] = None) -> list[Zone]:
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


# ---------------------------------------------------------------------------
# Confluence
# ---------------------------------------------------------------------------


def equilibrium(swing_low: float, swing_high: float) -> float:
    """The 0.5 premium/discount divider. The only number all sources shared."""
    return (swing_low + swing_high) / 2.0


def dragon_fruit(ob: Zone, fvg: Zone, max_gap_frac: float = 0.1) -> bool:
    """OB and FVG touching or overlapping - the sources' highest-rated entry."""
    if ob.side != fvg.side:
        return False
    height = max(ob.top - ob.bottom, 1e-12)
    if fvg.bottom <= ob.top and fvg.top >= ob.bottom:
        return True
    gap = min(abs(fvg.bottom - ob.top), abs(ob.bottom - fvg.top))
    return gap / height <= max_gap_frac


def confluence_score(flags: dict[str, bool], weights: Optional[dict[str, float]] = None) -> float:
    """Normalised 0-1 score over the source checklist."""
    keys = ["displacement", "fvg", "order_block", "sweep_before",
            "discount_premium", "htf_aligned", "key_level"]
    w = weights or {k: 1.0 for k in keys}
    total = sum(w.get(k, 1.0) for k in keys)
    hit = sum(w.get(k, 1.0) for k in keys if flags.get(k, False))
    return hit / total if total else 0.0


# ---------------------------------------------------------------------------
# Sweep grid derived directly from source contradictions
# ---------------------------------------------------------------------------

SOURCE_CONTRADICTION_GRID = {
    "entry_mode": ["limit_mid", "limit_ote", "confirm_close"],
    "target_mode": ["fixed_r", "next_liquidity"],
    "target_r": [1.5, 2.0, 3.0],
    "stop_mode": ["zone_edge", "nearest_wick", "deep_swing"],
    "max_tests": [1, 2, None],
    "body_pct": [0.70, 0.80, 0.85, 0.90],
    "require_displacement": [True, False],
}
