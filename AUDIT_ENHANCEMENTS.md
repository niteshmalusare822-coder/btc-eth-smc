# SMC MTF Strategy: Deep-Dive Audit & Production Enhancements (Auto-Updated)

**Author:** Elite Quant Algorithmic Trader | SMC Specialist  
**Date:** 2026-10-07 (engineering update; next collect run refreshes metrics)  
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


## 2026-10-07 Integrity & Profitability Upgrade

The audit is now explicitly centered on the **production SMC_MTF arm** versus its matched-random baseline. The collector no longer summarizes the 15M-only SMC arm while labeling the result as SMC_MTF.

### Production safety contract

- Canonical risk cap: **Rs.700**, inclusive of fees and slippage.
- Canonical max cost gate: **0.75R** unless deliberately overridden by deployment environment.
- Canonical TP ladder: **1.5R / 2R / 3R**.
- Live and backtest pass the same per-bar 5M quality value into the shared decision function.
- The optional 5M quality gate is tested out of sample rather than silently enabled in production.
- Research pooling no longer forces a separate `require_retest=True` configuration.

### Profitability gate

The latest stored pooled result is still **not profitable**: pooled net P&L is **-Rs.43,258**. The positive matched-random gap (+Rs.54.9/trade) therefore must not be treated as proof of a profitable strategy.

A production promotion requires all of these together: positive OOS net P&L, profit factor above 1, sufficient OOS trades, walk-forward stability, non-fragile sensitivity, and live/backtest parity checks.

### Research direction

The OOS sensitivity suite now includes the optional 5M quality gate and liquidity-sweep requirement alongside the existing entry/stop geometry tests. These experiments are evidence-building only; a historical improvement does not automatically become a live rule.

---
*Integrity update authored 2026-10-07. Automated metric refresh remains owned by `collect.py`.*
