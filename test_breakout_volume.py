import unittest

import numpy as np
import pandas as pd

from breakout_volume import signals


class BreakoutVolumeTests(unittest.TestCase):
    def _df(self):
        n = 80
        base = np.arange(n, dtype=float) + 100.0
        high = base + 1.0
        low = base - 1.0
        close = base.copy()
        volume = np.full(n, 100.0)
        ts = pd.date_range("2026-01-01", periods=n, freq="5min")
        return pd.DataFrame(
            {
                "open": base,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "ts": ts,
            }
        )

    def test_signal_does_not_use_current_bar_for_level_or_volume_baseline(self):
        df = self._df()
        # Make the final bar break the prior high with high volume.
        prior_high = df["high"].iloc[-21:-1].max()
        df.loc[df.index[-1], "close"] = prior_high + 2.0
        df.loc[df.index[-1], "high"] = prior_high + 2.5
        df.loc[df.index[-1], "volume"] = 250.0

        out = signals(df)
        last = out.iloc[-1]

        self.assertEqual(last["side"], "bull")
        self.assertAlmostEqual(last["level"], prior_high)
        self.assertGreaterEqual(last["volume_ratio"], 2.5)
        self.assertTrue(bool(last["signal"]))

    def test_no_signal_before_lookback_is_available(self):
        df = self._df().iloc[:30].copy()
        out = signals(df)
        self.assertTrue(out["side"].iloc[:21].isna().all())
        self.assertFalse(bool(out["signal"].iloc[:21].any()))


if __name__ == "__main__":
    unittest.main()
