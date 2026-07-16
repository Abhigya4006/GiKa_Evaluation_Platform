
from __future__ import annotations

from pathlib import Path
from typing import List, Set

from app.core.config import get_settings
from app.core.utils import read_json, utcnow_iso, write_json
from app.db import repository


def checkpoint_path(run_id: str) -> Path:
    return get_settings().checkpoints_dir / f"{run_id}.json"


def load_completed(run_id: str) -> Set[str]:
    completed: Set[str] = set(repository.stored_query_ids(run_id))
    path = checkpoint_path(run_id)
    if path.exists():
        try:
            data = read_json(path)
            completed |= set(data.get("completed", []))
        except Exception:  # noqa: BLE001
            pass
    return completed


def save_checkpoint(run_id: str, completed: List[str]) -> None:
    write_json(checkpoint_path(run_id), {
        "run_id": run_id,
        "updated_at": utcnow_iso(),
        "completed_count": len(completed),
        "completed": sorted(completed),
    })
