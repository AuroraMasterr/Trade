import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
from PIL import Image

from backtest.binance_api import BinanceAPI
from backtest.run_backtest import BacktestConfig, Backtester
from strategies.base import BaseStrategy


class _DummyStrategy(BaseStrategy):
    def generate_entry_signal(self, i, klines):
        if i == 1:
            return {"side": "long", "leverage": 10, "signal": "unit_test", "amplitude_pct": 1.0}
        return None

    def should_close(self, i, klines, position):
        return False


def _mock_bt_df() -> pd.DataFrame:
    start = datetime(2026, 1, 1, 0, 0, 0)
    rows = []
    close_seq = [100.0, 100.0, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7]
    for i in range(len(close_seq)):
        t = start + timedelta(hours=i)
        op = close_seq[i - 1] if i > 0 else close_seq[i]
        cl = close_seq[i]
        hi = max(op, cl) + 0.2
        lo = min(op, cl) - 0.2
        rows.append(
            {
                "open_time": t,
                "open": op,
                "high": hi,
                "low": lo,
                "close": cl,
                "volume": 1.0 + i,
                "close_time": t + timedelta(hours=1),
                "quote_asset_volume": 0.0,
                "number_of_trades": 1,
                "taker_buy_base_asset_volume": 0.0,
                "taker_buy_quote_asset_volume": 0.0,
                "ignore": 0,
            }
        )
    return pd.DataFrame(rows)


class TestBacktest(unittest.TestCase):
    @patch.object(BinanceAPI, "get_klines")
    def test_backtest_run(self, mock_get_klines):
        mock_get_klines.return_value = _mock_bt_df()
        bt = Backtester(config=BacktestConfig(symbol="BTCUSDT", interval="1h", max_hold_bars=4), strategy=_DummyStrategy())
        result = bt.run(start_time="2026-01-01 00:00:00", end_time="2026-01-02 00:00:00", limit=100)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["trade_list"][0]["exit_reason"], "max_hold_4h")

    @patch.object(BinanceAPI, "get_klines")
    def test_backtest_save_xlsx(self, mock_get_klines):
        mock_get_klines.return_value = _mock_bt_df()
        bt = Backtester(config=BacktestConfig(symbol="BTCUSDT", interval="1h", max_hold_bars=4), strategy=_DummyStrategy())
        result = bt.run(start_time="2026-01-01 00:00:00", end_time="2026-01-02 00:00:00", limit=100)

        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "fake.png")
            Image.new("RGB", (80, 40), color=(255, 255, 255)).save(img_path)

            with patch("backtest.run_backtest.CandlestickDrawer.plot_around_kline", return_value=img_path), patch(
                "backtest.run_backtest.CandlestickDrawer.plot_last_7d_daily", return_value=img_path
            ):
                out = bt.save_trades_xlsx(result, output_path=os.path.join(td, "report.xlsx"))
                self.assertTrue(os.path.exists(out))
                self.assertRegex(os.path.basename(out), r"report_\d{8}_\d{6}\.xlsx")


if __name__ == "__main__":
    unittest.main()
