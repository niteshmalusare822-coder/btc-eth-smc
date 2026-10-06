# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 17
- **Total Trades Pooled:** 583
- **Pooled Edge (INR):** 54.9
- **Standard Error:** 6.5
- **Sigma (Z-Score):** 8.41
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -43258.0

## Verdict
> Pooled edge is positive and outside the noise band. This is worth walk-forward and sensitivity confirmation before anything is called an edge.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC | 12 | 41.7% | 0.35 | -683.6 | -449.3 | -234.3 | -8203.0 | 2/4 |
| ETH | 19 | 63.2% | 0.99 | -8.7 | -551.2 | +542.5 | -166.0 | 2/4 |
| SOL | 25 | 52.0% | 0.87 | -28.4 | -56.6 | +28.2 | -709.0 | 3/4 |
| XRP | 28 | 35.7% | 0.44 | -119.8 | -120.8 | +1.0 | -3355.0 | 1/4 |
| AVAX | 49 | 46.9% | 0.54 | -137.8 | -124.2 | -13.6 | -6752.0 | 3/4 |
| LINK | 41 | 48.8% | 0.73 | -73.4 | -105.9 | +32.5 | -3010.0 | 3/4 |
| DOGE | 33 | 48.5% | 2.04 | 143.9 | -80.2 | +224.1 | 4749.0 | 4/4 |
| ADA | 49 | 36.7% | 0.75 | -50.8 | -129.9 | +79.1 | -2490.0 | 3/4 |
| DEXE | 21 | 71.4% | 1.07 | 15.9 | -85.9 | +101.8 | 333.0 | 4/4 |
| BANK | 36 | 44.4% | 1.54 | 71.5 | -109.7 | +181.2 | 2575.0 | 3/4 |
| BNB | 7 | 71.4% | 5.74 | 180.3 | -102.7 | +283.0 | 1262.0 | 3/4 |
| SUI | 57 | 36.8% | 0.56 | -110.1 | -109.4 | -0.7 | -6273.0 | 4/4 |
| HBAR | 39 | 41.0% | 1.72 | 121.5 | -131.3 | +252.8 | 4739.0 | 4/4 |
| LTC | 36 | 38.9% | 0.95 | -10.8 | -94.6 | +83.8 | -390.0 | 3/4 |
| BCH | 41 | 31.7% | 0.19 | -287.4 | -122.1 | -165.3 | -11783.0 | 4/4 |
| DOT | 40 | 37.5% | 0.44 | -175.2 | -116.4 | -58.8 | -7008.0 | 3/4 |
| 1000PEPE | 50 | 38.0% | 0.59 | -135.5 | -119.2 | -16.3 | -6777.0 | 4/4 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
