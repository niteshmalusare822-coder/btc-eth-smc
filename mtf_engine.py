        "Forward entry is stale; price moved too far before the entry was reached",
    "FORWARD_ENTRY_NEAR_MISS":\n        "Forward entry was approached/touched and then rejected; pending limit cancelled",\n}


def decide(bias, trigger, setups, ts):
    """The one decision function. Returns (action, setup, side, level, reason).

    NO PRICE ARGUMENTS. A resting limit is justified at the close of bar i and
    the fill is a separate step starting at bar i+1, so the decision can never
    read the range of the bar it was taken on.

    Every gate is an AND. `reason` is now a BLOCKERS key rather than free text,
    so the exact gate that stopped a trade can be counted across a whole
    history instead of guessed at.
    """
    action, s, side, level, code = _evaluate(bias, trigger, setups, ts)
    return action, s, side, level, code


def _evaluate(bias, trigger, setups, ts):
    if bias not in ("BULLISH", "BEARISH"):
        return "NO_TRADE", None, None, None, "HTF_NEUTRAL"

    side = "bull" if bias == "BULLISH" else "bear"

    #if trigger not in ("bull", "bear"):
        #return "NO_TRADE", None, None, None, "NO_TRIGGER"
    #if trigger != side:
        #return "NO_TRADE", None, None, None, "TRIGGER_WRONG_WAY"

    live = active_setups_at(setups, ts, side)
    if not live:
        # separate "nothing at all" from "something, wrong side / stale", because
        # the fix for each is different
        any_side = active_setups_at(setups, ts)
        if any_side:
            return "NO_TRADE", None, None, None, "SETUP_WRONG_WAY"
        # The blocker code is a MEASUREMENT, so it has to describe THIS bar.
        # The old version ran any() over every setup ever confirmed, on either
        # side, expired or not. A single stale WAITING_FOR_RETEST setup from
        # days earlier pinned the code to AWAITING_RETEST indefinitely, so the
        # blocker histogram counted the wrong gate and anything concluded from
        # it was a conclusion about the wrong thing.
        #
        # Only setups that COULD have been active at ts are candidates: right
        # side, already confirmed, not yet aged out.
        cands = [x for x in setups
                 if x.side == side
                 and x.confirmed_ts <= ts <= x.expires_ts]
        alive = [x for x in cands
                 if not (x.dead_ts is not None and x.dead_ts < ts)]
        if any(x.state == "WAITING_FOR_RETEST"
               or (x.retest_ts is not None and x.retest_ts > ts)
               for x in alive):
            return "NO_TRADE", None, None, None, "AWAITING_RETEST"
        if cands:
            # in-window candidates existed and none survived: price killed them
            return "NO_TRADE", None, None, None, "SETUP_MITIGATED"
        if any(x.side == side and x.confirmed_ts <= ts for x in setups):
            return "NO_TRADE", None, None, None, "SETUP_EXPIRED"
        return "NO_TRADE", None, None, None, "NO_SETUP"

    s = live[0]
    return ("BUY" if side == "bull" else "SELL"), s, side, s.entry_level, "OK"


def gate_state(bias, trigger, setups, ts):
    """Every condition evaluated, whether or not it blocked. This is what the
    dashboard shows instead of a bare NO TRADE."""
    live_any = active_setups_at(setups, ts)
    want = "bull" if bias == "BULLISH" else "bear" if bias == "BEARISH" else None
    live_side = active_setups_at(setups, ts, want) if want else []
    s = live_side[0] if live_side else (live_any[0] if live_any else None)
    action, _, _, _, code = _evaluate(bias, trigger, setups, ts)
    return {
        "htf_bias_4h": bias,
        "setup_15m": bool(live_any),
        "setup_15m_side": (s.side if s else None),
        "trigger_5m": trigger or "none",
        "liquidity_sweep": bool(s.swept) if s else False,
        "imbalance": bool(s.imbalance) if s else False,
        "order_block": bool(s and s.poi_quality in ("OB", "OB+FVG")),
        "fvg": bool(s.has_fvg) if s else False,
        "action": action,
        "blocker": code,
        "blocker_text": BLOCKERS.get(code, code),
    }
