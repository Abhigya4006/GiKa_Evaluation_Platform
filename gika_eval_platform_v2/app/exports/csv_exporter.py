
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


def write_csv(path: str | Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        # Write header-only (or empty) file so downstream tooling has a file.
        with path.open("w", newline="", encoding="utf-8") as fh:
            if fieldnames:
                csv.writer(fh).writerow(fieldnames)
        return str(path)
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _flat(r.get(k)) for k in fieldnames})
    return str(path)


def _flat(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, ensure_ascii=False, default=str)
    return v
