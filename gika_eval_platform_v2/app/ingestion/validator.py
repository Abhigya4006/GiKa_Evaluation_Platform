
from __future__ import annotations

from typing import List

from app.schemas.dataset import BenchmarkDataset


def validate_dataset(ds: BenchmarkDataset) -> List[str]:
    warnings: List[str] = []

    for item in ds.items:
        declared_docs = {d.doc_id for d in item.gt_documents}

        # Answerable queries should have at least one supporting fact.
        if item.eval_label == "answerable" and not item.gt_supporting_facts:
            warnings.append(f"{item.query_id}: answerable but has no supporting facts")

        # Facts referencing a doc not declared in gt_documents.
        for f in item.gt_supporting_facts:
            if f.doc_id and declared_docs and f.doc_id not in declared_docs:
                warnings.append(
                    f"{item.query_id}: fact {f.fact_id} references undeclared doc {f.doc_id}"
                )

        # Empty query text.
        if not item.query.strip():
            warnings.append(f"{item.query_id}: empty query text")

    return warnings
