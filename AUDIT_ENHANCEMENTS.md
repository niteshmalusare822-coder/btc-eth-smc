# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-12 (Auto-Generated via collect.py)  
**Objective:** Measure the production SMC_MTF rules against a matched-random null, then improve only when the improvement survives out-of-sample testing, walk-forward validation, and sensitivity checks.

## Canonical Strategy / Execution Contract
- **Measured arm:** `SMC_MTF`
- **Matched null:** `MATCHED_RANDOM_vs_SMC_MTF`
- **Risk cap:** Rs.700 inclusive of fees and slippage
- **Backtest max cost gate:** 0.75R
- **1H bias / 15M setup / 5M trigger:** trigger is informational; 5M quality blocks only when explicitly enabled
- **Retest requirement:** False
- **Structure confirmation:** True
- **Entry model:** `limit_ote` at the canonical POI edge

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 601
- **Pooled Edge (INR):** 104.4
- **Standard Error:** 9.3
- **Sigma (Z-Score):** 11.29
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 28963.0
- **Pooled Profit Factor:** 1.21
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 31 | 54.8% | 1.68 | 358.3 | -314.2 | +672.5 | 11106.0 | 3/4 |
| ETH | 46 | 45.7% | 1.0 | -2.0 | -292.9 | +290.9 | -92.0 | 3/4 |
| SOL | 37 | 51.4% | 1.88 | 107.6 | -62.7 | +170.3 | 3980.0 | 4/4 |
| XRP | 39 | 46.2% | 1.83 | 124.1 | -56.9 | +181.0 | 4839.0 | 4/4 |
| AVAX | 23 | 52.2% | 0.73 | -87.4 | -136.8 | +49.4 | -2011.0 | 3/4 |
| LINK | 40 | 30.0% | 0.32 | -175.0 | -132.6 | -42.4 | -6999.0 | 2/4 |
| DOGE | 34 | 44.1% | 1.08 | 12.6 | -110.3 | +122.9 | 427.0 | 4/4 |
| ADA | 38 | 47.4% | 1.03 | 6.3 | -99.3 | +105.6 | 238.0 | 3/4 |
| DEXE | 29 | 44.8% | 0.56 | -113.7 | -136.4 | +22.7 | -3296.0 | 2/4 |
| BANK | 38 | 73.7% | 6.79 | 312.9 | -41.5 | +354.4 | 11890.0 | 3/4 |
| BNB | 36 | 58.3% | 1.15 | 16.3 | -75.7 | +92.0 | 587.0 | 4/4 |
| SUI | 36 | 41.7% | 1.3 | 69.3 | -82.3 | +151.6 | 2495.0 | 2/4 |
| HBAR | 41 | 51.2% | 0.72 | -50.1 | -103.8 | +53.7 | -2054.0 | 3/4 |
| LTC | 30 | 56.7% | 1.44 | 68.4 | -80.6 | +149.0 | 2051.0 | 4/4 |
| BCH | 33 | 63.6% | 1.9 | 126.9 | -72.1 | +199.0 | 4189.0 | 4/4 |
| DOT | 34 | 47.1% | 1.52 | 81.5 | -116.0 | +197.5 | 2770.0 | 4/4 |
| 1000PEPE | 36 | 55.6% | 0.89 | -32.1 | -115.5 | +83.4 | -1157.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
