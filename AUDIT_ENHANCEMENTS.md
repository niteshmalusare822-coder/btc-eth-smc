# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-23 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 480
- **Pooled Edge (INR):** 101.0
- **Standard Error:** 8.3
- **Sigma (Z-Score):** 12.19
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -9138.0
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
| BTC | 29 | 41.4% | 0.8 | -107.8 | -403.6 | +295.8 | -3126.0 | 4/4 |
| ETH | 31 | 45.2% | 1.07 | 52.6 | -350.0 | +402.6 | 1630.0 | 4/4 |
| SOL | 25 | 52.0% | 1.15 | 29.2 | -109.9 | +139.1 | 729.0 | 4/4 |
| XRP | 25 | 48.0% | 0.56 | -85.8 | -107.0 | +21.2 | -2146.0 | 3/4 |
| AVAX | 29 | 48.3% | 1.07 | 17.6 | -138.2 | +155.8 | 510.0 | 4/4 |
| LINK | 27 | 44.4% | 0.43 | -230.4 | -139.0 | -91.4 | -6222.0 | 3/4 |
| DOGE | 31 | 54.8% | 1.75 | 123.7 | -86.2 | +209.9 | 3836.0 | 3/4 |
| ADA | 29 | 69.0% | 3.02 | 209.1 | -127.4 | +336.5 | 6064.0 | 4/4 |
| DEXE | 18 | 27.8% | 0.56 | -167.9 | -162.8 | -5.1 | -3023.0 | 3/4 |
| BANK | 27 | 44.4% | 1.15 | 35.3 | -114.9 | +150.2 | 953.0 | 4/4 |
| BNB | 27 | 40.7% | 1.12 | 16.9 | -68.2 | +85.1 | 455.0 | 3/4 |
| SUI | 36 | 52.8% | 0.7 | -94.8 | -102.1 | +7.3 | -3414.0 | 3/4 |
| HBAR | 29 | 55.2% | 1.87 | 136.3 | -90.2 | +226.5 | 3953.0 | 4/4 |
| LTC | 30 | 50.0% | 0.92 | -14.3 | -90.5 | +76.2 | -429.0 | 3/4 |
| BCH | 28 | 57.1% | 1.36 | 65.0 | -71.9 | +136.9 | 1821.0 | 4/4 |
| DOT | 27 | 44.4% | 0.6 | -181.9 | -177.6 | -4.3 | -4911.0 | 3/4 |
| 1000PEPE | 32 | 46.9% | 0.5 | -181.8 | -125.1 | -56.7 | -5818.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
