"""Live, closed-candle SMC setup alerts using the shared MTF strategy engine.

This scanner never submits orders and cannot verify an exchange fill. A candle
wick touching a planned limit is therefore reported as an unverified event,
never as a BUY/SELL execution signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import data as D
import mtf_engine as M
import risk as R

LIVE_BARS_5M = D.clamp_bars(os.environ.get("LIVE_BARS_5M", 1200))
MAX_COST_IN_R = float(os.environ.get("MAX_COST_IN_R", 0.75))
MAX_SIGNAL_BAR_AGE_SECONDS = float(
    os.environ.get("MAX_SIGNAL_BAR_AGE_SECONDS", 600)
)


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
        "entry_mode": None,
        "entry_label": "POI midpoint",
    }
    result.update(extra)
    return result


def _entry_mode_label(mode: object) -> str:
    """Return the human-readable label used in the dashboard."""
    normalized = str(mode or "50").strip().lower().replace(" ", "_")
    mapping = {
        "50": "POI midpoint",
        "50%": "POI midpoint",
        "limit_mid": "POI midpoint",
        "mid": "POI midpoint",
        "zone_edge": "OB/FVG edge",
        "edge": "OB/FVG edge",
        "bottom_top": "OB/FVG edge",
        "limit_ote": "OB/FVG edge",
        "wick": "wick",
        "body": "body",
    }
    return mapping.get(normalized, normalized or "POI midpoint")


def _limit_entry_status(side: str, current: float, entry: float, stop: float,
                        touched: bool, age_seconds: float | None = None,
                        max_age_seconds: float = MAX_SIGNAL_BAR_AGE_SECONDS) -> str:
    """Classify the setup without claiming an execution happened."""
    if age_seconds is not None and age_seconds > max_age_seconds:
        return "EXPIRED"

    if side == "bull":
        if current <= stop:
            return "INVALIDATED"
        if touched:
            return "TOUCHED_UNVERIFIED"
        if current <= entry:
            return "MISSED_ENTRY"
    else:
        if current >= stop:
            return "INVALIDATED"
        if touched:
            return "TOUCHED_UNVERIFIED"
        if current >= entry:
            return "MISSED_ENTRY"
    return "PENDING_LIMIT"


def _setup_fields(setup, entry: float, stop: float) -> dict:
    return {
        "entry": entry,
        "sl": stop,
        "setup_15m": True,
        "entry_mode": getattr(setup, "entry_mode", "50"),
        "entry_label": _entry_mode_label(getattr(setup, "entry_mode", "50")),
        "zone": {
            "has_fvg": bool(setup.has_fvg),
            "entry_mode": getattr(setup, "entry_mode", "50"),
            "top": float(setup.zone_top),
            "bottom": float(setup.zone_bottom),
        },
        "setup_confirmed_ts": str(setup.confirmed_ts),
        "setup_expires_ts": str(setup.expires_ts),
    }


def build_signal(symbol: str) -> dict:
    """Build a causal setup from closed candles; never claim an order fill."""
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

    planned_entry = float(level)
    stop = float(setup.stop_level)
    setup_fields = _setup_fields(setup, planned_entry, stop)

    signal_age = None
    if isinstance(last_closed, pd.Timestamp):
        signal_age = (datetime.now(timezone.utc) - last_closed.to_pydatetime().astimezone(timezone.utc)).total_seconds()
    elif last_closed is not None:
        try:
            signal_age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(last_closed).replace("Z", "+00:00")).astimezone(timezone.utc)).total_seconds()
        except Exception:
            signal_age = None

    if signal_age is not None and signal_age > MAX_SIGNAL_BAR_AGE_SECONDS:
        base.update({
            "action": "NO_TRADE",
            "blocker": "EXPIRED",
            "reason": "Setup expired because the last closed 5m candle is stale; do not use this entry.",
            "order_status": "EXPIRED",
            **setup_fields,
        })
        return base

    structure_targets = M.structure_targets_at(
        df15, ctx.get("swings_15m", []), last_closed, side,
        planned_entry, max_targets=3
    )
    sizing = R.size_position(
        symbol, action, planned_entry, stop,
        structure_targets=structure_targets,
        structure_limit=(structure_targets[-1] if structure_targets else None),
    )
    if not sizing.ok:
        base.update({
            "action": "WATCHING",
            "reason": f"Setup found but sizing rejected it: {sizing.reason}",
            "order_status": "NOT_TRADEABLE_SIZING",
            **setup_fields,
        })
        return base

    reachable_targets = [t for t in (sizing.tps or []) if t.get("reachable")]
    if not reachable_targets:
        base.update({
            "action": "NO_TRADE",
            "blocker": "NO_REACHABLE_TARGETS",
            "reason": "No reachable take-profit target is available; setup is not tradeable.",
            "order_status": "EXPIRED",
            **setup_fields,
        })
        return base

    bar_low = float(df5["low"].iat[i])
    bar_high = float(df5["high"].iat[i])
    touched = bar_low <= planned_entry if side == "bull" else bar_high >= planned_entry
    cost_ok = sizing.cost_in_r <= MAX_COST_IN_R
    current_close = float(df5["close"].iat[i])
    entry_status = _limit_entry_status(
        side,
        current_close,
        planned_entry,
        stop,
        touched,
        age_seconds=signal_age,
        max_age_seconds=MAX_SIGNAL_BAR_AGE_SECONDS,
    )

    targets = list(sizing.tps or [])[:3]
    targets += [None] * (3 - len(targets))
    max_r = max((float(t.get("r_multiple", 0)) for t in reachable_targets), default=None)

    if not cost_ok:
        return {
            **base,
            **setup_fields,
            "action": "NO_TRADE",
            "tradeable": False,
            "reason": f"Estimated cost is {sizing.cost_in_r:.3f}R, above the configured {MAX_COST_IN_R:.3f}R maximum; do not trade this setup.",
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
            "order_status": "NOT_TRADEABLE_COST",
        }

    if entry_status == "INVALIDATED":
        base.update({
            "action": "NO_TRADE",
            "blocker": "SETUP_INVALIDATED_BY_PRICE",
            "reason": "Live price has crossed the planned stop; the setup is invalidated and does not qualify as a fresh entry.",
            "order_status": "INVALIDATED",
            **setup_fields,
        })
        return base

    if entry_status == "MISSED_ENTRY":
        base.update({
            "action": "NO_TRADE",
            "blocker": "MISSED_ENTRY",
            "reason": "Price has already crossed the planned level; skip this setup and do not chase the market.",
            "order_status": "MISSED_ENTRY",
            **setup_fields,
        })
        return base

    if entry_status == "EXPIRED":
        base.update({
            "action": "NO_TRADE",
            "blocker": "EXPIRED",
            "reason": "Setup has expired; stale signal should not be treated as a fresh pending entry.",
            "order_status": "EXPIRED",
            **setup_fields,
        })
        return base

    if entry_status == "TOUCHED_UNVERIFIED":
        reason = "Entry level was touched on a closed 5m candle, but exchange fill is unverified. Do not treat this as a fresh entry."
        status = "TOUCHED_UNVERIFIED"
    else:
        reason = "Valid setup; dashboard does not place orders. A resting limit at the planned entry is pending."
        status = "PENDING_LIMIT"

    return {
        **base,
        **setup_fields,
        "action": "WATCHING",
        "tradeable": False,
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
        "order_status": status,
    }
