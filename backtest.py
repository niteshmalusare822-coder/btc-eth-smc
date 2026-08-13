"""
backtest.py — correct measurement first, profit second.

Three arms are always run on the SAME bars, with the SAME stops, targets, fees,
slippage and session filter. The only difference between them is WHEN they
enter:

    RANDOM   coin-flip entries, matched trade count and stop distribution
    SMC      15M setup only, no 1H bias, no 5M trigger
    SMC_MTF  1H bias + 15M setup + 5M trigger

If SMC_MTF does not beat RANDOM, the extra timeframes are not adding
information and the answer is that there is no edge. That statement is the
deliverable, not a parameter search that makes the curve go up.

Also here: in-sample / out-of-sample split, walk-forward, and parameter
sensitivity. A result that survives only one parameter combination is
reported as fragile.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import mtf_engine as mtf
import poi_factors as poi
import risk as R

SESSION_HOURS = None  # e.g. (7, 22) UTC. None = all hours.


# ---------------------------------------------------------------------------
# EXIT
# ---------------------------------------------------------------------------
def simulate(df, side, entry, sl, tps, start, max_hold):
    """Scale out at TP1/TP2/TP3, one third each, stop on the remainder.

    Stop is checked BEFORE targets on every bar. A candle spanning both is a
    loss. Without tick data that is the only honest assumption.
    """
    hi = df["high"].to_numpy()
    lo = df["low"].to_numpy()
    cl = df["close"].to_numpy()
    n = len(df)
    last = min(start + max_hold, n - 1)

    remaining = 1.0
    realised_px = []          # (fraction, exit_price)
    hit = []
    tp_px = [t["price"] for t in tps]
    nxt = 0

    for j in range(start, last + 1):
        stopped = lo[j] <= sl if side == "bull" else hi[j] >= sl
        if stopped:
            realised_px.append((remaining, sl))
            return realised_px, hit, "STOP", j

        while nxt < len(tp_px):
            reached = hi[j] >= tp_px[nxt] if side == "bull" else lo[j] <= tp_px[nxt]
            if not reached:
                break
            frac = min(1.0 / 3.0, remaining)
            realised_px.append((frac, tp_px[nxt]))
            remaining -= frac
            hit.append(f"TP{nxt+1}")
            nxt += 1
            if remaining <= 1e-9:
                return realised_px, hit, "TP_ALL", j
        if remaining <= 1e-9:
            return realised_px, hit, "TP_ALL", j

    if remaining > 0:
        realised_px.append((remaining, cl[last]))
    return realised_px, hit, ("TIMEOUT" if not hit else "PARTIAL"), last


def pnl_inr(side, entry, legs, qty, usdt_inr, notional_inr, bars_held, tf_min):
    """Gross and net rupees. Net subtracts round-trip fee, slippage and funding
    on the whole notional. Nothing is netted off quietly."""
    gross = 0.0
    for frac, px in legs:
        move = (px - entry) if side == "bull" else (entry - px)
        gross += move * qty * frac * usdt_inr
    fees = notional_inr * R.ROUND_TRIP_FEE
    slip = notional_inr * R.ROUND_TRIP_SLIP
    funding = R.funding_cost_inr(notional_inr, bars_held, tf_min)
    return gross, gross - fees - slip - funding, fees, slip, funding


# ---------------------------------------------------------------------------
# ARMS
# ---------------------------------------------------------------------------
def _open_trade(symbol, df, i, side, entry, stop_level, atr, max_hold, tf_min):
    direction = "BUY" if side == "bull" else "SELL"
    buf = 0.10 * abs(entry - stop_level) if stop_level is not None else 0.0
    sl = (stop_level - buf) if side == "bull" else (stop_level + buf)

    lim = entry + 6 * atr if side == "bull" else entry - 6 * atr
    s = R.size_position(symbol, direction, entry, sl, atr=atr, structure_limit=lim)
    if not s.ok:
        return None, s.reason

    legs, hit, outcome, ex = simulate(df, side, entry, sl, s.tps, i, max_hold)
    held = ex - i
    gross, net, fees, slip, fund = pnl_inr(side, entry, legs, s.qty, R.USDT_INR,
                                           s.notional_inr, held, tf_min)
    return {
        "i": i, "exit_i": ex, "ts": str(df["ts"].iat[i]),
        "side": direction, "entry": entry, "sl": sl,
        "tps": s.tps, "tp_hit": hit, "outcome": outcome,
        "qty": s.qty, "notional_inr": s.notional_inr,
        "leverage_used": s.leverage_used, "leverage_allowed": s.leverage_allowed,
        "risk_inr": s.risk_inr, "cost_in_r": s.cost_in_r,
        "gross_inr": gross, "net_inr": net,
        "fees_inr": fees, "slippage_inr": slip, "funding_inr": fund,
        "bars_held": held,
    }, None


def run_arm(symbol, df5, ctx, arm, cfg, lo_i, hi_i, rng=None):
    """arm: 'random' | 'smc' | 'smc_mtf'. Same exits for all three."""
    atr = _atr(df5, 14).to_numpy()
    lows = df5["low"].to_numpy()
    highs = df5["high"].to_numpy()
    ts_all = mtf._ns(df5["ts"])
    tf_min = 5
    trades, rejected = [], 0
    busy_until = -1

    if arm == "random":
        idxs = sorted(rng.integers(lo_i, hi_i, cfg["n_random"]).tolist())
        for i in idxs:
            if i <= busy_until or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            if not _in_session(ts_all.iat[i]):
                continue
            side = "bull" if rng.random() < 0.5 else "bear"
            entry = df5["open"].iat[i]
            stop = entry - cfg["rand_sl_atr"] * atr[i] if side == "bull" \
                else entry + cfg["rand_sl_atr"] * atr[i]
            t, why = _open_trade(symbol, df5, i, side, entry, stop, atr[i],
                                 cfg["max_hold"], tf_min)
            if t:
                trades.append(t)
                busy_until = t["exit_i"]
            else:
                rejected += 1
        return trades, rejected

    for i in range(lo_i, hi_i):
        if i <= busy_until or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        ts = ts_all.iat[i]
        if not _in_session(ts):
            continue

        if arm == "smc_mtf":
            action, s, side, level, _ = mtf.decide(
                ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts,
                lows[i], highs[i])
            if action == "NO_TRADE":
                continue
        else:  # smc: 15M setup only, no bias and no trigger gate
            side, s, level = None, None, None
            for cand in mtf.active_setups_at(ctx["setups"], ts):
                lv = cand.ote_high if cand.side == "bull" else cand.ote_low
                touched = lows[i] <= lv if cand.side == "bull" else highs[i] >= lv
                if touched:
                    side, s, level = cand.side, cand, lv
                    break
            if s is None:
                continue

        t, why = _open_trade(symbol, df5, i, side, level, s.stop_level, atr[i],
                             cfg["max_hold"], tf_min)
        if t:
            trades.append(t)
            busy_until = t["exit_i"]
        else:
            rejected += 1

    return trades, rejected


def _in_session(ts):
    if SESSION_HOURS is None:
        return True
    lo, hi = SESSION_HOURS
    return lo <= ts.hour < hi


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ---------------------------------------------------------------------------
# METRICS
# ---------------------------------------------------------------------------
def metrics(trades, label):
    if not trades:
        return {"arm": label, "trades": 0, "note": "no trades"}
    net = np.array([t["net_inr"] for t in trades])
    gross = np.array([t["gross_inr"] for t in trades])
    wins, losses = net[net > 0], net[net <= 0]

    eq = np.cumsum(net)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))
    dd = float((peak[1:] - eq).max())

    longs = [t for t in trades if t["side"] == "BUY"]
    shorts = [t for t in trades if t["side"] == "SELL"]

    def _side(ts_):
        if not ts_:
            return {"trades": 0}
        a = np.array([t["net_inr"] for t in ts_])
        return {"trades": len(a), "win_pct": round(float((a > 0).mean() * 100), 1),
                "net_inr": round(float(a.sum()), 0)}

    gp, gl = float(wins.sum()), float(abs(losses.sum()))
    return {
        "arm": label,
        "trades": len(net),
        "win_rate_pct": round(float((net > 0).mean() * 100), 1),
        "avg_win_inr": round(float(wins.mean()), 0) if wins.size else 0.0,
        "avg_loss_inr": round(float(losses.mean()), 0) if losses.size else 0.0,
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
        "expectancy_inr": round(float(net.mean()), 1),
        "gross_pnl_inr": round(float(gross.sum()), 0),
        "net_pnl_inr": round(float(net.sum()), 0),
        "max_drawdown_inr": round(dd, 0),
        "fees_paid_inr": round(sum(t["fees_inr"] for t in trades), 0),
        "slippage_inr": round(sum(t["slippage_inr"] for t in trades), 0),
        "funding_inr": round(sum(t["funding_inr"] for t in trades), 0),
        "median_cost_in_r": round(float(np.median([t["cost_in_r"] for t in trades])), 3),
        "tp1_hit": sum(1 for t in trades if "TP1" in t["tp_hit"]),
        "tp2_hit": sum(1 for t in trades if "TP2" in t["tp_hit"]),
        "tp3_hit": sum(1 for t in trades if "TP3" in t["tp_hit"]),
        "stopped": sum(1 for t in trades if t["outcome"] == "STOP"),
        "timeouts": sum(1 for t in trades if t["outcome"] == "TIMEOUT"),
        "long": _side(longs), "short": _side(shorts),
    }


# ---------------------------------------------------------------------------
# ORCHESTRATION
# ---------------------------------------------------------------------------
DEFAULT_CFG = {"max_hold": 60, "rand_sl_atr": 1.0, "n_random": 400,
               "is_frac": 0.60, "wf_folds": 4, "seed": 42}


def full_report(symbol, df5, df15, df1h, cfg=None, params=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    params = params or mtf.PARAMS
    rng = np.random.default_rng(cfg["seed"])

    ctx = mtf.build_context(df5, df15, df1h, params)
    n = len(df5)
    warm = 100
    split = int(n * cfg["is_frac"])

    out = {"symbol": symbol, "bars_5m": n,
           "in_sample_bars": split - warm, "out_of_sample_bars": n - split,
           "costs": R.cost_summary(), "params": params}

    for name, lo, hi in [("in_sample", warm, split), ("out_of_sample", split, n - 2)]:
        arms = []
        for arm in ("random", "smc", "smc_mtf"):
            tr, rej = run_arm(symbol, df5, ctx, arm, cfg, lo, hi,
                              rng=np.random.default_rng(cfg["seed"]))
            m = metrics(tr, arm.upper())
            m["rejected_by_sizing"] = rej
            arms.append(m)
        out[name] = arms

    out["walk_forward"] = _walk_forward(symbol, df5, ctx, cfg, warm, n)
    out["sensitivity"] = _sensitivity(symbol, df5, df15, df1h, cfg, params, warm, n)
    out["verdict"] = _verdict(out)
    return out


def _walk_forward(symbol, df5, ctx, cfg, warm, n):
    folds = cfg["wf_folds"]
    edges = np.linspace(warm, n - 2, folds + 1).astype(int)
    res = []
    for k in range(folds):
        lo, hi = edges[k], edges[k + 1]
        rows = {}
        for arm in ("random", "smc_mtf"):
            tr, _ = run_arm(symbol, df5, ctx, arm, cfg, lo, hi,
                            rng=np.random.default_rng(cfg["seed"] + k))
            m = metrics(tr, arm)
            rows[arm] = {"trades": m.get("trades", 0),
                         "net_inr": m.get("net_inr", m.get("net_pnl_inr", 0)),
                         "expectancy_inr": m.get("expectancy_inr", 0)}
        res.append({"fold": k + 1, "bars": int(hi - lo), **rows})
    beat = sum(1 for r in res
               if r["smc_mtf"]["expectancy_inr"] > r["random"]["expectancy_inr"])
    return {"folds": res, "folds_beating_random": beat, "total_folds": folds}


def _sensitivity(symbol, df5, df15, df1h, cfg, params, warm, n):
    """Nudge one parameter at a time. A result that only survives one exact
    setting is fragile, whatever the headline number says."""
    grid = {"max_age": [40, 60, 90], "sweep_window": [10, 20, 30],
            "ote_high": [0.705, 0.79, 0.886]}
    rows = []
    for key, vals in grid.items():
        for v in vals:
            p = {**params, key: v}
            try:
                ctx = mtf.build_context(df5, df15, df1h, p)
                tr, _ = run_arm(symbol, df5, ctx, "smc_mtf", cfg, warm, n - 2)
                m = metrics(tr, "smc_mtf")
                rows.append({"param": key, "value": v,
                             "trades": m.get("trades", 0),
                             "expectancy_inr": m.get("expectancy_inr", 0),
                             "net_inr": m.get("net_pnl_inr", 0)})
            except Exception as e:
                rows.append({"param": key, "value": v, "error": str(e)})
    exps = [r.get("expectancy_inr", 0) for r in rows if "error" not in r]
    positive = sum(1 for e in exps if e > 0)
    return {"runs": rows, "positive_of_total": f"{positive}/{len(exps)}",
            "fragile": positive <= max(1, len(exps) // 4)}


def _verdict(out):
    oos = {m["arm"]: m for m in out["out_of_sample"]}
    smc = oos.get("SMC_MTF", {})
    rnd = oos.get("RANDOM", {})
    n = smc.get("trades", 0)
    e_smc = smc.get("expectancy_inr", 0) or 0
    e_rnd = rnd.get("expectancy_inr", 0) or 0
    edge = e_smc - e_rnd
    wf = out["walk_forward"]

    if n == 0:
        return {"profitable": False, "edge_vs_random_inr": None,
                "statement": "No trades survived out of sample. Nothing to measure."}
    if n < 30:
        return {"profitable": False, "edge_vs_random_inr": round(edge, 1),
                "statement": f"Only {n} out-of-sample trades. Too few to conclude "
                             f"anything. Treat as noise."}
    if e_smc <= 0:
        return {"profitable": False, "edge_vs_random_inr": round(edge, 1),
                "statement": f"UNPROFITABLE. Expectancy Rs.{e_smc:.0f} per trade "
                             f"after fees, slippage and funding."}
    if edge <= 0:
        return {"profitable": False, "edge_vs_random_inr": round(edge, 1),
                "statement": f"Positive P&L but it does NOT beat random entry "
                             f"(Rs.{e_smc:.0f} vs Rs.{e_rnd:.0f}). That is not an edge."}
    if wf["folds_beating_random"] < wf["total_folds"] - 1:
        return {"profitable": False, "edge_vs_random_inr": round(edge, 1),
                "statement": f"Beats random overall but only in "
                             f"{wf['folds_beating_random']}/{wf['total_folds']} "
                             f"walk-forward folds. Not stable."}
    if out["sensitivity"]["fragile"]:
        return {"profitable": False, "edge_vs_random_inr": round(edge, 1),
                "statement": "Edge exists at the chosen parameters but collapses "
                             "when they are nudged. Treat as overfit."}
    return {"profitable": True, "edge_vs_random_inr": round(edge, 1),
            "statement": f"Edge of Rs.{edge:.0f} per trade over random, stable "
                         f"across folds and parameter nudges, on {n} trades."}
