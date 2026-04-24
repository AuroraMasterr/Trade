from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from backtest.monitor import Monitor
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
        self.monitor = Monitor(symbol=config.symbol, interval=config.interval)

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

    def run(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        self._validate()
        candles = self.monitor.get_klines(
            symbol=self.config.symbol,
            interval=self.config.interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        ).reset_index(drop=True)

        trades: List[Dict[str, Any]] = []
        position: Optional[Dict[str, Any]] = None

        for i in range(len(candles)):
            close_price = float(candles.loc[i, "close"])
            high_price = float(candles.loc[i, "high"])
            low_price = float(candles.loc[i, "low"])
            open_time = candles.loc[i, "open_time"]

            if position is None:
                signal = self.strategy.generate_entry_signal(i, candles)
                if signal:
                    side = signal["side"]
                    leverage = float(signal["leverage"])
                    tp_price, sl_price = self._build_tp_sl_prices(close_price, side, leverage)
                    position = {
                        "entry_idx": i,
                        "entry_time": open_time,
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
            strategy_exit = self.strategy.should_close(i, candles, position)
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
                # Conservative assumption for bar-level backtest ambiguity.
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
                        "entry_time": position["entry_time"],
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
        result = {
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "max_hold_bars": self.config.max_hold_bars,
            "stop_loss_pnl_pct": self.config.stop_loss_pnl_pct,
            "take_profit_pnl_pct": self.config.take_profit_pnl_pct,
            "bars": len(candles),
            "trades": len(trades),
            "total_net_levered_return": total_net_levered_return,
            "trade_list": trades,
        }
        return result

    def save_trades_csv(self, result: Dict[str, Any], output_path: str) -> str:
        side_map = {"long": "做多", "short": "做空"}
        reason_map = {
            "stop_loss_same_bar": "同根K线先止损",
            "stop_loss": "止损",
            "take_profit": "止盈",
            "strategy": "策略平仓",
            "max_hold_4h": "超时平仓(4小时)",
        }

        columns = [
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
        ]
        rows: List[Dict[str, Any]] = []
        for idx, t in enumerate(result["trade_list"], start=1):
            rows.append(
                {
                    "序号": idx,
                    "交易对": result["symbol"],
                    "周期": result["interval"],
                    "信号时间": t["entry_time"],
                    "平仓时间": t["exit_time"],
                    "方向": side_map.get(t["side"], t["side"]),
                    "信号类型": t.get("signal"),
                    "Pinbar振幅(%)": t.get("amplitude_pct"),
                    "杠杆倍数": t["leverage"],
                    "开仓价": t["entry_price"],
                    "止盈价": t["tp_price"],
                    "止损价": t["sl_price"],
                    "平仓价": t["exit_price"],
                    "持有K线数": t["hold_bars"],
                    "平仓原因": reason_map.get(t["exit_reason"], t["exit_reason"]),
                    "毛收益率(未杠杆)": t["gross_unlevered_return"],
                    "毛收益率(杠杆后)": t["gross_levered_return"],
                    "净收益率(杠杆后)": t["net_levered_return"],
                    "止损规则(账户%)": result["stop_loss_pnl_pct"],
                    "止盈规则(账户%)": result["take_profit_pnl_pct"],
                    "最大持有小时": result["max_hold_bars"],
                }
            )

        df = pd.DataFrame(rows, columns=columns)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False, encoding="utf-8-sig")
        return str(out.resolve())


if __name__ == "__main__":
    config = BacktestConfig(symbol="BTCUSDT", interval="1h", max_hold_bars=4)
    strategy = SimplePinbarStrategy()
    backtester = Backtester(config=config, strategy=strategy)

    summary = backtester.run(
        start_time="2026-04-01 00:00:00",
        end_time="2026-04-24 00:00:00",
        limit=1000,
    )
    csv_path = backtester.save_trades_csv(summary, output_path="backtest/results/pinbar_backtest_report.csv")
    print(f"回测结果已保存: {csv_path}")
