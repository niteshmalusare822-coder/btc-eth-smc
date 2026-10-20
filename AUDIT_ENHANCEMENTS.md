# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-20 (Auto-Generated via collect.py)  
**Objective:** Measure the production SMC_MTF rules against a matched-random null, then improve only when the improvement survives out-of-sample testing, walk-forward validation, and sensitivity checks.

## Canonical Strategy / Execution Contract
- **Measured arm:** `SMC_MTF`
- **Matched null:** `MATCHED_RANDOM_vs_SMC_MTF`
- **Risk cap:** Rs.700 inclusive of fees and slippage
- **Backtest max cost gate:** 0.75R
- **1H bias / 15M setup / 5M trigger:** trigger is informational; 5M quality blocks only when explicitly enabled
- **Retest requirement:** False
- **Structure confirmation:** False
- **Entry model:** `limit_ote` at the canonical POI edge

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 237
- **Pooled Edge (INR):** 102.7
- **Standard Error:** 9.1
- **Sigma (Z-Score):** 11.3
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -4381.0
- **Pooled Profit Factor:** 0.92
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 7 | 42.9% | 0.32 | -644.0 | -162.5 | -481.5 | -4508.0 | 1/4 |
| ETH | 8 | 50.0% | 0.21 | -743.0 | -276.6 | -466.4 | -5944.0 | 3/4 |
| SOL | 16 | 43.8% | 0.44 | -114.8 | -107.2 | -7.6 | -1837.0 | 2/4 |
| XRP | 11 | 45.5% | 0.51 | -103.5 | -113.4 | +9.9 | -1138.0 | 3/4 |
| AVAX | 21 | 47.6% | 1.07 | 15.5 | -58.6 | +74.1 | 326.0 | 3/4 |
| LINK | 14 | 71.4% | 1.34 | 48.6 | -87.8 | +136.4 | 680.0 | 4/4 |
| DOGE | 10 | 60.0% | 0.8 | -21.3 | -124.8 | +103.5 | -213.0 | 4/4 |
| ADA | 16 | 68.8% | 1.45 | 35.6 | -54.8 | +90.4 | 570.0 | 3/4 |
| DEXE | 13 | 38.5% | 0.34 | -237.1 | -112.7 | -124.4 | -3082.0 | 2/4 |
| BANK | 16 | 62.5% | 2.98 | 183.6 | -133.2 | +316.8 | 2937.0 | 4/4 |
| BNB | 4 | 75.0% | 4.88 | 47.5 | -132.6 | +180.1 | 190.0 | 4/4 |
| SUI | 24 | 58.3% | 2.06 | 136.0 | -99.6 | +235.6 | 3263.0 | 4/4 |
| HBAR | 12 | 75.0% | 0.87 | -25.8 | -113.9 | +88.1 | -309.0 | 3/4 |
| LTC | 12 | 50.0% | 0.69 | -39.7 | -101.5 | +61.8 | -476.0 | 2/4 |
| BCH | 11 | 36.4% | 0.52 | -92.9 | -120.2 | +27.3 | -1022.0 | 4/4 |
| DOT | 23 | 60.9% | 1.53 | 171.0 | -98.3 | +269.3 | 3932.0 | 3/4 |
| 1000PEPE | 19 | 63.2% | 1.55 | 118.4 | -82.3 | +200.7 | 2250.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
