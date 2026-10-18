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
R:R, fees, slippage, 4H bias, 15M setup, 5M trigger and the reason.

A NO_TRADE is returned with the reason, not as an empty payload. Knowing which
timeframe disagreed is the useful part.
"""
import os
import threading
import time
import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

import data as D
import diagnostics as DG
import mtf_engine as mtf
import risk as R

from services.signal_service import build_signal

from services.report_service import (
    build_report,
    build_trade_log,
    build_diagnostic,
    build_entry_quality,
    probe_data,
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

SYMBOLS = ["BTC", "ETH", "DEXE", "SOL", "XRP", "AVAX", "LINK", "DOGE", "ADA", "BNB", "BANK", "SUI", "HBAR", "LTC", "BCH", "DOT", "1000PEPE"]
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




@app.route("/api/diagnostic/<symbol>")
def diagnostic(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
    try:
        res, hit = cached(("diag", symbol, bars), REPORT_TTL,
                          lambda: build_diagnostic(symbol, bars))
        payload = {k: v for k, v in res.items() if k != "_trades"}
        return jsonify({**payload, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"symbol": symbol, "error": str(e)}), 500


@app.route("/api/portfolio")
def portfolio():
    """All four assets plus a portfolio total built from pooled trades."""
    bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
    per_asset, all_trades, diags = [], [], []
    for s in SYMBOLS:
        try:
            res, _ = cached(("diag", s, bars), REPORT_TTL,
                            lambda s=s: build_diagnostic(s, bars))
            if res.get("error"):
                per_asset.append({"symbol": s, "error": res["error"]})
                continue
            per_asset.append(res["per_asset"]["SMC"])
            all_trades.extend(res.get("_trades") or [])
            diags.append({k: v for k, v in res.items()
                          if k in ("symbol", "significant_moves",
                                   "true_missed_signals", "valid_no_trades",
                                   "capture_rate_pct", "true_miss_rate_pct",
                                   "blockers")})
        except Exception as e:
            traceback.print_exc()
            per_asset.append({"symbol": s, "error": str(e)})

    merged = {}
    for d in diags:
        for k, v in (d.get("blockers") or {}).items():
            merged[k] = merged.get(k, 0) + v

    return jsonify({
        "per_asset": per_asset,
        "portfolio": DG.portfolio_from_trades(all_trades),
        "market_wide_diagnostic": {
            "symbols_analysed": len(diags),
            "total_significant_moves": sum(d["significant_moves"] for d in diags),
            "true_missed_signals": sum(d["true_missed_signals"] for d in diags),
            "valid_no_trades": sum(d["valid_no_trades"] for d in diags),
            "blockers": dict(sorted(merged.items(), key=lambda kv: -kv[1])),
            "per_symbol": diags,
        },
    })

@app.route("/api/entry-quality/<symbol>")
def entry_quality(symbol):
    """Root-cause diagnostics: entry vs exit failure, gate value, position
    modes, score buckets. Heavy — one symbol at a time."""
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    bars = D.clamp_bars(request.args.get("bars", REPORT_BARS_5M))
    try:
        res, hit = cached(("eq", symbol, bars), REPORT_TTL,
                          lambda: build_entry_quality(symbol, bars))
        return jsonify({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"symbol": symbol, "error": str(e)}), 500


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
                                  "/api/data-probe/<symbol>",
                                  "/api/diagnostic/<symbol>",
                                  "/api/portfolio",
                                  "/api/entry-quality/<symbol>"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
