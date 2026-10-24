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
- **Total Trades Pooled:** 466
- **Pooled Edge (INR):** 106.0
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 12.57
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -13633.0
- **Pooled Profit Factor:** 0.89
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 28 | 39.3% | 0.65 | -174.7 | -369.7 | +195.0 | -4891.0 | 4/4 |
| ETH | 31 | 45.2% | 0.79 | -149.9 | -352.7 | +202.8 | -4646.0 | 4/4 |
| SOL | 27 | 51.9% | 1.1 | 19.4 | -123.9 | +143.3 | 523.0 | 4/4 |
| XRP | 24 | 45.8% | 0.53 | -89.5 | -69.4 | -20.1 | -2148.0 | 3/4 |
| AVAX | 30 | 50.0% | 0.97 | -7.8 | -100.7 | +92.9 | -235.0 | 3/4 |
| LINK | 25 | 52.0% | 0.61 | -124.9 | -104.0 | -20.9 | -3123.0 | 3/4 |
| DOGE | 31 | 54.8% | 1.49 | 88.8 | -73.6 | +162.4 | 2753.0 | 3/4 |
| ADA | 30 | 66.7% | 1.14 | 26.3 | -109.6 | +135.9 | 788.0 | 4/4 |
| DEXE | 17 | 29.4% | 0.6 | -150.2 | -177.7 | +27.5 | -2553.0 | 3/4 |
| BANK | 25 | 48.0% | 1.65 | 112.2 | -100.9 | +213.1 | 2806.0 | 4/4 |
| BNB | 24 | 41.7% | 0.76 | -36.2 | -74.5 | +38.3 | -868.0 | 3/4 |
| SUI | 34 | 55.9% | 0.99 | -2.6 | -82.1 | +79.5 | -90.0 | 3/4 |
| HBAR | 28 | 57.1% | 2.1 | 169.7 | -118.7 | +288.4 | 4751.0 | 4/4 |
| LTC | 31 | 51.6% | 1.29 | 38.9 | -90.5 | +129.4 | 1207.0 | 3/4 |
| BCH | 28 | 57.1% | 1.32 | 52.7 | -78.4 | +131.1 | 1476.0 | 4/4 |
| DOT | 25 | 40.0% | 0.53 | -201.8 | -185.2 | -16.6 | -5046.0 | 2/4 |
| 1000PEPE | 28 | 53.6% | 0.58 | -154.9 | -119.0 | -35.9 | -4337.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
