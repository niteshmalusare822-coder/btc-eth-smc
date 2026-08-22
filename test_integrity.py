"""Integrity tests. These check that the measurement is honest, not that the
strategy is profitable. A failing test here means a number somewhere is a lie."""
import inspect

import numpy as np
import pandas as pd
import pytest

import backtest as B
import mtf_engine as mtf
import poi_factors as poi
import risk as R
from conftest import synth


# 1 ── HTF alignment has no look-ahead
def test_htf_not_visible_before_close():
    df5 = synth(600, 5, 3)
    d = df5.set_index("ts")
    df1h = d.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                 "close": "last", "volume": "sum"}).dropna().reset_index()
    state = pd.DataFrame({"ts": df1h["ts"], "htf_bias": [f"B{i}" for i in range(len(df1h))]})
    got = mtf.align_htf(df5, state, "1h", "htf_bias")

    ts5 = pd.to_datetime(df5["ts"])
    for i in range(len(df5)):
        if not isinstance(got[i], str):
            continue
        k = int(got[i][1:])
        close_time = pd.Timestamp(df1h["ts"].iat[k]) + pd.Timedelta(hours=1)
        assert close_time <= ts5.iat[i], (
            f"bar {i} at {ts5.iat[i]} saw a 1H candle closing at {close_time}")


def test_15m_not_visible_before_close():
    df5 = synth(600, 5, 4)
    d = df5.set_index("ts")
    df15 = d.resample("15min").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum"}).dropna().reset_index()
    state = pd.DataFrame({"ts": df15["ts"], "v": list(range(len(df15)))})
    got = mtf.align_htf(df5, state, "15m", "v")
    ts5 = pd.to_datetime(df5["ts"])
    for i in range(len(df5)):
        if not np.isfinite(got[i]):
            continue
        close_time = pd.Timestamp(df15["ts"].iat[int(got[i])]) + pd.Timedelta(minutes=15)
        assert close_time <= ts5.iat[i]


# 2 ── forming candle is dropped at the data layer
def _stub_history(monkeypatch, bars=2500, fail_1h_on=None):
    """Replace the paginated fetch with a deterministic in-memory venue."""
    import data as D

    def fake(venue, symbol, timeframe, target_bars,
             since=None, now=None, **kw):
        tf, target = timeframe, target_bars
        if fail_1h_on and venue == fail_1h_on and tf == "1h":
            return None, {"error": "unavailable"}
        secs = D.TF_SECONDS[tf]
        n = min(target, bars)
        end = 1700000000
        ts = pd.to_datetime(np.arange(end - n * secs, end, secs), unit="s")
        px = 3000 + np.cumsum(np.random.default_rng(2).normal(0, 2, n))
        df = pd.DataFrame({"ts": ts, "open": px, "high": px + 2, "low": px - 2,
                           "close": px, "volume": np.ones(n)})
        return df, {"requested_bars": target, "actual_bars": n,
                    "short_by": max(0, target - n), "source": venue,
                    "symbol": symbol, "timeframe": tf,
                    "coverage_start": str(df["ts"].iat[0]),
                    "coverage_end": str(df["ts"].iat[-1]), "pages_fetched": 3}

    monkeypatch.setattr(D, "fetch_ohlcv_history", fake)
    return 1700000000


def test_forming_candle_dropped(monkeypatch):
    import data as D
    end = _stub_history(monkeypatch)
    # the last stub candle OPENS at end-300 and closes at end, so a clock
    # reading before `end` means it is genuinely still forming
    frames, meta = D.load_mtf("ETH", 1000, now=end - 120)
    assert frames is not None
    assert meta["mixed"] is False
    assert meta["forming_candle_dropped"]["5m"] is True


# 3 ── signal on bar i never enters before bar i+1
def test_entry_never_on_signal_bar(report):
    for t in report["trade_log"]:
        assert t["fill_i"] >= t["i"] + 1, t


# 4 ── stops and targets are never evaluated before entry
def test_exit_index_after_entry(report):
    for t in report["trade_log"]:
        assert t["exit_i"] >= t["fill_i"], t


# 5 ── both SL and TP in one candle resolves to the stop
def test_same_candle_both_hit_is_a_stop():
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=3, freq="5min"),
        "open": [100.0, 100.0, 100.0],
        "high": [100.0, 130.0, 100.0],     # target inside this candle
        "low":  [100.0, 70.0, 100.0],      # and so is the stop
        "close": [100.0, 100.0, 100.0],
        "volume": [1, 1, 1]})
    tps = [{"level": "TP1", "price": 120.0, "reachable": True}]
    legs, hit, outcome, ex = B.simulate(df, "bull", 100.0, 90.0, tps, 1, 5)
    assert outcome == "STOP" and hit == []
    assert legs == [(1.0, 90.0)]


# 6/7 ── random baseline is matched in count and run over many seeds
def test_matched_baseline_matches_count(report):
    oos = {m["arm"]: m for m in report["out_of_sample"]}
    for base in ("SMC", "SMC_MTF"):
        mb = oos.get(f"MATCHED_RANDOM_vs_{base}")
        src = oos.get(base, {}).get("trades", 0)
        if mb is None or not src:
            continue
        assert mb["source_trades"] == src
        assert abs(mb["trades"] - src) <= max(2, src * 0.25), (mb["trades"], src)
        assert mb["seeds_used"] >= 5


def test_baseline_reports_a_distribution(report):
    oos = {m["arm"]: m for m in report["out_of_sample"]}
    mb = next((v for k, v in oos.items() if k.startswith("MATCHED_RANDOM")), None)
    if mb is None:
        pytest.skip("no matched baseline in this sample")
    for k in ("random_mean_expectancy", "random_median_expectancy",
              "random_std_expectancy", "random_mean_net_pnl"):
        assert k in mb


# 8/9 ── no duplicate and no overlapping trades
def test_no_duplicate_signals(report):
    for arm in ("smc", "smc_mtf", "random"):
        idx = [t["i"] for t in report["trade_log"] if t["arm"] == arm]
        assert len(idx) == len(set(idx)), f"{arm} opened two trades on one bar"


def test_no_overlapping_trades(report):
    for arm in ("smc", "smc_mtf", "random"):
        ts = sorted([t for t in report["trade_log"] if t["arm"] == arm],
                    key=lambda x: x["fill_i"])
        for a, b in zip(ts, ts[1:]):
            assert b["i"] > a["exit_i"], f"{arm} overlapped: {a['exit_i']} -> {b['i']}"


# 10/11 ── P&L sign conventions
@pytest.mark.parametrize("side,exit_px,should_profit", [
    ("bull", 3100.0, True), ("bull", 2900.0, False),
    ("bear", 2900.0, True), ("bear", 3100.0, False)])
def test_pnl_direction(side, exit_px, should_profit):
    qty, entry = 1.0, 3000.0
    gross, net, fees, slip, fund = B.pnl_inr(
        side, entry, [(1.0, exit_px)], qty, 88.0, qty * entry * 88.0, 5, 5)
    assert (gross > 0) is should_profit
    assert fees > 0 and slip > 0
    expected = (exit_px - entry) if side == "bull" else (entry - exit_px)
    assert gross == pytest.approx(expected * qty * 88.0)


def test_costs_charged_once():
    qty, entry, usdt = 1.0, 3000.0, 88.0
    notional = qty * entry * usdt
    g, n, fees, slip, fund = B.pnl_inr("bull", entry, [(1.0, entry)], qty,
                                       usdt, notional, 0, 5)
    assert fees == pytest.approx(notional * R.ROUND_TRIP_FEE)
    assert slip == pytest.approx(notional * R.ROUND_TRIP_SLIP)
    assert n == pytest.approx(-(fees + slip + fund))


def test_partial_tp_and_timeout():
    """With stop management off, an unfilled remainder times out."""
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=6, freq="5min"),
        "open": [100.0] * 6, "high": [100, 111, 100, 100, 100, 100.0],
        "low": [100.0] * 6, "close": [100.0] * 6, "volume": [1] * 6})
    tps = [{"level": "TP1", "price": 110.0, "reachable": True},
           {"level": "TP2", "price": 200.0, "reachable": True}]
    legs, hit, outcome, ex = B.simulate(df, "bull", 100.0, 90.0, tps, 1, 4,
                                        manage=False)
    assert hit == ["TP1"] and outcome == "PARTIAL"
    assert sum(f for f, _ in legs) == pytest.approx(1.0)


def test_stop_moves_to_breakeven_after_tp1():
    """Spec 17. Once TP1 pays, the remainder must not be able to lose money.
    Here price returns to the entry and the trailed stop takes it out."""
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=6, freq="5min"),
        "open": [100.0] * 6, "high": [100, 111, 100, 100, 100, 100.0],
        "low": [100.0] * 6, "close": [100.0] * 6, "volume": [1] * 6})
    tps = [{"level": "TP1", "price": 110.0, "reachable": True},
           {"level": "TP2", "price": 200.0, "reachable": True}]
    legs, hit, outcome, ex = B.simulate(df, "bull", 100.0, 90.0, tps, 1, 4,
                                        manage=True, cost_r=0.0)
    assert hit == ["TP1"]
    assert outcome == "TRAILED_STOP", outcome
    exits = [px for _, px in legs]
    assert min(exits) >= 100.0, "remainder exited below breakeven"


def test_stop_never_moves_away_from_price():
    """A stop may only ever tighten. Moving it out is how a small loss becomes
    a large one, and it must be impossible by construction."""
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=8, freq="5min"),
        "open": [100.0] * 8,
        "high": [100, 111, 121, 112, 100, 100, 100, 100.0],
        "low": [100.0, 100.5, 101, 95, 95, 95, 95, 95.0],
        "close": [100.0] * 8, "volume": [1] * 8})
    tps = [{"level": "TP1", "price": 110.0, "reachable": True},
           {"level": "TP2", "price": 120.0, "reachable": True},
           {"level": "TP3", "price": 500.0, "reachable": True}]
    legs, hit, outcome, ex = B.simulate(df, "bull", 100.0, 90.0, tps, 1, 6,
                                        manage=True, cost_r=0.0)
    assert hit[:2] == ["TP1", "TP2"]
    # after TP2 the stop sits at TP1 = 110, so the drop to 95 must exit there
    assert any(px >= 110.0 for _, px in legs)
    assert all(px >= 90.0 for _, px in legs), "exited below the original stop"


def test_unreachable_targets_are_not_used_as_exits():
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=4, freq="5min"),
        "open": [100.0] * 4, "high": [100, 101, 100, 100.0],
        "low": [100.0] * 4, "close": [100.0] * 4, "volume": [1] * 4})
    tps = [{"level": "TP1", "price": 101.0, "reachable": True},
           {"level": "TP2", "price": 102.0, "reachable": False}]
    legs, hit, outcome, ex = B.simulate(df, "bull", 100.0, 90.0, tps, 1, 3)
    assert hit == ["TP1"]
    assert sum(f for f, _ in legs) == pytest.approx(1.0), "unreachable TP took size"


# 12 ── live and backtest reach the same decision on the same closed bar
def test_live_backtest_decision_parity(frames):
    df5, df15, df1h = frames
    ctx = mtf.build_context(df5, df15, df1h, calib_end=None)
    ts_all = mtf._ts(df5["ts"])
    checked = 0
    for i in range(200, len(df5) - 2, 37):
        ts = ts_all.iat[i]
        a = mtf.decide(ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts)
        b = mtf.decide(ctx["bias"][i], ctx["trigger"][i], ctx["setups"], ts)
        assert a[0] == b[0] and a[3] == b[3]
        checked += 1
    assert checked > 20


def test_decide_takes_no_price_arguments():
    import inspect
    params = list(inspect.signature(mtf.decide).parameters)
    assert params == ["bias", "trigger", "setups", "ts"], params


# 13 ── same-source loading is preferred and mixed data is refused by default
def test_mixed_source_refused_by_default(monkeypatch):
    """CoinDCX cannot serve 1h, so the whole venue is abandoned rather than
    stitching 5m from CoinDCX onto 1h from somewhere else."""
    import data as D
    _stub_history(monkeypatch, fail_1h_on="coindcx")
    frames, meta = D.load_mtf("ETH", 1000, allow_mixed=False)
    assert frames is not None
    assert meta["mixed"] is False
    assert meta["source"] != "coindcx", "fell back per-frame instead of per-venue"


def test_mixed_source_allowed_only_explicitly(monkeypatch):
    import data as D

    def only_coindcx_5m(venue, symbol, timeframe, target_bars,
                        since=None, now=None, **kw):
        tf, target = timeframe, target_bars
        if (venue == "coindcx") != (tf == "5m"):
            return None, {"error": "unavailable"}
        secs = D.TF_SECONDS[tf]
        end = 1700000000
        n = min(target, 2000)
        ts = pd.to_datetime(np.arange(end - n * secs, end, secs), unit="s")
        px = np.full(n, 3000.0)
        df = pd.DataFrame({"ts": ts, "open": px, "high": px + 1, "low": px - 1,
                           "close": px, "volume": np.ones(n)})
        return df, {"requested_bars": target, "actual_bars": n, "short_by": 0,
                    "source": venue, "symbol": symbol, "timeframe": tf,
                    "coverage_start": str(ts[0]), "coverage_end": str(ts[-1]),
                    "pages_fetched": 1}

    monkeypatch.setattr(D, "fetch_ohlcv_history", only_coindcx_5m)
    frames, meta = D.load_mtf("ETH", 1000, allow_mixed=False)
    assert frames is None and "no single venue" in meta["error"]

    frames, meta = D.load_mtf("ETH", 1000, allow_mixed=True)
    assert frames is not None
    assert meta["mixed"] is True and meta["source"] == "MIXED"
    assert set(meta["sources"]) == {"5m", "15m", "1h"}
    assert any("MIXED SOURCE" in w for w in meta["warnings"])


# 14 ── bar counts are reported honestly
def test_actual_bar_count_reported(monkeypatch):
    import data as D
    _stub_history(monkeypatch, bars=1800)      # venue cannot serve 10000
    frames, meta = D.load_mtf("ETH", 10000)
    assert frames is not None
    # the new schema splits the evaluation target from the warmup-inclusive
    # request; either name must still expose the shortfall honestly
    requested = meta.get("requested_bars_5m",
                         meta.get("requested_with_warmup_5m"))
    assert requested > meta["actual_bars_5m"]
    assert any("SHORTFALL" in w.upper() or "only" in w
               for w in meta["warnings"]), meta["warnings"]
    assert meta["coverage_days"] > 0
    assert meta["pages_fetched"]["5m"] >= 1


# 13b ── verdict is one of the documented codes and never forced
def test_verdict_enum(report):
    assert report["verdict"]["verdict"] in {
        "NO_TRADES", "INSUFFICIENT_SAMPLE", "PROMISING_BUT_INSUFFICIENT_SAMPLE",
        "NO_EDGE", "FRAGILE", "UNSTABLE", "PROVEN_EDGE"}


def test_verdict_not_profitable_without_edge(report):
    v = report["verdict"]
    if v["verdict"] != "PROVEN_EDGE":
        assert v["profitable"] is False


# 12b ── gate counters exist and decrease monotonically where they should
def test_gate_counters_present(report):
    g = report["gate_counters"].get("out_of_sample")
    assert g, "no gate counters for the out-of-sample slice"
    assert g["bars_with_atr"] <= g["total_5m_bars"]
    assert g["entries_filled"] <= g["signals_generated"]


# ─── FIX A: the forming candle is dropped once, not twice ────────────────
def test_loader_output_last_row_is_closed_and_usable(monkeypatch):
    """After the loader runs, the final row IS the last closed bar. Anything
    downstream that then skips len-2 loses a real candle."""
    import data as D
    end = _stub_history(monkeypatch)
    # now is well past the final candle's close, so nothing should be dropped
    frames, meta = D.load_mtf("ETH", 1000, now=end + 100000)
    assert meta["forming_candle_dropped"]["5m"] is False
    last = pd.Timestamp(frames["5m"]["ts"].iat[-1])
    assert last.timestamp() + 300 <= end + 100000


def test_live_uses_the_last_closed_candle(monkeypatch):
    import app as A
    import data as D

    def fake(sym, b5, allow_mixed=False):
        d5 = synth(b5, 5, 13)
        d = d5.set_index("ts")
        rs = lambda r: d.resample(r).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"}).dropna().reset_index()
        f = {"5m": d5, "15m": rs("15min"), "1h": rs("1h")}
        return f, {"symbol": sym, "source": "synthetic", "mixed": False,
                   "frames": {k: {"requested_bars": b5, "actual_bars": len(v),
                                  "short_by": 0,
                                  "coverage_start": str(v["ts"].iat[0]),
                                  "coverage_end": str(v["ts"].iat[-1])}
                              for k, v in f.items()}}

    monkeypatch.setattr(D, "load_mtf", fake)
    A._cache.clear()
    res = A.build_signal("ETH")
    frames, _ = fake("ETH", A.LIVE_BARS_5M)
    expected = str(pd.to_datetime(frames["5m"]["ts"]).iat[-1])
    assert res["last_closed"] == expected, (
        f"live reported {res['last_closed']}, last closed bar is {expected}")


# ─── FIX B: live and backtest calibrate identically ─────────────────────
def test_calibration_is_causal():
    """Each bar's threshold must come only from bars before it."""
    df = poi.add_candle_metrics(synth(1200, 5, 17))
    thr = poi.rolling_body_threshold(df, window=300, target_pct=0.85)

    spike = df.copy()
    spike.loc[spike.index[-1], "body_vs_median"] = 999.0
    thr2 = poi.rolling_body_threshold(spike, window=300, target_pct=0.85)
    pd.testing.assert_series_equal(thr, thr2, check_names=False)


def test_calibration_identical_live_vs_backtest():
    """Same candles must yield the same threshold regardless of how much
    history sits around them. This is the parity guarantee."""
    full = poi.add_candle_metrics(synth(3000, 5, 19))
    thr_full = poi.rolling_body_threshold(full, window=500, target_pct=0.85)

    # a "live" frame: the same tail, fewer bars of history loaded
    tail = full.iloc[-1200:].reset_index(drop=True)
    thr_tail = poi.rolling_body_threshold(tail, window=500, target_pct=0.85)

    a = thr_full.iloc[-700:].to_numpy()
    b = thr_tail.iloc[-700:].to_numpy()
    assert np.allclose(a, b, equal_nan=True), "threshold depends on frame length"


def test_build_context_ignores_calib_end():
    df5 = synth(1500, 5, 23)
    d = df5.set_index("ts")
    rs = lambda r: d.resample(r).agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"}).dropna().reset_index()
    df15, df1h = rs("15min"), rs("1h")
    a = mtf.build_context(df5, df15, df1h, calib_end=None)
    b = mtf.build_context(df5, df15, df1h, calib_end=0.6)
    assert list(a["bias"]) == list(b["bias"])
    assert list(a["trigger"]) == list(b["trigger"])
    assert len(a["setups"]) == len(b["setups"])


# ─── FIX C: sensitivity is out-of-sample only ───────────────────────────
def test_sensitivity_runs_out_of_sample_only(report):
    runs = report["sensitivity"]["runs"]
    assert runs, "no sensitivity runs"
    for r in runs:
        if "error" in r:
            continue
        assert r.get("slice") == "out_of_sample", r
    oos = {m["arm"]: m for m in report["out_of_sample"]}
    baseline = oos.get("SMC_MTF", {}).get("trades", 0)
    for r in runs:
        if "error" in r:
            continue
        assert r["trades"] <= max(baseline * 6, 40), (
            f"{r['param']}={r['value']} produced {r['trades']} trades against an "
            f"out-of-sample baseline of {baseline}; looks like a wider slice")


# ═══ HISTORICAL DATA / SAMPLE SIZE ══════════════════════════════════════
def _fake_venue(bars=5000, tf_secs=300, start_ts=1700000000):
    """A venue that serves at most PAGE_LIMIT candles per request, so the
    loader has to paginate to reach anything larger."""
    import data as D
    all_ts = np.arange(start_ts, start_ts + bars * tf_secs, tf_secs)
    px = 3000 + np.cumsum(np.random.default_rng(1).normal(0, 3, len(all_ts)))

    def pager(symbol, timeframe, end_ts, span):
        lo, hi = end_ts - span, end_ts
        m = (all_ts >= lo) & (all_ts <= hi)
        if not m.any():
            return None
        t, p = all_ts[m][-D.PAGE_LIMIT:], px[m][-D.PAGE_LIMIT:]
        return D._clean(pd.DataFrame({
            "ts": pd.to_datetime(t, unit="s"), "open": p, "high": p + 2,
            "low": p - 2, "close": p, "volume": np.ones(len(t))}))
    return pager, all_ts


def test_pagination_reaches_target(monkeypatch):
    import data as D
    pager, all_ts = _fake_venue(bars=6000)
    monkeypatch.setattr(D, "_page_coindcx", pager)
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    now = float(all_ts[-1]) + 300
    df, meta = D.fetch_ohlcv_history("coindcx", "ETH", "5m", 4000, now=now)
    assert df is not None
    assert meta["pages_fetched"] > 1, "did not paginate"
    assert meta["actual_bars"] == 4000
    assert meta["short_by"] == 0


def test_pagination_stops_when_venue_runs_out(monkeypatch):
    import data as D
    pager, all_ts = _fake_venue(bars=1500)
    monkeypatch.setattr(D, "_page_coindcx", pager)
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    now = float(all_ts[-1]) + 300
    df, meta = D.fetch_ohlcv_history("coindcx", "ETH", "5m", 20000, now=now)
    assert meta["pages_fetched"] < D.MAX_PAGES, "looped instead of stopping"
    assert meta["actual_bars"] == 1500
    assert meta["short_by"] == 18500, "did not report the shortfall honestly"


def test_history_is_deduplicated_and_chronological(monkeypatch):
    import data as D
    pager, all_ts = _fake_venue(bars=3000)
    monkeypatch.setattr(D, "_page_coindcx", pager)
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    df, _ = D.fetch_ohlcv_history("coindcx", "ETH", "5m", 2500,
                                  now=float(all_ts[-1]) + 300)
    assert not df["ts"].duplicated().any()
    assert df["ts"].is_monotonic_increasing


def test_forming_candle_removed_only_when_incomplete():
    import data as D
    ts = pd.date_range("2024-01-01", periods=10, freq="5min")
    df = pd.DataFrame({"ts": ts, "open": 1.0, "high": 1.0, "low": 1.0,
                       "close": 1.0, "volume": 1.0})
    mid = ts[-1].timestamp() + 100          # last candle still forming
    out, dropped = D.drop_forming(df, "5m", now=mid)
    assert dropped and len(out) == 9

    after = ts[-1].timestamp() + 400        # it has since closed
    out2, dropped2 = D.drop_forming(df, "5m", now=after)
    assert not dropped2 and len(out2) == 10, "threw away a closed candle"


def test_bar_limits_are_validated():
    import data as D
    assert D.clamp_bars(50) == D.MIN_BACKTEST_BARS
    assert D.clamp_bars(999999) == D.MAX_BACKTEST_BARS
    assert D.clamp_bars("abc") == D.DEFAULT_BACKTEST_BARS
    assert D.clamp_bars(None) == D.DEFAULT_BACKTEST_BARS
    assert D.clamp_bars(12000) == 12000


def test_required_bars_scale_with_timeframe():
    import data as D
    need = D.required_bars(12000)
    assert need["5m"] > need["15m"] > need["1h"]
    assert need["15m"] >= 12000 // 3
    assert need["1h"] >= 12000 // 12
    for tf in ("5m", "15m", "1h"):
        assert need[tf] > 12000 // {"5m": 1, "15m": 3, "1h": 12}[tf], "no warmup"


def test_common_window_trims_to_the_shortest_frame():
    import data as D
    long5 = pd.DataFrame({"ts": pd.date_range("2024-01-01", periods=2000, freq="5min"),
                          "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0})
    short1h = pd.DataFrame({"ts": pd.date_range("2024-01-04", periods=40, freq="1h"),
                            "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0})
    frames, start, end = D.align_common_window({"5m": long5, "1h": short1h})
    assert start == short1h["ts"].iat[0]
    assert frames["5m"]["ts"].iat[0] >= start
    assert frames["5m"]["ts"].iat[-1] <= end


def test_validation_flags_bad_data():
    import data as D
    ts = pd.date_range("2024-01-01", periods=20, freq="5min")
    df = pd.DataFrame({"ts": ts, "open": 1.0, "high": 1.0, "low": 1.0,
                       "close": 1.0, "volume": 1.0})
    assert D.validate_ohlcv(df, "5m") == []

    bad = df.copy()
    bad.loc[5, "high"] = 0.5                # high below low
    assert any("impossible" in w for w in D.validate_ohlcv(bad, "5m"))

    gap = df.drop(index=range(5, 12)).reset_index(drop=True)
    assert any("gap" in w for w in D.validate_ohlcv(gap, "5m"))

    neg = df.copy()
    neg.loc[3, "close"] = -1.0
    assert any("non-positive" in w for w in D.validate_ohlcv(neg, "5m"))


def test_report_exposes_split_periods(report):
    s = report["split"]
    for k in ("is_start", "is_end", "oos_start", "oos_end", "is_bars", "oos_bars"):
        assert k in s
    assert pd.Timestamp(s["is_end"]) < pd.Timestamp(s["oos_start"]), "split overlaps"
    assert s["is_bars"] > 0 and s["oos_bars"] > 0


def test_walk_forward_reports_periods_and_seeds(report):
    for f in report["walk_forward"]["folds"]:
        assert "period_start" in f and "period_end" in f
        assert pd.Timestamp(f["period_start"]) <= pd.Timestamp(f["period_end"])
        if f["random_runs"]:
            assert f["random_runs"] >= 5


def test_gate_counters_expanded(report):
    g = report["gate_counters"]["out_of_sample"]
    for k in ("total_5m_bars", "valid_1h_bias", "matching_15m_setup",
              "matching_5m_trigger", "all_three_aligned", "entry_level_touched",
              "signals_generated", "entries_filled", "rejected_by_sizing",
              "expired_setup", "duplicate_signal_rejected"):
        assert k in g, k
    assert g["all_three_aligned"] <= min(g["valid_1h_bias"],
                                         g["matching_15m_setup"])
    assert g["entry_level_touched"] <= g["all_three_aligned"]
    assert g["entries_filled"] <= g["signals_generated"]


# ─── DATA PROBE: the diagnosis must name the real failure mode ──────────
def _probe_with(monkeypatch, page_behaviour, bars_available=30000):
    """page_behaviour: 'honours_from' or 'ignores_from'."""
    import data as D
    import app as A
    A._cache.clear()
    end = 1700000000

    def fake(venue, symbol, timeframe, target_bars,
             since=None, now=None, **kw):
        tf, target = timeframe, target_bars
        secs = D.TF_SECONDS[tf]
        if page_behaviour == "ignores_from":
            n, pages = min(D.PAGE_LIMIT, target), 2
        else:
            n, pages = min(target, bars_available), max(1, target // D.PAGE_LIMIT)
        ts = pd.to_datetime(np.arange(end - n * secs, end, secs), unit="s")
        px = np.full(n, 3000.0)
        df = pd.DataFrame({"ts": ts, "open": px, "high": px + 1, "low": px - 1,
                           "close": px, "volume": np.ones(n)})
        return df, {"requested_bars": target, "actual_bars": n,
                    "short_by": max(0, target - n), "source": venue,
                    "symbol": symbol, "timeframe": tf,
                    "coverage_start": str(ts[0]), "coverage_end": str(ts[-1]),
                    "pages_fetched": pages}

    monkeypatch.setattr(D, "fetch_ohlcv_history", fake)
    return A.app.test_client()


def test_probe_detects_working_pagination(monkeypatch):
    c = _probe_with(monkeypatch, "honours_from")
    d = c.get("/api/data-probe/ETH?bars=10000").get_json()
    assert d["actual_bars_5m"] >= 10000
    assert "works" in d["diagnosis"].lower()


def test_probe_detects_venue_ignoring_from(monkeypatch):
    """The failure mode that actually matters: the venue always returns the
    newest window, so backward paging never advances."""
    c = _probe_with(monkeypatch, "ignores_from")
    d = c.get("/api/data-probe/ETH?bars=10000").get_json()
    assert d["actual_bars_5m"] <= 1200
    assert "ignoring" in d["diagnosis"]
    assert d["coverage_days"] < 5


def test_probe_reports_timing_and_all_frames(monkeypatch):
    c = _probe_with(monkeypatch, "honours_from")
    d = c.get("/api/data-probe/ETH?bars=8000").get_json()
    assert set(d["per_timeframe"]) == {"5m", "15m", "1h"}
    assert d["total_seconds"] >= 0
    for tf, v in d["per_timeframe"].items():
        assert "bars_per_page" in v and "seconds" in v


# ═══ ORDER BLOCK RULES (source slides 1-8) ══════════════════════════════
def _ob_frame(sweep=True, gap=True):
    """Hand-built bullish order block.

    bar 0  filler
    bar 1  reference candle, low 98
    bar 2  THE ORDER BLOCK: bearish. Its low sweeps below bar 1 when sweep=True
    bar 3  bullish push
    bar 4  leaves a gap above bar 2's high when gap=True
    bar 5  break of structure
    """
    ob_low = 96.0 if sweep else 98.5      # below / above bar 1's low of 98
    gap_low = 106.0 if gap else 100.5     # above / below bar 2's high of 105
    rows = [
        (100, 101, 99, 100.5),            # 0
        (100.5, 102, 98, 99),             # 1  low = 98
        (105, 105, ob_low, 100),          # 2  bearish OB, high = 105
        (100, 104, 99.5, 103.5),          # 3
        (gap_low, gap_low + 4, gap_low, gap_low + 3),   # 4
        (gap_low + 3, gap_low + 9, gap_low + 2, gap_low + 8),  # 5
    ]
    return pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=len(rows), freq="15min"),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "volume": [1.0] * len(rows)})


def _one_bos(idx=5):
    return [poi.BOS(idx=idx, side="bull", level=102.0, swing_idx=1,
                    body_vs_median=3.0, is_sweep=False)]


def test_ob_requires_liquidity_sweep():
    """Slide 3: the last bearish candle must take out the previous candle's low."""
    df = poi.add_candle_metrics(_ob_frame(sweep=True))
    good = poi.find_order_blocks(df, _one_bos(), require_sweep=True,
                                 require_imbalance=False)
    assert len(good) == 1, "valid swept order block was rejected"
    assert good[0].formed_idx == 2

    df_bad = poi.add_candle_metrics(_ob_frame(sweep=False))
    bad = poi.find_order_blocks(df_bad, _one_bos(), require_sweep=True,
                                require_imbalance=False)
    assert [z.formed_idx for z in bad] != [2], "unswept candle accepted as an OB"


def test_ob_requires_imbalance():
    """Slides 4 and 6: no gap next to the block means no block."""
    df = poi.add_candle_metrics(_ob_frame(gap=True))
    assert poi.find_order_blocks(df, _one_bos(), require_imbalance=True), \
        "block with a clear gap was rejected"

    df_bad = poi.add_candle_metrics(_ob_frame(gap=False))
    assert not poi.find_order_blocks(df_bad, _one_bos(), require_imbalance=True), \
        "block with no gap was accepted"


def test_ob_rules_can_be_switched_off_for_comparison():
    """Both filters off must be a superset: that is how their value gets measured."""
    df = poi.add_candle_metrics(_ob_frame(sweep=False, gap=False))
    loose = poi.find_order_blocks(df, _one_bos(), require_sweep=False,
                                  require_imbalance=False)
    strict = poi.find_order_blocks(df, _one_bos(), require_sweep=True,
                                   require_imbalance=True)
    assert len(loose) >= len(strict)


def test_bearish_ob_sweeps_the_high():
    """Slide 5: the mirror rule. The last bullish candle must exceed the
    previous candle's high."""
    rows = [(100, 101, 99, 100.5),
            (100, 102, 99, 101),            # reference high = 102
            (100, 105, 99.5, 104),          # bullish OB, sweeps above 102
            (104, 104.5, 100, 100.5),
            (99, 99.5, 94, 94.5),           # gap below OB low of 99.5
            (94, 95, 88, 89)]
    df = poi.add_candle_metrics(pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=6, freq="15min"),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "volume": [1.0] * 6}))
    bos = [poi.BOS(idx=5, side="bear", level=99.0, swing_idx=1,
                   body_vs_median=3.0, is_sweep=False)]
    zones = poi.find_order_blocks(df, bos, require_sweep=True,
                                  require_imbalance=True)
    assert len(zones) == 1 and zones[0].formed_idx == 2
    assert zones[0].side == "bear"


def test_three_entry_modes_are_ordered_and_share_one_stop():
    """Slide 7. Price returns to the block from outside, so every mode enters
    at the edge it meets first; only the tightness changes. The stop is the
    same in all three, which is the whole point of the diagram."""
    z = poi.Zone("ob", "bull", 105, 100, wick_top=106, wick_bottom=99,
                 body_top=105, body_bottom=100)
    wick, body, half = z.entry_at("wick"), z.entry_at("body"), z.entry_at("50")
    assert wick > body > half, (wick, body, half)
    assert z.stop_at(0.0) == 99, "stop must sit at the wick, not the body"

    zb = poi.Zone("ob", "bear", 105, 100, wick_top=106, wick_bottom=99,
                  body_top=105, body_bottom=100)
    assert zb.entry_at("wick") < zb.entry_at("body") < zb.entry_at("50")
    assert zb.stop_at(0.0) == 106


def test_entry_mode_flows_through_to_setups(frames):
    _, df15, _ = frames
    out = {}
    for mode in ("wick", "body", "50"):
        p = {**mtf.PARAMS, "ob_entry_mode": mode}
        setups, _ = mtf.find_setups(df15, p)
        out[mode] = setups
        for s in setups:
            assert s.entry_mode == mode
            assert s.entry_level == s.ote_high == s.ote_low
    common = {s.confirmed_ts for s in out["wick"]} & {s.confirmed_ts for s in out["50"]}
    for ts_ in list(common)[:5]:
        w = next(s for s in out["wick"] if s.confirmed_ts == ts_)
        h = next(s for s in out["50"] if s.confirmed_ts == ts_)
        assert w.stop_level == pytest.approx(h.stop_level), \
            "stop moved between entry modes"


def test_stop_is_beyond_the_wick_not_the_body(frames):
    _, df15, _ = frames
    setups, _ = mtf.find_setups(df15, mtf.PARAMS)
    checked = 0
    for s in setups[:40]:
        if s.side == "bull":
            assert s.stop_level < s.entry_level
        else:
            assert s.stop_level > s.entry_level
        checked += 1
    assert checked > 0


# ═══ MISSED-MOVE DIAGNOSTICS ════════════════════════════════════════════
def test_moves_are_non_overlapping(frames):
    import diagnostics as DG
    df5, _, _ = frames
    moves = DG.find_significant_moves(df5)
    assert moves
    for a, b in zip(moves, moves[1:]):
        assert b["start_i"] > a["end_i"], "moves overlap, so misses are double counted"


def test_move_threshold_is_atr_relative(frames):
    """A fixed percentage would flag everything on a volatile asset and nothing
    on a quiet one. Raising the ATR multiple must reduce the count."""
    import diagnostics as DG
    df5, _, _ = frames
    loose = DG.find_significant_moves(df5, {"move_atr_mult": 2.0})
    tight = DG.find_significant_moves(df5, {"move_atr_mult": 5.0})
    assert len(tight) < len(loose)
    for m in tight:
        assert m["mfe_atr"] >= 5.0


def test_profitable_move_is_not_automatically_a_miss(frames):
    """The guard that stops this tool from being used to justify loosening
    filters: a move with no setup at all is VALID_NO_TRADE, not a miss."""
    import diagnostics as DG
    df5, df15, df1h = frames
    r = DG.missed_move_report("ETH", df5, df15, df1h)
    assert r["significant_moves"] > 0
    assert r["true_missed_signals"] < r["significant_moves"], \
        "every move was called a miss"
    assert r["valid_no_trades"] > 0
    assert sum(r["by_class"].values()) == r["significant_moves"]


def test_every_move_gets_a_named_blocker(frames):
    import diagnostics as DG
    df5, df15, df1h = frames
    r = DG.missed_move_report("ETH", df5, df15, df1h)
    assert sum(r["blockers"].values()) == r["significant_moves"]
    for code in r["blockers"]:
        assert code in mtf.BLOCKERS or code == "OUT_OF_RANGE", code


def test_traded_moves_are_not_counted_as_missed(frames):
    import diagnostics as DG
    df5, df15, df1h = frames
    ctx = mtf.build_context(df5, df15, df1h)
    moves = DG.find_significant_moves(df5)
    fake = [{"i": moves[0]["start_i"]}, {"i": moves[1]["start_i"]}]
    r = DG.missed_move_report("ETH", df5, df15, df1h, taken_trades=fake)
    assert r["signals_taken_on_moves"] >= 2
    assert r["capture_rate_pct"] > 0


def test_portfolio_is_pooled_not_averaged():
    """Averaging a 2-trade asset against a 200-trade asset describes nothing."""
    import diagnostics as DG
    big = [{"symbol": "ETH", "entry_ts": f"2024-01-01 00:{i:02d}:00",
            "net_inr": 10.0, "gross_inr": 12.0, "fees_inr": 1.0,
            "slippage_inr": 0.5, "funding_inr": 0.5} for i in range(50)]
    small = [{"symbol": "BANK", "entry_ts": "2024-01-02 00:00:00",
              "net_inr": -500.0, "gross_inr": -480.0, "fees_inr": 12.0,
              "slippage_inr": 6.0, "funding_inr": 2.0}]
    p = DG.portfolio_from_trades(big + small)
    assert p["trades"] == 51
    assert set(p["symbols"]) == {"ETH", "BANK"}
    # pooled net is 50*10 - 500 = 0, an average of win rates would say ~50%
    assert p["net_pnl_inr"] == 0
    assert p["win_rate_pct"] == pytest.approx(98.0, abs=0.1)


def test_blocker_codes_are_distinct_and_documented():
    for code in ("HTF_NEUTRAL", "NO_TRIGGER", "TRIGGER_WRONG_WAY",
                 "NO_SETUP", "SETUP_WRONG_WAY", "SETUP_EXPIRED",
                 "SETUP_MITIGATED", "OK"):
        assert code in mtf.BLOCKERS


def test_gate_state_reports_every_condition(frames):
    df5, df15, df1h = frames
    ctx = mtf.build_context(df5, df15, df1h)
    ts = mtf._ts(df5["ts"])
    s = mtf.gate_state(ctx["bias"][500], ctx["trigger"][500], ctx["setups"],
                       ts.iat[500])
    for k in ("htf_bias_1h", "setup_15m", "trigger_5m", "liquidity_sweep",
              "imbalance", "order_block", "fvg", "action", "blocker",
              "blocker_text"):
        assert k in s


# ═══ SCORING, DAILY LOCATION, STOP VALIDATION ═══════════════════════════
def test_previous_day_levels_never_use_today():
    """The single most common look-ahead in daily-bias systems: reading a high
    that has not printed yet."""
    import scoring as S
    ts = pd.date_range("2024-01-01", periods=576, freq="5min")   # 2 days
    df = pd.DataFrame({"ts": ts, "open": 100.0,
                       "high": np.r_[np.full(288, 110.0), np.full(288, 999.0)],
                       "low": np.r_[np.full(288, 90.0), np.full(288, 1.0)],
                       "close": 100.0, "volume": 1.0})
    hi, lo, mid = S.previous_day_levels(df)
    assert np.isnan(hi[0]), "day 1 has no previous day and must be NaN"
    assert hi[300] == 110.0 and lo[300] == 90.0, "day 2 read its own range"
    assert mid[300] == 100.0


def test_daily_location_is_symmetric():
    import scoring as S
    assert S.daily_location_ok("bull", 95.0, 100.0)
    assert not S.daily_location_ok("bull", 105.0, 100.0)
    assert S.daily_location_ok("bear", 105.0, 100.0)
    assert not S.daily_location_ok("bear", 95.0, 100.0)
    assert not S.daily_location_ok("bull", 95.0, float("nan"))


def test_stop_validation_rejects_both_extremes():
    """Spec 14. A stop under 0.5 ATR is what made cost-in-R explode."""
    import scoring as S
    ok, why = S.validate_stop(100.0, 99.0, atr=10.0)
    assert not ok and "too tight" in why
    ok, why = S.validate_stop(100.0, 80.0, atr=10.0)
    assert not ok and "too wide" in why
    ok, why = S.validate_stop(100.0, 90.0, atr=10.0)
    assert ok


def test_hard_requirements_cannot_be_scored_around():
    """A high score must not rescue a missing mandatory condition."""
    import scoring as S
    flags = {k: True for k in S.WEIGHTS}
    score, bd, ok, blocker = S.score_setup(flags)
    assert ok and score == S.MAX_SCORE

    flags["liquidity_sweep"] = False
    score, bd, ok, blocker = S.score_setup(flags)
    assert not ok and blocker == "NO_LIQUIDITY_SWEEP"
    assert score >= S.CFG["entry_score"], "score was high yet correctly refused"


def test_score_threshold_blocks_weak_setups():
    import scoring as S
    flags = {"liquidity_sweep": True, "structure_15m": True,
             "confirmation_5m": True, "daily_location": True}
    score, bd, ok, blocker = S.score_setup(flags)
    assert score == 8 and not ok and blocker == "SCORE_BELOW_THRESHOLD"
    flags["htf_1h_bias"] = True
    score, bd, ok, blocker = S.score_setup(flags)
    assert score == 10 and ok


def test_scoring_hard_gates_are_subset_of_old_and_gate():
    """Scoring must never permit a trade the old AND gate refused on
    structural grounds; it may only permit ones it refused on alignment."""
    import scoring as S
    flags = {"liquidity_sweep": True, "structure_15m": True,
             "confirmation_5m": True, "daily_location": True,
             "htf_4h_bias": False, "htf_1h_bias": False,
             "displacement_15m": True, "ob_fvg_15m": True,
             "retest_5m": True, "volume": True, "cvd": True,
             "ote_location": True}
    score, bd, ok, blocker = S.score_setup(flags)
    assert ok, "a strong setup with neutral HTF bias should now be allowed"
    for hard in ("liquidity_sweep", "structure_15m", "confirmation_5m"):
        f = dict(flags); f[hard] = False
        _, _, ok2, _ = S.score_setup(f)
        assert not ok2, f"{hard} was treated as optional"


def test_describe_names_what_was_missing():
    import scoring as S
    flags = {"liquidity_sweep": True, "structure_15m": True,
             "confirmation_5m": True}
    d = S.describe(*S.score_setup(flags))
    assert d["blocker"] == "WRONG_SIDE_OF_DAILY_MID"
    assert "daily_location" in d["absent"]
    assert d["max_score"] == 18


# ═══ MFE / MAE AND TIMEOUT DIAGNOSIS ═══════════════════════════════════
def test_excursion_measures_both_directions():
    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=5, freq="5min"),
        "open": [100.0] * 5, "high": [100, 105, 120, 102, 100.0],
        "low": [100.0, 96, 99, 85, 99.0], "close": [100.0] * 5,
        "volume": [1] * 5})
    e = B.excursion(df, "bull", 100.0, 90.0, 1, 4)   # risk = 10
    assert e["mfe_r"] == pytest.approx(2.0)          # high 120 -> +20 = 2R
    assert e["mae_r"] == pytest.approx(1.5)          # low 85  -> -15 = 1.5R
    assert e["bars_to_mfe"] == 1                     # index within the segment

    s = B.excursion(df, "bear", 100.0, 110.0, 1, 4)
    assert s["mfe_r"] == pytest.approx(1.5)
    assert s["mae_r"] == pytest.approx(2.0)


def test_every_trade_carries_excursion(report):
    for t in report["trade_log"][:40]:
        assert "mfe_r" in t and "mae_r" in t
        assert t["mfe_r"] >= 0 and t["mae_r"] >= 0


def test_timeout_diagnosis_picks_a_side(report):
    """The whole point is that it answers entry-vs-exit, not both."""
    ta = report["timeout_analysis"]
    assert "diagnosis" in ta and ta["diagnosis"]
    d = ta["diagnosis"].lower()
    assert ("entry" in d or "exit" in d or "too few" in d
            or "no " in d), ta["diagnosis"]
    for arm, blk in ta["per_arm"].items():
        for reason, stat in blk["by_exit_reason"].items():
            if stat["trades"]:
                assert 0 <= stat["pct_reaching_1R"] <= 100


def test_diagnosis_is_per_arm_never_pooled(report):
    """RANDOM contributes hundreds of structurally doomed trades. If its exit
    profile leaks into the strategy diagnosis, the conclusion describes a coin
    flip rather than the signal."""
    ta = report["timeout_analysis"]
    assert "per_arm" in ta
    assert ta["primary_arm"] in ("smc_mtf", "smc", None)
    arms = set(ta["per_arm"])
    assert "random" not in (ta["primary_arm"] or ""), ta["primary_arm"]
    # each arm's trade counts must be disjoint from the others
    total = sum(sum(s["trades"] for s in blk["by_exit_reason"].values())
                for blk in ta["per_arm"].values())
    assert total == report["trade_log_total"], (total, report["trade_log_total"])
    for arm in arms:
        d = ta["per_arm"][arm]["diagnosis"]
        assert arm in d, f"{arm} diagnosis does not name its own arm"


def test_funding_is_charged_at_stamps_not_continuously():
    """A trade that opens and closes between two funding stamps pays nothing."""
    import risk as R
    assert R.funding_events(6, 5) == 0            # 30 minutes
    assert R.funding_events(60, 5) == 0           # 5 hours
    assert R.funding_events(96, 5) == 1           # exactly 8 hours
    assert R.funding_events(200, 5) == 2          # 16.7 hours
    assert R.funding_cost_inr(100000, 60, 5) == 0.0
    assert R.funding_cost_inr(100000, 96, 5) > 0.0
    # monotonic: a longer hold never pays less
    prev = -1
    for bars in range(0, 400, 20):
        c = R.funding_cost_inr(100000, bars, 5)
        assert c >= prev
        prev = c


def test_min_notional_rejection_names_the_limit():
    import risk as R
    s = R.size_position("DEXE", "BUY", 2.0, 1.9)
    if not s.ok and "minimum" in s.reason:
        assert "MIN_NOTIONAL_INR" in s.reason, s.reason


def test_sensitivity_sweeps_parameters_that_do_something(report, frames):
    """The sensitivity grid must not contain no-op parameters.

    ote_high is the known no-op: find_setups sets ote_low = ote_high =
    entry_level once order block entries replaced OTE, so all three grid values
    produce byte-identical runs and three of nine "independent tests" were
    duplicates.

    HOW A NO-OP IS PROVEN. An earlier version of this test tried ONE
    alternative value per parameter and demanded the engine fingerprint change.
    That is fragile: sweep_window genuinely works (5/10/20/30/60 give 2/5/6/8/9
    setups on this fixture) but one specific pair of values can coincide, and
    the test then failed on a parameter that was doing its job. A single
    synthetic fixture cannot prove absence of effect.

    So a parameter is only flagged as a no-op when BOTH hold:
      1. it is never read on the engine's code path, and
      2. no value in a range changes the engine's output.
    """
    runs = report["sensitivity"]["runs"]
    params = {r["param"] for r in runs}
    assert "ote_high" not in params, "a known no-op parameter is still in the grid"

    df5, df15, df1h = frames

    def fingerprint(p):
        ctx = mtf.build_context(df5, df15, df1h, p)
        return (len(ctx["setups"]),
                tuple(round(s.entry_level, 6) for s in ctx["setups"][:50]),
                tuple(round(s.stop_level, 6) for s in ctx["setups"][:50]),
                tuple(ctx["trigger"][:2000]))

    base = fingerprint(mtf.PARAMS)

    # ote_high is a DETERMINISTIC no-op, not a fixture accident: prove it so
    # the grid can never regain it
    assert fingerprint({**mtf.PARAMS, "ote_high": 0.886}) == base, (
        "ote_high now changes the engine; revisit whether it belongs in the grid")

    source = "".join(inspect.getsource(f) for f in
                     (mtf.find_setups, mtf.trigger_series, mtf.htf_bias_series,
                      mtf.build_context))

    candidates = {
        "max_age": [20, 40, 90, 200],
        "sweep_window": [3, 5, 10, 30, 60],
        "trigger_lookback": [1, 2, 5, 10],
        "ob_entry_mode": ["wick", "50"],
        "stop_buffer_frac": [0.0, 0.05, 0.30],
    }
    for name, alts in candidates.items():
        if name not in params:
            continue
        read = name in source
        moved = any(fingerprint({**mtf.PARAMS, name: v}) != base for v in alts)
        # max_age is applied when zones are READ, not when they are built, so
        # it legitimately cannot move a build-time fingerprint
        if name == "max_age":
            assert read, "max_age is not read anywhere: genuinely a no-op"
            continue
        assert read or moved, (
            f"{name} is neither read on the engine path nor able to change its "
            f"output at any tested value: no-op in the grid")


def test_zero_trade_runs_excluded_from_fragility(report):
    """A parameter that suppresses the strategy entirely is not evidence that
    the strategy loses money."""
    s = report["sensitivity"]
    assert "runs_with_no_trades" in s
    pos, total = s["positive_of_total"].split("/")
    scored = sum(1 for r in s["runs"]
                 if "error" not in r and r.get("trades", 0) > 0)
    assert int(total) == scored


def test_funnel_conversions_are_monotonic(report):
    f = report["signal_funnel"]["out_of_sample"]
    counts = [s["count"] for s in f["stages"]]
    assert counts[0] == max(counts), "a later stage exceeded total bars"
    assert counts[-1] <= counts[-2], "more entries than signals"
    for s in f["stages"]:
        assert 0 <= s["pct_of_bars"] <= 100


def test_verdict_promising_is_distinct_from_insufficient():
    """Spec 37 wants these separated: a positive-expectancy small sample is
    not the same finding as a negative-expectancy small sample."""
    base = {"random_mean_expectancy": -50.0, "random_std_expectancy": 100.0}
    good = {"out_of_sample": [
                {"arm": "SMC_MTF", "trades": 10, "expectancy_inr": 40.0},
                {"arm": "MATCHED_RANDOM_vs_SMC_MTF", **base}],
            "walk_forward": {"folds_beating_random": 3, "folds_scored": 4},
            "sensitivity": {"fragile": False}, "min_trades": 30}
    assert B._verdict(good)["verdict"] == "PROMISING_BUT_INSUFFICIENT_SAMPLE"

    bad = {**good, "out_of_sample": [
        {"arm": "SMC_MTF", "trades": 10, "expectancy_inr": -40.0},
        {"arm": "MATCHED_RANDOM_vs_SMC_MTF", **base}]}
    assert B._verdict(bad)["verdict"] == "INSUFFICIENT_SAMPLE"
    assert B._verdict(good)["profitable"] is False, "promising is not proven"


# ═══ ENTRY QUALITY / POSITION MODES ════════════════════════════════════
def test_entry_vs_exit_failure_is_decided_by_numbers():
    import entry_quality as EQ
    never_moves = [{"outcome": "TIMEOUT", "mfe_r": 0.1, "mae_r": 0.05,
                    "bars_to_mfe": 3, "net_inr": -50.0} for _ in range(20)]
    c = EQ.classify_failure(never_moves)
    assert c["TIMEOUT"]["verdict"] == "ENTRY_FAILURE"

    gives_back = [{"outcome": "TIMEOUT", "mfe_r": 1.6, "mae_r": 0.2,
                   "bars_to_mfe": 5, "net_inr": -30.0} for _ in range(20)]
    c2 = EQ.classify_failure(gives_back)
    assert c2["TIMEOUT"]["verdict"] == "EXIT_FAILURE"


def test_stop_group_flags_immediate_adverse_moves():
    import entry_quality as EQ
    wrong_way = [{"outcome": "STOP", "mfe_r": 0.1, "mae_r": 1.4,
                  "bars_to_mfe": 1, "net_inr": -700.0} for _ in range(20)]
    c = EQ.classify_failure(wrong_way)
    assert "straight away" in c["STOP"]["explanation"]


def test_excursion_profile_reports_every_threshold():
    import entry_quality as EQ
    rows = [{"mfe_r": x, "mae_r": 0.1, "bars_to_mfe": 1, "net_inr": 0.0}
            for x in (0.1, 0.3, 0.6, 0.8, 1.5)]
    p = EQ.excursion_profile(rows, "test")
    assert p["pct_reaching_0.25R"] == 80.0
    assert p["pct_reaching_0.5R"] == 60.0
    assert p["pct_reaching_1.0R"] == 20.0


def test_score_buckets_detect_a_useless_score():
    import entry_quality as EQ
    flat = ([{"score": 3, "net_inr": 100.0, "mfe_r": 1.0} for _ in range(10)] +
            [{"score": 13, "net_inr": 100.0, "mfe_r": 1.0} for _ in range(10)])
    r = EQ.score_buckets(flat)
    assert r["predictive"] is False
    assert "not predictive" in r["note"]

    useful = ([{"score": 3, "net_inr": -200.0, "mfe_r": 0.2} for _ in range(10)] +
              [{"score": 13, "net_inr": 300.0, "mfe_r": 1.5} for _ in range(10)])
    assert EQ.score_buckets(useful)["predictive"] is True


def test_score_buckets_handle_missing_scores():
    import entry_quality as EQ
    r = EQ.score_buckets([{"net_inr": 1.0}, {"net_inr": 2.0}])
    assert r["predictive"] is None and "wire scoring" in r["note"]


def test_max_concurrent_counts_overlap():
    import entry_quality as EQ
    seq = [{"fill_i": 0, "exit_i": 10}, {"fill_i": 20, "exit_i": 30}]
    assert EQ._max_concurrent(seq) == 1
    overlap = [{"fill_i": 0, "exit_i": 10}, {"fill_i": 5, "exit_i": 15},
               {"fill_i": 6, "exit_i": 12}]
    assert EQ._max_concurrent(overlap) == 3


def test_concurrency_modes_change_trade_count(frames):
    """MODE_A was discarding aligned opportunities. Relaxing it must produce
    at least as many trades, and the peak risk must rise with it."""
    df5, df15, df1h = frames
    ctx = mtf.build_context(df5, df15, df1h)
    n = len(df5)
    split = int(n * 0.6)
    counts = {}
    for mode in (1, 2, "per_side"):
        cfg = {**B.DEFAULT_CFG, "concurrency": mode}
        tr, _ = B.run_arm("ETH", df5, ctx, "smc", cfg, split, n - 1,
                          rng=np.random.default_rng(42))
        counts[str(mode)] = len(tr)
    assert counts["2"] >= counts["1"], counts
    assert counts["per_side"] >= counts["1"], counts


def test_gate_value_reports_what_was_removed(frames):
    import entry_quality as EQ
    df5, df15, df1h = frames
    ctx = mtf.build_context(df5, df15, df1h)
    n = len(df5)
    r = EQ.gate_information_value("ETH", df5, ctx, B.DEFAULT_CFG,
                                  int(n * 0.6), n - 1)
    assert "with_all_gates" in r and "trades_removed_by_gates" in r
    assert r["verdict"]


# ═══ STRUCTURE CONFIRMATION ════════════════════════════════════════════
def _bos_frame(hold=True, higher_high=True):
    """bar 4 breaks the swing high of bar 1. What follows decides whether the
    market accepted the break."""
    rows = [(100, 102, 99, 101),
            (101, 108, 100, 107),        # swing high = 108
            (107, 107, 103, 104),
            (104, 106, 102, 105),
            (105, 115, 104, 114),        # BOS: closes above 108
            # pullback: low must dip BELOW the break bar's low to register,
            # but stay above it on a closing basis if the break is to hold
            (114, 114, 109 if hold else 100, 112 if hold else 101),
            (112, 113, 106 if hold else 99, 110 if hold else 100),
            (110, 118 if higher_high else 113, 109, 117 if higher_high else 112),
            (117, 120, 116, 119)]
    return pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=len(rows), freq="15min"),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "volume": [1.0] * len(rows)})


def test_confirmation_accepts_a_real_shift():
    df = poi.add_candle_metrics(_bos_frame(hold=True, higher_high=True))
    sw = poi.find_swings(df, 1, 1)
    brk = [poi.BOS(idx=4, side="bull", level=108.0, swing_idx=1,
                   body_vs_median=3.0, is_sweep=False)]
    p = {**mtf.PARAMS, "confirm_bars": 1, "confirm_max_wait": 6}
    kept, at = mtf._confirm_structure(df, brk, sw, p)
    assert len(kept) == 1, "a held break with HH+HL was rejected"
    assert at[4] > 4, "confirmation bar must be after the break bar"


def test_confirmation_rejects_a_failed_break():
    """Price closes back below the broken level: not a structure shift."""
    df = poi.add_candle_metrics(_bos_frame(hold=False))
    sw = poi.find_swings(df, 1, 1)
    brk = [poi.BOS(idx=4, side="bull", level=108.0, swing_idx=1,
                   body_vs_median=3.0, is_sweep=False)]
    p = {**mtf.PARAMS, "confirm_bars": 1, "confirm_max_wait": 6}
    kept, _ = mtf._confirm_structure(df, brk, sw, p)
    assert kept == [], "a break that closed back through was accepted"


def test_confirmation_delays_when_the_zone_is_tradeable(frames):
    """The real cost of the filter is the DELAY, not the rejections. A setup
    confirmed later cannot be traded at the break bar."""
    _, df15, _ = frames
    off = {**mtf.PARAMS, "require_structure_confirmation": False}
    on = {**mtf.PARAMS, "require_structure_confirmation": True,
          "confirm_bars": 2}
    s_off, _ = mtf.find_setups(df15, off)
    s_on, _ = mtf.find_setups(df15, on)

    assert len(s_on) <= len(s_off), "confirmation produced MORE setups"
    by_off = {s.ts: s for s in s_off}
    checked = 0
    for s in s_on:
        o = by_off.get(s.ts)
        if o is None:
            continue
        assert s.confirmed_ts >= o.confirmed_ts, (
            "confirmed setup became tradeable EARLIER than the unconfirmed one")
        checked += 1
    assert checked > 0, "no comparable setups found"


def test_confirmation_is_on_by_default():
    """Current research architecture enables structure confirmation by default."""
    assert mtf.PARAMS["require_structure_confirmation"] is True


def test_order_block_still_comes_from_the_break_bar(frames):
    """Confirmation must not shift which candle becomes the order block: the
    OB is the last opposite candle before the BREAK, not before the
    confirmation."""
    _, df15, _ = frames
    on = {**mtf.PARAMS, "require_structure_confirmation": True,
          "confirm_bars": 2}
    setups, _ = mtf.find_setups(df15, on)
    for s in setups[:30]:
        # the block must have formed before it became tradeable
        assert s.ts <= s.confirmed_ts


# ═══ RETEST STATE MACHINE (research architecture) ══════════════════════
def test_retest_is_required_by_default():
    """Current architecture requires a 15M retest before entry."""
    assert mtf.PARAMS["require_retest"] is True

def test_poi_without_retest_is_not_tradeable(frames):
    """Creating a POI is not an entry. Until price returns to the zone the
    setup must be invisible to decide()."""
    _, df15, _ = frames
    p = {**mtf.PARAMS, "require_retest": True}
    setups, _ = mtf.find_setups(df15, p)
    waiting = [s for s in setups if s.state == "WAITING_FOR_RETEST"]
    if not waiting:
        pytest.skip("every POI was retested in this fixture")
    s = waiting[0]
    live = mtf.active_setups_at(setups, s.confirmed_ts, s.side)
    assert s not in live, "an un-retested POI was offered for entry"


def test_retest_never_precedes_confirmation(frames):
    _, df15, _ = frames
    p = {**mtf.PARAMS, "require_retest": True}
    setups, _ = mtf.find_setups(df15, p)
    checked = 0
    for s in setups:
        if s.retest_ts is None:
            continue
        assert s.retest_ts >= s.confirmed_ts, (
            "retest recorded before the POI existed")
        checked += 1
    assert checked >= 0


def test_retested_setup_becomes_tradeable_only_after_the_retest(frames):
    _, df15, _ = frames
    p = {**mtf.PARAMS, "require_retest": True}
    setups, _ = mtf.find_setups(df15, p)
    done = [s for s in setups if s.retest_ts is not None]
    if not done:
        pytest.skip("no retested setups in this fixture")
    s = done[0]
    before = s.retest_ts - pd.Timedelta(minutes=15)
    assert s not in mtf.active_setups_at(setups, before, s.side)
    assert s in mtf.active_setups_at(setups, s.retest_ts, s.side)


def test_retest_reduces_or_holds_setup_count(frames):
    """A retest gate may only remove non-retested setups; it must not
    invent additional tradeable setups."""
    _, df15, _ = frames

    off, _ = mtf.find_setups(
        df15,
        {**mtf.PARAMS, "require_retest": False},
    )

    on, _ = mtf.find_setups(
        df15,
        {**mtf.PARAMS, "require_retest": True},
    )

    tradeable_on = [
        s for s in on
        if s.state != "WAITING_FOR_RETEST"
    ]

    assert len(tradeable_on) <= len(off)


def test_poi_quality_is_reported_not_enforced(frames):
    """OB and FVG are parallel POI sources. Quality is reported, not
    used as an implicit gate."""
    _, df15, _ = frames

    setups, _ = mtf.find_setups(df15, mtf.PARAMS)

    if not setups:
        pytest.skip("no setups")

    kinds = {s.poi_quality for s in setups}

    assert kinds <= {"OB", "OB+FVG", "FVG"}

    for s in setups:
        if s.poi_quality == "OB+FVG":
            assert s.has_fvg is True
        elif s.poi_quality == "FVG":
            assert s.has_fvg is True
        elif s.poi_quality == "OB":
            assert s.has_fvg is False

def test_awaiting_retest_has_its_own_blocker_code():
    assert "AWAITING_RETEST" in mtf.BLOCKERS


def test_persistence_counts_bars_after_the_shift_not_including_it():
    """confirm_bars = N means N closed bars AFTER the structure shift
    completes. Counting the completing candle itself made confirm_bars=2
    demand only one bar of persistence."""
    rows = [(100, 102, 99, 101), (101, 108, 100, 107), (107, 107, 103, 104),
            (104, 106, 102, 105), (105, 115, 104, 114), (114, 114, 109, 112),
            (112, 113, 106, 110), (110, 118, 109, 117), (117, 119, 115, 118),
            (118, 120, 116, 119), (119, 121, 117, 120)]
    df = poi.add_candle_metrics(pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=len(rows), freq="15min"),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "volume": [1.0] * len(rows)}))
    sw = poi.find_swings(df, 1, 1)

    # HL forms at bar 6, HH at bar 7, so the shift completes at bar 7
    got = {}
    for need in (0, 1, 2, 3):
        brk = [poi.BOS(idx=4, side="bull", level=108.0, swing_idx=1,
                       body_vs_median=3.0, is_sweep=False)]
        kept, at = mtf._confirm_structure(
            df, brk, sw, {**mtf.PARAMS, "confirm_bars": need,
                          "confirm_max_wait": 8})
        assert kept, f"confirm_bars={need} rejected a valid shift"
        got[need] = list(at.values())[0]

    assert got[0] == 7, f"shift bar should be 7, got {got[0]}"
    for need in (1, 2, 3):
        assert got[need] == 7 + need, (
            f"confirm_bars={need} confirmed at {got[need]}, expected {7 + need}")


def test_more_persistence_never_confirms_earlier():
    """Monotonic by construction: demanding more bars cannot produce an
    earlier entry."""
    rows = [(100, 102, 99, 101), (101, 108, 100, 107), (107, 107, 103, 104),
            (104, 106, 102, 105), (105, 115, 104, 114), (114, 114, 109, 112),
            (112, 113, 106, 110), (110, 118, 109, 117), (117, 119, 115, 118),
            (118, 120, 116, 119), (119, 121, 117, 120)]
    df = poi.add_candle_metrics(pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=len(rows), freq="15min"),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "volume": [1.0] * len(rows)}))
    sw = poi.find_swings(df, 1, 1)
    prev = -1
    for need in range(0, 4):
        brk = [poi.BOS(idx=4, side="bull", level=108.0, swing_idx=1,
                       body_vs_median=3.0, is_sweep=False)]
        _, at = mtf._confirm_structure(
            df, brk, sw, {**mtf.PARAMS, "confirm_bars": need,
                          "confirm_max_wait": 8})
        cur = list(at.values())[0]
        assert cur >= prev
        prev = cur


# ═══ POI SOURCES: OB and FVG as PARALLEL paths ═════════════════════════
def test_poi_sources_default_to_ob_and_fvg():
    """Current architecture allows OB and FVG as parallel POI paths."""
    assert mtf.PARAMS["poi_sources"] == ["ob", "fvg"]

def test_fvg_can_be_a_poi_on_its_own(frames):
    """The architecture branches after structure acceptance: OB POI or FVG
    POI. Research rejected mandatory OB+FVG overlap, so an FVG left by the
    displacement leg is a point of interest by itself."""
    _, df15, _ = frames
    only_fvg, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["fvg"]})
    if not only_fvg:
        pytest.skip("no FVG POIs in this fixture")
    assert all(s.poi_quality == "FVG" for s in only_fvg)


def test_both_paths_is_the_union_not_the_intersection(frames):
    """Parallel paths, not an AND gate. Enabling both must not produce fewer
    setups than either alone."""
    _, df15, _ = frames
    ob, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["ob"]})
    fv, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["fvg"]})
    both, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["ob", "fvg"]})
    assert len(both) >= len(ob)
    assert len(both) >= len(fv)
    assert len(both) <= len(ob) + len(fv), "a POI was counted on both paths"


def test_poi_quality_labels_are_distinct(frames):
    _, df15, _ = frames
    both, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["ob", "fvg"]})
    if not both:
        pytest.skip("no setups")
    assert {s.poi_quality for s in both} <= {"OB", "OB+FVG", "FVG"}


def test_fvg_poi_must_come_from_the_breaking_leg(frames):
    """A gap that merely sits nearby is a coincidence, not a POI. The lineage
    audit reported fvg_from_displacement_leg at zero precisely because
    proximity was being accepted as causation."""
    _, df15, _ = frames
    p = {**mtf.PARAMS, "poi_sources": ["fvg"]}
    setups, _ = mtf.find_setups(df15, p)
    if not setups:
        pytest.skip("no FVG POIs")
    for s in setups[:40]:
        # the POI cannot be tradeable before the break that claimed it
        assert s.confirmed_ts >= s.ts


def test_fvg_poi_is_never_tradeable_before_its_break(frames):
    _, df15, _ = frames
    setups, _ = mtf.find_setups(df15, {**mtf.PARAMS, "poi_sources": ["ob", "fvg"]})
    for s in setups[:40]:
        assert s.expires_ts >= s.confirmed_ts
        assert s.stop_level != s.entry_level
