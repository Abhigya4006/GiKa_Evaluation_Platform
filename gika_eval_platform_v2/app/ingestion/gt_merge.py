
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.dataset import BenchmarkDataset, DatasetItem, SupportingDocument, SupportingFact


@dataclass
class MergeResult:
    success: bool = True
    matched_count: int = 0
    unmatched_gt_ids: List[str] = field(default_factory=list)
    missing_dataset_ids: List[str] = field(default_factory=list)
    duplicate_gt_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def parse_ground_truth(raw: bytes, filename: str = "") -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], [f"Invalid JSON: {exc}"]

    if isinstance(data, dict):
        # Allow {"items": [...]} or {"ground_truth": [...]} wrappers.
        if "items" in data:
            data = data["items"]
        elif "ground_truth" in data:
            data = data["ground_truth"]
        else:
            return [], ["Expected a JSON list or object with 'items'/'ground_truth' key."]

    if not isinstance(data, list):
        return [], ["Ground-truth data must be a JSON list of records."]

    records: List[Dict[str, Any]] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"Entry {i} is not a dict.")
            continue
        if "query_id" not in entry or not entry["query_id"]:
            errors.append(f"Entry {i} is missing 'query_id'.")
            continue
        records.append(entry)

    return records, errors


def merge_ground_truth(
    dataset: BenchmarkDataset,
    gt_records: List[Dict[str, Any]],
) -> Tuple[BenchmarkDataset, MergeResult]:
    result = MergeResult()

    # Build index of dataset items by query_id.
    item_index: Dict[str, int] = {}
    for idx, item in enumerate(dataset.items):
        item_index[item.query_id] = idx

    dataset_ids = set(item_index.keys())

    # Check for duplicate query_ids in GT.
    seen_gt_ids: Dict[str, int] = {}
    for rec in gt_records:
        qid = rec["query_id"]
        seen_gt_ids[qid] = seen_gt_ids.get(qid, 0) + 1

    for qid, count in seen_gt_ids.items():
        if count > 1:
            result.duplicate_gt_ids.append(qid)
            result.errors.append(
                f"Duplicate query_id '{qid}' appears {count} times in ground-truth file."
            )

    if result.duplicate_gt_ids:
        result.success = False
        return dataset, result

    # Merge each GT record.
    gt_ids_used: set = set()
    for rec in gt_records:
        qid = rec["query_id"]
        if qid not in item_index:
            result.unmatched_gt_ids.append(qid)
            continue

        gt_ids_used.add(qid)
        idx = item_index[qid]
        item = dataset.items[idx]

        # Merge GT fields.
        if "gt_answer" in rec and rec["gt_answer"]:
            item.gt_answer = rec["gt_answer"]
        if "gt_answers" in rec and rec["gt_answers"]:
            item.gt_answers = list(rec["gt_answers"])
        # Backfill.
        if item.gt_answer and not item.gt_answers:
            item.gt_answers = [item.gt_answer]
        if item.gt_answers and not item.gt_answer:
            item.gt_answer = item.gt_answers[0]

        if "gt_supporting_facts" in rec and rec["gt_supporting_facts"]:
            facts = []
            for f in rec["gt_supporting_facts"]:
                if isinstance(f, dict):
                    facts.append(SupportingFact.model_validate(f))
            item.gt_supporting_facts = facts

        if "gt_documents" in rec and rec["gt_documents"]:
            docs = []
            for d in rec["gt_documents"]:
                if isinstance(d, dict):
                    docs.append(SupportingDocument.model_validate(d))
            item.gt_documents = docs

        result.matched_count += 1

    # Check for unmatched GT IDs.
    if result.unmatched_gt_ids:
        result.warnings.append(
            f"{len(result.unmatched_gt_ids)} ground-truth query IDs "
            f"have no match in the dataset: {result.unmatched_gt_ids[:10]}"
            + (" ..." if len(result.unmatched_gt_ids) > 10 else "")
        )

    # Check for dataset items not covered by GT.
    missing = dataset_ids - gt_ids_used
    if missing:
        result.missing_dataset_ids = sorted(missing)
        result.warnings.append(
            f"{len(missing)} dataset items have no ground-truth in the uploaded file."
        )

    if not result.errors:
        result.success = True

    return dataset, result
