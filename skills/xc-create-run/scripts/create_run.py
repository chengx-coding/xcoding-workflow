#!/usr/bin/env python3
"""Create standard `.xcoding/runs/<run-id>` directories."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


INVALID_RUN_ID = re.compile(r'[<>:"/\\|?*\x00]')
NON_SLUG = re.compile(r"[^a-z0-9-]+")
MULTI_DASH = re.compile(r"-{2,}")


class RunError(RuntimeError):
    """Error returned in the stable JSON error envelope."""


def slug(value: str, fallback: str = "run") -> str:
    normalized = NON_SLUG.sub("-", value.strip().lower().replace("_", "-").replace(" ", "-"))
    normalized = MULTI_DASH.sub("-", normalized).strip("-")
    return normalized or fallback


def validate_run_id(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise RunError("run_id must not be empty")
    if candidate in {".", ".."} or INVALID_RUN_ID.search(candidate):
        raise RunError("run_id must be a plain directory name")
    if candidate.endswith((".", " ")):
        raise RunError("run_id must not end with a dot or space")
    return candidate


def git_root(path: Path, required: bool = True) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        if not required:
            return None
        detail = result.stderr.strip() or result.stdout.strip()
        raise RunError(f"context_dir is not inside a Git worktree: {detail}")
    root = result.stdout.strip()
    if not root:
        raise RunError("Git did not return a context worktree root")
    return Path(root).resolve()


def unique_run_dir(runs_dir: Path, requested_id: str) -> tuple[str, Path]:
    suffix = 1
    while True:
        run_id = requested_id if suffix == 1 else f"{requested_id}-{suffix}"
        candidate = runs_dir / run_id
        try:
            candidate.mkdir()
        except FileExistsError:
            suffix += 1
            continue
        return run_id, candidate


def create_run(
    context_dir: Path,
    project_root: Path,
    topic: str,
    explicit_run_id: str,
    feature_ids: list[str],
) -> dict[str, Any]:
    resolved_context = context_dir.expanduser().resolve()
    if not resolved_context.is_dir():
        raise RunError(f"context_dir does not exist or is not a directory: {resolved_context}")
    context_repo_root = git_root(resolved_context)
    resolved_project = project_root.expanduser().resolve()
    project_repo_root = git_root(resolved_project, required=False)
    if project_repo_root is not None and project_repo_root == context_repo_root:
        raise RunError("context_dir must belong to a Git worktree independent from the business project repository")
    try:
        resolved_context.relative_to(context_repo_root)
    except ValueError as exc:
        raise RunError("context_dir must be inside its context Git worktree") from exc

    requested_id = validate_run_id(explicit_run_id) if explicit_run_id else f"{datetime.now():%Y%m%d-%H%M}-{slug(topic)}"
    runs_dir = resolved_context / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id, run_dir = unique_run_dir(runs_dir, requested_id)
    artifacts_dir = run_dir / "artifacts"
    runtime_dir = run_dir / "runtime"
    artifacts_dir.mkdir()
    runtime_dir.mkdir()
    return {
        "ok": True,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "runtime_dir": str(runtime_dir),
        "artifacts_dir": str(artifacts_dir),
        "context_dir": str(resolved_context),
        "context_repo_root": str(context_repo_root),
        "project_root": str(resolved_project),
        "feature_ids": [feature_id for feature_id in feature_ids if feature_id],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a standard XC workflow run directory.")
    parser.add_argument("--context-dir", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--topic", default="run")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--feature-id", action="append", default=[])
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                create_run(Path(args.context_dir), Path(args.project_root), args.topic, args.run_id, args.feature_id),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, RunError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "run_creation_error", "message": str(exc)}}, ensure_ascii=False, indent=2))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
