"""Live, closed-candle signal generation using the shared MTF strategy engine.

This module only creates scanner alerts. It never submits orders and does not
claim that an alert is profitable. Entries are limit levels from the existing
SMC POI logic; ``BUY``/``SELL`` means the most recently closed 5m candle
reached that planned level, not that an exchange fill is guaranteed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import data as D
import mtf_engine as M
import risk as R


LIVE_BARS_5M = D.clamp_bars(__import__("os").environ.get("LIVE_BARS_5M", 1200))
MAX_COST_IN_R = float(__import__("os").environ.get("MAX_COST_IN_R", 0.75))


def _base(symbol: str, action: str, reason: str, **extra) -> dict:
    """Return a stable response schema for the dashboard on every path."""
    result = {
        "symbol": symbol,
        "action": action,
        "tradeable": False,
        "reason": reason,
        "price": None,
        "entry": None,
        "sl": None,
        "tp1": None,
        "tp2": None,
        "tp3": None,
        "position_size_qty": 0.0,
        "notional_inr": 0.0,
        "margin_inr": 0.0,
        "leverage_used": 0.0,
        "risk_inr": 0.0,
        "fees_inr": 0.0,
        "slippage_inr": 0.0,
        "cost_in_r": None,
        "max_cost_pct": MAX_COST_IN_R * 100.0,
        "risk_reward": None,
        "sl_distance_pct": None,
        "htf_bias_4h": "NEUTRAL",
        "setup_15m": False,
        "trigger_5m": "none",
        "zone": None,
        "blocker": None,
        "source": None,
        "last_closed": None,
        "signal_generated_at": datetime.now(timezone.utc).isoformat(),
    }
    result.update(extra)
    return result


def build_signal(symbol: str) -> dict:
    """Build a causal signal from closed 5m/15m/4h candles.

    Data errors are reported in the response; unexpected coding errors are not
    swallowed and are handled by the Flask route's existing error handler.
    """
    symbol = str(symbol).upper()
    frames, meta = D.load_mtf(symbol, LIVE_BARS_5M, allow_mixed=False, live=True)
    if frames is None:
        return _base(symbol, "NO_TRADE", (meta or {}).get("error", "No market data"),
                     data_quality=meta or {})

    required = ("5m", "15m", "4h")
    if any(tf not in frames or frames[tf] is None or frames[tf].empty for tf in required):
        return _base(symbol, "NO_TRADE", "Required closed timeframe data is unavailable",
                     source=(meta or {}).get("source"), data_quality=meta or {})

    df5, df15, df4h = (frames["5m"], frames["15m"], frames["4h"])
    ctx = M.build_context(df5, df15, df4h)
    i = len(df5) - 1
    last_closed = M._ts(df5["ts"]).iat[i]
    bias = ctx["bias"][i]
    trigger = ctx["trigger"][i]
    quality = bool(ctx["quality"][i])

    action, setup, side, level, blocker = M.decide(
        bias, trigger, ctx["setups"], last_closed, quality=quality
    )
    base = _base(
        symbol,
        "NO_TRADE",
        M.BLOCKERS.get(blocker, blocker),
        price=float(df5["close"].iat[i]),
        htf_bias_4h=str(bias),
        trigger_5m=trigger or "none",
        blocker=blocker,
        source=(meta or {}).get("source"),
        last_closed=str(last_closed),
        data_quality=meta or {},
        quality_5m=quality,
    )
    if action not in ("BUY", "SELL") or setup is None:
        return base

    direction = action
    planned_entry = float(level)
    stop = float(setup.stop_level)
    structure_targets = M.structure_targets_at(
        df15, ctx.get("swings_15m", []), last_closed, side, planned_entry, max_targets=3
    )
    sizing = R.size_position(
        symbol, direction, planned_entry, stop,
        structure_targets=structure_targets,
        structure_limit=(structure_targets[-1] if structure_targets else None),
    )
    if not sizing.ok:
        base.update({
            "action": "WATCHING",
            "reason": f"Setup found but sizing rejected it: {sizing.reason}",
            "entry": planned_entry,
            "sl": stop,
            "setup_15m": True,
            "zone": {"has_fvg": bool(setup.has_fvg), "entry_mode": setup.entry_mode,
                     "top": float(setup.zone_top), "bottom": float(setup.zone_bottom)},
            "setup_confirmed_ts": str(setup.confirmed_ts),
            "setup_expires_ts": str(setup.expires_ts),
        })
        return base

    # Only the last fully closed 5m candle can produce a fresh touch alert.
    # The signal is not represented as a broker fill.
    bar_low = float(df5["low"].iat[i])
    bar_high = float(df5["high"].iat[i])
    touched = bar_low <= planned_entry if side == "bull" else bar_high >= planned_entry
    cost_ok = sizing.cost_in_r <= MAX_COST_IN_R
    final_action = action if touched else "WATCHING"
    if not cost_ok:
        final_action = "WATCHING"
        reason = (f"POI touched, but estimated cost is {sizing.cost_in_r:.3f}R; "
                  f"configured maximum is {MAX_COST_IN_R:.3f}R")
    elif touched:
        reason = "Closed 5m candle touched the planned POI limit; exchange fill is not verified"
    else:
        reason = "Valid SMC setup; waiting for a future 5m candle to touch the POI limit"

    targets = list(sizing.tps or [])[:3]
    targets += [None] * (3 - len(targets))
    max_r = max((float(t.get("r_multiple", 0)) for t in (sizing.tps or [])), default=None)
    return {
        **base,
        "action": final_action,
        "tradeable": bool(touched and cost_ok),
        "reason": reason,
        "entry": planned_entry,
        "sl": stop,
        "tp1": targets[0],
        "tp2": targets[1],
        "tp3": targets[2],
        "position_size_qty": float(sizing.qty),
        "notional_inr": float(sizing.notional_inr),
        "margin_inr": float(sizing.margin_inr),
        "leverage_used": float(sizing.leverage_used),
        "risk_inr": float(sizing.risk_inr),
        "fees_inr": float(sizing.fees_inr),
        "slippage_inr": float(sizing.slippage_inr),
        "cost_in_r": float(sizing.cost_in_r),
        "risk_reward": max_r,
        "sl_distance_pct": float(sizing.sl_distance_pct),
        "htf_bias_4h": str(bias),
        "setup_15m": True,
        "trigger_5m": trigger or "none",
        "zone": {"has_fvg": bool(setup.has_fvg), "entry_mode": setup.entry_mode,
                 "top": float(setup.zone_top), "bottom": float(setup.zone_bottom)},
        "order_status": "ENTRY_TOUCHED_UNVERIFIED" if touched else "PENDING_LIMIT",
        "setup_confirmed_ts": str(setup.confirmed_ts),
        "setup_expires_ts": str(setup.expires_ts),
    }
