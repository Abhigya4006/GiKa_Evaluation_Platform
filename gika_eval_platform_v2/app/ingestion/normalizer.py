
from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.dataset import BenchmarkDataset


def dataset_record(ds: BenchmarkDataset) -> Dict[str, Any]:
    return {
        "dataset_id": ds.dataset_id,
        "name": ds.name,
        "version": ds.version,
        "domain": ds.domain,
        "source": ds.source,
        "metric_config": ds.metric_config.model_dump(),
    }


def query_records(ds: BenchmarkDataset) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ds.items:
        records.append({
            "query_id": item.query_id,
            "query": item.query,
            "gt_answer": item.gt_answer,
            "gt_answers": list(item.gt_answers or []),
            "categories": list(item.categories),
            "difficulty": item.difficulty,
            "eval_label": item.eval_label,
            "metadata": dict(item.metadata),
            "gt_supporting_facts": [f.model_dump() for f in item.gt_supporting_facts],
            "gt_documents": [d.model_dump() for d in item.gt_documents],
        })
    return records


def leaderboard_records(ds: BenchmarkDataset) -> List[Dict[str, Any]]:
    return [e.model_dump() for e in ds.leaderboard]
