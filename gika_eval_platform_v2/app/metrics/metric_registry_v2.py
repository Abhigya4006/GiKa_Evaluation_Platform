
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

# Metric compute function signature:
#   (query_dict, response_dict, generated_answer, judge_result, config) -> metric_value
MetricComputeFn = Callable[
    [Dict[str, Any], Dict[str, Any], str, Optional[Dict[str, Any]], Dict[str, Any]],
    Optional[float],
]


@dataclass
class MetricDefinition:
    name: str                      # internal key (e.g. "recall")
    display_name: str              # UI label (e.g. "Retrieval Recall")
    category: str                  # "retrieval" or "answer"
    required_fields: List[str]     # dataset fields needed (from capability_analyzer)
    compute: MetricComputeFn       # function that computes the metric value
    description: str = ""
    config_schema: Dict[str, Any] = field(default_factory=dict)


# Global registry.
_REGISTRY: Dict[str, MetricDefinition] = {}


def register_metric(definition: MetricDefinition) -> None:
    _REGISTRY[definition.name] = definition


def get_metric(name: str) -> Optional[MetricDefinition]:
    return _REGISTRY.get(name)


def get_all_metrics() -> List[MetricDefinition]:
    return list(_REGISTRY.values())


def get_metrics_by_category(category: str) -> List[MetricDefinition]:
    return [m for m in _REGISTRY.values() if m.category == category]


def list_metric_names() -> List[str]:
    return list(_REGISTRY.keys())


def get_available_metric_names(detected_fields: Set[str]) -> List[str]:
    available = []
    for md in _REGISTRY.values():
        if set(md.required_fields) <= detected_fields:
            available.append(md.name)
    return available


def compute_selected_metrics(
    selected_metrics: List[str],
    query: Dict[str, Any],
    response: Dict[str, Any],
    *,
    generated_answer: str = "",
    judge_result: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    available_metrics: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    cfg = config or {}

    for metric_name in selected_metrics:
        md = _REGISTRY.get(metric_name)
        if md is None:
            continue

        # Check if metric is available for this dataset.
        if available_metrics is not None and metric_name not in available_metrics:
            results[metric_name] = None
            results[f"{metric_name}_unavailable"] = True
            continue

        try:
            value = md.compute(query, response, generated_answer, judge_result, cfg)
            if value is not None:
                value = round(float(value), 4)
            results[metric_name] = value
        except Exception:  # noqa: BLE001
            results[metric_name] = None

    return results


# --------------------------------------------------------------------------- #
# Register built-in V1 metrics
# --------------------------------------------------------------------------- #

def _compute_recall(query, response, gen_answer, judge_result, config):
    from app.metrics.recall import recall
    gt_facts = query.get("gt_supporting_facts", []) or []
    ks = response.get("knowledge_state", []) or []
    return recall(gt_facts, ks)


def _compute_precision(query, response, gen_answer, judge_result, config):
    from app.metrics.precision import precision
    gt_facts = query.get("gt_supporting_facts", []) or []
    ks = response.get("knowledge_state", []) or []
    return precision(gt_facts, ks)


def _compute_f1(query, response, gen_answer, judge_result, config):
    from app.metrics.recall import recall
    from app.metrics.precision import precision
    from app.metrics.f1 import f1
    gt_facts = query.get("gt_supporting_facts", []) or []
    ks = response.get("knowledge_state", []) or []
    r = recall(gt_facts, ks)
    p = precision(gt_facts, ks)
    return f1(p, r)


def _compute_document_recall(query, response, gen_answer, judge_result, config):
    from app.metrics.document_recall import document_recall
    gt_docs = query.get("gt_documents", []) or []
    ks = response.get("knowledge_state", []) or []
    return document_recall(gt_docs, ks)


def _compute_exact_match(query, response, gen_answer, judge_result, config):
    from app.metrics.exact_match import exact_match_any
    gt_answers = query.get("gt_answers") or (
        [query["gt_answer"]] if query.get("gt_answer") else []
    )
    ks = response.get("knowledge_state", []) or []
    normalize = config.get("em_normalize", True)
    return exact_match_any(gt_answers, ks, generated_answer=gen_answer, normalize=normalize)


def _compute_semantic_similarity(query, response, gen_answer, judge_result, config):
    from app.metrics.semantic_similarity import semantic_similarity
    gt_facts = query.get("gt_supporting_facts", []) or []
    ks = response.get("knowledge_state", []) or []
    return semantic_similarity(gt_facts, ks)


def _compute_llm_judge_score(query, response, gen_answer, judge_result, config):
    if not judge_result:
        return None
    try:
        score = judge_result.get("score")
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


def _compute_token_overlap(query, response, gen_answer, judge_result, config):
    from app.core.utils import tokenize
    gt_answers = query.get("gt_answers") or (
        [query["gt_answer"]] if query.get("gt_answer") else []
    )
    if not gt_answers or not gen_answer:
        return 0.0

    best = 0.0
    gen_tokens = set(tokenize(gen_answer))
    if not gen_tokens:
        return 0.0

    for gt in gt_answers:
        gt_tokens = set(tokenize(gt))
        if not gt_tokens:
            continue
        overlap = gen_tokens & gt_tokens
        if not overlap:
            continue
        p = len(overlap) / len(gen_tokens)
        r = len(overlap) / len(gt_tokens)
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        best = max(best, f1)
    return best


# Register all built-in metrics.
_BUILTINS = [
    MetricDefinition(
        name="recall",
        display_name="Retrieval Recall",
        category="retrieval",
        required_fields=["gt_supporting_facts"],
        compute=_compute_recall,
        description="Fraction of ground-truth supporting facts retrieved.",
    ),
    MetricDefinition(
        name="precision",
        display_name="Precision",
        category="retrieval",
        required_fields=["gt_supporting_facts"],
        compute=_compute_precision,
        description="Fraction of retrieved facts that are relevant.",
    ),
    MetricDefinition(
        name="f1",
        display_name="F1 Score",
        category="retrieval",
        required_fields=["gt_supporting_facts"],
        compute=_compute_f1,
        description="Harmonic mean of precision and recall.",
    ),
    MetricDefinition(
        name="document_recall",
        display_name="Document Recall",
        category="retrieval",
        required_fields=["gt_documents"],
        compute=_compute_document_recall,
        description="Fraction of ground-truth documents retrieved.",
    ),
    MetricDefinition(
        name="exact_match",
        display_name="Exact Match",
        category="answer",
        required_fields=["gt_answer"],
        compute=_compute_exact_match,
        description="Whether the generated answer exactly matches any ground-truth answer.",
    ),
    MetricDefinition(
        name="semantic_similarity",
        display_name="Semantic Similarity",
        category="answer",
        required_fields=["gt_supporting_facts"],
        compute=_compute_semantic_similarity,
        description="Token-overlap Jaccard similarity between GT facts and retrieved content.",
    ),
    MetricDefinition(
        name="llm_judge_score",
        display_name="LLM Judge Score",
        category="answer",
        required_fields=["gt_answer"],
        compute=_compute_llm_judge_score,
        description="Score assigned by the LLM-as-Judge evaluator.",
    ),
    MetricDefinition(
        name="token_overlap",
        display_name="Token Overlap F1",
        category="answer",
        required_fields=["gt_answer"],
        compute=_compute_token_overlap,
        description="Token-level F1 overlap between generated and ground-truth answers. Example extensible metric.",
    ),
]

for _md in _BUILTINS:
    register_metric(_md)
