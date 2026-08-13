#!/usr/bin/env python3
"""Restore-point storage, manifest, and verification helpers.

Restore points are workshop-scoped recovery snapshots stored next to a
managed runtime tree under ``<runtime_dir>/restore-points/<id>/``. This
module owns the directory layout, manifest schema, deterministic listing,
and fail-closed checksum verification. Command wiring and runtime-tree
mutation remain in ``application``.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import core


RESTORE_POINTS_DIRNAME = "restore-points"
MANIFEST_FILENAME = "manifest.json"
TREE_STORED_NAME = "tree.xml"
MANIFEST_SCHEMA_VERSION = 1
RESTORE_POINT_ID_RE = re.compile(r"^rp_[0-9]{8}-[0-9]{6}_[a-f0-9]{8}$")
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_ARTIFACT_DIRNAME = "artifacts"


class RestorePointError(core.RuntimeErrorBase):
    """Base error for restore-point operations."""

    code = "restore_point_error"


class RestorePointNotFoundError(RestorePointError):
    code = "restore_point_not_found"


class RestorePointInvalidIdError(RestorePointError):
    code = "restore_point_invalid_id"


class RestorePointChecksumError(RestorePointError):
    code = "restore_point_checksum_mismatch"


class RestorePointMissingFileError(RestorePointError):
    code = "restore_point_file_missing"


class RestorePointPathError(RestorePointError):
    code = "restore_point_path_violation"


class RestorePointManifestError(RestorePointError):
    code = "restore_point_manifest_invalid"


def new_restore_point_id(now: Optional[datetime] = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"rp_{timestamp}_{uuid.uuid4().hex[:8]}"


def validate_restore_point_id(restore_point_id: str) -> None:
    if not RESTORE_POINT_ID_RE.fullmatch(restore_point_id or ""):
        raise RestorePointInvalidIdError(
            "restore-point id must match rp_<UTC timestamp>_<8 hex characters>",
            {"restore_point_id": restore_point_id},
        )


def restore_points_root(tree_path: Path) -> Path:
    return tree_path.parent / RESTORE_POINTS_DIRNAME


def restore_point_dir(tree_path: Path, restore_point_id: str) -> Path:
    validate_restore_point_id(restore_point_id)
    return restore_points_root(tree_path) / restore_point_id


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return sanitized or "artifact"


def workshop_root_for(tree_path: Path) -> Path:
    """Return the workshop root containing the runtime tree.

    The workshop Git repository root is preferred; outside a repository the
    nearest ancestor containing ``.xcoding/`` is the fallback anchor. A tree
    without either anchor fails closed.
    """
    repo = core.git_root_for(tree_path)
    if repo is not None:
        return repo
    resolved = tree_path.resolve()
    current = resolved if resolved.is_dir() else resolved.parent
    while True:
        if (current / ".xcoding").is_dir():
            return current
        if current.parent == current:
            raise RestorePointPathError(
                "runtime tree is not inside a workshop Git repository",
                {"tree_path": str(tree_path)},
            )
        current = current.parent


def require_inside_workshop(workshop: Path, candidate: Path, label: str) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workshop)
    except ValueError:
        raise RestorePointPathError(
            f"{label} must resolve inside the workshop Git repository",
            {
                "label": label,
                "workshop": str(workshop),
                "path": str(candidate),
            },
        ) from None
    return resolved


def collect_declared_artifacts(
    tree_path: Path,
    root: ET.Element,
) -> List[Dict[str, Any]]:
    """Resolve the runtime's declared terminal artifacts for capture."""
    workshop = workshop_root_for(tree_path)
    entries: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for declared in core.declared_artifacts(root):
        declared_path = str(declared["path"])
        resolved = Path(declared_path).resolve()
        if str(resolved) in seen:
            continue
        seen.add(str(resolved))
        resolved = require_inside_workshop(workshop, resolved, "declared artifact")
        if not resolved.is_file():
            raise RestorePointMissingFileError(
                "declared artifact does not exist at capture time",
                {"path": declared_path, "resolved_path": str(resolved)},
            )
        entries.append({"path": declared_path, "resolved_path": resolved})
    return entries


def _load_manifest_json(rp_dir: Path) -> Dict[str, Any]:
    manifest_path = rp_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise RestorePointMissingFileError(
            "restore point manifest is missing",
            {"restore_point_dir": str(rp_dir), "file": str(manifest_path)},
        )
    try:
        data = json.loads(
            manifest_path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=core.strict_json_object,
            parse_constant=core.reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise RestorePointManifestError(
            "restore point manifest is not valid JSON",
            {"path": str(manifest_path), "error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise RestorePointManifestError(
            "restore point manifest root must be an object",
            {"path": str(manifest_path)},
        )
    return data


def validate_manifest_shape(manifest: Dict[str, Any], restore_point_id: str) -> List[Dict[str, Any]]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RestorePointManifestError(
            "restore point manifest has unsupported schema_version",
            {"schema_version": manifest.get("schema_version")},
        )
    if manifest.get("id") != restore_point_id:
        raise RestorePointManifestError(
            "restore point manifest id does not match its directory",
            {"id": manifest.get("id"), "directory": restore_point_id},
        )
    if not isinstance(manifest.get("created_at"), str) or not manifest["created_at"]:
        raise RestorePointManifestError("restore point manifest missing created_at")
    if not isinstance(manifest.get("name"), str):
        raise RestorePointManifestError("restore point manifest name must be a string")
    tree_sha256 = manifest.get("tree_sha256")
    if not isinstance(tree_sha256, str) or not SHA256_HEX_RE.fullmatch(tree_sha256):
        raise RestorePointManifestError("restore point manifest has invalid tree sha256")
    if not isinstance(manifest.get("tree_stored_as"), str) or not manifest["tree_stored_as"]:
        raise RestorePointManifestError("restore point manifest has invalid tree_stored_as")
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise RestorePointManifestError("restore point manifest artifacts must be a list")
    artifacts: List[Dict[str, Any]] = []
    for index, entry in enumerate(raw_artifacts):
        if not isinstance(entry, dict):
            raise RestorePointManifestError(
                "restore point manifest artifact entries must be objects",
                {"index": index},
            )
        declared = entry.get("path")
        resolved = entry.get("resolved_path")
        entry_sha256 = entry.get("sha256")
        stored_as = entry.get("stored_as")
        if not isinstance(declared, str) or not declared:
            raise RestorePointManifestError(
                "restore point manifest artifact missing path",
                {"index": index},
            )
        if not isinstance(resolved, str) or not resolved:
            raise RestorePointManifestError(
                "restore point manifest artifact missing resolved_path",
                {"index": index},
            )
        if not isinstance(entry_sha256, str) or not SHA256_HEX_RE.fullmatch(entry_sha256):
            raise RestorePointManifestError(
                "restore point manifest artifact has invalid sha256",
                {"index": index, "path": declared},
            )
        if not isinstance(stored_as, str) or not stored_as:
            raise RestorePointManifestError(
                "restore point manifest artifact missing stored_as",
                {"index": index, "path": declared},
            )
        artifacts.append(
            {
                "path": declared,
                "resolved_path": Path(resolved),
                "sha256": entry_sha256,
                "stored_as": stored_as,
            }
        )
    return artifacts


def load_verified_restore_point(
    tree_path: Path,
    restore_point_id: str,
) -> Dict[str, Any]:
    """Load one restore point and verify every stored checksum fail closed."""
    validate_restore_point_id(restore_point_id)
    rp_dir = restore_points_root(tree_path) / restore_point_id
    if not rp_dir.is_dir():
        raise RestorePointNotFoundError(
            "restore point does not exist",
            {
                "tree_path": str(tree_path),
                "restore_point_id": restore_point_id,
                "directory": str(rp_dir),
            },
        )
    manifest = _load_manifest_json(rp_dir)
    artifact_entries = validate_manifest_shape(manifest, restore_point_id)
    tree_stored_path = rp_dir / str(manifest["tree_stored_as"])
    if not tree_stored_path.exists():
        raise RestorePointMissingFileError(
            "restore point tree copy is missing",
            {"restore_point_id": restore_point_id, "stored_as": manifest["tree_stored_as"]},
        )
    if sha256_file(tree_stored_path) != manifest["tree_sha256"]:
        raise RestorePointChecksumError(
            "restore point tree checksum mismatch",
            {
                "restore_point_id": restore_point_id,
                "stored_as": manifest["tree_stored_as"],
                "expected_sha256": manifest["tree_sha256"],
                "actual_sha256": sha256_file(tree_stored_path),
            },
        )
    try:
        tree_bytes = tree_stored_path.read_bytes()
        ET.fromstring(tree_bytes)
    except ET.ParseError as exc:
        raise RestorePointChecksumError(
            "restore point tree bytes are not parseable XML",
            {"restore_point_id": restore_point_id, "error": str(exc)},
        ) from exc
    artifacts: List[Dict[str, Any]] = []
    for entry in artifact_entries:
        stored_path = rp_dir / str(entry["stored_as"])
        if not stored_path.exists():
            raise RestorePointMissingFileError(
                "restore point artifact copy is missing",
                {
                    "restore_point_id": restore_point_id,
                    "path": entry["path"],
                    "stored_as": entry["stored_as"],
                },
            )
        actual_sha256 = sha256_file(stored_path)
        if actual_sha256 != entry["sha256"]:
            raise RestorePointChecksumError(
                "restore point artifact checksum mismatch",
                {
                    "restore_point_id": restore_point_id,
                    "path": entry["path"],
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": actual_sha256,
                },
            )
        artifacts.append(
            {
                "path": entry["path"],
                "resolved_path": entry["resolved_path"],
                "stored_path": stored_path,
                "sha256": entry["sha256"],
            }
        )
    return {
        "id": restore_point_id,
        "created_at": manifest.get("created_at", ""),
        "name": manifest.get("name", ""),
        "tree_sha256": manifest["tree_sha256"],
        "tree_stored_as": manifest["tree_stored_as"],
        "tree_bytes": tree_bytes,
        "artifacts": artifacts,
        "directory": rp_dir,
    }


def write_restore_point(
    tree_path: Path,
    restore_point_id: str,
    name: str,
    tree_bytes: bytes,
    artifacts: Sequence[Dict[str, Any]],
    created_at: str,
) -> Dict[str, Any]:
    """Write a workshop-scoped restore point and return its manifest."""
    validate_restore_point_id(restore_point_id)
    rp_dir = restore_points_root(tree_path) / restore_point_id
    if rp_dir.exists():
        raise RestorePointError(
            "restore point directory already exists",
            {"restore_point_id": restore_point_id, "directory": str(rp_dir)},
        )
    core.atomic_write_bytes(rp_dir / TREE_STORED_NAME, tree_bytes)
    manifest_artifacts: List[Dict[str, Any]] = []
    for index, entry in enumerate(artifacts):
        resolved = entry["resolved_path"]
        stored_as = f"{_ARTIFACT_DIRNAME}/{index:03d}-{_sanitize_filename(resolved.name)}"
        core.atomic_write_bytes(rp_dir / stored_as, resolved.read_bytes())
        manifest_artifacts.append(
            {
                "path": entry["path"],
                "resolved_path": str(resolved),
                "sha256": sha256_file(resolved),
                "stored_as": stored_as,
            }
        )
    manifest: Dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "id": restore_point_id,
        "created_at": created_at,
        "name": name,
        "tree_sha256": sha256_bytes(tree_bytes),
        "tree_stored_as": TREE_STORED_NAME,
        "artifacts": manifest_artifacts,
    }
    core.atomic_write_text(
        rp_dir / MANIFEST_FILENAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return {**manifest, "directory": str(rp_dir)}


def list_restore_points(tree_path: Path) -> List[Dict[str, Any]]:
    """Enumerate restore points with metadata in deterministic order."""
    root_dir = restore_points_root(tree_path)
    entries: List[Dict[str, Any]] = []
    if not root_dir.is_dir():
        return entries
    for candidate in sorted(item.name for item in root_dir.iterdir() if item.is_dir()):
        rp_dir = root_dir / candidate
        manifest_path = rp_dir / MANIFEST_FILENAME
        if not manifest_path.exists():
            entries.append({"id": candidate, "status": "manifest_missing"})
            continue
        try:
            manifest = _load_manifest_json(rp_dir)
            artifact_count = (
                len(manifest["artifacts"])
                if isinstance(manifest.get("artifacts"), list)
                else 0
            )
            validate_manifest_shape(manifest, candidate)
            entries.append(
                {
                    "id": candidate,
                    "status": "valid",
                    "created_at": manifest.get("created_at", ""),
                    "name": manifest.get("name", ""),
                    "tree_sha256": manifest.get("tree_sha256", ""),
                    "artifact_count": artifact_count,
                }
            )
        except (RestorePointManifestError, RestorePointMissingFileError) as exc:
            entries.append(
                {
                    "id": candidate,
                    "status": "manifest_invalid",
                    "error": str(exc),
                }
            )
    entries.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))))
    return entries


__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "RESTORE_POINTS_DIRNAME",
    "RESTORE_POINT_ID_RE",
    "RestorePointChecksumError",
    "RestorePointError",
    "RestorePointInvalidIdError",
    "RestorePointManifestError",
    "RestorePointMissingFileError",
    "RestorePointNotFoundError",
    "RestorePointPathError",
    "collect_declared_artifacts",
    "list_restore_points",
    "load_verified_restore_point",
    "new_restore_point_id",
    "require_inside_workshop",
    "restore_point_dir",
    "restore_points_root",
    "sha256_bytes",
    "sha256_file",
    "validate_manifest_shape",
    "validate_restore_point_id",
    "workshop_root_for",
    "write_restore_point",
]
