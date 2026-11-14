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
- **Total Trades Pooled:** 598
- **Pooled Edge (INR):** 116.6
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 13.83
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 25935.0
- **Pooled Profit Factor:** 1.2
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 32 | 56.2% | 1.54 | 286.4 | -268.7 | +555.1 | 9165.0 | 4/4 |
| ETH | 40 | 45.0% | 1.0 | 1.6 | -284.1 | +285.7 | 64.0 | 4/4 |
| SOL | 35 | 54.3% | 1.92 | 109.1 | -66.9 | +176.0 | 3820.0 | 4/4 |
| XRP | 39 | 46.2% | 1.4 | 58.6 | -65.0 | +123.6 | 2285.0 | 4/4 |
| AVAX | 22 | 50.0% | 0.57 | -164.1 | -127.7 | -36.4 | -3610.0 | 3/4 |
| LINK | 40 | 32.5% | 0.41 | -143.2 | -137.1 | -6.1 | -5730.0 | 2/4 |
| DOGE | 38 | 47.4% | 1.07 | 9.9 | -105.5 | +115.4 | 378.0 | 4/4 |
| ADA | 38 | 50.0% | 0.86 | -24.3 | -83.7 | +59.4 | -923.0 | 3/4 |
| DEXE | 30 | 46.7% | 0.84 | -38.9 | -133.5 | +94.6 | -1168.0 | 3/4 |
| BANK | 39 | 69.2% | 5.13 | 260.3 | -38.5 | +298.8 | 10151.0 | 3/4 |
| BNB | 38 | 65.8% | 1.62 | 50.1 | -78.0 | +128.1 | 1904.0 | 4/4 |
| SUI | 32 | 53.1% | 1.69 | 118.8 | -84.9 | +203.7 | 3801.0 | 4/4 |
| HBAR | 42 | 54.8% | 0.98 | -2.8 | -88.4 | +85.6 | -118.0 | 4/4 |
| LTC | 30 | 56.7% | 1.01 | 1.7 | -86.5 | +88.2 | 52.0 | 3/4 |
| BCH | 38 | 63.2% | 2.54 | 160.2 | -63.3 | +223.5 | 6087.0 | 4/4 |
| DOT | 35 | 48.6% | 1.61 | 90.3 | -118.4 | +208.7 | 3160.0 | 4/4 |
| 1000PEPE | 30 | 46.7% | 0.64 | -112.8 | -122.8 | +10.0 | -3383.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
