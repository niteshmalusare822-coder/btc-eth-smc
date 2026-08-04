"""
Risk-first position sizing.

The old calc_position_size_for_target() answered "how big must I be to make
Rs.500?". That question has no upper bound: as the stop tightens, the size
required to hit a fixed profit grows without limit. On a Rs.3,000 account it
was returning positions worth Rs.11,000 to Rs.2,27,000.

This module answers the only question that has a safe answer: "how big can I
be so that being wrong costs no more than X% of the account?" Profit is then
whatever it happens to be. Fees are charged on both legs before sizing, so
the stated risk is what actually leaves the account.

Every number is configurable by environment variable so nothing needs a code
change to retune.
"""

import os

# ── Account settings (override via Render environment variables) ────────
CAPITAL_INR = float(os.environ.get("TRADING_CAPITAL_INR", 3000))
RISK_PCT = float(os.environ.get("RISK_PCT_PER_TRADE", 3.0))
USDT_INR = float(os.environ.get("USDT_INR_RATE", 102.0))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", 5))

# Round-trip taker fee as a fraction of notional. 0.05% per leg = 0.001 total.
# The old code charged 0.04% ONCE, which understated cost by more than half.
FEE_RATE_PER_LEG = float(os.environ.get("FEE_RATE_PER_LEG", 0.0005))
ROUND_TRIP_FEE = FEE_RATE_PER_LEG * 2

# Below this the exchange minimum order size makes the trade impossible to
# place at the correct risk, so it is better to say so than to round up.
MIN_NOTIONAL_INR = float(os.environ.get("MIN_NOTIONAL_INR", 200))


def calc_risk_based_size(entry, sl, tp=None, capital_inr=None, risk_pct=None,
                         usdt_inr=None, max_leverage=None):
    """Size a position from the stop distance, not from a profit wish.

    Returns None when the inputs cannot describe a real trade (no direction,
    no stop, or a stop sitting on top of the entry).
    """
    if entry is None or sl is None:
        return None
    try:
        entry = float(entry)
        sl = float(sl)
    except (TypeError, ValueError):
        return None
    if entry <= 0:
        return None

    capital_inr = CAPITAL_INR if capital_inr is None else float(capital_inr)
    risk_pct = RISK_PCT if risk_pct is None else float(risk_pct)
    usdt_inr = USDT_INR if usdt_inr is None else float(usdt_inr)
    max_leverage = MAX_LEVERAGE if max_leverage is None else float(max_leverage)

    sl_distance = abs(entry - sl)
    if sl_distance <= 0:
        return None

    risk_inr = capital_inr * risk_pct / 100.0

    # Being wrong costs the stop distance PLUS the round trip in fees, both
    # scaled by quantity. Solve for qty so the total equals the risk budget.
    cost_per_unit_inr = (sl_distance + entry * ROUND_TRIP_FEE) * usdt_inr
    qty = risk_inr / cost_per_unit_inr

    notional_inr = qty * entry * usdt_inr
    leverage = notional_inr / capital_inr if capital_inr > 0 else float("inf")

    # Leverage cap is a hard ceiling. If honouring it means risking less than
    # the budget, that is fine — under-risking never blew up an account.
    capped = False
    if leverage > max_leverage:
        capped = True
        notional_inr = capital_inr * max_leverage
        qty = notional_inr / (entry * usdt_inr)
        leverage = max_leverage
        risk_inr = qty * cost_per_unit_inr

    profit_at_tp_inr = None
    rr = None
    if tp is not None:
        try:
            tp = float(tp)
            gross = qty * abs(tp - entry) * usdt_inr
            fees = qty * entry * ROUND_TRIP_FEE * usdt_inr
            profit_at_tp_inr = gross - fees
            rr = profit_at_tp_inr / risk_inr if risk_inr > 0 else None
        except (TypeError, ValueError):
            pass

    too_small = notional_inr < MIN_NOTIONAL_INR
    # A trade that pays less than it risks is not a trade, however good the
    # signal looked. This is the gate that kills BTC/ETH 1m scalps, where the
    # round trip in fees eats most of a sub-0.1% ATR target.
    poor_rr = rr is not None and rr < 1.0
    tradeable = not (too_small or poor_rr)

    return {
        "tradeable": tradeable,
        "qty": _sig(qty),
        "notional_inr": round(notional_inr, 2),
        "risk_inr": round(risk_inr, 2),
        "risk_pct_of_capital": round(risk_inr / capital_inr * 100, 2) if capital_inr else None,
        "leverage_needed": round(leverage, 2),
        "leverage_capped": capped,
        "profit_at_tp_inr": round(profit_at_tp_inr, 2) if profit_at_tp_inr is not None else None,
        "reward_risk": round(rr, 2) if rr is not None else None,
        "fee_cost_inr": round(qty * entry * ROUND_TRIP_FEE * usdt_inr, 2),
        "capital_inr": capital_inr,
        "too_small_to_trade": too_small,
        "note": _note(capped, too_small, poor_rr, rr, risk_inr, capital_inr),
    }


def capital_needed_for_profit(entry, sl, tp, target_profit_inr,
                              risk_pct=None, usdt_inr=None):
    """How much capital this trade would need to yield target_profit_inr
    WITHOUT exceeding the risk limit. This is the honest answer to
    'why am I not making Rs.500 a trade' — the account is simply too small."""
    if None in (entry, sl, tp):
        return None
    entry, sl, tp = float(entry), float(sl), float(tp)
    risk_pct = RISK_PCT if risk_pct is None else float(risk_pct)
    usdt_inr = USDT_INR if usdt_inr is None else float(usdt_inr)

    sl_distance = abs(entry - sl)
    tp_distance = abs(tp - entry)
    if sl_distance <= 0 or tp_distance <= 0:
        return None

    fee_per_unit = entry * ROUND_TRIP_FEE
    net_win_per_unit = (tp_distance - fee_per_unit) * usdt_inr
    if net_win_per_unit <= 0:
        return None                      # fees exceed the whole target

    qty_needed = target_profit_inr / net_win_per_unit
    risk_of_that_qty = qty_needed * (sl_distance + fee_per_unit) * usdt_inr
    return round(risk_of_that_qty / (risk_pct / 100.0), 0)


def _sig(qty):
    """Crypto quantities span BANK (thousands) to BTC (0.0001). Keep four
    significant figures instead of four decimal places, or small-priced
    assets lose all precision."""
    if qty <= 0:
        return 0.0
    if qty >= 1000:
        return round(qty, 0)
    if qty >= 1:
        return round(qty, 2)
    return float(f"{qty:.4g}")


def _note(capped, too_small, poor_rr, rr, risk, capital):
    # Most damaging problem first — a warning nobody reads is not a warning.
    if poor_rr:
        return (f"SKIP: after fees this pays only {rr:.2f}x what it risks. "
                f"Fees are eating the target — use a higher-ATR pair or timeframe.")
    if too_small:
        return ("SKIP: position too small to place at this risk level — the "
                "account cannot support this trade.")
    if capped:
        return (f"Size limited by the {MAX_LEVERAGE:g}x leverage cap, so actual "
                f"risk is below the {RISK_PCT:g}% budget. That is fine.")
    return f"Risking Rs.{risk:.0f} of Rs.{capital:.0f}. Never add to this."
