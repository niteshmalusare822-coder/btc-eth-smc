
import data as D, mtf_engine as m, risk as R, numpy as np

print("=" * 66)
print("CONFIG (from risk.py, not assumed)")
print("=" * 66)
for k, v in R.cost_summary().items():
    print("  %-28s %s" % (k, v))
print("  %-28s %s" % ("tp_r_ladder", R.TP_R_LADDER))
print("  %-28s %s" % ("leverage_fraction", R.LEVERAGE_FRACTION))
print("  %-28s %s" % ("min_notional_inr", R.MIN_NOTIONAL_INR))

for sym in ("BTC", "ETH"):
    f, _ = D.load_mtf(sym, 4000)
    if f is None:
        continue
    df5 = f["5m"]
    ctx = m.build_context(df5, f["15m"], f["1h"])
    ts = m._ts(df5["ts"])
    tr = df5["high"] - df5["low"]
    atr_s = tr.rolling(14, min_periods=5).mean()

    hit = None
    for i in range(len(df5) - 1, 100, -1):
        a, s, side, lvl, code = m.decide(
            ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts.iat[i])
        if code == "OK":
            hit = (i, a, s, side, lvl)
            break
    if not hit:
        print("\n%s: no OK bar in this window" % sym)
        continue

    i, action, setup, side, level = hit
    atr = float(atr_s.iat[i])
    limit = level + 6 * atr if side == "bull" else level - 6 * atr
    z = R.size_position(sym, action, level, setup.stop_level,
                        atr=atr, structure_limit=limit)

    print("\n" + "=" * 66)
    print("%s   %s   %s" % (sym, action, ts.iat[i]))
    print("=" * 66)
    if not z.ok:
        print("  NOT SIZEABLE:", z.reason)
        continue

    dist = abs(z.entry - z.sl)
    print("  %-24s Rs.%s" % ("capital", R.CAPITAL_INR))
    print("  %-24s Rs.%s  (%.1f%% of capital)" % (
        "risk cap", R.MAX_RISK_INR, 100 * R.MAX_RISK_INR / R.CAPITAL_INR))
    print("  %-24s %.6f" % ("entry", z.entry))
    print("  %-24s %.6f" % ("stop loss", z.sl))
    print("  %-24s %.6f  (%.3f%%)" % ("stop distance", dist, z.sl_distance_pct))
    print("  %-24s %.8f" % ("position size (qty)", z.qty))
    print("  %-24s Rs.%.2f" % ("notional", z.notional_inr))
    print("  %-24s Rs.%.2f" % ("margin required", z.margin_inr))
    print("  %-24s %.2fx  (allowed %.2fx, venue max %.0fx)" % (
        "leverage used", z.leverage_used, z.leverage_allowed, z.leverage_max))
    print("  -" * 32)
    print("  %-24s Rs.%.2f" % ("fees (both legs)", z.fees_inr))
    print("  %-24s Rs.%.2f" % ("slippage (both legs)", z.slippage_inr))
    for bars in (12, 96):
        fc = R.funding_cost_inr(z.notional_inr, bars, 5)
        ev = R.funding_events(bars, 5)
        print("  %-24s Rs.%.2f   (%d stamps, %d bars = %.1fh)" % (
            "funding if held %db" % bars, fc, ev, bars, bars * 5 / 60))
    total = z.fees_inr + z.slippage_inr
    print("  %-24s Rs.%.2f  (%.3f%% of notional)" % (
        "total cost (no funding)", total, 100 * total / z.notional_inr))
    print("  %-24s %.4f  %s" % ("cost in R", z.cost_in_r,
          "TRADEABLE" if z.cost_in_r <= 0.15 else "ABOVE 15% LIMIT"))
    print("  -" * 32)
    print("  %-6s %-12s %-12s %-10s %s" % ("level", "price", "gross Rs.", "net Rs.", "reachable"))
    for t in (z.tps or []):
        print("  %-6s %-12.6f %-12.2f %-10.2f %s" % (
            t["level"], t["price"], t.get("gross_inr", 0), t.get("net_inr", 0),
            t.get("reachable")))
    print("  %-6s %-12.6f %-12.2f %-10.2f" % (
        "SL", z.sl, -z.gross_loss_inr, -z.risk_inr))
    print("\n  worst case loss  Rs.%.2f  (%.1f%% of capital)" % (
        z.risk_inr, 100 * z.risk_inr / R.CAPITAL_INR))
