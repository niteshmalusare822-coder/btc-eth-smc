"""
scanner_fixed.py

Realistic backtesting wrapper that reuses scanner.py feature builders and
signal logic but enforces:
 - No look-ahead: entries at next completed candle open
 - Slippage and taker fees applied to entry/exit
 - Funding cost approximated per day held
 - Position sizing via RiskManager (uses CONFIG['RISK_PCT_PER_TRADE'])
 - PnL reported as USD and percent-of-account; metrics returned include
   Profit Factor, Expectancy, Average R, Max Drawdown, Sharpe, Win Rate, Total Trades

This file is intentionally conservative: it uses scanner.py indicators and
scoring so strategy logic is unchanged; only execution/PNL modeling is fixed.
"""

import math
import numpy as np
import pandas as pd
import scanner as base

# Defaults (Binance Futures-like realistic defaults)
DEFAULT_TAKER_FEE = 0.0004       # 0.04% per side
DEFAULT_MAKER_FEE = 0.0002       # 0.02%
DEFAULT_SLIPPAGE = 0.0003        # 0.03% per fill (adverse)
DEFAULT_FUNDING_DAILY = 0.0003   # 0.03% per day (conservative placeholder)
EXECUTION_DELAY_BARS = 1         # enter on next bar open

TF_SECONDS = {
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '1h': 3600,
    '4h': 14400,
    '1d': 86400,
}


def _seconds_for_timeframe(tf):
    return TF_SECONDS.get(tf, 60)


def _apply_slippage(price, direction, slippage):
    if price is None or (isinstance(price, float) and math.isnan(price)):
        return None
    if direction == 'BUY':
        return price * (1 + slippage)
    return price * (1 - slippage)


def improved_run_backtest(symbol, timeframe='5m', limit=None,
                          capital_usdt=10000.0, fee_taker=DEFAULT_TAKER_FEE,
                          slippage=DEFAULT_SLIPPAGE, funding_daily=DEFAULT_FUNDING_DAILY,
                          leverage=None, execution_delay_bars=EXECUTION_DELAY_BARS):
    """
    Realistic backtest wrapper around the existing strategy logic.
    - Signals computed with completed candles only.
    - Entry at next candle open (execution_delay_bars).
    - Slippage and taker fees applied to entry and exit.
    - Funding cost approximated by days held * funding_daily * notional.
    - Position sizing via RiskManager.position_size (uses CONFIG['RISK_PCT_PER_TRADE']).

    Returns: dict with trades and metrics: profit_factor, expectancy, avg_R, max_drawdown,
    sharpe, win_rate, total_trades, recent_trades
    """
    limit = limit or base.CONFIG.get('BACKTEST_CANDLES', 6000)
    df, ex_id = base.fetch_ohlcv_failover(symbol, timeframe, limit)
    if df is None:
        return {'error': 'no data'}

    # Build feature set using existing helpers (no change to indicators)
    df = base.add_indicators_vectorized(df)
    df = base.detect_candle_patterns_vectorized(df)
    df = base.detect_pro_divergence_vectorized(df)
    df = base.detect_structure_live_pro(df, base.CONFIG['SWING_LOOKBACK'])
    df['sweep_v'] = base.detect_liquidity_sweep_vectorized(df, base.CONFIG['LIQUIDITY_SWEEP_LOOKBACK'])
    df = base.compute_active_fvg_series(df, base.CONFIG['FVG_MIN_GAP_PCT'])
    df = base.calc_equal_level_density(df, base.CONFIG['BSL_SSL_LOOKBACK'], base.CONFIG['EQUAL_LEVEL_TOLERANCE_PCT'])
    df = base.detect_inducement(df, base.CONFIG['INDUCEMENT_MINOR_LOOKBACK'])
    regime_series, _, _ = base._vectorized_regime(df)
    df['regime_label'] = regime_series
    liq_b, liq_s = base._liquidity_score_vectorized(df, w=1.0)
    df['liq_buy'] = liq_b; df['liq_sell'] = liq_s

    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    WINDOW = base.CONFIG.get('BACKTEST_OUTCOME_WINDOW', 20)

    # Risk manager for sizing
    rm = base.RiskManager(account_capital_usdt=capital_usdt)
    # allow overriding leverage param; fallback to CONFIG
    leverage = min(leverage if leverage is not None else base.CONFIG.get('MAX_LEVERAGE', 5), base.CONFIG.get('MAX_LEVERAGE', 5))

    trades = []

    # Loop through potential signal times, using only data up to i
    for i in range(60, n - WINDOW - execution_delay_bars):
        # read indicators at time i (completed candle)
        adx = df['adx'].iloc[i]; rsi = df['rsi'].iloc[i]; atr = df['atr'].iloc[i]
        if pd.isna(adx) or adx < base.CONFIG['ADX_MIN']: continue
        if pd.isna(rsi): continue
        if rsi > base.CONFIG['RSI_OVERBOUGHT'] or rsi < base.CONFIG['RSI_OVERSOLD']: continue
        if pd.isna(atr): continue
        if df['regime_label'].iloc[i] != 'TRENDING': continue

        # compute scores same as run_backtest to preserve strategy logic
        buy_score, sell_score = 0.0, 0.0
        pat = df['pat_sig'].iloc[i]; div = df['divergence'].iloc[i]; struct = df['structure_event'].iloc[i]
        price_at_signal = closes[i]
        if pat == 'BUY': buy_score += 2
        elif pat == 'SELL': sell_score += 2
        if div == 'BULL_DIV': buy_score += 3
        elif div == 'BEAR_DIV': sell_score += 3
        if struct in ('BOS_BULL', 'CHoCH_BULL'): buy_score += 2
        elif struct in ('BOS_BEAR', 'CHoCH_BEAR'): sell_score += 2
        if 'vp_poc' in df.columns:
            poc = df['vp_poc'].iloc[i]
        if not pd.isna(poc):
            buy_score += 0.5 if price_at_signal > poc else 0
            sell_score += 0.5 if price_at_signal <= poc else 0
        if not pd.isna(df['vwap'].iloc[i]):
            buy_score += 0.5 if price_at_signal > df['vwap'].iloc[i] else 0
            sell_score += 0.5 if price_at_signal <= df['vwap'].iloc[i] else 0
        if df['ema5'].iloc[i] > df['ema20'].iloc[i]: buy_score += 0.5
        else: sell_score += 0.5
        buy_score += df['liq_buy'].iloc[i]
        sell_score += df['liq_sell'].iloc[i]

        # acceleration boost kept
        if 'volume' in df.columns and not pd.isna(df['vwap'].iloc[i]):
            if price_at_signal > df['vwap'].iloc[i] and df['ema5'].iloc[i] > df['ema20'].iloc[i]:
                buy_score += 1.0
            elif price_at_signal <= df['vwap'].iloc[i] and df['ema5'].iloc[i] <= df['ema20'].iloc[i]:
                sell_score += 1.0

        # scoring gate
        gap = abs(buy_score - sell_score)
        if gap < base.CONFIG['SCORE_GAP_MIN']: continue
        direction = None
        if buy_score >= base.CONFIG['SCORE_THRESHOLD'] and buy_score > sell_score:
            direction = 'BUY'
        elif sell_score >= base.CONFIG['SCORE_THRESHOLD'] and sell_score > buy_score:
            direction = 'SELL'
        if direction is None: continue

        # ENTRY: next completed candle's open (execution delay)
        entry_idx = i + execution_delay_bars
        entry_raw = opens[entry_idx]
        entry_price = _apply_slippage(entry_raw, direction, slippage)
        if entry_price is None: continue

        # compute TP/SL around entry price using ATR at signal
        tp, sl = base.calc_tp_sl(direction, entry_price, atr)
        if tp is None or sl is None: continue

        # position sizing (risk in USD using RiskManager). Use RiskManager.position_size
        sizing = rm.position_size(entry_price, sl, leverage=leverage)
        if 'error' in sizing:
            continue
        qty = sizing['qty']
        notional = sizing['notional_usdt']
        margin_required = sizing['margin_required_usdt']
        # skip trade if margin > capital (can't open)
        if margin_required > capital_usdt:
            continue

        # proto-scan for outcome from entry_idx+1 to entry_idx+WINDOW (we disallow fills on open bar itself)
        outcome = 'OPEN'; exit_price = None; time_in_bars = 0
        for j in range(entry_idx + 1, min(entry_idx + WINDOW + 1, n)):
            time_in_bars = j - entry_idx
            fh = highs[j]; fl = lows[j]
            if direction == 'BUY':
                eff_tp = tp * (1 - slippage)
                eff_sl = sl * (1 + slippage)
                if fh >= eff_tp:
                    outcome, exit_price = 'WIN', eff_tp; break
                if fl <= eff_sl:
                    outcome, exit_price = 'LOSS', eff_sl; break
            else:
                eff_tp = tp * (1 + slippage)
                eff_sl = sl * (1 - slippage)
                if fl <= eff_tp:
                    outcome, exit_price = 'WIN', eff_tp; break
                if fh >= eff_sl:
                    outcome, exit_price = 'LOSS', eff_sl; break
        if outcome == 'OPEN':
            continue

        # compute PnL in USDT
        if direction == 'BUY':
            pnl_usdt = (exit_price - entry_price) * qty
        else:
            pnl_usdt = (entry_price - exit_price) * qty

        # fees: taker at entry + taker at exit applied on notional
        fee_usdt = notional * fee_taker * 2.0
        # funding cost approx: notional * funding_daily * days_held
        seconds = _seconds_for_timeframe(timeframe)
        days_held = (time_in_bars * seconds) / 86400.0 if time_in_bars > 0 else 0.0
        funding_usdt = notional * funding_daily * days_held

        pnl_after_costs = pnl_usdt - fee_usdt - funding_usdt
        pnl_pct_of_account = (pnl_after_costs / capital_usdt) * 100.0

        trades.append({
            'time': str(df.index[i]),
            'direction': direction,
            'entry_idx': int(entry_idx),
            'entry_price': round(entry_price, 6),
            'exit_price': round(exit_price, 6),
            'tp': round(tp, 6),
            'sl': round(sl, 6),
            'qty': qty,
            'notional_usdt': round(notional, 2),
            'margin_required_usdt': round(margin_required, 2),
            'outcome': outcome,
            'pnl_usdt': round(pnl_after_costs, 4),
            'pnl_pct_of_account': round(pnl_pct_of_account, 4),
            'time_in_bars': time_in_bars,
            'fees_usdt': round(fee_usdt, 6),
            'funding_usdt': round(funding_usdt, 6),
        })

    # If no trades
    if not trades:
        return {'symbol': symbol, 'timeframe': timeframe, 'total_trades': 0, 'message': 'No signals in this window'}

    wins = [t for t in trades if t['outcome'] == 'WIN']
    losses = [t for t in trades if t['outcome'] == 'LOSS']
    total = len(trades)
    win_rate = round(len(wins) / total * 100.0, 2)
    gross_profit = sum(max(0, t['pnl_usdt']) for t in trades)
    gross_loss = abs(sum(min(0, t['pnl_usdt']) for t in trades))
    profit_factor = round((gross_profit / gross_loss) if gross_loss > 0 else None, 4)

    # Expectancy in % of account per trade
    expectancy = round(np.mean([t['pnl_pct_of_account'] for t in trades]), 4)

    # Average R multiple: pnl_usdt / risk_amount_usdt
    risk_pct = base.CONFIG.get('RISK_PCT_PER_TRADE', 1.0)
    risk_amount = capital_usdt * (risk_pct / 100.0)
    r_list = [(t['pnl_usdt'] / risk_amount) if risk_amount > 0 else None for t in trades]
    avg_R = round(np.nanmean([r for r in r_list if r is not None]), 4) if r_list else None

    # equity curve compound
    equity = capital_usdt
    equity_curve = [equity]
    for t in trades:
        equity += t['pnl_usdt']
        equity_curve.append(equity)
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_drawdown_pct = float(np.min(dd)) * 100.0

    # Sharpe/Sortino on trade returns (per-trade returns using pnl / capital)
    returns = np.array([t['pnl_usdt'] / capital_usdt for t in trades])
    mean_r = returns.mean()
    std_r = returns.std(ddof=1) if len(returns) > 1 else 0.0
    sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else None
    neg = returns[returns < 0]
    std_down = neg.std(ddof=1) if len(neg) > 1 else 0.0
    sortino = (mean_r / std_down * math.sqrt(252)) if std_down > 0 else None

    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'total_trades': total,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'expectancy_pct_of_account': expectancy,
        'avg_R': avg_R,
        'sharpe': sharpe,
        'sortino': sortino,
        'max_drawdown_pct': round(max_drawdown_pct, 4),
        'recent_trades': trades[-10:],
    }
