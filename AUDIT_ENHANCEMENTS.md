# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 694
- **Pooled Edge (INR):** -13.3
- **Standard Error:** 18.7
- **Sigma (Z-Score):** -0.71
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -73206.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 40 | 37.5% | 0.24 | -425.3 | -190.9 | -234.4 | -17012.0 | 1/4 |
| ETH | 48 | 39.6% | 0.42 | -329.6 | -187.8 | -141.8 | -15822.0 | 2/4 |
| SOL | 45 | 44.4% | 0.6 | -85.9 | -57.7 | -28.2 | -3867.0 | 0/4 |
| XRP | 43 | 48.8% | 0.66 | -79.8 | -55.6 | -24.2 | -3431.0 | 2/4 |
| AVAX | 39 | 53.8% | 0.83 | -47.7 | -55.5 | +7.8 | -1860.0 | 2/4 |
| LINK | 36 | 44.4% | 0.55 | -124.8 | -59.1 | -65.7 | -4494.0 | 3/4 |
| DOGE | 39 | 48.7% | 0.74 | -65.0 | -35.6 | -29.4 | -2534.0 | 1/4 |
| ADA | 45 | 57.8% | 0.71 | -69.8 | -48.0 | -21.8 | -3141.0 | 1/4 |
| DEXE | 23 | 43.5% | 0.33 | -203.7 | -68.5 | -135.2 | -4685.0 | 1/4 |
| BANK | 36 | 47.2% | 1.25 | 35.7 | -71.1 | +106.8 | 1286.0 | 3/4 |
| BNB | 50 | 48.0% | 0.58 | -60.2 | -55.6 | -4.6 | -3010.0 | 2/4 |
| SUI | 44 | 47.7% | 0.59 | -123.7 | -72.8 | -50.9 | -5442.0 | 0/4 |
| HBAR | 33 | 51.5% | 1.17 | 40.8 | -55.2 | +96.0 | 1345.0 | 2/4 |
| LTC | 47 | 44.7% | 1.13 | 23.5 | -67.3 | +90.8 | 1104.0 | 3/4 |
| BCH | 38 | 26.3% | 0.42 | -213.6 | -78.4 | -135.2 | -8117.0 | 1/4 |
| DOT | 43 | 44.2% | 0.77 | -66.4 | -48.0 | -18.4 | -2854.0 | 2/4 |
| 1000PEPE | 45 | 51.1% | 0.94 | -14.9 | -59.4 | +44.5 | -672.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
