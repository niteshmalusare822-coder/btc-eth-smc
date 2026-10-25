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
- **Total Trades Pooled:** 411
- **Pooled Edge (INR):** 113.8
- **Standard Error:** 7.3
- **Sigma (Z-Score):** 15.53
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -12518.0
- **Pooled Profit Factor:** 0.9
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 24 | 41.7% | 0.72 | -206.3 | -456.8 | +250.5 | -4952.0 | 4/4 |
| ETH | 28 | 50.0% | 0.83 | -156.7 | -410.3 | +253.6 | -4387.0 | 4/4 |
| SOL | 23 | 52.2% | 1.52 | 70.4 | -130.9 | +201.3 | 1619.0 | 3/4 |
| XRP | 26 | 42.3% | 0.45 | -123.9 | -94.4 | -29.5 | -3221.0 | 3/4 |
| AVAX | 23 | 47.8% | 0.98 | -3.4 | -110.8 | +107.4 | -78.0 | 4/4 |
| LINK | 27 | 51.9% | 0.88 | -35.3 | -118.7 | +83.4 | -952.0 | 4/4 |
| DOGE | 27 | 55.6% | 1.25 | 50.0 | -60.7 | +110.7 | 1349.0 | 3/4 |
| ADA | 26 | 65.4% | 1.54 | 92.7 | -96.3 | +189.0 | 2411.0 | 3/4 |
| DEXE | 14 | 42.9% | 1.61 | 138.2 | -167.4 | +305.6 | 1935.0 | 4/4 |
| BANK | 23 | 47.8% | 1.5 | 88.9 | -80.6 | +169.5 | 2044.0 | 3/4 |
| BNB | 18 | 38.9% | 0.8 | -21.1 | -88.1 | +67.0 | -379.0 | 3/4 |
| SUI | 30 | 50.0% | 0.97 | -7.1 | -117.2 | +110.1 | -214.0 | 3/4 |
| HBAR | 23 | 56.5% | 1.87 | 166.0 | -119.9 | +285.9 | 3817.0 | 4/4 |
| LTC | 25 | 44.0% | 0.85 | -25.4 | -100.0 | +74.6 | -635.0 | 4/4 |
| BCH | 24 | 54.2% | 1.18 | 37.8 | -90.5 | +128.3 | 906.0 | 3/4 |
| DOT | 25 | 32.0% | 0.35 | -307.7 | -136.6 | -171.1 | -7692.0 | 1/4 |
| 1000PEPE | 25 | 60.0% | 0.59 | -163.6 | -161.5 | -2.1 | -4089.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
