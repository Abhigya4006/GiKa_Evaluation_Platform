
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ANSWER_CACHE_DIRNAME = "answer_cache"


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #

class BaseGenerator(ABC):

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        query: str,
        retrieval_response: Dict[str, Any],
        gt_answer: str = "",
    ) -> str:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Extractive fallback
# --------------------------------------------------------------------------- #

_FILLER_PATTERNS = (
    "supplementary context detail",
    "loosely related statement",
    "off-topic content",
    "completely unrelated content",
    "this content is unrelated",
)


def _is_filler(text: str) -> bool:
    lower = (text or "").lower()
    return any(p in lower for p in _FILLER_PATTERNS)


class ExtractiveGenerator(BaseGenerator):

    name = "extractive"

    def generate(
        self,
        query: str,
        retrieval_response: Dict[str, Any],
        gt_answer: str = "",
    ) -> str:
        knowledge_state = retrieval_response.get("knowledge_state", []) or []
        if not knowledge_state:
            return "No relevant information was retrieved to answer this question."

        sorted_nodes = sorted(
            knowledge_state,
            key=lambda n: float(n.get("node_score", 0) or 0),
            reverse=True,
        )
        seen: set = set()
        fact_texts: List[str] = []
        for node in sorted_nodes:
            for fact in node.get("facts", []) or []:
                text = (fact.get("text", "") or "").strip()
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                fact_texts.append(text)

        if not fact_texts:
            return "Retrieved nodes contained no factual content."
        if len(fact_texts) == 1:
            return fact_texts[0]

        informative = [t for t in fact_texts if not _is_filler(t)]
        if not informative:
            informative = fact_texts[:1]
        return " ".join(informative)


# --------------------------------------------------------------------------- #
# HTTP LLM generator
# --------------------------------------------------------------------------- #

_GENERATOR_SYSTEM = (
    "You are a careful question-answering assistant. You will be given a "
    "question and a set of retrieved facts. Answer the question using only "
    "the retrieved facts. Reply with a concise answer — no prefaces, no "
    "citations, no meta commentary. If the facts do not support an answer, "
    "reply exactly: I don't know."
)


def _cache_dir() -> Path:
    d = get_settings().project_root / "data" / _ANSWER_CACHE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(model: str, prompt: str) -> str:
    payload = json.dumps({"m": model, "p": prompt}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    p = _cache_dir() / f"{key}.json"
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh).get("answer")
    except Exception:  # noqa: BLE001
        return None


def _cache_put(key: str, answer: str) -> None:
    p = _cache_dir() / f"{key}.json"
    try:
        with p.open("w", encoding="utf-8") as fh:
            json.dump({"answer": answer}, fh, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("answer cache write failed: %s", exc)


def _build_prompt(query: str, retrieval_response: Dict[str, Any]) -> str:
    lines: List[str] = ["Retrieved facts:"]
    seen: set = set()
    for node in retrieval_response.get("knowledge_state", []) or []:
        for fact in node.get("facts", []) or []:
            text = (fact.get("text", "") or "").strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            lines.append(f"- {text}")
    if len(lines) == 1:
        lines.append("- (no facts retrieved)")
    lines.append("")
    lines.append(f"Question: {query}")
    lines.append("Answer:")
    return "\n".join(lines)


class HTTPLLMGenerator(BaseGenerator):

    name = "llm"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        s = get_settings()
        self.endpoint = endpoint or s.llm_endpoint
        self.api_key = api_key or s.llm_api_key
        self.model = model or s.llm_model
        self._fallback = ExtractiveGenerator()

    def generate(
        self,
        query: str,
        retrieval_response: Dict[str, Any],
        gt_answer: str = "",
    ) -> str:
        if not self.endpoint or not self.api_key:
            return self._fallback.generate(query, retrieval_response, gt_answer)

        prompt = _build_prompt(query, retrieval_response)
        key = _cache_key(self.model, prompt)
        cached = _cache_get(key)
        if cached is not None:
            return cached

        answer = self._call_llm(prompt)
        if answer is None:
            return self._fallback.generate(query, retrieval_response, gt_answer)

        _cache_put(key, answer)
        return answer

    def _call_llm(self, prompt: str) -> Optional[str]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _GENERATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            import httpx  # type: ignore
            r = httpx.post(self.endpoint, json=body, headers=headers, timeout=30.0)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except ImportError:
            return self._urllib_post(self.endpoint, body, headers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM generator HTTP call failed: %s", exc)
            return None

    @staticmethod
    def _urllib_post(url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Optional[str]:
        import urllib.error
        import urllib.request
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return payload["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM generator urllib call failed: %s", exc)
            return None


# Back-compat alias so older tests / callers still work.
LLMGenerator = HTTPLLMGenerator


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #

_GENERATORS = {
    "extractive": ExtractiveGenerator,
    "llm": HTTPLLMGenerator,
}


def get_generator(name: Optional[str] = None, **kwargs) -> BaseGenerator:
    s = get_settings()
    resolved = (name or s.answer_generator or "extractive").strip().lower()
    cls = _GENERATORS.get(resolved, ExtractiveGenerator)
    return cls(**kwargs) if kwargs else cls()
