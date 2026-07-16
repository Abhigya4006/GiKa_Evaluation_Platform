
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.compat import BaseModel, Field


class RunSummary(BaseModel):
    run_id: str
    dataset_id: str
    dataset_version: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_queries: int = 0
    overall_metrics: Dict[str, float] = Field(default_factory=dict)
    success_rate: float = 0.0
    failure_counts: Dict[str, int] = Field(default_factory=dict)


class QueryDetail(BaseModel):
    query_id: str
    query_text: str
    gt_answer: str = ""
    categories: List[str] = Field(default_factory=list)
    difficulty: str = ""
    gt_facts: List[Dict[str, Any]] = Field(default_factory=list)
    gt_documents: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    failure_type: str = "success"
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class LeaderboardComparisonRow(BaseModel):
    metric: str
    current_run: Optional[float] = None
    leaderboard: Optional[float] = None
    system_name: Optional[str] = None
    gap: Optional[float] = None
