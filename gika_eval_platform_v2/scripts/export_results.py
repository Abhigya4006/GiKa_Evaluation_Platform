


from __future__ import annotations


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import argparse

from app.db import repository
from app.services.export_service import export_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Export results for a run.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--latest", action="store_true", help="Export the most recent run.")
    args = parser.parse_args()

    run_id = args.run_id
    if args.latest or not run_id:
        runs = repository.list_runs()
        if not runs:
            print("No runs found.")
            return
        run_id = runs[0]["run_id"]

    paths = export_run(run_id)
    print(f"Exported run {run_id}:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
