
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List

# Articles removed during normalization (SQuAD-style EM normalization).
_ARTICLES = {"a", "an", "the"}
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def new_run_id() -> str:
    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}_{uuid.uuid4().hex[:6]}"


def normalize_text(text: str | None, remove_articles: bool = True) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = _PUNCT_RE.sub(" ", t)
    tokens = _WS_RE.sub(" ", t).strip().split(" ")
    if remove_articles:
        tokens = [tok for tok in tokens if tok not in _ARTICLES]
    return " ".join(tok for tok in tokens if tok)


def tokenize(text: str | None) -> List[str]:
    norm = normalize_text(text)
    return norm.split(" ") if norm else []


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def write_json(path: str | Path, obj: Any, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, ensure_ascii=False, default=str)


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def round_or_none(value: float | None, ndigits: int = 4) -> float | None:
    return None if value is None else round(float(value), ndigits)
