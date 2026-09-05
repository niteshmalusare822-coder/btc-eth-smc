#!/usr/bin/env python3
"""
app.py — the only process that runs on Render.

GET /                            endpoint index
GET /api/health                  service state and bar limits
GET /api/config                  account, costs, leverage, parameters
GET /api/signal/<symbol>         BUY / SELL / NO_TRADE + full ticket
GET /api/signals                 all symbols
GET /api/report/<symbol>         3-arm measurement: RANDOM vs SMC vs SMC_MTF
GET /api/trades/<symbol>         trade log on its own endpoint
GET /api/data-probe/<symbol>     pagination only, seconds not minutes
GET /api/diagnostic/<symbol>     missed-move analysis
GET /api/portfolio               all four assets plus pooled portfolio
GET /api/entry-quality/<symbol>  entry vs exit failure, gate value, modes

A NO_TRADE is returned with the reason, not as an empty payload. Knowing which
timeframe disagreed is the useful part.

REVIEW FIXES IN THIS VERSION
---------------------------
1. Blocker codes were leaking to the UI. mtf.decide() now returns machine codes
   like HTF_NEUTRAL so they can be counted; the dashboard was printing the code
   itself. Codes are translated through mtf.BLOCKERS before they leave the API.
2. full_report() was running up to four times per symbol for one page load:
   once for /api/report, again inside build_trade_log, again inside
   build_diagnostic, and again inside EQ.full_diagnosis. On a 0.1 CPU instance
   that alone was a timeout. There is now one shared report cache keyed by
   (symbol, bars) that every consumer reads from.
3. /api/portfolio ran four heavy diagnostics in one request with no ceiling. It
   now caps its own bar count and says so in the response.
4. The cache had no bound. On a 512 MB instance a handful of 10,000-bar reports
   with trade logs will exhaust memory. It is now size-capped and evicts oldest.
5. numpy scalars reached jsonify in a few paths. Everything leaving the API now
   passes through a JSON-safety pass that also converts NaN and inf to null,
   because NaN is not valid JSON and silently breaks JSON.parse in the browser.
6. The live ticket said "entry at OTE" while the engine had moved to order block
   wick/body/50 entries. The text now reports the mode actually used.
7. A NaN ATR produced a NaN structure_limit, which made every rupee target
   silently "reachable". Guarded.
8. bars was parsed in several places with different failure behaviour. One
   helper now does it everywhere.
9. build_signal() had a broken dict literal — the "base.update({...})" call
   for the ticket fields was never closed before the trailing-status try/except
   was pasted inside it, which is a syntax error and means this file could not
   even be imported. The dict is now closed properly and the trailing-status
   block runs as its own step after it.
10. That trailing-status block called backtest.simulate(...), but the module
    is imported as "import backtest as C" — "backtest" was never defined, so
    every call raised NameError and silently fell into the except branch,
    always reporting live_status as NOT_RUN. Now calls C.simulate(...).
"""

import os
import threading
import time
import traceback
from collections import OrderedDict

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

import backtest as C
import data as D
import diagnostics as DG
import entry_quality as EQ
import mtf_engine as mtf
import risk as R
mtf.TF_MINUTES["15m"] = 5

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-store"
    return response

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "AVAX", "LINK", "DOGE", "ADA", "DEXE", "BANK"]
SIGNAL_TTL = int(os.environ.get("SIGNAL_TTL", 120))
REPORT_TTL = int(os.environ.get("REPORT_TTL", 3600))
LIVE_BARS_5M = int(os.environ.get("LIVE_BARS_5M", 1200))
REPORT_BARS_5M = D.clamp_bars(
    os.environ.get("REPORT_BARS_5M", 4000)
)
# /api/portfolio does four symbols in one request. Left at 10,000 bars each on
# a 0.1 CPU instance it will not finish inside any sane timeout, so it gets its
# own lower ceiling rather than silently hanging.
PORTFOLIO_MAX_BARS = int(os.environ.get("PORTFOLIO_MAX_BARS", 4000))

# 512 MB instance. A 10,000-bar report with its trade log is not small, and an
# unbounded dict of them is an out-of-memory kill waiting to happen.
CACHE_MAX_ENTRIES = int(os.environ.get("CACHE_MAX_ENTRIES", 24))

_cache = OrderedDict()
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# INFRASTRUCTURE
# ---------------------------------------------------------------------------
def cached(key, ttl, fn):
    """TTL cache with a hard entry cap and oldest-first eviction.

    The function is deliberately called OUTSIDE the lock. Holding the lock
    across a 60 second backtest would serialise every request behind it, which
    on a single gthread worker means the whole service stalls.
    """
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            _cache.move_to_end(key)
            return hit[1], True

    val = fn()

    with _lock:
        _cache[key] = (now, val)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return val, False


def json_safe(obj):
    """Make anything jsonify-able.

    Two things bite here. numpy scalars are not JSON types, and NaN/inf are
    emitted by Flask as bare NaN/Infinity tokens which are NOT valid JSON —
    the browser's JSON.parse throws and the dashboard shows a blank card with
    no useful error. Both become null.
    """
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return json_safe(obj.tolist())
    return obj


def ok(payload, status=200):
    return jsonify(json_safe(payload)), status


def bars_arg(default=None, cap=None):
    """One place that parses ?bars=. clamp_bars already handles junk input by
    falling back to the default, so this only adds the per-endpoint ceiling."""
    raw = request.args.get("bars", default if default is not None
                           else REPORT_BARS_5M)
    n = D.clamp_bars(raw)
    return min(n, cap) if cap else n


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else round(v, 8)


def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def blocker_text(code):
    """Machine codes are for counting; humans get the sentence."""
    return mtf.BLOCKERS.get(code, code)


# ---------------------------------------------------------------------------
# SHARED HEAVY WORK
# ---------------------------------------------------------------------------
def _load(symbol, bars, live=False):
    frames, meta = D.load_mtf(
        symbol,
        bars,
        live=live,
    )
    if frames is not None:
        frames["15m"] = frames["5m"]
    return frames, (meta or {})


def report_for(symbol, bars):
    """THE single entry point for a full backtest.

    Everything that needs a report goes through here, so a page that hits
    /api/report, /api/trades and /api/diagnostic for the same symbol runs the
    backtest once instead of three times.
    """
    def _build():
        frames, meta = _load(symbol, bars)
        if frames is None:
            return {"symbol": symbol,
                    "error": meta.get("error", "no data"),
                    "data_quality": meta}
        # Use the strategy defaults from mtf_engine.py as the single
        # source of truth. Do not silently override research parameters here.
        strategy_params = dict(mtf.PARAMS)

        rep = C.full_report(
            symbol,
            frames["5m"],
            frames["15m"],
            frames["1h"],
            params=strategy_params,
        )
        rep["source"] = meta.get("source")
        rep["data_quality"] = meta
        return rep

    res, hit = cached(("report", symbol, bars), REPORT_TTL, _build)
    return res, hit


# ---------------------------------------------------------------------------
# LIVE SIGNAL
# ---------------------------------------------------------------------------
def build_signal(symbol):
    frames, meta = _load(
        symbol,
        LIVE_BARS_5M,
        live=True,
    )
    if frames is None:
        return {"symbol": symbol, "action": "NO_TRADE",
                "blocker": "NO_DATA",
                "reason": meta.get("error", "no data"),
                "data_quality": meta}

    df5, df15, df1h = frames["5m"], frames["15m"], frames["1h"]
    if len(df5) < 200:
        return {"symbol": symbol, "action": "NO_TRADE", "blocker": "NO_DATA",
                "reason": f"only {len(df5)} 5m bars, not enough history",
                "source": meta.get("source")}

    # calibration is a trailing rolling window, so live and backtest compute
    # the identical threshold on the identical candles
    ctx = mtf.build_context(df5, df15, df1h)

    # data.load_mtf already dropped the forming candle, so the final row IS the
    # last closed bar
    i = len(df5) - 1
    ts = mtf._ts(df5["ts"]).iat[i]
    atr = float(_atr(df5).iat[i])
    price = float(df5["close"].iat[i])

    bias = ctx["bias"][i]
    trig = ctx["trigger"][i] or "none"
    # same call the backtest makes: no price arguments, so this reports a
    # RESTING LIMIT rather than pretending the bar already filled it
    action, setup, side, level, code = mtf.decide(
        bias, ctx["trigger"][i], ctx["setups"], ts)

    base = {
        "symbol": symbol, "source": meta.get("source"), "price": _f(price),
        "last_closed": str(ts),
        "htf_bias_1h": bias,
        "setup_15m": bool(mtf.active_setups_at(
            ctx["setups"], ts, "bull" if bias == "BULLISH" else
            "bear" if bias == "BEARISH" else None)),
        "trigger_5m": trig,
        "atr_5m": _f(atr),
        "blocker": code,
        "reason": blocker_text(code),
    }

    if action == "NO_TRADE" or setup is None:
        base["action"] = "NO_TRADE"
        return base

    # a NaN ATR would make structure_limit NaN, and every comparison against
    # NaN is False, which silently marked unreachable targets as reachable
    if not np.isfinite(atr) or atr <= 0:
        base["action"] = "NO_TRADE"
        base["blocker"] = "NO_ATR"
        base["reason"] = "ATR unavailable on the last closed bar"
        return base

    sl = setup.stop_level
    limit = level + 6 * atr if side == "bull" else level - 6 * atr
    s = R.size_position(symbol, action, level, sl, atr=atr,
                        structure_limit=limit)

    if not s.ok:
        base["action"] = "NO_TRADE"
        base["blocker"] = "NOT_SIZEABLE"
        base["reason"] = f"setup valid but not sizeable: {s.reason}"
        return base

    reachable = [t for t in s.tps if t.get("reachable")]
    potential = max((t["net_inr"] for t in reachable), default=0)
    rr = round(potential / s.risk_inr, 2) if s.risk_inr > 0 else None
    max_cost = float(os.environ.get("MAX_COST_IN_R", 0.15))

    base.update({
        "action": action,
        "entry": _f(level), "sl": _f(sl),
        "tp1": s.tps[0] if len(s.tps) > 0 else None,
        "tp2": s.tps[1] if len(s.tps) > 1 else None,
        "tp3": s.tps[2] if len(s.tps) > 2 else None,
        "position_size_qty": _f(s.qty),
        "notional_inr": _f(s.notional_inr), "margin_inr": _f(s.margin_inr),
        "leverage_allowed": s.leverage_allowed,
        "leverage_used": s.leverage_used,
        "leverage_max_venue": s.leverage_max,
        "risk_inr": _f(s.risk_inr),
        "potential_profit_inr": _f(potential),
        "risk_reward": rr,
        "fees_inr": _f(s.fees_inr), "slippage_inr": _f(s.slippage_inr),
        "sl_distance_pct": _f(s.sl_distance_pct),
        "cost_in_r": _f(s.cost_in_r),
        "order_type": "resting limit — fills on a later candle, or not at all",
        "distance_to_entry_pct": _f((level - price) / price * 100)
        if price else None,
        "tradeable": bool(np.isfinite(s.cost_in_r) and s.cost_in_r <= max_cost),
        "zone": {"top": _f(setup.zone_top), "bottom": _f(setup.zone_bottom),
                 "has_fvg": setup.has_fvg, "swept": setup.swept,
                 "imbalance": setup.imbalance,
                 "entry_mode": setup.entry_mode},
        "reason": (f"1H {bias} + 5M "
                   f"{'OB+FVG' if setup.has_fvg else 'OB'} after liquidity "
                   f"sweep + 5M {trig} shift, entry at the order block "
                   f"{setup.entry_mode}"),
    })

    # --- LIVE TRAILING & STOP STATUS TRACKING ---
    # Run the manage-loop simulation forward from this setup so the ticket can
    # report whether the stop has already trailed or hit breakeven. This uses
    # the same simulate() the backtest uses, imported here as C.
    try:
        sim_legs, sim_hit, sim_outcome, sim_ex = C.simulate(
            df5, "bull" if action == "BUY" else "bear",
            level, sl, s.tps, start=max(0, len(df5) - 200), max_hold=100,
            manage=True, cost_r=s.cost_in_r
        )
        current_active_sl = sim_legs[-1][1] if sim_legs else sl

        base.update({
            "live_status": sim_outcome,
            "tp_hit_status": sim_hit,
            "current_sl": round(current_active_sl, 8),
            "trailing_active": len(sim_hit) > 0
        })
    except Exception:
        base.update({
            "live_status": "NOT_RUN",
            "current_sl": sl,
            "trailing_active": False
        })
    return base


# ---------------------------------------------------------------------------
# DERIVED VIEWS  (all reuse report_for)
# ---------------------------------------------------------------------------
def build_trade_log(symbol, limit, bars):
    rep, _ = report_for(symbol, bars)
    if rep.get("error"):
        return {"symbol": symbol, "error": rep["error"]}
    return {"symbol": symbol, "source": rep.get("source"),
            "total": rep.get("trade_log_total", 0),
            "trades": (rep.get("trade_log") or [])[:limit]}


def build_diagnostic(symbol, bars):
    """Missed-move analysis, with the strategy's own trades supplied so a move
    it actually traded is not counted as a miss."""
    rep, _ = report_for(symbol, bars)
    if rep.get("error"):
        return {"symbol": symbol, "error": rep["error"]}

    frames, meta = _load(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": meta.get("error", "no data")}

    log = rep.get("trade_log") or []
    taken = [t for t in log if t.get("arm") == "smc_mtf"]
    smc_trades = [t for t in log if t.get("arm") == "smc"]
    oos = {m["arm"]: m for m in rep.get("out_of_sample", [])}

    out = DG.missed_move_report(symbol, frames["5m"], frames["15m"],
                                frames["1h"], taken_trades=taken)
    out["source"] = rep.get("source")
    out["coverage_days"] = (rep.get("data_quality") or {}).get("coverage_days")
    out["per_asset"] = {
        "SMC": DG.per_asset_stats(symbol, oos.get("SMC"), smc_trades),
        "SMC_MTF": DG.per_asset_stats(symbol, oos.get("SMC_MTF"), taken),
    }
    # blockers arrive as machine codes; give the reader the sentence too
    out["blockers_explained"] = {
        code: {"count": n, "meaning": blocker_text(code)}
        for code, n in (out.get("blockers") or {}).items()
    }
    out["_trades"] = smc_trades
    return out


def build_entry_quality(symbol, bars):
    frames, meta = _load(symbol, bars)
    if frames is None:
        return {"symbol": symbol, "error": meta.get("error", "no data")}
    out = EQ.full_diagnosis(symbol, frames["5m"], frames["15m"], frames["1h"])
    out["source"] = meta.get("source")
    out["coverage_days"] = meta.get("coverage_days")
    return out


def probe_data(symbol, bars, venue="coindcx"):
    """Pagination only. No signals, no backtest, no metrics.

    Answers one question in seconds instead of minutes: when the loader asks
    the venue for N candles, how many does it get, in how many requests, and
    how long did it hold the worker.
    """
    t0 = time.time()
    per_tf = {}
    need = D.required_bars(bars)

    for tf in ("5m", "15m", "1h"):
        t1 = time.time()
        try:
            df, meta = D.fetch_ohlcv_history(venue, symbol, tf, need[tf])
        except Exception as e:
            per_tf[tf] = {"requested_bars": need[tf], "actual_bars": 0,
                          "error": str(e),
                          "seconds": round(time.time() - t1, 2)}
            continue
        meta = meta or {}
        if df is None or df.empty:
            per_tf[tf] = {"requested_bars": need[tf], "actual_bars": 0,
                          "error": meta.get("error", "no data"),
                          "seconds": round(time.time() - t1, 2)}
            continue
        pages = meta.get("pages_fetched", 0)
        got = meta.get("actual_bars", len(df))
        per_tf[tf] = {
            "requested_bars": need[tf], "actual_bars": got,
            "short_by": meta.get("short_by", max(0, need[tf] - got)),
            "pages_fetched": pages,
            "bars_per_page": round(got / pages, 1) if pages else None,
            "coverage_start": meta.get("coverage_start"),
            "coverage_end": meta.get("coverage_end"),
            "seconds": round(time.time() - t1, 2),
            "warnings": D.validate_ohlcv(df, tf),
        }

    five = per_tf.get("5m", {})
    got = five.get("actual_bars", 0)
    want = max(five.get("requested_bars", 1), 1)
    pages = five.get("pages_fetched", 0) or 0

    if got == 0:
        diag = f"{venue} returned nothing. Check the pair string."
    elif got >= want * 0.9:
        diag = "Pagination works. The venue honours the from/to window."
    elif pages <= 2 and got <= D.PAGE_LIMIT * 1.2:
        diag = ("Paging made no progress past the first window. The venue is "
                "very likely ignoring `from` and always returning the most "
                "recent candles. Backward paging will not work against this "
                "endpoint and a different history source is needed.")
    else:
        diag = (f"Paging advanced across {pages} requests but the venue ran "
                f"out at {got} candles. That is all the history it holds.")

    return {"symbol": symbol, "source": venue,
            "requested_bars_5m": bars,
            "actual_bars_5m": got,
            "coverage_days": round(got * 5 / 1440.0, 1),
            "diagnosis": diag,
            "per_timeframe": per_tf,
            "total_seconds": round(time.time() - t0, 2),
            "render_timeout_seconds": 600}


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
def _bad_symbol(symbol):
    return symbol not in SYMBOLS


@app.route("/api/health")
def health():
    return ok({"status": "ok", "service": "smc-mtf-scanner",
               "symbols": SYMBOLS, "cached": len(_cache),
               "cache_max_entries": CACHE_MAX_ENTRIES,
               "default_report_bars": REPORT_BARS_5M,
               "min_report_bars": D.MIN_BACKTEST_BARS,
               "max_report_bars": D.MAX_BACKTEST_BARS,
               "portfolio_max_bars": PORTFOLIO_MAX_BARS,
               "time": int(time.time())})


@app.route("/api/config")
def config():
    return ok({"costs": R.cost_summary(),
               "params": mtf.PARAMS,
               "blockers": mtf.BLOCKERS,
               "leverage": {s: {"venue_max": R.MAX_LEVERAGE_BY_SYMBOL.get(s),
                                "allowed": R.allowed_leverage(s)}
                            for s in SYMBOLS}})


@app.route("/api/signal/<symbol>")
def signal_one(symbol):
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    try:
        res, hit = cached(("sig", symbol), SIGNAL_TTL,
                          lambda: build_signal(symbol))
        return ok({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "action": "NO_TRADE",
                   "error": str(e)}, 500)


@app.route("/api/signals")
def signals():
    out = []
    for s in SYMBOLS:
        try:
            res, _ = cached(("sig", s), SIGNAL_TTL,
                            lambda s=s: build_signal(s))
            out.append(res)
        except Exception as e:
            traceback.print_exc()
            out.append({"symbol": s, "action": "NO_TRADE", "error": str(e)})
    return ok({"generated_at": int(time.time()), "results": out,
               "actionable": sum(1 for r in out
                                 if r.get("action") in ("BUY", "SELL")
                                 and r.get("tradeable"))})


@app.route("/api/report/<symbol>")
def report(symbol):
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    try:
        bars = bars_arg()
        res, hit = report_for(symbol, bars)
        payload = dict(res)

        # the log is large; opt in with ?trades=1 so the dashboard poll
        # stays small
        want = request.args.get("trades") in ("1", "true", "yes")
        if not want:
            payload.pop("trade_log", None)
        else:
            try:
                lim = min(int(request.args.get("limit", 200)), 1000)
            except (TypeError, ValueError):
                lim = 200
            payload["trade_log"] = (payload.get("trade_log") or [])[:lim]

        v = payload.get("verdict") or {}
        return ok({**payload, "from_cache": hit,
                   "verdict_code": v.get("verdict")})
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "error": str(e)}, 500)


@app.route("/api/trades/<symbol>")
def trades(symbol):
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    try:
        limit = min(int(request.args.get("limit", 150)), 500)
    except (TypeError, ValueError):
        limit = 150
    try:
        bars = bars_arg()
        res = build_trade_log(symbol, limit, bars)
        return ok(res)
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "error": str(e)}, 500)


@app.route("/api/data-probe/<symbol>")
def data_probe(symbol):
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    venue = request.args.get("venue", "coindcx")
    try:
        bars = bars_arg()
        res, hit = cached(("probe", symbol, bars, venue), 300,
                          lambda: probe_data(symbol, bars, venue))
        return ok({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "error": str(e)}, 500)


@app.route("/api/diagnostic/<symbol>")
def diagnostic(symbol):
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    try:
        bars = bars_arg()
        res, hit = cached(("diag", symbol, bars), REPORT_TTL,
                          lambda: build_diagnostic(symbol, bars))
        payload = {k: v for k, v in res.items() if k != "_trades"}
        return ok({**payload, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "error": str(e)}, 500)


@app.route("/api/portfolio")
def portfolio():
    """All four assets plus a portfolio total built from pooled trades.

    Capped at PORTFOLIO_MAX_BARS because this is four full backtests in one
    request. Ask for more per symbol via /api/report/<symbol>?bars=...
    """
    bars = bars_arg(default=PORTFOLIO_MAX_BARS, cap=PORTFOLIO_MAX_BARS)
    per_asset, all_trades, diags, errors = [], [], [], []

    for s in SYMBOLS:
        try:
            res, _ = cached(("diag", s, bars), REPORT_TTL,
                            lambda s=s: build_diagnostic(s, bars))
            if res.get("error"):
                per_asset.append({"symbol": s, "error": res["error"]})
                errors.append({"symbol": s, "error": res["error"]})
                continue
            per_asset.append(res["per_asset"]["SMC"])
            all_trades.extend(res.get("_trades") or [])
            diags.append({k: v for k, v in res.items()
                          if k in ("symbol", "significant_moves",
                                   "true_missed_signals", "valid_no_trades",
                                   "capture_rate_pct", "true_miss_rate_pct",
                                   "blockers")})
        except Exception as e:
            traceback.print_exc()
            per_asset.append({"symbol": s, "error": str(e)})
            errors.append({"symbol": s, "error": str(e)})

    merged = {}
    for d in diags:
        for k, v in (d.get("blockers") or {}).items():
            merged[k] = merged.get(k, 0) + v

    return ok({
        "bars_per_symbol": bars,
        "bars_capped_at": PORTFOLIO_MAX_BARS,
        "note": ("four backtests in one request, so the bar count is capped "
                 "here. Use /api/report/<symbol>?bars=... for a deeper "
                 "single-symbol run."),
        "per_asset": per_asset,
        "errors": errors,
        "portfolio": DG.portfolio_from_trades(all_trades),
        "market_wide_diagnostic": {
            "symbols_analysed": len(diags),
            "total_significant_moves": sum(d["significant_moves"]
                                           for d in diags),
            "true_missed_signals": sum(d["true_missed_signals"]
                                       for d in diags),
            "valid_no_trades": sum(d["valid_no_trades"] for d in diags),
            "blockers": dict(sorted(merged.items(), key=lambda kv: -kv[1])),
            "blockers_explained": {
                code: {"count": n, "meaning": blocker_text(code)}
                for code, n in sorted(merged.items(), key=lambda kv: -kv[1])
            },
            "per_symbol": diags,
        },
    })


@app.route("/api/entry-quality/<symbol>")
def entry_quality(symbol):
    """Root-cause diagnostics: entry vs exit failure, gate value, position
    modes, score buckets. Heavy — one symbol at a time."""
    symbol = symbol.upper()
    if _bad_symbol(symbol):
        return ok({"error": f"symbol must be one of {SYMBOLS}"}, 400)
    try:
        bars = bars_arg()
        res, hit = cached(("eq", symbol, bars), REPORT_TTL,
                          lambda: build_entry_quality(symbol, bars))
        return ok({**res, "from_cache": hit})
    except Exception as e:
        traceback.print_exc()
        return ok({"symbol": symbol, "error": str(e)}, 500)


@app.route("/")
def root():
    return ok({"service": "smc-mtf-scanner",
               "endpoints": ["/api/health", "/api/config",
                             "/api/signal/<symbol>", "/api/signals",
                             "/api/report/<symbol>",
                             "/api/trades/<symbol>",
                             "/api/data-probe/<symbol>",
                             "/api/diagnostic/<symbol>",
                             "/api/portfolio",
                             "/api/entry-quality/<symbol>"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
