#!/usr/bin/env python3
"""
app.py — the only process that runs on Render.

GET /api/health
GET /api/config                       account, costs, leverage, parameters
GET /api/signal/<symbol>              BUY / SELL / NO_TRADE / MANAGE + full ticket
GET /api/signals                      all symbols
GET /api/report/<symbol>              3-arm measurement: RANDOM vs SMC vs SMC_MTF

Every signal returns the complete ticket the spec asked for: entry, SL,
TP1/2/3, position size, allowed leverage, risk in rupees, potential profit,
R:R, fees, slippage, 1H bias, 15M setup, 5M trigger and the reason.

A NO_TRADE is returned with the reason, not as an empty payload. Knowing which
timeframe disagreed is the useful part.
"""

import os
import threading
import time
import traceback

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

import backtest as B
import data as D
import mtf_engine as mtf
import risk as R

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

SYMBOLS = ["BTC", "ETH", "DEXE", "BANK"]
SIGNAL_TTL = int(os.environ.get("SIGNAL_TTL", 120))
REPORT_TTL = int(os.environ.get("REPORT_TTL", 3600))
LIVE_BARS_5M = int(os.environ.get("LIVE_BARS_5M", 1000))
REPORT_BARS_5M = int(os.environ.get("REPORT_BARS_5M", 4000))

_cache, _lock = {}, threading.Lock()


def cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1], True
    val = fn()
    with _lock:
        _cache[key] = (now, val)
    return val, False


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else round(v, 8)


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ---------------------------------------------------------------------------
def build_signal(symbol):
    frames, meta = D.load_mtf(symbol, LIVE_BARS_5M)
    if frames is None:
        return {"symbol": symbol, "action": "NO_TRADE",
                "reason": meta.get("error", "no data"), "data": meta}
    source = meta.get("source")

    df5, df15, df1h = frames["5m"], frames["15m"], frames["1h"]
    # calib_end=None is correct here and ONLY here: in a live scan every bar
    # in the frame is already in the past, so there is no future to leak.
    ctx = mtf.build_context(df5, df15, df1h, calib_end=None)

    i = len(df5) - 2                      # last CLOSED 5M bar
    ts = mtf._ts(df5["ts"]).iat[i]
    atr = float(_atr(df5).iat[i])
    price = float(df5["close"].iat[i])

    bias = ctx["bias"][i]
    trig = ctx["trigger"][i] or "none"
    # same call the backtest makes: no price arguments, so the live scanner
    # reports a RESTING LIMIT rather than pretending the bar already filled it
    action, setup, side, level, why = mtf.decide(
        bias, ctx["trigger"][i], ctx["setups"], ts)

    base = {
        "symbol": symbol, "source": source, "price": _f(price),
        "last_closed": str(ts),
        "htf_bias_1h": bias,
        "setup_15m": bool(mtf.active_setups_at(
            ctx["setups"], ts, "bull" if bias == "BULLISH" else
            "bear" if bias == "BEARISH" else None)),
        "trigger_5m": trig,
        "atr_5m": _f(atr),
        "reason": why,
    }

    if action == "NO_TRADE" or setup is None:
        base["action"] = "NO_TRADE"
        return base

    buf = 0.10 * abs(level - setup.stop_level)
    sl = setup.stop_level - buf if side == "bull" else setup.stop_level + buf
    limit = level + 6 * atr if side == "bull" else level - 6 * atr
    s = R.size_position(symbol, action, level, sl, atr=atr, structure_limit=limit)

    if not s.ok:
        base["action"] = "NO_TRADE"
        base["reason"] = f"setup valid but not sizeable: {s.reason}"
        return base

    reachable = [t for t in s.tps if t["reachable"]]
    potential = max((t["net_inr"] for t in reachable), default=0)
    rr = round(potential / s.risk_inr, 2) if s.risk_inr > 0 else None

    base.update({
        "action": action,
        "entry": _f(level), "sl": _f(sl),
        "tp1": s.tps[0] if len(s.tps) > 0 else None,
        "tp2": s.tps[1] if len(s.tps) > 1 else None,
        "tp3": s.tps[2] if len(s.tps) > 2 else None,
        "position_size_qty": _f(s.qty),
        "notional_inr": _f(s.notional_inr), "margin_inr": _f(s.margin_inr),
        "leverage_allowed": s.leverage_allowed,
        "leverage_used": s.leverage_used,
        "leverage_max_venue": s.leverage_max,
        "risk_inr": _f(s.risk_inr),
        "potential_profit_inr": potential,
        "risk_reward": rr,
        "fees_inr": _f(s.fees_inr), "slippage_inr": _f(s.slippage_inr),
        "sl_distance_pct": _f(s.sl_distance_pct),
        "cost_in_r": _f(s.cost_in_r),
        "order_type": "resting limit — fills on a later candle, or not at all",
        "distance_to_entry_pct": _f((level - price) / price * 100),
        "tradeable": bool(s.cost_in_r <= float(os.environ.get("MAX_COST_IN_R", 0.15))),
        "zone": {"top": _f(setup.zone_top), "bottom": _f(setup.zone_bottom),
                 "has_fvg": setup.has_fvg, "swept": setup.swept},
        "reason": (f"1H {bias} + 15M {'OB+FVG' if setup.has_fvg else 'OB'} after "
                   f"liquidity sweep + 5M {trig} shift, entry at OTE"),
    })
    return base


def build_report(symbol):
    frames, meta = D.load_mtf(symbol, REPORT_BARS_5M)
    if frames is None:
        return {"symbol": symbol, "error": meta.get("error", "no data"),
                "data": meta}
    rep = B.full_report(symbol, frames["5m"], frames["15m"], frames["1h"])
    rep["source"] = meta.get("source")
    rep["data"] = meta            # requested vs actual bars, coverage, warnings
    return rep


def build_trade_log(symbol, limit=150):  # noqa: C901
    """The audit trail on its own endpoint, so it can be pulled without
    re-running the whole three-arm report."""
    frames, meta = D.load_mtf(symbol, REPORT_BARS_5M)
    if frames is None:
        return {"symbol": symbol, "error": meta.get("error", "no data")}
    rep = B.full_report(symbol, frames["5m"], frames["15m"], frames["1h"])
    return {"symbol": symbol, "source": meta.get("source"),
            "total": rep.get("trade_log_total", 0),
            "trades": (rep.get("trade_log") or [])[:limit]}


# ---------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "smc-mtf-scanner",
                    "symbols": SYMBOLS, "cached": len(_cache),
                    "time": int(time.time())})


@app.route("/api/config")
def config():
    return jsonify({"costs": R.cost_summary(),
                    "params": mtf.PARAMS,
                    "leverage": {s: {"venue_max": R.MAX_LEVERAGE_BY_SYMBOL.get(s),
                                     "allowed": R.allowed_leverage(s)}
                                 for s in SYMBOLS}})


@app.route("/api/signal/<symbol>")
def signal_one(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    try:
        res, hit = cached(("sig", symbol), SIGNAL_TTL, lambda: build_signal(symbol))
        return jsonify({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"symbol": symbol, "action": "NO_TRADE", "error": str(e)}), 500


@app.route("/api/signals")
def signals():
    out = []
    for s in SYMBOLS:
        try:
            res, _ = cached(("sig", s), SIGNAL_TTL, lambda s=s: build_signal(s))
            out.append(res)
        except Exception as e:
            traceback.print_exc()
            out.append({"symbol": s, "action": "NO_TRADE", "error": str(e)})
    return jsonify({"generated_at": int(time.time()), "results": out,
                    "actionable": sum(1 for r in out
                                      if r.get("action") in ("BUY", "SELL")
                                      and r.get("tradeable"))})


@app.route("/api/report/<symbol>")
def report(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    try:
        res, hit = cached(("rep", symbol), REPORT_TTL, lambda: build_report(symbol))
        # FIX 9: the log is large. Opt in with ?trades=1, otherwise it is
        # stripped so the dashboard poll stays small.
        want = request.args.get("trades") in ("1", "true", "yes")
        payload = dict(res)
        if not want:
            payload.pop("trade_log", None)
        else:
            try:
                lim = min(int(request.args.get("limit", 200)), 1000)
            except ValueError:
                lim = 200
            payload["trade_log"] = (payload.get("trade_log") or [])[:lim]
        return jsonify({**payload, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/trades/<symbol>")
def trades(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    try:
        limit = min(int(request.args.get("limit", 150)), 500)
    except ValueError:
        limit = 150
    try:
        res, hit = cached(("log", symbol, limit), REPORT_TTL,
                          lambda: build_trade_log(symbol, limit))
        return jsonify({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/")
def root():
    return jsonify({"service": "smc-mtf-scanner",
                    "endpoints": ["/api/health", "/api/config",
                                  "/api/signal/<symbol>", "/api/signals",
                                  "/api/report/<symbol>",
                                  "/api/trades/<symbol>"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
