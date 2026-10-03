# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 694
- **Pooled Edge (INR):** -27.2
- **Standard Error:** 18.7
- **Sigma (Z-Score):** -1.46
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -87654.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 41 | 39.0% | 0.28 | -383.1 | -190.6 | -192.5 | -15707.0 | 1/4 |
| ETH | 51 | 37.3% | 0.42 | -338.2 | -159.9 | -178.3 | -17246.0 | 1/4 |
| SOL | 44 | 40.9% | 0.54 | -101.3 | -58.8 | -42.5 | -4456.0 | 0/4 |
| XRP | 44 | 47.7% | 0.64 | -92.5 | -47.6 | -44.9 | -4070.0 | 2/4 |
| AVAX | 35 | 48.6% | 0.69 | -98.0 | -58.1 | -39.9 | -3430.0 | 2/4 |
| LINK | 35 | 40.0% | 0.49 | -152.7 | -65.8 | -86.9 | -5343.0 | 3/4 |
| DOGE | 40 | 47.5% | 0.7 | -73.3 | -36.2 | -37.1 | -2933.0 | 1/4 |
| ADA | 45 | 60.0% | 0.74 | -63.1 | -65.7 | +2.6 | -2840.0 | 1/4 |
| DEXE | 25 | 48.0% | 0.4 | -168.2 | -66.6 | -101.6 | -4204.0 | 2/4 |
| BANK | 31 | 45.2% | 0.95 | -9.5 | -70.4 | +60.9 | -294.0 | 3/4 |
| BNB | 51 | 47.1% | 0.6 | -56.5 | -61.1 | +4.6 | -2881.0 | 2/4 |
| SUI | 43 | 46.5% | 0.57 | -136.6 | -70.9 | -65.7 | -5875.0 | 1/4 |
| HBAR | 33 | 51.5% | 1.06 | 14.3 | -53.9 | +68.2 | 472.0 | 2/4 |
| LTC | 51 | 41.2% | 0.87 | -25.7 | -53.1 | +27.4 | -1311.0 | 2/4 |
| BCH | 37 | 18.9% | 0.25 | -308.6 | -71.1 | -237.5 | -11420.0 | 0/4 |
| DOT | 44 | 45.5% | 0.68 | -89.4 | -50.2 | -39.2 | -3933.0 | 3/4 |
| 1000PEPE | 44 | 50.0% | 0.82 | -49.6 | -66.8 | +17.2 | -2183.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
