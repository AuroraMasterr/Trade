import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import matplotlib
import pandas as pd

from backtest.binance_api import BinanceAPI
from draw.candlestick_drawer import CandlestickDrawer

matplotlib.use("Agg")


def _mock_klines_df(interval: str, bars: int = 20) -> pd.DataFrame:
    freq_map = {"15m": "15min", "1h": "1h", "2h": "2h", "1d": "1d"}
    freq = freq_map[interval]
    start = datetime(2026, 1, 1, 0, 0, 0)
    times = pd.date_range(start=start, periods=bars, freq=freq)
    rows = []
    for i, t in enumerate(times):
        op = 100.0 + i * 0.5
        cl = op + (0.3 if i % 2 == 0 else -0.2)
        hi = max(op, cl) + 0.4
        lo = min(op, cl) - 0.4
        rows.append(
            {
                "open_time": t,
                "open": op,
                "high": hi,
                "low": lo,
                "close": cl,
                "volume": 10.0 + i,
                "close_time": t + timedelta(minutes=1),
                "quote_asset_volume": 0.0,
                "number_of_trades": 1,
                "taker_buy_base_asset_volume": 0.0,
                "taker_buy_quote_asset_volume": 0.0,
                "ignore": 0,
            }
        )
    return pd.DataFrame(rows)


class TestCandlestickDrawer(unittest.TestCase):
    @patch.object(BinanceAPI, "get_klines")
    def test_plot_by_time_range_multi_intervals(self, mock_get_klines):
        def _side_effect(*args, **kwargs):
            interval = kwargs.get("interval") or "1h"
            return _mock_klines_df(interval=interval, bars=30)

        mock_get_klines.side_effect = _side_effect

        intervals = ["1h", "15m", "1d", "2h"]
        with tempfile.TemporaryDirectory() as td:
            for itv in intervals:
                drawer = CandlestickDrawer(symbol="BTCUSDT", interval=itv)
                out = drawer.plot_by_time_range(
                    "2026-01-01 00:00:00",
                    "2026-01-03 00:00:00",
                    save_path=os.path.join(td, f"chart_{itv}.png"),
                    show=False,
                    highlight_time="2026-01-02 00:00:00",
                )
                self.assertTrue(os.path.exists(out))
                self.assertRegex(os.path.basename(out), re.compile(rf"chart_{re.escape(itv)}_\d{{8}}_\d{{6}}\.png"))

    @patch.object(BinanceAPI, "get_klines")
    def test_plot_last_7d_and_high_low(self, mock_get_klines):
        def _side_effect(*args, **kwargs):
            interval = kwargs.get("interval")
            if interval == "1d":
                df = _mock_klines_df(interval="1d", bars=8)
                # make last day highest high and lowest low false
                df.loc[df.index[-1], "high"] = df["high"].max() + 5.0
                df.loc[df.index[-1], "low"] = df["low"].iloc[-2]
                return df
            return _mock_klines_df(interval="1h", bars=20)

        mock_get_klines.side_effect = _side_effect

        drawer = CandlestickDrawer(symbol="BTCUSDT", interval="1h")
        with tempfile.TemporaryDirectory() as td:
            out = drawer.plot_last_7d_daily(
                current_time="2026-01-08 00:00:00",
                save_path=os.path.join(td, "last7d.png"),
                show=False,
            )
            self.assertTrue(os.path.exists(out))
            self.assertTrue(drawer.is_obvious_high_7d(current_time="2026-01-08 00:00:00"))
            self.assertFalse(drawer.is_obvious_low_7d(current_time="2026-01-08 00:00:00"))


if __name__ == "__main__":
    unittest.main()
