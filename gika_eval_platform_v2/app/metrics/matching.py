
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from app.core.utils import normalize_text


def gt_fact_index(gt_facts: List[Dict[str, Any]]) -> Tuple[Set[str], Dict[str, str]]:
    ids: Set[str] = set()
    text_map: Dict[str, str] = {}
    for f in gt_facts:
        fid = f.get("fact_id")
        if fid:
            ids.add(fid)
        norm = normalize_text(f.get("text", ""))
        if norm:
            text_map[norm] = fid or norm
    return ids, text_map


def gt_doc_index(gt_docs: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str]]:
    ids = {d.get("doc_id") for d in gt_docs if d.get("doc_id")}
    names = {normalize_text(d.get("filename", "")) for d in gt_docs if d.get("filename")}
    names.discard("")
    return ids, names  # type: ignore[return-value]


def fact_is_relevant(fact: Dict[str, Any], gt_ids: Set[str], gt_text_map: Dict[str, str]) -> bool:
    fid = fact.get("fact_id")
    if fid and fid in gt_ids:
        return True
    norm = normalize_text(fact.get("text", ""))
    return bool(norm) and norm in gt_text_map


def doc_is_relevant(doc_id: Any, filename: Any, gt_ids: Set[str], gt_names: Set[str]) -> bool:
    if doc_id and doc_id in gt_ids:
        return True
    if filename:
        return normalize_text(filename) in gt_names
    return False


def matched_gt_fact_key(fact: Dict[str, Any], gt_ids: Set[str], gt_text_map: Dict[str, str]) -> str | None:
    fid = fact.get("fact_id")
    if fid and fid in gt_ids:
        return fid
    norm = normalize_text(fact.get("text", ""))
    if norm and norm in gt_text_map:
        return gt_text_map[norm]
    return None


def flatten_retrieved_facts(knowledge_state: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for node in knowledge_state:
        for f in node.get("facts", []):
            facts.append(f)
    return facts


def node_relevance_flags(
    knowledge_state: List[Dict[str, Any]],
    gt_fact_ids: Set[str],
    gt_fact_text_map: Dict[str, str],
    gt_doc_ids: Set[str],
    gt_doc_names: Set[str],
) -> List[bool]:
    flags: List[bool] = []
    for node in knowledge_state:
        has_fact = any(
            fact_is_relevant(f, gt_fact_ids, gt_fact_text_map)
            for f in node.get("facts", [])
        )
        has_doc = doc_is_relevant(
            node.get("doc_id"), node.get("filename"), gt_doc_ids, gt_doc_names
        )
        flags.append(bool(has_fact or has_doc))
    return flags
