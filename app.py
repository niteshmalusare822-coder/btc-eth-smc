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
LIVE_BARS_5M = int(os.environ.get("LIVE_BARS_5M", 1200))
# FIX 5: a 4000-bar default was about two weeks of 5m data. 10000 is the new
# floor and the caller may ask for more, bounded by data.MAX_BACKTEST_BARS.
REPORT_BARS_5M = D.clamp_bars(os.environ.get("REPORT_BARS_5M",
                                             D.DEFAULT_BACKTEST_BARS))

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
    # no calib_end: calibration is a trailing rolling window, identical to
    # what the backtest computes on the same candles
    ctx = mtf.build_context(df5, df15, df1h)

    # FIX A: data.load_mtf already dropped the forming candle, so the final
    # row IS the last closed bar. Using len-2 here skipped it a second time
    # and made every live signal one candle stale.
    i = len(df5) - 1
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


def build_report(symbol, bars=None):
    bars = D.clamp_bars(bars if bars is not None else REPORT_BARS_5M)
    frames, meta = D.load_mtf(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": meta.get("error", "no data"),
                "data": meta}
    rep = B.full_report(symbol, frames["5m"], frames["15m"], frames["1h"])
    rep["source"] = meta.get("source")
    rep["data_quality"] = meta    # FIX 13
    return rep


def build_trade_log(symbol, limit=150, bars=None):
    """The audit trail on its own endpoint, so it can be pulled without
    re-running the whole three-arm report."""
    frames, meta = D.load_mtf(symbol, D.clamp_bars(bars or REPORT_BARS_5M))
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
                    "default_report_bars": REPORT_BARS_5M,
                    "min_report_bars": D.MIN_BACKTEST_BARS,
                    "max_report_bars": D.MAX_BACKTEST_BARS,
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
        bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
        res, hit = cached(("rep", symbol, bars), REPORT_TTL,
                          lambda: build_report(symbol, bars))
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


def probe_data(symbol, bars):
    """Pagination only. No signals, no backtest, no metrics.

    This exists to answer one question in seconds instead of minutes: when the
    loader asks CoinDCX for N candles, how many does it actually get, how many
    requests did that take, and how long did it hold the worker for.

    It also exposes the assumption most likely to be wrong. The pager walks
    backwards by moving the `to` parameter behind the oldest candle it already
    holds. If the venue ignores that and keeps returning the most recent
    window, `pages_fetched` will stop at 2 and `actual_bars` will sit near one
    page. That pattern means the venue caps by window rather than by count and
    the paging strategy has to change.
    """
    t0 = time.time()
    per_tf = {}
    need = D.required_bars(bars)

    for tf in ("5m", "15m", "1h"):
        t1 = time.time()
        df, meta = D.fetch_ohlcv_history("coindcx", symbol, tf, need[tf])
        if df is None:
            per_tf[tf] = {"requested_bars": need[tf], "actual_bars": 0,
                          "error": meta.get("error"),
                          "seconds": round(time.time() - t1, 2)}
            continue
        pages = meta["pages_fetched"]
        got = meta["actual_bars"]
        per_tf[tf] = {
            "requested_bars": need[tf], "actual_bars": got,
            "short_by": meta["short_by"], "pages_fetched": pages,
            "bars_per_page": round(got / pages, 1) if pages else None,
            "coverage_start": meta["coverage_start"],
            "coverage_end": meta["coverage_end"],
            "seconds": round(time.time() - t1, 2),
            "warnings": D.validate_ohlcv(df, tf),
        }

    five = per_tf.get("5m", {})
    got, want = five.get("actual_bars", 0), five.get("requested_bars", 1)
    pages = five.get("pages_fetched", 0)

    if got == 0:
        diag = "CoinDCX returned nothing. Check the pair string."
    elif got >= want * 0.9:
        diag = "Pagination works. The venue honours the from/to window."
    elif pages <= 2 and got <= D.PAGE_LIMIT * 1.2:
        diag = ("Paging made no progress past the first window. CoinDCX is "
                "very likely ignoring `from` and always returning the most "
                "recent candles. Backward paging will not work against this "
                "endpoint and a different history source is needed.")
    else:
        diag = (f"Paging advanced across {pages} requests but the venue ran "
                f"out at {got} candles. That is all the history it holds.")

    return {"symbol": symbol, "source": "coindcx",
            "requested_bars_5m": bars,
            "actual_bars_5m": got,
            "coverage_days": round(got * 5 / 1440.0, 1),
            "diagnosis": diag,
            "per_timeframe": per_tf,
            "total_seconds": round(time.time() - t0, 2),
            "render_timeout_seconds": 600}


@app.route("/api/data-probe/<symbol>")
def data_probe(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
    try:
        res, hit = cached(("probe", symbol, bars), 300,
                          lambda: probe_data(symbol, bars))
        return jsonify({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"symbol": symbol, "error": str(e)}), 500


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
        bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
        res, hit = cached(("log", symbol, limit, bars), REPORT_TTL,
                          lambda: build_trade_log(symbol, limit, bars))
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
                                  "/api/trades/<symbol>",
                                  "/api/data-probe/<symbol>"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
