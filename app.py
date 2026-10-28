#!/usr/bin/env python3
"""
app.py — the only process that runs on Render.

GET /api/health
GET /api/config                       account, costs, leverage, parameters
GET /api/live-prices                  CoinDCX websocket prices, REST fallback
GET /api/live-status                  websocket health
GET /api/signal/<symbol>              BUY / SELL / NO_TRADE / MANAGE + full ticket
GET /api/signals                      all symbols
GET /api/report/<symbol>              3-arm measurement: RANDOM vs SMC vs SMC_MTF

Every signal returns the complete ticket the spec asked for: entry, SL,
TP1/2/3, position size, allowed leverage, risk in rupees, potential profit,
R:R, fees, slippage, 4H bias, 15M setup, 5M trigger and the reason.

A NO_TRADE is returned with the reason, not as an empty payload. Knowing which
timeframe disagreed is the useful part.

LIVE PRICE
----------
A background thread listens to the CoinDCX futures trades websocket and keeps
the last traded price per symbol in LIVE_PRICE. /api/live-prices serves it.
Any symbol with no fresh websocket price falls back to the CoinDCX public REST
endpoint. Signal logic in services/ is not touched; /api/signal and
/api/signals only gain an extra `live_price` field.
"""
import json
import os
import threading
import time
import traceback

import requests
import socketio
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
# LIVE PRICE  (CoinDCX websocket + REST fallback)
# ---------------------------------------------------------------------------
PAIR_WS = {s: f"B-{s}_USDT" for s in SYMBOLS}

LIVE_PRICE = {}        # symbol -> {"price": float, "updated_at": epoch}
LIVE_1M_BARS = {}      # symbol -> [{"ts","open","high","low","close","volume"}]
LIVE_WS_LOCK = threading.Lock()
LIVE_WS_STARTED = False
LIVE_WS_CONNECTED = False
LIVE_WS_LAST_ERROR = None

# a websocket price older than this is stale; REST is used for that symbol
LIVE_PRICE_MAX_AGE = float(os.environ.get("LIVE_PRICE_MAX_AGE", 10))
COINDCX_REST_PRICES_URL = (
    "https://public.coindcx.com/market_data/v3/current_prices/futures/rt"
)


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _live_ws_worker():
    global LIVE_WS_LAST_ERROR, LIVE_WS_CONNECTED
    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        global LIVE_WS_CONNECTED
        LIVE_WS_CONNECTED = True
        print(">>> LIVE_WS connected, joining channels", flush=True)
        for pair in PAIR_WS.values():
            sio.emit("join", {"channelName": f"{pair}@trades-futures"})

    @sio.event
    def disconnect():
        global LIVE_WS_CONNECTED
        LIVE_WS_CONNECTED = False
        print(">>> LIVE_WS disconnected", flush=True)

    @sio.on("new-trade")
    def on_new_trade(response):
        try:
            payload = json.loads(response["data"])
        except Exception as e:
            print(">>> TRADE PARSE ERROR:", repr(e), flush=True)
            return

        raw = payload.get("data", payload) if isinstance(payload, dict) else payload
        trade = raw[0] if isinstance(raw, list) and raw else raw

        if not isinstance(trade, dict):
            return

        pair = (
            trade.get("s")
            or trade.get("pair")
            or trade.get("symbol")
            or trade.get("market")
        )

        sym = next((s for s, p in PAIR_WS.items() if p == pair), None)

        if sym is None:
            print(">>> TRADE SYM MISMATCH:", repr(pair), flush=True)
            return

        try:
            price = float(
                trade.get("p")
                or trade.get("price")
                or trade.get("last_price")
            )
        except (TypeError, ValueError):
            print(">>> TRADE PRICE ERROR:", repr(trade), flush=True)
            return

        now = time.time()

        with LIVE_WS_LOCK:
            # ----------------------------------------------------------
            # LIVE PRICE
            # ----------------------------------------------------------
            LIVE_PRICE[sym] = {"price": price, "updated_at": now}

            # ----------------------------------------------------------
            # DEVELOPING 1M CANDLE
            # ----------------------------------------------------------
            minute_start = int(now // 60) * 60

            bars = LIVE_1M_BARS.setdefault(sym, [])

            if not bars or bars[-1]["ts"] != minute_start:
                bars.append({
                    "ts": minute_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 0.0,
                })
            else:
                candle = bars[-1]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price

            # Keep only recent 1M candles.
            if len(bars) > 20:
                del bars[:-20]

    print(">>> LIVE_WS worker thread starting", flush=True)
    while True:
        try:
            print(">>> LIVE_WS attempting connection...", flush=True)
            sio.connect("wss://stream.coindcx.com", transports=["websocket"])
            sio.wait()
        except Exception as e:
            LIVE_WS_LAST_ERROR = repr(e)
            print(f">>> LIVE_WS ERROR: {e!r}", flush=True)
            time.sleep(5)


def start_live_ws_once():
    global LIVE_WS_STARTED
    with LIVE_WS_LOCK:
        if LIVE_WS_STARTED:
            return
        LIVE_WS_STARTED = True
    threading.Thread(target=_live_ws_worker, daemon=True).start()


def post_worker_init(worker):
    """gunicorn hook, kept so a gunicorn.conf.py that imports it still works."""
    start_live_ws_once()


def live_price_fresh(symbol, max_age=LIVE_PRICE_MAX_AGE):
    with LIVE_WS_LOCK:
        entry = LIVE_PRICE.get(symbol)
    if not entry:
        return None
    if time.time() - entry["updated_at"] > max_age:
        return None
    return entry["price"]


def _coindcx_rest_prices():
    """One CoinDCX public REST call for every futures pair.

    Shape: {"ts": ms, "prices": {"B-BTC_USDT": {"ls": last, ...}}}
    "ls" is the last traded price.
    """
    r = requests.get(COINDCX_REST_PRICES_URL, timeout=5)
    r.raise_for_status()
    body = r.json()
    table = body.get("prices") or {}
    out = {}
    for sym, pair in PAIR_WS.items():
        row = table.get(pair)
        if not isinstance(row, dict):
            continue
        px = _f(row.get("ls"))
        if px is not None and px > 0:
            out[sym] = px
    return {"prices": out, "ts": body.get("ts")}


def _with_live_price(res, symbol):
    """Copy a cached ticket and attach the freshest live price, if any."""
    res = dict(res)
    fresh = live_price_fresh(symbol)
    if fresh is not None:
        res["live_price"] = fresh
    return res


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


@app.route("/api/live-status")
def live_status():
    now = time.time()
    with LIVE_WS_LOCK:
        ages = {s: round(now - v["updated_at"], 1)
                for s, v in LIVE_PRICE.items()}
    return jsonify({"started": LIVE_WS_STARTED,
                    "connected": LIVE_WS_CONNECTED,
                    "symbols_with_price": len(ages),
                    "age_sec": ages,
                    "last_error": LIVE_WS_LAST_ERROR})


@app.route("/api/live-prices")
def live_prices():
    """WebSocket price first. Any symbol with no fresh WS price (missing or
    older than LIVE_PRICE_MAX_AGE seconds) is filled from CoinDCX REST."""
    start_live_ws_once()
    now = time.time()
    out = {}

    with LIVE_WS_LOCK:
        for s, v in LIVE_PRICE.items():
            age = now - v["updated_at"]
            if age <= LIVE_PRICE_MAX_AGE:
                out[s] = {"live_price": _f(v["price"]),
                          "age_sec": round(age, 1),
                          "source": "ws"}

    ws_count = len(out)
    rest_error = None
    need_rest = [s for s in SYMBOLS if s not in out]

    if need_rest:
        try:
            rest, _ = cached(("coindcx_rest_prices",), 2,
                             _coindcx_rest_prices)
            rest_age = 0.0
            if rest.get("ts"):
                rest_age = max(0.0, now - float(rest["ts"]) / 1000.0)
            for s in need_rest:
                px = rest["prices"].get(s)
                if px is not None:
                    out[s] = {"live_price": _f(px),
                              "age_sec": round(rest_age, 1),
                              "source": "rest"}
        except Exception as e:
            rest_error = repr(e)
            print(f">>> LIVE_PRICES REST ERROR: {rest_error}", flush=True)

    return jsonify({"prices": out,
                    "ws_symbols": ws_count,
                    "rest_symbols": len(out) - ws_count,
                    "missing": [s for s in SYMBOLS if s not in out],
                    "rest_error": rest_error,
                    "time": int(time.time())})


@app.route("/api/signal/<symbol>")
def signal_one(symbol):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        return jsonify({"error": f"symbol must be one of {SYMBOLS}"}), 400
    try:
        res, hit = cached(("sig", symbol), SIGNAL_TTL, lambda: build_signal(symbol))
        return jsonify({**_with_live_price(res, symbol), "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"symbol": symbol, "action": "NO_TRADE", "error": str(e)}), 500


@app.route("/api/signals")
def signals():
    out = []
    for s in SYMBOLS:
        try:
            res, _ = cached(("sig", s), SIGNAL_TTL, lambda s=s: build_signal(s))
            out.append(_with_live_price(res, s))
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
                                  "/api/live-prices", "/api/live-status",
                                  "/api/signal/<symbol>", "/api/signals",
                                  "/api/report/<symbol>",
                                  "/api/trades/<symbol>",
                                  "/api/data-probe/<symbol>",
                                  "/api/diagnostic/<symbol>",
                                  "/api/portfolio",
                                  "/api/entry-quality/<symbol>"]})


# Start the websocket thread as soon as the app is imported by gunicorn.
# start_live_ws_once() is guarded, so calling it again is harmless.
start_live_ws_once()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
