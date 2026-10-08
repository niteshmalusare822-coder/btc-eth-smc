# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-08 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 314
- **Pooled Edge (INR):** 105.2
- **Standard Error:** 8.5
- **Sigma (Z-Score):** 12.39
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -3810.0
- **Pooled Profit Factor:** 0.94
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 5 | 80.0% | 5.94 | 375.6 | -60.0 | +435.6 | 1878.0 | 3/4 |
| ETH | 10 | 60.0% | 0.27 | -639.7 | -434.0 | -205.7 | -6397.0 | 2/4 |
| SOL | 13 | 61.5% | 0.73 | -69.4 | -68.0 | -1.4 | -902.0 | 3/4 |
| XRP | 12 | 25.0% | 0.23 | -247.8 | -101.0 | -146.8 | -2974.0 | 1/4 |
| AVAX | 29 | 51.7% | 1.31 | 40.0 | -108.9 | +148.9 | 1161.0 | 4/4 |
| LINK | 21 | 71.4% | 7.41 | 331.1 | -84.7 | +415.8 | 6953.0 | 4/4 |
| DOGE | 18 | 55.6% | 1.47 | 81.4 | -80.7 | +162.1 | 1465.0 | 3/4 |
| ADA | 24 | 41.7% | 0.59 | -98.8 | -123.8 | +25.0 | -2370.0 | 3/4 |
| DEXE | 13 | 53.8% | 0.62 | -97.9 | -76.9 | -21.0 | -1273.0 | 3/4 |
| BANK | 19 | 31.6% | 0.72 | -34.2 | -139.7 | +105.5 | -650.0 | 3/4 |
| BNB | 4 | 50.0% | 6.55 | 215.0 | -112.2 | +327.2 | 860.0 | 4/4 |
| SUI | 28 | 46.4% | 1.26 | 32.5 | -83.1 | +115.6 | 909.0 | 4/4 |
| HBAR | 19 | 57.9% | 2.33 | 109.2 | -137.7 | +246.9 | 2075.0 | 4/4 |
| LTC | 21 | 33.3% | 0.76 | -35.6 | -108.3 | +72.7 | -747.0 | 3/4 |
| BCH | 21 | 42.9% | 0.82 | -26.0 | -111.4 | +85.4 | -545.0 | 4/4 |
| DOT | 32 | 43.8% | 0.5 | -173.7 | -112.7 | -61.0 | -5557.0 | 2/4 |
| 1000PEPE | 25 | 52.0% | 1.82 | 92.2 | -140.3 | +232.5 | 2304.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
