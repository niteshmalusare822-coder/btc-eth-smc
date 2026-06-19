import ccxt
import pandas as pd

exchange = ccxt.mexc({
“enableRateLimit”: True,
“options”: {
“defaultType”: “swap”
}
})

def ema(series, period):
return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
delta = series.diff()

gain = delta.clip(lower=0).rolling(period).mean()
loss = (-delta.clip(upper=0)).rolling(period).mean()
rs = gain / loss
return 100 - (100 / (1 + rs))

def analyze(symbol, timeframe=“5m”):

candles = exchange.fetch_ohlcv(
    symbol,
    timeframe=timeframe,
    limit=200
)
df = pd.DataFrame(
    candles,
    columns=[
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]
)
df["ema9"] = ema(df["close"], 9)
df["ema21"] = ema(df["close"], 21)
df["rsi"] = rsi(df["close"])
price = float(df["close"].iloc[-1])
signal = "WAIT"
if (
    df["ema9"].iloc[-1]
    >
    df["ema21"].iloc[-1]
):
    signal = "BUY"
elif (
    df["ema9"].iloc[-1]
    <
    df["ema21"].iloc[-1]
):
    signal = "SELL"
return {
    "symbol": symbol,
    "timeframe": timeframe,
    "price": round(price, 2),
    "signal": signal,
    "rsi": round(
        float(df["rsi"].iloc[-1]),
        2
    )
}
