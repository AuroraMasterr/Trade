import requests
import pandas as pd
import time
from datetime import datetime
from typing import Callable, Optional, Union

BASE_HOSTS = [
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]

class Monitor:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h", timeout: int = 10):
        self.symbol = symbol.upper()
        self.interval = interval
        self.timeout = timeout

    def _request(self, path: str, params: dict):
        last_error = None
        for host in BASE_HOSTS:
            url = f"{host}{path}"
            try:
                print(f"Trying: {url}")
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Failed on {url}: {e}")
                last_error = e
        raise RuntimeError(f"All Binance endpoints failed. Last error: {last_error}")

    @staticmethod
    def _to_ms(dt: Optional[Union[str, datetime, pd.Timestamp]]) -> Optional[int]:
        if dt is None:
            return None
        ts = pd.to_datetime(dt)
        return int(ts.timestamp() * 1000)

    @staticmethod
    def _parse_duration_to_seconds(duration: str) -> int:
        unit = duration[-1].lower()
        value = int(duration[:-1])
        if unit == "s":
            return value
        if unit == "m":
            return value * 60
        if unit == "h":
            return value * 3600
        raise ValueError("duration only supports s/m/h, e.g. '30s', '5m', '1h'")

    def get_klines(
        self,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        start_time: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_time: Optional[Union[str, datetime, pd.Timestamp]] = None,
        limit: int = 500,
    ):
        params = {
            "symbol": (symbol or self.symbol).upper(),
            "interval": interval or self.interval,
            "limit": limit,
        }
        start_ms = self._to_ms(start_time)
        end_ms = self._to_ms(end_time)
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms

        data = self._request("/api/v3/klines", params=params)

        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ]

        df = pd.DataFrame(data, columns=columns)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        numeric_cols = [
            "open", "high", "low", "close", "volume",
            "quote_asset_volume", "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume"
        ]
        for col in numeric_cols:
            df[col] = df[col].astype(float)

        df["number_of_trades"] = df["number_of_trades"].astype(int)
        return df

    def get_current_price(self, symbol: Optional[str] = None) -> float:
        params = {"symbol": (symbol or self.symbol).upper()}
        data = self._request("/api/v3/ticker/price", params=params)
        return float(data["price"])

    def watch_price(
        self,
        symbol: Optional[str] = None,
        report_every: str = "1h",
        poll_interval_seconds: int = 30,
        rule: Optional[Callable[[float, Optional[float]], bool]] = None,
        on_report: Optional[Callable[[str], None]] = None,
    ):
        symbol = (symbol or self.symbol).upper()
        report_every_seconds = self._parse_duration_to_seconds(report_every)
        reporter = on_report or print

        last_report_time = 0.0
        last_price = None

        while True:
            try:
                price = self.get_current_price(symbol=symbol)
                now = time.time()

                periodic_trigger = (now - last_report_time) >= report_every_seconds
                rule_trigger = rule(price, last_price) if rule else False

                if periodic_trigger or rule_trigger:
                    reason = "periodic" if periodic_trigger else "rule"
                    reporter(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"{symbol} current price: {price:.8f} (trigger={reason})"
                    )
                    last_report_time = now

                last_price = price
            except Exception as e:
                reporter(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] monitor error: {e}")

            time.sleep(poll_interval_seconds)


def get_binance_klines(symbol="BTCUSDT", interval="1h", limit=200):
    monitor = Monitor(symbol=symbol, interval=interval)
    return monitor.get_klines(limit=limit)


if __name__ == "__main__":
    monitor = Monitor(symbol="BTCUSDT", interval="1h")

    # 1) 查询指定时间段 K 线
    btc_klines = monitor.get_klines(
        start_time="2026-04-20 00:00:00",
        end_time="2026-04-24 00:00:00",
        limit=1000,
    )
    print(btc_klines[["open_time", "open", "high", "low", "close", "volume"]].head())

    # 2) 定义触发规则（当前价格相对上次价格波动超过 0.5% 时触发）
    def price_jump_rule(current_price: float, previous_price: Optional[float]) -> bool:
        if previous_price is None or previous_price == 0:
            return False
        return abs(current_price - previous_price) / previous_price >= 0.005

    # 3) 开始监控：每 1h 至少报告一次；规则满足时也会报告
    # monitor.watch_price(report_every="1h", poll_interval_seconds=30, rule=price_jump_rule)
