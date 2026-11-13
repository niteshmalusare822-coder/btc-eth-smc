"""Live, closed-candle SMC setup alerts using the shared MTF strategy engine.

This scanner never submits orders and cannot verify an exchange fill. A candle
wick touching a planned limit is reported as an unverified event, never as an
exchange execution signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import data as D
import mtf_engine as M
import risk as R

LIVE_BARS_5M = D.clamp_bars(os.environ.get("LIVE_BARS_5M", 1200))
MAX_COST_IN_R = float(os.environ.get("MAX_COST_IN_R", 0.75))
MAX_SIGNAL_BAR_AGE_SECONDS = float(os.environ.get("MAX_SIGNAL_BAR_AGE_SECONDS", 600))


def _base(symbol: str, action: str, reason: str, **extra) -> dict:
    result = {
        "symbol": symbol, "action": action, "tradeable": False, "reason": reason,
        "price": None, "entry": None, "sl": None, "tp1": None, "tp2": None,
        "tp3": None, "position_size_qty": 0.0, "notional_inr": 0.0,
        "margin_inr": 0.0, "leverage_used": 0.0, "risk_inr": 0.0,
        "fees_inr": 0.0, "slippage_inr": 0.0, "cost_in_r": None,
        "max_cost_pct": MAX_COST_IN_R * 100.0, "risk_reward": None,
        "sl_distance_pct": None, "htf_bias_4h": "NEUTRAL", "setup_15m": False,
        "trigger_5m": "none", "zone": None, "blocker": None, "source": None,
        "last_closed": None, "signal_generated_at": datetime.now(timezone.utc).isoformat(),
    }
    result.update(extra)
    return result


def entry_mode_label(mode: object) -> str:
    """Describe the actual entry calculation; unknown modes are not guessed."""
    key = str(mode or "50").strip().lower().replace(" ", "_")
    labels = {
        "50": "POI midpoint", "50%": "POI midpoint", "mid": "POI midpoint",
        "limit_mid": "POI midpoint", "zone_edge": "POI edge", "edge": "POI edge",
        "bottom_top": "POI edge", "wick": "OB wick level", "body": "OB body level",
        "limit_ote": "OTE level",
    }
    return labels.get(key, f"POI level ({key})")


def classify_entry_state(side: str, current: float, entry: float, stop: float,
                         touched: bool, now: datetime | None = None,
                         expires_at: datetime | None = None) -> str:
    """Classify a proposed limit using current/closed-candle evidence.

    Priority is stop invalidation, setup expiry, price already through entry,
    historical candle touch, then a genuinely pending limit. Touch is never a
    broker fill confirmation.
    """
    if side not in ("bull", "bear"):
        raise ValueError("side must be bull or bear")
    if side == "bull":
        if current <= stop:
            return "INVALIDATED"
    elif current >= stop:
        return "INVALIDATED"

    if now is not None and expires_at is not None:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now >= expires_at:
            return "EXPIRED"

    # Price that is already beyond the resting limit is not a fresh opportunity.
    if (side == "bull" and current <= entry) or (side == "bear" and current >= entry):
        return "MISSED_ENTRY"
    if touched:
        return "TOUCHED_UNVERIFIED"
    return "PENDING_LIMIT"


def _as_utc(value) -> datetime | None:
    try:
        parsed = value.to_pydatetime() if hasattr(value, "to_pydatetime") else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _setup_fields(setup, entry: float, stop: float) -> dict:
    mode = getattr(setup, "entry_mode", "50")
    return {
        "entry": entry, "sl": stop, "setup_15m": True,
        "entry_mode": mode, "entry_label": entry_mode_label(mode),
        "zone": {"has_fvg": bool(setup.has_fvg), "entry_mode": mode,
                 "entry_label": entry_mode_label(mode),
                 "top": float(setup.zone_top), "bottom": float(setup.zone_bottom)},
        "setup_confirmed_ts": str(setup.confirmed_ts),
        "setup_expires_ts": str(setup.expires_ts),
    }


def build_signal(symbol: str) -> dict:
    """Build a causal setup from closed candles; never claim an order fill."""
    symbol = str(symbol).upper()
    frames, meta = D.load_mtf(symbol, LIVE_BARS_5M, allow_mixed=False, live=True)
    if frames is None:
        return _base(symbol, "NO_TRADE", (meta or {}).get("error", "No market data"), data_quality=meta or {})
    if any(tf not in frames or frames[tf] is None or frames[tf].empty for tf in ("5m", "15m", "4h")):
        return _base(symbol, "NO_TRADE", "Required closed timeframe data is unavailable", source=(meta or {}).get("source"), data_quality=meta or {})

    df5, df15, df4h = (frames["5m"], frames["15m"], frames["4h"])
    ctx = M.build_context(df5, df15, df4h)
    i = len(df5) - 1
    last_closed = M._ts(df5["ts"]).iat[i]
    bias, trigger, quality = ctx["bias"][i], ctx["trigger"][i], bool(ctx["quality"][i])
    action, setup, side, level, blocker = M.decide(bias, trigger, ctx["setups"], last_closed, quality=quality)
    base = _base(symbol, "NO_TRADE", M.BLOCKERS.get(blocker, blocker),
                 price=float(df5["close"].iat[i]), htf_bias_4h=str(bias),
                 trigger_5m=trigger or "none", blocker=blocker, source=(meta or {}).get("source"),
                 last_closed=str(last_closed), data_quality=meta or {}, quality_5m=quality)
    if action not in ("BUY", "SELL") or setup is None:
        return base

    entry, stop = float(level), float(setup.stop_level)
    fields = _setup_fields(setup, entry, stop)
    now = datetime.now(timezone.utc)
    bar_open = _as_utc(last_closed)
    if bar_open is None:
        return {**base, **fields, "action": "NO_TRADE", "blocker": "STALE_DATA",
                "reason": "Signal candle timestamp is invalid; do not use this setup.", "order_status": "EXPIRED"}
    signal_age = (now - (bar_open + timedelta(minutes=5))).total_seconds()
    expires = _as_utc(setup.expires_ts)
    if signal_age < -30 or signal_age > MAX_SIGNAL_BAR_AGE_SECONDS or (expires and now >= expires):
        return {**base, **fields, "action": "NO_TRADE", "blocker": "EXPIRED",
                "reason": "Signal candle is stale or the setup has expired; do not use it as a fresh entry.",
                "signal_bar_age_seconds": round(signal_age, 1), "order_status": "EXPIRED"}

    targets = M.structure_targets_at(df15, ctx.get("swings_15m", []), last_closed, side, entry, max_targets=3)
    sizing = R.size_position(symbol, action, entry, stop, structure_targets=targets,
                              structure_limit=(targets[-1] if targets else None))
    if not sizing.ok:
        return {**base, **fields, "action": "NO_TRADE", "reason": f"Sizing rejected setup: {sizing.reason}", "order_status": "NOT_TRADEABLE_SIZING"}
    reachable = [t for t in (sizing.tps or []) if t.get("reachable")]
    if not reachable:
        return {**base, **fields, "action": "NO_TRADE", "blocker": "NO_REACHABLE_TARGETS",
                "reason": "No reachable take-profit target; setup is not tradeable.", "order_status": "NOT_TRADEABLE_NO_TARGET"}

    low, high = float(df5["low"].iat[i]), float(df5["high"].iat[i])
    touched = low <= entry if side == "bull" else high >= entry
    current = float(df5["close"].iat[i])
    state = classify_entry_state(side, current, entry, stop, touched, now=now, expires_at=expires)
    if state in ("INVALIDATED", "EXPIRED", "MISSED_ENTRY"):
        descriptions = {
            "INVALIDATED": "Price crossed the planned stop; setup invalidated.",
            "EXPIRED": "Setup expired; it is not a fresh pending entry.",
            "MISSED_ENTRY": "Price already crossed the planned entry; skip it and do not chase.",
        }
        return {**base, **fields, "action": "NO_TRADE", "blocker": state,
                "reason": descriptions[state], "order_status": state,
                "signal_bar_age_seconds": round(signal_age, 1)}

    if sizing.cost_in_r > MAX_COST_IN_R:
        return {**base, **fields, "action": "NO_TRADE", "blocker": "COST_GATE",
                "reason": f"Estimated cost {sizing.cost_in_r:.3f}R exceeds {MAX_COST_IN_R:.3f}R; do not trade.",
                "order_status": "NOT_TRADEABLE_COST"}

    tps = list(sizing.tps or [])[:3] + [None] * (3 - len(sizing.tps or []))
    return {**base, **fields, "action": "WATCHING", "tradeable": False,
            "reason": ("Entry touched on a closed 5m candle; exchange fill is unverified. Do not treat as a fresh entry."
                       if state == "TOUCHED_UNVERIFIED" else
                       "Valid setup; scanner does not place orders. This is a setup alert, not an approved trade."),
            "order_status": state, "signal_bar_age_seconds": round(signal_age, 1),
            "tp1": tps[0], "tp2": tps[1], "tp3": tps[2],
            "position_size_qty": float(sizing.qty), "notional_inr": float(sizing.notional_inr),
            "margin_inr": float(sizing.margin_inr), "leverage_used": float(sizing.leverage_used),
            "risk_inr": float(sizing.risk_inr), "fees_inr": float(sizing.fees_inr),
            "slippage_inr": float(sizing.slippage_inr), "cost_in_r": float(sizing.cost_in_r),
            "risk_reward": max(float(t["r_multiple"]) for t in reachable),
            "sl_distance_pct": float(sizing.sl_distance_pct)}
