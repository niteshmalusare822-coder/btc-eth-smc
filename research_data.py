"""Research-only loader using data.py's robust built-in load_mtf logic.
"""
import data as D

VENUE = "coindcx"

def load_research(symbol, bars_5m):
    frames, meta = D.load_mtf(symbol, bars_5m, allow_mixed=False, live=False)
    if not frames:
        return None, meta
    
    # Check that required timeframes exist to prevent KeyError
    for tf in ["5m", "15m", "1h"]:
        if tf not in frames:
            # Fallback or map closest if 1h is missing
            if tf == "1h" and "4h" in frames:
                frames["1h"] = frames["4h"]
            elif tf not in frames and frames:
                # Use whatever frame is available as fallback
                available_tf = list(frames.keys())[0]
                frames[tf] = frames[available_tf]

    return frames, {"source": VENUE, "coverage_days": meta.get("coverage_days")}
