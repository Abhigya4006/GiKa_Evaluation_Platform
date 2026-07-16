"""Dataset management endpoints: upload, parse, validate, GT merge, ingest."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db import repository
from app.ingestion.capability_analyzer import analyze_dataset
from app.ingestion.csv_loader import detect_columns
from app.ingestion.gt_merge import merge_ground_truth, parse_ground_truth
from app.ingestion.parse import detect_format, parse_bytes
from app.ingestion.validator import validate_dataset
from app.schemas.dataset import BenchmarkDataset
from app.services.run_service import ingest_from_object

router = APIRouter()

# Module-level cache for parsed datasets awaiting ingest.
# In production this should be replaced by a session / temp store.
_parsed_cache: Dict[str, BenchmarkDataset] = {}


@router.get("")
def list_datasets() -> List[Dict[str, Any]]:
    """Return all ingested datasets with query counts."""
    datasets = repository.list_datasets()
    for d in datasets:
        d["query_count"] = len(repository.get_queries(d["dataset_id"]))
    return datasets


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str) -> Dict[str, Any]:
    ds = repository.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")
    ds["query_count"] = len(repository.get_queries(dataset_id))
    return ds


@router.get("/{dataset_id}/queries")
def get_dataset_queries(dataset_id: str) -> List[Dict[str, Any]]:
    ds = repository.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")
    return repository.get_queries(dataset_id)


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_id: str = Form(""),
    name: str = Form(""),
    version: str = Form("1.0.0"),
    csv_mapping: str = Form(""),
) -> Dict[str, Any]:
    """
    Upload and parse a benchmark file (JSON or CSV).
    Returns parsed preview, validation, and capability analysis.
    Does NOT ingest — call POST /api/datasets/ingest for that.
    """
    raw = await file.read()
    filename = file.filename or "upload"
    fmt = detect_format(filename, raw)

    # Resolve dataset_id.
    if not dataset_id:
        dataset_id = _slugify(filename.rsplit(".", 1)[0])

    # Parse CSV mapping JSON if provided.
    mapping_dict: Optional[Dict[str, Any]] = None
    if csv_mapping and csv_mapping.strip():
        try:
            mapping_dict = json.loads(csv_mapping)
        except json.JSONDecodeError:
            raise HTTPException(400, "csv_mapping is not valid JSON")

    # Detect columns for CSV files.
    detected_columns: List[str] = []
    if fmt == "csv":
        try:
            detected_columns = detect_columns(raw)
        except Exception:
            detected_columns = []

    # Parse.
    try:
        dataset, warnings = parse_bytes(
            raw,
            filename=filename,
            dataset_id=dataset_id or None,
            name=name or None,
            csv_mapping=mapping_dict,
        )
    except Exception as exc:
        raise HTTPException(400, f"Parsing failed: {exc}")

    if version:
        dataset.version = version

    # Capability analysis.
    report = analyze_dataset(dataset)

    # Validation.
    val_warnings = validate_dataset(dataset)

    # Cache for later ingest / GT merge.
    _parsed_cache[dataset.dataset_id] = dataset

    # Build preview rows (first 50).
    preview_rows = []
    for it in dataset.items[:50]:
        preview_rows.append({
            "query_id": it.query_id,
            "query": it.query[:120],
            "gt_answer": it.gt_answer[:100],
            "difficulty": it.difficulty,
            "categories": it.categories,
            "facts_count": len(it.gt_supporting_facts),
            "docs_count": len(it.gt_documents),
        })

    return {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "version": dataset.version,
        "format": fmt,
        "total_items": len(dataset.items),
        "preview": preview_rows,
        "capability_report": report.to_dict(),
        "validation_warnings": val_warnings,
        "parse_warnings": warnings,
        "detected_columns": detected_columns,
    }


@router.post("/gt-merge")
async def merge_gt(
    file: UploadFile = File(...),
    dataset_id: str = Form(...),
) -> Dict[str, Any]:
    """Upload ground-truth records and merge into a previously parsed (cached) dataset."""
    if dataset_id not in _parsed_cache:
        raise HTTPException(
            404,
            "No parsed dataset in cache for this dataset_id. Upload the dataset first.",
        )

    raw = await file.read()
    gt_records, gt_errors = parse_ground_truth(raw, file.filename or "gt.json")

    if gt_errors:
        raise HTTPException(400, f"GT parse errors: {gt_errors}")

    dataset = _parsed_cache[dataset_id]
    merged_ds, merge_result = merge_ground_truth(dataset, gt_records)

    if merge_result.errors:
        raise HTTPException(400, f"Merge errors: {merge_result.errors}")

    # Update cache.
    _parsed_cache[dataset_id] = merged_ds

    # Re-analyze.
    new_report = analyze_dataset(merged_ds)

    return {
        "success": merge_result.success,
        "matched_count": merge_result.matched_count,
        "unmatched_gt_ids": merge_result.unmatched_gt_ids,
        "missing_dataset_ids": merge_result.missing_dataset_ids,
        "warnings": merge_result.warnings,
        "updated_capability_report": new_report.to_dict(),
    }


@router.post("/ingest")
def ingest_dataset_endpoint(
    dataset_id: str = Form(...),
) -> Dict[str, Any]:
    """Ingest a previously uploaded/parsed dataset into the database."""
    if dataset_id not in _parsed_cache:
        raise HTTPException(
            404,
            "No parsed dataset in cache. Upload the dataset first via /api/datasets/upload.",
        )

    dataset = _parsed_cache[dataset_id]
    try:
        ingest_from_object(dataset)
    except Exception as exc:
        raise HTTPException(500, f"Ingestion failed: {exc}")

    # Remove from cache after successful ingest.
    _parsed_cache.pop(dataset_id, None)

    return {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "items_count": len(dataset.items),
        "message": f"Ingested {dataset.dataset_id} with {len(dataset.items)} queries.",
    }


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> Dict[str, str]:
    ds = repository.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")
    conn = repository.connect()
    try:
        conn.execute("DELETE FROM datasets WHERE dataset_id=?", (dataset_id,))
        conn.commit()
    finally:
        conn.close()
    return {"message": f"Dataset {dataset_id} deleted."}


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_.":
            out.append("_")
    slug = "".join(out).strip("_")
    return slug or "dataset"
