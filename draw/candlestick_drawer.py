from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Union

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

from backtest.binance_api import BinanceAPI
from backtest.kline import Kline
from backtest.period import Period
from backtest.utils import append_timestamp, to_datetime


class CandlestickDrawer:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h"):
        self.symbol = symbol.upper()
        self.interval = interval
        self.api = BinanceAPI(symbol=self.symbol, interval=self.interval)

    def _fetch_period(
        self,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        interval: Optional[str] = None,
        limit: int = 1500,
    ) -> Period:
        itv = interval or self.interval
        df = self.api.get_klines(
            symbol=self.symbol,
            interval=itv,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        klines: List[Kline] = []
        for _, row in df.iterrows():
            klines.append(
                Kline(
                    symbol=self.symbol,
                    interval=itv,
                    timestamp=int(row["open_time"].timestamp()),
                    open_price=float(row["open"]),
                    high_price=float(row["high"]),
                    low_price=float(row["low"]),
                    close_price=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
        return Period(symbol=self.symbol, interval=itv, klines=klines)

    @staticmethod
    def _calc_width(x_vals: List[float]) -> float:
        if len(x_vals) < 2:
            return 0.6
        diffs = [x_vals[i] - x_vals[i - 1] for i in range(1, len(x_vals))]
        min_diff = min(diffs)
        return max(min_diff * 0.7, 0.01)

    @staticmethod
    def _to_percent_ohlc(klines: List[Kline], base_price: float) -> List[Tuple[float, float, float, float]]:
        out: List[Tuple[float, float, float, float]] = []
        for k in klines:
            out.append(
                (
                    (k.open_price - base_price) / base_price * 100.0,
                    (k.high_price - base_price) / base_price * 100.0,
                    (k.low_price - base_price) / base_price * 100.0,
                    (k.close_price - base_price) / base_price * 100.0,
                )
            )
        return out

    @staticmethod
    def _find_nearest_index(klines: List[Kline], ts: int) -> int:
        best_i = 0
        best_d = abs(klines[0].timestamp - ts)
        for i in range(1, len(klines)):
            d = abs(klines[i].timestamp - ts)
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    @staticmethod
    def _plot_klines(
        klines: List[Kline],
        title: str,
        save_path: Optional[Union[str, Path]] = None,
        show: bool = False,
        highlight_time: Optional[Union[str, datetime, int, float]] = None,
    ) -> str:
        if not klines:
            raise ValueError("No kline data to plot.")

        highlight_ts = int(to_datetime(highlight_time).timestamp()) if highlight_time is not None else None
        if highlight_ts is None:
            highlight_idx = len(klines) // 2
        else:
            highlight_idx = CandlestickDrawer._find_nearest_index(klines, highlight_ts)

        base_price = klines[highlight_idx].close_price if klines[highlight_idx].close_price != 0 else klines[0].close_price
        pct_ohlc = CandlestickDrawer._to_percent_ohlc(klines, base_price=base_price)

        fig, ax = plt.subplots(figsize=(14, 7))
        x_vals = [mdates.date2num(datetime.fromtimestamp(k.timestamp)) for k in klines]
        width = CandlestickDrawer._calc_width(x_vals)

        for x, (op, hi, lo, cl) in zip(x_vals, pct_ohlc):
            color = "#16a34a" if cl >= op else "#dc2626"
            ax.vlines(x, lo, hi, color=color, linewidth=1)
            body_low = min(op, cl)
            body_h = abs(cl - op)
            if body_h == 0:
                body_h = max((hi - lo) * 0.02, 1e-6)
            rect = Rectangle((x - width / 2, body_low), width, body_h, facecolor=color, edgecolor=color, linewidth=1)
            ax.add_patch(rect)

        highlight_x = x_vals[highlight_idx]
        highlight_y = pct_ohlc[highlight_idx][3]
        ax.axvline(highlight_x, color="#1d4ed8", linestyle="--", linewidth=1.2, alpha=0.9, label="当前时刻")
        ax.scatter([highlight_x], [highlight_y], color="#1d4ed8", s=30, zorder=5)

        ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Change (%)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}%"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        ax.grid(alpha=0.2)
        ax.legend(loc="best")
        fig.autofmt_xdate()

        out = append_timestamp(save_path or "draw/output/candlestick.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(out, dpi=150)
        if show:
            plt.show()
        plt.close(fig)
        return str(out.resolve())

    def plot_by_time_range(
        self,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        limit: int = 1500,
        save_path: Optional[str] = None,
        show: bool = False,
        highlight_time: Optional[Union[str, datetime, int, float]] = None,
    ) -> str:
        period = self._fetch_period(start_time=start_time, end_time=end_time, interval=self.interval, limit=limit)
        title = f"{self.symbol} {self.interval} Candlestick ({start_time} to {end_time})"
        return self._plot_klines(period.klines, title=title, save_path=save_path, show=show, highlight_time=highlight_time)

    def plot_around_kline(
        self,
        center_kline: Kline,
        hours_before: int = 4,
        hours_after: int = 4,
        limit: int = 2000,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> str:
        if center_kline.symbol.upper() != self.symbol:
            raise ValueError("center_kline symbol must match drawer settings.")
        start_dt = datetime.fromtimestamp(center_kline.timestamp) - timedelta(hours=hours_before)
        end_dt = datetime.fromtimestamp(center_kline.timestamp) + timedelta(hours=hours_after)
        period = self._fetch_period(start_time=start_dt, end_time=end_dt, interval=center_kline.interval, limit=limit)
        title = (
            f"{self.symbol} {center_kline.interval} Around {datetime.fromtimestamp(center_kline.timestamp)} "
            f"(-{hours_before}h/+{hours_after}h)"
        )
        return self._plot_klines(
            period.klines,
            title=title,
            save_path=save_path,
            show=show,
            highlight_time=center_kline.timestamp,
        )

    def plot_last_7d_daily(
        self,
        current_time: Optional[Union[str, datetime]] = None,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> str:
        now_dt = to_datetime(current_time or datetime.now())
        start_dt = now_dt - timedelta(days=7)
        period = self._fetch_period(start_time=start_dt, end_time=now_dt, interval="1d", limit=20)
        title = f"{self.symbol} 1d Previous 7 Days (to {now_dt.strftime('%Y-%m-%d %H:%M:%S')})"
        return self._plot_klines(
            period.klines,
            title=title,
            save_path=save_path,
            show=show,
            highlight_time=now_dt,
        )

    def is_obvious_high_7d(self, current_time: Optional[Union[str, datetime]] = None) -> bool:
        now_dt = to_datetime(current_time or datetime.now())
        start_dt = now_dt - timedelta(days=7)
        period = self._fetch_period(start_time=start_dt, end_time=now_dt, interval="1d", limit=20)
        if len(period.klines) < 2:
            return False
        highs = [k.high_price for k in period.klines]
        return highs[-1] >= max(highs[:-1])

    def is_obvious_low_7d(self, current_time: Optional[Union[str, datetime]] = None) -> bool:
        now_dt = to_datetime(current_time or datetime.now())
        start_dt = now_dt - timedelta(days=7)
        period = self._fetch_period(start_time=start_dt, end_time=now_dt, interval="1d", limit=20)
        if len(period.klines) < 2:
            return False
        lows = [k.low_price for k in period.klines]
        return lows[-1] <= min(lows[:-1])
