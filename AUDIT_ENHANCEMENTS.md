# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-17 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 41
- **Pooled Edge (INR):** 145.2
- **Standard Error:** 8.8
- **Sigma (Z-Score):** 16.56
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 4615.0
- **Pooled Profit Factor:** 1.93
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 1 | 100.0% | n/a | 1468.0 | -302.1 | +665.2 | 1468.0 | 4/4 |
| ETH | 3 | 66.7% | 12.07 | 623.7 | -288.1 | +570.7 | 1871.0 | 4/4 |
| SOL | 2 | 0.0% | 0.0 | -277.0 | -77.6 | +218.1 | -554.0 | 4/4 |
| XRP | 2 | 50.0% | 2.89 | 35.0 | -85.1 | +155.4 | 70.0 | 4/4 |
| AVAX | 3 | 66.7% | 1.51 | 33.7 | -147.5 | -25.3 | 101.0 | 3/4 |
| LINK | 2 | 50.0% | 2.61 | 171.5 | -119.4 | +64.6 | 343.0 | 2/4 |
| DOGE | 2 | 50.0% | 0.94 | -14.5 | -97.6 | +107.6 | -29.0 | 4/4 |
| ADA | 3 | 33.3% | 0.24 | -67.0 | -94.3 | +65.9 | -201.0 | 3/4 |
| DEXE | 5 | 40.0% | 2.09 | 197.6 | -143.1 | +226.9 | 988.0 | 3/4 |
| BANK | 1 | 0.0% | 0.0 | -553.0 | -33.1 | +295.9 | -553.0 | 3/4 |
| BNB | 1 | 0.0% | 0.0 | -294.0 | -84.4 | +159.7 | -294.0 | 4/4 |
| SUI | 2 | 50.0% | 4.98 | 123.5 | -99.5 | +305.6 | 247.0 | 3/4 |
| HBAR | 4 | 25.0% | 0.73 | -22.8 | -104.7 | +75.5 | -91.0 | 4/4 |
| LTC | 2 | 50.0% | 0.38 | -116.0 | -65.6 | +100.9 | -232.0 | 3/4 |
| BCH | 4 | 50.0% | 2.61 | 88.8 | -67.9 | +166.4 | 355.0 | 4/4 |
| DOT | 2 | 50.0% | 3.29 | 86.0 | -119.5 | +219.8 | 172.0 | 4/4 |
| 1000PEPE | 2 | 50.0% | 5.3 | 477.0 | -152.6 | +220.0 | 954.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
