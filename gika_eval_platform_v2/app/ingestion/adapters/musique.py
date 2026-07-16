
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.ingestion.adapters.base import BaseAdapter

_HOP_PREFIX_RE = re.compile(r"^(?P<hop>\d+)hop(?P<variant>\d*)__")


def _parse_hop_count(question_id: str) -> Optional[int]:
    m = _HOP_PREFIX_RE.match(question_id or "")
    if not m:
        return None
    try:
        return int(m.group("hop"))
    except ValueError:  # pragma: no cover - regex forbids
        return None


def _hop_type(question_id: str) -> str:
    m = _HOP_PREFIX_RE.match(question_id or "")
    if not m:
        return "unknown_hop"
    variant = m.group("variant") or ""
    return f"{m.group('hop')}hop{variant}"


def _difficulty_from_hops(hop_count: Optional[int]) -> str:
    if hop_count is None:
        return "medium"
    if hop_count <= 2:
        return "easy"
    if hop_count == 3:
        return "medium"
    return "hard"


class MusiqueAdapter(BaseAdapter):

    name = "musique"

    def can_handle(self, raw: Dict[str, Any]) -> bool:
        # We require both ``questions`` (dict) and ``chunks`` (dict) at the top
        # level. ``metadata`` is a nice-to-have but we don't insist on it.
        return (
            isinstance(raw.get("questions"), dict)
            and isinstance(raw.get("chunks"), dict)
            and "items" not in raw  # native shape wins if both apply
        )

    def to_internal(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        meta = raw.get("metadata") or {}
        chunks = raw.get("chunks") or {}
        questions = raw.get("questions") or {}

        dataset_id = self._dataset_id(meta)
        name = str(meta.get("entity_name") or dataset_id)

        items: List[Dict[str, Any]] = []
        for qid, q in questions.items():
            if not isinstance(q, dict):
                continue
            items.append(self._adapt_question(qid, q, chunks))

        return {
            "dataset_id": dataset_id,
            "name": name,
            "version": str(meta.get("version") or "1.0.0"),
            "domain": "open-domain-qa",
            "source": "musique",
            "metric_config": {},
            "leaderboard": [],
            "items": items,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dataset_id(meta: Dict[str, Any]) -> str:
        for key in ("entity_id", "dataset_id", "name"):
            v = meta.get(key)
            if v:
                # Slugify: replace non [a-zA-Z0-9_] with underscore.
                slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(v)).strip("_").lower()
                if slug:
                    return slug
        return "musique_dataset"

    def _adapt_question(
        self,
        qid: str,
        q: Dict[str, Any],
        chunks: Dict[str, Any],
    ) -> Dict[str, Any]:
        # gt_answer may be a list (MuSiQue) or a string (fallback).
        raw_gt = q.get("gt_answer")
        if isinstance(raw_gt, list):
            gt_answers = [str(x) for x in raw_gt if x is not None]
        elif raw_gt is None:
            gt_answers = []
        else:
            gt_answers = [str(raw_gt)]
        gt_answer_str = gt_answers[0] if gt_answers else ""

        gt_chunks = q.get("gt_chunks") or {}
        chunk_ids = list(gt_chunks.keys()) if isinstance(gt_chunks, dict) else []

        gt_facts = self._build_facts(chunk_ids, chunks)
        gt_documents = self._build_documents(gt_facts, chunk_ids, chunks)

        hop_count = _parse_hop_count(qid)
        categories = [_hop_type(qid)]

        return {
            "query_id": str(q.get("question_id") or qid),
            "query": str(q.get("question") or ""),
            "gt_answer": gt_answer_str,
            "gt_answers": gt_answers,
            "categories": categories,
            "difficulty": _difficulty_from_hops(hop_count),
            "eval_label": "answerable",  # MuSiQue queries are all answerable.
            "gt_supporting_facts": gt_facts,
            "gt_documents": gt_documents,
            "metadata": {
                "source_dataset_type": "musique",
                "hop_count": hop_count,
                "hop_type": categories[0],
                "reasoning_steps": list(q.get("reasoning_steps") or []),
                "original_raw_item": dict(q),
            },
        }

    @staticmethod
    def _build_facts(chunk_ids: List[str], chunks: Dict[str, Any]) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        for cid in chunk_ids:
            ch = chunks.get(cid) if isinstance(chunks.get(cid), dict) else {}
            ch_meta = ch.get("metadata") or {}
            doc_id = ch_meta.get("doc_id") or cid  # MuSiQue: doc_id == chunk_id
            facts.append({
                "fact_id": cid,
                "text": ch.get("text", "") or "",
                "doc_id": str(doc_id) if doc_id is not None else None,
            })
        return facts

    @staticmethod
    def _build_documents(
        gt_facts: List[Dict[str, Any]],
        chunk_ids: List[str],
        chunks: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for cid, fact in zip(chunk_ids, gt_facts):
            did = fact.get("doc_id") or cid
            if did in seen:
                continue
            ch = chunks.get(cid) if isinstance(chunks.get(cid), dict) else {}
            ch_meta = ch.get("metadata") or {}
            filename = ch_meta.get("title") or ch_meta.get("filename") or None
            seen[did] = {
                "doc_id": did,
                "filename": str(filename) if filename else None,
                "page_numbers": [],
            }
        return list(seen.values())
