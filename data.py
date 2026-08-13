"""
data.py — OHLCV loading. CoinDCX first, ccxt failover second.

CoinDCX is the venue you are actually filled on, so it is the primary source.
A stop that never triggered on Binance data may well have triggered on the
CoinDCX book. Every loader returns the source name so a result computed on a
failover venue is visible rather than silent.
"""

from __future__ import annotations

import time

import pandas as pd

COINDCX_URL = "https://public.coindcx.com/market_data/candlesticks"

PAIR_MAP = {
    "BTC": "B-BTC_USDT",
    "ETH": "B-ETH_USDT",
    "DEXE": "B-DEXE_USDT",
    "BANK": "B-BANK_USDT",   # VERIFY the exact pair string on CoinDCX
}

CCXT_MAP = {
    "BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT",
    "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT",
}

RESOLUTION = {"5m": "5", "15m": "15", "1h": "60"}
TF_SECONDS = {"5m": 300, "15m": 900, "1h": 3600}
FAILOVER = ["mexc", "bybit", "okx", "gateio"]

_ccxt_cache = {}
OHLC = ["open", "high", "low", "close", "volume"]


def _clean(df, bars):
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    df = df.astype({c: float for c in OHLC})
    return df.tail(bars).reset_index(drop=True)


def fetch_coindcx(symbol, tf, bars):
    import requests
    pair, res, secs = PAIR_MAP.get(symbol), RESOLUTION.get(tf), TF_SECONDS.get(tf)
    if not (pair and res and secs):
        return None, None
    to_t = int(time.time())
    from_t = to_t - secs * (bars + 10)
    try:
        r = requests.get(COINDCX_URL, timeout=20, params={
            "pair": pair, "from": from_t, "to": to_t, "resolution": res, "pcode": "f"})
        r.raise_for_status()
        data = r.json()
        candles = data.get("data", data) if isinstance(data, dict) else data
        if not candles or len(candles) < 200:
            return None, None
        rows = []
        for c in candles:
            ts = c.get("time", c.get("t"))
            o, h = c.get("open", c.get("o")), c.get("high", c.get("h"))
            lo, cl = c.get("low", c.get("l")), c.get("close", c.get("c"))
            v = c.get("volume", c.get("v", 0))
            if None in (ts, o, h, lo, cl):
                continue
            rows.append([ts, o, h, lo, cl, v])
        if len(rows) < 200:
            return None, None
        df = pd.DataFrame(rows, columns=["ts"] + OHLC)
        unit = "ms" if df["ts"].iloc[0] > 10 ** 12 else "s"
        df["ts"] = pd.to_datetime(df["ts"], unit=unit)
        return _clean(df, bars), "coindcx"
    except Exception:
        return None, None


def fetch_ccxt(symbol, tf, bars):
    try:
        import ccxt
    except ImportError:
        return None, None
    sym = CCXT_MAP.get(symbol)
    if not sym:
        return None, None
    for ex_id in FAILOVER:
        try:
            if ex_id not in _ccxt_cache:
                _ccxt_cache[ex_id] = getattr(ccxt, ex_id)({"enableRateLimit": True})
            o = _ccxt_cache[ex_id].fetch_ohlcv(sym, tf, limit=min(bars, 1000))
            if not o or len(o) < 200:
                continue
            df = pd.DataFrame(o, columns=["ts"] + OHLC)
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return _clean(df, bars), ex_id
        except Exception:
            continue
    return None, None


def load(symbol, tf, bars):
    df, src = fetch_coindcx(symbol, tf, bars)
    if df is not None:
        return df, src
    return fetch_ccxt(symbol, tf, bars)


def load_mtf(symbol, bars_5m):
    """All three frames from ONE source where possible.

    Mixing venues across timeframes would mean the 1H bias is computed on
    different prints than the 5M entry, which is a subtle way to make a
    backtest disagree with reality.
    """
    out, sources = {}, set()
    need = {"5m": bars_5m, "15m": max(400, bars_5m // 3), "1h": max(300, bars_5m // 12)}
    for tf, n in need.items():
        df, src = load(symbol, tf, n)
        if df is None or len(df) < 250:
            return None, src
        out[tf] = df
        sources.add(src)
    return out, "+".join(sorted(sources))
