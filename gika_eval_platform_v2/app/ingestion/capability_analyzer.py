
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from app.schemas.dataset import BenchmarkDataset


class IngestionStatus(str, Enum):
    READY = "ready"            # All fields present for full evaluation
    INCOMPLETE = "incomplete"  # Usable but some metrics unavailable
    INVALID = "invalid"        # Schema-level errors prevent use


# Canonical field keys that map to evaluation capabilities.
FIELD_QUERY_ID = "query_id"
FIELD_QUERY = "query"
FIELD_GT_ANSWER = "gt_answer"
FIELD_GT_ANSWERS = "gt_answers"
FIELD_GT_SUPPORTING_FACTS = "gt_supporting_facts"
FIELD_GT_DOCUMENTS = "gt_documents"
FIELD_DIFFICULTY = "difficulty"
FIELD_CATEGORIES = "categories"

ALL_EVAL_FIELDS = [
    FIELD_QUERY_ID, FIELD_QUERY, FIELD_GT_ANSWER, FIELD_GT_ANSWERS,
    FIELD_GT_SUPPORTING_FACTS, FIELD_GT_DOCUMENTS,
    FIELD_DIFFICULTY, FIELD_CATEGORIES,
]


@dataclass
class IngestionReport:
    status: str = IngestionStatus.READY.value
    detected_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    supported_metrics: List[str] = field(default_factory=list)
    unsupported_metrics: List[str] = field(default_factory=list)
    field_coverage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detected_fields": self.detected_fields,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "errors": self.errors,
            "supported_metrics": self.supported_metrics,
            "unsupported_metrics": self.unsupported_metrics,
            "field_coverage": self.field_coverage,
        }


def analyze_dataset(ds: BenchmarkDataset) -> IngestionReport:
    report = IngestionReport()

    if not ds.items:
        report.status = IngestionStatus.INVALID.value
        report.errors.append("Dataset contains no items.")
        return report

    # Scan all items to determine field coverage.
    has_query_ids = True
    has_queries = True
    has_gt_answer = False
    has_gt_answers = False
    has_supporting_facts = False
    has_documents = False
    has_difficulty = False
    has_categories = False

    items_missing_qid = 0
    items_missing_query = 0
    items_missing_answer = 0
    items_missing_facts = 0
    items_missing_docs = 0

    for item in ds.items:
        if not item.query_id or not item.query_id.strip():
            items_missing_qid += 1
        if not item.query or not item.query.strip():
            items_missing_query += 1
        if item.gt_answer and item.gt_answer.strip():
            has_gt_answer = True
        else:
            items_missing_answer += 1
        if item.gt_answers:
            has_gt_answers = True
        if item.gt_supporting_facts:
            has_supporting_facts = True
        else:
            items_missing_facts += 1
        if item.gt_documents:
            has_documents = True
        else:
            items_missing_docs += 1
        if item.difficulty and item.difficulty != "medium":
            has_difficulty = True
        if item.categories:
            has_categories = True

    n = len(ds.items)
    if items_missing_qid > 0:
        has_query_ids = False
    if items_missing_query > 0:
        has_queries = False

    # Record detected fields.
    detected: List[str] = []
    missing: List[str] = []

    if has_query_ids:
        detected.append(FIELD_QUERY_ID)
    else:
        report.errors.append(
            f"Query IDs are missing for {items_missing_qid}/{n} items."
        )
    if has_queries:
        detected.append(FIELD_QUERY)
    else:
        report.errors.append(
            f"Query text is missing for {items_missing_query}/{n} items."
        )

    if has_gt_answer or has_gt_answers:
        detected.append(FIELD_GT_ANSWER)
        if has_gt_answers:
            detected.append(FIELD_GT_ANSWERS)
    else:
        missing.append(FIELD_GT_ANSWER)
        report.warnings.append(
            "Ground-truth answers are missing — answer-side metrics "
            "(exact_match, semantic_similarity, llm_judge_score) cannot run."
        )

    if has_supporting_facts:
        detected.append(FIELD_GT_SUPPORTING_FACTS)
        if items_missing_facts > 0:
            report.warnings.append(
                f"Supporting facts are missing for {items_missing_facts}/{n} items. "
                "Retrieval recall will be 0 for those items."
            )
    else:
        missing.append(FIELD_GT_SUPPORTING_FACTS)
        report.warnings.append(
            "Supporting facts required for retrieval recall are unavailable."
        )

    if has_documents:
        detected.append(FIELD_GT_DOCUMENTS)
        if items_missing_docs > 0:
            report.warnings.append(
                f"Ground-truth documents are missing for {items_missing_docs}/{n} items."
            )
    else:
        missing.append(FIELD_GT_DOCUMENTS)
        report.warnings.append(
            "Ground-truth documents are unavailable — document_recall cannot run."
        )

    if has_difficulty:
        detected.append(FIELD_DIFFICULTY)
    if has_categories:
        detected.append(FIELD_CATEGORIES)

    report.detected_fields = detected
    report.missing_fields = missing

    report.field_coverage = {
        "total_items": n,
        "items_with_answer": n - items_missing_answer,
        "items_with_facts": n - items_missing_facts,
        "items_with_docs": n - items_missing_docs,
        "items_missing_qid": items_missing_qid,
    }

    # Determine supported/unsupported metrics from the metric registry.
    _classify_metrics(report, detected, missing)

    # Determine overall status.
    if report.errors:
        report.status = IngestionStatus.INVALID.value
    elif missing:
        report.status = IngestionStatus.INCOMPLETE.value
    else:
        report.status = IngestionStatus.READY.value

    return report


def _classify_metrics(
    report: IngestionReport,
    detected: List[str],
    missing: List[str],
) -> None:
    # Import here to avoid circular imports.
    from app.metrics.metric_registry_v2 import get_all_metrics

    detected_set = set(detected)
    for md in get_all_metrics():
        required = set(md.required_fields)
        if required <= detected_set:
            report.supported_metrics.append(md.name)
        else:
            report.unsupported_metrics.append(md.name)


def get_available_metrics_for_dataset(ds: BenchmarkDataset) -> Dict[str, bool]:
    report = analyze_dataset(ds)
    result: Dict[str, bool] = {}
    for m in report.supported_metrics:
        result[m] = True
    for m in report.unsupported_metrics:
        result[m] = False
    return result
