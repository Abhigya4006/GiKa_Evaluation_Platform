
import json
import tempfile
from pathlib import Path

from app.db import repository
from app.ingestion.adapters import (
    HotpotQAAdapter,
    MusiqueAdapter,
    NativeAdapter,
    adapt,
    detect_adapter,
)
from app.ingestion.loader import load_dataset
from app.ingestion.parse import parse_bytes
from app.ingestion.validator import validate_dataset


# -------------------------------------------------------------------- #
# Fixtures — synthetic HotpotQA data written to temp files.
# -------------------------------------------------------------------- #

_HOTPOT_ITEMS = [
    {
        "_id": "hotpot_test_001",
        "question": "Were Scott Derrickson and Ed Wood of the same nationality?",
        "answer": "yes",
        "type": "comparison",
        "level": "hard",
        "supporting_facts": [["Scott Derrickson", 0], ["Ed Wood", 0]],
        "context": [
            ["Scott Derrickson", ["Scott Derrickson is an American director."]],
            ["Ed Wood", ["Edward Davis Wood Jr. was an American filmmaker."]],
            ["Adam Collis", ["Adam Collis is a Canadian-born screenwriter."]],
        ],
    },
    {
        "_id": "hotpot_test_002",
        "question": "What is the name of this Canadian-born screenwriter?",
        "answer": "Adam Collis",
        "type": "bridge",
        "level": "medium",
        "supporting_facts": [["Adam Collis", 0]],
        "context": [
            ["Adam Collis", ["Adam Collis is a Canadian-born screenwriter."]],
        ],
    },
]


def _write_temp_json(data) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump(data, f)
    f.close()
    return f.name


# -------------------------------------------------------------------- #
# Native + MuSiQue (existing, kept unchanged)
# -------------------------------------------------------------------- #


def test_native_adapter_handles_items_shape():
    ds = load_dataset("data/sample_dataset/dataset.json")
    assert ds.dataset_id == "eu_ai_act_bench"
    assert len(ds.items) == 32
    assert ds.items[0].gt_answers == [ds.items[0].gt_answer]


def test_musique_adapter_handles_musique_shape():
    ds = load_dataset("data/musique_sample/dataset.json")
    assert ds.dataset_id == "musique_validation"
    assert len(ds.items) == 1000
    first = ds.items[0]
    assert first.query_id.startswith("2hop__")
    assert "Tracy McConnell" in first.gt_answers
    assert first.gt_supporting_facts
    assert first.gt_supporting_facts[0].text
    assert first.categories == ["2hop"]
    assert first.metadata.get("hop_count") == 2


def test_musique_multi_answer_preserved():
    ds = load_dataset("data/musique_sample/dataset.json")
    for item in ds.items:
        if item.query_id == "2hop__67660_81007":
            assert set(item.gt_answers) >= {"Tracy McConnell", "The Mother"}
            break
    else:
        raise AssertionError("Expected test question not present in dataset")


# -------------------------------------------------------------------- #
# Adapter detection / dispatch
# -------------------------------------------------------------------- #


def test_adapter_detection_dispatch():
    native = {"items": [{"query_id": "q1", "query": "?"}]}
    assert isinstance(detect_adapter(native), NativeAdapter)

    musique = {"metadata": {}, "questions": {"q": {}}, "chunks": {}}
    assert isinstance(detect_adapter(musique), MusiqueAdapter)

    # HotpotQA — bare list
    assert isinstance(detect_adapter(_HOTPOT_ITEMS), HotpotQAAdapter)

    # HotpotQA — wrapped object
    assert isinstance(detect_adapter({"data": _HOTPOT_ITEMS}), HotpotQAAdapter)

    # Unknown shape
    assert detect_adapter({"totally_random": True}) is None


# -------------------------------------------------------------------- #
# HotpotQA adapter
# -------------------------------------------------------------------- #


def test_hotpotqa_bare_list():
    path = _write_temp_json(_HOTPOT_ITEMS)
    ds = load_dataset(path)
    assert ds.source == "hotpotqa"
    assert len(ds.items) == 2

    item = ds.items[0]
    assert item.query_id == "hotpot_test_001"
    assert item.gt_answers == ["yes"]
    assert item.categories == ["comparison"]
    assert item.difficulty == "hard"
    assert len(item.gt_supporting_facts) == 2
    assert item.gt_supporting_facts[0].text  # non-empty — resolved from context
    assert item.gt_supporting_facts[0].doc_id == "Scott Derrickson"
    assert len(item.gt_documents) == 2
    assert item.metadata.get("source_dataset_type") == "hotpotqa"
    assert item.metadata.get("question_type") == "comparison"
    assert "original_raw_item" in item.metadata


def test_hotpotqa_wrapped_object():
    path = _write_temp_json({"data": _HOTPOT_ITEMS})
    ds = load_dataset(path)
    assert ds.source == "hotpotqa"
    assert len(ds.items) == 2


def test_hotpotqa_no_context_degrades_gracefully():
    items = [{
        "_id": "no_ctx_001",
        "question": "Who is the director?",
        "answer": "Nobody",
        "type": "bridge",
        "level": "easy",
        "supporting_facts": [["Some Movie", 2]],
    }]
    path = _write_temp_json(items)
    ds = load_dataset(path)
    item = ds.items[0]
    assert item.gt_answers == ["Nobody"]
    assert len(item.gt_supporting_facts) == 1
    assert item.gt_supporting_facts[0].text == ""  # graceful degradation
    assert item.gt_supporting_facts[0].fact_id  # but fact_id is populated
    assert len(item.gt_documents) == 1


def test_hotpotqa_no_supporting_facts_answers_still_work():
    items = [{
        "_id": "minimal_001",
        "question": "Capital of France?",
        "answer": "Paris",
        "type": "simple",
        "level": "easy",
    }]
    path = _write_temp_json(items)
    ds = load_dataset(path)
    item = ds.items[0]
    assert item.gt_answers == ["Paris"]
    assert item.gt_supporting_facts == []  # empty, not an error
    assert item.gt_documents == []


def test_hotpotqa_dataset_id_override():
    internal = adapt(_HOTPOT_ITEMS, dataset_id_override="my_custom_id")
    assert internal["dataset_id"] == "my_custom_id"


def test_hotpotqa_upload_via_parse_bytes():
    raw = json.dumps(_HOTPOT_ITEMS).encode()
    ds, warnings = parse_bytes(raw, filename="hotpot.json", dataset_id="upload_hotpot")
    assert ds.dataset_id == "upload_hotpot"
    assert ds.source == "hotpotqa"
    assert len(ds.items) == 2
    assert warnings == []


# -------------------------------------------------------------------- #
# Persistence
# -------------------------------------------------------------------- #


def test_ingestion_persists_gt_answers():
    q = repository.get_query("q_0001")
    assert q is not None
    assert q["gt_answers"]
    musique_queries = repository.get_queries("musique_test_slice")
    assert len(musique_queries) == 5
    assert musique_queries[0]["gt_answers"]


def test_validator_runs():
    ds = load_dataset("data/sample_dataset/dataset.json")
    warnings = validate_dataset(ds)
    assert isinstance(warnings, list)
