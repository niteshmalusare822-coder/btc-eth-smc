# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-21 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 249
- **Pooled Edge (INR):** 90.6
- **Standard Error:** 8.9
- **Sigma (Z-Score):** 10.13
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 3228.0
- **Pooled Profit Factor:** 1.06
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 7 | 57.1% | 1.29 | 190.9 | -206.4 | +397.3 | 1336.0 | 3/4 |
| ETH | 8 | 50.0% | 0.29 | -471.8 | -276.6 | -195.2 | -3774.0 | 3/4 |
| SOL | 16 | 37.5% | 0.37 | -139.8 | -101.9 | -37.9 | -2236.0 | 1/4 |
| XRP | 15 | 60.0% | 0.96 | -6.1 | -98.9 | +92.8 | -91.0 | 4/4 |
| AVAX | 21 | 47.6% | 1.3 | 47.4 | -59.2 | +106.6 | 995.0 | 3/4 |
| LINK | 15 | 73.3% | 1.35 | 47.0 | -94.0 | +141.0 | 705.0 | 4/4 |
| DOGE | 11 | 63.6% | 0.96 | -3.6 | -127.7 | +124.1 | -40.0 | 4/4 |
| ADA | 16 | 68.8% | 1.35 | 29.4 | -53.1 | +82.5 | 471.0 | 3/4 |
| DEXE | 13 | 30.8% | 0.33 | -239.8 | -112.7 | -127.1 | -3118.0 | 2/4 |
| BANK | 15 | 60.0% | 2.85 | 186.7 | -114.3 | +301.0 | 2800.0 | 4/4 |
| BNB | 5 | 60.0% | 3.1 | 32.4 | -143.1 | +175.5 | 162.0 | 3/3 |
| SUI | 23 | 65.2% | 4.14 | 244.0 | -86.0 | +330.0 | 5612.0 | 4/4 |
| HBAR | 14 | 71.4% | 0.89 | -19.9 | -110.7 | +90.8 | -279.0 | 4/4 |
| LTC | 14 | 50.0% | 0.5 | -78.2 | -91.7 | +13.5 | -1095.0 | 2/4 |
| BCH | 13 | 30.8% | 0.36 | -134.8 | -118.3 | -16.5 | -1753.0 | 3/4 |
| DOT | 23 | 56.5% | 1.15 | 47.9 | -109.3 | +157.2 | 1102.0 | 3/4 |
| 1000PEPE | 20 | 65.0% | 1.58 | 121.5 | -76.5 | +198.0 | 2431.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
