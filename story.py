"""
story.py — the setup as one causal sequence, and a counter for every link.

    1H CONTEXT
        |
    15M LIQUIDITY EVENT
        |
    15M BOS / MSS
        |
    STRUCTURE ACCEPTANCE
        |
    +---+---+
    |       |
   OB      FVG
    |       |
    +---+---+
        |
     RETEST
        |
    5M TRIGGER
        |
      ENTRY -> SL + TP LADDER

WHAT THIS FILE IS NOT
---------------------
It is not a new engine. Every link above already exists in mtf_engine.py and
poi_factors.py. This file does three things those cannot do:

1. NAMES THE PROFILE. STORY_PARAMS turns the whole chain on as one config
   instead of three unrelated flags. BASELINE_PARAMS keeps the frozen
   behaviour so an A/B stays possible.

2. SEPARATES BOS FROM CHoCH. poi_factors.find_bos() labels every break "BOS"
   and has no concept of a market structure shift. The diagram treats these as
   one node, but they are opposite events: a BOS continues the existing leg, a
   CHoCH ends it. A setup built on a continuation break after a liquidity
   sweep is a different trade from one built on a reversal break, and pooling
   them means neither can be measured. classify_breaks() splits them.

3. COUNTS SURVIVORS PER LINK. funnel() reports how many candidates reach each
   node. With 55 out-of-sample trades the binding question is not which filter
   is best, it is which filter is spending the sample. That cannot be answered
   by a win rate; it needs the counts.

CAUSALITY
---------
classify_breaks() reads only break events in index order and carries forward
state. It never looks at a bar above the break it is labelling. funnel() calls
the same mtf_engine functions the live scanner calls, so its counts describe
the real pipeline and not a parallel reimplementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import mtf_engine as mtf
import poi_factors as poi


# ---------------------------------------------------------------------------
# PROFILES
# ---------------------------------------------------------------------------

# Frozen. Every experimental gate off. This is the number everything else must
# beat, and it must not be edited to make a comparison look better.
BASELINE_PARAMS = dict(mtf.PARAMS)

# The full sequence. Each override below is one node of the diagram.
STORY_PARAMS = {
    **mtf.PARAMS,

    # 15M LIQUIDITY EVENT -> BOS. Already mandatory in find_setups(); the
    # window is the only tunable part of it.
    "sweep_window": 20,

    # STRUCTURE ACCEPTANCE
    "require_structure_confirmation": True,
    "structure_confirm_bars": 2,
    "structure_max_bars": 12,

    # OB POI and FVG POI as alternative paths, not a mandatory overlap
    "poi_mode": "OB_OR_FVG",

    # RETEST
    "require_retest": True,
    "retest_max_wait": 40,
    "retest_depth": 0.0,
}

# Between the two extremes there is only one honest way to attribute a change:
# move one node at a time. These are the intermediate profiles.
LADDER = {
    "0_baseline": BASELINE_PARAMS,
    "1_acceptance": {**BASELINE_PARAMS, "require_structure_confirmation": True},
    "2_acceptance_poi": {**BASELINE_PARAMS, "require_structure_confirmation": True,
                         "poi_mode": "OB_OR_FVG"},
    "3_full_story": STORY_PARAMS,
}


# ---------------------------------------------------------------------------
# BOS vs CHoCH
# ---------------------------------------------------------------------------

@dataclass
class Break:
    idx: int
    side: str          # 'bull' | 'bear'
    level: float
    kind: str          # 'BOS' | 'CHOCH' | 'FIRST'
    displacement: float


def classify_breaks(bos_events) -> list[Break]:
    """Split find_bos() output into continuation and shift.

    The rule is mechanical and needs no lookahead. Carry the direction of the
    last non-sweep break. A new break in the SAME direction continues the leg
    and is a BOS. A break in the OPPOSITE direction ends it and is a CHoCH.
    The first break of a series has no prior direction, so it is labelled
    FIRST and should be counted separately rather than silently folded into
    either bucket.

    Sweeps are excluded. A wick beyond a level is a liquidity event, not a
    structural one, and mtf_engine already routes it that way.
    """
    out: list[Break] = []
    direction = None

    for b in bos_events:
        if b.is_sweep:
            continue

        if direction is None:
            kind = "FIRST"
        elif b.side == direction:
            kind = "BOS"
        else:
            kind = "CHOCH"

        out.append(Break(idx=b.idx, side=b.side, level=float(b.level),
                         kind=kind, displacement=float(b.body_vs_median)))
        direction = b.side

    return out


def sweep_before(bos_events, break_idx: int, side: str, window: int) -> bool:
    """Was liquidity taken on the opposite side within `window` bars before
    this break? Same test find_setups() applies, exposed for counting."""
    want = "bear" if side == "bull" else "bull"
    return any(
        s.is_sweep and s.side == want and 0 < break_idx - s.idx <= window
        for s in bos_events
    )


# ---------------------------------------------------------------------------
# FUNNEL
# ---------------------------------------------------------------------------

def funnel(df_15m, params=None) -> dict:
    """Survivor count at every node of the sequence, on one 15M frame.

    Returns raw counts and the pass rate of each link relative to the one
    above it. A link whose pass rate is very low is where the sample is going;
    a link whose pass rate is near 1.0 is not doing anything and should be
    justified or dropped.
    """
    p = {**mtf.PARAMS, **(params or {})}

    df = poi.add_candle_metrics(df_15m)
    thr = poi.rolling_body_threshold(
        df, window=p.get("calib_window", 500), target_pct=p["body_pct"])
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    events = poi.find_bos(df, swings, body_threshold=thr,
                          require_displacement=True)

    sweeps = [e for e in events if e.is_sweep]
    classified = classify_breaks(events)

    with_sweep = [
        b for b in classified
        if sweep_before(events, b.idx, b.side, p["sweep_window"])
    ]

    # STRUCTURE ACCEPTANCE, counted on the sweep-backed breaks only, because
    # that is the order find_setups() applies them in.
    accepted = []
    if p.get("require_structure_confirmation", False):
        by_idx = {e.idx: e for e in events if not e.is_sweep}
        for b in with_sweep:
            ev = by_idx.get(b.idx)
            if ev is None:
                continue
            got = mtf._structure_confirmed_after_bos(
                df, swings, ev,
                confirm_bars=p.get("structure_confirm_bars", 2),
                max_structure_bars=p.get("structure_max_bars", 12),
            )
            if got is not None:
                accepted.append(b)
    else:
        accepted = list(with_sweep)

    # POI and RETEST are easiest to count from the real setup builder, so the
    # numbers cannot drift from what the scanner actually does.
    setups, _ = mtf.find_setups(df_15m, p)

    retested = [s for s in setups if s.state == "RETESTED"]
    waiting = [s for s in setups if s.state == "WAITING_FOR_RETEST"]
    ready = [s for s in setups if s.state == "READY"]

    by_quality: dict[str, int] = {}
    for s in setups:
        by_quality[s.poi_quality] = by_quality.get(s.poi_quality, 0) + 1

    tradeable = len(retested) + len(ready)

    nodes = [
        ("swings", len(swings)),
        ("liquidity_events", len(sweeps)),
        ("structure_breaks", len(classified)),
        ("breaks_with_sweep", len(with_sweep)),
        ("structure_accepted", len(accepted)),
        ("poi_built", len(setups)),
        ("tradeable_after_retest", tradeable),
    ]

    survival = {}
    for (name, count), (_, prev) in zip(nodes[1:], nodes[:-1]):
        survival[name] = round(count / prev, 4) if prev else None

    return {
        "params": {k: p[k] for k in (
            "sweep_window", "require_structure_confirmation",
            "structure_confirm_bars", "structure_max_bars",
            "poi_mode", "require_retest", "retest_max_wait", "retest_depth",
        )},
        "counts": dict(nodes),
        "survival_rate": survival,
        "break_kind": {
            "FIRST": sum(1 for b in classified if b.kind == "FIRST"),
            "BOS": sum(1 for b in classified if b.kind == "BOS"),
            "CHOCH": sum(1 for b in classified if b.kind == "CHOCH"),
        },
        "break_kind_with_sweep": {
            "FIRST": sum(1 for b in with_sweep if b.kind == "FIRST"),
            "BOS": sum(1 for b in with_sweep if b.kind == "BOS"),
            "CHOCH": sum(1 for b in with_sweep if b.kind == "CHOCH"),
        },
        "poi_quality": by_quality,
        "retest_state": {
            "RETESTED": len(retested),
            "WAITING_FOR_RETEST": len(waiting),
            "READY": len(ready),
        },
    }


def compare(df_15m, profiles=None) -> pd.DataFrame:
    """Run the funnel under each profile in the ladder, side by side.

    One row per node, one column per profile. Reading down a column shows
    where that configuration loses its candidates; reading across a row shows
    what a single node change cost.
    """
    profiles = profiles or LADDER
    cols = {}
    for name, p in profiles.items():
        f = funnel(df_15m, p)
        row = dict(f["counts"])
        row["choch_share_of_breaks"] = (
            round(f["break_kind"]["CHOCH"] / max(f["counts"]["structure_breaks"], 1), 3)
        )
        cols[name] = row
    return pd.DataFrame(cols)


# ---------------------------------------------------------------------------
# KNOWN DEFECT, recorded here so it is not lost
# ---------------------------------------------------------------------------
#
# mtf_engine.gate_state() reports:
#
#     "order_block": bool(s)
#
# That was correct when OB was the only POI. Under poi_mode="OB_OR_FVG" an FVG
# setup now reports order_block=True, so the dashboard and any downstream
# scoring flag cannot tell the two paths apart. The fix is one line:
#
#     "order_block": bool(s) and s.poi_quality in ("OB", "OB+FVG"),
#
# It is not applied from this file because gate_state is engine surface and
# changing it silently would break the frozen baseline comparison.


if __name__ == "__main__":
    import sys
    import data as D

    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    bars_5m = int(sys.argv[2]) if len(sys.argv) > 2 else 9000

    loaded = D.load_mtf(symbol, bars_5m)

    # load_mtf's return shape is not assumed here. Pull the 15m frame out of
    # whatever it hands back, and fail loudly rather than guessing wrong.
    df15 = None
    if isinstance(loaded, dict):
        for k in ("15m", "df15", "df_15m"):
            if k in loaded:
                df15 = loaded[k]
                break
    elif isinstance(loaded, (tuple, list)):
        frames = [x for x in loaded if isinstance(x, pd.DataFrame)]
        if len(frames) >= 2:
            df15 = frames[1]   # 5m, 15m, 1h order

    if df15 is None:
        raise SystemExit(
            f"could not find the 15m frame in load_mtf output: {type(loaded)}")

    print(f"\n{symbol}  15m  {len(df15)} bars\n")
    print(compare(df15).to_string())
