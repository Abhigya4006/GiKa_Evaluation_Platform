
from __future__ import annotations

from typing import Any, Dict, Optional

from app.api_client.providers.generic_http import GenericHTTPProvider


# Default chat_subscription_id if the caller didn't set one. Chosen to match
# the example in Section 4.1 of the V1 directive.
_DEFAULT_CHAT_SUB = "gpt-5-mini"


class GikaRetrieveProvider(GenericHTTPProvider):

    name = "gika_retrieve"

    # ---- build_request -------------------------------------------------- #

    def build_request(
        self, query_text: str, query_id: str, dataset_id: Optional[str]
    ) -> Dict[str, Any]:
        graph_configs = self.config.extra.get("graph_configs")
        if not graph_configs:
            raise ValueError(
                "gika_retrieve provider requires provider_config.extra."
                "graph_configs to be set (list of {graph_id, tenant_id, "
                "neo4j_database_name})."
            )
        chat_sub = self.config.extra.get("chat_subscription_id") or _DEFAULT_CHAT_SUB
        return {
            "query": query_text,
            "query_id": query_id,
            "graph_configs": graph_configs,
            "chat_subscription_id": chat_sub,
        }

    # ---- normalize ------------------------------------------------------ #

    # Inherits GenericHTTPProvider.normalize, which already handles the V1
    # response envelope (knowledge_state, confidence, exploration_time,
    # extras). Override here if GIKA's response shape diverges (e.g. wraps
    # facts as {"chunk_id", "content"} instead of {"fact_id", "text"}).
