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
def _find_fill(df, side, level, start, cfg):
    """Where and at what price the order actually executes.

    Returns (fill_index, fill_price) or (None, None).

    ENTRY MODELS
      next_open  (default) market order at the OPEN of signal_bar + 1. Always
                 fills, at a price nobody could have known when the signal
                 printed. This is the honest default.
      limit_ote  a resting limit at `level`, which must be TOUCHED by a bar
                 STRICTLY AFTER the signal bar. The signal bar is never
                 eligible: its range was already complete when the decision
                 was taken, so filling on it is look-ahead. Unfilled orders
                 expire after max_wait bars and are counted, not discarded.

    Either way the entry index is >= signal_i + 1, so no stop or target is ever
    evaluated on a bar the decision already saw.
    """
    if start >= len(df) - 1:
        return None, None

    if cfg.get("entry_model", "next_open") == "next_open":
        return start, float(df["open"].iat[start])

    lows = df["low"].to_numpy()
    highs = df["high"].to_numpy()
    last = min(start + cfg["max_wait"], len(df) - 2)
    for j in range(start, last + 1):
        if side == "bull" and lows[j] <= level:
            return j, level
        if side == "bear" and highs[j] >= level:
            return j, level
    return None, None


def _open_trade(symbol, df, sig_i, side, level, stop_level, atr, cfg, tf_min,
                bias=None, setup=None, trigger=None, arm="",
                setup_ts=None, entry_reason=""):
    """Place a resting limit at the close of sig_i, fill from sig_i+1 onward.

    Returns (trade_dict, reject_reason). trade_dict carries the full audit
    trail: what each timeframe said, when the order was placed, when it filled,
    when and why it closed.
    """
    direction = "BUY" if side == "bull" else "SELL"
    # stop_level already sits beyond the OB wick with its own padding, so no
    # second buffer here: doubling it silently widened every stop
    sl = stop_level
    if (side == "bull" and level <= sl) or (side == "bear" and level >= sl):
        return None, "entry on the wrong side of the stop"

    fill_i, entry = _find_fill(df, side, level, sig_i + 1, cfg)
    if fill_i is None:
        return None, "order never filled"
    if (side == "bull" and entry <= sl) or (side == "bear" and entry >= sl):
        return None, "filled beyond the stop"

    lim = entry + 6 * atr if side == "bull" else entry - 6 * atr
    s = R.size_position(symbol, direction, entry, sl, atr=atr, structure_limit=lim)
    if not s.ok:
        return None, s.reason

    legs, hit, outcome, ex = simulate(df, side, entry, sl, s.tps, fill_i, cfg["max_hold"])
    held = ex - fill_i
    gross, net, fees, slip, fund = pnl_inr(side, entry, legs, s.qty, R.USDT_INR,
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
        "signal_level": round(level, 8),
        "actual_entry": round(entry, 8),
        "entry_model": cfg.get("entry_model", "next_open"),
        "entry_slippage_px": round(entry - level, 8),
        "entry": round(entry, 8), "sl": round(sl, 8),
        "setup_confirmed_ts": (str(setup_ts[0]) if setup_ts else None),
        "setup_expires_ts": (str(setup_ts[1]) if setup_ts else None),
        "entry_reason": entry_reason,
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
    # FIX 12: where trades disappear, counted rather than guessed at
    gates = {"total_5m_bars": 0, "bars_with_atr": 0, "bars_not_busy": 0,
             "valid_1h_bias": 0, "matching_15m_setup": 0,
             "matching_5m_trigger": 0, "all_three_aligned": 0,
             "ote_touched": 0, "signals_generated": 0, "entries_filled": 0,
             "rejected_by_sizing": 0, "expired_setup": 0,
             "duplicate_signal_rejected": 0, "order_never_filled": 0}

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
        gates["total_5m_bars"] += 1
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        gates["bars_with_atr"] += 1

        ts = ts_all.iat[i]
        bias_here = ctx["bias"][i]
        has_bias = bias_here in ("BULLISH", "BEARISH")
        if has_bias:
            gates["valid_1h_bias"] += 1
        want = "bull" if bias_here == "BULLISH" else \
               "bear" if bias_here == "BEARISH" else None
        live_now = mtf.active_setups_at(ctx["setups"], ts, want)
        if live_now:
            gates["matching_15m_setup"] += 1
        elif has_bias and mtf.active_setups_at(ctx["setups"], ts):
            gates["expired_setup"] += 1
        has_trig = ctx["trigger"][i] == want and want is not None
        if ctx["trigger"][i] in ("bull", "bear"):
            gates["matching_5m_trigger"] += 1
        if has_bias and live_now and has_trig:
            gates["all_three_aligned"] += 1
            lv = live_now[0].ote_high if want == "bull" else live_now[0].ote_low
            touched = (df5["low"].iat[i] <= lv) if want == "bull" \
                else (df5["high"].iat[i] >= lv)
            if touched:
                gates["ote_touched"] += 1

        if i <= busy_until:
            if has_bias and live_now and has_trig:
                gates["duplicate_signal_rejected"] += 1
            continue
        gates["bars_not_busy"] += 1
        if not _in_session(ts):
            continue

        if arm == "smc_mtf":
            action, s, side, level, why = mtf.decide(
                ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts)
            if action == "NO_TRADE":
                continue
            gates["signals_generated"] += 1
            bias_s, setup_s, trig_s = ctx["bias"][i], \
                ("OB+FVG" if s.has_fvg else "OB"), ctx["trigger"][i]
            reason_s = f"1H {bias_s} + 15M {setup_s} after sweep + 5M {trig_s}"
        else:  # smc: 15M setup only, no 1H bias gate and no 5M trigger gate
            live = mtf.active_setups_at(ctx["setups"], ts)
            if not live:
                continue
            s = live[0]
            side = s.side
            level = s.entry_level
            gates["signals_generated"] += 1
            bias_s, setup_s, trig_s = "ignored", \
                ("OB+FVG" if s.has_fvg else "OB"), "ignored"
            reason_s = f"15M {setup_s} only, 1H and 5M gates bypassed"

        tr, why = _open_trade(symbol, df5, i, side, level, s.stop_level, atr[i],
                              cfg, tf_min, bias=bias_s, setup=setup_s,
                              trigger=trig_s, arm=arm,
                              setup_ts=(s.confirmed_ts, s.expires_ts),
                              entry_reason=reason_s)
        if tr:
            gates["entries_filled"] += 1
            trades.append(tr)
            busy_until = tr["exit_i"]   # FIX 10: keyed to the real exit index
        else:
            _rej(why)
            if why and "fill" in why:
                gates["order_never_filled"] += 1
            elif why:
                gates["rejected_by_sizing"] += 1

    rejected["_gates"] = gates
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
RANDOM_SEEDS = [11, 22, 33, 44, 55, 66, 77, 88, 99, 111,
                122, 133, 144, 155, 166, 177, 188, 199, 211, 222]

DEFAULT_CFG = {"max_hold": 60, "rand_sl_atr": 1.0, "n_random": 400,
               "wf_seeds": 10,
               "entry_model": "next_open",   # or "limit_ote"
               "max_wait": 12,      # bars a resting limit stays live before cancel
               "min_trades": 30,    # below this the verdict is INSUFFICIENT SAMPLE
               "log_trades": 150,   # trades returned in the audit log
               "is_frac": 0.60, "wf_folds": 4, "seed": 42}


def full_report(symbol, df5, df15, df1h, cfg=None, params=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    params = params or mtf.PARAMS
    rng = np.random.default_rng(cfg["seed"])

    n = len(df5)
    warm = 100
    split = int(n * cfg["is_frac"])

    # Calibration is a trailing rolling quantile computed per bar, so there is
    # no split to get wrong and live computes the identical number.
    ctx = mtf.build_context(df5, df15, df1h, params)

    ts = mtf._ts(df5["ts"])
    out = {"symbol": symbol, "bars_5m": n,
           "split": {
               "is_start": str(ts.iat[warm]), "is_end": str(ts.iat[split - 1]),
               "oos_start": str(ts.iat[split]), "oos_end": str(ts.iat[n - 1]),
               "is_bars": split - warm, "oos_bars": n - split,
               "is_frac": cfg["is_frac"], "warmup_bars": warm,
               "note": "strict chronological split, never shuffled",
           },
           "in_sample_bars": split - warm, "out_of_sample_bars": n - split,
           "costs": R.cost_summary(), "params": params}

    log, gate_report = [], {}
    for name, lo, hi in [("in_sample", warm, split), ("out_of_sample", split, n - 1)]:
        arms, by_arm = [], {}
        for arm in ("random", "smc", "smc_mtf"):
            tr, rej = run_arm(symbol, df5, ctx, arm, cfg, lo, hi,
                              rng=np.random.default_rng(cfg["seed"]))
            by_arm[arm] = tr
            g = rej.pop("_gates", None)
            if g and arm == "smc_mtf":
                gate_report[name] = g
            m = metrics(tr, arm.upper())
            m["rejected"] = rej
            m["rejected_by_sizing"] = sum(
                v for k, v in rej.items()
                if k != "_gates" and ("size" in k or "notional" in k
                                      or "risk" in k or "minimum" in k))
            arms.append(m)

        for base in ("smc_mtf", "smc"):
            mb = matched_baseline(symbol, df5, ctx, cfg, by_arm.get(base) or [])
            if mb:
                mb["arm"] = f"MATCHED_RANDOM_vs_{base.upper()}"
                arms.append(mb)

        if name == "out_of_sample":
            for arm in ("smc_mtf", "smc", "random"):
                log.extend(by_arm.get(arm) or [])
        out[name] = arms

    log.sort(key=lambda t: t["signal_ts"])
    out["gate_counters"] = gate_report
    out["trade_log"] = log
    out["trade_log_total"] = len(log)

    out["walk_forward"] = _walk_forward(symbol, df5, ctx, cfg, warm, n)
    # FIX C: fragility is judged on unseen bars only. Running it from `warm`
    # mixed in-sample results into the robustness check, which flatters it.
    out["sensitivity"] = _sensitivity(symbol, df5, df15, df1h, cfg, params, split, n)
    out["min_trades"] = cfg["min_trades"]
    out["verdict"] = _verdict(out)
    return out


def matched_baseline(symbol, df5, ctx, cfg, src_trades, seeds=None):
    """FIX 3. The fair null: same signal bars, same stop distances, same
    sizing, costs, session filter, max_hold and no-overlap rule as the arm it
    is matched to. Only the SIDE is randomised.

    Run across many seeds so a single lucky or unlucky path cannot decide the
    verdict. Returns the full distribution, not one number.

    The old baseline drew 400 entries at unrelated moments while SMC_MTF had
    three. That is not a control, it is a different experiment.
    """
    seeds = seeds or RANDOM_SEEDS[:cfg.get("matched_seeds", 20)]
    if not src_trades:
        return None

    exps, nets, wins, counts = [], [], [], []
    for sd in seeds:
        mt, _ = run_arm(symbol, df5, ctx, "matched_random", cfg, 0, 0,
                        rng=np.random.default_rng(sd), matched=src_trades)
        m = metrics(mt, "matched")
        if not m.get("trades"):
            continue
        exps.append(m["expectancy_inr"])
        nets.append(m["net_pnl_inr"])
        wins.append(m["win_rate_pct"])
        counts.append(m["trades"])

    if not exps:
        return None
    exps = np.array(exps, dtype=float)
    return {
        "arm": "MATCHED_RANDOM",
        "seeds_used": len(exps),
        "trades": int(np.mean(counts)),
        "source_trades": len(src_trades),
        "win_rate_pct": round(float(np.mean(wins)), 1),
        "random_mean_expectancy": round(float(exps.mean()), 1),
        "random_median_expectancy": round(float(np.median(exps)), 1),
        "random_std_expectancy": round(float(exps.std(ddof=1)) if exps.size > 1 else 0.0, 1),
        "random_p95_expectancy": round(float(np.percentile(exps, 95)), 1),
        "random_mean_net_pnl": round(float(np.mean(nets)), 0),
        "expectancy_inr": round(float(exps.mean()), 1),
        "net_pnl_inr": round(float(np.mean(nets)), 0),
    }


def _walk_forward(symbol, df5, ctx, cfg, warm, n):
    """Anchored walk-forward. Each fold TESTS a later slice while everything
    before it is history the strategy has already lived through.

    Parameters are identical in every fold. Nothing is refitted; calibration is
    a trailing rolling window, so a later fold simply has more past behind it.
    """
    folds = cfg["wf_folds"]
    ts = mtf._ts(df5["ts"])
    edges = np.linspace(warm, n - 1, folds + 1).astype(int)
    res, beat = [], 0

    for k in range(folds):
        lo, hi = int(edges[k]), int(edges[k + 1])
        tr, _ = run_arm(symbol, df5, ctx, "smc_mtf", cfg, lo, hi,
                        rng=np.random.default_rng(cfg["seed"] + k))
        m = metrics(tr, "smc_mtf")
        sm, _ = run_arm(symbol, df5, ctx, "smc", cfg, lo, hi,
                        rng=np.random.default_rng(cfg["seed"] + k))
        msm = metrics(sm, "smc")
        base = matched_baseline(symbol, df5, ctx, cfg, tr,
                                seeds=RANDOM_SEEDS[:cfg.get("wf_seeds", 10)])
        row = {
            "fold": k + 1,
            "period_start": str(ts.iat[lo]), "period_end": str(ts.iat[hi - 1]),
            "train_bars": lo - warm, "test_bars": hi - lo,
            "smc_mtf_trades": m.get("trades", 0),
            "smc_mtf_expectancy_inr": m.get("expectancy_inr"),
            "smc_trades": msm.get("trades", 0),
            "smc_expectancy_inr": msm.get("expectancy_inr"),
            "random_mean_expectancy": base and base["random_mean_expectancy"],
            "random_median_expectancy": base and base["random_median_expectancy"],
            "random_std_expectancy": base and base["random_std_expectancy"],
            "random_runs": base and base["seeds_used"],
        }
        if base and m.get("expectancy_inr") is not None:
            row["difference_inr"] = round(
                m["expectancy_inr"] - base["random_mean_expectancy"], 1)
            row["beat_random"] = bool(row["difference_inr"] > 0)
            beat += int(row["beat_random"])
        else:
            row["difference_inr"] = None
            row["beat_random"] = None
        res.append(row)

    scored = sum(1 for r in res if r["beat_random"] is not None)
    return {"folds": res, "folds_beating_random": beat,
            "folds_scored": scored, "total_folds": folds}


def _sensitivity(symbol, df5, df15, df1h, cfg, params, oos_start, n):
    """Nudge one parameter at a time, OUT OF SAMPLE ONLY.

    A result that survives only one exact setting is fragile whatever the
    headline number says. Measuring that on in-sample bars would be measuring
    how well the parameters fit the data they were chosen on.
    """
    grid = {"max_age": [40, 60, 90], "sweep_window": [10, 20, 30],
            "ote_high": [0.705, 0.79, 0.886]}
    rows = []
    for key, vals in grid.items():
        for v in vals:
            p = {**params, key: v}
            try:
                ctx = mtf.build_context(df5, df15, df1h, p)
                tr, _ = run_arm(symbol, df5, ctx, "smc_mtf", cfg, oos_start, n - 1)
                m = metrics(tr, "smc_mtf")
                rows.append({"param": key, "value": v, "slice": "out_of_sample",
                             "trades": m.get("trades", 0),
                             "win_rate_pct": m.get("win_rate_pct"),
                             "profit_factor": m.get("profit_factor"),
                             "expectancy_inr": m.get("expectancy_inr", 0),
                             "net_inr": m.get("net_pnl_inr", 0)})
            except Exception as e:
                rows.append({"param": key, "value": v, "slice": "out_of_sample", "error": str(e)})
    exps = [r.get("expectancy_inr", 0) for r in rows if "error" not in r]
    positive = sum(1 for e in exps if e > 0)
    return {"runs": rows, "positive_of_total": f"{positive}/{len(exps)}",
            "fragile": positive <= max(1, len(exps) // 4)}


def _verdict(out):
    """FIX 13. One of: NO_TRADES, INSUFFICIENT_SAMPLE, NO_EDGE, UNSTABLE,
    FRAGILE, EDGE. Never forced to profitable.

    Judged against the MATCHED baseline, not the unmatched RANDOM arm, and
    against its mean across many seeds rather than a single path.
    """
    cfg_min = out.get("min_trades", 30)
    oos = {m["arm"]: m for m in out["out_of_sample"]}
    smc = oos.get("SMC_MTF", {})
    base = oos.get("MATCHED_RANDOM_vs_SMC_MTF")
    wf = out["walk_forward"]
    sens = out["sensitivity"]

    n = smc.get("trades", 0)
    e = smc.get("expectancy_inr")

    def _v(code, statement, edge=None):
        return {"verdict": code, "profitable": code == "EDGE",
                "edge_vs_random_inr": edge, "statement": statement,
                "trades_out_of_sample": n, "min_trades_required": cfg_min}

    if not n:
        return _v("NO_TRADES",
                  "No trades survived out of sample. Nothing to measure. "
                  "Check the gate counters to see where they were filtered out.")
    if base is None:
        return _v("INSUFFICIENT_SAMPLE",
                  f"{n} trades but no matched baseline could be built.")

    edge = round(e - base["random_mean_expectancy"], 1)
    sd = base["random_std_expectancy"] or 0.0
    z = round(edge / sd, 2) if sd > 0 else None

    if n < cfg_min:
        return _v("INSUFFICIENT_SAMPLE",
                  f"Only {n} out-of-sample trades, {cfg_min} required. "
                  f"Expectancy Rs.{e:.0f} against a random mean of "
                  f"Rs.{base['random_mean_expectancy']:.0f}, but at this sample "
                  f"size that difference is not evidence of anything.", edge)
    if e <= 0:
        return _v("NO_EDGE",
                  f"Expectancy is Rs.{e:.0f} per trade after fees, slippage and "
                  f"funding. Losing money slowly is still losing money.", edge)
    if edge <= 0:
        return _v("NO_EDGE",
                  f"Positive P&L, but a coin flip on the same bars with the same "
                  f"stops averages Rs.{base['random_mean_expectancy']:.0f} against "
                  f"this strategy's Rs.{e:.0f}. Not an edge.", edge)
    if z is not None and z < 1.0:
        return _v("FRAGILE",
                  f"Beats the random mean by Rs.{edge:.0f}, but the random "
                  f"distribution has a standard deviation of Rs.{sd:.0f}. "
                  f"That is {z} sigma, well inside noise.", edge)
    if wf["folds_scored"] and wf["folds_beating_random"] < wf["folds_scored"] - 1:
        return _v("UNSTABLE",
                  f"Beats random overall but only in "
                  f"{wf['folds_beating_random']}/{wf['folds_scored']} scored "
                  f"walk-forward folds. The edge does not persist.", edge)
    if sens.get("fragile"):
        return _v("FRAGILE",
                  "Edge exists at the chosen parameters and collapses when they "
                  "are nudged. That is a fitted result, not a discovered one.", edge)
    return _v("EDGE",
              f"Rs.{edge:.0f} per trade over the matched random mean ({z} sigma), "
              f"stable across folds and parameter nudges, on {n} trades.", edge)
