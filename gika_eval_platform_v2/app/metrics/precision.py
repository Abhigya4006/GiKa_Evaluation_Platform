
from __future__ import annotations

from typing import Any, Dict, List

from app.core.utils import safe_div
from app.metrics.matching import fact_is_relevant, flatten_retrieved_facts, gt_fact_index


def precision(gt_facts: List[Dict[str, Any]], knowledge_state: List[Dict[str, Any]]) -> float:
    retrieved = flatten_retrieved_facts(knowledge_state)
    if not retrieved:
        return 0.0
    if not gt_facts:
        # Nothing was relevant to retrieve; any retrieval is noise.
        return 0.0
    gt_ids, gt_text_map = gt_fact_index(gt_facts)
    relevant = sum(1 for f in retrieved if fact_is_relevant(f, gt_ids, gt_text_map))
    return safe_div(relevant, len(retrieved))
