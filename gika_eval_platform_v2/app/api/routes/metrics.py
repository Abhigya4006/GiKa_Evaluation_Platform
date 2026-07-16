"""Metric registry endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from app.metrics.metric_registry_v2 import get_all_metrics, get_metrics_by_category

router = APIRouter()


@router.get("")
def list_metrics() -> List[Dict[str, Any]]:
    """Return all registered metrics with metadata."""
    return [
        {
            "name": m.name,
            "display_name": m.display_name,
            "category": m.category,
            "description": m.description,
            "required_fields": m.required_fields,
        }
        for m in get_all_metrics()
    ]


@router.get("/by-category/{category}")
def metrics_by_category(category: str) -> List[Dict[str, Any]]:
    return [
        {
            "name": m.name,
            "display_name": m.display_name,
            "category": m.category,
            "description": m.description,
            "required_fields": m.required_fields,
        }
        for m in get_metrics_by_category(category)
    ]
