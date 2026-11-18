#!/usr/bin/env python3
"""
audit_missed.py — which gate stopped the trade?

Replays the LIVE gate order bar by bar over the audit window and records the
first gate that failed, so "NO TRADE" gets a root cause.

Gate order (same as services/live_signal.py build_signal):
    1. 4H bias            HTF_NEUTRAL
    2. 15M setup          NO_SETUP / SETUP_WRONG_WAY / AWAITING_RETEST
    3. setup still alive  SETUP_EXPIRED / SETUP_MITIGATED
    4. 5M quality gate    WEAK_5M_CONFIRMATION (only when the gate is enabled)
    5. sizing             SIZING_REJECTED
    6. reachable target   NO_REACHABLE_TARGETS
    7. entry state        INVALIDATED / EXPIRED / MISSED_ENTRY
    8. cost gate          COST_GATE
    ok                    ALERT (would show as a setup alert)

The 5M trigger is informational in this engine and never blocks, so it is not
a gate here.

WINDOW. Same as AUDIT_ENHANCEMENTS.md: the full calendar day of YESTERDAY in
IST (UTC+05:30), 00:00 to 24:00. On 18-Nov the report covers 17-Nov.

Usage (same arguments style as collect.py):
    python3 audit_missed.py --symbols BTC,ETH,SOL --bars 10000
    python3 audit_missed.py                      # every symbol in PAIR_MAP
    python3 audit_missed.py --hours 12           # override: last 12h instead

Output: MISSED_TRADE_AUDIT.md
"""

from __future__ import annotations

import argparse
import io
import contextlib
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd

import backtest as B
import collect as C
import data as D
import mtf_engine as M
import research_data as RD
import risk as R
from services import live_signal as LS

IST = timezone(timedelta(hours=5, minutes=30))

STAGES = [
    ("4H Bias", {"HTF_NEUTRAL"}),
    ("15M Setup", {"NO_SETUP", "SETUP_WRONG_WAY", "AWAITING_RETEST"}),
    ("Setup Alive", {"SETUP_EXPIRED", "SETUP_MITIGATED"}),
    ("5M Quality", {"WEAK_5M_CONFIRMATION"}),
    ("Target Reachable", {"SIZING_REJECTED", "NO_REACHABLE_TARGETS"}),
    ("Entry Valid", {"INVALIDATED", "EXPIRED", "MISSED_ENTRY"}),
    ("Cost Gate", {"COST_GATE"}),
]


# Where to look for each root cause. Report only: nothing here changes the strategy.
# Line numbers drift, so each entry also carries a grep pattern.
FIX_MAP = {
    "NO_REACHABLE_TARGETS": {
        "file": "risk.py",
        "where": "_rupee_targets() (about line 331), TP_R_LADDER (about line 56); "
                 "structure_limit is passed from live_signal.py (~143) and backtest.py (~311)",
        "grep": "grep -n \"TP_R_LADDER\\|structure_limit\\|def _rupee_targets\" risk.py services/live_signal.py backtest.py",
        "experiments": [
            "A/B: lower the minimum R of TP1 in TP_R_LADDER (1.5 -> 1.0), behind a flag, default unchanged",
            "A/B: structure_limit = farthest swing instead of the nearest, behind a flag",
            "Check stop width first: a very wide OB-wick stop makes 1.5R unreachable by construction",
        ],
        "caution": "Live does not pass atr to size_position(); backtest does. Align that before comparing.",
    },
    "SIZING_REJECTED": {
        "file": "risk.py",
        "where": "size_position() (about line 216)",
        "grep": "grep -n \"def size_position\" risk.py",
        "experiments": ["Read the reject reason in the live card or in backtest 'rejected' counts"],
        "caution": "Risk cap is Rs.700 including costs; do not raise it to get more trades.",
    },
    "SETUP_EXPIRED": {
        "file": "mtf_engine.py",
        "where": "PARAMS['max_age'] (about line 52, env MAX_AGE_BARS) and expires_ts (about line 407)",
        "grep": "grep -n \"max_age\\|MAX_AGE_BARS\\|expires_ts\" mtf_engine.py",
        "experiments": ["A/B: max_age 24 -> 36 or 48 on in-sample bars, then check OOS"],
        "caution": "A longer life lets older zones trade; check that win rate does not fall.",
    },
    "SETUP_MITIGATED": {
        "file": "mtf_engine.py / poi_factors.py",
        "where": "PARAMS['kill_on'] and update_zones()",
        "grep": "grep -n \"kill_on\\|def update_zones\" mtf_engine.py poi_factors.py",
        "experiments": ["Only inspect. A zone price already invalidated should not be traded."],
        "caution": "Do not relax this; it protects against entering a dead zone.",
    },
    "AWAITING_RETEST": {
        "file": "mtf_engine.py",
        "where": "PARAMS['require_retest'], retest_max_wait",
        "grep": "grep -n \"require_retest\\|retest_max_wait\" mtf_engine.py",
        "experiments": ["Retest is off by default; this code appears only if it was turned on"],
        "caution": "",
    },
    "WEAK_5M_CONFIRMATION": {
        "file": "mtf_engine.py",
        "where": "PARAMS['require_5m_quality_gate'], volume_expansion_min, close_ratio_min",
        "grep": "grep -n \"require_5m_quality_gate\\|volume_expansion_min\\|close_ratio_min\" mtf_engine.py",
        "experiments": ["A/B: gate off vs on, on in-sample bars first"],
        "caution": "",
    },
    "MISSED_ENTRY": {
        "file": "services/live_signal.py",
        "where": "classify_entry_state() (about line 49)",
        "grep": "grep -n \"def classify_entry_state\" services/live_signal.py",
        "experiments": ["Not a strategy fault: price already went through the limit. Do not chase."],
        "caution": "",
    },
    "INVALIDATED": {
        "file": "services/live_signal.py",
        "where": "classify_entry_state() (about line 49)",
        "grep": "grep -n \"def classify_entry_state\" services/live_signal.py",
        "experiments": ["Not a strategy fault: price crossed the stop before entry."],
        "caution": "",
    },
    "COST_GATE": {
        "file": "backtest.py / services/live_signal.py",
        "where": "MAX_COST_IN_R env (default 0.75)",
        "grep": "grep -n \"MAX_COST_IN_R\" backtest.py services/live_signal.py",
        "experiments": ["Cost gate exists because fees eat the trade when the stop is tight. Leave it."],
        "caution": "",
    },
    "HTF_NEUTRAL": {
        "file": "mtf_engine.py",
        "where": "htf_bias_series()",
        "grep": "grep -n \"def htf_bias_series\" mtf_engine.py",
        "experiments": ["Quality filter. Do not relax."],
        "caution": "",
    },
    "SETUP_WRONG_WAY": {
        "file": "mtf_engine.py",
        "where": "_evaluate()",
        "grep": "grep -n \"def _evaluate\" mtf_engine.py",
        "experiments": ["Quality filter. Do not relax."],
        "caution": "",
    },
    "NO_SETUP": {
        "file": "mtf_engine.py",
        "where": "find_setups()",
        "grep": "grep -n \"def find_setups\" mtf_engine.py",
        "experiments": ["Normal when the market has not produced a displacement. Not a fault."],
        "caution": "",
    },
}


def fix_section(total_setups, total_bars):
    """Report section D: for the biggest blockers, where to look and what to A/B."""
    ranked = [(k, v) for k, v in total_setups.most_common() if k != "ALERT"]
    if not ranked:
        ranked = [(k, v) for k, v in total_bars.most_common() if k != "ALERT"]
    lines = ["D) Where to look (report only, nothing here is applied automatically)"]
    for code, n in ranked[:4]:
        info = FIX_MAP.get(code)
        lines.append("")
        lines.append(f"   {code}  ({n})")
        if not info:
            lines.append("      no entry in FIX_MAP")
            continue
        lines.append(f"      file : {info['file']}")
        lines.append(f"      where: {info['where']}")
        lines.append(f"      find : {info['grep']}")
        for e in info["experiments"]:
            lines.append(f"      try  : {e}")
        if info["caution"]:
            lines.append(f"      note : {info['caution']}")
    return lines


def judge_bar(sym, df5, ctx, i):
    """Return (root_cause_code, setup_or_None) for 5M bar i."""
    ts = M._ts(df5["ts"]).iat[i]
    bias = ctx["bias"][i]
    quality = bool(ctx["quality"][i])
    action, setup, side, level, code = M.decide(
        bias, ctx["trigger"][i], ctx["setups"], ts, quality=quality)

    if action not in ("BUY", "SELL") or setup is None:
        return code, None

    entry, stop = float(level), float(setup.stop_level)
    targets = M.structure_targets_at(
        ctx["df15"], ctx.get("swings_15m", []), ts, side, entry, max_targets=3)

    with contextlib.redirect_stdout(io.StringIO()):      # silence risk.py prints
        sizing = R.size_position(
            sym, action, entry, stop, structure_targets=targets,
            structure_limit=(targets[-1] if targets else None))

    if not sizing.ok:
        return "SIZING_REJECTED", setup
    if not [t for t in (sizing.tps or []) if t.get("reachable")]:
        return "NO_REACHABLE_TARGETS", setup

    low, high = float(df5["low"].iat[i]), float(df5["high"].iat[i])
    touched = low <= entry if side == "bull" else high >= entry
    current = float(df5["close"].iat[i])
    now = LS._as_utc(ts + pd.Timedelta(minutes=5))
    expires = LS._as_utc(setup.expires_ts)
    state = LS.classify_entry_state(side, current, entry, stop, touched,
                                    now=now, expires_at=expires)
    if state in ("INVALIDATED", "EXPIRED", "MISSED_ENTRY"):
        return state, setup

    if sizing.cost_in_r > LS.MAX_COST_IN_R:
        return "COST_GATE", setup
    return "ALERT", setup


def snapshot_block(sym, code, bias):
    """The ✅/❌ ladder for the latest bar of one symbol."""
    lines = [sym]
    failed = False
    for name, codes in STAGES:
        if name == "5M Quality" and code != "WEAK_5M_CONFIRMATION":
            continue                                   # not blocking unless it fails
        if failed:
            lines.append(f"  {name:18s} -")
        elif code in codes:
            lines.append(f"  {name:18s} ❌")
            failed = True
        else:
            lines.append(f"  {name:18s} ✅")
    lines.append("  Root cause: " + ("ALERT (setup would be shown)" if code == "ALERT" else code))
    return "\n".join(lines)


def audit_symbol(sym, bars, hours=None):
    """Audit one symbol. Default window = yesterday (IST), full calendar day."""
    if sym not in D.PAIR_MAP:
        C.register(sym, f"B-{sym}_USDT")
    frames, meta = RD.load_research(sym, bars)
    if frames is None:
        return None, f"{sym}: no data ({(meta or {}).get('error')})"

    df5, df15, df4 = frames["5m"], frames["15m"], frames["4h"]
    ctx = M.build_context(df5, df15, df4)
    ts_all = M._ts(df5["ts"])

    # Data timestamps are naive UTC, same convention collect.py uses for exit_ts.
    ts_ist = ts_all + pd.Timedelta(hours=5, minutes=30)
    if hours is None:
        day = datetime.now(IST).date() - timedelta(days=1)
        idxs = [i for i in range(len(df5)) if ts_ist.iat[i].date() == day]
    else:
        start_ts = ts_all.iat[-1] - pd.Timedelta(hours=hours)
        idxs = [i for i in range(len(df5)) if ts_all.iat[i] >= start_ts]
    if not idxs:
        return None, f"{sym}: no 5m bars inside the audit window"

    bar_hist = Counter()
    setup_codes = {}                  # setup key -> Counter of codes
    last_code = None
    for i in idxs:
        code, setup = judge_bar(sym, df5, ctx, i)
        bar_hist[code] += 1
        last_code = code
        if setup is not None:
            key = (str(setup.confirmed_ts), round(setup.entry_level, 8), setup.side)
            setup_codes.setdefault(key, Counter())[code] += 1

    # one verdict per unique setup: ALERT if it ever got that far,
    # otherwise the blocker it hit most often
    setup_final = Counter()
    for cnt in setup_codes.values():
        setup_final["ALERT" if cnt.get("ALERT") else cnt.most_common(1)[0][0]] += 1

    last_i = idxs[-1]
    return {
        "sym": sym, "bars": len(idxs), "bar_hist": bar_hist,
        "setups": len(setup_codes), "setup_final": setup_final,
        "last_code": last_code, "last_bias": str(ctx["bias"][last_i]),
        "last_ts": str(ts_all.iat[last_i]),
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", help="comma separated, e.g. BTC,ETH,SOL")
    ap.add_argument("--bars", type=int, default=10000)
    ap.add_argument("--hours", type=float, default=None,
                    help="override: audit the last N hours instead of yesterday (IST)")
    ap.add_argument("--out", default="MISSED_TRADE_AUDIT.md")
    a = ap.parse_args()

    syms = ([s.strip().upper() for s in a.symbols.split(",") if s.strip()]
            if a.symbols else list(D.PAIR_MAP))
    bars = D.clamp_bars(a.bars)

    report_date = datetime.now(IST).date() - timedelta(days=1)
    window_txt = (f"{report_date} (full IST day)" if a.hours is None
                  else f"last {a.hours:g}h")

    total_bars, total_setups = Counter(), Counter()
    blocks, notes = [], []
    for sym in syms:
        try:
            res, err = audit_symbol(sym, bars, a.hours)
        except Exception as e:
            err, res = f"{sym}: ERROR {e}", None
        if err:
            notes.append(err)
            print(err)
            continue
        total_bars.update(res["bar_hist"])
        total_setups.update(res["setup_final"])
        blocks.append(snapshot_block(sym, res["last_code"], res["last_bias"])
                      + f"\n  (last bar of window {res['last_ts']}, "
                        f"{res['setups']} setups seen)")
        print(f"{sym:9s} last={res['last_code']:22s} setups_in_window={res['setups']}")

    body = []
    body.append("A) Unique setups by final outcome (what actually happened to each setup)")
    for k, v in total_setups.most_common():
        body.append(f"   {v:5d}  {k}")
    body.append("")
    body.append("B) 5M bars by first blocking gate (time spent blocked, not trade count)")
    for k, v in total_bars.most_common():
        body.append(f"   {v:5d}  {k}")
    body.append("")
    body.extend(fix_section(total_setups, total_bars))
    body.append("")
    body.append("C) Last bar of the window, per symbol")
    body.append("")
    body.append("\n\n".join(blocks))
    if notes:
        body.append("")
        body.extend(notes)

    md = (
        "# Missed Trade Audit (generated with AUDIT_ENHANCEMENTS.md)\n\n"
        f"**Date:** {report_date} (Auto-Generated via audit_missed.py)  \n"
        f"**Window:** {window_txt}  \n"
        f"**Symbols audited:** {len(blocks)} of {len(syms)}\n\n"
        "```text\n" + "\n".join(body) + "\n```\n\n"
        "> This shows WHICH gate blocked a trade, not whether the gate was wrong. "
        "A gate is only relaxed after out-of-sample evidence.\n\n"
        "---\n*Note: updated by the same daily GitHub Action as AUDIT_ENHANCEMENTS.md.*\n"
    )
    with open(a.out, "w") as f:
        f.write(md)
    print(f"\nwritten to {a.out}")


if __name__ == "__main__":
    main()
