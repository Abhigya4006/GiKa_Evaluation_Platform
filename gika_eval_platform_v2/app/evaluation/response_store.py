
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.core.config import get_settings
from app.core.utils import write_json
from app.db import repository


def response_path(run_id: str, query_id: str) -> Path:
    base = get_settings().raw_responses_dir / run_id
    return base / f"{query_id}.json"


def store_response(
    run_id: str,
    query_id: str,
    raw_payload: Dict[str, Any],
    retrieval_time_ms: int,
    status: str,
) -> str:
    path = response_path(run_id, query_id)
    write_json(path, raw_payload)
    repository.upsert_response({
        "run_id": run_id,
        "query_id": query_id,
        "raw_payload": raw_payload,
        "raw_payload_path": str(path),
        "retrieval_time_ms": retrieval_time_ms,
        "status": status,
    })
    return str(path)


def load_response(run_id: str, query_id: str) -> Dict[str, Any] | None:
    rec = repository.get_response(run_id, query_id)
    return rec.get("raw_payload") if rec else None
