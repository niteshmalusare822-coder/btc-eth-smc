# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-07 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 301
- **Pooled Edge (INR):** 80.9
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 9.64
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -12061.0
- **Pooled Profit Factor:** 0.82
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 6 | 66.7% | 1.65 | 148.2 | -244.7 | +392.9 | 889.0 | 3/4 |
| ETH | 10 | 50.0% | 0.26 | -700.8 | -467.8 | -233.0 | -7008.0 | 2/4 |
| SOL | 12 | 58.3% | 0.65 | -97.4 | -61.6 | -35.8 | -1169.0 | 2/4 |
| XRP | 13 | 30.8% | 0.26 | -235.3 | -92.4 | -142.9 | -3059.0 | 1/4 |
| AVAX | 24 | 50.0% | 1.11 | 15.8 | -115.7 | +131.5 | 380.0 | 4/4 |
| LINK | 20 | 70.0% | 3.1 | 269.9 | -97.3 | +367.2 | 5397.0 | 3/4 |
| DOGE | 17 | 52.9% | 1.46 | 82.6 | -84.7 | +167.3 | 1405.0 | 4/4 |
| ADA | 22 | 36.4% | 0.5 | -151.4 | -141.9 | -9.5 | -3330.0 | 3/4 |
| DEXE | 11 | 63.6% | 2.12 | 97.9 | -47.0 | +144.9 | 1077.0 | 4/4 |
| BANK | 19 | 31.6% | 0.48 | -95.2 | -134.9 | +39.7 | -1809.0 | 3/4 |
| BNB | 5 | 60.0% | 4.65 | 194.4 | -135.7 | +330.1 | 972.0 | 3/3 |
| SUI | 27 | 40.7% | 0.87 | -19.6 | -107.6 | +88.0 | -529.0 | 3/4 |
| HBAR | 19 | 57.9% | 2.04 | 92.9 | -119.9 | +212.8 | 1766.0 | 3/4 |
| LTC | 22 | 36.4% | 0.38 | -174.4 | -117.1 | -57.3 | -3836.0 | 3/4 |
| BCH | 21 | 42.9% | 0.81 | -28.0 | -116.3 | +88.3 | -587.0 | 4/4 |
| DOT | 30 | 43.3% | 0.51 | -169.0 | -122.2 | -46.8 | -5070.0 | 2/4 |
| 1000PEPE | 23 | 52.2% | 1.99 | 106.5 | -136.5 | +243.0 | 2450.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
