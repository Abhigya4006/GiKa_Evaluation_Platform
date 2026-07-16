
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.compat import BaseModel, Field


class RunManifest(BaseModel):

    run_id: str
    dataset_id: str
    dataset_version: str
    api_endpoint: str
    api_config: Dict[str, Any] = Field(default_factory=dict)
    metric_config: Dict[str, Any] = Field(default_factory=dict)
    total_queries: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = "pending"


class QueryMetricResult(BaseModel):

    run_id: str
    query_id: str

    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0
    exact_match: float = 0.0
    semantic_similarity: Optional[float] = None
    document_recall: float = 0.0
    answerability_score: Optional[float] = None

    mrr: float = 0.0
    ndcg: float = 0.0
    map_score: float = 0.0

    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0

    success: bool = False
    failure_type: str = "success"
    metric_details: Dict[str, Any] = Field(default_factory=dict)


class AggregatedMetric(BaseModel):
    run_id: str
    scope_type: str          # overall | category | difficulty | failure_type
    scope_value: str         # e.g. "all", "temporal", "hard", "no_retrieval"
    metric_name: str
    metric_value: float
