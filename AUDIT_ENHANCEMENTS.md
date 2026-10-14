# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-14 (Auto-Generated via collect.py)  
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
- **Total Symbols Usable:** 16
- **Total Trades Pooled:** 221
- **Pooled Edge (INR):** 33.6
- **Standard Error:** 8.9
- **Sigma (Z-Score):** 3.79
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -25206.0
- **Pooled Profit Factor:** 0.57
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 3 | 33.3% | 0.29 | -255.7 | -241.9 | -13.8 | -767.0 | 2/4 |
| ETH | 8 | 50.0% | 0.25 | -757.0 | -423.1 | -333.9 | -6056.0 | 3/4 |
| SOL | 12 | 50.0% | 0.39 | -186.7 | -91.2 | -95.5 | -2240.0 | 2/4 |
| XRP | 12 | 16.7% | 0.07 | -329.4 | -125.4 | -204.0 | -3953.0 | 1/4 |
| AVAX | 22 | 50.0% | 0.74 | -54.3 | -85.9 | +31.6 | -1195.0 | 3/4 |
| LINK | 17 | 76.5% | 1.52 | 56.6 | -103.2 | +159.8 | 963.0 | 4/4 |
| DOGE | 11 | 54.5% | 1.09 | 16.5 | -88.4 | +104.9 | 181.0 | 4/4 |
| ADA | 20 | 45.0% | 0.54 | -126.1 | -107.9 | -18.2 | -2522.0 | 3/4 |
| DEXE | 11 | 36.4% | 0.23 | -385.7 | -126.9 | -258.8 | -4243.0 | 3/4 |
| BANK | 16 | 43.8% | 1.21 | 23.7 | -174.4 | +198.1 | 379.0 | 4/4 |
| BNB | 3 | 33.3% | 0.06 | -93.3 | -156.7 | +63.4 | -280.0 | 3/3 |
| SUI | 24 | 45.8% | 1.18 | 26.3 | -111.7 | +138.0 | 631.0 | 4/4 |
| HBAR | 10 | 50.0% | 1.57 | 45.4 | -128.2 | +173.6 | 454.0 | 4/4 |
| LTC | 12 | 50.0% | 1.14 | 18.0 | -98.1 | +116.1 | 216.0 | 2/4 |
| BCH | 14 | 35.7% | 0.47 | -72.2 | -122.8 | +50.6 | -1011.0 | 4/4 |
| DOT | 26 | 46.2% | 0.54 | -221.7 | -105.7 | -116.0 | -5763.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
