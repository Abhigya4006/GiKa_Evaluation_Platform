
from __future__ import annotations

import math
from typing import Any, Dict, List

from app.core.utils import safe_div
from app.metrics.matching import (
    gt_doc_index,
    gt_fact_index,
    node_relevance_flags,
)


def _flags(
    gt_facts: List[Dict[str, Any]],
    gt_docs: List[Dict[str, Any]],
    knowledge_state: List[Dict[str, Any]],
) -> List[bool]:
    gt_ids, gt_text_map = gt_fact_index(gt_facts)
    gt_doc_ids, gt_doc_names = gt_doc_index(gt_docs)
    return node_relevance_flags(knowledge_state, gt_ids, gt_text_map, gt_doc_ids, gt_doc_names)


def recall_at_k(flags: List[bool], k: int) -> float:
    if not flags:
        return 0.0
    return 1.0 if any(flags[:k]) else 0.0


def hit_rate(flags: List[bool]) -> float:
    return 1.0 if any(flags) else 0.0


def mrr(flags: List[bool]) -> float:
    for i, rel in enumerate(flags):
        if rel:
            return 1.0 / (i + 1)
    return 0.0


def average_precision(flags: List[bool]) -> float:
    num_relevant = sum(1 for f in flags if f)
    if num_relevant == 0:
        return 0.0
    hits = 0
    score = 0.0
    for i, rel in enumerate(flags):
        if rel:
            hits += 1
            score += hits / (i + 1)
    return safe_div(score, num_relevant)


def ndcg(flags: List[bool], k: int | None = None) -> float:
    if not flags:
        return 0.0
    cutoff = k if k is not None else len(flags)
    rels = [1.0 if f else 0.0 for f in flags[:cutoff]]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
    ideal = sorted(rels, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return safe_div(dcg, idcg)


def compute_ranking_metrics(
    gt_facts: List[Dict[str, Any]],
    gt_docs: List[Dict[str, Any]],
    knowledge_state: List[Dict[str, Any]],
    ks: List[int],
) -> Dict[str, Any]:
    flags = _flags(gt_facts, gt_docs, knowledge_state)
    result: Dict[str, Any] = {
        "flags": flags,
        "mrr": mrr(flags),
        "ndcg": ndcg(flags),
        "map_score": average_precision(flags),
        "hit_rate": hit_rate(flags),
        "recall_at_k": {},
    }
    for k in ks:
        result["recall_at_k"][k] = recall_at_k(flags, k)
    # first relevant rank (1-indexed) or None
    first = next((i + 1 for i, f in enumerate(flags) if f), None)
    result["first_relevant_rank"] = first
    return result
