# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-25 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 21
- **Pooled Edge (INR):** 98.0
- **Standard Error:** 8.5
- **Sigma (Z-Score):** 11.58
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -2769.0
- **Pooled Profit Factor:** 0.26
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 1 | 0.0% | 0.0 | -752.0 | -457.2 | +42.6 | -752.0 | 3/4 |
| SOL | 2 | 100.0% | n/a | 213.5 | -81.9 | +156.6 | 427.0 | 4/4 |
| XRP | 1 | 0.0% | 0.0 | -168.0 | -120.0 | +58.7 | -168.0 | 4/4 |
| AVAX | 2 | 0.0% | 0.0 | -172.0 | -112.5 | +137.6 | -344.0 | 3/4 |
| LINK | 2 | 100.0% | n/a | 106.5 | -100.8 | +101.3 | 213.0 | 3/4 |
| DOGE | 2 | 0.0% | 0.0 | -250.5 | -141.4 | +38.1 | -501.0 | 3/4 |
| ADA | 2 | 50.0% | 0.38 | -58.5 | -81.3 | +157.0 | -117.0 | 4/4 |
| BNB | 1 | 0.0% | 0.0 | -196.0 | -93.4 | +167.5 | -196.0 | 3/4 |
| SUI | 3 | 0.0% | 0.0 | -293.7 | -55.0 | +29.2 | -881.0 | 2/4 |
| HBAR | 2 | 50.0% | 1.41 | 36.5 | -105.9 | +101.1 | 73.0 | 4/4 |
| BCH | 1 | 0.0% | 0.0 | -198.0 | -90.5 | +116.9 | -198.0 | 3/4 |
| DOT | 1 | 0.0% | 0.0 | -160.0 | -76.0 | +132.1 | -160.0 | 4/4 |
| 1000PEPE | 1 | 0.0% | 0.0 | -165.0 | -147.5 | +58.7 | -165.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
