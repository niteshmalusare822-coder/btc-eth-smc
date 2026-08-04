"""
viability.py — Turns the journal into a straight answer to one question:
"is this worth trading, and at what account size?"

Rs.3,000 at 1% risk is Rs.30 a trade. No strategy on earth turns that into
daily income. So the job of the scanner right now is not to earn — it is to
prove or disprove its own edge while the capital stays intact.

This module reports three things off REAL logged signals:
  1. Where the sample stands against the number of trades needed to call it
  2. What the measured edge would actually pay at the current account size
  3. What account size that same edge would need to hit a target income

Every number comes from resolved journal rows. Nothing here is projected
from a backtest, because a backtest can be retuned until it agrees with you.
"""

import math
import os

RR = float(os.environ.get("TP_ATR_MULT", 2.2)) / float(os.environ.get("SL_ATR_MULT", 0.8))
CAPITAL_INR = float(os.environ.get("TRADING_CAPITAL_INR", 3000))
RISK_PCT = float(os.environ.get("RISK_PCT_PER_TRADE", 1.0))

# Below this many resolved signals, any win rate is noise. See sample_needed().
MIN_SAMPLE = int(os.environ.get("MIN_SAMPLE_FOR_VERDICT", 30))


def breakeven_win_rate(rr=None):
    """The win rate at which a strategy with this reward:risk merely breaks
    even. Losing money above it is impossible; making money below it is too."""
    rr = RR if rr is None else rr
    return 1.0 / (1.0 + rr)


def sample_needed(target_wr, baseline_wr=None, power=0.80, alpha=0.05):
    """Resolved trades needed to distinguish target_wr from breakeven with
    the given statistical power. Two-proportion arcsine approximation."""
    baseline_wr = breakeven_win_rate() if baseline_wr is None else baseline_wr
    if target_wr <= baseline_wr:
        return None
    h = 2 * math.asin(math.sqrt(target_wr)) - 2 * math.asin(math.sqrt(baseline_wr))
    z_a = 1.959963985 if alpha == 0.05 else 1.644853627
    z_b = 0.841621234 if power == 0.80 else 1.281551566
    return int(math.ceil(((z_a + z_b) / h) ** 2))


def wilson_interval(wins, n, z=1.959963985):
    """95% confidence bounds on a win rate. A point estimate off 15 trades is
    meaningless without these — 1/15 looks catastrophic but its interval still
    contains breakeven."""
    if n <= 0:
        return None, None
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def income_projection(win_rate, capital_inr=None, risk_pct=None,
                      trades_per_day=1.0, rr=None):
    """What this win rate pays per trade and per month at a given account
    size. Deliberately reports rupees, not percentages — 45% a month sounds
    like a career until it is printed as Rs.1,856."""
    capital_inr = CAPITAL_INR if capital_inr is None else float(capital_inr)
    risk_pct = RISK_PCT if risk_pct is None else float(risk_pct)
    rr = RR if rr is None else rr

    risk_inr = capital_inr * risk_pct / 100.0
    per_trade = win_rate * risk_inr * rr - (1 - win_rate) * risk_inr
    return {
        "risk_per_trade_inr": round(risk_inr, 2),
        "expectancy_per_trade_inr": round(per_trade, 2),
        "per_month_inr": round(per_trade * trades_per_day * 30, 2),
        "per_month_pct_of_capital": round(per_trade * trades_per_day * 30 / capital_inr * 100, 1),
        "trades_per_day": trades_per_day,
    }


def capital_for_income(win_rate, target_monthly_inr, risk_pct=None,
                       trades_per_day=1.0, rr=None):
    """Account size this edge would need to produce a target monthly income.
    Returns None when the edge is at or below breakeven, because no amount of
    capital makes a losing system pay."""
    risk_pct = RISK_PCT if risk_pct is None else float(risk_pct)
    rr = RR if rr is None else rr
    per_unit = win_rate * rr - (1 - win_rate)      # expectancy per 1 rupee risked
    if per_unit <= 0:
        return None
    monthly_per_rupee_risked = per_unit * trades_per_day * 30
    risk_needed = target_monthly_inr / monthly_per_rupee_risked
    return round(risk_needed / (risk_pct / 100.0), 0)


def assess(journal_stats, capital_inr=None, risk_pct=None,
           trades_per_day=1.0, target_monthly_inr=5000):
    """Full verdict from a signal_log.stats() dict."""
    capital_inr = CAPITAL_INR if capital_inr is None else float(capital_inr)
    risk_pct = RISK_PCT if risk_pct is None else float(risk_pct)

    be = breakeven_win_rate()
    resolved = journal_stats.get("resolved", 0) or 0
    wins = journal_stats.get("wins", 0) or 0
    needed = sample_needed(0.40) or 0

    out = {
        "capital_inr": capital_inr,
        "risk_pct": risk_pct,
        "reward_risk": round(RR, 2),
        "breakeven_win_rate_pct": round(be * 100, 1),
        "resolved_signals": resolved,
        "signals_needed_for_verdict": needed,
        "progress_pct": round(min(100.0, resolved / needed * 100), 1) if needed else None,
    }

    if resolved < MIN_SAMPLE:
        out["stage"] = "COLLECTING"
        out["verdict"] = (f"{resolved} of ~{needed} signals. Too early to judge — "
                          f"do not trade this live yet.")
        out["measured_win_rate_pct"] = round(wins / resolved * 100, 1) if resolved else None
        return out

    wr = wins / resolved
    lo, hi = wilson_interval(wins, resolved)
    out["measured_win_rate_pct"] = round(wr * 100, 1)
    out["win_rate_95_ci_pct"] = [round(lo * 100, 1), round(hi * 100, 1)]

    # The honest test is whether the LOWER bound clears breakeven, not the
    # point estimate. A point estimate above breakeven with an interval
    # straddling it is exactly the illusion that funds losing accounts.
    if hi < be:
        out["stage"] = "DISPROVEN"
        out["verdict"] = ("Edge is statistically absent — the whole confidence "
                          "interval sits below breakeven. Change the strategy, "
                          "do not change the position size.")
        return out
    if lo <= be:
        out["stage"] = "INCONCLUSIVE"
        out["verdict"] = (f"Win rate {wr*100:.1f}% but the interval "
                          f"[{lo*100:.1f}%, {hi*100:.1f}%] still contains breakeven "
                          f"({be*100:.1f}%). Keep collecting — this is not yet an edge.")
        return out

    out["stage"] = "CONFIRMED"
    # Project off the CONSERVATIVE bound, never the flattering point estimate.
    out["projection_at_current_capital"] = income_projection(
        lo, capital_inr, risk_pct, trades_per_day)
    out["capital_needed_for_target"] = capital_for_income(
        lo, target_monthly_inr, risk_pct, trades_per_day)
    out["target_monthly_inr"] = target_monthly_inr
    out["verdict"] = (f"Edge holds at the 95% lower bound ({lo*100:.1f}% vs "
                      f"{be*100:.1f}% breakeven). Projections below use that "
                      f"lower bound, not the headline win rate.")
    return out
