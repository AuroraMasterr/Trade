from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseStrategy


class SimplePinbarStrategy(BaseStrategy):
    """
    Simplified pinbar strategy on 1h candles:
    - obvious high/low context by lookback range
    - wick length >= 2/3 of candle range
    - leverage selected by candle amplitude
    """

    def __init__(self, lookback_bars: int = 24, min_amplitude_pct: float = 0.8):
        self.lookback_bars = lookback_bars
        self.min_amplitude_pct = min_amplitude_pct

    @staticmethod
    def _calc_amplitude_pct(row: pd.Series) -> float:
        base = float(row["open"])
        if base == 0:
            return 0.0
        return (float(row["high"]) - float(row["low"])) / base * 100.0

    @staticmethod
    def _pick_leverage(amplitude_pct: float) -> Optional[int]:
        if 0.8 <= amplitude_pct <= 1.6:
            return 30
        if 1.6 < amplitude_pct <= 2.5:
            return 10
        if amplitude_pct > 2.5:
            return 5
        return None

    @staticmethod
    def _is_bearish_pinbar(row: pd.Series) -> bool:
        high = float(row["high"])
        low = float(row["low"])
        op = float(row["open"])
        cl = float(row["close"])

        candle_range = high - low
        if candle_range <= 0:
            return False

        upper_wick = high - max(op, cl)
        return upper_wick >= candle_range * (2.0 / 3.0)

    @staticmethod
    def _is_bullish_pinbar(row: pd.Series) -> bool:
        high = float(row["high"])
        low = float(row["low"])
        op = float(row["open"])
        cl = float(row["close"])

        candle_range = high - low
        if candle_range <= 0:
            return False

        lower_wick = min(op, cl) - low
        return lower_wick >= candle_range * (2.0 / 3.0)

    def _is_obvious_high(self, i: int, candles: pd.DataFrame) -> bool:
        if i < self.lookback_bars:
            return False
        prev = candles.iloc[i - self.lookback_bars : i]
        return float(candles.loc[i, "high"]) >= float(prev["high"].max())

    def _is_obvious_low(self, i: int, candles: pd.DataFrame) -> bool:
        if i < self.lookback_bars:
            return False
        prev = candles.iloc[i - self.lookback_bars : i]
        return float(candles.loc[i, "low"]) <= float(prev["low"].min())

    def generate_entry_signal(
        self,
        i: int,
        candles: pd.DataFrame,
    ) -> Optional[Dict[str, Any]]:
        row = candles.loc[i]
        amplitude_pct = self._calc_amplitude_pct(row)
        leverage = self._pick_leverage(amplitude_pct)
        if leverage is None or amplitude_pct < self.min_amplitude_pct:
            return None

        if self._is_obvious_high(i, candles) and self._is_bearish_pinbar(row):
            return {
                "side": "short",
                "leverage": leverage,
                "signal": "bearish_pinbar",
                "amplitude_pct": amplitude_pct,
            }

        if self._is_obvious_low(i, candles) and self._is_bullish_pinbar(row):
            return {
                "side": "long",
                "leverage": leverage,
                "signal": "bullish_pinbar",
                "amplitude_pct": amplitude_pct,
            }

        return None

    def should_close(
        self,
        i: int,
        candles: pd.DataFrame,
        position: Dict[str, Any],
    ) -> bool:
        return False


# Backward-compatible alias
HourlyTemplateStrategy = SimplePinbarStrategy
