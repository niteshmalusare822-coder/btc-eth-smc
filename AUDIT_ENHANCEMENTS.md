# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-13 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 600
- **Pooled Edge (INR):** 96.2
- **Standard Error:** 9.4
- **Sigma (Z-Score):** 10.22
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 22612.0
- **Pooled Profit Factor:** 1.17
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 31 | 58.1% | 1.72 | 380.4 | -309.8 | +690.2 | 11792.0 | 4/4 |
| ETH | 44 | 50.0% | 1.13 | 71.4 | -266.0 | +337.4 | 3143.0 | 4/4 |
| SOL | 37 | 51.4% | 1.82 | 100.7 | -56.1 | +156.8 | 3727.0 | 4/4 |
| XRP | 39 | 43.6% | 1.48 | 72.2 | -50.0 | +122.2 | 2814.0 | 4/4 |
| AVAX | 23 | 47.8% | 0.61 | -143.1 | -148.3 | +5.2 | -3292.0 | 3/4 |
| LINK | 39 | 28.2% | 0.31 | -176.4 | -133.0 | -43.4 | -6880.0 | 2/4 |
| DOGE | 36 | 44.4% | 1.04 | 7.2 | -100.2 | +107.4 | 260.0 | 4/4 |
| ADA | 38 | 47.4% | 0.66 | -63.0 | -93.3 | +30.3 | -2393.0 | 3/4 |
| DEXE | 31 | 48.4% | 0.94 | -14.0 | -117.6 | +103.6 | -434.0 | 3/4 |
| BANK | 37 | 67.6% | 5.05 | 273.4 | -43.1 | +316.5 | 10116.0 | 3/4 |
| BNB | 36 | 61.1% | 1.43 | 38.8 | -72.8 | +111.6 | 1398.0 | 3/4 |
| SUI | 34 | 44.1% | 1.43 | 91.6 | -86.1 | +177.7 | 3114.0 | 4/4 |
| HBAR | 41 | 51.2% | 0.72 | -49.7 | -99.1 | +49.4 | -2036.0 | 3/4 |
| LTC | 31 | 54.8% | 0.91 | -14.5 | -88.2 | +73.7 | -449.0 | 4/4 |
| BCH | 36 | 58.3% | 2.14 | 155.8 | -62.2 | +218.0 | 5610.0 | 4/4 |
| DOT | 33 | 48.5% | 1.24 | 35.6 | -114.5 | +150.1 | 1176.0 | 4/4 |
| 1000PEPE | 34 | 44.1% | 0.57 | -148.6 | -143.8 | -4.8 | -5054.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
