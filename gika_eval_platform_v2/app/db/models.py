
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utcnow
from app.db.base import Base


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, default="1.0.0")
    domain: Mapped[str] = mapped_column(String, default="generic")
    source: Mapped[str] = mapped_column(String, default="internal-curated")
    metric_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    queries: Mapped[list["Query"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    leaderboard_entries: Mapped[list["LeaderboardEntry"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class Query(Base):
    __tablename__ = "queries"

    query_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    gt_answer: Mapped[str] = mapped_column(Text, default="")
    # V1: list of acceptable answers (MuSiQue-style multi-answer support).
    # JSON-serialized list[str]. Backfilled from ``gt_answer`` when only the
    # singular was provided (see repository.upsert_query / get_queries).
    gt_answers_json: Mapped[list] = mapped_column(JSON, default=list)
    categories_json: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String, default="medium", index=True)
    eval_label: Mapped[str] = mapped_column(String, default="answerable")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    dataset: Mapped["Dataset"] = relationship(back_populates="queries")
    supporting_facts: Mapped[list["SupportingFact"]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )
    supporting_documents: Mapped[list["SupportingDocument"]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )


class SupportingFact(Base):
    __tablename__ = "supporting_facts"

    # A GT fact_id may repeat across datasets, so the PK is a surrogate.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[str] = mapped_column(String, index=True)
    query_id: Mapped[str] = mapped_column(
        ForeignKey("queries.query_id", ondelete="CASCADE"), index=True
    )
    fact_text: Mapped[str] = mapped_column(Text, default="")
    doc_id: Mapped[str | None] = mapped_column(String, nullable=True)

    query: Mapped["Query"] = relationship(back_populates="supporting_facts")

    __table_args__ = (
        UniqueConstraint("query_id", "fact_id", name="uq_fact_query"),
    )


class SupportingDocument(Base):
    __tablename__ = "supporting_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String, index=True)
    query_id: Mapped[str] = mapped_column(
        ForeignKey("queries.query_id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    page_numbers_json: Mapped[list] = mapped_column(JSON, default=list)

    query: Mapped["Query"] = relationship(back_populates="supporting_documents")

    __table_args__ = (
        UniqueConstraint("query_id", "doc_id", name="uq_doc_query"),
    )


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"), index=True
    )
    system_name: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="leaderboard_entries")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"), index=True
    )
    dataset_version: Mapped[str] = mapped_column(String, default="", server_default="")
    run_name: Mapped[str] = mapped_column(String, default="", server_default="")
    provider: Mapped[str] = mapped_column(String, default="generic_http", server_default="generic_http", index=True)
    provider_config_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    api_endpoint: Mapped[str] = mapped_column(String, default="", server_default="")
    api_config_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    metric_config_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    selected_metrics_json: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    comparison_group_id: Mapped[str] = mapped_column(String, default="", server_default="")
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    total_queries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApiResponse(Base):
    __tablename__ = "api_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), index=True
    )
    query_id: Mapped[str] = mapped_column(String, index=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload_path: Mapped[str] = mapped_column(String, default="")
    retrieval_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Idempotent storage: one response per (run_id, query_id).
    __table_args__ = (
        UniqueConstraint("run_id", "query_id", name="uq_response_run_query"),
        Index("ix_response_run_query", "run_id", "query_id"),
    )


class QueryMetric(Base):
    __tablename__ = "query_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), index=True
    )
    query_id: Mapped[str] = mapped_column(String, index=True)

    recall: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    precision: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    f1: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    exact_match: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    document_recall: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

    # V1 LLM-as-Judge outputs (Directive Section 5.1).
    llm_judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_judge_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_judge_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # V1 answer-generation output (from the benchmarking module, not the
    # retrieval API — see Directive Section 3.2).
    generated_answer: Mapped[str] = mapped_column(Text, default="", server_default="")

    # ---- Deferred columns (V1 does not write to these) -----------------
    # Kept for backward compatibility with pre-V1 rows and so ranking-metric
    # support can be reactivated without a schema drop. See Directive
    # Section 5.2 and app/metrics/ranking.py.
    # NOTE: server_default is required so the SQLAlchemy DDL includes
    # DEFAULT in the column definition; without it, raw-SQL INSERTs that
    # omit these columns would violate NOT NULL.
    answerability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    ndcg: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    map_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    recall_at_1: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    recall_at_3: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    recall_at_5: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    recall_at_10: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

    success: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    failure_type: Mapped[str] = mapped_column(String, default="success", server_default="success", index=True)
    metric_details_json: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("run_id", "query_id", name="uq_metric_run_query"),
        Index("ix_metric_run_query", "run_id", "query_id"),
    )


class DynamicMetricResult(Base):
    __tablename__ = "dynamic_metric_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), index=True
    )
    query_id: Mapped[str] = mapped_column(String, index=True)
    metric_name: Mapped[str] = mapped_column(String, index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("run_id", "query_id", "metric_name", name="uq_dyn_metric_run_query_name"),
        Index("ix_dyn_metric_run_query", "run_id", "query_id"),
    )


class AggregatedResult(Base):
    __tablename__ = "aggregated_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), index=True
    )
    scope_type: Mapped[str] = mapped_column(String, index=True)   # overall|category|difficulty|failure_type
    scope_value: Mapped[str] = mapped_column(String, index=True)  # all|<category>|<difficulty>|<failure>
    metric_name: Mapped[str] = mapped_column(String, index=True)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint(
            "run_id", "scope_type", "scope_value", "metric_name",
            name="uq_agg_scope_metric",
        ),
        Index("ix_agg_run_scope", "run_id", "scope_type"),
    )
