from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

from backtest.binance_api import BinanceAPI
from backtest.kline import Kline
from backtest.utils import append_timestamp, format_datetime, to_datetime
from draw.candlestick_drawer import CandlestickDrawer
from strategies.base import BaseStrategy
from strategies.hourly_template import SimplePinbarStrategy


@dataclass
class BacktestConfig:
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    max_hold_bars: int = 4
    fee_rate: float = 0.0005
    stop_loss_pnl_pct: float = 10.0
    take_profit_pnl_pct: float = 25.0


class Backtester:
    def __init__(self, config: BacktestConfig, strategy: BaseStrategy):
        self.config = config
        self.strategy = strategy
        self.api = BinanceAPI(symbol=config.symbol, interval=config.interval)

    def _validate(self):
        if self.config.interval != "1h":
            raise ValueError("This backtest is designed for 1h candles only.")
        if self.config.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be > 0")
        if self.config.stop_loss_pnl_pct <= 0 or self.config.take_profit_pnl_pct <= 0:
            raise ValueError("stop_loss_pnl_pct and take_profit_pnl_pct must be > 0")

    def _build_tp_sl_prices(self, entry_price: float, side: str, leverage: float):
        tp_move = (self.config.take_profit_pnl_pct / 100.0) / leverage
        sl_move = (self.config.stop_loss_pnl_pct / 100.0) / leverage
        if side == "long":
            tp_price = entry_price * (1.0 + tp_move)
            sl_price = entry_price * (1.0 - sl_move)
        elif side == "short":
            tp_price = entry_price * (1.0 - tp_move)
            sl_price = entry_price * (1.0 + sl_move)
        else:
            raise ValueError(f"unsupported side: {side}")
        return tp_price, sl_price

    @staticmethod
    def _calc_unlevered_return(side: str, entry_price: float, exit_price: float) -> float:
        if side == "long":
            return (exit_price - entry_price) / entry_price
        if side == "short":
            return (entry_price - exit_price) / entry_price
        raise ValueError(f"unsupported side: {side}")

    def _to_klines(self, candles_df: pd.DataFrame, symbol: str) -> List[Kline]:
        klines: List[Kline] = []
        for _, row in candles_df.iterrows():
            klines.append(
                Kline(
                    symbol=symbol,
                    interval=self.config.interval,
                    timestamp=int(pd.Timestamp(row["open_time"]).timestamp()),
                    open_price=float(row["open"]),
                    high_price=float(row["high"]),
                    low_price=float(row["low"]),
                    close_price=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
        return klines

    def run(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        self._validate()
        candles_df = self.api.get_klines(
            symbol=self.config.symbol,
            interval=self.config.interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        ).reset_index(drop=True)
        klines = self._to_klines(candles_df, symbol=self.config.symbol)

        trades: List[Dict[str, Any]] = []
        position: Optional[Dict[str, Any]] = None

        for i in range(len(klines)):
            kline = klines[i]
            close_price = kline.close_price
            high_price = kline.high_price
            low_price = kline.low_price
            open_time = to_datetime(kline.timestamp)

            if position is None:
                signal = self.strategy.generate_entry_signal(i, klines)
                if signal:
                    side = signal["side"]
                    leverage = float(signal["leverage"])
                    tp_price, sl_price = self._build_tp_sl_prices(close_price, side, leverage)
                    position = {
                        "entry_idx": i,
                        "entry_time": open_time,
                        "entry_kline": kline,
                        "side": side,
                        "leverage": leverage,
                        "signal": signal.get("signal"),
                        "amplitude_pct": signal.get("amplitude_pct"),
                        "entry_price": close_price,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                    }
                continue

            hold_bars = i - position["entry_idx"]
            strategy_exit = self.strategy.should_close(i, klines, position)
            timeout_exit = hold_bars >= self.config.max_hold_bars
            side = position["side"]
            tp_price = float(position["tp_price"])
            sl_price = float(position["sl_price"])

            if side == "long":
                hit_tp = high_price >= tp_price
                hit_sl = low_price <= sl_price
            else:
                hit_tp = low_price <= tp_price
                hit_sl = high_price >= sl_price

            exit_reason = None
            exit_price = close_price
            if hit_tp and hit_sl:
                exit_reason = "stop_loss_same_bar"
                exit_price = sl_price
            elif hit_sl:
                exit_reason = "stop_loss"
                exit_price = sl_price
            elif hit_tp:
                exit_reason = "take_profit"
                exit_price = tp_price
            elif strategy_exit:
                exit_reason = "strategy"
            elif timeout_exit:
                exit_reason = "max_hold_4h"

            if exit_reason is not None:
                entry = position["entry_price"]
                leverage = float(position["leverage"])
                gross_unlevered_return = self._calc_unlevered_return(side, entry, exit_price)
                gross_levered_return = gross_unlevered_return * leverage
                net_levered_return = gross_levered_return - 2 * self.config.fee_rate * leverage

                trades.append(
                    {
                        "entry_idx": position["entry_idx"],
                        "entry_time": position["entry_time"],
                        "entry_kline": position["entry_kline"],
                        "exit_time": open_time,
                        "side": side,
                        "leverage": leverage,
                        "signal": position.get("signal"),
                        "amplitude_pct": position.get("amplitude_pct"),
                        "entry_price": entry,
                        "exit_price": exit_price,
                        "tp_price": tp_price,
                        "sl_price": sl_price,
                        "hold_bars": hold_bars,
                        "exit_reason": exit_reason,
                        "gross_unlevered_return": gross_unlevered_return,
                        "gross_levered_return": gross_levered_return,
                        "net_levered_return": net_levered_return,
                    }
                )
                position = None

        total_net_levered_return = sum(t["net_levered_return"] for t in trades)
        return {
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "max_hold_bars": self.config.max_hold_bars,
            "stop_loss_pnl_pct": self.config.stop_loss_pnl_pct,
            "take_profit_pnl_pct": self.config.take_profit_pnl_pct,
            "bars": len(klines),
            "trades": len(trades),
            "total_net_levered_return": total_net_levered_return,
            "trade_list": trades,
        }

    @staticmethod
    def _format_pct(ratio: float) -> str:
        return f"{ratio * 100:.2f}%"

    def save_trades_xlsx(self, result: Dict[str, Any], output_path: str) -> str:
        side_map = {"long": "做多", "short": "做空"}
        reason_map = {
            "stop_loss_same_bar": "同根K线先止损",
            "stop_loss": "止损",
            "take_profit": "止盈",
            "strategy": "策略平仓",
            "max_hold_4h": "超时平仓(4小时)",
        }
        headers = [
            "序号",
            "交易对",
            "周期",
            "信号时间",
            "平仓时间",
            "方向",
            "信号类型",
            "Pinbar振幅(%)",
            "杠杆倍数",
            "开仓价",
            "止盈价",
            "止损价",
            "平仓价",
            "持有K线数",
            "平仓原因",
            "毛收益率(未杠杆)",
            "毛收益率(杠杆后)",
            "净收益率(杠杆后)",
            "止损规则(账户%)",
            "止盈规则(账户%)",
            "最大持有小时",
            "买入点前后4h蜡烛图(高亮当前时刻)",
            "当前时刻前7天日线图(高亮当前时刻)",
        ]

        wb = Workbook()
        ws = wb.active
        ws.title = "Backtest"
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=header)

        out_target = append_timestamp(output_path)
        charts_dir = out_target.parent / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)
        drawer = CandlestickDrawer(symbol=result["symbol"], interval=result["interval"])

        chart1_col = len(headers) - 1
        chart2_col = len(headers)
        ws.column_dimensions[get_column_letter(chart1_col)].width = 70
        ws.column_dimensions[get_column_letter(chart2_col)].width = 70

        for idx, trade in enumerate(result["trade_list"], start=1):
            row_idx = idx + 1
            entry_time = to_datetime(trade["entry_time"])
            row_values = [
                idx,
                result["symbol"],
                result["interval"],
                format_datetime(trade["entry_time"]),
                format_datetime(trade["exit_time"]),
                side_map.get(trade["side"], trade["side"]),
                trade.get("signal"),
                f"{float(trade.get('amplitude_pct', 0.0)):.2f}%",
                trade["leverage"],
                trade["entry_price"],
                trade["tp_price"],
                trade["sl_price"],
                trade["exit_price"],
                trade["hold_bars"],
                reason_map.get(trade["exit_reason"], trade["exit_reason"]),
                self._format_pct(trade["gross_unlevered_return"]),
                self._format_pct(trade["gross_levered_return"]),
                self._format_pct(trade["net_levered_return"]),
                f"{result['stop_loss_pnl_pct']:.2f}%",
                f"{result['take_profit_pnl_pct']:.2f}%",
                result["max_hold_bars"],
            ]
            for col_idx, val in enumerate(row_values, start=1):
                ws.cell(row=row_idx, column=col_idx, value=val)

            entry_kline: Kline = trade["entry_kline"]
            chart_4h = drawer.plot_around_kline(
                center_kline=entry_kline,
                hours_before=4,
                hours_after=4,
                save_path=str(charts_dir / f"{result['symbol']}_{result['interval']}_entry_{idx}_4h.png"),
                show=False,
            )
            chart_7d = drawer.plot_last_7d_daily(
                current_time=entry_time,
                save_path=str(charts_dir / f"{result['symbol']}_{result['interval']}_entry_{idx}_7d_daily.png"),
                show=False,
            )

            img1 = XLImage(chart_4h)
            img1.width = 560
            img1.height = 280
            ws.add_image(img1, f"{get_column_letter(chart1_col)}{row_idx}")

            img2 = XLImage(chart_7d)
            img2.width = 560
            img2.height = 280
            ws.add_image(img2, f"{get_column_letter(chart2_col)}{row_idx}")

            ws.row_dimensions[row_idx].height = 210

        for col_idx in range(1, chart1_col):
            ws.column_dimensions[get_column_letter(col_idx)].width = 16

        out_target.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_target)
        return str(out_target.resolve())


if __name__ == "__main__":
    config = BacktestConfig(symbol="BTCUSDT", interval="1h", max_hold_bars=4)
    strategy = SimplePinbarStrategy()
    backtester = Backtester(config=config, strategy=strategy)
    summary = backtester.run(
        start_time="2026-01-01 00:00:00",
        end_time="2026-01-24 00:00:00",
        limit=1000,
    )
    xlsx_path = backtester.save_trades_xlsx(summary, output_path="backtest/results/pinbar_backtest_report.xlsx")
    print(f"回测结果已保存: {xlsx_path}")
