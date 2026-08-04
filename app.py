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
import gc
import os

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
    """Keepalive target. Also revives the scanner if its thread has died,
    so an external cron ping is enough to keep the whole thing healthy."""
    _ensure_scanner()
    with _DASH_LOCK:
        return jsonify({
            "status": "ok",
            "scanner_alive": _scanner_thread is not None and _scanner_thread.is_alive(),
            "passes": _DASH["passes"],
            "last_pass_seconds": _DASH["last_pass_seconds"],
            "progress": _DASH["progress"],
            "data_age_seconds": round(time.time() - _DASH["ts"], 1) if _DASH["ts"] else None,
            "error": _DASH["error"],
        })

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

_DASH = {"data": None, "ts": 0.0, "error": None, "progress": "not started",
         "passes": 0, "last_pass_seconds": None, "thread_alive": False}
_DASH_LOCK = threading.Lock()

# Render's free tier gives 0.1 CPU. A full pass over 4 tickers x 2 timeframes
# takes minutes there. Sleeping only 10s meant the loop was effectively running
# back-to-back forever: CPU stayed pinned, Render throttled the container, and
# the /api/dashboard request itself became slow enough for the browser to time
# out. Rest is proportional to how long the pass actually took, with a floor.
_MIN_REST = int(os.environ.get("SCAN_MIN_REST", 60))   # never rest less than this
_REST_RATIO = 1.0                                      # rest ≈ as long as the pass ran
_MAX_REST = 300


def _pending(tick, tf):
    """Placeholder so every ticker exists in the payload from the first byte."""
    return {"symbol": tick, "timeframe": tf, "pending": True}


def _blank_dashboard():
    return {key: {tf: _pending(tick, tf) for tf in ("1m", "5m")}
            for key, tick in TICKERS.items()}


def _log(msg):
    print(f"[scan] {msg}", flush=True)


def _publish(key, payload):
    with _DASH_LOCK:
        if _DASH["data"] is None:
            # Seed every ticker so the frontend never receives a payload that
            # is missing eth/dexe/bank just because btc finished first.
            _DASH["data"] = _blank_dashboard()
        _DASH["data"][key] = payload
        _DASH["ts"] = time.time()
        _DASH["progress"] = f"{key} updated"


def _build_dashboard():
    for key, tick in TICKERS.items():
        t0 = time.time()
        try:
            payload = {}
            for tf in ("1m", "5m"):
                t1 = time.time()
                payload[tf] = safe_analyze(tick, tf)
                _log(f"{key} {tf} took {time.time() - t1:.1f}s")
            _publish(key, payload)
            _log(f"{key} published in {time.time() - t0:.1f}s")
        except Exception as e:
            # One bad ticker (rate limit, delisted contract, exchange hiccup)
            # must not take the other three down with it.
            _log(f"{key} FAILED: {e}")
            _publish(key, {tf: {"symbol": tick, "timeframe": tf, "error": str(e)}
                           for tf in ("1m", "5m")})
            continue

        try:
            for tf, p in payload.items():
                signal_log.log_signal(tick, tf, p)
        except Exception as e:
            _log(f"journal failed for {key}: {e}")


def _refresh_loop():
    _log("background scanner thread started")
    with _DASH_LOCK:
        _DASH["thread_alive"] = True
    while True:
        t0 = time.time()
        try:
            _build_dashboard()
            elapsed = time.time() - t0
            with _DASH_LOCK:
                _DASH["error"] = None
                _DASH["passes"] += 1
                _DASH["last_pass_seconds"] = round(elapsed, 1)
            _log(f"full pass complete in {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            with _DASH_LOCK:
                _DASH["error"] = str(e)
            _log(f"pass FAILED after {elapsed:.1f}s: {e}")

        # pandas frames from the pass are dead by now; hand the memory back
        # before sleeping. 512 MB on the free tier goes fast otherwise.
        gc.collect()

        rest = min(_MAX_REST, max(_MIN_REST, elapsed * _REST_RATIO))
        _log(f"resting {rest:.0f}s before next pass")
        time.sleep(rest)


_scanner_thread = None
_START_LOCK = threading.Lock()


def _ensure_scanner():
    """Start the scanner, or restart it if the thread has died.

    This used to fire only inside /api/dashboard, which meant a keepalive
    pinging /health kept the instance awake without ever starting a scan.
    It now runs at import time as well, and re-checks liveness on each call.
    """
    global _scanner_thread
    with _START_LOCK:
        if _scanner_thread is not None and _scanner_thread.is_alive():
            return
        if _scanner_thread is not None:
            _log("scanner thread was dead — restarting")
        _scanner_thread = threading.Thread(target=_refresh_loop, daemon=True)
        _scanner_thread.start()


# Start immediately on import so gunicorn boots a working scanner without
# needing a browser to hit /api/dashboard first.
_ensure_scanner()


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


@app.route("/api/scanner-status")
def scanner_status():
    """Plain-language view of what the background thread is doing right now."""
    with _DASH_LOCK:
        seeded = _DASH["data"] is not None
        pending = []
        if seeded:
            for key, tfs in _DASH["data"].items():
                for tf, p in tfs.items():
                    if isinstance(p, dict) and p.get("pending"):
                        pending.append(f"{key}/{tf}")
        return jsonify({
            "scanner_alive": _scanner_thread is not None and _scanner_thread.is_alive(),
            "passes_completed": _DASH["passes"],
            "last_pass_seconds": _DASH["last_pass_seconds"],
            "min_rest_seconds": _MIN_REST,
            "progress": _DASH["progress"],
            "still_pending": pending,
            "error": _DASH["error"],
        })


if __name__ == "__main__":
    # Kept at the very bottom on purpose: routes defined below an app.run()
    # call never get registered when running locally with `python app.py`.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
