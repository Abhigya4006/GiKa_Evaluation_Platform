"""Export endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.export_service import export_run

router = APIRouter()


@router.post("/{run_id}")
def export_run_endpoint(run_id: str) -> Dict[str, Any]:
    """Export all results for a run and return the file paths."""
    try:
        paths = export_run(run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Export failed: {exc}")
    return {"run_id": run_id, "files": paths}
