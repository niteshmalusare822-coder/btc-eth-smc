# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-20 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 51
- **Pooled Edge (INR):** 108.9
- **Standard Error:** 9.7
- **Sigma (Z-Score):** 11.28
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -4732.0
- **Pooled Profit Factor:** 0.57
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (T-1 trades only)
| Symbol | Trades (T-1) | Win% | PF | Expectancy (INR) | Random Mean (OOS) | Edge (OOS) | Net PnL (INR) | WF Folds (OOS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 5 | 20.0% | 0.27 | -443.6 | -327.1 | +198.8 | -2218.0 | 2/4 |
| ETH | 4 | 25.0% | 0.48 | -279.2 | -293.3 | +317.8 | -1117.0 | 4/4 |
| SOL | 2 | 100.0% | n/a | 221.5 | -80.3 | +126.6 | 443.0 | 4/4 |
| XRP | 2 | 0.0% | 0.0 | -201.0 | -107.5 | +55.6 | -402.0 | 4/4 |
| AVAX | 5 | 20.0% | 0.37 | -145.0 | -97.2 | +99.9 | -725.0 | 2/4 |
| LINK | 3 | 33.3% | 0.18 | -90.7 | -130.1 | +89.4 | -272.0 | 3/4 |
| DOGE | 2 | 100.0% | n/a | 244.0 | -111.5 | +90.2 | 488.0 | 2/4 |
| ADA | 1 | 100.0% | n/a | 528.0 | -98.2 | +126.2 | 528.0 | 4/4 |
| BANK | 2 | 50.0% | 2.62 | 177.0 | -79.7 | +164.0 | 354.0 | 4/4 |
| BNB | 5 | 60.0% | 2.26 | 108.0 | -89.1 | +114.0 | 540.0 | 2/4 |
| SUI | 2 | 0.0% | 0.0 | -181.0 | -54.2 | +79.4 | -362.0 | 3/4 |
| HBAR | 5 | 40.0% | 0.35 | -121.2 | -111.1 | +61.1 | -606.0 | 4/4 |
| LTC | 6 | 33.3% | 0.5 | -71.2 | -74.1 | +68.0 | -427.0 | 4/4 |
| BCH | 2 | 0.0% | 0.0 | -172.0 | -102.9 | +120.7 | -344.0 | 3/3 |
| DOT | 4 | 25.0% | 0.38 | -117.2 | -105.2 | +155.0 | -469.0 | 4/4 |
| 1000PEPE | 1 | 0.0% | 0.0 | -143.0 | -79.5 | +57.4 | -143.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
