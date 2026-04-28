import unittest

from backtest.kline import Kline
from strategies.hourly_template import SimplePinbarStrategy
from test.result_utils import write_json, write_text


def _k(ts: int, op: float, hi: float, lo: float, cl: float) -> Kline:
    return Kline(
        symbol="BTCUSDT",
        interval="1h",
        timestamp=ts,
        open_price=op,
        high_price=hi,
        low_price=lo,
        close_price=cl,
        volume=1.0,
    )


class TestSimplePinbarStrategy(unittest.TestCase):
    def test_bearish_pinbar_entry_and_leverage(self):
        s = SimplePinbarStrategy(lookback_bars=3, min_amplitude_pct=0.8)
        klines = [
            _k(1, 100, 100.5, 99.8, 100.1),
            _k(2, 100.1, 100.4, 99.9, 100.0),
            _k(3, 100.0, 100.3, 99.7, 99.9),
            _k(4, 100.0, 101.0, 100.0, 100.2),  # range ~1.0%, upper wick long
        ]
        signal = s.generate_entry_signal(3, klines)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "short")
        self.assertEqual(signal["leverage"], 30)
        write_json("test_strategy/bearish_signal.json", signal)

    def test_bullish_pinbar_entry_and_leverage(self):
        s = SimplePinbarStrategy(lookback_bars=3, min_amplitude_pct=0.8)
        klines = [
            _k(1, 100, 100.3, 99.8, 100.1),
            _k(2, 100.1, 100.2, 99.9, 100.0),
            _k(3, 100.0, 100.1, 99.7, 99.9),
            _k(4, 100.0, 100.2, 98.0, 99.8),  # range ~2.2%, lower wick long
        ]
        signal = s.generate_entry_signal(3, klines)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"], "long")
        self.assertEqual(signal["leverage"], 10)
        write_json("test_strategy/bullish_signal.json", signal)

    def test_should_close_default_false(self):
        s = SimplePinbarStrategy()
        k = _k(1, 100, 101, 99, 100)
        self.assertFalse(s.should_close(0, [k], {"entry_price": 100}))
        write_text("test_strategy/should_close.log", "should_close returns False by default")


if __name__ == "__main__":
    unittest.main()
