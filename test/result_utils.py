import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def get_result_dir() -> Path:
    env_dir = os.getenv("TEST_RESULT_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path("test") / f"result_{ts}"
    p.mkdir(parents=True, exist_ok=True)
    os.environ["TEST_RESULT_DIR"] = str(p.resolve())
    return p


def write_text(name: str, content: str) -> Path:
    p = get_result_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def write_json(name: str, data: Any) -> Path:
    p = get_result_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p
