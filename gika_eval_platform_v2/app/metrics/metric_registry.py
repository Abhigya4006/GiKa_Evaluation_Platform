
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.utils import round_or_none
from app.metrics import (
    document_recall,
    exact_match,
    f1,
    precision,
    recall,
    semantic_similarity,
)

# Metric names that appear in query_metrics rows and aggregated_results, in
# canonical display order. Downstream services (analytics, exports, dashboard)
# import this list to stay in sync.
V1_RETRIEVAL_METRICS = ["recall", "precision", "f1", "document_recall"]
V1_ANSWER_METRICS = ["exact_match", "semantic_similarity", "llm_judge_score"]
V1_ALL_METRICS = V1_RETRIEVAL_METRICS + V1_ANSWER_METRICS


def compute_all_metrics(
    query: Dict[str, Any],
    response: Dict[str, Any],
    *,
    generated_answer: str = "",
    judge_result: Optional[Dict[str, Any]] = None,
    em_normalize: bool = True,
) -> Dict[str, Any]:
    gt_facts = query.get("gt_supporting_facts", []) or []
    gt_docs = query.get("gt_documents", []) or []
    gt_answers: List[str] = query.get("gt_answers") or (
        [query["gt_answer"]] if query.get("gt_answer") else []
    )
    knowledge_state = response.get("knowledge_state", []) or []

    rec = recall.recall(gt_facts, knowledge_state)
    prec = precision.precision(gt_facts, knowledge_state)
    f1_val = f1.f1(prec, rec)
    doc_rec = document_recall.document_recall(gt_docs, knowledge_state)

    # EM: multi-answer aware. A hit against any acceptable answer counts.
    em = exact_match.exact_match_any(
        gt_answers, knowledge_state,
        generated_answer=generated_answer,
        normalize=em_normalize,
    )
    sem = semantic_similarity.semantic_similarity(gt_facts, knowledge_state)

    judge_score: Optional[float] = None
    judge_verdict: Optional[str] = None
    judge_rationale: Optional[str] = None
    if judge_result:
        try:
            judge_score = float(judge_result.get("score")) if judge_result.get("score") is not None else None
        except (TypeError, ValueError):
            judge_score = None
        judge_verdict = judge_result.get("verdict")
        judge_rationale = judge_result.get("rationale")

    return {
        # V1 retrieval-side
        "recall": round(rec, 4),
        "precision": round(prec, 4),
        "f1": round(f1_val, 4),
        "document_recall": round(doc_rec, 4),
        # V1 answer-side
        "exact_match": round(em, 4),
        "semantic_similarity": round_or_none(sem),
        "llm_judge_score": round_or_none(judge_score),
        "llm_judge_verdict": judge_verdict,
        "llm_judge_rationale": judge_rationale,
        # Diagnostics for the failure taxonomy / UI (not surfaced as metrics).
        "metric_details": {
            "num_retrieved_nodes": len(knowledge_state),
            "num_gt_facts": len(gt_facts),
            "num_gt_docs": len(gt_docs),
            "num_gt_answers": len(gt_answers),
            # first_relevant_rank is an internal diagnostic for the failure
            # taxonomy (LOW_RANK_RELEVANT_NODE). Not a surfaced ranking metric.
            "first_relevant_rank": _first_relevant_rank(gt_facts, gt_docs, knowledge_state),
        },
    }


def _first_relevant_rank(
    gt_facts: List[Dict[str, Any]],
    gt_docs: List[Dict[str, Any]],
    knowledge_state: List[Dict[str, Any]],
) -> Optional[int]:
    from app.metrics.matching import (
        gt_doc_index,
        gt_fact_index,
        node_relevance_flags,
    )

    gt_ids, gt_text_map = gt_fact_index(gt_facts)
    gt_doc_ids, gt_doc_names = gt_doc_index(gt_docs)
    flags = node_relevance_flags(knowledge_state, gt_ids, gt_text_map, gt_doc_ids, gt_doc_names)
    for i, rel in enumerate(flags):
        if rel:
            return i + 1
    return None
