# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-27 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 426
- **Pooled Edge (INR):** 113.5
- **Standard Error:** 7.2
- **Sigma (Z-Score):** 15.73
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -2698.0
- **Pooled Profit Factor:** 0.98
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 23 | 47.8% | 0.95 | -27.5 | -434.7 | +407.2 | -632.0 | 4/4 |
| ETH | 26 | 53.8% | 0.95 | -46.0 | -390.4 | +344.4 | -1196.0 | 3/4 |
| SOL | 23 | 47.8% | 0.93 | -10.8 | -112.4 | +101.6 | -248.0 | 3/4 |
| XRP | 27 | 40.7% | 0.39 | -149.2 | -90.4 | -58.8 | -4029.0 | 2/4 |
| AVAX | 23 | 56.5% | 2.04 | 108.2 | -110.0 | +218.2 | 2489.0 | 4/4 |
| LINK | 31 | 38.7% | 0.72 | -58.1 | -136.2 | +78.1 | -1800.0 | 3/4 |
| DOGE | 31 | 48.4% | 1.28 | 43.5 | -72.3 | +115.8 | 1347.0 | 4/4 |
| ADA | 28 | 64.3% | 1.81 | 99.9 | -88.9 | +188.8 | 2796.0 | 3/4 |
| DEXE | 15 | 46.7% | 1.31 | 76.3 | -144.4 | +220.7 | 1144.0 | 4/4 |
| BANK | 24 | 54.2% | 1.73 | 133.3 | -73.2 | +206.5 | 3199.0 | 4/4 |
| BNB | 21 | 52.4% | 0.91 | -9.9 | -94.5 | +84.6 | -207.0 | 4/4 |
| SUI | 30 | 53.3% | 1.05 | 11.8 | -121.4 | +133.2 | 353.0 | 3/4 |
| HBAR | 24 | 54.2% | 1.54 | 77.1 | -126.1 | +203.2 | 1850.0 | 4/4 |
| LTC | 25 | 40.0% | 0.77 | -37.3 | -103.6 | +66.3 | -933.0 | 4/4 |
| BCH | 22 | 50.0% | 0.95 | -13.3 | -128.8 | +115.5 | -293.0 | 4/4 |
| DOT | 29 | 44.8% | 0.51 | -161.3 | -126.9 | -34.4 | -4679.0 | 2/4 |
| 1000PEPE | 24 | 62.5% | 0.77 | -77.5 | -155.0 | +77.5 | -1859.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
