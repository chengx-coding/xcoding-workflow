"""Read-only setup planning for an explicit packaged adapter and target root."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any

from .bundle.resources import inspect_installed_bundle, installed_bundle_root


_ADAPTER_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ACTIONS = ("create", "replace", "unchanged", "conflict")


class SetupInputError(ValueError):
    """Structurally invalid explicit setup input."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class SetupReadinessError(RuntimeError):
    """A complete dry-run plan whose target is not ready for later application."""

    def __init__(self, plan: dict[str, Any]) -> None:
        super().__init__("setup target is not ready")
        self.code = "target-not-ready"
        self.details = {"plan": plan}


def empty_setup_plan(
    adapter_id: str | None,
    target_root: str | None,
) -> dict[str, Any]:
    """Return the stable empty plan used for missing explicit inputs."""
    return {
        "adapter_id": adapter_id,
        "target_root": target_root,
        "operations": [],
        "drift": {action: 0 for action in _ACTIONS},
        "readiness": {"ready": False, "issues": []},
        "writes_performed": False,
    }


def _path_is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    return bool(os_is_junction and os_is_junction(path))


def _issue(code: str, path: Path, message: str) -> dict[str, str]:
    return {"code": code, "path": str(path), "message": message}


def _first_unsafe_component(path: Path) -> dict[str, str] | None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            current.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            return _issue(
                "target-inaccessible",
                current,
                f"cannot inspect target path component: {error}",
            )
        if _path_is_link_or_junction(current):
            return _issue(
                "target-link",
                current,
                "target path must not traverse a symlink or junction",
            )
    return None


def _nearest_existing(path: Path) -> Path:
    current = path
    while True:
        try:
            current.lstat()
            return current
        except FileNotFoundError:
            if current == current.parent:
                return current
            current = current.parent


def inspect_target_readiness(target_root: Path) -> dict[str, Any]:
    """Inspect a target root without creating files or probing with writes."""
    if not target_root.is_absolute():
        raise SetupInputError(
            "target-root-invalid",
            "target root must be an explicit absolute path",
            details={"target_root": str(target_root)},
        )

    issues: list[dict[str, str]] = []
    unsafe = _first_unsafe_component(target_root)
    if unsafe is not None:
        issues.append(unsafe)
    try:
        mode = target_root.lstat().st_mode
    except FileNotFoundError:
        ancestor = _nearest_existing(target_root.parent)
        writable = (
            not issues
            and stat.S_ISDIR(ancestor.lstat().st_mode)
            and os.access(ancestor, os.W_OK)
        )
        if not writable and not issues:
            issues.append(
                _issue(
                    "target-parent-not-writable",
                    ancestor,
                    "nearest existing target parent is not writable",
                )
            )
        return {
            "target_root": str(target_root),
            "exists": False,
            "kind": "missing",
            "writable": writable,
            "ready": not issues,
            "issues": issues,
        }
    except OSError as error:
        issues.append(
            _issue(
                "target-inaccessible",
                target_root,
                f"cannot inspect target root: {error}",
            )
        )
        return {
            "target_root": str(target_root),
            "exists": None,
            "kind": "inaccessible",
            "writable": False,
            "ready": False,
            "issues": issues,
        }

    if _path_is_link_or_junction(target_root):
        kind = "link"
    elif stat.S_ISDIR(mode):
        kind = "directory"
    elif stat.S_ISREG(mode):
        kind = "file"
    else:
        kind = "other"
    writable = kind == "directory" and os.access(target_root, os.W_OK)
    if kind != "directory" and not issues:
        issues.append(
            _issue(
                "target-not-directory",
                target_root,
                "target root exists but is not a regular directory",
            )
        )
    elif not writable and not issues:
        issues.append(
            _issue(
                "target-not-writable",
                target_root,
                "target root is not writable",
            )
        )
    return {
        "target_root": str(target_root),
        "exists": True,
        "kind": kind,
        "writable": writable,
        "ready": not issues,
        "issues": issues,
    }


def _inspect_target(
    target_root: Path,
    relative_path: str,
    source_data: bytes,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    target = target_root.joinpath(*relative_path.split("/"))
    issues: list[dict[str, str]] = []
    current = target_root
    for part in relative_path.split("/")[:-1]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except OSError as error:
            issues.append(
                _issue(
                    "target-inaccessible",
                    current,
                    f"cannot inspect target directory: {error}",
                )
            )
            return {"action": "conflict", "target_path": str(target)}, issues
        if _path_is_link_or_junction(current) or not stat.S_ISDIR(mode):
            issues.append(
                _issue(
                    "target-conflict",
                    current,
                    "target parent is not a regular directory",
                )
            )
            return {"action": "conflict", "target_path": str(target)}, issues

    try:
        mode = target.lstat().st_mode
    except FileNotFoundError:
        action = "create"
        target_details: dict[str, Any] = {"exists": False}
    except OSError as error:
        issues.append(
            _issue(
                "target-inaccessible",
                target,
                f"cannot inspect target file: {error}",
            )
        )
        action = "conflict"
        target_details = {"exists": None}
    else:
        if _path_is_link_or_junction(target) or not stat.S_ISREG(mode):
            issues.append(
                _issue(
                    "target-conflict",
                    target,
                    "target entry is not a regular file",
                )
            )
            action = "conflict"
            target_details = {"exists": True, "kind": "conflict"}
        else:
            try:
                target_data = target.read_bytes()
            except OSError as error:
                issues.append(
                    _issue(
                        "target-inaccessible",
                        target,
                        f"cannot read target file: {error}",
                    )
                )
                action = "conflict"
                target_details = {"exists": True, "kind": "file"}
            else:
                action = "unchanged" if target_data == source_data else "replace"
                target_details = {
                    "exists": True,
                    "kind": "file",
                    "size": len(target_data),
                    "sha256": hashlib.sha256(target_data).hexdigest(),
                }
                if action == "replace" and not os.access(target, os.W_OK):
                    issues.append(
                        _issue(
                            "target-not-writable",
                            target,
                            "drifted target file is not writable",
                        )
                    )

    return {
        "relative_path": relative_path,
        "target_path": str(target),
        "action": action,
        "source_size": len(source_data),
        "source_sha256": hashlib.sha256(source_data).hexdigest(),
        "target": target_details,
    }, issues


def setup_plan(adapter_id: str, target_root: Path) -> dict[str, Any]:
    """Calculate deterministic adapter drift without changing the target."""
    if not _ADAPTER_ID.fullmatch(adapter_id):
        raise SetupInputError(
            "adapter-invalid",
            "adapter must use a canonical lowercase identifier",
            details={"adapter": adapter_id},
        )
    readiness = inspect_target_readiness(target_root)
    inspection = inspect_installed_bundle()
    records = tuple(
        record
        for record in inspection.manifest.resources
        if record.kind == "host-adapter" and record.adapter_id == adapter_id
    )
    if not records:
        available = sorted(
            {
                record.adapter_id
                for record in inspection.manifest.resources
                if record.kind == "host-adapter" and record.adapter_id is not None
            }
        )
        raise SetupInputError(
            "adapter-unknown",
            "adapter is not present in the packaged Bundle",
            details={"adapter": adapter_id, "available": available},
        )

    bundle_root = installed_bundle_root()
    operations: list[dict[str, Any]] = []
    issues = list(readiness["issues"])
    prefix = f"adapters/{adapter_id}/"
    for record in records:
        relative_path = record.bundle_path.removeprefix(prefix)
        source = bundle_root.joinpath(*record.bundle_path.split("/")).read_bytes()
        if readiness["exists"] is False:
            operation = {
                "relative_path": relative_path,
                "target_path": str(
                    target_root.joinpath(*relative_path.split("/"))
                ),
                "action": "create",
                "source_size": len(source),
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "target": {"exists": False},
            }
        elif readiness["kind"] == "directory":
            operation, operation_issues = _inspect_target(
                target_root,
                relative_path,
                source,
            )
            issues.extend(operation_issues)
        else:
            operation = {
                "relative_path": relative_path,
                "target_path": str(
                    target_root.joinpath(*relative_path.split("/"))
                ),
                "action": "conflict",
                "source_size": len(source),
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "target": {"exists": None},
            }
        operations.append(operation)

    drift = {
        action: sum(operation["action"] == action for operation in operations)
        for action in _ACTIONS
    }
    readiness = {**readiness, "ready": not issues, "issues": issues}
    plan = {
        "adapter_id": adapter_id,
        "target_root": str(target_root),
        "bundle_manifest_sha256": inspection.manifest_sha256,
        "operations": operations,
        "drift": drift,
        "readiness": readiness,
        "writes_performed": False,
    }
    if not readiness["ready"]:
        raise SetupReadinessError(plan)
    return plan


__all__ = [
    "SetupInputError",
    "SetupReadinessError",
    "empty_setup_plan",
    "inspect_target_readiness",
    "setup_plan",
]
