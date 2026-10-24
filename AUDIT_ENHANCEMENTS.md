# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-24 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 472
- **Pooled Edge (INR):** 105.0
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 12.58
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -12215.0
- **Pooled Profit Factor:** 0.9
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 29 | 37.9% | 0.64 | -174.0 | -372.1 | +198.1 | -5046.0 | 4/4 |
| ETH | 31 | 48.4% | 0.82 | -126.7 | -349.3 | +222.6 | -3929.0 | 4/4 |
| SOL | 27 | 51.9% | 1.11 | 20.3 | -123.4 | +143.7 | 547.0 | 4/4 |
| XRP | 25 | 44.0% | 0.52 | -87.5 | -71.1 | -16.4 | -2188.0 | 3/4 |
| AVAX | 30 | 50.0% | 1.02 | 4.6 | -94.6 | +99.2 | 138.0 | 4/4 |
| LINK | 26 | 50.0% | 0.61 | -120.9 | -103.4 | -17.5 | -3144.0 | 3/4 |
| DOGE | 31 | 54.8% | 1.49 | 88.8 | -73.6 | +162.4 | 2753.0 | 3/4 |
| ADA | 31 | 67.7% | 1.16 | 27.4 | -109.7 | +137.1 | 848.0 | 4/4 |
| DEXE | 18 | 33.3% | 0.7 | -105.4 | -170.5 | +65.1 | -1897.0 | 3/4 |
| BANK | 25 | 48.0% | 1.58 | 104.6 | -104.4 | +209.0 | 2615.0 | 4/4 |
| BNB | 24 | 41.7% | 0.77 | -34.3 | -73.5 | +39.2 | -823.0 | 3/4 |
| SUI | 35 | 54.3% | 0.96 | -10.2 | -87.5 | +77.3 | -357.0 | 3/4 |
| HBAR | 28 | 57.1% | 2.02 | 163.9 | -112.8 | +276.7 | 4588.0 | 4/4 |
| LTC | 31 | 48.4% | 1.22 | 31.3 | -89.6 | +120.9 | 970.0 | 3/4 |
| BCH | 28 | 60.7% | 1.51 | 74.8 | -78.4 | +153.2 | 2093.0 | 4/4 |
| DOT | 25 | 40.0% | 0.53 | -201.8 | -185.2 | -16.6 | -5046.0 | 2/4 |
| 1000PEPE | 28 | 53.6% | 0.58 | -154.9 | -119.0 | -35.9 | -4337.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
