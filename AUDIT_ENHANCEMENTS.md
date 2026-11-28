# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-27 (Auto-Generated via collect.py)  
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
- **Pooled Edge (INR):** 97.4
- **Standard Error:** 9.1
- **Sigma (Z-Score):** 10.74
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -1520.0
- **Pooled Profit Factor:** 0.47
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 4 | 50.0% | 0.47 | -180.5 | -491.9 | +9.9 | -722.0 | 3/4 |
| ETH | 1 | 0.0% | 0.0 | -776.0 | -383.6 | +124.6 | -776.0 | 3/4 |
| XRP | 1 | 100.0% | n/a | 107.0 | -110.6 | +62.4 | 107.0 | 3/4 |
| LINK | 1 | 0.0% | 0.0 | -182.0 | -94.3 | +83.0 | -182.0 | 3/4 |
| BNB | 1 | 100.0% | n/a | 150.0 | -96.8 | +154.8 | 150.0 | 2/4 |
| SUI | 1 | 0.0% | 0.0 | -276.0 | -59.1 | +12.1 | -276.0 | 2/4 |
| HBAR | 2 | 100.0% | n/a | 200.0 | -103.6 | +119.2 | 400.0 | 3/4 |
| LTC | 1 | 100.0% | n/a | 79.0 | -50.7 | +58.6 | 79.0 | 4/4 |
| BCH | 1 | 0.0% | 0.0 | -141.0 | -74.5 | +115.3 | -141.0 | 3/4 |
| 1000PEPE | 1 | 0.0% | 0.0 | -159.0 | -124.8 | +108.0 | -159.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
