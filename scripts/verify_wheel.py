"""Seal a work-order candidate and verify reproducible Stage 1 wheels."""

from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


EXPECTED_DISTRIBUTION = "xcoding-workflow-spike"
EXPECTED_NORMALIZED_DISTRIBUTION = "xcoding_workflow_spike"
EXPECTED_VERSION = "0.0.0.dev0"
EXPECTED_TAG = "py3-none-any"
EXPECTED_WHEEL_FILENAME = (
    f"{EXPECTED_NORMALIZED_DISTRIBUTION}-{EXPECTED_VERSION}-{EXPECTED_TAG}.whl"
)
EXPECTED_DIST_INFO = (
    f"{EXPECTED_NORMALIZED_DISTRIBUTION}-{EXPECTED_VERSION}.dist-info"
)
EXPECTED_PYTHON_REQUIRES = ">=3.12,<3.13"
EXPECTED_SOURCE_STATE = "work-order-candidate"
EXPECTED_BUNDLE_SCHEMA = 1
EXPECTED_RUNTIME_SCHEMA = 1
MANIFEST_MEMBER = "xcoding/_bundle/bundle-manifest.json"

_LOWER_HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_HASH = re.compile(r"sha256=([A-Za-z0-9_-]{43})\Z")
_GIT_FILE_MODES = {"100644", "100755"}
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


class VerificationError(RuntimeError):
    """Fail-closed verification error with structured details."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True)
class CandidateFile:
    mode: str
    path: str
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True)
class WheelInspection:
    path: Path
    sha256: str
    size: int
    members: Mapping[str, bytes]
    zip_metadata: tuple[tuple[Any, ...], ...]
    archive_comment: bytes
    manifest: Mapping[str, Any]


def _fail(code: str, message: str, **details: Any) -> None:
    raise VerificationError(code, message, details=details)


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


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    return bool(os_is_junction and os_is_junction(path))


def _existing_directory(value: Path | str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail("path_invalid", f"{label} must be absolute", path=str(path))
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        _fail("path_invalid", f"{label} is unavailable", path=str(path), error=str(error))
    if _is_link_or_junction(path) or not resolved.is_dir():
        _fail(
            "path_invalid",
            f"{label} must be a physical directory",
            path=str(path),
        )
    return resolved


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_roots(
    project_root: Path | str,
    disposable_root: Path | str,
) -> tuple[Path, Path]:
    project = _existing_directory(project_root, label="project_root")
    disposable = _existing_directory(disposable_root, label="disposable_root")
    if _is_relative_to(disposable, project) or _is_relative_to(project, disposable):
        _fail(
            "path_invalid",
            "disposable_root and project_root must be disjoint",
            project_root=str(project),
            disposable_root=str(disposable),
        )
    return project, disposable


def _external_output_path(
    value: Path | str,
    disposable_root: Path,
    *,
    label: str,
    must_exist: bool,
    directory: bool = False,
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail("path_invalid", f"{label} must be absolute", path=str(path))
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as error:
        _fail("path_invalid", f"{label} is unavailable", path=str(path), error=str(error))
    if not _is_relative_to(resolved, disposable_root) or resolved == disposable_root:
        _fail(
            "path_invalid",
            f"{label} must be below disposable_root",
            path=str(resolved),
            disposable_root=str(disposable_root),
        )
    if must_exist:
        if _is_link_or_junction(path):
            _fail("path_invalid", f"{label} must not be a link", path=str(path))
        if directory != resolved.is_dir():
            expected = "directory" if directory else "file"
            _fail("path_invalid", f"{label} must be a {expected}", path=str(path))
    else:
        parent = resolved.parent.resolve(strict=True)
        if not _is_relative_to(parent, disposable_root):
            _fail("path_invalid", f"{label} parent escapes disposable_root")
        if resolved.exists() or resolved.is_symlink():
            _fail("path_invalid", f"{label} must not already exist", path=str(resolved))
    return resolved


def _validate_relative_path(value: str, *, label: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        _fail("path_unsafe", f"{label} is not a safe POSIX relative path", path=value)
    if value.startswith("/") or re.match(r"[A-Za-z]:", value):
        _fail("path_unsafe", f"{label} must be relative", path=value)
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _fail("path_unsafe", f"{label} contains an unsafe segment", path=value)
    if PurePosixPath(value).is_absolute():
        _fail("path_unsafe", f"{label} must be relative", path=value)
    if any(any(ord(character) < 32 for character in part) for part in parts):
        _fail("path_unsafe", f"{label} contains a control character", path=value)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("path_unsafe", f"{label} is not valid UTF-8", path=repr(value))
    return value


def _validate_path_set(paths: Iterable[str], *, label: str) -> list[str]:
    values = list(paths)
    exact: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for value in values:
        _validate_relative_path(value, label=label)
        keys = (
            ("duplicate", value, exact),
            ("casefold", value.casefold(), casefolded),
            ("nfc", unicodedata.normalize("NFC", value), normalized),
        )
        for collision, key, seen in keys:
            if key in seen:
                _fail(
                    "path_collision",
                    f"{label} has a {collision} collision",
                    first=seen[key],
                    second=value,
                    collision=collision,
                )
        exact[value] = value
        casefolded[value.casefold()] = value
        normalized[unicodedata.normalize("NFC", value)] = value
    return values


def _run_git(
    project_root: Path,
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    process_environment = os.environ.copy()
    if environment is not None:
        process_environment.update(environment)
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *arguments],
            env=process_environment,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        _fail("candidate_invalid", f"cannot execute Git: {error}")
    if result.returncode != 0:
        _fail(
            "candidate_invalid",
            "Git candidate operation failed",
            argv=list(arguments),
            stdout=result.stdout.decode("utf-8", errors="replace"),
            stderr=result.stderr.decode("utf-8", errors="replace"),
        )
    return result.stdout


def _current_changed_paths(project_root: Path) -> list[str]:
    output = _run_git(
        project_root,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )
    paths: list[str] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            _fail("candidate_invalid", "cannot parse Git status record")
        status_bytes = record[:2]
        if b"R" in status_bytes or b"C" in status_bytes:
            _fail(
                "candidate_invalid",
                "renames and copies must be represented as explicit delete/add paths",
            )
        try:
            path = record[3:].decode("utf-8")
        except UnicodeDecodeError:
            _fail("candidate_invalid", "candidate path is not UTF-8")
        paths.append(_validate_relative_path(path, label="candidate_path"))
    return sorted(_validate_path_set(paths, label="candidate_path"))


def _candidate_inventory(
    project_root: Path,
    disposable_root: Path,
    baseline_revision: str,
    candidate_paths: Sequence[str],
) -> tuple[str, list[CandidateFile]]:
    object_root = disposable_root / ".candidate-git-objects"
    index_path = disposable_root / ".candidate-index"
    if object_root.exists() or index_path.exists():
        _fail(
            "path_invalid",
            "candidate temporary Git paths already exist",
            object_root=str(object_root),
            index_path=str(index_path),
        )
    object_root.mkdir()
    original_objects = Path(
        os.fsdecode(_run_git(project_root, ["rev-parse", "--git-path", "objects"])).strip()
    )
    if not original_objects.is_absolute():
        original_objects = (project_root / original_objects).resolve(strict=True)
    environment = {
        "GIT_INDEX_FILE": str(index_path),
        "GIT_OBJECT_DIRECTORY": str(object_root),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(original_objects),
    }
    try:
        _run_git(project_root, ["read-tree", baseline_revision], environment=environment)
        _run_git(
            project_root,
            ["add", "-A", "--", *candidate_paths],
            environment=environment,
        )
        tree_oid = os.fsdecode(
            _run_git(project_root, ["write-tree"], environment=environment)
        ).strip()
        tree_output = _run_git(
            project_root,
            ["ls-tree", "-r", "-z", "--full-tree", tree_oid],
            environment=environment,
        )
        inventory: list[CandidateFile] = []
        for record in tree_output.split(b"\0"):
            if not record:
                continue
            try:
                metadata, raw_path = record.split(b"\t", 1)
                mode_bytes, type_bytes, oid_bytes = metadata.split()
                mode = mode_bytes.decode("ascii")
                object_type = type_bytes.decode("ascii")
                oid = oid_bytes.decode("ascii")
                path = raw_path.decode("utf-8")
            except (ValueError, UnicodeError):
                _fail("candidate_invalid", "candidate tree has an invalid record")
            if object_type != "blob" or mode not in _GIT_FILE_MODES:
                _fail(
                    "candidate_invalid",
                    "candidate tree contains an unsupported entry",
                    path=path,
                    mode=mode,
                    object_type=object_type,
                )
            _validate_relative_path(path, label="candidate_tree.path")
            data = _run_git(
                project_root,
                ["cat-file", "blob", oid],
                environment=environment,
            )
            inventory.append(CandidateFile(mode=mode, path=path, data=data))
        inventory.sort(key=lambda item: item.path.encode("utf-8"))
        _validate_path_set((item.path for item in inventory), label="candidate_tree.path")
        return tree_oid, inventory
    finally:
        if index_path.exists():
            index_path.unlink()
        shutil.rmtree(object_root, ignore_errors=True)


def _candidate_tree_digest(inventory: Sequence[CandidateFile]) -> str:
    digest = hashlib.sha256()
    digest.update(b"xc-candidate-tree-v1\0")
    for item in inventory:
        path_bytes = item.path.encode("utf-8")
        digest.update(item.mode.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(len(path_bytes)).encode("ascii"))
        digest.update(b"\0")
        digest.update(path_bytes)
        digest.update(b"\0")
        digest.update(bytes.fromhex(item.sha256))
    return digest.hexdigest()


def _write_candidate_archive(path: Path, inventory: Sequence[CandidateFile]) -> None:
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as archive:
            archive.comment = b""
            for item in inventory:
                info = zipfile.ZipInfo(item.path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = int(item.mode, 8) << 16
                info.internal_attr = 0
                info.comment = b""
                info.extra = b""
                archive.writestr(info, item.data)
    except (OSError, zipfile.BadZipFile) as error:
        _fail("candidate_invalid", f"cannot write candidate archive: {error}")


def seal_candidate(
    *,
    project_root: Path | str,
    disposable_root: Path | str,
    baseline_revision: str,
    candidate_paths: Sequence[str],
    archive_path: Path | str,
    descriptor_path: Path | str,
) -> dict[str, Any]:
    """Seal the complete baseline plus exact current candidate changes."""
    project, disposable = _validate_roots(project_root, disposable_root)
    archive = _external_output_path(
        archive_path,
        disposable,
        label="archive_path",
        must_exist=False,
    )
    descriptor = _external_output_path(
        descriptor_path,
        disposable,
        label="descriptor_path",
        must_exist=False,
    )
    if archive == descriptor:
        _fail("path_invalid", "archive_path and descriptor_path must differ")
    if not _LOWER_HEX_40.fullmatch(baseline_revision):
        _fail("candidate_invalid", "baseline_revision must be 40 lowercase hex")
    head = os.fsdecode(_run_git(project, ["rev-parse", "HEAD"])).strip()
    if head != baseline_revision:
        _fail(
            "candidate_invalid",
            "baseline_revision must equal the current HEAD",
            expected=head,
            actual=baseline_revision,
        )
    top_level = Path(
        os.fsdecode(_run_git(project, ["rev-parse", "--show-toplevel"])).strip()
    ).resolve(strict=True)
    if top_level != project:
        _fail("candidate_invalid", "project_root must be the Git top level")

    supplied_paths = sorted(
        _validate_path_set(candidate_paths, label="candidate_path")
    )
    actual_paths = _current_changed_paths(project)
    if supplied_paths != actual_paths:
        _fail(
            "candidate_invalid",
            "candidate paths must exactly match the current Git status",
            missing=sorted(set(actual_paths) - set(supplied_paths)),
            unexpected=sorted(set(supplied_paths) - set(actual_paths)),
        )
    if not supplied_paths:
        _fail("candidate_invalid", "candidate must contain at least one changed path")

    tree_oid, inventory = _candidate_inventory(
        project,
        disposable,
        baseline_revision,
        supplied_paths,
    )
    candidate_tree_sha256 = _candidate_tree_digest(inventory)
    try:
        _write_candidate_archive(archive, inventory)
        candidate_archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        descriptor_value = {
            "schema_version": 1,
            "baseline_revision": baseline_revision,
            "source_state": EXPECTED_SOURCE_STATE,
            "candidate_tree_sha256": candidate_tree_sha256,
            "candidate_source_archive_sha256": candidate_archive_sha256,
            "candidate_git_tree": tree_oid,
            "candidate_paths": supplied_paths,
            "tree_digest_format": "xc-candidate-tree-v1",
            "archive_format": "zip-stored-fixed-metadata-v1",
            "files": [
                {
                    "mode": item.mode,
                    "path": item.path,
                    "size": len(item.data),
                    "sha256": item.sha256,
                }
                for item in inventory
            ],
        }
        descriptor.write_bytes(_canonical_json_bytes(descriptor_value))
    except BaseException:
        archive.unlink(missing_ok=True)
        descriptor.unlink(missing_ok=True)
        raise
    return {
        "baseline_revision": baseline_revision,
        "source_state": EXPECTED_SOURCE_STATE,
        "candidate_tree_sha256": candidate_tree_sha256,
        "candidate_source_archive_sha256": candidate_archive_sha256,
        "candidate_git_tree": tree_oid,
        "candidate_path_count": len(supplied_paths),
        "candidate_file_count": len(inventory),
        "archive_path": str(archive),
        "descriptor_path": str(descriptor),
    }


def _load_strict_json(data: bytes, *, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _fail("manifest_invalid", f"{label} has duplicate key {key!r}")
            value[key] = item
        return value

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        _fail("manifest_invalid", f"{label} is not valid UTF-8 JSON: {error}")
    if not isinstance(value, dict):
        _fail("manifest_invalid", f"{label} root must be an object")
    if _canonical_json_bytes(value) != data:
        _fail("manifest_invalid", f"{label} is not canonical JSON")
    return value


def _single_header(message: Any, name: str, *, label: str) -> str:
    values = message.get_all(name, [])
    if len(values) != 1:
        _fail(
            "metadata_invalid",
            f"{label} must contain exactly one {name} header",
            count=len(values),
        )
    return str(values[0])


def _verify_core_metadata(members: Mapping[str, bytes], expected_tag: str) -> None:
    metadata_name = f"{EXPECTED_DIST_INFO}/METADATA"
    wheel_name = f"{EXPECTED_DIST_INFO}/WHEEL"
    entry_points_name = f"{EXPECTED_DIST_INFO}/entry_points.txt"
    for required in (
        "xcoding/__init__.py",
        "xcoding/__main__.py",
        "xcoding/cli.py",
        "xcoding/runtime/__init__.py",
        "xcoding/runtime/application.py",
        "xcoding/runtime/commands.py",
        "xcoding/runtime/core.py",
        "xcoding/runtime/query.py",
        "xcoding/runtime/assets/minimal-template.xml",
        "xcoding/viewer/__init__.py",
        "xcoding/viewer/cli.py",
        "xcoding/viewer/picker.py",
        "xcoding/viewer/server.py",
        "xcoding/viewer/static/app.css",
        "xcoding/viewer/static/app.js",
        "xcoding/viewer/static/index.html",
        "xcoding/daemon/__init__.py",
        "xcoding/daemon/cli.py",
        "xcoding/daemon/protocol.py",
        "xcoding/daemon/server.py",
        MANIFEST_MEMBER,
        metadata_name,
        wheel_name,
        entry_points_name,
        f"{EXPECTED_DIST_INFO}/RECORD",
    ):
        if required not in members:
            _fail("member_missing", "wheel is missing a required member", member=required)

    parser = BytesParser(policy=policy.default)
    metadata = parser.parsebytes(members[metadata_name])
    if metadata.defects:
        _fail("metadata_invalid", "METADATA has parser defects")
    expected_headers = {
        "Name": EXPECTED_DISTRIBUTION,
        "Version": EXPECTED_VERSION,
    }
    for name, expected in expected_headers.items():
        actual = _single_header(metadata, name, label="METADATA")
        if actual != expected:
            _fail(
                "metadata_invalid",
                f"METADATA {name} mismatch",
                expected=expected,
                actual=actual,
            )
    actual_python_requires = _single_header(
        metadata,
        "Requires-Python",
        label="METADATA",
    )
    if {
        item.strip() for item in actual_python_requires.split(",")
    } != {
        item.strip() for item in EXPECTED_PYTHON_REQUIRES.split(",")
    }:
        _fail(
            "metadata_invalid",
            "METADATA Requires-Python mismatch",
            expected=EXPECTED_PYTHON_REQUIRES,
            actual=actual_python_requires,
        )

    wheel = parser.parsebytes(members[wheel_name])
    if wheel.defects:
        _fail("metadata_invalid", "WHEEL has parser defects")
    expected_wheel_headers = {
        "Wheel-Version": "1.0",
        "Root-Is-Purelib": "true",
        "Tag": expected_tag,
    }
    for name, expected in expected_wheel_headers.items():
        actual = _single_header(wheel, name, label="WHEEL")
        if actual != expected:
            _fail(
                "metadata_invalid",
                f"WHEEL {name} mismatch",
                expected=expected,
                actual=actual,
            )

    entry_points = configparser.ConfigParser(interpolation=None, strict=True)
    entry_points.optionxform = str
    try:
        entry_points.read_string(members[entry_points_name].decode("utf-8"))
    except (UnicodeError, configparser.Error) as error:
        _fail("metadata_invalid", f"entry_points.txt is invalid: {error}")
    if entry_points.sections() != ["console_scripts"]:
        _fail("metadata_invalid", "entry_points.txt has unexpected sections")
    if dict(entry_points.items("console_scripts")) != {
        "xcoding": "xcoding.cli:main"
    }:
        _fail("metadata_invalid", "entry_points.txt console script mismatch")


def _verify_record(members: Mapping[str, bytes]) -> None:
    record_name = f"{EXPECTED_DIST_INFO}/RECORD"
    try:
        text = members[record_name].decode("utf-8")
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except (UnicodeError, csv.Error) as error:
        _fail("record_invalid", f"RECORD is invalid UTF-8 CSV: {error}")
    records: dict[str, tuple[str, str]] = {}
    for index, row in enumerate(rows):
        if len(row) != 3:
            _fail("record_invalid", "RECORD row must have three fields", row=index)
        path, encoded_hash, encoded_size = row
        _validate_relative_path(path, label=f"RECORD[{index}].path")
        if path in records:
            _fail("record_invalid", "RECORD has a duplicate path", path=path)
        records[path] = (encoded_hash, encoded_size)
    if set(records) != set(members):
        _fail(
            "record_invalid",
            "RECORD path set does not equal the wheel member set",
            missing=sorted(set(members) - set(records)),
            unexpected=sorted(set(records) - set(members)),
        )
    for path in sorted(members):
        encoded_hash, encoded_size = records[path]
        if path == record_name:
            if encoded_hash or encoded_size:
                _fail("record_invalid", "RECORD must leave its own hash and size empty")
            continue
        match = _RECORD_HASH.fullmatch(encoded_hash)
        if match is None:
            _fail("record_invalid", "RECORD member must use unpadded SHA-256", path=path)
        try:
            recorded_digest = base64.urlsafe_b64decode(match.group(1) + "=")
        except ValueError:
            _fail("record_invalid", "RECORD member hash is invalid", path=path)
        actual_digest = hashlib.sha256(members[path]).digest()
        if recorded_digest != actual_digest:
            _fail("record_invalid", "RECORD member hash mismatch", path=path)
        if not encoded_size.isdecimal() or str(int(encoded_size)) != encoded_size:
            _fail("record_invalid", "RECORD member size is not canonical", path=path)
        if int(encoded_size) != len(members[path]):
            _fail(
                "record_invalid",
                "RECORD member size mismatch",
                path=path,
                expected=len(members[path]),
                actual=int(encoded_size),
            )


def _verify_manifest(
    members: Mapping[str, bytes],
    *,
    baseline_revision: str,
    candidate_tree_sha256: str,
    candidate_source_archive_sha256: str,
) -> dict[str, Any]:
    manifest_data = members[MANIFEST_MEMBER]
    manifest = _load_strict_json(manifest_data, label="Bundle manifest")
    if set(manifest) != _MANIFEST_FIELDS:
        _fail(
            "manifest_invalid",
            "Bundle manifest fields are not exact",
            missing=sorted(_MANIFEST_FIELDS - set(manifest)),
            unexpected=sorted(set(manifest) - _MANIFEST_FIELDS),
        )
    expected_values = {
        "bundle_schema_version": EXPECTED_BUNDLE_SCHEMA,
        "xc_version": EXPECTED_VERSION,
        "baseline_revision": baseline_revision,
        "source_state": EXPECTED_SOURCE_STATE,
        "candidate_tree_sha256": candidate_tree_sha256,
        "candidate_source_archive_sha256": candidate_source_archive_sha256,
        "python_requires": EXPECTED_PYTHON_REQUIRES,
        "runtime_tree_schema": EXPECTED_RUNTIME_SCHEMA,
    }
    for field, expected in expected_values.items():
        if manifest[field] != expected:
            _fail(
                "manifest_invalid",
                f"Bundle manifest {field} mismatch",
                field=field,
                expected=expected,
                actual=manifest[field],
            )
    resources = manifest["resources"]
    if not isinstance(resources, list) or not resources:
        _fail("manifest_invalid", "Bundle manifest resources must be non-empty")
    bundle_prefix = "xcoding/_bundle/"
    actual_bundle_paths = {
        path.removeprefix(bundle_prefix)
        for path in members
        if path.startswith(bundle_prefix) and path != MANIFEST_MEMBER
    }
    declared: dict[str, dict[str, Any]] = {}
    previous_path = ""
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict) or set(resource) != _RESOURCE_FIELDS:
            _fail("manifest_invalid", "Bundle resource fields are not exact", index=index)
        bundle_path = resource["bundle_path"]
        source_path = resource["source_path"]
        if not isinstance(bundle_path, str) or not isinstance(source_path, str):
            _fail("manifest_invalid", "Bundle resource paths must be strings", index=index)
        _validate_relative_path(bundle_path, label=f"resources[{index}].bundle_path")
        _validate_relative_path(source_path, label=f"resources[{index}].source_path")
        if bundle_path <= previous_path or bundle_path in declared:
            _fail("manifest_invalid", "Bundle resources are not uniquely sorted")
        previous_path = bundle_path
        if resource["kind"] not in {"skill", "viewer", "host-adapter"}:
            _fail("manifest_invalid", "Bundle resource kind is invalid", index=index)
        if (
            not isinstance(resource["size"], int)
            or isinstance(resource["size"], bool)
            or resource["size"] < 0
        ):
            _fail("manifest_invalid", "Bundle resource size is invalid", index=index)
        digest = resource["sha256"]
        if not isinstance(digest, str) or not _LOWER_HEX_64.fullmatch(digest):
            _fail("manifest_invalid", "Bundle resource hash is invalid", index=index)
        declared[bundle_path] = resource
    _validate_path_set(declared, label="Bundle resource path")
    if set(declared) != actual_bundle_paths:
        _fail(
            "manifest_invalid",
            "Bundle manifest path set does not equal wheel Bundle members",
            missing=sorted(actual_bundle_paths - set(declared)),
            unexpected=sorted(set(declared) - actual_bundle_paths),
        )
    for bundle_path, resource in declared.items():
        data = members[f"{bundle_prefix}{bundle_path}"]
        if len(data) != resource["size"]:
            _fail("manifest_invalid", "Bundle resource size mismatch", path=bundle_path)
        if hashlib.sha256(data).hexdigest() != resource["sha256"]:
            _fail("manifest_invalid", "Bundle resource hash mismatch", path=bundle_path)
    return manifest


def _zip_metadata(info: zipfile.ZipInfo) -> tuple[Any, ...]:
    return (
        info.filename,
        info.date_time,
        info.compress_type,
        info.comment,
        info.extra,
        info.create_system,
        info.create_version,
        info.extract_version,
        info.flag_bits,
        info.volume,
        info.internal_attr,
        info.external_attr,
        info.CRC,
        info.compress_size,
        info.file_size,
    )


def inspect_wheel(
    path: Path,
    *,
    expected_tag: str,
    baseline_revision: str,
    candidate_tree_sha256: str,
    candidate_source_archive_sha256: str,
) -> WheelInspection:
    """Verify one fixed Stage 1 wheel without extracting it."""
    wheel_bytes = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes), mode="r") as archive:
            if archive.testzip() is not None:
                _fail("wheel_invalid", "wheel has a member with a bad CRC")
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _validate_path_set(names, label="wheel member")
            members: dict[str, bytes] = {}
            metadata: list[tuple[Any, ...]] = []
            for info in infos:
                name = _validate_relative_path(info.filename, label="wheel member")
                if info.is_dir() or name.endswith("/"):
                    _fail("member_unsafe", "wheel must not contain directory members", member=name)
                if info.flag_bits & 0x1:
                    _fail("member_unsafe", "wheel member must not be encrypted", member=name)
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type not in {0, stat.S_IFREG}:
                    _fail(
                        "member_unsafe",
                        "wheel member must be a regular file",
                        member=name,
                        mode=oct(mode),
                    )
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    _fail(
                        "member_unsafe",
                        "wheel member uses an unsupported compression method",
                        member=name,
                    )
                if not (
                    name.startswith("xcoding/")
                    or name.startswith(f"{EXPECTED_DIST_INFO}/")
                ):
                    _fail(
                        "member_unexpected",
                        "wheel member is outside the fixed package layout",
                        member=name,
                    )
                if "__pycache__" in name.split("/") or name.endswith((".pyc", ".pyo")):
                    _fail("member_unexpected", "wheel contains bytecode", member=name)
                members[name] = archive.read(info)
                metadata.append(_zip_metadata(info))
            archive_comment = archive.comment
    except (OSError, zipfile.BadZipFile) as error:
        _fail("wheel_invalid", f"cannot read wheel: {error}")

    _verify_core_metadata(members, expected_tag)
    _verify_record(members)
    manifest = _verify_manifest(
        members,
        baseline_revision=baseline_revision,
        candidate_tree_sha256=candidate_tree_sha256,
        candidate_source_archive_sha256=candidate_source_archive_sha256,
    )
    return WheelInspection(
        path=path,
        sha256=hashlib.sha256(wheel_bytes).hexdigest(),
        size=len(wheel_bytes),
        members=members,
        zip_metadata=tuple(metadata),
        archive_comment=archive_comment,
        manifest=manifest,
    )


def _sole_wheel(output_directory: Path) -> Path:
    entries = sorted(output_directory.iterdir(), key=lambda item: item.name)
    if any(_is_link_or_junction(entry) or not entry.is_file() for entry in entries):
        _fail(
            "wheel_output_invalid",
            "wheel output directory must contain only one regular file",
            entries=[entry.name for entry in entries],
        )
    if [entry.name for entry in entries] != [EXPECTED_WHEEL_FILENAME]:
        _fail(
            "wheel_output_invalid",
            "wheel output directory does not contain exactly the expected wheel",
            expected=EXPECTED_WHEEL_FILENAME,
            actual=[entry.name for entry in entries],
        )
    return entries[0]


def verify_reproducible_wheels(
    *,
    project_root: Path | str,
    disposable_root: Path | str,
    first_directory: Path | str,
    second_directory: Path | str,
    expected_tag: str,
    baseline_revision: str,
    candidate_tree_sha256: str,
    candidate_source_archive_sha256: str,
) -> dict[str, Any]:
    """Verify two independently built wheels and prove byte identity."""
    project, disposable = _validate_roots(project_root, disposable_root)
    del project
    first_output = _external_output_path(
        first_directory,
        disposable,
        label="first_directory",
        must_exist=True,
        directory=True,
    )
    second_output = _external_output_path(
        second_directory,
        disposable,
        label="second_directory",
        must_exist=True,
        directory=True,
    )
    if first_output == second_output:
        _fail("path_invalid", "wheel output directories must be distinct")
    if expected_tag != EXPECTED_TAG:
        _fail("wheel_invalid", "expected_tag must be py3-none-any")
    if not _LOWER_HEX_40.fullmatch(baseline_revision):
        _fail("candidate_invalid", "baseline_revision must be 40 lowercase hex")
    for field, value in (
        ("candidate_tree_sha256", candidate_tree_sha256),
        ("candidate_source_archive_sha256", candidate_source_archive_sha256),
    ):
        if not _LOWER_HEX_64.fullmatch(value):
            _fail("candidate_invalid", f"{field} must be 64 lowercase hex")

    first = inspect_wheel(
        _sole_wheel(first_output),
        expected_tag=expected_tag,
        baseline_revision=baseline_revision,
        candidate_tree_sha256=candidate_tree_sha256,
        candidate_source_archive_sha256=candidate_source_archive_sha256,
    )
    second = inspect_wheel(
        _sole_wheel(second_output),
        expected_tag=expected_tag,
        baseline_revision=baseline_revision,
        candidate_tree_sha256=candidate_tree_sha256,
        candidate_source_archive_sha256=candidate_source_archive_sha256,
    )
    differences: list[str] = []
    if list(first.members) != list(second.members):
        differences.append("member-order")
    if first.members != second.members:
        differences.append("member-bytes")
    if first.zip_metadata != second.zip_metadata:
        differences.append("zip-metadata")
    if first.archive_comment != second.archive_comment:
        differences.append("archive-comment")
    if first.sha256 != second.sha256 or first.path.read_bytes() != second.path.read_bytes():
        differences.append("wheel-bytes")
    if differences:
        _fail(
            "wheel_not_reproducible",
            "independent wheel builds are not byte-identical",
            differences=differences,
            first_sha256=first.sha256,
            second_sha256=second.sha256,
        )
    return {
        "wheel_filename": EXPECTED_WHEEL_FILENAME,
        "wheel_sha256": first.sha256,
        "wheel_size": first.size,
        "member_count": len(first.members),
        "members_byte_identical": True,
        "zip_metadata_byte_identical": True,
        "wheel_byte_identical": True,
        "baseline_revision": baseline_revision,
        "source_state": EXPECTED_SOURCE_STATE,
        "candidate_tree_sha256": candidate_tree_sha256,
        "candidate_source_archive_sha256": candidate_source_archive_sha256,
        "bundle_manifest_sha256": hashlib.sha256(
            first.members[MANIFEST_MEMBER]
        ).hexdigest(),
        "first_wheel": str(first.path),
        "second_wheel": str(second.path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    candidate = subparsers.add_parser(
        "candidate",
        help="seal current candidate bytes against the current HEAD baseline",
    )
    candidate.add_argument("--project-root", type=Path, required=True)
    candidate.add_argument("--disposable-root", type=Path, required=True)
    candidate.add_argument("--baseline-revision", required=True)
    candidate.add_argument("--candidate-path", action="append", required=True)
    candidate.add_argument("--archive", type=Path, required=True)
    candidate.add_argument("--descriptor", type=Path, required=True)

    wheel = subparsers.add_parser(
        "wheel",
        help="verify two independently built Stage 1 wheels",
    )
    wheel.add_argument("--project-root", type=Path, required=True)
    wheel.add_argument("--disposable-root", type=Path, required=True)
    wheel.add_argument("--first", type=Path, required=True)
    wheel.add_argument("--second", type=Path, required=True)
    wheel.add_argument("--expected-tag", required=True)
    wheel.add_argument("--baseline-revision", required=True)
    wheel.add_argument("--candidate-tree-sha256", required=True)
    wheel.add_argument("--candidate-source-archive-sha256", required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(arguments)
    try:
        if options.operation == "candidate":
            result = seal_candidate(
                project_root=options.project_root,
                disposable_root=options.disposable_root,
                baseline_revision=options.baseline_revision,
                candidate_paths=options.candidate_path,
                archive_path=options.archive,
                descriptor_path=options.descriptor,
            )
        else:
            result = verify_reproducible_wheels(
                project_root=options.project_root,
                disposable_root=options.disposable_root,
                first_directory=options.first,
                second_directory=options.second,
                expected_tag=options.expected_tag,
                baseline_revision=options.baseline_revision,
                candidate_tree_sha256=options.candidate_tree_sha256,
                candidate_source_archive_sha256=(
                    options.candidate_source_archive_sha256
                ),
            )
    except VerificationError as error:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": False,
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "details": error.details,
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(
        json.dumps(
            {"schema_version": 1, "ok": True, "result": result},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
