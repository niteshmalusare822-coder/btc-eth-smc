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


@app.route("/api/live-prices")
def live_prices_route():
    with LIVE_WS_LOCK:
        out = {s: {"live_price": _f(v["price"]),
                    "age_sec": round(time.time() - v["updated_at"], 1)}
               for s, v in LIVE_PRICE.items()}
    return ok({"prices": out, "time": int(time.time())})


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
                             "/api/entry-quality/<symbol>",
