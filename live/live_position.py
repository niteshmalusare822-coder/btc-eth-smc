import numpy as np
import pandas as pd

import backtest as C

import threading
from dataclasses import dataclass
from typing import Optional


# ==============================================================
# GLOBAL LIVE POSITION STORE
# ==============================================================

LIVE_POSITIONS = {}
LIVE_POSITIONS_LOCK = threading.RLock()


# ==============================================================
# POSITION STATE
# ==============================================================

@dataclass
class PositionState:
    symbol: str
    side: str

    entry: float
    sl: float

    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None

    risk_inr: float = 0.0
    cost_in_r: float = 0.0

    entry_ts: Optional[str] = None
    exit_ts: Optional[str] = None
    exit_reason: Optional[str] = None

    entry_reached: bool = True

    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False

    trailing_sl: Optional[float] = None
    trailing_enabled: bool = False

    position_status: str = "ACTIVE"


# ==============================================================
# CREATE POSITION
# ==============================================================

def create_position(
    symbol,
    side,
    entry,
    sl,
    tp1=None,
    tp2=None,
    tp3=None,
    risk_inr=0.0,
    cost_in_r=0.0,
    entry_ts=None,
    trailing_enabled=False,
):
    side = str(side).lower()

    if side not in ("bull", "bear"):
        raise ValueError("side must be bull or bear")

    entry = float(entry)
    sl = float(sl)

    if entry <= 0 or sl <= 0:
        raise ValueError("entry and sl must be positive")

    if side == "bull" and sl >= entry:
        raise ValueError("Bull position requires SL below entry")

    if side == "bear" and sl <= entry:
        raise ValueError("Bear position requires SL above entry")

    state = PositionState(
        symbol=symbol,
        side=side,
        entry=entry,
        sl=sl,
        tp1=float(tp1) if tp1 is not None else None,
        tp2=float(tp2) if tp2 is not None else None,
        tp3=float(tp3) if tp3 is not None else None,
        risk_inr=float(risk_inr),
        cost_in_r=float(cost_in_r),
        entry_ts=entry_ts,
        trailing_sl=sl,
        trailing_enabled=trailing_enabled,
    )

    with LIVE_POSITIONS_LOCK:
        LIVE_POSITIONS[symbol] = state

    return state


# ==============================================================
# GET POSITION
# ==============================================================

def get_position(symbol):
    with LIVE_POSITIONS_LOCK:
        return LIVE_POSITIONS.get(symbol)


# ==============================================================
# REMOVE POSITION
# ==============================================================

def remove_position(symbol):
    with LIVE_POSITIONS_LOCK:
        return LIVE_POSITIONS.pop(symbol, None)


# ==============================================================
# POSITION STATUS
# ==============================================================

def position_active(symbol):
    with LIVE_POSITIONS_LOCK:
        return symbol in LIVE_POSITIONS


# ==============================================================
# POSITION TICKET
# ==============================================================

def position_ticket(state, live_price=None):

    effective_sl = (
        state.trailing_sl
        if state.trailing_sl is not None
        else state.sl
    )

    return {
        "symbol": state.symbol,
        "action": "BUY" if state.side == "bull" else "SELL",

        "position_active": True,

        "side": state.side,

        "entry": state.entry,
        "sl": state.sl,
        "effective_sl": effective_sl,

        "tp1": state.tp1,
        "tp2": state.tp2,
        "tp3": state.tp3,

        "entry_reached": state.entry_reached,

        "tp1_hit": state.tp1_hit,
        "tp2_hit": state.tp2_hit,
        "tp3_hit": state.tp3_hit,

        "trailing_enabled": state.trailing_enabled,
        "trailing_sl": state.trailing_sl,

        "status": state.position_status,

        "risk_inr": state.risk_inr,
        "cost_in_r": state.cost_in_r,

        "entry_ts": state.entry_ts,
        "exit_ts": state.exit_ts,
        "exit_reason": state.exit_reason,

        "live_price": live_price,
    }


# ==============================================================
# MANAGE POSITION
# ==============================================================

def manage_position(symbol, live_price, timestamp=None):

    px = float(live_price)

    if px <= 0:
        raise ValueError("live_price must be positive")

    with LIVE_POSITIONS_LOCK:

        state = LIVE_POSITIONS.get(symbol)

        if state is None:
            return None

        # ------------------------------------------------------
        # Waiting for entry fill
        # ------------------------------------------------------

        if not state.entry_reached:

            reached = (
                px <= state.entry
                if state.side == "bull"
                else px >= state.entry
            )

            if not reached:
                return "ACTIVE_POSITION"

            state.entry_reached = True
            state.position_status = "ACTIVE"

            return "ENTRY_REACHED"

        # ------------------------------------------------------
        # Active position
        # ------------------------------------------------------

        effective_sl = (
            state.trailing_sl
            if state.trailing_sl is not None
            else state.sl
        )

        sl_hit = (
            px <= effective_sl
            if state.side == "bull"
            else px >= effective_sl
        )

        if sl_hit:
            state.position_status = "SL_HIT"
            state.exit_reason = "SL_HIT"
            state.exit_ts = timestamp

            LIVE_POSITIONS.pop(symbol, None)

            return "SL_HIT"

        # ------------------------------------------------------
        # TP PRIORITY
        # TP3 -> TP2 -> TP1
        # ------------------------------------------------------

        if state.side == "bull":

            if state.tp3 and px >= state.tp3:
                state.tp3_hit = True
                state.position_status = "TP3_HIT"
                state.exit_reason = "TP3_HIT"
                state.exit_ts = timestamp

                LIVE_POSITIONS.pop(symbol, None)

                return "TP3_HIT"

            if state.tp2 and px >= state.tp2 and not state.tp2_hit:
                state.tp2_hit = True
                state.position_status = "TP2_HIT"

                return "TP2_HIT"

            if state.tp1 and px >= state.tp1 and not state.tp1_hit:
                state.tp1_hit = True
                state.position_status = "TP1_HIT"

                return "TP1_HIT"

        else:

            if state.tp3 and px <= state.tp3:
                state.tp3_hit = True
                state.position_status = "TP3_HIT"
                state.exit_reason = "TP3_HIT"
                state.exit_ts = timestamp

                LIVE_POSITIONS.pop(symbol, None)

                return "TP3_HIT"

            if state.tp2 and px <= state.tp2 and not state.tp2_hit:
                state.tp2_hit = True
                state.position_status = "TP2_HIT"

                return "TP2_HIT"

            if state.tp1 and px <= state.tp1 and not state.tp1_hit:
                state.tp1_hit = True
                state.position_status = "TP1_HIT"

                return "TP1_HIT"

        state.position_status = "ACTIVE"

        return "ACTIVE_POSITION"


# ==============================================================
# TRAILING STOP UPDATE
# ==============================================================

def update_trailing_stop(symbol, new_sl):

    new_sl = float(new_sl)

    with LIVE_POSITIONS_LOCK:

        state = LIVE_POSITIONS.get(symbol)

        if state is None:
            return False

        if not state.trailing_enabled:
            return False

        current_sl = (
            state.trailing_sl
            if state.trailing_sl is not None
            else state.sl
        )

        if state.side == "bull":

            if new_sl <= current_sl:
                return False

        else:

            if new_sl >= current_sl:
                return False

        state.trailing_sl = new_sl

        return True
