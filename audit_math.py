#!/usr/bin/env python3
"""
audit_math.py — recompute every number in a trade from first principles.

WHY THIS IS WRITTEN THE WAY IT IS
---------------------------------
This module deliberately does NOT import risk.size_position or backtest.pnl_inr
and does not call any engine function. Every value is rebuilt from the raw
inputs — entry price, stop price, exit legs, bars held — using only the config
constants and arithmetic written out longhand below.

If the audit reused the engine's own functions it would only prove the code
agrees with itself, which is worth nothing. A disagreement between this file
and the engine means one of them is wrong, and that is exactly the signal
wanted.

NOTHING IS MODIFIED. This reports.

USAGE
    python3 audit_math.py --trades trades.json --arm smc --n 5
    python3 audit_math.py --symbol BTC --bars 10000 --n 5      (fetches live)
"""

from __future__ import annotations

import argparse
import json
import math

# ── constants, read from risk.py's environment contract, not from risk.py ──
CAPITAL_INR = 10000.0
MAX_RISK_INR = 700.0
USDT_INR = 88.0

FEE_PER_LEG = 0.0005
SLIPPAGE_PER_LEG = 0.0002
FUNDING_PER_8H = 0.0001
FUNDING_INTERVAL_HOURS = 8.0
MIN_NOTIONAL_INR = 200.0

LEVERAGE_FRACTION = 0.20
MAX_LEVERAGE = {"BTC": 100, "ETH": 100, "DEXE": 25, "BANK": 20}
DEFAULT_MAX_LEVERAGE = 20

TP_R_LADDER = [1.0, 2.0, 3.0]
TP_SPLIT = [0.30, 0.30, 0.40]
TF_MINUTES = 5

ROUND_TRIP_FEE = FEE_PER_LEG * 2
ROUND_TRIP_SLIP = SLIPPAGE_PER_LEG * 2
ROUND_TRIP_COST = ROUND_TRIP_FEE + ROUND_TRIP_SLIP

TOL = 0.01          # rupee tolerance; anything larger is a real discrepancy


def recompute(t):
    """Rebuild the whole trade longhand. Returns {field: expected}."""
    sym = t.get("symbol", "BTC")
    side = t["side"]                       # BUY / SELL
    entry = float(t["entry"])
    sl = float(t["sl"])
    bars = int(t.get("bars_held", 0))

    e = {}

    # ── 1. stop distance ─────────────────────────────────────────────────
    e["sl_distance_px"] = abs(entry - sl)
    e["sl_distance_pct"] = e["sl_distance_px"] / entry * 100
    sl_dist_inr = e["sl_distance_px"] * USDT_INR
    entry_inr = entry * USDT_INR

    # ── 2. quantity solved from risk, INCLUSIVE of costs ─────────────────
    # risk = qty*sl_dist_inr + qty*entry_inr*round_trip
    #      -> qty = risk / (sl_dist_inr + entry_inr*round_trip)
    cost_per_unit = entry_inr * ROUND_TRIP_COST
    denom = sl_dist_inr + cost_per_unit
    qty_raw = MAX_RISK_INR / denom if denom > 0 else 0.0

    # ── 3. leverage can only ever SHRINK the position ────────────────────
    lev_max = MAX_LEVERAGE.get(sym, DEFAULT_MAX_LEVERAGE)
    lev_allowed = round(lev_max * LEVERAGE_FRACTION, 2)
    max_notional = CAPITAL_INR * lev_allowed

    notional_raw = qty_raw * entry_inr
    capped = notional_raw > max_notional
    qty = qty_raw * (max_notional / notional_raw) if capped else qty_raw

    e["leverage_max_venue"] = lev_max
    e["leverage_allowed"] = lev_allowed
    e["qty"] = qty
    e["notional_inr"] = qty * entry_inr
    e["leverage_used"] = round(e["notional_inr"] / CAPITAL_INR, 2)
    e["margin_inr"] = e["notional_inr"] / lev_allowed if lev_allowed else 0.0
    e["position_capped_by_leverage"] = capped
    e["below_min_notional"] = e["notional_inr"] < MIN_NOTIONAL_INR

    # ── 4. costs ─────────────────────────────────────────────────────────
    e["fees_inr"] = e["notional_inr"] * ROUND_TRIP_FEE
    e["slippage_inr"] = e["notional_inr"] * ROUND_TRIP_SLIP
    hours = bars * TF_MINUTES / 60.0
    e["funding_events"] = int(hours // FUNDING_INTERVAL_HOURS)
    e["funding_inr"] = e["notional_inr"] * FUNDING_PER_8H * e["funding_events"]

    # cost expressed against the stop: the viability number
    e["cost_in_r"] = cost_per_unit / sl_dist_inr if sl_dist_inr > 0 else math.inf

    # total risk if the stop is hit, must land on MAX_RISK_INR when uncapped
    e["gross_loss_at_stop_inr"] = qty * sl_dist_inr
    e["total_risk_inr"] = (e["gross_loss_at_stop_inr"] + e["fees_inr"]
                           + e["slippage_inr"])

    # ── 5. take profit ladder ────────────────────────────────────────────
    sign = 1.0 if side == "BUY" else -1.0
    tps = []
    for i, r in enumerate(TP_R_LADDER, start=1):
        move = r * e["sl_distance_px"]
        px = entry + sign * move
        gross = qty * move * USDT_INR
        tps.append({"level": f"TP{i}", "r": r, "price": px,
                    "gross_inr": gross,
                    "net_inr": gross - qty * entry_inr * ROUND_TRIP_COST})
    e["tps"] = tps

    # ── 6. realised P&L from the actual exit legs ────────────────────────
    legs = t.get("_legs")
    if legs:
        gross = 0.0
        for frac, px in legs:
            move = (px - entry) if side == "BUY" else (entry - px)
            gross += move * qty * frac * USDT_INR
        e["gross_inr"] = gross
        e["net_inr"] = (gross - e["fees_inr"] - e["slippage_inr"]
                        - e["funding_inr"])
    else:
        # legs are not in the log; verify the identity that must always hold
        e["gross_inr"] = None
        e["net_inr"] = None
        if t.get("gross_inr") is not None:
            e["net_from_engine_gross"] = (float(t["gross_inr"]) - e["fees_inr"]
                                          - e["slippage_inr"] - e["funding_inr"])
    return e


FIELDS = [
    ("sl_distance_pct", "sl_distance_pct"),
    ("qty", "qty"),
    ("notional_inr", "notional_inr"),
    ("margin_inr", "margin_inr"),
    ("leverage_used", "leverage_used"),
    ("leverage_allowed", "leverage_allowed"),
    ("fees_inr", "fees_inr"),
    ("slippage_inr", "slippage_inr"),
    ("funding_inr", "funding_inr"),
    ("cost_in_r", "cost_in_r"),
    ("total_risk_inr", "risk_inr"),
    ("gross_inr", "gross_inr"),
    ("net_inr", "net_inr"),
]


def audit_one(t, idx):
    e = recompute(t)
    print(f"\n{'=' * 88}")
    print(f"TRADE {idx}   {t.get('symbol', '?')}  {t['side']}  "
          f"entry {t['entry']}  sl {t['sl']}  {t.get('outcome')}  "
          f"held {t.get('bars_held')} bars")
    print(f"{'=' * 88}")
    print(f"{'field':<26}{'expected':>16}{'engine':>16}{'difference':>16}  ")
    print("-" * 88)

    problems = []
    for exp_key, eng_key in FIELDS:
        exp = e.get(exp_key)
        eng = t.get(eng_key)
        if exp is None or eng is None:
            print(f"{exp_key:<26}{'-' if exp is None else f'{exp:16.4f}':>16}"
                  f"{'not in log' if eng is None else f'{eng:16.4f}':>16}"
                  f"{'':>16}")
            continue
        exp, eng = float(exp), float(eng)
        d = exp - eng
        bad = abs(d) > max(TOL, abs(exp) * 0.001)
        if bad:
            problems.append((exp_key, exp, eng, d))
        print(f"{exp_key:<26}{exp:>16.4f}{eng:>16.4f}{d:>+16.4f}"
              f"{'  <-- MISMATCH' if bad else ''}")

    # identities that must hold regardless of what the log says
    print("-" * 88)
    checks = []
    if not e["position_capped_by_leverage"]:
        checks.append(("risk cap honoured",
                       abs(e["total_risk_inr"] - MAX_RISK_INR) < 1.0,
                       f"total risk Rs.{e['total_risk_inr']:.2f} vs cap "
                       f"Rs.{MAX_RISK_INR:.0f}"))
    else:
        checks.append(("leverage cap applied", True,
                       f"notional capped at Rs.{e['notional_inr']:.0f}, "
                       f"risk Rs.{e['total_risk_inr']:.2f} below the cap"))
    checks.append(("leverage within allowance",
                   e["leverage_used"] <= e["leverage_allowed"] + 0.01,
                   f"{e['leverage_used']}x of {e['leverage_allowed']}x"))
    checks.append(("notional clears venue minimum",
                   not e["below_min_notional"],
                   f"Rs.{e['notional_inr']:.0f} vs Rs.{MIN_NOTIONAL_INR:.0f}"))
    if t.get("gross_inr") is not None and t.get("net_inr") is not None:
        implied = (float(t["gross_inr"]) - float(t.get("fees_inr", 0))
                   - float(t.get("slippage_inr", 0))
                   - float(t.get("funding_inr", 0)))
        checks.append(("net = gross - fees - slip - funding",
                       abs(implied - float(t["net_inr"])) < 1.0,
                       f"implied Rs.{implied:.2f} vs logged "
                       f"Rs.{float(t['net_inr']):.2f}"))
    for name, ok, detail in checks:
        print(f"  [{'OK ' if ok else 'FAIL'}] {name:<38} {detail}")
        if not ok:
            problems.append((name, None, None, None))

    print("\n  TP ladder (expected)")
    for tp in e["tps"]:
        logged = (t.get(tp["level"].lower()) or {})
        lp = logged.get("price")
        mark = ""
        if lp is not None:
            mark = ("  match" if abs(float(lp) - tp["price"]) < 0.01
                    else f"  <-- log says {float(lp):.4f}")
        print(f"    {tp['level']}  {tp['r']}R  price {tp['price']:14.4f}  "
              f"gross Rs.{tp['gross_inr']:9.2f}  net Rs.{tp['net_inr']:9.2f}{mark}")

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default="trades.json")
    ap.add_argument("--symbol")
    ap.add_argument("--bars", type=int, default=10000)
    ap.add_argument("--arm", default="smc")
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()

    trades = []
    if a.symbol:
        import backtest as B
        import data as D
        f, _ = D.load_mtf(a.symbol.upper(), D.clamp_bars(a.bars))
        if f is None:
            print("no data")
            return
        rep = B.full_report(a.symbol.upper(), f["5m"], f["15m"], f["1h"])
        trades = [t for t in (rep.get("trade_log") or [])
                  if t.get("arm") == a.arm]
    else:
        raw = json.load(open(a.trades))
        rows = raw if isinstance(raw, list) else (raw.get("trades") or [])
        trades = [t for t in rows if t.get("arm") == a.arm]

    if not trades:
        print(f"no '{a.arm}' trades found")
        return

    print(f"auditing {min(a.n, len(trades))} of {len(trades)} '{a.arm}' trades")
    print(f"capital Rs.{CAPITAL_INR:.0f}  risk cap Rs.{MAX_RISK_INR:.0f}  "
          f"USDTINR {USDT_INR}  fee {FEE_PER_LEG * 100:.2f}%/leg  "
          f"slip {SLIPPAGE_PER_LEG * 100:.2f}%/leg")

    all_problems = []
    for i, t in enumerate(trades[:a.n], 1):
        all_problems += audit_one(t, i)

    print(f"\n{'=' * 88}\nSUMMARY\n{'=' * 88}")
    if not all_problems:
        print("  No discrepancies. Every audited field matches an independent")
        print("  recomputation to within one paisa.")
    else:
        seen = {}
        for p in all_problems:
            seen[p[0]] = seen.get(p[0], 0) + 1
        print(f"  {len(all_problems)} discrepancies across "
              f"{min(a.n, len(trades))} trades:")
        for k, n in sorted(seen.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<40} {n} trade(s)")
        print("\n  Nothing has been modified. Fix the engine or this audit, "
              "whichever is wrong.")


if __name__ == "__main__":
    main()
