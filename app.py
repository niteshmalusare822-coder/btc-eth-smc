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

@app.route("/")
def home():
    return jsonify({
        "status": "running"
    })

@app.route("/api/dashboard")
def dashboard():
    return jsonify({
        "btc": {
            "1m": sanitize(analyze("BTC/USDT:USDT", "1m")),
            "5m": sanitize(analyze("BTC/USDT:USDT", "5m")),
            "15m": sanitize(analyze("BTC/USDT:USDT", "15m")),
            "1h": sanitize(analyze("BTC/USDT:USDT", "1h"))
        },
        "eth": {
            "1m": sanitize(analyze("ETH/USDT:USDT", "1m")),
            "5m": sanitize(analyze("ETH/USDT:USDT", "5m")),
            "15m": sanitize(analyze("ETH/USDT:USDT", "15m")),
            "1h": sanitize(analyze("ETH/USDT:USDT", "1h"))
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
