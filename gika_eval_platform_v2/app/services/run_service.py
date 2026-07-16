
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.enums import RunStatus
from app.core.logging import get_logger
from app.core.utils import new_run_id, utcnow_iso
from app.db import repository
from app.ingestion import normalizer
from app.ingestion.loader import load_dataset, load_leaderboard
from app.ingestion.validator import validate_dataset
from app.schemas.dataset import BenchmarkDataset

logger = get_logger(__name__)


def ingest_from_object(
    ds: BenchmarkDataset,
    leaderboard_path: Optional[str] = None,
) -> BenchmarkDataset:
    warnings = validate_dataset(ds)
    for w in warnings:
        logger.warning("dataset warning: %s", w)

    repository.upsert_dataset(normalizer.dataset_record(ds))
    for q in normalizer.query_records(ds):
        repository.upsert_query(q, ds.dataset_id)

    lb = normalizer.leaderboard_records(ds)
    if not lb:
        lb = load_leaderboard(leaderboard_path)
    if lb:
        repository.replace_leaderboard(ds.dataset_id, lb)

    logger.info(
        "Ingested dataset '%s' (%d queries, %d leaderboard entries)",
        ds.dataset_id, len(ds.items), len(lb),
    )
    return ds


def ingest_dataset(path: Optional[str] = None, leaderboard_path: Optional[str] = None) -> BenchmarkDataset:
    ds = load_dataset(path)
    return ingest_from_object(ds, leaderboard_path=leaderboard_path)


def create_run(
    dataset_id: str,
    api_endpoint: Optional[str] = None,
    run_name: str = "",
    metric_config: Optional[Dict[str, Any]] = None,
    api_config: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
    selected_metrics: Optional[List[str]] = None,
    comparison_group_id: str = "",
) -> str:
    settings = get_settings()
    ds = repository.get_dataset(dataset_id)
    if not ds:
        raise ValueError(f"Dataset not found: {dataset_id}")

    queries = repository.get_queries(dataset_id)
    run_id = new_run_id()

    resolved_endpoint = api_endpoint or settings.retrieval_endpoint
    pc = dict(provider_config or {})
    pc.setdefault("endpoint", resolved_endpoint)
    pc.setdefault("timeout_s", settings.request_timeout_s)
    pc.setdefault("max_retries", settings.max_retries)

    resolved_provider = (provider or "").strip() or "generic_http"

    # Default to all registered metrics if none specified.
    if selected_metrics is None:
        from app.metrics.metric_registry_v2 import list_metric_names
        selected_metrics = list_metric_names()

    run = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "dataset_version": ds.get("version", ""),
        "run_name": run_name or f"run over {dataset_id}",
        "provider": resolved_provider,
        "provider_config": pc,
        "api_endpoint": resolved_endpoint,
        "api_config": api_config or {
            "timeout_s": settings.request_timeout_s,
            "max_retries": settings.max_retries,
        },
        "metric_config": metric_config or {
            "em_normalize": settings.em_normalize,
        },
        "selected_metrics": selected_metrics,
        "comparison_group_id": comparison_group_id,
        "status": RunStatus.PENDING.value,
        "total_queries": len(queries),
        "started_at": utcnow_iso(),
        "finished_at": None,
    }
    repository.create_run(run)
    logger.info("Created run %s (provider=%s) over %d queries",
                run_id, resolved_provider, len(queries))
    return run_id


def list_runs() -> List[Dict[str, Any]]:
    return repository.list_runs()


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return repository.get_run(run_id)
