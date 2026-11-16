# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-16 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 30
- **Pooled Edge (INR):** 143.1
- **Standard Error:** 8.5
- **Sigma (Z-Score):** 16.8
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 4770.0
- **Pooled Profit Factor:** 2.08
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 1 | 0.0% | 0.0 | -1673.0 | -305.3 | +657.1 | -1673.0 | 4/4 |
| ETH | 3 | 33.3% | 1.65 | 303.7 | -290.2 | +439.4 | 911.0 | 4/4 |
| SOL | 1 | 100.0% | n/a | 631.0 | -75.5 | +248.3 | 631.0 | 4/4 |
| XRP | 1 | 100.0% | n/a | 81.0 | -82.7 | +142.6 | 81.0 | 3/4 |
| AVAX | 1 | 100.0% | n/a | 322.0 | -154.0 | +32.9 | 322.0 | 4/4 |
| LINK | 2 | 50.0% | 1.44 | 47.5 | -121.9 | +31.8 | 95.0 | 2/4 |
| ADA | 2 | 100.0% | n/a | 443.5 | -89.7 | +80.1 | 887.0 | 3/4 |
| DEXE | 2 | 100.0% | n/a | 332.0 | -134.9 | +178.3 | 664.0 | 3/4 |
| BANK | 2 | 100.0% | n/a | 141.0 | -36.6 | +314.8 | 282.0 | 3/4 |
| BNB | 2 | 100.0% | n/a | 268.5 | -87.7 | +152.6 | 537.0 | 3/4 |
| SUI | 1 | 100.0% | n/a | 607.0 | -108.7 | +309.7 | 607.0 | 3/4 |
| HBAR | 5 | 80.0% | 5.55 | 179.4 | -94.0 | +95.4 | 897.0 | 4/4 |
| LTC | 1 | 0.0% | 0.0 | -211.0 | -79.8 | +132.5 | -211.0 | 4/4 |
| BCH | 1 | 0.0% | 0.0 | -204.0 | -68.7 | +188.9 | -204.0 | 4/4 |
| DOT | 3 | 100.0% | n/a | 193.7 | -108.9 | +238.0 | 581.0 | 4/4 |
| 1000PEPE | 2 | 50.0% | 1.71 | 181.5 | -132.2 | +40.2 | 363.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
