#!/usr/bin/env python3
"""
collect.py — pool trades across many symbols to reach a decidable sample.

WHY THIS EXISTS
---------------
On four symbols over 36 days the SMC arm produced 55 out-of-sample trades and a
pooled edge of -0.09 sigma against the matched random baseline. That is not a
negative result; it is not a result at all. The sample cannot distinguish an
edge of +50 rupees per trade from an edge of zero.

Nothing about the strategy is changed here. The only variable is how many
independent trades the same rules are measured over.

WHAT IT DOES NOT DO
-------------------
It does not search for the best symbols. Every symbol that returns usable data
is included and reported, winners and losers alike. Dropping the losers after
seeing the results is how a backtest gets fabricated, so the per-symbol table
is printed in full and the pooled figure uses all of it.

USAGE
    python3 collect.py --discover                 list tradeable CoinDCX pairs
    python3 collect.py --symbols BTC,ETH,SOL,XRP  run those
    python3 collect.py --from-file symbols.txt    run a saved list
    python3 collect.py --symbols ... --bars 20000 --out run1.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback

import numpy as np

import backtest as B
import data as D

ARM = "SMC"                 # the statistically testable arm
MATCHED = "MATCHED_RANDOM_vs_SMC"


# ---------------------------------------------------------------------------
def discover_pairs(limit=60):
    """Ask CoinDCX which futures pairs exist, so the symbol list is not guessed.

    data.PAIR_MAP only knows four. Anything else has to be looked up, and a
    wrong pair string fails silently as "no data" rather than as an error.
    """
    import requests
    urls = ["https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments",
            "https://public.coindcx.com/market_data/v3/current_prices/futures/rt"]
    found = []
    for u in urls:
        try:
            r = requests.get(u, timeout=20)
            r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else list(
                (data.get("prices") or data.get("data") or data).keys())
            for it in items:
                s = it if isinstance(it, str) else str(it)
                if s.startswith("B-") and s.endswith("_USDT"):
                    found.append(s)
        except Exception:
            continue
    out = sorted(set(found))
    return out[:limit]


def register(symbol, pair):
    """Teach data.py about a pair for this process only. Nothing is written to
    the repository, so a bad discovery cannot poison the deployed config."""
    D.PAIR_MAP[symbol] = pair
    D.CCXT_MAP.setdefault(symbol, f"{symbol}/USDT:USDT")


# ---------------------------------------------------------------------------
def run_symbol(symbol, bars, cfg):
    frames, meta = D.load_mtf(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": (meta or {}).get("error", "no data")}
    rep = B.full_report(symbol, frames["5m"], frames["15m"], frames["1h"],
                        cfg=cfg)
    oos = {m["arm"]: m for m in rep.get("out_of_sample", [])}
    smc, rnd = oos.get(ARM, {}), oos.get(MATCHED, {})
    log = [t for t in (rep.get("trade_log") or []) if t.get("arm") == "smc"]

    return {
        "symbol": symbol,
        "coverage_days": (meta or {}).get("coverage_days"),
        "source": (meta or {}).get("source"),
        "trades": smc.get("trades", 0),
        "win_rate_pct": smc.get("win_rate_pct"),
        "profit_factor": smc.get("profit_factor"),
        "expectancy_inr": smc.get("expectancy_inr"),
        "gross_pnl_inr": smc.get("gross_pnl_inr"),
        "net_pnl_inr": smc.get("net_pnl_inr"),
        "max_drawdown_inr": smc.get("max_drawdown_inr"),
        "median_cost_in_r": smc.get("median_cost_in_r"),
        "long": smc.get("long"), "short": smc.get("short"),
        "random_mean_expectancy": rnd.get("random_mean_expectancy"),
        "random_std_expectancy": rnd.get("random_std_expectancy"),
        "verdict": (rep.get("verdict") or {}).get("verdict"),
        "wf": f"{(rep.get('walk_forward') or {}).get('folds_beating_random')}"
              f"/{(rep.get('walk_forward') or {}).get('folds_scored')}",
        "_trades": log,
    }


def pooled(rows):
    """Inverse-variance weighted edge across symbols.

    Weighting by 1/sigma^2 rather than averaging expectancies stops a symbol
    with 4 noisy trades from carrying the same weight as one with 40.
    """
    usable = [r for r in rows
              if r.get("trades") and r.get("random_std_expectancy")
              and r.get("expectancy_inr") is not None
              and r.get("random_mean_expectancy") is not None]
    if not usable:
        return {"symbols": 0, "note": "no symbol produced a comparable arm"}

    w = np.array([1.0 / max(r["random_std_expectancy"], 1e-9) ** 2
                  for r in usable])
    e = np.array([r["expectancy_inr"] - r["random_mean_expectancy"]
                  for r in usable])
    edge = float((w * e).sum() / w.sum())
    se = float(np.sqrt(1.0 / w.sum()))
    z = edge / se if se else 0.0

    all_tr = [t for r in usable for t in r["_trades"]]
    net = np.array([t["net_inr"] for t in all_tr], dtype=float) \
        if all_tr else np.array([0.0])
    longs = [t for t in all_tr if t["side"] == "BUY"]
    shorts = [t for t in all_tr if t["side"] == "SELL"]

    def _side(rows_):
        if not rows_:
            return {"trades": 0}
        a = np.array([t["net_inr"] for t in rows_], dtype=float)
        return {"trades": len(a),
                "win_rate_pct": round(float((a > 0).mean() * 100), 1),
                "per_trade_inr": round(float(a.mean()), 1),
                "net_inr": round(float(a.sum()), 0)}

    if abs(z) < 1.96:
        verdict = ("NOT DECIDABLE — the pooled edge is inside the noise band. "
                   "More trades, not different rules.")
    elif edge > 0:
        verdict = ("Pooled edge is positive and outside the noise band. This "
                   "is worth walk-forward and sensitivity confirmation before "
                   "anything is called an edge.")
    else:
        verdict = ("Pooled edge is significantly NEGATIVE. The rules lose to a "
                   "coin flip on matched entries. Stop tuning and reconsider "
                   "the premise.")

    return {
        "symbols": len(usable),
        "total_trades": len(all_tr),
        "pooled_edge_inr": round(edge, 1),
        "standard_error": round(se, 1),
        "sigma": round(z, 2),
        "significant_at_95pct": bool(abs(z) > 1.96),
        "trades_needed_for_95pct": (
            int(((1.96 + 0.84) * float(np.std(e, ddof=1) if len(e) > 1
                                       else se) / abs(edge)) ** 2)
            if edge else None),
        "pooled_net_inr": round(float(net.sum()), 0),
        "long": _side(longs), "short": _side(shorts),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", help="comma separated, e.g. BTC,ETH,SOL")
    p.add_argument("--from-file")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--bars", type=int, default=10000)
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--out", default="collect_results.json")
    a = p.parse_args()

    if a.discover:
        pairs = discover_pairs()
        if not pairs:
            print("no pairs returned; check network access to CoinDCX")
            sys.exit(1)
        print(f"{len(pairs)} futures pairs found:\n")
        for pr in pairs:
            print(f"  {pr.replace('B-', '').replace('_USDT', ''):10s} {pr}")
        print("\nSave the ones you want, then run:")
        print("  python3 collect.py --symbols BTC,ETH,SOL,XRP")
        return

    if a.from_file:
        syms = [s.strip().upper() for s in open(a.from_file)
                if s.strip() and not s.startswith("#")]
    elif a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    else:
        syms = list(D.PAIR_MAP)

    for s in syms:
        if s not in D.PAIR_MAP:
            register(s, f"B-{s}_USDT")

    cfg = {**B.DEFAULT_CFG, "matched_seeds": a.seeds}
    bars = D.clamp_bars(a.bars)
    print(f"{len(syms)} symbols, {bars} 5m bars each, {a.seeds} matched seeds\n")

    rows, t0 = [], time.time()
    for i, s in enumerate(syms, 1):
        t1 = time.time()
        try:
            r = run_symbol(s, bars, cfg)
        except Exception as e:
            traceback.print_exc()
            r = {"symbol": s, "error": str(e)}
        rows.append(r)
        if r.get("error"):
            print(f"  [{i}/{len(syms)}] {s:8s} FAILED: {r['error']}")
        else:
            print(f"  [{i}/{len(syms)}] {s:8s} n={r['trades']:3} "
                  f"exp=Rs.{str(r['expectancy_inr']):>8} "
                  f"rnd=Rs.{str(r['random_mean_expectancy']):>8} "
                  f"{r['coverage_days']}d  {time.time() - t1:.0f}s")

    print(f"\ncollected in {time.time() - t0:.0f}s")

    print("\n" + "=" * 92)
    print("PER SYMBOL — SMC arm, out of sample. Every symbol shown, none dropped.")
    print("=" * 92)
    print(f"{'sym':<8}{'n':>4}{'win%':>7}{'PF':>6}{'exp':>9}{'random':>9}"
          f"{'edge':>8}{'gross':>9}{'net':>9}{'cost/R':>8}{'WF':>6}")
    print("-" * 92)
    for r in rows:
        if r.get("error") or not r.get("trades"):
            print(f"{r['symbol']:<8}  {r.get('error', 'no trades')}")
            continue
        edge = (r["expectancy_inr"] - r["random_mean_expectancy"]
                if r.get("random_mean_expectancy") is not None else None)
        print(f"{r['symbol']:<8}{r['trades']:>4}{r['win_rate_pct']:>7.1f}"
              f"{str(r['profit_factor']):>6}{r['expectancy_inr']:>9.1f}"
              f"{str(r['random_mean_expectancy']):>9}"
              f"{(f'{edge:+.1f}' if edge is not None else '-'):>8}"
              f"{str(r['gross_pnl_inr']):>9}{str(r['net_pnl_inr']):>9}"
              f"{str(r['median_cost_in_r']):>8}{r['wf']:>6}")

    pool = pooled(rows)
    print("\n" + "=" * 92)
    print("POOLED")
    print("=" * 92)
    for k in ("symbols", "total_trades", "pooled_edge_inr", "standard_error",
              "sigma", "significant_at_95pct", "trades_needed_for_95pct",
              "pooled_net_inr"):
        print(f"  {k:26s} {pool.get(k)}")
    print(f"  {'long':26s} {pool.get('long')}")
    print(f"  {'short':26s} {pool.get('short')}")
    print(f"\n  {pool.get('verdict')}")

    with open(a.out, "w") as f:
        json.dump({"per_symbol": [{k: v for k, v in r.items()
                                   if k != "_trades"} for r in rows],
                   "pooled": {k: v for k, v in pool.items()
                              if not k.startswith("_")}}, f, indent=1,
                  default=str)
    print(f"\nwritten to {a.out}")


if __name__ == "__main__":
    main()
