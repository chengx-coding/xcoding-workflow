"""Thin install, upgrade, and uninstall lifecycle wrappers.

Every mutating payload operation stays inside the single setup transaction
engine.  This module only selects the scope root, validates the requested host
set, sequences the external ``uv`` CLI step, and reports lifecycle-specific
results.  It never implements a second installer or a second state model.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .bundle.manifest import MANIFEST_NAME
from .bundle.resources import DISTRIBUTION_NAME
from .setup_transaction import (
    HOST_ORDER,
    SetupTransactionError,
    setup,
    uninstall as uninstall_payload,
)
from .version import version_report


SCOPES = ("user", "project")
UV_TOOL_INSTALL_TIMEOUT = 900
CLI_PAYLOAD_TIMEOUT = 600
OUTPUT_LIMIT = 8000
_FILE_IN_USE_MARKERS = (
    "access is denied",
    "being used by another process",
    "file in use",
    "another process",
    "os error 32",
    "winerror 32",
    "error 32",
    "cannot access the file",
    "拒绝访问",
    "另一个程序",
)


class LifecycleError(SetupTransactionError):
    """Stable lifecycle failure carrying a code, message, and details.

    It deliberately extends :class:`SetupTransactionError` so every CLI error
    path that already handles setup failures keeps working unchanged.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, details=details)
        self.message = message


def _normalize_scope(scope: str) -> str:
    if scope not in SCOPES:
        raise LifecycleError(
            "scope_unknown",
            "install scope is not supported",
            details={"scope": scope, "available": list(SCOPES)},
        )
    return scope


def _scope_root(
    scope: str,
    project_root: str | Path | None,
) -> Path:
    if scope == "project":
        if project_root is None or str(project_root) == "":
            raise LifecycleError(
                "project_root_required",
                "project scope requires an explicit project root",
            )
        return Path(project_root).absolute()
    if project_root is not None and str(project_root) != "":
        raise LifecycleError(
            "project_root_not_allowed",
            "user scope resolves the home directory and does not accept a project root",
            details={"project_root": str(project_root)},
        )
    return Path.home()


def _normalize_hosts(hosts: Sequence[str] | None) -> list[str]:
    if hosts is None:
        return list(HOST_ORDER)
    unknown = sorted(set(hosts) - set(HOST_ORDER))
    if unknown:
        raise LifecycleError(
            "host_unknown",
            "host is not supported by this package",
            details={"unknown": unknown, "available": list(HOST_ORDER)},
        )
    selected = [host for host in HOST_ORDER if host in set(hosts)]
    if not selected:
        raise LifecycleError(
            "host_required",
            "install requires at least one host",
            details={"available": list(HOST_ORDER)},
        )
    return selected


def _adoption_allowed(scope: str, adopt_legacy: bool) -> bool:
    if adopt_legacy and scope != "user":
        raise LifecycleError(
            "adopt_legacy_requires_user_scope",
            "legacy adoption is only supported for the user scope",
            details={"scope": scope},
        )
    return adopt_legacy


def _running_version() -> dict[str, Any]:
    report = version_report()
    return {
        "xc_version": report["xc_version"],
        "bundle_manifest_sha256": report["bundle_manifest_sha256"],
    }


def _payload_status(dry_run: bool, payload: Mapping[str, Any]) -> str:
    if dry_run:
        return "dry-run"
    operations = payload.get("operations")
    if not isinstance(operations, list):
        return "reconciled"
    changed = any(
        isinstance(operation, Mapping)
        and operation.get("action") in {"create", "replace", "remove"}
        for operation in operations
    )
    return "reconciled" if changed else "up-to-date"


def install(
    scope: str = "user",
    project_root: str | None = None,
    hosts: Sequence[str] | None = None,
    *,
    dry_run: bool = False,
    adopt_legacy: bool = False,
) -> dict[str, Any]:
    """Install or repair the payload for one scope through the setup engine."""

    selected_scope = _normalize_scope(scope)
    target_root = _scope_root(selected_scope, project_root)
    selected_hosts = _normalize_hosts(hosts)
    adopt = _adoption_allowed(selected_scope, adopt_legacy)
    result = setup(
        target_root,
        selected_hosts,
        dry_run=dry_run,
        adopt_legacy=adopt,
    )
    running = _running_version()
    result = dict(result)
    result.update(
        {
            "scope": selected_scope,
            "root": result.get("project_root", str(target_root)),
            "version": running["xc_version"],
            "bundle_manifest_sha256": running["bundle_manifest_sha256"],
            "dry_run": dry_run,
        }
    )
    return result


def uninstall(
    scope: str = "user",
    project_root: str | None = None,
    *,
    dry_run: bool = False,
    keep_state: bool = True,
) -> dict[str, Any]:
    """Remove hash-verified payload files for one scope."""

    selected_scope = _normalize_scope(scope)
    target_root = _scope_root(selected_scope, project_root)
    result = uninstall_payload(
        target_root,
        dry_run=dry_run,
        keep_state=keep_state,
    )
    result = dict(result)
    result.update(
        {
            "scope": selected_scope,
            "root": result.get("project_root", str(target_root)),
            "dry_run": dry_run,
        }
    )
    return result


def _bounded(value: object, limit: int = OUTPUT_LIMIT) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...<truncated>...\n{text[-half:]}"


def _run(argv: Sequence[str], *, timeout: int) -> dict[str, Any]:
    command = [str(part) for part in argv]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "command": command,
            "returncode": None,
            "timeout": True,
            "stdout": _bounded(error.stdout),
            "stderr": _bounded(error.stderr),
        }
    except OSError as error:
        raise LifecycleError(
            "process_unavailable",
            "cannot execute an external lifecycle step",
            details={
                "command": command,
                "exception": type(error).__name__,
                "message": str(error),
            },
        ) from error
    return {
        "command": command,
        "returncode": completed.returncode,
        "timeout": False,
        "stdout": _bounded(completed.stdout),
        "stderr": _bounded(completed.stderr),
    }


def _normalized_distribution_name(value: str) -> str:
    """Normalize a distribution name the way PEP 503 compares project names."""

    return re.sub(r"[-_.]+", "-", value).lower()


def _wheel_version(wheel: Path) -> str:
    if (
        wheel.suffix.lower() != ".whl"
        or not wheel.is_file()
        or wheel.is_symlink()
    ):
        raise LifecycleError(
            "wheel_invalid",
            "upgrade --wheel requires an existing wheel file",
            details={"wheel": str(wheel)},
        )
    try:
        with zipfile.ZipFile(wheel) as archive:
            entries = [
                name
                for name in archive.namelist()
                if name.count("/") == 1 and name.endswith(".dist-info/METADATA")
            ]
            if len(entries) != 1:
                raise LifecycleError(
                    "wheel_invalid",
                    "wheel must contain exactly one dist-info METADATA file",
                    details={"wheel": str(wheel), "entries": sorted(entries)},
                )
            metadata = archive.read(entries[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as error:
        raise LifecycleError(
            "wheel_invalid",
            "wheel is not a readable zip archive",
            details={"wheel": str(wheel), "exception": type(error).__name__},
        ) from error
    except OSError as error:
        raise LifecycleError(
            "wheel_invalid",
            "wheel cannot be read",
            details={"wheel": str(wheel), "exception": type(error).__name__},
        ) from error
    name: str | None = None
    version: str | None = None
    for line in metadata.splitlines():
        if line.lower().startswith("name:"):
            name = line.split(":", 1)[1].strip() or None
        elif line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip() or None
    if version is None:
        raise LifecycleError(
            "wheel_invalid",
            "wheel METADATA has no Version field",
            details={"wheel": str(wheel)},
        )
    if name is None:
        raise LifecycleError(
            "wheel_invalid",
            "wheel METADATA has no Name field",
            details={"wheel": str(wheel)},
        )
    if _normalized_distribution_name(name) != _normalized_distribution_name(
        DISTRIBUTION_NAME
    ):
        raise LifecycleError(
            "wheel_invalid",
            "wheel does not provide the xcoding-workflow distribution",
            details={
                "wheel": str(wheel),
                "name": name,
                "expected": DISTRIBUTION_NAME,
            },
        )
    return version


def _wheel_bundle_sha256(wheel: Path) -> str | None:
    """Return the Bundle manifest digest carried by the wheel, when present.

    A target Bundle is only known before installation if the wheel itself
    carries the packaged Bundle; a metadata-only artifact has no Bundle to
    compare and reports ``None``.
    """

    try:
        with zipfile.ZipFile(wheel) as archive:
            entry = f"xcoding/_bundle/{MANIFEST_NAME}"
            if entry not in archive.namelist():
                return None
            return hashlib.sha256(archive.read(entry)).hexdigest()
    except (KeyError, OSError, zipfile.BadZipFile):
        return None


def _file_in_use_signature(result: Mapping[str, Any]) -> str | None:
    haystack = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
    for marker in _FILE_IN_USE_MARKERS:
        if marker in haystack:
            return marker
    return None


def _payload_argv(
    launcher: str,
    scope: str,
    target_root: Path,
    hosts: Sequence[str],
    *,
    adopt_legacy: bool,
) -> list[str]:
    argv = [launcher, "install", "--scope", scope, "--json"]
    if scope == "project":
        argv.extend(["--project-root", str(target_root)])
    for host in hosts:
        argv.extend(["--host", host])
    if adopt_legacy:
        argv.append("--adopt-legacy")
    return argv


def upgrade(
    scope: str = "user",
    project_root: str | None = None,
    hosts: Sequence[str] | None = None,
    wheel: str | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    adopt_legacy: bool = False,
) -> dict[str, Any]:
    """Upgrade the CLI from a wheel, then reconcile the payload with the new CLI.

    Without a wheel the payload is reconciled to the running CLI.  With a wheel
    the CLI step runs as an external ``uv`` subprocess; payload writes never
    start unless that step succeeds.  Legacy adoption is never implied by the
    scope: it happens only when the caller passes ``adopt_legacy=True``.
    """

    selected_scope = _normalize_scope(scope)
    target_root = _scope_root(selected_scope, project_root)
    selected_hosts = _normalize_hosts(hosts)
    adopt = _adoption_allowed(selected_scope, adopt_legacy)
    running = _running_version()

    if wheel is None:
        payload = install(
            selected_scope,
            project_root,
            selected_hosts,
            dry_run=dry_run,
            adopt_legacy=adopt,
        )
        writes = bool(payload.get("writes_performed"))
        return {
            "scope": selected_scope,
            "root": payload.get("root", str(target_root)),
            "wheel": None,
            "status": _payload_status(dry_run, payload),
            "version": running["xc_version"],
            "bundle_manifest_sha256": running["bundle_manifest_sha256"],
            "cli": {
                "step": "not-requested",
                "current_version": running["xc_version"],
                "target_version": running["xc_version"],
            },
            "payload": payload,
            "writes_performed": False if dry_run else writes,
        }

    wheel_path = Path(wheel)
    target_version = _wheel_version(wheel_path)
    equal = target_version == running["xc_version"]
    if equal and not force:
        payload = install(
            selected_scope,
            project_root,
            selected_hosts,
            dry_run=dry_run,
            adopt_legacy=adopt,
        )
        writes = bool(payload.get("writes_performed"))
        return {
            "scope": selected_scope,
            "root": payload.get("root", str(target_root)),
            "wheel": str(wheel_path),
            "status": _payload_status(dry_run, payload),
            "version": running["xc_version"],
            "target_version": target_version,
            "bundle_manifest_sha256": payload.get(
                "bundle_manifest_sha256",
                running["bundle_manifest_sha256"],
            ),
            "cli": {
                "step": "skipped-equal-version",
                "current_version": running["xc_version"],
                "target_version": target_version,
                "forced": False,
            },
            "payload": payload,
            "writes_performed": False if dry_run else writes,
        }

    uv = shutil.which("uv")
    if uv is None:
        raise LifecycleError(
            "uv_unavailable",
            "uv is required to replace the installed CLI",
            details={"wheel": str(wheel_path)},
        )
    uv_command = [uv, "tool", "install", "--force", str(wheel_path)]
    if dry_run:
        return {
            "scope": selected_scope,
            "root": str(target_root),
            "wheel": str(wheel_path),
            "status": "dry-run",
            "version": running["xc_version"],
            "target_version": target_version,
            "bundle_manifest_sha256": running["bundle_manifest_sha256"],
            "cli": {
                "step": "would-run",
                "command": uv_command,
                "current_version": running["xc_version"],
                "target_version": target_version,
                "forced": force,
            },
            "payload": {
                "step": "deferred-until-cli-upgrade",
                "reason": (
                    "the payload for the target version is only available "
                    "after the new CLI is installed"
                ),
                "dry_run": True,
            },
            "writes_performed": False,
        }

    uv_result = _run(uv_command, timeout=UV_TOOL_INSTALL_TIMEOUT)
    if uv_result["returncode"] != 0:
        signature = _file_in_use_signature(uv_result)
        if signature is not None:
            code = "cli_upgrade_requires_external_step"
            message = (
                "uv cannot replace the running CLI on this platform; close every "
                "xcoding process and run the uv tool install command again"
            )
        else:
            code = "cli_upgrade_failed"
            message = "uv failed to install the requested CLI wheel"
        raise LifecycleError(
            code,
            message,
            details={
                "wheel": str(wheel_path),
                "uv": uv_result,
                "signature": signature,
                "current_version": running["xc_version"],
                "target_version": target_version,
            },
        )

    launcher = shutil.which("xcoding")
    if launcher is None:
        raise LifecycleError(
            "cli_upgraded_payload_failed",
            "the upgraded CLI launcher is not available on PATH",
            details={
                "wheel": str(wheel_path),
                "uv": uv_result,
                "next_step": "open a new shell so the xcoding launcher is on PATH, then run 'xcoding install --scope ...'",
            },
        )
    payload_command = _payload_argv(
        launcher,
        selected_scope,
        target_root,
        selected_hosts,
        adopt_legacy=adopt,
    )
    payload_result = _run(payload_command, timeout=CLI_PAYLOAD_TIMEOUT)
    envelope: Any = None
    if payload_result["returncode"] == 0:
        try:
            envelope = json.loads(payload_result["stdout"])
        except (json.JSONDecodeError, TypeError):
            envelope = None
    if (
        payload_result["returncode"] != 0
        or not isinstance(envelope, dict)
        or envelope.get("ok") is not True
        or not isinstance(envelope.get("result"), dict)
    ):
        raise LifecycleError(
            "cli_upgraded_payload_failed",
            "the CLI was upgraded but the payload phase failed; do not treat this as success",
            details={
                "wheel": str(wheel_path),
                "uv": uv_result,
                "cli": payload_result,
                "payload_error": (
                    envelope.get("error")
                    if isinstance(envelope, dict)
                    else None
                ),
                "next_step": "resolve the reported payload error, then rerun 'xcoding upgrade' or 'xcoding install'",
            },
        )
    payload = envelope["result"]
    payload_version = payload.get("version")
    payload_bundle = payload.get("bundle_manifest_sha256")
    target_bundle = _wheel_bundle_sha256(wheel_path)
    verification: dict[str, Any] = {}
    if payload_version != target_version:
        verification["version"] = {
            "expected": target_version,
            "actual": payload_version,
        }
    elif target_version != running["xc_version"]:
        # A different target version must install a different Bundle.  The
        # wheel's own Bundle digest is the only pre-installation target identity
        # when the artifact carries one.
        bundle_changed = payload_bundle != running["bundle_manifest_sha256"]
        matches_target = target_bundle is not None and payload_bundle == target_bundle
        if not (bundle_changed or matches_target):
            verification["bundle_manifest_sha256"] = {
                "expected_different_from": running["bundle_manifest_sha256"],
                "expected_any": target_bundle,
                "actual": payload_bundle,
            }
    if verification:
        raise LifecycleError(
            "cli_upgraded_payload_failed",
            (
                "the CLI was upgraded but the payload phase did not run the target "
                "CLI version; do not treat this as success"
            ),
            details={
                "wheel": str(wheel_path),
                "uv": uv_result,
                "cli": payload_result,
                "payload": payload,
                "verification": verification,
                "current_version": running["xc_version"],
                "target_version": target_version,
                "next_step": "open a new shell so the target xcoding launcher is on PATH, then rerun 'xcoding upgrade' or 'xcoding install'",
            },
        )
    return {
        "scope": selected_scope,
        "root": payload.get("project_root", str(target_root)),
        "wheel": str(wheel_path),
        "status": "upgraded",
        "version": target_version,
        "bundle_manifest_sha256": payload.get(
            "bundle_manifest_sha256",
            running["bundle_manifest_sha256"],
        ),
        "cli": {
            "step": "uv-tool-install",
            "command": uv_command,
            "current_version": running["xc_version"],
            "target_version": target_version,
            "forced": force,
            "result": uv_result,
        },
        "payload": payload,
        "writes_performed": bool(payload.get("writes_performed", True)),
    }


__all__ = [
    "CLI_PAYLOAD_TIMEOUT",
    "LifecycleError",
    "SCOPES",
    "UV_TOOL_INSTALL_TIMEOUT",
    "install",
    "uninstall",
    "upgrade",
]
