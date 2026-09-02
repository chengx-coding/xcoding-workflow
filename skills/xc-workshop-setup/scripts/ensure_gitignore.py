#!/usr/bin/env python3
"""Record the workshop .gitignore entry for a chosen workshop topology.

Deterministically ensure that <project-root>/.gitignore carries the workshop
directory rule for the two independent topologies, and report nothing to do
for the non-ignored topologies. The implementation is strict-append: it never
rewrites an existing user line, never duplicates an equivalent entry, and never
writes when the entry is already actively negated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


ENTRY = "/.xcoding/"
ENTRY_REASON = f"workshop directory rule {ENTRY}"

# Existing ignore patterns that are equivalent to the entry we would append.
EQUIVALENT_ENTRIES = {"/.xcoding/", "/.xcoding", ".xcoding/", ".xcoding"}

# Patterns that re-include the workshop directory and therefore defeat an ignore.
NEGATING_ENTRIES = {
    "!.xcoding",
    "!.xcoding/",
    "!/.xcoding",
    "!/.xcoding/",
    "!.xcoding/**",
    "!/.xcoding/**",
}

ALLOWED_TOPOLOGIES = {"independent-link", "independent-nested", "same-repo", "no-git"}
IGNORED_TOPOLOGIES = {"independent-link", "independent-nested"}


def _read_lines(gitignore: Path) -> List[str]:
    if not gitignore.exists():
        return []
    return gitignore.read_text(encoding="utf-8").splitlines()


def _report(status: str, gitignore: Path, detail: str) -> Dict[str, str]:
    return {"status": status, "path": str(gitignore), "detail": detail}


def ensure_gitignore(project_root: str, topology: str) -> Dict[str, str]:
    """Return the result record for the requested topology."""
    if topology not in ALLOWED_TOPOLOGIES:
        # Fail closed: an unknown topology is never silently treated as a default.
        return _report(
            "error",
            Path(project_root) / ".gitignore",
            f"invalid topology: {topology}",
        )

    gitignore = Path(project_root).resolve() / ".gitignore"

    if topology not in IGNORED_TOPOLOGIES:
        return _report(
            "not-applicable",
            gitignore,
            f"topology={topology} is versioned or untracked; no .gitignore entry is written",
        )

    lines = _read_lines(gitignore)

    for line in lines:
        stripped = line.strip()
        if stripped in NEGATING_ENTRIES:
            return _report(
                "skipped-conflict",
                gitignore,
                f"entry is already negated by: {stripped}",
            )

    for line in lines:
        stripped = line.strip()
        if stripped in EQUIVALENT_ENTRIES:
            return _report(
                "already-present",
                gitignore,
                f"{ENTRY_REASON} already present as: {stripped}",
            )

    gitignore.parent.mkdir(parents=True, exist_ok=True)
    data = gitignore.read_bytes() if gitignore.exists() else b""
    if data and not data.endswith(b"\n"):
        data += b"\n"
    data += ENTRY.encode("utf-8") + b"\n"
    gitignore.write_bytes(data)

    return _report("appended", gitignore, f"{ENTRY_REASON} appended")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ensure the product .gitignore carries the workshop directory rule."
    )
    parser.add_argument("--project-root", required=True, help="Business project root directory.")
    parser.add_argument(
        "--topology",
        required=True,
        help="Workshop topology value (independent-link, independent-nested, same-repo, no-git).",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = ensure_gitignore(args.project_root, args.topology)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
