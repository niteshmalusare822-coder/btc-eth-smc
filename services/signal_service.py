import os

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
    )

    base = {
        "symbol": symbol,
        "source": source,
        "price": _f(price),
        "last_closed": str(ts),
        #" latest_df5_ts": str(df5["ts"].iat[-1]),

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
        return base

    sl = setup.stop_level

    limit = (
        level + (6 * atr)
        if side == "bull"
        else level - (6 * atr)
    )

    s = R.size_position(
        symbol,
        action,
        level,
        sl,
        atr=atr,
        structure_limit=limit,
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
    
    base.update(
        {
            "action": action,
            "entry": _f(level),
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

            "order_type":
                "resting limit — fills on a later candle, or not at all",

            "distance_to_entry_pct": _f(
                (level - price) / price * 100
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
                f"4H {bias} + 15M "
                f"{'OB+FVG' if setup.has_fvg else 'OB'} "
                f"after liquidity sweep + "
                f"5M {trig} shift, "
                f"entry at OTE"
            ),
        }
    )

    return base
