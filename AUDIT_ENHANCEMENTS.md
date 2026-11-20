# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-19 (Auto-Generated via collect.py)  
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
- **Pooled Edge (INR):** 102.1
- **Standard Error:** 9.1
- **Sigma (Z-Score):** 11.23
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -753.0
- **Pooled Profit Factor:** 0.84
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 2 | 0.0% | 0.0 | -678.5 | -302.4 | +247.9 | -1357.0 | 4/4 |
| ETH | 4 | 50.0% | 0.59 | -156.8 | -272.1 | +336.7 | -627.0 | 4/4 |
| SOL | 2 | 50.0% | 0.7 | -25.5 | -59.9 | +137.1 | -51.0 | 3/4 |
| XRP | 1 | 0.0% | 0.0 | -183.0 | -87.7 | +74.9 | -183.0 | 4/4 |
| AVAX | 2 | 100.0% | n/a | 481.5 | -102.7 | +33.4 | 963.0 | 3/4 |
| DOGE | 1 | 0.0% | 0.0 | -147.0 | -121.9 | +52.7 | -147.0 | 2/4 |
| ADA | 2 | 100.0% | n/a | 197.5 | -94.5 | +139.8 | 395.0 | 4/4 |
| DEXE | 3 | 66.7% | 1.72 | 75.3 | -100.0 | +206.1 | 226.0 | 4/4 |
| BANK | 1 | 0.0% | 0.0 | -178.0 | -65.8 | +146.9 | -178.0 | 4/4 |
| BNB | 2 | 100.0% | n/a | 196.5 | -82.2 | +165.9 | 393.0 | 2/4 |
| SUI | 1 | 0.0% | 0.0 | -144.0 | -69.0 | +105.6 | -144.0 | 3/4 |
| HBAR | 4 | 75.0% | 2.48 | 69.5 | -96.1 | +94.7 | 278.0 | 3/4 |
| LTC | 4 | 25.0% | 0.16 | -112.2 | -88.8 | +48.1 | -449.0 | 4/4 |
| DOT | 1 | 100.0% | n/a | 128.0 | -129.7 | +86.6 | 128.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
