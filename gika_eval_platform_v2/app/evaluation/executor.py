
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.answer_generation.generator import BaseGenerator, get_generator
from app.api_client.base import BaseProvider
from app.core.config import get_settings
from app.core.enums import ResponseStatus
from app.core.logging import get_logger
from app.db import repository
from app.evaluation import failure_taxonomy, response_store
from app.evaluation.judge import BaseJudge, get_judge
from app.metrics.metric_registry import compute_all_metrics
from app.metrics.metric_registry_v2 import compute_selected_metrics

logger = get_logger(__name__)


def execute_query(
    run_id: str,
    query: Dict[str, Any],
    provider: BaseProvider,
    metric_config: Dict[str, Any],
    answer_generator: Optional[BaseGenerator] = None,
    judge: Optional[BaseJudge] = None,
    selected_metrics: Optional[List[str]] = None,
    available_metrics: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    query_id = query["query_id"]
    query_text = query.get("query_text") or query.get("query", "")
    dataset_id = query.get("dataset_id")

    # --- Step 1: Retrieval (retrieval-only, no answer generation). ---
    canonical, status = provider.retrieve(
        query_text=query_text,
        query_id=query_id,
        dataset_id=dataset_id,
    )
    retrieval_time_ms = int(canonical.get("retrieval_time_ms", 0) or 0)

    # --- Step 2: Store raw retrieval response BEFORE metric computation. ---
    response_store.store_response(
        run_id=run_id,
        query_id=query_id,
        raw_payload=canonical,
        retrieval_time_ms=retrieval_time_ms,
        status=status,
    )

    # --- Step 3: Generate the final answer (benchmarking module). ---
    gen = answer_generator or get_generator()
    gt_answer = query.get("gt_answer", "")
    generated_answer = gen.generate(query_text, canonical, gt_answer)

    # --- Step 4: LLM-as-Judge evaluation. ---
    jd = judge or get_judge()
    gt_answers = query.get("gt_answers") or ([gt_answer] if gt_answer else [])
    judge_result = jd.evaluate(
        question=query_text,
        generated_answer=generated_answer,
        gt_answers=gt_answers,
        retrieval_response=canonical,
    )

    # --- Step 5: Compute V1 metrics (for backward-compat fixed columns). ---
    em_normalize = bool(metric_config.get("em_normalize", settings.em_normalize))
    metrics = compute_all_metrics(
        query, canonical,
        generated_answer=generated_answer,
        judge_result=judge_result,
        em_normalize=em_normalize,
    )

    # --- Step 5b: Compute V2 selected metrics (dynamic). ---
    v2_results: Dict[str, Any] = {}
    if selected_metrics:
        v2_results = compute_selected_metrics(
            selected_metrics,
            query, canonical,
            generated_answer=generated_answer,
            judge_result=judge_result,
            config=metric_config,
            available_metrics=available_metrics,
        )

    # --- Step 6: Classify success/failure. ---
    success, failure_type = failure_taxonomy.classify(
        metrics,
        response_status=status,
        knowledge_state_len=len(canonical.get("knowledge_state", [])),
        success_recall_threshold=settings.success_recall_threshold,
        success_doc_recall_threshold=settings.success_doc_recall_threshold,
        low_rank_threshold=settings.low_rank_threshold,
    )

    # --- Step 7: Persist per-query results. ---
    # 7a: Fixed V1 columns.
    metric_row = {
        "run_id": run_id,
        "query_id": query_id,
        **{k: v for k, v in metrics.items() if k != "metric_details"},
        "generated_answer": generated_answer,
        "success": success,
        "failure_type": failure_type,
        "metric_details": metrics.get("metric_details", {}),
    }
    repository.upsert_query_metric(metric_row)

    # 7b: Dynamic V2 metrics.
    dyn_rows = []
    for mname, mval in v2_results.items():
        if mname.endswith("_unavailable"):
            continue
        dyn_rows.append({
            "run_id": run_id,
            "query_id": query_id,
            "metric_name": mname,
            "metric_value": mval,
            "metric_metadata": {},
        })
    if dyn_rows:
        repository.upsert_dynamic_metrics_batch(dyn_rows)

    _ = ResponseStatus  # keep import referenced
    return metric_row
