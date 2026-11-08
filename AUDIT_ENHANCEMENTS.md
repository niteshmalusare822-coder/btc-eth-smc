# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-08 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 471
- **Pooled Edge (INR):** 78.3
- **Standard Error:** 7.7
- **Sigma (Z-Score):** 10.14
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -8566.0
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
| BTC | 25 | 52.0% | 1.55 | 205.5 | -409.6 | +615.1 | 5138.0 | 4/4 |
| ETH | 30 | 50.0% | 0.76 | -129.8 | -376.9 | +247.1 | -3893.0 | 3/4 |
| SOL | 25 | 48.0% | 1.59 | 82.7 | -74.0 | +156.7 | 2068.0 | 4/4 |
| XRP | 30 | 36.7% | 0.85 | -35.7 | -113.1 | +77.4 | -1071.0 | 2/4 |
| AVAX | 26 | 53.8% | 1.33 | 60.3 | -94.5 | +154.8 | 1567.0 | 4/4 |
| LINK | 35 | 34.3% | 0.45 | -101.3 | -132.6 | +31.3 | -3544.0 | 1/4 |
| DOGE | 26 | 26.9% | 0.38 | -146.7 | -96.0 | -50.7 | -3814.0 | 3/4 |
| ADA | 31 | 45.2% | 0.87 | -31.9 | -87.3 | +55.4 | -989.0 | 3/4 |
| DEXE | 20 | 60.0% | 0.92 | -12.1 | -105.7 | +93.6 | -242.0 | 4/4 |
| BANK | 32 | 68.8% | 2.09 | 120.6 | -44.9 | +165.5 | 3859.0 | 4/4 |
| BNB | 24 | 45.8% | 0.59 | -54.5 | -79.8 | +25.3 | -1307.0 | 2/4 |
| SUI | 28 | 46.4% | 0.55 | -109.0 | -106.0 | -3.0 | -3053.0 | 3/4 |
| HBAR | 31 | 48.4% | 1.53 | 58.9 | -105.1 | +164.0 | 1826.0 | 4/4 |
| LTC | 24 | 33.3% | 0.35 | -100.5 | -102.1 | +1.6 | -2412.0 | 4/4 |
| BCH | 28 | 32.1% | 0.68 | -84.1 | -114.3 | +30.2 | -2355.0 | 4/4 |
| DOT | 32 | 50.0% | 1.25 | 32.6 | -92.9 | +125.5 | 1043.0 | 3/4 |
| 1000PEPE | 24 | 54.2% | 0.89 | -57.8 | -82.2 | +24.4 | -1387.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
