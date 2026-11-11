# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-11 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 588
- **Pooled Edge (INR):** 115.8
- **Standard Error:** 9.4
- **Sigma (Z-Score):** 12.32
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 21678.0
- **Pooled Profit Factor:** 1.16
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 31 | 51.6% | 1.22 | 122.8 | -347.6 | +470.4 | 3807.0 | 4/4 |
| ETH | 41 | 48.8% | 1.01 | 8.4 | -279.2 | +287.6 | 343.0 | 3/4 |
| SOL | 36 | 52.8% | 1.87 | 113.6 | -59.6 | +173.2 | 4091.0 | 4/4 |
| XRP | 38 | 42.1% | 1.24 | 41.8 | -70.6 | +112.4 | 1587.0 | 4/4 |
| AVAX | 25 | 52.0% | 0.8 | -61.2 | -120.6 | +59.4 | -1530.0 | 3/4 |
| LINK | 40 | 35.0% | 0.43 | -137.6 | -122.0 | -15.6 | -5503.0 | 3/4 |
| DOGE | 34 | 47.1% | 1.26 | 42.1 | -119.7 | +161.8 | 1430.0 | 4/4 |
| ADA | 38 | 42.1% | 0.95 | -9.8 | -95.8 | +86.0 | -373.0 | 3/4 |
| DEXE | 31 | 51.6% | 0.72 | -59.9 | -140.2 | +80.3 | -1858.0 | 4/4 |
| BANK | 35 | 71.4% | 6.48 | 321.9 | -42.5 | +364.4 | 11266.0 | 3/4 |
| BNB | 35 | 51.4% | 1.16 | 17.6 | -73.0 | +90.6 | 615.0 | 4/4 |
| SUI | 34 | 38.2% | 1.15 | 37.5 | -84.3 | +121.8 | 1274.0 | 3/4 |
| HBAR | 39 | 59.0% | 1.11 | 17.4 | -86.9 | +104.3 | 677.0 | 4/4 |
| LTC | 30 | 50.0% | 1.03 | 5.0 | -99.3 | +104.3 | 150.0 | 2/4 |
| BCH | 32 | 59.4% | 1.81 | 123.8 | -85.8 | +209.6 | 3962.0 | 4/4 |
| DOT | 33 | 48.5% | 1.52 | 90.2 | -107.5 | +197.7 | 2976.0 | 4/4 |
| 1000PEPE | 36 | 50.0% | 0.89 | -34.3 | -107.7 | +73.4 | -1236.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
