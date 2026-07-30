#!/usr/bin/env python3
"""Create explicit XC feature directories without creating baseline documents."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SAFE_FEATURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def git_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"workshop_path must be inside a Git worktree: {path}")
    return Path(result.stdout.strip()).resolve()


def initialize_feature(workshop_path: Path, feature_id: str) -> dict[str, object]:
    resolved_workshop = workshop_path.resolve()
    if resolved_workshop.name != ".xcoding":
        raise ValueError(f"workshop_path must resolve to a .xcoding directory: {resolved_workshop}")
    if not SAFE_FEATURE_ID.fullmatch(feature_id):
        raise ValueError("feature_id must be a safe single path segment")
    workshop_repo_root = git_root(resolved_workshop)
    feature_dir = resolved_workshop / "features" / feature_id
    if feature_dir.exists():
        raise ValueError(f"feature directory already exists: {feature_dir}")
    feature_dir.mkdir(parents=True)
    return {
        "ok": True,
        "feature_id": feature_id,
        "feature_dir": str(feature_dir),
        "workshop_path": str(resolved_workshop),
        "workshop_repo_root": str(workshop_repo_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage explicit XC feature directories.")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    initialize = subparsers.add_parser("init", help="Create an empty feature directory.")
    initialize.add_argument("--workshop", required=True)
    initialize.add_argument("--feature-id", required=True)
    args = parser.parse_args()
    try:
        if args.operation != "init":
            raise ValueError(f"unsupported operation: {args.operation}")
        payload = initialize_feature(Path(args.workshop), args.feature_id)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": {"code": "feature_error", "message": str(exc)}}, indent=2))
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
