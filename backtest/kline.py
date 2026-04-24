from dataclasses import dataclass


@dataclass
class Kline:
    symbol: str
    interval: str
    timestamp: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    @property
    def price_change_pct(self) -> float:
        """Price change percent based on open/close."""
        if self.open_price == 0:
            return 0.0
        return (self.close_price - self.open_price) / self.open_price * 100.0

    @property
    def range_pct(self) -> float:
        """Range percent based on open price."""
        if self.open_price == 0:
            return 0.0
        return (self.high_price - self.low_price) / self.open_price * 100.0

    @property
    def upper_shadow(self) -> float:
        """Upper wick length."""
        return self.high_price - max(self.open_price, self.close_price)

    @property
    def lower_shadow(self) -> float:
        """Lower wick length."""
        return min(self.open_price, self.close_price) - self.low_price

    @property
    def body_size(self) -> float:
        """Body size."""
        return abs(self.close_price - self.open_price)

    @property
    def candle_range(self) -> float:
        """Full candle range."""
        return self.high_price - self.low_price

    def is_tiny_candle(self, max_range_pct: float = 0.2) -> bool:
        """True when candle range percent is less than threshold."""
        return self.range_pct <= max_range_pct

    def is_pinbar(self, wick_ratio_threshold: float = 2.0 / 3.0) -> bool:
        """Simplified pinbar check by wick/range ratio."""
        if self.candle_range <= 0:
            return False
        return (
            self.upper_shadow >= self.candle_range * wick_ratio_threshold
            or self.lower_shadow >= self.candle_range * wick_ratio_threshold
        )

    def is_bullish_pinbar(self, wick_ratio_threshold: float = 2.0 / 3.0) -> bool:
        """Bullish pinbar: long lower wick."""
        if self.candle_range <= 0:
            return False
        return self.lower_shadow >= self.candle_range * wick_ratio_threshold

    def is_bearish_pinbar(self, wick_ratio_threshold: float = 2.0 / 3.0) -> bool:
        """Bearish pinbar: long upper wick."""
        if self.candle_range <= 0:
            return False
        return self.upper_shadow >= self.candle_range * wick_ratio_threshold
