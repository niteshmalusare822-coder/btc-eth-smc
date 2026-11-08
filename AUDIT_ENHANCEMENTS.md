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
- **Structure confirmation:** True
- **Entry model:** `limit_ote` at the canonical POI edge

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 579
- **Pooled Edge (INR):** 129.7
- **Standard Error:** 9.0
- **Sigma (Z-Score):** 14.45
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 21262.0
- **Pooled Profit Factor:** 1.17
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 28 | 50.0% | 0.98 | -11.7 | -404.4 | +392.7 | -328.0 | 4/4 |
| ETH | 34 | 47.1% | 1.12 | 52.8 | -309.5 | +362.3 | 1795.0 | 4/4 |
| SOL | 33 | 57.6% | 2.25 | 140.7 | -69.7 | +210.4 | 4643.0 | 4/4 |
| XRP | 41 | 43.9% | 1.18 | 27.2 | -76.8 | +104.0 | 1115.0 | 4/4 |
| AVAX | 28 | 53.6% | 1.65 | 90.8 | -121.7 | +212.5 | 2543.0 | 4/4 |
| LINK | 38 | 36.8% | 0.53 | -105.2 | -119.7 | +14.5 | -3997.0 | 1/4 |
| DOGE | 29 | 41.4% | 0.84 | -26.2 | -110.2 | +84.0 | -760.0 | 3/4 |
| ADA | 33 | 51.5% | 1.43 | 72.1 | -83.7 | +155.8 | 2379.0 | 3/4 |
| DEXE | 29 | 58.6% | 1.14 | 24.3 | -114.4 | +138.7 | 704.0 | 3/4 |
| BANK | 39 | 66.7% | 1.39 | 83.6 | -44.9 | +128.5 | 3260.0 | 3/4 |
| BNB | 39 | 46.2% | 0.92 | -9.6 | -76.4 | +66.8 | -374.0 | 4/4 |
| SUI | 34 | 35.3% | 1.06 | 13.8 | -93.2 | +107.0 | 468.0 | 3/4 |
| HBAR | 36 | 66.7% | 1.94 | 98.6 | -92.9 | +191.5 | 3550.0 | 4/4 |
| LTC | 31 | 48.4% | 1.07 | 12.2 | -91.4 | +103.6 | 379.0 | 4/4 |
| BCH | 34 | 55.9% | 1.49 | 93.8 | -92.5 | +186.3 | 3189.0 | 4/4 |
| DOT | 36 | 52.8% | 1.42 | 69.3 | -96.5 | +165.8 | 2496.0 | 4/4 |
| 1000PEPE | 37 | 48.6% | 1.02 | 5.4 | -104.2 | +109.6 | 200.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
