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
- **Total Trades Pooled:** 229
- **Pooled Edge (INR):** 87.3
- **Standard Error:** 9.0
- **Sigma (Z-Score):** 9.69
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -4506.0
- **Pooled Profit Factor:** 0.91
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 6 | 33.3% | 0.29 | -775.2 | -166.2 | -609.0 | -4651.0 | 1/4 |
| ETH | 7 | 57.1% | 0.41 | -327.0 | -294.1 | -32.9 | -2289.0 | 3/4 |
| SOL | 16 | 37.5% | 0.41 | -120.8 | -107.2 | -13.6 | -1932.0 | 2/4 |
| XRP | 10 | 40.0% | 0.45 | -127.4 | -127.7 | +0.3 | -1274.0 | 3/4 |
| AVAX | 22 | 45.5% | 1.26 | 44.2 | -59.0 | +103.2 | 973.0 | 3/4 |
| LINK | 15 | 66.7% | 0.72 | -54.4 | -92.0 | +37.6 | -816.0 | 3/4 |
| DOGE | 10 | 60.0% | 0.8 | -21.3 | -124.8 | +103.5 | -213.0 | 4/4 |
| ADA | 14 | 71.4% | 1.35 | 33.2 | -48.9 | +82.1 | 465.0 | 3/4 |
| DEXE | 12 | 41.7% | 0.47 | -151.8 | -122.6 | -29.2 | -1822.0 | 2/4 |
| BANK | 16 | 62.5% | 2.98 | 183.6 | -133.2 | +316.8 | 2937.0 | 4/4 |
| BNB | 4 | 50.0% | 0.28 | -53.5 | -132.6 | +79.1 | -214.0 | 4/4 |
| SUI | 23 | 56.5% | 1.82 | 109.7 | -95.7 | +205.4 | 2524.0 | 4/4 |
| HBAR | 11 | 72.7% | 0.85 | -31.6 | -109.8 | +78.2 | -348.0 | 4/4 |
| LTC | 12 | 50.0% | 0.69 | -39.7 | -101.5 | +61.8 | -476.0 | 2/4 |
| BCH | 10 | 30.0% | 0.33 | -142.7 | -119.0 | -23.7 | -1427.0 | 3/4 |
| DOT | 23 | 56.5% | 1.33 | 117.3 | -107.2 | +224.5 | 2698.0 | 3/4 |
| 1000PEPE | 18 | 61.1% | 1.33 | 75.5 | -72.0 | +147.5 | 1359.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
