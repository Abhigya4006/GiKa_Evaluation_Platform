

from __future__ import annotations


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import argparse
from pathlib import Path

from app.core.logging import get_logger
from app.db.init_db import init_db
from app.services.run_service import ingest_dataset

logger = get_logger("seed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample dataset into the DB.")
    parser.add_argument("--dataset", default=None, help="Path to dataset.json")
    parser.add_argument("--leaderboard", default=None, help="Path to leaderboard.json")
    parser.add_argument("--no-init", action="store_true", help="Skip DB init.")
    args = parser.parse_args()

    # Always initialise DB schema unless explicitly skipped.
    if not args.no_init:
        init_db()

    # Resolve dataset path early to give a clear error.
    if args.dataset and not Path(args.dataset).exists():
        print(f"ERROR: Dataset file not found: {args.dataset}")
        _sys.exit(1)

    if not args.dataset:
        # Check the configured default exists.
        from app.core.config import get_settings
        default_path = get_settings().sample_dataset_path
        if not default_path.exists():
            print(f"ERROR: Default sample dataset not found at {default_path}")
            print("  Available datasets:")
            data_dir = Path("data")
            if data_dir.exists():
                for p in sorted(data_dir.rglob("dataset.json")):
                    print(f"    {p}")
            print(f"\n  Run with: python scripts/seed_sample_data.py --dataset <path>")
            _sys.exit(1)

    ds = ingest_dataset(path=args.dataset, leaderboard_path=args.leaderboard)
    logger.info("Seeded dataset '%s' with %d queries.", ds.dataset_id, len(ds.items))
    print(f"Seeded dataset '{ds.dataset_id}' ({len(ds.items)} queries).")


if __name__ == "__main__":
    main()
