
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.metrics.matching import (
    flatten_retrieved_facts,
    gt_fact_index,
    matched_gt_fact_key,
)


def answerability(
    gt_facts: List[Dict[str, Any]],
    knowledge_state: List[Dict[str, Any]],
    threshold: float = 0.5,
) -> Tuple[float, bool]:
    retrieved = flatten_retrieved_facts(knowledge_state)
    if not gt_facts:
        # Unanswerable query: correct behavior is to retrieve little/nothing.
        score = 1.0 if not retrieved else 0.0
        return score, score >= threshold

    gt_ids, gt_text_map = gt_fact_index(gt_facts)
    total = len({f.get("fact_id") or f.get("text") for f in gt_facts})
    hit = set()
    for f in retrieved:
        key = matched_gt_fact_key(f, gt_ids, gt_text_map)
        if key is not None:
            hit.add(key)
    score = (len(hit) / total) if total else 0.0
    return score, score >= threshold
