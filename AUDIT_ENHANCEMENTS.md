# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-08 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 496
- **Pooled Edge (INR):** 84.5
- **Standard Error:** 7.8
- **Sigma (Z-Score):** 10.85
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -9938.0
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
| BTC | 25 | 48.0% | 1.14 | 71.4 | -395.5 | +466.9 | 1784.0 | 4/4 |
| ETH | 31 | 51.6% | 0.84 | -77.7 | -383.8 | +306.1 | -2408.0 | 4/4 |
| SOL | 28 | 46.4% | 1.75 | 101.4 | -71.1 | +172.5 | 2838.0 | 4/4 |
| XRP | 31 | 38.7% | 0.94 | -13.4 | -117.6 | +104.2 | -414.0 | 4/4 |
| AVAX | 27 | 51.9% | 1.28 | 51.1 | -99.5 | +150.6 | 1380.0 | 4/4 |
| LINK | 35 | 42.9% | 0.49 | -109.9 | -130.2 | +20.3 | -3847.0 | 1/4 |
| DOGE | 27 | 29.6% | 0.43 | -121.7 | -94.2 | -27.5 | -3285.0 | 3/4 |
| ADA | 31 | 41.9% | 0.84 | -38.8 | -87.5 | +48.7 | -1203.0 | 3/4 |
| DEXE | 20 | 60.0% | 0.92 | -12.1 | -105.7 | +93.6 | -242.0 | 3/4 |
| BANK | 34 | 64.7% | 1.94 | 113.6 | -58.5 | +172.1 | 3863.0 | 4/4 |
| BNB | 32 | 46.9% | 0.51 | -70.6 | -86.3 | +15.7 | -2260.0 | 2/4 |
| SUI | 31 | 48.4% | 0.67 | -71.2 | -100.7 | +29.5 | -2208.0 | 3/4 |
| HBAR | 31 | 48.4% | 1.43 | 42.0 | -108.2 | +150.2 | 1302.0 | 4/4 |
| LTC | 26 | 50.0% | 0.5 | -83.8 | -92.1 | +8.3 | -2180.0 | 4/4 |
| BCH | 28 | 39.3% | 0.84 | -38.4 | -100.6 | +62.2 | -1075.0 | 4/4 |
| DOT | 32 | 46.9% | 0.87 | -24.9 | -96.5 | +71.6 | -798.0 | 3/4 |
| 1000PEPE | 27 | 51.9% | 0.91 | -43.9 | -71.0 | +27.1 | -1185.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
