"""
features.py — signal-time state capture. DIAGNOSTIC ONLY.

Answers one question the excursion analysis cannot: WHICH signal conditions
are associated with trades that never move.

STRICT RULES
------------
1. Nothing here can change which trades are taken. Every value is computed
   AFTER the existing decision and only ever written to the trade log.
2. Every feature describes the SIGNAL bar, never the fill bar or the exit.
3. Every indicator is causal. Series are built once per run from bars up to
   and including the signal bar, then indexed — no windowing that can see
   forward, and no recomputation per trade.
4. Nothing is fabricated. A feature the repository cannot support causally
   returns None, not a guess.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
It does not tune anything. The volume-spike threshold and the trend-regime
bands are fixed constants chosen before looking at any outcome. Choosing them
by what best separates TIMEOUT from SUCCESS would be fitting the diagnosis to
the data it is meant to diagnose.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed by definition, never tuned against outcomes.
VOLUME_LOOKBACK = 20
VOLUME_SPIKE_RATIO = 1.5
RSI_PERIOD = 14
REGIME_LOOKBACK = 50
REGIME_TREND_R2 = 0.30        # trailing regression fit above this = trending
REGIME_VOL_PCTL = 0.80        # ATR above this trailing percentile = volatile


def _rsi(close, period=RSI_PERIOD):
    """Wilder RSI. ewm is causal: each value uses only prior and current bars."""
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    au = up.ewm(alpha=1 / period, adjust=False).mean()
    ad = dn.ewm(alpha=1 / period, adjust=False).mean()
    rs = au / ad.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _trend_regime(close, lookback=REGIME_LOOKBACK):
    """TREND_UP / TREND_DOWN / RANGE, from a TRAILING linear fit.

    Deliberately crude. A rolling ordinary least squares slope over the last
    `lookback` closes, scored by how much of the variance it explains. High
    fit and positive slope is a trend; low fit is a range. The window ends at
    the current bar, so no future close contributes.
    """
    n = len(close)
    x = np.arange(lookback, dtype=float)
    x = x - x.mean()
    denom = float((x ** 2).sum())
    y = close.to_numpy(dtype=float)

    slope = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    for i in range(lookback - 1, n):
        w = y[i - lookback + 1: i + 1]
        wm = w.mean()
        b = float((x * (w - wm)).sum()) / denom
        pred = wm + b * x
        ss_res = float(((w - pred) ** 2).sum())
        ss_tot = float(((w - wm) ** 2).sum())
        slope[i] = b
        r2[i] = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, r2


def build_indicator_cache(df5):
    """Every causal series a snapshot needs, computed ONCE per run.

    Rebuilding RSI or the regression per trade would be the same numbers at
    many times the cost on a 0.1 CPU instance, which is why this is separated
    from the snapshot itself.
    """
    close = df5["close"]
    vol = df5.get("volume")

    if vol is not None and vol.notna().any() and (vol > 0).any():
        # shift(1): the median is over PREVIOUS bars, so the current bar is
        # compared against history rather than against itself
        med = vol.shift(1).rolling(VOLUME_LOOKBACK, min_periods=5).median()
        vol_ratio = (vol / med.replace(0.0, np.nan)).to_numpy(dtype=float)
    else:
        vol_ratio = np.full(len(df5), np.nan)

    atr = _atr(df5).to_numpy(dtype=float)
    atr_pctl = pd.Series(atr).rolling(200, min_periods=50).rank(pct=True) \
        .to_numpy(dtype=float)
    slope, r2 = _trend_regime(close)

    return {
        "ts": pd.to_datetime(df5["ts"]).to_numpy(),
        "rsi": _rsi(close).to_numpy(dtype=float),
        "vol_ratio": vol_ratio,
        "volume_available": bool(vol is not None and (vol > 0).any()),
        "slope": slope, "r2": r2,
        "atr_pctl": atr_pctl,
    }


def _num(x):
    """JSON-safe float, or None. NaN is not valid JSON."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 4) if np.isfinite(v) else None


def _regime(cache, i):
    r2, slope, pctl = cache["r2"][i], cache["slope"][i], cache["atr_pctl"][i]
    if not np.isfinite(r2) or not np.isfinite(slope):
        return None
    if np.isfinite(pctl) and pctl >= REGIME_VOL_PCTL:
        return "VOLATILE"
    if r2 < REGIME_TREND_R2:
        return "RANGE"
    return "TREND_UP" if slope > 0 else "TREND_DOWN"


def diagnostic_score(flags):
    """A confluence count computed AFTER the decision, purely for grouping.

    REPLACES A BROKEN FIELD. The existing trade log carries

        "score": int(sum(v for k, v in (flags or {}).items() if v is True) * 0)

    which multiplies by zero and is therefore always 0. Every score bucket in
    entry_quality.score_buckets() has been reading that constant, which is why
    scoring never looked predictive — it was never computed.

    This is NOT scoring.py. scoring.py is not on the signal path and wiring it
    in would change which trades are taken. This counts conditions that were
    already true at the signal bar and nothing more.
    """
    weights = {
        "liquidity_sweep": 2, "imbalance": 2, "fvg_present": 1,
        "htf_aligned": 2, "trigger_aligned": 2, "volume_spike": 1,
    }
    breakdown, total = {}, 0
    for k, w in weights.items():
        hit = bool(flags.get(k))
        breakdown[k] = {"hit": hit, "points": w if hit else 0, "max": w}
        total += w if hit else 0
    return total, breakdown


def build_feature_snapshot(cache, i, setup, side, bias, trigger, arm):
    """State at the SIGNAL bar. Never the fill bar, never the exit."""
    if i < 0 or i >= len(cache["rsi"]):
        return None

    ts = pd.Timestamp(cache["ts"][i])
    vr = cache["vol_ratio"][i]
    vol_ok = cache["volume_available"] and np.isfinite(vr)
    spike = bool(vr >= VOLUME_SPIKE_RATIO) if vol_ok else None

    want = "bull" if bias == "BULLISH" else "bear" if bias == "BEARISH" else None
    htf_aligned = bool(want is not None and side == want)

    setup_age = None
    if setup is not None and getattr(setup, "confirmed_ts", None) is not None:
        try:
            setup_age = int((ts - pd.Timestamp(setup.confirmed_ts))
                            .total_seconds() // 300)
        except (TypeError, ValueError):
            setup_age = None

    flags = {
        "liquidity_sweep": bool(getattr(setup, "swept", False)),
        "imbalance": bool(getattr(setup, "imbalance", False)),
        "fvg_present": bool(getattr(setup, "has_fvg", False)),
        "htf_aligned": htf_aligned,
        "trigger_aligned": bool(trigger in ("bull", "bear") and trigger == side),
        "volume_spike": bool(spike),
    }
    score, breakdown = diagnostic_score(flags)

    return {
        "diagnostic_score": score,
        "diagnostic_score_breakdown": breakdown,

        # For SMC the 1H gate is bypassed by design. This is what the 1H frame
        # SAID at that instant, not a condition the entry required.
        "observed_htf_bias": bias if bias in ("BULLISH", "BEARISH", "NEUTRAL")
        else None,
        "htf_was_a_requirement": arm == "smc_mtf",
        "htf_aligned": htf_aligned,

        "fvg_present": flags["fvg_present"],
        "liquidity_sweep": flags["liquidity_sweep"],
        "imbalance": flags["imbalance"],

        # poi_factors confirms structure breaks via find_bos() and does not
        # distinguish a continuation break from a character change. Reporting
        # CHOCH would be inventing a classification the repository does not
        # make, so this is always BOS and the limitation is stated.
        "structure_type": "BOS" if setup is not None else None,
        "structure_note": "poi_factors.find_bos does not classify CHoCH "
                          "separately; BOS is the only structure label the "
                          "repository can support causally",

        "volume_ratio": _num(vr) if vol_ok else None,
        "volume_spike": spike,
        "rsi_5m": _num(cache["rsi"][i]),
        "trend_regime": _regime(cache, i),

        "direction": "LONG" if side == "bull" else "SHORT",
        "signal_hour_utc": int(ts.hour),
        "signal_ts": str(ts),

        "trigger_5m": trigger if trigger in ("bull", "bear") else "none",
        "setup_age_bars": setup_age,
        "entry_mode": getattr(setup, "entry_mode", None),
    }


# ---------------------------------------------------------------------------
# GROUP COMPARISON
# ---------------------------------------------------------------------------
NUMERIC = ["diagnostic_score", "volume_ratio", "rsi_5m", "setup_age_bars"]
BOOLEAN = ["fvg_present", "volume_spike", "liquidity_sweep", "imbalance",
           "htf_aligned"]
CATEGORICAL = ["observed_htf_bias", "structure_type", "trend_regime",
               "direction", "trigger_5m", "signal_hour_utc"]

# PARTIAL is kept out of SUCCESS on purpose: a trade that banked TP1 and then
# drifted is not the same event as one that ran its targets, and merging them
# would flatter the success group.
SUCCESS_OUTCOMES = {"TP_ALL", "TRAILED_STOP"}


def _sample_flag(n):
    if n < 5:
        return "VERY_SMALL_SAMPLE"
    if n < 10:
        return "SMALL_SAMPLE"
    return "EXPLORATORY"


def _agg(rows):
    snaps = [t.get("feature_snapshot") for t in rows
             if isinstance(t.get("feature_snapshot"), dict)]
    out = {"trades": len(rows), "with_snapshot": len(snaps),
           "numeric": {}, "boolean": {}, "categorical": {}}

    for f in NUMERIC:
        vals = [s[f] for s in snaps if s.get(f) is not None]
        out["numeric"][f] = {"count_valid": len(vals)} if not vals else {
            "count_valid": len(vals),
            "median": round(float(np.median(vals)), 3),
            "mean": round(float(np.mean(vals)), 3),
            "min": round(float(np.min(vals)), 3),
            "max": round(float(np.max(vals)), 3),
        }

    for f in BOOLEAN:
        vals = [s[f] for s in snaps if s.get(f) is not None]
        t = sum(1 for v in vals if v)
        out["boolean"][f] = {
            "available_count": len(vals), "true_count": t,
            "false_count": len(vals) - t,
            "true_pct": round(t / len(vals) * 100, 1) if vals else None,
        }

    for f in CATEGORICAL:
        vals = [s[f] for s in snaps if s.get(f) is not None]
        counts = {}
        for v in vals:
            counts[str(v)] = counts.get(str(v), 0) + 1
        out["categorical"][f] = {
            "available_count": len(vals),
            "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
            "pct": {k: round(v / len(vals) * 100, 1)
                    for k, v in counts.items()} if vals else {},
        }
    return out


def _compare(a, b, label_a, label_b):
    out = {"numeric": {}, "boolean": {}, "categorical": {}}
    for f in NUMERIC:
        x, y = a["numeric"].get(f, {}), b["numeric"].get(f, {})
        if "median" in x and "median" in y:
            out["numeric"][f] = {
                f"{label_a}_median": x["median"],
                f"{label_b}_median": y["median"],
                "difference": round(x["median"] - y["median"], 3)}
    for f in BOOLEAN:
        x, y = a["boolean"].get(f, {}), b["boolean"].get(f, {})
        if x.get("true_pct") is not None and y.get("true_pct") is not None:
            out["boolean"][f] = {
                f"{label_a}_pct": x["true_pct"], f"{label_b}_pct": y["true_pct"],
                "difference_pct_points": round(x["true_pct"] - y["true_pct"], 1)}
    for f in CATEGORICAL:
        out["categorical"][f] = {
            label_a: a["categorical"].get(f, {}).get("pct", {}),
            label_b: b["categorical"].get(f, {}).get("pct", {})}
    return out


def _findings(groups, comparisons):
    """Only report a gap that is large AND backed by more than a handful of
    trades. Confidence is always LOW here by construction — these samples
    cannot support anything else, and saying otherwise would be dressing up a
    coin flip as a result."""
    to_n = groups.get("TIMEOUT", {}).get("trades", 0)
    su_n = groups.get("SUCCESS", {}).get("trades", 0)
    out = []
    if to_n < 5 or su_n < 5:
        return out, ["Fewer than 5 trades in a comparison group. Too few "
                     "trades to attribute failure to a specific condition."]

    cmp_ = comparisons.get("TIMEOUT_vs_SUCCESS", {})
    for f, d in (cmp_.get("boolean") or {}).items():
        gap = d.get("difference_pct_points")
        if gap is not None and abs(gap) >= 25:
            out.append({
                "feature": f,
                "observation": f"{d['TIMEOUT_pct']}% of timeout trades had "
                               f"{f} versus {d['SUCCESS_pct']}% of successful "
                               f"trades ({gap:+.1f} points)",
                "sample_size": {"timeout": to_n, "success": su_n},
                "confidence": "LOW"})
    for f, d in (cmp_.get("categorical") or {}).items():
        if f == "signal_hour_utc":
            continue
        t, s = d.get("TIMEOUT", {}), d.get("SUCCESS", {})
        for k in set(t) | set(s):
            gap = t.get(k, 0.0) - s.get(k, 0.0)
            if abs(gap) >= 30:
                out.append({
                    "feature": f,
                    "observation": f"{t.get(k, 0)}% of timeout trades were "
                                   f"{f}={k} versus {s.get(k, 0)}% of "
                                   f"successful trades ({gap:+.1f} points)",
                    "sample_size": {"timeout": to_n, "success": su_n},
                    "confidence": "LOW"})
    return out, []


def timeout_feature_analysis(trade_log, arms=("smc", "smc_mtf")):
    """TIMEOUT vs SUCCESS vs STOP vs PARTIAL, per arm.

    RANDOM is excluded: it is a control, and its signal conditions describe a
    coin flip rather than the strategy.
    """
    out = {}
    for arm in arms:
        rows = [t for t in trade_log if t.get("arm") == arm]
        if not rows:
            continue
        groups = {
            "TIMEOUT": [t for t in rows if t["outcome"] == "TIMEOUT"],
            "SUCCESS": [t for t in rows if t["outcome"] in SUCCESS_OUTCOMES],
            "STOP": [t for t in rows if t["outcome"] == "STOP"],
            "PARTIAL": [t for t in rows if t["outcome"] == "PARTIAL"],
        }
        agg = {k: _agg(v) for k, v in groups.items()}
        comparisons = {
            "TIMEOUT_vs_SUCCESS": _compare(agg["TIMEOUT"], agg["SUCCESS"],
                                           "TIMEOUT", "SUCCESS"),
            "TIMEOUT_vs_STOP": _compare(agg["TIMEOUT"], agg["STOP"],
                                        "TIMEOUT", "STOP"),
        }
        findings, warns = _findings({k: {"trades": len(v)}
                                     for k, v in groups.items()}, comparisons)
        sizes = {k: len(v) for k, v in groups.items()}
        flags = {k: _sample_flag(n) for k, n in sizes.items()}

        warnings = list(warns)
        warnings.append("Small sample size. Do not modify the strategy based "
                        "on this result alone.")
        warnings.append("PARTIAL trades are reported separately and are NOT "
                        "counted as successes.")

        out[arm] = {
            "sample_warning": (f"{sizes['TIMEOUT']} timeout trades, "
                               f"{sizes['SUCCESS']} successes; "
                               f"{flags['TIMEOUT']}"),
            "group_sizes": sizes,
            "sample_flags": flags,
            "groups": agg,
            "comparisons": comparisons,
            "diagnosis": {
                "status": "EXPLORATORY",
                "findings": findings,
                "warnings": warnings,
            },
        }
    return out
