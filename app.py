from flask import Flask, jsonify
from flask_cors import CORS
from scanner import analyze

app = Flask(__name__)

CORS(app)

@app.route("/")
def home():
    return jsonify({
        "status": "running"
    })

@app.route("/api/dashboard")
def dashboard():
    return jsonify({
        "btc": {
            "1m": analyze("BTC/USDT:USDT", "1m"),
            "5m": analyze("BTC/USDT:USDT", "5m"),
            "15m": analyze("BTC/USDT:USDT", "15m"),
            "1h": analyze("BTC/USDT:USDT", "1h")
        },
        "eth": {
            "1m": analyze("ETH/USDT:USDT", "1m"),
            "5m": analyze("ETH/USDT:USDT", "5m"),
            "15m": analyze("ETH/USDT:USDT", "15m"),
            "1h": analyze("ETH/USDT:USDT", "1h")
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
