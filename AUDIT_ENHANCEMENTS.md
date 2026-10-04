# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 673
- **Pooled Edge (INR):** -21.7
- **Standard Error:** 18.6
- **Sigma (Z-Score):** -1.16
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -83033.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 37 | 35.1% | 0.2 | -458.7 | -220.5 | -238.2 | -16971.0 | 1/4 |
| ETH | 48 | 37.5% | 0.4 | -353.0 | -171.3 | -181.7 | -16942.0 | 1/4 |
| SOL | 42 | 45.2% | 0.6 | -86.9 | -61.5 | -25.4 | -3648.0 | 1/4 |
| XRP | 41 | 48.8% | 0.64 | -92.7 | -50.7 | -42.0 | -3799.0 | 1/4 |
| AVAX | 32 | 43.8% | 0.57 | -148.3 | -51.0 | -97.3 | -4745.0 | 1/4 |
| LINK | 30 | 40.0% | 0.49 | -144.9 | -63.7 | -81.2 | -4348.0 | 2/4 |
| DOGE | 41 | 51.2% | 0.81 | -45.2 | -51.0 | +5.8 | -1853.0 | 1/4 |
| ADA | 44 | 59.1% | 0.76 | -56.3 | -50.1 | -6.2 | -2479.0 | 1/4 |
| DEXE | 25 | 52.0% | 0.43 | -150.8 | -71.3 | -79.5 | -3771.0 | 1/4 |
| BANK | 36 | 50.0% | 0.9 | -16.2 | -72.7 | +56.5 | -583.0 | 3/4 |
| BNB | 50 | 52.0% | 0.64 | -47.2 | -55.4 | +8.2 | -2360.0 | 3/4 |
| SUI | 41 | 48.8% | 0.6 | -122.4 | -81.7 | -40.7 | -5019.0 | 3/4 |
| HBAR | 33 | 48.5% | 1.03 | 8.2 | -65.3 | +73.5 | 270.0 | 3/4 |
| LTC | 49 | 40.8% | 0.87 | -26.8 | -58.1 | +31.3 | -1313.0 | 3/4 |
| BCH | 38 | 23.7% | 0.27 | -294.8 | -66.1 | -228.7 | -11202.0 | 2/4 |
| DOT | 46 | 47.8% | 0.74 | -70.3 | -53.9 | -16.4 | -3236.0 | 1/4 |
| 1000PEPE | 40 | 50.0% | 0.9 | -25.9 | -53.1 | +27.2 | -1034.0 | 1/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
