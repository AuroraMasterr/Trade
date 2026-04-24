from typing import Any, Dict, List, Optional

from backtest.kline import Kline
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
    def _pick_leverage(amplitude_pct: float) -> Optional[int]:
        if 0.8 <= amplitude_pct <= 1.6:
            return 30
        if 1.6 < amplitude_pct <= 2.5:
            return 10
        if amplitude_pct > 2.5:
            return 5
        return None

    def _is_obvious_high(self, i: int, klines: List[Kline]) -> bool:
        if i < self.lookback_bars:
            return False
        prev = klines[i - self.lookback_bars : i]
        max_prev_high = max(k.high_price for k in prev)
        return klines[i].high_price >= max_prev_high

    def _is_obvious_low(self, i: int, klines: List[Kline]) -> bool:
        if i < self.lookback_bars:
            return False
        prev = klines[i - self.lookback_bars : i]
        min_prev_low = min(k.low_price for k in prev)
        return klines[i].low_price <= min_prev_low

    def generate_entry_signal(
        self,
        i: int,
        klines: List[Kline],
    ) -> Optional[Dict[str, Any]]:
        kline = klines[i]
        amplitude_pct = kline.range_pct
        leverage = self._pick_leverage(amplitude_pct)
        if leverage is None or amplitude_pct < self.min_amplitude_pct:
            return None

        if self._is_obvious_high(i, klines) and kline.is_bearish_pinbar():
            return {
                "side": "short",
                "leverage": leverage,
                "signal": "bearish_pinbar",
                "amplitude_pct": amplitude_pct,
            }

        if self._is_obvious_low(i, klines) and kline.is_bullish_pinbar():
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
        klines: List[Kline],
        position: Dict[str, Any],
    ) -> bool:
        return False


# Backward-compatible alias
HourlyTemplateStrategy = SimplePinbarStrategy
