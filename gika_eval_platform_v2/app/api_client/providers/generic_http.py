
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.api_client.base import BaseProvider, ProviderConfig
from app.api_client.client import RetrievalClient
from app.core.enums import ResponseStatus


# Reserved response envelope fields. Everything else is preserved on the
# canonical response's ``extras`` dict.
_RESERVED_ENVELOPE_KEYS = {
    "query_id",
    "knowledge_state",
    "confidence",
    "exploration_time",
    "retrieval_time_ms",
    "answerable",
    "retrieval_strategy",
}


class GenericHTTPProvider(BaseProvider):
    name = "generic_http"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = RetrievalClient(
            endpoint=config.endpoint,
            timeout_s=config.timeout_s,
            max_retries=config.max_retries,
            backoff_base_s=config.backoff_base_s,
            backoff_max_s=config.backoff_max_s,
        )
        # Optional bearer token / extra headers.
        self._headers: Dict[str, str] = dict(config.headers or {})
        bearer = (config.auth or {}).get("bearer_token")
        if bearer:
            self._headers["Authorization"] = f"Bearer {bearer}"
        self._client.extra_headers = self._headers  # type: ignore[attr-defined]

    # ---- build_request -------------------------------------------------- #

    def build_request(
        self, query_text: str, query_id: str, dataset_id: Optional[str]
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "query": query_text,
            "query_id": query_id,
        }
        graph_configs = self.config.extra.get("graph_configs")
        if graph_configs:
            request["graph_configs"] = graph_configs
        chat_sub = self.config.extra.get("chat_subscription_id")
        if chat_sub:
            request["chat_subscription_id"] = chat_sub
        return request

    # ---- call ----------------------------------------------------------- #

    def call(self, request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        return self._client.retrieve(request)

    # ---- normalize ------------------------------------------------------ #

    def normalize(self, raw: Dict[str, Any], query_id: str) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return BaseProvider._empty_canonical(query_id)

        ks = raw.get("knowledge_state", []) or []
        fixed_nodes: List[Dict[str, Any]] = []
        for i, node in enumerate(ks):
            if not isinstance(node, dict):
                continue
            facts_raw = node.get("facts", []) or []
            facts_norm: List[Dict[str, Any]] = []
            for f in facts_raw:
                if isinstance(f, str):
                    facts_norm.append({"fact_id": None, "text": f})
                elif isinstance(f, dict):
                    facts_norm.append({
                        "fact_id": f.get("fact_id"),
                        "text": f.get("text", ""),
                    })
            fixed = {
                "rank": int(node.get("rank", i + 1)),
                "from_node_id": node.get("from_node_id", f"node_{i+1}"),
                "from_label": node.get("from_label", ""),
                "node_score": float(node.get("node_score", 0.0) or 0.0),
                "doc_id": node.get("doc_id"),
                "filename": node.get("filename"),
                "page_numbers": list(node.get("page_numbers", []) or []),
                "facts": facts_norm,
            }
            fixed_nodes.append(fixed)

        # Import the schema lazily so metric modules don't need it to import.
        from app.schemas.api_contract import RetrieveResponse

        exploration_time = float(raw.get("exploration_time", 0.0) or 0.0)
        ret_ms = int(raw.get("retrieval_time_ms", 0) or 0)
        if not ret_ms and exploration_time:
            ret_ms = int(exploration_time * 1000)

        # Preserve any unknown envelope fields so real-API metadata isn't lost.
        extras = {k: v for k, v in raw.items() if k not in _RESERVED_ENVELOPE_KEYS}

        payload = {
            "query_id": raw.get("query_id", query_id),
            "knowledge_state": fixed_nodes,
            "confidence": float(raw.get("confidence", 0.0) or 0.0),
            "exploration_time": exploration_time,
            "answerable": bool(raw.get("answerable", False)),
            "retrieval_time_ms": ret_ms,
            "retrieval_strategy": raw.get("retrieval_strategy", "unknown"),
            "extras": extras,
        }
        return RetrieveResponse.model_validate(payload).model_dump()


# ------------------------------------------------------------------------- #
# Small extension to RetrievalClient: honour extra_headers if set.
# Monkey-patched here to avoid modifying the (working) client module directly.
# ------------------------------------------------------------------------- #

def _patch_client_headers() -> None:
    import json as _json
    import urllib.error
    import urllib.request

    def _post(self: RetrievalClient, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import httpx  # type: ignore

            r = httpx.post(
                self.endpoint,
                json=request,
                headers=getattr(self, "extra_headers", None) or None,
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            return r.json()
        except ImportError:
            return _post_urllib(self, request)

    def _post_urllib(self: RetrievalClient, request: Dict[str, Any]) -> Dict[str, Any]:
        data = _json.dumps(request).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers.update(getattr(self, "extra_headers", None) or {})
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return _json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise TimeoutError(str(exc)) from exc
            raise

    RetrievalClient._post = _post           # type: ignore[assignment]
    RetrievalClient._post_urllib = _post_urllib  # type: ignore[assignment]


_patch_client_headers()
_ = ResponseStatus  # keep import referenced
