
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from app.ingestion.csv_loader import CSVMapping, parse_csv_to_dataset
from app.schemas.dataset import BenchmarkDataset


def detect_format(filename: str, raw: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".json"):
        return "json"
    if lower.endswith((".csv", ".tsv")):
        return "csv"
    # Sniff first non-whitespace char.
    head = raw[:64].lstrip() if isinstance(raw, (bytes, bytearray)) else str(raw)[:64].lstrip()
    if isinstance(head, bytes):
        head = head.decode("utf-8", errors="ignore").lstrip()
    return "json" if head[:1] in ("{", "[") else "csv"


def parse_bytes(
    raw: bytes,
    *,
    filename: str = "",
    dataset_id: Optional[str] = None,
    name: Optional[str] = None,
    csv_mapping: Optional[Dict[str, Any]] = None,
) -> Tuple[BenchmarkDataset, list]:
    fmt = detect_format(filename, raw)

    if fmt == "json":
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(data, (dict, list)):
            raise ValueError(
                "Top-level JSON must be an object or a list of examples "
                "(supported shapes: native, MuSiQue, HotpotQA, or any shape "
                "recognised by app.ingestion.adapters)."
            )
        # Route through the adapter registry so uploads of any recognised
        # source shape (native, MuSiQue, HotpotQA, future GIKA) work
        # identically — including bare top-level lists.
        from app.ingestion.adapters import adapt as _adapt
        internal = _adapt(
            data,
            dataset_id_override=dataset_id,
            name_override=name,
        )
        return BenchmarkDataset.model_validate(internal), []

    # CSV path.
    if not dataset_id:
        raise ValueError("dataset_id is required for CSV uploads.")
    mapping = CSVMapping.from_dict(csv_mapping) if csv_mapping else None
    result = parse_csv_to_dataset(
        raw,
        dataset_id=dataset_id,
        name=name or dataset_id,
        mapping=mapping,
    )
    return result.dataset, list(result.warnings)
