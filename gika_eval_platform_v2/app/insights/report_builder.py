
from __future__ import annotations

from typing import Any, Dict, List


def build_text_summary(insights: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"Evaluation Insights — run {insights.get('run_id')}")
    lines.append(f"Dataset: {insights.get('dataset_id')} | Queries: {insights.get('num_queries')}")
    lines.append("")

    strongest = insights.get("strongest_categories", [])
    if strongest:
        s = ", ".join(f"{c['category']} (F1={c['f1']:.2f})" for c in strongest)
        lines.append(f"Strongest categories: {s}")
    weakest = insights.get("weakest_categories", [])
    if weakest:
        w = ", ".join(f"{c['category']} (F1={c['f1']:.2f})" for c in weakest)
        lines.append(f"Weakest categories: {w}")

    diff = insights.get("difficulty_success_rate", {})
    if diff:
        d = ", ".join(f"{k}={v:.2f}" for k, v in sorted(diff.items()))
        lines.append(f"Success rate by difficulty: {d}")

    fc = insights.get("failure_counts", {})
    if fc:
        f = ", ".join(f"{k}={v}" for k, v in sorted(fc.items(), key=lambda kv: -kv[1]))
        lines.append(f"Failure taxonomy: {f}")

    missed = insights.get("frequently_missed_documents", [])
    if missed:
        m = ", ".join(f"{d['doc_id']} (x{d['miss_count']})" for d in missed)
        lines.append(f"Frequently missed documents: {m}")

    zero = insights.get("zero_recall_queries", [])
    if zero:
        lines.append(f"Zero-recall queries ({len(zero)}): {', '.join(zero[:10])}")

    noisy = insights.get("noisy_retrieval_queries", [])
    if noisy:
        lines.append(f"Noisy (high recall / low precision): {', '.join(noisy[:10])}")

    hard = insights.get("hard_failure_queries", [])
    if hard:
        lines.append("Top hard-failure queries:")
        for h in hard:
            lines.append(f"  - {h['query_id']}: {h['failure_type']} (F1={h.get('f1')})")

    return "\n".join(lines)
