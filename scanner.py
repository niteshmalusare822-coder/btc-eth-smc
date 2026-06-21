import ccxt
import pandas as pd
import numpy as np

# ── Config ──────────────────────────────────────────────
CONFIG = {
    'EMA_FAST': 5,
    'EMA_SLOW': 20,
    'RSI_PERIOD': 7,
    'ATR_PERIOD': 14,
    'ADX_PERIOD': 14,
    'ADX_MIN': 15,
    'SWING_LOOKBACK': 3,
    'LIQUIDITY_SWEEP_LOOKBACK': 20,
    'VOLUME_PROFILE_LOOKBACK': 100,
    'VOLUME_PROFILE_BINS': 24,
    'SCORE_THRESHOLD': 5,
    'ATR_COMPRESSION_RATIO': 0.7,
    'ATR_MA_PERIOD': 50,
    'CHOPPINESS_PERIOD': 14,
    'CHOPPINESS_TREND_MAX': 61.8,
    'LIMIT': 200,
}

EXCHANGE_IDS = ['mexc', 'bybit', 'okx', 'gateio']

_exchanges = []
for ex_id in EXCHANGE_IDS:
    try:
        klass = getattr(ccxt, ex_id)
        _exchanges.append((ex_id, klass({'enableRateLimit': True, 'timeout': 15000})))
    except Exception:
        continue


def fetch_ohlcv_failover(ticker, timeframe, limit):
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


# ── Indicators ──────────────────────────────────────────
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


# ── Regime filter ───────────────────────────────────────
def detect_market_regime(df):
    atr = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx = calc_adx(df, CONFIG['ADX_PERIOD'])

    current_atr, current_atr_ma = atr.iloc[-1], atr_ma.iloc[-1]
    current_ci, current_adx = ci.iloc[-1], adx.iloc[-1]
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


# ── Structure / patterns ───────────────────────────────
def detect_structure_live_pro(df, lookback=3):
    df = df.copy()
    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    events, trends = [None] * n, [None] * n
    trend = None
    last_swing_high = last_swing_low = None
    for i in range(lookback * 2, n):
        lh = highs[i - 2 * lookback: i - lookback]
        rh = highs[i - lookback + 1: i + 1]
        ll = lows[i - 2 * lookback: i - lookback]
        rl = lows[i - lookback + 1: i + 1]
        if len(lh) == lookback and len(rh) == lookback:
            if highs[i - lookback] >= lh.max() and highs[i - lookback] >= rh.max():
                last_swing_high = highs[i - lookback]
            if lows[i - lookback] <= ll.min() and lows[i - lookback] <= rl.min():
                last_swing_low = lows[i - lookback]
        close = closes[i]
        if last_swing_high is not None and close > last_swing_high:
            events[i] = "BOS_BULL" if trend == "BULL" else "CHoCH_BULL"
            trend = "BULL"
            last_swing_high = highs[i]
        elif last_swing_low is not None and close < last_swing_low:
            events[i] = "BOS_BEAR" if trend == "BEAR" else "CHoCH_BEAR"
            trend = "BEAR"
            last_swing_low = lows[i]
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
    data = df.tail(CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    if len(data) < 5:
        return None
    last = data.iloc[-1]
    p_highs, p_lows = data["high"].iloc[:-1], data["low"].iloc[:-1]
    if last["high"] > p_highs.max() and last["close"] < p_highs.max():
        return "EQUAL_HIGH_SWEEP"
    if last["low"] < p_lows.min() and last["close"] > p_lows.min():
        return "EQUAL_LOW_SWEEP"
    return None


# ── Per-timeframe analysis ──────────────────────────────
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
    sweep = detect_liquidity_sweep(df)
    vp = calc_volume_profile(df, CONFIG['VOLUME_PROFILE_LOOKBACK'], CONFIG['VOLUME_PROFILE_BINS'])
    regime = detect_market_regime(df)
    last = df.iloc[-1]
    return {
        "structure_event": last["structure_event"],
        "structure_trend": last["structure_trend"],
        "adx": last["adx"], "price": last["close"], "vwap": last["vwap"],
        "ema5": last["ema5"], "ema20": last["ema20"], "rsi": last["rsi"],
        "pattern": last["pat_sig"], "divergence": last["divergence"],
        "sweep": sweep, "vp": vp, "regime": regime,
    }

def get_htf_bias(snap_1h, snap_4h):
    score = 0
    for snap, weight in [(snap_1h, 1.0), (snap_4h, 1.5)]:
        if snap["structure_trend"] == "BULL":
            score += weight
        elif snap["structure_trend"] == "BEAR":
            score -= weight
        score += weight * 0.5 if snap["ema5"] > snap["ema20"] else -weight * 0.5
    if score >= 1.5:
        return "BULLISH"
    if score <= -1.5:
        return "BEARISH"
    return "NEUTRAL"

def get_ltf_scores(snap_5m, snap_15m):
    buy_score, sell_score = 0.0, 0.0
    for snap, w in [(snap_5m, 1.0), (snap_15m, 1.2)]:
        if snap["pattern"] == "BUY":
            buy_score += 2 * w
        elif snap["pattern"] == "SELL":
            sell_score += 2 * w
        if snap["divergence"] == "BULL_DIV":
            buy_score += 3 * w
        elif snap["divergence"] == "BEAR_DIV":
            sell_score += 3 * w
        if snap["sweep"] == "EQUAL_LOW_SWEEP":
            buy_score += 3 * w
        elif snap["sweep"] == "EQUAL_HIGH_SWEEP":
            sell_score += 3 * w
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
    return round(buy_score, 2), round(sell_score, 2)

def decide_direction(buy_score, sell_score, htf_bias, entry_adx, regime_5m, regime_15m):
    if pd.isna(entry_adx) or entry_adx < CONFIG['ADX_MIN']:
        return None, f"NO TREND (ADX {entry_adx:.1f} < {CONFIG['ADX_MIN']})"
    if regime_5m["regime"] == "COMPRESSION":
        return None, f"BLOCKED (5m ATR compression, ratio {regime_5m['atr_ratio']})"
    if regime_15m["regime"] == "RANGING":
        return None, f"BLOCKED (15m choppy, CI {regime_15m['choppiness']})"
    if htf_bias == "BULLISH" and buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
        return "BUY", "BUY"
    if htf_bias == "BEARISH" and sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
        return "SELL", "SELL"
    return None, "WAIT (no aligned confluence yet)"


# ── PUBLIC ENTRY POINT — called by app.py ───────────────
def analyze(symbol, timeframe="5m"):
    """
    Returns a signal dict for the dashboard.
    Uses SMC structure + regime filter + multi-timeframe scoring.
    """
    df_entry, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
    if df_entry is None:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}

    snap_entry = analyze_timeframe(df_entry)
    price = float(snap_entry["price"])
    rsi_now = float(snap_entry["rsi"]) if not pd.isna(snap_entry["rsi"]) else None

    # Higher timeframe bias (1h + 4h) — best-effort, skip if unavailable
    htf_bias = "NEUTRAL"
    df_1h, _ = fetch_ohlcv_failover(symbol, "1h", CONFIG['LIMIT'])
    df_4h, _ = fetch_ohlcv_failover(symbol, "4h", CONFIG['LIMIT'])
    if df_1h is not None and df_4h is not None:
        snap_1h = analyze_timeframe(df_1h)
        snap_4h = analyze_timeframe(df_4h)
        htf_bias = get_htf_bias(snap_1h, snap_4h)

    buy_score, sell_score = get_ltf_scores(snap_entry, snap_entry)

    direction, reason = decide_direction(
        buy_score, sell_score, htf_bias, snap_entry["adx"],
        snap_entry["regime"], snap_entry["regime"]
    )

    signal = direction if direction else "WAIT"

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
    }
