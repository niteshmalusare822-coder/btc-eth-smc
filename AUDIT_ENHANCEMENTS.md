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
- **Total Trades Pooled:** 481
- **Pooled Edge (INR):** 109.0
- **Standard Error:** 8.3
- **Sigma (Z-Score):** 13.17
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -14219.0
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
| BTC | 29 | 41.4% | 0.73 | -128.9 | -360.2 | +231.3 | -3739.0 | 4/4 |
| ETH | 33 | 45.5% | 0.76 | -164.2 | -361.5 | +197.3 | -5418.0 | 4/4 |
| SOL | 28 | 50.0% | 1.1 | 18.4 | -121.3 | +139.7 | 515.0 | 3/4 |
| XRP | 25 | 44.0% | 0.51 | -90.5 | -73.5 | -17.0 | -2263.0 | 3/4 |
| AVAX | 30 | 50.0% | 1.03 | 7.4 | -102.6 | +110.0 | 222.0 | 4/4 |
| LINK | 25 | 52.0% | 0.59 | -136.7 | -110.3 | -26.4 | -3417.0 | 3/4 |
| DOGE | 32 | 53.1% | 1.47 | 83.9 | -75.5 | +159.4 | 2684.0 | 4/4 |
| ADA | 32 | 62.5% | 1.08 | 13.8 | -113.2 | +127.0 | 440.0 | 4/4 |
| DEXE | 19 | 31.6% | 0.77 | -80.6 | -179.4 | +98.8 | -1532.0 | 3/4 |
| BANK | 26 | 46.2% | 1.46 | 86.1 | -114.8 | +200.9 | 2238.0 | 4/4 |
| BNB | 24 | 45.8% | 0.74 | -37.3 | -73.2 | +35.9 | -896.0 | 3/4 |
| SUI | 35 | 54.3% | 0.96 | -10.2 | -87.5 | +77.3 | -357.0 | 4/4 |
| HBAR | 28 | 57.1% | 2.07 | 167.6 | -116.7 | +284.3 | 4693.0 | 4/4 |
| LTC | 31 | 48.4% | 1.18 | 25.7 | -96.8 | +122.5 | 798.0 | 3/4 |
| BCH | 29 | 58.6% | 1.44 | 69.0 | -81.8 | +150.8 | 2000.0 | 4/4 |
| DOT | 26 | 42.3% | 0.52 | -194.4 | -181.7 | -12.7 | -5055.0 | 2/4 |
| 1000PEPE | 29 | 51.7% | 0.54 | -177.0 | -121.8 | -55.2 | -5132.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
