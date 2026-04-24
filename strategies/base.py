from abc import ABC
from typing import Any, Dict, Optional

import pandas as pd


class BaseStrategy(ABC):
    """Strategy interface used by the backtest engine."""

    def generate_entry_signal(
        self,
        i: int,
        candles: pd.DataFrame,
    ) -> Optional[Dict[str, Any]]:
        """
        Return entry signal dict or None.
        Expected keys:
        - side: "long" or "short"
        - leverage: numeric leverage
        """
        return None

    def should_close(
        self,
        i: int,
        candles: pd.DataFrame,
        position: Dict[str, Any],
    ) -> bool:
        """Optional strategy-defined early exit."""
        return False
