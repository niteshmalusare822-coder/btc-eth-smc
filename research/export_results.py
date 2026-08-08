"""export_results.py - turns a factor sweep into data/factor_results.json.

A Wilson interval only tells you if the sample is big enough. It does not tell
you whether the same edge appears in data with no real structure. Block-shuffle
keeps volatility clustering but destroys sequence, so anything that still
"works" on shuffled data is reading shape, not signal.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd


def wilson(wins, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def block_shuffle(df, block=64, seed=None):
    """Rebuild OHLC from block-shuffled log returns."""
    rng = np.random.default_rng(seed)
    close = df["close"].to_numpy(dtype=float)
    lr = np.diff(np.log(close), prepend=np.log(close[0]))
    blocks = [lr[i:i + block] for i in range(0, len(lr), block)]
    rng.shuffle(blocks)
    sh = np.concatenate(blocks)[:len(lr)]
    new_close = close[0] * np.exp(np.cumsum(sh))
    scale = new_close / close
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = df[col].to_numpy(dtype=float) * scale
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    return out


def run_null_baseline(df, backtest_fn, params, iterations=200, block=64, metric="win_rate"):
    """backtest_fn(df, **params) must return a dict containing `metric`."""
    s = []
    for k in range(iterations):
        try:
            r = backtest_fn(block_shuffle(df, block=block, seed=k), **params)
        except Exception:
            continue
        v = r.get(metric)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            s.append(float(v))
    if not s:
        return {"null_mean": None, "null_p05": None, "null_p95": None, "null_n": 0}
    a = np.array(s)
    return {"null_mean": float(a.mean()),
            "null_p05": float(np.quantile(a, 0.05)),
            "null_p95": float(np.quantile(a, 0.95)),
            "null_n": len(a),
            "_samples": a}


def build_row(factor, params, stats, null):
    """stats needs: trades, wins, win_rate; optional expectancy_r, avg_r, max_dd_r."""
    t = int(stats["trades"])
    w = int(stats["wins"])
    lo, hi = wilson(w, t)
    pctl = None
    if null.get("_samples") is not None and len(null["_samples"]):
        pctl = float((null["_samples"] < stats["win_rate"]).mean())
    rd = lambda x: None if x is None else round(x, 4)
    return {
        "factor": factor,
        "params": params,
        "trades": t,
        "wins": w,
        "win_rate": round(float(stats["win_rate"]), 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "expectancy_r": round(float(stats.get("expectancy_r", 0.0)), 4),
        "avg_r": round(float(stats.get("avg_r", 0.0)), 4),
        "max_dd_r": round(float(stats.get("max_dd_r", 0.0)), 4),
        "null_mean": rd(null["null_mean"]),
        "null_p05": rd(null["null_p05"]),
        "null_p95": rd(null["null_p95"]),
        "null_n": null.get("null_n", 0),
        "percentile_vs_null": rd(pctl),
    }


def export(rows, run_meta, path="data/factor_results.json"):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       **run_meta},
               "results": rows}
    p.write_text(json.dumps(payload, indent=2))
    return p


EXPORT_COMPLETE = True
