"""Evaluation run endpoints: create, execute, list, detail, dashboard analytics."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api_client.providers import DEFAULT_PROVIDER, available_providers
from app.core.enums import ScopeType
from app.db import repository
from app.evaluation.runner import run_evaluation
from app.services import analytics_service, leaderboard_service
from app.services.run_service import create_run, get_run, list_runs

router = APIRouter()


class CreateRunRequest(BaseModel):
    dataset_id: str
    provider: str = ""
    api_endpoint: str = ""
    run_name: str = ""
    local_mode: bool = False
    selected_metrics: Optional[List[str]] = None
    chat_subscription_id: str = ""
    graph_configs: Optional[List[Dict[str, Any]]] = None
    extra_config: Optional[Dict[str, Any]] = None
    comparison_group_id: str = ""


class ExecuteRunRequest(BaseModel):
    """Optional body for the execute endpoint."""
    pass


@router.get("")
def list_all_runs() -> List[Dict[str, Any]]:
    """List all evaluation runs, newest first."""
    runs = list_runs()
    result = []
    for r in runs:
        # Parse JSON fields for the response.
        rec = dict(r)
        for jf in ("provider_config_json", "api_config_json",
                    "metric_config_json", "selected_metrics_json"):
            raw = rec.pop(jf, None)
            key = jf.replace("_json", "")
            if raw and isinstance(raw, str):
                try:
                    rec[key] = json.loads(raw)
                except Exception:
                    rec[key] = raw
        result.append(rec)
    return result


@router.get("/providers")
def get_providers() -> Dict[str, Any]:
    """Return available retrieval providers and the default."""
    return {
        "providers": available_providers(),
        "default": DEFAULT_PROVIDER,
    }


@router.post("")
def create_new_run(req: CreateRunRequest) -> Dict[str, Any]:
    """Create a new evaluation run (does NOT execute it yet)."""
    chosen_provider = "mock_local" if req.local_mode else (req.provider or DEFAULT_PROVIDER)

    extra_cfg: Dict[str, Any] = dict(req.extra_config or {})
    if chosen_provider != "mock_local" and req.api_endpoint:
        extra_cfg.setdefault("endpoint", req.api_endpoint)

    provider_extra = dict(extra_cfg.get("extra", {}) or {})
    if req.chat_subscription_id:
        provider_extra.setdefault("chat_subscription_id", req.chat_subscription_id)
    if req.graph_configs:
        provider_extra.setdefault("graph_configs", req.graph_configs)
    extra_cfg["extra"] = provider_extra

    try:
        run_id = create_run(
            dataset_id=req.dataset_id,
            api_endpoint=req.api_endpoint if chosen_provider != "mock_local" else None,
            run_name=req.run_name or f"run-{chosen_provider}",
            provider=chosen_provider,
            provider_config=extra_cfg,
            selected_metrics=req.selected_metrics,
            comparison_group_id=req.comparison_group_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {"run_id": run_id, "status": "pending"}


@router.post("/{run_id}/execute")
def execute_run(run_id: str) -> Dict[str, Any]:
    """Execute a pending evaluation run (blocking)."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")

    try:
        summary = run_evaluation(run_id)
    except Exception as exc:
        raise HTTPException(500, f"Evaluation failed: {exc}")

    return summary


@router.get("/{run_id}")
def get_run_detail(run_id: str) -> Dict[str, Any]:
    """Return run metadata."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")
    rec = dict(run)
    for jf in ("provider_config_json", "api_config_json",
                "metric_config_json", "selected_metrics_json"):
        raw = rec.pop(jf, None)
        key = jf.replace("_json", "")
        if raw and isinstance(raw, str):
            try:
                rec[key] = json.loads(raw)
            except Exception:
                rec[key] = raw
    return rec


@router.get("/{run_id}/dashboard")
def get_dashboard_data(run_id: str) -> Dict[str, Any]:
    """
    Full analytics payload for a run — mirrors dashboard._load_dashboard_data.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")
    dataset_id = run.get("dataset_id", "")
    return {
        "run": _clean_run(run),
        "dataset_id": dataset_id,
        "summary": analytics_service.run_summary(run_id),
        "query_rows": analytics_service.query_rows(run_id, dataset_id),
        "difficulty": analytics_service.scope_table(run_id, ScopeType.DIFFICULTY.value),
        "category": analytics_service.scope_table(run_id, ScopeType.CATEGORY.value),
        "documents": analytics_service.document_analysis(run_id, dataset_id),
        "leaderboard": leaderboard_service.leaderboard_comparison(run_id, dataset_id),
    }


@router.get("/{run_id}/queries/{query_id}")
def get_query_detail(run_id: str, query_id: str) -> Dict[str, Any]:
    """Detailed query-level result for inspection."""
    detail = analytics_service.query_detail(run_id, query_id)
    dyn = repository.get_dynamic_metrics_for_query(run_id, query_id)
    detail["dynamic_metrics"] = dyn
    return detail


@router.get("/{run_id}/compare/{other_run_id}")
def compare_two_runs(run_id: str, other_run_id: str) -> Dict[str, Any]:
    """Compare aggregate and per-query metrics between two runs."""
    aggregate = analytics_service.compare_runs(run_id, other_run_id)
    per_query = analytics_service.compare_runs_per_query(run_id, other_run_id)
    return {
        "aggregate": aggregate,
        "per_query": per_query,
    }


def _clean_run(run: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(run)
    for jf in ("provider_config_json", "api_config_json",
                "metric_config_json", "selected_metrics_json"):
        raw = rec.pop(jf, None)
        key = jf.replace("_json", "")
        if raw and isinstance(raw, str):
            try:
                rec[key] = json.loads(raw)
            except Exception:
                rec[key] = raw
    return rec
