
from __future__ import annotations

from typing import Any, Dict, List

from app.core.utils import safe_div
from app.metrics.matching import (
    flatten_retrieved_facts,
    gt_fact_index,
    matched_gt_fact_key,
)


def recall(gt_facts: List[Dict[str, Any]], knowledge_state: List[Dict[str, Any]]) -> float:
    if not gt_facts:
        # No GT facts to retrieve -> vacuously perfect coverage.
        return 1.0
    gt_ids, gt_text_map = gt_fact_index(gt_facts)
    total_gt = len({f.get("fact_id") or f.get("text") for f in gt_facts})
    hit_keys = set()
    for f in flatten_retrieved_facts(knowledge_state):
        key = matched_gt_fact_key(f, gt_ids, gt_text_map)
        if key is not None:
            hit_keys.add(key)
    return safe_div(len(hit_keys), total_gt)
