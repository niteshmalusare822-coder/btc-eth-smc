# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 16
- **Total Trades Pooled:** 166
- **Pooled Edge (INR):** 34.9
- **Standard Error:** 14.0
- **Sigma (Z-Score):** 2.49
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -19016.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 3 | 66.7% | 0.39 | -244.0 | -632.7 | +388.7 | -732.0 | 1/3 |
| ETH | 8 | 50.0% | 0.88 | -49.0 | -447.3 | +398.3 | -392.0 | 3/4 |
| SOL | 11 | 54.5% | 0.71 | -26.7 | -80.1 | +53.4 | -294.0 | 2/3 |
| XRP | 13 | 38.5% | 0.49 | -68.8 | -135.2 | +66.4 | -894.0 | 4/4 |
| AVAX | 9 | 33.3% | 0.2 | -268.6 | -338.9 | +70.3 | -2417.0 | 3/4 |
| LINK | 8 | 62.5% | 1.13 | 16.1 | -134.8 | +150.9 | 129.0 | 2/4 |
| DOGE | 14 | 42.9% | 0.35 | -108.9 | -147.6 | +38.7 | -1524.0 | 4/4 |
| ADA | 18 | 44.4% | 0.58 | -91.8 | -158.7 | +66.9 | -1652.0 | 0/3 |
| DEXE | 1 | 0.0% | 0.0 | -283.0 | -283.0 | +0.0 | -283.0 | 2/3 |
| BANK | 5 | 80.0% | 3.67 | 196.8 | -61.0 | +257.8 | 984.0 | 2/3 |
| BNB | 10 | 30.0% | 0.15 | -98.5 | -108.7 | +10.2 | -985.0 | 3/4 |
| SUI | 14 | 14.3% | 0.01 | -356.3 | -338.8 | -17.5 | -4988.0 | 2/3 |
| HBAR | 12 | 33.3% | 0.31 | -128.2 | -159.3 | +31.1 | -1538.0 | 3/4 |
| LTC | 9 | 33.3% | 0.28 | -139.9 | -128.4 | -11.5 | -1259.0 | 2/3 |
| BCH | 8 | 25.0% | 0.34 | -175.2 | -192.8 | +17.6 | -1402.0 | 1/4 |
| DOT | 12 | 8.3% | 0.05 | -312.7 | -183.2 | -129.5 | -3752.0 | 1/4 |
| 1000PEPE | 12 | 58.3% | 2.25 | 141.7 | -84.5 | +226.2 | 1700.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
