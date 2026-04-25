from backtest.binance_api import BinanceAPI


class Monitor(BinanceAPI):
    """Backward-compatible alias. Prefer using BinanceAPI directly."""


def get_binance_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 200):
    api = BinanceAPI(symbol=symbol, interval=interval)
    return api.get_klines(limit=limit)
