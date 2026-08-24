import numpy as np, research_data as R, mtf_engine as m

print("stop distance needed for cost_in_R <= 0.15 : 0.93%\n")
for sym in ("BTC", "ETH", "SOL", "LINK"):
    f, _ = R.load_research(sym, 20000)
    if f is None: continue
    print(sym)
    for tf in ("5m", "15m", "1h"):
        st, _ = m.find_setups(f[tf])
        d = [abs(s.entry_level - s.stop_level) / s.entry_level * 100
             for s in st if s.entry_level]
        if not d: 
            print("   %-4s no setups" % tf); continue
        med = float(np.median(d))
        viable = sum(1 for x in d if x >= 0.93)
        print("   %-4s setups=%3d  median stop=%.3f%%  cost_in_R=%.2f  "
              "viable=%d/%d" % (tf, len(st), med, 0.14/med, viable, len(d)))
    print()
