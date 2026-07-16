
import csv
import io
import json

from app.db import repository
from app.ingestion.csv_loader import CSVMapping, parse_csv_to_dataset
from app.ingestion.parse import detect_format, parse_bytes
from app.services.run_service import ingest_from_object


def _csv_bytes(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode()


def test_detect_format_by_extension():
    assert detect_format("bench.json", b"{}") == "json"
    assert detect_format("bench.csv", b"a,b\n1,2\n") == "csv"
    assert detect_format("bench.tsv", b"a\tb\n") == "csv"


def test_detect_format_by_content_sniff():
    assert detect_format("noext", b"{\"a\":1}") == "json"
    assert detect_format("noext", b"col1,col2\n1,2\n") == "csv"


def test_csv_layout_a_one_row_per_query():
    raw = _csv_bytes([
        ["query_id", "query", "gt_answer", "categories", "difficulty",
         "gt_supporting_facts", "gt_documents"],
        ["q_01", "Q1?", "A1", "cat1", "easy",
         '[{"fact_id":"f1","text":"Fact 1","doc_id":"d1"}]',
         '[{"doc_id":"d1","filename":"f.pdf","page_numbers":[3]}]'],
        ["q_02", "Q2?", "A2", "cat2", "hard",
         '[{"fact_id":"f2","text":"Fact 2","doc_id":"d2"}]',
         '[{"doc_id":"d2","filename":"g.pdf","page_numbers":[7]}]'],
    ])
    r = parse_csv_to_dataset(raw, dataset_id="layout_a_test", name="A")
    assert len(r.dataset.items) == 2
    q1 = r.dataset.items[0]
    assert q1.query == "Q1?"
    assert q1.gt_answer == "A1"
    assert q1.difficulty == "easy"
    assert len(q1.gt_supporting_facts) == 1
    assert q1.gt_supporting_facts[0].fact_id == "f1"
    assert len(q1.gt_documents) == 1
    assert q1.gt_documents[0].page_numbers == [3]


def test_csv_layout_b_aggregates_by_query_id():
    raw = _csv_bytes([
        ["query_id", "query", "gt_answer", "difficulty",
         "fact_id", "fact_text", "fact_doc_id", "doc_id", "filename", "page_numbers"],
        ["q_01", "Q1?", "A1", "hard", "f1", "Fact 1a", "d1", "d1", "f.pdf", "3"],
        ["q_01", "Q1?", "A1", "hard", "f2", "Fact 1b", "d1", "d1", "f.pdf", "3"],
        ["q_02", "Q2?", "A2", "easy", "f3", "Fact 2",  "d2", "d2", "g.pdf", "1,2"],
    ])
    r = parse_csv_to_dataset(raw, dataset_id="layout_b_test", name="B")
    assert len(r.dataset.items) == 2
    q1 = next(i for i in r.dataset.items if i.query_id == "q_01")
    assert len(q1.gt_supporting_facts) == 2  # aggregated across the two rows
    assert {f.fact_id for f in q1.gt_supporting_facts} == {"f1", "f2"}
    assert len(q1.gt_documents) == 1  # de-duped across the two rows
    q2 = next(i for i in r.dataset.items if i.query_id == "q_02")
    assert q2.gt_documents[0].page_numbers == [1, 2]  # comma-separated pages parsed


def test_csv_column_mapping_renames_source_columns():
    raw = _csv_bytes([
        ["id", "question", "answer", "tags", "level", "fact"],
        ["q_01", "Why?", "because", "x,y", "easy", "the reason"],
    ])
    mapping = CSVMapping(
        query_id="id", query="question", gt_answer="answer",
        categories="tags", difficulty="level", fact_text="fact",
    )
    r = parse_csv_to_dataset(raw, dataset_id="mapped_test", name="Mapped", mapping=mapping)
    q = r.dataset.items[0]
    assert q.query == "Why?"
    assert q.gt_answer == "because"
    assert q.categories == ["x", "y"]
    assert q.difficulty == "easy"
    assert len(q.gt_supporting_facts) == 1
    assert q.gt_supporting_facts[0].text == "the reason"


def test_csv_auto_generates_query_id_when_missing():
    raw = _csv_bytes([
        ["query", "gt_answer", "difficulty"],
        ["First?", "A", "easy"],
        ["Second?", "B", "medium"],
    ])
    r = parse_csv_to_dataset(raw, dataset_id="autoid_test", name="Auto")
    assert len(r.dataset.items) == 2
    assert r.dataset.items[0].query_id == "autoid_test_q_0001"
    assert r.dataset.items[1].query_id == "autoid_test_q_0002"


def test_parse_bytes_json_path_overrides_dataset_id():
    payload = json.dumps({
        "dataset_id": "from_file",
        "name": "From File",
        "items": [{
            "query_id": "q1", "query": "Q?", "gt_answer": "A",
            "categories": [], "difficulty": "easy", "eval_label": "answerable",
            "gt_supporting_facts": [{"fact_id": "f1", "text": "t"}],
            "gt_documents": [],
        }],
    }).encode()
    ds, warnings = parse_bytes(payload, filename="x.json", dataset_id="renamed", name="Renamed")
    assert ds.dataset_id == "renamed"  # override applied
    assert ds.name == "Renamed"
    assert warnings == []


def test_parse_bytes_csv_requires_dataset_id():
    raw = _csv_bytes([["query", "gt_answer"], ["Q?", "A"]])
    try:
        parse_bytes(raw, filename="x.csv")
    except ValueError as exc:
        assert "dataset_id" in str(exc)
    else:
        raise AssertionError("expected ValueError when dataset_id is missing for CSV")


def test_ingest_from_object_persists_and_is_idempotent():
    raw = _csv_bytes([
        ["query_id", "query", "gt_answer", "difficulty",
         "fact_id", "fact_text", "fact_doc_id", "doc_id", "filename", "page_numbers"],
        ["u_01", "Uploaded?", "yes", "easy", "f1", "text 1", "d1", "d1", "f.pdf", "1"],
    ])
    ds, _ = parse_bytes(raw, filename="upload.csv", dataset_id="ui_upload_test", name="UI Test")
    ingest_from_object(ds)
    assert repository.get_dataset("ui_upload_test") is not None
    qs = repository.get_queries("ui_upload_test")
    assert len(qs) == 1
    assert qs[0]["query_id"] == "u_01"

    # Re-ingesting the same dataset must not create duplicates.
    ingest_from_object(ds)
    assert len(repository.get_queries("ui_upload_test")) == 1


def test_ingest_from_object_does_not_touch_sample_dataset():
    original = len(repository.get_queries("eu_ai_act_bench"))
    raw = _csv_bytes([["query", "gt_answer"], ["Q?", "A"]])
    ds, _ = parse_bytes(raw, filename="x.csv", dataset_id="isolation_test", name="Iso")
    ingest_from_object(ds)
    assert len(repository.get_queries("eu_ai_act_bench")) == original


def test_invalid_json_raises_clean_error():
    try:
        parse_bytes(b"not valid json {[", filename="broken.json")
    except ValueError as exc:
        assert "JSON" in str(exc) or "Invalid" in str(exc)
    else:
        raise AssertionError("expected ValueError on invalid JSON")


def test_csv_without_data_rows_raises():
    raw = _csv_bytes([["query_id", "query", "gt_answer"]])
    try:
        parse_csv_to_dataset(raw, dataset_id="empty", name="E")
    except ValueError as exc:
        assert "no data rows" in str(exc).lower() or "header" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for header-only CSV")


def test_query_id_collision_between_datasets_raises():
    # Ingest a small dataset with an explicit query_id.
    raw_a = _csv_bytes([
        ["query_id", "query", "gt_answer"],
        ["shared_qid", "Q from A?", "A"],
    ])
    ds_a, _ = parse_bytes(raw_a, filename="a.csv", dataset_id="collide_a", name="A")
    ingest_from_object(ds_a)

    # Attempt to ingest a second dataset that reuses the same query_id.
    raw_b = _csv_bytes([
        ["query_id", "query", "gt_answer"],
        ["shared_qid", "Q from B?", "B"],
    ])
    ds_b, _ = parse_bytes(raw_b, filename="b.csv", dataset_id="collide_b", name="B")
    try:
        ingest_from_object(ds_b)
    except ValueError as exc:
        assert "already used" in str(exc)
    else:
        raise AssertionError("expected ValueError on cross-dataset query_id collision")

    # Ensure dataset A survived intact.
    assert len(repository.get_queries("collide_a")) == 1
    assert repository.get_query("shared_qid")["dataset_id"] == "collide_a"
