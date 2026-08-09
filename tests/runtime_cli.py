#!/usr/bin/env python3
"""Source-tree test entry for the package-owned runtime CLI."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["runtime", *sys.argv[1:]]))
