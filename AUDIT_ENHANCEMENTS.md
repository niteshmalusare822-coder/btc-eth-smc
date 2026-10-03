# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 679
- **Pooled Edge (INR):** -35.3
- **Standard Error:** 19.0
- **Sigma (Z-Score):** -1.86
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -88689.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 38 | 39.5% | 0.24 | -415.7 | -233.1 | -182.6 | -15795.0 | 1/4 |
| ETH | 50 | 36.0% | 0.38 | -368.5 | -176.6 | -191.9 | -18423.0 | 1/4 |
| SOL | 43 | 41.9% | 0.57 | -93.5 | -54.4 | -39.1 | -4020.0 | 1/4 |
| XRP | 43 | 46.5% | 0.6 | -100.7 | -57.2 | -43.5 | -4332.0 | 0/4 |
| AVAX | 32 | 46.9% | 0.62 | -127.5 | -63.7 | -63.8 | -4081.0 | 2/4 |
| LINK | 32 | 37.5% | 0.44 | -165.7 | -56.4 | -109.3 | -5303.0 | 3/4 |
| DOGE | 41 | 48.8% | 0.71 | -72.2 | -33.2 | -39.0 | -2960.0 | 1/4 |
| ADA | 44 | 61.4% | 0.82 | -42.9 | -46.6 | +3.7 | -1888.0 | 1/4 |
| DEXE | 25 | 48.0% | 0.4 | -168.2 | -66.6 | -101.6 | -4204.0 | 1/4 |
| BANK | 31 | 45.2% | 0.95 | -9.5 | -70.5 | +61.0 | -294.0 | 2/4 |
| BNB | 50 | 48.0% | 0.54 | -65.8 | -55.0 | -10.8 | -3289.0 | 2/4 |
| SUI | 43 | 46.5% | 0.57 | -136.6 | -70.9 | -65.7 | -5875.0 | 3/4 |
| HBAR | 33 | 48.5% | 1.0 | 0.0 | -49.9 | +49.9 | 1.0 | 2/4 |
| LTC | 51 | 41.2% | 0.87 | -25.7 | -53.1 | +27.4 | -1311.0 | 4/4 |
| BCH | 36 | 19.4% | 0.25 | -317.1 | -81.9 | -235.2 | -11417.0 | 2/4 |
| DOT | 45 | 46.7% | 0.71 | -78.0 | -52.5 | -25.5 | -3510.0 | 2/4 |
| 1000PEPE | 42 | 50.0% | 0.83 | -47.3 | -63.2 | +15.9 | -1988.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
