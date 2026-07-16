
import os as _os, sys as _sys  # noqa: E402
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import uuid
from typing import Any, Dict, List

from app.api_client.providers import DEFAULT_PROVIDER, available_providers
from app.core.enums import ScopeType
from app.db import repository
from app.evaluation.runner import run_evaluation
from app.ingestion.csv_loader import CSVMapping, detect_columns
from app.ingestion.parse import detect_format, parse_bytes
from app.services import analytics_service, leaderboard_service
from app.services.run_service import create_run, ingest_from_object

try:
    import pandas as pd
    import streamlit as st
    _STREAMLIT = True
except Exception:  # noqa: BLE001
    _STREAMLIT = False


# --------------------------------------------------------------------------- #
# Data helpers (usable without Streamlit — covered by the smoke test).
# --------------------------------------------------------------------------- #

def _run_options() -> List[Dict[str, Any]]:
    return repository.list_runs()


def _load_dashboard_data(run_id: str) -> Dict[str, Any]:
    run = repository.get_run(run_id) or {}
    dataset_id = run.get("dataset_id", "")
    return {
        "run": run,
        "dataset_id": dataset_id,
        "summary": analytics_service.run_summary(run_id),
        "query_rows": analytics_service.query_rows(run_id, dataset_id),
        "difficulty": analytics_service.scope_table(run_id, ScopeType.DIFFICULTY.value),
        "category": analytics_service.scope_table(run_id, ScopeType.CATEGORY.value),
        "documents": analytics_service.document_analysis(run_id, dataset_id),
        "leaderboard": leaderboard_service.leaderboard_comparison(run_id, dataset_id),
    }


# --------------------------------------------------------------------------- #
# Streamlit views.
# --------------------------------------------------------------------------- #

def main() -> None:  # pragma: no cover - requires Streamlit runtime
    if not _STREAMLIT:
        raise RuntimeError("Streamlit is not installed. Install requirements.txt to run the dashboard.")

    st.set_page_config(page_title="GIKA Eval Dashboard", layout="wide")
    st.title("GIKA Dataset Evaluation & Analytics")

    # ---- Top-level navigation ----
    view = st.sidebar.radio(
        "View",
        ["Analytics", "Datasets", "New Run", "Compare"],
        index=_default_view_index(),
        key="nav_view",
    )
    st.sidebar.markdown("---")

    if view == "Analytics":
        _view_analytics()
    elif view == "Datasets":
        _view_datasets()
    elif view == "New Run":
        _view_new_run()
    elif view == "Compare":
        _view_compare()


def _default_view_index() -> int:
    try:
        if not repository.list_runs() and repository.list_datasets():
            return 2
        if not repository.list_datasets():
            return 1
    except Exception:  # noqa: BLE001
        pass
    return 0


# --------------------------------------------------------------------------- #
# View: Analytics
# --------------------------------------------------------------------------- #

def _view_analytics() -> None:  # pragma: no cover
    runs = _run_options()
    if not runs:
        st.warning(
            "No evaluation runs found yet. Head over to **New Run** (or run "
            "`python scripts/run_evaluation.py --local --export`) to create one."
        )
        return

    run_labels = {
        f"{r['run_id']}  [{r.get('provider') or 'generic_http'}]  ({r.get('status')})": r["run_id"]
        for r in runs
    }
    default_run_id = st.session_state.get("focus_run_id")
    label_list = list(run_labels.keys())
    default_index = 0
    if default_run_id:
        for i, k in enumerate(label_list):
            if run_labels[k] == default_run_id:
                default_index = i
                break
        st.session_state.pop("focus_run_id", None)

    chosen_label = st.sidebar.selectbox("Select run", label_list, index=default_index)
    run_id = run_labels[chosen_label]

    compare_label = st.sidebar.selectbox(
        "Compare with (optional)", ["—"] + [l for l in run_labels if run_labels[l] != run_id]
    )

    data = _load_dashboard_data(run_id)
    summary = data["summary"]
    overall = summary["overall"]

    st.header("Overall Run Summary")
    run = data["run"]
    st.caption(
        f"Dataset: {run.get('dataset_id')} v{run.get('dataset_version')} | "
        f"Status: {run.get('status')} | "
        f"Provider: {run.get('provider') or 'generic_http'} | "
        f"Endpoint: {run.get('api_endpoint') or '(in-process)'}"
    )
    cols = st.columns(6)
    for col, (label, key) in zip(cols, [
        ("Recall", "recall"), ("Precision", "precision"), ("F1", "f1"),
        ("Exact Match", "exact_match"), ("Doc Recall", "document_recall"),
        ("Success Rate", "success_rate"),
    ]):
        val = overall.get(key)
        col.metric(label, f"{val:.3f}" if isinstance(val, (int, float)) else "—")

    cols2 = st.columns(3)
    for col, (label, key) in zip(cols2, [
        ("Semantic Similarity", "semantic_similarity"),
        ("LLM Judge", "llm_judge_score"),
        ("Queries", "num_queries"),
    ]):
        val = overall.get(key)
        col.metric(
            label,
            f"{val:.3f}" if key != "num_queries" and isinstance(val, (int, float))
            else str(int(val)) if val else "—",
        )

    # V2 dynamic metrics in overall.
    from app.metrics.metric_registry_v2 import get_all_metrics, list_metric_names
    v1_names = {"recall", "precision", "f1", "document_recall", "exact_match",
                "semantic_similarity", "llm_judge_score", "success_rate", "num_queries"}
    extra_metric_names = [k for k in overall if k not in v1_names]
    if extra_metric_names:
        st.subheader("Additional Metrics")
        ecols = st.columns(min(len(extra_metric_names), 4))
        for i, mn in enumerate(extra_metric_names):
            val = overall.get(mn)
            ecols[i % len(ecols)].metric(
                mn.replace("_", " ").title(),
                f"{val:.3f}" if isinstance(val, (int, float)) else "—"
            )

    # ---- Failure taxonomy ----
    st.header("Failure Taxonomy")
    fc = summary["failure_counts"]
    if fc:
        fc_df = pd.DataFrame(sorted(fc.items(), key=lambda kv: -kv[1]), columns=["failure_type", "count"])
        c1, c2 = st.columns([1, 2])
        c1.dataframe(fc_df, use_container_width=True)
        c2.bar_chart(fc_df.set_index("failure_type"))

    # ---- Query-level table with filters ----
    st.header("Query-Level Results")
    qrows = data["query_rows"]
    qdf = pd.DataFrame(qrows)
    if not qdf.empty:
        fcol1, fcol2, fcol3 = st.columns(3)
        difficulties = ["(all)"] + sorted(x for x in qdf["difficulty"].dropna().unique())
        chosen_diff = fcol1.selectbox("Difficulty", difficulties)
        all_cats = sorted({c for row in qrows for c in (row.get("categories") or [])})
        chosen_cat = fcol2.selectbox("Category", ["(all)"] + all_cats)
        only_failures = fcol3.checkbox("Only failures", value=False)

        view = qdf.copy()
        if chosen_diff != "(all)":
            view = view[view["difficulty"] == chosen_diff]
        if chosen_cat != "(all)":
            view = view[view["categories"].apply(lambda cs: chosen_cat in (cs or []))]
        if only_failures:
            view = view[~view["success"].fillna(False)]
        view = view.copy()
        view["categories"] = view["categories"].apply(lambda cs: ", ".join(cs or []))
        st.dataframe(view, use_container_width=True, height=360)

        st.subheader("Inspect a query")
        qid_options = view["query_id"].tolist() if not view.empty else qdf["query_id"].tolist()
        qid = st.selectbox("Query id", qid_options)
        if qid:
            detail = analytics_service.query_detail(run_id, qid)
            q = detail["query"]
            m = detail["metrics"]
            left, right = st.columns(2)
            with left:
                st.markdown("**Query**")
                st.write(q.get("query_text"))
                st.markdown("**Ground-truth answer(s)**")
                gt_answers = q.get("gt_answers") or ([q.get("gt_answer")] if q.get("gt_answer") else [])
                st.write(gt_answers)
                st.markdown("**GT supporting facts**")
                st.dataframe(pd.DataFrame(q.get("gt_supporting_facts", [])), use_container_width=True)
                st.markdown("**GT documents**")
                st.dataframe(pd.DataFrame(q.get("gt_documents", [])), use_container_width=True)
            with right:
                st.markdown("**Generated answer**")
                st.write(m.get("generated_answer") or "—")
                st.markdown("**Metrics**")
                show = {k: m.get(k) for k in (
                    "recall", "precision", "f1", "document_recall",
                    "exact_match", "semantic_similarity",
                    "llm_judge_score", "llm_judge_verdict", "llm_judge_rationale",
                    "success", "failure_type")}
                # Add dynamic metrics.
                dyn = repository.get_dynamic_metrics_for_query(run_id, qid)
                for dn, dv in dyn.items():
                    if dn not in show:
                        show[dn] = dv
                st.json(show)
                st.markdown("**Retrieved knowledge_state (raw)**")
                st.json(detail["raw_response"].get("knowledge_state", []))

    # ---- Category & difficulty analysis ----
    st.header("Category Analysis")
    cat_df = pd.DataFrame(data["category"])
    if not cat_df.empty:
        keep = [c for c in ["scope_value", "f1", "recall", "precision", "success_rate", "num_queries"]
                if c in cat_df.columns]
        cat_df = cat_df[keep].sort_values("f1", ascending=False)
        st.dataframe(cat_df, use_container_width=True)
        st.bar_chart(cat_df.set_index("scope_value")["f1"])

    st.header("Difficulty Analysis")
    diff_df = pd.DataFrame(data["difficulty"])
    if not diff_df.empty:
        keep = [c for c in ["scope_value", "f1", "recall", "success_rate", "num_queries"]
                if c in diff_df.columns]
        diff_df = diff_df[keep]
        st.dataframe(diff_df, use_container_width=True)

    # ---- Document analysis ----
    st.header("Document Analysis")
    docs = data["documents"]
    d1, d2, d3 = st.columns(3)
    d1.markdown("**Most retrieved**")
    d1.dataframe(pd.DataFrame(docs["most_retrieved"], columns=["doc_id", "count"]), use_container_width=True)
    d2.markdown("**Most missed**")
    d2.dataframe(pd.DataFrame(docs["most_missed"], columns=["doc_id", "count"]), use_container_width=True)
    d3.markdown("**Failure-linked**")
    d3.dataframe(pd.DataFrame(docs["failure_linked"], columns=["doc_id", "count"]), use_container_width=True)

    # ---- Leaderboard ----
    st.header("Leaderboard Comparison")
    lb = pd.DataFrame(data["leaderboard"])
    if not lb.empty:
        st.dataframe(lb, use_container_width=True)
    else:
        st.info("No leaderboard baselines for this dataset.")

    # ---- Run comparison ----
    if compare_label != "—":
        st.header("Run Comparison")
        other_id = run_labels[compare_label]
        cmp_rows = analytics_service.compare_runs(other_id, run_id)
        st.caption(f"run_a = {other_id}  |  run_b = {run_id}")
        st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True)

        # Per-query differences.
        with st.expander("Per-query metric differences"):
            pq_cmp = analytics_service.compare_runs_per_query(other_id, run_id)
            if pq_cmp:
                st.dataframe(pd.DataFrame(pq_cmp), use_container_width=True, height=300)


# --------------------------------------------------------------------------- #
# View: Datasets — upload / preview / validate / capability analysis / GT merge
# --------------------------------------------------------------------------- #

def _view_datasets() -> None:  # pragma: no cover
    st.header("Datasets")
    st.caption(
        "Upload a benchmark dataset (JSON or CSV), preview the parsed rows, "
        "view capability analysis, upload separate ground truth, and ingest."
    )

    # ---- Ingested datasets table ----
    existing = repository.list_datasets()
    if existing:
        with st.expander(f"📚 Ingested datasets ({len(existing)})", expanded=False):
            rows = []
            for d in existing:
                qcount = len(repository.get_queries(d["dataset_id"]))
                rows.append({
                    "dataset_id": d["dataset_id"],
                    "name": d.get("name"),
                    "version": d.get("version"),
                    "domain": d.get("domain"),
                    "queries": qcount,
                    "created_at": d.get("created_at"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("### Upload")
    uploaded = st.file_uploader(
        "Benchmark file (JSON or CSV)",
        type=["json", "csv", "tsv"],
        key="upload_file",
        help="JSON follows the canonical BenchmarkDataset schema. "
             "CSV is auto-detected as one-row-per-query or one-row-per-fact.",
    )
    if not uploaded:
        st.info(
            "**JSON format:** top-level object with `dataset_id`, `name`, "
            "`items[]` where each item has `query_id`, `query`, `gt_answer`, "
            "`gt_supporting_facts[]`, `gt_documents[]`, `difficulty`, `categories[]`. "
            "See `data/sample_dataset/dataset.json` for a complete example.\n\n"
            "**CSV format:** columns `query_id, query, gt_answer, categories, "
            "difficulty` plus either JSON-encoded `gt_supporting_facts` / "
            "`gt_documents` cells (one row per query), OR per-row `fact_id, "
            "fact_text, fact_doc_id, doc_id, filename, page_numbers` columns "
            "(multiple rows per query, grouped by `query_id`). "
            "See `data/sample_dataset/example_csv_layout_a.csv` and "
            "`example_csv_layout_b.csv` for templates."
        )
        return

    raw = uploaded.getvalue()
    fmt = detect_format(uploaded.name, raw)
    st.success(f"Loaded **{uploaded.name}** ({len(raw)} bytes) — detected format: **{fmt}**")

    c1, c2, c3 = st.columns(3)
    default_dsid = _slugify(uploaded.name.rsplit(".", 1)[0])
    dataset_id = c1.text_input("Dataset ID", value=default_dsid, key="up_dsid",
                               help="Unique key. Existing dataset with this id will be replaced.")
    display_name = c2.text_input("Display name", value=default_dsid.replace("_", " ").title(), key="up_name")
    version = c3.text_input("Version", value="1.0.0", key="up_version")

    csv_mapping_dict: Dict[str, Any] = {}
    if fmt == "csv":
        st.markdown("#### CSV column mapping")
        st.caption(
            "Match your source columns to the evaluator's canonical fields. "
            "Leave a mapping as its default if your file already uses the canonical name. "
            "For CSVs with one row per fact, both `fact_text` and `doc_id` per-row "
            "columns will be aggregated by `query_id`."
        )
        try:
            src_cols = detect_columns(raw)
        except Exception:  # noqa: BLE001
            src_cols = []
        options = ["(default)"] + src_cols
        canonical_fields = [
            ("query_id", "query_id"), ("query", "query"), ("gt_answer", "gt_answer"),
            ("categories", "categories"), ("difficulty", "difficulty"), ("eval_label", "eval_label"),
            ("gt_supporting_facts (JSON cell)", "gt_supporting_facts"),
            ("fact_id (per-row)", "fact_id"),
            ("fact_text (per-row)", "fact_text"),
            ("fact_doc_id (per-row)", "fact_doc_id"),
            ("gt_documents (JSON cell)", "gt_documents"),
            ("doc_id (per-row)", "doc_id"),
            ("filename (per-row)", "filename"),
            ("page_numbers (per-row)", "page_numbers"),
        ]
        cols = st.columns(3)
        for i, (label, key) in enumerate(canonical_fields):
            with cols[i % 3]:
                choice = st.selectbox(label, options, key=f"map_{key}")
                if choice and choice != "(default)":
                    csv_mapping_dict[key] = choice

    # ---- Parse + preview ----
    try:
        with st.spinner("Parsing..."):
            dataset, warnings = parse_bytes(
                raw,
                filename=uploaded.name,
                dataset_id=dataset_id or None,
                name=display_name or None,
                csv_mapping=csv_mapping_dict or None,
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Parsing failed: {exc}")
        return

    if version:
        dataset.version = version

    # Store parsed dataset in session state for GT merge.
    st.session_state["parsed_dataset"] = dataset

    st.markdown("### Preview")
    _render_dataset_preview(dataset, warnings)

    # ---- Capability Analysis (Requirement 1) ----
    from app.ingestion.capability_analyzer import analyze_dataset
    report = analyze_dataset(dataset)

    st.markdown("### Dataset Capability Analysis")

    status_color = {
        "ready": "✅", "incomplete": "⚠️", "invalid": "❌"
    }.get(report.status, "❓")
    st.markdown(f"**Status:** {status_color} **{report.status.upper()}**")

    cap_c1, cap_c2 = st.columns(2)
    with cap_c1:
        st.markdown("**Detected fields:**")
        for f in report.detected_fields:
            st.write(f"  ✓ {f}")
        if report.missing_fields:
            st.markdown("**Missing fields:**")
            for f in report.missing_fields:
                st.write(f"  ✗ {f}")

    with cap_c2:
        st.markdown("**Supported metrics:**")
        for m in report.supported_metrics:
            st.write(f"  ✓ {m}")
        if report.unsupported_metrics:
            st.markdown("**Unavailable metrics:**")
            for m in report.unsupported_metrics:
                st.write(f"  ✗ {m}")

    if report.warnings:
        with st.expander(f"⚠️ Capability warnings ({len(report.warnings)})"):
            for w in report.warnings:
                st.warning(w)

    if report.errors:
        for e in report.errors:
            st.error(e)

    # ---- Validation warnings ----
    from app.ingestion.validator import validate_dataset
    val_warnings = validate_dataset(dataset)
    if val_warnings:
        with st.expander(f"⚠️ Validation warnings ({len(val_warnings)})", expanded=False):
            for w in val_warnings:
                st.write("-", w)
    else:
        st.success("✅ Validation passed — no schema warnings.")

    # ---- Separate Ground-Truth Upload (Requirement 1) ----
    st.markdown("### Upload Separate Ground Truth (Optional)")
    st.caption(
        "If your dataset is missing ground-truth answers, supporting facts, or documents, "
        "upload them here as a JSON file. Records are matched by `query_id`."
    )

    gt_file = st.file_uploader(
        "Ground-truth file (JSON)",
        type=["json"],
        key="gt_upload",
        help='JSON list of objects with query_id + gt_answer/gt_answers/gt_supporting_facts/gt_documents.',
    )
    if gt_file:
        from app.ingestion.gt_merge import parse_ground_truth, merge_ground_truth
        gt_raw = gt_file.getvalue()
        gt_records, gt_errors = parse_ground_truth(gt_raw, gt_file.name)

        if gt_errors:
            for e in gt_errors:
                st.error(f"GT parse error: {e}")
        elif gt_records:
            st.info(f"Parsed {len(gt_records)} ground-truth records.")
            if st.button("🔗 Merge ground truth into dataset", key="merge_gt_btn"):
                merged_ds, merge_result = merge_ground_truth(dataset, gt_records)
                if merge_result.errors:
                    for e in merge_result.errors:
                        st.error(e)
                else:
                    st.success(f"Merged {merge_result.matched_count} records successfully.")
                    if merge_result.unmatched_gt_ids:
                        st.warning(
                            f"{len(merge_result.unmatched_gt_ids)} GT query_ids "
                            f"had no match in the dataset."
                        )
                    if merge_result.missing_dataset_ids:
                        st.info(
                            f"{len(merge_result.missing_dataset_ids)} dataset items "
                            f"have no ground-truth in the uploaded file."
                        )
                    # Update session state and re-analyze.
                    st.session_state["parsed_dataset"] = merged_ds
                    dataset = merged_ds
                    new_report = analyze_dataset(dataset)
                    st.markdown("**Updated capability analysis:**")
                    st.write(f"Status: {new_report.status} | "
                             f"Supported: {new_report.supported_metrics} | "
                             f"Unsupported: {new_report.unsupported_metrics}")

    # ---- Ingest ----
    st.markdown("### Ingest")
    st.caption("Ingestion is idempotent: uploading the same dataset_id again replaces the existing dataset's queries.")

    # Use latest dataset from session (may include GT merge).
    final_dataset = st.session_state.get("parsed_dataset", dataset)

    ingest_c1, ingest_c2 = st.columns([1, 3])
    if ingest_c1.button("💾 Ingest dataset", type="primary", key="ingest_btn"):
        try:
            with st.spinner(f"Ingesting {final_dataset.dataset_id}..."):
                ingest_from_object(final_dataset)
            ingest_c2.success(
                f"Ingested `{final_dataset.dataset_id}` — {len(final_dataset.items)} queries. "
                f"Head to **New Run** to launch an evaluation."
            )
        except Exception as exc:  # noqa: BLE001
            ingest_c2.error(f"Ingestion failed: {exc}")


def _render_dataset_preview(dataset, warnings: List[str]) -> None:  # pragma: no cover
    difficulties = [i.difficulty for i in dataset.items]
    diff_counts = {d: difficulties.count(d) for d in set(difficulties)}
    unans = sum(1 for i in dataset.items if i.eval_label == "unanswerable")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Queries", len(dataset.items))
    c2.metric("Difficulty spread", ", ".join(f"{k}={v}" for k, v in sorted(diff_counts.items())) or "—")
    c3.metric("Unanswerable", unans)
    c4.metric("Warnings", len(warnings))

    rows = []
    for it in dataset.items[:20]:
        rows.append({
            "query_id": it.query_id,
            "query": (it.query[:80] + "…") if len(it.query) > 80 else it.query,
            "gt_answer": (it.gt_answer[:60] + "…") if len(it.gt_answer) > 60 else it.gt_answer,
            "difficulty": it.difficulty,
            "categories": ", ".join(it.categories or []),
            "#facts": len(it.gt_supporting_facts),
            "#docs": len(it.gt_documents),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    if len(dataset.items) > 20:
        st.caption(f"Showing first 20 of {len(dataset.items)} queries.")


# --------------------------------------------------------------------------- #
# Helper: metric selection UI
# --------------------------------------------------------------------------- #

def _metric_selection_ui(dataset_id: str, key_prefix: str = "nr") -> List[str]:
    from app.metrics.metric_registry_v2 import get_all_metrics
    from app.ingestion.capability_analyzer import analyze_dataset, IngestionReport
    from app.schemas.dataset import BenchmarkDataset

    all_metrics = get_all_metrics()

    # Determine availability from dataset.
    supported = set()
    unsupported = set()
    try:
        queries = repository.get_queries(dataset_id)
        items_data = []
        for q in queries:
            items_data.append({
                "query_id": q["query_id"],
                "query": q.get("query_text", ""),
                "gt_answer": q.get("gt_answer", ""),
                "gt_answers": q.get("gt_answers", []),
                "gt_supporting_facts": q.get("gt_supporting_facts", []),
                "gt_documents": q.get("gt_documents", []),
            })
        if items_data:
            ds_rec = repository.get_dataset(dataset_id) or {}
            mini_ds = BenchmarkDataset.model_validate({
                "dataset_id": dataset_id,
                "name": ds_rec.get("name", dataset_id),
                "items": items_data,
            })
            report = analyze_dataset(mini_ds)
            supported = set(report.supported_metrics)
            unsupported = set(report.unsupported_metrics)
    except Exception:
        supported = {m.name for m in all_metrics}

    st.markdown("#### Select Metrics")
    selected = []

    ret_metrics = [m for m in all_metrics if m.category == "retrieval"]
    ans_metrics = [m for m in all_metrics if m.category == "answer"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Retrieval metrics**")
        for m in ret_metrics:
            available = m.name in supported
            label = f"{m.display_name}"
            if not available:
                label += " ⚠️ (unavailable)"
            checked = st.checkbox(
                label, value=available,
                disabled=not available,
                key=f"{key_prefix}_met_{m.name}",
                help=m.description,
            )
            if checked and available:
                selected.append(m.name)

    with col2:
        st.markdown("**Answer metrics**")
        for m in ans_metrics:
            available = m.name in supported
            label = f"{m.display_name}"
            if not available:
                label += " ⚠️ (unavailable)"
            checked = st.checkbox(
                label, value=available,
                disabled=not available,
                key=f"{key_prefix}_met_{m.name}",
                help=m.description,
            )
            if checked and available:
                selected.append(m.name)

    if unsupported:
        st.caption(
            "⚠️ Metrics marked unavailable cannot run because the dataset "
            "is missing required ground-truth data."
        )

    return selected


# --------------------------------------------------------------------------- #
# View: New Run — dataset + provider + metrics + endpoint → launch
# --------------------------------------------------------------------------- #

def _view_new_run() -> None:  # pragma: no cover
    st.header("New Evaluation Run")

    datasets = repository.list_datasets()
    if not datasets:
        st.warning("No datasets ingested yet. Go to **Datasets** and upload one first.")
        return

    ds_id = st.selectbox(
        "Dataset",
        [d["dataset_id"] for d in datasets],
        format_func=lambda x: f"{x}  ({_query_count(x)} queries)",
        key="nr_ds",
    )

    # Metric selection.
    selected_metrics = _metric_selection_ui(ds_id, key_prefix="nr")

    with st.form("new_run_form", clear_on_submit=False):
        st.markdown("### Configure Provider")
        c1, c2 = st.columns(2)
        with c1:
            provider_name = st.selectbox(
                "Provider",
                available_providers(),
                index=available_providers().index(DEFAULT_PROVIDER)
                if DEFAULT_PROVIDER in available_providers() else 0,
                key="nr_provider",
                help=(
                    "mock_local — bundled in-process retriever, no HTTP needed. "
                    "generic_http — any endpoint following the canonical contract. "
                    "gika_retrieve — extends generic_http; edit "
                    "app/api_client/providers/gika_retrieve.py to map GIKA's shape."
                ),
            )
            local_mode = st.checkbox(
                "Use local mock retriever",
                value=False,
                key="nr_local",
                help="Shortcut: forces provider = mock_local (ignores endpoint URL).",
            )
        with c2:
            endpoint_url = st.text_input(
                "Endpoint URL",
                value="http://127.0.0.1:8000/retrieve",
                key="nr_endpoint",
            )
            run_name = st.text_input("Run name (optional)", key="nr_name")
            chat_subscription_id = st.text_input(
                "chat_subscription_id", value="gpt-5-mini", key="nr_chatsub",
            )
            graph_configs_json = st.text_area(
                "graph_configs (JSON list)",
                value='[{"graph_id": "graph-1", "tenant_id": "kb_XXXX", "neo4j_database_name": "dbXXXX"}]',
                key="nr_gc", height=90,
            )

        with st.expander("Advanced — extra provider config JSON"):
            extra_json = st.text_area("JSON", value="", key="nr_extra", height=100)

        submitted = st.form_submit_button("▶ Run evaluation", type="primary")

    if submitted:
        extra_cfg: Dict[str, Any] = {}
        if extra_json.strip():
            try:
                extra_cfg = json.loads(extra_json)
                if not isinstance(extra_cfg, dict):
                    raise ValueError("Extra config must be a JSON object.")
            except Exception as exc:
                st.error(f"Extra provider config is not valid JSON: {exc}")
                st.stop()
        chosen_provider = "mock_local" if local_mode else provider_name
        if chosen_provider != "mock_local":
            extra_cfg.setdefault("endpoint", endpoint_url)
        provider_extra = dict(extra_cfg.get("extra") or {})
        if chat_subscription_id:
            provider_extra.setdefault("chat_subscription_id", chat_subscription_id)
        if graph_configs_json.strip():
            try:
                gc = json.loads(graph_configs_json)
                if isinstance(gc, list):
                    provider_extra.setdefault("graph_configs", gc)
            except Exception:
                st.warning("graph_configs is not valid JSON; ignoring.")
        extra_cfg["extra"] = provider_extra

        try:
            new_rid = create_run(
                dataset_id=ds_id,
                api_endpoint=endpoint_url if chosen_provider != "mock_local" else None,
                run_name=run_name or f"dashboard-{chosen_provider}",
                provider=chosen_provider,
                provider_config=extra_cfg,
                selected_metrics=selected_metrics or None,
            )
            status_ph = st.empty()
            status_ph.info(f"Run **{new_rid}** created (status=pending). Executing...")
            with st.spinner(f"Evaluating with {chosen_provider}..."):
                summary = run_evaluation(new_rid)
            success_rate = summary['overall'].get('success_rate')
            status_ph.success(
                f"Run **{new_rid}** finished: status={summary['status']} | "
                f"queries={summary['total_queries']} | "
                f"success_rate={success_rate:.3f}" if success_rate is not None
                else f"Run **{new_rid}** finished."
            )
            if st.button("📊 Open in Analytics", key=f"open_{new_rid}"):
                st.session_state["focus_run_id"] = new_rid
                st.session_state["nav_view"] = "Analytics"
                st.rerun()
        except Exception as exc:
            st.error(f"Run failed: {exc}")

    # ---- Run history ----
    st.markdown("### Recent runs")
    runs = repository.list_runs()
    if not runs:
        st.caption("No runs yet.")
        return

    rows = []
    for r in runs[:30]:
        overall = analytics_service.run_summary(r["run_id"])["overall"]
        rows.append({
            "run_id": r["run_id"],
            "dataset": r.get("dataset_id"),
            "provider": r.get("provider") or "generic_http",
            "endpoint": r.get("api_endpoint") or "(in-process)",
            "status": r.get("status"),
            "queries": r.get("total_queries"),
            "success_rate": overall.get("success_rate"),
            "f1": overall.get("f1"),
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=320)
    st.caption("Pick a run above and switch to **Analytics** to inspect it.")


# --------------------------------------------------------------------------- #
# View: Compare — configure two systems, run both, compare
# --------------------------------------------------------------------------- #

def _view_compare() -> None:  # pragma: no cover
    st.header("Side-by-Side Retrieval Comparison")
    st.caption(
        "Configure two retrieval systems and benchmark them on the same dataset "
        "with the same metrics for a fair comparison."
    )

    datasets = repository.list_datasets()
    if not datasets:
        st.warning("No datasets ingested yet. Go to **Datasets** and upload one first.")
        return

    ds_id = st.selectbox(
        "Dataset",
        [d["dataset_id"] for d in datasets],
        format_func=lambda x: f"{x}  ({_query_count(x)} queries)",
        key="cmp_ds",
    )

    # Metric selection.
    selected_metrics = _metric_selection_ui(ds_id, key_prefix="cmp")

    st.markdown("---")
    st.markdown("### Configure Retrieval Systems")

    sys_a_col, sys_b_col = st.columns(2)

    with sys_a_col:
        st.markdown("#### System A")
        a_name = st.text_input("Display name", value="System A", key="cmp_a_name")
        a_provider = st.selectbox("Provider", available_providers(), key="cmp_a_provider")
        a_local = st.checkbox("Use local mock", value=False, key="cmp_a_local")
        a_endpoint = st.text_input("Endpoint URL", value="http://127.0.0.1:8000/retrieve", key="cmp_a_ep")

    with sys_b_col:
        st.markdown("#### System B")
        b_name = st.text_input("Display name", value="System B", key="cmp_b_name")
        b_provider = st.selectbox("Provider", available_providers(), key="cmp_b_provider")
        b_local = st.checkbox("Use local mock", value=False, key="cmp_b_local")
        b_endpoint = st.text_input("Endpoint URL", value="http://127.0.0.1:8001/retrieve", key="cmp_b_ep")

    if st.button("▶ Run Comparison", type="primary", key="cmp_run_btn"):
        group_id = f"cmp_{uuid.uuid4().hex[:8]}"

        # Create and run System A.
        prov_a = "mock_local" if a_local else a_provider
        prov_b = "mock_local" if b_local else b_provider

        try:
            st.info(f"Comparison group: `{group_id}`")
            progress = st.empty()

            # System A
            progress.info(f"Running **{a_name}**...")
            rid_a = create_run(
                dataset_id=ds_id,
                api_endpoint=a_endpoint if prov_a != "mock_local" else None,
                run_name=a_name,
                provider=prov_a,
                selected_metrics=selected_metrics or None,
                comparison_group_id=group_id,
            )
            summary_a = run_evaluation(rid_a)

            # System B
            progress.info(f"Running **{b_name}**...")
            rid_b = create_run(
                dataset_id=ds_id,
                api_endpoint=b_endpoint if prov_b != "mock_local" else None,
                run_name=b_name,
                provider=prov_b,
                selected_metrics=selected_metrics or None,
                comparison_group_id=group_id,
            )
            summary_b = run_evaluation(rid_b)

            progress.success(
                f"Both runs completed! Group: `{group_id}` | "
                f"{a_name}: {summary_a['status']} | {b_name}: {summary_b['status']}"
            )

            # Show comparison.
            st.markdown("### Side-by-Side Results")
            st.markdown(f"**{a_name}** (`{rid_a}`) vs **{b_name}** (`{rid_b}`)")

            cmp_rows = analytics_service.compare_runs(rid_a, rid_b)
            cmp_df = pd.DataFrame(cmp_rows)
            if not cmp_df.empty:
                cmp_df.columns = ["metric", a_name, b_name, "delta"]
                st.dataframe(cmp_df, use_container_width=True)

                # Visual comparison.
                numeric_rows = cmp_df[cmp_df["metric"].isin([
                    "recall", "precision", "f1", "document_recall",
                    "exact_match", "semantic_similarity", "success_rate"
                ])].copy()
                if not numeric_rows.empty:
                    chart_df = numeric_rows.set_index("metric")[[a_name, b_name]]
                    st.bar_chart(chart_df)

            # Per-query differences.
            with st.expander("Per-query metric differences"):
                pq_cmp = analytics_service.compare_runs_per_query(rid_a, rid_b)
                if pq_cmp:
                    st.dataframe(pd.DataFrame(pq_cmp), use_container_width=True, height=300)

        except Exception as exc:
            st.error(f"Comparison failed: {exc}")

    # Show historical comparison groups.
    st.markdown("### Historical Comparison Groups")
    all_runs = repository.list_runs()
    groups: Dict[str, List[Dict]] = {}
    for r in all_runs:
        gid = r.get("comparison_group_id") or ""
        if isinstance(gid, str) and gid.startswith("cmp_"):
            groups.setdefault(gid, []).append(r)

    if groups:
        for gid, gruns in sorted(groups.items(), reverse=True):
            with st.expander(f"Group: {gid} ({len(gruns)} runs)"):
                summary_rows = []
                for r in gruns:
                    overall = analytics_service.run_summary(r["run_id"])["overall"]
                    summary_rows.append({
                        "run_id": r["run_id"],
                        "run_name": r.get("run_name", ""),
                        "provider": r.get("provider", ""),
                        "status": r.get("status", ""),
                        "f1": overall.get("f1"),
                        "recall": overall.get("recall"),
                        "success_rate": overall.get("success_rate"),
                    })
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)
    else:
        st.caption("No comparison groups yet. Run a comparison above to create one.")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

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


def _query_count(dataset_id: str) -> int:
    try:
        return len(repository.get_queries(dataset_id))
    except Exception:  # noqa: BLE001
        return 0


if __name__ == "__main__":  # pragma: no cover
    main()
