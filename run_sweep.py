"""run_sweep.py - validate poi_factors setups through smc.py's execution loop.

smc.backtest() calls fetch(), find_setups(), entry_level() and _report() by
name from module globals, so all four can be swapped at runtime. Same fill
logic, same stop-wins-ambiguous-candles rule, same timeout handling, without
editing smc.py at all.
"""
from __future__ import annotations
import argparse
import itertools
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "research"))

import smc
import poi_factors as pf
import export_results as er


def _leg(df, a, b):
    lo = float(df["low"].values[a:b + 1].min())
    hi = float(df["high"].values[a:b + 1].max())
    return lo, hi


def _target(df, side, bar, price, lb):
    sh, sl = smc.swing_lists(df, lb)
    if side == "BUY":
        return smc._next_liquidity_above(sh, bar, price)
    return smc._next_liquidity_below(sl, bar, price)


def setups_from_bos(df, p, cfg):
    """Body-close BOS. The one rule all three sources agreed on."""
    lb = p["SWING_LOOKBACK"]
    buf = p["SL_BUFFER_PCT"] / 100.0
    sw = pf.find_swings(df, cfg["swing_left"], cfg["swing_right"])
    events = pf.find_bos(df, sw, body_threshold=cfg["body_threshold"],
                         require_displacement=cfg["require_displacement"])
    closes = df["close"].values
    out = []
    for e in events:
        if e.is_sweep:
            continue
        lo, hi = _leg(df, e.swing_idx, e.idx)
        if hi <= lo:
            continue
        side = "BUY" if e.side == "bull" else "SELL"
        tgt = _target(df, side, e.idx, closes[e.idx], lb)
        if tgt is None:
            continue
        stop = lo * (1 - buf) if side == "BUY" else hi * (1 + buf)
        out.append({"bar": e.idx, "dir": side, "sweep_bar": e.swing_idx,
                    "stop": stop, "target": tgt,
                    "leg_low": lo, "leg_high": hi})
    return out


def _zone_setups(df, p, cfg, zones):
    """Shared path for OB / FVG / dragon-fruit zones.
    entry_px is explicit so entry_mode can be swept."""
    lb = p["SWING_LOOKBACK"]
    buf = p["SL_BUFFER_PCT"] / 100.0
    closes = df["close"].values
    mode = cfg["entry_mode"]
    out = []
    live = list(zones)
    for i in range(len(df)):
        pf.update_zones(live, df, i, kill_on=cfg["kill_on"])
    for z in zones:
        if z.confirmed_idx >= len(df) - 1:
            continue
        side = "BUY" if z.side == "bull" else "SELL"
        lo, hi = _leg(df, z.formed_idx, z.confirmed_idx)
        if hi <= lo:
            continue
        if mode == "limit_mid":
            entry_px = z.mid
        elif mode == "limit_ote":
            a, b = z.ote()
            entry_px = (a + b) / 2.0
        else:
            entry_px = float(closes[z.confirmed_idx])
        tgt = _target(df, side, z.confirmed_idx, closes[z.confirmed_idx], lb)
        if tgt is None:
            continue
        stop = (z.bottom * (1 - buf)) if side == "BUY" else (z.top * (1 + buf))
        out.append({"bar": z.confirmed_idx, "dir": side, "sweep_bar": z.formed_idx,
                    "stop": stop, "target": tgt, "leg_low": lo, "leg_high": hi,
                    "entry_px": entry_px})
    return out


def setups_from_ob(df, p, cfg):
    sw = pf.find_swings(df, cfg["swing_left"], cfg["swing_right"])
    ev = [e for e in pf.find_bos(df, sw, cfg["body_threshold"],
                                 require_displacement=cfg["require_displacement"])
          if not e.is_sweep]
    zones = pf.find_order_blocks(df, ev, body_dominance_cut=cfg["body_dominance_cut"])
    return _zone_setups(df, p, cfg, zones)


def setups_from_fvg(df, p, cfg):
    zones = pf.find_fvgs(df, cfg["body_threshold"],
                         require_displacement=cfg["require_displacement"])
    return _zone_setups(df, p, cfg, zones)


def setups_dragon_fruit(df, p, cfg):
    """OB and FVG touching - the sources' highest-rated confluence."""
    sw = pf.find_swings(df, cfg["swing_left"], cfg["swing_right"])
    ev = [e for e in pf.find_bos(df, sw, cfg["body_threshold"],
                                 require_displacement=cfg["require_displacement"])
          if not e.is_sweep]
    obs = pf.find_order_blocks(df, ev, body_dominance_cut=cfg["body_dominance_cut"])
    fvgs = pf.find_fvgs(df, cfg["body_threshold"],
                        require_displacement=cfg["require_displacement"])
    keep = [ob for ob in obs if any(pf.dragon_fruit(ob, f) for f in fvgs)]
    return _zone_setups(df, p, cfg, keep)


BUILDERS = {
    "bos_body_close": setups_from_bos,
    "order_block": setups_from_ob,
    "fvg": setups_from_fvg,
    "dragon_fruit": setups_dragon_fruit,
}


_ORIG_ENTRY = smc.entry_level


def _entry_level(setup, p):
    """Honour an explicit entry price when the builder set one."""
    if "entry_px" in setup:
        return float(setup["entry_px"])
    return _ORIG_ENTRY(setup, p)


def run_one(df, factor, cfg, p_over):
    """Run smc.backtest against an injected dataframe and setup builder."""
    smc.fetch = lambda *a, **k: (df, "injected")
    smc.find_setups = lambda d, p: _filter_min_stop(d, BUILDERS[factor](d, p, cfg), cfg)
    smc.entry_level = _entry_level
    smc._report = lambda trades, *a, **k: {"trades": trades}

    res = smc.backtest("INJECTED", "15m", len(df), params=p_over)
    trades = res.get("trades", []) if isinstance(res, dict) else []
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": 0.0,
                "expectancy_r": 0.0, "avg_r": 0.0, "max_dd_r": 0.0}

    risk = [abs(t["entry"] - t["sl"]) / t["entry"] * 100 for t in trades]
    rs = [t["pnl_pct"] / r if r > 0 else 0.0 for t, r in zip(trades, risk)]
    wins = sum(1 for r in rs if r > 0)
    eq = np.cumsum(rs)
    dd = float((eq - np.maximum.accumulate(eq)).min()) if len(eq) else 0.0
    return {"trades": n, "wins": wins, "win_rate": wins / n,
            "expectancy_r": float(np.mean(rs)), "avg_r": float(np.mean(rs)),
            "max_dd_r": dd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USDT:USDT")
    ap.add_argument("--tf", default="15m")
    ap.add_argument("--candles", type=int, default=3000)
    ap.add_argument("--null", type=int, default=0)
    ap.add_argument("--out", default="data/factor_results.json")
    args = ap.parse_args()

    df, src = smc.fetch(args.symbol, args.tf, args.candles)
    if df is None or len(df) < 300:
        print("no usable data")
        return
    df = pf.add_candle_metrics(df)
    train = df.iloc[: len(df) // 2]
    print(f"{len(df)} bars from {src}\n")

    rows = []
    for factor in BUILDERS:
        for body_pct, disp, cost in itertools.product(
                [0.75, 0.85], [True, False], [0.06, 0.10, 0.15]):
            thr = pf.calibrate_body_threshold(train, target_pct=body_pct)
            cfg = {"body_threshold": thr, "require_displacement": disp,
                   "swing_left": 2, "swing_right": 2, "entry_mode": "limit_ote",
                   "kill_on": "full", "body_dominance_cut": 0.6}
            p_over = {"ROUND_TRIP_COST_PCT": cost}
            stats = run_one(df, factor, cfg, p_over)
            print(f"  {factor:16s} pct={body_pct} disp={str(disp):5s} cost={cost} "
                  f"-> {stats['trades']:4d} trades  wr={stats['win_rate']:.3f} "
                  f"exp={stats['expectancy_r']:+.3f}")
            if stats["trades"] < 10:
                continue
            if args.null:
                null = er.run_null_baseline(
                    df, lambda d, **kw: run_one(d, factor, cfg, p_over),
                    {}, iterations=args.null)
            else:
                null = {"null_mean": None, "null_p05": None,
                        "null_p95": None, "null_n": 0}
            rows.append(er.build_row(
                factor, {"body_pct": body_pct, "displacement": disp, "cost_pct": cost},
                stats, null))

    path = er.export(rows, {
        "symbol": args.symbol, "timeframe": args.tf, "bars": len(df),
        "fee_bps_roundtrip": "swept 6-15",
        "fee_mode": "flat (maker/taker split pending)",
        "body_threshold": "calibrated per row", "null_iterations": args.null,
    }, args.out)
    print(f"\nwrote {path} with {len(rows)} rows")




def _atr(df, period=14):
    """Wilder ATR. Used only to reject setups whose stop is inside the noise."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) <= period:
        return out
    out[period] = tr[1:period + 1].mean()
    for i in range(period + 1, len(tr)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def _filter_min_stop(df, setups, cfg):
    """Drop setups whose stop sits closer than min_stop_atr * ATR.

    Without this, FVG zones produce stops a few dollars wide. Bar-level OHLC
    cannot honestly resolve whether such a stop or the target came first, so
    the resulting R multiples are measurement error, not edge.
    """
    k = cfg.get("min_stop_atr", 0.5)
    if not k:
        return setups
    atr = _atr(df)
    out = []
    for s in setups:
        i = s["bar"]
        a = atr[i] if i < len(atr) else np.nan
        if np.isnan(a) or a <= 0:
            continue
        entry = s.get("entry_px")
        if entry is None:
            entry = smc.entry_level(s, smc.PARAMS)
        if entry is None:
            continue
        if abs(float(entry) - float(s["stop"])) >= k * a:
            out.append(s)
    return out

if __name__ == "__main__":
    main()
