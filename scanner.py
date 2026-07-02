"""
SCALPING BOT — Multi-Factor Engine + Liquidity Concepts Combo
================================================================
Base engine (EMA/RSI/ADX/Structure/Divergence/VolumeProfile/Regime) +
Liquidity Concepts from the Mind Math Money "Liquidity Concepts" course:

  - BSL / SSL (Buy/Sell Side Liquidity)  -> external liquidity, rolling
    high/low levels + "equal highs/lows" density (how crowded the pool is)
  - Liquidity Sweep                       -> price wicks through a level
    and closes back inside it (stop-hunt)
  - Fair Value Gap (FVG) / Liquidity Void -> internal liquidity, 3-candle
    imbalance zones that act as magnets / reaction zones
  - Inducement                            -> a minor swing wick-trap that
    closes back inside range (proxy for "fake move before the real one")
  - Internal <-> External liquidity cycle -> feeds into HTF bias & scoring

RESTRICTED TO SCALPING TIMEFRAMES ONLY: 1m (entry), 5m (confirm), 15m (HTF bias)
The old 1h HTF leg has been removed per scalper requirement.

Everything is wired through TWO parallel paths that use the SAME weights/logic:
  1. LIVE path   -> analyze_timeframe() / calc_liquidity_score() (scalar, per-symbol)
  2. BACKTEST path -> vectorized equivalents (_liquidity_score_vectorized etc.)
so backtest results should be representative of what the live signal does.

⚠️ Educational / research tool. Not financial advice. Always forward-test
   on paper before risking real capital, and validate profit_factor /
   expectancy_pct from run_backtest_full() and run_factor_backtest()
   before trusting any signal.
"""

import ccxt
import requests
import pandas as pd
import numpy as np
import time as _t

# Map our symbol format -> CoinDCX futures pair format
COINDCX_PAIR_MAP = {
    "BTC/USDT:USDT": "B-BTC_USDT",
    "ETH/USDT:USDT": "B-ETH_USDT",
}

# CoinDCX resolution strings per timeframe (only 1m/5m/15m are actually used now)
COINDCX_RESOLUTION_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
}

# ── Config — SCALPER MODE (1m / 5m / 15m only) ───────────────────────────
CONFIG = {
    'EMA_FAST': 5,
    'EMA_SLOW': 20,
    'RSI_PERIOD': 7,
    'ATR_PERIOD': 14,
    'ADX_PERIOD': 14,
    'ADX_MIN': 18,
    'SWING_LOOKBACK': 3,
    'LIQUIDITY_SWEEP_LOOKBACK': 20,
    'VOLUME_PROFILE_LOOKBACK': 100,
    'VOLUME_PROFILE_BINS': 24,
    'SCORE_THRESHOLD': 6.0,        # raised because liquidity factors add extra points
    'SCORE_GAP_MIN': 4.0,
    'FEE_PCT': 0.04,
    'ATR_COMPRESSION_RATIO': 0.7,
    'ATR_MA_PERIOD': 50,
    'CHOPPINESS_PERIOD': 14,
    'CHOPPINESS_TREND_MAX': 61.8,
    'LIMIT': 300,
    'TP_ATR_MULT': 2.0,
    'SL_ATR_MULT': 1.0,
    'RSI_OVERBOUGHT': 70,
    'RSI_OVERSOLD': 30,
    'BACKTEST_CANDLES': 6000,
    'BACKTEST_OUTCOME_WINDOW': 20,

    # ── Liquidity Concepts params (NEW) ──────────────────────────────────
    'FVG_MIN_GAP_PCT': 0.02,          # min gap size (% of price) to count as a real FVG
    'BSL_SSL_LOOKBACK': 20,           # rolling window for external liquidity (BSL/SSL) levels
    'EQUAL_LEVEL_TOLERANCE_PCT': 0.05,  # how close highs/lows must be to count as "equal"
    'INDUCEMENT_MINOR_LOOKBACK': 2,   # small swing window used to detect inducement wick-traps
    'FVG_PROXIMITY_PCT': 0.3,         # how close price must be to an unfilled FVG to score it
    'EQUAL_LEVEL_MIN_COUNT': 3,       # min touches to call a pool "crowded" (stronger sweep target)
}

EXCHANGE_IDS = ['mexc', 'bybit', 'okx', 'gateio']

_exchanges = []
for ex_id in EXCHANGE_IDS:
    try:
        klass = getattr(ccxt, ex_id)
        _exchanges.append((ex_id, klass({'enableRateLimit': True, 'timeout': 15000})))
    except Exception:
        continue


def fetch_coindcx_futures(ticker, timeframe, limit):
    pair = COINDCX_PAIR_MAP.get(ticker)
    resolution = COINDCX_RESOLUTION_MAP.get(timeframe)
    if pair is None or resolution is None:
        return None, None

    tf_seconds = {"1m": 60, "5m": 300, "15m": 900}[timeframe]
    to_time = int(_t.time())
    from_time = to_time - (tf_seconds * (limit + 5))

    url = "https://public.coindcx.com/market_data/candlesticks"
    params = {
        "pair": pair,
        "from": from_time,
        "to": to_time,
        "resolution": resolution,
        "pcode": "f",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        candles = data.get("data", data) if isinstance(data, dict) else data
        if not candles or len(candles) < 50:
            return None, None

        rows = []
        for c in candles:
            ts = c.get("time", c.get("t"))
            o = c.get("open", c.get("o"))
            h = c.get("high", c.get("h"))
            l = c.get("low", c.get("l"))
            cl = c.get("close", c.get("c"))
            v = c.get("volume", c.get("v", 0))
            if None in (ts, o, h, l, cl):
                continue
            rows.append([ts, o, h, l, cl, v])

        if len(rows) < 50:
            return None, None

        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        if df["timestamp"].iloc[0] > 10 ** 12:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("timestamp", inplace=True)
        df = df.astype(float).sort_index()
        return df.tail(limit), "coindcx"

    except Exception:
        return None, None


def fetch_ohlcv_failover(ticker, timeframe, limit):
    df, src = fetch_coindcx_futures(ticker, timeframe, limit)
    if df is not None:
        return df, src

    for ex_id, ex in _exchanges:
        try:
            ohlcv = ex.fetch_ohlcv(ticker, timeframe, limit=limit)
            if not ohlcv or len(ohlcv) < 50:
                continue
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df.astype(float), ex_id
        except Exception:
            continue
    return None, None


# ── Base Indicators ───────────────────────────────────────────────────────
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + (gain / (loss + 1e-10))))

def calc_atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm_adj = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm_adj = minus_dm.where(minus_dm > plus_dm, 0.0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean() + 1e-10
    plus_di = 100 * (plus_dm_adj.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm_adj.ewm(alpha=1 / period, adjust=False).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    return dx.ewm(alpha=1 / period, adjust=False).mean()

def calc_choppiness_index(df, period=14):
    atr_sum = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1).rolling(period).sum()
    high_roll = df["high"].rolling(period).max()
    low_roll = df["low"].rolling(period).min()
    denom = np.log10(period + 1e-10)
    return 100 * np.log10((atr_sum / (high_roll - low_roll + 1e-10)) + 1e-10) / denom

def calc_session_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tpv = tp * df["volume"]
    day = df.index.date
    cum_tpv = pd.Series(tpv.values, index=df.index).groupby(day).cumsum()
    cum_vol = df["volume"].groupby(day).cumsum()
    return cum_tpv / (cum_vol + 1e-10)

def calc_volume_profile(df, lookback=100, bins=24):
    data = df.tail(lookback)
    if len(data) < 5:
        return {"poc": None}
    price_min, price_max = data["low"].min(), data["high"].max()
    if price_max <= price_min:
        return {"poc": None}
    bin_edges = np.linspace(price_min, price_max, bins + 1)
    vol_per_bin = np.zeros(bins)
    tp = (data["high"] + data["low"] + data["close"]) / 3
    bin_idx = np.clip(np.searchsorted(bin_edges, tp.values) - 1, 0, bins - 1)
    for idx, vol in zip(bin_idx, data["volume"].values):
        vol_per_bin[idx] += vol
    poc_idx = int(np.argmax(vol_per_bin))
    poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
    return {"poc": round(poc_price, 4)}

def detect_market_regime(df):
    atr = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx = calc_adx(df, CONFIG['ADX_PERIOD'])
    current_atr = atr.iloc[-1]
    current_atr_ma = atr_ma.iloc[-1]
    current_ci = ci.iloc[-1]
    current_adx = adx.iloc[-1]
    atr_ratio = (current_atr / current_atr_ma) if current_atr_ma > 0 else 1.0
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy = current_ci > CONFIG['CHOPPINESS_TREND_MAX'] if not np.isnan(current_ci) else False
    is_trending = current_adx >= CONFIG['ADX_MIN'] if not np.isnan(current_adx) else False
    if is_compressed:
        regime = "COMPRESSION"
    elif is_choppy or not is_trending:
        regime = "RANGING"
    else:
        regime = "TRENDING"
    return {
        "regime": regime,
        "atr_ratio": round(atr_ratio, 3) if not np.isnan(atr_ratio) else None,
        "choppiness": round(current_ci, 2) if not np.isnan(current_ci) else None,
        "adx": round(current_adx, 2) if not np.isnan(current_adx) else None,
    }


# ── Structure / Patterns ───────────────────────────────────────────────────
def detect_structure_live_pro(df, lookback=3):
    df = df.copy()
    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    events, trends = [None] * n, [None] * n
    trend = None
    last_swing_high = last_swing_low = None
    for i in range(lookback * 2, n):
        lh = highs[i - 2 * lookback:i - lookback]
        rh = highs[i - lookback + 1:i + 1]
        ll = lows[i - 2 * lookback:i - lookback]
        rl = lows[i - lookback + 1:i + 1]
        if len(lh) == lookback and len(rh) == lookback:
            if highs[i - lookback] >= lh.max() and highs[i - lookback] >= rh.max():
                last_swing_high = highs[i - lookback]
            if lows[i - lookback] <= ll.min() and lows[i - lookback] <= rl.min():
                last_swing_low = lows[i - lookback]
        close = closes[i]
        if last_swing_high is not None and close > last_swing_high:
            events[i] = "BOS_BULL" if trend == "BULL" else "CHoCH_BULL"
            trend = "BULL"; last_swing_high = highs[i]
        elif last_swing_low is not None and close < last_swing_low:
            events[i] = "BOS_BEAR" if trend == "BEAR" else "CHoCH_BEAR"
            trend = "BEAR"; last_swing_low = lows[i]
        trends[i] = trend
    df["structure_event"] = events
    df["structure_trend"] = trends
    return df

def detect_candle_patterns_vectorized(df):
    df = df.copy()
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    b, tr = (c - o).abs(), h - l
    uw = h - np.maximum(o, c)
    lw = np.minimum(o, c) - l
    df["pat_sig"] = ""
    hammer = (tr > 0) & (lw >= 2 * b) & (uw <= 0.3 * b) & (b >= 0.1 * tr)
    star = (tr > 0) & (uw >= 2 * b) & (lw <= 0.3 * b) & (b >= 0.1 * tr)
    bull_eng = (pc < po) & (c > o) & (o < pc) & (c > po)
    bear_eng = (pc > po) & (c < o) & (o > pc) & (c < po)
    df.loc[hammer, "pat_sig"] = "BUY"
    df.loc[star, "pat_sig"] = "SELL"
    df.loc[bull_eng, "pat_sig"] = "BUY"
    df.loc[bear_eng, "pat_sig"] = "SELL"
    return df

def detect_pro_divergence_vectorized(df, lookback=20):
    df = df.copy()
    df["divergence"] = ""
    roll_min_c = df["close"].shift(1).rolling(lookback).min()
    roll_min_r = df["rsi"].shift(1).rolling(lookback).min()
    roll_max_c = df["close"].shift(1).rolling(lookback).max()
    roll_max_r = df["rsi"].shift(1).rolling(lookback).max()
    df.loc[(df["close"] <= roll_min_c) & (df["rsi"] > roll_min_r) & (df["rsi"] < 50), "divergence"] = "BULL_DIV"
    df.loc[(df["close"] >= roll_max_c) & (df["rsi"] < roll_max_r) & (df["rsi"] > 50), "divergence"] = "BEAR_DIV"
    return df

def detect_liquidity_sweep(df):
    """Scalar version — used for the live single-snapshot path."""
    data = df.tail(CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    if len(data) < 5: return None
    last = data.iloc[-1]
    p_highs = data["high"].iloc[:-1]
    p_lows = data["low"].iloc[:-1]
    if last["high"] > p_highs.max() and last["close"] < p_highs.max(): return "EQUAL_HIGH_SWEEP"
    if last["low"] < p_lows.min() and last["close"] > p_lows.min(): return "EQUAL_LOW_SWEEP"
    return None

def detect_liquidity_sweep_vectorized(df, lookback=20):
    """Vectorized version of detect_liquidity_sweep — used for fast backtests."""
    high, low, close = df["high"], df["low"], df["close"]
    roll_high_prior = high.shift(1).rolling(lookback - 1).max()
    roll_low_prior = low.shift(1).rolling(lookback - 1).min()
    sweep = pd.Series('', index=df.index)
    bsl_sweep = (high > roll_high_prior) & (close < roll_high_prior)
    ssl_sweep = (low < roll_low_prior) & (close > roll_low_prior)
    sweep[bsl_sweep] = 'EQUAL_HIGH_SWEEP'
    sweep[ssl_sweep] = 'EQUAL_LOW_SWEEP'
    return sweep


# ── LIQUIDITY CONCEPTS (NEW): FVG, BSL/SSL, Equal-Level Density, Inducement ─
def detect_fvg_vectorized(df, min_gap_pct=0.02):
    """3-candle Fair Value Gap detection.
    Bullish FVG at i: low[i] > high[i-2]  (gap left below, acts as support magnet)
    Bearish FVG at i: high[i] < low[i-2]  (gap left above, acts as resistance magnet)
    """
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    bull_gap = low - high.shift(2)
    bear_gap = low.shift(2) - high
    bull_mask = (bull_gap > 0) & (bull_gap / close * 100 >= min_gap_pct)
    bear_mask = (bear_gap > 0) & (bear_gap / close * 100 >= min_gap_pct)
    df["fvg"] = ""
    df["fvg_top"] = np.nan
    df["fvg_bottom"] = np.nan
    df.loc[bull_mask, "fvg"] = "BULL_FVG"
    df.loc[bull_mask, "fvg_top"] = low[bull_mask]
    df.loc[bull_mask, "fvg_bottom"] = high.shift(2)[bull_mask]
    df.loc[bear_mask, "fvg"] = "BEAR_FVG"
    df.loc[bear_mask, "fvg_top"] = low.shift(2)[bear_mask]
    df.loc[bear_mask, "fvg_bottom"] = high[bear_mask]
    return df

def compute_active_fvg_series(df, min_gap_pct=0.02):
    """Single forward pass: tracks nearest UNFILLED FVG zone at each bar and
    the % distance of price to it (used as an 'internal liquidity magnet' score).
    A bull FVG is considered filled once close trades back below its bottom;
    a bear FVG is filled once close trades back above its top."""
    df = detect_fvg_vectorized(df, min_gap_pct)
    n = len(df)
    close = df["close"].values
    fvg = df["fvg"].values
    fvg_top = df["fvg_top"].values
    fvg_bottom = df["fvg_bottom"].values

    active_bull = None  # (top, bottom)
    active_bear = None
    dist_bull = np.full(n, np.nan)
    dist_bear = np.full(n, np.nan)

    for i in range(n):
        if fvg[i] == "BULL_FVG":
            active_bull = (fvg_top[i], fvg_bottom[i])
        if fvg[i] == "BEAR_FVG":
            active_bear = (fvg_top[i], fvg_bottom[i])
        c = close[i]
        if active_bull is not None:
            _, bottom = active_bull
            if c < bottom:
                active_bull = None
            else:
                dist_bull[i] = (c - bottom) / c * 100
        if active_bear is not None:
            top, _ = active_bear
            if c > top:
                active_bear = None
            else:
                dist_bear[i] = (top - c) / c * 100

    df["dist_to_bull_fvg_pct"] = dist_bull
    df["dist_to_bear_fvg_pct"] = dist_bear
    return df

def detect_bsl_ssl_zones(df, lookback=20):
    """External liquidity levels — rolling high (BSL pool) / rolling low (SSL pool)."""
    df = df.copy()
    df["bsl_level"] = df["high"].rolling(lookback).max()
    df["ssl_level"] = df["low"].rolling(lookback).min()
    df["dist_to_bsl_pct"] = (df["bsl_level"] - df["close"]) / df["close"] * 100
    df["dist_to_ssl_pct"] = (df["close"] - df["ssl_level"]) / df["close"] * 100
    return df

def calc_equal_level_density(df, lookback=20, tol_pct=0.05):
    """How many highs/lows in the lookback window sit within tol_pct of the
    rolling extreme — a proxy for how 'crowded' (equal highs/equal lows)
    a liquidity pool is. Denser pool = more reliable sweep target."""
    def count_equal_high(window):
        level = window.max()
        if level == 0: return 0
        return np.sum(np.abs(window - level) / level * 100 <= tol_pct)

    def count_equal_low(window):
        level = window.min()
        if level == 0: return 0
        return np.sum(np.abs(window - level) / level * 100 <= tol_pct)

    df = df.copy()
    df["eq_high_count"] = df["high"].rolling(lookback).apply(count_equal_high, raw=True)
    df["eq_low_count"] = df["low"].rolling(lookback).apply(count_equal_low, raw=True)
    return df

def detect_inducement(df, minor_lookback=2):
    """Proxy for 'inducement': price wicks through a MINOR (small) prior
    swing point and closes back inside it — a small trap before the real
    (external) liquidity sweep. Uses only trailing data (no lookahead),
    so it's safe for both live signals and backtests."""
    df = df.copy()
    high, low, close, open_ = df["high"], df["low"], df["close"], df["open"]
    prior_high = high.shift(1).rolling(minor_lookback).max()
    prior_low = low.shift(1).rolling(minor_lookback).min()
    df["inducement"] = ""
    bull_ind = (low < prior_low) & (close > prior_low) & (close > open_)
    bear_ind = (high > prior_high) & (close < prior_high) & (close < open_)
    df.loc[bull_ind, "inducement"] = "BULL_INDUCEMENT"
    df.loc[bear_ind, "inducement"] = "BEAR_INDUCEMENT"
    return df

def calc_liquidity_score(snap):
    """SCALAR version (live path) — combines sweep + inducement + FVG
    proximity + equal-level density confluence into a buy/sell score."""
    buy, sell = 0.0, 0.0

    if snap.get("sweep") == "EQUAL_LOW_SWEEP":
        buy += 2.5
    elif snap.get("sweep") == "EQUAL_HIGH_SWEEP":
        sell += 2.5

    if snap.get("inducement") == "BULL_INDUCEMENT":
        buy += 2.0
    elif snap.get("inducement") == "BEAR_INDUCEMENT":
        sell += 2.0

    dbull = snap.get("dist_to_bull_fvg_pct")
    dbear = snap.get("dist_to_bear_fvg_pct")
    if dbull is not None and not pd.isna(dbull) and 0 <= dbull <= CONFIG['FVG_PROXIMITY_PCT']:
        buy += 1.5
    if dbear is not None and not pd.isna(dbear) and 0 <= dbear <= CONFIG['FVG_PROXIMITY_PCT']:
        sell += 1.5

    eqh = snap.get("eq_high_count") or 0
    eql = snap.get("eq_low_count") or 0
    if snap.get("sweep") == "EQUAL_LOW_SWEEP" and eql >= CONFIG['EQUAL_LEVEL_MIN_COUNT']:
        buy += 1.0
    if snap.get("sweep") == "EQUAL_HIGH_SWEEP" and eqh >= CONFIG['EQUAL_LEVEL_MIN_COUNT']:
        sell += 1.0

    return buy, sell

def _liquidity_score_vectorized(df, w=1.0):
    """VECTORIZED version (backtest path) — mirrors calc_liquidity_score exactly."""
    buy = pd.Series(0.0, index=df.index)
    sell = pd.Series(0.0, index=df.index)

    buy += np.where(df["sweep_v"] == "EQUAL_LOW_SWEEP", 2.5 * w, 0.0)
    sell += np.where(df["sweep_v"] == "EQUAL_HIGH_SWEEP", 2.5 * w, 0.0)

    buy += np.where(df["inducement"] == "BULL_INDUCEMENT", 2.0 * w, 0.0)
    sell += np.where(df["inducement"] == "BEAR_INDUCEMENT", 2.0 * w, 0.0)

    dbull = df["dist_to_bull_fvg_pct"]
    dbear = df["dist_to_bear_fvg_pct"]
    buy += np.where((dbull >= 0) & (dbull <= CONFIG['FVG_PROXIMITY_PCT']), 1.5 * w, 0.0)
    sell += np.where((dbear >= 0) & (dbear <= CONFIG['FVG_PROXIMITY_PCT']), 1.5 * w, 0.0)

    eqh = df["eq_high_count"].fillna(0)
    eql = df["eq_low_count"].fillna(0)
    buy += np.where((df["sweep_v"] == "EQUAL_LOW_SWEEP") & (eql >= CONFIG['EQUAL_LEVEL_MIN_COUNT']), 1.0 * w, 0.0)
    sell += np.where((df["sweep_v"] == "EQUAL_HIGH_SWEEP") & (eqh >= CONFIG['EQUAL_LEVEL_MIN_COUNT']), 1.0 * w, 0.0)

    return buy, sell


def add_indicators_vectorized(df):
    df = df.copy()
    df["ema5"] = calc_ema(df["close"], CONFIG['EMA_FAST'])
    df["ema20"] = calc_ema(df["close"], CONFIG['EMA_SLOW'])
    df["rsi"] = calc_rsi(df["close"], CONFIG['RSI_PERIOD'])
    df["atr"] = calc_atr(df, CONFIG['ATR_PERIOD'])
    df["adx"] = calc_adx(df, CONFIG['ADX_PERIOD'])
    df["vwap"] = calc_session_vwap(df)
    return df

def analyze_timeframe(df):
    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = detect_bsl_ssl_zones(df, CONFIG['BSL_SSL_LOOKBACK'])
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    sweep = detect_liquidity_sweep(df)
    vp = calc_volume_profile(df, CONFIG['VOLUME_PROFILE_LOOKBACK'], CONFIG['VOLUME_PROFILE_BINS'])
    regime = detect_market_regime(df)
    last = df.iloc[-1]
    return {
        "structure_event": last["structure_event"],
        "structure_trend": last["structure_trend"],
        "adx": last["adx"], "price": last["close"], "vwap": last["vwap"],
        "ema5": last["ema5"], "ema20": last["ema20"], "rsi": last["rsi"],
        "atr": last["atr"],
        "pattern": last["pat_sig"], "divergence": last["divergence"],
        "sweep": sweep, "vp": vp, "regime": regime,
        # ── Liquidity concepts fields ──
        "fvg": last["fvg"],
        "dist_to_bull_fvg_pct": last["dist_to_bull_fvg_pct"],
        "dist_to_bear_fvg_pct": last["dist_to_bear_fvg_pct"],
        "bsl_level": last["bsl_level"], "ssl_level": last["ssl_level"],
        "dist_to_bsl_pct": last["dist_to_bsl_pct"], "dist_to_ssl_pct": last["dist_to_ssl_pct"],
        "eq_high_count": last["eq_high_count"], "eq_low_count": last["eq_low_count"],
        "inducement": last["inducement"],
    }


# ── HTF Bias — SCALPER uses 15m ONLY (1h removed) ──────────────────────────
def get_htf_bias(snap_15m):
    weight = 1.0
    score = 0.0
    if snap_15m["structure_trend"] == "BULL": score += weight
    elif snap_15m["structure_trend"] == "BEAR": score -= weight
    score += weight * 0.5 if snap_15m["ema5"] > snap_15m["ema20"] else -weight * 0.5
    if not pd.isna(snap_15m["rsi"]):
        if snap_15m["rsi"] > 55: score += weight * 0.3
        elif snap_15m["rsi"] < 45: score -= weight * 0.3
    # liquidity confluence on the HTF adds conviction to the bias
    if snap_15m.get("sweep") == "EQUAL_LOW_SWEEP": score += 0.5
    elif snap_15m.get("sweep") == "EQUAL_HIGH_SWEEP": score -= 0.5
    if snap_15m.get("inducement") == "BULL_INDUCEMENT": score += 0.3
    elif snap_15m.get("inducement") == "BEAR_INDUCEMENT": score -= 0.3

    if score >= 0.9: return "BULLISH"
    if score <= -0.9: return "BEARISH"
    return "NEUTRAL"

# ── LTF Scores — SCALPER uses 1m + 5m (+ liquidity concepts) ──────────────
def get_ltf_scores(snap_1m, snap_5m):
    buy_score, sell_score = 0.0, 0.0
    for snap, w in [(snap_1m, 1.0), (snap_5m, 1.2)]:
        if snap["pattern"] == "BUY": buy_score += 2 * w
        elif snap["pattern"] == "SELL": sell_score += 2 * w
        if snap["divergence"] == "BULL_DIV": buy_score += 3 * w
        elif snap["divergence"] == "BEAR_DIV": sell_score += 3 * w
        if snap["sweep"] == "EQUAL_LOW_SWEEP": buy_score += 3 * w
        elif snap["sweep"] == "EQUAL_HIGH_SWEEP": sell_score += 3 * w
        if snap["structure_event"] in ("BOS_BULL", "CHoCH_BULL"):
            buy_score += (2 if "CHoCH" in snap["structure_event"] else 1.5) * w
        elif snap["structure_event"] in ("BOS_BEAR", "CHoCH_BEAR"):
            sell_score += (2 if "CHoCH" in snap["structure_event"] else 1.5) * w
        if snap["vp"]["poc"] is not None:
            buy_score += 0.5 * w if snap["price"] > snap["vp"]["poc"] else 0
            sell_score += 0.5 * w if snap["price"] <= snap["vp"]["poc"] else 0
        if not pd.isna(snap["vwap"]):
            buy_score += 0.5 * w if snap["price"] > snap["vwap"] else 0
            sell_score += 0.5 * w if snap["price"] <= snap["vwap"] else 0
        if snap["ema5"] > snap["ema20"]: buy_score += 0.5 * w
        else: sell_score += 0.5 * w
        if not pd.isna(snap["rsi"]):
            if snap["rsi"] < 35: buy_score += 1.0 * w
            elif snap["rsi"] > 65: sell_score += 1.0 * w
        # ── NEW: Liquidity Concepts contribution (sweep+inducement+FVG+density) ──
        liq_buy, liq_sell = calc_liquidity_score(snap)
        buy_score += liq_buy * w
        sell_score += liq_sell * w
    return round(buy_score, 2), round(sell_score, 2)

def decide_direction(buy_score, sell_score, htf_bias,
                      entry_adx, regime_1m, regime_5m, entry_rsi=None):
    if pd.isna(entry_adx) or entry_adx < CONFIG['ADX_MIN']:
        return None, f"NO TREND (ADX {entry_adx:.1f} < {CONFIG['ADX_MIN']})"

    if entry_rsi is not None and not pd.isna(entry_rsi):
        if entry_rsi > CONFIG['RSI_OVERBOUGHT']:
            return None, f"BLOCKED (RSI overbought {entry_rsi:.1f})"
        if entry_rsi < CONFIG['RSI_OVERSOLD']:
            return None, f"BLOCKED (RSI oversold {entry_rsi:.1f})"

    if regime_1m["regime"] == "COMPRESSION" or regime_5m["regime"] == "COMPRESSION":
        return None, "BLOCKED (compression, wait breakout)"
    if regime_1m["regime"] == "RANGING" or regime_5m["regime"] == "RANGING":
        return None, f"BLOCKED (choppy CI 1m={regime_1m['choppiness']}, 5m={regime_5m['choppiness']})"
    if regime_1m["regime"] != "TRENDING" or regime_5m["regime"] != "TRENDING":
        return None, "BLOCKED (not trending)"

    if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
        if (buy_score - sell_score) >= CONFIG['SCORE_GAP_MIN'] and htf_bias in ("BULLISH", "NEUTRAL"):
            return "BUY", "BUY ✅"
    if sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
        if (sell_score - buy_score) >= CONFIG['SCORE_GAP_MIN'] and htf_bias in ("BEARISH", "NEUTRAL"):
            return "SELL", "SELL ✅"
    return None, "WAIT (score/bias aligned nahi)"

def calc_tp_sl(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    sl_dist = round(CONFIG['SL_ATR_MULT'] * atr, 4)
    tp_dist = round(CONFIG['TP_ATR_MULT'] * atr, 4)
    if direction == "BUY":
        return round(price + tp_dist, 4), round(price - sl_dist, 4)
    return round(price - tp_dist, 4), round(price + sl_dist, 4)


import time as _time

# ── HTF cache — 15m ONLY — 30s ─────────────────────────────────────────────
_HTF_CACHE = {}
_HTF_CACHE_TTL = 30

def _get_htf_bias_cached(symbol):
    now = _time.time()
    cached = _HTF_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < _HTF_CACHE_TTL:
        return cached["bias"]
    htf_bias = "NEUTRAL"
    df_15m, _ = fetch_ohlcv_failover(symbol, "15m", CONFIG['LIMIT'])
    if df_15m is not None:
        snap_15m = analyze_timeframe(df_15m)
        htf_bias = get_htf_bias(snap_15m)
    _HTF_CACHE[symbol] = {"bias": htf_bias, "ts": now}
    return htf_bias

# ── LTF cache — 1m + 5m — 15s ──────────────────────────────────────────────
_LTF_CACHE = {}
_LTF_CACHE_TTL = 15

def _get_ltf_snaps_cached(symbol):
    now = _time.time()
    cached = _LTF_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < _LTF_CACHE_TTL:
        return cached["snap_1m"], cached["snap_5m"]
    df_1m, _ = fetch_ohlcv_failover(symbol, "1m", CONFIG['LIMIT'])
    df_5m, _ = fetch_ohlcv_failover(symbol, "5m", CONFIG['LIMIT'])
    snap_1m = analyze_timeframe(df_1m) if df_1m is not None else None
    snap_5m = analyze_timeframe(df_5m) if df_5m is not None else None
    _LTF_CACHE[symbol] = {"snap_1m": snap_1m, "snap_5m": snap_5m, "ts": now}
    return snap_1m, snap_5m


# ── PUBLIC ENTRY POINT (LIVE) ────────────────────────────────────────────
def analyze(symbol, timeframe="1m"):
    df_entry, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
    if df_entry is None:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}

    snap_entry = analyze_timeframe(df_entry)
    price = float(snap_entry["price"])
    rsi_now = float(snap_entry["rsi"]) if not pd.isna(snap_entry["rsi"]) else None
    atr_now = float(snap_entry["atr"]) if not pd.isna(snap_entry["atr"]) else None

    htf_bias = _get_htf_bias_cached(symbol)

    snap_1m, snap_5m = _get_ltf_snaps_cached(symbol)
    if snap_1m is None: snap_1m = snap_entry
    if snap_5m is None: snap_5m = snap_entry

    buy_score, sell_score = get_ltf_scores(snap_1m, snap_5m)

    direction, reason = decide_direction(
        buy_score, sell_score, htf_bias, snap_entry["adx"],
        snap_1m["regime"], snap_5m["regime"],
        entry_rsi=rsi_now
    )

    signal = direction if direction else "WAIT"
    tp, sl = calc_tp_sl(direction, price, atr_now)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": round(price, 4),
        "rsi": round(rsi_now, 2) if rsi_now is not None else None,
        "signal": signal,
        "reason": reason,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "htf_bias": htf_bias,
        "regime": snap_entry["regime"]["regime"],
        "structure": snap_entry["structure_event"],
        "exchange": ex_id,
        "entry": round(price, 4) if direction else None,
        "tp": tp,
        "sl": sl,
        "atr": round(atr_now, 4) if atr_now else None,
        # ── Liquidity concepts context (useful for debugging why a signal fired) ──
        "liquidity": {
            "sweep": snap_entry["sweep"],
            "fvg": snap_entry["fvg"],
            "dist_to_bull_fvg_pct": round(snap_entry["dist_to_bull_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bull_fvg_pct"]) else None,
            "dist_to_bear_fvg_pct": round(snap_entry["dist_to_bear_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bear_fvg_pct"]) else None,
            "bsl_level": round(snap_entry["bsl_level"], 4) if not pd.isna(snap_entry["bsl_level"]) else None,
            "ssl_level": round(snap_entry["ssl_level"], 4) if not pd.isna(snap_entry["ssl_level"]) else None,
            "eq_high_count": snap_entry["eq_high_count"],
            "eq_low_count": snap_entry["eq_low_count"],
            "inducement": snap_entry["inducement"],
        },
    }


# ── FAST SINGLE-TIMEFRAME BACKTEST (now includes liquidity factors) ───────
def run_backtest(symbol, timeframe="5m"):
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['BACKTEST_CANDLES'])
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    liq_buy_s, liq_sell_s = _liquidity_score_vectorized(df, w=1.0)
    df["liq_buy"] = liq_buy_s
    df["liq_sell"] = liq_sell_s

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    results = []
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

    for i in range(60, n - WINDOW):
        rsi = df["rsi"].iloc[i]
        adx = df["adx"].iloc[i]
        atr = df["atr"].iloc[i]
        ema5 = df["ema5"].iloc[i]
        ema20 = df["ema20"].iloc[i]
        vwap = df["vwap"].iloc[i]
        pat = df["pat_sig"].iloc[i]
        div = df["divergence"].iloc[i]
        struct = df["structure_event"].iloc[i]
        price = closes[i]

        if pd.isna(adx) or adx < CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > CONFIG['RSI_OVERBOUGHT'] or rsi < CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue

        buy_score, sell_score = 0.0, 0.0
        if pat == "BUY": buy_score += 2
        elif pat == "SELL": sell_score += 2
        if div == "BULL_DIV": buy_score += 3
        elif div == "BEAR_DIV": sell_score += 3
        if struct in ("BOS_BULL", "CHoCH_BULL"): buy_score += 2
        elif struct in ("BOS_BEAR", "CHoCH_BEAR"): sell_score += 2
        if not pd.isna(vwap):
            if price > vwap: buy_score += 0.5
            else: sell_score += 0.5
        if ema5 > ema20: buy_score += 0.5
        else: sell_score += 0.5
        if rsi < 35: buy_score += 1.0
        elif rsi > 65: sell_score += 1.0

        # ── NEW: liquidity concepts contribution ──
        buy_score += df["liq_buy"].iloc[i]
        sell_score += df["liq_sell"].iloc[i]

        gap = abs(buy_score - sell_score)
        if gap < CONFIG['SCORE_GAP_MIN']:
            continue

        direction = None
        if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
            direction = "BUY"
        elif sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
            direction = "SELL"
        if direction is None: continue

        tp, sl = calc_tp_sl(direction, price, atr)
        if tp is None: continue

        outcome = "OPEN"
        exit_price = None
        for j in range(i + 1, min(i + WINDOW + 1, n)):
            fh = highs[j]; fl = lows[j]
            if direction == "BUY":
                if fh >= tp: outcome = "WIN"; exit_price = tp; break
                if fl <= sl: outcome = "LOSS"; exit_price = sl; break
            else:
                if fl <= tp: outcome = "WIN"; exit_price = tp; break
                if fh >= sl: outcome = "LOSS"; exit_price = sl; break
        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                   else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']

        results.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": round(price, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "outcome": outcome, "pnl_pct": round(pnl_pct, 4),
        })

    if not results:
        return {"symbol": symbol, "timeframe": timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No signals in this window"}

    wins = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total = len(wins) + len(losses)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)
    avg_rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else None

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": CONFIG['BACKTEST_CANDLES'],
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy, "avg_rr": avg_rr,
        "recent_trades": results[-10:],
    }


# ── FULL MULTI-TIMEFRAME BACKTEST (mirrors live analyze() — 1m/5m/15m only) ─
def _vectorized_regime(df):
    atr = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx = calc_adx(df, CONFIG['ADX_PERIOD'])

    atr_ratio = atr / atr_ma.replace(0, np.nan)
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy = ci > CONFIG['CHOPPINESS_TREND_MAX']
    is_trending = adx >= CONFIG['ADX_MIN']

    regime = pd.Series("RANGING", index=df.index)
    regime[is_trending & ~is_choppy & ~is_compressed] = "TRENDING"
    regime[is_compressed] = "COMPRESSION"
    return regime, ci, adx

def _build_tf_features(df):
    """Compute all per-row indicators/events needed for scoring — including
    the new Liquidity Concepts columns — vectorized."""
    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = detect_bsl_ssl_zones(df, CONFIG['BSL_SSL_LOOKBACK'])
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    regime, ci, adx_full = _vectorized_regime(df)
    df["regime_label"] = regime
    return df

def _htf_bias_series_single(df15):
    """Vectorized HTF bias using 15m ONLY (1h removed for scalper mode)."""
    weight = 1.0
    s = pd.Series(0.0, index=df15.index)
    s += np.where(df15["structure_trend"] == "BULL", weight, np.where(df15["structure_trend"] == "BEAR", -weight, 0.0))
    s += np.where(df15["ema5"] > df15["ema20"], weight * 0.5, -weight * 0.5)
    s += np.where(df15["rsi"] > 55, weight * 0.3, np.where(df15["rsi"] < 45, -weight * 0.3, 0.0))
    s += np.where(df15["sweep_v"] == "EQUAL_LOW_SWEEP", 0.5, np.where(df15["sweep_v"] == "EQUAL_HIGH_SWEEP", -0.5, 0.0))
    s += np.where(df15["inducement"] == "BULL_INDUCEMENT", 0.3, np.where(df15["inducement"] == "BEAR_INDUCEMENT", -0.3, 0.0))
    bias = np.where(s >= 0.9, "BULLISH", np.where(s <= -0.9, "BEARISH", "NEUTRAL"))
    return pd.Series(bias, index=df15.index, name="bias")

def _ltf_score_series(df1m, df5m):
    """Vectorized 1m+5m scoring including liquidity concepts, for merge_asof."""
    def score_component(df, w):
        buy = pd.Series(0.0, index=df.index)
        sell = pd.Series(0.0, index=df.index)
        buy += np.where(df["pat_sig"] == "BUY", 2 * w, 0.0)
        sell += np.where(df["pat_sig"] == "SELL", 2 * w, 0.0)
        buy += np.where(df["divergence"] == "BULL_DIV", 3 * w, 0.0)
        sell += np.where(df["divergence"] == "BEAR_DIV", 3 * w, 0.0)
        buy += np.where(df["sweep_v"] == "EQUAL_LOW_SWEEP", 3 * w, 0.0)
        sell += np.where(df["sweep_v"] == "EQUAL_HIGH_SWEEP", 3 * w, 0.0)
        is_choch = df["structure_event"].astype(str).str.contains("CHoCH")
        bull_evt = df["structure_event"].isin(["BOS_BULL", "CHoCH_BULL"])
        bear_evt = df["structure_event"].isin(["BOS_BEAR", "CHoCH_BEAR"])
        buy += np.where(bull_evt, np.where(is_choch, 2 * w, 1.5 * w), 0.0)
        sell += np.where(bear_evt, np.where(is_choch, 2 * w, 1.5 * w), 0.0)
        buy += np.where(df["close"] > df["vwap"], 0.5 * w, 0.0)
        sell += np.where(df["close"] <= df["vwap"], 0.5 * w, 0.0)
        buy += np.where(df["ema5"] > df["ema20"], 0.5 * w, 0.0)
        sell += np.where(df["ema5"] <= df["ema20"], 0.5 * w, 0.0)
        buy += np.where(df["rsi"] < 35, 1.0 * w, 0.0)
        sell += np.where(df["rsi"] > 65, 1.0 * w, 0.0)
        # ── liquidity concepts ──
        liq_b, liq_s = _liquidity_score_vectorized(df, w)
        buy += liq_b
        sell += liq_s
        return buy, sell

    b1, s1 = score_component(df1m, 1.0)
    b5, s5 = score_component(df5m, 1.2)

    out1m = pd.DataFrame({"time": df1m.index, "b1": b1.values, "s1": s1.values})
    out5m = pd.DataFrame({"time": df5m.index, "b5": b5.values, "s5": s5.values})
    merged = pd.merge_asof(out1m.sort_values("time"), out5m.sort_values("time"),
                            on="time", direction="backward")
    merged["buy_score"] = round((merged["b1"] + merged["b5"]), 2)
    merged["sell_score"] = round((merged["s1"] + merged["s5"]), 2)
    merged = merged.set_index("time")
    return merged[["buy_score", "sell_score"]]

def run_backtest_full(symbol, entry_timeframe="5m"):
    """
    Backtest that mirrors the LIVE multi-timeframe strategy:
    - HTF bias from 15m ONLY (scalper mode — 1h removed)
    - LTF score from 1m + 5m (incl. liquidity concepts)
    - Regime/ADX/RSI filters same as decide_direction()
    """
    limit = CONFIG['BACKTEST_CANDLES']

    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, limit)
    df_1m, _ = fetch_ohlcv_failover(symbol, "1m", limit)
    df_5m, _ = fetch_ohlcv_failover(symbol, "5m", limit)
    df_15m, _ = fetch_ohlcv_failover(symbol, "15m", limit)

    if any(x is None for x in [df_entry, df_1m, df_5m, df_15m]):
        return {"error": "insufficient data across timeframes (need 1m/5m/15m)"}

    df_entry = _build_tf_features(df_entry)
    df_1m = _build_tf_features(df_1m)
    df_5m = _build_tf_features(df_5m)
    df_15m = _build_tf_features(df_15m)

    bias_series = _htf_bias_series_single(df_15m)
    score_df = _ltf_score_series(df_1m, df_5m)

    entry_times = pd.DataFrame({"time": df_entry.index})
    bias_aligned = pd.merge_asof(entry_times, bias_series.rename("bias").reset_index(),
                                  on="time", direction="backward")
    score_aligned = pd.merge_asof(entry_times, score_df.reset_index(),
                                   on="time", direction="backward")

    df_entry = df_entry.reset_index()
    df_entry["bias"] = bias_aligned["bias"]
    df_entry["buy_score"] = score_aligned["buy_score"]
    df_entry["sell_score"] = score_aligned["sell_score"]

    closes = df_entry["close"].values
    highs = df_entry["high"].values
    lows = df_entry["low"].values
    n = len(df_entry)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []

    for i in range(60, n - WINDOW):
        row = df_entry.iloc[i]
        rsi, adx, atr = row["rsi"], row["adx"], row["atr"]
        if pd.isna(adx) or adx < CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > CONFIG['RSI_OVERBOUGHT'] or rsi < CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue

        buy_score, sell_score = row["buy_score"], row["sell_score"]
        if pd.isna(buy_score) or pd.isna(sell_score): continue

        gap = abs(buy_score - sell_score)
        if gap < CONFIG['SCORE_GAP_MIN']: continue

        bias = row["bias"]
        regime = row["regime_label"]
        if regime == "RANGING": continue

        direction = None
        if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score and bias in ("BULLISH", "NEUTRAL"):
            direction = "BUY"
        elif sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score and bias in ("BEARISH", "NEUTRAL"):
            direction = "SELL"
        if direction is None: continue

        price = closes[i]
        tp, sl = calc_tp_sl(direction, price, atr)
        if tp is None: continue

        outcome, exit_price = "OPEN", None
        for j in range(i + 1, min(i + WINDOW + 1, n)):
            fh, fl = highs[j], lows[j]
            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= sl: outcome, exit_price = "LOSS", sl; break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= sl: outcome, exit_price = "LOSS", sl; break
        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                   else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']

        results.append({
            "time": row["timestamp"].strftime("%m-%d %H:%M") if "timestamp" in row else str(row.name),
            "direction": direction, "entry": round(price, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "outcome": outcome, "pnl_pct": round(pnl_pct, 4),
        })

    if not results:
        return {"symbol": symbol, "timeframe": entry_timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No signals in this window"}

    wins = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total = len(wins) + len(losses)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)
    avg_rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else None

    return {
        "symbol": symbol, "timeframe": entry_timeframe, "candles_tested": limit,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy, "avg_rr": avg_rr,
        "recent_trades": results[-10:],
        "note": "Multi-timeframe backtest: 15m HTF bias + 1m/5m LTF scoring, incl. BSL/SSL sweep, FVG, inducement, equal-level density.",
    }


# ── FACTOR-ISOLATION BACKTEST (now with FVG + Inducement as own factors) ──
def run_factor_backtest(symbol, timeframe="5m"):
    """
    Tests each signal component SEPARATELY to see which ones have real edge:
      1. Liquidity Sweep (BSL/SSL) only
      2. Structure Break (BOS/CHoCH) only
      3. Divergence only
      4. Candle Pattern only
      5. EMA crossover (baseline)
      6. Fair Value Gap (FVG) proximity only        [NEW]
      7. Inducement wick-trap only                   [NEW]
    """
    limit = CONFIG['BACKTEST_CANDLES']
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

    def simulate(direction_fn, label):
        results = []
        for i in range(60, n - WINDOW):
            atr = df["atr"].iloc[i]
            if pd.isna(atr): continue
            direction = direction_fn(i)
            if direction is None: continue

            price = closes[i]
            tp, sl = calc_tp_sl(direction, price, atr)
            if tp is None: continue

            outcome, exit_price = "OPEN", None
            for j in range(i + 1, min(i + WINDOW + 1, n)):
                fh, fl = highs[j], lows[j]
                if direction == "BUY":
                    if fh >= tp: outcome, exit_price = "WIN", tp; break
                    if fl <= sl: outcome, exit_price = "LOSS", sl; break
                else:
                    if fl <= tp: outcome, exit_price = "WIN", tp; break
                    if fh >= sl: outcome, exit_price = "LOSS", sl; break
            if outcome == "OPEN": continue

            pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                       else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']
            results.append({"outcome": outcome, "pnl_pct": pnl_pct})

        wins = [r for r in results if r["outcome"] == "WIN"]
        losses = [r for r in results if r["outcome"] == "LOSS"]
        total = len(wins) + len(losses)
        if total == 0:
            return {"label": label, "total_trades": 0, "note": "no signals"}

        gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
        gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        win_rate = round(len(wins) / total * 100, 1)
        avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
        avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
        expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)

        return {
            "label": label, "total_trades": total, "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate, "profit_factor": profit_factor, "expectancy_pct": expectancy,
        }

    def f_sweep(i):
        s = df["sweep_v"].iloc[i]
        if s == "EQUAL_LOW_SWEEP": return "BUY"
        if s == "EQUAL_HIGH_SWEEP": return "SELL"
        return None

    def f_structure(i):
        ev = df["structure_event"].iloc[i]
        if ev in ("BOS_BULL", "CHoCH_BULL"): return "BUY"
        if ev in ("BOS_BEAR", "CHoCH_BEAR"): return "SELL"
        return None

    def f_divergence(i):
        d = df["divergence"].iloc[i]
        if d == "BULL_DIV": return "BUY"
        if d == "BEAR_DIV": return "SELL"
        return None

    def f_pattern(i):
        p = df["pat_sig"].iloc[i]
        if p == "BUY": return "BUY"
        if p == "SELL": return "SELL"
        return None

    def f_ema_baseline(i):
        if i < 1: return None
        cross_up = df["ema5"].iloc[i - 1] <= df["ema20"].iloc[i - 1] and df["ema5"].iloc[i] > df["ema20"].iloc[i]
        cross_down = df["ema5"].iloc[i - 1] >= df["ema20"].iloc[i - 1] and df["ema5"].iloc[i] < df["ema20"].iloc[i]
        if cross_up: return "BUY"
        if cross_down: return "SELL"
        return None

    def f_fvg(i):
        dbull = df["dist_to_bull_fvg_pct"].iloc[i]
        dbear = df["dist_to_bear_fvg_pct"].iloc[i]
        if not pd.isna(dbull) and 0 <= dbull <= CONFIG['FVG_PROXIMITY_PCT']: return "BUY"
        if not pd.isna(dbear) and 0 <= dbear <= CONFIG['FVG_PROXIMITY_PCT']: return "SELL"
        return None

    def f_inducement(i):
        ind = df["inducement"].iloc[i]
        if ind == "BULL_INDUCEMENT": return "BUY"
        if ind == "BEAR_INDUCEMENT": return "SELL"
        return None

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": limit,
        "factors": [
            simulate(f_sweep, "1. Liquidity Sweep (BSL/SSL) only"),
            simulate(f_structure, "2. Structure Break (BOS/CHoCH) only"),
            simulate(f_divergence, "3. Divergence only"),
            simulate(f_pattern, "4. Candle Pattern only"),
            simulate(f_ema_baseline, "5. EMA Crossover (baseline)"),
            simulate(f_fvg, "6. Fair Value Gap (FVG) proximity only"),
            simulate(f_inducement, "7. Inducement wick-trap only"),
        ]
    }


# ── COMBINED FACTOR BACKTEST (now votes include FVG + Inducement) ─────────
def run_combined_backtest(symbol, timeframe="5m", min_agree=2, strong_adx=25, use_breakeven=True):
    """
    Trade only when >= min_agree factors agree on direction, AND adx >= strong_adx.
    Factors voting: Liquidity Sweep, Structure Break, Divergence, Candle Pattern,
    EMA crossover, FVG proximity, Inducement — i.e. the full liquidity-concepts
    + base-engine combo, voted together.
    """
    limit = CONFIG['BACKTEST_CANDLES']
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []

    def get_factor_votes(i):
        votes = []

        s = df["sweep_v"].iloc[i]
        if s == "EQUAL_LOW_SWEEP": votes.append("BUY")
        elif s == "EQUAL_HIGH_SWEEP": votes.append("SELL")

        ev = df["structure_event"].iloc[i]
        if ev in ("BOS_BULL", "CHoCH_BULL"): votes.append("BUY")
        elif ev in ("BOS_BEAR", "CHoCH_BEAR"): votes.append("SELL")

        d = df["divergence"].iloc[i]
        if d == "BULL_DIV": votes.append("BUY")
        elif d == "BEAR_DIV": votes.append("SELL")

        p = df["pat_sig"].iloc[i]
        if p == "BUY": votes.append("BUY")
        elif p == "SELL": votes.append("SELL")

        if i >= 1:
            cross_up = df["ema5"].iloc[i - 1] <= df["ema20"].iloc[i - 1] and df["ema5"].iloc[i] > df["ema20"].iloc[i]
            cross_down = df["ema5"].iloc[i - 1] >= df["ema20"].iloc[i - 1] and df["ema5"].iloc[i] < df["ema20"].iloc[i]
            if cross_up: votes.append("BUY")
            elif cross_down: votes.append("SELL")

        dbull = df["dist_to_bull_fvg_pct"].iloc[i]
        dbear = df["dist_to_bear_fvg_pct"].iloc[i]
        if not pd.isna(dbull) and 0 <= dbull <= CONFIG['FVG_PROXIMITY_PCT']: votes.append("BUY")
        if not pd.isna(dbear) and 0 <= dbear <= CONFIG['FVG_PROXIMITY_PCT']: votes.append("SELL")

        ind = df["inducement"].iloc[i]
        if ind == "BULL_INDUCEMENT": votes.append("BUY")
        elif ind == "BEAR_INDUCEMENT": votes.append("SELL")

        return votes

    for i in range(60, n - WINDOW):
        adx = df["adx"].iloc[i]
        atr = df["atr"].iloc[i]
        if pd.isna(adx) or pd.isna(atr): continue
        if adx < strong_adx: continue

        votes = get_factor_votes(i)
        buy_votes = votes.count("BUY")
        sell_votes = votes.count("SELL")

        direction = None
        if buy_votes >= min_agree and buy_votes > sell_votes:
            direction = "BUY"
        elif sell_votes >= min_agree and sell_votes > buy_votes:
            direction = "SELL"
        if direction is None: continue

        price = closes[i]
        tp, sl = calc_tp_sl(direction, price, atr)
        if tp is None: continue

        breakeven_dist = atr * 0.5
        sl_moved = False
        current_sl = sl

        outcome, exit_price = "OPEN", None
        for j in range(i + 1, min(i + WINDOW + 1, n)):
            fh, fl = highs[j], lows[j]

            if use_breakeven and not sl_moved:
                if direction == "BUY" and fh >= price + breakeven_dist:
                    current_sl = price; sl_moved = True
                elif direction == "SELL" and fl <= price - breakeven_dist:
                    current_sl = price; sl_moved = True

            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= current_sl:
                    outcome = "BREAKEVEN" if sl_moved else "LOSS"
                    exit_price = current_sl; break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= current_sl:
                    outcome = "BREAKEVEN" if sl_moved else "LOSS"
                    exit_price = current_sl; break

        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                   else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']

        results.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": round(price, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "outcome": outcome, "pnl_pct": round(pnl_pct, 4), "votes": votes,
        })

    if not results:
        return {"symbol": symbol, "timeframe": timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No signals — try lowering min_agree or strong_adx"}

    wins = [r for r in results if r["outcome"] in ("WIN", "BREAKEVEN") and r["pnl_pct"] > 0]
    losses = [r for r in results if r["pnl_pct"] <= 0]
    total = len(results)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": limit,
        "min_agree": min_agree, "strong_adx": strong_adx, "use_breakeven": use_breakeven,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
        "recent_trades": results[-10:],
    }


# ── FUNDING RATE FACTOR (unchanged — separate optional factor) ────────────
import ccxt as _ccxt_funding

_funding_exchange = None
try:
    _funding_exchange = _ccxt_funding.okx({'enableRateLimit': True, 'timeout': 15000})
except Exception:
    _funding_exchange = None

def fetch_funding_rate_history(symbol="BTC/USDT:USDT", limit=500):
    if _funding_exchange is None:
        return None, "exchange not initialized"
    try:
        raw = _funding_exchange.fetch_funding_rate_history(symbol, limit=limit)
        if not raw or len(raw) < 20:
            return None, f"got {len(raw) if raw else 0} entries, need 20+"
        rows = []
        for r in raw:
            ts = r.get("timestamp")
            fr = r.get("fundingRate")
            if ts is None or fr is None:
                continue
            rows.append([ts, fr])
        if len(rows) < 20:
            return None, "not enough valid rows after parsing"
        df = pd.DataFrame(rows, columns=["timestamp", "funding_rate"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        return df, None
    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
    # Quick smoke test — adjust symbol as needed
    SYMBOL = "BTC/USDT:USDT"
    print(f"Live signal for {SYMBOL}:")
    print(analyze(SYMBOL, timeframe="1m"))
    print("\nFast backtest (5m):")
    print(run_backtest(SYMBOL, timeframe="5m"))

def run_funding_rate_backtest(symbol="BTC/USDT:USDT", price_timeframe="15m", funding_symbol="BTC/USDT:USDT"):
    """
    Isolated test: does extreme funding rate predict mean-reversion?
    Strategy: when funding rate is extremely positive (crowded longs) -> SELL
              when extremely negative (crowded shorts) -> BUY
    Uses percentile-based thresholds (top/bottom 15% of funding rate distribution).
    """
    limit = CONFIG['BACKTEST_CANDLES']
    price_df, ex_id = fetch_ohlcv_failover(symbol, price_timeframe, limit)
    if price_df is None:
        return {"error": "no price data"}

    funding_df, fund_err = fetch_funding_rate_history(funding_symbol, limit=1000)
    if funding_df is None:
        return {"error": f"no funding rate data — {fund_err}"}

    price_df = add_indicators_vectorized(price_df)  # for ATR

    # Align funding rate onto price timeframe via merge_asof (backward = no lookahead)
    price_times = pd.DataFrame({"time": price_df.index})
    funding_reset = funding_df.reset_index().rename(columns={"timestamp": "time"})
    merged = pd.merge_asof(price_times.sort_values("time"), funding_reset.sort_values("time"),
                            on="time", direction="backward")
    merged = merged.set_index("time")

    price_df = price_df.copy()
    price_df["funding_rate"] = merged["funding_rate"]

    # Percentile thresholds for "extreme" funding
    valid_fr = price_df["funding_rate"].dropna()
    if len(valid_fr) < 50:
        return {"error": "insufficient overlapping funding rate data"}

    high_thresh = valid_fr.quantile(0.85)
    low_thresh = valid_fr.quantile(0.15)

    closes = price_df["close"].values
    highs = price_df["high"].values
    lows = price_df["low"].values
    atrs = price_df["atr"].values
    funding_vals = price_df["funding_rate"].values
    n = len(price_df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []

    for i in range(60, n - WINDOW):
        fr = funding_vals[i]
        atr = atrs[i]
        if pd.isna(fr) or pd.isna(atr): continue

        direction = None
        if fr >= high_thresh:
            direction = "SELL"
        elif fr <= low_thresh:
            direction = "BUY"
        if direction is None: continue

        price = closes[i]
        tp, sl = calc_tp_sl(direction, price, atr)
        if tp is None: continue

        outcome, exit_price = "OPEN", None
        for j in range(i + 1, min(i + WINDOW + 1, n)):
            fh, fl = highs[j], lows[j]
            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= sl: outcome, exit_price = "LOSS", sl; break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= sl: outcome, exit_price = "LOSS", sl; break
        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                   else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']

        results.append({
            "time": price_df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": round(price, 2),
            "funding_rate": round(float(fr), 6),
            "outcome": outcome, "pnl_pct": round(pnl_pct, 4),
        })

    if not results:
        return {"symbol": symbol, "total_trades": 0, "message": "No extreme funding signals found"}

    wins = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total = len(wins) + len(losses)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)

    return {
        "symbol": symbol, "timeframe": price_timeframe, "candles_tested": limit,
        "high_funding_threshold": round(float(high_thresh), 6),
        "low_funding_threshold": round(float(low_thresh), 6),
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
        "recent_trades": results[-10:],
        "note": "Tests funding-rate mean-reversion in isolation (Bybit/OKX funding data, CoinDCX/failover price data).",
    }
