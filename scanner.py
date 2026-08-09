"""
SCALPING BOT — Multi-Factor Engine + Liquidity Concepts Combo  (v5)
================================================================================
Base engine (EMA/RSI/ADX/Structure/Divergence/VolumeProfile/Regime) +
Liquidity Concepts (BSL/SSL, Sweep, FVG, Inducement, Equal-Level Density).

WHAT CHANGED IN v5 — 1m REMOVED EVERYWHERE, AND THE FEE NUMBER IS NOW REAL.

  F19 1m IS GONE. Not disabled — removed. It is absent from
      COINDCX_RESOLUTION_MAP, TF_SECONDS and TIMEFRAME_CONFIRM_MAP, so any
      code path that still asks for it gets None from the fetcher rather
      than silently trading a timeframe that cannot pay its own fees.

      The arithmetic: a 1m ATR on BTC is roughly 0.05% of price. At
      TP_ATR_MULT 2.2 that is a 0.11% gross target against a 0.18%
      round-trip cost. The target is smaller than the toll. No entry filter,
      no confluence score and no amount of tuning fixes a trade whose best
      case loses money. 5m is marginal and 15m is where the arithmetic
      starts to work, which is why those two are what remain.

  F20 THE BACKTEST LADDER MOVED UP ONE STEP. run_backtest_full() used to
      read 1m for entry scores, 5m for confirmation and 15m for bias. With
      1m gone it now reads 5m for entry scores, 15m for confirmation and 1h
      for bias. The relationships between the three are unchanged — the same
      3x-ish spacing, the same shift(1) look-ahead guard — so the numbers
      remain comparable in structure to the old ones, just on slower bars.

  F21 ROUND_TRIP_COST_PCT IS NOW 0.18, NOT 0.10. The old value was a
      placeholder with "PUT YOUR OWN NUMBER HERE" next to it, and it was
      roughly half of reality. CoinDCX futures standard tier charges 0.075%
      taker per side. This engine's live signals are market entries, so both
      sides pay taker: 0.075 x 2 = 0.15%, plus 18% GST on the fee = 0.177%,
      rounded to 0.18. Spread is on top of that and is not modelled.

      Expect fewer signals. cost_gate() requires a target of at least
      MIN_TP_COST_RATIO (3.0) x cost, which is now 0.54% instead of 0.30%.
      Setups that vanish were never profitable — they were being measured
      against a cost that did not exist. To revert, change this one line.

  F22 PARAMETERS RENAMED FROM TIMEFRAME TO ROLE. decide_direction() took
      regime_1m/regime_5m and get_ltf_scores() took snap_1m/snap_5m, which
      stopped being true the moment the entry timeframe changed. They are
      now regime_entry/regime_confirm and snap_entry/snap_confirm. Nothing
      about the logic changed; the names now describe what the arguments
      actually are.

--------------------------------------------------------------------------------
WHAT CHANGED IN v3/v4 — every edit tagged "# FIX v3:" / "# FIX v4:" inline.

  F1  Wilder RSI and Wilder ATR. calc_rsi/calc_atr used rolling().mean()
      (Cutler's), while calc_adx internally used ewm (Wilder). Two different
      ATR definitions in one file, and neither matched the TradingView chart
      sitting next to the dashboard.

  F2  CLOSED-CANDLE RULE. analyze_timeframe() read df.iloc[-1] — the candle
      still forming. Every indicator, candle pattern and BOS/CHoCH flipped on
      each poll. analyze_timeframe(closed_only=True) now drops the forming
      bar; all live paths pass True, backtests pass False.

  F3  COST GATE. A trade whose gross target is ~2x its own cost cannot be
      profitable at any realistic win rate. cost_gate() rejects those setups
      outright, live and in backtest.

  F4  FEE_PCT (0.04) was deducted ONCE. Taker fees are charged per side.
      Replaced by ROUND_TRIP_COST_PCT covering entry + exit + spread.

  F5  STOP CHECKED FIRST. Every backtest loop tested TP before SL, so any
      candle spanning both levels was scored a WIN. Now the stop wins
      ambiguous candles.

  F6  TIMEOUT TRADES NO LONGER DELETED. `if outcome == "OPEN": continue`
      silently removed every trade that chopped sideways — exactly the
      trades that in reality exit flat and eat the full fee.

  F7  ENTRY AT NEXT BAR'S OPEN. Backtests filled at the close of the signal
      bar, a price not knowable until that bar ended.

  F8  NEUTRAL HTF BIAS NOW BLOCKS BOTH DIRECTIONS. Previously a NEUTRAL
      higher timeframe permitted longs AND shorts.

  F9  NaN NO LONGER VOTES BEARISH. `if ema5 > ema20: buy else: sell` sends
      any NaN into the sell branch.

  F10 LOOK-AHEAD REMOVED from run_backtest_full(). The index is candle OPEN
      time but each row's indicators are computed through that candle's
      CLOSE, so merge_asof handed a fast bar a slow row that did not exist
      yet. The bias series is now shift(1)ed before alignment.

  F11 candles_tested reports len(df), not the CONFIG constant.

  F12 REGIME NOW HONOURS PER-ASSET ADX_MIN.

  F13 calc_tp_sl_with_slippage() uses _px(), not round(x, 4).

  F14 CoinDCX resolutions for 1h and 4h added.

  F15 MAX_CONSECUTIVE_LOSSES is now enforced in RiskManager.

  F16 Backtests report blocked_by_cost_gate.

  F17 CVD pressure is volume-normalised, so one threshold works on every
      symbol regardless of how much it trades.

  F18 The card reports both the entry and confirmation regime, so
      "Regime: TRENDING" next to "BLOCKED (Choppy Flat Zones)" is no longer
      a mystery — the confirm frame was the one blocking.

KNOWN REMAINING GAP (not fixed here, needs a decision):
  run_backtest_full() still does not apply the confluence gate, the CVD
  check or the blow-off veto that live analyze() and run_backtest() apply.
  Its numbers will therefore be more permissive than live. Treat
  run_backtest() as the closer proxy until that parity work is done.

⚠️ Educational / research tool. Not financial advice. No backtest or live
   signal guarantees future profit. Forward-test on paper first, and only
   risk capital you can afford to lose, sized per the risk rules below.
"""

import ccxt
import requests
import pandas as pd
import numpy as np
import time as _t
from blowoff import detect_blowoff, blowoff_series, blowoff_gate, blowoff_gate_row

import sizing  # risk-first position sizing (replaces profit-target sizing)

COINDCX_PAIR_MAP = {
    "BTC/USDT:USDT": "B-BTC_USDT",
    "ETH/USDT:USDT": "B-ETH_USDT",
    "DEXE/USDT:USDT": "B-DEXE_USDT",
    "BANK/USDT:USDT": "B-BANK_USDT",   # VERIFY exact pair name on CoinDCX
}

# FIX v5 (F19): 1m removed. A request for it now returns None from
# fetch_coindcx_futures() instead of quietly succeeding, which is the point —
# a timeframe whose target is smaller than its fee should fail loudly rather
# than produce signals nobody should take.
# FIX v3 (F14): 1h and 4h are present because TIMEFRAME_CONFIRM_MAP asks for
# them (15m->1h, 1h->4h); without them those confirmation snapshots silently
# fell through to a different exchange with different prints.
COINDCX_RESOLUTION_MAP = {
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
}

# FIX v3 (F14): matching seconds table, used to compute the "from" timestamp.
TF_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}

# The only timeframes this engine will scan or trade. Anything outside this
# tuple has not been checked against cost_reality_check() and should not be
# wired into a live path without doing so first.
SUPPORTED_TIMEFRAMES = ("5m", "15m", "1h", "4h")

CONFIG = {
    'EMA_FAST': 5,
    'EMA_SLOW': 20,
    'RSI_PERIOD': 14,     # FIX v3 (F1): was 7. With Wilder smoothing a 7-period
                          # RSI is extremely noisy and its 15/85 gates stop meaning
                          # anything. 14 is the period the thresholds assume.
    'ATR_PERIOD': 14,
    'ADX_PERIOD': 14,
    'ADX_MIN': 18,
    'SWING_LOOKBACK': 3,
    'LIQUIDITY_SWEEP_LOOKBACK': 20,
    'VOLUME_PROFILE_LOOKBACK': 100,
    'VOLUME_PROFILE_BINS': 24,
    'SCORE_THRESHOLD': 5.0,
    'SCORE_GAP_MIN': 3.5,

    # ── FIX v5 (F21): the real number, not a placeholder ────────────────
    # CoinDCX futures standard tier: 0.075% taker per side. Live signals here
    # are market entries, so both sides pay taker.
    #     0.075 x 2 = 0.15%, + 18% GST on the fee = 0.177% -> 0.18
    # Spread is on top of this and is not modelled, so treat 0.18 as a floor.
    # If you move to limit entries (maker 0.025% per side) this drops to about
    # 0.06 — but only once the code actually places limit orders.
    'ROUND_TRIP_COST_PCT': 0.18,

    # A trade must target at least this multiple of its own cost, or the
    # arithmetic cannot work. At 2.2R gross TP / 0.8R SL and cost c, the
    # breakeven win rate is (0.8R + c) / (3.0R). When c approaches R that
    # number climbs past 60% and stays there.
    'MIN_TP_COST_RATIO': 3.0,

    'ATR_COMPRESSION_RATIO': 0.7,
    'ATR_MA_PERIOD': 50,
    'CHOPPINESS_PERIOD': 14,
    'CHOPPINESS_TREND_MAX': 61.8,
    'LIMIT': 150,
    # ── FIX v6 (F23): TP_ATR_MULT raised from 2.2 to 3.0 ────────────────
    # The fee is a fixed percentage of price; the target is not. So the only
    # way to shrink the fee's share of a winning trade is to make the target
    # bigger. Measured on BTC 15m: 1R is about 0.44% of price, so at 0.18%
    # round-trip the fee ate roughly 20% of every R. At 3.0 the target is
    # 36% further out and the fee's share drops to about 15%.
    #
    # This does NOT loosen any filter. ADX_MIN, MIN_CONFLUENCE_SCORE and
    # SCORE_THRESHOLD are untouched on purpose — a signal that only appears
    # because a gate was lowered is a signal the gate existed to reject.
    #
    # The trade-off is honest: a further target is hit less often. Gross R:R
    # goes from 2.75 to 3.75, which moves the breakeven win rate from about
    # 26% to about 21%. Expect win rate to fall and expectancy to be the
    # number that decides whether this was worth it — watch expectancy_pct
    # and profit_factor, not win_rate, when comparing before and after.
    'TP_ATR_MULT': 3.0,
    'SL_ATR_MULT': 0.8,
    'RSI_OVERBOUGHT': 85,
    'RSI_OVERSOLD': 15,
    'BACKTEST_CANDLES': 3000,

    # ── FIX v6 (F26): the window was far too short for the target ───────
    # This was 10 bars. With TP at 3.0 ATR and SL at 0.8 ATR, a trade needs
    # 3 ATR of favourable movement to win but only 0.8 ATR of adverse
    # movement to lose. In 10 bars the adverse move is routine and the
    # favourable one is rare, so nearly everything resolved as LOSS or
    # TIMEOUT — and a TIMEOUT exits at market and still pays the full
    # round-trip fee, so it books as a loss too.
    #
    # The signature was unmistakable: run_factor_backtest returned profit
    # factors of 0.07 to 0.23 across ALL EIGHT factors, including the plain
    # EMA-crossover baseline. Win rates of 15% against a 21% breakeven means
    # the test was performing WORSE than random, which no combination of
    # eight unrelated signals does by accident. That is a broken measurement,
    # not eight broken factors.
    #
    # 60 bars is 5 hours on 5m and 15 hours on 15m — enough room for a 3 ATR
    # move to actually resolve. smc.py has used TIMEOUT_BARS 40 for exactly
    # this reason; this file never got the same treatment.
    #
    # If you change TP_ATR_MULT, revisit this. The two are coupled: a further
    # target needs more time, and leaving the window behind silently turns
    # every backtest into a fee-collection simulator.
    'BACKTEST_OUTCOME_WINDOW': 60,

    # ── Divergence quality gates ────────────────────────────────────
    'DIV_MIN_RSI_GAP': 5.0,
    'DIV_MIN_PEAK_SEPARATION': 5,
    'DIV_TRENDING_WEIGHT': 0.35,
    'DIV_RANGING_WEIGHT': 1.0,

    'FVG_MIN_GAP_PCT': 0.02,
    'BSL_SSL_LOOKBACK': 20,
    'EQUAL_LEVEL_TOLERANCE_PCT': 0.05,
    'INDUCEMENT_MINOR_LOOKBACK': 2,
    'FVG_PROXIMITY_PCT': 0.3,
    'EQUAL_LEVEL_MIN_COUNT': 3,

    'TARGET_PROFIT_INR_MIN': 500,
    'TARGET_PROFIT_INR_MAX': 1000,
    'USDT_INR_RATE': 102.0,

    'MIN_PROFIT_LOCK_ATR_MULT': 0.3,
    'TRAIL_ATR_MULT': 0.6,

    'CVD_PRESSURE_LOOKBACK': 10,
    'CVD_PRESSURE_MIN_ABS': 0,   # legacy raw-sum threshold, no longer gated on
    # FIX v4 (F17): the raw delta sum scales with the asset's volume, so
    # comparing it against 0 meant ANY negative reading vetoed a BUY. On BTC
    # that value swings by tens of units candle to candle, so roughly half of
    # otherwise-valid setups were being killed at random. Gate on the
    # volume-normalised fraction instead: -1.0 = every candle in the window
    # closed on its low, +1.0 = every candle closed on its high. 0.12 means
    # "at least 12% of the window's volume leaned against the trade".
    'CVD_PRESSURE_MIN_FRAC': 0.12,

    'MOMENTUM_LOOKBACK': 10,
    'ENABLE_PRIME_HOURS_FILTER': False,
    'RISK_PCT_PER_TRADE': 1.0,
    'MAX_DAILY_LOSS_PCT': 3.0,
    'MAX_LEVERAGE': 5,
    'MAX_CONCURRENT_POSITIONS': 2,

    'SLIPPAGE_BPS': 2,
    'REALISTIC_BACKTEST': True,

    'ADAPTIVE_SIZE_HIGH_VOL_RATIO': 1.5,
    'ADAPTIVE_SIZE_LOW_VOL_RATIO': 0.7,
    'ADAPTIVE_SIZE_HIGH_VOL_MULT': 0.6,
    'ADAPTIVE_SIZE_LOW_VOL_MULT': 1.2,

    'MIN_CONFLUENCE_SCORE': 3.0,

    # ── FIX v6 (F24): confluence weights are data, not code ─────────────
    # These used to be hardcoded inside calc_confluence_score(), which meant
    # changing one required editing a function and hoping nothing else read
    # it. They are here so that after run_factor_backtest() tells you which
    # factors actually clear profit factor 1.2, you set the failures to 0.0
    # in ONE place and the whole engine follows.
    #
    # fvg_proximity and inducement are 0.0 ON PURPOSE. They contribute to
    # buy_score/sell_score already but were never part of confluence. Giving
    # them weight now would LOOSEN the gate before anything has been
    # measured, which is backwards. Turn them on only if the factor report
    # shows they carry edge.
    #
    # A weight of 0.0 disables a component without removing it, so the
    # breakdown still reports whether it fired. That is what lets you tell
    # "this factor never triggers" apart from "this factor triggers and
    # loses money" — two very different problems with the same symptom.
    'CONFLUENCE_WEIGHTS': {
        'candle_pattern': 2.0,
        'structure_break': 3.0,
        'divergence': 2.5,
        'sweep_with_equal_levels': 3.0,
        'fvg_proximity': 0.0,       # measured? no. weight stays 0.
        'inducement': 0.0,          # measured? no. weight stays 0.
        'htf_ema_alignment': 1.5,
    },

    # ── FIX v6 (F25): the acceleration boost double-counted trend ───────
    # get_ltf_scores() awarded 0.5 for price>vwap, 0.5 for ema5>ema20, and
    # then a further 1.0 for BOTH being true — scoring the same two
    # conditions twice. Across the entry and confirm snapshots that is 2.2
    # points a plain trending bar collects with no setup present at all.
    #
    # This is why a card could read "Score: BUY 10.6 / SELL 2.1" and be
    # blocked at "Low confluence 1.5" in the same breath. The 10.6 was
    # measuring trend; the 1.5 was measuring setup. Both were right.
    #
    # Off by default. Set True to restore the old scores exactly.
    'ENABLE_ACCELERATION_BOOST': False,

    'PRIME_HOURS_ASIAN_DEAD_START': 0,
    'PRIME_HOURS_ASIAN_DEAD_END': 8,
    'PRIME_HOURS_OVERLAP_START': 8,
    'PRIME_HOURS_OVERLAP_END': 17,
    'PRIME_HOURS_NY_CLOSE_START': 17,
    'PRIME_HOURS_NY_CLOSE_END': 20,

    'GRID_MIN_WIN_RATE': 50.0,

    'VOLUME_SPIKE_LOOKBACK': 20,
    'VOLUME_SPIKE_MULT': 1.2,

    'MAX_CONSECUTIVE_LOSSES': 3,   # FIX v3 (F15): now actually enforced

    # ── Order-flow proxy settings ───────────────────────────────────────
    'OF_DELTA_LOOKBACK': 20,
    'OF_ABSORPTION_VOL_MULT': 1.8,
    'OF_ABSORPTION_BODY_MAX_PCT': 35,
    'OF_VP_LOOKBACK': 100,
    'OF_VP_BINS': 30,
    'OF_LVN_PCTL': 25,
    'OF_HVN_PCTL': 75,
    'OF_RETEST_TOL_PCT': 0.15,
    'OF_BREAKOUT_LOOKBACK': 20,
    'OF_SECOND_DRIVE_MAX_BARS': 12,
    'OF_SQUEEZE_ATR_MULT': 1.5,
    'OF_SQUEEZE_VOL_MULT': 1.5,
    'OF_BREAKEVEN_TRIGGER_ATR_MULT': 0.5,
    'OF_SL_BUFFER_TICKS_PCT': 0.03,
    'OF_RISK_BASE_PCT': 0.25,
    'OF_RISK_HOUSE_MONEY_PCT': 0.50,
    'OF_SESSION_NY_START_UTC': 13,
    'OF_SESSION_NY_END_UTC': 20,
    'OF_SESSION_LDN_START_UTC': 7,
    'OF_SESSION_LDN_END_UTC': 16,
}

ASSET_OVERRIDES = {
    "BTC/USDT:USDT": {
        'ADX_MIN': 14,
        'SCORE_GAP_MIN': 2.5,
        'MIN_CONFLUENCE_SCORE': 2.0,
    },
    "ETH/USDT:USDT": {
        'ADX_MIN': 14,
        'SCORE_GAP_MIN': 2.5,
        'MIN_CONFLUENCE_SCORE': 2.0,
    },
    "BANK/USDT:USDT": {
        'ADX_MIN': 22,
        'SCORE_GAP_MIN': 4.5,
        'MIN_CONFLUENCE_SCORE': 4.0,
    },
}


def get_effective_config(symbol):
    eff = dict(CONFIG)
    eff.update(ASSET_OVERRIDES.get(symbol, {}))
    return eff


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

    tf_seconds = TF_SECONDS.get(timeframe)   # FIX v3 (F14): shared table, no KeyError
    if tf_seconds is None:
        return None, None
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
    """FIX v5 (F19): unsupported timeframes are refused here rather than
    falling through to a ccxt exchange. Without this the 1m removal would be
    cosmetic — CoinDCX would return None and mexc/bybit would happily serve
    1m candles instead, which is exactly the silent cross-venue behaviour
    F14 existed to stop."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return None, None

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
            df = df.astype(float).sort_index()
            return df.tail(limit), ex_id
        except Exception:
            continue
    return None, None


# ── Base Indicators ─────────────────────────────────────────────────────
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(close, period=14):
    """FIX v3 (F1): Wilder smoothing (ewm alpha=1/period), not a simple
    rolling mean. The old version was Cutler's RSI — a different indicator
    with a different distribution, so RSI_OVERBOUGHT/OVERSOLD were calibrated
    against numbers TradingView never produces."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - (100 / (1 + (gain / (loss + 1e-10))))


def calc_atr(df, period=14):
    """FIX v3 (F1): Wilder ATR. calc_adx() below already smoothed TR with
    ewm(alpha=1/period); this used rolling().mean(). Two ATRs, one file."""
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


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


def detect_market_regime(df, eff_cfg=None):
    """FIX v3 (F12): accepts eff_cfg so the per-asset ADX_MIN override is
    honoured. Previously this read the global CONFIG['ADX_MIN'] (18) while
    decide_direction() read the override (14 for BTC/ETH). The regime gate
    therefore blocked exactly the trades the override existed to allow —
    the BTC and ETH overrides were doing nothing at all."""
    eff_cfg = eff_cfg if eff_cfg is not None else CONFIG
    atr = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx = calc_adx(df, CONFIG['ADX_PERIOD'])
    current_atr = atr.iloc[-1]; current_atr_ma = atr_ma.iloc[-1]
    current_ci = ci.iloc[-1]; current_adx = adx.iloc[-1]
    atr_ratio = (current_atr / current_atr_ma) if current_atr_ma > 0 else 1.0
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy = current_ci > CONFIG['CHOPPINESS_TREND_MAX'] if not np.isnan(current_ci) else False
    is_trending = current_adx >= eff_cfg['ADX_MIN'] if not np.isnan(current_adx) else False
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


def _bars_since_extreme(series, lookback, use_max=True):
    f = np.argmax if use_max else np.argmin
    return series.rolling(lookback).apply(
        lambda w: len(w) - 1 - f(w), raw=True)


def detect_pro_divergence_vectorized(df, lookback=20):
    df = df.copy()
    df["divergence"] = ""
    prior_c = df["close"].shift(1)
    prior_r = df["rsi"].shift(1)

    roll_min_c = prior_c.rolling(lookback).min()
    roll_min_r = prior_r.rolling(lookback).min()
    roll_max_c = prior_c.rolling(lookback).max()
    roll_max_r = prior_r.rolling(lookback).max()

    gap = CONFIG['DIV_MIN_RSI_GAP']
    sep = CONFIG['DIV_MIN_PEAK_SEPARATION']
    bars_to_peak = _bars_since_extreme(prior_r, lookback, use_max=True)
    bars_to_trough = _bars_since_extreme(prior_r, lookback, use_max=False)

    bull = (
        (df["close"] <= roll_min_c) &
        (df["rsi"] - roll_min_r >= gap) &
        (bars_to_trough >= sep) &
        (df["rsi"] < 50)
    )
    bear = (
        (df["close"] >= roll_max_c) &
        (roll_max_r - df["rsi"] >= gap) &
        (bars_to_peak >= sep) &
        (df["rsi"] > 50)
    )
    df.loc[bull, "divergence"] = "BULL_DIV"
    df.loc[bear, "divergence"] = "BEAR_DIV"
    return df


def divergence_weight(regime_label):
    if regime_label == "TRENDING":
        return CONFIG['DIV_TRENDING_WEIGHT']
    return CONFIG['DIV_RANGING_WEIGHT']


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


def _drop_forming_candle(df):
    """FIX v3 (F2): the exchange returns the candle currently being built,
    because fetch_coindcx_futures() asks for data up to `now`. Reading
    df.iloc[-1] therefore means every indicator, every candle pattern and
    every BOS/CHoCH confirmation is recomputed from a bar that is still
    changing — the classic repaint. Signals flipped between polls for no
    reason other than an unfinished wick."""
    if df is None or len(df) < 2:
        return df
    return df.iloc[:-1]


def analyze_timeframe(df, closed_only=False, eff_cfg=None):
    """FIX v3 (F2): closed_only defaults False so backtest/vectorized paths
    are untouched. Every LIVE caller passes True."""
    if closed_only:
        df = _drop_forming_candle(df)
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
    regime = detect_market_regime(df, eff_cfg=eff_cfg)   # FIX v3 (F12)
    cvd_pressure_series = calc_recent_cvd_pressure(df)
    # FIX v4 (F17): computed once. Calling calc_cvd_pressure_norm() twice —
    # once for the isna() check and once for the value — doubles a full-frame
    # rolling computation on every snapshot, and a scan pass builds eight.
    cvd_norm_series = calc_cvd_pressure_norm(df)
    _cvd_norm = cvd_norm_series.iloc[-1]
    last = df.iloc[-1]
    return {
        "cvd_pressure_norm": float(_cvd_norm) if not pd.isna(_cvd_norm) else 0.0,
        "structure_event": last["structure_event"], "structure_trend": last["structure_trend"],
        "adx": last["adx"], "price": last["close"], "vwap": last["vwap"],
        "volume": last["volume"],
        "ema5": last["ema5"], "ema20": last["ema20"], "rsi": last["rsi"], "atr": last["atr"],
        "pattern": last["pat_sig"], "divergence": last["divergence"],
        "sweep": sweep, "vp": vp, "regime": regime,
        "cvd_pressure": float(cvd_pressure_series.iloc[-1]) if not pd.isna(cvd_pressure_series.iloc[-1]) else 0.0,
        "fvg": last["fvg"],
        "dist_to_bull_fvg_pct": last["dist_to_bull_fvg_pct"],
        "dist_to_bear_fvg_pct": last["dist_to_bear_fvg_pct"],
        "bsl_level": last["bsl_level"], "ssl_level": last["ssl_level"],
        "dist_to_bsl_pct": last["dist_to_bsl_pct"], "dist_to_ssl_pct": last["dist_to_ssl_pct"],
        "eq_high_count": last["eq_high_count"], "eq_low_count": last["eq_low_count"],
        "inducement": last["inducement"],
    }


def get_htf_bias(snap_htf):
    """Directional bias from the highest timeframe in the ladder.

    FIX v3 (F9): NaN no longer votes bearish. The old line was
        score += weight*0.5 if snap["ema5"] > snap["ema20"] else -weight*0.5
    and a NaN comparison is False, so it fell into the -0.5 branch. Combined
    with a NaN RSI that is -1.25 — enough on its own to return BEARISH from
    missing data alone."""
    weight = 1.0; score = 0.0
    if snap_htf["structure_trend"] == "BULL": score += weight
    elif snap_htf["structure_trend"] == "BEAR": score -= weight

    e5, e20 = snap_htf.get("ema5"), snap_htf.get("ema20")
    if pd.notna(e5) and pd.notna(e20):
        score += weight * 0.5 if e5 > e20 else -weight * 0.5

    if not pd.isna(snap_htf["rsi"]):
        if snap_htf["rsi"] > 55: score += weight * 0.3
        elif snap_htf["rsi"] < 45: score -= weight * 0.3
    if snap_htf.get("sweep") == "EQUAL_LOW_SWEEP": score += 0.5
    elif snap_htf.get("sweep") == "EQUAL_HIGH_SWEEP": score -= 0.5
    if snap_htf.get("inducement") == "BULL_INDUCEMENT": score += 0.3
    elif snap_htf.get("inducement") == "BEAR_INDUCEMENT": score -= 0.3
    if score >= 0.9: return "BULLISH"
    if score <= -0.9: return "BEARISH"
    return "NEUTRAL"


def get_ltf_scores(snap_entry, snap_confirm):
    """FIX v5 (F22): arguments named by ROLE, not by timeframe. These used to
    be snap_1m/snap_5m, which stopped being accurate the moment the entry
    timeframe changed. The confirmation frame still carries the heavier
    weight (1.2), unchanged from before."""
    buy_score, sell_score = 0.0, 0.0
    for snap, w in [(snap_entry, 1.0), (snap_confirm, 1.2)]:
        if snap is None:
            continue
        if snap["pattern"] == "BUY": buy_score += 2 * w
        elif snap["pattern"] == "SELL": sell_score += 2 * w

        try:
            dw = divergence_weight(snap["regime"]["regime"])
        except (KeyError, TypeError):
            dw = 1.0
        if snap["divergence"] == "BULL_DIV": buy_score += 3 * w * dw
        elif snap["divergence"] == "BEAR_DIV": sell_score += 3 * w * dw

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

        # FIX v3 (F9): NaN EMA used to fall through to the sell branch.
        e5, e20 = snap.get("ema5"), snap.get("ema20")
        if pd.notna(e5) and pd.notna(e20):
            if e5 > e20: buy_score += 0.5 * w
            else: sell_score += 0.5 * w

        liq_buy, liq_sell = calc_liquidity_score(snap)
        buy_score += liq_buy * w
        sell_score += liq_sell * w

        # FIX v6 (F25): this re-scores the same two conditions (price vs
        # vwap, ema5 vs ema20) that were already scored above, so a plain
        # trending bar collects 2.2 across both snapshots from trend alone
        # with no actual setup present. Now off by default — see
        # ENABLE_ACCELERATION_BOOST in CONFIG for the full reasoning.
        if CONFIG['ENABLE_ACCELERATION_BOOST']:
            if "volume" in snap and not pd.isna(snap["vwap"]):
                if pd.notna(e5) and pd.notna(e20):
                    if snap["price"] > snap["vwap"] and e5 > e20:
                        buy_score += 1.0 * w
                    elif snap["price"] <= snap["vwap"] and e5 <= e20:
                        sell_score += 1.0 * w

    return round(buy_score, 2), round(sell_score, 2)


def calc_confluence_score(snap_entry, snap_confirm, weights=None, breakdown=False):
    """How many INDEPENDENT structural reasons exist to take this trade.

    FIX v6 (F24): weights come from CONFIG['CONFLUENCE_WEIGHTS'] instead of
    being hardcoded, and the function can return a per-component breakdown.

    The breakdown matters more than the total. A score of 1.5 tells you the
    trade was rejected; the breakdown tells you it was rejected because the
    ONLY thing agreeing was EMA alignment, which is trend, not setup. That
    distinction is what stops you from lowering MIN_CONFLUENCE_SCORE to
    "fix" a card that was correctly rejected.

    Every field is read with .get() so a partial snapshot (run_backtest
    passes a small dict for snap_confirm) cannot raise. A missing field
    counts as "did not fire", which is the honest default.
    """
    w = weights if weights is not None else CONFIG['CONFLUENCE_WEIGHTS']
    fired = {}

    fired['candle_pattern'] = snap_entry.get("pattern") in ("BUY", "SELL")

    fired['structure_break'] = snap_entry.get("structure_event") in (
        "CHoCH_BULL", "BOS_BULL", "CHoCH_BEAR", "BOS_BEAR")

    fired['divergence'] = snap_entry.get("divergence") in ("BULL_DIV", "BEAR_DIV")

    sweep = snap_entry.get("sweep")
    eql = snap_entry.get("eq_low_count") or 0
    eqh = snap_entry.get("eq_high_count") or 0
    fired['sweep_with_equal_levels'] = (
        (sweep == "EQUAL_LOW_SWEEP" and eql >= CONFIG['EQUAL_LEVEL_MIN_COUNT']) or
        (sweep == "EQUAL_HIGH_SWEEP" and eqh >= CONFIG['EQUAL_LEVEL_MIN_COUNT'])
    )

    # FIX v6 (F24): these two feed buy_score/sell_score but were never part
    # of confluence. They are counted here so the breakdown is honest about
    # what the bar contains, but their default weight is 0.0 so nothing
    # changes until the factor report justifies turning them on.
    dbull = snap_entry.get("dist_to_bull_fvg_pct")
    dbear = snap_entry.get("dist_to_bear_fvg_pct")
    near_fvg = False
    for d in (dbull, dbear):
        if d is not None and not pd.isna(d) and 0 <= d <= CONFIG['FVG_PROXIMITY_PCT']:
            near_fvg = True
    fired['fvg_proximity'] = near_fvg

    fired['inducement'] = snap_entry.get("inducement") in (
        "BULL_INDUCEMENT", "BEAR_INDUCEMENT")

    e5, e20 = snap_entry.get("ema5"), snap_entry.get("ema20")
    c5, c20 = snap_confirm.get("ema5"), snap_confirm.get("ema20")
    if all(pd.notna(x) for x in (e5, e20, c5, c20)):
        fired['htf_ema_alignment'] = (e5 > e20) == (c5 > c20)
    else:
        # FIX v3 (F9) applies here too: missing data is not agreement.
        fired['htf_ema_alignment'] = False

    score = round(sum(w.get(k, 0.0) for k, hit in fired.items() if hit), 2)

    if breakdown:
        detail = {k: {"fired": bool(hit), "weight": w.get(k, 0.0),
                      "contributed": w.get(k, 0.0) if hit else 0.0}
                  for k, hit in fired.items()}
        return score, detail
    return score


# FIX v6 (F24): decide_direction() returns (direction, reason) and changing
# that signature would break every caller. This one-slot list carries the
# confluence breakdown out to analyze() without touching the contract.
# Single-threaded per request in practice; it is read immediately after the
# call that writes it, never held across one.
_last_confluence_detail = [None]


def decide_direction(buy_score, sell_score, htf_bias, entry_adx, regime_entry, regime_confirm,
                     entry_rsi=None, snap_entry=None, snap_confirm=None, cvd_pressure=None,
                     eff_cfg=None):
    """FIX v5 (F22): regime_1m/regime_5m and snap_1m/snap_5m renamed to
    entry/confirm. The gates are unchanged."""
    eff_cfg = eff_cfg if eff_cfg is not None else CONFIG
    if pd.isna(entry_adx) or entry_adx < eff_cfg['ADX_MIN']:
        return None, f"NO TREND (ADX {entry_adx:.1f} < {eff_cfg['ADX_MIN']})"
    if entry_rsi is not None and not pd.isna(entry_rsi):
        if entry_rsi > CONFIG['RSI_OVERBOUGHT'] and buy_score >= sell_score:
            return None, f"BLOCKED (RSI overbought {entry_rsi:.1f})"
        if entry_rsi < CONFIG['RSI_OVERSOLD'] and sell_score >= buy_score:
            return None, f"BLOCKED (RSI oversold {entry_rsi:.1f})"
    is_entry_comp = regime_entry["regime"] == "COMPRESSION"
    is_confirm_comp = regime_confirm["regime"] == "COMPRESSION"

    # Compression-breakout bypass.
    # FIX v3 (F8): htf_bias must now actively agree. A NEUTRAL higher
    # timeframe used to authorise both a long and a short here, which is how
    # a clean uptrend still produced SELL signals.
    if is_confirm_comp and not is_entry_comp and entry_adx > eff_cfg['ADX_MIN']:
        if (buy_score >= CONFIG['SCORE_THRESHOLD'] + 0.5 and buy_score > sell_score
                and htf_bias == "BULLISH"):
            if cvd_pressure is None or cvd_pressure >= -CONFIG['CVD_PRESSURE_MIN_FRAC']:
                return "BUY", "COMPRESSION BREAKOUT LONG"
        if (sell_score >= CONFIG['SCORE_THRESHOLD'] + 0.5 and sell_score > buy_score
                and htf_bias == "BEARISH"):
            if cvd_pressure is None or cvd_pressure <= CONFIG['CVD_PRESSURE_MIN_FRAC']:
                return "SELL", "COMPRESSION BREAKOUT SHORT"

    if is_entry_comp and is_confirm_comp:
        return None, "BLOCKED (Tight Squeeze Range)"

    if regime_entry["regime"] == "RANGING" or regime_confirm["regime"] == "RANGING":
        return None, "BLOCKED (Choppy Flat Zones)"

    if regime_entry["regime"] != "TRENDING" or regime_confirm["regime"] != "TRENDING":
        return None, "BLOCKED (Not Dynamic Trending Structure)"

    confluence_score = None
    confluence_detail = None
    if snap_entry is not None and snap_confirm is not None:
        confluence_score, confluence_detail = calc_confluence_score(
            snap_entry, snap_confirm, breakdown=True)
        if confluence_score < eff_cfg['MIN_CONFLUENCE_SCORE']:
            # FIX v6 (F24): name what DID fire. "Low confluence 1.5 < 2.0" on
            # its own invites lowering the threshold; "only htf_ema_alignment"
            # makes it obvious the bar had trend and no setup, which is
            # exactly what this gate exists to reject.
            hits = [k for k, v in confluence_detail.items() if v["fired"]]
            _last_confluence_detail[0] = confluence_detail
            return None, (f"BLOCKED (Low confluence {confluence_score:.1f} < "
                          f"{eff_cfg['MIN_CONFLUENCE_SCORE']} — fired: "
                          f"{', '.join(hits) if hits else 'nothing'})")
    _last_confluence_detail[0] = confluence_detail

    # FIX v3 (F8): NEUTRAL now blocks BOTH sides instead of permitting both.
    # A higher timeframe with no opinion is a reason to stand down, not a
    # licence to trade either way.
    if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
        if (buy_score - sell_score) >= eff_cfg['SCORE_GAP_MIN'] and htf_bias == "BULLISH":
            if cvd_pressure is not None and cvd_pressure < -CONFIG['CVD_PRESSURE_MIN_FRAC']:
                return None, f"BLOCKED (CVD pressure against BUY: {cvd_pressure:.2f})"
            return "BUY", "BUY" + (f" (confluence {confluence_score:.1f})" if confluence_score is not None else "")
    if sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
        if (sell_score - buy_score) >= eff_cfg['SCORE_GAP_MIN'] and htf_bias == "BEARISH":
            if cvd_pressure is not None and cvd_pressure > CONFIG['CVD_PRESSURE_MIN_FRAC']:
                return None, f"BLOCKED (CVD pressure against SELL: {cvd_pressure:.2f})"
            return "SELL", "SELL" + (f" (confluence {confluence_score:.1f})" if confluence_score is not None else "")
    return None, f"WAIT (bias {htf_bias} | buy {buy_score} / sell {sell_score})"


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


def _px(v):
    """Significant figures, not decimal places. round(x, 2) is fine for BTC
    at 63,000 but turns a 0.0568 BANK entry, its 0.0592 target and its 0.0553
    stop into three identical numbers."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return float(f"{v:.8g}")


def calc_tp_sl(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    sl_dist = CONFIG['SL_ATR_MULT'] * atr
    tp_dist = CONFIG['TP_ATR_MULT'] * atr
    if direction == "BUY":
        return _px(price + tp_dist), _px(price - sl_dist)
    return _px(price - tp_dist), _px(price + sl_dist)


def calc_tp_sl_with_slippage(direction, price, atr, slippage_bps=None):
    """FIX v3 (F13): now uses _px() like calc_tp_sl(). This function was still
    on round(x, 4) — and since REALISTIC_BACKTEST is True, this is the one
    LIVE analyze() actually calls. On BANK (~0.054) that rounding was
    flattening entry, TP and SL into the same 4-decimal number, making the
    stop distance meaningless and position sizing impossible."""
    if direction is None or atr is None or pd.isna(atr):
        return None, None
    slippage_bps = slippage_bps if slippage_bps is not None else CONFIG['SLIPPAGE_BPS']
    sl_dist = CONFIG['SL_ATR_MULT'] * atr
    tp_dist = CONFIG['TP_ATR_MULT'] * atr
    slippage_amt = price * (slippage_bps / 10000)

    if direction == "BUY":
        tp = _px(price + tp_dist - slippage_amt)   # exit earlier, less profit
        sl = _px(price - sl_dist - slippage_amt)   # stop further away, bigger loss
    else:
        tp = _px(price - tp_dist + slippage_amt)
        sl = _px(price + sl_dist + slippage_amt)
    return tp, sl


def round_trip_cost_pct():
    """FIX v3 (F4): single source of truth for transaction cost."""
    return CONFIG['ROUND_TRIP_COST_PCT']


def cost_gate(price, tp):
    """FIX v3 (F3): reject setups whose gross target is not meaningfully
    larger than the cost of taking the trade.

    With gross TP of R_tp, gross SL of R_sl and round-trip cost c, expectancy
    is p*(R_tp - c) - (1-p)*(R_sl + c). As c approaches R_sl the required
    win rate climbs past anything this strategy has demonstrated. Blocking
    these setups is not conservatism, it is arithmetic."""
    if tp is None or price is None:
        return False
    try:
        price = float(price); tp = float(tp)
    except (TypeError, ValueError):
        return False
    if price == 0:
        return False
    edge_pct = abs(tp - price) / price * 100.0
    return edge_pct >= CONFIG['MIN_TP_COST_RATIO'] * round_trip_cost_pct()


def detect_volume_spike(df, lookback=None, multiplier=None):
    lookback = lookback or CONFIG['VOLUME_SPIKE_LOOKBACK']
    multiplier = multiplier or CONFIG['VOLUME_SPIKE_MULT']
    avg_vol = df["volume"].rolling(lookback).mean()
    vol_ratio = df["volume"] / (avg_vol + 1e-10)
    return vol_ratio >= multiplier


def calc_tp_sl_scaled(direction, price, atr):
    if direction is None or atr is None or pd.isna(atr):
        return None
    sl_dist = CONFIG['SL_ATR_MULT'] * atr
    tp_base = CONFIG['TP_ATR_MULT'] * atr

    if direction == "BUY":
        sl = _px(price - sl_dist)
        tp1 = _px(price + tp_base * 0.5)
        tp2 = _px(price + tp_base * 0.75)
        tp3 = _px(price + tp_base)
    else:
        sl = _px(price + sl_dist)
        tp1 = _px(price - tp_base * 0.5)
        tp2 = _px(price - tp_base * 0.75)
        tp3 = _px(price - tp_base)

    return {"sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "tp1_pct": 50, "tp2_pct": 30, "tp3_pct": 20}


import time as _time

_HTF_CACHE = {}
_HTF_CACHE_TTL = 15

# The timeframe the directional bias is read from. Kept as a named constant
# because two separate functions need to agree on it.
HTF_BIAS_TIMEFRAME = "15m"


def _get_htf_bias_cached(symbol):
    now = _time.time()
    cached = _HTF_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < _HTF_CACHE_TTL:
        return cached["bias"]
    htf_bias = "NEUTRAL"
    eff_cfg = get_effective_config(symbol)
    df_htf, _ = fetch_ohlcv_failover(symbol, HTF_BIAS_TIMEFRAME, CONFIG['LIMIT'])
    if df_htf is not None:
        # FIX v3 (F2): closed candles only for the bias snapshot too.
        snap_htf = analyze_timeframe(df_htf, closed_only=True, eff_cfg=eff_cfg)
        htf_bias = get_htf_bias(snap_htf)
    _HTF_CACHE[symbol] = {"bias": htf_bias, "ts": now}
    return htf_bias


_LTF_CACHE = {}
_SIGNAL_AGE_CACHE = {}
_LTF_CACHE_TTL = 10

# FIX v5 (F19): the "1m": "5m" entry is gone. 5m is now the fastest entry
# timeframe and confirms against 15m.
TIMEFRAME_CONFIRM_MAP = {
    "5m": "15m",
    "15m": "1h",
    "1h": "4h",
}


def _get_ltf_snaps_cached(symbol, timeframe="5m", preloaded_entry_snap=None):
    now = _time.time()
    confirm_tf = TIMEFRAME_CONFIRM_MAP.get(timeframe, "15m")
    cache_key = (symbol, timeframe)
    cached = _LTF_CACHE.get(cache_key)
    if cached and (now - cached["ts"]) < _LTF_CACHE_TTL:
        return cached["snap_entry"], cached["snap_confirm"]

    eff_cfg = get_effective_config(symbol)

    if preloaded_entry_snap is not None:
        snap_entry_tf = preloaded_entry_snap
    else:
        df_entry_tf, _ = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
        # FIX v3 (F2)
        snap_entry_tf = (analyze_timeframe(df_entry_tf, closed_only=True, eff_cfg=eff_cfg)
                         if df_entry_tf is not None else None)

    df_confirm, _ = fetch_ohlcv_failover(symbol, confirm_tf, CONFIG['LIMIT'])
    snap_confirm = (analyze_timeframe(df_confirm, closed_only=True, eff_cfg=eff_cfg)
                    if df_confirm is not None else None)

    _LTF_CACHE[cache_key] = {"snap_entry": snap_entry_tf, "snap_confirm": snap_confirm, "ts": now}
    return snap_entry_tf, snap_confirm


def calc_position_size_for_target(entry_price, tp_price, target_profit_inr=None, usdt_inr_rate=None):
    if entry_price is None or tp_price is None:
        return None
    target_profit_inr = target_profit_inr if target_profit_inr is not None else CONFIG['TARGET_PROFIT_INR_MIN']
    usdt_inr_rate = usdt_inr_rate if usdt_inr_rate is not None else CONFIG['USDT_INR_RATE']
    price_move = abs(tp_price - entry_price)
    if price_move <= 0:
        return None
    qty = target_profit_inr / (price_move * usdt_inr_rate)
    return round(qty, 4)


def calc_dynamic_trailing_exit(direction, entry_price, current_price, atr, sl, tp, extreme_price=None):
    if atr is None or atr <= 0 or entry_price is None or current_price is None:
        return {"sl": sl, "min_profit_locked": False, "tp_hit": False, "note": "invalid inputs"}
    if direction not in ("BUY", "SELL"):
        return {"sl": sl, "min_profit_locked": False, "tp_hit": False, "note": "invalid direction"}

    extreme = extreme_price if extreme_price is not None else current_price
    min_lock_dist = atr * CONFIG['MIN_PROFIT_LOCK_ATR_MULT']
    trail_dist = atr * CONFIG['TRAIL_ATR_MULT']
    new_sl = sl
    min_profit_locked = False
    tp_hit = False
    note = "no change yet — price hasn't moved far enough in favor"

    if direction == "BUY":
        favorable_move = extreme - entry_price
        if favorable_move >= min_lock_dist:
            locked_sl = entry_price + min_lock_dist
            new_sl = max(new_sl, locked_sl) if new_sl is not None else locked_sl
            min_profit_locked = True
            note = "minimum profit locked"
        trailing_sl = extreme - trail_dist
        if new_sl is None or trailing_sl > new_sl:
            new_sl = trailing_sl
            note = "trailing stop tightened toward max"
        if tp is not None and current_price >= tp:
            tp_hit = True
            note = "target reached — consider closing"
    else:
        favorable_move = entry_price - extreme
        if favorable_move >= min_lock_dist:
            locked_sl = entry_price - min_lock_dist
            new_sl = min(new_sl, locked_sl) if new_sl is not None else locked_sl
            min_profit_locked = True
            note = "minimum profit locked"
        trailing_sl = extreme + trail_dist
        if new_sl is None or trailing_sl < new_sl:
            new_sl = trailing_sl
            note = "trailing stop tightened toward max"
        if tp is not None and current_price <= tp:
            tp_hit = True
            note = "target reached — consider closing"

    return {
        "sl": _px(new_sl) if new_sl is not None else None,
        "min_profit_locked": min_profit_locked,
        "tp_hit": tp_hit,
        "note": note,
    }


def analyze(symbol, timeframe="5m"):
    """FIX v5 (F19): default entry timeframe is 5m. A caller asking for an
    unsupported timeframe gets a clear error instead of a signal built from
    another exchange's candles."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return {"symbol": symbol, "timeframe": timeframe,
                "error": f"unsupported timeframe — this engine trades {SUPPORTED_TIMEFRAMES}"}

    eff_cfg = get_effective_config(symbol)
    df_entry, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['LIMIT'])
    if df_entry is None or len(df_entry) < 3:
        return {"symbol": symbol, "timeframe": timeframe, "error": "no data"}

    # FIX v3 (F2): the snapshot the decision is built from must come from a
    # candle that has finished. df_closed is also what momentum and the
    # volume-spike filter read, so nothing in the decision path can be
    # influenced by a bar that is still moving.
    df_closed = _drop_forming_candle(df_entry)

    snap_entry = analyze_timeframe(df_entry, closed_only=True, eff_cfg=eff_cfg)
    price = float(snap_entry["price"])
    rsi_now = float(snap_entry["rsi"]) if not pd.isna(snap_entry["rsi"]) else None
    atr_now = float(snap_entry["atr"]) if not pd.isna(snap_entry["atr"]) else None

    # Raw momentum — display only, no filters, so you can see the market is
    # moving even when nothing clears the entry gates.
    mom_lookback = min(CONFIG['MOMENTUM_LOOKBACK'], len(df_closed) - 1)
    momentum_pct = None
    if mom_lookback > 0:
        past_price = float(df_closed["close"].iloc[-1 - mom_lookback])
        if past_price:
            momentum_pct = round((price - past_price) / past_price * 100, 3)
    if momentum_pct is None:
        momentum_note = "no data"
    elif abs(momentum_pct) >= 1.0:
        momentum_note = f"Strong move ({'up' if momentum_pct > 0 else 'down'})"
    elif abs(momentum_pct) >= 0.3:
        momentum_note = f"Moving {'up' if momentum_pct > 0 else 'down'}"
    else:
        momentum_note = "Quiet / choppy"

    # Last CLOSED candle's own move. This used to read the forming bar, so it
    # flickered red/green within the same period.
    last_candle_pct = None
    last_open = float(df_closed["open"].iloc[-1])
    if last_open:
        last_candle_pct = round((price - last_open) / last_open * 100, 3)
    last_candle_direction = ("up" if (last_candle_pct or 0) > 0
                             else ("down" if (last_candle_pct or 0) < 0 else "flat"))

    htf_bias = _get_htf_bias_cached(symbol)

    snap_entry_tf, snap_confirm = _get_ltf_snaps_cached(
        symbol, timeframe=timeframe, preloaded_entry_snap=snap_entry
    )
    if snap_entry_tf is None: snap_entry_tf = snap_entry
    if snap_confirm is None: snap_confirm = snap_entry

    if CONFIG['ENABLE_PRIME_HOURS_FILTER']:
        prime_ok, prime_reason = is_prime_trading_hours()
        if not prime_ok:
            return {
                "symbol": symbol, "timeframe": timeframe, "price": _px(price),
                "signal": "WAIT", "reason": f"BLOCKED ({prime_reason})",
            }

    buy_score, sell_score = get_ltf_scores(snap_entry_tf, snap_confirm)
    direction, reason = decide_direction(
        buy_score, sell_score, htf_bias, snap_entry["adx"],
        snap_entry_tf["regime"], snap_confirm["regime"], entry_rsi=rsi_now,
        snap_entry=snap_entry_tf, snap_confirm=snap_confirm,
        cvd_pressure=snap_entry_tf.get("cvd_pressure_norm"),   # FIX v4 (F17)
        eff_cfg=eff_cfg,
    )
    confluence_detail = _last_confluence_detail[0]
    bo = detect_blowoff(df_closed, symbol=symbol)
    bo_ok, bo_reason = blowoff_gate(direction, bo)
    if not bo_ok:
        direction, reason = None, bo_reason

    if direction is not None:
        vol_spike_series = detect_volume_spike(df_closed)
        if not bool(vol_spike_series.tail(3).any()):
            direction, reason = None, f"BLOCKED (No volume spike confirming {reason})"

    if CONFIG['REALISTIC_BACKTEST']:
        tp, sl = calc_tp_sl_with_slippage(direction, price, atr_now)
    else:
        tp, sl = calc_tp_sl(direction, price, atr_now)

    # FIX v3 (F3): the cost gate runs last, after every other filter, so the
    # reason string tells you plainly when a setup was valid but too small to
    # be worth its fees. If you see this constantly on a timeframe, that
    # timeframe is not tradeable at your fee level — move up, don't loosen it.
    if direction is not None and not cost_gate(price, tp):
        edge = abs(float(tp) - price) / price * 100 if tp else 0.0
        direction = None
        reason = (f"BLOCKED (edge {edge:.3f}% < {CONFIG['MIN_TP_COST_RATIO']}x "
                  f"round-trip cost {round_trip_cost_pct()}%)")
        tp, sl = None, None

    signal = direction if direction else "WAIT"
    blowoff_info = {
        "active": bo["blowoff"], "score": bo["score"],
        "confirmed": bo["confirmed"], "levels": bo.get("levels", {}),
    }

    age_key = f"{symbol}:{timeframe}"
    now_ts = _t.time()
    prev = _SIGNAL_AGE_CACHE.get(age_key)
    if signal == "WAIT":
        _SIGNAL_AGE_CACHE.pop(age_key, None)
        signal_age_seconds = None
    elif prev is not None and prev["signal"] == signal:
        signal_age_seconds = round(now_ts - prev["since"], 1)
    else:
        _SIGNAL_AGE_CACHE[age_key] = {"signal": signal, "since": now_ts}
        signal_age_seconds = 0.0

    tp_levels = calc_tp_sl_scaled(direction, price, atr_now) if direction else None

    suggested_qty_min = calc_position_size_for_target(price, tp, CONFIG['TARGET_PROFIT_INR_MIN']) if direction else None
    suggested_qty_max = calc_position_size_for_target(price, tp, CONFIG['TARGET_PROFIT_INR_MAX']) if direction else None

    risk_size = sizing.calc_risk_based_size(price, sl, tp) if direction else None
    capital_for_target = (sizing.capital_needed_for_profit(
        price, sl, tp, CONFIG['TARGET_PROFIT_INR_MIN']) if direction else None)

    return {
        "symbol": symbol, "timeframe": timeframe, "price": _px(price),
        "rsi": round(rsi_now, 2) if rsi_now is not None else None,
        "signal": signal, "reason": reason,
        "signal_age_seconds": signal_age_seconds,
        "buy_score": buy_score, "sell_score": sell_score, "htf_bias": htf_bias,
        "regime": snap_entry["regime"]["regime"], "structure": snap_entry["structure_event"],
        # FIX v4 (F18): the card showed only the entry timeframe's regime, so
        # "Regime: TRENDING" sat next to "BLOCKED (Choppy Flat Zones)" and
        # looked like a contradiction. decide_direction() requires BOTH the
        # entry and the confirmation timeframe to be TRENDING — the confirm
        # frame was the one blocking, and it was invisible.
        "regime_entry": snap_entry_tf["regime"]["regime"],
        "regime_confirm": snap_confirm["regime"]["regime"],
        "confirm_timeframe": TIMEFRAME_CONFIRM_MAP.get(timeframe, "15m"),
        "exchange": ex_id, "entry": _px(price) if direction else None,
        "tp": tp, "sl": sl, "atr": _px(atr_now) if atr_now else None,
        "tp_levels": tp_levels,
        "risk_size": risk_size,
        "capital_needed_for_500": capital_for_target,
        "suggested_qty_for_min_profit": suggested_qty_min,
        "suggested_qty_for_max_profit": suggested_qty_max,
        "cvd_pressure": round(snap_entry_tf.get("cvd_pressure", 0.0), 2),
        "cvd_pressure_norm": round(snap_entry_tf.get("cvd_pressure_norm", 0.0), 3),
        "cvd_gate_threshold": CONFIG['CVD_PRESSURE_MIN_FRAC'],
        # FIX v6 (F24): which structural components actually fired, and what
        # each was worth. A component with weight 0.0 still reports whether
        # it fired, so "never triggers" is distinguishable from "triggers and
        # is switched off".
        "confluence_detail": confluence_detail,
        "confluence_threshold": eff_cfg['MIN_CONFLUENCE_SCORE'],
        "acceleration_boost_enabled": CONFIG['ENABLE_ACCELERATION_BOOST'],
        "blowoff": blowoff_info,
        "momentum_pct": momentum_pct,
        "momentum_note": momentum_note,
        "last_candle_pct": last_candle_pct,
        "last_candle_direction": last_candle_direction,
        "round_trip_cost_pct": round_trip_cost_pct(),
        "target_profit_range_inr": [CONFIG['TARGET_PROFIT_INR_MIN'], CONFIG['TARGET_PROFIT_INR_MAX']],
        "liquidity": {
            "sweep": snap_entry["sweep"], "fvg": snap_entry["fvg"],
            "dist_to_bull_fvg_pct": round(snap_entry["dist_to_bull_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bull_fvg_pct"]) else None,
            "dist_to_bear_fvg_pct": round(snap_entry["dist_to_bear_fvg_pct"], 3) if not pd.isna(snap_entry["dist_to_bear_fvg_pct"]) else None,
            "bsl_level": _px(snap_entry["bsl_level"]) if not pd.isna(snap_entry["bsl_level"]) else None,
            "ssl_level": _px(snap_entry["ssl_level"]) if not pd.isna(snap_entry["ssl_level"]) else None,
            "eq_high_count": snap_entry["eq_high_count"], "eq_low_count": snap_entry["eq_low_count"],
            "inducement": snap_entry["inducement"],
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# SHARED BACKTEST EXECUTION + REPORTING
# ══════════════════════════════════════════════════════════════════════════
def _simulate_exit(direction, entry, tp, sl, highs, lows, closes, start_j, window, n,
                   breakeven_dist=None):
    """FIX v3 (F5, F6): one shared exit simulator, so a fix here applies to
    every backtest instead of being re-implemented five times with five
    chances to get it wrong.

    F5 — the STOP is checked before the target. Previously every loop tested
    TP first, so a candle whose range covered both levels was recorded as a
    WIN. With TP 2.2 ATR and SL 0.8 ATR the two are only 3 ATR apart, and a
    single volatile bar spans that regularly. Without knowing the intrabar
    path the honest assumption is the adverse one.

    F6 — trades that resolve neither way are closed at market on the last bar
    of the window and returned as TIMEOUT, instead of being dropped. The old
    `if outcome == "OPEN": continue` deleted precisely the trades that chop
    sideways and pay the full round-trip fee for nothing.
    """
    current_sl = sl
    sl_moved = False
    for j in range(start_j, min(start_j + window, n)):
        fh, fl = highs[j], lows[j]

        if breakeven_dist is not None and not sl_moved:
            if direction == "BUY" and fh >= entry + breakeven_dist:
                current_sl = entry; sl_moved = True
            elif direction == "SELL" and fl <= entry - breakeven_dist:
                current_sl = entry; sl_moved = True

        if direction == "BUY":
            if fl <= current_sl:
                return ("BREAKEVEN" if sl_moved else "LOSS"), current_sl, j
            if fh >= tp:
                return "WIN", tp, j
        else:
            if fh >= current_sl:
                return ("BREAKEVEN" if sl_moved else "LOSS"), current_sl, j
            if fl <= tp:
                return "WIN", tp, j

    last_j = min(start_j + window, n) - 1
    return "TIMEOUT", closes[last_j], last_j


def _net_pnl_pct(direction, entry, exit_price):
    """FIX v3 (F4): round-trip cost, not a single-sided fee."""
    gross = ((exit_price - entry) / entry * 100 if direction == "BUY"
             else (entry - exit_price) / entry * 100)
    return gross - round_trip_cost_pct()


def _summarize(results, symbol, timeframe, candles, blocked_by_cost=0, extra=None):
    """FIX v3 (F11, F16): candles is the measured length of the data actually
    returned, and the number of setups killed by the cost gate is reported so
    a low trade count is explainable rather than mysterious.

    Wins/losses are classified by net P&L sign, not by the outcome label, so
    a TIMEOUT that ended slightly green counts as a win and a BREAKEVEN that
    still paid fees counts as a loss — which is what actually happened to the
    account."""
    base = {"symbol": symbol, "timeframe": timeframe, "candles_tested": candles,
            "blocked_by_cost_gate": blocked_by_cost,
            "round_trip_cost_pct": round_trip_cost_pct()}
    if extra:
        base.update(extra)

    if not results:
        base.update({"total_trades": 0, "win_rate": 0,
                     "message": "No signals in this window"})
        return base

    total = len(results)
    wins = [r for r in results if r["pnl_pct"] > 0]
    losses = [r for r in results if r["pnl_pct"] <= 0]
    timeouts = [r for r in results if r["outcome"] == "TIMEOUT"]

    gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
    gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    win_rate = round(len(wins) / total * 100, 1)
    expectancy = round(sum(r["pnl_pct"] for r in results) / total, 4)

    base.update({
        "total_trades": total,
        "wins": len(wins), "losses": len(losses), "timeouts": len(timeouts),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
        "avg_win_pct": avg_win, "avg_loss_pct": avg_loss,
        "avg_rr": round(avg_win / avg_loss, 2) if avg_loss > 0 else None,
        "recent_trades": results[-10:],
    })
    return base


def _vectorized_regime(df, eff_cfg=None):
    """FIX v3 (F12): honours the per-asset ADX_MIN, same as detect_market_regime."""
    eff_cfg = eff_cfg if eff_cfg is not None else CONFIG
    atr = calc_atr(df, CONFIG['ATR_PERIOD'])
    atr_ma = atr.rolling(CONFIG['ATR_MA_PERIOD']).mean()
    ci = calc_choppiness_index(df, CONFIG['CHOPPINESS_PERIOD'])
    adx = calc_adx(df, CONFIG['ADX_PERIOD'])
    atr_ratio = atr / atr_ma.replace(0, np.nan)
    is_compressed = atr_ratio < CONFIG['ATR_COMPRESSION_RATIO']
    is_choppy = ci > CONFIG['CHOPPINESS_TREND_MAX']
    is_trending = adx >= eff_cfg['ADX_MIN']
    regime = pd.Series("RANGING", index=df.index)
    regime[is_trending & ~is_choppy & ~is_compressed] = "TRENDING"
    regime[is_compressed] = "COMPRESSION"
    return regime, ci, adx


def _build_tf_features(df, eff_cfg=None):
    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = detect_bsl_ssl_zones(df, CONFIG['BSL_SSL_LOOKBACK'])
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    regime, ci, adx_full = _vectorized_regime(df, eff_cfg=eff_cfg)
    df["regime_label"] = regime
    return df


def _htf_bias_series_single(df_htf):
    """Bias series from the slowest frame in the ladder. FIX v5 (F22):
    parameter renamed from df15 — with 1m gone this frame is 1h, not 15m."""
    weight = 1.0
    s = pd.Series(0.0, index=df_htf.index)
    s += np.where(df_htf["structure_trend"] == "BULL", weight, np.where(df_htf["structure_trend"] == "BEAR", -weight, 0.0))
    s += np.where(df_htf["ema5"] > df_htf["ema20"], weight * 0.5, -weight * 0.5)
    s += np.where(df_htf["rsi"] > 55, weight * 0.3, np.where(df_htf["rsi"] < 45, -weight * 0.3, 0.0))
    s += np.where(df_htf["sweep_v"] == "EQUAL_LOW_SWEEP", 0.5, np.where(df_htf["sweep_v"] == "EQUAL_HIGH_SWEEP", -0.5, 0.0))
    s += np.where(df_htf["inducement"] == "BULL_INDUCEMENT", 0.3, np.where(df_htf["inducement"] == "BEAR_INDUCEMENT", -0.3, 0.0))

    # FIX v3 (F10): shift by one bar before this series is merged onto a
    # faster timeframe. The DataFrame index is the candle's OPEN time, but
    # every value on that row (ema5, rsi, structure_trend, sweep) is computed
    # through the candle's CLOSE. merge_asof(direction="backward") matches a
    # fast bar to the slow row labelled with an earlier open time — whose
    # contents do not exist until that slow bar closes. That is future
    # information feeding the entry decision, and it is why backtest results
    # looked usable while live did not. Shifting means each bar only ever
    # sees the last fully completed higher-timeframe candle.
    s = s.shift(1)

    bias = np.where(s >= 0.9, "BULLISH", np.where(s <= -0.9, "BEARISH", "NEUTRAL"))
    return pd.Series(bias, index=df_htf.index, name="bias")


def _ltf_score_series(df_entry_tf, df_confirm_tf):
    """FIX v5 (F22): was _ltf_score_series(df1m, df5m). Now takes the entry
    frame and the confirmation frame by role. With 1m removed the callers
    pass 5m and 15m."""
    def score_component(df, w):
        buy = pd.Series(0.0, index=df.index); sell = pd.Series(0.0, index=df.index)
        buy += np.where(df["pat_sig"] == "BUY", 2 * w, 0.0)
        sell += np.where(df["pat_sig"] == "SELL", 2 * w, 0.0)
        _dw = np.where(df["regime_label"] == "TRENDING",
                       CONFIG['DIV_TRENDING_WEIGHT'], CONFIG['DIV_RANGING_WEIGHT']) \
              if "regime_label" in df.columns else 1.0
        buy += np.where(df["divergence"] == "BULL_DIV", 3 * w * _dw, 0.0)
        sell += np.where(df["divergence"] == "BEAR_DIV", 3 * w * _dw, 0.0)
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
        liq_b, liq_s = _liquidity_score_vectorized(df, w)
        buy += liq_b; sell += liq_s
        return buy, sell

    b_entry, s_entry = score_component(df_entry_tf, 1.0)
    b_conf, s_conf = score_component(df_confirm_tf, 1.2)

    # FIX v3 (F10): same open-time / close-value mismatch as the bias series.
    # The confirmation contribution is shifted so an entry bar never reads a
    # confirmation candle that has not finished forming.
    b_conf, s_conf = b_conf.shift(1), s_conf.shift(1)

    out_entry = pd.DataFrame({"time": df_entry_tf.index,
                              "b_entry": b_entry.values, "s_entry": s_entry.values})
    out_conf = pd.DataFrame({"time": df_confirm_tf.index,
                             "b_conf": b_conf.values, "s_conf": s_conf.values})
    merged = pd.merge_asof(out_entry.sort_values("time"), out_conf.sort_values("time"),
                           on="time", direction="backward")
    merged["buy_score"] = (merged["b_entry"] + merged["b_conf"].fillna(0)).round(2)
    merged["sell_score"] = (merged["s_entry"] + merged["s_conf"].fillna(0)).round(2)
    merged = merged.set_index("time")
    return merged[["buy_score", "sell_score"]]


def run_backtest_full(symbol, entry_timeframe="5m"):
    """Multi-timeframe backtest.

    FIX v5 (F20): the ladder moved up one step now that 1m is gone. It was
    1m scores / 5m confirm / 15m bias; it is now 5m scores / 15m confirm /
    1h bias. Same relative spacing, same shift(1) look-ahead guard.

    STILL NOT AT FULL LIVE PARITY: the confluence gate, the CVD check and the
    blow-off veto that live analyze() applies are not replicated here, so this
    remains more permissive than live. run_backtest() below is the closer
    proxy. Do not treat these numbers as a live forecast."""
    eff_cfg = get_effective_config(symbol)
    limit = CONFIG['BACKTEST_CANDLES']
    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, limit)
    df_fast, _ = fetch_ohlcv_failover(symbol, "5m", limit)
    df_mid, _ = fetch_ohlcv_failover(symbol, "15m", limit)
    df_slow, _ = fetch_ohlcv_failover(symbol, "1h", limit)
    if any(x is None for x in [df_entry, df_fast, df_mid, df_slow]):
        return {"error": "insufficient data across timeframes (need 5m/15m/1h)"}

    df_entry = _build_tf_features(df_entry, eff_cfg=eff_cfg)
    df_fast = _build_tf_features(df_fast, eff_cfg=eff_cfg)
    df_mid = _build_tf_features(df_mid, eff_cfg=eff_cfg)
    df_slow = _build_tf_features(df_slow, eff_cfg=eff_cfg)

    bias_series = _htf_bias_series_single(df_slow)
    score_df = _ltf_score_series(df_fast, df_mid)

    regime_entry_series = df_fast[["regime_label"]].rename(columns={"regime_label": "regime_entry"})
    regime_confirm_series = df_mid[["regime_label"]].rename(columns={"regime_label": "regime_confirm"})

    entry_times = pd.DataFrame({"time": df_entry.index})

    def _asof(right_df):
        r = right_df.reset_index()
        r.columns = ["time"] + list(r.columns[1:])
        return pd.merge_asof(entry_times, r.sort_values("time"), on="time", direction="backward")

    bias_aligned = _asof(bias_series.rename("bias").to_frame())
    score_aligned = _asof(score_df)
    regime_entry_aligned = _asof(regime_entry_series)
    regime_confirm_aligned = _asof(regime_confirm_series)

    df_entry = df_entry.reset_index()
    df_entry["bias"] = bias_aligned["bias"]
    df_entry["buy_score"] = score_aligned["buy_score"]
    df_entry["sell_score"] = score_aligned["sell_score"]
    df_entry["regime_entry"] = regime_entry_aligned["regime_entry"]
    df_entry["regime_confirm"] = regime_confirm_aligned["regime_confirm"]

    opens = df_entry["open"].values
    closes = df_entry["close"].values
    highs = df_entry["high"].values
    lows = df_entry["low"].values
    n = len(df_entry)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []
    blocked_by_cost = 0

    # FIX v3 (F7): stop one bar earlier because the entry now happens on bar i+1.
    for i in range(60, n - WINDOW - 1):
        row = df_entry.iloc[i]
        rsi, adx, atr = row["rsi"], row["adx"], row["atr"]
        if pd.isna(adx) or adx < eff_cfg['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if pd.isna(atr): continue

        buy_score, sell_score = row["buy_score"], row["sell_score"]
        if pd.isna(buy_score) or pd.isna(sell_score): continue
        if rsi > CONFIG['RSI_OVERBOUGHT'] and buy_score >= sell_score: continue
        if rsi < CONFIG['RSI_OVERSOLD'] and sell_score >= buy_score: continue
        gap = abs(buy_score - sell_score)
        if gap < eff_cfg['SCORE_GAP_MIN']: continue

        if row["regime_entry"] != "TRENDING" or row["regime_confirm"] != "TRENDING":
            continue

        bias = row["bias"]
        direction = None
        # FIX v3 (F8): NEUTRAL no longer authorises both sides, matching live.
        if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score and bias == "BULLISH":
            direction = "BUY"
        elif sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score and bias == "BEARISH":
            direction = "SELL"
        if direction is None: continue

        # FIX v3 (F7): fill at the next bar's open. The close of the signal
        # bar is not knowable until that bar has ended.
        entry = opens[i + 1]
        tp, sl = calc_tp_sl(direction, entry, atr)
        if tp is None: continue

        if not cost_gate(entry, tp):
            blocked_by_cost += 1
            continue

        outcome, exit_price, _j = _simulate_exit(
            direction, entry, tp, sl, highs, lows, closes, i + 1, WINDOW, n)

        results.append({
            "time": row["timestamp"].strftime("%m-%d %H:%M") if "timestamp" in row else str(row.name),
            "direction": direction, "entry": _px(entry), "tp": _px(tp), "sl": _px(sl),
            "outcome": outcome, "pnl_pct": round(_net_pnl_pct(direction, entry, exit_price), 4),
        })

    return _summarize(results, symbol, entry_timeframe, len(df_entry),
                      blocked_by_cost=blocked_by_cost,
                      extra={"ladder": "5m scores / 15m confirm / 1h bias",
                             "note": "v5: 1m removed, ladder shifted up. SL-first fills, "
                                     "next-bar-open entry, timeout trades counted, round-trip "
                                     "cost 0.18. Confluence/CVD/blowoff gates still NOT "
                                     "replicated here — see docstring."})


def run_backtest(symbol, timeframe="5m"):
    eff_cfg = get_effective_config(symbol)
    df, ex_id = fetch_ohlcv_failover(symbol, timeframe, CONFIG['BACKTEST_CANDLES'])
    if df is None:
        return {"error": "no data"}

    df = add_indicators_vectorized(df)
    df = detect_candle_patterns_vectorized(df)
    df = detect_pro_divergence_vectorized(df)
    df = detect_structure_live_pro(df, CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = detect_liquidity_sweep_vectorized(df, CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    bo_df = blowoff_series(df, symbol=symbol)
    df = compute_active_fvg_series(df, CONFIG['FVG_MIN_GAP_PCT'])
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])

    _confirm_tf = TIMEFRAME_CONFIRM_MAP.get(timeframe)
    _confirm_rule = {"15m": "15min", "1h": "1h", "4h": "4h"}.get(_confirm_tf)
    if _confirm_rule:
        _htf_close = df["close"].resample(_confirm_rule).last().dropna()
        df["htf_ema5"] = calc_ema(_htf_close, 5).shift(1).reindex(df.index, method="ffill")
        df["htf_ema20"] = calc_ema(_htf_close, 20).shift(1).reindex(df.index, method="ffill")
    else:
        df["htf_ema5"] = df["ema5"]
        df["htf_ema20"] = df["ema20"]
    df = detect_inducement(df, CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    regime_series, _, _ = _vectorized_regime(df, eff_cfg=eff_cfg)   # FIX v3 (F12)
    df["regime_label"] = regime_series
    liq_buy_s, liq_sell_s = _liquidity_score_vectorized(df, w=1.0)
    df["liq_buy"] = liq_buy_s
    df["liq_sell"] = liq_sell_s
    # FIX v4 (F17): backtest must gate on the same normalised value as live,
    # otherwise the two diverge again the moment the threshold changes.
    cvd_pressure_series = calc_cvd_pressure_norm(df)
    df["sweep"] = df["sweep_v"]

    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    results = []
    blocked_by_cost = 0
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

    for i in range(60, n - WINDOW - 1):
        rsi = df["rsi"].iloc[i]; adx = df["adx"].iloc[i]; atr = df["atr"].iloc[i]
        ema5 = df["ema5"].iloc[i]; ema20 = df["ema20"].iloc[i]; vwap = df["vwap"].iloc[i]
        pat = df["pat_sig"].iloc[i]; div = df["divergence"].iloc[i]; struct = df["structure_event"].iloc[i]
        price_sig = closes[i]

        if pd.isna(adx) or adx < eff_cfg['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if pd.isna(atr): continue
        if df["regime_label"].iloc[i] != "TRENDING": continue

        buy_score, sell_score = 0.0, 0.0
        if pat == "BUY": buy_score += 2
        elif pat == "SELL": sell_score += 2
        dw = divergence_weight(df["regime_label"].iloc[i])
        if div == "BULL_DIV": buy_score += 3 * dw
        elif div == "BEAR_DIV": sell_score += 3 * dw
        if struct in ("BOS_BULL", "CHoCH_BULL"): buy_score += 2
        elif struct in ("BOS_BEAR", "CHoCH_BEAR"): sell_score += 2
        if not pd.isna(vwap):
            if price_sig > vwap: buy_score += 0.5
            else: sell_score += 0.5
        # FIX v3 (F9): NaN EMA no longer defaults to a sell vote.
        if pd.notna(ema5) and pd.notna(ema20):
            if ema5 > ema20: buy_score += 0.5
            else: sell_score += 0.5

        buy_score += df["liq_buy"].iloc[i]
        sell_score += df["liq_sell"].iloc[i]

        if rsi > CONFIG['RSI_OVERBOUGHT'] and buy_score >= sell_score: continue
        if rsi < CONFIG['RSI_OVERSOLD'] and sell_score >= buy_score: continue

        gap = abs(buy_score - sell_score)
        if gap < eff_cfg['SCORE_GAP_MIN']: continue

        direction = None
        if buy_score >= CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score: direction = "BUY"
        elif sell_score >= CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score: direction = "SELL"
        if direction is None: continue

        if not blowoff_gate_row(direction, bo_df, i)[0]:
            continue

        # FIX v6 (F24): live analyze() passes a full snapshot to confluence.
        # This dict must carry the same fields or the two paths score the
        # same bar differently — the exact parity drift F17 was about. fvg
        # and inducement are included even though their default weight is
        # 0.0, so flipping a weight later changes live and backtest together.
        snap_i = {
            "pattern": pat, "structure_event": struct, "divergence": div,
            "sweep": df["sweep"].iloc[i],
            "eq_low_count": df["eq_low_count"].iloc[i] if "eq_low_count" in df.columns else 0,
            "eq_high_count": df["eq_high_count"].iloc[i] if "eq_high_count" in df.columns else 0,
            "dist_to_bull_fvg_pct": df["dist_to_bull_fvg_pct"].iloc[i] if "dist_to_bull_fvg_pct" in df.columns else np.nan,
            "dist_to_bear_fvg_pct": df["dist_to_bear_fvg_pct"].iloc[i] if "dist_to_bear_fvg_pct" in df.columns else np.nan,
            "inducement": df["inducement"].iloc[i] if "inducement" in df.columns else "",
            "ema5": ema5, "ema20": ema20,
        }
        _h5 = df["htf_ema5"].iloc[i]
        _h20 = df["htf_ema20"].iloc[i]
        if pd.isna(_h5) or pd.isna(_h20):
            _h5, _h20 = ema5, ema20
        confluence_score = calc_confluence_score(snap_i, {"ema5": _h5, "ema20": _h20})
        if confluence_score < eff_cfg['MIN_CONFLUENCE_SCORE']:
            continue

        cvd_val = cvd_pressure_series.iloc[i]
        if not pd.isna(cvd_val):
            if direction == "BUY" and cvd_val < -CONFIG['CVD_PRESSURE_MIN_FRAC']:
                continue
            if direction == "SELL" and cvd_val > CONFIG['CVD_PRESSURE_MIN_FRAC']:
                continue

        entry = opens[i + 1]                       # FIX v3 (F7)
        tp, sl = calc_tp_sl(direction, entry, atr)
        if tp is None: continue

        if not cost_gate(entry, tp):               # FIX v3 (F3)
            blocked_by_cost += 1
            continue

        outcome, exit_price, _j = _simulate_exit(
            direction, entry, tp, sl, highs, lows, closes, i + 1, WINDOW, n)

        results.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": _px(entry), "tp": _px(tp), "sl": _px(sl),
            "outcome": outcome, "pnl_pct": round(_net_pnl_pct(direction, entry, exit_price), 4),
        })

    return _summarize(results, symbol, timeframe, len(df),
                      blocked_by_cost=blocked_by_cost,
                      extra={"note": "v5: closest proxy for live. SL-first fills, next-bar-open "
                                     "entry, timeouts counted, round-trip cost 0.18, cost gate."})


def run_factor_backtest(symbol, timeframe="5m", candles=None):
    """Which single factors actually carry edge on their own.

    FIX v6 (F27): every factor function now reads NUMPY ARRAYS, not
    df[col].iloc[i]. Scalar .iloc access goes through pandas indexing
    machinery on every single call; in a loop of 3000 bars across 8 factors
    that is 24,000 of them per run, and it was the reason this endpoint took
    over two minutes and got killed by gunicorn's 120s timeout once
    BACKTEST_OUTCOME_WINDOW went from 10 to 60. The arrays are extracted
    once up front and indexed directly, which is roughly an order of
    magnitude faster and changes no result.

    `candles` is a parameter so a slow host can ask for less. Fewer candles
    means a smaller sample and wider error bars, not a faster answer to the
    same question — halve it only if the request will not complete
    otherwise, and read the trade counts accordingly.
    """
    eff_cfg = get_effective_config(symbol)
    limit = candles if candles is not None else CONFIG['BACKTEST_CANDLES']
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
    df = calc_equal_level_density(df, CONFIG['BSL_SSL_LOOKBACK'], CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])

    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df); WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']

    # FIX v6 (F27): one extraction, then plain array indexing everywhere.
    a_atr = df["atr"].values
    a_sweep = df["sweep_v"].values
    a_struct = df["structure_event"].values
    a_div = df["divergence"].values
    a_pat = df["pat_sig"].values
    a_ema5 = df["ema5"].values
    a_ema20 = df["ema20"].values
    a_dbull = df["dist_to_bull_fvg_pct"].values
    a_dbear = df["dist_to_bear_fvg_pct"].values
    a_ind = df["inducement"].values
    a_eqh = df["eq_high_count"].values
    a_eql = df["eq_low_count"].values

    fvg_prox = CONFIG['FVG_PROXIMITY_PCT']
    eq_min = CONFIG['EQUAL_LEVEL_MIN_COUNT']

    def simulate(direction_fn, label):
        results = []
        blocked = 0
        for i in range(60, n - WINDOW - 1):
            atr = a_atr[i]
            if np.isnan(atr): continue
            direction = direction_fn(i)
            if direction is None: continue
            entry = opens[i + 1]                   # FIX v3 (F7)
            tp, sl = calc_tp_sl(direction, entry, atr)
            if tp is None: continue
            if not cost_gate(entry, tp):           # FIX v3 (F3)
                blocked += 1
                continue
            outcome, exit_price, _j = _simulate_exit(
                direction, entry, tp, sl, highs, lows, closes, i + 1, WINDOW, n)
            results.append({"outcome": outcome,
                            "pnl_pct": _net_pnl_pct(direction, entry, exit_price)})

        if not results:
            return {"label": label, "total_trades": 0, "blocked_by_cost_gate": blocked,
                    "outcome_window_bars": WINDOW, "note": "no signals"}

        total = len(results)
        wins = [r for r in results if r["pnl_pct"] > 0]
        losses = [r for r in results if r["pnl_pct"] <= 0]
        timeouts = [r for r in results if r["outcome"] == "TIMEOUT"]
        gross_profit = sum(r["pnl_pct"] for r in wins) if wins else 0.0
        gross_loss = abs(sum(r["pnl_pct"] for r in losses)) if losses else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        win_rate = round(len(wins) / total * 100, 1)
        expectancy = round(sum(r["pnl_pct"] for r in results) / total, 4)
        # FIX v6 (F26): timeout_pct is the first number to read. If most
        # trades time out, the outcome window is too short for TP_ATR_MULT
        # and every other figure below is measuring fees, not edge. Fix the
        # window before drawing any conclusion about the factor itself.
        return {"label": label, "total_trades": total, "wins": len(wins),
                "losses": len(losses), "timeouts": len(timeouts),
                "timeout_pct": round(len(timeouts) / total * 100, 1),
                "win_rate": win_rate, "profit_factor": profit_factor,
                "expectancy_pct": expectancy,
                "avg_win_pct": round(gross_profit / len(wins), 4) if wins else 0.0,
                "avg_loss_pct": round(gross_loss / len(losses), 4) if losses else 0.0,
                "blocked_by_cost_gate": blocked,
                "outcome_window_bars": WINDOW}

    def f_sweep(i):
        s = a_sweep[i]
        if s == "EQUAL_LOW_SWEEP": return "BUY"
        if s == "EQUAL_HIGH_SWEEP": return "SELL"
        return None

    def f_structure(i):
        ev = a_struct[i]
        if ev in ("BOS_BULL", "CHoCH_BULL"): return "BUY"
        if ev in ("BOS_BEAR", "CHoCH_BEAR"): return "SELL"
        return None

    def f_divergence(i):
        d = a_div[i]
        if d == "BULL_DIV": return "BUY"
        if d == "BEAR_DIV": return "SELL"
        return None

    def f_pattern(i):
        p = a_pat[i]
        if p == "BUY": return "BUY"
        if p == "SELL": return "SELL"
        return None

    def f_ema_baseline(i):
        if i < 1: return None
        if a_ema5[i - 1] <= a_ema20[i - 1] and a_ema5[i] > a_ema20[i]: return "BUY"
        if a_ema5[i - 1] >= a_ema20[i - 1] and a_ema5[i] < a_ema20[i]: return "SELL"
        return None

    def f_fvg(i):
        dbull = a_dbull[i]; dbear = a_dbear[i]
        if not np.isnan(dbull) and 0 <= dbull <= fvg_prox: return "BUY"
        if not np.isnan(dbear) and 0 <= dbear <= fvg_prox: return "SELL"
        return None

    def f_inducement(i):
        ind = a_ind[i]
        if ind == "BULL_INDUCEMENT": return "BUY"
        if ind == "BEAR_INDUCEMENT": return "SELL"
        return None

    def f_equal_level_density(i):
        eqh = a_eqh[i]; eql = a_eql[i]
        if np.isnan(eqh) or np.isnan(eql): return None
        if eql >= eq_min and eql > eqh: return "BUY"
        if eqh >= eq_min and eqh > eql: return "SELL"
        return None

    return {
        "symbol": symbol, "timeframe": timeframe, "candles_tested": len(df),
        "round_trip_cost_pct": round_trip_cost_pct(),
        "outcome_window_bars": WINDOW,
        "tp_atr_mult": CONFIG['TP_ATR_MULT'], "sl_atr_mult": CONFIG['SL_ATR_MULT'],
        # FIX v6 (F26): on a pure random walk with no edge at all, a 3.0/0.8
        # ATR target set resolves at roughly 28% wins. Any factor at or below
        # that number is not an underperforming factor — it is noise. Compare
        # win_rate against this, never against 50%.
        "random_walk_win_rate_pct": 28.0,
        "factors": [
            simulate(f_sweep, "1. Liquidity Sweep (BSL/SSL) only"),
            simulate(f_structure, "2. Structure Break (BOS/CHoCH) only"),
            simulate(f_divergence, "3. Divergence only"),
            simulate(f_pattern, "4. Candle Pattern only"),
            simulate(f_ema_baseline, "5. EMA Crossover (baseline)"),
            simulate(f_fvg, "6. Fair Value Gap (FVG) proximity only"),
            simulate(f_inducement, "7. Inducement wick-trap only"),
            simulate(f_equal_level_density, "8. Equal-Level Density only"),
        ]
    }


# ══════════════════════════════════════════════════════════════════════════
# RISK MANAGEMENT MODULE
# ══════════════════════════════════════════════════════════════════════════
class RiskManager:
    """Computes sizes and yes/no gates. Does NOT place orders."""

    def __init__(self, account_capital_usdt):
        self.capital = account_capital_usdt
        self.daily_pnl_pct = 0.0
        self.trades_today = []
        self.open_positions = 0
        self.consecutive_losses = 0   # FIX v3 (F15)

    def reset_day(self):
        self.daily_pnl_pct = 0.0
        self.trades_today = []
        self.consecutive_losses = 0

    def record_trade_result(self, pnl_pct_of_capital):
        self.daily_pnl_pct += pnl_pct_of_capital
        self.trades_today.append(pnl_pct_of_capital)
        # FIX v3 (F15): MAX_CONSECUTIVE_LOSSES was declared in CONFIG and
        # referenced nowhere in the entire file. Tilt after a losing streak is
        # the most expensive failure mode in discretionary scalping, and the
        # guard that was supposed to catch it did not exist.
        if pnl_pct_of_capital <= 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def circuit_breaker_tripped(self):
        return self.daily_pnl_pct <= -abs(CONFIG['MAX_DAILY_LOSS_PCT'])

    def can_open_new_position(self):
        if self.circuit_breaker_tripped():
            return False, (f"Daily loss limit hit ({self.daily_pnl_pct:.2f}% <= "
                           f"-{CONFIG['MAX_DAILY_LOSS_PCT']}%). No more trades today.")
        if self.consecutive_losses >= CONFIG['MAX_CONSECUTIVE_LOSSES']:
            return False, (f"{self.consecutive_losses} losses in a row "
                           f"(limit {CONFIG['MAX_CONSECUTIVE_LOSSES']}). Stop and review "
                           f"before the next entry.")
        if self.open_positions >= CONFIG['MAX_CONCURRENT_POSITIONS']:
            return False, f"Max concurrent positions ({CONFIG['MAX_CONCURRENT_POSITIONS']}) already open."
        return True, "OK"

    def position_size(self, entry_price, sl_price, leverage=1):
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
        ok, reason = self.can_open_new_position()
        if not ok:
            return {"take_trade": False, "reason": reason}
        if signal_dict.get("signal") not in ("BUY", "SELL"):
            return {"take_trade": False, "reason": "No active signal (WAIT)."}
        entry = signal_dict.get("entry"); sl = signal_dict.get("sl")
        if entry is None or sl is None:
            return {"take_trade": False, "reason": "Missing entry/SL in signal."}
        size = self.position_size(entry, sl, leverage=leverage)
        return {"take_trade": True, "sizing": size, "signal": signal_dict}


# ══════════════════════════════════════════════════════════════════════════
# ORDER FLOW PROXY MODULE — approximated from OHLCV
# ══════════════════════════════════════════════════════════════════════════
def calc_recent_cvd_pressure(df, lookback=None):
    lookback = lookback or CONFIG['CVD_PRESSURE_LOOKBACK']
    df = calc_candle_delta_proxy(df)
    return df["delta_proxy"].rolling(lookback).sum()


def calc_cvd_pressure_norm(df, lookback=None):
    """FIX v4 (F17): volume-normalised CVD pressure, range roughly -1..+1.

    calc_recent_cvd_pressure() returns a raw sum of (close-location * volume).
    Its magnitude therefore depends entirely on how much the asset trades —
    -76 is enormous on one symbol and noise on another — which makes any fixed
    threshold meaningless and makes comparing across BTC/ETH/DEXE/BANK
    impossible. Dividing by the window's total volume removes the scale, so a
    single threshold works everywhere."""
    lookback = lookback or CONFIG['CVD_PRESSURE_LOOKBACK']
    d = calc_candle_delta_proxy(df)
    delta_sum = d["delta_proxy"].rolling(lookback).sum()
    vol_sum = d["volume"].rolling(lookback).sum()
    return delta_sum / (vol_sum + 1e-10)


def calc_candle_delta_proxy(df):
    df = df.copy()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng
    mfm = mfm.fillna(0.0)
    df["delta_proxy"] = mfm * df["volume"]
    return df


def calc_cvd_proxy(df):
    df = calc_candle_delta_proxy(df)
    day = df.index.date
    df["cvd_proxy"] = pd.Series(df["delta_proxy"].values, index=df.index).groupby(day).cumsum()
    return df


def detect_absorption_proxy(df, vol_mult=None, body_max_pct=None):
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
    poc_price = _px(bin_mid[poc_idx])

    vols_nonzero = vol_per_bin[nonzero_mask]
    lvn_thresh = np.percentile(vols_nonzero, lvn_pctl)
    hvn_thresh = np.percentile(vols_nonzero, hvn_pctl)

    lvn_levels = sorted(_px(p) for p, v in zip(bin_mid, vol_per_bin)
                        if 0 < v <= lvn_thresh)
    hvn_levels = sorted(_px(p) for p, v in zip(bin_mid, vol_per_bin)
                        if v >= hvn_thresh)

    return {"poc": poc_price, "hvn_levels": hvn_levels, "lvn_levels": lvn_levels}


def in_session(ts):
    hour = ts.hour
    ny = CONFIG['OF_SESSION_NY_START_UTC'] <= hour < CONFIG['OF_SESSION_NY_END_UTC']
    ldn = CONFIG['OF_SESSION_LDN_START_UTC'] <= hour < CONFIG['OF_SESSION_LDN_END_UTC']
    return ny or ldn, ("NY" if ny else ("LDN" if ldn else None))


def _nearest_level(price, levels, tol_pct):
    if not levels:
        return None
    for lvl in levels:
        if lvl == 0:
            continue
        if abs(price - lvl) / lvl * 100 <= tol_pct:
            return lvl
    return None


def detect_second_drive_setup(df, vp_nodes, breakout_lookback=None, max_bars=None, tol_pct=None):
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
    lookback = df.tail(10)
    buffer_pct = CONFIG['OF_SL_BUFFER_TICKS_PCT'] / 100
    if direction == "BUY":
        swing_low = lookback["low"].min()
        return _px(swing_low * (1 - buffer_pct))
    if direction == "SELL":
        swing_high = lookback["high"].max()
        return _px(swing_high * (1 + buffer_pct))
    return None


def apply_breakeven_trigger(direction, entry_price, current_high, current_low, atr, sl, cvd_pressure=None):
    trigger_dist = atr * CONFIG['OF_BREAKEVEN_TRIGGER_ATR_MULT']
    if direction == "BUY" and current_high >= entry_price + trigger_dist:
        if cvd_pressure is None or cvd_pressure >= -CONFIG['CVD_PRESSURE_MIN_FRAC']:
            return max(sl, entry_price)
    if direction == "SELL" and current_low <= entry_price - trigger_dist:
        if cvd_pressure is None or cvd_pressure <= CONFIG['CVD_PRESSURE_MIN_FRAC']:
            return min(sl, entry_price)
    return sl


class OrderFlowRiskManager(RiskManager):
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


def analyze_orderflow(symbol, entry_timeframe="5m", structure_timeframe="15m"):
    """FIX v5 (F19): was 1m entry / 5m structure. Now 5m entry / 15m
    structure. The POC target this produces is often only a fraction of a
    percent away, so the cost gate below rejects a large share of them —
    that is the gate doing its job, not a bug."""
    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, CONFIG['LIMIT'])
    df_struct, _ = fetch_ohlcv_failover(symbol, structure_timeframe, CONFIG['LIMIT'])
    if df_entry is None or df_struct is None:
        return {"symbol": symbol, "error": "no data"}

    # FIX v3 (F2): closed candles only, same rule as analyze().
    df_entry = _drop_forming_candle(df_entry)
    df_struct = _drop_forming_candle(df_struct)
    if df_entry is None or len(df_entry) < 30:
        return {"symbol": symbol, "error": "not enough closed candles"}

    now_ts = df_entry.index[-1]
    session_ok, session_name = in_session(now_ts)

    df_entry = add_indicators_vectorized(df_entry)
    df_entry = calc_cvd_proxy(df_entry)
    df_entry["absorption"] = detect_absorption_proxy(df_entry)

    vp_nodes = build_volume_profile_nodes(df_struct)
    atr_series = calc_atr(df_entry, CONFIG['ATR_PERIOD'])

    if not session_ok:
        return {
            "symbol": symbol, "timeframe": entry_timeframe, "signal": "WAIT",
            "reason": "Outside NY/London high-volatility session",
            "session": session_name, "price": _px(df_entry["close"].iloc[-1]),
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
            "reason": reason, "session": session_name, "price": _px(price),
            "vp_nodes": vp_nodes,
        }

    sl = calc_orderflow_sl(direction, df_entry, atr_now)
    poc = vp_nodes.get("poc")
    if poc is not None:
        tp = poc
    else:
        tp, _ = calc_tp_sl(direction, price, atr_now)

    # FIX v3 (F3): POC can sit on the wrong side of price, or close enough to
    # it that the trade cannot pay its own fees. Both were being returned as
    # live signals.
    if tp is None or (direction == "BUY" and tp <= price) or (direction == "SELL" and tp >= price):
        return {
            "symbol": symbol, "timeframe": entry_timeframe, "signal": "WAIT",
            "reason": "Target (POC) is on the wrong side of price",
            "session": session_name, "price": _px(price), "vp_nodes": vp_nodes,
        }
    if not cost_gate(price, tp):
        edge = abs(tp - price) / price * 100
        return {
            "symbol": symbol, "timeframe": entry_timeframe, "signal": "WAIT",
            "reason": (f"BLOCKED (edge {edge:.3f}% < {CONFIG['MIN_TP_COST_RATIO']}x "
                       f"round-trip cost {round_trip_cost_pct()}%)"),
            "session": session_name, "price": _px(price), "vp_nodes": vp_nodes,
        }

    return {
        "symbol": symbol, "timeframe": entry_timeframe, "signal": direction,
        "setup_type": setup_type, "reason": reason, "session": session_name,
        "price": _px(price), "entry": _px(price),
        "sl": sl, "tp": _px(tp),
        "atr": _px(atr_now),
        "cvd_proxy": round(float(df_entry["cvd_proxy"].iloc[-1]), 2),
        "absorption": df_entry["absorption"].iloc[-1] or None,
        "vp_nodes": vp_nodes,
        "exchange": ex_id,
        "round_trip_cost_pct": round_trip_cost_pct(),
        "note": "OHLCV-based order-flow PROXY — not real tape/footprint data. Paper trade first.",
    }


def run_orderflow_backtest(symbol, entry_timeframe="5m", structure_timeframe="15m"):
    """FIX v5 (F19): was 1m entry / 5m structure."""
    limit = CONFIG['BACKTEST_CANDLES']
    df_entry, ex_id = fetch_ohlcv_failover(symbol, entry_timeframe, limit)
    df_struct, _ = fetch_ohlcv_failover(symbol, structure_timeframe, limit)
    if df_entry is None or df_struct is None:
        return {"error": "no data"}

    df_entry = add_indicators_vectorized(df_entry)
    df_entry = calc_cvd_proxy(df_entry)
    atr_series = calc_atr(df_entry, CONFIG['ATR_PERIOD'])
    cvd_pressure_series = calc_cvd_pressure_norm(df_entry)   # FIX v4 (F17)

    opens = df_entry["open"].values
    closes = df_entry["close"].values
    highs = df_entry["high"].values
    lows = df_entry["low"].values
    n = len(df_entry)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    min_lookback = CONFIG['OF_BREAKOUT_LOOKBACK'] + CONFIG['OF_SECOND_DRIVE_MAX_BARS'] + 25
    results = []
    blocked_by_cost = 0

    for i in range(min_lookback, n - WINDOW - 1):
        ts = df_entry.index[i]
        session_ok, session_name = in_session(ts)
        if not session_ok:
            continue

        sub_df = df_entry.iloc[:i + 1]
        vp_source = df_struct[df_struct.index <= ts]
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

        entry = opens[i + 1]                       # FIX v3 (F7)
        sl = calc_orderflow_sl(direction, sub_df, atr_now)
        poc = vp_nodes.get("poc")
        tp = poc if poc is not None else (entry + atr_now * CONFIG['TP_ATR_MULT'] if direction == "BUY"
                                          else entry - atr_now * CONFIG['TP_ATR_MULT'])
        if sl is None or tp is None:
            continue
        if direction == "BUY" and (tp <= entry or sl >= entry):
            continue
        if direction == "SELL" and (tp >= entry or sl <= entry):
            continue
        if not cost_gate(entry, tp):               # FIX v3 (F3)
            blocked_by_cost += 1
            continue

        # Breakeven management, then the shared SL-first exit simulator.
        current_sl = sl
        outcome, exit_price, _j = None, None, None
        for j in range(i + 1, min(i + 1 + WINDOW, n)):
            fh, fl = highs[j], lows[j]
            current_sl = apply_breakeven_trigger(direction, entry, fh, fl, atr_now, current_sl,
                                                 cvd_pressure=cvd_pressure_series.iloc[j])
            # FIX v3 (F5): stop first.
            if direction == "BUY":
                if fl <= current_sl:
                    outcome = "BREAKEVEN" if current_sl >= entry else "LOSS"
                    exit_price = current_sl; break
                if fh >= tp:
                    outcome, exit_price = "WIN", tp; break
            else:
                if fh >= current_sl:
                    outcome = "BREAKEVEN" if current_sl <= entry else "LOSS"
                    exit_price = current_sl; break
                if fl <= tp:
                    outcome, exit_price = "WIN", tp; break
        if outcome is None:                        # FIX v3 (F6)
            outcome = "TIMEOUT"
            exit_price = closes[min(i + WINDOW, n - 1)]

        results.append({
            "time": df_entry.index[i].strftime("%m-%d %H:%M"), "session": session_name,
            "setup": setup_type, "direction": direction,
            "entry": _px(entry), "tp": _px(tp), "sl": _px(sl),
            "outcome": outcome, "pnl_pct": round(_net_pnl_pct(direction, entry, exit_price), 4),
        })

    by_setup = {}
    for r in results:
        by_setup.setdefault(r["setup"], []).append(r)
    setup_breakdown = {}
    for k, rs in by_setup.items():
        w = [r for r in rs if r["pnl_pct"] > 0]
        setup_breakdown[k] = {"trades": len(rs),
                              "win_rate": round(len(w) / len(rs) * 100, 1) if rs else 0}

    return _summarize(results, symbol, entry_timeframe, len(df_entry),
                      blocked_by_cost=blocked_by_cost,
                      extra={"setup_breakdown": setup_breakdown,
                             "structure_timeframe": structure_timeframe,
                             "note": "OHLCV-based order-flow PROXY backtest — no real tape data."})


def run_combined_backtest(symbol, timeframe="5m", min_agree=2, strong_adx=25, use_breakeven=True):
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

    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []
    blocked_by_cost = 0

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

    for i in range(60, n - WINDOW - 1):
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

        entry = opens[i + 1]                       # FIX v3 (F7)
        tp, sl = calc_tp_sl(direction, entry, atr)
        if tp is None: continue
        if not cost_gate(entry, tp):               # FIX v3 (F3)
            blocked_by_cost += 1
            continue

        breakeven_dist = (atr * 0.5) if use_breakeven else None
        outcome, exit_price, _j = _simulate_exit(
            direction, entry, tp, sl, highs, lows, closes, i + 1, WINDOW, n,
            breakeven_dist=breakeven_dist)

        results.append({
            "time": df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": _px(entry), "tp": _px(tp), "sl": _px(sl),
            "outcome": outcome, "pnl_pct": round(_net_pnl_pct(direction, entry, exit_price), 4),
            "votes": votes,
        })

    return _summarize(results, symbol, timeframe, len(df),
                      blocked_by_cost=blocked_by_cost,
                      extra={"min_agree": min_agree, "strong_adx": strong_adx,
                             "use_breakeven": use_breakeven})


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
    """Does extreme funding predict mean reversion?

    NOTE ON A REMAINING BIAS: the percentile thresholds are computed from the
    WHOLE sample, including bars in the future relative to each trade. That is
    a mild look-ahead — at bar i you could not have known the eventual 85th
    percentile. For a rough factor probe it is acceptable; if this factor ever
    graduates into the live score, switch to an expanding-window quantile."""
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

    opens = price_df["open"].values
    closes = price_df["close"].values
    highs = price_df["high"].values
    lows = price_df["low"].values
    atrs = price_df["atr"].values
    funding_vals = price_df["funding_rate"].values
    n = len(price_df)
    WINDOW = CONFIG['BACKTEST_OUTCOME_WINDOW']
    results = []
    blocked_by_cost = 0

    for i in range(60, n - WINDOW - 1):
        fr = funding_vals[i]
        atr = atrs[i]
        if pd.isna(fr) or pd.isna(atr): continue

        direction = None
        if fr >= high_thresh: direction = "SELL"
        elif fr <= low_thresh: direction = "BUY"
        if direction is None: continue

        entry = opens[i + 1]                       # FIX v3 (F7)
        tp, sl = calc_tp_sl(direction, entry, atr)
        if tp is None: continue
        if not cost_gate(entry, tp):               # FIX v3 (F3)
            blocked_by_cost += 1
            continue

        outcome, exit_price, _j = _simulate_exit(
            direction, entry, tp, sl, highs, lows, closes, i + 1, WINDOW, n)

        results.append({
            "time": price_df.index[i].strftime("%m-%d %H:%M"),
            "direction": direction, "entry": _px(entry),
            "funding_rate": round(float(fr), 6),
            "outcome": outcome, "pnl_pct": round(_net_pnl_pct(direction, entry, exit_price), 4),
        })

    return _summarize(results, symbol, price_timeframe, len(price_df),
                      blocked_by_cost=blocked_by_cost,
                      extra={"high_funding_threshold": round(float(high_thresh), 6),
                             "low_funding_threshold": round(float(low_thresh), 6),
                             "note": "Tests funding-rate mean-reversion in isolation."})


# ══════════════════════════════════════════════════════════════════════════
# COST REALITY CHECK — run this before anything else
# ══════════════════════════════════════════════════════════════════════════
def cost_reality_check(symbol="BTC/USDT:USDT", timeframes=SUPPORTED_TIMEFRAMES):
    """FIX v3 (F3): the single most useful number in this file.

    For each timeframe it reports the median ATR as a percentage of price, the
    gross take-profit that TP_ATR_MULT implies, and how many multiples of your
    round-trip cost that target represents. Any timeframe below
    MIN_TP_COST_RATIO is not tradeable at your fee level — no signal quality
    fixes that, because the target is smaller than the toll.

    FIX v5 (F19): defaults to SUPPORTED_TIMEFRAMES. 1m used to be in this
    list and used to come back "TOO SMALL" every single run, which is what
    prompted removing it outright."""
    out = []
    cost = round_trip_cost_pct()
    for tf in timeframes:
        df, src = fetch_ohlcv_failover(symbol, tf, 500)
        if df is None or len(df) < 50:
            out.append({"timeframe": tf, "error": "no data"})
            continue
        atr_pct = float((calc_atr(df, CONFIG['ATR_PERIOD']) / df["close"] * 100).median())
        tp_pct = CONFIG['TP_ATR_MULT'] * atr_pct
        sl_pct = CONFIG['SL_ATR_MULT'] * atr_pct
        ratio = tp_pct / cost if cost > 0 else None
        # Breakeven win rate with gross TP, gross SL and round-trip cost c:
        #   p*(TP - c) = (1-p)*(SL + c)  ->  p = (SL + c) / (TP + SL)
        breakeven_wr = (sl_pct + cost) / (tp_pct + sl_pct) * 100 if (tp_pct + sl_pct) > 0 else None
        out.append({
            "timeframe": tf, "source": src,
            "median_atr_pct": round(atr_pct, 4),
            "gross_tp_pct": round(tp_pct, 4),
            "gross_sl_pct": round(sl_pct, 4),
            "round_trip_cost_pct": cost,
            "tp_to_cost_ratio": round(ratio, 2) if ratio else None,
            "breakeven_win_rate_pct": round(breakeven_wr, 1) if breakeven_wr else None,
            "verdict": ("TRADEABLE" if ratio and ratio >= CONFIG['MIN_TP_COST_RATIO']
                        else "TOO SMALL — fees eat the target"),
        })
    return {"symbol": symbol, "results": out}


# ══════════════════════════════════════════════════════════════════════════
# TUNING TOOLS
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
        nn = f.get("total_trades")
        verdict = "KEEP" if (pf is not None and pf >= 1.2) else "WEAK/DROP"
        print(f"  {f['label']:<45} trades={nn:<4} win_rate={wr:<6} pf={pf}  {verdict}")
        if pf is not None and pf >= 1.2:
            good_factors.append(f['label'])
        else:
            bad_factors.append(f['label'])

    print("\nSummary:")
    print("  Factors with real edge (pf>=1.2):", good_factors or "NONE")
    print("  Weak/noise factors:", bad_factors)
    return result


def step2_grid_search():
    """WARNING: this mutates the global CONFIG while it runs. Never call it in
    the same process as a live scanner — every analyze() during the sweep would
    be using whatever combination the loop happens to be on."""
    print("\n" + "=" * 70)
    print("STEP 2: Grid search — TP/SL multipliers, ADX_MIN, SCORE_THRESHOLD")
    print("=" * 70)

    tp_mults = [1.5, 2.0, 2.5, 3.0]
    sl_mults = [0.8, 1.0, 1.2, 1.5]
    adx_mins = [15, 18, 22, 25]
    score_thresholds = [4.0, 5.0, 6.0, 7.0]

    original_config = _copy.deepcopy(CONFIG)
    results = []

    total_runs = len(tp_mults) * len(sl_mults) * len(adx_mins) * len(score_thresholds)
    run_count = 0

    try:
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
    finally:
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

    print("\nREMINDER: this is an in-sample sweep over the most recent candles.")
    print("The top row is the combination that best fits noise you already have.")
    print("Re-run on a different window before believing any of it.")

    return results_sorted


def step3_apply_best(results_sorted):
    if not results_sorted:
        return
    best = results_sorted[0]
    print("\n" + "=" * 70)
    print("STEP 3: Best config found")
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
        print("The current signal factors do not have real edge on this")
        print("symbol/timeframe/window — tuning TP/SL alone will not fix it.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "cost":
        print("Cost reality check — run this FIRST:")
        import json as _json
        print(_json.dumps(cost_reality_check("BTC/USDT:USDT"), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "live":
        SYMBOL = "BTC/USDT:USDT"
        print(f"Live signal for {SYMBOL}:")
        sig = analyze(SYMBOL, timeframe="5m")
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
        sig = analyze_orderflow(SYMBOL, entry_timeframe="5m", structure_timeframe="15m")
        print(sig)
        print("\nHouse-money risk sizing example (10,000 USDT capital, 3x leverage):")
        ofrm = OrderFlowRiskManager(account_capital_usdt=10000)
        if sig.get("signal") in ("BUY", "SELL") and sig.get("sl") is not None:
            print(ofrm.position_size_orderflow(sig["entry"], sig["sl"], leverage=3))
        else:
            print("No active signal to size.")
        print("\nOrder-flow-proxy backtest (5m entry / 15m structure):")
        print(run_orderflow_backtest(SYMBOL, entry_timeframe="5m", structure_timeframe="15m"))
    else:
        factor_result = step1_factor_report()
        grid_results = step2_grid_search()
        step3_apply_best(grid_results)
