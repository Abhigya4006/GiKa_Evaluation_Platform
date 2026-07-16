
from __future__ import annotations

from app.core.utils import safe_div


def f1(precision_value: float, recall_value: float) -> float:
    denom = precision_value + recall_value
    return safe_div(2 * precision_value * recall_value, denom)
