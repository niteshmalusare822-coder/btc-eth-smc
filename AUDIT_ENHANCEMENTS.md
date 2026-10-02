# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 688
- **Pooled Edge (INR):** -13.6
- **Standard Error:** 18.7
- **Sigma (Z-Score):** -0.72
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -79209.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 40 | 40.0% | 0.29 | -379.2 | -219.1 | -160.1 | -15167.0 | 1/4 |
| ETH | 49 | 36.7% | 0.4 | -360.0 | -158.7 | -201.3 | -17638.0 | 2/4 |
| SOL | 44 | 43.2% | 0.62 | -83.6 | -57.3 | -26.3 | -3679.0 | 0/4 |
| XRP | 43 | 48.8% | 0.63 | -93.7 | -61.4 | -32.3 | -4028.0 | 2/4 |
| AVAX | 38 | 52.6% | 0.8 | -59.9 | -57.1 | -2.8 | -2276.0 | 2/4 |
| LINK | 35 | 42.9% | 0.6 | -116.0 | -67.5 | -48.5 | -4059.0 | 3/4 |
| DOGE | 39 | 48.7% | 0.71 | -74.3 | -35.7 | -38.6 | -2899.0 | 1/4 |
| ADA | 46 | 56.5% | 0.72 | -68.0 | -49.4 | -18.6 | -3130.0 | 1/4 |
| DEXE | 24 | 45.8% | 0.38 | -181.5 | -67.8 | -113.7 | -4357.0 | 2/4 |
| BANK | 34 | 50.0% | 1.0 | -0.5 | -66.7 | +66.2 | -17.0 | 1/4 |
| BNB | 50 | 50.0% | 0.68 | -46.0 | -58.2 | +12.2 | -2298.0 | 2/4 |
| SUI | 43 | 46.5% | 0.57 | -136.6 | -70.9 | -65.7 | -5875.0 | 2/4 |
| HBAR | 32 | 50.0% | 1.02 | 4.3 | -57.9 | +62.2 | 138.0 | 2/4 |
| LTC | 48 | 43.8% | 1.09 | 15.8 | -66.3 | +82.1 | 757.0 | 3/4 |
| BCH | 37 | 24.3% | 0.34 | -248.9 | -85.0 | -163.9 | -9208.0 | 0/4 |
| DOT | 41 | 41.5% | 0.71 | -87.7 | -54.0 | -33.7 | -3596.0 | 3/4 |
| 1000PEPE | 45 | 51.1% | 0.85 | -41.7 | -48.7 | +7.0 | -1877.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
