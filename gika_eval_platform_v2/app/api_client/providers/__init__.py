
from __future__ import annotations

from typing import Dict, List, Optional, Type

from app.api_client.base import BaseProvider, ProviderConfig
from app.api_client.providers.generic_http import GenericHTTPProvider
from app.api_client.providers.gika_retrieve import GikaRetrieveProvider
from app.api_client.providers.mock_local import MockLocalProvider

PROVIDERS: Dict[str, Type[BaseProvider]] = {
    MockLocalProvider.name: MockLocalProvider,
    GenericHTTPProvider.name: GenericHTTPProvider,
    GikaRetrieveProvider.name: GikaRetrieveProvider,
}

# Default when a run row has no provider recorded (backward compatibility).
DEFAULT_PROVIDER = GenericHTTPProvider.name


def available_providers() -> List[str]:
    return list(PROVIDERS.keys())


def get_provider(name: Optional[str], config: Optional[ProviderConfig] = None) -> BaseProvider:
    key = (name or DEFAULT_PROVIDER).strip().lower()
    cls = PROVIDERS.get(key) or PROVIDERS[DEFAULT_PROVIDER]
    return cls(config or ProviderConfig())


__all__ = [
    "PROVIDERS",
    "DEFAULT_PROVIDER",
    "available_providers",
    "get_provider",
    "BaseProvider",
    "ProviderConfig",
]
