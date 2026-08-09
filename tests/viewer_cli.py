#!/usr/bin/env python3
"""Source-tree test entry for the package-owned Viewer CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))
os.environ["PYTHONPATH"] = os.pathsep.join(
    [
        str(SOURCE_ROOT),
        os.environ.get("PYTHONPATH", ""),
    ]
).rstrip(os.pathsep)

from xcoding.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["viewer", *sys.argv[1:]]))
