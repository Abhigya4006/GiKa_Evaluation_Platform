
from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.utils import jaccard, normalize_text, tokenize

logger = get_logger(__name__)

_JUDGE_CACHE_DIRNAME = "judge_cache"


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #

class BaseJudge(ABC):

    name: str = "base"

    @abstractmethod
    def evaluate(
        self,
        question: str,
        generated_answer: str,
        gt_answers: List[str],
        retrieval_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def _cache_dir() -> Path:
    d = get_settings().project_root / "data" / _JUDGE_CACHE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(judge_id: str, question: str, gt_answers: List[str],
               generated_answer: str, model: str) -> str:
    payload = json.dumps({
        "judge": judge_id,
        "q": question,
        "a": sorted(gt_answers),
        "g": generated_answer,
        "m": model,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    p = _cache_dir() / f"{key}.json"
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    p = _cache_dir() / f"{key}.json"
    try:
        with p.open("w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("judge cache write failed: %s", exc)


# --------------------------------------------------------------------------- #
# HeuristicJudge
# --------------------------------------------------------------------------- #

def _verdict_from_score(score: float, pass_threshold: float) -> str:
    if score >= pass_threshold:
        return "correct"
    if score >= min(0.35, pass_threshold / 2):
        return "partial"
    return "incorrect"


class HeuristicJudge(BaseJudge):

    name = "heuristic"

    def __init__(self, pass_threshold: float = 0.7):
        self.pass_threshold = float(pass_threshold)

    def evaluate(
        self,
        question: str,
        generated_answer: str,
        gt_answers: List[str],
        retrieval_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        gt_answers = [a for a in (gt_answers or []) if a]
        if not gt_answers or not (generated_answer or "").strip():
            return self._result(0.0, "incorrect", "No answer or no ground truth.", cache_hit=False)

        # No cache lookup for the heuristic path — it's fast and deterministic.
        best_score = 0.0
        best_reason = ""
        gen_norm = normalize_text(generated_answer)
        gen_toks = set(tokenize(generated_answer))
        for gt in gt_answers:
            gt_norm = normalize_text(gt)
            if not gt_norm:
                continue
            # Substring signal (strong, high-precision).
            substring = 1.0 if gt_norm in gen_norm else 0.0
            # Token overlap signal (softer, catches paraphrases).
            gt_toks = set(tokenize(gt))
            overlap = jaccard(gen_toks, gt_toks)
            score = max(substring, overlap)
            if score > best_score:
                best_score = score
                if substring == 1.0:
                    best_reason = f"Contains the acceptable answer '{gt}'."
                else:
                    best_reason = (
                        f"Token overlap {overlap:.2f} vs acceptable answer '{gt}'."
                    )
        verdict = _verdict_from_score(best_score, self.pass_threshold)
        return self._result(best_score, verdict, best_reason or "No match.", cache_hit=False)

    def _result(self, score: float, verdict: str, rationale: str, cache_hit: bool) -> Dict[str, Any]:
        return {
            "score": round(float(score), 4),
            "verdict": verdict,
            "rationale": rationale,
            "judge": self.name,
            "cache_hit": cache_hit,
        }


# --------------------------------------------------------------------------- #
# HTTPLLMJudge
# --------------------------------------------------------------------------- #

class HTTPLLMJudge(BaseJudge):

    name = "llm"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        pass_threshold: float = 0.7,
    ):
        s = get_settings()
        self.endpoint = endpoint or s.llm_endpoint
        self.api_key = api_key or s.llm_api_key
        self.model = model or s.llm_model
        self.pass_threshold = float(pass_threshold)
        self._fallback = HeuristicJudge(pass_threshold=self.pass_threshold)

    def evaluate(
        self,
        question: str,
        generated_answer: str,
        gt_answers: List[str],
        retrieval_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        gt_answers = [a for a in (gt_answers or []) if a]
        if not self.endpoint or not self.api_key:
            return self._fallback.evaluate(question, generated_answer, gt_answers, retrieval_response)

        key = _cache_key(self.name, question, gt_answers, generated_answer, self.model)
        cached = _cache_get(key)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

        result = self._call_llm(question, generated_answer, gt_answers)
        if result is None:
            return self._fallback.evaluate(question, generated_answer, gt_answers, retrieval_response)

        _cache_put(key, result)
        return result

    def _call_llm(
        self, question: str, generated_answer: str, gt_answers: List[str]
    ) -> Optional[Dict[str, Any]]:
        prompt = _judge_prompt(question, generated_answer, gt_answers)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            import httpx  # type: ignore
            r = httpx.post(self.endpoint, json=body, headers=headers, timeout=30.0)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except ImportError:
            content = self._urllib_post(self.endpoint, body, headers)
            if content is None:
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM judge HTTP call failed: %s", exc)
            return None

        try:
            parsed = json.loads(content)
            score = float(parsed["score"])
            verdict = str(parsed.get("verdict") or _verdict_from_score(score, self.pass_threshold))
            rationale = str(parsed.get("rationale") or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM judge JSON parse failed: %s", exc)
            return None

        if not (0.0 <= score <= 1.0):
            logger.warning("LLM judge score %s out of [0,1]; clipping.", score)
            score = max(0.0, min(1.0, score))

        return {
            "score": round(score, 4),
            "verdict": verdict,
            "rationale": rationale,
            "judge": self.name,
            "cache_hit": False,
        }

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
                return payload["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM judge urllib call failed: %s", exc)
            return None


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

_JUDGE_SYSTEM = (
    "You are a strict grading assistant. You will be given a question, a "
    "candidate answer, and a list of acceptable ground-truth answers. Your "
    "job is to grade the candidate answer against the acceptable answers "
    "and reply with a JSON object of the form "
    "{\"score\": <0-1 float>, \"verdict\": \"correct|partial|incorrect\", "
    "\"rationale\": \"<one sentence>\"}. Do not add any prose outside the JSON."
)


def _judge_prompt(question: str, generated_answer: str, gt_answers: List[str]) -> str:
    accepted = "\n".join(f"  - {a}" for a in gt_answers) or "  (none provided)"
    return (
        f"Question:\n{question}\n\n"
        f"Candidate answer:\n{generated_answer or '(empty)'}\n\n"
        f"Acceptable answers (any of them is fully correct):\n{accepted}\n\n"
        "Grade the candidate answer. Return JSON only."
    )


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #

_JUDGES = {
    "heuristic": HeuristicJudge,
    "llm": HTTPLLMJudge,
}


def get_judge(name: Optional[str] = None) -> BaseJudge:
    s = get_settings()
    resolved = (name or s.judge or "heuristic").strip().lower()
    cls = _JUDGES.get(resolved, HeuristicJudge)
    return cls(pass_threshold=s.llm_judge_pass_threshold)
