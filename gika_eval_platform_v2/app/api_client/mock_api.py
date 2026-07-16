
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from app.db import repository

# Distractor documents used to simulate wrong-document retrieval. Deliberately
# generic-sounding so they look plausible across benchmarks (MuSiQue's fake
# wiki-style docs, ACME's policy PDFs, etc.).
_DISTRACTOR_DOCS = [
    ("doc_unrelated_policy", "Unrelated Policy Handbook"),
    ("doc_press_release", "Press Release 2023"),
    ("doc_random_annex", "Miscellaneous Annex Z"),
]


def _seed(query_id: str) -> int:
    return int(hashlib.sha256(query_id.encode("utf-8")).hexdigest(), 16)


def _outcome(query_id: str, difficulty: str) -> str:
    bucket = _seed(query_id) % 10
    if difficulty == "easy":
        return "perfect" if bucket < 9 else "partial"
    if difficulty == "medium":
        if bucket < 6:
            return "perfect"
        if bucket < 8:
            return "partial"
        return "low_rank"
    # hard
    if bucket < 2:
        return "perfect"
    if bucket < 4:
        return "partial"
    if bucket < 6:
        return "wrong_document"
    if bucket < 8:
        return "low_rank"
    return "miss"


def _node(rank: int, node_id: str, label: str, score: float, doc_id, filename,
          pages: List[int], facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "rank": rank,
        "from_node_id": node_id,
        "from_label": label,
        "node_score": round(score, 3),
        "doc_id": doc_id,
        "filename": filename,
        "page_numbers": pages,
        "facts": facts,
    }


def build_response(
    query_id: str,
    max_nodes: int = 10,
    dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    start = time.time()
    q = repository.get_query(query_id)
    if q is None:
        return _finalize(query_id, [], answerable=False, start=start, confidence=0.0)

    gt_facts = q.get("gt_supporting_facts", [])
    gt_docs = q.get("gt_documents", [])
    difficulty = q.get("difficulty", "medium")
    eval_label = q.get("eval_label", "answerable")

    # Unanswerable queries: sometimes correctly abstain, sometimes over-retrieve
    # a distractor (to exercise irrelevant_retrieval).
    if eval_label == "unanswerable" or not gt_facts:
        if _seed(query_id) % 2 == 0:
            nodes: List[Dict[str, Any]] = []
            answerable = False
            confidence = 0.9  # confidently abstains
        else:
            did, fn = _DISTRACTOR_DOCS[_seed(query_id) % len(_DISTRACTOR_DOCS)]
            nodes = [_node(1, "cluster_distractor", "Unrelated", 0.42, did, fn, [1],
                           [{"fact_id": None, "text": "This content is unrelated to the query."}])]
            answerable = False
            confidence = 0.3
        return _finalize(query_id, nodes[:max_nodes], answerable, start, confidence)

    outcome = _outcome(query_id, difficulty)
    primary_doc = gt_docs[0] if gt_docs else {"doc_id": None, "filename": None, "page_numbers": []}
    gt_fact_dicts = [{"fact_id": f.get("fact_id"), "text": f.get("text", "")} for f in gt_facts]

    nodes = []
    answerable = True
    confidence = 0.7

    if outcome == "perfect":
        confidence = 0.95
        nodes.append(_node(
            1, "cluster_primary", (q.get("query_text", "") or "")[:24] or "Node", 0.95,
            primary_doc.get("doc_id"), primary_doc.get("filename"),
            primary_doc.get("page_numbers", []),
            gt_fact_dicts + [{"fact_id": None, "text": "Supplementary context detail."}],
        ))

    elif outcome == "partial":
        confidence = 0.7
        nodes.append(_node(
            1, "cluster_primary", "Partial", 0.88,
            primary_doc.get("doc_id"), primary_doc.get("filename"),
            primary_doc.get("page_numbers", []),
            gt_fact_dicts[:1] + [{"fact_id": None, "text": "Loosely related statement."}],
        ))

    elif outcome == "wrong_document":
        confidence = 0.55
        did, fn = _DISTRACTOR_DOCS[_seed(query_id) % len(_DISTRACTOR_DOCS)]
        nodes.append(_node(
            1, "cluster_wrongdoc", "WrongDoc", 0.80, did, fn, [2],
            [{"fact_id": None, "text": gt_fact_dicts[0]["text"] if gt_fact_dicts else "n/a"}],
        ))
        answerable = True

    elif outcome == "low_rank":
        confidence = 0.45
        for i in range(3):
            did, fn = _DISTRACTOR_DOCS[(_seed(query_id) + i) % len(_DISTRACTOR_DOCS)]
            nodes.append(_node(
                i + 1, f"cluster_distract_{i}", "Distract", 0.7 - 0.1 * i, did, fn, [i + 1],
                [{"fact_id": None, "text": "Off-topic content."}],
            ))
        nodes.append(_node(
            4, "cluster_primary", "Correct-LowRank", 0.52,
            primary_doc.get("doc_id"), primary_doc.get("filename"),
            primary_doc.get("page_numbers", []),
            gt_fact_dicts,
        ))

    else:  # miss
        confidence = 0.2
        did, fn = _DISTRACTOR_DOCS[_seed(query_id) % len(_DISTRACTOR_DOCS)]
        nodes.append(_node(
            1, "cluster_miss", "Miss", 0.5, did, fn, [3],
            [{"fact_id": None, "text": "Completely unrelated content."}],
        ))
        answerable = False

    nodes = nodes[:max(1, int(max_nodes))]
    return _finalize(query_id, nodes, answerable, start, confidence)


def _finalize(
    query_id: str,
    nodes: List[Dict[str, Any]],
    answerable: bool,
    start: float,
    confidence: float,
) -> Dict[str, Any]:
    elapsed_ms = max(1, int((time.time() - start) * 1000))
    # Deterministic pseudo-latency so stored fields are stable across runs.
    pseudo_ms = 100 + (_seed(query_id) % 120)
    ret_ms = pseudo_ms or elapsed_ms
    return {
        "query_id": query_id,
        "knowledge_state": nodes,
        "confidence": round(confidence, 3),
        "exploration_time": round(ret_ms / 1000.0, 3),  # V1 field, in seconds
        "answerable": answerable,
        "retrieval_time_ms": ret_ms,
        "retrieval_strategy": "hybrid_graph_vector",
    }


# --------------------------------------------------------------------------- #
# Optional FastAPI app (used when FastAPI is installed).
# --------------------------------------------------------------------------- #

def _build_fastapi_app():
    from fastapi import FastAPI  # local import so module works without FastAPI
    from app.schemas.api_contract import RetrieveRequest, RetrieveResponse

    api = FastAPI(title="GIKA Mock Retrieval API (V1)", version="1.0.0")

    @api.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @api.post("/retrieve", response_model=RetrieveResponse)
    def retrieve(req: RetrieveRequest) -> Dict[str, Any]:
        return build_response(req.query_id, dataset_id=req.dataset_id)

    return api


try:  # pragma: no cover - only when FastAPI present
    app = _build_fastapi_app()
except Exception:  # noqa: BLE001
    app = None  # offline: use scripts/run_mock_api.py stdlib server instead
