# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-22 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 36
- **Pooled Edge (INR):** 106.9
- **Standard Error:** 9.0
- **Sigma (Z-Score):** 11.89
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -2623.0
- **Pooled Profit Factor:** 0.62
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 3 | 0.0% | 0.0 | -774.3 | -359.9 | +160.2 | -2323.0 | 3/4 |
| ETH | 3 | 66.7% | 1.08 | 20.7 | -270.4 | +258.5 | 62.0 | 4/4 |
| SOL | 2 | 50.0% | 0.39 | -61.0 | -79.4 | +131.0 | -122.0 | 4/4 |
| XRP | 3 | 33.3% | 0.41 | -74.3 | -108.4 | +56.4 | -223.0 | 4/4 |
| AVAX | 2 | 50.0% | 2.17 | 91.0 | -98.6 | +95.6 | 182.0 | 2/4 |
| LINK | 1 | 0.0% | 0.0 | -237.0 | -134.9 | +110.1 | -237.0 | 3/4 |
| DOGE | 2 | 0.0% | 0.0 | -300.0 | -137.0 | +66.1 | -600.0 | 2/4 |
| ADA | 2 | 50.0% | 1.39 | 36.5 | -93.8 | +117.8 | 73.0 | 4/4 |
| BANK | 3 | 33.3% | 0.23 | -132.0 | -89.5 | +148.4 | -396.0 | 4/4 |
| BNB | 1 | 0.0% | 0.0 | -218.0 | -93.4 | +159.6 | -218.0 | 2/4 |
| SUI | 2 | 50.0% | 1.06 | 6.0 | -78.1 | +68.8 | 12.0 | 3/4 |
| HBAR | 2 | 50.0% | 0.9 | -10.0 | -111.2 | +82.7 | -20.0 | 4/4 |
| LTC | 2 | 100.0% | n/a | 268.0 | -89.5 | +60.1 | 536.0 | 4/4 |
| BCH | 1 | 100.0% | n/a | 358.0 | -107.5 | +122.1 | 358.0 | 4/4 |
| DOT | 4 | 0.0% | 0.0 | -170.5 | -86.6 | +134.7 | -682.0 | 3/4 |
| 1000PEPE | 3 | 66.7% | 5.64 | 325.0 | -89.4 | +102.2 | 975.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
