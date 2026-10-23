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
- **Total Trades Pooled:** 476
- **Pooled Edge (INR):** 108.9
- **Standard Error:** 8.1
- **Sigma (Z-Score):** 13.39
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -6548.0
- **Pooled Profit Factor:** 0.95
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 28 | 39.3% | 0.67 | -165.9 | -393.4 | +227.5 | -4646.0 | 4/4 |
| ETH | 30 | 46.7% | 0.99 | -8.3 | -364.8 | +356.5 | -248.0 | 4/4 |
| SOL | 27 | 48.1% | 0.99 | -1.0 | -122.2 | +121.2 | -27.0 | 4/4 |
| XRP | 23 | 56.5% | 0.85 | -24.5 | -74.4 | +49.9 | -563.0 | 3/4 |
| AVAX | 29 | 48.3% | 1.02 | 5.9 | -106.1 | +112.0 | 172.0 | 3/4 |
| LINK | 26 | 57.7% | 0.68 | -96.7 | -112.5 | +15.8 | -2513.0 | 3/4 |
| DOGE | 31 | 54.8% | 1.37 | 67.1 | -84.9 | +152.0 | 2081.0 | 3/4 |
| ADA | 29 | 72.4% | 2.12 | 116.6 | -126.2 | +242.8 | 3381.0 | 4/4 |
| DEXE | 18 | 27.8% | 0.56 | -166.6 | -176.0 | +9.4 | -2999.0 | 2/4 |
| BANK | 26 | 46.2% | 1.6 | 102.5 | -99.8 | +202.3 | 2665.0 | 4/4 |
| BNB | 27 | 44.4% | 0.83 | -23.6 | -69.8 | +46.2 | -636.0 | 3/4 |
| SUI | 35 | 54.3% | 1.01 | 2.2 | -84.4 | +86.6 | 77.0 | 4/4 |
| HBAR | 29 | 58.6% | 1.89 | 136.7 | -103.0 | +239.7 | 3964.0 | 4/4 |
| LTC | 31 | 54.8% | 1.35 | 47.1 | -90.9 | +138.0 | 1461.0 | 3/4 |
| BCH | 28 | 57.1% | 1.37 | 56.4 | -84.2 | +140.6 | 1580.0 | 4/4 |
| DOT | 28 | 42.9% | 0.57 | -198.6 | -173.9 | -24.7 | -5562.0 | 2/4 |
| 1000PEPE | 31 | 51.6% | 0.56 | -152.7 | -123.1 | -29.6 | -4735.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
