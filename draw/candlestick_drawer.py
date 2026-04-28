from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
    def _setup_plot_style():
        plt.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

    @staticmethod
    def _plot_klines(
        klines: List[Kline],
        title: str,
        save_path: Optional[Union[str, Path]] = None,
        show: bool = False,
        highlight_time: Optional[Union[str, datetime, int, float]] = None,
        y_mode: str = "pct",
    ) -> str:
        if not klines:
            raise ValueError("No kline data to plot.")
        if y_mode not in {"pct", "price"}:
            raise ValueError("y_mode must be 'pct' or 'price'")

        CandlestickDrawer._setup_plot_style()
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
        highlight_x = x_vals[highlight_idx]

        # Put highlight line behind candles so wicks stay visible.
        line = ax.axvline(
            highlight_x,
            color="#9ca3af",
            linestyle="--",
            linewidth=1.0,
            alpha=0.45,
            zorder=0,
            label="当前时刻",
        )
        line.set_dashes((10, 8))

        if y_mode == "pct":
            ohlc_seq = pct_ohlc
        else:
            ohlc_seq = [(k.open_price, k.high_price, k.low_price, k.close_price) for k in klines]

        for x, (op, hi, lo, cl) in zip(x_vals, ohlc_seq):
            color = "#16a34a" if cl >= op else "#dc2626"
            ax.vlines(x, lo, hi, color=color, linewidth=1, zorder=2)
            body_low = min(op, cl)
            body_h = abs(cl - op)
            if body_h == 0:
                body_h = max((hi - lo) * 0.02, 1e-6)
            rect = Rectangle((x - width / 2, body_low), width, body_h, facecolor=color, edgecolor=color, linewidth=1, zorder=3)
            ax.add_patch(rect)

        highlight_y = ohlc_seq[highlight_idx][3]
        ax.scatter([highlight_x], [highlight_y], color="#6b7280", s=30, zorder=4)

        ax.set_title(title)
        ax.set_xlabel("时间")
        if y_mode == "pct":
            ax.set_ylabel("涨跌幅(%)")
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}%"))
        else:
            ax.set_ylabel("当前价格")
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
        y_mode: str = "pct",
    ) -> str:
        period = self._fetch_period(start_time=start_time, end_time=end_time, interval=self.interval, limit=limit)
        title = f"{self.symbol} {self.interval} 蜡烛图（{start_time} 到 {end_time}）"
        return self._plot_klines(
            period.klines,
            title=title,
            save_path=save_path,
            show=show,
            highlight_time=highlight_time,
            y_mode=y_mode,
        )

    def plot_around_kline(
        self,
        center_kline: Kline,
        hours_before: int = 4,
        hours_after: int = 4,
        limit: int = 2000,
        save_path: Optional[str] = None,
        show: bool = False,
        y_mode: str = "pct",
    ) -> str:
        if center_kline.symbol.upper() != self.symbol:
            raise ValueError("center_kline symbol must match drawer settings.")
        start_dt = datetime.fromtimestamp(center_kline.timestamp) - timedelta(hours=hours_before)
        end_dt = datetime.fromtimestamp(center_kline.timestamp) + timedelta(hours=hours_after)
        period = self._fetch_period(start_time=start_dt, end_time=end_dt, interval=center_kline.interval, limit=limit)
        title = (
            f"{self.symbol} {center_kline.interval} 买入点前后蜡烛图 "
            f"（-{hours_before}h/+{hours_after}h，中心={datetime.fromtimestamp(center_kline.timestamp)}）"
        )
        return self._plot_klines(
            period.klines,
            title=title,
            save_path=save_path,
            show=show,
            highlight_time=center_kline.timestamp,
            y_mode=y_mode,
        )

    def plot_last_7d_daily(
        self,
        current_time: Optional[Union[str, datetime]] = None,
        save_path: Optional[str] = None,
        show: bool = False,
        y_mode: str = "pct",
    ) -> str:
        now_dt = to_datetime(current_time or datetime.now())
        start_dt = now_dt - timedelta(days=7)
        period = self._fetch_period(start_time=start_dt, end_time=now_dt, interval="1d", limit=20)
        title = f"{self.symbol} 1d 前7天日线图（截至 {now_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
        return self._plot_klines(
            period.klines,
            title=title,
            save_path=save_path,
            show=show,
            highlight_time=now_dt,
            y_mode=y_mode,
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

    @staticmethod
    def _plot_klines_on_axis(
        ax,
        klines: List[Kline],
        title: str,
        highlight_time: Optional[Union[str, datetime, int, float]] = None,
        y_mode: str = "price",
        interval: str = "1h",
    ) -> None:
        if not klines:
            raise ValueError("No kline data to plot.")
        if y_mode not in {"pct", "price"}:
            raise ValueError("y_mode must be 'pct' or 'price'")

        CandlestickDrawer._setup_plot_style()
        highlight_ts = int(to_datetime(highlight_time).timestamp()) if highlight_time is not None else None
        if highlight_ts is None:
            highlight_idx = len(klines) - 1
        else:
            highlight_idx = CandlestickDrawer._find_nearest_index(klines, highlight_ts)

        base_price = klines[highlight_idx].close_price if klines[highlight_idx].close_price != 0 else klines[0].close_price
        pct_ohlc = CandlestickDrawer._to_percent_ohlc(klines, base_price=base_price)

        x_vals = [mdates.date2num(datetime.fromtimestamp(k.timestamp)) for k in klines]
        interval_seconds = 3600 if interval == "1h" else 900 if interval == "15m" else 3600
        width = (interval_seconds / 86400.0) * 0.7
        highlight_x = x_vals[highlight_idx]

        ax.axvline(highlight_x, color="#9ca3af", linestyle="--", linewidth=1.0, alpha=0.45, zorder=0)

        if y_mode == "pct":
            ohlc_seq = pct_ohlc
        else:
            ohlc_seq = [(k.open_price, k.high_price, k.low_price, k.close_price) for k in klines]

        for x, (op, hi, lo, cl) in zip(x_vals, ohlc_seq):
            color = "#16a34a" if cl >= op else "#dc2626"
            ax.vlines(x, lo, hi, color=color, linewidth=1, zorder=2)
            body_low = min(op, cl)
            body_h = abs(cl - op)
            if body_h == 0:
                body_h = max((hi - lo) * 0.02, 1e-6)
            rect = Rectangle((x - width / 2, body_low), width, body_h, facecolor=color, edgecolor=color, linewidth=1, zorder=3)
            ax.add_patch(rect)

        highlight_y = ohlc_seq[highlight_idx][3]
        ax.scatter([highlight_x], [highlight_y], color="#6b7280", s=28, zorder=4)

        ax.set_title(title)
        ax.set_xlabel("时间")
        if y_mode == "pct":
            ax.set_ylabel("涨跌幅(%)")
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}%"))
        else:
            ax.set_ylabel("价格")

        if interval == "1h":
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        elif interval == "15m":
            ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 15, 30, 45]))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))

        # Keep candle positions aligned to exact interval boundaries.
        ax.set_xlim(
            x_vals[0] - (interval_seconds / 86400.0) * 0.5,
            x_vals[-1] + (interval_seconds / 86400.0) * 0.5,
        )
        ax.grid(alpha=0.2)

    def plot_hourly_dual_timeframe(
        self,
        anchor_hour: Optional[Union[str, datetime]] = None,
        save_path: Optional[Union[str, Path]] = None,
        show: bool = False,
        y_mode: str = "price",
    ) -> str:
        """
        Build a stitched image with:
        - last 12h in 1h candles  [anchor-12h, anchor)
        - last 3h  in 15m candles [anchor-3h,  anchor)
        """
        anchor_dt = to_datetime(anchor_hour or datetime.now()).replace(minute=0, second=0, microsecond=0)
        h1_start = anchor_dt - timedelta(hours=12)
        m15_start = anchor_dt - timedelta(hours=3)

        h1_period = self._fetch_period(
            start_time=h1_start,
            end_time=anchor_dt,
            interval="1h",
            limit=24,
        )
        m15_period = self._fetch_period(
            start_time=m15_start,
            end_time=anchor_dt,
            interval="15m",
            limit=32,
        )

        h1_klines = [k for k in h1_period.klines if h1_start.timestamp() <= k.timestamp < anchor_dt.timestamp()]
        m15_klines = [k for k in m15_period.klines if m15_start.timestamp() <= k.timestamp < anchor_dt.timestamp()]

        if len(h1_klines) > 12:
            h1_klines = h1_klines[-12:]
        if len(m15_klines) > 12:
            m15_klines = m15_klines[-12:]

        if not h1_klines or not m15_klines:
            raise ValueError("Not enough kline data to draw dual timeframe chart.")

        CandlestickDrawer._setup_plot_style()
        fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=False)

        self._plot_klines_on_axis(
            axes[0],
            h1_klines,
            title=f"{self.symbol} 1小时K线（{h1_start:%Y-%m-%d %H:%M} 至 {anchor_dt:%Y-%m-%d %H:%M}，不含{anchor_dt:%H:00}）",
            highlight_time=anchor_dt - timedelta(hours=1),
            y_mode=y_mode,
            interval="1h",
        )
        self._plot_klines_on_axis(
            axes[1],
            m15_klines,
            title=f"{self.symbol} 15分钟K线（{m15_start:%Y-%m-%d %H:%M} 至 {anchor_dt:%Y-%m-%d %H:%M}，不含{anchor_dt:%H:00}）",
            highlight_time=anchor_dt - timedelta(minutes=15),
            y_mode=y_mode,
            interval="15m",
        )

        fig.suptitle(f"{self.symbol} 多周期快照（整点：{anchor_dt:%Y-%m-%d %H:%M}）", fontsize=14)
        fig.autofmt_xdate()
        plt.tight_layout()

        out = append_timestamp(save_path or "draw/output/dual_timeframe_chart.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out, dpi=150)
        if show:
            plt.show()
        plt.close(fig)
        return str(out.resolve())

    def get_last_1h_stats(self, anchor_hour: Optional[Union[str, datetime]] = None) -> Dict[str, Any]:
        """Return stats of the last closed 1h candle: [anchor-1h, anchor)."""
        anchor_dt = to_datetime(anchor_hour or datetime.now()).replace(minute=0, second=0, microsecond=0)
        start_dt = anchor_dt - timedelta(hours=2)
        period = self._fetch_period(start_time=start_dt, end_time=anchor_dt, interval="1h", limit=4)
        klines = [k for k in period.klines if (anchor_dt - timedelta(hours=1)).timestamp() <= k.timestamp < anchor_dt.timestamp()]
        if not klines:
            raise ValueError("No last 1h candle found for stats.")
        k = klines[-1]
        return {
            "symbol": self.symbol,
            "start": datetime.fromtimestamp(k.timestamp),
            "end": datetime.fromtimestamp(k.timestamp) + timedelta(hours=1),
            "open": k.open_price,
            "high": k.high_price,
            "low": k.low_price,
            "close": k.close_price,
            "amplitude_pct": k.range_pct,
            "change_pct": k.price_change_pct,
        }
