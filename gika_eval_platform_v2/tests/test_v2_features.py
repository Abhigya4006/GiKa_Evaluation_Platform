
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.api_client.mock_api import build_response
from app.core.enums import ScopeType
from app.db import repository
from app.evaluation.runner import run_evaluation
from app.ingestion.adapters import adapt
from app.ingestion.capability_analyzer import (
    IngestionStatus,
    analyze_dataset,
    get_available_metrics_for_dataset,
)
from app.ingestion.gt_merge import merge_ground_truth, parse_ground_truth
from app.ingestion.loader import load_dataset
from app.metrics.metric_registry_v2 import (
    MetricDefinition,
    compute_selected_metrics,
    get_all_metrics,
    get_metric,
    list_metric_names,
    register_metric,
)
from app.schemas.dataset import BenchmarkDataset, DatasetItem
from app.services.export_service import export_run
from app.services.run_service import create_run, ingest_from_object
from app.services import analytics_service


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_dataset(
    items: List[Dict[str, Any]],
    dataset_id: str = "test_ds",
    name: str = "Test Dataset",
) -> BenchmarkDataset:
    return BenchmarkDataset.model_validate({
        "dataset_id": dataset_id,
        "name": name,
        "items": items,
    })


def _complete_item(qid: str = "q1") -> Dict[str, Any]:
    return {
        "query_id": qid,
        "query": "What is the capital of France?",
        "gt_answer": "Paris",
        "gt_answers": ["Paris"],
        "gt_supporting_facts": [
            {"fact_id": "f1", "text": "Paris is the capital of France.", "doc_id": "doc1"}
        ],
        "gt_documents": [
            {"doc_id": "doc1", "filename": "geo.pdf", "page_numbers": [1]}
        ],
        "difficulty": "easy",
        "categories": ["geography"],
    }


def _no_answer_item(qid: str = "q2") -> Dict[str, Any]:
    return {
        "query_id": qid,
        "query": "What is X?",
        "gt_answer": "",
        "gt_answers": [],
        "gt_supporting_facts": [
            {"fact_id": "f1", "text": "Some fact.", "doc_id": "doc1"}
        ],
        "gt_documents": [
            {"doc_id": "doc1"}
        ],
    }


def _no_facts_item(qid: str = "q3") -> Dict[str, Any]:
    return {
        "query_id": qid,
        "query": "What is Y?",
        "gt_answer": "Something",
        "gt_answers": ["Something"],
        "gt_supporting_facts": [],
        "gt_documents": [],
    }


# --------------------------------------------------------------------------- #
# Test 1: Complete ground truth → status ready
# --------------------------------------------------------------------------- #

def test_complete_dataset_status_ready():
    ds = _make_dataset([_complete_item("q1"), _complete_item("q2")])
    report = analyze_dataset(ds)
    assert report.status == IngestionStatus.READY.value
    assert "gt_answer" in report.detected_fields
    assert "gt_supporting_facts" in report.detected_fields
    assert "gt_documents" in report.detected_fields
    assert not report.errors
    assert len(report.supported_metrics) > 0


# --------------------------------------------------------------------------- #
# Test 2: Dataset with no gt_answer → detected as missing
# --------------------------------------------------------------------------- #

def test_no_gt_answer_detected():
    ds = _make_dataset([_no_answer_item()])
    report = analyze_dataset(ds)
    assert report.status == IngestionStatus.INCOMPLETE.value
    assert "gt_answer" in report.missing_fields
    any_answer_warning = any("Ground-truth answers are missing" in w for w in report.warnings)
    assert any_answer_warning


# --------------------------------------------------------------------------- #
# Test 3: No supporting facts → recall marked unsupported
# --------------------------------------------------------------------------- #

def test_no_facts_recall_unsupported():
    ds = _make_dataset([_no_facts_item()])
    report = analyze_dataset(ds)
    assert "recall" in report.unsupported_metrics
    assert "precision" in report.unsupported_metrics
    assert "f1" in report.unsupported_metrics
    any_fact_warning = any("Supporting facts" in w for w in report.warnings)
    assert any_fact_warning


# --------------------------------------------------------------------------- #
# Test 4: Separate GT file merges by query_id
# --------------------------------------------------------------------------- #

def test_gt_merge_by_query_id():
    ds = _make_dataset([_no_answer_item("q1"), _no_answer_item("q2")])
    gt_records = [
        {"query_id": "q1", "gt_answer": "Answer1", "gt_answers": ["Answer1"]},
        {"query_id": "q2", "gt_answer": "Answer2", "gt_answers": ["Answer2"]},
    ]
    merged, result = merge_ground_truth(ds, gt_records)
    assert result.success
    assert result.matched_count == 2
    assert merged.items[0].gt_answer == "Answer1"
    assert merged.items[1].gt_answer == "Answer2"
    assert merged.items[0].gt_answers == ["Answer1"]


# --------------------------------------------------------------------------- #
# Test 5: Unmatched query IDs during GT merge → clear validation issue
# --------------------------------------------------------------------------- #

def test_gt_merge_unmatched_ids():
    ds = _make_dataset([_no_answer_item("q1")])
    gt_records = [
        {"query_id": "q1", "gt_answer": "A"},
        {"query_id": "q_nonexistent", "gt_answer": "B"},
    ]
    merged, result = merge_ground_truth(ds, gt_records)
    assert result.success
    assert result.matched_count == 1
    assert "q_nonexistent" in result.unmatched_gt_ids
    assert any("no match" in w.lower() for w in result.warnings)


# --------------------------------------------------------------------------- #
# Test 6: Duplicate query IDs in GT → rejected/reported
# --------------------------------------------------------------------------- #

def test_gt_merge_duplicate_ids():
    ds = _make_dataset([_no_answer_item("q1")])
    gt_records = [
        {"query_id": "q1", "gt_answer": "A"},
        {"query_id": "q1", "gt_answer": "B"},
    ]
    _, result = merge_ground_truth(ds, gt_records)
    assert not result.success
    assert "q1" in result.duplicate_gt_ids
    assert any("Duplicate" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Test 7: Metric registry correctly lists available metrics
# --------------------------------------------------------------------------- #

def test_metric_registry_lists_metrics():
    names = list_metric_names()
    assert "recall" in names
    assert "precision" in names
    assert "f1" in names
    assert "document_recall" in names
    assert "exact_match" in names
    assert "semantic_similarity" in names
    assert "llm_judge_score" in names
    assert "token_overlap" in names  # example extensible metric

    all_mets = get_all_metrics()
    assert len(all_mets) >= 8
    for m in all_mets:
        assert m.name
        assert m.display_name
        assert m.category in ("retrieval", "answer")
        assert callable(m.compute)


# --------------------------------------------------------------------------- #
# Test 8: Metric capability detection maps required fields correctly
# --------------------------------------------------------------------------- #

def test_metric_capability_detection():
    ds_complete = _make_dataset([_complete_item()])
    avail = get_available_metrics_for_dataset(ds_complete)
    assert avail["recall"] is True
    assert avail["exact_match"] is True
    assert avail["token_overlap"] is True

    ds_no_facts = _make_dataset([_no_facts_item()])
    avail2 = get_available_metrics_for_dataset(ds_no_facts)
    assert avail2["recall"] is False
    assert avail2["precision"] is False
    assert avail2["exact_match"] is True  # has gt_answer


# --------------------------------------------------------------------------- #
# Test 9: Selecting only recall computes only recall
# --------------------------------------------------------------------------- #

def test_selecting_only_recall():
    query = {
        "gt_supporting_facts": [{"fact_id": "f1", "text": "Fact text."}],
        "gt_documents": [{"doc_id": "d1"}],
        "gt_answer": "Answer",
        "gt_answers": ["Answer"],
    }
    response = {"knowledge_state": [
        {"rank": 1, "from_node_id": "n1", "doc_id": "d1",
         "facts": [{"fact_id": "f1", "text": "Fact text."}]}
    ]}
    results = compute_selected_metrics(
        ["recall"],
        query, response,
        generated_answer="Answer",
        available_metrics={"recall", "precision", "f1", "document_recall",
                           "exact_match", "token_overlap"},
    )
    assert "recall" in results
    assert results["recall"] == 1.0
    # Other metrics should NOT be in results.
    assert "precision" not in results
    assert "f1" not in results
    assert "exact_match" not in results


# --------------------------------------------------------------------------- #
# Test 10: Unsupported selected metric does not return fake zero
# --------------------------------------------------------------------------- #

def test_unsupported_metric_not_fake_zero():
    query = {"gt_answer": "A", "gt_answers": ["A"]}  # no facts
    response = {"knowledge_state": []}
    results = compute_selected_metrics(
        ["recall"],
        query, response,
        available_metrics=set(),  # recall not available
    )
    assert results["recall"] is None
    assert results.get("recall_unavailable") is True


# --------------------------------------------------------------------------- #
# Test 11: Example new metric/plugin works
# --------------------------------------------------------------------------- #

def test_token_overlap_metric_plugin():
    md = get_metric("token_overlap")
    assert md is not None
    assert md.category == "answer"
    assert "gt_answer" in md.required_fields

    query = {"gt_answer": "Paris is the capital", "gt_answers": ["Paris is the capital"]}
    response = {"knowledge_state": []}
    results = compute_selected_metrics(
        ["token_overlap"],
        query, response,
        generated_answer="The capital is Paris",
        available_metrics={"token_overlap"},
    )
    assert results["token_overlap"] is not None
    assert results["token_overlap"] > 0  # "paris", "capital" overlap

    # Can register a custom metric.
    def _custom(q, r, gen, judge, cfg):
        return 0.42

    register_metric(MetricDefinition(
        name="custom_test_metric",
        display_name="Custom Test",
        category="answer",
        required_fields=[],
        compute=_custom,
        description="Test metric.",
    ))
    assert get_metric("custom_test_metric") is not None
    res = compute_selected_metrics(
        ["custom_test_metric"], {}, {},
        available_metrics={"custom_test_metric"},
    )
    assert res["custom_test_metric"] == 0.42


# --------------------------------------------------------------------------- #
# Test 12: Dynamic metric results persist and reload from DB
# --------------------------------------------------------------------------- #

def test_dynamic_metrics_persist():
    repository.init_schema()

    # Create a run with selected metrics including token_overlap.
    run_id = create_run(
        "eu_ai_act_bench",
        run_name="pytest-dynamic-persist",
        provider="mock_local",
        selected_metrics=["recall", "precision", "f1", "token_overlap"],
    )
    run_evaluation(run_id, local_fn=build_response)

    # Check dynamic metrics persisted.
    dyn = repository.get_dynamic_metrics(run_id)
    assert len(dyn) > 0

    # token_overlap should be in there.
    metric_names = {d["metric_name"] for d in dyn}
    assert "token_overlap" in metric_names

    # Check per-query retrieval.
    first_qid = dyn[0]["query_id"]
    per_q = repository.get_dynamic_metrics_for_query(run_id, first_qid)
    assert "token_overlap" in per_q


# --------------------------------------------------------------------------- #
# Test 13: Dynamic metrics appear in exports
# --------------------------------------------------------------------------- #

def test_dynamic_metrics_in_exports():
    repository.init_schema()
    run_id = create_run(
        "eu_ai_act_bench",
        run_name="pytest-dynamic-export",
        provider="mock_local",
        selected_metrics=["recall", "token_overlap"],
    )
    run_evaluation(run_id, local_fn=build_response)
    paths = export_run(run_id)

    # Per-query CSV should contain token_overlap column.
    csv_path = paths["per_query_csv"]
    with open(csv_path, "r") as f:
        header = f.readline().strip()
    assert "token_overlap" in header

    # Per-query JSON should contain token_overlap.
    json_path = paths["per_query_json"]
    with open(json_path, "r") as f:
        data = json.load(f)
    assert any("token_overlap" in row for row in data)


# --------------------------------------------------------------------------- #
# Test 14: Two configured API systems create two separate runs
# --------------------------------------------------------------------------- #

def test_two_systems_create_two_runs():
    repository.init_schema()
    group_id = "cmp_test_group"

    rid_a = create_run(
        "eu_ai_act_bench",
        run_name="System A",
        provider="mock_local",
        comparison_group_id=group_id,
    )
    rid_b = create_run(
        "eu_ai_act_bench",
        run_name="System B",
        provider="mock_local",
        comparison_group_id=group_id,
    )

    assert rid_a != rid_b

    summary_a = run_evaluation(rid_a, local_fn=build_response)
    summary_b = run_evaluation(rid_b, local_fn=build_response)

    assert summary_a["status"] in ("completed", "partial")
    assert summary_b["status"] in ("completed", "partial")
    assert summary_a["total_queries"] == 32
    assert summary_b["total_queries"] == 32

    # Both runs should be in the same comparison group.
    group_runs = repository.get_runs_by_comparison_group(group_id)
    assert len(group_runs) == 2
    group_run_ids = {r["run_id"] for r in group_runs}
    assert rid_a in group_run_ids
    assert rid_b in group_run_ids


# --------------------------------------------------------------------------- #
# Test 15: Comparison analytics correctly compares two runs
# --------------------------------------------------------------------------- #

def test_comparison_analytics():
    repository.init_schema()
    group_id = "cmp_analytics_test"

    rid_a = create_run(
        "eu_ai_act_bench", run_name="Cmp-A", provider="mock_local",
        comparison_group_id=group_id,
    )
    rid_b = create_run(
        "eu_ai_act_bench", run_name="Cmp-B", provider="mock_local",
        comparison_group_id=group_id,
    )
    run_evaluation(rid_a, local_fn=build_response)
    run_evaluation(rid_b, local_fn=build_response)

    # Overall comparison.
    cmp = analytics_service.compare_runs(rid_a, rid_b)
    assert len(cmp) > 0
    metric_names = {r["metric"] for r in cmp}
    assert "recall" in metric_names
    assert "f1" in metric_names
    for row in cmp:
        assert row["run_a"] is not None
        assert row["run_b"] is not None
        if row["delta"] is not None:
            # Same mock -> delta should be 0.
            assert isinstance(row["delta"], (int, float))

    # Per-query comparison.
    pq_cmp = analytics_service.compare_runs_per_query(rid_a, rid_b)
    assert len(pq_cmp) == 32
    assert "query_id" in pq_cmp[0]
    assert "recall_a" in pq_cmp[0]
    assert "recall_b" in pq_cmp[0]

    # Comparison group summary.
    group_summary = analytics_service.comparison_group_summary(group_id)
    assert len(group_summary) == 2


# --------------------------------------------------------------------------- #
# Test 16: Existing MuSiQue ingestion still works
# --------------------------------------------------------------------------- #

def test_musique_ingestion_still_works():
    ds = load_dataset("data/musique_sample/dataset.json")
    assert ds.dataset_id == "musique_validation"
    assert len(ds.items) == 1000
    first = ds.items[0]
    assert first.query_id.startswith("2hop__")
    assert first.gt_supporting_facts
    assert first.gt_answers


# --------------------------------------------------------------------------- #
# Test 17: Existing HotpotQA ingestion still works
# --------------------------------------------------------------------------- #

def test_hotpotqa_ingestion_still_works():
    from app.ingestion.adapters.hotpotqa import HotpotQAAdapter

    hotpot_items = [
        {
            "_id": "hp_test_001",
            "question": "Were Scott and Ed the same?",
            "answer": "yes",
            "type": "comparison",
            "level": "hard",
            "supporting_facts": [["Scott", 0], ["Ed", 0]],
            "context": [
                ["Scott", ["Scott is American."]],
                ["Ed", ["Ed was American."]],
            ],
        },
    ]
    adapter = HotpotQAAdapter()
    assert adapter.can_handle(hotpot_items)
    internal = adapt(hotpot_items)
    ds = BenchmarkDataset.model_validate(internal)
    assert len(ds.items) == 1
    assert ds.items[0].gt_answer == "yes"
    assert ds.items[0].gt_supporting_facts


# --------------------------------------------------------------------------- #
# Test 18: mock_local evaluation still works
# --------------------------------------------------------------------------- #

def test_mock_local_evaluation_still_works():
    repository.init_schema()
    run_id = create_run(
        "eu_ai_act_bench",
        run_name="pytest-mock-local-v2",
        provider="mock_local",
    )
    summary = run_evaluation(run_id, local_fn=build_response)
    assert summary["status"] in ("completed", "partial")
    assert summary["provider"] == "mock_local"
    assert summary["total_queries"] == 32

    metrics = repository.get_query_metrics(run_id)
    assert len(metrics) == 32
    for m in metrics:
        assert "recall" in m
        assert "f1" in m
        assert "exact_match" in m


# --------------------------------------------------------------------------- #
# Additional: GT parse from bytes
# --------------------------------------------------------------------------- #

def test_gt_parse_from_bytes():
    gt_data = [
        {"query_id": "q1", "gt_answer": "Paris"},
        {"query_id": "q2", "gt_answer": "London"},
    ]
    raw = json.dumps(gt_data).encode("utf-8")
    records, errors = parse_ground_truth(raw, "gt.json")
    assert len(records) == 2
    assert not errors
    assert records[0]["query_id"] == "q1"

    # Bad JSON.
    _, errors2 = parse_ground_truth(b"not json", "bad.json")
    assert errors2

    # Missing query_id.
    bad_data = [{"gt_answer": "no id"}]
    records3, errors3 = parse_ground_truth(json.dumps(bad_data).encode(), "bad2.json")
    assert len(records3) == 0
    assert errors3
