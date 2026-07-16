
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from app.core.enums import ResponseStatus


@dataclass
class ProviderConfig:

    endpoint: Optional[str] = None
    timeout_s: float = 15.0
    max_retries: int = 3
    backoff_base_s: float = 0.5
    backoff_max_s: float = 8.0
    auth: Dict[str, Any] = field(default_factory=dict)     # e.g. {"bearer_token": "..."}
    headers: Dict[str, str] = field(default_factory=dict)  # extra headers to send
    extra: Dict[str, Any] = field(default_factory=dict)    # provider-specific knobs

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ProviderConfig":
        data = data or {}
        # V1: silently drop any legacy top_k passed in via config JSON.
        # It has no effect on the request payload; we only preserve it as a
        # provider-local cap by folding it into extras.mock_max_nodes so
        # existing runbooks that set top_k still bound the mock's output.
        extra = dict(data.get("extra", {}))
        if "top_k" in data and "mock_max_nodes" not in extra:
            try:
                extra["mock_max_nodes"] = int(data["top_k"])
            except (TypeError, ValueError):
                pass
        return cls(
            endpoint=data.get("endpoint"),
            timeout_s=float(data.get("timeout_s", 15.0)),
            max_retries=int(data.get("max_retries", 3)),
            backoff_base_s=float(data.get("backoff_base_s", 0.5)),
            backoff_max_s=float(data.get("backoff_max_s", 8.0)),
            auth=dict(data.get("auth", {})),
            headers=dict(data.get("headers", {})),
            extra=extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "timeout_s": self.timeout_s,
            "max_retries": self.max_retries,
            "backoff_base_s": self.backoff_base_s,
            "backoff_max_s": self.backoff_max_s,
            "auth": dict(self.auth),
            "headers": dict(self.headers),
            "extra": dict(self.extra),
        }


class BaseProvider:

    #: Human-readable provider id (also the value stored in evaluation_runs.provider).
    name: str = "base"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    # ---- primitives subclasses implement -------------------------------- #

    def build_request(
        self, query_text: str, query_id: str, dataset_id: Optional[str]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def call(self, request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        raise NotImplementedError

    def normalize(self, raw: Dict[str, Any], query_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    # ---- convenience orchestrator (do not override) --------------------- #

    def retrieve(
        self, query_text: str, query_id: str, dataset_id: Optional[str]
    ) -> Tuple[Dict[str, Any], str]:
        request = self.build_request(query_text, query_id, dataset_id)
        raw, transport_status = self.call(request)

        if transport_status != ResponseStatus.OK.value:
            return self._empty_canonical(query_id), transport_status

        try:
            canonical = self.normalize(raw, query_id)
        except Exception:  # noqa: BLE001
            return self._empty_canonical(query_id), ResponseStatus.INVALID.value

        if not isinstance(canonical, dict) or "knowledge_state" not in canonical:
            return self._empty_canonical(query_id), ResponseStatus.INVALID.value

        return canonical, ResponseStatus.OK.value

    @staticmethod
    def _empty_canonical(query_id: str) -> Dict[str, Any]:
        return {
            "query_id": query_id,
            "knowledge_state": [],
            "confidence": 0.0,
            "exploration_time": 0.0,
            "answerable": False,
            "retrieval_time_ms": 0,
            "retrieval_strategy": "unknown",
            "extras": {},
        }

