# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 679
- **Pooled Edge (INR):** -33.2
- **Standard Error:** 18.9
- **Sigma (Z-Score):** -1.75
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -87863.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 38 | 36.8% | 0.23 | -439.5 | -217.4 | -222.1 | -16701.0 | 1/4 |
| ETH | 50 | 36.0% | 0.38 | -365.7 | -181.1 | -184.6 | -18283.0 | 1/4 |
| SOL | 43 | 41.9% | 0.57 | -91.9 | -54.7 | -37.2 | -3950.0 | 1/4 |
| XRP | 43 | 48.8% | 0.63 | -92.6 | -58.1 | -34.5 | -3982.0 | 0/4 |
| AVAX | 32 | 46.9% | 0.67 | -113.4 | -66.1 | -47.3 | -3630.0 | 2/4 |
| LINK | 32 | 37.5% | 0.43 | -167.9 | -56.1 | -111.8 | -5373.0 | 2/4 |
| DOGE | 41 | 51.2% | 0.75 | -62.1 | -33.8 | -28.3 | -2547.0 | 1/4 |
| ADA | 44 | 61.4% | 0.82 | -41.8 | -50.2 | +8.4 | -1837.0 | 1/4 |
| DEXE | 25 | 48.0% | 0.4 | -168.2 | -66.6 | -101.6 | -4204.0 | 1/4 |
| BANK | 31 | 48.4% | 0.95 | -8.7 | -70.6 | +61.9 | -270.0 | 2/4 |
| BNB | 50 | 48.0% | 0.55 | -63.4 | -55.4 | -8.0 | -3168.0 | 2/4 |
| SUI | 43 | 46.5% | 0.57 | -135.6 | -71.1 | -64.5 | -5830.0 | 3/4 |
| HBAR | 33 | 48.5% | 1.0 | -1.0 | -49.7 | +48.7 | -34.0 | 2/4 |
| LTC | 51 | 41.2% | 0.87 | -25.7 | -53.1 | +27.4 | -1311.0 | 3/4 |
| BCH | 36 | 19.4% | 0.25 | -317.1 | -81.9 | -235.2 | -11417.0 | 2/4 |
| DOT | 45 | 46.7% | 0.75 | -67.3 | -51.2 | -16.1 | -3030.0 | 3/4 |
| 1000PEPE | 42 | 50.0% | 0.81 | -54.7 | -61.9 | +7.2 | -2296.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
