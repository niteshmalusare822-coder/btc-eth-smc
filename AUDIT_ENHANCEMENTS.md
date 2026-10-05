# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 268
- **Pooled Edge (INR):** 57.3
- **Standard Error:** 7.2
- **Sigma (Z-Score):** 7.98
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -12697.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 2 | 50.0% | 0.4 | -261.0 | -550.4 | +289.4 | -522.0 | 1/2 |
| ETH | 6 | 83.3% | 5.82 | 563.7 | -295.0 | +858.7 | 3382.0 | 3/3 |
| SOL | 6 | 66.7% | 5.72 | 250.3 | -116.1 | +366.4 | 1502.0 | 2/4 |
| XRP | 11 | 27.3% | 0.4 | -132.1 | -93.4 | -38.7 | -1453.0 | 1/4 |
| AVAX | 28 | 42.9% | 0.65 | -90.9 | -102.8 | +11.9 | -2546.0 | 1/4 |
| LINK | 16 | 43.8% | 0.7 | -43.1 | -142.7 | +99.6 | -689.0 | 2/4 |
| DOGE | 16 | 50.0% | 1.34 | 51.5 | -72.8 | +124.3 | 824.0 | 2/4 |
| ADA | 21 | 47.6% | 0.9 | -20.0 | -109.3 | +89.3 | -421.0 | 2/4 |
| DEXE | 6 | 50.0% | 0.92 | -17.0 | -43.0 | +26.0 | -102.0 | 2/4 |
| BANK | 8 | 25.0% | 0.35 | -57.9 | -126.6 | +68.7 | -463.0 | 2/4 |
| BNB | 1 | 100.0% | None | 105.0 | -47.6 | +152.6 | 105.0 | 2/2 |
| SUI | 40 | 30.0% | 0.4 | -110.0 | -99.1 | -10.9 | -4398.0 | 2/4 |
| HBAR | 19 | 47.4% | 0.42 | -101.9 | -147.1 | +45.2 | -1936.0 | 2/4 |
| LTC | 18 | 33.3% | 0.87 | -14.6 | -87.7 | +73.1 | -263.0 | 3/4 |
| BCH | 15 | 33.3% | 0.98 | -4.7 | -112.0 | +107.3 | -71.0 | 3/4 |
| DOT | 30 | 40.0% | 0.22 | -227.8 | -111.1 | -116.7 | -6834.0 | 3/4 |
| 1000PEPE | 25 | 56.0% | 1.34 | 47.5 | -85.8 | +133.3 | 1188.0 | 3/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
