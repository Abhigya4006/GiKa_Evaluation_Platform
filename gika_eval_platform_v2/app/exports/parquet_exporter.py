
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.exports.csv_exporter import write_csv

logger = get_logger(__name__)


def write_parquet(path: str | Path, rows: List[Dict[str, Any]]) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore

        if not rows:
            table = pa.table({})
        else:
            cols: Dict[str, list] = {k: [] for k in rows[0].keys()}
            for r in rows:
                for k in cols:
                    v = r.get(k)
                    if isinstance(v, (dict, list)):
                        import json
                        v = json.dumps(v, ensure_ascii=False, default=str)
                    cols[k].append(v)
            table = pa.table(cols)
        pq.write_table(table, str(path))
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.info("pyarrow unavailable (%s); writing CSV fallback.", type(exc).__name__)
        csv_path = path.with_suffix(".csv")
        return write_csv(csv_path, rows)
