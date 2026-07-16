"""Side-by-side comparison endpoints."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import repository
from app.evaluation.runner import run_evaluation
from app.services import analytics_service
from app.services.run_service import create_run

router = APIRouter()


class SystemConfig(BaseModel):
    name: str = "System"
    provider: str = "mock_local"
    local_mode: bool = False
    endpoint: str = "http://127.0.0.1:8000/retrieve"


class CompareRequest(BaseModel):
    dataset_id: str
    system_a: SystemConfig
    system_b: SystemConfig
    selected_metrics: Optional[List[str]] = None


@router.post("")
def run_comparison(req: CompareRequest) -> Dict[str, Any]:
    """Run two retrieval systems on the same dataset and return comparative results."""
    group_id = f"cmp_{uuid.uuid4().hex[:8]}"

    prov_a = "mock_local" if req.system_a.local_mode else req.system_a.provider
    prov_b = "mock_local" if req.system_b.local_mode else req.system_b.provider

    try:
        # System A.
        rid_a = create_run(
            dataset_id=req.dataset_id,
            api_endpoint=req.system_a.endpoint if prov_a != "mock_local" else None,
            run_name=req.system_a.name,
            provider=prov_a,
            selected_metrics=req.selected_metrics,
            comparison_group_id=group_id,
        )
        summary_a = run_evaluation(rid_a)

        # System B.
        rid_b = create_run(
            dataset_id=req.dataset_id,
            api_endpoint=req.system_b.endpoint if prov_b != "mock_local" else None,
            run_name=req.system_b.name,
            provider=prov_b,
            selected_metrics=req.selected_metrics,
            comparison_group_id=group_id,
        )
        summary_b = run_evaluation(rid_b)

    except Exception as exc:
        raise HTTPException(500, f"Comparison failed: {exc}")

    # Aggregate comparison.
    aggregate = analytics_service.compare_runs(rid_a, rid_b)
    per_query = analytics_service.compare_runs_per_query(rid_a, rid_b)

    return {
        "group_id": group_id,
        "system_a": {"run_id": rid_a, "name": req.system_a.name, "summary": summary_a},
        "system_b": {"run_id": rid_b, "name": req.system_b.name, "summary": summary_b},
        "aggregate": aggregate,
        "per_query": per_query,
    }


@router.get("/groups")
def list_comparison_groups() -> List[Dict[str, Any]]:
    """Return historical comparison groups."""
    all_runs = repository.list_runs()
    groups: Dict[str, List[Dict]] = {}
    for r in all_runs:
        gid = r.get("comparison_group_id") or ""
        if isinstance(gid, str) and gid.startswith("cmp_"):
            groups.setdefault(gid, []).append(r)

    result = []
    for gid, gruns in sorted(groups.items(), reverse=True):
        summaries = []
        for r in gruns:
            overall = analytics_service.run_summary(r["run_id"])["overall"]
            summaries.append({
                "run_id": r["run_id"],
                "run_name": r.get("run_name", ""),
                "provider": r.get("provider", ""),
                "status": r.get("status", ""),
                "f1": overall.get("f1"),
                "recall": overall.get("recall"),
                "success_rate": overall.get("success_rate"),
            })
        result.append({"group_id": gid, "runs": summaries})
    return result
