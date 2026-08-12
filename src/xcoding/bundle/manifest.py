"""Strict parsing and read-only verification for packaged Bundle resources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


BUNDLE_SCHEMA_VERSION = 1
RUNTIME_TREE_SCHEMA = 1
SOURCE_STATE = "work-order-candidate"
MANIFEST_NAME = "bundle-manifest.json"
VIEWER_PREFIX = "skills/xc-orchestration-runtime/viewer/static/"

_ADAPTER_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_LOWER_HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_FIELDS = {
    "bundle_schema_version",
    "xc_version",
    "baseline_revision",
    "source_state",
    "candidate_tree_sha256",
    "candidate_source_archive_sha256",
    "python_requires",
    "runtime_tree_schema",
    "resources",
}
_RESOURCE_FIELDS = {
    "kind",
    "adapter_id",
    "source_path",
    "bundle_path",
    "size",
    "sha256",
}


class BundleValidationError(RuntimeError):
    """Read-only Bundle verification failure with a stable error code."""

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


@dataclass(frozen=True)
class ResourceRecord:
    kind: str
    adapter_id: str | None
    source_path: str
    bundle_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class BundleManifest:
    bundle_schema_version: int
    xc_version: str
    baseline_revision: str
    source_state: str
    candidate_tree_sha256: str
    candidate_source_archive_sha256: str
    python_requires: str
    runtime_tree_schema: int
    resources: tuple[ResourceRecord, ...]


@dataclass(frozen=True)
class BundleInspection:
    manifest: BundleManifest
    manifest_sha256: str
    resource_count: int
    partition_counts: Mapping[str, int]
    adapter_partition_counts: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_sha256": self.manifest_sha256,
            "resource_count": self.resource_count,
            "partition_counts": dict(self.partition_counts),
            "adapter_partition_counts": dict(
                self.adapter_partition_counts
            ),
            "bundle_schema_version": self.manifest.bundle_schema_version,
            "xc_version": self.manifest.xc_version,
            "baseline_revision": self.manifest.baseline_revision,
            "source_state": self.manifest.source_state,
            "candidate_tree_sha256": self.manifest.candidate_tree_sha256,
            "candidate_source_archive_sha256": (
                self.manifest.candidate_source_archive_sha256
            ),
            "python_requires": self.manifest.python_requires,
            "runtime_tree_schema": self.manifest.runtime_tree_schema,
        }


def _fail(code: str, message: str, **details: Any) -> None:
    raise BundleValidationError(code, message, details=details)


def _validate_relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("resource_path_unsafe", f"{field} must be a non-empty string")
    if "\\" in value or "\x00" in value:
        _fail(
            "resource_path_unsafe",
            f"{field} must use safe forward-slash relative syntax",
            path=value,
        )
    if value.startswith("/") or re.match(r"[A-Za-z]:", value):
        _fail("resource_path_unsafe", f"{field} must be relative", path=value)
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _fail(
            "resource_path_unsafe",
            f"{field} contains an empty, dot, or parent segment",
            path=value,
        )
    if any(any(ord(character) < 32 for character in part) for part in parts):
        _fail(
            "resource_path_unsafe",
            f"{field} contains a control character",
            path=value,
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("resource_path_unsafe", f"{field} is not valid UTF-8", path=repr(value))
    return value


def _validate_path_set(paths: Iterable[str], *, field: str) -> None:
    exact: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for path in paths:
        _validate_relative_path(path, field=field)
        previous: str | None = None
        collision = ""
        if path in exact:
            previous, collision = exact[path], "duplicate"
        elif path.casefold() in casefolded:
            previous, collision = casefolded[path.casefold()], "casefold"
        elif unicodedata.normalize("NFC", path) in normalized:
            previous, collision = (
                normalized[unicodedata.normalize("NFC", path)],
                "nfc",
            )
        if previous is not None:
            _fail(
                "resource_path_collision",
                f"{field} has a {collision} collision",
                collision=collision,
                first=previous,
                second=path,
            )
        exact[path] = path
        casefolded[path.casefold()] = path
        normalized[unicodedata.normalize("NFC", path)] = path


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            "manifest_invalid",
            f"{label} has invalid fields",
            missing=sorted(expected - actual),
            unexpected=sorted(actual - expected),
        )


def _require_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("manifest_invalid", f"{field} must be a non-empty string")
    return value


def _require_integer(value: object, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("manifest_invalid", f"{field} must be an integer >= {minimum}")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _load_json(data: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _fail("manifest_invalid", f"manifest has duplicate key {key!r}")
            value[key] = item
        return value

    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        _fail("manifest_invalid", f"manifest is not valid UTF-8 JSON: {error}")
    if not isinstance(value, dict):
        _fail("manifest_invalid", "manifest root must be an object")
    if _canonical_json_bytes(value) != data:
        _fail(
            "manifest_invalid",
            "manifest must use canonical sorted UTF-8 JSON with one LF terminator",
        )
    return value


def parse_manifest(data: bytes) -> BundleManifest:
    """Parse canonical manifest bytes and validate the fixed schema."""
    value = _load_json(data)
    _require_exact_fields(value, _MANIFEST_FIELDS, label="manifest")
    if _require_integer(
        value["bundle_schema_version"],
        field="bundle_schema_version",
        minimum=1,
    ) != BUNDLE_SCHEMA_VERSION:
        _fail("manifest_invalid", "unsupported bundle_schema_version")
    if _require_integer(
        value["runtime_tree_schema"],
        field="runtime_tree_schema",
        minimum=1,
    ) != RUNTIME_TREE_SCHEMA:
        _fail("manifest_invalid", "unsupported runtime_tree_schema")

    xc_version = _require_string(value["xc_version"], field="xc_version")
    python_requires = _require_string(
        value["python_requires"],
        field="python_requires",
    )
    baseline_revision = _require_string(
        value["baseline_revision"],
        field="baseline_revision",
    )
    source_state = _require_string(value["source_state"], field="source_state")
    candidate_tree = _require_string(
        value["candidate_tree_sha256"],
        field="candidate_tree_sha256",
    )
    candidate_archive = _require_string(
        value["candidate_source_archive_sha256"],
        field="candidate_source_archive_sha256",
    )
    if not _LOWER_HEX_40.fullmatch(baseline_revision):
        _fail(
            "source_mismatch",
            "baseline_revision must be 40 lowercase hexadecimal characters",
        )
    if source_state != SOURCE_STATE:
        _fail("source_mismatch", f"source_state must be {SOURCE_STATE!r}")
    if not _LOWER_HEX_64.fullmatch(candidate_tree):
        _fail(
            "source_mismatch",
            "candidate_tree_sha256 must be 64 lowercase hexadecimal characters",
        )
    if not _LOWER_HEX_64.fullmatch(candidate_archive):
        _fail(
            "source_mismatch",
            "candidate_source_archive_sha256 must be 64 lowercase hexadecimal characters",
        )

    raw_resources = value["resources"]
    if not isinstance(raw_resources, list) or not raw_resources:
        _fail("manifest_invalid", "resources must be a non-empty array")
    records: list[ResourceRecord] = []
    for index, raw_record in enumerate(raw_resources):
        if not isinstance(raw_record, dict):
            _fail("manifest_invalid", f"resources[{index}] must be an object")
        _require_exact_fields(
            raw_record,
            _RESOURCE_FIELDS,
            label=f"resources[{index}]",
        )
        kind = raw_record["kind"]
        if kind not in {"skill", "viewer", "host-adapter"}:
            _fail("manifest_invalid", f"resources[{index}].kind is invalid")
        adapter_id = raw_record["adapter_id"]
        if kind == "host-adapter":
            if not isinstance(adapter_id, str) or not _ADAPTER_ID.fullmatch(adapter_id):
                _fail(
                    "manifest_invalid",
                    f"resources[{index}].adapter_id is not canonical",
                )
        elif adapter_id is not None:
            _fail(
                "manifest_invalid",
                f"resources[{index}].adapter_id must be null",
            )
        source_path = _validate_relative_path(
            raw_record["source_path"],
            field=f"resources[{index}].source_path",
        )
        bundle_path = _validate_relative_path(
            raw_record["bundle_path"],
            field=f"resources[{index}].bundle_path",
        )
        if bundle_path == MANIFEST_NAME:
            _fail("manifest_invalid", "manifest must not hash itself")
        if kind == "viewer":
            if (
                not source_path.startswith(VIEWER_PREFIX)
                or source_path != bundle_path
            ):
                _fail(
                    "manifest_invalid",
                    "viewer resources must retain the canonical Viewer path",
                )
        elif kind == "skill":
            if (
                not source_path.startswith("skills/xc-")
                or source_path.count("/") < 2
                or source_path.startswith(VIEWER_PREFIX)
                or source_path != bundle_path
            ):
                _fail(
                    "manifest_invalid",
                    "skill resources must retain a non-Viewer canonical Skill path",
                )
        elif not bundle_path.startswith(f"adapters/{adapter_id}/"):
            _fail(
                "manifest_invalid",
                "host-adapter bundle_path must be under adapters/<adapter_id>/",
            )
        size = _require_integer(
            raw_record["size"],
            field=f"resources[{index}].size",
        )
        digest = raw_record["sha256"]
        if not isinstance(digest, str) or not _LOWER_HEX_64.fullmatch(digest):
            _fail(
                "manifest_invalid",
                f"resources[{index}].sha256 must be lowercase SHA-256",
            )
        records.append(
            ResourceRecord(
                kind=kind,
                adapter_id=adapter_id,
                source_path=source_path,
                bundle_path=bundle_path,
                size=size,
                sha256=digest,
            )
        )

    if [record.bundle_path for record in records] != sorted(
        record.bundle_path for record in records
    ):
        _fail("manifest_invalid", "resources must be sorted by bundle_path")
    _validate_path_set(
        (record.source_path for record in records),
        field="source_path",
    )
    _validate_path_set(
        (record.bundle_path for record in records),
        field="bundle_path",
    )
    partitions = {
        kind: {
            record.bundle_path for record in records if record.kind == kind
        }
        for kind in ("skill", "viewer", "host-adapter")
    }
    if any(
        partitions[left] & partitions[right]
        for left, right in (
            ("skill", "viewer"),
            ("skill", "host-adapter"),
            ("viewer", "host-adapter"),
        )
    ):
        _fail(
            "resource_path_collision",
            "resource kind partitions are not disjoint",
        )
    if set().union(*partitions.values()) != {
        record.bundle_path for record in records
    }:
        _fail("manifest_invalid", "resource partitions do not cover the manifest")

    return BundleManifest(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
        xc_version=xc_version,
        baseline_revision=baseline_revision,
        source_state=source_state,
        candidate_tree_sha256=candidate_tree,
        candidate_source_archive_sha256=candidate_archive,
        python_requires=python_requires,
        runtime_tree_schema=RUNTIME_TREE_SCHEMA,
        resources=tuple(records),
    )


def _path_is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    return bool(os_is_junction and os_is_junction(path))


def _read_manifest_bytes(root: Any) -> bytes:
    if isinstance(root, Path):
        if _path_is_link_or_junction(root):
            _fail("resource_path_unsafe", "Bundle root must not be a link")
        try:
            if not stat.S_ISDIR(root.lstat().st_mode):
                _fail("resource_path_unsafe", "Bundle root must be a directory")
        except OSError as error:
            _fail("resource_missing", f"Bundle root is unavailable: {error}")
    try:
        manifest = root.joinpath(MANIFEST_NAME)
    except (AttributeError, OSError) as error:
        _fail("resource_path_unsafe", f"cannot locate Bundle manifest: {error}")
    if isinstance(manifest, Path) and _path_is_link_or_junction(manifest):
        _fail("resource_path_unsafe", "Bundle manifest must not be a link")
    try:
        if not manifest.is_file() or manifest.is_dir():
            _fail("resource_missing", "Bundle manifest is missing", path=MANIFEST_NAME)
        return manifest.read_bytes()
    except OSError as error:
        _fail("resource_path_unsafe", f"cannot read Bundle manifest: {error}")


def _read_actual_files(root: Any) -> dict[str, bytes]:
    if isinstance(root, Path):
        if _path_is_link_or_junction(root):
            _fail("resource_path_unsafe", "Bundle root must not be a link")
        try:
            if not stat.S_ISDIR(root.lstat().st_mode):
                _fail("resource_path_unsafe", "Bundle root must be a directory")
        except OSError as error:
            _fail("resource_missing", f"Bundle root is unavailable: {error}")

    files: dict[str, bytes] = {}
    stack: list[tuple[Any, str]] = [(root, "")]
    while stack:
        directory, prefix = stack.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as error:
            _fail("resource_path_unsafe", f"cannot enumerate Bundle: {error}")
        for entry in reversed(entries):
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            _validate_relative_path(relative, field="bundle_path")
            if isinstance(entry, Path) and _path_is_link_or_junction(entry):
                _fail(
                    "resource_path_unsafe",
                    "Bundle must not contain symlinks or junctions",
                    path=relative,
                )
            try:
                is_directory = entry.is_dir()
                is_file = entry.is_file()
            except OSError as error:
                _fail(
                    "resource_path_unsafe",
                    f"cannot inspect Bundle entry: {error}",
                    path=relative,
                )
            if is_directory and not is_file:
                stack.append((entry, relative))
            elif is_file and not is_directory:
                try:
                    files[relative] = entry.read_bytes()
                except OSError as error:
                    _fail(
                        "resource_path_unsafe",
                        f"cannot read Bundle entry: {error}",
                        path=relative,
                    )
            else:
                _fail(
                    "resource_path_unsafe",
                    "Bundle entries must be regular files or directories",
                    path=relative,
                )
    _validate_path_set(files, field="bundle_path")
    return files


def inspect_bundle(
    root: Any,
    *,
    expected_version: str | None = None,
    expected_provenance: Mapping[str, str] | None = None,
) -> BundleInspection:
    """Validate a physical or importlib resource Bundle without mutation."""
    manifest_bytes = _read_manifest_bytes(root)
    manifest = parse_manifest(manifest_bytes)

    if expected_version is not None and manifest.xc_version != expected_version:
        _fail(
            "version_mismatch",
            "Bundle version does not match installed distribution metadata",
            expected=expected_version,
            actual=manifest.xc_version,
        )
    if expected_provenance is not None:
        fields = (
            "baseline_revision",
            "source_state",
            "candidate_tree_sha256",
            "candidate_source_archive_sha256",
        )
        for field in fields:
            expected = expected_provenance.get(field)
            actual_value = getattr(manifest, field)
            if expected is None or expected != actual_value:
                _fail(
                    "source_mismatch",
                    f"Bundle provenance mismatch for {field}",
                    field=field,
                    expected=expected,
                    actual=actual_value,
                )

    actual = _read_actual_files(root)
    actual.pop(MANIFEST_NAME, None)
    declared = {record.bundle_path: record for record in manifest.resources}
    missing = sorted(declared.keys() - actual.keys())
    unexpected = sorted(actual.keys() - declared.keys())
    if missing:
        _fail(
            "resource_missing",
            "Bundle resources are missing",
            missing=missing,
            unexpected=unexpected,
        )
    if unexpected:
        _fail(
            "resource_unexpected",
            "Bundle contains unexpected resources",
            unexpected=unexpected,
        )

    for bundle_path in sorted(declared):
        record = declared[bundle_path]
        data = actual[bundle_path]
        if len(data) != record.size:
            _fail(
                "resource_size_mismatch",
                "Bundle resource size does not match the manifest",
                path=bundle_path,
                expected=record.size,
                actual=len(data),
            )
    for bundle_path in sorted(declared):
        record = declared[bundle_path]
        digest = hashlib.sha256(actual[bundle_path]).hexdigest()
        if digest != record.sha256:
            _fail(
                "resource_hash_mismatch",
                "Bundle resource digest does not match the manifest",
                path=bundle_path,
                expected=record.sha256,
                actual=digest,
            )

    partition_counts = {
        kind: sum(record.kind == kind for record in manifest.resources)
        for kind in ("skill", "viewer", "host-adapter")
    }
    adapter_partition_counts = {
        adapter_id: sum(
            record.kind == "host-adapter"
            and record.adapter_id == adapter_id
            for record in manifest.resources
        )
        for adapter_id in sorted(
            {
                record.adapter_id
                for record in manifest.resources
                if record.kind == "host-adapter"
                and record.adapter_id is not None
            }
        )
    }
    return BundleInspection(
        manifest=manifest,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        resource_count=len(manifest.resources),
        partition_counts=partition_counts,
        adapter_partition_counts=adapter_partition_counts,
    )


__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "BundleInspection",
    "BundleManifest",
    "BundleValidationError",
    "MANIFEST_NAME",
    "RUNTIME_TREE_SCHEMA",
    "ResourceRecord",
    "SOURCE_STATE",
    "inspect_bundle",
    "parse_manifest",
]
