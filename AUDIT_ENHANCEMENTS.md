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
- **Total Trades Pooled:** 18
- **Pooled Edge (INR):** 92.1
- **Standard Error:** 9.5
- **Sigma (Z-Score):** 9.68
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 1185.0
- **Pooled Profit Factor:** 1.62
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| SOL | 1 | 0.0% | 0.0 | -200.0 | -44.1 | +131.6 | -200.0 | 3/4 |
| XRP | 1 | 100.0% | n/a | 107.0 | -98.1 | +109.6 | 107.0 | 4/4 |
| AVAX | 2 | 50.0% | 1.12 | 11.5 | -106.2 | +1.4 | 23.0 | 3/4 |
| ADA | 1 | 0.0% | 0.0 | -142.0 | -101.1 | +107.2 | -142.0 | 4/4 |
| DEXE | 4 | 50.0% | 3.5 | 338.8 | -178.2 | +86.6 | 1355.0 | 4/4 |
| HBAR | 4 | 50.0% | 1.0 | 0.0 | -98.2 | +97.6 | 0.0 | 4/4 |
| LTC | 1 | 100.0% | n/a | 143.0 | -89.6 | +45.3 | 143.0 | 4/4 |
| BCH | 4 | 25.0% | 0.8 | -25.2 | -92.1 | +118.3 | -101.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
