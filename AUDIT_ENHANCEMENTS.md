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
- **Total Trades Pooled:** 609
- **Pooled Edge (INR):** 88.5
- **Standard Error:** 8.5
- **Sigma (Z-Score):** 10.47
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 15190.0
- **Pooled Profit Factor:** 1.11
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 32 | 59.4% | 1.8 | 395.9 | -295.6 | +691.5 | 12670.0 | 4/4 |
| ETH | 43 | 48.8% | 1.13 | 72.5 | -285.9 | +358.4 | 3118.0 | 4/4 |
| SOL | 37 | 51.4% | 1.68 | 82.9 | -69.8 | +152.7 | 3068.0 | 4/4 |
| XRP | 39 | 43.6% | 1.29 | 44.6 | -64.7 | +109.3 | 1739.0 | 3/4 |
| AVAX | 24 | 45.8% | 0.47 | -196.4 | -142.7 | -53.7 | -4714.0 | 3/4 |
| LINK | 40 | 30.0% | 0.42 | -142.1 | -134.3 | -7.8 | -5683.0 | 3/4 |
| DOGE | 37 | 45.9% | 0.97 | -4.3 | -109.5 | +105.2 | -158.0 | 4/4 |
| ADA | 39 | 48.7% | 0.71 | -52.2 | -89.9 | +37.7 | -2034.0 | 3/4 |
| DEXE | 32 | 46.9% | 0.88 | -31.1 | -124.1 | +93.0 | -996.0 | 3/4 |
| BANK | 37 | 64.9% | 4.47 | 247.4 | -44.0 | +291.4 | 9155.0 | 3/4 |
| BNB | 37 | 59.5% | 1.16 | 16.6 | -89.5 | +106.1 | 616.0 | 3/4 |
| SUI | 34 | 44.1% | 1.16 | 34.9 | -82.5 | +117.4 | 1187.0 | 4/4 |
| HBAR | 43 | 48.8% | 0.71 | -52.3 | -99.9 | +47.6 | -2249.0 | 4/4 |
| LTC | 30 | 53.3% | 0.82 | -31.1 | -99.7 | +68.6 | -934.0 | 4/4 |
| BCH | 36 | 55.6% | 1.34 | 61.6 | -55.6 | +117.2 | 2219.0 | 4/4 |
| DOT | 36 | 44.4% | 1.09 | 15.5 | -121.7 | +137.2 | 558.0 | 3/4 |
| 1000PEPE | 33 | 48.5% | 0.75 | -71.9 | -114.7 | +42.8 | -2372.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
