import pandas as pd
from types import SimpleNamespace

from app import _forward_entry_near_miss


def _setup(ts="2026-09-21 10:00:00"):
    return SimpleNamespace(confirmed_ts=pd.Timestamp(ts))


def test_buy_entry_touched_then_rejected_is_cancelled():
    df = pd.DataFrame({
        "ts": pd.date_range("2026-09-21 10:00", periods=4, freq="5min"),
        "low": [100.8, 100.0, 100.7, 102.0],
        "high": [101.5, 101.2, 101.3, 102.4],
    })
    cancelled, level = _forward_entry_near_miss(
        df, _setup(), "bull", 100.0, 99.0, 100.9
    )
    assert cancelled is True
    assert level == 100.75


def test_buy_stays_active_while_price_is_at_entry():
    df = pd.DataFrame({
        "ts": pd.date_range("2026-09-21 10:00", periods=3, freq="5min"),
        "low": [100.8, 100.0, 100.2],
        "high": [101.5, 101.2, 101.3],
    })
    cancelled, _ = _forward_entry_near_miss(
        df, _setup(), "bull", 100.0, 99.0, 100.1
    )
    assert cancelled is False


def test_sell_entry_touched_then_rejected_is_cancelled():
    df = pd.DataFrame({
        "ts": pd.date_range("2026-09-21 10:00", periods=4, freq="5min"),
        "low": [98.5, 98.8, 98.7, 97.0],
        "high": [99.2, 100.0, 99.4, 97.5],
    })
    cancelled, level = _forward_entry_near_miss(
        df, _setup(), "bear", 100.0, 101.0, 99.1
    )
    assert cancelled is True
    assert level == 99.25


def test_far_move_without_entry_touch_uses_existing_stale_guard():
    df = pd.DataFrame({
        "ts": pd.date_range("2026-09-21 10:00", periods=3, freq="5min"),
        "low": [102.0, 101.5, 101.2],
        "high": [103.0, 102.5, 102.0],
    })
    cancelled, _ = _forward_entry_near_miss(
        df, _setup(), "bull", 100.0, 99.0, 101.0
    )
    assert cancelled is False
