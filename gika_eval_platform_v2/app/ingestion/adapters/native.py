
from __future__ import annotations

from typing import Any, Dict, List

from app.ingestion.adapters.base import BaseAdapter


class NativeAdapter(BaseAdapter):

    name = "native"

    def can_handle(self, raw: Dict[str, Any]) -> bool:
        # We recognize any dict with an ``items`` key that looks like a list of
        # query records. Deliberately permissive so the dashboard's existing
        # JSON uploads keep working unchanged.
        return isinstance(raw.get("items"), list)

    def to_internal(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "dataset_id": raw.get("dataset_id", "unknown_dataset"),
            "name": raw.get("name", raw.get("dataset_id", "Unknown")),
            "version": raw.get("version", "1.0.0"),
            "domain": raw.get("domain", "generic"),
            "source": raw.get("source", "internal-curated"),
            "metric_config": raw.get("metric_config", {}) or {},
            "leaderboard": raw.get("leaderboard", []) or [],
            "items": [],
        }
        for it in raw.get("items", []):
            if not isinstance(it, dict):
                continue
            gt_ans_raw = it.get("gt_answer", "")
            if isinstance(gt_ans_raw, list):
                gt_answers: List[str] = [str(x) for x in gt_ans_raw if x is not None]
                gt_answer_str = gt_answers[0] if gt_answers else ""
            else:
                gt_answer_str = str(gt_ans_raw or "")
                gt_answers = [gt_answer_str] if gt_answer_str else []

            # If the source also carried gt_answers explicitly, take the union.
            explicit = it.get("gt_answers")
            if isinstance(explicit, list):
                for x in explicit:
                    if x is not None and str(x) not in gt_answers:
                        gt_answers.append(str(x))

            out["items"].append({
                "query_id": it.get("query_id", ""),
                "query": it.get("query", ""),
                "gt_answer": gt_answer_str,
                "gt_answers": gt_answers,
                "categories": list(it.get("categories", []) or []),
                "difficulty": it.get("difficulty", "medium"),
                "eval_label": it.get("eval_label", "answerable"),
                "gt_supporting_facts": [
                    {
                        "fact_id": f.get("fact_id", "") or "",
                        "text": f.get("text", "") or "",
                        "doc_id": f.get("doc_id"),
                    }
                    for f in (it.get("gt_supporting_facts") or [])
                    if isinstance(f, dict)
                ],
                "gt_documents": [
                    {
                        "doc_id": d.get("doc_id", "") or "",
                        "filename": d.get("filename"),
                        "page_numbers": list(d.get("page_numbers", []) or []),
                    }
                    for d in (it.get("gt_documents") or [])
                    if isinstance(d, dict)
                ],
                "metadata": dict(it.get("metadata", {}) or {}),
            })
        return out
