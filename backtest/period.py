from dataclasses import dataclass
from datetime import datetime
from typing import List

from .kline import Kline
from .utils import interval_to_seconds


@dataclass
class Period:
    symbol: str
    interval: str
    klines: List[Kline]

    def __post_init__(self):
        self.klines = sorted(self.klines, key=lambda k: k.timestamp)
        for k in self.klines:
            if k.symbol != self.symbol:
                raise ValueError("All klines in period must have same symbol.")
            if k.interval != self.interval:
                raise ValueError("All klines in period must have same interval.")

    def is_continuous(self) -> bool:
        if len(self.klines) <= 1:
            return True
        step = interval_to_seconds(self.interval)
        for i in range(1, len(self.klines)):
            if self.klines[i].timestamp - self.klines[i - 1].timestamp != step:
                return False
        return True

    def slice_by_time(self, start_time: datetime, end_time: datetime) -> "Period":
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        sliced = [k for k in self.klines if start_ts <= k.timestamp <= end_ts]
        return Period(symbol=self.symbol, interval=self.interval, klines=sliced)

    def around_kline(self, center: Kline, days_before: int, days_after: int) -> "Period":
        if center.symbol != self.symbol or center.interval != self.interval:
            raise ValueError("Center kline symbol/interval must match this period.")
        start_ts = center.timestamp - days_before * 86400
        end_ts = center.timestamp + days_after * 86400
        sliced = [k for k in self.klines if start_ts <= k.timestamp <= end_ts]
        return Period(symbol=self.symbol, interval=self.interval, klines=sliced)
