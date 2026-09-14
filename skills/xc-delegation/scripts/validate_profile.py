"""Invoke the installed canonical delegation profile validator."""

from __future__ import annotations

import sys

from xcoding.delegation.commands import main


if __name__ == "__main__":
    raise SystemExit(main(["validate-profile", *sys.argv[1:]]))
