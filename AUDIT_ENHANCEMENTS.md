# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-11 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 282
- **Pooled Edge (INR):** 76.1
- **Standard Error:** 8.8
- **Sigma (Z-Score):** 8.7
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -13378.0
- **Pooled Profit Factor:** 0.78
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 4 | 50.0% | 1.14 | 38.0 | -158.6 | +196.6 | 152.0 | 2/4 |
| ETH | 9 | 55.6% | 0.24 | -740.8 | -401.9 | -338.9 | -6667.0 | 3/4 |
| SOL | 11 | 63.6% | 0.51 | -128.9 | -77.1 | -51.8 | -1418.0 | 3/4 |
| XRP | 14 | 28.6% | 0.28 | -198.9 | -115.6 | -83.3 | -2785.0 | 1/4 |
| AVAX | 26 | 50.0% | 0.76 | -42.3 | -73.7 | +31.4 | -1100.0 | 4/4 |
| LINK | 19 | 73.7% | 5.94 | 262.6 | -90.7 | +353.3 | 4989.0 | 3/4 |
| DOGE | 14 | 50.0% | 0.75 | -66.1 | -117.2 | +51.1 | -925.0 | 3/4 |
| ADA | 22 | 45.5% | 0.67 | -72.0 | -99.1 | +27.1 | -1583.0 | 3/4 |
| DEXE | 12 | 50.0% | 0.61 | -108.2 | -76.9 | -31.3 | -1299.0 | 3/4 |
| BANK | 18 | 33.3% | 0.47 | -67.8 | -155.3 | +87.5 | -1221.0 | 2/4 |
| BNB | 5 | 60.0% | 3.47 | 147.0 | -106.9 | +253.9 | 735.0 | 4/4 |
| SUI | 25 | 40.0% | 0.71 | -44.9 | -96.5 | +51.6 | -1123.0 | 4/4 |
| HBAR | 15 | 60.0% | 3.09 | 156.9 | -131.0 | +287.9 | 2353.0 | 4/4 |
| LTC | 20 | 30.0% | 0.66 | -51.5 | -112.5 | +61.0 | -1031.0 | 2/4 |
| BCH | 19 | 42.1% | 0.84 | -21.6 | -117.9 | +96.3 | -410.0 | 4/4 |
| DOT | 28 | 50.0% | 0.68 | -122.8 | -103.8 | -19.0 | -3438.0 | 2/4 |
| 1000PEPE | 21 | 52.4% | 1.55 | 66.3 | -152.2 | +218.5 | 1393.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
