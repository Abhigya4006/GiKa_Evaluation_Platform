
from __future__ import annotations

from typing import Any, Dict

from app.core.enums import ResponseStatus
from app.schemas.api_contract import RetrieveResponse


def normalize_response(raw: Dict[str, Any], query_id: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty(query_id)

    ks = raw.get("knowledge_state", [])
    fixed_nodes = []
    for i, node in enumerate(ks or []):
        if not isinstance(node, dict):
            continue
        facts = node.get("facts", [])
        norm_facts = []
        for f in facts:
            if isinstance(f, str):
                norm_facts.append({"fact_id": None, "text": f})
            elif isinstance(f, dict):
                norm_facts.append({"fact_id": f.get("fact_id"), "text": f.get("text", "")})
        node = dict(node)
        node["facts"] = norm_facts
        node.setdefault("rank", i + 1)
        fixed_nodes.append(node)

    payload = {
        "query_id": raw.get("query_id", query_id),
        "knowledge_state": fixed_nodes,
        "answerable": bool(raw.get("answerable", False)),
        "retrieval_time_ms": int(raw.get("retrieval_time_ms", 0) or 0),
        "retrieval_strategy": raw.get("retrieval_strategy", "unknown"),
    }
    validated = RetrieveResponse.model_validate(payload)
    return validated.model_dump()


def validate_status(raw: Dict[str, Any], transport_status: str) -> str:
    if transport_status != ResponseStatus.OK.value:
        return transport_status
    if not isinstance(raw, dict) or "knowledge_state" not in raw:
        return ResponseStatus.INVALID.value
    return ResponseStatus.OK.value


def _empty(query_id: str) -> Dict[str, Any]:
    return {
        "query_id": query_id,
        "knowledge_state": [],
        "answerable": False,
        "retrieval_time_ms": 0,
        "retrieval_strategy": "unknown",
    }
