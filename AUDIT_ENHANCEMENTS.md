# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-18 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 16
- **Pooled Edge (INR):** 97.8
- **Standard Error:** 9.7
- **Sigma (Z-Score):** 10.09
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -468.0
- **Pooled Profit Factor:** 0.85
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 2 | 0.0% | 0.0 | -673.0 | -337.8 | +267.6 | -1346.0 | 3/4 |
| ETH | 2 | 100.0% | n/a | 542.0 | -189.9 | +293.6 | 1084.0 | 4/4 |
| SOL | 2 | 50.0% | 2.44 | 100.5 | -48.0 | +136.4 | 201.0 | 3/4 |
| XRP | 1 | 0.0% | 0.0 | -175.0 | -84.2 | +94.4 | -175.0 | 4/4 |
| DEXE | 4 | 50.0% | 2.31 | 173.2 | -132.9 | +169.6 | 693.0 | 4/4 |
| BANK | 1 | 0.0% | 0.0 | -137.0 | -53.8 | +143.2 | -137.0 | 4/4 |
| SUI | 1 | 0.0% | 0.0 | -242.0 | -70.4 | +119.1 | -242.0 | 3/4 |
| HBAR | 1 | 0.0% | 0.0 | -162.0 | -92.2 | +98.8 | -162.0 | 4/4 |
| LTC | 1 | 0.0% | 0.0 | -148.0 | -82.4 | +22.7 | -148.0 | 4/4 |
| BCH | 1 | 0.0% | 0.0 | -236.0 | -97.4 | +113.9 | -236.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
