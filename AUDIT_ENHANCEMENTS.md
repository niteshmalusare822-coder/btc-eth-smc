# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-26 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 15
- **Pooled Edge (INR):** 95.9
- **Standard Error:** 8.9
- **Sigma (Z-Score):** 10.83
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -784.0
- **Pooled Profit Factor:** 0.52
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| XRP | 1 | 0.0% | 0.0 | -139.0 | -117.6 | +57.6 | -139.0 | 4/4 |
| BANK | 3 | 33.3% | 0.57 | -44.0 | -75.4 | +175.4 | -132.0 | 4/4 |
| BNB | 1 | 0.0% | 0.0 | -149.0 | -96.1 | +163.0 | -149.0 | 3/4 |
| SUI | 1 | 0.0% | 0.0 | -162.0 | -60.6 | +17.9 | -162.0 | 2/4 |
| HBAR | 2 | 50.0% | 0.63 | -29.5 | -100.2 | +116.6 | -59.0 | 4/4 |
| LTC | 2 | 50.0% | 0.47 | -88.0 | -64.3 | +62.9 | -176.0 | 4/4 |
| BCH | 2 | 100.0% | n/a | 107.0 | -90.8 | +108.6 | 214.0 | 3/4 |
| DOT | 1 | 100.0% | n/a | 184.0 | -76.0 | +132.1 | 184.0 | 4/4 |
| 1000PEPE | 2 | 0.0% | 0.0 | -182.5 | -128.8 | +78.6 | -365.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
