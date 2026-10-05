# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 12
- **Total Trades Pooled:** 74
- **Pooled Edge (INR):** 26.0
- **Standard Error:** 12.8
- **Sigma (Z-Score):** 2.03
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -2770.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| ETH | 1 | 100.0% | None | 237.0 | -222.8 | +459.8 | 237.0 | 0/0 |
| SOL | 1 | 100.0% | None | 163.0 | -1.0 | +164.0 | 163.0 | 1/1 |
| XRP | 3 | 33.3% | 1.12 | 7.0 | -49.5 | +56.5 | 21.0 | 1/4 |
| AVAX | 8 | 50.0% | 0.45 | -263.2 | -118.5 | -144.7 | -2106.0 | 1/3 |
| LINK | 5 | 40.0% | 1.04 | 5.0 | -77.9 | +82.9 | 25.0 | 2/2 |
| DOGE | 6 | 33.3% | 0.69 | -29.3 | -104.3 | +75.0 | -176.0 | 0/2 |
| ADA | 7 | 71.4% | 1.87 | 266.6 | -86.2 | +352.8 | 1866.0 | 2/3 |
| BANK | 1 | 0.0% | 0.0 | -137.0 | -137.0 | +0.0 | -137.0 | 1/2 |
| SUI | 16 | 50.0% | 1.12 | 10.1 | -89.9 | +100.0 | 161.0 | 1/4 |
| HBAR | 4 | 50.0% | 0.93 | -6.0 | -33.6 | +27.6 | -24.0 | 2/3 |
| LTC | 3 | 0.0% | 0.0 | -182.3 | -182.3 | +0.0 | -547.0 | 1/4 |
| BCH | 6 | 0.0% | 0.0 | -211.3 | -140.3 | -71.0 | -1268.0 | 0/3 |
| DOT | 10 | 50.0% | 0.21 | -275.2 | -107.2 | -168.0 | -2752.0 | 1/4 |
| 1000PEPE | 7 | 57.1% | 2.42 | 154.7 | -59.9 | +214.6 | 1083.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
