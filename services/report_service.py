import os
import time

import backtest as B
import data as D
import diagnostics as DG
import entry_quality as EQ

REPORT_BARS_5M = D.clamp_bars(
    os.environ.get("REPORT_BARS_5M", D.DEFAULT_BACKTEST_BARS)
)


def build_report(symbol, bars=None):
    bars = D.clamp_bars(
        bars if bars is not None else REPORT_BARS_5M
    )

    frames, meta = D.load_mtf(symbol, bars)

    if frames is None:
        return {
            "symbol": symbol,
            "error": meta.get("error", "no data"),
            "data": meta,
        }

    rep = B.full_report(
        symbol,
        frames["5m"],
        frames["15m"],
        frames["4h"],
    )

    rep["source"] = meta.get("source")
    rep["data_quality"] = meta
    return rep


def build_trade_log(symbol, limit=150, bars=None):
    frames, meta = D.load_mtf(
        symbol,
        D.clamp_bars(bars or REPORT_BARS_5M)
    )

    if frames is None:
        return {
            "symbol": symbol,
            "error": meta.get("error", "no data"),
        }

    rep = B.full_report(
        symbol,
        frames["5m"],
        frames["15m"],
        frames["4h"],
    )

    return {
        "symbol": symbol,
        "source": meta.get("source"),
        "total": rep.get("trade_log_total", 0),
        "trades": (rep.get("trade_log") or [])[:limit],
    }


def probe_data(symbol, bars):
    t0 = time.time()
    per_tf = {}
    need = D.required_bars(bars)

    for tf in ("5m", "15m", "4h"):
        t1 = time.time()
        df, meta = D.fetch_ohlcv_history(
            "coindcx",
            symbol,
            tf,
            need[tf]
        )

        if df is None:
            per_tf[tf] = {
                "requested_bars": need[tf],
                "actual_bars": 0,
                "error": meta.get("error"),
                "seconds": round(time.time() - t1, 2),
            }
            continue

        pages = meta["pages_fetched"]
        got = meta["actual_bars"]

        per_tf[tf] = {
            "requested_bars": need[tf],
            "actual_bars": got,
            "short_by": meta["short_by"],
            "pages_fetched": pages,
            "bars_per_page": round(got / pages, 1) if pages else None,
            "coverage_start": meta["coverage_start"],
            "coverage_end": meta["coverage_end"],
            "seconds": round(time.time() - t1, 2),
            "warnings": D.validate_ohlcv(df, tf),
        }

    five = per_tf.get("5m", {})
    got = five.get("actual_bars", 0)
    want = five.get("requested_bars", 1)
    pages = five.get("pages_fetched", 0)

    if got == 0:
        diag = "CoinDCX returned nothing. Check the pair string."
    elif got >= want * 0.9:
        diag = "Pagination works. The venue honours the from/to window."
    elif pages <= 2 and got <= D.PAGE_LIMIT * 1.2:
        diag = (
            "Paging made no progress past the first window. CoinDCX is "
            "very likely ignoring `from` and always returning the most "
            "recent candles."
        )
    else:
        diag = (
            f"Paging advanced across {pages} requests but the venue ran "
            f"out at {got} candles."
        )

    return {
        "symbol": symbol,
        "source": "coindcx",
        "requested_bars_5m": bars,
        "actual_bars_5m": got,
        "coverage_days": round(got * 5 / 1440.0, 1),
        "diagnosis": diag,
        "per_timeframe": per_tf,
        "total_seconds": round(time.time() - t0, 2),
        "render_timeout_seconds": 600,
    }


def build_diagnostic(symbol, bars):
    frames, meta = D.load_mtf(
        symbol,
        D.clamp_bars(bars)
    )

    if frames is None:
        return {
            "symbol": symbol,
            "error": meta.get("error", "no data"),
        }

    rep = B.full_report(
        symbol,
        frames["5m"],
        frames["15m"],
        frames["4h"],
    )

    taken = [
        t for t in (rep.get("trade_log") or [])
        if t["arm"] == "smc_mtf"
    ]

    smc_trades = [
        t for t in (rep.get("trade_log") or [])
        if t["arm"] == "smc"
    ]

    oos = {
        m["arm"]: m
        for m in rep["out_of_sample"]
    }

    out = DG.missed_move_report(
        symbol,
        frames["5m"],
        frames["15m"],
        frames["4h"],
        taken_trades=taken,
    )

    out["source"] = meta.get("source")
    out["coverage_days"] = meta.get("coverage_days")
    out["per_asset"] = {
        "SMC": DG.per_asset_stats(
            symbol,
            oos.get("SMC"),
            smc_trades,
        ),
        "SMC_MTF": DG.per_asset_stats(
            symbol,
            oos.get("SMC_MTF"),
            taken,
        ),
    }
    out["_trades"] = smc_trades
    return out


def build_entry_quality(symbol, bars):
    frames, meta = D.load_mtf(
        symbol,
        D.clamp_bars(bars)
    )

    if frames is None:
        return {
            "symbol": symbol,
            "error": meta.get("error", "no data"),
        }

    out = EQ.full_diagnosis(
        symbol,
        frames["5m"],
        frames["15m"],
        frames["4h"],
    )

    out["source"] = meta.get("source")
    out["coverage_days"] = meta.get("coverage_days")
    return out
