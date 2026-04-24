from draw import CandlestickDrawer
from backtest.kline import Kline

drawer = CandlestickDrawer(symbol="BTCUSDT", interval="1h")
drawer.plot_by_time_range("2026-04-01 00:00:00", "2026-04-05 00:00:00")

k = Kline(symbol="BTCUSDT", interval="1h", timestamp=1711929600,
    open_price=68000, high_price=69000, low_price=67000, close_price=68500, volume=123.4)
drawer.plot_around_kline(k, days_before=2, days_after=2)
