
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

from app.core.enums import ScopeType
from app.db import repository


def _worst_by(metrics: List[Dict[str, Any]], key: str, n: int) -> List[Dict[str, Any]]:
    ordered = sorted(metrics, key=lambda m: (m.get(key) if m.get(key) is not None else 0.0))
    return [{"query_id": m["query_id"], key: m.get(key), "failure_type": m.get("failure_type")}
            for m in ordered[:n]]


def _best_by(metrics: List[Dict[str, Any]], key: str, n: int) -> List[Dict[str, Any]]:
    ordered = sorted(metrics, key=lambda m: (m.get(key) if m.get(key) is not None else 0.0), reverse=True)
    return [{"query_id": m["query_id"], key: m.get(key)} for m in ordered[:n]]


def generate_insights(run_id: str, dataset_id: str, top_n: int = 5) -> Dict[str, Any]:
    metrics = repository.get_query_metrics(run_id)
    queries = {q["query_id"]: q for q in repository.get_queries(dataset_id)}

    # Category-level average f1 (strongest/weakest categories).
    cat_agg = repository.get_aggregates(run_id, ScopeType.CATEGORY.value)
    cat_f1: Dict[str, float] = {}
    for a in cat_agg:
        if a["metric_name"] == "f1":
            cat_f1[a["scope_value"]] = a["metric_value"]
    strongest = sorted(cat_f1.items(), key=lambda kv: kv[1], reverse=True)[:3]
    weakest = sorted(cat_f1.items(), key=lambda kv: kv[1])[:3]

    # Zero-recall queries.
    zero_recall = [m["query_id"] for m in metrics if m.get("recall", 0.0) == 0.0
                   and queries.get(m["query_id"], {}).get("gt_supporting_facts")]

    # Low precision but high recall (noisy retrieval).
    noisy = [m["query_id"] for m in metrics
             if m.get("recall", 0.0) >= 0.8 and m.get("precision", 1.0) <= 0.4]

    # Frequently missed documents: GT docs whose queries had doc_recall < 1.
    missed_docs: Counter = Counter()
    for m in metrics:
        if m.get("document_recall", 1.0) < 1.0:
            for d in queries.get(m["query_id"], {}).get("gt_documents", []):
                if d.get("doc_id"):
                    missed_docs[d["doc_id"]] += 1

    # Failure type counts.
    failure_counts = dict(Counter(m.get("failure_type", "success") for m in metrics))

    # Hard-failure queries (not success and low f1).
    hard_failures = [
        {"query_id": m["query_id"], "failure_type": m["failure_type"],
         "f1": m.get("f1"), "recall": m.get("recall")}
        for m in sorted(metrics, key=lambda x: x.get("f1", 0.0))
        if not m.get("success")
    ][:top_n]

    # Difficulty-level success rate.
    diff_agg = repository.get_aggregates(run_id, ScopeType.DIFFICULTY.value)
    diff_success = {a["scope_value"]: a["metric_value"] for a in diff_agg
                    if a["metric_name"] == "success_rate"}

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "num_queries": len(metrics),
        "strongest_categories": [{"category": c, "f1": v} for c, v in strongest],
        "weakest_categories": [{"category": c, "f1": v} for c, v in weakest],
        "zero_recall_queries": zero_recall,
        "noisy_retrieval_queries": noisy,
        "frequently_missed_documents": [
            {"doc_id": d, "miss_count": c} for d, c in missed_docs.most_common(5)
        ],
        "failure_counts": failure_counts,
        "hard_failure_queries": hard_failures,
        "difficulty_success_rate": diff_success,
        "worst_queries_by_f1": _worst_by(metrics, "f1", top_n),
        "best_queries_by_f1": _best_by(metrics, "f1", top_n),
    }
