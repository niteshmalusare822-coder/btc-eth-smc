# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-15 (Auto-Generated via collect.py)  
**Objective:** Measure the production SMC_MTF rules against a matched-random null, then improve only when the improvement survives out-of-sample testing, walk-forward validation, and sensitivity checks.

## Canonical Strategy / Execution Contract
- **Measured arm:** `SMC_MTF`
- **Matched null:** `MATCHED_RANDOM_vs_SMC_MTF`
- **Risk cap:** Rs.700 inclusive of fees and slippage
- **Backtest max cost gate:** 0.75R
- **1H bias / 15M setup / 5M trigger:** trigger is informational; 5M quality blocks only when explicitly enabled
- **Retest requirement:** False
- **Structure confirmation:** False
- **Entry model:** `limit_ote` at the canonical POI edge

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 251
- **Pooled Edge (INR):** 36.8
- **Standard Error:** 7.8
- **Sigma (Z-Score):** 4.71
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -27641.0
- **Pooled Profit Factor:** 0.59
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 6 | 33.3% | 0.22 | -619.7 | -157.2 | -462.5 | -3718.0 | 3/4 |
| ETH | 8 | 50.0% | 0.34 | -492.8 | -429.5 | -63.3 | -3942.0 | 2/4 |
| SOL | 13 | 46.2% | 0.4 | -167.7 | -113.4 | -54.3 | -2180.0 | 2/4 |
| XRP | 15 | 33.3% | 0.18 | -225.1 | -118.2 | -106.9 | -3377.0 | 1/4 |
| AVAX | 24 | 45.8% | 0.77 | -46.5 | -104.0 | +57.5 | -1117.0 | 3/4 |
| LINK | 19 | 73.7% | 1.26 | 34.4 | -108.0 | +142.4 | 653.0 | 2/4 |
| DOGE | 11 | 54.5% | 1.12 | 20.4 | -77.9 | +98.3 | 224.0 | 3/4 |
| ADA | 20 | 45.0% | 0.49 | -154.1 | -114.3 | -39.8 | -3081.0 | 2/4 |
| DEXE | 11 | 36.4% | 0.22 | -396.4 | -135.4 | -261.0 | -4360.0 | 3/4 |
| BANK | 17 | 52.9% | 2.27 | 125.8 | -171.6 | +297.4 | 2138.0 | 3/4 |
| BNB | 4 | 25.0% | 0.05 | -87.2 | -132.6 | +45.4 | -349.0 | 4/4 |
| SUI | 22 | 45.5% | 1.18 | 28.1 | -116.8 | +144.9 | 619.0 | 4/4 |
| HBAR | 10 | 40.0% | 1.15 | 14.5 | -128.1 | +142.6 | 145.0 | 4/4 |
| LTC | 11 | 45.5% | 1.07 | 9.5 | -118.4 | +127.9 | 105.0 | 2/4 |
| BCH | 12 | 25.0% | 0.33 | -126.8 | -138.5 | +11.7 | -1522.0 | 3/4 |
| DOT | 26 | 42.3% | 0.43 | -310.5 | -125.5 | -185.0 | -8072.0 | 1/4 |
| 1000PEPE | 22 | 59.1% | 1.04 | 8.8 | -117.2 | +126.0 | 193.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
