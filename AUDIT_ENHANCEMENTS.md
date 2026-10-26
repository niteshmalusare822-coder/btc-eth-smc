# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-26 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 434
- **Pooled Edge (INR):** 113.0
- **Standard Error:** 6.9
- **Sigma (Z-Score):** 16.32
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -10583.0
- **Pooled Profit Factor:** 0.92
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 25 | 48.0% | 0.81 | -132.2 | -452.4 | +320.2 | -3305.0 | 4/4 |
| ETH | 26 | 50.0% | 0.84 | -145.5 | -406.7 | +261.2 | -3783.0 | 3/4 |
| SOL | 24 | 54.2% | 1.66 | 81.4 | -124.8 | +206.2 | 1954.0 | 3/4 |
| XRP | 26 | 38.5% | 0.4 | -146.8 | -84.8 | -62.0 | -3816.0 | 3/4 |
| AVAX | 23 | 52.2% | 1.15 | 27.1 | -116.1 | +143.2 | 624.0 | 4/4 |
| LINK | 33 | 39.4% | 0.7 | -79.7 | -125.9 | +46.2 | -2631.0 | 3/4 |
| DOGE | 29 | 48.3% | 1.13 | 24.7 | -77.5 | +102.2 | 716.0 | 3/4 |
| ADA | 27 | 63.0% | 1.73 | 91.7 | -89.2 | +180.9 | 2477.0 | 3/4 |
| DEXE | 15 | 46.7% | 1.42 | 94.4 | -142.6 | +237.0 | 1416.0 | 4/4 |
| BANK | 23 | 52.2% | 1.68 | 129.8 | -54.3 | +184.1 | 2986.0 | 4/4 |
| BNB | 19 | 52.6% | 0.84 | -14.8 | -93.6 | +78.8 | -282.0 | 4/4 |
| SUI | 32 | 53.1% | 1.05 | 11.6 | -119.4 | +131.0 | 372.0 | 3/4 |
| HBAR | 25 | 56.0% | 2.19 | 174.3 | -118.6 | +292.9 | 4357.0 | 4/4 |
| LTC | 26 | 42.3% | 0.82 | -29.0 | -103.7 | +74.7 | -753.0 | 4/4 |
| BCH | 28 | 53.6% | 0.87 | -29.5 | -92.5 | +63.0 | -825.0 | 3/4 |
| DOT | 29 | 37.9% | 0.35 | -287.1 | -126.4 | -160.7 | -8326.0 | 2/4 |
| 1000PEPE | 24 | 62.5% | 0.79 | -73.5 | -155.1 | +81.6 | -1764.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
