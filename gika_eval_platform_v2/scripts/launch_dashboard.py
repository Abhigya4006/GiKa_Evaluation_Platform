


from __future__ import annotations


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import subprocess
import sys
from pathlib import Path


def main() -> None:
    dashboard = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
    try:
        subprocess.run(["streamlit", "run", str(dashboard)], check=True)
    except FileNotFoundError:
        print("Streamlit is not installed. Install requirements.txt first:")
        print("  pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
