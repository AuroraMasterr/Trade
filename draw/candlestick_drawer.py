from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Union

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from backtest.kline import Kline
from backtest.monitor import Monitor
from backtest.period import Period


class CandlestickDrawer:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h"):
        self.symbol = symbol.upper()
        self.interval = interval
        self.monitor = Monitor(symbol=self.symbol, interval=self.interval)

    @staticmethod
    def _to_seconds(dt: Union[str, datetime]) -> int:
        return int(datetime.fromisoformat(str(dt)).timestamp()) if isinstance(dt, str) else int(dt.timestamp())

    def _fetch_period(
        self,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        limit: int = 1500,
    ) -> Period:
        df = self.monitor.get_klines(
            symbol=self.symbol,
            interval=self.interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        klines: List[Kline] = []
        for _, row in df.iterrows():
            ts = int(row["open_time"].timestamp())
            klines.append(
                Kline(
                    symbol=self.symbol,
                    interval=self.interval,
                    timestamp=ts,
                    open_price=float(row["open"]),
                    high_price=float(row["high"]),
                    low_price=float(row["low"]),
                    close_price=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
        return Period(symbol=self.symbol, interval=self.interval, klines=klines)

    @staticmethod
    def _plot_klines(
        klines: List[Kline],
        title: str,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> str:
        if not klines:
            raise ValueError("No kline data to plot.")

        fig, ax = plt.subplots(figsize=(14, 7))
        x_vals = [mdates.date2num(datetime.fromtimestamp(k.timestamp)) for k in klines]
        width = 0.02 if len(x_vals) < 200 else 0.01

        for x, k in zip(x_vals, klines):
            color = "#16a34a" if k.close_price >= k.open_price else "#dc2626"
            ax.vlines(x, k.low_price, k.high_price, color=color, linewidth=1)
            body_low = min(k.open_price, k.close_price)
            body_h = abs(k.close_price - k.open_price)
            if body_h == 0:
                body_h = max((k.high_price - k.low_price) * 0.02, 1e-8)
            rect = Rectangle(
                (x - width / 2, body_low),
                width,
                body_h,
                facecolor=color,
                edgecolor=color,
                linewidth=1,
            )
            ax.add_patch(rect)

        ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Price")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        fig.autofmt_xdate()
        ax.grid(alpha=0.2)

        out = save_path or "draw/output/candlestick.png"
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        if show:
            plt.show()
        plt.close(fig)
        return str(out_path.resolve())

    def plot_by_time_range(
        self,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        limit: int = 1500,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> str:
        period = self._fetch_period(start_time=start_time, end_time=end_time, limit=limit)
        title = f"{self.symbol} {self.interval} Candlestick ({start_time} to {end_time})"
        return self._plot_klines(period.klines, title=title, save_path=save_path, show=show)

    def plot_around_kline(
        self,
        center_kline: Kline,
        days_before: int = 2,
        days_after: int = 2,
        limit: int = 2000,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> str:
        if center_kline.symbol.upper() != self.symbol or center_kline.interval != self.interval:
            raise ValueError("center_kline symbol/interval must match drawer settings.")
        start_dt = datetime.fromtimestamp(center_kline.timestamp) - timedelta(days=days_before)
        end_dt = datetime.fromtimestamp(center_kline.timestamp) + timedelta(days=days_after)
        period = self._fetch_period(start_time=start_dt, end_time=end_dt, limit=limit)
        title = (
            f"{self.symbol} {self.interval} Around {datetime.fromtimestamp(center_kline.timestamp)} "
            f"(-{days_before}d/+{days_after}d)"
        )
        return self._plot_klines(period.klines, title=title, save_path=save_path, show=show)
