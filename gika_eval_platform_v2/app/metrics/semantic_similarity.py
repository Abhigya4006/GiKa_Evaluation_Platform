
from __future__ import annotations

from typing import Any, Dict, List

from app.core.utils import jaccard, tokenize
from app.metrics.matching import flatten_retrieved_facts


def semantic_similarity(
    gt_facts: List[Dict[str, Any]],
    knowledge_state: List[Dict[str, Any]],
) -> float:
    retrieved = flatten_retrieved_facts(knowledge_state)
    if not gt_facts or not retrieved:
        return 0.0
    gt_tokens = [tokenize(f.get("text", "")) for f in gt_facts]
    best = 0.0
    for rf in retrieved:
        rt = tokenize(rf.get("text", ""))
        for gt in gt_tokens:
            best = max(best, jaccard(rt, gt))
    return best
