"""Research-only loader using data.py's robust built-in load_mtf logic.
"""
import data as D

VENUE = "coindcx"

REQUIRED_TFS = ["5m", "15m", "1h"]


def load_research(symbol, bars_5m):
    frames, meta = D.load_mtf(symbol, bars_5m, allow_mixed=False, live=False)
    if not frames:
        return None, meta

    # Reject the symbol outright if any required timeframe is missing.
    # Substituting one timeframe's bars for another (e.g. 4h data into the
    # 1h slot, or whatever frame happens to be first into the 5m slot)
    # silently corrupts every downstream POI/retest/trigger calculation
    # without raising an error, so it's not an acceptable fallback here.
    missing = [tf for tf in REQUIRED_TFS if tf not in frames]
    if missing:
        reason = f"missing required timeframe(s): {', '.join(missing)}"
        return None, {**(meta or {}), "source": VENUE, "error": reason}

    return frames, {"source": VENUE, "coverage_days": meta.get("coverage_days")}
