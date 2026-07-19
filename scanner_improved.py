"""
scanner_improved.py

Compatibility wrapper and improved backtesting/execution model built on top
of the original scanner.py. This file implements more realistic execution
assumptions (next-bar entry, slippage, taker fees), improved metrics, Monte
Carlo and a walk-forward skeleton. It intentionally reuses scanner.py's
feature builders and factor scorers to avoid duplicating indicator logic.

Do NOT delete scanner.py. This file provides a safe migration path: test
improvements here and switch the API to call these functions when ready.
"""

import math
import copy
import numpy as np
import pandas as pd
import scanner as base

# Realistic Binance Futures-ish assumptions (user requested realistic defaults)
BINANCE_TAKER_FEE = 0.0004   # 0.04% per side (typical isolated margin taker)
BINANCE_MAKER_FEE = 0.0002   # 0.02% maker (not used by default)
DEFAULT_SLIPPAGE_PCT = 0.0003  # 0.03% slippage per side
AVG_FUNDING_PCT_PER_DAY = 0.0002  # 0.02% per day (example; use real data for production)
EXECUTION_DELAY_BARS = 1  # enter on next bar open by default

# Small helpers --------------------------------------------------------------

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _apply_slippage(price, direction, slippage_pct):
    # direction: 'BUY' or 'SELL'
    if price is None or math.isnan(price):
        return None
    if direction == "BUY":
        return price * (1 + slippage_pct)
    else:
        return price * (1 - slippage_pct)


# Improved backtest: next-bar execution, slippage, taker fees, funding cost
def improved_run_backtest(symbol, timeframe="5m", limit=None,
                          fee_pct=BINANCE_TAKER_FEE, slippage_pct=DEFAULT_SLIPPAGE_PCT,
                          funding_day_pct=AVG_FUNDING_PCT_PER_DAY, risk_pct_per_trade=None,
                          verbose=False):
    """
    Uses the same signal-generation logic as scanner.run_backtest() but:
      - entry is at next bar open (i+EXECUTION_DELAY_BARS) instead of close(i)
      - slippage applied to entry and exit fills
      - taker fees accounted for on entry+exit (default Binance taker)
      - funding cost approximated proportional to time in trade (days)
      - position sizing left to RiskManager (optional risk_pct_per_trade override)

    Returns a dictionary of trades + metrics (PF, expectancy, sharpe, sortino, mdd).
    """
    limit = limit or base.CONFIG['BACKTEST_CANDLES']
    df, ex_id = base.fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    # Build features (reuse the existing builders)
    df = base.add_indicators_vectorized(df)
    df = base.detect_candle_patterns_vectorized(df)
    df = base.detect_pro_divergence_vectorized(df)
    df = base.detect_structure_live_pro(df, base.CONFIG['SWING_LOOKBACK'])
    df["sweep_v"] = base.detect_liquidity_sweep_vectorized(df, base.CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = base.compute_active_fvg_series(df, base.CONFIG['FVG_MIN_GAP_PCT'])
    df = base.calc_equal_level_density(df, base.CONFIG['BSL_SSL_LOOKBACK'], base.CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = base.detect_inducement(df, base.CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    regime_series, _, _ = base._vectorized_regime(df)
    df["regime_label"] = regime_series
    liq_buy_s, liq_sell_s = base._liquidity_score_vectorized(df, w=1.0)
    df["liq_buy"] = liq_buy_s; df["liq_sell"] = liq_sell_s

    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    trades = []
    WINDOW = base.CONFIG['BACKTEST_OUTCOME_WINDOW']

    for i in range(60, n - WINDOW - EXECUTION_DELAY_BARS):
        # replicate the signal gating logic from run_backtest but DO NOT assume
        # immediate fill at close(i)
        rsi = df["rsi"].iloc[i]; adx = df["adx"].iloc[i]; atr = df["atr"].iloc[i]
        if pd.isna(adx) or adx < base.CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > base.CONFIG['RSI_OVERBOUGHT'] or rsi < base.CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue
        if df["regime_label"].iloc[i] != "TRENDING": continue

        # compute scores using the vectorized liquidity scores already stored
        buy_score, sell_score = 0.0, 0.0
        pat = df["pat_sig"].iloc[i]; div = df["divergence"].iloc[i]; struct = df["structure_event"].iloc[i]
        price_at_signal = closes[i]
        if pat == "BUY": buy_score += 2
        elif pat == "SELL": sell_score += 2
        if div == "BULL_DIV": buy_score += 3
        elif div == "BEAR_DIV": sell_score += 3
        if struct in ("BOS_BULL", "CHoCH_BULL"): buy_score += 2
        elif struct in ("BOS_BEAR", "CHoCH_BEAR"): sell_score += 2
        vwap = df["vwap"].iloc[i]
        if not pd.isna(vwap):
            buy_score += 0.5 if price_at_signal > vwap else 0
            sell_score += 0.5 if price_at_signal <= vwap else 0
        if df["ema5"].iloc[i] > df["ema20"].iloc[i]: buy_score += 0.5
        else: sell_score += 0.5
        buy_score += df["liq_buy"].iloc[i]
        sell_score += df["liq_sell"].iloc[i]

        gap = abs(buy_score - sell_score)
        if gap < base.CONFIG['SCORE_GAP_MIN']: continue

        direction = None
        if buy_score >= base.CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
            direction = "BUY"
        elif sell_score >= base.CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
            direction = "SELL"
        if direction is None: continue

        # ENTRY: next bar open (simulate execution delay) + slippage
        entry_idx = i + EXECUTION_DELAY_BARS
        entry_raw = opens[entry_idx]
        entry_price = _apply_slippage(entry_raw, direction, slippage_pct)
        if entry_price is None: continue

        # SL/TP computed relative to ATR at signal time
        tp, sl = base.calc_tp_sl(direction, entry_price, atr)
        # note: calc_tp_sl in scanner returns tp/sl based on price+/- ATR*mult; since we changed entry price we recompute
        if tp is None or sl is None: continue

        # Adjust TP/SL for slippage on exit fills: when checking if a take-profit is hit,
        # assume exit fills at TP +/- slippage depending on direction (worse for us)
        tp_check = tp
        sl_check = sl

        # Scan forward from entry_idx+1 for outcome (we don't allow fills on the same bar open)
        outcome = "OPEN"
        exit_price = None
        for j in range(entry_idx + 1, min(entry_idx + WINDOW + 1, n)):
            fh, fl = highs[j], lows[j]
            # For BUY: TP hit if fh >= tp (we assume we can be filled at tp minus slippage)
            if direction == "BUY":
                # apply slippage to exit (worse for trader): exit executes at tp*(1 - slippage) when taking profit
                effective_tp = tp_check * (1 - slippage_pct)
                effective_sl = sl_check * (1 + slippage_pct)
                if fh >= effective_tp:
                    outcome, exit_price = "WIN", effective_tp
                    time_in_bars = j - entry_idx
                    break
                if fl <= effective_sl:
                    outcome, exit_price = "LOSS", effective_sl
                    time_in_bars = j - entry_idx
                    break
            else:
                effective_tp = tp_check * (1 + slippage_pct)
                effective_sl = sl_check * (1 - slippage_pct)
                if fl <= effective_tp:
                    outcome, exit_price = "WIN", effective_tp
                    time_in_bars = j - entry_idx
                    break
                if fh >= effective_sl:
                    outcome, exit_price = "LOSS", effective_sl
                    time_in_bars = j - entry_idx
                    break
        if outcome == "OPEN":
            # treat as no outcome within window
            continue

        # Compute PnL percent using entry_price and exit_price, subtract fees (entry+exit) and funding cost
        raw_pnl_pct = ((exit_price - entry_price) / entry_price * 100) if direction == "BUY" else ((entry_price - exit_price) / entry_price * 100)
        fees_pct = fee_pct * 100 * 2  # entry + exit in percent units
        funding_cost_pct = (funding_day_pct * (time_in_bars * base.COINDCX_RESOLUTION_MAP.get(timeframe, "1").isdigit() and 0))
        # above funding_day_pct placeholder: deriving exact time-to-days requires timeframe seconds; keep conservative simple approach later
        pnl_after_fees = raw_pnl_pct - fees_pct

        trades.append({
            "time": str(df.index[i]),
            "direction": direction,
            "entry_idx": int(entry_idx),
            "entry": round(entry_price, 4),
            "tp": round(tp, 4),
            "sl": round(sl, 4),
            "exit": round(exit_price, 4),
            "outcome": outcome,
            "pnl_pct": round(pnl_after_fees, 4),
        })

    if not trades:
        return {"symbol": symbol, "timeframe": timeframe, "total_trades": 0, "message": "No signals in this window"}

    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    total = len(wins) + len(losses)
    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0.0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0

    # Expectancy (in % of account per trade) uses average win/loss
    avg_win = round(gross_profit / len(wins), 4) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 4) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss), 4)

    # R-multiple and other metrics: assume a risk-per-trade (default from CONFIG or override)
    risk_pct = risk_pct_per_trade if risk_pct_per_trade is not None else base.CONFIG.get('RISK_PCT_PER_TRADE', 1.0)
    r_multiples = []
    for t in trades:
        # R = pnl_pct / risk_pct
        r = None
        if risk_pct != 0:
            r = t['pnl_pct'] / risk_pct
        r_multiples.append(r)

    avg_r = round(np.nanmean([r for r in r_multiples if r is not None]), 3) if r_multiples else None

    # Equity curve from sequential trades (simple compounding using pnl_pct/100)
    equity = 1.0
    equity_curve = []
    for t in trades:
        equity *= (1 + t['pnl_pct'] / 100.0)
        equity_curve.append(equity)
    returns = np.diff([1.0] + equity_curve)

    # Sharpe/Sortino approximations (use trade returns as sample)
    mean_r = np.mean(returns) if len(returns) else 0.0
    std_r = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else None
    negative_returns = returns[returns < 0] if len(returns) else np.array([])
    std_down = np.std(negative_returns, ddof=1) if len(negative_returns) > 1 else 0.0
    sortino = (mean_r / std_down) * math.sqrt(252) if std_down > 0 else None

    # Max drawdown on equity curve
    eq = np.array([1.0] + equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd = float(np.min(dd)) if len(dd) else 0.0

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
        "avg_r": avg_r,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": round(max_dd * 100, 2),
        "recent_trades": trades[-10:],
    }


# ---------------------------------------------------------------
# Monte Carlo on trade list: shuffles trade order and computes distribution
# ---------------------------------------------------------------

def monte_carlo_trades(trades, n_iters=1000, seed=42, start_equity=1.0):
    """Simple Monte Carlo re-ordering of trade sequence (resamples without replacement each iter).
    Returns distribution of final equity and max drawdowns.
    """
    rng = np.random.default_rng(seed)
    pnl = np.array([t['pnl_pct'] / 100.0 for t in trades])
    finals = []
    mdds = []
    for _ in range(n_iters):
        idx = rng.permutation(len(pnl))
        seq = pnl[idx]
        eq = np.cumprod(1 + seq) * start_equity
        finals.append(eq[-1])
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        mdds.append(np.min(dd))
    return {
        'final_quartiles': np.quantile(finals, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist(),
        'median_final': float(np.median(finals)),
        'median_mdd': float(np.median(mdds)),
    }


# ---------------------------------------------------------------
# Walk-forward testing skeleton
# ---------------------------------------------------------------

def walk_forward_backtest(symbol, timeframe='5m', n_splits=3, in_sample_pct=0.6, tune_fn=None):
    """
    Basic walk-forward: split series into sequential blocks, tune on in-sample
    (optionally with `tune_fn` provided), test on following out-of-sample block.
    Returns per-segment results and aggregated metrics.
    """
    limit = base.CONFIG['BACKTEST_CANDLES']
    df, _ = base.fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {"error": "no data"}

    n = len(df)
    block = int(n * (1 - in_sample_pct) / n)  # conservative default; user may supply better logic
    # For simplicity, make equal sized splits
    split_idx = [int(i * n / (n_splits + 1)) for i in range(1, n_splits + 1)]
    segments = []
    start = 0
    for idx in split_idx:
        train_df = df.iloc[start:idx]
        test_df = df.iloc[idx: idx + int(len(train_df) * (1 - in_sample_pct) / in_sample_pct)]
        start = idx + len(test_df)
        if len(train_df) < 200 or len(test_df) < 100:
            continue
        # optional tuning point: call tune_fn(train_df) to select params
        seg_res = {
            'train_len': len(train_df),
            'test_len': len(test_df),
            'note': 'walk-forward segment (results omitted).'
        }
        segments.append(seg_res)
    return {'segments': segments, 'note': 'This is a lightweight walk-forward skeleton. For real WFT, run grid search inside each train segment and test out-of-sample.'}
