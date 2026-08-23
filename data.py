"""
data.py — historical OHLCV loading with safe pagination and data validation.

Features
--------
* Historical pagination instead of silently stopping at 1000 candles.
* CoinDCX primary source with CCXT venue failover.
* Forming candles are removed only when genuinely incomplete.
* Duplicate, invalid and non-monotonic data is detected.
* All MTF frames are aligned to a common historical window.
* Requested evaluation bars and warmup bars are reported separately.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd


# =============================================================================
# VENUES
# =============================================================================

COINDCX_URL = "https://public.coindcx.com/market_data/candlesticks"

PAIR_MAP = {
    "BTC": "B-BTC_USDT",
    "ETH": "B-ETH_USDT",
    "DEXE": "B-DEXE_USDT",
    "BANK": "B-BANK_USDT",
}

# Preferred CCXT symbols.
# Actual exchange markets are checked dynamically because not every exchange
# uses the same futures/spot symbol format.
CCXT_MAP = {
    "BTC": "BTC/USDT:USDT",
    "ETH": "ETH/USDT:USDT",
    "DEXE": "DEXE/USDT:USDT",
    "BANK": "BANK/USDT:USDT",
}

FAILOVER = [
    "mexc",
    "bybit",
    "okx",
    "gateio",
]


# =============================================================================
# TIMEFRAMES
# =============================================================================

RESOLUTION = {
    "5m": "5",
    "15m": "15",
    "1h": "60",
}

TF_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


# =============================================================================
# PAGINATION / LIMITS
# =============================================================================

PAGE_LIMIT = 1000
MAX_PAGES = 60

DEFAULT_BACKTEST_BARS = 30000
MIN_BACKTEST_BARS = 500
MAX_BACKTEST_BARS = 60000


# =============================================================================
# WARMUP
# =============================================================================

WARMUP_BARS = {
    "5m": 600,
    "15m": 600,
    "1h": 600,
}


OHLC = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]

_ccxt_cache = {}


# =============================================================================
# HELPERS
# =============================================================================

def to_ns(series):
    """
    Convert timestamps safely to timezone-naive datetime64[ns].
    """

    out = pd.to_datetime(series, errors="coerce")

    try:
        if getattr(out.dtype, "tz", None) is not None:
            out = out.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass

    return out.astype("datetime64[ns]")


def _clean(df):
    """
    Normalize and clean OHLCV dataframe.
    """

    if df is None or df.empty:
        return pd.DataFrame(columns=["ts"] + OHLC)

    df = df.copy()

    df["ts"] = to_ns(df["ts"])

    df = df.dropna(subset=["ts"])

    for column in OHLC:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(subset=OHLC)

    df = (
        df.drop_duplicates("ts")
        .sort_values("ts")
        .reset_index(drop=True)
    )

    return df


# =============================================================================
# BAR CALCULATION
# =============================================================================

def required_bars(bars_5m):
    """
    Calculate how many candles each timeframe needs.

    bars_5m is the requested evaluation window.

    Example:
        10000 x 5m candles

    Equivalent wall-clock coverage:
        15m -> approximately 3334 candles
        1h  -> approximately 834 candles

    Warmup is added separately.
    """

    bars_5m = clamp_bars(bars_5m)

    span_seconds = bars_5m * TF_SECONDS["5m"]

    result = {}

    for timeframe, seconds in TF_SECONDS.items():

        evaluation_bars = int(
            np.ceil(span_seconds / seconds)
        )

        result[timeframe] = (
            evaluation_bars
            + WARMUP_BARS[timeframe]
        )

    return result


def clamp_bars(
    value,
    default=DEFAULT_BACKTEST_BARS,
):
    """
    Clamp user requested bars to safe limits.
    """

    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return max(
        MIN_BACKTEST_BARS,
        min(MAX_BACKTEST_BARS, value),
    )


# =============================================================================
# COINDCX PAGE FETCH
# =============================================================================

def _page_coindcx(
    symbol,
    timeframe,
    end_ts,
    span,
):
    """
    Fetch one historical page from CoinDCX.

    end_ts and span are Unix seconds.
    """

    import requests

    pair = PAIR_MAP.get(symbol)
    resolution = RESOLUTION.get(timeframe)

    if not pair or not resolution:
        return None

    response = requests.get(
        COINDCX_URL,
        timeout=25,
        params={
            "pair": pair,
            "from": int(end_ts - span),
            "to": int(end_ts),
            "resolution": resolution,
            "pcode": "f",
        },
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):
        candles = data.get("data", data)
    else:
        candles = data

    if not candles:
        return None

    rows = []

    for candle in candles:

        ts = candle.get(
            "time",
            candle.get("t"),
        )

        open_price = candle.get(
            "open",
            candle.get("o"),
        )

        high_price = candle.get(
            "high",
            candle.get("h"),
        )

        low_price = candle.get(
            "low",
            candle.get("l"),
        )

        close_price = candle.get(
            "close",
            candle.get("c"),
        )

        volume = candle.get(
            "volume",
            candle.get("v", 0),
        )

        if None in (
            ts,
            open_price,
            high_price,
            low_price,
            close_price,
        ):
            continue

        rows.append([
            ts,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        ])

    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=["ts"] + OHLC,
    )

    first_timestamp = float(df["ts"].iloc[0])

    unit = (
        "ms"
        if first_timestamp > 10 ** 12
        else "s"
    )

    df["ts"] = pd.to_datetime(
        df["ts"],
        unit=unit,
        errors="coerce",
    )

    return _clean(df)


# =============================================================================
# CCXT PAGE FETCH
# =============================================================================

def _get_ccxt_exchange(venue):
    """
    Create and cache a CCXT exchange instance.
    """

    if venue in _ccxt_cache:
        return _ccxt_cache[venue]

    import ccxt

    exchange_class = getattr(
        ccxt,
        venue,
    )

    exchange = exchange_class({
        "enableRateLimit": True,
    })

    exchange.load_markets()

    _ccxt_cache[venue] = exchange

    return exchange


def _resolve_ccxt_symbol(
    exchange,
    symbol,
):
    """
    Resolve the requested symbol against actual exchange markets.

    Different exchanges may expose:
        BTC/USDT
        BTC/USDT:USDT
        BTC-USDT-SWAP
    etc.

    We only return a market that actually exists.
    """

    preferred = CCXT_MAP.get(symbol)

    candidates = [
        preferred,
        f"{symbol}/USDT",
        f"{symbol}/USDT:USDT",
    ]

    for candidate in candidates:

        if (
            candidate
            and candidate in exchange.markets
        ):
            return candidate

    # Last fallback:
    # search markets by base/quote.

    for market_symbol, market in exchange.markets.items():

        base = market.get("base")
        quote = market.get("quote")

        if (
            base == symbol
            and quote == "USDT"
            and market.get("active", True)
        ):
            return market_symbol

    return None


def _page_ccxt(
    symbol,
    timeframe,
    since_ms,
    venue,
):
    """
    Fetch one page through CCXT.
    """

    try:
        exchange = _get_ccxt_exchange(venue)
    except Exception:
        return None

    market_symbol = _resolve_ccxt_symbol(
        exchange,
        symbol,
    )

    if market_symbol is None:
        return None

    try:

        rows = exchange.fetch_ohlcv(
            market_symbol,
            timeframe=timeframe,
            since=int(since_ms),
            limit=PAGE_LIMIT,
        )

    except Exception:
        return None

    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=["ts"] + OHLC,
    )

    df["ts"] = pd.to_datetime(
        df["ts"],
        unit="ms",
        errors="coerce",
    )

    return _clean(df)


# =============================================================================
# HISTORICAL PAGINATION
# =============================================================================

def fetch_ohlcv_history(
    venue,
    symbol,
    timeframe,
    target_bars,
    since=None,
    now=None,
):
    """
    Fetch historical OHLCV with backwards pagination.

    The loop continues until:

    * target_bars is collected
    * MAX_PAGES is reached
    * the venue stops returning older data
    * an optional `since` boundary is reached

    Returns:
        (dataframe, metadata)
    """

    seconds = TF_SECONDS.get(timeframe)

    if seconds is None:
        return None, {
            "error": (
                f"unsupported timeframe: "
                f"{timeframe}"
            )
        }

    try:
        target_bars = int(target_bars)
    except (TypeError, ValueError):
        return None, {
            "error": "invalid target_bars"
        }

    now_ts = int(
        now
        if now is not None
        else time.time()
    )

    span = seconds * PAGE_LIMIT

    frames = []

    pages = 0

    end_ts = now_ts

    seen_oldest = None

    stopped_reason = None

    while pages < MAX_PAGES:

        pages += 1

        try:

            if venue == "coindcx":

                chunk = _page_coindcx(
                    symbol=symbol,
                    timeframe=timeframe,
                    end_ts=end_ts,
                    span=span,
                )

            else:

                # CCXT fetches forward from `since`.
                # Request a page beginning one PAGE_LIMIT window
                # before the current backwards boundary.

                since_ts = end_ts - span

                chunk = _page_ccxt(
                    symbol=symbol,
                    timeframe=timeframe,
                    since_ms=int(
                        since_ts * 1000
                    ),
                    venue=venue,
                )

        except Exception as exc:

            stopped_reason = (
                f"request error: {type(exc).__name__}"
            )

            break

        if chunk is None or chunk.empty:

            stopped_reason = (
                "venue returned no data"
            )

            break

        chunk = _clean(chunk)

        if chunk.empty:

            stopped_reason = (
                "page contained no valid candles"
            )

            break

        oldest = chunk["ts"].iat[0]

        oldest_ts = int(
            oldest.timestamp()
        )

        # Detect repeated pages.
        # Without this a broken venue could return the same page forever.

        if (
            seen_oldest is not None
            and oldest_ts >= seen_oldest
        ):

            stopped_reason = (
                "venue repeated the same page"
            )

            break

        seen_oldest = oldest_ts

        frames.append(chunk)

        combined = _clean(
            pd.concat(
                frames,
                ignore_index=True,
            )
        )

        if len(combined) >= target_bars:

            stopped_reason = (
                "target reached"
            )

            break

        if (
            since is not None
            and oldest_ts <= int(since)
        ):

            stopped_reason = (
                "since boundary reached"
            )

            break

        # Move the next request backwards.

        end_ts = oldest_ts - 1

        # Small rate-limit friendly delay.

        time.sleep(0.2)

    if not frames:

        return None, {
            "error": "no data",
            "pages_fetched": pages,
            "stopped_reason": stopped_reason,
        }

    df = _clean(
        pd.concat(
            frames,
            ignore_index=True,
        )
    )

    # Keep the newest target bars.

    df = (
        df.tail(target_bars)
        .reset_index(drop=True)
    )

    actual_bars = int(len(df))

    return df, {
        "requested_bars": int(target_bars),
        "actual_bars": actual_bars,
        "short_by": max(
            0,
            int(target_bars) - actual_bars,
        ),
        "source": venue,
        "symbol": symbol,
        "timeframe": timeframe,
        "coverage_start": (
            str(df["ts"].iat[0])
            if not df.empty
            else None
        ),
        "coverage_end": (
            str(df["ts"].iat[-1])
            if not df.empty
            else None
        ),
        "pages_fetched": pages,
        "stopped_reason": stopped_reason,
    }


# =============================================================================
# FORMING CANDLE DETECTION
# =============================================================================

def drop_forming(
    df,
    timeframe,
    now=None,
):
    """
    Remove ONLY the final candle if it is still forming.

    Historical datasets are not blindly truncated.
    """

    if df is None or df.empty:
        return df, False

    seconds = TF_SECONDS.get(timeframe)

    if seconds is None:
        return df, False

    now_ts = float(
        now
        if now is not None
        else time.time()
    )

    last_open = (
        df["ts"]
        .iat[-1]
        .timestamp()
    )

    candle_close = (
        last_open
        + seconds
    )

    if candle_close > now_ts:

        return (
            df.iloc[:-1]
            .reset_index(drop=True),
            True,
        )

    return df, False


# =============================================================================
# DATA VALIDATION
# =============================================================================

def validate_ohlcv(
    df,
    timeframe,
):
    """
    Return a list of data quality warnings.
    """

    warnings = []

    if df is None or df.empty:
        return ["no data"]

    if df["ts"].duplicated().any():

        warnings.append(
            f"{timeframe}: duplicate timestamps"
        )

    if not df["ts"].is_monotonic_increasing:

        warnings.append(
            f"{timeframe}: timestamps not chronological"
        )

    if df[OHLC].isna().any().any():

        warnings.append(
            f"{timeframe}: missing OHLCV values"
        )

    price_columns = [
        "open",
        "high",
        "low",
        "close",
    ]

    if (
        df[price_columns] <= 0
    ).any().any():

        warnings.append(
            f"{timeframe}: non-positive prices"
        )

    impossible = df[
        (
            df["high"]
            < df["low"]
        )
        |
        (
            df["high"]
            < df[
                ["open", "close"]
            ].max(axis=1)
        )
        |
        (
            df["low"]
            > df[
                ["open", "close"]
            ].min(axis=1)
        )
    ]

    if len(impossible):

        warnings.append(
            f"{timeframe}: "
            f"{len(impossible)} impossible OHLC candles"
        )

    expected = pd.Timedelta(
        seconds=TF_SECONDS[timeframe]
    )

    gaps = (
        df["ts"]
        .diff()
        .dropna()
    )

    large_gaps = gaps[
        gaps > expected * 3
    ]

    if len(large_gaps):

        warnings.append(
            f"{timeframe}: "
            f"{len(large_gaps)} large gaps, "
            f"largest={large_gaps.max()}"
        )

    odd_gaps = gaps[
        (gaps != expected)
        &
        (gaps <= expected * 3)
    ]

    if (
        len(gaps) > 0
        and len(odd_gaps)
        > len(gaps) * 0.02
    ):

        warnings.append(
            f"{timeframe}: "
            f"{len(odd_gaps)} unexpected candle intervals"
        )

    return warnings


# =============================================================================
# COMMON MTF WINDOW
# =============================================================================

def align_common_window(
    frames,
    preserve_live_latest=False,
):
    """
    Align MTF datasets to a shared historical start.

    BACKTEST:
        Keep the original strict common historical window.
        Every timeframe is clipped to common_start/common_end.

    LIVE:
        Keep common_start for sufficient history, but do NOT clip
        the latest closed candle of 5m/15m/1h to the slowest
        timeframe. Each timeframe keeps its own latest closed data.

    This is important because 1h naturally closes less frequently
    than 5m/15m. Using min(last_ts) in LIVE would unnecessarily
    throw away fresh lower-timeframe candles.
    """
    if not frames:
        return {}, None, None

    for df in frames.values():
        if df is None or df.empty:
            return {}, None, None

    common_start = max(
        df["ts"].iat[0]
        for df in frames.values()
    )

    common_end = min(
        df["ts"].iat[-1]
        for df in frames.values()
    )

    result = {}

    for timeframe, df in frames.items():

        if preserve_live_latest:
            # LIVE:
            # Keep every timeframe up to its own latest CLOSED candle.
            # drop_forming() has already removed any still-forming candle.
            result[timeframe] = (
                df[
                    df["ts"] >= common_start
                ]
                .reset_index(drop=True)
            )

        else:
            # BACKTEST:
            # Preserve the original strict common-window behavior.
            result[timeframe] = (
                df[
                    (df["ts"] >= common_start)
                    &
                    (df["ts"] <= common_end)
                ]
                .reset_index(drop=True)
            )

    return (
        result,
        common_start,
        common_end,
    )

# =============================================================================
# LOAD MULTI TIMEFRAME DATA
# =============================================================================

def load_mtf(
    symbol,
    bars_5m,
    allow_mixed=False,
    now=None,
    live=False,
):
    """
    Load 5m, 15m and 1h historical data.

    Preference:
        1. CoinDCX for all frames
        2. One CCXT failover venue for all frames
        3. Mixed sources only if explicitly allowed
    """

    symbol = str(symbol).upper()

    requested_evaluation_bars = clamp_bars(
        bars_5m
    )

    need = required_bars(
        requested_evaluation_bars
    )

    venues = (
        ["coindcx"]
        + FAILOVER
    )

    warnings = []

    venue_failures = {}

    # -------------------------------------------------------------------------
    # FIRST TRY: ONE VENUE FOR ALL TIMEFRAMES
    # -------------------------------------------------------------------------

    for venue in venues:

        frames = {}

        metas = {}

        venue_ok = True

        failure_reason = None

        for timeframe in (
            "5m",
            "15m",
            "1h",
        ):

            df, meta = fetch_ohlcv_history(
                venue=venue,
                symbol=symbol,
                timeframe=timeframe,
                target_bars=need[timeframe],
                now=now,
            )

            if (
                df is None
                or len(df) < 300
            ):

                venue_ok = False

                failure_reason = (
                    f"{timeframe}: "
                    f"{meta.get('error', 'too few bars')}"
                )

                break

            df, dropped = drop_forming(
                df,
                timeframe,
                now=now,
            )

            meta[
                "forming_candle_dropped"
            ] = dropped

            meta["actual_bars"] = len(df)

            frames[timeframe] = df

            metas[timeframe] = meta

        if venue_ok:

            return _finish(
                symbol=symbol,
                frames=frames,
                metas=metas,
                source=venue,
                need=need,
                mixed=False,
                warnings=warnings,
                requested_evaluation_bars=requested_evaluation_bars,
                preserve_live_latest=live,
            )

        venue_failures[venue] = failure_reason


    # -------------------------------------------------------------------------
    # NO MIXED SOURCES
    # -------------------------------------------------------------------------

    if not allow_mixed:

        return None, {
            "source": None,
            "mixed": False,
            "error": (
                "no single venue served "
                "all required timeframes"
            ),
            "venue_failures": venue_failures,
        }


    # -------------------------------------------------------------------------
    # MIXED SOURCE FALLBACK
    # -------------------------------------------------------------------------

    frames = {}

    metas = {}

    sources = {}

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        found = False

        for venue in venues:

            df, meta = fetch_ohlcv_history(
                venue=venue,
                symbol=symbol,
                timeframe=timeframe,
                target_bars=need[timeframe],
                now=now,
            )

            if (
                df is None
                or len(df) < 300
            ):
                continue

            df, dropped = drop_forming(
                df,
                timeframe,
                now=now,
            )

            meta[
                "forming_candle_dropped"
            ] = dropped

            meta["actual_bars"] = len(df)

            frames[timeframe] = df

            metas[timeframe] = meta

            sources[timeframe] = venue

            found = True

            break

        if not found:

            return None, {
                "source": None,
                "mixed": True,
                "error": (
                    f"no venue served "
                    f"{timeframe}"
                ),
                "venue_failures": venue_failures,
            }

    warnings.append(
        "MIXED SOURCE WARNING: "
        "different timeframes came from different venues. "
        "Treat this result as indicative only."
    )

    result = _finish(
        symbol=symbol,
        frames=frames,
        metas=metas,
        source="MIXED",
        need=need,
        mixed=True,
        warnings=warnings,
        requested_evaluation_bars=requested_evaluation_bars,
        preserve_live_latest=live,
    )

    if result[1] is not None:

        result[1]["sources"] = sources

    return result


# =============================================================================
# FINAL DATA QUALITY REPORT
# =============================================================================

def _finish(
    symbol,
    frames,
    metas,
    source,
    need,
    mixed,
    warnings,
    requested_evaluation_bars,
    preserve_live_latest=False,
):
    """
    Validate, align and produce final data quality metadata.
    """

    warnings = list(warnings)

    # Validate before alignment.

    for timeframe, df in frames.items():

        warnings.extend(
            validate_ohlcv(
                df,
                timeframe,
            )
        )

    frames, common_start, common_end = (
        align_common_window(frames)
    )

    if (
        common_start is None
        or common_end is None
    ):

        return None, {
            "source": source,
            "mixed": bool(mixed),
            "symbol": symbol,
            "error": (
                "no common historical window"
            ),
            "warnings": warnings,
        }

    for timeframe, df in frames.items():

        if len(df) < 300:

            warnings.append(
                f"{timeframe}: only "
                f"{len(df)} bars inside "
                f"the common window"
            )

    # Warn honestly when requested 5m history could not be collected.

    five_meta = metas["5m"]

    if five_meta.get("short_by", 0) > 0:

        warnings.append(
            "HISTORICAL SHORTFALL: "
            f"requested "
            f"{five_meta['requested_bars']} "
            f"5m bars including warmup, "
            f"received "
            f"{five_meta['actual_bars']}."
        )

    coverage_days = (
        common_end - common_start
    ).total_seconds() / 86400.0

    data_quality = {

        "source": source,

        "mixed": bool(mixed),

        "symbol": symbol,


        # User request.

        "requested_evaluation_bars_5m":
            int(requested_evaluation_bars),


        # Internal request including warmup.

        "requested_with_warmup_5m":
            int(need["5m"]),


        "requested_with_warmup_15m":
            int(need["15m"]),


        "requested_with_warmup_1h":
            int(need["1h"]),


        # Actual usable data after common-window alignment.

        "actual_bars_5m":
            int(len(frames["5m"])),

        "actual_bars_15m":
            int(len(frames["15m"])),

        "actual_bars_1h":
            int(len(frames["1h"])),


        "usable_5m_bars":
            int(len(frames["5m"])),

        "usable_15m_bars":
            int(len(frames["15m"])),

        "usable_1h_bars":
            int(len(frames["1h"])),


        # Common historical window.

        "common_start":
            str(common_start),

        "common_end":
            str(common_end),

        "coverage_days":
            round(
                coverage_days,
                2,
            ),


        # Raw source coverage.

        "coverage_start":
            metas["5m"].get(
                "coverage_start"
            ),

        "coverage_end":
            metas["5m"].get(
                "coverage_end"
            ),


        # Pagination proof.

        "pages_fetched": {
            timeframe:
            meta.get(
                "pages_fetched",
                0,
            )
            for timeframe, meta
            in metas.items()
        },


        # Why pagination stopped.

        "pagination_stop_reason": {
            timeframe:
            meta.get(
                "stopped_reason"
            )
            for timeframe, meta
            in metas.items()
        },


        # Forming candle status.

        "forming_candle_dropped": {
            timeframe:
            meta.get(
                "forming_candle_dropped",
                False,
            )
            for timeframe, meta
            in metas.items()
        },


        # Full raw metadata.

        "per_timeframe":
            metas,


        "warnings":
            warnings,
    }

    return frames, data_quality
