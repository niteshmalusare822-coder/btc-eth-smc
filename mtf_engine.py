"""
mtf_engine.py — 4H bias, 15M setup, 5M trigger. One decision, three jobs.

    4H   decides DIRECTION.   BULLISH / BEARISH / NEUTRAL. Neutral = no trade.
    15M  decides WHETHER a setup exists, in the 4H direction only.
    5M   decides WHEN to enter. It never picks a side.

LOOK-AHEAD CONTROL
------------------
This is the part that is easy to get wrong and impossible to notice.

Higher-timeframe state is joined to the 5M timeline with merge_asof on the
higher frame's CLOSE time, not its open time. A 15M candle stamped 10:00 does
not exist as information until 10:15. The join therefore uses
`ts + one_bar_duration` as the key, so a 5M bar at 10:05 sees the 15M candle
that closed at 10:00 and nothing newer. Same for 4H.

Every structural object (swing, BOS, order block) already carries
confirmed_idx from poi_factors, and zones are only read through
zones_active_at(). Nothing in this file touches an index above the current bar.

DECISION PARAMETERS: 7 total. That is the whole tunable surface.
    swing_left/right, body_pct, max_age, sweep_window, ote band, trigger_lookback

ENTRY QUALITY GATE
-------------------
trigger_series() stays informational by design — see decide() below, that
contract is unchanged. Separately, entry_quality_series() reads the 5M
candle AT THE ENTRY BAR ITSELF for volume expansion and a close near one
extreme of its range (i.e. not a wick-poke/doji). This is a DIFFERENT,
BLOCKING gate: decide() will not return OK on a bar that fails it, even when
a live 15M setup exists. Before this gate existed, the 5M candle at the
entry bar was never inspected at all — the 15M-setup path accepted any bar
inside a live setup's window regardless of what the 5M candle looked like.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import poi_factors as poi

TF_MINUTES = {"5m": 5, "15m": 15, "4h": 240}

PARAMS = {
    "swing_left": 1,
    "swing_right": 1,
    "body_pct": 0.85,        # calibration quantile, not a hand-picked constant
    "max_age": 96,           # bars a 15M zone stays valid
    "sweep_window": 24,      # bars allowed between the sweep and the BOS
    "require_liquidity_sweep": False,  # sweep is quality/context, not a mandatory POI gate
    # OB entry model from the source material: "wick", "body" or "50".
    # OTE is a different school's entry and is no longer used for order blocks.
    "ob_entry_mode": "zone_edge",   # BUY=zone bottom, SELL=zone top
    "require_ob_sweep": False,        # the OB candle must take prior liquidity
    "require_ob_imbalance": False,    # a gap must sit next to the OB
    "imbalance_window": 3,
    "stop_buffer_frac": 0.30,        # padding beyond the OB wick
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
    "confirm_bars": 1,          # closed 15M candles the shift must survive
    "confirm_max_wait": 12,     # bars allowed to complete confirmation

    # ── RETEST (off by default so A/B stays possible) ──────────────────
    # Creating a POI is not an entry. The research architecture requires price
    # to RETURN to the zone before a trade is allowed. Without this the engine
    # can enter on a bar where price is nowhere near the order block, which is
    # not what the setup describes.
    "require_retest": False,
    "retest_max_wait": 9,      # bars a POI waits to be retested before expiry
    "retest_depth": 0.0,        # 0 = touching the zone edge counts as a retest

    # ── POI SOURCES ────────────────────────────────────────────────────
    # The architecture has two PARALLEL paths after structure acceptance:
    #
    #     STRUCTURE ACCEPTANCE
    #        |            |
    #        v            v
    #      OB POI      FVG POI
    #        |            |
    #        +-----+------+
    #              v
    #            RETEST
    #
    # They are alternatives, not an AND. The research explicitly rejected
    # making OB+FVG overlap mandatory, so an FVG left by the displacement leg
    # is a POI in its own right even when no order block qualified.
    #
    # Default uses both POI paths; each is still independently lineage-checked.
    "poi_sources": ["ob", "fvg"],       # ["ob"], ["fvg"], or ["ob", "fvg"]
    "fvg_min_size_atr": 0.0,     # optional floor on FVG height

    # ── 5M ENTRY QUALITY GATE (blocking, unlike trigger_series) ────────
    "require_5m_quality_gate": False,
    "early_poi": True,
    "volume_expansion_min": 1.2,   # entry bar volume must exceed MA20 * this
    "close_ratio_min": 0.5,        # how close to an extreme the bar must close
                                     # 0 = anywhere, 1 = exact high/low
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
# 4H BIAS
# ---------------------------------------------------------------------------
def htf_bias_series(df_4h, p=None, calib_end=None):
    """
    BULLISH / BEARISH / NEUTRAL per 4H bar, causal.

    Direction-first:

        valid bull BOS -> BULLISH
        valid bear BOS -> BEARISH

    Bias remains in that direction until an opposite valid BOS occurs.

    IMPORTANT:
    Rolling swing equilibrium is NOT used to turn the structural bias
    NEUTRAL. NEUTRAL exists only before the first valid BOS.
    """
    p = p or PARAMS

    df = poi.add_candle_metrics(df_4h)

    swings = poi.find_swings(
        df,
        p["swing_left"],
        p["swing_right"],
    )

    thr = _calibrate(df, p, calib_end)

    bos = poi.find_bos(
        df,
        swings,
        body_threshold=thr,
        require_displacement=True,
    )

    n = len(df)
    bias = np.array(["NEUTRAL"] * n, dtype=object)

    # Ignore liquidity sweeps.
    # Only confirmed/non-sweep BOS events change HTF direction.
    breaks = [b for b in bos if not b.is_sweep]

    cur = "NEUTRAL"
    bi = 0

    for i in range(n):

        while bi < len(breaks) and breaks[bi].idx <= i:
            if breaks[bi].side == "bull":
                cur = "BULLISH"
            else:
                cur = "BEARISH"

            bi += 1

        if cur == "BULLISH":
            bias[i] = "BULLISH"

        elif cur == "BEARISH":
            bias[i] = "BEARISH"

        else:
            bias[i] = "NEUTRAL"

    return pd.DataFrame({
        "ts": df["ts"].values,
        "htf_bias": bias,
    })


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
    retest_ts: object = None  # when price first returned into the POI
    state: str = "READY"      # READY | WAITING_FOR_RETEST | RETESTED | DEAD
    poi_quality: str = "OB"   # OB | OB+FVG


def find_setups(df_15m, p=None, calib_end=None):
    """Displacement/BOS -> OB or FVG POI, with liquidity sweep as context.

    A valid displacement BOS can create a tradeable POI on its own. A prior
    opposite-side liquidity sweep is preferred SMC context, but it is not a
    mandatory gate by default. This prevents the engine from going silent
    during clean displacement moves where price never produces the exact
    sweep+BOS sequence.

    If require_liquidity_sweep=True, the stricter sweep->BOS path is restored.
    """
    p = p or PARAMS
    df = poi.add_candle_metrics(df_15m)
    thr = _calibrate(df, p, calib_end)
    swings = poi.find_swings(df, p["swing_left"], p["swing_right"])
    bos = poi.find_bos(df, swings, body_threshold=thr, require_displacement=True)

    breaks = [b for b in bos if not b.is_sweep]
    sweeps = [b for b in bos if b.is_sweep]

    kept = []
    require_sweep = bool(p.get("require_liquidity_sweep", False))
    for b in breaks:
        want = "bear" if b.side == "bull" else "bull"
        swept = any(
            s.side == want and 0 < b.idx - s.idx <= p["sweep_window"]
            for s in sweeps
        )
        if (not require_sweep) or swept:
            kept.append(b)

    confirm_at = {}
    if p.get("require_structure_confirmation"):
        kept, confirm_at = _confirm_structure(df, kept, swings, p)

    use_ob = "ob" in p.get("poi_sources", ["ob"])
    use_fvg = "fvg" in p.get("poi_sources", ["ob"])

    obs = poi.find_order_blocks(
        df, kept,
        lookback=p.get("ob_lookback", 30),
        require_sweep=p.get("require_ob_sweep", True),
        require_imbalance=p.get("require_ob_imbalance", True),
        imbalance_window=p.get("imbalance_window", 3))

    # EARLY POI: arm the zone at the close of the displacement candle.
    # This is causal and avoids waiting for a later confirmed swing/BOS.
    if p.get("early_poi", True):
        early = poi.find_displacement_pois(df, body_threshold=thr)
        if not use_ob:
            early = [z for z in early if z.kind != "ob"]
        if not use_fvg:
            early = [z for z in early if z.kind != "fvg"]
        obs.extend(early)

    fvgs = poi.find_fvgs(df, body_threshold=thr, require_displacement=True)

    if not use_ob:
        obs = []

    # ── FVG AS A POI IN ITS OWN RIGHT ───────────────────────────────────
    # An FVG only qualifies when it was left BY the displacement leg that
    # broke structure: same side, formed at or before the break, and inside
    # the lookback window. A gap that merely happens to sit nearby is not a
    # point of interest, it is a coincidence — which is exactly what the
    # lineage audit found when it reported fvg_from_displacement_leg at zero.
    if use_fvg:
        look = int(p.get("ob_lookback", 30))
        floor_atr = float(p.get("fvg_min_size_atr", 0.0))
        rng = (df["high"] - df["low"]).rolling(14, min_periods=5).mean().to_numpy()
        claimed = {z.formed_idx for z in obs}
        for ev in kept:
            for f in fvgs:
                if f.side != ev.side:
                    continue
                if not (ev.idx - look <= f.formed_idx <= ev.idx):
                    continue
                if f.formed_idx in claimed:
                    continue
                if floor_atr > 0:
                    a = rng[f.formed_idx]
                    if not np.isfinite(a) or a <= 0 or (f.top - f.bottom) < floor_atr * a:
                        continue
                # the gap becomes tradeable only once the break confirmed it
                f.confirmed_idx = max(f.confirmed_idx, ev.idx)
                f.meta["from_break_idx"] = ev.idx
                obs.append(f)
                claimed.add(f.formed_idx)
                break

    obs.sort(key=lambda z: z.confirmed_idx)

    ts = _ts(df["ts"]).to_numpy()
    bar = pd.Timedelta(minutes=TF_MINUTES["15m"])

    # ORDER MATTERS. Structure confirmation is applied BEFORE the mitigation
    # replay, not after.
    #
    # update_zones() guards with `z.confirmed_idx > i: continue`, which is
    # correct only if confirmed_idx is already final. Running the replay first
    # judged zones from their BREAK bar, then confirmation pushed confirmed_idx
    # forward by up to confirm_max_wait bars. Zones ended up carrying dead_ts
    # EARLIER than confirmed_ts: dead before they were born, never tradeable
    # at any instant.
    #
    # The lookup key is the BREAK index, because that is how _confirm_structure
    # keys its map. Order blocks carry confirmed_idx == break idx and match
    # directly, but an FVG POI sets confirmed_idx = max(own, break) and can end
    # up ABOVE the break bar, missing the lookup and skipping the confirmation
    # delay entirely — two POI paths under different rules, which makes any A/B
    # between them meaningless. from_break_idx is recorded when the FVG is
    # adopted, so it is used when present.
    if confirm_at:
        for z in obs:
            key = z.meta.get("from_break_idx", z.confirmed_idx)
            c = confirm_at.get(key)
            if c is not None and c > z.confirmed_idx:
                z.confirmed_idx = c
        obs.sort(key=lambda z: z.confirmed_idx)

    for i in range(len(df)):
        poi.update_zones(obs, df, i, p.get("kill_on", "full"))

    # ── RETEST DETECTION ────────────────────────────────────────────────
    # For each zone, the first bar AT OR AFTER its confirmation where price
    # trades back into the zone. Scanned forward bar by bar from the
    # confirmation bar, so it can never see a return that has not happened.
    retest_idx = {}
    if p.get("require_retest"):
        hi_a = df["high"].to_numpy()
        lo_a = df["low"].to_numpy()
        wait = int(p.get("retest_max_wait", 9))
        depth = float(p.get("retest_depth", 0.0))
        for z in obs:
            span = z.top - z.bottom
            # depth 0 = the zone edge; higher values demand a deeper return
            edge = (z.top - span * depth) if z.side == "bull" \
                else (z.bottom + span * depth)
            last = min(z.confirmed_idx + wait, len(df) - 1)
            for j in range(z.confirmed_idx + 1, last + 1):
                inside = (lo_a[j] <= edge) if z.side == "bull" \
                    else (hi_a[j] >= edge)
                if inside:
                    retest_idx[id(z)] = j
                    break

    setups = []
    for z in obs:
        has_fvg = any(f.confirmed_idx <= z.confirmed_idx and poi.dragon_fruit(z, f)
                      for f in fvgs)
        # Canonical execution edge: BUY at POI bottom, SELL at POI top.
        mode = p.get("ob_entry_mode", "zone_edge")
        entry = z.entry_at(mode)
        stop = z.stop_at(p.get("stop_buffer_frac", 0.30))
        # NOT clamped to len(df)-1. Clamping expired every setup near the end
        # of the frame early: the last 15M bar closes up to 15 minutes before
        # the last 5M bar, so a fresh setup could be reported expired on the
        # very bar being judged. Expiry is max_age bars after confirmation,
        # whether or not the data reaches that far.
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
            expires_ts=(pd.Timestamp(ts[z.confirmed_idx])
                        + bar * (1 + int(p["max_age"]))),
            has_fvg=has_fvg,
            poi_quality=("FVG" if z.kind == "fvg"
                         else "OB+FVG" if has_fvg else "OB"),
            retest_ts=(pd.Timestamp(ts[retest_idx[id(z)]]) + bar
                       if id(z) in retest_idx else None),
            state=("RETESTED" if id(z) in retest_idx
                   else "WAITING_FOR_RETEST" if p.get("require_retest")
                   else "READY"),
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
        got_pullback, pull_extreme = False, None
        shift_at, done = None, None

        for j in range(i + 1, last + 1):
            # 1. the break must hold on a CLOSING basis
            if b.side == "bull" and closes[j] < level:
                break
            if b.side == "bear" and closes[j] > level:
                break

            # PERSISTENCE COUNTING. confirm_bars means N closed bars AFTER the
            # shift completes, not including the bar that completed it. The
            # earlier version counted the completing candle itself, so
            # confirm_bars=2 was really demanding one bar of persistence.
            if shift_at is not None:
                if j - shift_at >= need:
                    done = j
                    break
                continue

            if b.side == "bull":
                if not got_pullback:
                    if lows[j] < lows[j - 1]:
                        got_pullback, pull_extreme = True, lows[j]
                else:
                    pull_extreme = min(pull_extreme, lows[j])
                    if pull_extreme > ref_low and highs[j] > ref_high:
                        shift_at = j          # HL then HH: the shift is complete
                        if need == 0:
                            done = j
                            break
            else:
                if not got_pullback:
                    if highs[j] > highs[j - 1]:
                        got_pullback, pull_extreme = True, highs[j]
                else:
                    pull_extreme = max(pull_extreme, highs[j])
                    if pull_extreme < ref_high and lows[j] < ref_low:
                        shift_at = j          # LH then LL: the shift is complete
                        if need == 0:
                            done = j
                            break

        if done is not None:
            kept.append(b)
            at[b.idx] = done
    return kept, at


# ---------------------------------------------------------------------------
# 5M TRIGGER (informational — see module docstring)
# ---------------------------------------------------------------------------
def trigger_series(df_5m, p=None, calib_end=None):
    """Micro structure shift on 5M. Direction-agnostic: it reports what the
    5M chart just did, and the caller checks it against the 4H/15M side.

    STAYS INFORMATIONAL. decide() does not gate on this — see
    entry_quality_series() below for the blocking 5M check.
    """
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
# 5M ENTRY QUALITY GATE (blocking)
# ---------------------------------------------------------------------------
def entry_quality_series(df_5m, p=None):
    """True on 5M bars that show real conviction, False on wick-pokes/noise.

    Two conditions, both must hold:
      1. volume on this bar exceeds its 20-bar MA by volume_expansion_min
      2. the close sits near one extreme of the bar's range (close_ratio_min),
         ruling out dojis and reversal wicks

    This is read by decide() as an independent, BLOCKING condition on the
    entry bar — unlike trigger_series, which stays informational by design.
    Before this existed, nothing in the 15M-setup entry path inspected the
    5M candle at all.

    Returns a boolean numpy array, one entry per 5M bar. Bars inside the
    volume-MA warmup window (no finite MA yet) are not penalized.
    """
    p = p or PARAMS
    vol = df_5m["volume"].to_numpy(dtype=float)
    vol_ma = pd.Series(vol).rolling(20, min_periods=5).mean().to_numpy()

    o = df_5m["open"].to_numpy(dtype=float)
    c = df_5m["close"].to_numpy(dtype=float)
    h = df_5m["high"].to_numpy(dtype=float)
    lo = df_5m["low"].to_numpy(dtype=float)

    rng = h - lo
    close_ratio = np.where(rng > 1e-12, (c - lo) / np.maximum(rng, 1e-12), 0.5)
    # 0 = closed exactly mid-range (doji-like), 1 = closed exactly at an extreme
    extremity = np.abs(close_ratio - 0.5) * 2.0

    vol_min = float(p.get("volume_expansion_min", 1.2))
    ext_min = float(p.get("close_ratio_min", 0.5))

    vol_ok = vol > (vol_ma * vol_min)
    shape_ok = extremity >= ext_min

    ok = vol_ok & shape_ok
    # no volume MA yet (warmup) -> do not penalize, let the setup/bias gates decide
    ok = np.where(np.isnan(vol_ma), True, ok)

    return ok


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

def structure_targets_at(df_15m, swings, ts, side, entry, max_targets=3):
    """Return confirmed opposing swing/liquidity targets available at ts.

    Only swings whose confirmation timestamp is already <= ts are eligible.
    No future swing can be used.
    """
    ts = pd.Timestamp(ts)
    entry = float(entry)
    candidates = []

    if df_15m is None or df_15m.empty:
        return []

    ts_series = pd.to_datetime(df_15m["ts"]).reset_index(drop=True)

    for sw in swings:
        if sw.confirmed_idx is None:
            continue

        idx = int(sw.confirmed_idx)

        if idx < 0 or idx >= len(ts_series):
            continue

        confirmed_ts = ts_series.iloc[idx]

        if confirmed_ts > ts:
            continue

        price = float(sw.price)

        if side == "bull":
            if sw.kind == "high" and price > entry:
                candidates.append(price)

        elif side == "bear":
            if sw.kind == "low" and price < entry:
                candidates.append(price)

    if side == "bull":
        levels = sorted(set(candidates))
    else:
        levels = sorted(set(candidates), reverse=True)

    # Remove levels that are effectively duplicates.
    unique = []
    for level in levels:
        if not unique:
            unique.append(level)
            continue

        if abs(level - unique[-1]) / unique[-1] > 0.001:
            unique.append(level)

    return unique[:max_targets]


def build_context(df_5m, df_15m, df_4h, p=None, calib_end=None):
    """Everything a bar-by-bar loop needs, precomputed and causal.

    calib_end is accepted and ignored. Calibration is now a trailing rolling
    quantile computed per bar, so live and backtest produce identical
    thresholds on identical candles.

    swings_15m contains the confirmed 15M swing structure used for
    causal liquidity/structure-based TP targeting.

    "quality" is the blocking 5M entry-quality gate (entry_quality_series).
    It is a plain boolean numpy array aligned 1:1 with df_5m, so callers can
    index it the same way as "trigger": ctx["quality"][i].
    """
    p = p or PARAMS

    bias_df = htf_bias_series(df_4h, p, calib_end)
    setups, thr15 = find_setups(df_15m, p, calib_end)
    trig = trigger_series(df_5m, p, calib_end)
    quality = entry_quality_series(df_5m, p)

    bias_on_5m = align_htf(
        df_5m, bias_df, "4h", "htf_bias"
    )

    swings_15m = poi.find_swings(
        df_15m,
        p["swing_left"],
        p["swing_right"],
    )

    return {
        "bias": bias_on_5m,
        "setups": setups,
        "trigger": trig,
        "quality": quality,
        "threshold_15m": thr15,
        "swings_15m": swings_15m,
        "df15": df_15m,
    }


def active_setups_at(setups, ts, side=None):
    """Setups already confirmed and not yet expired at this instant."""
    out = []
    for s in setups:
        if s.confirmed_ts > ts or s.expires_ts < ts:
            continue
        if s.dead_ts is not None and s.dead_ts < ts:
            continue
        # a POI that has not been retested is not tradeable. This is the whole
        # point of the retest architecture: the setup is defined once and then
        # followed until price returns, expires or is invalidated.
        if s.state == "WAITING_FOR_RETEST":
            continue
        if s.retest_ts is not None and s.retest_ts > ts:
            continue
        if side and s.side != side:
            continue
        out.append(s)

    # Prefer the FRESHEST confirmed setup.  The previous implementation
    # returned setups in creation order, so decide() and app.py could select
    # an older live zone while a newer valid 15M setup was already available.
    # That makes the planned entry stale even though a newer setup exists.
    # This changes selection only; it does not loosen any SMC gate.
    out.sort(key=lambda s: (s.confirmed_ts, s.retest_ts or s.confirmed_ts),
             reverse=True)
    return out


BLOCKERS = {
    "OK": "aligned, trade allowed",
    "HTF_NEUTRAL": "4H bias neutral",
    "NO_TRIGGER": "no 5M trigger",
    "TRIGGER_WRONG_WAY": "5M trigger against the 4H direction",
    "NO_SETUP": "no live 15M setup",
    "SETUP_WRONG_WAY": "15M setup exists but on the other side",
    "SETUP_EXPIRED": "15M setup aged out",
    "SETUP_MITIGATED": "15M zone already invalidated by price",
    "AWAITING_RETEST": "POI formed but price has not returned to it",
    "WEAK_5M_CONFIRMATION":
        "15M setup is live but the 5M entry bar lacks volume/close conviction",

    # FORWARD_ENTRY stale protection
    # Used by app.py when an unfilled limit entry has moved >= 3R away.
    "FORWARD_ENTRY_STALE":
        "Forward entry is stale; price moved too far before the entry was reached",
    "FORWARD_ENTRY_NEAR_MISS":
        "Forward entry was approached/touched and then rejected; pending limit cancelled",
}


def decide(bias, trigger, setups, ts, quality=True, p=None):
    """Main decision uses 4H bias + 15M setup.

    5M trigger is INFORMATION ONLY and never blocks a valid setup.

    The optional 5M quality gate is controlled by
    `require_5m_quality_gate`. It is OFF by default, so quality remains
    informational unless explicitly enabled.
    Returns:
        (action, setup, side, level, reason)
    """
    p = p or PARAMS
    action, s, side, level, code = _evaluate(
        bias,
        trigger,
        setups,
        ts,
        quality,
        p,
    )

    return action, s, side, level, code


def _evaluate(bias, trigger, setups, ts, quality=True, p=None):
    p = p or PARAMS
    # ------------------------------------------------------------
    # 1. 4H BIAS = mandatory
    # ------------------------------------------------------------
    if bias not in ("BULLISH", "BEARISH"):
        return (
            "NO_TRADE",
            None,
            None,
            None,
            "HTF_NEUTRAL",
        )

    side = "bull" if bias == "BULLISH" else "bear"

    # ------------------------------------------------------------
    # 2. 5M TRIGGER = INFORMATION ONLY
    #
    # IMPORTANT:
    # Do NOT block the trade here.
    #
    # trigger can be:
    #   bull
    #   bear
    #   None / "none"
    #
    # All of these are allowed to continue to the 15M setup gate.
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # 3. 15M SETUP = mandatory
    # ------------------------------------------------------------
    live = active_setups_at(
        setups,
        ts,
        side,
    )

    if not live:

        # Check whether a setup exists on the opposite side.
        any_side = active_setups_at(
            setups,
            ts,
        )

        if any_side:
            return (
                "NO_TRADE",
                None,
                None,
                None,
                "SETUP_WRONG_WAY",
            )

        # Only setups which could actually have been active
        # at this timestamp are considered.
        cands = [
            x for x in setups
            if (
                x.side == side
                and x.confirmed_ts <= ts <= x.expires_ts
            )
        ]

        alive = [
            x for x in cands
            if not (
                x.dead_ts is not None
                and x.dead_ts < ts
            )
        ]

        # Setup exists but price has not retested the POI yet.
        if any(
            x.state == "WAITING_FOR_RETEST"
            or (
                x.retest_ts is not None
                and x.retest_ts > ts
            )
            for x in alive
        ):
            return (
                "NO_TRADE",
                None,
                None,
                None,
                "AWAITING_RETEST",
            )

        # Setup existed in its valid time window but got invalidated.
        if cands:
            return (
                "NO_TRADE",
                None,
                None,
                None,
                "SETUP_MITIGATED",
            )

        # A setup existed previously but has expired.
        if any(
            x.side == side
            and x.confirmed_ts <= ts
            for x in setups
        ):
            return (
                "NO_TRADE",
                None,
                None,
                None,
                "SETUP_EXPIRED",
            )

        return (
            "NO_TRADE",
            None,
            None,
            None,
            "NO_SETUP",
        )

    # ------------------------------------------------------------
    # 4. VALID 15M SETUP
    #
    # 5M trigger does NOT matter here. The 5M QUALITY gate does.
    # ------------------------------------------------------------
    s = live[0]

    # 5M confirmation/quality is informational only. The 15M POI edge
    # is the execution price; the execution layer waits for price to touch it.
    action = (
        "BUY"
        if side == "bull"
        else "SELL"
    )

    return (
        action,
        s,
        side,
        s.entry_level,
        "OK",
    )

def gate_state(bias, trigger, setups, ts, quality=True, p=None):
    """Show all conditions.

    5M trigger is informational only and never blocks a trade.
    The 5M quality gate (volume + close conviction on the entry bar) does.
    """
    p = p or PARAMS

    live_any = active_setups_at(
        setups,
        ts,
    )

    want = (
        "bull"
        if bias == "BULLISH"
        else "bear"
        if bias == "BEARISH"
        else None
    )

    live_side = (
        active_setups_at(setups, ts, want)
        if want
        else []
    )

    s = (
        live_side[0]
        if live_side
        else (
            live_any[0]
            if live_any
            else None
        )
    )

    action, _, _, _, code = _evaluate(
        bias,
        trigger,
        setups,
        ts,
        quality,
        p,
    )

    return {
        "htf_bias_4h": bias,

        "setup_15m": bool(live_any),

        "setup_15m_side": (
            s.side
            if s
            else None
        ),

        # INFORMATION ONLY
        "trigger_5m": trigger or "none",

        "trigger_5m_role": "INFORMATION_ONLY",

        # BLOCKING
        "quality_5m": bool(quality),

        "quality_5m_role": "INFORMATION_ONLY",

        "liquidity_sweep": (
            bool(s.swept)
            if s
            else False
        ),

        "imbalance": (
            bool(s.imbalance)
            if s
            else False
        ),

        "order_block": (
            bool(
                s
                and s.poi_quality in (
                    "OB",
                    "OB+FVG",
                )
            )
        ),

        "fvg": (
            bool(s.has_fvg)
            if s
            else False
        ),

        "action": action,

        "blocker": code,

        "blocker_text": BLOCKERS.get(
            code,
            code,
        ),
    }
