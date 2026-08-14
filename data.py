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


def to_ns(series):
    """Every timestamp in this project is datetime64[ns]. No exceptions."""
    out = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(out.dtype, "tz", None) is not None:
            out = out.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return out.astype("datetime64[ns]")


def _clean(df, bars):
    # Force a single timestamp resolution at the door. pandas will happily hand
    # back datetime64[us] from one venue and datetime64[ns] from another, and
    # merge_asof refuses to join across resolutions — which is exactly how the
    # 1H bias failed to reach the 5M timeline. Normalising here means no
    # downstream code has to think about it.
    df["ts"] = to_ns(df["ts"])
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


def fetch_ccxt_venue(symbol, tf, bars, ex_id):
    """One named venue. load_mtf needs this so it can keep all three
    timeframes on the same book instead of failing over per frame."""
    try:
        import ccxt
    except ImportError:
        return None, None
    sym = CCXT_MAP.get(symbol)
    if not sym:
        return None, None
    try:
        if ex_id not in _ccxt_cache:
            _ccxt_cache[ex_id] = getattr(ccxt, ex_id)({"enableRateLimit": True})
        o = _ccxt_cache[ex_id].fetch_ohlcv(sym, tf, limit=min(bars, 1000))
        if not o or len(o) < 200:
            return None, None
        df = pd.DataFrame(o, columns=["ts"] + OHLC)
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return _clean(df, bars), ex_id
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


def _fetch_one(symbol, tf, bars, venue):
    if venue == "coindcx":
        return fetch_coindcx(symbol, tf, bars)
    return fetch_ccxt_venue(symbol, tf, bars, venue)


def load_mtf(symbol, bars_5m, allow_mixed=False):
    """FIX 7 + FIX 8. All three frames from ONE venue, forming candle removed.

    Old behaviour: each timeframe was fetched independently with its own
    CoinDCX-then-ccxt failover, so 5m could come from CoinDCX while 1h came
    from gateio. The 1H bias was then computed on different prints than the 5M
    entries and nobody could see it. Venues are now tried whole: every frame
    from CoinDCX, or every frame from one failover, and mixed data is refused
    unless explicitly allowed.

    FIX 8: the final candle of every frame is still forming. It is dropped
    here, at the door, so no downstream code can accidentally read a high or
    low that has not finished printing.

    Returns (frames, meta). meta reports requested vs actual bars per frame, so
    asking for 4000 and receiving 1000 is visible instead of silent.
    """
    need = {"5m": bars_5m,
            "15m": max(400, bars_5m // 3),
            "1h": max(300, bars_5m // 12)}

    venues = ["coindcx"] + FAILOVER
    partial = None

    for venue in venues:
        frames, ok = {}, True
        for tf, n in need.items():
            # +1 because the newest candle is dropped as still forming
            df, _ = _fetch_one(symbol, tf, n + 1, venue)
            if df is None or len(df) < 251:
                ok = False
                break
            frames[tf] = df.iloc[:-1].reset_index(drop=True)   # FIX 8
        if ok:
            return frames, _meta(symbol, frames, venue, need, mixed=False)
        if partial is None and frames:
            partial = (frames, venue)

    if not allow_mixed:
        return None, {"symbol": symbol, "source": None,
                      "error": "no single venue served all three timeframes",
                      "mixed": False}

    # explicit opt-in only, and loudly labelled
    frames, used = {}, []
    for tf, n in need.items():
        df, src = load_any(symbol, tf, n + 1)
        if df is None or len(df) < 251:
            return None, {"symbol": symbol, "source": None,
                          "error": f"no venue served {tf}", "mixed": True}
        frames[tf] = df.iloc[:-1].reset_index(drop=True)
        used.append(src)
    meta = _meta(symbol, frames, "MIXED: " + " + ".join(sorted(set(used))),
                 need, mixed=True)
    meta["warning"] = ("Timeframes came from different venues. Bias and entries "
                       "are computed on different prints; treat results as "
                       "indicative only.")
    return frames, meta


def _meta(symbol, frames, source, need, mixed):
    out = {"symbol": symbol, "source": source, "mixed": bool(mixed), "frames": {}}
    for tf, df in frames.items():
        out["frames"][tf] = {
            "requested_bars": int(need[tf]),
            "actual_bars": int(len(df)),
            "short_by": max(0, int(need[tf]) - int(len(df))),
            "coverage_start": str(df["ts"].iat[0]),
            "coverage_end": str(df["ts"].iat[-1]),
        }
    short = [tf for tf, f in out["frames"].items() if f["short_by"] > 0]
    if short:
        out["warning"] = (f"Fewer bars than requested on {', '.join(short)}. "
                          f"Report covers the actual range, not the requested one.")
    return out


def load_any(symbol, tf, bars):
    """Old behaviour, kept for the mixed-source path only."""
    df, src = fetch_coindcx(symbol, tf, bars)
    if df is not None:
        return df, src
    return fetch_ccxt(symbol, tf, bars)
