# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 577
- **Pooled Edge (INR):** 64.1
- **Standard Error:** 6.7
- **Sigma (Z-Score):** 9.57
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -32579.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 11 | 45.5% | 0.4 | -607.7 | -449.8 | -157.9 | -6685.0 | 2/4 |
| ETH | 19 | 63.2% | 0.95 | -31.3 | -545.4 | +514.1 | -595.0 | 2/4 |
| SOL | 25 | 52.0% | 0.85 | -32.2 | -46.3 | +14.1 | -804.0 | 3/4 |
| XRP | 29 | 31.0% | 0.42 | -114.7 | -110.4 | -4.3 | -3327.0 | 2/4 |
| AVAX | 47 | 44.7% | 0.48 | -163.1 | -124.7 | -38.4 | -7666.0 | 3/4 |
| LINK | 41 | 46.3% | 0.7 | -83.0 | -106.4 | +23.4 | -3404.0 | 3/4 |
| DOGE | 32 | 46.9% | 2.07 | 141.8 | -86.4 | +228.2 | 4536.0 | 4/4 |
| ADA | 49 | 36.7% | 0.79 | -39.7 | -113.5 | +73.8 | -1947.0 | 3/4 |
| DEXE | 20 | 70.0% | 1.05 | 12.2 | -86.7 | +98.9 | 243.0 | 4/4 |
| BANK | 36 | 47.2% | 1.75 | 95.6 | -106.1 | +201.7 | 3441.0 | 3/4 |
| BNB | 8 | 62.5% | 3.4 | 134.9 | -103.6 | +238.5 | 1079.0 | 4/4 |
| SUI | 58 | 36.2% | 0.54 | -114.8 | -109.4 | -5.4 | -6656.0 | 4/4 |
| HBAR | 37 | 40.5% | 1.73 | 130.3 | -135.6 | +265.9 | 4821.0 | 4/4 |
| LTC | 38 | 39.5% | 0.96 | -8.6 | -88.5 | +79.9 | -326.0 | 3/4 |
| BCH | 39 | 35.9% | 0.54 | -89.9 | -122.8 | +32.9 | -3506.0 | 4/4 |
| DOT | 40 | 37.5% | 0.44 | -176.8 | -117.2 | -59.6 | -7073.0 | 3/4 |
| 1000PEPE | 48 | 41.7% | 0.68 | -98.1 | -109.4 | +11.3 | -4710.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
