# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 16
- **Total Trades Pooled:** 170
- **Pooled Edge (INR):** 54.4
- **Standard Error:** 13.6
- **Sigma (Z-Score):** 3.99
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -18550.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 3 | 66.7% | 0.2 | -321.0 | -372.0 | +51.0 | -963.0 | 1/3 |
| ETH | 8 | 62.5% | 0.68 | -92.9 | -462.1 | +369.2 | -743.0 | 3/4 |
| SOL | 11 | 63.6% | 0.3 | -53.7 | -99.8 | +46.1 | -591.0 | 3/3 |
| XRP | 13 | 38.5% | 0.32 | -91.2 | -138.0 | +46.8 | -1185.0 | 4/4 |
| AVAX | 9 | 44.4% | 0.11 | -264.9 | -336.9 | +72.0 | -2384.0 | 3/4 |
| LINK | 7 | 57.1% | 0.56 | -61.7 | -159.7 | +98.0 | -432.0 | 2/4 |
| DOGE | 15 | 60.0% | 0.92 | -8.1 | -103.7 | +95.6 | -122.0 | 3/3 |
| ADA | 18 | 50.0% | 0.51 | -101.3 | -161.8 | +60.5 | -1824.0 | 0/3 |
| BANK | 5 | 80.0% | 2.85 | 136.6 | -90.1 | +226.7 | 683.0 | 2/3 |
| BNB | 11 | 45.5% | 0.23 | -70.4 | -99.4 | +29.0 | -774.0 | 4/4 |
| SUI | 15 | 26.7% | 0.07 | -265.4 | -282.7 | +17.3 | -3981.0 | 2/3 |
| HBAR | 12 | 41.7% | 0.34 | -100.8 | -170.3 | +69.5 | -1210.0 | 4/4 |
| LTC | 9 | 44.4% | 0.29 | -118.6 | -106.6 | -12.0 | -1067.0 | 2/3 |
| BCH | 10 | 20.0% | 0.45 | -136.8 | -175.4 | +38.6 | -1368.0 | 2/4 |
| DOT | 12 | 33.3% | 0.1 | -256.7 | -155.4 | -101.3 | -3080.0 | 2/4 |
| 1000PEPE | 12 | 75.0% | 1.64 | 40.9 | -140.6 | +181.5 | 491.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
