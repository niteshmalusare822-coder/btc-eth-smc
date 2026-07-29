"""
signal_log.py — Automatic signal journal.

Answers the one question the scanner has never been asked:
does it actually make money?

How it works:
  1. Every time /api/dashboard runs, any BUY/SELL signal gets recorded once
     (deduped — a signal that stays live for 20 polls is still one entry).
  2. Later calls walk forward through candles from the entry time and mark
     each open signal WIN (TP first) or LOSS (SL first).
  3. /api/journal/stats gives you win rate, expectancy, profit factor —
     computed from what the scanner ACTUALLY said, not from a backtest.

IMPORTANT — persistence on Render free tier:
  The filesystem is wiped on every restart and redeploy. Free instances also
  sleep when idle. So this DB will lose history unless you either
    (a) attach a Render persistent disk and set JOURNAL_DB to a path on it, or
    (b) run this locally / on a VPS.
  Set the env var JOURNAL_DB to control the location.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("JOURNAL_DB", "/tmp/signal_journal.db")


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at    TEXT NOT NULL,
                symbol       TEXT NOT NULL,
                timeframe    TEXT NOT NULL,
                direction    TEXT NOT NULL,
                entry        REAL NOT NULL,
                tp           REAL,
                sl           REAL,
                rsi          REAL,
                buy_score    REAL,
                sell_score   REAL,
                htf_bias     TEXT,
                regime       TEXT,
                blowoff      INTEGER DEFAULT 0,
                outcome      TEXT DEFAULT 'OPEN',
                resolved_at  TEXT,
                exit_price   REAL,
                pnl_pct      REAL,
                bars_held    INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_open ON signals(outcome)")


def _has_open(c, symbol, timeframe, direction):
    row = c.execute(
        "SELECT 1 FROM signals WHERE symbol=? AND timeframe=? AND direction=? "
        "AND outcome='OPEN' LIMIT 1", (symbol, timeframe, direction)
    ).fetchone()
    return row is not None


def log_signal(symbol, timeframe, payload):
    """Record a BUY/SELL signal once. Returns True if a new row was written."""
    if not isinstance(payload, dict):
        return False
    sig = payload.get("signal")
    if sig not in ("BUY", "SELL"):
        return False
    entry = payload.get("entry") or payload.get("price")
    if not entry:
        return False

    init_db()
    with _conn() as c:
        if _has_open(c, symbol, timeframe, sig):
            return False          # already tracking this one
        bo = payload.get("blowoff") or {}
        c.execute(
            "INSERT INTO signals (logged_at,symbol,timeframe,direction,entry,tp,sl,"
            "rsi,buy_score,sell_score,htf_bias,regime,blowoff) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), symbol, timeframe, sig,
             float(entry), payload.get("tp"), payload.get("sl"),
             payload.get("rsi"), payload.get("buy_score"),
             payload.get("sell_score"), payload.get("htf_bias"),
             payload.get("regime"), 1 if bo.get("active") else 0)
        )
    return True


def resolve_open(fetch_fn, limit=300):
    """
    Walk candles forward from each open signal and mark WIN/LOSS.
    fetch_fn(symbol, timeframe, limit) -> (df, source)
    """
    init_db()
    resolved = 0
    with _conn() as c:
        rows = c.execute("SELECT * FROM signals WHERE outcome='OPEN'").fetchall()

    by_market = {}
    for r in rows:
        by_market.setdefault((r["symbol"], r["timeframe"]), []).append(r)

    for (symbol, timeframe), group in by_market.items():
        try:
            df, _ = fetch_fn(symbol, timeframe, limit)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        if "timestamp" in df.columns:
            ts = df["timestamp"]
        else:
            ts = None

        for r in group:
            tp, sl = r["tp"], r["sl"]
            if tp is None or sl is None:
                continue
            start = 0
            if ts is not None:
                try:
                    t0 = datetime.fromisoformat(r["logged_at"]).timestamp() * 1000
                    later = [i for i, v in enumerate(ts) if float(v) >= t0]
                    if not later:
                        continue
                    start = later[0]
                except Exception:
                    start = 0

            outcome = exit_px = bars = None
            for j in range(start, len(df)):
                hi = float(df["high"].iloc[j])
                lo = float(df["low"].iloc[j])
                if r["direction"] == "BUY":
                    if lo <= sl: outcome, exit_px = "LOSS", sl
                    elif hi >= tp: outcome, exit_px = "WIN", tp
                else:
                    if hi >= sl: outcome, exit_px = "LOSS", sl
                    elif lo <= tp: outcome, exit_px = "WIN", tp
                if outcome:
                    bars = j - start
                    break
            if not outcome:
                continue

            pnl = (exit_px - r["entry"]) / r["entry"] * 100
            if r["direction"] == "SELL":
                pnl = -pnl
            with _conn() as c:
                c.execute(
                    "UPDATE signals SET outcome=?,resolved_at=?,exit_price=?,"
                    "pnl_pct=?,bars_held=? WHERE id=?",
                    (outcome, datetime.now(timezone.utc).isoformat(),
                     exit_px, round(pnl, 4), bars, r["id"])
                )
            resolved += 1
    return resolved


def stats(symbol=None, timeframe=None):
    """Win rate, expectancy, profit factor — from real logged signals."""
    init_db()
    q = "SELECT * FROM signals WHERE outcome IN ('WIN','LOSS')"
    args = []
    if symbol:
        q += " AND symbol=?"; args.append(symbol)
    if timeframe:
        q += " AND timeframe=?"; args.append(timeframe)
    with _conn() as c:
        rows = [dict(r) for r in c.execute(q, args).fetchall()]
        open_n = c.execute("SELECT COUNT(*) n FROM signals WHERE outcome='OPEN'").fetchone()["n"]

    if not rows:
        return {"resolved": 0, "open": open_n,
                "note": "no resolved signals yet — needs time to accumulate"}

    wins = [r for r in rows if r["outcome"] == "WIN"]
    losses = [r for r in rows if r["outcome"] == "LOSS"]
    gp = sum(r["pnl_pct"] for r in wins)
    gl = abs(sum(r["pnl_pct"] for r in losses))
    exp = sum(r["pnl_pct"] for r in rows) / len(rows)

    if len(rows) < 30:
        verdict = f"TOO EARLY — {len(rows)} signals, need 30+ before trusting this"
    elif exp <= 0:
        verdict = "SCANNER IS NOT PROFITABLE on these settings"
    elif gl > 0 and gp / gl < 1.2:
        verdict = "EDGE TOO THIN to survive slippage"
    else:
        verdict = "PROFITABLE so far — keep collecting"

    return {
        "resolved": len(rows), "open": open_n,
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(rows) * 100, 1),
        "expectancy_pct": round(exp, 3),
        "total_pct": round(sum(r["pnl_pct"] for r in rows), 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
        "verdict": verdict,
    }


def recent(limit=50):
    init_db()
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
