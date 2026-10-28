import os
from datetime import datetime, timezone  # <--- नवीन इम्पोर्ट ॲड केला

import numpy as np
import pandas as pd

import data as D
import mtf_engine as mtf
import risk as R


LIVE_BARS_5M = int(
    os.environ.get("LIVE_BARS_5M", 1200)
)

MAX_COST_IN_R = float(
    os.environ.get("MAX_COST_IN_R", 0.75)
)


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None

    return None if not np.isfinite(v) else round(v, 8)


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]

    pc = c.shift(1)

    tr = pd.concat(
        [
            h - l,
            (h - pc).abs(),
            (l - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


def build_signal(symbol):
    frames, meta = D.load_mtf(
        symbol,
        LIVE_BARS_5M
    )

    if frames is None:
        return {
            "symbol": symbol,
            "action": "NO_TRADE",
            "reason": meta.get("error", "no data"),
            "data": meta,
        }

    source = meta.get("source")

    df5 = frames["5m"]
    df15 = frames["15m"]
    df4h = frames["4h"]

    ctx = mtf.build_context(
        df5,
        df15,
        df4h
    )

    i = len(df5) - 1

    ts = mtf._ts(df5["ts"]).iat[i]
    atr = float(_atr(df5).iat[i])
    price = float(df5["close"].iat[i])

    bias = ctx["bias"][i]
    trig = ctx["trigger"][i] or "none"

    action, setup, side, level, why = mtf.decide(
        bias,
        ctx["trigger"][i],
        ctx["setups"],
        ts,
        quality=ctx["quality"][i],
    )

    # ============================================================
    # STRICT 30-MINUTE TIME FILTER (जुने सिग्नल्स रोखण्यासाठी)
    # ============================================================
        # STRICT 30-MINUTE TIME FILTER (सेटअपच्या वेळेची तपासणी)
    now_utc = datetime.now(timezone.utc)
    
    # सेटअपची वेळ तपासा (setup object मधून)
    if hasattr(setup, 'ts'):
        setup_ts = setup.ts
    else:
        setup_ts = ts  # fallback to current candle time
    
    if setup_ts.tzinfo is None:
        setup_ts_aware = setup_ts.replace(tzinfo=timezone.utc)
    else:
        setup_ts_aware = setup_ts
        
    age_minutes = (now_utc - setup_ts_aware).total_seconds() / 60

    
    # जर सिग्नल ३० मिनिटांपेक्षा जुना असेल, तर जबरदस्तीने NO_TRADE करा
    if age_minutes > 30 and action in ["BUY", "SELL"]:
        action = "NO_TRADE"
        why = f"Signal too old ({int(age_minutes)} mins). Strictly fresh signals only."
        setup = None  # सेटअप रद्द करा जेणेकरून पुढे एन्ट्री मिळणार नाही
    # ============================================================

    # ============================================================
    
        # ============================================================
    # PROACTIVE LOGIC: फक्त Limit Order (गाडीच्या मागे धावू नका)
    # ============================================================
    entry_type = "limit"
    entry_price = level
    
    # बॉट आता नेहमी Zone च्या 50% ला Limit Order लावेल.
    # जर प्राईस खूप दूर गेली असेल, तर खालील R:R Safety Lock 
    # ती ऑर्डर आपोआप रद्द (NO_TRADE) करेल.
    # ============================================================


    base = {
        "symbol": symbol,
        "source": source,
        "price": _f(price),
        "last_closed": str(ts),
        "signal_generated_at": str(ts),
        "htf_bias_4h": bias,
        "setup_15m": bool(
            mtf.active_setups_at(
                ctx["setups"],
                ts,
                "bull"
                if bias == "BULLISH"
                else "bear"
                if bias == "BEARISH"
                else None,
            )
        ),
        "trigger_5m": trig,
        "atr_5m": _f(atr),
        "reason": why,
    }

    if action == "NO_TRADE" or setup is None:
        base["action"] = "NO_TRADE"
        # जुना सेटअप डॅशबोर्डवर दिसू नये म्हणून टाइमस्टॅम्प क्लिअर करा
        base["last_closed"] = str(datetime.now(timezone.utc))
        base["signal_generated_at"] = str(datetime.now(timezone.utc))
        base["reason"] = why if why else "No fresh setup found in last 30 minutes"
        return base


    sl = setup.stop_level

    s = R.size_position(
        symbol,
        action,
        entry_price,
        sl,
        atr=atr,
        structure_limit=(
            entry_price + (6 * atr)
            if side == "bull"
            else entry_price - (6 * atr)
        ),
    )

    if not s.ok:
        base["action"] = "NO_TRADE"
        base["reason"] = (
            f"setup valid but not sizeable: {s.reason}"
        )
        return base

    reachable = [
        t for t in s.tps
        if t["reachable"]
    ]

    potential = max(
        (t["net_inr"] for t in reachable),
        default=0,
    )
    
    rr = (
        round(potential / s.risk_inr, 2)
        if s.risk_inr > 0
        else None
    )

     # ============================================================
    # NAKED OB DETECTION & STRICT R:R RULE
    # ============================================================
    setup_type = "STANDARD SMC"  # Default
    is_naked_ob = False
    
    if setup is not None:
        # जर FVG नसेल आणि आधीची Liquidity Sweep झाली नसेल, तर हे Naked OB आहे
        if not setup.has_fvg and not setup.swept:
            is_naked_ob = True
            setup_type = "AGGRESSIVE NAKED OB"
            
            # Naked OB साठी कडक R:R नियम (किमान 1.5)
            if rr is not None and rr < 1.5:
                action = "NO_TRADE"
                why = f"Aggressive Naked OB requires min 1.5 R:R. Current: {rr}."
                setup = None
    # ============================================================
    
    # ============================================================
    # RULE 2: R:R SAFETY LOCK (पैसे वाचवण्यासाठी)
    # ============================================================
    if rr is not None and rr < 1.0:
        base["action"] = "NO_TRADE"
        base["reason"] = (
            f"Price moved too far. R:R dropped to {rr}. "
            f"Entry type: {entry_type}. Skipped to protect capital."
        )
        return base
    # ============================================================

    base.update(
        {
            "action": action,
            "entry": _f(entry_price),
            "sl": _f(sl),

            "tp1": s.tps[0] if len(s.tps) > 0 else None,
            "tp2": s.tps[1] if len(s.tps) > 1 else None,
            "tp3": s.tps[2] if len(s.tps) > 2 else None,

            "position_size_qty": _f(s.qty),
            "notional_inr": _f(s.notional_inr),
            "margin_inr": _f(s.margin_inr),

            "leverage_allowed": s.leverage_allowed,
            "leverage_used": s.leverage_used,
            "leverage_max_venue": s.leverage_max,

            "risk_inr": _f(s.risk_inr),
            "potential_profit_inr": potential,
            "risk_reward": rr,

            "fees_inr": _f(s.fees_inr),
            "slippage_inr": _f(s.slippage_inr),

            "sl_distance_pct": _f(s.sl_distance_pct),
            "cost_in_r": _f(s.cost_in_r),

            "order_type": (
                "resting limit — fills on a later candle, or not at all"
                if entry_type == "limit"
                else "market momentum — fills immediately at current price"
            ),

            "distance_to_entry_pct": _f(
                (entry_price - price) / price * 100
            ),

            "tradeable": bool(
                s.cost_in_r <= MAX_COST_IN_R
            ),

            "zone": {
                "top": _f(setup.zone_top),
                "bottom": _f(setup.zone_bottom),
                "has_fvg": setup.has_fvg,
                "swept": setup.swept,
                "imbalance": setup.imbalance,
                "entry_mode": setup.entry_mode,
            },

            "reason": (
                f"[{setup_type}] "
                f"4H {bias} + 15M "
                f"{'OB+FVG' if setup.has_fvg else 'Naked OB'} "
                f"{'(Swept)' if setup.swept else '(No Sweep)'} + "
                f"5M {trig} shift, "
                f"entry at OTE ({entry_type})"
            ),
        }
    )

    return base
