# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-18 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 235
- **Pooled Edge (INR):** 38.1
- **Standard Error:** 8.4
- **Sigma (Z-Score):** 4.56
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -13783.0
- **Pooled Profit Factor:** 0.75
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> NO-GO — relative edge may be positive, but pooled net P&L is not profitable after costs. Keep the strategy in research and improve/validate the rules before deployment.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 5 | 40.0% | 0.85 | -141.0 | -349.1 | +208.1 | -705.0 | 2/4 |
| ETH | 9 | 44.4% | 0.32 | -380.7 | -409.7 | +29.0 | -3426.0 | 2/4 |
| SOL | 13 | 46.2% | 0.48 | -114.2 | -120.3 | +6.1 | -1484.0 | 2/4 |
| XRP | 11 | 18.2% | 0.04 | -311.7 | -159.5 | -152.2 | -3429.0 | 1/4 |
| AVAX | 21 | 52.4% | 1.36 | 60.0 | -55.4 | +115.4 | 1260.0 | 2/4 |
| LINK | 16 | 68.8% | 0.86 | -26.6 | -92.1 | +65.5 | -425.0 | 2/4 |
| DOGE | 10 | 50.0% | 0.63 | -61.4 | -129.4 | +68.0 | -614.0 | 4/4 |
| ADA | 21 | 52.4% | 0.5 | -95.4 | -97.0 | +1.6 | -2003.0 | 3/4 |
| DEXE | 9 | 44.4% | 0.7 | -55.7 | -114.7 | +59.0 | -501.0 | 2/4 |
| BANK | 16 | 56.2% | 2.12 | 126.2 | -173.8 | +300.0 | 2019.0 | 3/4 |
| BNB | 4 | 50.0% | 0.28 | -53.5 | -132.6 | +79.1 | -214.0 | 4/4 |
| SUI | 22 | 50.0% | 1.51 | 76.7 | -115.0 | +191.7 | 1688.0 | 4/4 |
| HBAR | 11 | 63.6% | 2.32 | 102.7 | -83.4 | +186.1 | 1130.0 | 4/4 |
| LTC | 12 | 50.0% | 0.65 | -45.7 | -104.8 | +59.1 | -548.0 | 2/4 |
| BCH | 11 | 18.2% | 0.13 | -195.4 | -139.8 | -55.6 | -2149.0 | 3/4 |
| DOT | 25 | 48.0% | 0.79 | -82.4 | -127.6 | +45.2 | -2060.0 | 2/4 |
| 1000PEPE | 19 | 52.6% | 0.6 | -122.2 | -87.0 | -35.2 | -2322.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
