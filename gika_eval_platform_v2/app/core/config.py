
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

# Project root = two levels up from this file (app/core/config.py -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
METRICS_FILE = CONFIG_DIR / "metrics.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


class Settings:

    def __init__(self) -> None:
        raw = _load_yaml(SETTINGS_FILE)
        metrics = _load_yaml(METRICS_FILE)

        self.app_name: str = raw.get("app_name", "GIKA Eval Platform")
        self.env: str = raw.get("env", "local")

        # DB
        self.db_url: str = os.getenv("GIKA_DB_URL", raw.get("db_url", "sqlite:///./data/gika_eval.db"))

        # Mock API
        self.mock_api_host: str = os.getenv("GIKA_MOCK_API_HOST", raw.get("mock_api_host", "127.0.0.1"))
        self.mock_api_port: int = int(os.getenv("GIKA_MOCK_API_PORT", raw.get("mock_api_port", 8000)))

        # Retrieval endpoint
        self.retrieval_endpoint: str = os.getenv(
            "GIKA_RETRIEVAL_ENDPOINT", raw.get("retrieval_endpoint", "http://127.0.0.1:8000/retrieve")
        )

        # Paths
        paths = raw.get("paths", {})
        self.project_root: Path = PROJECT_ROOT
        self.sample_dataset_path: Path = _resolve(paths.get("sample_dataset", "data/synthetic_enterprise_bench/dataset.json"))
        self.sample_leaderboard_path: Path = _resolve(
            paths.get("sample_leaderboard", "data/sample_dataset/leaderboard.json")
        )
        self.raw_responses_dir: Path = _resolve(paths.get("raw_responses_dir", "data/raw_responses"))
        self.exports_dir: Path = _resolve(paths.get("exports_dir", "data/exports"))
        self.checkpoints_dir: Path = _resolve(paths.get("checkpoints_dir", "data/checkpoints"))
        self.outputs_dir: Path = _resolve(paths.get("outputs_dir", "outputs"))

        # Evaluation
        ev = raw.get("evaluation", {})
        # V1: no top_k (Directive Section 4.2).
        self.request_timeout_s: float = float(ev.get("request_timeout_s", 15.0))
        self.max_retries: int = int(ev.get("max_retries", 3))
        self.backoff_base_s: float = float(ev.get("backoff_base_s", 0.5))
        self.backoff_max_s: float = float(ev.get("backoff_max_s", 8.0))
        self.batch_size: int = int(ev.get("batch_size", 8))

        # Benchmarking modules (V1 answer generation + LLM judge).
        bench = raw.get("benchmarking", {})
        self.answer_generator: str = os.getenv(
            "GIKA_ANSWER_GENERATOR", bench.get("answer_generator", "extractive")
        )
        self.judge: str = os.getenv(
            "GIKA_JUDGE", bench.get("judge", "heuristic")
        )
        # Optional LLM endpoint used by both the LLM generator and LLM judge
        # when they are selected. When either env var is missing, the LLM
        # implementations fall back to their deterministic counterparts.
        self.llm_endpoint: str = os.getenv("GIKA_LLM_ENDPOINT", "")
        self.llm_api_key: str = os.getenv("GIKA_LLM_API_KEY", "")
        self.llm_model: str = os.getenv("GIKA_LLM_MODEL", "gpt-4o-mini")

        # Logging
        self.log_level: str = os.getenv("GIKA_LOG_LEVEL", raw.get("logging", {}).get("level", "INFO"))

        # Metrics config (raw dict, consumed by metric modules).
        self.metrics: Dict[str, Any] = metrics or {}
        self.em_normalize: bool = bool(self.metrics.get("em_normalize", True))
        self.success_recall_threshold: float = float(self.metrics.get("success_recall_threshold", 0.5))
        self.success_doc_recall_threshold: float = float(self.metrics.get("success_doc_recall_threshold", 0.5))
        self.semantic_similarity_threshold: float = float(self.metrics.get("semantic_similarity_threshold", 0.6))
        self.llm_judge_pass_threshold: float = float(self.metrics.get("llm_judge_pass_threshold", 0.7))
        self.low_rank_threshold: int = int(self.metrics.get("low_rank_threshold", 3))

    def ensure_dirs(self) -> None:
        for d in (self.raw_responses_dir, self.exports_dir, self.checkpoints_dir, self.outputs_dir):
            d.mkdir(parents=True, exist_ok=True)
        # DB parent dir for sqlite file URLs.
        if self.db_url.startswith("sqlite"):
            db_path = self.db_url.split("///", 1)[-1]
            if db_path and db_path != ":memory:":
                _resolve(db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
