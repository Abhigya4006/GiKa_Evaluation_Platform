
import os
import tempfile

import pytest

# Point the DB at a temp file BEFORE app modules read settings.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["GIKA_DB_URL"] = f"sqlite:///{_tmp.name}"


@pytest.fixture(scope="session", autouse=True)
def _init_and_seed():
    from app.db.init_db import init_db
    from app.services.run_service import ingest_dataset
    init_db(drop=True)
    # Ingest the 32-item native-shape sample explicitly (tests keep O(seconds)).
    ingest_dataset("data/sample_dataset/dataset.json")
    # Also ingest a tiny slice of the MuSiQue file so we exercise the
    # MusiqueAdapter code path in tests without paying the 1000-item cost.
    _ingest_musique_sample()
    yield
    try:
        os.unlink(_tmp.name)
    except OSError:
        pass


def _ingest_musique_sample() -> None:
    import json
    from pathlib import Path

    from app.ingestion.adapters import adapt
    from app.schemas.dataset import BenchmarkDataset
    from app.services.run_service import ingest_from_object

    p = Path("data/musique_sample/dataset.json")
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    # Trim to first 5 questions to keep the test DB small.
    qids = list(raw.get("questions", {}).keys())[:5]
    raw = {
        "metadata": raw.get("metadata", {}),
        "questions": {k: raw["questions"][k] for k in qids},
        "chunks": raw.get("chunks", {}),
    }
    internal = adapt(raw, dataset_id_override="musique_test_slice",
                     name_override="MuSiQue (test slice)")
    ds = BenchmarkDataset.model_validate(internal)
    ingest_from_object(ds)
