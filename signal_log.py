"""
signal_log.py — Automatic signal journal.  (v2 — RESOLUTION FIXES)

Answers the one question the scanner has never been asked:
does it actually make money?

How it works:
  1. Every scan pass records any BUY/SELL signal once (deduped — a signal
     that stays live for 20 polls is still one entry).
  2. Later calls walk forward through candles from the entry time and mark
     each open signal WIN (TP first) or LOSS (SL first).
  3. /api/journal/stats gives win rate, expectancy and profit factor from
     what the scanner ACTUALLY said, not from a backtest.

WHAT CHANGED IN v2 — every edit is tagged "# FIX v2:" inline.

  J1  ENTRY INDEX WAS ALWAYS ZERO. resolve_open() looked for a "timestamp"
      COLUMN, but fetch_ohlcv_failover() sets timestamp as the INDEX
      (df.set_index("timestamp", inplace=True)). The lookup therefore always
      returned None, `start` stayed 0, and every signal was resolved by
      walking the candle window from its OLDEST bar — including hours of
      price action that happened BEFORE the signal existed. A 10:00 signal
      was being marked WIN or LOSS by what price did at 06:00. Every
      outcome in the journal so far is meaningless, not merely noisy.

  J2  FEES WERE NEVER DEDUCTED. Every backtest path runs P&L through
      _net_pnl_pct(), which subtracts round_trip_cost_pct(). The journal
      did not, so it reported ~0.10% more per trade than the account would
      ever see — and viability.py builds its entire verdict on these rows.
      The journal was the most optimistic number in the whole system while
      being presented as the most honest one.

  J3  SIGNALS WITH NO FORWARD CANDLES ARE NOW SKIPPED, not resolved. If the
      fetched window does not reach the signal time, there is nothing to
      resolve yet; the row stays OPEN and is retried on the next call.

⚠️  Journal rows written before this fix were produced by the broken
    resolver. They cannot be repaired after the fact — the candle data they
    were scored against is not recorded. Clear the signals table once after
    deploying this, or every honest row from now on will be averaged in with
    rows that were effectively random.

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

# FIX v2 (J2): the journal must charge the same round trip the backtests
# charge, or the two disagree by exactly the amount that decides whether the
# strategy is viable. Keep this in step with CONFIG['ROUND_TRIP_COST_PCT']
# in scanner.py — same number, same meaning: (taker_fee * 2) + spread.
ROUND_TRIP_COST_PCT = float(os.environ.get("ROUND_TRIP_COST_PCT", 0.10))

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
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
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


def _entry_index(df, logged_at):
    """FIX v2 (J1): position of the first candle at or after the signal.

    The old code searched for a "timestamp" COLUMN. fetch_ohlcv_failover()
    puts timestamp in the INDEX, so that branch never ran and `start`
    silently defaulted to 0 — resolving every signal against the entire
    fetched window, most of which predates the signal.

    Returns None when the window does not reach the signal yet, so the row
    stays OPEN and gets retried instead of being scored on stale bars.
    """
    try:
        t0 = datetime.fromisoformat(logged_at)
    except (TypeError, ValueError):
        return None

    # Rows are logged with an aware UTC timestamp; the candle index is naive
    # UTC. Compare like with like rather than letting pandas raise.
    if t0.tzinfo is not None:
        t0 = t0.astimezone(timezone.utc).replace(tzinfo=None)

    try:
        pos = int(df.index.searchsorted(t0, side="left"))
    except Exception:
        return None

    if pos >= len(df.index):
        return None
    return pos


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

        for r in group:
            tp, sl = r["tp"], r["sl"]
            if tp is None or sl is None:
                continue

            # FIX v2 (J1, J3): start at the signal, or leave it OPEN.
            start = _entry_index(df, r["logged_at"])
            if start is None:
                continue

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
            # FIX v2 (J2): charge the round trip, same as every backtest path.
            pnl -= ROUND_TRIP_COST_PCT

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

    # FIX v2 (J2): pnl_pct is now net of fees, so a WIN that only just
    # reached its target can still be a losing row. Classify by the money,
    # not by the label, exactly as _summarize() does in scanner.py.
    wins = [r for r in rows if (r["pnl_pct"] or 0) > 0]
    losses = [r for r in rows if (r["pnl_pct"] or 0) <= 0]
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
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "verdict": verdict,
        "storage": store,
    }


def recent(limit=50):
    init_db()
    with _Conn() as c:
        c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (int(limit),))
        return c.fetchall()
