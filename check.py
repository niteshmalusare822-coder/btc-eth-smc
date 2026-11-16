#!/usr/bin/env python3
"""
check.py — backtest vs live parity check.

For every backtest trade that exited yesterday (IST), cut the data at the
signal bar exactly as live would see it (last LIVE_BARS 5m bars, only closed
15m / 4h bars), run the same decide() and see if live would have produced
the same signal.

Usage:
    python3 check.py                  # default symbols DOT,ETH,ADA
    python3 check.py BTC,ETH,SOL
    python3 check.py ALL              # every symbol in PAIR_MAP (slow)
"""

from __future__ import annotations

import sys

import pandas as pd

import backtest as B
import collect as C
import data as D
import mtf_engine as M
import research_data as RD

LIVE_BARS = 1200


def replay_symbol(sym):
    if sym not in D.PAIR_MAP:
        C.register(sym, f"B-{sym}_USDT")

    cfg = {**B.DEFAULT_CFG, "matched_seeds": 20}
    bars = D.clamp_bars(10000)

    r = C.run_symbol(sym, bars, cfg)
    if r.get("error"):
        print(f"{sym:8s} FAILED: {r['error']}")
        return 0, 0

    trades = C._t1_trades(r["_trades"])
    if not trades:
        print(f"{sym:8s} no T-1 trades")
        return 0, 0

    frames, _ = RD.load_research(sym, bars)
    df5, df15, df4 = frames["5m"], frames["15m"], frames["4h"]
    ts5, ts15, ts4 = M._ts(df5["ts"]), M._ts(df15["ts"]), M._ts(df4["ts"])

    agree = disagree = 0
    for t in trades:
        sig = M._ts(pd.Series([t["signal_ts"]])).iat[0]
        end = sig + pd.Timedelta(minutes=5)

        d5 = df5[ts5 <= sig].tail(LIVE_BARS).reset_index(drop=True)
        d15 = df15[ts15 + pd.Timedelta(minutes=15) <= end].reset_index(drop=True)
        d4 = df4[ts4 + pd.Timedelta(hours=4) <= end].reset_index(drop=True)

        ctx = M.build_context(d5, d15, d4)
        i = len(d5) - 1
        action, setup, side, level, why = M.decide(
            ctx["bias"][i], ctx["trigger"][i], ctx["setups"],
            M._ts(d5["ts"]).iat[i], quality=bool(ctx["quality"][i]))

        ok = action == t["side"]
        agree += int(ok)
        disagree += int(not ok)
        note = "" if ok else f"  reason={why}"
        print(f"{sym:8s} {t['signal_ts']}  backtest={t['side']:4s}  "
              f"replay={action:8s}{note}")

    return agree, disagree


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "DOT,ETH,ADA"
    if arg.upper() == "ALL":
        symbols = list(D.PAIR_MAP)
    else:
        symbols = [s.strip().upper() for s in arg.split(",") if s.strip()]

    total_agree = total_disagree = 0
    for sym in symbols:
        try:
            a, d = replay_symbol(sym)
        except Exception as e:
            print(f"{sym:8s} ERROR: {e}")
            continue
        total_agree += a
        total_disagree += d

    print(f"\nagree={total_agree} disagree={total_disagree}")


if __name__ == "__main__":
    main()
