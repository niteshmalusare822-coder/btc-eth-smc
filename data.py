"""
data.py — historical OHLCV loading with pagination.

WHAT WAS WRONG BEFORE
---------------------
There was no pagination anywhere. The ccxt path was hard-capped at
`limit=min(bars, 1000)` and the CoinDCX path issued a single from/to request.
Asking for 10,000 candles returned about 1,000 and nothing said so, which is
why every report was being judged on roughly three days of 5m data.

WHAT THIS DOES NOW
------------------
* Pages backwards until the target is met or the venue runs out.
* Reports requested vs actual, page count and coverage for every timeframe.
* Removes the final candle ONLY when it is genuinely still forming.
* Keeps all three timeframes on one venue unless mixed source is opted into.
* Trims every frame to the window all three actually share.
* Validates for duplicates, gaps, bad prices and non-monotonic timestamps.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

COINDCX_URL = "https://public.coindcx.com/market_data/candlesticks"

PAIR_MAP = {"BTC": "B-BTC_USDT", "ETH": "B-ETH_USDT",
            "DEXE": "B-DEXE_USDT", "BANK": "B-BANK_USDT"}
CCXT_MAP = {"BTC": "BTC/USDT:USDT", "ETH": "ETH/USDT:USDT",
            "DEXE": "DEXE/USDT:USDT", "BANK": "BANK/USDT:USDT"}

RESOLUTION = {"5m": "5", "15m": "15", "1h": "60"}
TF_SECONDS = {"5m": 300, "15m": 900, "1h": 3600}
FAILOVER = ["mexc", "bybit", "okx", "gateio"]

PAGE_LIMIT = 1000          # candles per request most venues will serve
MAX_PAGES = 60             # hard stop so a misbehaving API cannot loop forever

# warmup each frame needs on top of the evaluation window: swings, ATR, and the
# 500-bar rolling calibration window all need history before the first signal
WARMUP_BARS = {"5m": 600, "15m": 600, "1h": 600}

_ccxt_cache = {}
OHLC = ["open", "high", "low", "close", "volume"]


def to_ns(series):
    out = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(out.dtype, "tz", None) is not None:
            out = out.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return out.astype("datetime64[ns]")


def _clean(df):
    df = df.copy()
    df["ts"] = to_ns(df["ts"])
    df = df.dropna(subset=["ts"])
    df = df.astype({c: float for c in OHLC})
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


# ---------------------------------------------------------------------------
# REQUIRED BARS PER TIMEFRAME  (FIX 6)
# ---------------------------------------------------------------------------
def required_bars(bars_5m):
    """Bars each frame needs to cover the same wall-clock window, plus warmup.

    Requesting the same count for every timeframe was wrong in both directions:
    4000 1h candles is five months of history nobody asked for, while 4000/12
    with no warmup leaves the 1H bias blind for its first 600 bars.
    """
    span_min = bars_5m * 5
    out = {}
    for tf, secs in TF_SECONDS.items():
        cover = int(np.ceil(span_min / (secs / 60)))
        out[tf] = cover + WARMUP_BARS[tf]
    return out


# ---------------------------------------------------------------------------
# PAGINATED FETCH  (FIX 1)
# ---------------------------------------------------------------------------
def _page_coindcx(symbol, tf, end_ts, secs, span):
    import requests
    pair, res = PAIR_MAP.get(symbol), RESOLUTION.get(tf)
    if not (pair and res):
        return None
    r = requests.get(COINDCX_URL, timeout=25, params={
        "pair": pair, "from": int(end_ts - span), "to": int(end_ts),
        "resolution": res, "pcode": "f"})
    r.raise_for_status()
    data = r.json()
    candles = data.get("data", data) if isinstance(data, dict) else data
    if not candles:
        return None
    rows = []
    for c in candles:
        ts = c.get("time", c.get("t"))
        o, h = c.get("open", c.get("o")), c.get("high", c.get("h"))
        lo, cl = c.get("low", c.get("l")), c.get("close", c.get("c"))
        v = c.get("volume", c.get("v", 0))
        if None in (ts, o, h, lo, cl):
            continue
        rows.append([ts, o, h, lo, cl, v])
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts"] + OHLC)
    unit = "ms" if float(df["ts"].iloc[0]) > 10 ** 12 else "s"
    df["ts"] = pd.to_datetime(df["ts"], unit=unit)
    return _clean(df)


def _page_ccxt(symbol, tf, since_ms, venue):
    try:
        import ccxt
    except ImportError:
        return None
    sym = CCXT_MAP.get(symbol)
    if not sym:
        return None
    if venue not in _ccxt_cache:
        _ccxt_cache[venue] = getattr(ccxt, venue)({"enableRateLimit": True})
    o = _ccxt_cache[venue].fetch_ohlcv(sym, tf, since=since_ms, limit=PAGE_LIMIT)
    if not o:
        return None
    df = pd.DataFrame(o, columns=["ts"] + OHLC)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return _clean(df)


def fetch_ohlcv_history(venue, symbol, timeframe, target_bars, since=None,
                        now=None):
    """Page until target_bars are collected or the venue stops producing new
    candles. Returns (df, meta). meta never claims more than was received.

    Pages walk BACKWARDS from the most recent candle, because the thing being
    extended is history, not the present. Each page ends one second before the
    oldest candle already held, so pages cannot overlap into an infinite loop.
    """
    secs = TF_SECONDS.get(timeframe)
    if not secs:
        return None, {"error": f"unsupported timeframe {timeframe}"}

    now = int(now if now is not None else time.time())
    span = secs * PAGE_LIMIT
    frames, pages, end_ts = [], 0, now
    seen_oldest = None

    while pages < MAX_PAGES:
        pages += 1
        try:
            if venue == "coindcx":
                chunk = _page_coindcx(symbol, timeframe, end_ts, secs, span)
            else:
                chunk = _page_ccxt(symbol, timeframe,
                                   int((end_ts - span) * 1000), venue)
        except Exception:
            break
        if chunk is None or chunk.empty:
            break

        frames.append(chunk)
        oldest = chunk["ts"].iat[0]

        # no progress: the venue is replaying the same window, so stop
        if seen_oldest is not None and oldest >= seen_oldest:
            break
        seen_oldest = oldest

        have = pd.concat(frames).drop_duplicates("ts")
        if len(have) >= target_bars:
            break
        end_ts = int(oldest.timestamp()) - 1
        if since is not None and int(oldest.timestamp()) <= int(since):
            break
        time.sleep(0.2)

    if not frames:
        return None, {"error": "no data", "pages_fetched": pages}

    df = _clean(pd.concat(frames, ignore_index=True)).tail(target_bars)
    df = df.reset_index(drop=True)
    return df, {
        "requested_bars": int(target_bars),
        "actual_bars": int(len(df)),
        "short_by": max(0, int(target_bars) - int(len(df))),
        "source": venue, "symbol": symbol, "timeframe": timeframe,
        "coverage_start": str(df["ts"].iat[0]),
        "coverage_end": str(df["ts"].iat[-1]),
        "pages_fetched": pages,
    }


# ---------------------------------------------------------------------------
# FORMING CANDLE  (FIX 4)
# ---------------------------------------------------------------------------
def drop_forming(df, timeframe, now=None):
    """Remove the last candle ONLY if its period has not finished.

    Dropping it unconditionally threw away a perfectly good closed candle on
    historical data, and combined with a second skip downstream the live
    scanner was reading a bar that was two periods old.
    """
    if df is None or df.empty:
        return df, False
    secs = TF_SECONDS[timeframe]
    now_ts = float(now if now is not None else time.time())
    last_open = df["ts"].iat[-1].timestamp()
    if last_open + secs > now_ts:
        return df.iloc[:-1].reset_index(drop=True), True
    return df, False


# ---------------------------------------------------------------------------
# VALIDATION  (FIX 12)
# ---------------------------------------------------------------------------
def validate_ohlcv(df, timeframe):
    w = []
    if df is None or df.empty:
        return ["no data"]
    if df["ts"].duplicated().any():
        w.append(f"{timeframe}: duplicate timestamps")
    if not df["ts"].is_monotonic_increasing:
        w.append(f"{timeframe}: timestamps not chronological")
    if df[OHLC].isna().any().any():
        w.append(f"{timeframe}: missing OHLCV values")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        w.append(f"{timeframe}: non-positive prices")
    bad = df[(df["high"] < df["low"]) |
             (df["high"] < df[["open", "close"]].max(axis=1)) |
             (df["low"] > df[["open", "close"]].min(axis=1))]
    if len(bad):
        w.append(f"{timeframe}: {len(bad)} candles with impossible OHLC ordering")

    expected = pd.Timedelta(seconds=TF_SECONDS[timeframe])
    gaps = df["ts"].diff().dropna()
    big = gaps[gaps > expected * 3]
    if len(big):
        w.append(f"{timeframe}: {len(big)} gaps, largest {big.max()}")
    odd = gaps[(gaps != expected) & (gaps <= expected * 3)]
    if len(odd) > len(gaps) * 0.02:
        w.append(f"{timeframe}: {len(odd)} bars with unexpected duration")
    return w


# ---------------------------------------------------------------------------
# COMMON WINDOW  (FIX 3)
# ---------------------------------------------------------------------------
def align_common_window(frames):
    """Trim every frame to the period all three actually cover.

    If 1h history only reaches back a month while 5m reaches back four, the
    backtest must evaluate one month. Anything earlier would be running the
    entry logic with no higher-timeframe bias behind it.
    """
    start = max(f["ts"].iat[0] for f in frames.values())
    end = min(f["ts"].iat[-1] for f in frames.values())
    out = {}
    for tf, f in frames.items():
        out[tf] = f[(f["ts"] >= start) & (f["ts"] <= end)].reset_index(drop=True)
    return out, start, end


# ---------------------------------------------------------------------------
# MTF LOAD  (FIX 2, 5, 13)
# ---------------------------------------------------------------------------
DEFAULT_BACKTEST_BARS = 10000
MIN_BACKTEST_BARS = 500
MAX_BACKTEST_BARS = 30000


def clamp_bars(n, default=DEFAULT_BACKTEST_BARS):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return default
    return max(MIN_BACKTEST_BARS, min(MAX_BACKTEST_BARS, n))


def load_mtf(symbol, bars_5m, allow_mixed=False, now=None):
    """All three frames from ONE venue, paginated, aligned, validated.

    Returns (frames, data_quality). frames is None when nothing usable loaded.
    """
    need = required_bars(bars_5m)
    venues = ["coindcx"] + FAILOVER
    warnings, per_venue = [], {}

    for venue in venues:
        frames, metas, ok = {}, {}, True
        for tf in ("5m", "15m", "1h"):
            df, meta = fetch_ohlcv_history(venue, symbol, tf, need[tf], now=now)
            if df is None or len(df) < 300:
                ok = False
                per_venue[venue] = f"{tf}: {meta.get('error', 'too few bars')}"
                break
            df, dropped = drop_forming(df, tf, now=now)
            meta["forming_candle_dropped"] = dropped
            meta["actual_bars"] = len(df)
            frames[tf], metas[tf] = df, meta
        if ok:
            return _finish(symbol, frames, metas, venue, need, False, warnings)

    if not allow_mixed:
        return None, {"source": None, "mixed": False,
                      "error": "no single venue served all three timeframes",
                      "venue_failures": per_venue}

    frames, metas, sources = {}, {}, {}
    for tf in ("5m", "15m", "1h"):
        got = False
        for venue in venues:
            df, meta = fetch_ohlcv_history(venue, symbol, tf, need[tf], now=now)
            if df is not None and len(df) >= 300:
                df, dropped = drop_forming(df, tf, now=now)
                meta["forming_candle_dropped"] = dropped
                meta["actual_bars"] = len(df)
                frames[tf], metas[tf], sources[tf] = df, meta, venue
                got = True
                break
        if not got:
            return None, {"source": None, "mixed": True,
                          "error": f"no venue served {tf}"}
    warnings.append("MIXED SOURCE: timeframes came from different venues, so "
                    "bias and entries are computed on different prints. "
                    "Treat this report as indicative only.")
    out = _finish(symbol, frames, metas, "MIXED", need, True, warnings)
    out[1]["sources"] = sources
    return out


def _finish(symbol, frames, metas, source, need, mixed, warnings):
    for tf, df in frames.items():
        warnings.extend(validate_ohlcv(df, tf))

    frames, common_start, common_end = align_common_window(frames)

    for tf, df in frames.items():
        if len(df) < 300:
            warnings.append(f"{tf}: only {len(df)} bars inside the common window")

    f5 = metas["5m"]
    if f5["short_by"] > 0:
        warnings.append(
            f"WARNING: requested {f5['requested_bars']} 5m bars, "
            f"only {f5['actual_bars']} available")

    days = (common_end - common_start).total_seconds() / 86400.0
    dq = {
        "source": source, "mixed": bool(mixed), "symbol": symbol,
        "requested_bars_5m": need["5m"],
        "actual_bars_5m": len(frames["5m"]),
        "actual_bars_15m": len(frames["15m"]),
        "actual_bars_1h": len(frames["1h"]),
        "coverage_start": str(metas["5m"]["coverage_start"]),
        "coverage_end": str(metas["5m"]["coverage_end"]),
        "common_start": str(common_start),
        "common_end": str(common_end),
        "coverage_days": round(days, 1),
        "usable_5m_bars": len(frames["5m"]),
        "usable_15m_bars": len(frames["15m"]),
        "usable_1h_bars": len(frames["1h"]),
        "pages_fetched": {tf: m["pages_fetched"] for tf, m in metas.items()},
        "forming_candle_dropped": {tf: m.get("forming_candle_dropped")
                                   for tf, m in metas.items()},
        "per_timeframe": metas,
        "warnings": warnings,
    }
    return frames, dq
