import os, sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def synth(bars, minutes, seed=1):
    rng = np.random.default_rng(seed)
    sig = 0.60 / np.sqrt(525600 / minutes)
    ret = rng.normal(0, sig, bars)
    close = 3000 * np.exp(np.cumsum(ret))
    w = np.abs(rng.normal(0, sig * 0.7, bars)) * close
    op = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=bars, freq=f"{minutes}min"),
        "open": op, "high": np.maximum(op, close) + w,
        "low": np.minimum(op, close) - w, "close": close,
        "volume": rng.uniform(100, 1000, bars)})


@pytest.fixture(scope="session")
def frames():
    df5 = synth(4000, 5, 7)
    d = df5.set_index("ts")
    rs = lambda r: d.resample(r).agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"}).dropna().reset_index()
    return df5, rs("15min"), rs("1h")


@pytest.fixture(scope="session")
def report(frames):
    import backtest as B
    return B.full_report("ETH", *frames)
