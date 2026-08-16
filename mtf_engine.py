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
    # OB entry model from the source material: "wick", "body" or "50".
    # OTE is a different school's entry and is no longer used for order blocks.
    "ob_entry_mode": "body",
    "require_ob_sweep": True,        # the OB candle must take prior liquidity
    "require_ob_imbalance": True,    # a gap must sit next to the OB
    "imbalance_window": 3,
    "stop_buffer_frac": 0.10,        # padding beyond the OB wick
    "ote_low": 0.618,
    "ote_high": 0.79,
    "trigger_lookback": 3,   # 5M bars the entry trigger may look back over
    "kill_on": "full",       # when a 15M zone is considered mitigated
    "calib_window": 500,     # trailing bars behind the displacement threshold

    # ── STRUCTURE CONFIRMATION (off by default so A/B stays possible) ──
    # A BOS says a level broke. It does not say the market accepted the break.
    # Requiring a fresh HH+HL (bull) or LL+LH (bear) afterwards is the
    # difference between "a level broke" and "structure shifted".
    #
    # OFF by default. Turning it on must be justified out of sample against
    # the unchanged baseline, not assumed.
    "require_structure_confirmation": False,
    "confirm_bars": 2,          # closed 15M candles the shift must survive
    "confirm_max_wait": 12,     # bars allowed to complete confirmation
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
    entry_level: float
    entry_mode: str
    imbalance: bool
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

    confirm_at = {}
    if p.get("require_structure_confirmation"):
        kept, confirm_at = _confirm_structure(df, kept, swings, p)

    obs = poi.find_order_blocks(
        df, kept,
        lookback=p.get("ob_lookback", 30),
        require_sweep=p.get("require_ob_sweep", True),
        require_imbalance=p.get("require_ob_imbalance", True),
        imbalance_window=p.get("imbalance_window", 3))
    fvgs = poi.find_fvgs(df, body_threshold=thr, require_displacement=True)

    # BUG FIX: mitigation was never applied on the 15M frame. A zone that price
    # had already torn straight through stayed "active" until its age expired,
    # so entries were being taken into dead levels. Replaying bar by bar is the
    # only safe way to do this — vectorising it would leak future bars in.
    for i in range(len(df)):
        poi.update_zones(obs, df, i, p.get("kill_on", "full"))

    ts = _ts(df["ts"]).to_numpy()
    bar = pd.Timedelta(minutes=TF_MINUTES["15m"])
    if confirm_at:
        # a zone cannot be traded before its structure shift completed
        for z in obs:
            c = confirm_at.get(z.confirmed_idx)
            if c is not None and c > z.confirmed_idx:
                z.confirmed_idx = c

    setups = []
    for z in obs:
        has_fvg = any(f.confirmed_idx <= z.confirmed_idx and poi.dragon_fruit(z, f)
                      for f in fvgs)
        mode = p.get("ob_entry_mode", "body")
        entry = z.entry_at(mode)
        stop = z.stop_at(p.get("stop_buffer_frac", 0.10))
        exp_idx = min(z.confirmed_idx + p["max_age"], len(df) - 1)
        setups.append(Setup(
            ts=pd.Timestamp(ts[z.formed_idx]),
            side=z.side,
            zone_top=z.top, zone_bottom=z.bottom,
            ote_low=entry, ote_high=entry,
            entry_level=entry, entry_mode=mode,
            stop_level=stop,
            swept=bool(z.meta.get("swept_previous")),
            imbalance=bool(z.meta.get("imbalance")),
            # confirmed only once the 15M candle that broke structure CLOSED
            confirmed_ts=pd.Timestamp(ts[z.confirmed_idx]) + bar,
            expires_ts=pd.Timestamp(ts[exp_idx]) + bar,
            has_fvg=has_fvg,
            dead_ts=(pd.Timestamp(ts[z.dead_idx]) + bar
                     if z.dead_idx is not None else None),
        ))
    setups.sort(key=lambda s: s.confirmed_ts)
    # report the latest usable threshold value, not the whole series
    last = pd.Series(thr).dropna()
    return setups, (float(last.iat[-1]) if len(last) else float("nan"))


def _confirm_structure(df, breaks, swings, p):
    """A break is only a structure SHIFT once the market builds on it.

    For a bull BOS at bar b, all three must happen within confirm_max_wait
    bars, and only then is the setup tradeable:

        1. no candle CLOSES back below the broken level
        2. a higher low forms   (a pullback low above the break bar's low)
        3. a higher high prints (above the high of the break candle)

    Bear is the mirror.

    THE COST, STATED PLAINLY. The expensive part is not the rejected breaks,
    it is the DELAY. A setup confirmed at bar b+5 cannot be traded at bar b,
    so price has already moved by the time the zone opens. The confirmation
    bar is returned separately and applied to the zone, because leaving the
    zone tradeable from b would let the backtest act on a confirmation that
    had not happened yet.

    b.idx is deliberately NOT moved: find_order_blocks searches backwards from
    b.idx for the last opposite-colour candle, so shifting it would select a
    candle from inside the post-break move instead of the one that caused it.

    Returns (confirmed_breaks, {break_idx: confirmation_idx}).
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    need = int(p.get("confirm_bars", 2))
    wait = int(p.get("confirm_max_wait", 12))

    kept, at = [], {}
    for b in breaks:
        i = b.idx
        last = min(i + wait, n - 1)
        if last - i < need:
            continue

        ref_high, ref_low, level = highs[i], lows[i], b.level
        survived, got_pullback, pull_extreme, done = 0, False, None, None

        for j in range(i + 1, last + 1):
            # 1. the break must hold on a CLOSING basis
            if b.side == "bull" and closes[j] < level:
                break
            if b.side == "bear" and closes[j] > level:
                break
            survived += 1

            if b.side == "bull":
                if not got_pullback:
                    if lows[j] < lows[j - 1]:
                        got_pullback, pull_extreme = True, lows[j]
                else:
                    pull_extreme = min(pull_extreme, lows[j])
                    if (pull_extreme > ref_low and highs[j] > ref_high
                            and survived >= need):
                        done = j
                        break
            else:
                if not got_pullback:
                    if highs[j] > highs[j - 1]:
                        got_pullback, pull_extreme = True, highs[j]
                else:
                    pull_extreme = max(pull_extreme, highs[j])
                    if (pull_extreme < ref_high and lows[j] < ref_low
                            and survived >= need):
                        done = j
                        break

        if done is not None:
            kept.append(b)
            at[b.idx] = done
    return kept, at


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


BLOCKERS = {
    "OK": "aligned, trade allowed",
    "HTF_NEUTRAL": "1H bias neutral",
    "NO_TRIGGER": "no 5M trigger",
    "TRIGGER_WRONG_WAY": "5M trigger against the 1H direction",
    "NO_SETUP": "no live 15M setup",
    "SETUP_WRONG_WAY": "15M setup exists but on the other side",
    "SETUP_EXPIRED": "15M setup aged out",
    "SETUP_MITIGATED": "15M zone already invalidated by price",
}


def decide(bias, trigger, setups, ts):
    """The one decision function. Returns (action, setup, side, level, reason).

    NO PRICE ARGUMENTS. A resting limit is justified at the close of bar i and
    the fill is a separate step starting at bar i+1, so the decision can never
    read the range of the bar it was taken on.

    Every gate is an AND. `reason` is now a BLOCKERS key rather than free text,
    so the exact gate that stopped a trade can be counted across a whole
    history instead of guessed at.
    """
    action, s, side, level, code = _evaluate(bias, trigger, setups, ts)
    return action, s, side, level, code


def _evaluate(bias, trigger, setups, ts):
    if bias not in ("BULLISH", "BEARISH"):
        return "NO_TRADE", None, None, None, "HTF_NEUTRAL"

    side = "bull" if bias == "BULLISH" else "bear"

    if trigger not in ("bull", "bear"):
        return "NO_TRADE", None, None, None, "NO_TRIGGER"
    if trigger != side:
        return "NO_TRADE", None, None, None, "TRIGGER_WRONG_WAY"

    live = active_setups_at(setups, ts, side)
    if not live:
        # separate "nothing at all" from "something, wrong side / stale", because
        # the fix for each is different
        any_side = active_setups_at(setups, ts)
        if any_side:
            return "NO_TRADE", None, None, None, "SETUP_WRONG_WAY"
        confirmed = [x for x in setups if x.confirmed_ts <= ts]
        if any(x.dead_ts is not None and x.dead_ts <= ts for x in confirmed):
            return "NO_TRADE", None, None, None, "SETUP_MITIGATED"
        if any(x.expires_ts < ts for x in confirmed):
            return "NO_TRADE", None, None, None, "SETUP_EXPIRED"
        return "NO_TRADE", None, None, None, "NO_SETUP"

    s = live[0]
    return ("BUY" if side == "bull" else "SELL"), s, side, s.entry_level, "OK"


def gate_state(bias, trigger, setups, ts):
    """Every condition evaluated, whether or not it blocked. This is what the
    dashboard shows instead of a bare NO TRADE."""
    live_any = active_setups_at(setups, ts)
    want = "bull" if bias == "BULLISH" else "bear" if bias == "BEARISH" else None
    live_side = active_setups_at(setups, ts, want) if want else []
    s = live_side[0] if live_side else (live_any[0] if live_any else None)
    action, _, _, _, code = _evaluate(bias, trigger, setups, ts)
    return {
        "htf_bias_1h": bias,
        "setup_15m": bool(live_any),
        "setup_15m_side": (s.side if s else None),
        "trigger_5m": trigger or "none",
        "liquidity_sweep": bool(s.swept) if s else False,
        "imbalance": bool(s.imbalance) if s else False,
        "order_block": bool(s) ,
        "fvg": bool(s.has_fvg) if s else False,
        "action": action,
        "blocker": code,
        "blocker_text": BLOCKERS.get(code, code),
    }
