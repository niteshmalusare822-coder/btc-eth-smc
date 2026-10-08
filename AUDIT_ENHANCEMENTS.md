# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-08 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 305
- **Pooled Edge (INR):** 85.1
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 10.14
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -2975.0
- **Pooled Profit Factor:** 0.95
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 5 | 80.0% | 5.94 | 375.6 | -60.0 | +435.6 | 1878.0 | 3/4 |
| ETH | 10 | 60.0% | 0.27 | -639.7 | -434.0 | -205.7 | -6397.0 | 1/4 |
| SOL | 13 | 61.5% | 0.73 | -69.4 | -69.8 | +0.4 | -902.0 | 3/4 |
| XRP | 13 | 30.8% | 0.33 | -162.3 | -76.6 | -85.7 | -2110.0 | 1/4 |
| AVAX | 28 | 53.6% | 1.39 | 48.7 | -105.5 | +154.2 | 1364.0 | 4/4 |
| LINK | 20 | 75.0% | 7.96 | 351.4 | -88.7 | +440.1 | 7028.0 | 4/4 |
| DOGE | 17 | 58.8% | 1.81 | 120.1 | -76.4 | +196.5 | 2041.0 | 3/4 |
| ADA | 23 | 43.5% | 0.66 | -79.4 | -130.6 | +51.2 | -1826.0 | 3/4 |
| DEXE | 12 | 66.7% | 2.31 | 104.7 | -82.7 | +187.4 | 1256.0 | 4/4 |
| BANK | 18 | 38.9% | 1.2 | 22.9 | -126.5 | +149.4 | 412.0 | 2/4 |
| BNB | 4 | 50.0% | 6.55 | 215.0 | -112.2 | +327.2 | 860.0 | 4/4 |
| SUI | 26 | 46.2% | 1.2 | 24.3 | -80.8 | +105.1 | 632.0 | 4/4 |
| HBAR | 18 | 55.6% | 2.19 | 103.3 | -126.1 | +229.4 | 1860.0 | 4/4 |
| LTC | 22 | 27.3% | 0.28 | -233.2 | -129.9 | -103.3 | -5131.0 | 3/4 |
| BCH | 21 | 47.6% | 0.94 | -8.7 | -104.6 | +95.9 | -182.0 | 4/4 |
| DOT | 31 | 45.2% | 0.46 | -208.1 | -120.6 | -87.5 | -6452.0 | 2/4 |
| 1000PEPE | 24 | 54.2% | 2.11 | 112.2 | -129.4 | +241.6 | 2694.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
