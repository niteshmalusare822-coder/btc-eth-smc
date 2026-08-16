#!/usr/bin/env python3
"""
lineage.py — reconstruct the 15M structure behind every trade.

For each SMC trade this walks BACKWARDS through the chain and records what
actually produced it:

    swept swing price and timestamp
    BOS timestamp, direction, kind (BOS vs CHoCH), displacement
    whether the sweep and the BOS concern the same structural leg
    OB formation bar and its age at entry
    FVG present, and whether it came from the displacement leg

Then it splits trades into STRONG (reached >= 1R) and WEAK and compares every
structural attribute between them.

THE QUESTION THIS ANSWERS
-------------------------
Were the weak trades weak because the structure was weak, or was the structure
fine and the entry/management lost the money? Those need opposite fixes and
until now we have been guessing.

WHAT THE CODE ALREADY TELLS US (verified, not assumed)
------------------------------------------------------
* find_bos tracks last_high / last_low, i.e. the most recently CONFIRMED
  fractal. There is no swing hierarchy, so a "structure break" is a break of
  the nearest small fractal, not of a major level.
* find_setups requires only that SOME opposite-side sweep occurred within
  sweep_window bars. It never checks that the BOS reverses the leg whose
  liquidity was taken. That link is measured here for the first time.
* dragon_fruit tests geometric overlap only. It does not check that the FVG
  was created by the displacement leg that caused the BOS.

None of that is changed here. It is measured.

USAGE
    python3 lineage.py --symbol BTC --bars 10000
    python3 lineage.py --symbol BTC --bars 10000 --dump lineage_btc.json
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

import backtest as B
import data as D
import mtf_engine as mtf
import poi_factors as poi

STRONG_MFE_R = 1.0


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def build_structure_index(df15, p):
    """Everything the 15M engine derives, kept with its provenance."""
    df = poi.add_candle_metrics(df15)
    thr = poi.rolling_body_threshold(df, window=p.get("calib_window", 500),
                                     target_pct=p["body_pct"])
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    events = poi.find_bos(df, swings, body_threshold=thr,
                          require_displacement=True)
    breaks = [e for e in events if not e.is_sweep]
    sweeps = [e for e in events if e.is_sweep]
    obs = poi.find_order_blocks(
        df, breaks,
        lookback=p.get("ob_lookback", 30),
        require_sweep=p.get("require_ob_sweep", True),
        require_imbalance=p.get("require_ob_imbalance", True),
        imbalance_window=p.get("imbalance_window", 3))
    fvgs = poi.find_fvgs(df, body_threshold=thr, require_displacement=True)

    # label continuation vs reversal, causally
    kinds, prev = {}, None
    for e in breaks:
        kinds[e.idx] = ("UNKNOWN_FIRST" if prev is None
                        else "BOS" if e.side == prev else "CHOCH")
        prev = e.side

    return {"df": df, "ts": mtf._ts(df["ts"]), "atr": _atr(df).to_numpy(),
            "swings": swings, "breaks": breaks, "sweeps": sweeps,
            "obs": obs, "fvgs": fvgs, "kinds": kinds}


def trace(entry_ts, side, idx, p):
    """Walk back from an order block to the sweep that preceded its break."""
    ts, obs, breaks, sweeps = idx["ts"], idx["obs"], idx["breaks"], idx["sweeps"]
    bar = pd.Timedelta(minutes=15)

    # the order block whose confirmation is the latest one at or before entry
    live = [z for z in obs
            if z.side == side and (ts.iat[z.confirmed_idx] + bar) <= entry_ts]
    if not live:
        return None
    ob = max(live, key=lambda z: z.confirmed_idx)

    brk = next((b for b in breaks if b.idx == ob.confirmed_idx), None)
    if brk is None:
        return None

    want = "bear" if brk.side == "bull" else "bull"
    prior = [s for s in sweeps
             if s.side == want and 0 < brk.idx - s.idx <= p["sweep_window"]]
    sweep = max(prior, key=lambda s: s.idx) if prior else None

    # THE LINK NOBODY CHECKS: does the break actually reverse the leg whose
    # liquidity was taken? For a bull setup the sweep took lows; the break
    # must clear a high that formed AFTER that sweep, otherwise the two events
    # are unrelated and merely happened close together in time.
    same_leg = None
    if sweep is not None:
        same_leg = bool(brk.swing_idx > sweep.idx)

    # was the FVG produced by the displacement leg, or just sitting nearby?
    fvg_hit, fvg_from_leg = False, None
    for f in idx["fvgs"]:
        if f.confirmed_idx <= ob.confirmed_idx and poi.dragon_fruit(ob, f):
            fvg_hit = True
            fvg_from_leg = bool(ob.formed_idx <= f.formed_idx <= brk.idx)
            break

    a = idx["atr"][brk.idx]
    return {
        "sweep_ts": (str(ts.iat[sweep.idx]) if sweep else None),
        "swept_price": (round(float(sweep.level), 8) if sweep else None),
        "bars_sweep_to_bos": (brk.idx - sweep.idx) if sweep else None,
        "bos_ts": str(ts.iat[brk.idx]),
        "bos_direction": brk.side,
        "bos_kind": idx["kinds"].get(brk.idx, "UNKNOWN"),
        "bos_level": round(float(brk.level), 8),
        "bos_displacement": round(float(brk.body_vs_median), 3),
        "bos_swing_age_bars": brk.idx - brk.swing_idx,
        "sweep_and_bos_same_leg": same_leg,
        "ob_formed_ts": str(ts.iat[ob.formed_idx]),
        "ob_confirmed_ts": str(ts.iat[ob.confirmed_idx]),
        "ob_age_bars_at_entry": int(
            (entry_ts - (ts.iat[ob.confirmed_idx] + bar)) / bar),
        "ob_height_atr": (round(float((ob.top - ob.bottom) / a), 3)
                          if np.isfinite(a) and a > 0 else None),
        "ob_body_dominant": bool(ob.meta.get("body_dominant")),
        "ob_gap_size": round(float(ob.meta.get("gap_size", 0.0)), 8),
        "fvg_present": fvg_hit,
        "fvg_from_displacement_leg": fvg_from_leg,
    }


def compare(strong, weak, field):
    """Independent split on one structural attribute."""
    def _vals(rows):
        out = [r[field] for r in rows if r.get(field) is not None]
        return out

    a, b = _vals(strong), _vals(weak)
    if not a or not b:
        return {"field": field, "note": "insufficient data"}

    if isinstance(a[0], bool):
        pa, pb = float(np.mean(a)) * 100, float(np.mean(b)) * 100
        return {"field": field, "type": "rate",
                "strong_pct": round(pa, 1), "weak_pct": round(pb, 1),
                "difference": round(pa - pb, 1),
                "strong_n": len(a), "weak_n": len(b)}
    if isinstance(a[0], str):
        keys = sorted(set(a) | set(b))
        return {"field": field, "type": "category",
                "strong": {k: a.count(k) for k in keys},
                "weak": {k: b.count(k) for k in keys}}

    A, Bv = np.array(a, dtype=float), np.array(b, dtype=float)
    sd = (np.sqrt(A.var(ddof=1) / len(A) + Bv.var(ddof=1) / len(Bv))
          if len(A) > 1 and len(Bv) > 1 else 0.0)
    t = (A.mean() - Bv.mean()) / sd if sd else 0.0
    return {"field": field, "type": "numeric",
            "strong_mean": round(float(A.mean()), 3),
            "weak_mean": round(float(Bv.mean()), 3),
            "difference": round(float(A.mean() - Bv.mean()), 3),
            "t": round(float(t), 2),
            "significant_95": bool(abs(t) > 1.96),
            "strong_n": len(A), "weak_n": len(Bv)}


FIELDS = ["bos_kind", "bos_displacement", "bos_swing_age_bars",
          "bars_sweep_to_bos", "sweep_and_bos_same_leg",
          "ob_age_bars_at_entry", "ob_height_atr", "ob_body_dominant",
          "fvg_present", "fvg_from_displacement_leg"]


def run(symbol, bars, params=None):
    p = params or mtf.PARAMS
    frames, meta = D.load_mtf(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": (meta or {}).get("error", "no data")}

    rep = B.full_report(symbol, frames["5m"], frames["15m"], frames["1h"])
    trades = [t for t in (rep.get("trade_log") or []) if t.get("arm") == "smc"]
    if not trades:
        return {"symbol": symbol, "error": "no SMC trades"}

    idx = build_structure_index(frames["15m"], p)
    rows = []
    for t in trades:
        side = "bull" if t["side"] == "BUY" else "bear"
        lin = trace(pd.Timestamp(t["entry_ts"]), side, idx, p)
        if lin is None:
            continue
        rows.append({**lin,
                     "entry_ts": t["entry_ts"], "side": t["side"],
                     "mfe_r": t.get("mfe_r"), "mae_r": t.get("mae_r"),
                     "outcome": t["outcome"], "net_inr": t["net_inr"],
                     "strong": bool((t.get("mfe_r") or 0) >= STRONG_MFE_R)})

    strong = [r for r in rows if r["strong"]]
    weak = [r for r in rows if not r["strong"]]
    return {"symbol": symbol,
            "coverage_days": (meta or {}).get("coverage_days"),
            "traced": len(rows), "untraced": len(trades) - len(rows),
            "strong_n": len(strong), "weak_n": len(weak),
            "comparisons": [compare(strong, weak, f) for f in FIELDS],
            "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC")
    ap.add_argument("--bars", type=int, default=10000)
    ap.add_argument("--dump")
    a = ap.parse_args()

    s = a.symbol.upper()
    if s not in D.PAIR_MAP:
        D.PAIR_MAP[s] = f"B-{s}_USDT"
        D.CCXT_MAP.setdefault(s, f"{s}/USDT:USDT")

    r = run(s, D.clamp_bars(a.bars))
    if r.get("error"):
        print(f"{s}: {r['error']}")
        return

    print(f"\n{'=' * 84}\n{s} — 15M STRUCTURE LINEAGE   "
          f"({r['coverage_days']} days)\n{'=' * 84}")
    print(f"  SMC trades traced {r['traced']}   untraced {r['untraced']}")
    print(f"  STRONG (MFE >= {STRONG_MFE_R}R)  {r['strong_n']}"
          f"      WEAK  {r['weak_n']}")

    if not r["strong_n"] or not r["weak_n"]:
        print("\n  One side is empty. Nothing to compare.")
        return

    print(f"\n  {'attribute':<32}{'strong':>12}{'weak':>12}{'diff':>10}{'t':>8}")
    print("  " + "-" * 74)
    for c in r["comparisons"]:
        if c.get("note"):
            print(f"  {c['field']:<32}{c['note']:>34}")
        elif c["type"] == "numeric":
            flag = " *" if c["significant_95"] else ""
            print(f"  {c['field']:<32}{c['strong_mean']:>12.2f}"
                  f"{c['weak_mean']:>12.2f}{c['difference']:>+10.2f}"
                  f"{c['t']:>+8.2f}{flag}")
        elif c["type"] == "rate":
            print(f"  {c['field']:<32}{c['strong_pct']:>11.1f}%"
                  f"{c['weak_pct']:>11.1f}%{c['difference']:>+10.1f}")
        else:
            print(f"  {c['field']:<32}strong={c['strong']}  weak={c['weak']}")

    print("\n  * = significant at 95% on this sample. With ~20 trades and 10")
    print("    attributes compared, expect roughly one false positive by")
    print("    chance. Treat a single star as a hypothesis, not a finding.")

    if a.dump:
        with open(a.dump, "w") as f:
            json.dump(r, f, indent=1, default=str)
        print(f"\n  full lineage written to {a.dump}")


if __name__ == "__main__":
    main()
