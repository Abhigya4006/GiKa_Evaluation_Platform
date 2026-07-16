
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.utils import read_json
from app.ingestion.adapters import adapt
from app.schemas.dataset import BenchmarkDataset


def load_dataset(path: Optional[str | Path] = None) -> BenchmarkDataset:
    settings = get_settings()
    ds_path = Path(path) if path else settings.sample_dataset_path
    raw = read_json(ds_path)
    if isinstance(raw, (dict, list)):
        internal = adapt(raw)
    else:
        internal = {}
    return BenchmarkDataset.model_validate(internal)


def load_leaderboard(path: Optional[str | Path] = None) -> list[dict]:
    settings = get_settings()
    lb_path = Path(path) if path else settings.sample_leaderboard_path
    if not Path(lb_path).exists():
        return []
    raw = read_json(lb_path)
    if isinstance(raw, dict):
        return raw.get("entries", [])
    if isinstance(raw, list):
        return raw
    return []
