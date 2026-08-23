"""Research-only loader. Bybit for backtests, CoinDCX stays live.

CoinDCX serves clean 5m history for exactly four symbols; the other 21 tested
carried 3 gap warnings each, with holes up to 20 days on the 1h frame. Bar
counters (max_age, sweep_window, confirm_max_wait) count BARS, not time, so a
gap silently stretches a 15-hour setup into weeks. Bybit returned 25 of 25
clean over the same window.

This file does NOT touch data.load_mtf. Live signals still come from CoinDCX
through the unchanged path in app.py.
"""
import data as D

VENUE = "bybit"


def load_research(symbol, bars_5m):
    need = D.required_bars(bars_5m)
    frames, metas = {}, {}
    for tf in ("5m", "15m", "1h"):
        df, meta = D.fetch_ohlcv_history(VENUE, symbol, tf, need[tf])
        if df is None or len(df) < 300:
            return None, {"error": f"{symbol} {tf}: {meta.get('error', 'too few bars')}"}
        df, dropped = D.drop_forming(df, tf)
        meta["forming_candle_dropped"] = dropped
        meta["actual_bars"] = len(df)
        frames[tf], metas[tf] = df, meta
    return D._finish(symbol=symbol, frames=frames, metas=metas, source=VENUE,
                     need=need, mixed=False, warnings=[],
                     requested_evaluation_bars=D.clamp_bars(bars_5m))
