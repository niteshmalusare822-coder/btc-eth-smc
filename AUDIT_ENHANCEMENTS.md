# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-21 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 28
- **Pooled Edge (INR):** 112.4
- **Standard Error:** 9.2
- **Sigma (Z-Score):** 12.24
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 1657.0
- **Pooled Profit Factor:** 1.35
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 1 | 100.0% | n/a | 225.0 | -306.8 | +182.3 | 225.0 | 3/4 |
| SOL | 4 | 0.0% | 0.0 | -207.5 | -85.0 | +129.3 | -830.0 | 4/4 |
| XRP | 2 | 0.0% | 0.0 | -282.5 | -117.3 | +50.2 | -565.0 | 3/4 |
| AVAX | 4 | 50.0% | 3.4 | 281.2 | -102.4 | +111.3 | 1125.0 | 3/4 |
| LINK | 2 | 50.0% | 3.73 | 198.0 | -137.1 | +92.0 | 396.0 | 3/4 |
| DOGE | 1 | 0.0% | 0.0 | -412.0 | -146.5 | +64.7 | -412.0 | 2/4 |
| ADA | 2 | 0.0% | 0.0 | -274.5 | -102.7 | +123.1 | -549.0 | 4/4 |
| DEXE | 1 | 0.0% | 0.0 | -283.0 | -158.5 | +135.5 | -283.0 | 4/4 |
| BANK | 4 | 50.0% | 1.53 | 107.0 | -82.7 | +151.7 | 428.0 | 4/4 |
| BNB | 1 | 0.0% | 0.0 | -162.0 | -97.2 | +153.6 | -162.0 | 2/4 |
| SUI | 2 | 0.0% | 0.0 | -226.0 | -67.9 | +65.2 | -452.0 | 3/4 |
| LTC | 1 | 100.0% | n/a | 723.0 | -79.1 | +63.5 | 723.0 | 4/4 |
| DOT | 3 | 100.0% | n/a | 671.0 | -104.9 | +149.1 | 2013.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
