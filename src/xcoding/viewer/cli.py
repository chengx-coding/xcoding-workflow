"""Command-line entry for the package-owned orchestration Viewer."""

from __future__ import annotations

from collections.abc import Sequence

from . import server


def main(argv: Sequence[str] | None = None) -> int:
    return server.main(list(argv) if argv is not None else None)


__all__ = ["main"]
