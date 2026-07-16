
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import get_settings
from app.core.enums import ResponseStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetrievalClient:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout_s: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_base_s: Optional[float] = None,
        backoff_max_s: Optional[float] = None,
        local_fn=None,
    ) -> None:
        s = get_settings()
        self.endpoint = endpoint or s.retrieval_endpoint
        self.timeout_s = timeout_s if timeout_s is not None else s.request_timeout_s
        self.max_retries = max_retries if max_retries is not None else s.max_retries
        self.backoff_base_s = backoff_base_s if backoff_base_s is not None else s.backoff_base_s
        self.backoff_max_s = backoff_max_s if backoff_max_s is not None else s.backoff_max_s
        # Optional in-process function to bypass HTTP entirely (offline / tests).
        self.local_fn = local_fn

    def retrieve(self, request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        if self.local_fn is not None:
            try:
                resp = self.local_fn(
                    request["query_id"],
                    dataset_id=request.get("dataset_id"),
                )
                return resp, ResponseStatus.OK.value
            except TypeError:
                # Back-compat: older local_fn signatures that also accept
                # a max_nodes kwarg — pass the mock's cap through if present.
                try:
                    resp = self.local_fn(
                        request["query_id"],
                        max_nodes=int(request.get("mock_max_nodes", 10)),
                        dataset_id=request.get("dataset_id"),
                    )
                    return resp, ResponseStatus.OK.value
                except Exception as exc:  # noqa: BLE001
                    logger.error("local retrieval fn failed: %s", exc)
                    return {}, ResponseStatus.API_ERROR.value
            except Exception as exc:  # noqa: BLE001
                logger.error("local retrieval fn failed: %s", exc)
                return {}, ResponseStatus.API_ERROR.value

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._post(request)
                return resp, ResponseStatus.OK.value
            except TimeoutError as exc:
                last_err = exc
                status = ResponseStatus.TIMEOUT.value
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                status = ResponseStatus.API_ERROR.value

            if attempt < self.max_retries:
                delay = min(self.backoff_base_s * (2 ** attempt), self.backoff_max_s)
                logger.warning(
                    "retrieve attempt %d failed (%s); retrying in %.2fs",
                    attempt + 1, last_err, delay,
                )
                time.sleep(delay)

        logger.error("retrieve failed after %d attempts: %s", self.max_retries + 1, last_err)
        return {}, status  # type: ignore[possibly-undefined]

    def _post(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import httpx  # type: ignore

            r = httpx.post(self.endpoint, json=request, timeout=self.timeout_s)
            r.raise_for_status()
            return r.json()
        except ImportError:
            return self._post_urllib(request)

    def _post_urllib(self, request: Dict[str, Any]) -> Dict[str, Any]:
        import urllib.error
        import urllib.request

        data = json.dumps(request).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise TimeoutError(str(exc)) from exc
            raise
