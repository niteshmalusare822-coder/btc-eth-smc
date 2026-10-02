# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 685
- **Pooled Edge (INR):** -18.0
- **Standard Error:** 18.7
- **Sigma (Z-Score):** -0.96
- **Significant at 95%:** False
- **Pooled Net PnL (INR):** -79145.0

## Verdict
> NOT DECIDABLE — the pooled edge is inside the noise band. More trades, not different rules.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 39 | 38.5% | 0.26 | -405.1 | -219.4 | -185.7 | -15799.0 | 1/4 |
| ETH | 48 | 37.5% | 0.41 | -343.3 | -169.8 | -173.5 | -16480.0 | 2/4 |
| SOL | 44 | 43.2% | 0.56 | -96.0 | -55.1 | -40.9 | -4224.0 | 0/4 |
| XRP | 42 | 50.0% | 0.67 | -79.1 | -59.7 | -19.4 | -3322.0 | 2/4 |
| AVAX | 38 | 52.6% | 0.8 | -59.9 | -57.1 | -2.8 | -2276.0 | 2/4 |
| LINK | 35 | 42.9% | 0.53 | -135.6 | -64.1 | -71.5 | -4747.0 | 3/4 |
| DOGE | 39 | 48.7% | 0.7 | -75.3 | -35.6 | -39.7 | -2938.0 | 1/4 |
| ADA | 46 | 58.7% | 0.74 | -61.0 | -47.0 | -14.0 | -2806.0 | 1/4 |
| DEXE | 24 | 45.8% | 0.38 | -181.0 | -67.8 | -113.2 | -4344.0 | 2/4 |
| BANK | 33 | 48.5% | 1.07 | 12.2 | -69.8 | +82.0 | 402.0 | 3/4 |
| BNB | 50 | 50.0% | 0.62 | -53.9 | -56.8 | +2.9 | -2694.0 | 2/4 |
| SUI | 44 | 47.7% | 0.59 | -126.1 | -72.6 | -53.5 | -5548.0 | 0/4 |
| HBAR | 32 | 50.0% | 1.02 | 4.3 | -57.9 | +62.2 | 138.0 | 2/4 |
| LTC | 47 | 44.7% | 1.11 | 19.9 | -66.7 | +86.6 | 934.0 | 3/4 |
| BCH | 37 | 24.3% | 0.34 | -248.9 | -85.0 | -163.9 | -9208.0 | 1/4 |
| DOT | 42 | 42.9% | 0.69 | -92.0 | -50.0 | -42.0 | -3863.0 | 4/4 |
| 1000PEPE | 45 | 48.9% | 0.81 | -52.7 | -46.7 | -6.0 | -2370.0 | 2/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
