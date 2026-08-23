
import json, time, traceback
import backtest as B
import mtf_engine as m
import research_data as R

SYMBOLS = ["BTC","ETH","SOL","XRP","BNB","ADA","DOGE","AVAX","LINK","DOT",
           "LTC","TRX","UNI","ATOM","NEAR","APT","ARB","OP","INJ","SUI",
           "FIL","AAVE","SAND","DEXE","BANK"]
BARS = 20000

pool = {"SMC_MTF": [], "MATCHED_RANDOM_vs_SMC_MTF": [], "SMC": []}
rows = []
t0 = time.time()

for n, sym in enumerate(SYMBOLS, 1):
    try:
        f, meta = R.load_research(sym, BARS)
        if f is None:
            print("[%d/%d] %s LOAD FAIL" % (n, len(SYMBOLS), sym), flush=True)
            continue
        rep = B.full_report(sym, f["5m"], f["15m"], f["1h"], params=dict(m.PARAMS))
        oos = {a["arm"]: a for a in rep["out_of_sample"]}
        for arm in pool:
            a = oos.get(arm)
            if a and a.get("trades"):
                pool[arm].append((a["trades"], a.get("expectancy_inr") or 0.0))
        s = oos.get("SMC_MTF", {})
        r = oos.get("MATCHED_RANDOM_vs_SMC_MTF", {})
        rows.append((sym, s.get("trades", 0), s.get("expectancy_inr"),
                     r.get("expectancy_inr")))
        print("[%d/%d] %-5s trades=%3d smc=%s rand=%s (%ds)" % (
            n, len(SYMBOLS), sym, s.get("trades", 0),
            s.get("expectancy_inr"), r.get("expectancy_inr"),
            time.time() - t0), flush=True)
    except Exception:
        print("[%d/%d] %s ERROR" % (n, len(SYMBOLS), sym), flush=True)
        traceback.print_exc()

print("\n" + "=" * 62)
print("POOLED OUT-OF-SAMPLE")
print("=" * 62)
for arm, xs in pool.items():
    tot = sum(t for t, _ in xs)
    if not tot:
        print("%-28s no trades" % arm)
        continue
    exp = sum(t * e for t, e in xs) / tot
    print("%-28s trades=%4d  expectancy=%+8.2f  symbols=%d" % (
        arm, tot, exp, len(xs)))

s = pool["SMC_MTF"]
r = pool["MATCHED_RANDOM_vs_SMC_MTF"]
if s and r:
    ns = sum(t for t, _ in s)
    nr = sum(t for t, _ in r)
    es = sum(t * e for t, e in s) / ns
    er = sum(t * e for t, e in r) / nr
    print("\nedge over matched random: %+.2f INR/trade on %d trades" % (es - er, ns))
    print("VERDICT:", "SMC_MTF BEATS random" if es > er else "SMC_MTF LOSES to random")
    print("NOTE: a positive gap on <100 trades is still not proof.")

json.dump({"rows": rows, "pool": pool}, open("/tmp/pooled.json", "w"), default=str)
print("\ntotal %ds" % (time.time() - t0))
