# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 270
- **Pooled Edge (INR):** 55.6
- **Standard Error:** 7.1
- **Sigma (Z-Score):** 7.82
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -10603.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 2 | 50.0% | 0.4 | -261.0 | -550.4 | +289.4 | -522.0 | 1/2 |
| ETH | 6 | 83.3% | 5.82 | 563.7 | -295.0 | +858.7 | 3382.0 | 3/3 |
| SOL | 7 | 57.1% | 3.95 | 194.1 | -119.3 | +313.4 | 1359.0 | 2/4 |
| XRP | 11 | 18.2% | 0.25 | -174.9 | -103.3 | -71.6 | -1924.0 | 1/4 |
| AVAX | 29 | 41.4% | 0.6 | -108.6 | -91.8 | -16.8 | -3149.0 | 1/4 |
| LINK | 16 | 43.8% | 0.7 | -43.1 | -142.7 | +99.6 | -689.0 | 2/4 |
| DOGE | 16 | 50.0% | 1.25 | 40.4 | -72.8 | +113.2 | 646.0 | 1/4 |
| ADA | 20 | 55.0% | 1.2 | 40.4 | -106.4 | +146.8 | 807.0 | 2/4 |
| DEXE | 6 | 66.7% | 1.32 | 61.0 | -39.0 | +100.0 | 366.0 | 2/4 |
| BANK | 8 | 25.0% | 0.35 | -57.9 | -126.6 | +68.7 | -463.0 | 1/4 |
| BNB | 1 | 100.0% | None | 105.0 | -47.6 | +152.6 | 105.0 | 2/2 |
| SUI | 40 | 30.0% | 0.45 | -87.2 | -93.6 | +6.4 | -3488.0 | 3/4 |
| HBAR | 20 | 50.0% | 0.43 | -94.1 | -136.4 | +42.3 | -1882.0 | 2/4 |
| LTC | 18 | 33.3% | 0.87 | -14.6 | -87.7 | +73.1 | -263.0 | 3/4 |
| BCH | 15 | 33.3% | 0.98 | -4.7 | -112.0 | +107.3 | -71.0 | 3/4 |
| DOT | 30 | 40.0% | 0.23 | -224.0 | -115.7 | -108.3 | -6719.0 | 3/4 |
| 1000PEPE | 25 | 56.0% | 1.69 | 76.1 | -85.8 | +161.9 | 1902.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
