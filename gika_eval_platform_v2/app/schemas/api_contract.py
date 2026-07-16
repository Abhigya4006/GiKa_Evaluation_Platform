
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.compat import BaseModel, Field, model_validator


class GraphConfig(BaseModel):
    graph_id: str = ""
    tenant_id: str = ""
    neo4j_database_name: str = ""


class RetrieveRequest(BaseModel):
    query: str = ""
    query_id: str = ""
    graph_configs: List[GraphConfig] = Field(default_factory=list)
    chat_subscription_id: str = ""

    # Non-wire helper: convenience for the mock provider so it knows which
    # ingested dataset to look up GT facts from. Never sent to a real
    # HTTP endpoint (the generic_http provider strips it).
    dataset_id: Optional[str] = None


class RetrievedFact(BaseModel):
    # fact_id may be null when the retrieval system emits a fact it can't map
    # back to a canonical GT fact.
    fact_id: Optional[str] = None
    text: str = ""


class KnowledgeNode(BaseModel):
    rank: int = 0
    from_node_id: str = ""
    from_label: str = ""
    node_score: float = 0.0
    doc_id: Optional[str] = None
    filename: Optional[str] = None
    page_numbers: List[int] = Field(default_factory=list)
    facts: List[RetrievedFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coerce_facts(self) -> "KnowledgeNode":
        coerced: List[RetrievedFact] = []
        for f in self.facts or []:
            if isinstance(f, RetrievedFact):
                coerced.append(f)
            elif isinstance(f, dict):
                coerced.append(RetrievedFact.model_validate(f))
        self.facts = coerced
        return self


class RetrieveResponse(BaseModel):
    query_id: str = ""
    knowledge_state: List[KnowledgeNode] = Field(default_factory=list)

    # V1 envelope fields returned by the real GIKA endpoint.
    confidence: float = 0.0
    exploration_time: float = 0.0  # seconds (V1 field name)

    # Convenience mirrors kept for the internal evaluator; ``retrieval_time_ms``
    # is derived from ``exploration_time`` when not supplied directly.
    answerable: bool = False
    retrieval_time_ms: int = 0
    retrieval_strategy: str = "unknown"

    # Preserved extra graph metadata that the real API may include — kept as
    # opaque extras so we don't lose information downstream.
    extras: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coerce_nodes(self) -> "RetrieveResponse":
        coerced: List[KnowledgeNode] = []
        for n in self.knowledge_state or []:
            if isinstance(n, KnowledgeNode):
                coerced.append(n)
            elif isinstance(n, dict):
                coerced.append(KnowledgeNode.model_validate(n))
        self.knowledge_state = coerced
        # Derive retrieval_time_ms from exploration_time (V1 field name) when
        # the ms field wasn't provided.
        if not self.retrieval_time_ms and self.exploration_time:
            self.retrieval_time_ms = int(float(self.exploration_time) * 1000)
        return self


def _unused(_: Any) -> None:  # keep Any import referenced for linters
    return None

