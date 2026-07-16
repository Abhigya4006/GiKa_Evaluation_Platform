
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.answer_generation.generator import get_generator
from app.api_client.base import ProviderConfig
from app.api_client.providers import DEFAULT_PROVIDER, get_provider
from app.core.config import get_settings
from app.core.enums import RunStatus
from app.core.logging import get_logger
from app.core.utils import utcnow_iso
from app.db import repository
from app.evaluation import analytics, checkpoint, executor
from app.evaluation.judge import get_judge
from app.metrics.metric_registry_v2 import get_available_metric_names, list_metric_names

logger = get_logger(__name__)


def run_evaluation(
    run_id: str,
    *,
    local_fn=None,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    run = repository.get_run(run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    dataset_id = run["dataset_id"]
    queries = repository.get_queries(dataset_id)
    metric_config = _load_json(run.get("metric_config_json"))
    api_config = _load_json(run.get("api_config_json"))

    # V2: Resolve selected metrics and dataset availability.
    import json as _json
    selected_metrics_raw = run.get("selected_metrics_json") or "[]"
    if isinstance(selected_metrics_raw, str):
        try:
            selected_metrics = _json.loads(selected_metrics_raw)
        except Exception:
            selected_metrics = list_metric_names()
    else:
        selected_metrics = selected_metrics_raw
    if not selected_metrics:
        selected_metrics = list_metric_names()

    # Determine which fields the dataset provides.
    from app.ingestion.capability_analyzer import analyze_dataset as _analyze
    from app.schemas.dataset import BenchmarkDataset as _BD
    from app.ingestion.loader import load_dataset as _ld
    try:
        ds_record = repository.get_dataset(dataset_id)
        # Build a minimal BenchmarkDataset from DB queries for capability analysis.
        items_data = []
        for q in queries:
            items_data.append({
                "query_id": q["query_id"],
                "query": q.get("query_text", ""),
                "gt_answer": q.get("gt_answer", ""),
                "gt_answers": q.get("gt_answers", []),
                "gt_supporting_facts": [
                    {"fact_id": f.get("fact_id", ""), "text": f.get("text", "")}
                    for f in q.get("gt_supporting_facts", [])
                ],
                "gt_documents": [
                    {"doc_id": d.get("doc_id", "")}
                    for d in q.get("gt_documents", [])
                ],
            })
        mini_ds = _BD.model_validate({
            "dataset_id": dataset_id,
            "name": (ds_record or {}).get("name", dataset_id),
            "items": items_data,
        })
        report = _analyze(mini_ds)
        available_metrics = set(report.supported_metrics)
    except Exception:
        available_metrics = set(list_metric_names())

    # Provider selection.
    provider_name = (run.get("provider") or DEFAULT_PROVIDER)
    provider_config_data = _load_json(run.get("provider_config_json"))
    if not provider_config_data:
        provider_config_data = {
            "endpoint": run.get("api_endpoint") or settings.retrieval_endpoint,
            "timeout_s": api_config.get("timeout_s", settings.request_timeout_s),
            "max_retries": api_config.get("max_retries", settings.max_retries),
        }

    if local_fn is not None:
        provider_name = "mock_local"
        logger.info("local_fn provided -> forcing provider=mock_local for run %s", run_id)

    provider = get_provider(provider_name, ProviderConfig.from_dict(provider_config_data))

    repository.update_run_status(run_id, RunStatus.RUNNING.value)

    # Benchmarking module (V1 answer generator + judge). Both fall back to a
    # deterministic implementation when GIKA_LLM_ENDPOINT / GIKA_LLM_API_KEY
    # are not configured.
    answer_gen = get_generator()
    judge = get_judge()
    logger.info(
        "Run %s: provider=%s | answer_generator=%s | judge=%s",
        run_id, provider.name, answer_gen.name, judge.name,
    )

    completed = checkpoint.load_completed(run_id)
    pending = [q for q in queries if q["query_id"] not in completed]
    logger.info(
        "Run %s: %d total, %d already done, %d pending",
        run_id, len(queries), len(completed), len(pending),
    )

    bsize = batch_size or settings.batch_size
    any_error = False
    completed_list: List[str] = list(completed)

    for start in range(0, len(pending), bsize):
        batch = pending[start:start + bsize]
        for q in batch:
            q = {**q, "dataset_id": dataset_id}
            row = executor.execute_query(
                run_id, q, provider, metric_config, answer_gen, judge,
                selected_metrics=selected_metrics,
                available_metrics=available_metrics,
            )
            if row.get("failure_type") in ("api_error", "response_invalid"):
                any_error = True
            completed_list.append(q["query_id"])
        checkpoint.save_checkpoint(run_id, completed_list)
        logger.info("Run %s: completed %d/%d", run_id, len(completed_list), len(queries))

    analytics.aggregate_run(run_id, dataset_id)

    final_status = RunStatus.PARTIAL.value if any_error else RunStatus.COMPLETED.value
    repository.update_run_status(run_id, final_status, finished_at=utcnow_iso())
    logger.info("Run %s finished with status=%s", run_id, final_status)

    return {
        "run_id": run_id,
        "provider": provider.name,
        "answer_generator": answer_gen.name,
        "judge": judge.name,
        "status": final_status,
        "total_queries": len(queries),
        "overall": analytics.overall_metrics(run_id),
    }


def _load_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:  # noqa: BLE001
        return {}
