from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd


def to_datetime(value: Union[str, int, float, datetime, pd.Timestamp]) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    return pd.to_datetime(value).to_pydatetime()


def to_unix_seconds(value: Union[str, int, float, datetime, pd.Timestamp]) -> int:
    return int(to_datetime(value).timestamp())


def to_unix_millis(value: Union[str, int, float, datetime, pd.Timestamp]) -> int:
    return int(to_datetime(value).timestamp() * 1000)


def format_datetime(value: Union[str, int, float, datetime, pd.Timestamp], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return to_datetime(value).strftime(fmt)


def append_timestamp(path: Union[str, Path], dt: Optional[datetime] = None) -> Path:
    p = Path(path)
    now = dt or datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    return p.with_name(f"{p.stem}_{ts}{p.suffix}")


def interval_to_seconds(interval: str) -> int:
    unit = interval[-1].lower()
    value = int(interval[:-1])
    if unit == "s":
        return value
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    if unit == "d":
        return value * 86400
    raise ValueError(f"Unsupported interval: {interval}")
