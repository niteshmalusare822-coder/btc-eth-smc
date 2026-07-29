from flask import Flask, jsonify, request
from flask_cors import CORS
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

@app.route("/api/dashboard")
def dashboard():
    try:
        return jsonify({
            "btc": {
                "1m": safe_analyze("BTC/USDT:USDT", "1m"),
                "5m": safe_analyze("BTC/USDT:USDT", "5m"),
            },
            "eth": {
                "1m": safe_analyze("ETH/USDT:USDT", "1m"),
                "5m": safe_analyze("ETH/USDT:USDT", "5m"),
            },
            "dexe": {
                "1m": safe_analyze("DEXE/USDT:USDT", "1m"),
                "5m": safe_analyze("DEXE/USDT:USDT", "5m"),
            },
            "bank": {
                "1m": safe_analyze("BANK/USDT:USDT", "1m"),
                "5m": safe_analyze("BANK/USDT:USDT", "5m"),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
