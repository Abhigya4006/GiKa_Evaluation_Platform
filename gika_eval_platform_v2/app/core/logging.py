
from __future__ import annotations

import logging
import sys

from app.core.config import get_settings

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(level)
        # Avoid duplicate handlers on re-import (e.g. Streamlit reruns).
        if not root.handlers:
            root.addHandler(handler)
        _CONFIGURED = True
    return logging.getLogger(name)
