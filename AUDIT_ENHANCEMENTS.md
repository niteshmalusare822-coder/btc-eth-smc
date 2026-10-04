# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 324
- **Pooled Edge (INR):** -39.4
- **Standard Error:** 26.2
- **Sigma (Z-Score):** -1.5
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -42979.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 15 | 46.7% | 0.53 | -162.5 | -196.5 | +34.0 | -2437.0 | 3/4 |
| ETH | 24 | 45.8% | 0.48 | -260.2 | -172.2 | -88.0 | -6244.0 | 2/4 |
| SOL | 23 | 43.5% | 0.7 | -68.7 | -65.3 | -3.4 | -1580.0 | 1/4 |
| XRP | 21 | 33.3% | 0.28 | -292.6 | -52.1 | -240.5 | -6145.0 | 1/4 |
| AVAX | 12 | 33.3% | 0.55 | -169.5 | -15.1 | -154.4 | -2034.0 | 1/4 |
| LINK | 15 | 53.3% | 0.76 | -35.6 | -43.2 | +7.6 | -534.0 | 2/4 |
| DOGE | 26 | 46.2% | 0.87 | -33.9 | -27.9 | -6.0 | -881.0 | 1/4 |
| ADA | 23 | 39.1% | 0.37 | -219.3 | -48.0 | -171.3 | -5045.0 | 1/4 |
| DEXE | 10 | 50.0% | 1.45 | 112.2 | -72.2 | +184.4 | 1122.0 | 2/4 |
| BANK | 15 | 40.0% | 0.52 | -71.0 | -46.1 | -24.9 | -1065.0 | 1/4 |
| BNB | 25 | 48.0% | 0.75 | -34.5 | -62.0 | +27.5 | -862.0 | 3/4 |
| SUI | 17 | 41.2% | 0.32 | -234.9 | -114.3 | -120.6 | -3994.0 | 3/4 |
| HBAR | 20 | 35.0% | 0.45 | -225.1 | -36.3 | -188.8 | -4502.0 | 1/4 |
| LTC | 22 | 40.9% | 0.45 | -147.7 | -65.7 | -82.0 | -3249.0 | 1/4 |
| BCH | 13 | 53.8% | 0.48 | -104.8 | -70.1 | -34.7 | -1362.0 | 2/4 |
| DOT | 22 | 40.9% | 0.69 | -103.4 | -34.2 | -69.2 | -2275.0 | 3/4 |
| 1000PEPE | 21 | 47.6% | 0.75 | -90.1 | -53.8 | -36.3 | -1892.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
