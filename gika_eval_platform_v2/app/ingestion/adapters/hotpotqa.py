
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.ingestion.adapters.base import BaseAdapter


# Keys that signal a HotpotQA-style example when present together.
_HOTPOT_REQUIRED = {"question", "answer"}
_HOTPOT_OPTIONAL = {"supporting_facts", "context", "type", "level", "_id"}

# Keys commonly used to wrap examples in an object envelope.
_WRAPPER_KEYS = ("data", "examples", "items", "questions", "rows")


def _unwrap_list(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in _WRAPPER_KEYS:
            candidate = raw.get(key)
            if isinstance(candidate, list) and len(candidate) > 0:
                return candidate
    return None


def _looks_like_hotpot_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    keys = set(item.keys())
    # Must have both "question" and "answer".
    if not _HOTPOT_REQUIRED.issubset(keys):
        return False
    # And at least one HotpotQA-specific optional field to distinguish from
    # other QA formats that happen to have question + answer.
    return bool(keys & _HOTPOT_OPTIONAL)


def _slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_").lower()


class HotpotQAAdapter(BaseAdapter):

    name = "hotpotqa"

    # ------------------------------------------------------------------ #
    # Shape detection
    # ------------------------------------------------------------------ #

    def can_handle(self, raw: Any) -> bool:
        items = _unwrap_list(raw)
        if not items:
            return False
        sample = items[:5]
        return any(_looks_like_hotpot_item(it) for it in sample)

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #

    def to_internal(self, raw: Any) -> Dict[str, Any]:
        items_raw = _unwrap_list(raw)
        if items_raw is None:
            items_raw = []

        # Attempt to extract a dataset-level metadata envelope.
        meta: Dict[str, Any] = {}
        if isinstance(raw, dict):
            meta = {k: v for k, v in raw.items()
                    if k not in set(_WRAPPER_KEYS) and not isinstance(v, list)}

        dataset_id = self._dataset_id(meta)
        name = str(meta.get("name") or meta.get("dataset_name") or dataset_id)

        items: List[Dict[str, Any]] = []
        for idx, it in enumerate(items_raw):
            if not isinstance(it, dict):
                continue
            if not it.get("question"):
                continue
            items.append(self._adapt_item(it, idx))

        return {
            "dataset_id": dataset_id,
            "name": name,
            "version": str(meta.get("version") or "1.0.0"),
            "domain": "open-domain-qa",
            "source": "hotpotqa",
            "metric_config": {},
            "leaderboard": [],
            "items": items,
        }

    # ------------------------------------------------------------------ #
    # Per-item mapping
    # ------------------------------------------------------------------ #

    def _adapt_item(self, it: Dict[str, Any], idx: int) -> Dict[str, Any]:
        query_id = str(it.get("_id") or it.get("id") or f"hotpot_{idx:06d}")
        question = str(it.get("question") or "")
        answer = str(it.get("answer") or "")
        gt_answers = [answer] if answer else []

        # Build a context lookup: title -> [sentence_0, sentence_1, ...].
        context_map = self._build_context_map(it.get("context"))

        # Resolve supporting_facts into gt_supporting_facts.
        raw_sf = it.get("supporting_facts") or []
        gt_facts = self._resolve_supporting_facts(raw_sf, context_map)

        # GT documents: deduplicated titles from supporting_facts.
        gt_documents = self._build_documents(gt_facts)

        # Category / difficulty from HotpotQA's type / level fields.
        q_type = str(it.get("type") or "unknown").strip().lower()
        level = str(it.get("level") or "medium").strip().lower()
        if level not in ("easy", "medium", "hard"):
            level = "medium"
        categories = [q_type] if q_type else ["unknown"]

        return {
            "query_id": query_id,
            "query": question,
            "gt_answer": answer,
            "gt_answers": gt_answers,
            "categories": categories,
            "difficulty": level,
            "eval_label": "answerable",
            "gt_supporting_facts": gt_facts,
            "gt_documents": gt_documents,
            "metadata": {
                "source_dataset_type": "hotpotqa",
                "question_type": q_type,
                "original_raw_item": dict(it),
            },
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dataset_id(meta: Dict[str, Any]) -> str:
        for key in ("dataset_id", "name", "dataset_name"):
            v = meta.get(key)
            if v and isinstance(v, str):
                slug = _slugify(v)
                if slug:
                    return slug
        return "hotpotqa_dataset"

    @staticmethod
    def _build_context_map(
        context: Any,
    ) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {}
        if not isinstance(context, list):
            return mapping
        for entry in context:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            title = str(entry[0])
            sentences = entry[1]
            if isinstance(sentences, list):
                mapping[title] = [str(s) for s in sentences]
            elif isinstance(sentences, str):
                # Some preprocessed variants flatten sentences into one string.
                mapping[title] = [sentences]
        return mapping

    @staticmethod
    def _resolve_supporting_facts(
        raw_sf: List[Any],
        context_map: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        seen: set = set()
        for entry in raw_sf:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            title = str(entry[0])
            try:
                sent_idx = int(entry[1])
            except (TypeError, ValueError):
                sent_idx = 0

            fact_id = f"{_slugify(title)}__{sent_idx}"
            if fact_id in seen:
                continue
            seen.add(fact_id)

            # Look up actual sentence text from context.
            text = ""
            sentences = context_map.get(title)
            if sentences and 0 <= sent_idx < len(sentences):
                text = sentences[sent_idx]

            facts.append({
                "fact_id": fact_id,
                "text": text,
                "doc_id": title,
            })
        return facts

    @staticmethod
    def _build_documents(
        gt_facts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for fact in gt_facts:
            did = fact.get("doc_id") or ""
            if not did or did in seen:
                continue
            seen[did] = {
                "doc_id": did,
                "filename": did,  # Use the Wikipedia title as the filename.
                "page_numbers": [],
            }
        return list(seen.values())
