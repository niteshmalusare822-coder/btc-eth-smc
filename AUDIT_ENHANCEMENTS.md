# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-16 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 240
- **Pooled Edge (INR):** 13.2
- **Standard Error:** 8.1
- **Sigma (Z-Score):** 1.62
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -23724.0
- **Pooled Profit Factor:** 0.65
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 6 | 50.0% | 0.92 | -65.3 | -246.7 | +181.4 | -392.0 | 4/4 |
| ETH | 8 | 37.5% | 0.13 | -974.1 | -474.8 | -499.3 | -7793.0 | 1/4 |
| SOL | 12 | 41.7% | 0.34 | -205.8 | -120.0 | -85.8 | -2470.0 | 2/4 |
| XRP | 14 | 28.6% | 0.14 | -266.6 | -124.1 | -142.5 | -3733.0 | 1/4 |
| AVAX | 23 | 47.8% | 0.93 | -13.3 | -86.5 | +73.2 | -307.0 | 3/4 |
| LINK | 17 | 64.7% | 0.85 | -26.4 | -105.9 | +79.5 | -449.0 | 2/4 |
| DOGE | 11 | 54.5% | 0.91 | -19.1 | -93.1 | +74.0 | -210.0 | 4/4 |
| ADA | 21 | 52.4% | 0.64 | -89.7 | -97.5 | +7.8 | -1884.0 | 3/4 |
| DEXE | 9 | 33.3% | 0.5 | -125.3 | -164.7 | +39.4 | -1128.0 | 3/4 |
| BANK | 17 | 52.9% | 1.3 | 51.4 | -171.6 | +223.0 | 874.0 | 4/4 |
| BNB | 4 | 50.0% | 0.28 | -53.5 | -132.6 | +79.1 | -214.0 | 4/4 |
| SUI | 21 | 42.9% | 1.12 | 19.1 | -124.0 | +143.1 | 401.0 | 4/4 |
| HBAR | 9 | 66.7% | 3.86 | 155.2 | -108.9 | +264.1 | 1397.0 | 4/4 |
| LTC | 12 | 41.7% | 1.06 | 8.5 | -114.0 | +122.5 | 102.0 | 3/4 |
| BCH | 10 | 10.0% | 0.07 | -218.7 | -139.1 | -79.6 | -2187.0 | 3/4 |
| DOT | 26 | 46.2% | 0.53 | -247.9 | -122.2 | -125.7 | -6446.0 | 1/4 |
| 1000PEPE | 20 | 55.0% | 1.15 | 35.8 | -100.6 | +136.4 | 715.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
