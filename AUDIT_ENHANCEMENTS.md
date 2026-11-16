# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-15 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 43
- **Pooled Edge (INR):** 140.8
- **Standard Error:** 8.5
- **Sigma (Z-Score):** 16.5
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 10255.0
- **Pooled Profit Factor:** 2.04
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 2 | 50.0% | 2.41 | 541.0 | -340.4 | +684.9 | 1082.0 | 4/4 |
| ETH | 2 | 50.0% | 0.34 | -241.5 | -281.2 | +330.1 | -483.0 | 3/4 |
| SOL | 7 | 42.9% | 2.82 | 298.9 | -83.6 | +254.2 | 2092.0 | 4/4 |
| XRP | 2 | 50.0% | 0.39 | -285.5 | -73.5 | +123.2 | -571.0 | 4/4 |
| AVAX | 3 | 33.3% | 0.19 | -148.0 | -149.1 | +6.7 | -444.0 | 4/4 |
| LINK | 1 | 100.0% | n/a | 503.0 | -122.0 | +33.1 | 503.0 | 2/4 |
| DOGE | 1 | 100.0% | n/a | 110.0 | -105.1 | +117.7 | 110.0 | 4/4 |
| ADA | 1 | 0.0% | 0.0 | -376.0 | -91.4 | +82.7 | -376.0 | 4/4 |
| DEXE | 3 | 66.7% | 11.55 | 829.7 | -126.6 | +181.6 | 2489.0 | 4/4 |
| BANK | 2 | 100.0% | n/a | 496.0 | -28.3 | +308.3 | 992.0 | 3/4 |
| BNB | 4 | 25.0% | 1.44 | 95.0 | -80.5 | +154.9 | 380.0 | 4/4 |
| SUI | 3 | 33.3% | 3.39 | 672.0 | -101.1 | +287.4 | 2016.0 | 3/4 |
| HBAR | 1 | 0.0% | 0.0 | -395.0 | -90.7 | +93.5 | -395.0 | 4/4 |
| LTC | 3 | 66.7% | 9.56 | 739.0 | -76.9 | +160.0 | 2217.0 | 4/4 |
| BCH | 4 | 50.0% | 0.48 | -209.2 | -52.4 | +168.1 | -837.0 | 4/4 |
| DOT | 2 | 100.0% | n/a | 430.0 | -104.3 | +225.9 | 860.0 | 4/4 |
| 1000PEPE | 2 | 50.0% | 1.52 | 310.0 | -116.4 | +14.0 | 620.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
