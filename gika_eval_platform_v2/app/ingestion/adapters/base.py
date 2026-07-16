
from __future__ import annotations

from typing import Any, Dict


class BaseAdapter:

    #: Short adapter id (used only for logging).
    name: str = "base"

    def can_handle(self, raw: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def to_internal(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
