
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import repository
from app.exports.csv_exporter import write_csv
from app.exports.json_exporter import write_json_export
from app.insights.generators import generate_insights
from app.insights.report_builder import build_text_summary

logger = get_logger(__name__)

_PER_QUERY_FIELDS = [
    "query_id",
    # V1 retrieval-side.
    "recall", "precision", "f1", "document_recall",
    # V1 answer-side.
    "exact_match", "semantic_similarity",
    "llm_judge_score", "llm_judge_verdict", "llm_judge_rationale",
    # V1 answer-generation output.
    "generated_answer",
    # Classification.
    "success", "failure_type",
]


def export_run(run_id: str) -> Dict[str, str]:
    settings = get_settings()
    run = repository.get_run(run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")
    dataset_id = run["dataset_id"]

    out_dir = Path(settings.outputs_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, str] = {}

    # 1) Per-query results (CSV + JSON).
    metrics = repository.get_query_metrics(run_id)

    # Merge dynamic metrics into per-query rows.
    dyn_metrics = repository.get_dynamic_metrics(run_id)
    dyn_by_query: Dict[str, Dict[str, Any]] = {}
    dyn_metric_names: List[str] = []
    for dm in dyn_metrics:
        qid = dm["query_id"]
        dyn_by_query.setdefault(qid, {})
        dyn_by_query[qid][dm["metric_name"]] = dm["metric_value"]
        if dm["metric_name"] not in dyn_metric_names:
            dyn_metric_names.append(dm["metric_name"])

    # Exclude dynamic names that duplicate V1 fixed fields.
    extra_dyn_names = [n for n in dyn_metric_names if n not in set(_PER_QUERY_FIELDS)]
    export_fields = list(_PER_QUERY_FIELDS) + extra_dyn_names

    per_query_rows: List[Dict[str, Any]] = []
    for m in metrics:
        row = {k: m.get(k) for k in _PER_QUERY_FIELDS}
        # Add dynamic metric columns.
        qid = m.get("query_id", "")
        for dn in extra_dyn_names:
            row[dn] = dyn_by_query.get(qid, {}).get(dn)
        per_query_rows.append(row)
    paths["per_query_csv"] = write_csv(out_dir / "per_query_results.csv", per_query_rows, export_fields)
    paths["per_query_json"] = write_json_export(out_dir / "per_query_results.json", per_query_rows)

    # Also emit the brief's exact filename for per-query metrics.
    paths["query_metrics_csv"] = write_csv(out_dir / "query_metrics.csv", per_query_rows, _PER_QUERY_FIELDS)

    # 2) Aggregate summary (CSV + JSON). "aggregated_results.csv" matches the brief.
    aggregates = repository.get_aggregates(run_id)
    agg_fields = ["scope_type", "scope_value", "metric_name", "metric_value"]
    paths["aggregates_csv"] = write_csv(out_dir / "aggregated_results.csv", aggregates, agg_fields)
    paths["aggregates_json"] = write_json_export(out_dir / "aggregate_summary.json", aggregates)

    # 2b) Failure taxonomy CSV (counts by failure type) — brief-named.
    from app.core.enums import ScopeType
    failure_rows = [
        {"failure_type": a["scope_value"], "count": int(a["metric_value"])}
        for a in repository.get_aggregates(run_id, ScopeType.FAILURE_TYPE.value)
    ]
    failure_rows.sort(key=lambda r: -r["count"])
    paths["failure_taxonomy_csv"] = write_csv(
        out_dir / "failure_taxonomy.csv", failure_rows, ["failure_type", "count"]
    )

    # 3) Insights (JSON + text report).
    insights = generate_insights(run_id, dataset_id)
    paths["insights_json"] = write_json_export(out_dir / "insights.json", insights)
    report_txt = build_text_summary(insights)
    report_path = out_dir / "insights_report.txt"
    report_path.write_text(report_txt, encoding="utf-8")
    paths["insights_report"] = str(report_path)

    # 4) Run metadata.
    paths["run_meta"] = write_json_export(out_dir / "run_metadata.json", run)

    logger.info("Exported run %s to %s (%d files)", run_id, out_dir, len(paths))
    return paths
