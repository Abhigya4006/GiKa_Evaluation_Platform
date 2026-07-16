
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from app.core.enums import ScopeType
from app.core.utils import safe_div
from app.db import repository
from app.metrics.metric_registry import V1_ALL_METRICS

# The set aggregated here MUST match V1_ALL_METRICS from the metric registry.
_AVG_METRICS = list(V1_ALL_METRICS)


def _get_dynamic_metric_names(run_id: str) -> list:
    all_dyn = repository.get_dynamic_metrics(run_id)
    names = sorted({r["metric_name"] for r in all_dyn})
    # Exclude metrics already in V1 to avoid double-counting.
    return [n for n in names if n not in set(_AVG_METRICS)]


def _avg(rows: List[Dict[str, Any]], key: str) -> float:
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    if not vals:
        return 0.0
    return round(safe_div(sum(vals), len(vals)), 4)


def _scope_block(run_id: str, scope_type: str, scope_value: str,
                 rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in _AVG_METRICS:
        out.append({
            "run_id": run_id, "scope_type": scope_type, "scope_value": scope_value,
            "metric_name": m, "metric_value": _avg(rows, m),
        })
    success_rate = round(safe_div(sum(1 for r in rows if r.get("success")), len(rows)), 4) if rows else 0.0
    out.append({
        "run_id": run_id, "scope_type": scope_type, "scope_value": scope_value,
        "metric_name": "success_rate", "metric_value": success_rate,
    })
    out.append({
        "run_id": run_id, "scope_type": scope_type, "scope_value": scope_value,
        "metric_name": "num_queries", "metric_value": float(len(rows)),
    })
    return out


def aggregate_run(run_id: str, dataset_id: str) -> List[Dict[str, Any]]:
    metrics = repository.get_query_metrics(run_id)
    queries = {q["query_id"]: q for q in repository.get_queries(dataset_id)}

    rows: List[Dict[str, Any]] = []

    # Overall.
    rows += _scope_block(run_id, ScopeType.OVERALL.value, "all", metrics)

    # By difficulty.
    by_diff: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # By category.
    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # Failure counts.
    fail_counts: Dict[str, int] = defaultdict(int)

    for m in metrics:
        q = queries.get(m["query_id"], {})
        diff = q.get("difficulty", "unknown")
        by_diff[diff].append(m)
        for cat in q.get("categories", []):
            by_cat[cat].append(m)
        fail_counts[m.get("failure_type", "success")] += 1

    for diff, diff_rows in by_diff.items():
        rows += _scope_block(run_id, ScopeType.DIFFICULTY.value, diff, diff_rows)

    for cat, cat_rows in by_cat.items():
        rows += _scope_block(run_id, ScopeType.CATEGORY.value, cat, cat_rows)

    for ftype, count in fail_counts.items():
        rows.append({
            "run_id": run_id, "scope_type": ScopeType.FAILURE_TYPE.value,
            "scope_value": ftype, "metric_name": "count", "metric_value": float(count),
        })

    # V2: Aggregate dynamic metrics.
    dyn_names = _get_dynamic_metric_names(run_id)
    if dyn_names:
        all_dyn = repository.get_dynamic_metrics(run_id)
        # Build {query_id: {metric_name: value}} index.
        dyn_by_query: Dict[str, Dict[str, Any]] = defaultdict(dict)
        for dr in all_dyn:
            dyn_by_query[dr["query_id"]][dr["metric_name"]] = dr["metric_value"]

        # Overall dynamic metrics.
        for mname in dyn_names:
            vals = [dyn_by_query[qid][mname]
                    for qid in dyn_by_query
                    if mname in dyn_by_query[qid]
                    and dyn_by_query[qid][mname] is not None]
            avg_val = round(safe_div(sum(vals), len(vals)), 4) if vals else 0.0
            rows.append({
                "run_id": run_id, "scope_type": ScopeType.OVERALL.value,
                "scope_value": "all", "metric_name": mname, "metric_value": avg_val,
            })

    repository.replace_aggregates(run_id, rows)
    return rows


def overall_metrics(run_id: str) -> Dict[str, float]:
    aggs = repository.get_aggregates(run_id, ScopeType.OVERALL.value)
    return {a["metric_name"]: a["metric_value"] for a in aggs}
