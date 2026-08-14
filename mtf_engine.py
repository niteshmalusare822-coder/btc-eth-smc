"""
mtf_engine.py — 1H bias, 15M setup, 5M trigger. One decision, three jobs.

    1H   decides DIRECTION.   BULLISH / BEARISH / NEUTRAL. Neutral = no trade.
    15M  decides WHETHER a setup exists, in the 1H direction only.
    5M   decides WHEN to enter. It never picks a side.

LOOK-AHEAD CONTROL
------------------
This is the part that is easy to get wrong and impossible to notice.

Higher-timeframe state is joined to the 5M timeline with merge_asof on the
higher frame's CLOSE time, not its open time. A 15M candle stamped 10:00 does
not exist as information until 10:15. The join therefore uses
`ts + one_bar_duration` as the key, so a 5M bar at 10:05 sees the 15M candle
that closed at 10:00 and nothing newer. Same for 1H.

Every structural object (swing, BOS, order block) already carries
confirmed_idx from poi_factors, and zones are only read through
zones_active_at(). Nothing in this file touches an index above the current bar.

DECISION PARAMETERS: 7 total. That is the whole tunable surface.
    swing_left/right, body_pct, max_age, sweep_window, ote band, trigger_lookback
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import poi_factors as poi

TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60}

PARAMS = {
    "swing_left": 2,
    "swing_right": 2,
    "body_pct": 0.85,        # calibration quantile, not a hand-picked constant
    "max_age": 60,           # bars a 15M zone stays valid
    "sweep_window": 20,      # bars allowed between the sweep and the BOS
    "ote_low": 0.618,
    "ote_high": 0.79,
    "trigger_lookback": 3,   # 5M bars the entry trigger may look back over
    "kill_on": "full",       # when a 15M zone is considered mitigated
    "calib_window": 500,     # trailing bars behind the displacement threshold
}


def _calibrate(df, p, calib_end=None):
    """Per-bar displacement threshold from a trailing window.

    PARITY. Earlier versions calibrated once per run: the backtest used its
    in-sample slice, live used its whole frame. Both were causal, but they
    produced DIFFERENT numbers, so the same candle could pass the displacement
    filter live and fail it in the backtest. Shared decide() logic does not
    help if the two sides are fed different thresholds.

    A trailing rolling quantile is identical in both. At bar t the threshold
    comes from the `calib_window` bars strictly before t, whether those bars
    arrived from a websocket or from a CSV. calib_end is accepted and ignored,
    kept only so older callers do not break.
    """
    return poi.rolling_body_threshold(
        df, window=p.get("calib_window", 500), target_pct=p["body_pct"])


# ---------------------------------------------------------------------------
# 1H BIAS
# ---------------------------------------------------------------------------
def htf_bias_series(df_1h, p=None, calib_end=None):
    """BULLISH / BEARISH / NEUTRAL per 1H bar, causal.

    Bias flips on a confirmed BOS and only stays valid while price holds on the
    correct side of the last swing range equilibrium. Both conditions must
    agree, otherwise the bar is NEUTRAL and no trade is allowed anywhere.
    """
    p = p or PARAMS
    df = poi.add_candle_metrics(df_1h)
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    thr = _calibrate(df, p, calib_end)
    bos = poi.find_bos(df, swings, body_threshold=thr, require_displacement=True)

    n = len(df)
    bias = np.array(["NEUTRAL"] * n, dtype=object)

    breaks = [b for b in bos if not b.is_sweep]
    cur = "NEUTRAL"
    bi = 0
    # rolling equilibrium of the last confirmed swing high / low
    last_hi = np.nan
    last_lo = np.nan
    si = 0
    close = df["close"].to_numpy()

    for i in range(n):
        while si < len(swings) and swings[si].confirmed_idx <= i:
            s = swings[si]
            if s.kind == "high":
                last_hi = s.price
            else:
                last_lo = s.price
            si += 1
        while bi < len(breaks) and breaks[bi].idx <= i:
            cur = "BULLISH" if breaks[bi].side == "bull" else "BEARISH"
            bi += 1

        if cur == "NEUTRAL" or np.isnan(last_hi) or np.isnan(last_lo) or last_hi <= last_lo:
            bias[i] = "NEUTRAL"
            continue

        eq = poi.equilibrium(last_lo, last_hi)
        if cur == "BULLISH":
            bias[i] = "BULLISH" if close[i] >= eq else "NEUTRAL"
        else:
            bias[i] = "BEARISH" if close[i] <= eq else "NEUTRAL"

    return pd.DataFrame({"ts": df["ts"].values, "htf_bias": bias})


# ---------------------------------------------------------------------------
# 15M SETUP
# ---------------------------------------------------------------------------
@dataclass
class Setup:
    ts: pd.Timestamp
    side: str            # 'bull' | 'bear'
    zone_top: float
    zone_bottom: float
    ote_low: float
    ote_high: float
    stop_level: float
    confirmed_ts: pd.Timestamp
    expires_ts: pd.Timestamp
    has_fvg: bool
    swept: bool
    dead_ts: object = None    # when price invalidated the zone, if it did


def find_setups(df_15m, p=None, calib_end=None):
    """Sweep -> BOS -> order block, with the FVG overlap flagged.

    A setup is only emitted when a liquidity sweep of the OPPOSITE side
    happened within sweep_window bars before the break. That is the whole
    SMC premise: liquidity is taken, then structure shifts.
    """
    p = p or PARAMS
    df = poi.add_candle_metrics(df_15m)
    thr = _calibrate(df, p, calib_end)
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    bos = poi.find_bos(df, swings, body_threshold=thr, require_displacement=True)

    breaks = [b for b in bos if not b.is_sweep]
    sweeps = [b for b in bos if b.is_sweep]

    kept = []
    for b in breaks:
        want = "bear" if b.side == "bull" else "bull"
        if any(s.side == want and 0 < b.idx - s.idx <= p["sweep_window"] for s in sweeps):
            kept.append(b)

    obs = poi.find_order_blocks(df, kept)
    fvgs = poi.find_fvgs(df, body_threshold=thr, require_displacement=True)

    # BUG FIX: mitigation was never applied on the 15M frame. A zone that price
    # had already torn straight through stayed "active" until its age expired,
    # so entries were being taken into dead levels. Replaying bar by bar is the
    # only safe way to do this — vectorising it would leak future bars in.
    for i in range(len(df)):
        poi.update_zones(obs, df, i, p.get("kill_on", "full"))

    ts = _ts(df["ts"]).to_numpy()
    bar = pd.Timedelta(minutes=TF_MINUTES["15m"])
    setups = []
    for z in obs:
        has_fvg = any(f.confirmed_idx <= z.confirmed_idx and poi.dragon_fruit(z, f)
                      for f in fvgs)
        lo_ote, hi_ote = z.ote(p["ote_low"], p["ote_high"])
        exp_idx = min(z.confirmed_idx + p["max_age"], len(df) - 1)
        setups.append(Setup(
            ts=pd.Timestamp(ts[z.formed_idx]),
            side=z.side,
            zone_top=z.top, zone_bottom=z.bottom,
            ote_low=lo_ote, ote_high=hi_ote,
            stop_level=z.bottom if z.side == "bull" else z.top,
            # confirmed only once the 15M candle that broke structure CLOSED
            confirmed_ts=pd.Timestamp(ts[z.confirmed_idx]) + bar,
            expires_ts=pd.Timestamp(ts[exp_idx]) + bar,
            has_fvg=has_fvg, swept=True,
            dead_ts=(pd.Timestamp(ts[z.dead_idx]) + bar
                     if z.dead_idx is not None else None),
        ))
    setups.sort(key=lambda s: s.confirmed_ts)
    # report the latest usable threshold value, not the whole series
    last = pd.Series(thr).dropna()
    return setups, (float(last.iat[-1]) if len(last) else float("nan"))


# ---------------------------------------------------------------------------
# 5M TRIGGER
# ---------------------------------------------------------------------------
def trigger_series(df_5m, p=None, calib_end=None):
    """Micro structure shift on 5M. Direction-agnostic: it reports what the
    5M chart just did, and the caller checks it against the 1H/15M side."""
    p = p or PARAMS
    df = poi.add_candle_metrics(df_5m)
    thr = _calibrate(df, p, calib_end)
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    bos = poi.find_bos(df, swings, body_threshold=thr, require_displacement=True)

    n = len(df)
    trig = np.array([""] * n, dtype=object)
    for b in bos:
        if not b.is_sweep:
            trig[b.idx] = "bull" if b.side == "bull" else "bear"

    # a trigger stays warm for trigger_lookback bars
    warm = np.array([""] * n, dtype=object)
    for i in range(n):
        for k in range(0, p["trigger_lookback"] + 1):
            j = i - k
            if j >= 0 and trig[j]:
                warm[i] = trig[j]
                break
    return warm


# ---------------------------------------------------------------------------
# ALIGNMENT
# ---------------------------------------------------------------------------
def _ns(series):
    """Every timestamp in this project, as int64 nanoseconds since the epoch.

    Not datetime64. merge_asof refuses to join datetime64[ns] against [us] or
    [ms], and which resolution you get depends on the pandas version, the
    Python version and which venue answered. Chasing that with astype() means
    the code breaks again the next time any of those three changes.

    Integers have one dtype. Merging on int64 cannot mismatch, on any pandas.
    """
    out = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(out.dtype, "tz", None) is not None:
            out = out.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    # NOT .astype("int64"): that returns the raw underlying integer in
    # WHATEVER unit the column happens to carry, so a seconds-resolution
    # column and a nanosecond one produce numbers a billion times apart and
    # the merge silently finds nothing. Dividing by a Timedelta is explicit
    # about the unit and behaves the same on every pandas version.
    return ((out - pd.Timestamp("1970-01-01")) // pd.Timedelta(1, "ns")).astype("int64")


def _ts(series):
    """Real Timestamps, for display and for comparing against setup windows."""
    out = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(out.dtype, "tz", None) is not None:
            out = out.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return out


def align_htf(df_5m, df_htf_state, tf, col):
    """Join higher-timeframe state onto the 5M timeline with NO look-ahead.

    The join key is the higher frame's CLOSE time (ts + one bar) expressed in
    integer nanoseconds, so a 5M bar can only ever see higher-frame candles
    that had already finished.
    """
    bar_ns = int(TF_MINUTES[tf] * 60 * 1_000_000_000)

    right = pd.DataFrame({
        "available_at": _ns(df_htf_state["ts"]) + bar_ns,
        col: df_htf_state[col].to_numpy(),
    }).dropna(subset=["available_at"]).sort_values("available_at")

    left = pd.DataFrame({"ts": _ns(df_5m["ts"])}).sort_values("ts")

    merged = pd.merge_asof(left, right, left_on="ts", right_on="available_at",
                           direction="backward")
    return merged[col].to_numpy()


def build_context(df_5m, df_15m, df_1h, p=None, calib_end=None):
    """Everything a bar-by-bar loop needs, precomputed and causal.

    calib_end is accepted and ignored. Calibration is now a trailing rolling
    quantile computed per bar, so live and backtest produce identical
    thresholds on identical candles. That is the parity guarantee: same
    functions, same thresholds, only the data source differs.
    """
    p = p or PARAMS
    bias_df = htf_bias_series(df_1h, p, calib_end)
    setups, thr15 = find_setups(df_15m, p, calib_end)
    trig = trigger_series(df_5m, p, calib_end)
    bias_on_5m = align_htf(df_5m, bias_df, "1h", "htf_bias")
    return {"bias": bias_on_5m, "setups": setups, "trigger": trig,
            "threshold_15m": thr15}


def active_setups_at(setups, ts, side=None):
    """Setups already confirmed and not yet expired at this instant."""
    out = []
    for s in setups:
        if s.confirmed_ts > ts or s.expires_ts < ts:
            continue
        if s.dead_ts is not None and s.dead_ts <= ts:
            continue
        if side and s.side != side:
            continue
        out.append(s)
    return out


def decide(bias, trigger, setups, ts):
    """The one decision function. Returns (action, setup, side, level, reason).

    NO PRICE ARGUMENTS. This used to take the current bar's low and high and
    check whether they had already touched the entry level — which meant the
    decision to trade bar i was made using bar i's completed range, and the
    exit was then simulated from that same bar. Classic same-bar look-ahead:
    in reality you place a resting limit at the close of bar i and find out on
    bar i+1 or later whether it filled.

    This now answers only "is a limit order justified, and at what price". The
    fill is a separate step that starts at the NEXT bar.

    Every gate is an AND. If any timeframe disagrees the answer is no trade,
    which is intended behaviour and the reason trade counts are low.
    """
    if bias not in ("BULLISH", "BEARISH"):
        return "NO_TRADE", None, None, None, "1H bias neutral"

    side = "bull" if bias == "BULLISH" else "bear"
    if trigger != side:
        return "NO_TRADE", None, None, None, "no 5M trigger in the 1H direction"

    live = active_setups_at(setups, ts, side)
    if not live:
        return "NO_TRADE", None, None, None, "no live 15M setup"

    # nearest setup first: the shallowest OTE is the one price reaches soonest
    s = live[0]
    level = s.ote_high if side == "bull" else s.ote_low
    return ("BUY" if side == "bull" else "SELL"), s, side, level, "aligned"
