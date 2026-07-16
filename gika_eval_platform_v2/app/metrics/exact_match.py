
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.core.utils import normalize_text
from app.metrics.matching import flatten_retrieved_facts


def _normalize_answers(gt_answers: Iterable[str], normalize: bool) -> List[str]:
    out: List[str] = []
    for a in gt_answers or []:
        if a is None:
            continue
        s = normalize_text(str(a)) if normalize else str(a).strip()
        if s:
            out.append(s)
    return out


def exact_match_any(
    gt_answers: Iterable[str],
    knowledge_state: List[Dict[str, Any]],
    generated_answer: str = "",
    normalize: bool = True,
) -> float:
    normalized_gt = _normalize_answers(gt_answers, normalize)
    if not normalized_gt:
        return 0.0

    # Primary: check the generated answer.
    if generated_answer:
        gen = normalize_text(generated_answer) if normalize else generated_answer.strip()
        for gt in normalized_gt:
            if gt and gt in gen:
                return 1.0

    # Fallback: check retrieved facts (retrieval-level EM). Useful for tests
    # and for runs where the answer generator produced empty output.
    for f in flatten_retrieved_facts(knowledge_state):
        text = normalize_text(f.get("text", "")) if normalize else f.get("text", "")
        for gt in normalized_gt:
            if gt and gt in text:
                return 1.0
    return 0.0


def exact_match(
    gt_answer: str,
    knowledge_state: List[Dict[str, Any]],
    generated_answer: str = "",
    normalize: bool = True,
) -> float:
    return exact_match_any(
        [gt_answer] if gt_answer else [],
        knowledge_state,
        generated_answer=generated_answer,
        normalize=normalize,
    )
