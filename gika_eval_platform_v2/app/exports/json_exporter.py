
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.utils import write_json


def write_json_export(path: str | Path, obj: Any) -> str:
    write_json(path, obj)
    return str(Path(path))
