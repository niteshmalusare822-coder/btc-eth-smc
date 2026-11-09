# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-09 (Auto-Generated via collect.py)  
**Objective:** Measure the production SMC_MTF rules against a matched-random null, then improve only when the improvement survives out-of-sample testing, walk-forward validation, and sensitivity checks.

## Canonical Strategy / Execution Contract
- **Measured arm:** `SMC_MTF`
- **Matched null:** `MATCHED_RANDOM_vs_SMC_MTF`
- **Risk cap:** Rs.700 inclusive of fees and slippage
- **Backtest max cost gate:** 0.75R
- **1H bias / 15M setup / 5M trigger:** trigger is informational; 5M quality blocks only when explicitly enabled
- **Retest requirement:** False
- **Structure confirmation:** True
- **Entry model:** `limit_ote` at the canonical POI edge

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 594
- **Pooled Edge (INR):** 111.3
- **Standard Error:** 9.2
- **Sigma (Z-Score):** 12.15
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 13808.0
- **Pooled Profit Factor:** 1.1
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 31 | 48.4% | 1.07 | 37.9 | -370.0 | +407.9 | 1176.0 | 4/4 |
| ETH | 38 | 47.4% | 0.81 | -112.5 | -314.0 | +201.5 | -4276.0 | 4/4 |
| SOL | 36 | 50.0% | 1.83 | 110.4 | -66.9 | +177.3 | 3975.0 | 4/4 |
| XRP | 41 | 51.2% | 1.6 | 89.5 | -70.2 | +159.7 | 3669.0 | 3/4 |
| AVAX | 25 | 52.0% | 0.79 | -61.7 | -111.9 | +50.2 | -1542.0 | 3/4 |
| LINK | 38 | 31.6% | 0.43 | -141.8 | -127.3 | -14.5 | -5387.0 | 1/4 |
| DOGE | 32 | 50.0% | 1.05 | 8.4 | -115.0 | +123.4 | 269.0 | 4/4 |
| ADA | 37 | 45.9% | 1.1 | 19.2 | -80.2 | +99.4 | 709.0 | 3/4 |
| DEXE | 27 | 51.9% | 0.71 | -66.1 | -123.6 | +57.5 | -1784.0 | 4/4 |
| BANK | 37 | 67.6% | 3.91 | 234.4 | -52.9 | +287.3 | 8673.0 | 3/4 |
| BNB | 38 | 47.4% | 0.95 | -6.1 | -84.7 | +78.6 | -232.0 | 3/4 |
| SUI | 33 | 42.4% | 1.25 | 57.9 | -86.3 | +144.2 | 1910.0 | 4/4 |
| HBAR | 39 | 61.5% | 1.3 | 41.5 | -83.6 | +125.1 | 1619.0 | 4/4 |
| LTC | 33 | 48.5% | 1.03 | 5.5 | -83.4 | +88.9 | 182.0 | 4/4 |
| BCH | 33 | 60.6% | 1.71 | 124.4 | -92.4 | +216.8 | 4106.0 | 4/4 |
| DOT | 36 | 50.0% | 1.6 | 92.6 | -95.2 | +187.8 | 3334.0 | 4/4 |
| 1000PEPE | 40 | 42.5% | 0.8 | -64.8 | -99.2 | +34.4 | -2593.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
