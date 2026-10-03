# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 679
- **Pooled Edge (INR):** -33.1
- **Standard Error:** 18.9
- **Sigma (Z-Score):** -1.75
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -88073.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 38 | 36.8% | 0.23 | -439.7 | -217.4 | -222.3 | -16709.0 | 1/4 |
| ETH | 50 | 36.0% | 0.38 | -368.2 | -177.9 | -190.3 | -18408.0 | 1/4 |
| SOL | 43 | 41.9% | 0.57 | -92.0 | -54.7 | -37.3 | -3957.0 | 1/4 |
| XRP | 43 | 51.2% | 0.64 | -87.7 | -59.4 | -28.3 | -3770.0 | 0/4 |
| AVAX | 32 | 46.9% | 0.66 | -115.8 | -65.7 | -50.1 | -3705.0 | 2/4 |
| LINK | 32 | 37.5% | 0.44 | -166.5 | -56.3 | -110.2 | -5328.0 | 2/4 |
| DOGE | 41 | 48.8% | 0.74 | -65.0 | -33.2 | -31.8 | -2666.0 | 1/4 |
| ADA | 44 | 61.4% | 0.82 | -40.9 | -50.3 | +9.4 | -1801.0 | 1/4 |
| DEXE | 25 | 48.0% | 0.4 | -168.2 | -66.6 | -101.6 | -4204.0 | 1/4 |
| BANK | 31 | 48.4% | 0.95 | -8.7 | -70.7 | +62.0 | -269.0 | 2/4 |
| BNB | 50 | 48.0% | 0.55 | -63.4 | -55.4 | -8.0 | -3169.0 | 2/4 |
| SUI | 43 | 46.5% | 0.57 | -135.6 | -71.1 | -64.5 | -5831.0 | 3/4 |
| HBAR | 33 | 48.5% | 0.99 | -1.3 | -49.7 | +48.4 | -44.0 | 2/4 |
| LTC | 51 | 41.2% | 0.87 | -25.7 | -53.1 | +27.4 | -1311.0 | 4/4 |
| BCH | 36 | 19.4% | 0.25 | -317.1 | -81.9 | -235.2 | -11417.0 | 2/4 |
| DOT | 45 | 46.7% | 0.74 | -72.0 | -51.8 | -20.2 | -3242.0 | 2/4 |
| 1000PEPE | 42 | 50.0% | 0.81 | -53.4 | -62.2 | +8.8 | -2242.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
