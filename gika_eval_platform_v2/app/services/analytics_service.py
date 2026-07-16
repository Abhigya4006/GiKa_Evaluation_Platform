
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.enums import ScopeType
from app.db import repository
from app.evaluation.response_store import load_response


def run_summary(run_id: str) -> Dict[str, Any]:
    run = repository.get_run(run_id) or {}
    overall = {a["metric_name"]: a["metric_value"]
               for a in repository.get_aggregates(run_id, ScopeType.OVERALL.value)}
    failure_counts = {a["scope_value"]: int(a["metric_value"])
                      for a in repository.get_aggregates(run_id, ScopeType.FAILURE_TYPE.value)}
    return {
        "run": run,
        "overall": overall,
        "success_rate": overall.get("success_rate", 0.0),
        "failure_counts": failure_counts,
    }


def scope_table(run_id: str, scope_type: str) -> List[Dict[str, Any]]:
    aggs = repository.get_aggregates(run_id, scope_type)
    pivot: Dict[str, Dict[str, Any]] = {}
    for a in aggs:
        pivot.setdefault(a["scope_value"], {"scope_value": a["scope_value"]})
        pivot[a["scope_value"]][a["metric_name"]] = a["metric_value"]
    return list(pivot.values())


def query_rows(run_id: str, dataset_id: str) -> List[Dict[str, Any]]:
    metrics = {m["query_id"]: m for m in repository.get_query_metrics(run_id)}
    rows: List[Dict[str, Any]] = []
    for q in repository.get_queries(dataset_id):
        m = metrics.get(q["query_id"], {})
        rows.append({
            "query_id": q["query_id"],
            "difficulty": q.get("difficulty"),
            "categories": q.get("categories", []),
            "eval_label": q.get("eval_label"),
            # V1 retrieval-side.
            "recall": m.get("recall"),
            "precision": m.get("precision"),
            "f1": m.get("f1"),
            "document_recall": m.get("document_recall"),
            # V1 answer-side.
            "exact_match": m.get("exact_match"),
            "semantic_similarity": m.get("semantic_similarity"),
            "llm_judge_score": m.get("llm_judge_score"),
            # Classification.
            "success": m.get("success"),
            "failure_type": m.get("failure_type"),
        })
    return rows


def query_detail(run_id: str, query_id: str) -> Dict[str, Any]:
    q = repository.get_query(query_id) or {}
    m = repository.get_query_metric(run_id, query_id) or {}
    raw = load_response(run_id, query_id) or {}
    return {
        "query": q,
        "metrics": m,
        "raw_response": raw,
    }


def compare_runs(run_id_a: str, run_id_b: str) -> List[Dict[str, Any]]:
    a = {x["metric_name"]: x["metric_value"]
         for x in repository.get_aggregates(run_id_a, ScopeType.OVERALL.value)}
    b = {x["metric_name"]: x["metric_value"]
         for x in repository.get_aggregates(run_id_b, ScopeType.OVERALL.value)}
    metrics = sorted(set(a) | set(b))
    rows = []
    for name in metrics:
        va, vb = a.get(name), b.get(name)
        delta = (vb - va) if (va is not None and vb is not None) else None
        rows.append({"metric": name, "run_a": va, "run_b": vb, "delta": delta})
    return rows


def compare_runs_per_query(run_id_a: str, run_id_b: str) -> List[Dict[str, Any]]:
    ma = {m["query_id"]: m for m in repository.get_query_metrics(run_id_a)}
    mb = {m["query_id"]: m for m in repository.get_query_metrics(run_id_b)}
    all_qids = sorted(set(ma.keys()) | set(mb.keys()))
    compare_keys = ["recall", "precision", "f1", "document_recall",
                    "exact_match", "semantic_similarity", "llm_judge_score"]
    rows = []
    for qid in all_qids:
        row: Dict[str, Any] = {"query_id": qid}
        a = ma.get(qid, {})
        b = mb.get(qid, {})
        for k in compare_keys:
            va = a.get(k)
            vb = b.get(k)
            row[f"{k}_a"] = va
            row[f"{k}_b"] = vb
            if va is not None and vb is not None:
                row[f"{k}_delta"] = round(vb - va, 4)
            else:
                row[f"{k}_delta"] = None
        rows.append(row)
    return rows


def comparison_group_summary(group_id: str) -> List[Dict[str, Any]]:
    runs = repository.get_runs_by_comparison_group(group_id)
    summaries = []
    for r in runs:
        overall = {a["metric_name"]: a["metric_value"]
                   for a in repository.get_aggregates(r["run_id"], ScopeType.OVERALL.value)}
        summaries.append({
            "run_id": r["run_id"],
            "run_name": r.get("run_name", ""),
            "provider": r.get("provider", ""),
            "api_endpoint": r.get("api_endpoint", ""),
            "status": r.get("status", ""),
            **overall,
        })
    return summaries


def document_analysis(run_id: str, dataset_id: str) -> Dict[str, Any]:
    metrics = {m["query_id"]: m for m in repository.get_query_metrics(run_id)}
    retrieved: Dict[str, int] = {}
    missed: Dict[str, int] = {}
    failure_linked: Dict[str, int] = {}
    for q in repository.get_queries(dataset_id):
        m = metrics.get(q["query_id"], {})
        doc_recall = m.get("document_recall", 0.0)
        for d in q.get("gt_documents", []):
            did = d.get("doc_id")
            if not did:
                continue
            if doc_recall and doc_recall >= 1.0:
                retrieved[did] = retrieved.get(did, 0) + 1
            else:
                missed[did] = missed.get(did, 0) + 1
            if not m.get("success", False):
                failure_linked[did] = failure_linked.get(did, 0) + 1
    return {
        "most_retrieved": sorted(retrieved.items(), key=lambda kv: -kv[1]),
        "most_missed": sorted(missed.items(), key=lambda kv: -kv[1]),
        "failure_linked": sorted(failure_linked.items(), key=lambda kv: -kv[1]),
    }
