
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from app.core.logging import get_logger
from app.ingestion.adapters.base import BaseAdapter
from app.ingestion.adapters.hotpotqa import HotpotQAAdapter
from app.ingestion.adapters.musique import MusiqueAdapter
from app.ingestion.adapters.native import NativeAdapter

logger = get_logger(__name__)

# Order matters: the first adapter whose ``can_handle`` returns True wins.
# More-specific adapters go first; ``NativeAdapter`` is the permissive
# fallback checked last.
ADAPTERS: List[BaseAdapter] = [
    MusiqueAdapter(),
    HotpotQAAdapter(),
    NativeAdapter(),
]


def detect_adapter(raw: Union[Dict[str, Any], List[Any]]) -> Optional[BaseAdapter]:
    for a in ADAPTERS:
        try:
            if a.can_handle(raw):
                return a
        except Exception as exc:  # noqa: BLE001 - defensive; try the next one
            logger.debug("adapter %s.can_handle raised %s", a.__class__.__name__, exc)
    return None


def adapt(
    raw: Union[Dict[str, Any], List[Any]],
    *,
    dataset_id_override: Optional[str] = None,
    name_override: Optional[str] = None,
) -> Dict[str, Any]:
    # Try the raw input first (supports adapters that accept lists directly).
    a = detect_adapter(raw)

    if a is None and isinstance(raw, list):
        # Wrap bare list in an object envelope and retry.
        wrapped = {"data": raw}
        a = detect_adapter(wrapped)
        if a is not None:
            raw = wrapped

    if a is None:
        if isinstance(raw, dict):
            hint = f"Top-level keys: {sorted(raw.keys())}"
        elif isinstance(raw, list):
            hint = f"Top-level list with {len(raw)} items"
        else:
            hint = f"Type: {type(raw).__name__}"
        raise ValueError(f"No adapter recognises this dataset shape. {hint}")

    out = a.to_internal(raw)
    if dataset_id_override:
        out["dataset_id"] = dataset_id_override
    if name_override:
        out["name"] = name_override
    logger.info(
        "Adapter %s produced %d items for dataset_id=%s",
        a.__class__.__name__, len(out.get("items", [])), out.get("dataset_id"),
    )
    return out


__all__ = [
    "BaseAdapter", "MusiqueAdapter", "HotpotQAAdapter", "NativeAdapter",
    "ADAPTERS", "detect_adapter", "adapt",
]
