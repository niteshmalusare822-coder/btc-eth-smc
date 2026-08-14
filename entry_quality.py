"""
entry_quality.py — diagnose WHY trades fail, before changing anything.

The findings that motivated this module:

    STOP     135 trades, median MFE 0.42R, median MAE 1.30R, 4.4% reached 1R
    TIMEOUT   13 trades, median MFE 0.45R, median MAE 0.08R, 0% reached 1R
    FUNNEL   40 aligned opportunities, 35 rejected because a position was open

Those three lines point at three different problems, and only one of them is
the strategy signal. This module measures each separately so the next change is
chosen from evidence rather than from whichever knob is easiest to turn.

Nothing here modifies the strategy. It reports.
"""

from __future__ import annotations

import numpy as np

import backtest as B
import mtf_engine as mtf

MFE_LEVELS = [0.25, 0.50, 0.75, 1.00]


# ---------------------------------------------------------------------------
# TASK 3 — is a timeout an exit failure or an entry failure?
# ---------------------------------------------------------------------------
def excursion_profile(trades, label=""):
    """How far did this group of trades actually get, at every threshold.

    A single median hides the shape. A group with median 0.45R could be every
    trade sitting at 0.45R, or half at 0.05R and half at 1.2R, and those two
    need opposite fixes.
    """
    if not trades:
        return {"label": label, "trades": 0}
    mfe = np.array([t.get("mfe_r", 0.0) for t in trades], dtype=float)
    mae = np.array([t.get("mae_r", 0.0) for t in trades], dtype=float)
    out = {
        "label": label, "trades": len(trades),
        "median_mfe_r": round(float(np.median(mfe)), 3),
        "median_mae_r": round(float(np.median(mae)), 3),
        "mean_mfe_r": round(float(mfe.mean()), 3),
        "p75_mfe_r": round(float(np.percentile(mfe, 75)), 3),
        "median_bars_to_mfe": int(np.median(
            [t.get("bars_to_mfe", 0) for t in trades])),
        "net_inr": round(sum(t["net_inr"] for t in trades), 0),
    }
    for lv in MFE_LEVELS:
        out[f"pct_reaching_{lv}R"] = round(float((mfe >= lv).mean() * 100), 1)
    return out


def classify_failure(trades):
    """ENTRY_FAILURE vs EXIT_FAILURE, decided by the numbers.

    The rule: if a group of trades rarely clears 0.5R, no exit rule could have
    saved it, so the entry is at fault. If it clears 1R often and still ends
    flat or negative, the entry found the move and the exit gave it back.
    """
    stops = [t for t in trades if t["outcome"] == "STOP"]
    timeouts = [t for t in trades if t["outcome"] == "TIMEOUT"]

    def _verdict(rows, name):
        if not rows:
            return {"group": name, "trades": 0, "verdict": "NO_DATA"}
        p = excursion_profile(rows, name)
        half, one = p["pct_reaching_0.5R"], p["pct_reaching_1.0R"]
        if one >= 40:
            v, why = "EXIT_FAILURE", (
                f"{one}% reached 1R and still ended here. The entry located "
                f"the move; the exit returned it.")
        elif half < 35:
            v, why = "ENTRY_FAILURE", (
                f"only {half}% ever cleared 0.5R. No exit rule rescues trades "
                f"that never move. The entry is the problem.")
        else:
            v, why = "MARGINAL", (
                f"{half}% cleared 0.5R but only {one}% reached 1R. Real but "
                f"shallow follow-through; a nearer first target is worth "
                f"testing before touching the entry.")
        return {**p, "verdict": v, "explanation": why}

    s = _verdict(stops, "STOP")
    t = _verdict(timeouts, "TIMEOUT")

    # a stop group whose MAE dwarfs its MFE went the wrong way immediately,
    # which is a direction problem, not a stop-width problem
    if s.get("trades") and s.get("median_mae_r", 0) > 2 * max(
            s.get("median_mfe_r", 0), 0.01):
        s["explanation"] += (
            f" MAE ({s['median_mae_r']}R) is more than double MFE "
            f"({s['median_mfe_r']}R): these went adverse straight away, so "
            f"widening the stop would only enlarge the same loss.")
    return {"STOP": s, "TIMEOUT": t}


# ---------------------------------------------------------------------------
# TASK 6 — does the score predict anything?
# ---------------------------------------------------------------------------
SCORE_BUCKETS = [(0, 5), (6, 7), (8, 9), (10, 11), (12, 18)]


def score_buckets(trades, key="score"):
    """Expectancy by score band.

    If the top band does not beat the bottom band, the scoring system is
    decoration and wiring it into the entry decision would add twelve
    parameters for nothing.
    """
    rows = []
    have = [t for t in trades if t.get(key) is not None]
    if not have:
        return {"buckets": [], "predictive": None,
                "note": "no scores recorded; wire scoring into the entry path first"}

    for lo, hi in SCORE_BUCKETS:
        grp = [t for t in have if lo <= t[key] <= hi]
        if not grp:
            rows.append({"bucket": f"{lo}-{hi}", "trades": 0})
            continue
        net = np.array([t["net_inr"] for t in grp], dtype=float)
        wins, losses = net[net > 0], net[net <= 0]
        gl = abs(losses.sum())
        rows.append({
            "bucket": f"{lo}-{hi}", "trades": len(grp),
            "win_rate_pct": round(float((net > 0).mean() * 100), 1),
            "expectancy_inr": round(float(net.mean()), 1),
            "profit_factor": round(float(wins.sum() / gl), 2) if gl else None,
            "median_mfe_r": round(float(np.median(
                [t.get("mfe_r", 0) for t in grp])), 2),
            "net_inr": round(float(net.sum()), 0),
        })

    scored = [r for r in rows if r.get("trades")]
    predictive = None
    if len(scored) >= 2:
        predictive = scored[-1]["expectancy_inr"] > scored[0]["expectancy_inr"]
    return {
        "buckets": rows,
        "predictive": predictive,
        "note": ("higher scores did outperform lower ones"
                 if predictive else
                 "higher scores did NOT outperform; the score is not "
                 "predictive on this sample and should not gate entries yet"),
    }


# ---------------------------------------------------------------------------
# TASK 5 — position management modes
# ---------------------------------------------------------------------------
def position_modes(symbol, df5, ctx, cfg, lo_i, hi_i, arm="smc_mtf"):
    """Rerun the SAME signals under four concurrency rules.

    MODE_A  one position at a time            (current behaviour)
    MODE_B  one position per direction
    MODE_C  up to two concurrent positions
    MODE_D  a pending setup may be replaced by a higher-scoring one

    35 of 40 aligned opportunities were being discarded by MODE_A. That is not
    a filter deciding the setups were bad; it is an accounting rule deciding
    the account was busy. Whether relaxing it helps is an empirical question,
    and relaxing it also multiplies risk, so all four are measured rather than
    assumed.
    """
    results = {}
    for mode, limit in (("MODE_A", 1), ("MODE_B", "per_side"),
                        ("MODE_C", 2), ("MODE_D", "replace")):
        c = {**cfg, "concurrency": limit}
        trades, rej = B.run_arm(symbol, df5, ctx, arm, c, lo_i, hi_i,
                                rng=np.random.default_rng(cfg.get("seed", 42)))
        m = B.metrics(trades, mode)
        conc = _max_concurrent(trades)
        results[mode] = {
            "mode": mode,
            "trades": m.get("trades", 0),
            "win_rate_pct": m.get("win_rate_pct"),
            "expectancy_inr": m.get("expectancy_inr"),
            "net_pnl_inr": m.get("net_pnl_inr"),
            "max_drawdown_inr": m.get("max_drawdown_inr"),
            "total_costs_inr": round(sum(
                t["fees_inr"] + t["slippage_inr"] + t["funding_inr"]
                for t in trades), 0),
            "max_concurrent_positions": conc,
            "peak_risk_inr": round(conc * cfg.get("max_risk_inr", 700), 0),
        }
    return {
        "modes": results,
        "warning": ("More concurrent positions means more simultaneous risk. "
                    "peak_risk_inr is the worst case if every open trade stops "
                    "together, which is exactly what happens in a fast move."),
    }


def _max_concurrent(trades):
    if not trades:
        return 0
    events = []
    for t in trades:
        events.append((t["fill_i"], 1))
        events.append((t["exit_i"], -1))
    events.sort()
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


# ---------------------------------------------------------------------------
# TASK 7 — does each gate actually add information?
# ---------------------------------------------------------------------------
def gate_information_value(symbol, df5, ctx, cfg, lo_i, hi_i):
    """Turn each gate off in turn and measure what it was removing.

    A gate earns its place only if the trades it rejects are worse than the
    trades it keeps. A gate that removes trades at the same expectancy is
    costing sample size for nothing — which matters enormously here, because
    sample size is the binding constraint on ever proving an edge.
    """
    base_trades, _ = B.run_arm(symbol, df5, ctx, "smc_mtf", cfg, lo_i, hi_i,
                               rng=np.random.default_rng(cfg.get("seed", 42)))
    base = B.metrics(base_trades, "with_all_gates")

    loose_trades, _ = B.run_arm(symbol, df5, ctx, "smc", cfg, lo_i, hi_i,
                                rng=np.random.default_rng(cfg.get("seed", 42)))
    loose = B.metrics(loose_trades, "15m_setup_only")

    kept_ids = {t["i"] for t in base_trades}
    rejected = [t for t in loose_trades if t["i"] not in kept_ids]
    rej = B.metrics(rejected, "rejected_by_htf_and_trigger")

    verdict = "UNKNOWN"
    if base.get("trades") and rej.get("trades"):
        if rej["expectancy_inr"] < base["expectancy_inr"]:
            verdict = ("the 1H bias and 5M trigger gates removed WORSE trades. "
                       "They are earning their place.")
        else:
            verdict = ("the gates removed trades that were no worse than the "
                       "ones kept. They are costing sample size without "
                       "improving quality.")
    return {
        "with_all_gates": base,
        "setup_only": loose,
        "trades_removed_by_gates": rej,
        "verdict": verdict,
    }


def full_diagnosis(symbol, df5, df15, df1h, cfg=None):
    """Everything above, on one symbol."""
    cfg = {**B.DEFAULT_CFG, **(cfg or {})}
    rep = B.full_report(symbol, df5, df15, df1h, cfg=cfg)
    log = rep.get("trade_log") or []
    smc = [t for t in log if t["arm"] == "smc"]

    n = len(df5)
    split = int(n * cfg["is_frac"])
    ctx = mtf.build_context(df5, df15, df1h)

    return {
        "symbol": symbol,
        "source": rep.get("source"),
        "coverage": rep.get("data_quality", {}).get("coverage_days"),
        "split": rep.get("split"),
        "failure_classification": classify_failure(smc),
        "excursion_by_exit": {
            k: excursion_profile([t for t in smc if t["outcome"] == k], k)
            for k in {t["outcome"] for t in smc}
        },
        "score_buckets": score_buckets(smc),
        "gate_information_value": gate_information_value(
            symbol, df5, ctx, cfg, split, n - 1),
        "position_modes": position_modes(symbol, df5, ctx, cfg, split, n - 1),
        "signal_funnel": rep.get("signal_funnel"),
        "verdict": rep.get("verdict"),
    }
