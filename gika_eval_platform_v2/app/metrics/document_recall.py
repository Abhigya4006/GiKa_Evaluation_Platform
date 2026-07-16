
from __future__ import annotations

from typing import Any, Dict, List

from app.core.utils import normalize_text, safe_div
from app.metrics.matching import gt_doc_index


def document_recall(gt_docs: List[Dict[str, Any]], knowledge_state: List[Dict[str, Any]]) -> float:
    if not gt_docs:
        return 1.0
    gt_ids, gt_names = gt_doc_index(gt_docs)
    total = len({d.get("doc_id") for d in gt_docs if d.get("doc_id")}) or len(gt_docs)
    hit = set()
    for node in knowledge_state:
        did = node.get("doc_id")
        fname = node.get("filename")
        if did and did in gt_ids:
            hit.add(did)
        elif fname and normalize_text(fname) in gt_names:
            hit.add(normalize_text(fname))
    return safe_div(len(hit), total)
