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
    """Scale out across the REACHABLE targets, stop on the remainder.

    Stop is checked BEFORE targets on every bar. A candle spanning both is a
    loss. Without tick data that is the only honest assumption.

    BUG FIX: this used every level in the ladder, including ones flagged
    unreachable. Two thirds of each position was aimed at prices that could
    not print, so the position could only ever be closed by the stop or the
    time stop, and hitting TP1 alone still netted a loss after full round-trip
    costs. Unreachable levels are now dropped and the size is split across
    what is actually left.
    """
    hi = df["high"].to_numpy()
    lo = df["low"].to_numpy()
    cl = df["close"].to_numpy()
    n = len(df)
    last = min(start + max_hold, n - 1)

    live = [t for t in (tps or []) if t.get("reachable")]
    if not live:
        live = [tps[0]] if tps else []
    share = 1.0 / len(live) if live else 1.0

    remaining = 1.0
    realised_px = []          # (fraction, exit_price)
    hit = []
    tp_px = [t["price"] for t in live]
    tp_name = [t["level"] for t in live]
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
            frac = min(share, remaining)
            realised_px.append((frac, tp_px[nxt]))
            remaining -= frac
            hit.append(tp_name[nxt])
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
def _find_fill(df, side, level, start, max_wait):
    """First bar at or after `start` whose range reaches the resting limit.

    start is signal_bar + 1. The signal bar itself is never eligible: its range
    was already complete when the decision was made, so filling on it would be
    trading on information the order did not have.
    """
    lows = df["low"].to_numpy()
    highs = df["high"].to_numpy()
    last = min(start + max_wait, len(df) - 2)
    for j in range(start, last + 1):
        if side == "bull" and lows[j] <= level:
            return j
        if side == "bear" and highs[j] >= level:
            return j
    return None


def _open_trade(symbol, df, sig_i, side, level, stop_level, atr, cfg, tf_min,
                bias=None, setup=None, trigger=None, arm=""):
    """Place a resting limit at the close of sig_i, fill from sig_i+1 onward.

    Returns (trade_dict, reject_reason). trade_dict carries the full audit
    trail: what each timeframe said, when the order was placed, when it filled,
    when and why it closed.
    """
    direction = "BUY" if side == "bull" else "SELL"
    buf = 0.10 * abs(level - stop_level) if stop_level is not None else 0.0
    sl = (stop_level - buf) if side == "bull" else (stop_level + buf)
    if (side == "bull" and level <= sl) or (side == "bear" and level >= sl):
        return None, "entry on the wrong side of the stop"

    fill_i = _find_fill(df, side, level, sig_i + 1, cfg["max_wait"])
    if fill_i is None:
        return None, "limit never filled"

    lim = level + 6 * atr if side == "bull" else level - 6 * atr
    s = R.size_position(symbol, direction, level, sl, atr=atr, structure_limit=lim)
    if not s.ok:
        return None, s.reason

    legs, hit, outcome, ex = simulate(df, side, level, sl, s.tps, fill_i, cfg["max_hold"])
    held = ex - fill_i
    gross, net, fees, slip, fund = pnl_inr(side, level, legs, s.qty, R.USDT_INR,
                                           s.notional_inr, held, tf_min)

    reason = {"STOP": "stop hit", "TP_ALL": "all reachable targets hit",
              "PARTIAL": "partial targets then time stop",
              "TIMEOUT": "time stop, no target reached"}.get(outcome, outcome)

    return {
        "arm": arm,
        "signal_ts": str(df["ts"].iat[sig_i]),
        "entry_ts": str(df["ts"].iat[fill_i]),
        "exit_ts": str(df["ts"].iat[ex]),
        "bars_to_fill": fill_i - sig_i,
        "bias_1h": bias, "setup_15m": setup, "trigger_5m": trigger,
        "side": direction,
        "entry": round(level, 8), "sl": round(sl, 8),
        "exit_reason": reason, "outcome": outcome, "tp_hit": hit,
        "targets": [{"level": t["level"], "price": t["price"],
                     "r": t["r_multiple"], "reachable": t["reachable"]}
                    for t in s.tps],
        "qty": s.qty, "notional_inr": round(s.notional_inr, 0),
        "leverage_used": s.leverage_used, "leverage_allowed": s.leverage_allowed,
        "risk_inr": round(s.risk_inr, 0), "cost_in_r": round(s.cost_in_r, 3),
        "gross_inr": round(gross, 0), "net_inr": round(net, 0),
        "fees_inr": round(fees, 0), "slippage_inr": round(slip, 0),
        "funding_inr": round(fund, 2),
        "bars_held": held,
        "i": sig_i, "fill_i": fill_i, "exit_i": ex,
    }, None


def run_arm(symbol, df5, ctx, arm, cfg, lo_i, hi_i, rng=None, matched=None):
    """arm: 'random' | 'smc' | 'smc_mtf' | 'matched_random'.

    All arms share _open_trade, so entry timing, fill rules, sizing, costs and
    exits are identical. Only the decision of WHEN and WHICH SIDE differs.

    matched_random replays a given trade list at the SAME signal bars with the
    SAME stop distances and a coin-flipped side. That is the fair null: it
    isolates whether the setup picks direction and timing better than chance,
    rather than comparing against trades taken at unrelated moments.
    """
    atr = _atr(df5, 14).to_numpy()
    ts_all = mtf._ts(df5["ts"])
    tf_min = 5
    trades, rejected = [], {}
    busy_until = -1

    def _rej(why):
        rejected[why] = rejected.get(why, 0) + 1

    if arm == "matched_random":
        for t in (matched or []):
            i = t["i"]
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            side = "bull" if rng.random() < 0.5 else "bear"
            level = t["entry"]
            dist = abs(t["entry"] - t["sl"])
            stop = level - dist if side == "bull" else level + dist
            tr, why = _open_trade(symbol, df5, i, side, level, stop, atr[i], cfg,
                                  tf_min, bias="RANDOM", setup="matched",
                                  trigger="coin flip", arm=arm)
            if tr:
                trades.append(tr)
            else:
                _rej(why)
        return trades, rejected

    if arm == "random":
        idxs = sorted(rng.integers(lo_i, hi_i, cfg["n_random"]).tolist())
        for i in idxs:
            if i <= busy_until or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            if not _in_session(ts_all.iat[i]):
                continue
            side = "bull" if rng.random() < 0.5 else "bear"
            level = float(df5["close"].iat[i])
            dist = cfg["rand_sl_atr"] * atr[i]
            stop = level - dist if side == "bull" else level + dist
            tr, why = _open_trade(symbol, df5, i, side, level, stop, atr[i], cfg,
                                  tf_min, bias="RANDOM", setup="none",
                                  trigger="coin flip", arm=arm)
            if tr:
                trades.append(tr)
                busy_until = tr["exit_i"]
            else:
                _rej(why)
        return trades, rejected

    for i in range(lo_i, hi_i):
        if i <= busy_until or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        ts = ts_all.iat[i]
        if not _in_session(ts):
            continue

        if arm == "smc_mtf":
            action, s, side, level, why = mtf.decide(
                ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts)
            if action == "NO_TRADE":
                continue
            bias_s, setup_s, trig_s = ctx["bias"][i], \
                ("OB+FVG" if s.has_fvg else "OB"), ctx["trigger"][i]
        else:  # smc: 15M setup only, no 1H bias gate and no 5M trigger gate
            live = mtf.active_setups_at(ctx["setups"], ts)
            if not live:
                continue
            s = live[0]
            side = s.side
            level = s.ote_high if side == "bull" else s.ote_low
            bias_s, setup_s, trig_s = "ignored", \
                ("OB+FVG" if s.has_fvg else "OB"), "ignored"

        tr, why = _open_trade(symbol, df5, i, side, level, s.stop_level, atr[i],
                              cfg, tf_min, bias=bias_s, setup=setup_s,
                              trigger=trig_s, arm=arm)
        if tr:
            trades.append(tr)
            busy_until = tr["exit_i"]
        else:
            _rej(why)

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
        "avg_bars_to_fill": round(float(np.mean([t["bars_to_fill"] for t in trades])), 1),
        "long": _side(longs), "short": _side(shorts),
    }


# ---------------------------------------------------------------------------
# ORCHESTRATION
# ---------------------------------------------------------------------------
DEFAULT_CFG = {"max_hold": 60, "rand_sl_atr": 1.0, "n_random": 400,
               "max_wait": 12,      # bars a resting limit stays live before cancel
               "matched_boot": 20,  # coin-flip replays of the matched null
               "log_trades": 150,   # trades returned in the audit log
               "is_frac": 0.60, "wf_folds": 4, "seed": 42}


def full_report(symbol, df5, df15, df1h, cfg=None, params=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    params = params or mtf.PARAMS
    rng = np.random.default_rng(cfg["seed"])

    n = len(df5)
    warm = 100
    split = int(n * cfg["is_frac"])

    # thresholds derived from the in-sample slice ONLY, then frozen and applied
    # to both halves. Calibrating on everything was leaking out-of-sample bars
    # into the very filter that decides whether an out-of-sample bar qualifies.
    ctx = mtf.build_context(df5, df15, df1h, params, calib_end=cfg["is_frac"])

    out = {"symbol": symbol, "bars_5m": n,
           "in_sample_bars": split - warm, "out_of_sample_bars": n - split,
           "costs": R.cost_summary(), "params": params}

    log = []
    for name, lo, hi in [("in_sample", warm, split), ("out_of_sample", split, n - 2)]:
        arms, by_arm = [], {}
        for arm in ("random", "smc", "smc_mtf"):
            tr, rej = run_arm(symbol, df5, ctx, arm, cfg, lo, hi,
                              rng=np.random.default_rng(cfg["seed"]))
            by_arm[arm] = tr
            m = metrics(tr, arm.upper())
            m["rejected"] = rej
            arms.append(m)

        # Fair null: same signal bars, same stop distances, coin-flipped side,
        # bootstrapped so one lucky draw cannot decide the verdict.
        for base in ("smc_mtf", "smc"):
            src = by_arm.get(base) or []
            if not src:
                continue
            boots = []
            for k in range(cfg["matched_boot"]):
                mt, _ = run_arm(symbol, df5, ctx, "matched_random", cfg, lo, hi,
                                rng=np.random.default_rng(cfg["seed"] + 1000 + k),
                                matched=src)
                mm = metrics(mt, "x")
                if mm.get("trades"):
                    boots.append(mm)
            if not boots:
                continue
            arms.append({
                "arm": f"MATCHED_RANDOM_vs_{base.upper()}",
                "trades": int(np.mean([x["trades"] for x in boots])),
                "win_rate_pct": round(float(np.mean([x["win_rate_pct"] for x in boots])), 1),
                "expectancy_inr": round(float(np.mean([x["expectancy_inr"] for x in boots])), 1),
                "net_pnl_inr": round(float(np.mean([x["net_pnl_inr"] for x in boots])), 0),
                "max_drawdown_inr": round(float(np.mean([x["max_drawdown_inr"] for x in boots])), 0),
                "profit_factor": round(float(np.mean([x["profit_factor"] or 0 for x in boots])), 2),
                "median_cost_in_r": round(float(np.mean([x["median_cost_in_r"] for x in boots])), 3),
                "boots": len(boots),
            })

        if name == "out_of_sample":
            for arm in ("smc_mtf", "smc", "random"):
                log.extend(by_arm.get(arm) or [])
        out[name] = arms

    log.sort(key=lambda t: t["signal_ts"])
    out["trade_log"] = log[:cfg["log_trades"]]
    out["trade_log_total"] = len(log)

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
                ctx = mtf.build_context(df5, df15, df1h, p, calib_end=cfg["is_frac"])
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
    # matched null first: same bars, same stops, coin-flipped side. The
    # unmatched RANDOM arm trades at unrelated moments and is a weaker control.
    rnd = oos.get("MATCHED_RANDOM_vs_SMC_MTF") or oos.get("RANDOM", {})
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
