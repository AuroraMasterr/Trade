# Trade

一个面向加密市场的裸K线研究与回测项目，核心思路**基于通哥和昊神的裸K线交易法**，并将其规则化、工程化，便于：
- 历史回测
- 图形复盘
- 定时监控与消息推送联动（可对接 `wxbot`）

## 方法论说明（重点）

本项目策略框架以“裸K线行为”作为主判断依据，强调：

- 关键位置（相对高低点）
- K线形态（Pinbar/长影线）
- 振幅与波动分层（不同振幅匹配不同杠杆）
- 固定风控（止损/止盈/最大持仓时长）

这与通哥、昊神常用的裸K线交易思想一致：
- 先看结构，再看形态
- 重视高低点与影线表达的资金行为
- 风控优先于主观预测

> 说明：项目是对上述交易法的程序化实现与研究复现，不构成投资建议。

## 项目结构

- `backtest/`
  - `binance_api.py`：Binance K线与价格接口
  - `kline.py`：K线数据结构与形态计算
  - `run_backtest.py`：回测主流程与报表导出
- `strategies/`
  - `base.py`：策略接口
  - `hourly_template.py`：示例策略（SimplePinbarStrategy）
- `draw/`
  - `candlestick_drawer.py`：K线绘图、多周期拼图
- `test/`：单元测试与样例产物

## 核心能力

1. 回测引擎
- 按历史K线逐根推进
- 支持策略开平仓信号
- 支持手续费、止盈止损、最大持仓bar数
- 输出逐笔交易明细与总收益

2. 裸K线策略模板
- `SimplePinbarStrategy`（1h）
- 基于 lookback 高低点 + pinbar 形态 + 振幅阈值
- 振幅分级决定杠杆（示例：30x/10x/5x）

3. 图形复盘
- 单区间K线图
- 围绕入场点局部图
- 多周期拼图（1h+15m / 4h+1h+15m）
- 高低点虚线与价格标注

## 快速开始

## 环境

建议 Python 3.10+（3.9 亦可），安装：
- `pandas`
- `requests`
- `matplotlib`
- `openpyxl`
- `Pillow`

## 运行回测

```powershell
python backtest\run_backtest.py
```

运行后会在 `backtest/results/` 下生成带图Excel报告。

## 运行测试

```powershell
python -m unittest discover -s test
```

## 主要接口示例

```python
from datetime import datetime
from draw.candlestick_drawer import CandlestickDrawer

drawer = CandlestickDrawer(symbol="BTCUSDT", interval="1h")

# 双图：1h + 15m
path1 = drawer.plot_hourly_dual_timeframe(anchor_hour=datetime.now())

# 三图竖排：4h + 1h + 15m
path2 = drawer.plot_hourly_triple_timeframe(anchor_hour=datetime.now())

# 三图分栏：左1h，右上4h，右下15m
path3 = drawer.plot_hourly_triple_timeframe_split(anchor_hour=datetime.now())
```

## 与 wxbot 联动

`wxbot/monitor.py` 可直接调用本项目图表函数：
- 到整点生成图表
- 判断最后1h振幅阈值
- 发送图和摘要到微信联系人

## 风险提示

- 回测结果不代表未来表现。
- 裸K线策略对交易时段、波动状态和执行纪律敏感。
- 建议先小资金、低杠杆、长时间复盘验证。
