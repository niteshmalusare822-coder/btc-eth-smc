"""
TUNING SCRIPT — finds a config that actually has positive edge.
================================================================
Run this AFTER placing scalping_liquidity_bot.py in the same folder.

What it does, in order:
  1. Runs run_factor_backtest() to show which individual factors
     (sweep, structure, divergence, pattern, EMA, FVG, inducement)
     have real edge on their own — vs which are just noise.
  2. Grid-searches TP/SL multiplier + ADX_MIN + SCORE_THRESHOLD
     combinations using run_backtest_full(), ranks them by
     profit_factor, and prints the top results.
  3. Prints the winning CONFIG values you should paste into
     scalping_liquidity_bot.py's CONFIG dict.

Usage:
    python3 tune_strategy.py
"""

import copy
import scalping_liquidity_bot as bot


SYMBOL = "BTC/USDT:USDT"   # change if needed
ENTRY_TF = "5m"            # scalping entry timeframe to tune on


def step1_factor_report():
    print("=" * 70)
    print(f"STEP 1: Factor isolation report — {SYMBOL} ({ENTRY_TF})")
    print("=" * 70)
    result = bot.run_factor_backtest(SYMBOL, timeframe=ENTRY_TF)
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
        verdict = "✅ KEEP" if (pf is not None and pf >= 1.2) else "❌ WEAK/DROP"
        print(f"  {f['label']:<45} trades={n:<4} win_rate={wr:<6} pf={pf}  {verdict}")
        if pf is not None and pf >= 1.2:
            good_factors.append(f['label'])
        else:
            bad_factors.append(f['label'])

    print("\nSummary:")
    print("  Factors with real edge (pf>=1.2):", good_factors or "NONE — none of the single factors have edge alone")
    print("  Weak/noise factors (consider dropping or down-weighting):", bad_factors)
    return result


def step2_grid_search():
    print("\n" + "=" * 70)
    print(f"STEP 2: Grid search — TP/SL multipliers, ADX_MIN, SCORE_THRESHOLD")
    print("=" * 70)

    # Search space — tweak ranges here if you want a wider/narrower search
    tp_mults = [1.5, 2.0, 2.5, 3.0]
    sl_mults = [0.8, 1.0, 1.2, 1.5]
    adx_mins = [15, 18, 22, 25]
    score_thresholds = [4.0, 5.0, 6.0, 7.0]

    original_config = copy.deepcopy(bot.CONFIG)
    results = []

    total_runs = len(tp_mults) * len(sl_mults) * len(adx_mins) * len(score_thresholds)
    run_count = 0

    for tp in tp_mults:
        for sl in sl_mults:
            for adx in adx_mins:
                for thresh in score_thresholds:
                    run_count += 1
                    bot.CONFIG['TP_ATR_MULT'] = tp
                    bot.CONFIG['SL_ATR_MULT'] = sl
                    bot.CONFIG['ADX_MIN'] = adx
                    bot.CONFIG['SCORE_THRESHOLD'] = thresh
                    # keep gap proportional to threshold so it stays meaningful
                    bot.CONFIG['SCORE_GAP_MIN'] = round(thresh * 0.6, 1)

                    res = bot.run_backtest(SYMBOL, timeframe=ENTRY_TF)

                    if res.get("total_trades", 0) < 8:
                        continue  # skip configs with too few trades to trust

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

    # restore original config
    bot.CONFIG.clear()
    bot.CONFIG.update(original_config)

    if not results:
        print("\nNo config produced >=8 trades. Market window might be too quiet/choppy —")
        print("try a different symbol, longer BACKTEST_CANDLES, or lower the min-trade filter.")
        return []

    # Rank: profit_factor first, then expectancy
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
    print("STEP 3: Best config found — paste this into CONFIG in scalping_liquidity_bot.py")
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
        print("\n⚠️  Even the best combo found here is weak (pf < 1.2).")
        print("   That means the CURRENT signal factors (sweep/FVG/structure/etc.)")
        print("   don't have real edge on this symbol/timeframe/window — tuning TP/SL")
        print("   alone won't fix it. You'd need to change WHICH factors are used")
        print("   (see Step 1 output), test other symbols, or accept this approach")
        print("   isn't ready for live capital yet.")


if __name__ == "__main__":
    factor_result = step1_factor_report()
    grid_results = step2_grid_search()
    step3_apply_best(grid_results)
