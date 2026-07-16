
from __future__ import annotations

from typing import Any, Dict

from app.core.enums import FailureType, ResponseStatus


def classify(
    metrics: Dict[str, Any],
    response_status: str,
    knowledge_state_len: int,
    *,
    success_recall_threshold: float,
    success_doc_recall_threshold: float,
    low_rank_threshold: int,
) -> tuple[bool, str]:
    # Hard failures at the transport / contract level.
    if response_status in (ResponseStatus.API_ERROR.value, ResponseStatus.TIMEOUT.value):
        return False, FailureType.API_ERROR.value
    if response_status == ResponseStatus.INVALID.value:
        return False, FailureType.RESPONSE_INVALID.value

    recall = metrics.get("recall", 0.0)
    doc_recall = metrics.get("document_recall", 0.0)
    em = metrics.get("exact_match", 0.0)
    sem = metrics.get("semantic_similarity") or 0.0
    ans = metrics.get("answerability_score")
    details = metrics.get("metric_details", {})
    first_rank = details.get("first_relevant_rank")
    num_gt_facts = details.get("num_gt_facts", 0)

    # Unanswerable queries (no GT facts). Correct behavior is to abstain: the
    # answerability metric is 1.0 when nothing was retrieved, 0.0 when the system
    # hallucinated a retrieval. recall is vacuously 1.0 here so it can't be used.
    if num_gt_facts == 0:
        if ans is not None and ans >= 1.0:
            return True, FailureType.SUCCESS.value
        if knowledge_state_len == 0:
            return True, FailureType.SUCCESS.value
        return False, FailureType.IRRELEVANT_RETRIEVAL.value

    # Success rule: driven by retrieval coverage (recall + document recall),
    # NOT by Exact Match. EM here is a weak substring proxy for "answer string
    # literally present" and should not, on its own, mark a well-retrieved query
    # as a failure. exact_answer_miss is reserved for the narrow case where the
    # evidence is fully retrieved yet the answer is clearly not reflected in it
    # (low EM AND low semantic overlap).
    if recall >= success_recall_threshold and doc_recall >= success_doc_recall_threshold:
        # Coverage is fine, but if the first relevant node is ranked below the
        # low-rank threshold, that is a ranking-quality failure worth surfacing.
        if first_rank is not None and first_rank > low_rank_threshold:
            return False, FailureType.LOW_RANK_RELEVANT_NODE.value
        if num_gt_facts > 0 and recall >= 1.0 and em == 0.0 and sem < 0.2:
            return False, FailureType.EXACT_ANSWER_MISS.value
        return True, FailureType.SUCCESS.value

    # No retrieval at all.
    if knowledge_state_len == 0:
        return False, FailureType.NO_RETRIEVAL.value

    # Relevant node exists but is ranked below the low-rank threshold.
    if first_rank is not None and first_rank > low_rank_threshold:
        return False, FailureType.LOW_RANK_RELEVANT_NODE.value

    # Nothing relevant retrieved despite having nodes.
    if recall == 0.0 and doc_recall == 0.0:
        return False, FailureType.IRRELEVANT_RETRIEVAL.value

    # Some facts but the correct document was missed.
    if doc_recall == 0.0 and recall > 0.0:
        return False, FailureType.WRONG_DOCUMENT.value

    # Partial fact coverage.
    if 0.0 < recall < 1.0:
        return False, FailureType.PARTIAL_FACT_COVERAGE.value

    # Full facts but answer string not present.
    if recall >= 1.0 and em == 0.0:
        return False, FailureType.EXACT_ANSWER_MISS.value

    return False, FailureType.IRRELEVANT_RETRIEVAL.value
