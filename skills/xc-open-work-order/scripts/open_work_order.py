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


CONFIG_FILENAME = "xc-orchestration-runtime.json"
LEGACY_CONFIG_FILENAME = "xc-orchestration-runtime.toml"
ALLOWED_WORKSHOP_TOPOLOGIES = {"independent-link", "independent-nested", "same-repo", "no-git"}
WORKSHOP_TOPOLOGY_DEFAULT = "independent-link"


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite number is not allowed: {value}")


def _parse_config(source: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            source.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise WorkOrderError(f"invalid JSON configuration: {exc}")
    if not isinstance(data, dict):
        raise WorkOrderError("configuration root must be an object")
    return data


def _read_workshop_config(workshop: Path) -> dict[str, Any] | None:
    """Locate and parse the workshop runtime JSON configuration.

    Walks upward from the resolved workshop path, mirroring the discovery in
    src/xcoding/runtime/core.py find_workspace_config. Returns the parsed
    object or None when no JSON configuration exists.
    """
    current = workshop
    while True:
        candidates = [
            (current / ".xcoding" / CONFIG_FILENAME, current / ".xcoding" / LEGACY_CONFIG_FILENAME)
        ]
        if current.name == ".xcoding":
            candidates.insert(0, (current / CONFIG_FILENAME, current / LEGACY_CONFIG_FILENAME))
        for candidate, legacy_candidate in candidates:
            if candidate.exists() and legacy_candidate.exists():
                raise WorkOrderError("both JSON and legacy TOML configuration files exist")
            if candidate.exists():
                return _parse_config(candidate)
            if legacy_candidate.exists():
                raise WorkOrderError(
                    "legacy TOML configuration is no longer supported; migrate it to JSON"
                )
        if current.parent == current:
            return None
        current = current.parent


def resolve_workshop_topology(workshop_path: Path) -> str:
    """Resolve the declared workshop topology, applying the same-repo guard.

    Absent configuration file or absent ``workshop`` section falls back to the
    default ``independent-link`` topology. An unknown value fails closed.
    """
    config = _read_workshop_config(workshop_path)
    if config is None:
        return WORKSHOP_TOPOLOGY_DEFAULT
    workshop = config.get("workshop")
    if workshop is None:
        return WORKSHOP_TOPOLOGY_DEFAULT
    if not isinstance(workshop, dict):
        raise WorkOrderError("workshop must be an object")
    topology = workshop.get("topology", WORKSHOP_TOPOLOGY_DEFAULT)
    if topology not in ALLOWED_WORKSHOP_TOPOLOGIES:
        raise WorkOrderError(
            "workshop.topology must be one of {}".format(", ".join(sorted(ALLOWED_WORKSHOP_TOPOLOGIES)))
        )
    if topology == "same-repo":
        git = config.get("git")
        if not (isinstance(git, dict) and "auto_commit" in git):
            raise WorkOrderError(
                "workshop_path topology=same-repo requires an explicit git.auto_commit declaration"
            )
    return topology


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
    requested_workshop = workshop_path.expanduser()
    if requested_workshop.name != ".xcoding":
        raise WorkOrderError(f"workshop_path must name a .xcoding directory: {requested_workshop}")
    resolved_workshop = requested_workshop.resolve()
    if not resolved_workshop.is_dir():
        raise WorkOrderError(f"workshop_path does not exist or is not a directory: {resolved_workshop}")
    topology = resolve_workshop_topology(resolved_workshop)
    resolved_project = project_root.expanduser().resolve()

    if topology in {"independent-link", "independent-nested"}:
        workshop_repo_root = git_root(resolved_workshop)
        project_repo_root = git_root(resolved_project, required=False)
        if project_repo_root is not None and project_repo_root == workshop_repo_root:
            raise WorkOrderError("workshop_path must belong to a Git worktree independent from the business project repository")
        try:
            resolved_workshop.relative_to(workshop_repo_root)
        except ValueError as exc:
            raise WorkOrderError("workshop_path must be inside its workshop Git worktree") from exc
    elif topology == "same-repo":
        workshop_repo_root = git_root(resolved_workshop)
        try:
            resolved_workshop.relative_to(workshop_repo_root)
        except ValueError as exc:
            raise WorkOrderError("workshop_path must be inside its workshop Git worktree") from exc
    elif topology == "no-git":
        workshop_repo_root = None
    else:
        raise WorkOrderError(
            "workshop.topology must be one of {}".format(", ".join(sorted(ALLOWED_WORKSHOP_TOPOLOGIES)))
        )

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
        "workshop_repo_root": str(workshop_repo_root) if workshop_repo_root else None,
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
