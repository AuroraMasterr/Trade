import unittest
from unittest.mock import patch

from backtest.binance_api import BinanceAPI
from test.result_utils import write_json, write_text


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestBinanceAPI(unittest.TestCase):
    @patch("backtest.binance_api.requests.get")
    def test_get_klines_parse(self, mock_get):
        mock_get.return_value = _MockResponse(
            [
                [
                    1704067200000,
                    "100.0",
                    "101.0",
                    "99.5",
                    "100.5",
                    "123.4",
                    1704070799999,
                    "0",
                    "2",
                    "0",
                    "0",
                    "0",
                ]
            ]
        )
        api = BinanceAPI(symbol="BTCUSDT", interval="1h")
        df = api.get_klines(limit=1)
        self.assertEqual(len(df), 1)
        self.assertEqual(float(df.loc[0, "close"]), 100.5)
        self.assertEqual(int(df.loc[0, "number_of_trades"]), 2)
        write_json("test_binance_api/get_klines.json", df.to_dict(orient="records"))

    @patch("backtest.binance_api.requests.get")
    def test_get_current_price(self, mock_get):
        mock_get.return_value = _MockResponse({"symbol": "BTCUSDT", "price": "98765.43"})
        api = BinanceAPI(symbol="BTCUSDT", interval="1h")
        price = api.get_current_price()
        self.assertEqual(price, 98765.43)
        write_json("test_binance_api/get_current_price.json", {"symbol": "BTCUSDT", "price": price})

    def test_buy_sell_not_implemented(self):
        api = BinanceAPI(symbol="BTCUSDT", interval="1h")
        with self.assertRaises(NotImplementedError):
            api.buy(symbol="BTCUSDT", quantity=0.1)
        with self.assertRaises(NotImplementedError):
            api.sell(symbol="BTCUSDT", quantity=0.1)
        write_text("test_binance_api/buy_sell.log", "buy/sell raise NotImplementedError as expected")


if __name__ == "__main__":
    unittest.main()
