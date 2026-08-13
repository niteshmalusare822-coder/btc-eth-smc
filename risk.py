"""
risk.py — position sizing, leverage and rupee targets.

Replaces sizing.py. The rule this module enforces is the one from the spec:

    Position size comes from the STOP DISTANCE, never from leverage.
    Leverage is a constraint that can only make a position smaller.

The ₹700 risk cap is inclusive of entry fee, exit fee and slippage on both
legs, so the solved quantity is:

    risk_inr = qty * sl_distance_inr + qty * entry_inr * (fee_rt + 2*slip)

        qty = risk_inr / (sl_distance_inr + entry_inr * (fee_rt + 2*slip))

Rupee take-profit levels are DERIVED from that quantity, then checked against
market structure. If the structure cannot carry the move, the level is
returned with reachable=False rather than being quietly forced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict

# ── Account ────────────────────────────────────────────────────────────────
CAPITAL_INR = float(os.environ.get("CAPITAL_INR", 10000))
MAX_RISK_INR = float(os.environ.get("MAX_RISK_INR", 700))
USDT_INR = float(os.environ.get("USDT_INR", 88.0))

# What you would LIKE each level to pay. Aspiration, not instruction.
TP_TARGETS_INR = [
    float(os.environ.get("TP1_INR", 1200)),
    float(os.environ.get("TP2_INR", 2000)),
    float(os.environ.get("TP3_INR", 3500)),
]

# What the market is actually asked to deliver, in R.
#
# BUG FIX: the ladder used to be solved backwards from the rupee targets. At a
# Rs.700 risk cap that demanded 2.47R / 3.94R / 6.68R, and the last two needed
# 7 to 12 ATR of travel — levels a 5M chart reaches almost never. Two thirds of
# every position was therefore aimed at prices that could not print, so the
# only way to book a net win was to hit an impossible target. Hitting TP1 and
# then stopping out netted MINUS Rs.69. That is the whole 1.1% win rate.
#
# The ladder is now structural. Rupee value is REPORTED per level, so you can
# see what each one pays and whether it clears your target, but it no longer
# dictates where the level sits.
TP_R_LADDER = [
    float(os.environ.get("TP1_R", 1.0)),
    float(os.environ.get("TP2_R", 2.0)),
    float(os.environ.get("TP3_R", 3.0)),
]

# ── Costs ──────────────────────────────────────────────────────────────────
FEE_PER_LEG = float(os.environ.get("FEE_PER_LEG", 0.0005))       # 0.05% taker
SLIPPAGE_PER_LEG = float(os.environ.get("SLIPPAGE_PER_LEG", 0.0002))
FUNDING_PER_8H = float(os.environ.get("FUNDING_PER_8H", 0.0001))  # 0.01%
MIN_NOTIONAL_INR = float(os.environ.get("MIN_NOTIONAL_INR", 200))

ROUND_TRIP_FEE = FEE_PER_LEG * 2
ROUND_TRIP_SLIP = SLIPPAGE_PER_LEG * 2
ROUND_TRIP_COST = ROUND_TRIP_FEE + ROUND_TRIP_SLIP

# ── Leverage: 20% of the venue maximum, per coin ───────────────────────────
LEVERAGE_FRACTION = float(os.environ.get("LEVERAGE_FRACTION", 0.20))

# CoinDCX futures maximums. VERIFY these against the venue before going live —
# they change, and a stale number here silently caps or inflates your margin.
MAX_LEVERAGE_BY_SYMBOL = {"BTC": 100, "ETH": 100, "DEXE": 25, "BANK": 20}
DEFAULT_MAX_LEVERAGE = 20


def allowed_leverage(symbol: str) -> float:
    """20% of the coin's maximum. Never the maximum itself."""
    mx = MAX_LEVERAGE_BY_SYMBOL.get(symbol, DEFAULT_MAX_LEVERAGE)
    return round(mx * LEVERAGE_FRACTION, 2)


@dataclass
class Sizing:
    ok: bool
    reason: str
    symbol: str = ""
    direction: str = ""
    entry: float = 0.0
    sl: float = 0.0
    qty: float = 0.0
    notional_usdt: float = 0.0
    notional_inr: float = 0.0
    margin_inr: float = 0.0
    leverage_used: float = 0.0
    leverage_allowed: float = 0.0
    leverage_max: float = 0.0
    sl_distance_pct: float = 0.0
    risk_inr: float = 0.0
    gross_loss_inr: float = 0.0
    fees_inr: float = 0.0
    slippage_inr: float = 0.0
    cost_in_r: float = 0.0
    tps: list = None

    def to_dict(self):
        d = asdict(self)
        return {k: (round(v, 8) if isinstance(v, float) else v) for k, v in d.items()}


def size_position(symbol, direction, entry, sl,
                  capital_inr=None, max_risk_inr=None, usdt_inr=None,
                  atr=None, structure_limit=None):
    """Solve quantity from the stop distance with all costs inside the cap.

    structure_limit: the furthest price the market structure can plausibly
    reach (next liquidity pool, or entry ± N*ATR). Used only to mark rupee
    targets reachable or not. It never changes the size.
    """
    capital_inr = CAPITAL_INR if capital_inr is None else float(capital_inr)
    max_risk_inr = MAX_RISK_INR if max_risk_inr is None else float(max_risk_inr)
    usdt_inr = USDT_INR if usdt_inr is None else float(usdt_inr)

    try:
        entry, sl = float(entry), float(sl)
    except (TypeError, ValueError):
        return Sizing(False, "bad entry/sl")
    if entry <= 0 or direction not in ("BUY", "SELL"):
        return Sizing(False, "bad direction or price")

    sl_dist = abs(entry - sl)
    if sl_dist <= 0:
        return Sizing(False, "stop sits on the entry")
    if (direction == "BUY" and sl >= entry) or (direction == "SELL" and sl <= entry):
        return Sizing(False, "stop is on the wrong side of the entry")

    sl_dist_inr = sl_dist * usdt_inr
    entry_inr = entry * usdt_inr

    # cost per unit of quantity, charged on both legs
    cost_per_unit = entry_inr * ROUND_TRIP_COST
    denom = sl_dist_inr + cost_per_unit
    if denom <= 0:
        return Sizing(False, "degenerate risk")

    qty = max_risk_inr / denom

    notional_inr = qty * entry_inr
    if notional_inr < MIN_NOTIONAL_INR:
        return Sizing(False, f"notional Rs.{notional_inr:.0f} below venue minimum")

    lev_allowed = allowed_leverage(symbol)
    lev_max = MAX_LEVERAGE_BY_SYMBOL.get(symbol, DEFAULT_MAX_LEVERAGE)
    max_notional = capital_inr * lev_allowed

    capped = False
    if notional_inr > max_notional:
        # leverage can only shrink the position, never justify a bigger one
        qty *= max_notional / notional_inr
        notional_inr = max_notional
        capped = True

    lev_used = round(notional_inr / capital_inr, 2) if capital_inr > 0 else 0.0
    margin_inr = notional_inr / lev_allowed if lev_allowed > 0 else notional_inr

    gross_loss = qty * sl_dist_inr
    fees = qty * entry_inr * ROUND_TRIP_FEE
    slip = qty * entry_inr * ROUND_TRIP_SLIP
    total_risk = gross_loss + fees + slip

    # fee expressed against the stop: the number that decides viability
    cost_in_r = (entry_inr * ROUND_TRIP_COST) / sl_dist_inr

    tps = _rupee_targets(direction, entry, qty, usdt_inr, sl_dist,
                         atr=atr, structure_limit=structure_limit)

    return Sizing(
        ok=True,
        reason="leverage-capped, risk below cap" if capped else "sized to risk cap",
        symbol=symbol, direction=direction, entry=entry, sl=sl,
        qty=qty,
        notional_usdt=notional_inr / usdt_inr, notional_inr=notional_inr,
        margin_inr=margin_inr,
        leverage_used=lev_used, leverage_allowed=lev_allowed, leverage_max=lev_max,
        sl_distance_pct=sl_dist / entry * 100,
        risk_inr=total_risk, gross_loss_inr=gross_loss,
        fees_inr=fees, slippage_inr=slip,
        cost_in_r=cost_in_r,
        tps=tps,
    )


def _rupee_targets(direction, entry, qty, usdt_inr, sl_dist,
                   atr=None, structure_limit=None):
    """Structural R ladder, with the rupee value of each level reported.

    reachable is decided by market structure only. An unreachable level is
    still returned so the dashboard can show it greyed out, but the backtest
    must not use it as an exit target.
    """
    out = []
    if qty <= 0 or sl_dist <= 0:
        return out
    entry_inr = entry * usdt_inr
    cost_inr = qty * entry_inr * ROUND_TRIP_COST

    for i, r_mult in enumerate(TP_R_LADDER, start=1):
        move_px = r_mult * sl_dist
        px = entry + move_px if direction == "BUY" else entry - move_px

        gross_inr = qty * move_px * usdt_inr
        net_inr = gross_inr - cost_inr          # full round trip, not a share

        reachable, why = True, ""
        if structure_limit is not None:
            if direction == "BUY" and px > structure_limit:
                reachable, why = False, "beyond the next liquidity level"
            elif direction == "SELL" and px < structure_limit:
                reachable, why = False, "beyond the next liquidity level"
        if reachable and atr and atr > 0 and move_px > 6 * atr:
            reachable, why = False, f"needs {move_px / atr:.1f} ATR of travel"

        want = TP_TARGETS_INR[i - 1] if i <= len(TP_TARGETS_INR) else None
        out.append({
            "level": f"TP{i}",
            "price": round(px, 8),
            "r_multiple": round(r_mult, 2),
            "gross_inr": round(gross_inr, 0),
            "net_inr": round(net_inr, 0),
            "target_inr": want,
            "meets_target": bool(want is not None and net_inr >= want),
            "reachable": reachable,
            "note": why,
        })
    return out


def funding_cost_inr(notional_inr, bars_held, tf_minutes):
    """Funding is charged every 8h. Most intraday trades never pay it; the ones
    that sit through a funding stamp do, and ignoring that flatters the result."""
    hours = bars_held * tf_minutes / 60.0
    periods = hours / 8.0
    return notional_inr * FUNDING_PER_8H * periods


def cost_summary():
    return {
        "capital_inr": CAPITAL_INR,
        "max_risk_inr": MAX_RISK_INR,
        "usdt_inr": USDT_INR,
        "fee_per_leg_pct": FEE_PER_LEG * 100,
        "slippage_per_leg_pct": SLIPPAGE_PER_LEG * 100,
        "round_trip_cost_pct": ROUND_TRIP_COST * 100,
        "funding_per_8h_pct": FUNDING_PER_8H * 100,
        "leverage_fraction": LEVERAGE_FRACTION,
        "tp_targets_inr": TP_TARGETS_INR,
        "tp_r_ladder": TP_R_LADDER,
    }
