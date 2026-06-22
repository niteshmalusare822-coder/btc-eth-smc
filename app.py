from flask import Flask, jsonify
from flask_cors import CORS
from scanner import analyze
import math

app = Flask(__name__)

# CORS configuration
CORS(app, resources={r"/api/*": {"origins": "https://niteshmalusare822-coder.github.io"}})

# ✅ Add headers after every response
@app.after_request
def add_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response

# ✅ Helper to sanitize NaN/Infinity values
def safe_value(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val

def sanitize(data: dict):
    """Convert NaN/Infinity in analyze() output to None"""
    return {k: safe_value(v) for k, v in data.items()}

def safe_analyze(symbol, timeframe):
    """
    Agar ek timeframe ka analyze() crash kare toh
    poora dashboard crash nahi hoga — sirf us TF mein error aayega
    """
    try:
        result = analyze(symbol, timeframe)
        return sanitize(result)
    except Exception as e:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(e)
        }

# ✅ Basic home route
@app.route("/")
def home():
    return jsonify({"status": "running"})

# ✅ UptimeRobot ke liye dedicated lightweight ping route
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ✅ Main dashboard route
@app.route("/api/dashboard")
def dashboard():
    try:
        return jsonify({
            "btc": {
                "1m":  safe_analyze("BTC/USDT:USDT", "1m"),
                "5m":  safe_analyze("BTC/USDT:USDT", "5m"),
                "15m": safe_analyze("BTC/USDT:USDT", "15m"),
                "1h":  safe_analyze("BTC/USDT:USDT", "1h"),
            },
            "eth": {
                "1m":  safe_analyze("ETH/USDT:USDT", "1m"),
                "5m":  safe_analyze("ETH/USDT:USDT", "5m"),
                "15m": safe_analyze("ETH/USDT:USDT", "15m"),
                "1h":  safe_analyze("ETH/USDT:USDT", "1h"),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
