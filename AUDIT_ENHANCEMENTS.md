# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-22 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 228
- **Pooled Edge (INR):** 29.4
- **Standard Error:** 9.8
- **Sigma (Z-Score):** 3.0
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -20375.0
- **Pooled Profit Factor:** 0.7
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 27 | 33.3% | 0.64 | -171.7 | -425.9 | +254.2 | -4636.0 | 4/4 |
| ETH | 35 | 45.7% | 0.71 | -140.2 | -388.2 | +248.0 | -4906.0 | 3/4 |
| SOL | 10 | 40.0% | 0.25 | -160.2 | -66.8 | -93.4 | -1602.0 | 1/4 |
| XRP | 9 | 33.3% | 0.25 | -240.2 | -143.4 | -96.8 | -2162.0 | 0/3 |
| AVAX | 13 | 53.8% | 0.72 | -74.1 | -89.1 | +15.0 | -963.0 | 3/4 |
| LINK | 13 | 61.5% | 0.83 | -28.2 | -68.9 | +40.7 | -367.0 | 4/4 |
| DOGE | 7 | 42.9% | 0.41 | -153.9 | -112.8 | -41.1 | -1077.0 | 2/4 |
| ADA | 14 | 78.6% | 1.76 | 71.4 | -44.5 | +115.9 | 999.0 | 3/4 |
| DEXE | 2 | 50.0% | 1.0 | -1.0 | -146.3 | +145.3 | -2.0 | 2/4 |
| BANK | 10 | 60.0% | 1.77 | 138.6 | -135.2 | +273.8 | 1386.0 | 3/4 |
| BNB | 3 | 66.7% | 0.3 | -66.7 | -141.5 | +74.8 | -200.0 | 2/3 |
| SUI | 16 | 50.0% | 0.97 | -5.9 | -114.6 | +108.7 | -94.0 | 3/4 |
| HBAR | 11 | 63.6% | 0.73 | -59.4 | -110.5 | +51.1 | -653.0 | 2/4 |
| LTC | 8 | 62.5% | 0.34 | -125.5 | -64.3 | -61.2 | -1004.0 | 0/4 |
| BCH | 9 | 22.2% | 0.17 | -180.1 | -102.1 | -78.0 | -1621.0 | 2/4 |
| DOT | 19 | 42.1% | 0.82 | -71.6 | -124.3 | +52.7 | -1361.0 | 2/4 |
| 1000PEPE | 22 | 45.5% | 0.65 | -96.0 | -116.1 | +20.1 | -2112.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
