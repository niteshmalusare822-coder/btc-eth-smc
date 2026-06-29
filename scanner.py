import ccxt
import requests
import pandas as pd
import numpy as np
import time as _t

# Map our symbol format -> CoinDCX futures pair format    # ← yeh block add karo
COINDCX_PAIR_MAP = {
    "BTC/USDT:USDT": "B-BTC_USDT",
    "ETH/USDT:USDT": "B-ETH_USDT",
}

# CoinDCX resolution strings per timeframe
COINDCX_RESOLUTION_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
}
# ── Config — SCALPER MODE ───────────────────────────────
CONFIG = {
    'EMA_FAST': 5,
    'EMA_SLOW': 20,
    'RSI_PERIOD': 7,               # Fast RSI — scalping ke liye
    'ATR_PERIOD': 14,
    'ADX_PERIOD': 14,
    'ADX_MIN': 18,             # weak/no-trend trades avoid karo
    'SWING_LOOKBACK': 3,
    'LIQUIDITY_SWEEP_LOOKBACK': 20,
    'VOLUME_PROFILE_LOOKBACK': 100,
    'VOLUME_PROFILE_BINS': 24,
    'SCORE_THRESHOLD': 4.5,    # zyada conviction chahiye signal ke liye
    'SCORE_GAP_MIN': 3.0,      # buy/sell score mein clear gap chahiye
    'FEE_PCT': 0.04,
    'ATR_COMPRESSION_RATIO': 0.7,
    'ATR_MA_PERIOD': 50,
    'CHOPPINESS_PERIOD': 14,
    'CHOPPINESS_TREND_MAX': 61.8,
    'LIMIT': 300,                  # 300 candles — fast fetch + backtest
    'TP_ATR_MULT': 2.0,            # Tight TP for scalping
    'SL_ATR_MULT': 1.0,           # Tight SL for scalping (2:1 RR)
    'RSI_OVERBOUGHT': 70,
    'RSI_OVERSOLD': 30,
    'BACKTEST_CANDLES': 6000,      # Backtest window — bada sample size
    'BACKTEST_OUTCOME_WINDOW': 20, # Kitne candles aage dekhe TP/SL ke liye
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
    """
    Fetch OHLCV candles from CoinDCX public futures API.
    Returns (df, 'coindcx') on success, (None, None) on failure.
    """
    pair = COINDCX_PAIR_MAP.get(ticker)
    resolution = COINDCX_RESOLUTION_MAP.get(timeframe)
    if pair is None or resolution is None:
        return None, None
 
    # Each candle's duration in seconds, used to compute "from" time
    tf_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}[timeframe]
    to_time = int(_t.time())
    from_time = to_time - (tf_seconds * (limit + 5))  # small buffer
 
    url = "https://public.coindcx.com/market_data/candlesticks"
    params = {
        "pair": pair,
        "from": from_time,
        "to": to_time,
        "resolution": resolution,
        "pcode": "f",  # f = futures
    }
 
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
 
        # CoinDCX returns {"s": "ok", "data": [...]} typically
        candles = data.get("data", data) if isinstance(data, dict) else data
        if not candles or len(candles) < 50:
            return None, None
 
        rows = []
        for c in candles:
            # Expected keys: time/t, open/o, high/h, low/l, close/c, volume/v
            ts = c.get("time", c.get("t"))
            o  = c.get("open",  c.get("o"))
            h  = c.get("high",  c.get("h"))
            l  = c.get("low",   c.get("l"))
            cl = c.get("close", c.get("c"))
            v  = c.get("volume", c.get("v", 0))
            if None in (ts, o, h, l, cl):
                continue
            rows.append([ts, o, h, l, cl, v])
 
        if len(rows) < 50:
            return None, None
 
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        # Normalize timestamp: CoinDCX may give seconds or ms
        if df["timestamp"].iloc[0] > 10**12:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("timestamp", inplace=True)
        df = df.astype(float).sort_index()
        return df.tail(limit), "coindcx"
 
    except Exception:
        return None, None
 
 
# ── UPDATED fetch_ohlcv_failover — tries CoinDCX first, then ccxt exchanges ──
def fetch_ohlcv_failover(ticker, timeframe, limit):
    # 1. Try CoinDCX futures first (this is what you actually trade on)
    df, src = fetch_coindcx_futures(ticker, timeframe, limit)
    if df is not None:
        return df, src
 
    # 2. Fallback to ccxt exchanges (mexc, bybit, okx, gateio)
    for ex_id, ex in _exchanges:
        try:
            ohlcv = ex.fetch_ohlcv(ticker, timeframe, limit=limit)
            if not ohlcv or len(ohlcv) < 50:
                continue
            df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
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
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + (gain / (loss + 1e-10))))

def calc_atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm_adj  = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm_adj = minus_dm.where(minus_dm > plus_dm, 0.0)
    tr  = pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean() + 1e-10
    plus_di  = 100 * (plus_dm_adj.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm_adj.ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    return dx.ewm(alpha=1/period, adjust=False).mean()

def calc_choppiness_index(df, period=14):
    atr_sum = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs()
    ], axis=1).max(axis=1).rolling(period).sum()
    high_roll = df["high"].rolling(period).max()
    low_roll  = df["low"].rolling(period).min()
    denom = np.log10(period + 1e-10)
    return 100 * np.log10((atr_sum / (high_roll - low_roll + 1e-10)) + 1e-10) / denom

def calc_session_vwap(df):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    tpv = tp * df["volume"]
    day = df.index.date
    cum_tpv = pd.Series(tpv.values, index=df.index).groupby(day).cumsum()
    cum_vol  = df["volume"].groupby(day).cumsum()
    return cum_tpv / (cum_vol + 1e-10)

def calc_volume_profile(df, lookback=100, bins=24):
    data = df.tail(lookback)
    if len(data) < 5:
        return {"poc": None}
    price_min, price_max = data["low"].min(), data["high"].max()
    if price_max <= price_min:
        return {"poc": None}
    bin_edges   = np.linspace(price_min, price_max, bins + 1)
    vol_per_bin = np.zeros(bins)
    tp      = (data["high"] + data["low"] + data["close"]) / 3
    bin_idx = np.clip(np.searchsorted(bin_edges, tp.values) - 1, 0, bins - 1)
    for idx, vol in zip(bin_idx, data["volume"].values):
        vol_per_bin[idx] += vol
    poc_idx   = int(np.argmax(vol_per_bin))
    poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
    return {"poc": round(poc_price, 4)}

def detect_market_regime(df):
    atr    = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci     = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx    = calc_adx(df, CONFIG['ADX_PERIOD'])
    current_atr    = atr.iloc[-1]
    current_atr_ma = atr_ma.iloc[-1]
    current_ci     = ci.iloc[-1]
    current_adx    = adx.iloc[-1]
    atr_ratio      = (current_atr / current_atr_ma) if current_atr_ma > 0 else 1.0
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy     = current_ci > CONFIG['CHOPPINESS_TREND_MAX'] if not np.isnan(current_ci) else False
    is_trending   = current_adx >= CONFIG['ADX_MIN']            if not np.isnan(current_adx) else False
    if is_compressed:
        regime = "COMPRESSION"
    elif is_choppy or not is_trending:
        regime = "RANGING"
    else:
        regime = "TRENDING"
    return {
        "regime":     regime,
        "atr_ratio":  round(atr_ratio,   3) if not np.isnan(atr_ratio)   else None,
        "choppiness": round(current_ci,  2) if not np.isnan(current_ci)  else None,
        "adx":        round(current_adx, 2) if not np.isnan(current_adx) else None,
    }


# ── Structure / Patterns ────────────────────────────────
def detect_structure_live_pro(df, lookback=3):
    df = df.copy()
    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    events, trends = [None]*n, [None]*n
    trend = None
    last_swing_high = last_swing_low = None
    for i in range(lookback*2, n):
        lh = highs[i-2*lookback:i-lookback]
        rh = highs[i-lookback+1:i+1]
        ll = lows[i-2*lookback:i-lookback]
        rl = lows[i-lookback+1:i+1]
        if len(lh)==lookback and len(rh)==lookback:
            if highs[i-lookback] >= lh.max() and highs[i-lookback] >= rh.max():
                last_swing_high = highs[i-lookback]
            if lows[i-lookback] <= ll.min() and lows[i-lookback] <= rl.min():
                last_swing_low = lows[i-lookback]
        close = closes[i]
        if last_swing_high is not None and close > last_swing_high:
            events[i] = "BOS_BULL" if trend=="BULL" else "CHoCH_BULL"
            trend = "BULL"; last_swing_high = highs[i]
        elif last_swing_low is not None and close < last_swing_low:
            events[i] = "BOS_BEAR" if trend=="BEAR" else "CHoCH_BEAR"
            trend = "BEAR"; last_swing_low = lows[i]
        trends[i] = trend
    df["structure_event"] = events
    df["structure_trend"] = trends
    return df

def detect_candle_patterns_vectorized(df):
    df = df.copy()
    o,h,l,c = df["open"],df["high"],df["low"],df["close"]
    po,pc   = o.shift(1), c.shift(1)
    b,tr    = (c-o).abs(), h-l
    uw = h - np.maximum(o,c)
    lw = np.minimum(o,c) - l
    df["pat_sig"] = ""
    hammer   = (tr>0)&(lw>=2*b)&(uw<=0.3*b)&(b>=0.1*tr)
    star     = (tr>0)&(uw>=2*b)&(lw<=0.3*b)&(b>=0.1*tr)
    bull_eng = (pc<po)&(c>o)&(o<pc)&(c>po)
    bear_eng = (pc>po)&(c<o)&(o>pc)&(c<po)
    df.loc[hammer,   "pat_sig"] = "BUY"
    df.loc[star,     "pat_sig"] = "SELL"
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
    df.loc[(df["close"]<=roll_min_c)&(df["rsi"]>roll_min_r)&(df["rsi"]<50),"divergence"] = "BULL_DIV"
    df.loc[(df["close"]>=roll_max_c)&(df["rsi"]<roll_max_r)&(df["rsi"]>50),"divergence"] = "BEAR_DIV"
    return df

def detect_liquidity_sweep(df):
    data = df.tail(CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    if len(data) < 5: return None
    last   = data.iloc[-1]
    p_highs = data["high"].iloc[:-1]
    p_lows  = data["low"].iloc[:-1]
    if last["high"] > p_highs.max() and last["close"] < p_highs.max(): return "EQUAL_HIGH_SWEEP"
    if last["low"]  < p_lows.min()  and last["close"] > p_lows.min():  return "EQUAL_LOW_SWEEP"
    return None

def add_indicators_vectorized(df):
    df = df.copy()
    df["ema5"]  = calc_ema(df["close"], CONFIG['EMA_FAST'])
    df["ema20"] = calc_ema(df["close"], CONFIG['EMA_SLOW'])
    df["rsi"]   = calc_rsi(df["close"], CONFIG['RSI_PERIOD'])
    df["atr"]   = calc_atr(df, CONFIG['ATR_PERIOD'])
    df["adx"]   = calc_adx(df, CONFIG['ADX_PERIOD'])
    df["vwap"]  = calc_session_vwap(df)
    return df

def analyze_timeframe(df):
    df    = add_indicators_vectorized(df)
    df    = detect_candle_patterns_vectorized(df)
    df    = detect_pro_divergence_vectorized(df)
    df    = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    sweep = detect_liquidity_sweep(df)
    vp    = calc_volume_profile(df, CONFIG['VOLUME_PROFILE_LOOKBACK'], CONFIG['VOLUME_PROFILE_BINS'])
    regime = detect_market_regime(df)
    last  = df.iloc[-1]
    return {
        "structure_event": last["structure_event"],
        "structure_trend": last["structure_trend"],
        "adx":   last["adx"], "price": last["close"], "vwap": last["vwap"],
        "ema5":  last["ema5"], "ema20": last["ema20"], "rsi":  last["rsi"],
        "atr":   last["atr"],
        "pattern": last["pat_sig"], "divergence": last["divergence"],
        "sweep": sweep, "vp": vp, "regime": regime,
    }


# ── HTF Bias — SCALPER uses 15m + 1h ───────────────────
def get_htf_bias(snap_15m, snap_1h):
    score = 0
    for snap, weight in [(snap_15m, 1.0), (snap_1h, 1.5)]:
        if snap["structure_trend"] == "BULL": score += weight
        elif snap["structure_trend"] == "BEAR": score -= weight
        score += weight*0.5 if snap["ema5"] > snap["ema20"] else -weight*0.5
        if not pd.isna(snap["rsi"]):
            if snap["rsi"] > 55:   score += weight*0.3
            elif snap["rsi"] < 45: score -= weight*0.3
    if score >= 1.0:  return "BULLISH"
    if score <= -1.0: return "BEARISH"
    return "NEUTRAL"

# ── LTF Scores — SCALPER uses 1m + 5m ──────────────────
def get_ltf_scores(snap_1m, snap_5m):
    buy_score, sell_score = 0.0, 0.0
    for snap, w in [(snap_1m, 1.0), (snap_5m, 1.2)]:
        if snap["pattern"] == "BUY":   buy_score  += 2*w
        elif snap["pattern"] == "SELL": sell_score += 2*w
        if snap["divergence"] == "BULL_DIV":  buy_score  += 3*w
        elif snap["divergence"] == "BEAR_DIV": sell_score += 3*w
        if snap["sweep"] == "EQUAL_LOW_SWEEP":  buy_score  += 3*w
        elif snap["sweep"] == "EQUAL_HIGH_SWEEP": sell_score += 3*w
        if snap["structure_event"] in ("BOS_BULL","CHoCH_BULL"):
            buy_score  += (2 if "CHoCH" in snap["structure_event"] else 1.5)*w
        elif snap["structure_event"] in ("BOS_BEAR","CHoCH_BEAR"):
            sell_score += (2 if "CHoCH" in snap["structure_event"] else 1.5)*w
        if snap["vp"]["poc"] is not None:
            buy_score  += 0.5*w if snap["price"] >  snap["vp"]["poc"] else 0
            sell_score += 0.5*w if snap["price"] <= snap["vp"]["poc"] else 0
        if not pd.isna(snap["vwap"]):
            buy_score  += 0.5*w if snap["price"] >  snap["vwap"] else 0
            sell_score += 0.5*w if snap["price"] <= snap["vwap"] else 0
        if snap["ema5"] > snap["ema20"]: buy_score  += 0.5*w
        else:                             sell_score += 0.5*w
        if not pd.isna(snap["rsi"]):
            if snap["rsi"] < 35:   buy_score  += 1.0*w
            elif snap["rsi"] > 65: sell_score += 1.0*w
    return round(buy_score, 2), round(sell_score, 2)

def decide_direction(buy_score, sell_score, htf_bias,
                     entry_adx, regime_1m, regime_5m, entry_rsi=None):
    # --- ADX filter ---                      
    if pd.isna(entry_adx) or entry_adx < CONFIG['ADX_MIN']:
        return None, f"NO TREND (ADX {entry_adx:.1f} < {CONFIG['ADX_MIN']})"
    # --- RSI filter ---    
    if entry_rsi is not None and not pd.isna(entry_rsi):
        if entry_rsi > CONFIG['RSI_OVERBOUGHT']:
            return None, f"BLOCKED (RSI overbought {entry_rsi:.1f})"
        if entry_rsi < CONFIG['RSI_OVERSOLD']:
            return None, f"BLOCKED (RSI oversold {entry_rsi:.1f})"

    # --- 👉 YAHAN ADD KARO ---
    if regime_1m["regime"] != "TRENDING" or regime_5m["regime"] != "TRENDING":
        return None, "BLOCKED (not trending)"

    # --- Compression / Ranging filters ---                     
    if regime_1m["regime"] == "COMPRESSION" and regime_5m["regime"] != "TRENDING":
        return None, f"BLOCKED (compression, wait breakout)"
    if regime_5m["regime"] == "RANGING":
        return None, f"BLOCKED (5m choppy CI {regime_5m['choppiness']})"

    # --- Signal scoring ---                     
    if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
        if htf_bias in ("BULLISH","NEUTRAL"):
            return "BUY", "BUY ✅"
    if sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
        if htf_bias in ("BEARISH","NEUTRAL"):
            return "SELL", "SELL ✅"
    return None, "WAIT (score/bias aligned nahi)"

def calc_tp_sl(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    sl_dist = round(CONFIG['SL_ATR_MULT'] * atr, 4)
    tp_dist = round(CONFIG['TP_ATR_MULT'] * atr, 4)
    if direction == "BUY":
        return round(price+tp_dist, 4), round(price-sl_dist, 4)
    return round(price-tp_dist, 4), round(price+sl_dist, 4)


# ── FAST BACKTEST ───────────────────────────────────────
def run_backtest(symbol, timeframe="5m"):
    """
    Vectorized backtest with richer stats:
    win rate, profit factor, expectancy, avg R:R, last 10 trades.
    """
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['BACKTEST_CANDLES'])
    if df is None:
        return {"error": "no data"}
 
    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
 
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)
    results = []
    WINDOW  = CONFIG['BACKTEST_OUTCOME_WINDOW']
 
    for i in range(60, n - WINDOW):
        rsi   = df["rsi"].iloc[i]
        adx   = df["adx"].iloc[i]
        atr   = df["atr"].iloc[i]
        ema5  = df["ema5"].iloc[i]
        ema20 = df["ema20"].iloc[i]
        vwap  = df["vwap"].iloc[i]
        pat   = df["pat_sig"].iloc[i]
        div   = df["divergence"].iloc[i]
        struct = df["structure_event"].iloc[i]
        price = closes[i]
 
        if pd.isna(adx) or adx < CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > CONFIG['RSI_OVERBOUGHT'] or rsi < CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue
 
        buy_score, sell_score = 0.0, 0.0
        if pat == "BUY":   buy_score  += 2
        elif pat == "SELL": sell_score += 2
        if div == "BULL_DIV":  buy_score  += 3
        elif div == "BEAR_DIV": sell_score += 3
        if struct in ("BOS_BULL","CHoCH_BULL"): buy_score  += 2
        elif struct in ("BOS_BEAR","CHoCH_BEAR"): sell_score += 2
        if not pd.isna(vwap):
            if price > vwap: buy_score  += 0.5
            else:            sell_score += 0.5
        if ema5 > ema20: buy_score  += 0.5
        else:             sell_score += 0.5
        if rsi < 35:   buy_score  += 1.0
        elif rsi > 65: sell_score += 1.0
 
        # ── NEW: score-gap filter — close scores get skipped (weak conviction) ──
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
        for j in range(i+1, min(i+WINDOW+1, n)):
            fh = highs[j]
            fl = lows[j]
            if direction == "BUY":
                if fh >= tp: outcome = "WIN";  exit_price = tp; break
                if fl <= sl: outcome = "LOSS"; exit_price = sl; break
            else:
                if fl <= tp: outcome = "WIN";  exit_price = tp; break
                if fh >= sl: outcome = "LOSS"; exit_price = sl; break
 
        if outcome == "OPEN": continue
 
        # ── NEW: P&L in % terms, fees included ──
        if direction == "BUY":
            pnl_pct = (exit_price - price) / price * 100
        else:
            pnl_pct = (price - exit_price) / price * 100
        pnl_pct -= CONFIG['FEE_PCT']  # round-trip fee/slippage deduction
 
        results.append({
            "time":      df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction,
            "entry":     round(price, 2),
            "tp":        round(tp, 2),
            "sl":        round(sl, 2),
            "outcome":   outcome,
            "pnl_pct":   round(pnl_pct, 4),
        })
 
    if not results:
        return {
            "symbol": symbol, "timeframe": timeframe,
            "total_trades": 0, "win_rate": 0,
            "message": "No signals in this window"
        }
 
    wins   = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total  = len(wins) + len(losses)
 
    # ── NEW: Profit Factor, Expectancy, Avg R:R ──
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss   = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
 
    avg_win  = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0
 
    expectancy = round((win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss), 4)
    avg_rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else None
 
    return {
        "symbol":         symbol,
        "timeframe":      timeframe,
        "candles_tested": CONFIG['BACKTEST_CANDLES'],
        "total_trades":   total,
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       win_rate,
        "profit_factor":  profit_factor,   # >1.5 generally healthy
        "expectancy_pct": expectancy,      # avg expected return per trade, fees included
        "avg_rr":         avg_rr,          # avg win size / avg loss size
        "recent_trades":  results[-10:],
    }


import time as _time

# ── HTF cache — 15m + 1h — 30s ─────────────────────────
_HTF_CACHE     = {}
_HTF_CACHE_TTL = 30

def _get_htf_bias_cached(symbol):
    now    = _time.time()
    cached = _HTF_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < _HTF_CACHE_TTL:
        return cached["bias"]
    htf_bias = "NEUTRAL"
    df_15m, _ = fetch_ohlcv_failover(symbol, "15m", CONFIG['LIMIT'])
    df_1h,  _ = fetch_ohlcv_failover(symbol, "1h",  CONFIG['LIMIT'])
    if df_15m is not None and df_1h is not None:
        snap_15m = analyze_timeframe(df_15m)
        snap_1h  = analyze_timeframe(df_1h)
        htf_bias = get_htf_bias(snap_15m, snap_1h)
    _HTF_CACHE[symbol] = {"bias": htf_bias, "ts": now}
    return htf_bias

# ── LTF cache — 1m + 5m — 15s ──────────────────────────
_LTF_CACHE     = {}
_LTF_CACHE_TTL = 15

def _get_ltf_snaps_cached(symbol):
    now    = _time.time()
    cached = _LTF_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < _LTF_CACHE_TTL:
        return cached["snap_1m"], cached["snap_5m"]
    df_1m, _ = fetch_ohlcv_failover(symbol, "1m", CONFIG['LIMIT'])
    df_5m, _ = fetch_ohlcv_failover(symbol, "5m", CONFIG['LIMIT'])
    snap_1m = analyze_timeframe(df_1m) if df_1m is not None else None
    snap_5m = analyze_timeframe(df_5m) if df_5m is not None else None
    _LTF_CACHE[symbol] = {"snap_1m": snap_1m, "snap_5m": snap_5m, "ts": now}
    return snap_1m, snap_5m


# ── PUBLIC ENTRY POINT ───────────────────────────────────
def analyze(symbol, timeframe="1m"):
    df_entry, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
    if df_entry is None:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}

    snap_entry = analyze_timeframe(df_entry)
    price   = float(snap_entry["price"])
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
        "symbol":     symbol,
        "timeframe":  timeframe,
        "price":      round(price, 4),
        "rsi":        round(rsi_now, 2) if rsi_now is not None else None,
        "signal":     signal,
        "reason":     reason,
        "buy_score":  buy_score,
        "sell_score": sell_score,
        "htf_bias":   htf_bias,
        "regime":     snap_entry["regime"]["regime"],
        "structure":  snap_entry["structure_event"],
        "exchange":   ex_id,
        "entry":      round(price, 4) if direction else None,
        "tp":         tp,
        "sl":         sl,
        "atr":        round(atr_now, 4) if atr_now else None,
    }

# ── FULL MULTI-TIMEFRAME BACKTEST (mirrors live analyze() logic) ──────
def _vectorized_regime(df):
    """Per-row regime classification (vectorized version of detect_market_regime)."""
    atr    = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci     = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx    = calc_adx(df, CONFIG['ADX_PERIOD'])

    atr_ratio = atr / atr_ma.replace(0, np.nan)
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy     = ci > CONFIG['CHOPPINESS_TREND_MAX']
    is_trending   = adx >= CONFIG['ADX_MIN']

    regime = pd.Series("RANGING", index=df.index)
    regime[is_trending & ~is_choppy & ~is_compressed] = "TRENDING"
    regime[is_compressed] = "COMPRESSION"
    return regime, ci, adx


def _build_tf_features(df):
    """Compute all per-row indicators/events needed for scoring, vectorized."""
    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    regime, ci, adx_full = _vectorized_regime(df)
    df["regime_label"] = regime
    return df


def _htf_bias_series(df15, df1h):
    """Vectorized version of get_htf_bias, per-row, for merge_asof."""
    def score_component(df, weight):
        s = pd.Series(0.0, index=df.index)
        s += np.where(df["structure_trend"] == "BULL", weight,
              np.where(df["structure_trend"] == "BEAR", -weight, 0.0))
        s += np.where(df["ema5"] > df["ema20"], weight*0.5, -weight*0.5)
        s += np.where(df["rsi"] > 55, weight*0.3, np.where(df["rsi"] < 45, -weight*0.3, 0.0))
        return s

    s15 = score_component(df15, 1.0).rename("s15")
    s1h = score_component(df1h, 1.5).rename("s1h")

    out15 = pd.DataFrame({"time": df15.index, "s15": s15.values})
    out1h = pd.DataFrame({"time": df1h.index, "s1h": s1h.values})
    merged = pd.merge_asof(out15.sort_values("time"), out1h.sort_values("time"),
                            on="time", direction="backward")
    merged["score"] = merged["s15"] + merged["s1h"]
    merged["bias"] = np.where(merged["score"] >= 1.0, "BULLISH",
                       np.where(merged["score"] <= -1.0, "BEARISH", "NEUTRAL"))
    merged = merged.set_index("time")
    return merged["bias"]


def _ltf_score_series(df1m, df5m):
    """Vectorized version of get_ltf_scores, per-row, for merge_asof."""
    def score_component(df, w):
        buy  = pd.Series(0.0, index=df.index)
        sell = pd.Series(0.0, index=df.index)
        buy  += np.where(df["pat_sig"] == "BUY",  2*w, 0.0)
        sell += np.where(df["pat_sig"] == "SELL", 2*w, 0.0)
        buy  += np.where(df["divergence"] == "BULL_DIV", 3*w, 0.0)
        sell += np.where(df["divergence"] == "BEAR_DIV", 3*w, 0.0)
        is_choch = df["structure_event"].astype(str).str.contains("CHoCH")
        bull_evt = df["structure_event"].isin(["BOS_BULL", "CHoCH_BULL"])
        bear_evt = df["structure_event"].isin(["BOS_BEAR", "CHoCH_BEAR"])
        buy  += np.where(bull_evt, np.where(is_choch, 2*w, 1.5*w), 0.0)
        sell += np.where(bear_evt, np.where(is_choch, 2*w, 1.5*w), 0.0)
        buy  += np.where(df["close"] > df["vwap"], 0.5*w, 0.0)
        sell += np.where(df["close"] <= df["vwap"], 0.5*w, 0.0)
        buy  += np.where(df["ema5"] > df["ema20"], 0.5*w, 0.0)
        sell += np.where(df["ema5"] <= df["ema20"], 0.5*w, 0.0)
        buy  += np.where(df["rsi"] < 35, 1.0*w, 0.0)
        sell += np.where(df["rsi"] > 65, 1.0*w, 0.0)
        return buy, sell

    b1, s1 = score_component(df1m, 1.0)
    b5, s5 = score_component(df5m, 1.2)

    out1m = pd.DataFrame({"time": df1m.index, "b1": b1.values, "s1": s1.values})
    out5m = pd.DataFrame({"time": df5m.index, "b5": b5.values, "s5": s5.values})
    merged = pd.merge_asof(out1m.sort_values("time"), out5m.sort_values("time"),
                            on="time", direction="backward")
    merged["buy_score"]  = round((merged["b1"] + merged["b5"]), 2)
    merged["sell_score"] = round((merged["s1"] + merged["s5"]), 2)
    merged = merged.set_index("time")
    return merged[["buy_score", "sell_score"]]


def run_backtest_full(symbol, entry_timeframe="15m"):
    """
    Backtest that mirrors the LIVE multi-timeframe strategy:
    - HTF bias from 15m + 1h
    - LTF score from 1m + 5m
    - Regime/ADX/RSI filters same as decide_direction()
    NOTE: liquidity-sweep & volume-profile(POC) terms are omitted (too
    expensive per-bar); everything else mirrors analyze().
    """
    limit = CONFIG['BACKTEST_CANDLES']

    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, limit)
    df_1m,  _ = fetch_ohlcv_failover(symbol, "1m",  limit)
    df_5m,  _ = fetch_ohlcv_failover(symbol, "5m",  limit)
    df_15m, _ = fetch_ohlcv_failover(symbol, "15m", limit)
    df_1h,  _ = fetch_ohlcv_failover(symbol, "1h",  limit)

    if any(x is None for x in [df_entry, df_1m, df_5m, df_15m, df_1h]):
        return {"error": "insufficient data across timeframes"}

    df_entry = _build_tf_features(df_entry)
    df_1m    = _build_tf_features(df_1m)
    df_5m    = _build_tf_features(df_5m)
    df_15m   = _build_tf_features(df_15m)
    df_1h    = _build_tf_features(df_1h)

    bias_series = _htf_bias_series(df_15m, df_1h)
    score_df    = _ltf_score_series(df_1m, df_5m)

    # Align bias + scores onto entry timeframe timestamps (backward = no lookahead)
    entry_times = pd.DataFrame({"time": df_entry.index})
    bias_aligned = pd.merge_asof(entry_times, bias_series.rename("bias").reset_index(),
                                  on="time", direction="backward")
    score_aligned = pd.merge_asof(entry_times, score_df.reset_index(),
                                   on="time", direction="backward")

    df_entry = df_entry.reset_index()
    df_entry["bias"]       = bias_aligned["bias"]
    df_entry["buy_score"]  = score_aligned["buy_score"]
    df_entry["sell_score"] = score_aligned["sell_score"]

    closes = df_entry["close"].values
    highs  = df_entry["high"].values
    lows   = df_entry["low"].values
    n      = len(df_entry)
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
        if regime == "RANGING": continue   # same as decide_direction's choppy block

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
        for j in range(i+1, min(i+WINDOW+1, n)):
            fh, fl = highs[j], lows[j]
            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= sl: outcome, exit_price = "LOSS", sl; break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= sl: outcome, exit_price = "LOSS", sl; break
        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price)/price*100 if direction == "BUY"
                   else (price - exit_price)/price*100) - CONFIG['FEE_PCT']

        results.append({
            "time": row["timestamp"].strftime("%m-%d %H:%M") if "timestamp" in row else str(row.name),
            "direction": direction, "entry": round(price,2), "tp": round(tp,2), "sl": round(sl,2),
            "outcome": outcome, "pnl_pct": round(pnl_pct,4),
        })

    if not results:
        return {"symbol": symbol, "timeframe": entry_timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No signals in this window"}

    wins   = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    total  = len(wins) + len(losses)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss   = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit/gross_loss, 2) if gross_loss > 0 else None
    avg_win  = round(gross_profit/len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss/len(losses), 4) if losses else 0.0
    win_rate = round(len(wins)/total*100, 1) if total > 0 else 0
    expectancy = round((win_rate/100*avg_win) - ((1-win_rate/100)*avg_loss), 4)
    avg_rr = round(avg_win/avg_loss, 2) if avg_loss > 0 else None

    return {
        "symbol": symbol, "timeframe": entry_timeframe, "candles_tested": limit,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy, "avg_rr": avg_rr,
        "recent_trades": results[-10:],
        "note": "Full multi-timeframe backtest (bias+score aligned). Liquidity sweep & POC terms omitted.",
    }

# ── FACTOR-ISOLATION BACKTEST ───────────────────────────
# Tests each signal component SEPARATELY to find which ones
# actually have edge, and which are just noise.

def run_factor_backtest(symbol, timeframe="15m"):
    """
    Tests 5 strategies independently on the SAME data:
    1. Liquidity Sweep only
    2. Structure Break (BOS/CHoCH) only
    3. Divergence only
    4. Candle Pattern only
    5. EMA crossover only (simple baseline for comparison)
    Returns profit factor + win rate for each, so you can see
    which factor actually has edge.
    """
    limit = CONFIG['BACKTEST_CANDLES']
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

    def simulate(direction_fn, label):
        """direction_fn(i) -> 'BUY' / 'SELL' / None for row i"""
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
            for j in range(i+1, min(i+WINDOW+1, n)):
                fh, fl = highs[j], lows[j]
                if direction == "BUY":
                    if fh >= tp: outcome, exit_price = "WIN", tp; break
                    if fl <= sl: outcome, exit_price = "LOSS", sl; break
                else:
                    if fl <= tp: outcome, exit_price = "WIN", tp; break
                    if fh >= sl: outcome, exit_price = "LOSS", sl; break
            if outcome == "OPEN": continue

            pnl_pct = ((exit_price - price)/price*100 if direction == "BUY"
                       else (price - exit_price)/price*100) - CONFIG['FEE_PCT']
            results.append({"outcome": outcome, "pnl_pct": pnl_pct})

        wins   = [r for r in results if r["outcome"] == "WIN"]
        losses = [r for r in results if r["outcome"] == "LOSS"]
        total  = len(wins) + len(losses)
        if total == 0:
            return {"label": label, "total_trades": 0, "note": "no signals"}

        gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
        gross_loss   = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
        profit_factor = round(gross_profit/gross_loss, 2) if gross_loss > 0 else None
        win_rate = round(len(wins)/total*100, 1)
        avg_win  = round(gross_profit/len(wins), 4) if wins else 0.0
        avg_loss = round(gross_loss/len(losses), 4) if losses else 0.0
        expectancy = round((win_rate/100*avg_win) - ((1-win_rate/100)*avg_loss), 4)

        return {
            "label": label, "total_trades": total, "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate, "profit_factor": profit_factor, "expectancy_pct": expectancy,
        }

    # ── Factor 1: Liquidity Sweep only ──
    def f_sweep(i):
        data = df.iloc[max(0, i-CONFIG['LIQUIDITY_SWEEP_LOOKBACK']):i+1]
        if len(data) < 5: return None
        last = data.iloc[-1]
        p_highs, p_lows = data["high"].iloc[:-1], data["low"].iloc[:-1]
        if last["high"] > p_highs.max() and last["close"] < p_highs.max(): return "SELL"
        if last["low"] < p_lows.min() and last["close"] > p_lows.min(): return "BUY"
        return None

    # ── Factor 2: Structure Break only ──
    def f_structure(i):
        ev = df["structure_event"].iloc[i]
        if ev in ("BOS_BULL", "CHoCH_BULL"): return "BUY"
        if ev in ("BOS_BEAR", "CHoCH_BEAR"): return "SELL"
        return None

    # ── Factor 3: Divergence only ──
    def f_divergence(i):
        d = df["divergence"].iloc[i]
        if d == "BULL_DIV": return "BUY"
        if d == "BEAR_DIV": return "SELL"
        return None

    # ── Factor 4: Candle Pattern only ──
    def f_pattern(i):
        p = df["pat_sig"].iloc[i]
        if p == "BUY": return "BUY"
        if p == "SELL": return "SELL"
        return None

    # ── Factor 5: Simple EMA crossover baseline (for comparison) ──
    def f_ema_baseline(i):
        if i < 1: return None
        cross_up   = df["ema5"].iloc[i-1] <= df["ema20"].iloc[i-1] and df["ema5"].iloc[i] > df["ema20"].iloc[i]
        cross_down = df["ema5"].iloc[i-1] >= df["ema20"].iloc[i-1] and df["ema5"].iloc[i] < df["ema20"].iloc[i]
        if cross_up: return "BUY"
        if cross_down: return "SELL"
        return None

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": limit,
        "factors": [
            simulate(f_sweep, "1. Liquidity Sweep only"),
            simulate(f_structure, "2. Structure Break (BOS/CHoCH) only"),
            simulate(f_divergence, "3. Divergence only"),
            simulate(f_pattern, "4. Candle Pattern only"),
            simulate(f_ema_baseline, "5. EMA Crossover (baseline)"),
        ]
    }
    # ── COMBINED FACTOR BACKTEST (2+ factors must agree) ────
def run_combined_backtest(symbol, timeframe="15m", min_agree=2, strong_adx=25, use_breakeven=True):
    """
    Tests combined signal: trade only when >= min_agree factors
    agree on direction (BUY or SELL), AND adx >= strong_adx (strong trend only).
    Also applies breakeven-move logic to cut losses early.
    """
    limit = CONFIG['BACKTEST_CANDLES']
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []

    def get_factor_votes(i):
        """Returns list of 'BUY'/'SELL' votes from each factor at row i."""
        votes = []

        # Liquidity sweep
        data = df.iloc[max(0, i-CONFIG['LIQUIDITY_SWEEP_LOOKBACK']):i+1]
        if len(data) >= 5:
            last = data.iloc[-1]
            p_highs, p_lows = data["high"].iloc[:-1], data["low"].iloc[:-1]
            if last["high"] > p_highs.max() and last["close"] < p_highs.max(): votes.append("SELL")
            elif last["low"] < p_lows.min() and last["close"] > p_lows.min(): votes.append("BUY")

        # Structure break
        ev = df["structure_event"].iloc[i]
        if ev in ("BOS_BULL", "CHoCH_BULL"): votes.append("BUY")
        elif ev in ("BOS_BEAR", "CHoCH_BEAR"): votes.append("SELL")

        # Divergence
        d = df["divergence"].iloc[i]
        if d == "BULL_DIV": votes.append("BUY")
        elif d == "BEAR_DIV": votes.append("SELL")

        # Candle pattern
        p = df["pat_sig"].iloc[i]
        if p == "BUY": votes.append("BUY")
        elif p == "SELL": votes.append("SELL")

        # EMA crossover
        if i >= 1:
            cross_up   = df["ema5"].iloc[i-1] <= df["ema20"].iloc[i-1] and df["ema5"].iloc[i] > df["ema20"].iloc[i]
            cross_down = df["ema5"].iloc[i-1] >= df["ema20"].iloc[i-1] and df["ema5"].iloc[i] < df["ema20"].iloc[i]
            if cross_up: votes.append("BUY")
            elif cross_down: votes.append("SELL")

        return votes

    for i in range(60, n - WINDOW):
        adx = df["adx"].iloc[i]
        atr = df["atr"].iloc[i]
        if pd.isna(adx) or pd.isna(atr): continue
        if adx < strong_adx: continue   # ── strong trend filter ──

        votes = get_factor_votes(i)
        buy_votes  = votes.count("BUY")
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

        # ── breakeven logic ──
        breakeven_dist = atr * 0.5  # move SL to entry after price moves 0.5*ATR in favor
        sl_moved = False
        current_sl = sl

        outcome, exit_price = "OPEN", None
        for j in range(i+1, min(i+WINDOW+1, n)):
            fh, fl = highs[j], lows[j]

            if use_breakeven and not sl_moved:
                if direction == "BUY" and fh >= price + breakeven_dist:
                    current_sl = price
                    sl_moved = True
                elif direction == "SELL" and fl <= price - breakeven_dist:
                    current_sl = price
                    sl_moved = True

            if direction == "BUY":
                if fh >= tp: outcome, exit_price = "WIN", tp; break
                if fl <= current_sl:
                    outcome = "BREAKEVEN" if sl_moved else "LOSS"
                    exit_price = current_sl
                    break
            else:
                if fl <= tp: outcome, exit_price = "WIN", tp; break
                if fh >= current_sl:
                    outcome = "BREAKEVEN" if sl_moved else "LOSS"
                    exit_price = current_sl
                    break

        if outcome == "OPEN": continue

        pnl_pct = ((exit_price - price)/price*100 if direction == "BUY"
                   else (price - exit_price)/price*100) - CONFIG['FEE_PCT']

        results.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": round(price,2), "tp": round(tp,2), "sl": round(sl,2),
            "outcome": outcome, "pnl_pct": round(pnl_pct,4), "votes": votes,
        })

    if not results:
        return {"symbol": symbol, "timeframe": timeframe, "total_trades": 0,
                "win_rate": 0, "message": "No signals — try lowering min_agree or strong_adx"}

    wins   = [r for r in results if r["outcome"] in ("WIN", "BREAKEVEN") and r["pnl_pct"] > 0]
    losses = [r for r in results if r["pnl_pct"] <= 0]
    total  = len(results)
    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss   = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit/gross_loss, 2) if gross_loss > 0 else None
    win_rate = round(len(wins)/total*100, 1) if total > 0 else 0
    avg_win  = round(gross_profit/len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss/len(losses), 4) if losses else 0.0
    expectancy = round((win_rate/100*avg_win) - ((1-win_rate/100)*avg_loss), 4)

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": limit,
        "min_agree": min_agree, "strong_adx": strong_adx, "use_breakeven": use_breakeven,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
        "recent_trades": results[-10:],
    }
