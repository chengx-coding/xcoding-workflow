"""Invoke the installed read-only legacy delegation scanner."""

from __future__ import annotations

import sys

from xcoding.delegation.commands import main


if __name__ == "__main__":
    raise SystemExit(main(["scan-legacy", *sys.argv[1:]]))
