# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-10 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 590
- **Pooled Edge (INR):** 118.1
- **Standard Error:** 9.2
- **Sigma (Z-Score):** 12.8
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 23223.0
- **Pooled Profit Factor:** 1.16
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 31 | 48.4% | 1.17 | 105.6 | -355.1 | +460.7 | 3273.0 | 4/4 |
| ETH | 39 | 51.3% | 1.02 | 15.4 | -297.4 | +312.8 | 600.0 | 4/4 |
| SOL | 38 | 50.0% | 1.76 | 100.1 | -64.8 | +164.9 | 3802.0 | 4/4 |
| XRP | 40 | 45.0% | 1.29 | 47.0 | -74.9 | +121.9 | 1882.0 | 4/4 |
| AVAX | 25 | 52.0% | 0.71 | -92.9 | -120.7 | +27.8 | -2322.0 | 3/4 |
| LINK | 38 | 31.6% | 0.43 | -146.5 | -121.5 | -25.0 | -5568.0 | 2/4 |
| DOGE | 31 | 48.4% | 1.37 | 59.2 | -110.9 | +170.1 | 1836.0 | 4/4 |
| ADA | 38 | 44.7% | 1.08 | 14.6 | -82.5 | +97.1 | 556.0 | 3/4 |
| DEXE | 28 | 50.0% | 0.66 | -84.9 | -120.5 | +35.6 | -2378.0 | 4/4 |
| BANK | 35 | 68.6% | 4.61 | 289.8 | -42.4 | +332.2 | 10144.0 | 3/4 |
| BNB | 37 | 51.4% | 1.11 | 12.5 | -78.8 | +91.3 | 463.0 | 4/4 |
| SUI | 33 | 42.4% | 1.39 | 90.1 | -90.6 | +180.7 | 2973.0 | 3/4 |
| HBAR | 39 | 61.5% | 1.19 | 27.9 | -82.6 | +110.5 | 1087.0 | 4/4 |
| LTC | 31 | 48.4% | 1.04 | 7.5 | -94.8 | +102.3 | 233.0 | 4/4 |
| BCH | 34 | 58.8% | 1.69 | 117.5 | -83.1 | +200.6 | 3996.0 | 4/4 |
| DOT | 35 | 51.4% | 1.67 | 107.0 | -97.1 | +204.1 | 3746.0 | 4/4 |
| 1000PEPE | 38 | 47.4% | 0.91 | -28.9 | -96.0 | +67.1 | -1100.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
