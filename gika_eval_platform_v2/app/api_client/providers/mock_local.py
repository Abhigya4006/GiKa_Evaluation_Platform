
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.api_client.base import BaseProvider, ProviderConfig
from app.api_client.mock_api import build_response
from app.core.enums import ResponseStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_MOCK_MAX_NODES = 10


class MockLocalProvider(BaseProvider):
    name = "mock_local"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)

    def build_request(
        self, query_text: str, query_id: str, dataset_id: Optional[str]
    ) -> Dict[str, Any]:
        req: Dict[str, Any] = {
            "query": query_text,
            "query_id": query_id,
            "dataset_id": dataset_id,
            "mock_max_nodes": int(self.config.extra.get(
                "mock_max_nodes", _DEFAULT_MOCK_MAX_NODES
            )),
        }
        # Preserve graph_configs / chat_subscription_id if set, so the raw
        # stored payload accurately reflects what a real call would look
        # like when we later swap to the HTTP provider.
        gc = self.config.extra.get("graph_configs")
        if gc:
            req["graph_configs"] = gc
        cs = self.config.extra.get("chat_subscription_id")
        if cs:
            req["chat_subscription_id"] = cs
        return req

    def call(self, request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        try:
            payload = build_response(
                request["query_id"],
                max_nodes=int(request.get("mock_max_nodes", _DEFAULT_MOCK_MAX_NODES)),
                dataset_id=request.get("dataset_id"),
            )
            return payload, ResponseStatus.OK.value
        except Exception as exc:  # noqa: BLE001
            logger.error("mock_local retrieval failed: %s", exc)
            return {}, ResponseStatus.API_ERROR.value

    def normalize(self, raw: Dict[str, Any], query_id: str) -> Dict[str, Any]:
        # Delegate to the generic HTTP normalizer for identical semantics.
        from app.api_client.providers.generic_http import GenericHTTPProvider
        return GenericHTTPProvider(self.config).normalize(raw, query_id)
