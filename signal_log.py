"""
signal_log.py — Automatic signal journal.

Answers the one question the scanner has never been asked:
does it actually make money?

How it works:
  1. Every scan pass records any BUY/SELL signal once (deduped — a signal
     that stays live for 20 polls is still one entry).
  2. Later calls walk forward through candles from the entry time and mark
     each open signal WIN (TP first) or LOSS (SL first).
  3. /api/journal/stats gives win rate, expectancy and profit factor from
     what the scanner ACTUALLY said, not from a backtest.

PERSISTENCE
  Set DATABASE_URL to a Postgres connection string and the journal lives
  there permanently. Without it, this falls back to SQLite at JOURNAL_DB —
  fine locally, but on Render's free tier that path is wiped on every
  restart and redeploy, which is why earlier journal data never survived
  long enough to test anything.

  Resolution is deliberately pessimistic: if a candle touches both the stop
  and the target, it is recorded as a LOSS. Better to understate the edge
  than to invent one.
"""

import os
import sqlite3
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = os.environ.get("JOURNAL_DB", "/tmp/signal_journal.db")
USING_POSTGRES = bool(DATABASE_URL)

if USING_POSTGRES:
    import psycopg2
    import psycopg2.extras


def backend():
    """Which store is live. Surfaced on /api/journal/stats so a silent
    fallback to ephemeral SQLite can never go unnoticed again."""
    return {
        "backend": "postgres" if USING_POSTGRES else "sqlite",
        "ephemeral": not USING_POSTGRES,
        "location": "DATABASE_URL" if USING_POSTGRES else DB_PATH,
        "warning": None if USING_POSTGRES else
                   "SQLite on Render free tier is wiped on every restart. "
                   "Set DATABASE_URL to keep journal history.",
    }


class _Conn:
    """Thin wrapper so the same SQL works on both engines."""

    def __init__(self):
        if USING_POSTGRES:
            self.c = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            self.cur = self.c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            self.c = sqlite3.connect(DB_PATH, timeout=10)
            self.c.row_factory = sqlite3.Row
            self.cur = self.c.cursor()

    def execute(self, sql, args=()):
        if USING_POSTGRES:
            sql = sql.replace("?", "%s")
        self.cur.execute(sql, args)
        return self.cur

    def fetchall(self):
        return [dict(r) for r in self.cur.fetchall()]

    def fetchone(self):
        r = self.cur.fetchone()
        return dict(r) if r is not None else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.c.commit()
        else:
            self.c.rollback()
        self.c.close()
        return False


_conn = _Conn
_initialised = False


def init_db():
    global _initialised
    if _initialised:
        return
    pk = "BIGSERIAL PRIMARY KEY" if USING_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with _Conn() as c:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS signals (
                id           {pk},
                logged_at    TEXT NOT NULL,
                symbol       TEXT NOT NULL,
                timeframe    TEXT NOT NULL,
                direction    TEXT NOT NULL,
                entry        DOUBLE PRECISION NOT NULL,
                tp           DOUBLE PRECISION,
                sl           DOUBLE PRECISION,
                rsi          DOUBLE PRECISION,
                buy_score    DOUBLE PRECISION,
                sell_score   DOUBLE PRECISION,
                htf_bias     TEXT,
                regime       TEXT,
                blowoff      INTEGER DEFAULT 0,
                outcome      TEXT DEFAULT 'OPEN',
                resolved_at  TEXT,
                exit_price   DOUBLE PRECISION,
                pnl_pct      DOUBLE PRECISION,
                bars_held    INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_open ON signals(outcome)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_market ON signals(symbol, timeframe)")
    _initialised = True


def log_signal(symbol, timeframe, payload):
    """Record a BUY/SELL signal once. Returns True if a new row was written."""
    if not isinstance(payload, dict):
        return False
    if payload.get("signal") not in ("BUY", "SELL"):
        return False
    sig = payload["signal"]
    entry = payload.get("entry") or payload.get("price")
    if not entry:
        return False

    init_db()
    with _Conn() as c:
        c.execute("SELECT 1 FROM signals WHERE symbol=? AND timeframe=? "
                  "AND direction=? AND outcome='OPEN' LIMIT 1",
                  (symbol, timeframe, sig))
        if c.fetchone() is not None:
            return False                      # already tracking this one
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
    """Walk candles forward from each open signal and mark WIN/LOSS.
    fetch_fn(symbol, timeframe, limit) -> (df, source)"""
    init_db()
    resolved = 0
    with _Conn() as c:
        c.execute("SELECT * FROM signals WHERE outcome='OPEN'")
        rows = c.fetchall()

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
        ts = df["timestamp"] if "timestamp" in df.columns else None

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
                # Stop checked first on purpose — an ambiguous candle counts
                # against us, so the journal can never flatter the strategy.
                if r["direction"] == "BUY":
                    if lo <= sl:   outcome, exit_px = "LOSS", sl
                    elif hi >= tp: outcome, exit_px = "WIN", tp
                else:
                    if hi >= sl:   outcome, exit_px = "LOSS", sl
                    elif lo <= tp: outcome, exit_px = "WIN", tp
                if outcome:
                    bars = j - start
                    break
            if not outcome:
                continue

            pnl = (exit_px - r["entry"]) / r["entry"] * 100
            if r["direction"] == "SELL":
                pnl = -pnl
            with _Conn() as c:
                c.execute("UPDATE signals SET outcome=?,resolved_at=?,exit_price=?,"
                          "pnl_pct=?,bars_held=? WHERE id=?",
                          (outcome, datetime.now(timezone.utc).isoformat(),
                           exit_px, round(pnl, 4), bars, r["id"]))
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

    with _Conn() as c:
        c.execute(q, tuple(args))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) AS n FROM signals WHERE outcome='OPEN'")
        open_n = c.fetchone()["n"]

    store = backend()
    if not rows:
        return {"resolved": 0, "open": open_n,
                "note": "no resolved signals yet — needs time to accumulate",
                "storage": store}

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
        "storage": store,
    }


def recent(limit=50):
    init_db()
    with _Conn() as c:
        c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (int(limit),))
        return c.fetchall()
