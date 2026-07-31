from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import signal_log
from scanner import fetch_ohlcv_failover
from sma_strategy_test import backtest_sma
from scanner import analyze, run_backtest, run_backtest_full, run_factor_backtest, run_combined_backtest, run_funding_rate_backtest, calc_dynamic_trailing_exit
# new realistic backtest import
from scanner_fixed import improved_run_backtest
import math

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://niteshmalusare822-coder.github.io"}})

@app.after_request
def add_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response

def safe_value(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val

def sanitize(data: dict):
    return {k: safe_value(v) for k, v in data.items()}

def safe_analyze(symbol, timeframe):
    try:
        result = analyze(symbol, timeframe)
        return sanitize(result)
    except Exception as e:
        return {"symbol": symbol, "timeframe": timeframe, "error": str(e)}

@app.route("/")
def home():
    return jsonify({"status": "running"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ── Background dashboard builder ─────────────────────────────
# Publishes each symbol AS SOON as it finishes instead of waiting for all
# four. On Render's free tier (0.1 CPU) a full pass can take minutes, so
# waiting for the whole set meant the dashboard sat on "warming" forever.
# Every step is logged to stdout so Render logs show exactly where time goes.

TICKERS = {
    "btc":  "BTC/USDT:USDT",
    "eth":  "ETH/USDT:USDT",
    "dexe": "DEXE/USDT:USDT",
    "bank": "BANK/USDT:USDT",
}

_DASH = {"data": None, "ts": 0.0, "error": None, "progress": "not started", "passes": 0}
_DASH_LOCK = threading.Lock()
_SCAN_INTERVAL = 10          # seconds to wait between full passes


def _log(msg):
    print(f"[scan] {msg}", flush=True)


def _publish(key, payload):
    with _DASH_LOCK:
        if _DASH["data"] is None:
            _DASH["data"] = {}
        _DASH["data"][key] = payload
        _DASH["ts"] = time.time()
        _DASH["progress"] = f"{key} updated"


def _build_dashboard():
    for key, tick in TICKERS.items():
        t0 = time.time()
        payload = {}
        for tf in ("1m", "5m"):
            t1 = time.time()
            payload[tf] = safe_analyze(tick, tf)
            _log(f"{key} {tf} took {time.time() - t1:.1f}s")
        _publish(key, payload)
        _log(f"{key} published in {time.time() - t0:.1f}s")

        try:
            for tf, p in payload.items():
                signal_log.log_signal(tick, tf, p)
        except Exception as e:
            _log(f"journal failed for {key}: {e}")


def _refresh_loop():
    _log("background scanner thread started")
    while True:
        t0 = time.time()
        try:
            _build_dashboard()
            with _DASH_LOCK:
                _DASH["error"] = None
                _DASH["passes"] += 1
            _log(f"full pass complete in {time.time() - t0:.1f}s")
        except Exception as e:
            with _DASH_LOCK:
                _DASH["error"] = str(e)
            _log(f"pass FAILED: {e}")
        time.sleep(_SCAN_INTERVAL)


_scanner_started = False
_START_LOCK = threading.Lock()


def _ensure_scanner():
    global _scanner_started
    with _START_LOCK:
        if _scanner_started:
            return
        _scanner_started = True
        threading.Thread(target=_refresh_loop, daemon=True).start()


@app.route("/api/dashboard")
def dashboard():
    _ensure_scanner()
    with _DASH_LOCK:
        data = _DASH["data"]
        ts = _DASH["ts"]
        err = _DASH["error"]
        progress = _DASH["progress"]
        passes = _DASH["passes"]

    if not data:
        return jsonify({"warming": True, "progress": progress, "error": err}), 200

    out = dict(data)
    out["_age_seconds"] = round(time.time() - ts, 1)
    out["_progress"] = progress
    out["_passes"] = passes
    if err:
        out["_error"] = err
    return jsonify(out)


@app.route("/api/strategy-test/<symbol>/<timeframe>")
def strategy_test(symbol, timeframe):
    """Does the SMA8/50 setup actually make money? Run it, don't guess."""
    sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT",
               "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
    ticker = sym_map.get(symbol.upper())
    if not ticker:
        return jsonify({"error": f"unknown symbol {symbol}"}), 400
    try:
        return jsonify(backtest_sma(ticker, timeframe))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-test-all")
def strategy_test_all():
    """All four assets, both timeframes, one call."""
    out = {}
    for name, ticker in (("BTC", "BTC/USDT:USDT"), ("ETH", "ETH/USDT:USDT"),
                         ("DEXE", "DEXE/USDT:USDT"), ("BANK", "BANK/USDT:USDT")):
        for tf in ("5m", "15m"):
            try:
                out[f"{name}_{tf}"] = backtest_sma(ticker, tf)
            except Exception as e:
                out[f"{name}_{tf}"] = {"error": str(e)}
    return jsonify(out)

@app.route("/api/backtest/<symbol>/<timeframe>")
def backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_backtest(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# New realistic backtest endpoint
@app.route("/api/backtest-realistic/<symbol>/<timeframe>")
def backtest_realistic(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        # optional query params
        capital = float(request.args.get('capital', 10000))
        fee = float(request.args.get('fee', 0.0004))
        slippage = float(request.args.get('slippage', 0.0003))
        leverage = request.args.get('leverage', None)
        leverage = int(leverage) if leverage is not None else None
        result = improved_run_backtest(full_symbol, timeframe, capital_usdt=capital, fee_taker=fee, slippage=slippage, leverage=leverage)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/backtest-full/<symbol>/<timeframe>")
def backtest_full(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_backtest_full(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/factor-backtest/<symbol>/<timeframe>")
def factor_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_factor_backtest(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/combined-backtest/<symbol>/<timeframe>")
def combined_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        min_agree = int(request.args.get("min_agree", 2))
        strong_adx = float(request.args.get("strong_adx", 25))
        result = run_combined_backtest(full_symbol, timeframe, min_agree, strong_adx)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trail/<symbol>/<timeframe>")
def trail(symbol, timeframe):
    """
    LIVE trade management. Call this AFTER you've taken an entry, passing your
    actual entry/sl/tp — it fetches the current price/ATR itself and returns
    an updated stop-loss: locked at a guaranteed minimum profit once price has
    moved far enough in your favor, then trailing tighter as it extends toward
    your max target.
    Query params: direction=BUY|SELL, entry=<price>, sl=<price>, tp=<price optional>,
                   extreme=<best price since entry, optional>
    """
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")

        direction = request.args.get("direction", "").upper()
        entry = float(request.args.get("entry"))
        sl = float(request.args.get("sl"))
        tp_raw = request.args.get("tp")
        tp = float(tp_raw) if tp_raw not in (None, "") else None
        extreme_raw = request.args.get("extreme")
        extreme = float(extreme_raw) if extreme_raw not in (None, "") else None

        live = analyze(full_symbol, timeframe)
        current_price = live.get("price")
        atr = live.get("atr")

        result = calc_dynamic_trailing_exit(direction, entry, current_price, atr, sl, tp, extreme_price=extreme)
        result["current_price"] = current_price
        result["symbol"] = full_symbol
        result["timeframe"] = timeframe
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/funding-backtest/<symbol>/<timeframe>")
def funding_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        funding_sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT", "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        funding_symbol = funding_sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT")
        result = run_funding_rate_backtest(full_symbol, timeframe, funding_symbol)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


@app.route("/api/journal/stats")
def journal_stats():
    """Is the scanner actually profitable? This is the number that matters."""
    try:
        signal_log.resolve_open(fetch_ohlcv_failover)
    except Exception:
        pass
    return jsonify(signal_log.stats(request.args.get("symbol"),
                                    request.args.get("timeframe")))


@app.route("/api/journal")
def journal_list():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    return jsonify({"signals": signal_log.recent(limit)})


@app.route("/api/journal/resolve")
def journal_resolve():
    n = signal_log.resolve_open(fetch_ohlcv_failover)
    return jsonify({"resolved": n})
