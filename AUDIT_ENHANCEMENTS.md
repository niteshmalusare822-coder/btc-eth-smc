# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-25 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 427
- **Pooled Edge (INR):** 117.5
- **Standard Error:** 7.2
- **Sigma (Z-Score):** 16.33
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -10947.0
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
| BTC | 25 | 44.0% | 0.74 | -188.3 | -445.0 | +256.7 | -4708.0 | 4/4 |
| ETH | 30 | 50.0% | 0.84 | -142.6 | -379.6 | +237.0 | -4279.0 | 4/4 |
| SOL | 24 | 54.2% | 1.55 | 71.1 | -126.7 | +197.8 | 1707.0 | 3/4 |
| XRP | 27 | 40.7% | 0.42 | -134.8 | -96.3 | -38.5 | -3639.0 | 3/4 |
| AVAX | 25 | 48.0% | 0.97 | -6.0 | -104.7 | +98.7 | -151.0 | 4/4 |
| LINK | 28 | 50.0% | 0.87 | -37.2 | -121.7 | +84.5 | -1041.0 | 4/4 |
| DOGE | 28 | 57.1% | 1.28 | 53.1 | -59.5 | +112.6 | 1488.0 | 3/4 |
| ADA | 26 | 65.4% | 1.35 | 57.9 | -92.0 | +149.9 | 1506.0 | 3/4 |
| DEXE | 14 | 42.9% | 1.61 | 138.2 | -167.4 | +305.6 | 1935.0 | 4/4 |
| BANK | 25 | 48.0% | 1.63 | 99.0 | -91.7 | +190.7 | 2476.0 | 4/4 |
| BNB | 18 | 44.4% | 0.85 | -14.6 | -87.0 | +72.4 | -263.0 | 4/4 |
| SUI | 30 | 50.0% | 0.97 | -7.1 | -117.2 | +110.1 | -214.0 | 3/4 |
| HBAR | 24 | 58.3% | 2.32 | 203.0 | -122.3 | +325.3 | 4871.0 | 4/4 |
| LTC | 26 | 46.2% | 0.86 | -22.2 | -94.8 | +72.6 | -578.0 | 4/4 |
| BCH | 25 | 56.0% | 1.19 | 38.2 | -89.6 | +127.8 | 954.0 | 3/4 |
| DOT | 26 | 34.6% | 0.35 | -293.0 | -133.9 | -159.1 | -7617.0 | 1/4 |
| 1000PEPE | 26 | 61.5% | 0.66 | -130.5 | -155.2 | +24.7 | -3394.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
