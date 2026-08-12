"""Validate and summarize Stage 1 package-spike matrix evidence.

The driver is provider-neutral and deliberately does not manufacture runner
results. External runners execute the approved package checks and emit one
canonical cell-evidence document per required cell. This module verifies the
digest-addressed candidate inputs, validates those documents, and promotes the
provisional pin only when all three required cells contain matching pass
evidence.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import platform
import re
import stat
import sys
import unicodedata
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
CELL_EVIDENCE_KIND = "xc-stage1-package-spike-cell"
SUMMARY_EVIDENCE_KIND = "xc-stage1-package-spike-summary"
EXPECTED_WHEEL_FILENAME = (
    "xcoding_workflow_spike-0.0.0.dev0-py3-none-any.whl"
)
MANIFEST_MEMBER = "xcoding/_bundle/bundle-manifest.json"
TOOLCHAIN_MEMBER = "build_support/stage1_toolchain.json"
REQUIRED_CELLS = (
    "windows-x86_64",
    "linux-x86_64-gnu",
    "macos-recorded-arch",
)
REQUIRED_COMMANDS = (
    "candidate-preflight",
    "wheel-preflight",
    "uv-version",
    "managed-python-find",
    "install",
    "repeat-install",
    "package-tests",
    "version",
    "bundle-inspect",
    "doctor",
    "setup-dry-run",
    "failure-injections",
    "uninstall",
    "cleanup",
)
WINDOWS_COMMAND = "windows-console-oracle"
REQUIRED_CHECKS = (
    "candidate-provenance",
    "wheel-provenance",
    "platform-identity",
    "standard-user",
    "uv-pin",
    "managed-python",
    "package-tests",
    "resource-negatives",
    "install",
    "repeat-install",
    "four-commands",
    "dry-run-no-write",
    "failure-cleanup",
    "uninstall-ownership",
    "unicode-paths",
    "long-paths",
    "no-tk",
    "path-warning",
    "readonly-target",
    "permissions",
    "windows-console-oracle",
    "fixture-cleanup",
)

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_GIT_OID = re.compile(r"[0-9a-f]{40,64}\Z")
_GIT_MODES = {"100644", "100755"}
_CELL_STATUSES = {"passed", "failed", "unrun"}
_CHECK_STATUSES = {"passed", "failed", "unrun", "not-applicable"}
_COMMAND_STATUSES = {"passed", "failed", "unrun"}
_ATTESTATION_KIND = "xc-stage1-hmac-execution-attestation"
_ATTESTATION_ALGORITHM = "hmac-sha256"
_MAX_BOUND_OUTPUT_BYTES = 16 * 1024 * 1024
_CANDIDATE_DESCRIPTOR_SCHEMA = 2

_DESCRIPTOR_FIELDS = {
    "schema_version",
    "baseline_revision",
    "baseline_git_tree",
    "source_state",
    "candidate_origin",
    "candidate_tree_sha256",
    "candidate_source_archive_sha256",
    "candidate_git_tree",
    "candidate_paths",
    "tree_digest_format",
    "archive_format",
    "files",
}
_DESCRIPTOR_FILE_FIELDS = {"mode", "path", "size", "sha256"}
_BINDING_FIELDS = {
    "baseline_revision",
    "candidate_tree_sha256",
    "candidate_source_archive_sha256",
    "candidate_descriptor_sha256",
    "wheel_sha256",
    "wheel_filename",
}
_EVIDENCE_FIELDS = {
    "schema_version",
    "evidence_kind",
    "cell_id",
    "status",
    "execution",
    "bindings",
    "environment",
    "provenance",
    "commands",
    "checks",
    "cleanup",
    "failure",
    "attestation",
}
_EXECUTION_FIELDS = {
    "execution_id",
    "provider",
    "run_id",
    "run_attempt",
    "job_id",
    "runner_name",
    "started_at_utc",
    "finished_at_utc",
}
_ENVIRONMENT_FIELDS = {
    "runner_os",
    "os_name",
    "os_version",
    "os_image",
    "architecture",
    "libc",
    "standard_user",
    "is_root",
    "long_paths_supported",
    "sys_executable",
    "sys_base_executable",
    "sys_version",
    "fixture_root",
    "uv_python_install_dir",
    "uv_tool_dir",
    "uv_tool_bin_dir",
}
_PROVENANCE_FIELDS = {
    "candidate_archive_verified",
    "candidate_descriptor_verified",
    "candidate_tree_verified",
    "wheel_verified",
    "uv_version",
    "uv_version_output",
    "uv_artifact_filename",
    "uv_artifact_sha256",
    "uv_artifact_verified",
    "python_request",
    "python_build_identity",
    "managed_python_find",
    "managed_python_verified",
}
_COMMAND_FIELDS = {
    "id",
    "argv",
    "cwd",
    "expected_exit",
    "exit_code",
    "status",
    "started_at_utc",
    "duration_ms",
    "stdout_sha256",
    "stderr_sha256",
    "stdout_b64",
    "stderr_b64",
}
_CLEANUP_FIELDS = {
    "attempted",
    "fixture_removed",
    "candidate_staging_removed",
    "unexpected_preserved",
    "status",
}
_FAILURE_FIELDS = {"code", "message"}
_ATTESTATION_FIELDS = {
    "kind",
    "algorithm",
    "key_id",
    "runner_identity_sha256",
    "command_contract_sha256",
    "payload_sha256",
    "signature",
}


class MatrixError(RuntimeError):
    """Stable protocol or verification failure."""

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


def _fail(code: str, message: str, **details: Any) -> None:
    raise MatrixError(code, message, details=details)


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


def _attestation_key_id(key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        _fail(
            "attestation_key_invalid",
            "trusted attestation keys must contain at least 32 bytes",
        )
    return hashlib.sha256(b"xc-stage1-attestation-key-v1\0" + key).hexdigest()


def _runner_identity_sha256(execution: Mapping[str, Any]) -> str:
    identity = {
        field: execution[field]
        for field in (
            "provider",
            "run_id",
            "run_attempt",
            "job_id",
            "runner_name",
        )
    }
    return _sha256_bytes(_canonical_json_bytes(identity))


def _command_contract_sha256(commands: Sequence[Mapping[str, Any]]) -> str:
    contract = [
        {
            "id": command["id"],
            "argv": list(command["argv"]),
            "cwd": command["cwd"],
            "expected_exit": command["expected_exit"],
        }
        for command in commands
    ]
    return _sha256_bytes(_canonical_json_bytes(contract))


def _attestation_message(
    *,
    key_id: str,
    runner_identity_sha256: str,
    command_contract_sha256: str,
    payload_sha256: str,
) -> bytes:
    return b"xc-stage1-execution-attestation-v1\0" + _canonical_json_bytes(
        {
            "key_id": key_id,
            "runner_identity_sha256": runner_identity_sha256,
            "command_contract_sha256": command_contract_sha256,
            "payload_sha256": payload_sha256,
        }
    )


def _attest_cell_evidence(
    value: Mapping[str, Any],
    *,
    key: bytes,
    expected_command_contract_sha256: str,
) -> dict[str, Any]:
    """Issue the bounded attestation used by a trusted execution adapter."""
    expected_contract = _require_hash(
        expected_command_contract_sha256,
        field="expected_command_contract_sha256",
    )
    commands = value.get("commands")
    execution = value.get("execution")
    if not isinstance(commands, list) or not all(
        isinstance(command, dict) for command in commands
    ):
        _fail("schema_invalid", "attested commands must be an object array")
    if not isinstance(execution, dict):
        _fail("schema_invalid", "attested execution identity must be an object")
    environment = value.get("environment")
    if not isinstance(environment, dict):
        _fail("schema_invalid", "attested platform identity must be an object")
    current_os, current_architecture, current_libc = _current_platform()
    if (
        environment.get("runner_os") != current_os
        or environment.get("architecture") != current_architecture
        or environment.get("libc") != current_libc
    ):
        _fail(
            "current_platform_mismatch",
            "trusted attestation can only be issued for the current runner platform",
            current_os=current_os,
            current_architecture=current_architecture,
            current_libc=current_libc,
        )
    command_contract = _command_contract_sha256(commands)
    if command_contract != expected_contract:
        _fail(
            "command_contract_mismatch",
            "executed argv does not match the approved command contract",
            expected=expected_contract,
            actual=command_contract,
        )
    key_id = _attestation_key_id(key)
    runner_identity = _runner_identity_sha256(execution)
    payload = dict(value)
    payload.pop("attestation", None)
    payload_sha256 = _sha256_bytes(_canonical_json_bytes(payload))
    signature = hmac.new(
        key,
        _attestation_message(
            key_id=key_id,
            runner_identity_sha256=runner_identity,
            command_contract_sha256=command_contract,
            payload_sha256=payload_sha256,
        ),
        hashlib.sha256,
    ).hexdigest()
    result = dict(value)
    result["attestation"] = {
        "kind": _ATTESTATION_KIND,
        "algorithm": _ATTESTATION_ALGORITHM,
        "key_id": key_id,
        "runner_identity_sha256": runner_identity,
        "command_contract_sha256": command_contract,
        "payload_sha256": payload_sha256,
        "signature": signature,
    }
    return result


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json_bytes(
    data: bytes,
    *,
    label: str,
    require_canonical: bool,
) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail("json_invalid", f"{label} has duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        _fail("json_invalid", f"{label} is not valid UTF-8 JSON: {error}")
    if not isinstance(value, dict):
        _fail("json_invalid", f"{label} root must be an object")
    if require_canonical and _canonical_json_bytes(value) != data:
        _fail("json_not_canonical", f"{label} must be canonical JSON")
    return value


def _regular_file(value: Path | str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail("path_invalid", f"{label} must be absolute", path=str(path))
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        _fail(
            "path_invalid",
            f"{label} is unavailable",
            path=str(path),
            exception=type(error).__name__,
        )
    if path.is_symlink() or not resolved.is_file():
        _fail("path_invalid", f"{label} must be a regular non-link file")
    return resolved


def _output_file(value: Path | str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail("path_invalid", f"{label} must be absolute", path=str(path))
    resolved = path.resolve(strict=False)
    try:
        parent = resolved.parent.resolve(strict=True)
    except OSError as error:
        _fail(
            "path_invalid",
            f"{label} parent is unavailable",
            exception=type(error).__name__,
        )
    if not parent.is_dir() or parent.is_symlink():
        _fail("path_invalid", f"{label} parent must be a physical directory")
    if resolved.exists() and (resolved.is_symlink() or not resolved.is_file()):
        _fail("path_invalid", f"{label} must be a regular file")
    return resolved


def _require_hash(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        _fail("value_invalid", f"{field} must be 64 lowercase hexadecimal")
    return value


def _require_revision(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _REVISION.fullmatch(value) is None:
        _fail("value_invalid", f"{field} must be 40 lowercase hexadecimal")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            "schema_invalid",
            f"{label} fields are not exact",
            missing=sorted(expected - actual),
            unexpected=sorted(actual - expected),
        )


def _require_string(
    value: Any,
    *,
    field: str,
    allow_unknown: bool = False,
) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("schema_invalid", f"{field} must be a non-empty string")
    if not allow_unknown and value == "unknown":
        _fail("schema_invalid", f"{field} must be recorded")
    return value


def _validate_relative_path(value: str, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "\x00" in value
        or value.startswith("/")
        or re.match(r"[A-Za-z]:", value)
    ):
        _fail("path_unsafe", f"{field} is not a safe POSIX relative path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _fail("path_unsafe", f"{field} contains an unsafe segment")
    if PurePosixPath(value).is_absolute():
        _fail("path_unsafe", f"{field} must be relative")
    if any(any(ord(character) < 32 for character in part) for part in parts):
        _fail("path_unsafe", f"{field} contains a control character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("path_unsafe", f"{field} is not valid UTF-8")
    return value


def _validate_path_set(paths: Iterable[str], *, field: str) -> list[str]:
    values = list(paths)
    exact: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for value in values:
        _validate_relative_path(value, field=field)
        keys = (
            ("duplicate", value, exact),
            ("casefold", value.casefold(), casefolded),
            ("nfc", unicodedata.normalize("NFC", value), normalized),
        )
        for collision, key, seen in keys:
            if key in seen:
                _fail(
                    "path_collision",
                    f"{field} has a {collision} collision",
                    first=seen[key],
                    second=value,
                )
        exact[value] = value
        casefolded[value.casefold()] = value
        normalized[unicodedata.normalize("NFC", value)] = value
    return values


def _candidate_tree_digest(files: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"xc-candidate-tree-v1\0")
    for item in files:
        path_bytes = str(item["path"]).encode("utf-8")
        digest.update(str(item["mode"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(len(path_bytes)).encode("ascii"))
        digest.update(b"\0")
        digest.update(path_bytes)
        digest.update(b"\0")
        digest.update(bytes.fromhex(str(item["sha256"])))
    return digest.hexdigest()


def _verify_descriptor(
    data: bytes,
    *,
    expected_descriptor_sha256: str,
    expected_archive_sha256: str,
    expected_tree_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if _sha256_bytes(data) != expected_descriptor_sha256:
        _fail("descriptor_digest_mismatch", "candidate descriptor SHA-256 mismatch")
    descriptor = _load_json_bytes(
        data,
        label="candidate descriptor",
        require_canonical=True,
    )
    _require_exact_fields(
        descriptor,
        _DESCRIPTOR_FIELDS,
        label="candidate descriptor",
    )
    if (
        descriptor["schema_version"] != _CANDIDATE_DESCRIPTOR_SCHEMA
        or descriptor["source_state"] != "work-order-candidate"
        or descriptor["tree_digest_format"] != "xc-candidate-tree-v1"
        or descriptor["archive_format"] != "zip-stored-fixed-metadata-v1"
    ):
        _fail("descriptor_invalid", "candidate descriptor identity is invalid")
    _require_revision(
        descriptor["baseline_revision"],
        field="baseline_revision",
    )
    baseline_git_tree = descriptor["baseline_git_tree"]
    if (
        not isinstance(baseline_git_tree, str)
        or _GIT_OID.fullmatch(baseline_git_tree) is None
    ):
        _fail("descriptor_invalid", "baseline_git_tree is invalid")
    if descriptor["candidate_source_archive_sha256"] != expected_archive_sha256:
        _fail("descriptor_mismatch", "descriptor archive digest mismatch")
    if descriptor["candidate_tree_sha256"] != expected_tree_sha256:
        _fail("descriptor_mismatch", "descriptor tree digest mismatch")
    git_oid = descriptor["candidate_git_tree"]
    if not isinstance(git_oid, str) or _GIT_OID.fullmatch(git_oid) is None:
        _fail("descriptor_invalid", "candidate_git_tree is invalid")

    candidate_paths = descriptor["candidate_paths"]
    if not isinstance(candidate_paths, list):
        _fail("descriptor_invalid", "candidate_paths must be a list")
    if candidate_paths != sorted(candidate_paths):
        _fail("descriptor_invalid", "candidate_paths must be sorted")
    _validate_path_set(candidate_paths, field="candidate_path")
    candidate_origin = descriptor["candidate_origin"]
    if candidate_origin == "dirty-worktree":
        if not candidate_paths:
            _fail(
                "descriptor_invalid",
                "dirty-worktree candidate_paths must be non-empty",
            )
    elif candidate_origin == "clean-head":
        if candidate_paths:
            _fail(
                "descriptor_invalid",
                "clean-head candidate_paths must be empty",
            )
        if git_oid != baseline_git_tree:
            _fail(
                "descriptor_invalid",
                "clean-head candidate_git_tree must equal baseline_git_tree",
            )
    else:
        _fail("descriptor_invalid", "candidate_origin is invalid")

    raw_files = descriptor["files"]
    if not isinstance(raw_files, list) or not raw_files:
        _fail("descriptor_invalid", "files must be non-empty")
    files: list[dict[str, Any]] = []
    previous = b""
    for index, raw in enumerate(raw_files):
        if not isinstance(raw, dict):
            _fail("descriptor_invalid", "file record must be an object", index=index)
        _require_exact_fields(
            raw,
            _DESCRIPTOR_FILE_FIELDS,
            label=f"files[{index}]",
        )
        mode = raw["mode"]
        path = raw["path"]
        size = raw["size"]
        digest = raw["sha256"]
        if mode not in _GIT_MODES:
            _fail("descriptor_invalid", "file mode is unsupported", index=index)
        _validate_relative_path(path, field=f"files[{index}].path")
        path_bytes = path.encode("utf-8")
        if previous and path_bytes <= previous:
            _fail("descriptor_invalid", "files must be uniquely byte-sorted")
        previous = path_bytes
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _fail("descriptor_invalid", "file size is invalid", index=index)
        _require_hash(digest, field=f"files[{index}].sha256")
        files.append(dict(raw))
    _validate_path_set((item["path"] for item in files), field="file path")
    if _candidate_tree_digest(files) != expected_tree_sha256:
        _fail("candidate_tree_mismatch", "descriptor tree digest is not reproducible")
    return descriptor, files


def _verify_archive(
    path: Path,
    *,
    expected_sha256: str,
    files: Sequence[Mapping[str, Any]],
) -> dict[str, bytes]:
    if _sha256_file(path) != expected_sha256:
        _fail("archive_digest_mismatch", "candidate archive SHA-256 mismatch")
    expected = {str(item["path"]): item for item in files}
    members: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if archive.comment:
                _fail("archive_invalid", "candidate archive comment must be empty")
            infos = archive.infolist()
            if [info.filename for info in infos] != list(expected):
                _fail("archive_invalid", "archive member order or exact set mismatch")
            if archive.testzip() is not None:
                _fail("archive_invalid", "archive contains a bad CRC")
            for info in infos:
                record = expected[info.filename]
                mode = f"{(info.external_attr >> 16) & 0o777777:06o}"
                if (
                    info.is_dir()
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.date_time != (1980, 1, 1, 0, 0, 0)
                    or info.comment
                    or info.extra
                    or info.create_system != 3
                    or mode != record["mode"]
                    or stat.S_IFMT(info.external_attr >> 16)
                    not in {0, stat.S_IFREG}
                ):
                    _fail(
                        "archive_invalid",
                        "archive member metadata mismatch",
                        member=info.filename,
                    )
                data = archive.read(info)
                if (
                    len(data) != record["size"]
                    or _sha256_bytes(data) != record["sha256"]
                ):
                    _fail(
                        "archive_invalid",
                        "archive member bytes mismatch",
                        member=info.filename,
                    )
                members[info.filename] = data
    except (OSError, zipfile.BadZipFile) as error:
        _fail(
            "archive_invalid",
            "candidate archive is unreadable",
            exception=type(error).__name__,
        )
    return members


def _toolchain_records(
    toolchain: Mapping[str, Any],
    platform_id: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], str, str]:
    if (
        toolchain.get("schema_version") != 1
        or toolchain.get("pin_status") != "provisional"
        or toolchain.get("promotion_gate") != "I6-windows-linux-macos-matrix"
    ):
        _fail("toolchain_invalid", "Stage 1 toolchain gate is invalid")
    fallback = toolchain.get("fallback_policy")
    if not isinstance(fallback, dict) or any(
        fallback.get(field) is not False
        for field in ("allow_latest", "allow_ambient_uv", "allow_system_python")
    ):
        _fail("toolchain_invalid", "toolchain fallback policy is not fail-closed")
    uv = toolchain.get("uv")
    python = toolchain.get("python")
    if not isinstance(uv, dict) or not isinstance(python, dict):
        _fail("toolchain_invalid", "toolchain uv/python sections are invalid")
    uv_records = [
        item
        for item in uv.get("artifacts", [])
        if isinstance(item, dict) and item.get("platform_id") == platform_id
    ]
    python_records = [
        item
        for item in python.get("downloads", [])
        if isinstance(item, dict) and item.get("platform_id") == platform_id
    ]
    if len(uv_records) != 1 or len(python_records) != 1:
        _fail(
            "toolchain_invalid",
            "toolchain does not contain one platform pin",
            platform_id=platform_id,
        )
    uv_version = _require_string(uv.get("version"), field="uv.version")
    python_request = _require_string(
        python.get("request"),
        field="python.request",
    )
    return uv_records[0], python_records[0], uv_version, python_request


def verify_inputs(
    *,
    candidate_archive: Path | str,
    candidate_archive_sha256: str,
    candidate_descriptor: Path | str,
    candidate_descriptor_sha256: str,
    candidate_tree_sha256: str,
    wheel: Path | str,
    wheel_sha256: str,
) -> dict[str, Any]:
    """Verify the immutable candidate transport and one wheel byte stream."""
    archive_path = _regular_file(candidate_archive, label="candidate_archive")
    descriptor_path = _regular_file(
        candidate_descriptor,
        label="candidate_descriptor",
    )
    wheel_path = _regular_file(wheel, label="wheel")
    expected_archive = _require_hash(
        candidate_archive_sha256,
        field="candidate_archive_sha256",
    )
    expected_descriptor = _require_hash(
        candidate_descriptor_sha256,
        field="candidate_descriptor_sha256",
    )
    expected_tree = _require_hash(
        candidate_tree_sha256,
        field="candidate_tree_sha256",
    )
    expected_wheel = _require_hash(wheel_sha256, field="wheel_sha256")
    if wheel_path.name != EXPECTED_WHEEL_FILENAME:
        _fail(
            "wheel_invalid",
            "wheel filename is not the fixed Stage 1 wheel",
            expected=EXPECTED_WHEEL_FILENAME,
            actual=wheel_path.name,
        )

    descriptor, files = _verify_descriptor(
        descriptor_path.read_bytes(),
        expected_descriptor_sha256=expected_descriptor,
        expected_archive_sha256=expected_archive,
        expected_tree_sha256=expected_tree,
    )
    members = _verify_archive(
        archive_path,
        expected_sha256=expected_archive,
        files=files,
    )
    if _sha256_file(wheel_path) != expected_wheel:
        _fail("wheel_digest_mismatch", "wheel SHA-256 mismatch")
    try:
        with zipfile.ZipFile(wheel_path, "r") as wheel_archive:
            manifest_data = wheel_archive.read(MANIFEST_MEMBER)
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        _fail(
            "wheel_invalid",
            "wheel Bundle manifest is unavailable",
            exception=type(error).__name__,
        )
    manifest = _load_json_bytes(
        manifest_data,
        label="wheel Bundle manifest",
        require_canonical=True,
    )
    expected_manifest = {
        "baseline_revision": descriptor["baseline_revision"],
        "source_state": "work-order-candidate",
        "candidate_tree_sha256": expected_tree,
        "candidate_source_archive_sha256": expected_archive,
    }
    for field, expected in expected_manifest.items():
        if manifest.get(field) != expected:
            _fail(
                "wheel_provenance_mismatch",
                f"wheel manifest {field} mismatch",
                expected=expected,
                actual=manifest.get(field),
            )
    if TOOLCHAIN_MEMBER not in members:
        _fail("candidate_invalid", "candidate archive lacks the toolchain record")
    toolchain = _load_json_bytes(
        members[TOOLCHAIN_MEMBER],
        label="Stage 1 toolchain",
        require_canonical=False,
    )
    for platform_id in (
        "windows-x86_64",
        "linux-x86_64-gnu",
        "macos-aarch64",
    ):
        _toolchain_records(toolchain, platform_id)

    bindings = {
        "baseline_revision": descriptor["baseline_revision"],
        "candidate_tree_sha256": expected_tree,
        "candidate_source_archive_sha256": expected_archive,
        "candidate_descriptor_sha256": expected_descriptor,
        "wheel_sha256": expected_wheel,
        "wheel_filename": EXPECTED_WHEEL_FILENAME,
    }
    return {
        "bindings": bindings,
        "candidate_file_count": len(files),
        "candidate_path_count": len(descriptor["candidate_paths"]),
        "toolchain": toolchain,
    }


def _validate_timestamp(value: Any, *, field: str) -> datetime:
    text = _require_string(value, field=field)
    if not text.endswith("Z"):
        _fail("schema_invalid", f"{field} must be UTC with a Z suffix")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        _fail("schema_invalid", f"{field} is not RFC 3339")
    return parsed


def _cross_platform_absolute(value: Any, *, field: str) -> str:
    text = _require_string(value, field=field)
    if not (
        PurePosixPath(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
    ):
        _fail("schema_invalid", f"{field} must be an absolute path")
    return text


def _cell_platform_id(cell_id: str, environment: Mapping[str, Any]) -> str:
    runner_os = environment["runner_os"]
    architecture = environment["architecture"]
    libc = environment["libc"]
    if cell_id == "windows-x86_64":
        if (
            runner_os != "windows"
            or architecture != "x86_64"
            or libc != "not-applicable"
        ):
            _fail("cell_mismatch", "Windows cell environment mismatch")
        return "windows-x86_64"
    if cell_id == "linux-x86_64-gnu":
        if (
            runner_os != "linux"
            or architecture != "x86_64"
            or not isinstance(libc, str)
            or not libc.startswith("glibc:")
        ):
            _fail("cell_mismatch", "Linux glibc x64 cell environment mismatch")
        return "linux-x86_64-gnu"
    if cell_id == "macos-recorded-arch":
        if (
            runner_os != "macos"
            or architecture not in {"aarch64", "x86_64"}
            or libc != "not-applicable"
        ):
            _fail("cell_mismatch", "macOS recorded-architecture cell mismatch")
        return f"macos-{architecture}"
    _fail("cell_invalid", "cell_id is not a required Stage 1 cell")


def _current_platform() -> tuple[str, str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }.get(machine, machine)
    runner_os = {
        "windows": "windows",
        "linux": "linux",
        "darwin": "macos",
    }.get(system, system)
    if runner_os == "linux":
        libc_name, libc_version = platform.libc_ver()
        libc = f"{libc_name.lower()}:{libc_version}" if libc_name else "unknown"
    else:
        libc = "not-applicable"
    return runner_os, architecture, libc


def _validate_execution(
    execution: Any,
    *,
    status: str,
    expected_run_id: str | None,
) -> dict[str, Any]:
    if not isinstance(execution, dict):
        _fail("schema_invalid", "execution must be an object")
    _require_exact_fields(execution, _EXECUTION_FIELDS, label="execution")
    try:
        uuid.UUID(_require_string(execution["execution_id"], field="execution_id"))
    except ValueError:
        _fail("schema_invalid", "execution_id must be a UUID")
    for field in ("provider", "run_id", "job_id", "runner_name"):
        _require_string(
            execution[field],
            field=f"execution.{field}",
            allow_unknown=status != "passed",
        )
    if (
        not isinstance(execution["run_attempt"], int)
        or isinstance(execution["run_attempt"], bool)
        or execution["run_attempt"] < 1
    ):
        _fail("schema_invalid", "execution.run_attempt must be a positive integer")
    started = _validate_timestamp(
        execution["started_at_utc"],
        field="execution.started_at_utc",
    )
    finished = _validate_timestamp(
        execution["finished_at_utc"],
        field="execution.finished_at_utc",
    )
    if finished < started:
        _fail("schema_invalid", "execution timestamps are reversed")
    if expected_run_id is not None and execution["run_id"] != expected_run_id:
        _fail("execution_mismatch", "cell evidence run_id mismatch")
    return execution


def _validate_environment(
    environment: Any,
    *,
    cell_id: str,
    status: str,
    require_current_platform: bool,
) -> str:
    if not isinstance(environment, dict):
        _fail("schema_invalid", "environment must be an object")
    _require_exact_fields(
        environment,
        _ENVIRONMENT_FIELDS,
        label="environment",
    )
    for field in (
        "runner_os",
        "os_name",
        "os_version",
        "os_image",
        "architecture",
        "libc",
        "sys_version",
    ):
        _require_string(
            environment[field],
            field=f"environment.{field}",
            allow_unknown=status != "passed",
        )
    for field in ("standard_user", "is_root", "long_paths_supported"):
        if environment[field] is not None and not isinstance(
            environment[field],
            bool,
        ):
            _fail("schema_invalid", f"environment.{field} must be boolean or null")
    for field in (
        "sys_executable",
        "sys_base_executable",
        "fixture_root",
        "uv_python_install_dir",
        "uv_tool_dir",
        "uv_tool_bin_dir",
    ):
        if status == "passed":
            _cross_platform_absolute(
                environment[field],
                field=f"environment.{field}",
            )
        else:
            _require_string(
                environment[field],
                field=f"environment.{field}",
                allow_unknown=True,
            )
    platform_id = _cell_platform_id(cell_id, environment)
    if status == "passed" and (
        environment["standard_user"] is not True
        or environment["is_root"] is not False
    ):
        _fail("environment_invalid", "passed evidence must be standard-user/non-root")
    if require_current_platform:
        current_os, current_arch, current_libc = _current_platform()
        if (
            environment["runner_os"] != current_os
            or environment["architecture"] != current_arch
            or (
                current_os == "linux"
                and not current_libc.startswith("glibc:")
            )
        ):
            _fail(
                "current_platform_mismatch",
                "evidence does not match the validating runner",
                current_os=current_os,
                current_architecture=current_arch,
                current_libc=current_libc,
            )
    return platform_id


def _validate_provenance(
    provenance: Any,
    *,
    status: str,
    platform_id: str,
    toolchain: Mapping[str, Any],
) -> None:
    if not isinstance(provenance, dict):
        _fail("schema_invalid", "provenance must be an object")
    _require_exact_fields(
        provenance,
        _PROVENANCE_FIELDS,
        label="provenance",
    )
    for field in (
        "candidate_archive_verified",
        "candidate_descriptor_verified",
        "candidate_tree_verified",
        "wheel_verified",
        "uv_artifact_verified",
        "managed_python_verified",
    ):
        if not isinstance(provenance[field], bool):
            _fail("schema_invalid", f"provenance.{field} must be boolean")
    for field in (
        "uv_version",
        "uv_version_output",
        "uv_artifact_filename",
        "uv_artifact_sha256",
        "python_request",
        "python_build_identity",
        "managed_python_find",
    ):
        _require_string(
            provenance[field],
            field=f"provenance.{field}",
            allow_unknown=status != "passed",
        )
    uv_record, python_record, uv_version, python_request = _toolchain_records(
        toolchain,
        platform_id,
    )
    expected_values = {
        "uv_version": uv_version,
        "uv_artifact_filename": uv_record.get("filename"),
        "uv_artifact_sha256": uv_record.get("sha256"),
        "python_request": python_request,
        "python_build_identity": python_record.get("build_identity"),
    }
    for field, expected in expected_values.items():
        if provenance[field] != expected:
            _fail(
                "provenance_mismatch",
                f"provenance.{field} does not match the candidate pin",
                expected=expected,
                actual=provenance[field],
            )
    _require_hash(
        provenance["uv_artifact_sha256"],
        field="provenance.uv_artifact_sha256",
    )
    if status == "passed":
        required_true = (
            "candidate_archive_verified",
            "candidate_descriptor_verified",
            "candidate_tree_verified",
            "wheel_verified",
            "uv_artifact_verified",
            "managed_python_verified",
        )
        if any(provenance[field] is not True for field in required_true):
            _fail("provenance_invalid", "passed evidence has an unverified input")
        _cross_platform_absolute(
            provenance["managed_python_find"],
            field="provenance.managed_python_find",
        )
        if not provenance["uv_version_output"].startswith(f"uv {uv_version}"):
            _fail("provenance_invalid", "uv version output does not match the pin")


def _bound_output_bytes(
    command: Mapping[str, Any],
    *,
    index: int,
    stream: str,
) -> bytes | None:
    encoded = command[f"{stream}_b64"]
    digest = command[f"{stream}_sha256"]
    if encoded is None and digest is None:
        return None
    if not isinstance(encoded, str) or not isinstance(digest, str):
        _fail(
            "schema_invalid",
            f"commands[{index}] {stream} bytes and digest must be paired",
        )
    _require_hash(digest, field=f"commands[{index}].{stream}_sha256")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        _fail(
            "schema_invalid",
            f"commands[{index}].{stream}_b64 is not canonical base64",
            exception=type(error).__name__,
        )
    if (
        len(data) > _MAX_BOUND_OUTPUT_BYTES
        or base64.b64encode(data).decode("ascii") != encoded
    ):
        _fail(
            "schema_invalid",
            f"commands[{index}].{stream}_b64 is non-canonical or too large",
        )
    if _sha256_bytes(data) != digest:
        _fail(
            "output_digest_mismatch",
            f"commands[{index}] {stream} bytes do not match their digest",
        )
    return data


def _validate_commands(
    commands: Any,
    *,
    status: str,
    cell_id: str,
    started: datetime,
    finished: datetime,
) -> str:
    if not isinstance(commands, list) or not commands:
        _fail("schema_invalid", "commands must be a non-empty array")
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            _fail("schema_invalid", "command must be an object", index=index)
        _require_exact_fields(
            command,
            _COMMAND_FIELDS,
            label=f"commands[{index}]",
        )
        command_id = _require_string(
            command["id"],
            field=f"commands[{index}].id",
        )
        if command_id in by_id:
            _fail("schema_invalid", "command IDs must be unique", id=command_id)
        by_id[command_id] = command
        argv = command["argv"]
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            _fail("schema_invalid", "command argv must be a non-empty string array")
        _require_string(
            command["cwd"],
            field=f"commands[{index}].cwd",
            allow_unknown=status != "passed",
        )
        if command["expected_exit"] not in {"zero", "nonzero"}:
            _fail("schema_invalid", "command expected_exit is invalid")
        if command["status"] not in _COMMAND_STATUSES:
            _fail("schema_invalid", "command status is invalid")
        if command["exit_code"] is not None and (
            not isinstance(command["exit_code"], int)
            or isinstance(command["exit_code"], bool)
        ):
            _fail("schema_invalid", "command exit_code must be integer or null")
        if command["duration_ms"] is not None and (
            not isinstance(command["duration_ms"], int)
            or isinstance(command["duration_ms"], bool)
            or command["duration_ms"] < 0
        ):
            _fail("schema_invalid", "command duration_ms is invalid")
        command_started = _validate_timestamp(
            command["started_at_utc"],
            field=f"commands[{index}].started_at_utc",
        )
        if command_started < started or command_started > finished:
            _fail("schema_invalid", "command timestamp escapes execution interval")
        stdout = _bound_output_bytes(command, index=index, stream="stdout")
        stderr = _bound_output_bytes(command, index=index, stream="stderr")
        if command["status"] == "passed":
            exit_code = command["exit_code"]
            if exit_code is None:
                _fail("schema_invalid", "passing command must record exit_code")
            expected_exit = command["expected_exit"]
            if (
                expected_exit == "zero"
                and exit_code != 0
            ) or (
                expected_exit == "nonzero"
                and exit_code == 0
            ):
                _fail(
                    "command_failed",
                    "command exit code does not match its expected outcome",
                    id=command_id,
                    expected_exit=expected_exit,
                    exit_code=exit_code,
                )
            if command["duration_ms"] is None:
                _fail("schema_invalid", "passing command must record duration_ms")
            if stdout is None or stderr is None:
                _fail(
                    "schema_invalid",
                    "passing command must bind stdout and stderr bytes and digests",
                )
    required = set(REQUIRED_COMMANDS)
    if cell_id == "windows-x86_64":
        required.add(WINDOWS_COMMAND)
    missing = required - set(by_id)
    if missing:
        _fail("schema_invalid", "required command evidence is missing", missing=sorted(missing))
    if status == "passed" and any(
        command["status"] != "passed" for command in by_id.values()
    ):
        _fail("command_failed", "passed evidence contains a non-passing command")
    return _command_contract_sha256(commands)


def _validate_attestation(
    attestation: Any,
    *,
    evidence: Mapping[str, Any],
    execution: Mapping[str, Any],
    status: str,
    command_contract_sha256: str,
    trusted_attestation_keys: Mapping[str, bytes],
    expected_command_contract_sha256: str | None,
    expected_runner_identity_sha256: str | None,
) -> tuple[bool, str | None, str | None]:
    if status != "passed" and attestation is None:
        return False, None, None
    if not isinstance(attestation, dict):
        _fail(
            "attestation_required",
            "passed evidence lacks a verifiable trusted execution attestation",
        )
    _require_exact_fields(attestation, _ATTESTATION_FIELDS, label="attestation")
    if (
        attestation["kind"] != _ATTESTATION_KIND
        or attestation["algorithm"] != _ATTESTATION_ALGORITHM
    ):
        _fail("attestation_invalid", "attestation kind or algorithm is invalid")
    key_id = _require_hash(attestation["key_id"], field="attestation.key_id")
    runner_identity = _require_hash(
        attestation["runner_identity_sha256"],
        field="attestation.runner_identity_sha256",
    )
    attested_contract = _require_hash(
        attestation["command_contract_sha256"],
        field="attestation.command_contract_sha256",
    )
    payload_sha256 = _require_hash(
        attestation["payload_sha256"],
        field="attestation.payload_sha256",
    )
    signature = _require_hash(
        attestation["signature"],
        field="attestation.signature",
    )
    if expected_command_contract_sha256 is None:
        _fail(
            "attestation_untrusted",
            "no approved command contract is configured for this cell",
        )
    expected_contract = _require_hash(
        expected_command_contract_sha256,
        field="expected_command_contract_sha256",
    )
    if (
        command_contract_sha256 != expected_contract
        or attested_contract != expected_contract
    ):
        _fail(
            "command_contract_mismatch",
            "attested argv does not match the exact approved command contract",
            expected=expected_contract,
            actual=command_contract_sha256,
        )
    key = trusted_attestation_keys.get(key_id)
    if key is None or _attestation_key_id(key) != key_id:
        _fail(
            "attestation_untrusted",
            "attestation key is not in the trusted runner key set",
            key_id=key_id,
        )
    expected_runner_identity = _runner_identity_sha256(execution)
    if runner_identity != expected_runner_identity:
        _fail(
            "attestation_identity_mismatch",
            "attestation does not bind the recorded runner identity",
        )
    if expected_runner_identity_sha256 is None:
        _fail(
            "attestation_untrusted",
            "no approved runner identity is configured for this cell",
        )
    approved_runner_identity = _require_hash(
        expected_runner_identity_sha256,
        field="expected_runner_identity_sha256",
    )
    if runner_identity != approved_runner_identity:
        _fail(
            "attestation_identity_mismatch",
            "attested runner identity is not approved for this cell",
            expected=approved_runner_identity,
            actual=runner_identity,
        )
    payload = dict(evidence)
    payload.pop("attestation", None)
    expected_payload = _sha256_bytes(_canonical_json_bytes(payload))
    if payload_sha256 != expected_payload:
        _fail(
            "attestation_payload_mismatch",
            "attestation does not bind the complete evidence payload",
        )
    expected_signature = hmac.new(
        key,
        _attestation_message(
            key_id=key_id,
            runner_identity_sha256=runner_identity,
            command_contract_sha256=attested_contract,
            payload_sha256=payload_sha256,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        _fail(
            "attestation_signature_mismatch",
            "trusted execution attestation signature is invalid",
        )
    return True, key_id, runner_identity


def _validate_checks(
    checks: Any,
    *,
    status: str,
    cell_id: str,
    long_paths_supported: bool | None,
) -> None:
    if not isinstance(checks, dict):
        _fail("schema_invalid", "checks must be an object")
    _require_exact_fields(checks, set(REQUIRED_CHECKS), label="checks")
    for name, value in checks.items():
        if value not in _CHECK_STATUSES:
            _fail("schema_invalid", f"checks.{name} status is invalid")
    if status != "passed":
        return
    for name, value in checks.items():
        allow_not_applicable = (
            name == "windows-console-oracle"
            and cell_id != "windows-x86_64"
        ) or (
            name == "long-paths"
            and long_paths_supported is False
        )
        if value == "not-applicable" and allow_not_applicable:
            continue
        if value != "passed":
            _fail(
                "check_failed",
                "passed evidence contains an incomplete required check",
                check=name,
                status=value,
            )


def validate_cell_evidence(
    value: Mapping[str, Any],
    *,
    expected_cell: str,
    expected_bindings: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    require_current_platform: bool = False,
    expected_run_id: str | None = None,
    trusted_attestation_keys: Mapping[str, bytes] | None = None,
    expected_command_contract_sha256: str | None = None,
    expected_runner_identity_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate one complete runner-owned cell evidence document."""
    if not isinstance(value, dict):
        _fail("schema_invalid", "cell evidence root must be an object")
    _require_exact_fields(value, _EVIDENCE_FIELDS, label="cell evidence")
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["evidence_kind"] != CELL_EVIDENCE_KIND
        or value["cell_id"] != expected_cell
    ):
        _fail("cell_mismatch", "cell evidence identity mismatch")
    status = value["status"]
    if status not in _CELL_STATUSES:
        _fail("schema_invalid", "cell status is invalid")

    bindings = value["bindings"]
    if not isinstance(bindings, dict):
        _fail("schema_invalid", "bindings must be an object")
    _require_exact_fields(bindings, _BINDING_FIELDS, label="bindings")
    if dict(bindings) != dict(expected_bindings):
        _fail(
            "binding_mismatch",
            "cell evidence candidate/wheel bindings mismatch",
        )

    execution = _validate_execution(
        value["execution"],
        status=status,
        expected_run_id=expected_run_id,
    )
    environment = value["environment"]
    platform_id = _validate_environment(
        environment,
        cell_id=expected_cell,
        status=status,
        require_current_platform=require_current_platform,
    )
    _validate_provenance(
        value["provenance"],
        status=status,
        platform_id=platform_id,
        toolchain=toolchain,
    )
    started = _validate_timestamp(
        execution["started_at_utc"],
        field="execution.started_at_utc",
    )
    finished = _validate_timestamp(
        execution["finished_at_utc"],
        field="execution.finished_at_utc",
    )
    command_contract_sha256 = _validate_commands(
        value["commands"],
        status=status,
        cell_id=expected_cell,
        started=started,
        finished=finished,
    )
    _validate_checks(
        value["checks"],
        status=status,
        cell_id=expected_cell,
        long_paths_supported=environment["long_paths_supported"],
    )

    cleanup = value["cleanup"]
    if not isinstance(cleanup, dict):
        _fail("schema_invalid", "cleanup must be an object")
    _require_exact_fields(cleanup, _CLEANUP_FIELDS, label="cleanup")
    for field in (
        "attempted",
        "fixture_removed",
        "candidate_staging_removed",
        "unexpected_preserved",
    ):
        if not isinstance(cleanup[field], bool):
            _fail("schema_invalid", f"cleanup.{field} must be boolean")
    if cleanup["status"] not in _COMMAND_STATUSES:
        _fail("schema_invalid", "cleanup.status is invalid")
    if status == "passed" and (
        cleanup["status"] != "passed"
        or any(
            cleanup[field] is not True
            for field in (
                "attempted",
                "fixture_removed",
                "candidate_staging_removed",
                "unexpected_preserved",
            )
        )
    ):
        _fail("cleanup_failed", "passed evidence has incomplete cleanup")

    failure = value["failure"]
    if status == "passed":
        if failure is not None:
            _fail("schema_invalid", "passed evidence must not contain failure")
    else:
        if not isinstance(failure, dict):
            _fail("schema_invalid", "failed/unrun evidence must contain failure")
        _require_exact_fields(failure, _FAILURE_FIELDS, label="failure")
        _require_string(failure["code"], field="failure.code")
        _require_string(failure["message"], field="failure.message")

    trusted, key_id, runner_identity = _validate_attestation(
        value["attestation"],
        evidence=value,
        execution=execution,
        status=status,
        command_contract_sha256=command_contract_sha256,
        trusted_attestation_keys=trusted_attestation_keys or {},
        expected_command_contract_sha256=expected_command_contract_sha256,
        expected_runner_identity_sha256=expected_runner_identity_sha256,
    )
    return {
        "valid": True,
        "status": status,
        "promotion_eligible": status == "passed" and trusted,
        "execution_id": execution["execution_id"],
        "runner_name": execution["runner_name"],
        "attestation_key_id": key_id,
        "runner_identity_sha256": runner_identity,
        "command_contract_sha256": command_contract_sha256,
        "platform_id": platform_id,
    }


def _cell_argument(value: str) -> tuple[str, Path]:
    if "=" not in value:
        _fail("argument_invalid", "--cell-evidence must use CELL=PATH")
    cell, raw_path = value.split("=", 1)
    if cell not in REQUIRED_CELLS:
        _fail("argument_invalid", "cell evidence uses an unknown cell", cell=cell)
    return cell, Path(raw_path)


def _validate_cell_trust_configuration(
    *,
    trusted_attestation_keys: Mapping[
        str, Mapping[str, bytes]
    ] | None,
    expected_command_contracts: Mapping[str, str] | None,
    expected_runner_identities: Mapping[str, str] | None,
) -> tuple[
    dict[str, dict[str, bytes]],
    dict[str, str],
    dict[str, str],
]:
    raw_keys = trusted_attestation_keys or {}
    raw_contracts = expected_command_contracts or {}
    raw_identities = expected_runner_identities or {}
    if not (raw_keys or raw_contracts or raw_identities):
        return {}, {}, {}
    required = set(REQUIRED_CELLS)
    declarations = {
        "trusted_attestation_keys": set(raw_keys),
        "expected_command_contracts": set(raw_contracts),
        "expected_runner_identities": set(raw_identities),
    }
    if any(cells != required for cells in declarations.values()):
        _fail(
            "argument_invalid",
            "trusted cell declarations must cover every required cell exactly",
            missing={
                name: sorted(required - cells)
                for name, cells in declarations.items()
            },
            unexpected={
                name: sorted(cells - required)
                for name, cells in declarations.items()
            },
        )
    keys: dict[str, dict[str, bytes]] = {}
    contracts: dict[str, str] = {}
    identities: dict[str, str] = {}
    for cell_id in REQUIRED_CELLS:
        cell_keys = raw_keys[cell_id]
        if not isinstance(cell_keys, dict) or not cell_keys:
            _fail(
                "argument_invalid",
                "each trusted cell must declare at least one attestation key",
                cell=cell_id,
            )
        validated_keys: dict[str, bytes] = {}
        for key_id, key in cell_keys.items():
            if _require_hash(
                key_id,
                field=f"trusted_attestation_keys.{cell_id}.key_id",
            ) != _attestation_key_id(key):
                _fail(
                    "argument_invalid",
                    "trusted attestation key ID does not match its cell key",
                    cell=cell_id,
                )
            validated_keys[key_id] = key
        keys[cell_id] = validated_keys
        contracts[cell_id] = _require_hash(
            raw_contracts[cell_id],
            field=f"expected_command_contracts.{cell_id}",
        )
        identities[cell_id] = _require_hash(
            raw_identities[cell_id],
            field=f"expected_runner_identities.{cell_id}",
        )
    return keys, contracts, identities


def summarize_evidence(
    *,
    evidence_paths: Mapping[str, Path | str],
    expected_bindings: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    expected_run_id: str | None = None,
    trusted_attestation_keys: Mapping[
        str, Mapping[str, bytes]
    ] | None = None,
    expected_command_contracts: Mapping[str, str] | None = None,
    expected_runner_identities: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a fail-closed summary over exactly the three required cells."""
    unexpected = set(evidence_paths) - set(REQUIRED_CELLS)
    if unexpected:
        _fail(
            "argument_invalid",
            "summary contains an unknown cell",
            unexpected=sorted(unexpected),
        )
    trusted_keys, trusted_contracts, trusted_runner_identities = (
        _validate_cell_trust_configuration(
            trusted_attestation_keys=trusted_attestation_keys,
            expected_command_contracts=expected_command_contracts,
            expected_runner_identities=expected_runner_identities,
        )
    )
    cells: list[dict[str, Any]] = []
    execution_ids: set[str] = set()
    runner_names: set[str] = set()
    runner_identities: set[str] = set()
    attestation_key_ids: set[str] = set()
    all_passed = True
    reason_codes: set[str] = set()
    for cell_id in REQUIRED_CELLS:
        raw_path = evidence_paths.get(cell_id)
        if raw_path is None:
            all_passed = False
            reason_codes.add("cell-unrun")
            cells.append(
                {
                    "cell_id": cell_id,
                    "outcome": "unknown",
                    "observed_status": "missing",
                    "evidence_sha256": None,
                    "execution_id": None,
                    "validation_errors": ["cell evidence is unavailable"],
                }
            )
            continue
        path = Path(raw_path)
        evidence_digest: str | None = None
        try:
            evidence_file = _regular_file(path, label=f"{cell_id} evidence")
            data = evidence_file.read_bytes()
            evidence_digest = _sha256_bytes(data)
            evidence = _load_json_bytes(
                data,
                label=f"{cell_id} evidence",
                require_canonical=True,
            )
            result = validate_cell_evidence(
                evidence,
                expected_cell=cell_id,
                expected_bindings=expected_bindings,
                toolchain=toolchain,
                expected_run_id=expected_run_id,
                trusted_attestation_keys=trusted_keys.get(cell_id, {}),
                expected_command_contract_sha256=trusted_contracts.get(cell_id),
                expected_runner_identity_sha256=(
                    trusted_runner_identities.get(cell_id)
                ),
            )
            observed = result["status"]
            errors: list[str] = []
            if observed != "passed" or not result["promotion_eligible"]:
                all_passed = False
                reason_codes.add(
                    "cell-failed" if observed == "failed" else "cell-unrun"
                )
            if result["execution_id"] in execution_ids:
                all_passed = False
                observed = "mismatched"
                reason_codes.add("execution-reused")
                errors.append("execution_id is reused by another cell")
            else:
                execution_ids.add(result["execution_id"])
            if result["runner_name"] in runner_names:
                all_passed = False
                observed = "mismatched"
                reason_codes.add("runner-reused")
                errors.append("runner_name is reused by another cell")
            else:
                runner_names.add(result["runner_name"])
            runner_identity = result["runner_identity_sha256"]
            if runner_identity in runner_identities:
                all_passed = False
                observed = "mismatched"
                reason_codes.add("runner-identity-reused")
                errors.append("attested runner identity is reused by another cell")
            elif runner_identity is not None:
                runner_identities.add(runner_identity)
            key_id = result["attestation_key_id"]
            if key_id in attestation_key_ids:
                all_passed = False
                observed = "mismatched"
                reason_codes.add("attestation-key-reused")
                errors.append("trusted runner attestation key is reused by another cell")
            elif key_id is not None:
                attestation_key_ids.add(key_id)
            cells.append(
                {
                    "cell_id": cell_id,
                    "outcome": "passed" if observed == "passed" else "unknown",
                    "observed_status": observed,
                    "evidence_sha256": evidence_digest,
                    "execution_id": result["execution_id"],
                    "runner_identity_sha256": runner_identity,
                    "attestation_key_id": key_id,
                    "validation_errors": errors,
                }
            )
        except (OSError, MatrixError) as error:
            all_passed = False
            reason_codes.add("cell-mismatched")
            message = (
                f"{error.code}: {error}"
                if isinstance(error, MatrixError)
                else f"{type(error).__name__}: {error}"
            )
            cells.append(
                {
                    "cell_id": cell_id,
                    "outcome": "unknown",
                    "observed_status": "mismatched",
                    "evidence_sha256": evidence_digest,
                    "execution_id": None,
                    "validation_errors": [message],
                }
            )
    evidence_set = {
        "bindings": dict(expected_bindings),
        "cells": [
            {
                "cell_id": cell["cell_id"],
                "evidence_sha256": cell["evidence_sha256"],
            }
            for cell in cells
        ],
    }
    if not all_passed and not reason_codes:
        reason_codes.add("matrix-incomplete")
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_kind": SUMMARY_EVIDENCE_KIND,
        "status": "passed" if all_passed else "unknown",
        "decision": "promote" if all_passed else "no-go",
        "pin_status": "fixed" if all_passed else "provisional",
        "promotion_eligible": all_passed,
        "bindings": dict(expected_bindings),
        "cells": cells,
        "evidence_set_sha256": _sha256_bytes(
            _canonical_json_bytes(evidence_set)
        ),
        "reason_codes": sorted(reason_codes),
    }


def _common_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--candidate-archive", type=Path, required=True)
    parser.add_argument("--candidate-archive-sha256", required=True)
    parser.add_argument("--candidate-descriptor", type=Path, required=True)
    parser.add_argument("--candidate-descriptor-sha256", required=True)
    parser.add_argument("--candidate-tree-sha256", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheel-sha256", required=True)


def _trusted_key_from_environment(name: str) -> bytes:
    value = os.environ.get(name)
    if value is None:
        _fail(
            "attestation_untrusted",
            "trusted attestation key environment variable is unavailable",
            environment=name,
        )
    return value.encode("utf-8")


def _cell_value_argument(value: str, *, option: str) -> tuple[str, str]:
    if "=" not in value:
        _fail("argument_invalid", f"{option} must use CELL=VALUE")
    cell, item = value.split("=", 1)
    if cell not in REQUIRED_CELLS or not item:
        _fail("argument_invalid", f"{option} contains an invalid cell or value")
    return cell, item


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)

    describe = commands.add_parser("describe")
    describe.add_argument("--output", type=Path)

    verify = commands.add_parser("verify-inputs")
    _common_input_arguments(verify)
    verify.add_argument("--output", type=Path)

    cell = commands.add_parser("validate-cell")
    _common_input_arguments(cell)
    cell.add_argument("--cell", choices=REQUIRED_CELLS, required=True)
    cell.add_argument("--evidence", type=Path, required=True)
    cell.add_argument("--expected-run-id")
    cell.add_argument("--require-current-platform", action="store_true")
    cell.add_argument("--attestation-key-env")
    cell.add_argument("--trusted-command-contract-sha256")
    cell.add_argument("--trusted-runner-identity-sha256")
    cell.add_argument("--output", type=Path)

    summary = commands.add_parser("summarize")
    _common_input_arguments(summary)
    summary.add_argument("--cell-evidence", action="append", default=[])
    summary.add_argument("--expected-run-id")
    summary.add_argument(
        "--trusted-attestation-key-env",
        action="append",
        default=[],
    )
    summary.add_argument(
        "--trusted-command-contract-sha256",
        action="append",
        default=[],
    )
    summary.add_argument(
        "--trusted-runner-identity-sha256",
        action="append",
        default=[],
    )
    summary.add_argument("--output", type=Path, required=True)
    return parser


def _write_optional(path: Path | None, value: object) -> None:
    if path is not None:
        target = _output_file(path, label="output")
        target.write_bytes(_canonical_json_bytes(value))


def _protocol_description() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "required_cells": list(REQUIRED_CELLS),
        "required_commands": list(REQUIRED_COMMANDS),
        "windows_additional_command": WINDOWS_COMMAND,
        "required_checks": list(REQUIRED_CHECKS),
        "cell_evidence_kind": CELL_EVIDENCE_KIND,
        "summary_evidence_kind": SUMMARY_EVIDENCE_KIND,
        "promotion_rule": (
            "promote only when every required cell uses its declared trusted "
            "key and expected runner identity for an attestation over the exact "
            "approved argv, output bytes, platform, cleanup, and bindings"
        ),
        "non_promotion_rule": (
            "missing, unrun, failed, malformed, mismatched, or reused "
            "evidence, or evidence without a cell-scoped trusted key, expected "
            "runner identity, and exact command contract, remains unknown and "
            "produces no-go"
        ),
        "trust_binding_required": True,
    }


def _emit(value: object) -> None:
    sys.stdout.buffer.write(_canonical_json_bytes(value))


def main(arguments: Sequence[str] | None = None) -> int:
    operation = ""
    try:
        options = _parser().parse_args(arguments)
        operation = options.operation
        if operation == "describe":
            result = _protocol_description()
            _write_optional(options.output, result)
        else:
            verified = verify_inputs(
                candidate_archive=options.candidate_archive,
                candidate_archive_sha256=options.candidate_archive_sha256,
                candidate_descriptor=options.candidate_descriptor,
                candidate_descriptor_sha256=options.candidate_descriptor_sha256,
                candidate_tree_sha256=options.candidate_tree_sha256,
                wheel=options.wheel,
                wheel_sha256=options.wheel_sha256,
            )
            if operation == "verify-inputs":
                result = {
                    "verified": True,
                    "bindings": verified["bindings"],
                    "candidate_file_count": verified["candidate_file_count"],
                    "candidate_path_count": verified["candidate_path_count"],
                }
                _write_optional(options.output, result)
            elif operation == "validate-cell":
                evidence_path = _regular_file(
                    options.evidence,
                    label="evidence",
                )
                evidence = _load_json_bytes(
                    evidence_path.read_bytes(),
                    label="cell evidence",
                    require_canonical=True,
                )
                trusted_cell_keys: dict[str, bytes] = {}
                if options.attestation_key_env:
                    trusted_key = _trusted_key_from_environment(
                        options.attestation_key_env
                    )
                    trusted_cell_keys[_attestation_key_id(trusted_key)] = trusted_key
                trust_values = (
                    options.attestation_key_env,
                    options.trusted_command_contract_sha256,
                    options.trusted_runner_identity_sha256,
                )
                if any(trust_values) and not all(trust_values):
                    _fail(
                        "argument_invalid",
                        "validate-cell trust requires a key, command contract, "
                        "and runner identity",
                        cell=options.cell,
                    )
                result = validate_cell_evidence(
                    evidence,
                    expected_cell=options.cell,
                    expected_bindings=verified["bindings"],
                    toolchain=verified["toolchain"],
                    require_current_platform=options.require_current_platform,
                    expected_run_id=options.expected_run_id,
                    trusted_attestation_keys=trusted_cell_keys,
                    expected_command_contract_sha256=(
                        options.trusted_command_contract_sha256
                    ),
                    expected_runner_identity_sha256=(
                        options.trusted_runner_identity_sha256
                    ),
                )
                result["evidence_sha256"] = _sha256_file(evidence_path)
                _write_optional(options.output, result)
            else:
                evidence_paths: dict[str, Path] = {}
                for item in options.cell_evidence:
                    cell_id, path = _cell_argument(item)
                    if cell_id in evidence_paths:
                        _fail(
                            "argument_invalid",
                            "duplicate --cell-evidence cell",
                            cell=cell_id,
                        )
                    evidence_paths[cell_id] = path
                trusted_keys: dict[str, dict[str, bytes]] = {}
                for item in options.trusted_attestation_key_env:
                    cell_id, environment_name = _cell_value_argument(
                        item,
                        option="--trusted-attestation-key-env",
                    )
                    if cell_id in trusted_keys:
                        _fail(
                            "argument_invalid",
                            "duplicate trusted attestation key cell",
                            cell=cell_id,
                        )
                    key = _trusted_key_from_environment(environment_name)
                    trusted_keys[cell_id] = {
                        _attestation_key_id(key): key,
                    }
                trusted_contracts: dict[str, str] = {}
                for item in options.trusted_command_contract_sha256:
                    cell_id, digest = _cell_value_argument(
                        item,
                        option="--trusted-command-contract-sha256",
                    )
                    if cell_id in trusted_contracts:
                        _fail(
                            "argument_invalid",
                            "duplicate trusted command contract cell",
                            cell=cell_id,
                        )
                    trusted_contracts[cell_id] = _require_hash(
                        digest,
                        field=f"trusted_command_contract.{cell_id}",
                    )
                trusted_runner_identities: dict[str, str] = {}
                for item in options.trusted_runner_identity_sha256:
                    cell_id, digest = _cell_value_argument(
                        item,
                        option="--trusted-runner-identity-sha256",
                    )
                    if cell_id in trusted_runner_identities:
                        _fail(
                            "argument_invalid",
                            "duplicate trusted runner identity cell",
                            cell=cell_id,
                        )
                    trusted_runner_identities[cell_id] = _require_hash(
                        digest,
                        field=f"trusted_runner_identity.{cell_id}",
                    )
                result = summarize_evidence(
                    evidence_paths=evidence_paths,
                    expected_bindings=verified["bindings"],
                    toolchain=verified["toolchain"],
                    expected_run_id=options.expected_run_id,
                    trusted_attestation_keys=trusted_keys,
                    expected_command_contracts=trusted_contracts,
                    expected_runner_identities=trusted_runner_identities,
                )
                _write_optional(options.output, result)
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": True,
                "operation": operation,
                "result": result,
            }
        )
        return 0
    except MatrixError as error:
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "operation": operation,
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "details": error.details,
                },
            }
        )
        return 2
    except Exception as error:
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "operation": operation,
                "error": {
                    "code": "internal_error",
                    "message": "unclassified matrix driver failure",
                    "details": {"exception": type(error).__name__},
                },
            }
        )
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
