import time
from datetime import datetime
from typing import Callable, Optional, Union

import pandas as pd
import requests

from backtest.utils import interval_to_seconds, to_unix_millis

BASE_HOSTS = [
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]


class BinanceAPI:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h", timeout: int = 10):
        self.symbol = symbol.upper()
        self.interval = interval
        self.timeout = timeout

    def _request(self, path: str, params: dict):
        last_error = None
        for host in BASE_HOSTS:
            url = f"{host}{path}"
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"All Binance endpoints failed. Last error: {last_error}")

    def get_klines(
        self,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        start_time: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_time: Optional[Union[str, datetime, pd.Timestamp]] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        params = {
            "symbol": (symbol or self.symbol).upper(),
            "interval": interval or self.interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = to_unix_millis(start_time)
        if end_time is not None:
            params["endTime"] = to_unix_millis(end_time)

        data = self._request("/api/v3/klines", params=params)
        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ]
        df = pd.DataFrame(data, columns=columns)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
        ]
        for col in numeric_cols:
            df[col] = df[col].astype(float)
        df["number_of_trades"] = df["number_of_trades"].astype(int)
        return df

    def get_current_price(self, symbol: Optional[str] = None) -> float:
        params = {"symbol": (symbol or self.symbol).upper()}
        data = self._request("/api/v3/ticker/price", params=params)
        return float(data["price"])

    def buy(self, symbol: str, quantity: float, **kwargs):
        raise NotImplementedError("BinanceAPI.buy is not implemented yet.")

    def sell(self, symbol: str, quantity: float, **kwargs):
        raise NotImplementedError("BinanceAPI.sell is not implemented yet.")

    def watch_price(
        self,
        symbol: Optional[str] = None,
        report_every: str = "1h",
        poll_interval_seconds: int = 30,
        rule: Optional[Callable[[float, Optional[float]], bool]] = None,
        on_report: Optional[Callable[[str], None]] = None,
    ):
        symbol = (symbol or self.symbol).upper()
        report_every_seconds = interval_to_seconds(report_every)
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
            except Exception as exc:
                reporter(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] monitor error: {exc}")
            time.sleep(poll_interval_seconds)
