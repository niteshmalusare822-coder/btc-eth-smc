"""Research harness for independent non-SMC strategies.

First strategy: breakout + volume.

It reuses the existing execution/risk engine from backtest.py, so fees,
slippage, sizing, targets and stop management stay identical to the existing
measurement framework. It does NOT alter SMC logic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

import numpy as np

import backtest as B
import data as D
from breakout_volume import DEFAULT_PARAMS, signals


@dataclass
class LabConfig:
    bars: int = 4000
    is_frac: float = 0.60
    warmup: int = 100
    max_hold: int = 60
    max_cost_in_r: float = 0.75
    position_mode: str = "B"
    max_concurrent: int = 2
    cooldown_bars: int = 3
    matched_seeds: int = 100


def _trade_cfg(c: dict) -> dict:
    return {
        **B.DEFAULT_CFG,
        "max_hold": int(c["max_hold"]),
        "max_cost_in_r": float(c["max_cost_in_r"]),
        "position_mode": c["position_mode"],
        "max_concurrent": int(c["max_concurrent"]),
        "cooldown_bars": int(c["cooldown_bars"]),
        "entry_model": "next_open",
    }


def _run_signals(symbol, df, sig, lo, hi, cfg):
    """Execute strategy signals in one chronological slice."""
    trades = []
    rejects = {}
    open_until = {"bull": -1, "bear": -1}
    open_slots = []
    last_signal = -10**9

    def reject(why):
        rejects[why] = rejects.get(why, 0) + 1

    for i in range(max(lo, 1), hi):
        if not bool(sig["signal"].iat[i]):
            continue

        if i - last_signal <= cfg["cooldown_bars"]:
            reject("cooldown")
            continue

        side = sig["side"].iat[i]
        level = float(sig["level"].iat[i])
        atr_value = float(sig["atr"].iat[i])

        if (
            side not in ("bull", "bear")
            or not np.isfinite(level)
            or not np.isfinite(atr_value)
            or atr_value <= 0
        ):
            reject("invalid_signal")
            continue

        mode = cfg["position_mode"]
        if mode == "B":
            if i <= open_until[side]:
                reject("position_overlap")
                continue
        else:
            open_slots = [x for x in open_slots if x >= i]
            if len(open_slots) >= cfg["max_concurrent"]:
                reject("position_overlap")
                continue

        stop_dist = float(cfg["stop_atr"]) * atr_value
        stop = level - stop_dist if side == "bull" else level + stop_dist

        tr, why = B._open_trade(
            symbol,
            df,
            i,
            side,
            level,
            stop,
            atr_value,
            _trade_cfg(cfg),
            5,
            bias="BREAKOUT",
            setup="VOLUME_CONFIRMED",
            trigger="CLOSE_BREAKOUT",
            arm="breakout_volume",
            entry_reason=(
                f"5M {'bullish' if side == 'bull' else 'bearish'} breakout "
                f"of {level:.8g} with volume "
                f"{sig['volume_ratio'].iat[i]:.2f}x prior median"
            ),
            flags={"breakout": True, "volume_confirmed": True},
        )

        last_signal = i

        if tr:
            trades.append(tr)
            if mode == "B":
                open_until[side] = tr["exit_i"]
            else:
                open_slots.append(tr["exit_i"])
        else:
            reject(why)

    return trades, rejects


def _matched_random(symbol, df, source_trades, cfg, seeds):
    """Random-side null using exact breakout timestamps and stop widths."""
    results = []

    for seed in range(1, seeds + 1):
        rng = np.random.default_rng(seed)
        rows = []
        open_until = {"bull": -1, "bear": -1}

        for t in sorted(source_trades, key=lambda x: x["i"]):
            i = int(t["i"])
            side = "bull" if rng.random() < 0.5 else "bear"

            if i <= open_until[side]:
                continue

            level = float(t["signal_level"])
            dist = abs(float(t["entry"]) - float(t["sl"]))

            # Preserve the source trade's stop width; only direction changes.
            stop = level - dist if side == "bull" else level + dist

            tr, _ = B._open_trade(
                symbol,
                df,
                i,
                side,
                level,
                stop,
                dist,
                _trade_cfg(cfg),
                5,
                bias="RANDOM_MATCHED",
                setup="matched",
                trigger="coin_flip",
                arm="matched_random_breakout",
            )

            if tr:
                rows.append(tr)
                open_until[side] = tr["exit_i"]

        results.append(B.metrics(rows, "MATCHED_RANDOM_BREAKOUT"))

    return results


def _summary(rows):
    return B.metrics(rows, "BREAKOUT_VOLUME")


def run_symbol(symbol: str, cfg: LabConfig, params: dict | None = None):
    frames, meta = D.load_mtf(symbol.upper(), cfg.bars)

    if frames is None:
        return {
            "symbol": symbol.upper(),
            "error": (meta or {}).get("error", "no data"),
        }

    df = frames["5m"].reset_index(drop=True)
    p = {**DEFAULT_PARAMS, **(params or {})}
    sig = signals(df, p)

    n = len(df)
    split = int(n * cfg.is_frac)
    run_cfg = {**p, **asdict(cfg)}

    is_trades, is_rej = _run_signals(
        symbol.upper(), df, sig, cfg.warmup, split, run_cfg
    )
    oos_trades, oos_rej = _run_signals(
        symbol.upper(), df, sig, split, n, run_cfg
    )

    matched = _matched_random(
        symbol.upper(), df, oos_trades, run_cfg, cfg.matched_seeds
    )

    exps = [
        m.get("expectancy_inr")
        for m in matched
        if m.get("trades", 0) > 0
        and m.get("expectancy_inr") is not None
    ]

    oos = _summary(oos_trades)
    random_mean = float(np.mean(exps)) if exps else None
    random_std = float(np.std(exps, ddof=1)) if len(exps) > 1 else None

    return {
        "strategy": "breakout_volume",
        "symbol": symbol.upper(),
        "data_bars_5m": n,
        "split": {
            "warmup": cfg.warmup,
            "is_bars": max(split - cfg.warmup, 0),
            "oos_bars": max(n - split, 0),
            "is_frac": cfg.is_frac,
        },
        "params": p,
        "execution": {
            k: v
            for k, v in asdict(cfg).items()
            if k not in ("bars", "is_frac", "warmup", "matched_seeds")
        },
        "in_sample": _summary(is_trades),
        "out_of_sample": oos,
        "matched_random": {
            "seeds": len(exps),
            "mean_expectancy_inr": (
                round(random_mean, 2) if random_mean is not None else None
            ),
            "std_expectancy_inr": (
                round(random_std, 2) if random_std is not None else None
            ),
            "difference_inr": (
                round(
                    float(oos.get("expectancy_inr") - random_mean),
                    2,
                )
                if random_mean is not None
                and oos.get("expectancy_inr") is not None
                else None
            ),
        },
        "rejections": {
            "in_sample": is_rej,
            "out_of_sample": oos_rej,
        },
        "note": (
            "OOS result is descriptive only until sample size and "
            "walk-forward stability are checked."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*", default=["BTC", "ETH"])
    ap.add_argument("--bars", type=int, default=4000)
    ap.add_argument("--lookback", type=int, default=20)
    ap.add_argument("--volume-factor", type=float, default=1.5)
    ap.add_argument("--stop-atr", type=float, default=1.0)
    ap.add_argument("--matched-seeds", type=int, default=100)
    args = ap.parse_args()

    cfg = LabConfig(
        bars=args.bars,
        matched_seeds=args.matched_seeds,
    )
    params = {
        "lookback": args.lookback,
        "volume_factor": args.volume_factor,
        "stop_atr": args.stop_atr,
    }

    for symbol in args.symbols:
        print(
            json.dumps(
                run_symbol(symbol, cfg, params),
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
