"""
scoring.py — location filter, confluence score, stop validation.

REPLACES THE HARD AND GATE
--------------------------
The old model demanded 1H bias AND 15M setup AND 5M trigger simultaneously.
On 36 days of real ETH data all three aligned 23 times and produced 5 trades.
The gate counters showed 2,565 bars with a valid 1H bias and 1,118 with a live
15M setup, so the components were firing; they simply never coincided.

Scoring keeps the components but stops requiring unanimity. Three conditions
remain HARD because without them there is no setup at all, only a guess:
a liquidity sweep, a 15M structure break, and a 5M confirmation. Everything
else contributes points.

WHAT THIS DOES NOT DO
---------------------
It does not loosen the strategy to manufacture trades. The hard requirements
are strictly a subset of the old AND gate, and the score threshold is a new
parameter that must be validated out of sample like any other. A scoring model
with twelve weights is a larger overfitting surface than a three-way AND, which
is exactly why the weights below are defaults to be TESTED, not tuned.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Confluence weights. Defaults from the source material, not from fitting ──
WEIGHTS = {
    "htf_4h_bias": 2,
    "htf_1h_bias": 2,
    "daily_location": 2,
    "liquidity_sweep": 2,
    "structure_15m": 2,
    "displacement_15m": 1,
    "ob_fvg_15m": 1,
    "confirmation_5m": 2,
    "retest_5m": 1,
    "volume": 1,
    "cvd": 1,
    "ote_location": 1,
}
MAX_SCORE = sum(WEIGHTS.values())          # 18

CFG = {
    "entry_score": 9,
    "min_stop_atr": 0.50,
    "max_stop_atr": 1.50,
    "sl_buffer_atr": 0.10,
    "cooldown_bars": 3,
    "require_sweep": True,
    "require_structure_15m": True,
    "require_confirmation_5m": True,
    "enforce_daily_location": True,
}


# ---------------------------------------------------------------------------
# DAILY 50% LOCATION  (spec section 3)
# ---------------------------------------------------------------------------
def previous_day_levels(df5):
    """Confirmed previous-day high, low and midpoint for every 5M bar.

    The current day's developing high and low are never used. The level in
    force on any bar comes from the day BEFORE it, which is fixed and knowable.
    Using today's range would be reading a high that has not printed yet — the
    single most common look-ahead in daily-bias systems.
    """
    ts = pd.to_datetime(df5["ts"])
    day = ts.dt.floor("D")
    g = pd.DataFrame({"day": day, "high": df5["high"].to_numpy(),
                      "low": df5["low"].to_numpy()})
    daily = g.groupby("day").agg(high=("high", "max"), low=("low", "min"))
    # shift(1): a bar in day D sees day D-1
    prev = daily.shift(1)
    prev["mid"] = (prev["high"] + prev["low"]) / 2.0
    out = prev.reindex(day).reset_index(drop=True)
    return out["high"].to_numpy(), out["low"].to_numpy(), out["mid"].to_numpy()


def daily_location_ok(side, price, prev_mid):
    """LONG only below the previous day's midpoint, SHORT only above it.

    A location filter, not a signal. Being in discount is not a reason to buy;
    it is a reason a buy is allowed to be considered.
    """
    if prev_mid is None or not np.isfinite(prev_mid):
        return False
    return price < prev_mid if side == "bull" else price > prev_mid


# ---------------------------------------------------------------------------
# STOP VALIDATION  (spec section 14)
# ---------------------------------------------------------------------------
def validate_stop(entry, sl, atr, cfg=None):
    """Stop must be between min_stop_atr and max_stop_atr away.

    This matters more than it looks. A stop tighter than 0.5 ATR is the reason
    the round trip was eating 12 to 119 percent of risk: the fee is fixed
    against notional while the stop shrinks, so cost-in-R explodes as the stop
    narrows. Rejecting those setups removes the trades that could never pay for
    themselves, rather than trying to out-trade the fee.

    A stop wider than 1.5 ATR is rejected too, because position size falls
    proportionally and the trade stops being the trade that was signalled.
    """
    cfg = {**CFG, **(cfg or {})}
    if not np.isfinite(atr) or atr <= 0:
        return False, "no ATR"
    dist = abs(entry - sl)
    if dist <= 0:
        return False, "zero stop distance"
    in_atr = dist / atr
    if in_atr < cfg["min_stop_atr"]:
        return False, f"stop too tight ({in_atr:.2f} ATR, min {cfg['min_stop_atr']})"
    if in_atr > cfg["max_stop_atr"]:
        return False, f"stop too wide ({in_atr:.2f} ATR, max {cfg['max_stop_atr']})"
    return True, f"{in_atr:.2f} ATR"


def sweep_stop(side, sweep_price, atr, cfg=None):
    """SL beyond the swept liquidity, padded by ATR. Never inside the sweep."""
    cfg = {**CFG, **(cfg or {})}
    pad = cfg["sl_buffer_atr"] * atr
    return sweep_price - pad if side == "bull" else sweep_price + pad


# ---------------------------------------------------------------------------
# CONFLUENCE SCORE  (spec section 11)
# ---------------------------------------------------------------------------
def score_setup(flags, cfg=None, weights=None):
    """Return (score, breakdown, hard_ok, blocker).

    hard_ok is False when a mandatory condition is absent, and no score can
    rescue that. The three mandatory conditions are a strict subset of the old
    AND gate, so this model can never take a trade the old one would have
    refused on structural grounds — only ones it refused on alignment grounds.
    """
    cfg = {**CFG, **(cfg or {})}
    w = {**WEIGHTS, **(weights or {})}

    breakdown, score = {}, 0
    for key, weight in w.items():
        hit = bool(flags.get(key, False))
        breakdown[key] = {"hit": hit, "points": weight if hit else 0,
                          "max": weight}
        if hit:
            score += weight

    if cfg["require_sweep"] and not flags.get("liquidity_sweep"):
        return score, breakdown, False, "NO_LIQUIDITY_SWEEP"
    if cfg["require_structure_15m"] and not flags.get("structure_15m"):
        return score, breakdown, False, "NO_15M_STRUCTURE"
    if cfg["require_confirmation_5m"] and not flags.get("confirmation_5m"):
        return score, breakdown, False, "NO_5M_CONFIRMATION"
    if cfg["enforce_daily_location"] and not flags.get("daily_location"):
        return score, breakdown, False, "WRONG_SIDE_OF_DAILY_MID"
    if score < cfg["entry_score"]:
        return score, breakdown, False, "SCORE_BELOW_THRESHOLD"
    return score, breakdown, True, "OK"


def describe(score, breakdown, hard_ok, blocker, cfg=None):
    """Human-readable rejection, built from what was actually evaluated."""
    cfg = {**CFG, **(cfg or {})}
    hits = [k for k, v in breakdown.items() if v["hit"]]
    misses = [k for k, v in breakdown.items() if not v["hit"]]
    return {
        "score": score, "max_score": MAX_SCORE,
        "threshold": cfg["entry_score"],
        "passed": hard_ok,
        "blocker": blocker,
        "present": hits,
        "absent": misses,
        "breakdown": breakdown,
    }
