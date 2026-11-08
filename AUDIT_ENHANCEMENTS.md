# 📅 Daily SMC MTF Audit Report (Auto-Reset at 10:00 AM IST)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-11-08 (Auto-Generated via collect.py)  
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
- **Total Trades Pooled:** 583
- **Pooled Edge (INR):** 132.8
- **Standard Error:** 8.9
- **Sigma (Z-Score):** 14.99
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** 21854.0
- **Pooled Profit Factor:** 1.18
- **Measured Arm:** SMC_MTF
- **Matched Null:** MATCHED_RANDOM_vs_SMC_MTF

## Verdict
> POSITIVE AND PROFITABLE SO FAR — pooled net P&L is positive, but walk-forward and sensitivity confirmation are still required before calling this a robust edge.

## Profitability Gate
A relative edge is not enough for production. The strategy is **not considered profitable** unless OOS net P&L is positive, pooled/trade-level profit factor is above 1, the OOS sample is sufficient, walk-forward remains stable, and sensitivity runs do not collapse. A negative pooled net P&L is always a **NO-GO** even when the matched-random edge is positive.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 29 | 51.7% | 0.97 | -17.0 | -434.8 | +417.8 | -492.0 | 4/4 |
| ETH | 34 | 47.1% | 1.12 | 54.4 | -330.8 | +385.2 | 1850.0 | 4/4 |
| SOL | 34 | 52.9% | 2.09 | 128.0 | -66.9 | +194.9 | 4352.0 | 4/4 |
| XRP | 40 | 42.5% | 1.45 | 74.1 | -78.1 | +152.2 | 2964.0 | 4/4 |
| AVAX | 30 | 46.7% | 1.49 | 70.1 | -114.6 | +184.7 | 2102.0 | 4/4 |
| LINK | 38 | 34.2% | 0.52 | -108.6 | -119.7 | +11.1 | -4128.0 | 1/4 |
| DOGE | 29 | 41.4% | 0.84 | -26.2 | -110.2 | +84.0 | -760.0 | 4/4 |
| ADA | 33 | 54.5% | 1.5 | 80.7 | -78.2 | +158.9 | 2663.0 | 3/4 |
| DEXE | 29 | 58.6% | 1.14 | 24.3 | -114.4 | +138.7 | 704.0 | 3/4 |
| BANK | 39 | 64.1% | 1.32 | 68.7 | -48.0 | +116.7 | 2678.0 | 3/4 |
| BNB | 38 | 44.7% | 0.9 | -12.3 | -77.8 | +65.5 | -468.0 | 3/4 |
| SUI | 35 | 34.3% | 1.16 | 34.6 | -91.4 | +126.0 | 1210.0 | 3/4 |
| HBAR | 36 | 66.7% | 1.94 | 98.6 | -92.9 | +191.5 | 3550.0 | 4/4 |
| LTC | 31 | 48.4% | 1.04 | 7.5 | -91.4 | +98.9 | 233.0 | 4/4 |
| BCH | 35 | 54.3% | 1.42 | 82.0 | -99.3 | +181.3 | 2870.0 | 4/4 |
| DOT | 36 | 52.8% | 1.44 | 71.8 | -96.5 | +168.3 | 2584.0 | 4/4 |
| 1000PEPE | 37 | 48.6% | 1.0 | -1.6 | -104.2 | +102.6 | -58.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
