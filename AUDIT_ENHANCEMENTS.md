# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-14 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 60
- **Pooled Edge (INR):** 133.6
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 15.87
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 18123.0
- **Pooled Profit Factor:** 5.85
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 4 | 25.0% | 0.03 | -507.2 | -307.9 | +576.6 | -2029.0 | 4/4 |
| ETH | 2 | 100.0% | n/a | 1122.5 | -271.4 | +274.4 | 2245.0 | 3/4 |
| SOL | 2 | 100.0% | n/a | 541.5 | -81.0 | +219.8 | 1083.0 | 4/4 |
| XRP | 4 | 75.0% | 5.94 | 221.0 | -67.6 | +110.5 | 884.0 | 4/4 |
| AVAX | 2 | 100.0% | n/a | 582.0 | -143.7 | -18.4 | 1164.0 | 4/4 |
| LINK | 3 | 100.0% | n/a | 365.7 | -127.0 | +14.4 | 1097.0 | 2/4 |
| DOGE | 7 | 57.1% | 2.11 | 91.0 | -106.2 | +112.5 | 637.0 | 3/4 |
| ADA | 6 | 83.3% | 7.52 | 305.2 | -85.0 | +60.7 | 1831.0 | 3/4 |
| BANK | 4 | 100.0% | n/a | 448.5 | -34.9 | +314.7 | 1794.0 | 3/4 |
| BNB | 5 | 80.0% | 4.39 | 112.0 | -89.9 | +144.3 | 560.0 | 3/4 |
| SUI | 4 | 75.0% | 5.77 | 301.8 | -98.9 | +275.2 | 1207.0 | 4/4 |
| HBAR | 5 | 100.0% | n/a | 477.6 | -89.2 | +86.8 | 2388.0 | 4/4 |
| LTC | 3 | 100.0% | n/a | 355.3 | -72.7 | +171.4 | 1066.0 | 4/4 |
| BCH | 5 | 80.0% | 7.19 | 232.8 | -58.1 | +181.6 | 1164.0 | 4/4 |
| DOT | 3 | 100.0% | n/a | 791.7 | -102.4 | +223.2 | 2375.0 | 4/4 |
| 1000PEPE | 1 | 100.0% | n/a | 657.0 | -97.7 | -10.9 | 657.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
