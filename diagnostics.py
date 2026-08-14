"""
diagnostics.py — why did the strategy not take that move?

The dashboard says NO TRADE. This module answers the follow-up question with
counted evidence instead of opinion: for every significant move in the history,
what did the strategy see at the moment the move began, and which gate stopped
it.

WHAT A MOVE IS
--------------
A significant move is a run where price travels at least `move_atr_mult` ATR in
one direction inside `move_window` bars, measured from a starting bar. Moves are
non-overlapping: once one is recorded the scan resumes after it ends. Using a
fixed percentage instead would flag hundreds of moves on a volatile asset and
none on a quiet one, which is why the threshold is ATR-relative.

WHAT A MISS IS NOT
------------------
Every profitable move is NOT a missed trade. A move only counts as a TRUE_MISS
if the strategy's own rules had a valid setup in the right direction before the
move started and something downstream still blocked it. If the rules never
produced a setup, that is the strategy being selective, not broken — it is
recorded as VALID_NO_TRADE with the specific gate named.

This distinction is the whole point. Counting all unrealised profit as "missed"
is how a filter gets loosened until nothing is left of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import mtf_engine as mtf

CFG = {
    "move_atr_mult": 3.0,     # how far price must travel to count as a move
    "move_window": 48,        # bars it may take (48 x 5m = 4 hours)
    "lookahead_gate": 0,      # bars BEFORE the move where the setup must exist
}

CLASSES = [
    "TRUE_MISS",              # valid setup, right direction, blocked downstream
    "SIGNAL_TAKEN",           # the strategy did fire here
    "VALID_NO_TRADE",         # rules produced nothing; selectivity working
    "WRONG_DIRECTION",        # setup existed but pointed the other way
    "SETUP_STALE",            # setup existed but had expired or been mitigated
]


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def find_significant_moves(df5, cfg=None):
    """Non-overlapping runs of at least move_atr_mult ATR within move_window.

    Measured forward from each candidate start using the maximum favourable
    excursion in each direction. This looks ahead ON PURPOSE — it is describing
    what the market did, not generating a signal. Nothing here feeds the
    strategy.
    """
    cfg = {**CFG, **(cfg or {})}
    atr = _atr(df5).to_numpy()
    hi = df5["high"].to_numpy()
    lo = df5["low"].to_numpy()
    cl = df5["close"].to_numpy()
    ts = mtf._ts(df5["ts"])
    n = len(df5)
    w = cfg["move_window"]

    moves = []
    i = 20
    while i < n - w - 1:
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        start = cl[i]
        up = hi[i + 1:i + 1 + w].max() - start
        dn = start - lo[i + 1:i + 1 + w].min()
        need = cfg["move_atr_mult"] * a

        if up >= need or dn >= need:
            side = "bull" if up >= dn else "bear"
            mfe = max(up, dn)
            end_i = min(i + w, n - 1)
            moves.append({
                "start_i": i, "end_i": end_i,
                "start_ts": str(ts.iat[i]), "end_ts": str(ts.iat[end_i]),
                "direction": "UP" if side == "bull" else "DOWN",
                "side": side,
                "start_price": round(float(start), 8),
                "mfe_price": round(float(mfe), 8),
                "move_pct": round(float(mfe / start * 100), 3),
                "mfe_atr": round(float(mfe / a), 2),
            })
            i = end_i + 1          # non-overlapping
        else:
            i += 1
    return moves


def classify_move(move, ctx, ts_all, taken_bars):
    """What the strategy saw at the bar the move began."""
    i = move["start_i"]
    if i >= len(ctx["bias"]):
        return "VALID_NO_TRADE", "OUT_OF_RANGE", {}

    ts = ts_all.iat[i]
    state = mtf.gate_state(ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts)

    if i in taken_bars:
        return "SIGNAL_TAKEN", "OK", state

    setups_now = mtf.active_setups_at(ctx["setups"], ts)
    right_way = [s for s in setups_now if s.side == move["side"]]

    if right_way and state["blocker"] in ("HTF_NEUTRAL", "NO_TRIGGER",
                                          "TRIGGER_WRONG_WAY"):
        # the rules DID find a valid zone pointing the right way, and a later
        # gate rejected it. This is the only category worth calling a miss.
        return "TRUE_MISS", state["blocker"], state

    if setups_now and not right_way:
        return "WRONG_DIRECTION", "SETUP_WRONG_WAY", state
    if state["blocker"] in ("SETUP_EXPIRED", "SETUP_MITIGATED"):
        return "SETUP_STALE", state["blocker"], state
    return "VALID_NO_TRADE", state["blocker"], state


def missed_move_report(symbol, df5, df15, df1h, taken_trades=None, cfg=None):
    """Per-symbol capture analysis."""
    cfg = {**CFG, **(cfg or {})}
    ctx = mtf.build_context(df5, df15, df1h)
    ts_all = mtf._ts(df5["ts"])
    taken_bars = {t["i"] for t in (taken_trades or [])}

    moves = find_significant_moves(df5, cfg)
    by_class = {c: 0 for c in CLASSES}
    blockers, examples = {}, []

    for mv in moves:
        cls, blocker, state = classify_move(mv, ctx, ts_all, taken_bars)
        by_class[cls] = by_class.get(cls, 0) + 1
        blockers[blocker] = blockers.get(blocker, 0) + 1
        if cls == "TRUE_MISS" and len(examples) < 10:
            examples.append({**mv, "blocker": blocker,
                             "blocker_text": mtf.BLOCKERS.get(blocker, blocker),
                             "state": state})

    total = len(moves)
    taken = by_class["SIGNAL_TAKEN"]
    missed = by_class["TRUE_MISS"]
    return {
        "symbol": symbol,
        "significant_moves": total,
        "signals_taken_on_moves": taken,
        "true_missed_signals": missed,
        "valid_no_trades": by_class["VALID_NO_TRADE"],
        "wrong_direction": by_class["WRONG_DIRECTION"],
        "setup_stale": by_class["SETUP_STALE"],
        "capture_rate_pct": round(taken / total * 100, 1) if total else None,
        "true_miss_rate_pct": round(missed / total * 100, 1) if total else None,
        "blockers": dict(sorted(blockers.items(), key=lambda kv: -kv[1])),
        "by_class": by_class,
        "examples": examples,
        "move_definition": f"{cfg['move_atr_mult']}x ATR within "
                           f"{cfg['move_window']} bars",
    }


def per_asset_stats(symbol, arm_metrics, trades):
    """One asset's line, computed from its own trades."""
    m = arm_metrics or {}
    return {
        "symbol": symbol,
        "trades": m.get("trades", 0),
        "wins": sum(1 for t in trades if t["net_inr"] > 0),
        "losses": sum(1 for t in trades if t["net_inr"] <= 0),
        "win_rate_pct": m.get("win_rate_pct"),
        "profit_factor": m.get("profit_factor"),
        "expectancy_inr": m.get("expectancy_inr"),
        "gross_pnl_inr": m.get("gross_pnl_inr"),
        "fees_inr": m.get("fees_paid_inr"),
        "slippage_inr": m.get("slippage_inr"),
        "funding_inr": m.get("funding_inr"),
        "net_pnl_inr": m.get("net_pnl_inr"),
        "max_drawdown_inr": m.get("max_drawdown_inr"),
        "avg_win_inr": m.get("avg_win_inr"),
        "avg_loss_inr": m.get("avg_loss_inr"),
        "median_cost_in_r": m.get("median_cost_in_r"),
    }


def portfolio_from_trades(all_trades):
    """Portfolio totals from the pooled trade list, chronologically ordered.

    NOT an average of per-asset statistics. Averaging win rates across assets
    with 5 and 500 trades produces a number that describes nothing, and
    averaging drawdowns hides the fact that losses can land on the same day.
    """
    if not all_trades:
        return {"trades": 0, "note": "no trades"}

    ts = sorted(all_trades, key=lambda t: t["entry_ts"])
    net = np.array([t["net_inr"] for t in ts], dtype=float)
    gross = np.array([t["gross_inr"] for t in ts], dtype=float)
    wins, losses = net[net > 0], net[net <= 0]
    gp, gl = float(wins.sum()), float(abs(losses.sum()))

    eq = np.cumsum(net)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))
    dd = float((peak[1:] - eq).max())

    costs = sum(t["fees_inr"] + t["slippage_inr"] + t["funding_inr"] for t in ts)
    return {
        "trades": len(ts),
        "symbols": sorted({t.get("symbol", "?") for t in ts}),
        "win_rate_pct": round(float((net > 0).mean() * 100), 1),
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
        "expectancy_inr": round(float(net.mean()), 1),
        "gross_pnl_inr": round(float(gross.sum()), 0),
        "total_costs_inr": round(float(costs), 0),
        "net_pnl_inr": round(float(net.sum()), 0),
        "max_drawdown_inr": round(dd, 0),
        "cost_share_of_gross_pct": (
            float(round(costs / abs(gross.sum()) * 100, 1))
            if gross.sum() != 0 else None),
        "note": "computed from pooled trade-level data, not averaged per asset",
    }
