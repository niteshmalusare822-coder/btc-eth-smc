#!/usr/bin/env python3
"""
structure_audit.py — validate the 15M chain before anything is built on it.

    liquidity sweep -> structure break -> order block -> FVG -> entry

If the structure break itself is weak or misclassified, every filter stacked
above it is decorating a broken foundation. This measures each link separately
and asks one question per link: does adding it change outcomes?

THE GAP THIS EXPOSES
--------------------
poi_factors.find_bos() labels every break "BOS". It has no concept of CHoCH.
That collapses two opposite events into one:

    BOS   break in the direction of the existing trend      = continuation
    CHoCH break against the existing trend, the first one   = reversal

SMC treats these as different signals with different follow-through. Measuring
them as one is like averaging a trend-following and a mean-reversion system and
wondering why the result is flat. This module classifies them causally and
reports each separately.

NOTHING HERE CHANGES THE STRATEGY. It is measurement only. poi_factors.py is
not modified; classification is derived from its output.

USAGE
    python3 structure_audit.py --symbols BTC,ETH --bars 10000
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

import data as D
import mtf_engine as mtf
import poi_factors as poi


# ---------------------------------------------------------------------------
# CHoCH vs BOS  (causal, derived, poi_factors untouched)
# ---------------------------------------------------------------------------
def classify_breaks(events):
    """Walk the break sequence forward and label each one.

    The prevailing direction is whatever the LAST confirmed break established.
    A break in that same direction continues it (BOS). A break the other way is
    the first sign the trend has turned (CHoCH). The very first break of a
    series has no prior direction, so it is UNKNOWN rather than guessed.

    This only ever reads breaks that already happened, so it is causal.
    """
    out, prev = [], None
    for e in events:
        if e.is_sweep:
            out.append({"idx": e.idx, "side": e.side, "kind": "SWEEP",
                        "displacement": e.body_vs_median})
            continue
        if prev is None:
            kind = "UNKNOWN_FIRST"
        elif e.side == prev:
            kind = "BOS"
        else:
            kind = "CHOCH"
        out.append({"idx": e.idx, "side": e.side, "kind": kind,
                    "displacement": e.body_vs_median})
        prev = e.side
    return out


def forward_outcome(df, idx, side, atr, horizon=32):
    """What price did after the break, in ATR. Descriptive, never a signal.

    Deliberately looks ahead — that is the point of an outcome measure. It is
    computed here and used nowhere near the entry logic.
    """
    n = len(df)
    if idx + 1 >= n or not np.isfinite(atr) or atr <= 0:
        return None
    end = min(idx + 1 + horizon, n - 1)
    hi = df["high"].to_numpy()[idx + 1:end + 1]
    lo = df["low"].to_numpy()[idx + 1:end + 1]
    ref = float(df["close"].iat[idx])
    if side == "bull":
        fav, adv = hi.max() - ref, ref - lo.min()
    else:
        fav, adv = ref - lo.min(), hi.max() - ref
    return {"mfe_atr": round(float(fav / atr), 3),
            "mae_atr": round(float(adv / atr), 3),
            "followed_through": bool(fav >= atr and fav > adv)}


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _summarise(rows, label):
    if not rows:
        return {"label": label, "n": 0}
    mfe = np.array([r["mfe_atr"] for r in rows], dtype=float)
    mae = np.array([r["mae_atr"] for r in rows], dtype=float)
    ft = np.array([r["followed_through"] for r in rows], dtype=bool)
    return {
        "label": label, "n": len(rows),
        "follow_through_pct": round(float(ft.mean() * 100), 1),
        "median_mfe_atr": round(float(np.median(mfe)), 2),
        "median_mae_atr": round(float(np.median(mae)), 2),
        "mfe_minus_mae": round(float(np.median(mfe) - np.median(mae)), 2),
    }


def _split_test(with_rows, without_rows, label):
    """Independent split, never nested.

    Comparing "chain with FVG" against "the whole chain" is comparing a subset
    to its own superset, which understates every difference. The honest
    comparison is HAS the property versus DOES NOT HAVE it, on disjoint sets.
    """
    if not with_rows or not without_rows:
        return {"test": label, "conclusive": False,
                "note": "one side is empty; nothing to compare"}
    a = np.array([r["mfe_atr"] - r["mae_atr"] for r in with_rows], dtype=float)
    b = np.array([r["mfe_atr"] - r["mae_atr"] for r in without_rows],
                 dtype=float)
    diff = float(a.mean() - b.mean())
    sd = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))) \
        if len(a) > 1 and len(b) > 1 else 0.0
    t = diff / sd if sd else 0.0
    return {
        "test": label,
        "with_n": len(a), "without_n": len(b),
        "with_edge_atr": round(float(a.mean()), 3),
        "without_edge_atr": round(float(b.mean()), 3),
        "difference_atr": round(diff, 3),
        "t": round(t, 2),
        "significant_95": bool(abs(t) > 1.96),
        "verdict": ("adds measurable value" if t > 1.96 else
                    "SUBTRACTS value" if t < -1.96 else
                    "no measurable effect; it only costs sample size"),
    }


# ---------------------------------------------------------------------------
def audit_symbol(symbol, bars, params=None):
    p = params or mtf.PARAMS
    frames, meta = D.load_mtf(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": (meta or {}).get("error", "no data")}

    df15 = poi.add_candle_metrics(frames["15m"])
    atr15 = _atr(df15).to_numpy()

    thr = poi.rolling_body_threshold(df15, window=p.get("calib_window", 500),
                                     target_pct=p["body_pct"])
    swings = poi.find_swings(df15, p["swing_left"], p["swing_right"])
    events = poi.find_bos(df15, swings, body_threshold=thr,
                          require_displacement=True)
    labelled = classify_breaks(events)

    breaks = [e for e in labelled if e["kind"] in ("BOS", "CHOCH",
                                                   "UNKNOWN_FIRST")]
    sweeps = [e for e in labelled if e["kind"] == "SWEEP"]

    # attach outcomes
    for e in labelled:
        e["outcome"] = forward_outcome(df15, e["idx"], e["side"],
                                       atr15[e["idx"]])
    ok = [e for e in labelled if e.get("outcome")]

    by_kind = {}
    for kind in ("BOS", "CHOCH", "SWEEP", "UNKNOWN_FIRST"):
        rows = [e["outcome"] for e in ok if e["kind"] == kind]
        by_kind[kind] = _summarise(rows, kind)

    # ── link 2: was the break preceded by a sweep? ───────────────────────
    sweep_idx = {e["idx"]: e["side"] for e in sweeps}
    swept, unswept = [], []
    for e in ok:
        if e["kind"] not in ("BOS", "CHOCH"):
            continue
        want = "bear" if e["side"] == "bull" else "bull"
        has = any(s_side == want and 0 < e["idx"] - s_i <= p["sweep_window"]
                  for s_i, s_side in sweep_idx.items())
        (swept if has else unswept).append(e["outcome"])

    # ── link 3 and 4: order block, and order block with FVG ──────────────
    real_breaks = [ev for ev in events if not ev.is_sweep]
    obs_all = poi.find_order_blocks(df15, real_breaks, require_sweep=False,
                                    require_imbalance=False)
    obs_strict = poi.find_order_blocks(df15, real_breaks, require_sweep=True,
                                       require_imbalance=True)
    strict_ids = {z.confirmed_idx for z in obs_strict}

    ob_pass, ob_fail = [], []
    for z in obs_all:
        o = forward_outcome(df15, z.confirmed_idx, z.side, atr15[z.confirmed_idx])
        if not o:
            continue
        (ob_pass if z.confirmed_idx in strict_ids else ob_fail).append(o)

    fvgs = poi.find_fvgs(df15, body_threshold=thr, require_displacement=True)
    with_fvg, no_fvg = [], []
    for z in obs_strict:
        o = forward_outcome(df15, z.confirmed_idx, z.side, atr15[z.confirmed_idx])
        if not o:
            continue
        hit = any(f.confirmed_idx <= z.confirmed_idx and poi.dragon_fruit(z, f)
                  for f in fvgs)
        (with_fvg if hit else no_fvg).append(o)

    # ── displacement strength ────────────────────────────────────────────
    disp = [e for e in ok if e["kind"] in ("BOS", "CHOCH")
            and np.isfinite(e["displacement"])]
    if disp:
        med = float(np.median([e["displacement"] for e in disp]))
        strong = [e["outcome"] for e in disp if e["displacement"] >= med]
        weak = [e["outcome"] for e in disp if e["displacement"] < med]
    else:
        strong = weak = []

    return {
        "symbol": symbol,
        "coverage_days": (meta or {}).get("coverage_days"),
        "bars_15m": len(df15),
        "counts": {
            "swings": len(swings),
            "sweeps": len(sweeps),
            "breaks_total": len(breaks),
            "BOS": sum(1 for e in labelled if e["kind"] == "BOS"),
            "CHOCH": sum(1 for e in labelled if e["kind"] == "CHOCH"),
            "order_blocks_raw": len(obs_all),
            "order_blocks_after_rules": len(obs_strict),
            "fvgs": len(fvgs),
        },
        "by_break_type": by_kind,
        "link_tests": [
            _split_test([o for o in by_kind_rows(ok, "CHOCH")],
                        [o for o in by_kind_rows(ok, "BOS")],
                        "CHoCH vs BOS"),
            _split_test(swept, unswept, "sweep before the break"),
            _split_test(ob_pass, ob_fail, "OB rules (sweep + imbalance)"),
            _split_test(with_fvg, no_fvg, "FVG overlapping the OB"),
            _split_test(strong, weak, "above-median displacement"),
        ],
    }


def by_kind_rows(ok, kind):
    return [e["outcome"] for e in ok if e["kind"] == kind]


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTC,ETH")
    ap.add_argument("--bars", type=int, default=10000)
    ap.add_argument("--out", default="structure_audit.json")
    a = ap.parse_args()

    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    for s in syms:
        if s not in D.PAIR_MAP:
            D.PAIR_MAP[s] = f"B-{s}_USDT"
            D.CCXT_MAP.setdefault(s, f"{s}/USDT:USDT")

    results = []
    for s in syms:
        print(f"\n{'=' * 78}\n{s}\n{'=' * 78}")
        r = audit_symbol(s, D.clamp_bars(a.bars))
        results.append(r)
        if r.get("error"):
            print(f"  FAILED: {r['error']}")
            continue

        c = r["counts"]
        print(f"  {r['coverage_days']} days, {r['bars_15m']} 15m bars")
        print(f"\n  CHAIN ATTRITION")
        print(f"    swings              {c['swings']:6}")
        print(f"    sweeps              {c['sweeps']:6}")
        print(f"    breaks              {c['breaks_total']:6}   "
              f"BOS {c['BOS']}  CHoCH {c['CHOCH']}")
        print(f"    order blocks raw    {c['order_blocks_raw']:6}")
        print(f"    after OB rules      {c['order_blocks_after_rules']:6}")
        print(f"    FVGs                {c['fvgs']:6}")

        print(f"\n  FOLLOW-THROUGH BY BREAK TYPE (32 bars forward)")
        print(f"    {'type':<16}{'n':>6}{'follow%':>9}{'medMFE':>9}"
              f"{'medMAE':>9}{'edge':>8}")
        for k, v in r["by_break_type"].items():
            if not v.get("n"):
                continue
            print(f"    {k:<16}{v['n']:>6}{v['follow_through_pct']:>9.1f}"
                  f"{v['median_mfe_atr']:>9.2f}{v['median_mae_atr']:>9.2f}"
                  f"{v['mfe_minus_mae']:>+8.2f}")

        print(f"\n  DOES EACH LINK EARN ITS PLACE?")
        for t in r["link_tests"]:
            if not t.get("with_n"):
                print(f"    {t['test']:<32} {t.get('note', 'no data')}")
                continue
            print(f"    {t['test']:<32} with={t['with_n']:<5}"
                  f"without={t['without_n']:<5} diff={t['difference_atr']:+.3f} "
                  f"t={t['t']:+.2f}  {t['verdict']}")

    with open(a.out, "w") as f:
        json.dump(results, f, indent=1, default=str)
    print(f"\nwritten to {a.out}")
    print("\nEvery test above is an INDEPENDENT split (has the property vs does "
          "not),\nnever a subset compared against its own superset.")


if __name__ == "__main__":
    main()
