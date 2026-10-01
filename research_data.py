 """Research-only loader using data.py's robust built-in load_mtf logic.
"""
import data as D

VENUE = "coindcx"

def load_research(symbol, bars_5m):
    # data.py madhil load_mtf direct call karu ya, je sarv pagination handle karte
    res, meta = D.load_mtf(symbol, bars_5m, allow_mixed=False, live=False)
    if res is None:
        return None, meta
    return res, {"source": VENUE, "coverage_days": meta.get("coverage_days")}
