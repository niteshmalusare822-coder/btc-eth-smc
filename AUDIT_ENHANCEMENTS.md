# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 685
- **Pooled Edge (INR):** -24.0
- **Standard Error:** 18.4
- **Sigma (Z-Score):** -1.31
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -80318.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 39 | 38.5% | 0.26 | -406.8 | -219.4 | -187.4 | -15867.0 | 1/4 |
| ETH | 48 | 37.5% | 0.42 | -337.6 | -186.1 | -151.5 | -16207.0 | 2/4 |
| SOL | 44 | 40.9% | 0.53 | -104.7 | -53.5 | -51.2 | -4608.0 | 0/4 |
| XRP | 42 | 47.6% | 0.64 | -88.1 | -46.6 | -41.5 | -3699.0 | 2/4 |
| AVAX | 39 | 51.3% | 0.79 | -60.5 | -54.3 | -6.2 | -2360.0 | 2/4 |
| LINK | 35 | 42.9% | 0.52 | -138.3 | -63.6 | -74.7 | -4842.0 | 3/4 |
| DOGE | 39 | 46.2% | 0.69 | -80.0 | -32.9 | -47.1 | -3119.0 | 1/4 |
| ADA | 45 | 57.8% | 0.71 | -71.2 | -48.1 | -23.1 | -3204.0 | 1/4 |
| DEXE | 23 | 43.5% | 0.33 | -203.7 | -68.5 | -135.2 | -4685.0 | 3/4 |
| BANK | 34 | 50.0% | 1.08 | 12.5 | -61.7 | +74.2 | 425.0 | 3/4 |
| BNB | 50 | 50.0% | 0.62 | -54.8 | -55.4 | +0.6 | -2740.0 | 2/4 |
| SUI | 44 | 47.7% | 0.62 | -116.8 | -74.1 | -42.7 | -5138.0 | 0/4 |
| HBAR | 32 | 50.0% | 1.02 | 4.3 | -57.9 | +62.2 | 138.0 | 2/4 |
| LTC | 47 | 44.7% | 1.14 | 25.3 | -67.6 | +92.9 | 1189.0 | 3/4 |
| BCH | 38 | 23.7% | 0.34 | -247.9 | -71.4 | -176.5 | -9420.0 | 1/4 |
| DOT | 42 | 40.5% | 0.69 | -90.2 | -45.2 | -45.0 | -3788.0 | 2/4 |
| 1000PEPE | 44 | 50.0% | 0.81 | -54.4 | -51.5 | -2.9 | -2393.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
