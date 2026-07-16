
from __future__ import annotations

from typing import Any, Dict, List

from app.core.enums import ScopeType
from app.db import repository

# Map leaderboard metric names to the aggregated_results overall metric names.
_METRIC_ALIASES = {
    "f1": "f1",
    "exact_match": "exact_match",
    "em": "exact_match",
    "recall": "recall",
    "document_recall": "document_recall",
    "precision": "precision",
}


def leaderboard_comparison(run_id: str, dataset_id: str) -> List[Dict[str, Any]]:
    overall = {a["metric_name"]: a["metric_value"]
               for a in repository.get_aggregates(run_id, ScopeType.OVERALL.value)}
    entries = repository.get_leaderboard(dataset_id)

    rows: List[Dict[str, Any]] = []
    for e in entries:
        metric_key = _METRIC_ALIASES.get(e["metric"], e["metric"])
        current = overall.get(metric_key)
        baseline = e["value"]
        gap = (current - baseline) if current is not None else None
        rows.append({
            "system_name": e["system_name"],
            "metric": e["metric"],
            "current_run": round(current, 4) if current is not None else None,
            "leaderboard": baseline,
            "gap": round(gap, 4) if gap is not None else None,
        })
    return rows
