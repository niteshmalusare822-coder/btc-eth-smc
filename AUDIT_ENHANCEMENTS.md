# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-10 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 290
- **Pooled Edge (INR):** 76.4
- **Standard Error:** 8.9
- **Sigma (Z-Score):** 8.55
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -11269.0
- **Pooled Profit Factor:** 0.81
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
| XRP | 15 | 33.3% | 0.3 | -182.2 | -107.9 | -74.3 | -2733.0 | 1/4 |
| AVAX | 28 | 50.0% | 1.18 | 23.0 | -91.9 | +114.9 | 645.0 | 3/4 |
| LINK | 19 | 73.7% | 5.94 | 262.6 | -90.7 | +353.3 | 4989.0 | 4/4 |
| DOGE | 14 | 50.0% | 0.75 | -66.1 | -117.2 | +51.1 | -925.0 | 3/4 |
| ADA | 23 | 43.5% | 0.81 | -43.9 | -100.2 | +56.3 | -1009.0 | 4/4 |
| DEXE | 11 | 45.5% | 0.54 | -138.4 | -68.4 | -70.0 | -1522.0 | 3/4 |
| BANK | 18 | 33.3% | 0.57 | -55.9 | -134.1 | +78.2 | -1006.0 | 2/4 |
| BNB | 5 | 60.0% | 3.47 | 147.0 | -106.9 | +253.9 | 735.0 | 4/4 |
| SUI | 26 | 38.5% | 0.67 | -51.2 | -98.0 | +46.8 | -1330.0 | 4/4 |
| HBAR | 16 | 56.2% | 2.74 | 138.1 | -131.9 | +270.0 | 2209.0 | 3/4 |
| LTC | 19 | 31.6% | 0.68 | -48.0 | -111.0 | +63.0 | -912.0 | 2/4 |
| BCH | 19 | 42.1% | 0.84 | -21.6 | -117.9 | +96.3 | -410.0 | 3/4 |
| DOT | 31 | 48.4% | 0.68 | -113.1 | -100.7 | -12.4 | -3507.0 | 2/4 |
| 1000PEPE | 22 | 54.5% | 1.57 | 65.5 | -142.0 | +207.5 | 1440.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
