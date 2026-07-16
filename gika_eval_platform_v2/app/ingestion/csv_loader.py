
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from app.schemas.dataset import BenchmarkDataset


# --------------------------------------------------------------------------- #
# Mapping
# --------------------------------------------------------------------------- #

@dataclass
class CSVMapping:

    query_id: str = "query_id"
    query: str = "query"
    gt_answer: str = "gt_answer"
    categories: str = "categories"
    difficulty: str = "difficulty"
    eval_label: str = "eval_label"

    # Facts — either one JSON-encoded cell OR a per-row (fact_id, fact_text, fact_doc_id).
    gt_supporting_facts: str = "gt_supporting_facts"  # JSON list, layout A
    fact_id: str = "fact_id"                          # layout B
    fact_text: str = "fact_text"                      # layout B
    fact_doc_id: str = "fact_doc_id"                  # layout B

    # Documents — either one JSON-encoded cell OR a per-row (doc_id, filename, pages).
    gt_documents: str = "gt_documents"                # JSON list, layout A
    doc_id: str = "doc_id"                            # layout B
    filename: str = "filename"                        # layout B
    page_numbers: str = "page_numbers"                # comma-separated or JSON

    #: Delimiter used inside string cells (categories, page_numbers).
    list_delimiter: str = ","

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CSVMapping":
        data = data or {}
        # Only apply known keys to avoid typo-silent-drops.
        allowed = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in allowed and v}
        return cls(**kwargs)


# --------------------------------------------------------------------------- #
# Cell parsing helpers
# --------------------------------------------------------------------------- #

def _clean(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _try_json(s: str) -> Optional[Any]:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def _parse_list_cell(cell: str, delimiter: str) -> List[str]:
    if not cell:
        return []
    parsed = _try_json(cell)
    if isinstance(parsed, list):
        return [str(x).strip() for x in parsed if _clean(x)]
    return [p.strip() for p in cell.split(delimiter) if p.strip()]


def _parse_pages_cell(cell: str, delimiter: str) -> List[int]:
    parsed = _try_json(cell)
    if isinstance(parsed, list):
        out: List[int] = []
        for x in parsed:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    if not cell:
        return []
    out = []
    for p in cell.split(delimiter):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError:
            continue
    return out


def _parse_facts_cell(cell: str) -> List[Dict[str, Any]]:
    parsed = _try_json(cell)
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, entry in enumerate(parsed):
        if isinstance(entry, str):
            out.append({"fact_id": f"f_{i+1:03d}", "text": entry, "doc_id": None})
        elif isinstance(entry, dict):
            out.append({
                "fact_id": entry.get("fact_id") or f"f_{i+1:03d}",
                "text": entry.get("text", ""),
                "doc_id": entry.get("doc_id"),
            })
    return out


def _parse_docs_cell(cell: str, delimiter: str) -> List[Dict[str, Any]]:
    parsed = _try_json(cell)
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, entry in enumerate(parsed):
        if isinstance(entry, str):
            out.append({"doc_id": entry, "filename": None, "page_numbers": []})
        elif isinstance(entry, dict):
            pages = entry.get("page_numbers", [])
            if isinstance(pages, str):
                pages = _parse_pages_cell(pages, delimiter)
            out.append({
                "doc_id": entry.get("doc_id") or f"doc_{i+1:03d}",
                "filename": entry.get("filename"),
                "page_numbers": list(pages or []),
            })
    return out


# --------------------------------------------------------------------------- #
# Core parser
# --------------------------------------------------------------------------- #

@dataclass
class CSVParseResult:
    dataset: BenchmarkDataset
    warnings: List[str] = field(default_factory=list)


def parse_csv_to_dataset(
    raw: bytes | str,
    *,
    dataset_id: str,
    name: str,
    version: str = "1.0.0",
    domain: str = "generic",
    source: str = "csv-upload",
    mapping: Optional[CSVMapping] = None,
) -> CSVParseResult:
    mapping = mapping or CSVMapping()
    text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
    text = text.lstrip("\ufeff")  # extra BOM guard

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    fieldnames = {f.strip() for f in reader.fieldnames}
    rows = list(reader)
    if not rows:
        raise ValueError("CSV has a header but no data rows.")

    m = mapping
    warnings: List[str] = []

    # Group rows by resolved query_id. If query_id column is missing, generate
    # sequential ids namespaced by dataset_id so bare CSVs don't collide with
    # queries from other datasets (queries.query_id is a global PK today).
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    auto_counter = 0

    for row in rows:
        raw_qid = _clean(row.get(m.query_id))
        if not raw_qid:
            auto_counter += 1
            raw_qid = f"{dataset_id}_q_{auto_counter:04d}"
        if raw_qid not in grouped:
            grouped[raw_qid] = []
            order.append(raw_qid)
        grouped[raw_qid].append(row)

    per_row_fact_cols_present = any(
        col in fieldnames for col in (m.fact_id, m.fact_text)
    )
    per_row_doc_cols_present = any(
        col in fieldnames for col in (m.doc_id, m.filename)
    )

    items: List[Dict[str, Any]] = []

    for qid in order:
        row_group = grouped[qid]
        head = row_group[0]

        query_text = _clean(head.get(m.query))
        gt_answer = _clean(head.get(m.gt_answer))
        difficulty = _clean(head.get(m.difficulty)) or "medium"
        eval_label = _clean(head.get(m.eval_label)) or "answerable"
        categories = _parse_list_cell(_clean(head.get(m.categories)), m.list_delimiter)

        if not query_text:
            warnings.append(f"{qid}: empty query text")

        # ---- Facts ----------------------------------------------------
        facts: List[Dict[str, Any]] = []
        seen_fact_keys: set = set()

        # Layout A: single JSON-encoded cell.
        packed_facts_cell = _clean(head.get(m.gt_supporting_facts))
        if packed_facts_cell:
            facts.extend(_parse_facts_cell(packed_facts_cell))

        # Layout B: per-row fact columns, aggregated across the group.
        if per_row_fact_cols_present:
            for i, r in enumerate(row_group):
                fid = _clean(r.get(m.fact_id))
                ftext = _clean(r.get(m.fact_text))
                if not ftext and not fid:
                    continue
                if not fid:
                    fid = f"{qid}_f{i+1:03d}"
                key = (fid, ftext)
                if key in seen_fact_keys:
                    continue
                seen_fact_keys.add(key)
                facts.append({
                    "fact_id": fid,
                    "text": ftext,
                    "doc_id": _clean(r.get(m.fact_doc_id)) or None,
                })

        # ---- Documents ------------------------------------------------
        docs: List[Dict[str, Any]] = []
        seen_doc_keys: set = set()

        packed_docs_cell = _clean(head.get(m.gt_documents))
        if packed_docs_cell:
            for d in _parse_docs_cell(packed_docs_cell, m.list_delimiter):
                key = (d["doc_id"], d.get("filename"))
                if key in seen_doc_keys:
                    continue
                seen_doc_keys.add(key)
                docs.append(d)

        if per_row_doc_cols_present:
            for r in row_group:
                did = _clean(r.get(m.doc_id))
                fname = _clean(r.get(m.filename)) or None
                if not did and not fname:
                    continue
                if not did:
                    did = fname or f"{qid}_doc"
                key = (did, fname)
                if key in seen_doc_keys:
                    continue
                seen_doc_keys.add(key)
                docs.append({
                    "doc_id": did,
                    "filename": fname,
                    "page_numbers": _parse_pages_cell(
                        _clean(r.get(m.page_numbers)), m.list_delimiter
                    ),
                })

        items.append({
            "query_id": qid,
            "query": query_text,
            "gt_answer": gt_answer,
            "categories": categories,
            "difficulty": difficulty,
            "eval_label": eval_label,
            "gt_supporting_facts": facts,
            "gt_documents": docs,
            "metadata": {},
        })

    payload = {
        "dataset_id": dataset_id,
        "name": name or dataset_id,
        "version": version,
        "domain": domain,
        "source": source,
        "metric_config": {"recall_at_k": [1, 3, 5, 10], "em_normalize": True},
        "leaderboard": [],
        "items": items,
    }

    dataset = BenchmarkDataset.model_validate(payload)
    return CSVParseResult(dataset=dataset, warnings=warnings)


def detect_columns(raw: bytes | str) -> List[str]:
    text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
    text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        return [c.strip() for c in row]
    return []


def _keep_types_referenced(_: Iterable[Any]) -> None:
    return None
