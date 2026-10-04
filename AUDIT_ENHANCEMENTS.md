# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-02 (Auto-Generated via collect.py)  
**Objective:** Maximize win rate, reduce false positives, optimize profit factors based on live/pooled OOS data.

## Executive Summary & Latest Pooled Metrics
- **Total Symbols Usable:** 9
- **Total Trades Pooled:** 38
- **Pooled Edge (INR):** -75.4
- **Standard Error:** 7.9
- **Sigma (Z-Score):** -9.56
- **Significant at 95%:** True
- **Pooled Net PnL (INR):** -755.0

## Verdict
> Pooled edge is significantly NEGATIVE. The rules lose to a coin flip on matched entries. Stop tuning and reconsider the premise.

## Per-Symbol Performance Table (Latest Run)
| Symbol | Trades | Win% | PF | Expectancy (INR) | Random Mean | Edge | Net PnL (INR) | WF Folds |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| XRP | 1 | 0.0% | 0.0 | -138.0 | -138.0 | +0.0 | -138.0 | 1/2 |
| AVAX | 5 | 40.0% | 0.35 | -388.2 | -145.8 | -242.4 | -1941.0 | 2/2 |
| LINK | 1 | 100.0% | None | 443.0 | 26.9 | +416.1 | 443.0 | 1/1 |
| DOGE | 4 | 25.0% | 0.37 | -126.8 | -110.5 | -16.3 | -507.0 | 0/1 |
| ADA | 7 | 71.4% | 2.06 | 301.9 | -78.2 | +380.1 | 2113.0 | 2/2 |
| BANK | 1 | 0.0% | 0.0 | -137.0 | -137.0 | +0.0 | -137.0 | 1/1 |
| SUI | 8 | 62.5% | 2.96 | 115.4 | -74.6 | +190.0 | 923.0 | 1/2 |
| HBAR | 1 | 100.0% | None | 54.0 | -14.4 | +68.4 | 54.0 | 1/1 |
| LTC | 1 | 0.0% | 0.0 | -163.0 | -163.0 | +0.0 | -163.0 | 0/1 |
| BCH | 2 | 0.0% | 0.0 | -266.0 | -166.7 | -99.3 | -532.0 | 0/1 |
| DOT | 5 | 40.0% | 0.2 | -286.2 | -122.4 | -163.8 | -1431.0 | 1/1 |
| 1000PEPE | 5 | 60.0% | 1.36 | 24.6 | -103.1 | +127.7 | 123.0 | 1/2 |

---
*Note: This report is dynamically updated by the automated daily GitHub Action using `collect.py`.*
