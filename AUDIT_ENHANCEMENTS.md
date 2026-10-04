# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 175
- **Pooled Edge (INR):** 56.2
- **Standard Error:** 16.6
- **Sigma (Z-Score):** 3.39
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -20285.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 3 | 33.3% | 0.38 | -424.0 | -626.3 | +202.3 | -1272.0 | 2/3 |
| ETH | 11 | 45.5% | 0.79 | -94.6 | -469.7 | +375.1 | -1041.0 | 3/4 |
| SOL | 11 | 54.5% | 0.92 | -8.1 | -66.0 | +57.9 | -89.0 | 2/3 |
| XRP | 13 | 30.8% | 0.53 | -75.9 | -160.1 | +84.2 | -987.0 | 4/4 |
| AVAX | 9 | 22.2% | 0.33 | -258.6 | -398.5 | +139.9 | -2327.0 | 2/4 |
| LINK | 8 | 75.0% | 2.39 | 108.8 | -87.6 | +196.4 | 870.0 | 3/4 |
| DOGE | 15 | 33.3% | 0.27 | -142.7 | -186.1 | +43.4 | -2141.0 | 4/4 |
| ADA | 19 | 52.6% | 0.77 | -42.7 | -128.8 | +86.1 | -811.0 | 1/3 |
| DEXE | 2 | 100.0% | None | 101.5 | -23.5 | +125.0 | 203.0 | 2/3 |
| BANK | 5 | 80.0% | 3.22 | 182.4 | -84.9 | +267.3 | 912.0 | 2/3 |
| BNB | 12 | 25.0% | 0.2 | -102.5 | -118.5 | +16.0 | -1230.0 | 3/4 |
| SUI | 13 | 23.1% | 0.21 | -285.7 | -328.6 | +42.9 | -3714.0 | 3/3 |
| HBAR | 12 | 33.3% | 0.45 | -113.1 | -169.0 | +55.9 | -1357.0 | 4/4 |
| LTC | 9 | 33.3% | 0.25 | -161.6 | -141.6 | -20.0 | -1454.0 | 2/3 |
| BCH | 9 | 33.3% | 0.35 | -162.2 | -147.7 | -14.5 | -1460.0 | 1/4 |
| DOT | 12 | 8.3% | 0.03 | -352.3 | -205.6 | -146.7 | -4228.0 | 1/4 |
| 1000PEPE | 12 | 33.3% | 0.94 | -13.2 | -173.0 | +159.8 | -159.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
