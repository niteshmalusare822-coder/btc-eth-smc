"""
SCALPING BOT — Multi-Factor Engine + Liquidity Concepts Combo  (v2.1 — FIXED)
================================================================
Base engine (EMA/RSI/ADX/Structure/Divergence/VolumeProfile/Regime) +
Liquidity Concepts (BSL/SSL, Sweep, FVG, Inducement, Equal-Level Density).

CHANGES FROM v1 (see comments tagged "# FIX:"):
  1. run_backtest() now applies the SAME regime filter as live decide_direction()
     (previously it only checked ADX/RSI — backtest was looser than live, so
     tuning results from step2_grid_search() were not trustworthy).
  2. run_backtest_full() now requires BOTH 1m and 5m regime == TRENDING
     (previously only checked entry-timeframe regime, and only blocked
     RANGING, not COMPRESSION — so it did NOT actually mirror live despite
     the docstring saying so).
  3. Equal-Level Density (crowded pool) is now its own testable factor in
     run_factor_backtest(), instead of being silently baked into every score
     with unknown standalone edge.
  4. Removed the RSI<35/>65 mean-reversion score bonus from get_ltf_scores()
     and the vectorized equivalents — it was contradicting the trend-following
     ADX-gated framework (decide_direction blocks RSI<30/>70, so encouraging
     RSI<35 entries via score bonus was internally inconsistent).
  5. analyze() no longer double-fetches 1m data when timeframe="1m".
  6. NEW: risk_management section — position sizing by % risk, daily loss
     circuit breaker, leverage sanity check. None of this existed in v1.

CHANGES IN v2.1 (this pass):
  7. FIX: removed a stray duplicate/orphaned dict block sitting right after
     analyze_timeframe()'s return statement — it was outside any bracket and
     caused a SyntaxError on import, so the whole module could not load.
  8. FIX: get_ltf_scores() was missing the calc_liquidity_score(snap) call
     (sweep magnitude, inducement, FVG-proximity, equal-level-density bonus).
     The vectorized backtest path (_ltf_score_series -> score_component ->
     _liquidity_score_vectorized) DOES include this, so live analyze() scores
     were silently lower/different than backtested scores using the same
     SCORE_THRESHOLD/SCORE_GAP_MIN — live and backtest were not apples-to-apples.
     Restored the call so live matches backtest again.

⚠️ Educational / research tool. Not financial advice. No backtest or live
   signal guarantees future profit. Forward-test on paper first, and only
   risk capital you can afford to lose, sized per the risk rules below.
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

COINDCX_RESOLUTION_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
}

CONFIG = {
    'EMA_FAST': 5,
    'EMA_SLOW': 20,
    'RSI_PERIOD': 7,
    'ATR_PERIOD': 14,
    'ADX_PERIOD': 14,
    'ADX_MIN': 20,
    'SWING_LOOKBACK': 3,
    'LIQUIDITY_SWEEP_LOOKBACK': 20,
    'VOLUME_PROFILE_LOOKBACK': 100,
    'VOLUME_PROFILE_BINS': 24,
    'SCORE_THRESHOLD': 6.0,
    'SCORE_GAP_MIN': 4.0,
    'FEE_PCT': 0.04,
    'ATR_COMPRESSION_RATIO': 0.7,
    'ATR_MA_PERIOD': 50,
    'CHOPPINESS_PERIOD': 14,
    'CHOPPINESS_TREND_MAX': 61.8,
    'LIMIT': 150,
    'TP_ATR_MULT': 1.5,   # IMPROVEMENT #6: was 2.0 — take quicker scalp wins
    'SL_ATR_MULT': 0.8,   # IMPROVEMENT #6: was 1.0 — tighter stops for scalping
    'RSI_OVERBOUGHT': 70,
    'RSI_OVERSOLD': 30,
    'BACKTEST_CANDLES': 6000,
    'BACKTEST_OUTCOME_WINDOW': 10,  # IMPROVEMENT #6: was 20 — tighter realistic scalp window

    'FVG_MIN_GAP_PCT': 0.02,
    'BSL_SSL_LOOKBACK': 20,
    'EQUAL_LEVEL_TOLERANCE_PCT': 0.05,
    'INDUCEMENT_MINOR_LOOKBACK': 2,
    'FVG_PROXIMITY_PCT': 0.3,
    'EQUAL_LEVEL_MIN_COUNT': 3,

    # ── NEW: Risk management defaults ─────────────────────────────────
    'RISK_PCT_PER_TRADE': 1.0,      # % of account risked per trade
    'MAX_DAILY_LOSS_PCT': 3.0,      # circuit breaker: stop trading for the day
    'MAX_LEVERAGE': 5,              # sanity cap regardless of exchange max
    'MAX_CONCURRENT_POSITIONS': 2,  # BTC + ETH at most, don't stack more

    # ── NEW: 10 scalping improvements ──────────────────────────────────
    # #1 Slippage-aware backtesting
    'SLIPPAGE_BPS': 2,               # 2 basis points slippage assumption
    'REALISTIC_BACKTEST': True,      # if True, backtests apply slippage to fills

    # #2 Volatility-adaptive position sizing
    'ADAPTIVE_SIZE_HIGH_VOL_RATIO': 1.5,   # atr/recent_atr_avg above this = high-vol
    'ADAPTIVE_SIZE_LOW_VOL_RATIO': 0.7,    # below this = low-vol
    'ADAPTIVE_SIZE_HIGH_VOL_MULT': 0.6,    # shrink size 40% in high vol
    'ADAPTIVE_SIZE_LOW_VOL_MULT': 1.2,     # grow size 20% in low vol

    # #3 Entry confluence filter
    'MIN_CONFLUENCE_SCORE': 5.0,     # minimum weighted confluence to allow entry

    # #7 Prime trading hours (separate from OF_SESSION_* used by order-flow module)
    'PRIME_HOURS_ASIAN_DEAD_START': 0,
    'PRIME_HOURS_ASIAN_DEAD_END': 8,
    'PRIME_HOURS_OVERLAP_START': 8,
    'PRIME_HOURS_OVERLAP_END': 17,
    'PRIME_HOURS_NY_CLOSE_START': 17,
    'PRIME_HOURS_NY_CLOSE_END': 20,

    # #8 Grid-search tuning
    'GRID_MIN_WIN_RATE': 50.0,       # skip tuning configs below this win rate

    # #9 Volume spike / momentum filter
    'VOLUME_SPIKE_LOOKBACK': 20,
    'VOLUME_SPIKE_MULT': 1.5,        # require volume >= 1.5x rolling average

    # #10 Consecutive-loss tilt prevention
    'MAX_CONSECUTIVE_LOSSES': 3,     # pause new trades after this many losses in a row

    # ── NEW: Fabio Valentino order-flow-STYLE proxy settings ──────────────
    # ⚠️ IMPORTANT: fetch_ohlcv() only returns O/H/L/C/Volume candles — it does
    # NOT include real bid/ask tape, delta, or aggression "bubbles" the way a
    # footprint/order-flow platform (Bookmap, ATAS, etc.) does. Everything below
    # is an OHLCV-based APPROXIMATION of order-flow concepts, not the real thing.
    # It's a reasonable proxy for research, but treat it as such.
    'OF_DELTA_LOOKBACK': 20,          # candles used for rolling CVD-proxy slope
    'OF_ABSORPTION_VOL_MULT': 1.8,    # vol > rolling_avg_vol * this = "big order" candle
    'OF_ABSORPTION_BODY_MAX_PCT': 35, # body must be <= this % of candle range to count as absorption
    'OF_VP_LOOKBACK': 100,            # volume profile window for HVN/LVN mapping
    'OF_VP_BINS': 30,
    'OF_LVN_PCTL': 25,                # bins below this volume percentile = Low Volume Node
    'OF_HVN_PCTL': 75,                # bins above this volume percentile = High Volume Node
    'OF_RETEST_TOL_PCT': 0.15,        # % distance to an LVN level counted as "retest"
    'OF_BREAKOUT_LOOKBACK': 20,       # bars used to define the balance range for breakout
    'OF_SECOND_DRIVE_MAX_BARS': 12,   # max bars allowed between breakout and retest
    'OF_SQUEEZE_ATR_MULT': 1.5,       # candle range vs ATR to qualify as a "squeeze" acceleration bar
    'OF_SQUEEZE_VOL_MULT': 1.5,       # volume vs rolling avg to qualify as squeeze
    'OF_BREAKEVEN_TRIGGER_ATR_MULT': 0.5,  # move SL to break-even after price moves this many ATR in favor
    'OF_SL_BUFFER_TICKS_PCT': 0.03,   # extra % buffer beyond swing high/low, proxy for "1-2 ticks" buffer
    'OF_RISK_BASE_PCT': 0.25,         # base risk % of equity per trade (Fabio: 0.25-0.5%)
    'OF_RISK_HOUSE_MONEY_PCT': 0.50,  # risk % once trading with today's banked profit ("house money")
    'OF_SESSION_NY_START_UTC': 13,    # New York session ~ 13:30-20:00 UTC (rounded to hour here)
    'OF_SESSION_NY_END_UTC': 20,
    'OF_SESSION_LDN_START_UTC': 7,    # London session ~ 07:00-16:00 UTC
    'OF_SESSION_LDN_END_UTC': 16,
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
    params = {"pair": pair, "from": from_time, "to": to_time, "resolution": resolution, "pcode": "f"}

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
            o = c.get("open", c.get("o")); h = c.get("high", c.get("h"))
            l = c.get("low", c.get("l")); cl = c.get("close", c.get("c"))
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


# ── Base Indicators ─────────────────────────────────────────────────────
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
    current_atr = atr.iloc[-1]; current_atr_ma = atr_ma.iloc[-1]
    current_ci = ci.iloc[-1]; current_adx = adx.iloc[-1]
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


# ── Structure / Patterns ─────────────────────────────────────────────────
def detect_structure_live_pro(df, lookback=3):
    df = df.copy()
    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    events, trends = [None] * n, [None] * n
    trend = None
    last_swing_high = last_swing_low = None
    for i in range(lookback * 2, n):
        lh = highs[i - 2 * lookback:i - lookback]; rh = highs[i - lookback + 1:i + 1]
        ll = lows[i - 2 * lookback:i - lookback]; rl = lows[i - lookback + 1:i + 1]
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
    uw = h - np.maximum(o, c); lw = np.minimum(o, c) - l
    df["pat_sig"] = ""
    hammer = (tr > 0) & (lw >= 2 * b) & (uw <= 0.3 * b) & (b >= 0.1 * tr)
    star = (tr > 0) & (uw >= 2 * b) & (lw <= 0.3 * b) & (b >= 0.1 * tr)
    bull_eng = (pc < po) & (c > o) & (o < pc) & (c > po)
    bear_eng = (pc > po) & (c < o) & (o > pc) & (c < po)
    df.loc[hammer, "pat_sig"] = "BUY"; df.loc[star, "pat_sig"] = "SELL"
    df.loc[bull_eng, "pat_sig"] = "BUY"; df.loc[bear_eng, "pat_sig"] = "SELL"
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
    data = df.tail(CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    if len(data) < 5: return None
    last = data.iloc[-1]
    p_highs = data["high"].iloc[:-1]; p_lows = data["low"].iloc[:-1]
    if last["high"] > p_highs.max() and last["close"] < p_highs.max(): return "EQUAL_HIGH_SWEEP"
    if last["low"] < p_lows.min() and last["close"] > p_lows.min(): return "EQUAL_LOW_SWEEP"
    return None

def detect_liquidity_sweep_vectorized(df, lookback=20):
    high, low, close = df["high"], df["low"], df["close"]
    roll_high_prior = high.shift(1).rolling(lookback - 1).max()
    roll_low_prior = low.shift(1).rolling(lookback - 1).min()
    sweep = pd.Series('', index=df.index)
    bsl_sweep = (high > roll_high_prior) & (close < roll_high_prior)
    ssl_sweep = (low < roll_low_prior) & (close > roll_low_prior)
    sweep[bsl_sweep] = 'EQUAL_HIGH_SWEEP'; sweep[ssl_sweep] = 'EQUAL_LOW_SWEEP'
    return sweep


# ── Liquidity Concepts ────────────────────────────────────────────────────
def detect_fvg_vectorized(df, min_gap_pct=0.02):
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    bull_gap = low - high.shift(2); bear_gap = low.shift(2) - high
    bull_mask = (bull_gap > 0) & (bull_gap / close * 100 >= min_gap_pct)
    bear_mask = (bear_gap > 0) & (bear_gap / close * 100 >= min_gap_pct)
    df["fvg"] = ""; df["fvg_top"] = np.nan; df["fvg_bottom"] = np.nan
    df.loc[bull_mask, "fvg"] = "BULL_FVG"
    df.loc[bull_mask, "fvg_top"] = low[bull_mask]
    df.loc[bull_mask, "fvg_bottom"] = high.shift(2)[bull_mask]
    df.loc[bear_mask, "fvg"] = "BEAR_FVG"
    df.loc[bear_mask, "fvg_top"] = low.shift(2)[bear_mask]
    df.loc[bear_mask, "fvg_bottom"] = high[bear_mask]
    return df

def compute_active_fvg_series(df, min_gap_pct=0.02):
    df = detect_fvg_vectorized(df, min_gap_pct)
    n = len(df)
    close = df["close"].values; fvg = df["fvg"].values
    fvg_top = df["fvg_top"].values; fvg_bottom = df["fvg_bottom"].values
    active_bull = None; active_bear = None
    dist_bull = np.full(n, np.nan); dist_bear = np.full(n, np.nan)
    for i in range(n):
        if fvg[i] == "BULL_FVG": active_bull = (fvg_top[i], fvg_bottom[i])
        if fvg[i] == "BEAR_FVG": active_bear = (fvg_top[i], fvg_bottom[i])
        c = close[i]
        if active_bull is not None:
            _, bottom = active_bull
            if c < bottom: active_bull = None
            else: dist_bull[i] = (c - bottom) / c * 100
        if active_bear is not None:
            top, _ = active_bear
            if c > top: active_bear = None
            else: dist_bear[i] = (top - c) / c * 100
    df["dist_to_bull_fvg_pct"] = dist_bull
    df["dist_to_bear_fvg_pct"] = dist_bear
    return df

def detect_bsl_ssl_zones(df, lookback=20):
    df = df.copy()
    df["bsl_level"] = df["high"].rolling(lookback).max()
    df["ssl_level"] = df["low"].rolling(lookback).min()
    df["dist_to_bsl_pct"] = (df["bsl_level"] - df["close"]) / df["close"] * 100
    df["dist_to_ssl_pct"] = (df["close"] - df["ssl_level"]) / df["close"] * 100
    return df

def calc_equal_level_density(df, lookback=20, tol_pct=0.05):
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
    buy, sell = 0.0, 0.0
    if snap.get("sweep") == "EQUAL_LOW_SWEEP": buy += 2.5
    elif snap.get("sweep") == "EQUAL_HIGH_SWEEP": sell += 2.5
    if snap.get("inducement") == "BULL_INDUCEMENT": buy += 2.0
    elif snap.get("inducement") == "BEAR_INDUCEMENT": sell += 2.0
    dbull = snap.get("dist_to_bull_fvg_pct"); dbear = snap.get("dist_to_bear_fvg_pct")
    if dbull is not None and not pd.isna(dbull) and 0 <= dbull <= CONFIG['FVG_PROXIMITY_PCT']: buy += 1.5
    if dbear is not None and not pd.isna(dbear) and 0 <= dbear <= CONFIG['FVG_PROXIMITY_PCT']: sell += 1.5
    eqh = snap.get("eq_high_count") or 0; eql = snap.get("eq_low_count") or 0
    if snap.get("sweep") == "EQUAL_LOW_SWEEP" and eql >= CONFIG['EQUAL_LEVEL_MIN_COUNT']: buy += 1.0
    if snap.get("sweep") == "EQUAL_HIGH_SWEEP" and eqh >= CONFIG['EQUAL_LEVEL_MIN_COUNT']: sell += 1.0
    return buy, sell

def _liquidity_score_vectorized(df, w=1.0):
    buy = pd.Series(0.0, index=df.index); sell = pd.Series(0.0, index=df.index)
    buy += np.where(df["sweep_v"] == "EQUAL_LOW_SWEEP", 2.5 * w, 0.0)
    sell += np.where(df["sweep_v"] == "EQUAL_HIGH_SWEEP", 2.5 * w, 0.0)
    buy += np.where(df["inducement"] == "BULL_INDUCEMENT", 2.0 * w, 0.0)
    sell += np.where(df["inducement"] == "BEAR_INDUCEMENT", 2.0 * w, 0.0)
    dbull = df["dist_to_bull_fvg_pct"]; dbear = df["dist_to_bear_fvg_pct"]
    buy += np.where((dbull >= 0) & (dbull <= CONFIG['FVG_PROXIMITY_PCT']), 1.5 * w, 0.0)
    sell += np.where((dbear >= 0) & (dbear <= CONFIG['FVG_PROXIMITY_PCT']), 1.5 * w, 0.0)
    eqh = df["eq_high_count"].fillna(0); eql = df["eq_low_count"].fillna(0)
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
        "structure_event": last["structure_event"], "structure_trend": last["structure_trend"],
        "adx": last["adx"], "price": last["close"], "vwap": last["vwap"],
        "volume": last["volume"],  # <-- Volatility acceleration trace karne ke liye line add ki
        "ema5": last["ema5"], "ema20": last["ema20"], "rsi": last["rsi"], "atr": last["atr"],
        "pattern": last["pat_sig"], "divergence": last["divergence"],
        "sweep": sweep, "vp": vp, "regime": regime,
        "fvg": last["fvg"],
        "dist_to_bull_fvg_pct": last["dist_to_bull_fvg_pct"],
        "dist_to_bear_fvg_pct": last["dist_to_bear_fvg_pct"],
        "bsl_level": last["bsl_level"], "ssl_level": last["ssl_level"],
        "dist_to_bsl_pct": last["dist_to_bsl_pct"], "dist_to_ssl_pct": last["dist_to_ssl_pct"],
        "eq_high_count": last["eq_high_count"], "eq_low_count": last["eq_low_count"],
        "inducement": last["inducement"],
    }
    # FIX #7: removed a stray duplicate dict block that was sitting here,
    # outside the function's return statement / outside any bracket. It was
    # a leftover copy-paste of the same keys and caused a SyntaxError on
    # import, which meant the entire module failed to load.


def get_htf_bias(snap_15m):
    weight = 1.0; score = 0.0
    if snap_15m["structure_trend"] == "BULL": score += weight
    elif snap_15m["structure_trend"] == "BEAR": score -= weight
    score += weight * 0.5 if snap_15m["ema5"] > snap_15m["ema20"] else -weight * 0.5
    if not pd.isna(snap_15m["rsi"]):
        if snap_15m["rsi"] > 55: score += weight * 0.3
        elif snap_15m["rsi"] < 45: score -= weight * 0.3
    if snap_15m.get("sweep") == "EQUAL_LOW_SWEEP": score += 0.5
    elif snap_15m.get("sweep") == "EQUAL_HIGH_SWEEP": score -= 0.5
    if snap_15m.get("inducement") == "BULL_INDUCEMENT": score += 0.3
    elif snap_15m.get("inducement") == "BEAR_INDUCEMENT": score -= 0.3
    if score >= 0.9: return "BULLISH"
    if score <= -0.9: return "BEARISH"
    return "NEUTRAL"

# FIX #4: removed RSI<35/>65 mean-reversion score bonus (contradicted the
# ADX-gated trend-following filter in decide_direction, which blocks
# RSI<30/>70 trades). Score now stays purely trend/structure/liquidity based.
# FIX #8: restored calc_liquidity_score(snap) call — this was missing here,
# so live scores were not including sweep/inducement/FVG-proximity/equal-level
# bonuses that the vectorized backtest path DOES include. Without this, live
# analyze() and run_backtest()/run_backtest_full() used different scoring
# formulas even though they share the same SCORE_THRESHOLD/SCORE_GAP_MIN.
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
        # RSI mean-reversion bonus removed here (FIX #4)

        # FIX #8: RESTORED — liquidity score (sweep magnitude, inducement,
        # FVG proximity, equal-level density). This makes live scoring
        # consistent with the vectorized backtest's _liquidity_score_vectorized().
        liq_buy, liq_sell = calc_liquidity_score(snap)
        buy_score += liq_buy * w
        sell_score += liq_sell * w

        # 🔥 Scalper Acceleration Boost (kept from your latest edit):
        if "volume" in snap and not pd.isna(snap["vwap"]):
            # Agar price trend ke sath vwap se door bhaag raha hai (Fast Momentum)
            if snap["price"] > snap["vwap"] and snap["ema5"] > snap["ema20"]:
                buy_score += 1.0 * w
            elif snap["price"] <= snap["vwap"] and snap["ema5"] <= snap["ema20"]:
                sell_score += 1.0 * w

    return round(buy_score, 2), round(sell_score, 2)

# IMPROVEMENT #3: Entry confluence filter — the base score system uses many
# lightweight 0.5-weight factors that can add up without any single strong
# signal. This counts only the STRONG factors (structure break, divergence,
# sweep+density combo, pattern, EMA alignment across both timeframes) and
# requires a minimum weighted confluence before an entry is allowed.
def calc_confluence_score(snap_1m, snap_5m):
    confluence = 0.0

    if snap_1m["pattern"] == "BUY" or snap_1m["pattern"] == "SELL":
        confluence += 2

    if snap_1m["structure_event"] in ("CHoCH_BULL", "BOS_BULL", "CHoCH_BEAR", "BOS_BEAR"):
        confluence += 3

    if snap_1m["divergence"] in ("BULL_DIV", "BEAR_DIV"):
        confluence += 2.5

    if (snap_1m["sweep"] == "EQUAL_LOW_SWEEP" and (snap_1m.get("eq_low_count") or 0) >= 3) or \
       (snap_1m["sweep"] == "EQUAL_HIGH_SWEEP" and (snap_1m.get("eq_high_count") or 0) >= 3):
        confluence += 3

    ema_1m_up = snap_1m["ema5"] > snap_1m["ema20"]
    ema_5m_up = snap_5m["ema5"] > snap_5m["ema20"]
    if ema_1m_up == ema_5m_up:
        confluence += 1.5

    return round(confluence, 2)


def decide_direction(buy_score, sell_score, htf_bias, entry_adx, regime_1m, regime_5m,
                      entry_rsi=None, snap_1m=None, snap_5m=None):
    if pd.isna(entry_adx) or entry_adx < CONFIG['ADX_MIN']:
        return None, f"NO TREND (ADX {entry_adx:.1f} < {CONFIG['ADX_MIN']})"
    if entry_rsi is not None and not pd.isna(entry_rsi):
        if entry_rsi > CONFIG['RSI_OVERBOUGHT']:
            return None, f"BLOCKED (RSI overbought {entry_rsi:.1f})"
        if entry_rsi < CONFIG['RSI_OVERSOLD']:
            return None, f"BLOCKED (RSI oversold {entry_rsi:.1f})"
    is_1m_comp = regime_1m["regime"] == "COMPRESSION"
    is_5m_comp = regime_5m["regime"] == "COMPRESSION"

    # PRO ENGINE BREAKOUT BYPASS: 5m compressed zone se 1m volatility trigger track karna
    if is_5m_comp and not is_1m_comp and entry_adx > CONFIG['ADX_MIN']:
        if buy_score >= CONFIG['SCORE_THRESHOLD'] + 0.5 and htf_bias in ("BULLISH", "NEUTRAL"):
            return "BUY", "COMPRESSION BREAKOUT LONG 🚀"
        if sell_score >= CONFIG['SCORE_THRESHOLD'] + 0.5 and htf_bias in ("BEARISH", "NEUTRAL"):
            return "SELL", "COMPRESSION BREAKOUT SHORT 🩸"

    # Jab tak box squeeze true trap state mein hai tabhi filter open hoga
    if is_1m_comp and is_5m_comp:
        return None, "BLOCKED (Tight Squeeze Range)"

    if regime_1m["regime"] == "RANGING" or regime_5m["regime"] == "RANGING":
        return None, f"BLOCKED (Choppy Flat Zones)"

    if regime_1m["regime"] != "TRENDING" or regime_5m["regime"] != "TRENDING":
        return None, "BLOCKED (Not Dynamic Trending Structure)"

    # IMPROVEMENT #3: confluence gate (only enforced when snaps are provided,
    # so existing callers that don't pass snaps keep their old behavior).
    confluence_score = None
    if snap_1m is not None and snap_5m is not None:
        confluence_score = calc_confluence_score(snap_1m, snap_5m)
        if confluence_score < CONFIG['MIN_CONFLUENCE_SCORE']:
            return None, f"BLOCKED (Low confluence {confluence_score:.1f} < {CONFIG['MIN_CONFLUENCE_SCORE']})"

    if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
        if (buy_score - sell_score) >= CONFIG['SCORE_GAP_MIN'] and htf_bias in ("BULLISH", "NEUTRAL"):
            return "BUY", "BUY ✅" + (f" (confluence {confluence_score:.1f})" if confluence_score is not None else "")
    if sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
        if (sell_score - buy_score) >= CONFIG['SCORE_GAP_MIN'] and htf_bias in ("BEARISH", "NEUTRAL"):
            return "SELL", "SELL ✅" + (f" (confluence {confluence_score:.1f})" if confluence_score is not None else "")
    return None, "WAIT (score/bias aligned nahi)"


# IMPROVEMENT #5: Intra-trade early exit — don't blindly hold to SL if the
# setup that justified the trade has broken down. Call this periodically
# while a position is open, passing the CURRENT snap and the snap captured
# AT ENTRY (analyze_timeframe() output for both).
def should_exit_early(snap_current, snap_entry, direction):
    if direction == "BUY" and snap_current["ema5"] <= snap_current["ema20"]:
        if snap_entry["ema5"] > snap_entry["ema20"]:
            return True, "EMA structure reversed"
    if direction == "SELL" and snap_current["ema5"] >= snap_current["ema20"]:
        if snap_entry["ema5"] < snap_entry["ema20"]:
            return True, "EMA structure reversed"

    if snap_current["regime"]["regime"] == "RANGING":
        return True, "Regime changed to RANGING"

    if direction == "BUY" and snap_current["divergence"] == "BEAR_DIV":
        return True, "Bearish divergence formed"
    if direction == "SELL" and snap_current["divergence"] == "BULL_DIV":
        return True, "Bullish divergence formed"

    return False, None


# IMPROVEMENT #7: Prime trading hours filter — scalping dies during the
# Asian low-volume window. Blocks trades outside NY/London active hours.
def is_prime_trading_hours(now_utc=None):
    from datetime import datetime, timezone
    utc_hour = (now_utc or datetime.now(timezone.utc)).hour

    if CONFIG['PRIME_HOURS_ASIAN_DEAD_START'] <= utc_hour < CONFIG['PRIME_HOURS_ASIAN_DEAD_END']:
        return False, "Asian dead zone (low volume)"
    if CONFIG['PRIME_HOURS_OVERLAP_START'] <= utc_hour < CONFIG['PRIME_HOURS_OVERLAP_END']:
        return True, "Prime overlap (London+NY)"
    if CONFIG['PRIME_HOURS_NY_CLOSE_START'] <= utc_hour < CONFIG['PRIME_HOURS_NY_CLOSE_END']:
        return True, "NY session"
    return False, "After hours"

def calc_tp_sl(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    sl_dist = round(CONFIG['SL_ATR_MULT'] * atr, 4)
    tp_dist = round(CONFIG['TP_ATR_MULT'] * atr, 4)
    if direction == "BUY":
        return round(price + tp_dist, 4), round(price - sl_dist, 4)
    return round(price - tp_dist, 4), round(price + sl_dist, 4)


# IMPROVEMENT #1: Slippage-aware TP/SL — real scalping fills are never
# exactly at the TP/SL price. This pulls TP in and pushes SL out by an
# assumed slippage amount so backtest results aren't overly optimistic.
def calc_tp_sl_with_slippage(direction, price, atr, slippage_bps=None):
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    slippage_bps = slippage_bps if slippage_bps is not None else CONFIG['SLIPPAGE_BPS']
    sl_dist = round(CONFIG['SL_ATR_MULT'] * atr, 4)
    tp_dist = round(CONFIG['TP_ATR_MULT'] * atr, 4)
    slippage_amt = price * (slippage_bps / 10000)

    if direction == "BUY":
        tp = round(price + tp_dist - slippage_amt, 4)   # TP pulled back (worse fill)
        sl = round(price - sl_dist - slippage_amt, 4)   # SL pushed further away (worse fill)
    else:
        tp = round(price - tp_dist + slippage_amt, 4)
        sl = round(price + sl_dist + slippage_amt, 4)
    return tp, sl


# IMPROVEMENT #9: Volume spike / momentum filter — scalpers need genuine
# participation behind a move. Flags bars where volume is well above its
# recent rolling average.
def detect_volume_spike(df, lookback=None, multiplier=None):
    lookback = lookback or CONFIG['VOLUME_SPIKE_LOOKBACK']
    multiplier = multiplier or CONFIG['VOLUME_SPIKE_MULT']
    avg_vol = df["volume"].rolling(lookback).mean()
    vol_ratio = df["volume"] / (avg_vol + 1e-10)
    return vol_ratio >= multiplier


# IMPROVEMENT #4: Partial profit-taking — instead of one TP, scale out at
# three levels (50% / 30% / 20%) so gains are locked progressively instead
# of an all-or-nothing single target.
def calc_tp_sl_scaled(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None
    sl_dist = round(CONFIG['SL_ATR_MULT'] * atr, 4)
    tp_base = round(CONFIG['TP_ATR_MULT'] * atr, 4)

    if direction == "BUY":
        sl = round(price - sl_dist, 4)
        tp1 = round(price + tp_base * 0.5, 4)    # 50% closed here
        tp2 = round(price + tp_base * 0.75, 4)   # 30% closed here
        tp3 = round(price + tp_base, 4)          # 20% rides to full target
    else:
        sl = round(price + sl_dist, 4)
        tp1 = round(price - tp_base * 0.5, 4)
        tp2 = round(price - tp_base * 0.75, 4)
        tp3 = round(price - tp_base, 4)

    return {"sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "tp1_pct": 50, "tp2_pct": 30, "tp3_pct": 20}


import time as _time

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

_LTF_CACHE = {}
_LTF_CACHE_TTL = 15

# BUGFIX: previously every call to analyze() — regardless of the requested
# entry timeframe — scored off a fixed 1m+5m pair cached PER SYMBOL (not per
# timeframe). That meant the "15m" and "1h" dashboard cards showed the exact
# same buy_score/sell_score as the "5m" card, because they all read the same
# stale symbol-level cache entry. This maps each entry timeframe to its own
# "confirmation" timeframe one step up, and caches per (symbol, timeframe)
# so every card genuinely reflects its own timeframe's data.
TIMEFRAME_CONFIRM_MAP = {
    "1m": "5m",
    "5m": "15m",
    "15m": "1h",
    "1h": "4h",
}

def _get_ltf_snaps_cached(symbol, timeframe="1m", preloaded_entry_snap=None):
    now = _time.time()
    confirm_tf = TIMEFRAME_CONFIRM_MAP.get(timeframe, "5m")
    cache_key = (symbol, timeframe)
    cached = _LTF_CACHE.get(cache_key)
    if cached and (now - cached["ts"]) < _LTF_CACHE_TTL:
        return cached["snap_entry"], cached["snap_confirm"]

    # If caller already fetched+analyzed the entry timeframe, reuse it
    # instead of hitting the API again.
    if preloaded_entry_snap is not None:
        snap_entry_tf = preloaded_entry_snap
    else:
        df_entry_tf, _ = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
        snap_entry_tf = analyze_timeframe(df_entry_tf) if df_entry_tf is not None else None

    df_confirm, _ = fetch_ohlcv_failover(symbol, confirm_tf, CONFIG['LIMIT'])
    snap_confirm = analyze_timeframe(df_confirm) if df_confirm is not None else None

    _LTF_CACHE[cache_key] = {"snap_entry": snap_entry_tf, "snap_confirm": snap_confirm, "ts": now}
    return snap_entry_tf, snap_confirm


def analyze(symbol, timeframe="1m"):
    df_entry, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
    if df_entry is None:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}

    snap_entry = analyze_timeframe(df_entry)
    price = float(snap_entry["price"])
    rsi_now = float(snap_entry["rsi"]) if not pd.isna(snap_entry["rsi"]) else None
    atr_now = float(snap_entry["atr"]) if not pd.isna(snap_entry["atr"]) else None

    htf_bias = _get_htf_bias_cached(symbol)

    # BUGFIX: pass snap_entry through so we don't re-fetch the entry
    # timeframe's data, and fetch its own confirmation timeframe (one
    # step up) instead of always reusing a fixed 1m/5m pair. This makes
    # each entry timeframe's score genuinely reflect that timeframe.
    snap_entry_tf, snap_confirm = _get_ltf_snaps_cached(
        symbol, timeframe=timeframe, preloaded_entry_snap=snap_entry
    )
    if snap_entry_tf is None: snap_entry_tf = snap_entry
    if snap_confirm is None: snap_confirm = snap_entry

    # IMPROVEMENT #7: skip entries outside prime NY/London hours
    prime_ok, prime_reason = is_prime_trading_hours()
    if not prime_ok:
        return {
            "symbol": symbol, "timeframe": timeframe, "price": round(price, 4),
            "signal": "WAIT", "reason": f"BLOCKED ({prime_reason})",
        }

    buy_score, sell_score = get_ltf_scores(snap_entry_tf, snap_confirm)
    direction, reason = decide_direction(
        buy_score, sell_score, htf_bias, snap_entry["adx"],
        snap_entry_tf["regime"], snap_confirm["regime"], entry_rsi=rsi_now,
        snap_1m=snap_entry_tf, snap_5m=snap_confirm,  # IMPROVEMENT #3: confluence gate
    )

    # IMPROVEMENT #9: require a volume spike behind the move, not just a low-volume drift
    if direction is not None:
        vol_spike_series = detect_volume_spike(df_entry)
        if not bool(vol_spike_series.iloc[-1]):
            direction, reason = None, f"BLOCKED (No volume spike confirming {reason})"

    signal = direction if direction else "WAIT"
    if CONFIG['REALISTIC_BACKTEST']:
        tp, sl = calc_tp_sl_with_slippage(direction, price, atr_now)  # IMPROVEMENT #1
    else:
        tp, sl = calc_tp_sl(direction, price, atr_now)
    tp_levels = calc_tp_sl_scaled(direction, price, atr_now) if direction else None  # IMPROVEMENT #4

    return {
        "symbol": symbol, "timeframe": timeframe, "price": round(price, 4),
        "rsi": round(rsi_now, 2) if rsi_now is not None else None,
        "signal": signal, "reason": reason,
        "buy_score": buy_score, "sell_score": sell_score, "htf_bias": htf_bias,
        "regime": snap_entry["regime"]["regime"], "structure": snap_entry["structure_event"],
        "exchange": ex_id, "entry": round(price, 4) if direction else None,
        "tp": tp, "sl": sl, "atr": round(atr_now, 4) if atr_now else None,
        "tp_levels": tp_levels,  # IMPROVEMENT #4: partial profit-taking (50/30/20)
        "liquidity": {
            "sweep": snap_entry["sweep"], "fvg": snap_entry["fvg"],
            "dist_to_bull_fvg_pct": round(snap_entry["dist_to_bull_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bull_fvg_pct"]) else None,
            "dist_to_bear_fvg_pct": round(snap_entry["dist_to_bear_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bear_fvg_pct"]) else None,
            "bsl_level": round(snap_entry["bsl_level"], 4) if not pd.isna(snap_entry["bsl_level"]) else None,
            "ssl_level": round(snap_entry["ssl_level"], 4) if not pd.isna(snap_entry["ssl_level"]) else None,
            "eq_high_count": snap_entry["eq_high_count"], "eq_low_count": snap_entry["eq_low_count"],
            "inducement": snap_entry["inducement"],
        },
    }


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
    weight = 1.0
    s = pd.Series(0.0, index=df15.index)
    s += np.where(df15["structure_trend"] == "BULL", weight, np.where(df15["structure_trend"] == "BEAR", -weight, 0.0))
    s += np.where(df15["ema5"] > df15["ema20"], weight * 0.5, -weight * 0.5)
    s += np.where(df15["rsi"] > 55, weight * 0.3, np.where(df15["rsi"] < 45, -weight * 0.3, 0.0))
    s += np.where(df15["sweep_v"] == "EQUAL_LOW_SWEEP", 0.5, np.where(df15["sweep_v"] == "EQUAL_HIGH_SWEEP", -0.5, 0.0))
    s += np.where(df15["inducement"] == "BULL_INDUCEMENT", 0.3, np.where(df15["inducement"] == "BEAR_INDUCEMENT", -0.3, 0.0))
    bias = np.where(s >= 0.9, "BULLISH", np.where(s <= -0.9, "BEARISH", "NEUTRAL"))
    return pd.Series(bias, index=df15.index, name="bias")

# FIX #4 applied here too: removed RSI mean-reversion bonus from vectorized scorer
def _ltf_score_series(df1m, df5m):
    def score_component(df, w):
        buy = pd.Series(0.0, index=df.index); sell = pd.Series(0.0, index=df.index)
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
        # RSI mean-reversion bonus removed (FIX #4)
        liq_b, liq_s = _liquidity_score_vectorized(df, w)
        buy += liq_b; sell += liq_s
        return buy, sell

    b1, s1 = score_component(df1m, 1.0)
    b5, s5 = score_component(df5m, 1.2)
    out1m = pd.DataFrame({"time": df1m.index, "b1": b1.values, "s1": s1.values})
    out5m = pd.DataFrame({"time": df5m.index, "b5": b5.values, "s5": s5.values})
    merged = pd.merge_asof(out1m.sort_values("time"), out5m.sort_values("time"), on="time", direction="backward")
    merged["buy_score"] = round((merged["b1"] + merged["b5"]), 2)
    merged["sell_score"] = round((merged["s1"] + merged["s5"]), 2)
    merged = merged.set_index("time")
    return merged[["buy_score", "sell_score"]]

# FIX #2: this now genuinely mirrors decide_direction() — both 1m AND 5m
# regime must be TRENDING (COMPRESSION and RANGING both block), matching live.
def run_backtest_full(symbol, entry_timeframe="5m"):
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

    # FIX #2: align BOTH 1m and 5m regime labels onto entry timeframe index
    regime_1m_series = df_1m[["regime_label"]].rename(columns={"regime_label": "regime_1m"})
    regime_5m_series = df_5m[["regime_label"]].rename(columns={"regime_label": "regime_5m"})

    entry_times = pd.DataFrame({"time": df_entry.index})
    bias_aligned = pd.merge_asof(entry_times, bias_series.rename("bias").reset_index(), on="time", direction="backward")
    score_aligned = pd.merge_asof(entry_times, score_df.reset_index(), on="time", direction="backward")
    regime1_aligned = pd.merge_asof(entry_times, regime_1m_series.reset_index().rename(columns={"timestamp": "time"}), on="time", direction="backward")
    regime5_aligned = pd.merge_asof(entry_times, regime_5m_series.reset_index().rename(columns={"timestamp": "time"}), on="time", direction="backward")

    df_entry = df_entry.reset_index()
    df_entry["bias"] = bias_aligned["bias"]
    df_entry["buy_score"] = score_aligned["buy_score"]
    df_entry["sell_score"] = score_aligned["sell_score"]
    df_entry["regime_1m"] = regime1_aligned["regime_1m"]
    df_entry["regime_5m"] = regime5_aligned["regime_5m"]

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

        # FIX #2: both timeframes must be TRENDING, exactly like decide_direction()
        if row["regime_1m"] != "TRENDING" or row["regime_5m"] != "TRENDING":
            continue

        bias = row["bias"]
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
        "note": "FIXED v2: now requires BOTH 1m and 5m regime==TRENDING, matching live decide_direction() exactly.",
    }


# FIX #1: run_backtest() (fast single-timeframe) now applies the regime
# filter so it's no longer looser than live. Previously only ADX+RSI gated it.
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
    regime_series, _, _ = _vectorized_regime(df)  # FIX #1
    df["regime_label"] = regime_series
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
        rsi = df["rsi"].iloc[i]; adx = df["adx"].iloc[i]; atr = df["atr"].iloc[i]
        ema5 = df["ema5"].iloc[i]; ema20 = df["ema20"].iloc[i]; vwap = df["vwap"].iloc[i]
        pat = df["pat_sig"].iloc[i]; div = df["divergence"].iloc[i]; struct = df["structure_event"].iloc[i]
        price = closes[i]

        if pd.isna(adx) or adx < CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > CONFIG['RSI_OVERBOUGHT'] or rsi < CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue
        if df["regime_label"].iloc[i] != "TRENDING": continue  # FIX #1

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
        # RSI mean-reversion bonus removed (FIX #4)

        buy_score += df["liq_buy"].iloc[i]
        sell_score += df["liq_sell"].iloc[i]

        gap = abs(buy_score - sell_score)
        if gap < CONFIG['SCORE_GAP_MIN']: continue

        direction = None
        if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score: direction = "BUY"
        elif sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score: direction = "SELL"
        if direction is None: continue

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
        "note": "FIXED v2: now requires regime==TRENDING, matching live filter (was missing in v1).",
    }


# ── Factor isolation backtest — includes Equal-Level Density (FIX #3) ─
def run_factor_backtest(symbol, timeframe="5m"):
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
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])  # FIX #3

    closes = df["close"].values; highs = df["high"].values; lows = df["low"].values
    n = len(df); WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

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
        return {"label": label, "total_trades": total, "wins": len(wins), "losses": len(losses),
                "win_rate": win_rate, "profit_factor": profit_factor, "expectancy_pct": expectancy}

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
        dbull = df["dist_to_bull_fvg_pct"].iloc[i]; dbear = df["dist_to_bear_fvg_pct"].iloc[i]
        if not pd.isna(dbull) and 0 <= dbull <= CONFIG['FVG_PROXIMITY_PCT']: return "BUY"
        if not pd.isna(dbear) and 0 <= dbear <= CONFIG['FVG_PROXIMITY_PCT']: return "SELL"
        return None

    def f_inducement(i):
        ind = df["inducement"].iloc[i]
        if ind == "BULL_INDUCEMENT": return "BUY"
        if ind == "BEAR_INDUCEMENT": return "SELL"
        return None

    # FIX #3: new standalone factor — crowded equal-high/low pool without a
    # sweep signal itself; tests whether density alone (not the sweep) has edge.
    def f_equal_level_density(i):
        eqh = df["eq_high_count"].iloc[i] or 0
        eql = df["eq_low_count"].iloc[i] or 0
        if pd.isna(eqh) or pd.isna(eql): return None
        if eql >= CONFIG['EQUAL_LEVEL_MIN_COUNT'] and eql > eqh: return "BUY"
        if eqh >= CONFIG['EQUAL_LEVEL_MIN_COUNT'] and eqh > eql: return "SELL"
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
            simulate(f_equal_level_density, "8. Equal-Level Density only (NEW)"),
        ]
    }


# ══════════════════════════════════════════════════════════════════════════
# RISK MANAGEMENT MODULE
# ══════════════════════════════════════════════════════════════════════════
class RiskManager:
    """
    Tracks daily P&L in-memory and enforces:
      - position sizing based on a fixed % risk per trade
      - a daily loss circuit breaker (stop suggesting new trades for the day)
      - a leverage sanity cap
      - a max concurrent positions cap
    This does NOT place orders — it only computes sizes and yes/no gates.
    You still execute manually (or wire this into your own order logic).
    """
    def __init__(self, account_capital_usdt):
        self.capital = account_capital_usdt
        self.daily_pnl_pct = 0.0
        self.trades_today = []
        self.open_positions = 0

    def reset_day(self):
        self.daily_pnl_pct = 0.0
        self.trades_today = []

    def record_trade_result(self, pnl_pct_of_capital):
        """Call after a trade closes. pnl_pct_of_capital = pnl in % of total account capital."""
        self.daily_pnl_pct += pnl_pct_of_capital
        self.trades_today.append(pnl_pct_of_capital)

    def circuit_breaker_tripped(self):
        return self.daily_pnl_pct <= -abs(CONFIG['MAX_DAILY_LOSS_PCT'])

    def can_open_new_position(self):
        if self.circuit_breaker_tripped():
            return False, f"Daily loss limit hit ({self.daily_pnl_pct:.2f}% <= -{CONFIG['MAX_DAILY_LOSS_PCT']}%). No more trades today."
        if self.open_positions >= CONFIG['MAX_CONCURRENT_POSITIONS']:
            return False, f"Max concurrent positions ({CONFIG['MAX_CONCURRENT_POSITIONS']}) already open."
        return True, "OK"

    def position_size(self, entry_price, sl_price, leverage=1):
        """
        Returns qty (in base asset units, e.g. BTC) sized so that if SL hits,
        loss = RISK_PCT_PER_TRADE % of account capital. Ignores fees/slippage
        (add a buffer yourself, e.g. size slightly smaller than this).
        """
        leverage = min(leverage, CONFIG['MAX_LEVERAGE'])
        risk_amount_usdt = self.capital * (CONFIG['RISK_PCT_PER_TRADE'] / 100)
        sl_distance = abs(entry_price - sl_price)
        if sl_distance <= 0:
            return {"error": "invalid SL distance"}
        qty = risk_amount_usdt / sl_distance
        notional = qty * entry_price
        margin_required = notional / leverage
        return {
            "qty": round(qty, 6),
            "notional_usdt": round(notional, 2),
            "margin_required_usdt": round(margin_required, 2),
            "leverage_used": leverage,
            "risk_amount_usdt": round(risk_amount_usdt, 2),
            "risk_pct_of_capital": CONFIG['RISK_PCT_PER_TRADE'],
        }

    def evaluate_signal(self, signal_dict, leverage=1):
        """
        Convenience wrapper: takes the dict returned by analyze() and returns
        whether to take it + suggested sizing, respecting the circuit breaker.
        """
        ok, reason = self.can_open_new_position()
        if not ok:
            return {"take_trade": False, "reason": reason}
        if signal_dict.get("signal") not in ("BUY", "SELL"):
            return {"take_trade": False, "reason": "No active signal (WAIT)."}
        entry = signal_dict.get("entry"); sl = signal_dict.get("sl")
        if entry is None or sl is None:
            return {"take_trade": False, "reason": "Missing entry/SL in signal."}
        sizing = self.position_size(entry, sl, leverage=leverage)
        return {"take_trade": True, "sizing": sizing, "signal": signal_dict}


# ══════════════════════════════════════════════════════════════════════════
# ORDER FLOW PROXY MODULE — Fabio Valentino style (approximated from OHLCV)
# ══════════════════════════════════════════════════════════════════════════
# ⚠️ See CONFIG note above: this is an OHLCV-based approximation of order
# flow concepts (CVD, absorption/aggression, LVN retest, squeeze), built
# because fetch_ohlcv() has no real bid/ask tape or footprint data. Use it
# as a research proxy, not a substitute for an actual order-flow platform.

def calc_candle_delta_proxy(df):
    """
    Proxy for per-candle buy/sell aggression ('delta') using the classic
    Chaikin Money-Flow-Multiplier idea:
        mfm = ((close - low) - (high - close)) / (high - low)
        delta_proxy = mfm * volume
    mfm is +1 when the candle closes at its high (all buy aggression),
    -1 when it closes at its low (all sell aggression), 0 if it closes
    mid-range. This is NOT real tape delta, just a shape-based estimate.
    """
    df = df.copy()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng
    mfm = mfm.fillna(0.0)
    df["delta_proxy"] = mfm * df["volume"]
    return df

def calc_cvd_proxy(df):
    """Session-reset cumulative delta proxy (like session VWAP, but for delta)."""
    df = calc_candle_delta_proxy(df)
    day = df.index.date
    df["cvd_proxy"] = pd.Series(df["delta_proxy"].values, index=df.index).groupby(day).cumsum()
    return df

def detect_absorption_proxy(df, vol_mult=None, body_max_pct=None):
    """
    Absorption proxy: unusually large volume but a small real body relative
    to the candle's range = "punching a wall" (aggression got absorbed by
    resting limit orders instead of pushing price further).
    Returns a Series of '' / 'BULL_ABSORPTION' / 'BEAR_ABSORPTION'.
    BULL_ABSORPTION: heavy volume, small body, closes in upper half -> sellers
      tried to push down and got absorbed (potential bullish reversal/hold).
    BEAR_ABSORPTION: heavy volume, small body, closes in lower half -> buyers
      tried to push up and got absorbed.
    """
    vol_mult = vol_mult or CONFIG['OF_ABSORPTION_VOL_MULT']
    body_max_pct = body_max_pct or CONFIG['OF_ABSORPTION_BODY_MAX_PCT']
    df = df.copy()
    avg_vol = df["volume"].rolling(20).mean()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body_pct = (df["close"] - df["open"]).abs() / rng * 100
    is_big_vol = df["volume"] > (avg_vol * vol_mult)
    is_small_body = body_pct <= body_max_pct
    closes_upper = (df["close"] - df["low"]) / rng > 0.5
    closes_lower = ~closes_upper
    sig = pd.Series('', index=df.index)
    sig[is_big_vol & is_small_body & closes_upper] = 'BULL_ABSORPTION'
    sig[is_big_vol & is_small_body & closes_lower] = 'BEAR_ABSORPTION'
    return sig

def build_volume_profile_nodes(df, lookback=None, bins=None, lvn_pctl=None, hvn_pctl=None):
    """
    Builds a volume profile over the lookback window and classifies bins as
    POC / HVN (High Volume Node) / LVN (Low Volume Node) based on percentile
    thresholds of volume-per-bin. Returns dict with poc, hvn_levels, lvn_levels
    (each level = midpoint price of that bin).
    """
    lookback = lookback or CONFIG['OF_VP_LOOKBACK']
    bins = bins or CONFIG['OF_VP_BINS']
    lvn_pctl = lvn_pctl if lvn_pctl is not None else CONFIG['OF_LVN_PCTL']
    hvn_pctl = hvn_pctl if hvn_pctl is not None else CONFIG['OF_HVN_PCTL']

    data = df.tail(lookback)
    if len(data) < 10:
        return {"poc": None, "hvn_levels": [], "lvn_levels": []}

    price_min, price_max = data["low"].min(), data["high"].max()
    if price_max <= price_min:
        return {"poc": None, "hvn_levels": [], "lvn_levels": []}

    bin_edges = np.linspace(price_min, price_max, bins + 1)
    vol_per_bin = np.zeros(bins)
    tp = (data["high"] + data["low"] + data["close"]) / 3
    bin_idx = np.clip(np.searchsorted(bin_edges, tp.values) - 1, 0, bins - 1)
    for idx, vol in zip(bin_idx, data["volume"].values):
        vol_per_bin[idx] += vol

    bin_mid = (bin_edges[:-1] + bin_edges[1:]) / 2
    nonzero_mask = vol_per_bin > 0
    if not nonzero_mask.any():
        return {"poc": None, "hvn_levels": [], "lvn_levels": []}

    poc_idx = int(np.argmax(vol_per_bin))
    poc_price = round(float(bin_mid[poc_idx]), 4)

    vols_nonzero = vol_per_bin[nonzero_mask]
    lvn_thresh = np.percentile(vols_nonzero, lvn_pctl)
    hvn_thresh = np.percentile(vols_nonzero, hvn_pctl)

    lvn_levels = sorted(round(float(p), 4) for p, v in zip(bin_mid, vol_per_bin)
                         if 0 < v <= lvn_thresh)
    hvn_levels = sorted(round(float(p), 4) for p, v in zip(bin_mid, vol_per_bin)
                         if v >= hvn_thresh)

    return {"poc": poc_price, "hvn_levels": hvn_levels, "lvn_levels": lvn_levels}

def in_session(ts):
    """
    Fabio trades New York + London high-volatility sessions only.
    ts: pandas Timestamp (assumed UTC-naive from exchange data, treated as UTC).
    """
    hour = ts.hour
    ny = CONFIG['OF_SESSION_NY_START_UTC'] <= hour < CONFIG['OF_SESSION_NY_END_UTC']
    ldn = CONFIG['OF_SESSION_LDN_START_UTC'] <= hour < CONFIG['OF_SESSION_LDN_END_UTC']
    return ny or ldn, ("NY" if ny else ("LDN" if ldn else None))

def _nearest_level(price, levels, tol_pct):
    """Return nearest level within tol_pct of price, else None."""
    if not levels:
        return None
    for lvl in levels:
        if lvl == 0:
            continue
        if abs(price - lvl) / lvl * 100 <= tol_pct:
            return lvl
    return None

def detect_second_drive_setup(df, vp_nodes, breakout_lookback=None, max_bars=None, tol_pct=None):
    """
    Fabio's 'wait for breakout, don't chase first drive, enter on retest of
    LVN with fresh aggression' pattern, approximated on OHLCV:
      1. Detect a breakout of the recent balance range (prior N-bar high/low).
      2. Within max_bars afterwards, look for the price coming back to
         retest a nearby LVN level (support/resistance handoff zone).
      3. Confirm with delta_proxy aggression in the breakout direction AND
         rising volume on the retest bar (bubbles-like confirmation).
    Returns (direction, reason) or (None, reason).
    """
    breakout_lookback = breakout_lookback or CONFIG['OF_BREAKOUT_LOOKBACK']
    max_bars = max_bars or CONFIG['OF_SECOND_DRIVE_MAX_BARS']
    tol_pct = tol_pct or CONFIG['OF_RETEST_TOL_PCT']

    if len(df) < breakout_lookback + max_bars + 5:
        return None, "Not enough data for second-drive scan"

    window = df.tail(breakout_lookback + max_bars + 1).copy()
    range_part = window.iloc[:breakout_lookback]
    later_part = window.iloc[breakout_lookback:]

    range_high = range_part["high"].max()
    range_low = range_part["low"].min()

    breakout_dir = None
    breakout_idx = None
    for i, (idx, row) in enumerate(later_part.iterrows()):
        if row["close"] > range_high:
            breakout_dir = "BUY"; breakout_idx = i; break
        if row["close"] < range_low:
            breakout_dir = "SELL"; breakout_idx = i; break

    if breakout_dir is None:
        return None, "No breakout of balance range yet"

    after_breakout = later_part.iloc[breakout_idx:]
    if len(after_breakout) < 2:
        return None, "Breakout too recent, waiting for retest"

    lvn_levels = vp_nodes.get("lvn_levels", [])
    last_row = after_breakout.iloc[-1]
    nearest_lvn = _nearest_level(last_row["close"], lvn_levels, tol_pct)
    if nearest_lvn is None:
        return None, "Waiting for LVN retest (no fake-out entry on first drive)"

    avg_vol = df["volume"].tail(20).mean()
    aggression_ok = last_row["volume"] > avg_vol
    delta_ok = True
    if "delta_proxy" in df.columns:
        last_delta = df["delta_proxy"].iloc[-1]
        delta_ok = (last_delta > 0) if breakout_dir == "BUY" else (last_delta < 0)

    if aggression_ok and delta_ok:
        return breakout_dir, f"SECOND DRIVE {breakout_dir} @ LVN retest {nearest_lvn}"
    return None, "Retest found but aggression/delta not confirming yet"

def detect_squeeze_proxy(df, atr_series):
    """
    Squeeze model proxy: trapped side gets forced out -> a sudden
    range-expansion candle (range >> ATR) with volume spike, in the
    direction that breaks a recent swing level. Approximates the
    "acceleration" Fabio describes when stops from the losing side cluster.
    """
    if len(df) < 25 or atr_series is None or len(atr_series) < 25:
        return None, "Not enough data for squeeze scan"

    last = df.iloc[-1]
    last_atr = atr_series.iloc[-1]
    if pd.isna(last_atr) or last_atr <= 0:
        return None, "ATR unavailable"

    candle_range = last["high"] - last["low"]
    avg_vol = df["volume"].tail(20).mean()

    is_expansion = candle_range >= (last_atr * CONFIG['OF_SQUEEZE_ATR_MULT'])
    is_vol_spike = last["volume"] >= (avg_vol * CONFIG['OF_SQUEEZE_VOL_MULT'])

    if not (is_expansion and is_vol_spike):
        return None, "No squeeze/acceleration bar detected"

    prior_high = df["high"].iloc[-21:-1].max()
    prior_low = df["low"].iloc[-21:-1].min()

    if last["close"] > prior_high:
        return "BUY", f"SQUEEZE LONG — range {candle_range:.4f} >= {CONFIG['OF_SQUEEZE_ATR_MULT']}x ATR, vol spike"
    if last["close"] < prior_low:
        return "SELL", f"SQUEEZE SHORT — range {candle_range:.4f} >= {CONFIG['OF_SQUEEZE_ATR_MULT']}x ATR, vol spike"
    return None, "Expansion bar but no clean break of prior swing level"

def calc_orderflow_sl(direction, df, atr):
    """
    SL placed just beyond the recent swing high/low (proxy for 'aggression
    bubble + 1-2 ticks'), buffered by OF_SL_BUFFER_TICKS_PCT to avoid getting
    clipped by slippage on the acceleration move.
    """
    lookback = df.tail(10)
    buffer_pct = CONFIG['OF_SL_BUFFER_TICKS_PCT'] / 100
    if direction == "BUY":
        swing_low = lookback["low"].min()
        return round(swing_low * (1 - buffer_pct), 4)
    if direction == "SELL":
        swing_high = lookback["high"].max()
        return round(swing_high * (1 + buffer_pct), 4)
    return None

def apply_breakeven_trigger(direction, entry_price, current_high, current_low, atr, sl):
    """
    Once price has moved OF_BREAKEVEN_TRIGGER_ATR_MULT * ATR in favor,
    move SL to break-even (entry_price). Returns the (possibly) updated SL.
    """
    trigger_dist = atr * CONFIG['OF_BREAKEVEN_TRIGGER_ATR_MULT']
    if direction == "BUY" and current_high >= entry_price + trigger_dist:
        return max(sl, entry_price)
    if direction == "SELL" and current_low <= entry_price - trigger_dist:
        return min(sl, entry_price)
    return sl


class OrderFlowRiskManager(RiskManager):
    """
    Extends RiskManager with Fabio's "risk the house money, not the original
    equity" idea: base risk stays small (0.25%) on the account's core capital;
    once the day is in profit, size the NEXT trade's risk off the larger
    house-money percentage instead, while the core capital risk stays capped.
    """
    def __init__(self, account_capital_usdt):
        super().__init__(account_capital_usdt)

    def current_risk_pct(self):
        if self.daily_pnl_pct > 0:
            return CONFIG['OF_RISK_HOUSE_MONEY_PCT']
        return CONFIG['OF_RISK_BASE_PCT']

    def position_size_orderflow(self, entry_price, sl_price, leverage=1):
        leverage = min(leverage, CONFIG['MAX_LEVERAGE'])
        risk_pct = self.current_risk_pct()
        risk_amount_usdt = self.capital * (risk_pct / 100)
        sl_distance = abs(entry_price - sl_price)
        if sl_distance <= 0:
            return {"error": "invalid SL distance"}
        qty = risk_amount_usdt / sl_distance
        notional = qty * entry_price
        margin_required = notional / leverage
        return {
            "qty": round(qty, 6),
            "notional_usdt": round(notional, 2),
            "margin_required_usdt": round(margin_required, 2),
            "leverage_used": leverage,
            "risk_amount_usdt": round(risk_amount_usdt, 2),
            "risk_pct_used": risk_pct,
            "mode": "house_money" if risk_pct == CONFIG['OF_RISK_HOUSE_MONEY_PCT'] else "base",
        }


def analyze_orderflow(symbol, entry_timeframe="1m", structure_timeframe="5m"):
    """
    Main live entry point for the Fabio-style order-flow-proxy strategy.
    Combines: session filter -> balance/consolidation via volume profile ->
    second-drive retest OR squeeze trigger -> delta/absorption confirmation
    -> SL beyond swing level -> TP at POC / prior balance area.
    """
    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, CONFIG['LIMIT'])
    df_5m, _ = fetch_ohlcv_failover(symbol, structure_timeframe, CONFIG['LIMIT'])
    if df_entry is None or df_5m is None:
        return {"symbol": symbol, "error": "no data"}

    now_ts = df_entry.index[-1]
    session_ok, session_name = in_session(now_ts)

    df_entry = add_indicators_vectorized(df_entry)
    df_entry = calc_cvd_proxy(df_entry)
    df_entry["absorption"] = detect_absorption_proxy(df_entry)

    vp_nodes = build_volume_profile_nodes(df_5m)
    atr_series = calc_atr(df_entry, CONFIG['ATR_PERIOD'])

    if not session_ok:
        return {
            "symbol": symbol, "timeframe": entry_timeframe, "signal": "WAIT",
            "reason": "Outside NY/London high-volatility session — Fabio skips this",
            "session": session_name, "price": round(float(df_entry["close"].iloc[-1]), 4),
        }

    price = float(df_entry["close"].iloc[-1])
    atr_now = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else None

    direction, reason = detect_second_drive_setup(df_entry, vp_nodes)
    setup_type = "SECOND_DRIVE"
    if direction is None:
        direction, sq_reason = detect_squeeze_proxy(df_entry, atr_series)
        setup_type = "SQUEEZE"
        reason = sq_reason if direction else f"{reason} | {sq_reason}"

    if direction is None or atr_now is None:
        return {
            "symbol": symbol, "timeframe": entry_timeframe, "signal": "WAIT",
            "reason": reason, "session": session_name, "price": round(price, 4),
            "vp_nodes": vp_nodes,
        }

    sl = calc_orderflow_sl(direction, df_entry, atr_now)
    poc = vp_nodes.get("poc")
    if poc is not None:
        tp = poc
    else:
        tp, _ = calc_tp_sl(direction, price, atr_now)

    return {
        "symbol": symbol, "timeframe": entry_timeframe, "signal": direction,
        "setup_type": setup_type, "reason": reason, "session": session_name,
        "price": round(price, 4), "entry": round(price, 4),
        "sl": sl, "tp": round(tp, 4) if tp is not None else None,
        "atr": round(atr_now, 4),
        "cvd_proxy": round(float(df_entry["cvd_proxy"].iloc[-1]), 2),
        "absorption": df_entry["absorption"].iloc[-1] or None,
        "vp_nodes": vp_nodes,
        "exchange": ex_id,
        "note": "OHLCV-based order-flow PROXY — not real tape/footprint data. Forward-test on paper first.",
    }


def run_orderflow_backtest(symbol, entry_timeframe="1m", structure_timeframe="5m"):
    """
    Backtests the order-flow proxy strategy (second-drive + squeeze),
    with session filtering and break-even management, mirroring
    analyze_orderflow()'s logic bar-by-bar.
    """
    limit = CONFIG['BACKTEST_CANDLES']
    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, limit)
    df_5m, _ = fetch_ohlcv_failover(symbol, structure_timeframe, limit)
    if df_entry is None or df_5m is None:
        return {"error": "no data"}

    df_entry = add_indicators_vectorized(df_entry)
    df_entry = calc_cvd_proxy(df_entry)
    atr_series = calc_atr(df_entry, CONFIG['ATR_PERIOD'])

    closes = df_entry["close"].values
    highs = df_entry["high"].values
    lows = df_entry["low"].values
    n = len(df_entry)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    min_lookback = CONFIG['OF_BREAKOUT_LOOKBACK'] + CONFIG['OF_SECOND_DRIVE_MAX_BARS'] + 25
    results = []

    for i in range(min_lookback, n - WINDOW):
        ts = df_entry.index[i]
        session_ok, session_name = in_session(ts)
        if not session_ok:
            continue

        sub_df = df_entry.iloc[:i + 1]
        vp_source = df_5m[df_5m.index <= ts]
        if len(vp_source) < 10:
            continue
        vp_nodes = build_volume_profile_nodes(vp_source)

        direction, _ = detect_second_drive_setup(sub_df, vp_nodes)
        setup_type = "SECOND_DRIVE"
        if direction is None:
            direction, _ = detect_squeeze_proxy(sub_df, atr_series.iloc[:i + 1])
            setup_type = "SQUEEZE"
        if direction is None:
            continue

        atr_now = atr_series.iloc[i]
        if pd.isna(atr_now) or atr_now <= 0:
            continue

        price = closes[i]
        sl = calc_orderflow_sl(direction, sub_df, atr_now)
        poc = vp_nodes.get("poc")
        tp = poc if poc is not None else (price + atr_now * CONFIG['TP_ATR_MULT'] if direction == "BUY"
                                           else price - atr_now * CONFIG['TP_ATR_MULT'])
        if sl is None or tp is None:
            continue
        # Sanity: TP must be on the correct side of entry
        if direction == "BUY" and tp <= price:
            continue
        if direction == "SELL" and tp >= price:
            continue

        current_sl = sl
        outcome, exit_price = "OPEN", None
        for j in range(i + 1, min(i + WINDOW + 1, n)):
            fh, fl = highs[j], lows[j]
            current_sl = apply_breakeven_trigger(direction, price, fh, fl, atr_now, current_sl)
            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= current_sl:
                    outcome = "BREAKEVEN" if current_sl >= price else "LOSS"
                    exit_price = current_sl; break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= current_sl:
                    outcome = "BREAKEVEN" if current_sl <= price else "LOSS"
                    exit_price = current_sl; break
        if outcome == "OPEN":
            continue

        pnl_pct = ((exit_price - price) / price * 100 if direction == "BUY"
                   else (price - exit_price) / price * 100) - CONFIG['FEE_PCT']
        results.append({
            "time": df_entry.index[i].strftime("%m-%d %H:%M"), "session": session_name,
            "setup": setup_type, "direction": direction,
            "entry": round(price, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "outcome": outcome, "pnl_pct": round(pnl_pct, 4),
        })

    if not results:
        return {"symbol": symbol, "timeframe": entry_timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No order-flow-proxy signals in this window"}

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

    by_setup = {}
    for r in results:
        by_setup.setdefault(r["setup"], []).append(r)
    setup_breakdown = {}
    for k, rs in by_setup.items():
        w = [r for r in rs if r["pnl_pct"] > 0]
        setup_breakdown[k] = {
            "trades": len(rs),
            "win_rate": round(len(w) / len(rs) * 100, 1) if rs else 0,
        }

    return {
        "symbol": symbol, "timeframe": entry_timeframe, "candles_tested": limit,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy, "setup_breakdown": setup_breakdown,
        "recent_trades": results[-10:],
        "note": "OHLCV-based order-flow PROXY backtest — no real tape/footprint data was used. "
                "Treat results as directional research, not a guarantee.",
    }


# ── COMBINED FACTOR BACKTEST (votes include FVG + Inducement) ─
def run_combined_backtest(symbol, timeframe="5m", min_agree=2, strong_adx=25, use_breakeven=True):
    """
    Trade only when >= min_agree factors agree on direction, AND adx >= strong_adx.
    Factors voting: Liquidity Sweep, Structure Break, Divergence, Candle Pattern,
    EMA crossover, FVG proximity, Inducement.
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


# ── FUNDING RATE FACTOR ──────────────────────────────────────
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


def run_funding_rate_backtest(symbol="BTC/USDT:USDT", price_timeframe="15m", funding_symbol="BTC/USDT:USDT"):
    """
    Isolated test: does extreme funding rate predict mean-reversion?
    SELL when funding is extremely positive (crowded longs), BUY when extremely negative.
    Uses percentile-based thresholds (top/bottom 15% of funding rate distribution).
    """
    limit = CONFIG['BACKTEST_CANDLES']
    price_df, ex_id = fetch_ohlcv_failover(symbol, price_timeframe, limit)
    if price_df is None:
        return {"error": "no price data"}

    funding_df, fund_err = fetch_funding_rate_history(funding_symbol, limit=1000)
    if funding_df is None:
        return {"error": f"no funding rate data — {fund_err}"}

    price_df = add_indicators_vectorized(price_df)

    price_times = pd.DataFrame({"time": price_df.index})
    funding_reset = funding_df.reset_index().rename(columns={"timestamp": "time"})
    merged = pd.merge_asof(price_times.sort_values("time"), funding_reset.sort_values("time"),
                            on="time", direction="backward")
    merged = merged.set_index("time")

    price_df = price_df.copy()
    price_df["funding_rate"] = merged["funding_rate"]

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
        if fr >= high_thresh: direction = "SELL"
        elif fr <= low_thresh: direction = "BUY"
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
        "note": "Tests funding-rate mean-reversion in isolation.",
    }


# ══════════════════════════════════════════════════════════════════════════
# TUNING TOOLS — NOTE: step2_grid_search() calls run_backtest(), which
# applies the regime filter (FIX #1) — so grid search results are trustworthy.
# ══════════════════════════════════════════════════════════════════════════
import copy as _copy

TUNE_SYMBOL = "BTC/USDT:USDT"
TUNE_ENTRY_TF = "5m"


def step1_factor_report():
    print("=" * 70)
    print(f"STEP 1: Factor isolation report — {TUNE_SYMBOL} ({TUNE_ENTRY_TF})")
    print("=" * 70)
    result = run_factor_backtest(TUNE_SYMBOL, timeframe=TUNE_ENTRY_TF)
    if "error" in result:
        print("ERROR:", result["error"])
        return None

    good_factors = []
    bad_factors = []
    for f in result["factors"]:
        if f.get("total_trades", 0) == 0:
            print(f"  {f['label']:<45} -> no signals in window")
            continue
        pf = f.get("profit_factor")
        wr = f.get("win_rate")
        n = f.get("total_trades")
        verdict = "KEEP" if (pf is not None and pf >= 1.2) else "WEAK/DROP"
        print(f"  {f['label']:<45} trades={n:<4} win_rate={wr:<6} pf={pf}  {verdict}")
        if pf is not None and pf >= 1.2:
            good_factors.append(f['label'])
        else:
            bad_factors.append(f['label'])

    print("\nSummary:")
    print("  Factors with real edge (pf>=1.2):", good_factors or "NONE")
    print("  Weak/noise factors:", bad_factors)
    return result


def step2_grid_search():
    print("\n" + "=" * 70)
    print(f"STEP 2: Grid search — TP/SL multipliers, ADX_MIN, SCORE_THRESHOLD")
    print("=" * 70)

    tp_mults = [1.5, 2.0, 2.5, 3.0]
    sl_mults = [0.8, 1.0, 1.2, 1.5]
    adx_mins = [15, 18, 22, 25]
    score_thresholds = [4.0, 5.0, 6.0, 7.0]

    original_config = _copy.deepcopy(CONFIG)
    results = []

    total_runs = len(tp_mults) * len(sl_mults) * len(adx_mins) * len(score_thresholds)
    run_count = 0

    for tp in tp_mults:
        for sl in sl_mults:
            for adx in adx_mins:
                for thresh in score_thresholds:
                    run_count += 1
                    CONFIG['TP_ATR_MULT'] = tp
                    CONFIG['SL_ATR_MULT'] = sl
                    CONFIG['ADX_MIN'] = adx
                    CONFIG['SCORE_THRESHOLD'] = thresh
                    CONFIG['SCORE_GAP_MIN'] = round(thresh * 0.6, 1)

                    res = run_backtest(TUNE_SYMBOL, timeframe=TUNE_ENTRY_TF)

                    if res.get("total_trades", 0) < 8:
                        continue

                    results.append({
                        "tp_mult": tp, "sl_mult": sl, "adx_min": adx,
                        "score_threshold": thresh,
                        "total_trades": res["total_trades"],
                        "win_rate": res["win_rate"],
                        "profit_factor": res.get("profit_factor"),
                        "expectancy_pct": res.get("expectancy_pct"),
                        "avg_rr": res.get("avg_rr"),
                    })

                    if run_count % 20 == 0:
                        print(f"  ...{run_count}/{total_runs} combos tested")

    CONFIG.clear()
    CONFIG.update(original_config)

    if not results:
        print("\nNo config produced >=8 trades.")
        return []

    results_sorted = sorted(
        results,
        key=lambda r: (r["profit_factor"] if r["profit_factor"] is not None else -999,
                        r["expectancy_pct"]),
        reverse=True
    )

    print(f"\nTop 10 configs (out of {len(results)} valid combos tested):\n")
    print(f"{'TP':<5}{'SL':<5}{'ADX':<5}{'THRESH':<8}{'Trades':<8}{'WinRate':<9}{'PF':<8}{'Expect%':<10}{'AvgRR':<7}")
    for r in results_sorted[:10]:
        print(f"{r['tp_mult']:<5}{r['sl_mult']:<5}{r['adx_min']:<5}{r['score_threshold']:<8}"
              f"{r['total_trades']:<8}{r['win_rate']:<9}{r['profit_factor']:<8}"
              f"{r['expectancy_pct']:<10}{r['avg_rr']:<7}")

    return results_sorted


def step3_apply_best(results_sorted):
    if not results_sorted:
        return
    best = results_sorted[0]
    print("\n" + "=" * 70)
    print("STEP 3: Best config found — paste this into CONFIG at the top of scanner_v2.py")
    print("=" * 70)
    print(f"""
    'TP_ATR_MULT': {best['tp_mult']},
    'SL_ATR_MULT': {best['sl_mult']},
    'ADX_MIN': {best['adx_min']},
    'SCORE_THRESHOLD': {best['score_threshold']},
    'SCORE_GAP_MIN': {round(best['score_threshold'] * 0.6, 1)},
    """)
    print(f"Backtest with this config: {best['total_trades']} trades, "
          f"win_rate={best['win_rate']}%, profit_factor={best['profit_factor']}, "
          f"expectancy={best['expectancy_pct']}%")

    if best['profit_factor'] is None or best['profit_factor'] < 1.2:
        print("\nEven the best combo found here is weak (pf < 1.2).")
        print("That means the current signal factors don't have real edge on this")
        print("symbol/timeframe/window — tuning TP/SL alone won't fix it.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        SYMBOL = "BTC/USDT:USDT"
        print(f"Live signal for {SYMBOL}:")
        sig = analyze(SYMBOL, timeframe="1m")
        print(sig)
        print("\nRisk-sized example (assume 10,000 USDT capital, 3x leverage):")
        rm = RiskManager(account_capital_usdt=10000)
        print(rm.evaluate_signal(sig, leverage=3))
        print("\nFast backtest (5m):")
        print(run_backtest(SYMBOL, timeframe="5m"))
    elif len(sys.argv) > 1 and sys.argv[1] == "factors":
        step1_factor_report()
    elif len(sys.argv) > 1 and sys.argv[1] == "orderflow":
        SYMBOL = "BTC/USDT:USDT"
        print(f"Order-flow-proxy live signal for {SYMBOL}:")
        sig = analyze_orderflow(SYMBOL, entry_timeframe="1m", structure_timeframe="5m")
        print(sig)
        print("\nHouse-money risk sizing example (10,000 USDT capital, 3x leverage):")
        ofrm = OrderFlowRiskManager(account_capital_usdt=10000)
        if sig.get("signal") in ("BUY", "SELL") and sig.get("sl") is not None:
            print(ofrm.position_size_orderflow(sig["entry"], sig["sl"], leverage=3))
        else:
            print("No active signal to size.")
        print("\nOrder-flow-proxy backtest (1m entry / 5m structure):")
        print(run_orderflow_backtest(SYMBOL, entry_timeframe="1m", structure_timeframe="5m"))
    else:
        factor_result = step1_factor_report()
        grid_results = step2_grid_search()
        step3_apply_best(grid_results)
