#!/usr/bin/env python3
"""Open a work order and create its standard workbench directories."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


INVALID_WORK_ORDER_ID = re.compile(r'[<>:"/\\|?*\x00]')
NON_SLUG = re.compile(r"[^a-z0-9-]+")
MULTI_DASH = re.compile(r"-{2,}")


class WorkOrderError(RuntimeError):
    """Error returned in the stable JSON error envelope."""


def slug(value: str, fallback: str = "work-order") -> str:
    normalized = NON_SLUG.sub("-", value.strip().lower().replace("_", "-").replace(" ", "-"))
    normalized = MULTI_DASH.sub("-", normalized).strip("-")
    return normalized or fallback


def validate_work_order_id(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise WorkOrderError("work_order_id must not be empty")
    if candidate in {".", ".."} or INVALID_WORK_ORDER_ID.search(candidate):
        raise WorkOrderError("work_order_id must be a plain directory name")
    if candidate.endswith((".", " ")):
        raise WorkOrderError("work_order_id must not end with a dot or space")
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
        raise WorkOrderError(f"workshop_path is not inside a Git worktree: {detail}")
    root = result.stdout.strip()
    if not root:
        raise WorkOrderError("Git did not return a workshop worktree root")
    return Path(root).resolve()


def unique_workbench(work_orders_path: Path, requested_id: str) -> tuple[str, Path]:
    suffix = 1
    while True:
        work_order_id = requested_id if suffix == 1 else f"{requested_id}-{suffix}"
        candidate = work_orders_path / work_order_id
        try:
            candidate.mkdir()
        except FileExistsError:
            suffix += 1
            continue
        return work_order_id, candidate


def open_work_order(
    workshop_path: Path,
    project_root: Path,
    topic: str,
    explicit_work_order_id: str,
    feature_ids: list[str],
) -> dict[str, Any]:
    resolved_workshop = workshop_path.expanduser().resolve()
    if not resolved_workshop.is_dir():
        raise WorkOrderError(f"workshop_path does not exist or is not a directory: {resolved_workshop}")
    if resolved_workshop.name != ".xcoding":
        raise WorkOrderError(f"workshop_path must resolve to a .xcoding directory: {resolved_workshop}")
    workshop_repo_root = git_root(resolved_workshop)
    resolved_project = project_root.expanduser().resolve()
    project_repo_root = git_root(resolved_project, required=False)
    if project_repo_root is not None and project_repo_root == workshop_repo_root:
        raise WorkOrderError("workshop_path must belong to a Git worktree independent from the business project repository")
    try:
        resolved_workshop.relative_to(workshop_repo_root)
    except ValueError as exc:
        raise WorkOrderError("workshop_path must be inside its workshop Git worktree") from exc

    requested_id = (
        validate_work_order_id(explicit_work_order_id)
        if explicit_work_order_id
        else f"{datetime.now():%Y%m%d-%H%M}-{slug(topic)}"
    )
    work_orders_path = resolved_workshop / "work-orders"
    work_orders_path.mkdir(parents=True, exist_ok=True)
    work_order_id, workbench_path = unique_workbench(work_orders_path, requested_id)
    artifacts_path = workbench_path / "artifacts"
    runtime_path = workbench_path / "runtime"
    artifacts_path.mkdir()
    runtime_path.mkdir()
    return {
        "ok": True,
        "work_order_id": work_order_id,
        "workbench_path": str(workbench_path),
        "work_orders_path": str(work_orders_path),
        "runtime_path": str(runtime_path),
        "artifacts_path": str(artifacts_path),
        "workshop_path": str(resolved_workshop),
        "workshop_repo_root": str(workshop_repo_root),
        "project_root": str(resolved_project),
        "feature_ids": [feature_id for feature_id in feature_ids if feature_id],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Open an XC work order and create its workbench.")
    parser.add_argument("--workshop", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--topic", default="work-order")
    parser.add_argument("--work-order-id", default="")
    parser.add_argument("--feature-id", action="append", default=[])
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                open_work_order(
                    Path(args.workshop),
                    Path(args.project_root),
                    args.topic,
                    args.work_order_id,
                    args.feature_id,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, WorkOrderError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": "work_order_open_error", "message": str(exc)}},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
