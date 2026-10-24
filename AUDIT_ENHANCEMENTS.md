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
- **Total Trades Pooled:** 478
- **Pooled Edge (INR):** 111.5
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 13.33
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -11813.0
- **Pooled Profit Factor:** 0.91
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 29 | 41.4% | 0.73 | -128.9 | -360.2 | +231.3 | -3739.0 | 4/4 |
| ETH | 33 | 45.5% | 0.77 | -153.9 | -356.0 | +202.1 | -5078.0 | 4/4 |
| SOL | 28 | 50.0% | 1.1 | 18.1 | -123.2 | +141.3 | 507.0 | 3/4 |
| XRP | 25 | 44.0% | 0.51 | -90.5 | -73.5 | -17.0 | -2263.0 | 3/4 |
| AVAX | 30 | 50.0% | 1.01 | 2.8 | -104.2 | +107.0 | 85.0 | 4/4 |
| LINK | 25 | 52.0% | 0.59 | -136.7 | -110.3 | -26.4 | -3417.0 | 3/4 |
| DOGE | 32 | 53.1% | 1.45 | 80.6 | -78.2 | +158.8 | 2580.0 | 3/4 |
| ADA | 32 | 65.6% | 1.19 | 34.6 | -100.8 | +135.4 | 1108.0 | 4/4 |
| DEXE | 18 | 33.3% | 0.81 | -68.4 | -170.5 | +102.1 | -1232.0 | 3/4 |
| BANK | 25 | 48.0% | 1.58 | 104.6 | -104.4 | +209.0 | 2615.0 | 4/4 |
| BNB | 24 | 41.7% | 0.77 | -34.3 | -73.5 | +39.2 | -823.0 | 3/4 |
| SUI | 35 | 54.3% | 0.96 | -10.2 | -87.5 | +77.3 | -357.0 | 4/4 |
| HBAR | 28 | 57.1% | 2.08 | 168.8 | -116.7 | +285.5 | 4725.0 | 4/4 |
| LTC | 31 | 48.4% | 1.2 | 28.5 | -96.8 | +125.3 | 883.0 | 3/4 |
| BCH | 29 | 58.6% | 1.47 | 72.0 | -81.8 | +153.8 | 2089.0 | 4/4 |
| DOT | 25 | 44.0% | 0.55 | -183.1 | -172.2 | -10.9 | -4578.0 | 2/4 |
| 1000PEPE | 29 | 51.7% | 0.55 | -169.6 | -121.8 | -47.8 | -4918.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
