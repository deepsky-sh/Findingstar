"""Double-click or run `python run.py [사진파일]` to start StarLab."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlab.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
