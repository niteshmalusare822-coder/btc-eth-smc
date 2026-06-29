from flask import Flask, jsonify, request
from flask_cors import CORS
from scanner import analyze, run_backtest, run_backtest_full, run_factor_backtest, run_combined_backtest, run_funding_rate_backtest
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
                "15m": safe_analyze("BTC/USDT:USDT", "15m"),
                "1h": safe_analyze("BTC/USDT:USDT", "1h"),
            },
            "eth": {
                "1m": safe_analyze("ETH/USDT:USDT", "1m"),
                "5m": safe_analyze("ETH/USDT:USDT", "5m"),
                "15m": safe_analyze("ETH/USDT:USDT", "15m"),
                "1h": safe_analyze("ETH/USDT:USDT", "1h"),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/backtest/<symbol>/<timeframe>")
def backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_backtest(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/backtest-full/<symbol>/<timeframe>")
def backtest_full(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_backtest_full(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/factor-backtest/<symbol>/<timeframe>")
def factor_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        result = run_factor_backtest(full_symbol, timeframe)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/combined-backtest/<symbol>/<timeframe>")
def combined_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        min_agree = int(request.args.get("min_agree", 2))
        strong_adx = float(request.args.get("strong_adx", 25))
        result = run_combined_backtest(full_symbol, timeframe, min_agree, strong_adx)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/funding-backtest/<symbol>/<timeframe>")
def funding_backtest(symbol, timeframe):
    try:
        sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        funding_sym_map = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT"}
        full_symbol = sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT:USDT")
        funding_symbol = funding_sym_map.get(symbol.upper(), f"{symbol.upper()}/USDT")
        result = run_funding_rate_backtest(full_symbol, timeframe, funding_symbol)
        return jsonify(sanitize(result))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
