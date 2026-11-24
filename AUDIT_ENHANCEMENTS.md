# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-24 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 14
- **Pooled Edge (INR):** 100.7
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 11.92
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -1642.0
- **Pooled Profit Factor:** 0.31
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 1 | 0.0% | 0.0 | -772.0 | -420.1 | +89.0 | -772.0 | 3/4 |
| XRP | 3 | 66.7% | 1.39 | 24.7 | -127.2 | +46.4 | 74.0 | 4/4 |
| LINK | 1 | 0.0% | 0.0 | -182.0 | -112.9 | +96.7 | -182.0 | 3/4 |
| DOGE | 1 | 0.0% | 0.0 | -183.0 | -136.4 | +54.5 | -183.0 | 4/4 |
| ADA | 1 | 100.0% | n/a | 178.0 | -87.8 | +148.0 | 178.0 | 4/4 |
| SUI | 1 | 100.0% | n/a | 165.0 | -71.7 | +60.9 | 165.0 | 2/4 |
| HBAR | 2 | 0.0% | 0.0 | -220.5 | -111.5 | +100.2 | -441.0 | 4/4 |
| LTC | 1 | 0.0% | 0.0 | -174.0 | -84.6 | +66.0 | -174.0 | 4/4 |
| BCH | 1 | 100.0% | n/a | 129.0 | -105.9 | +115.1 | 129.0 | 3/4 |
| DOT | 1 | 0.0% | 0.0 | -203.0 | -79.6 | +133.1 | -203.0 | 3/4 |
| 1000PEPE | 1 | 0.0% | 0.0 | -233.0 | -97.0 | +103.6 | -233.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
