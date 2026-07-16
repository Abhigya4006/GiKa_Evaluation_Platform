
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.compat import BaseModel, Field, model_validator


class SupportingFact(BaseModel):
    fact_id: str = ""
    text: str = ""
    doc_id: Optional[str] = None


class SupportingDocument(BaseModel):
    doc_id: str = ""
    filename: Optional[str] = None
    page_numbers: List[int] = Field(default_factory=list)


class LeaderboardEntry(BaseModel):
    system_name: str = ""
    metric: str = ""
    value: float = 0.0


class MetricConfig(BaseModel):

    # DEFERRED (V1): not consumed by V1 metrics. See Section 5.2 of the V1
    # directive and the ``ranking`` module docstring for reactivation notes.
    recall_at_k: List[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    em_normalize: bool = True

    model_config = {"extra": "allow"}


def _coerce_list(raw: Any, model: type) -> List[Any]:
    out: List[Any] = []
    for entry in raw or []:
        if isinstance(entry, model):
            out.append(entry)
        elif isinstance(entry, dict):
            out.append(model.model_validate(entry))
    return out


class DatasetItem(BaseModel):
    query_id: str = ""
    query: str = ""
    # ``gt_answer`` is the primary/canonical answer string (back-compat).
    # ``gt_answers`` is the full list of acceptable answers — populated by
    # adapters for datasets like MuSiQue that ship multiple valid answers
    # (e.g. ["Tracy McConnell", "The Mother"]). Metrics that need to accept
    # any of the alternatives (EM, judge) prefer this list; if it's empty,
    # they fall back to a one-element list containing ``gt_answer``.
    gt_answer: str = ""
    gt_answers: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    difficulty: str = "medium"
    eval_label: str = "answerable"
    gt_supporting_facts: List[SupportingFact] = Field(default_factory=list)
    gt_documents: List[SupportingDocument] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coerce(self) -> "DatasetItem":
        self.difficulty = (self.difficulty or "medium").strip().lower()
        self.gt_supporting_facts = _coerce_list(self.gt_supporting_facts, SupportingFact)
        self.gt_documents = _coerce_list(self.gt_documents, SupportingDocument)
        # Backfill gt_answers from gt_answer when only the singular was supplied,
        # so downstream code can always treat gt_answers as the source of truth.
        if not self.gt_answers and self.gt_answer:
            self.gt_answers = [self.gt_answer]
        # Backfill gt_answer from the first gt_answers entry when only the list
        # was supplied.
        if not self.gt_answer and self.gt_answers:
            self.gt_answer = self.gt_answers[0]
        return self


class BenchmarkDataset(BaseModel):
    dataset_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    domain: str = "generic"
    source: str = "internal-curated"
    metric_config: MetricConfig = Field(default_factory=MetricConfig)
    leaderboard: List[LeaderboardEntry] = Field(default_factory=list)
    items: List[DatasetItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_consistency(self) -> "BenchmarkDataset":
        if isinstance(self.metric_config, dict):
            self.metric_config = MetricConfig.model_validate(self.metric_config)
        self.leaderboard = _coerce_list(self.leaderboard, LeaderboardEntry)
        self.items = _coerce_list(self.items, DatasetItem)

        if not self.items:
            raise ValueError("Dataset must contain at least one item.")

        seen = set()
        for item in self.items:
            if item.query_id in seen:
                raise ValueError(f"Duplicate query_id detected: {item.query_id}")
            seen.add(item.query_id)
        return self
