#!/usr/bin/env python3
"""Sync project skills/ into .agents/skills/.

This script ensures .agents/skills/ is a faithful copy of the canonical
skills/ directory.  It is not a build step for generated artifacts; it
mirrors Skill packages so that agent tools which discover Skills under
.agents/ see the same content as the project source.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
AGENTS_DIR = PROJECT_ROOT / ".agents"
AGENTS_SKILLS = AGENTS_DIR / "skills"
PROJECT_SKILLS = PROJECT_ROOT / "skills"


def _is_xc_skill(name: str) -> bool:
    """Return True when the directory name matches the xc-* convention."""
    return name.startswith("xc-")


def _copy_skill(src: Path, dst: Path) -> None:
    """Fully replace dst with the contents of src."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def build_agents(*, clean_deprecated: bool = False) -> dict:
    """Sync project skills into .agents/skills/ and report results.

    Returns a summary dict suitable for JSON output.
    """
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    AGENTS_SKILLS.mkdir(parents=True, exist_ok=True)

    project_skills: set[str] = set()
    if PROJECT_SKILLS.is_dir():
        for entry in PROJECT_SKILLS.iterdir():
            if entry.is_dir():
                project_skills.add(entry.name)

    agents_skills: set[str] = set()
    if AGENTS_SKILLS.is_dir():
        for entry in AGENTS_SKILLS.iterdir():
            if entry.is_dir():
                agents_skills.add(entry.name)

    synced: list[str] = []
    added: list[str] = []
    deprecated: list[str] = []
    cleaned: list[str] = []
    skipped: list[str] = []

    # Sync or add skills present in the project.
    for name in sorted(project_skills):
        src = PROJECT_SKILLS / name
        dst = AGENTS_SKILLS / name
        if name in agents_skills:
            _copy_skill(src, dst)
            synced.append(name)
        else:
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            added.append(name)

    # Handle skills that exist only in .agents/skills/.
    for name in sorted(agents_skills - project_skills):
        if _is_xc_skill(name):
            if clean_deprecated:
                shutil.rmtree(AGENTS_SKILLS / name)
                cleaned.append(name)
            else:
                deprecated.append(name)
        else:
            skipped.append(name)

    return {
        "synced": synced,
        "added": added,
        "deprecated": deprecated,
        "cleaned": cleaned,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync project skills/ into .agents/skills/")
    parser.add_argument(
        "--clean-deprecated",
        action="store_true",
        help="Remove xc-* skills from .agents/skills/ that no longer exist in project skills/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON summary instead of human-readable output",
    )
    args = parser.parse_args()

    result = build_agents(clean_deprecated=args.clean_deprecated)

    if args.json:
        import json

        print(json.dumps(result, indent=2))
        return

    if result["synced"]:
        print(f"Synced {len(result['synced'])} skill(s): {', '.join(result['synced'])}")
    if result["added"]:
        print(f"Added {len(result['added'])} skill(s): {', '.join(result['added'])}")
    if result["deprecated"]:
        print(
            f"WARNING: {len(result['deprecated'])} xc-* skill(s) exist only in .agents/skills/ "
            f"and may be deprecated: {', '.join(result['deprecated'])}"
        )
        print("  Use --clean-deprecated to remove them.")
    if result["cleaned"]:
        print(f"Cleaned {len(result['cleaned'])} deprecated skill(s): {', '.join(result['cleaned'])}")
    if result["skipped"]:
        print(f"Skipped {len(result['skipped'])} non-xc-* skill(s): {', '.join(result['skipped'])}")

    if not any(result.values()):
        print("No changes.")


if __name__ == "__main__":
    main()
