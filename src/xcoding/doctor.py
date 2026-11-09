"""Read-only environment and Bundle readiness reporting."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from .bundle.resources import inspect_installed_bundle, installed_bundle_root
from .delegation.adapters import load_bundle_adapter_statement
from .delegation.errors import DelegationError
from .setup_plan import inspect_target_readiness


MINIMUM_PYTHON = (3, 12)
FORMAL_VERIFICATION_BASELINE = (3, 12, 13)


class DoctorReadinessError(RuntimeError):
    """One or more required doctor checks failed."""

    def __init__(self, report: dict[str, Any]) -> None:
        super().__init__("one or more required doctor checks failed")
        self.code = "readiness-failed"
        self.details = {"report": report}


def _check(
    check_id: str,
    *,
    required: bool,
    status: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": check_id,
        "required": required,
        "status": status,
        "details": details,
    }


def python_readiness(
    implementation: str,
    version_info: tuple[int, ...],
) -> dict[str, Any]:
    """Classify Python compatibility separately from formal evidence."""
    normalized = tuple(version_info[:3])
    version_ready = normalized[:2] >= MINIMUM_PYTHON
    implementation_ready = implementation == "CPython"
    ready = implementation_ready and version_ready
    matches_baseline = (
        implementation_ready
        and normalized == FORMAL_VERIFICATION_BASELINE
    )
    if matches_baseline:
        evidence_tier = "formal-verification-baseline"
    elif ready:
        evidence_tier = "accepted-not-formally-verified"
    else:
        evidence_tier = "unsupported"
    return {
        "ready": ready,
        "minimum_version": ".".join(map(str, MINIMUM_PYTHON)),
        "formal_verification_baseline": ".".join(
            map(str, FORMAL_VERIFICATION_BASELINE)
        ),
        "matches_formal_verification_baseline": matches_baseline,
        "evidence_tier": evidence_tier,
    }


def delegation_adapter_readiness(
    inspection: Any,
    bundle_root: Any,
) -> dict[str, Any]:
    """Validate and report every packaged host capability statement."""
    adapter_ids = sorted(
        {
            record.adapter_id
            for record in inspection.manifest.resources
            if record.kind == "host-adapter" and record.adapter_id is not None
        }
    )
    statements: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for adapter_id in adapter_ids:
        try:
            statement = load_bundle_adapter_statement(
                bundle_root,
                adapter_id,
            )
        except DelegationError as error:
            errors.append(
                {
                    "adapter_id": adapter_id,
                    "code": error.code,
                    "phase": error.phase,
                    "message": str(error),
                }
            )
            continue
        statements.append(
            {
                "adapter_id": statement["adapter_id"],
                "adapter_version": statement["adapter_version"],
                "mode": statement["mode"],
                "evidence": statement["evidence"],
                "capabilities": statement["capabilities"],
            }
        )
    if not adapter_ids:
        errors.append(
            {
                "adapter_id": "",
                "code": "adapter_statement_missing",
                "phase": "adapter",
                "message": "Bundle has no host adapter partitions",
            }
        )
    return {
        "ready": not errors,
        "statements": statements,
        "errors": errors,
    }


def payload_readiness(
    target_root: Path,
    *,
    inspection: Any | None = None,
) -> dict[str, Any]:
    """Classify an installed setup payload against the running distribution.

    The check is read-only.  It verifies the setup manifest version and bundle
    hash, then every manifest-owned file.  Files outside the manifest are
    unowned by XC and are reported as preserved rather than evaluated.

    A root without a setup manifest is not necessarily clean: the 0.3.6
    development-installer layout leaves two ``.xc-skill-install-manifest.json``
    records behind.  That layout is reported as ``legacy`` drift, not as
    ``not-installed``, because it needs the explicit adoption path.
    """

    root = Path(target_root)
    manifest_path = root / ".agents" / ".xcoding-setup" / "manifest.json"
    base: dict[str, Any] = {
        "target_root": str(root),
        "manifest_path": str(manifest_path),
    }
    if not manifest_path.exists():
        # Imported lazily so the common CLI-only doctor run never imports the
        # transaction engine.  The legacy probe itself claims and writes nothing.
        from .setup_transaction import legacy_install_status

        legacy = legacy_install_status(root)
        if not legacy["detected"]:
            return {"installed": False, "status": "not-installed"}
        return {
            **base,
            "installed": False,
            "status": "legacy",
            "legacy": legacy,
            "problems": [
                {
                    "code": "legacy-install-detected",
                    "status": "legacy",
                    "message": (
                        "a development-installer payload is present without a "
                        "setup manifest"
                    ),
                    "manifests": legacy["manifest_paths"],
                }
            ],
            "next_action": (
                "run `xcoding install --scope user --adopt-legacy` to adopt the "
                "verified legacy files, archive the legacy manifests, and "
                "create the setup manifest"
            ),
        }
    # Imported lazily so the doctor import graph stays free of the transaction
    # engine unless a target root actually asks for the payload check.
    from .setup_transaction import SetupTransactionError, load_setup_manifest

    try:
        manifest, files = load_setup_manifest(root)
    except SetupTransactionError as error:
        return {
            **base,
            "installed": True,
            "status": "invalid",
            "error": {
                "code": error.code,
                "message": str(error),
                "details": error.details,
            },
        }
    except OSError as error:
        return {
            **base,
            "installed": True,
            "status": "invalid",
            "error": {
                "code": "environment_error",
                "message": str(error),
                "details": {},
            },
        }
    if manifest is None:
        return {"installed": False, "status": "not-installed"}
    if inspection is None:
        from .version import version_report

        try:
            report = version_report()
        except Exception as error:  # report unavailable context, never crash read-only
            running: dict[str, Any] = {
                "xc_version": None,
                "bundle_manifest_sha256": None,
                "error": {
                    "code": getattr(error, "code", "version_unavailable"),
                    "message": str(error),
                },
            }
        else:
            running = {
                "xc_version": report["xc_version"],
                "bundle_manifest_sha256": report["bundle_manifest_sha256"],
            }
    else:
        running = {
            "xc_version": inspection.manifest.xc_version,
            "bundle_manifest_sha256": inspection.manifest_sha256,
        }
    problems: list[dict[str, Any]] = []
    kinds = {"skill": 0, "agent-definition": 0}
    verified = 0
    for relative in sorted(files):
        entry = files[relative]
        parts = PurePosixPath(relative).parts
        kind = (
            "agent-definition"
            if len(parts) >= 2 and parts[1] == "agents"
            else "skill"
        )
        kinds[kind] = kinds.get(kind, 0) + 1
        target = root.joinpath(*parts)
        problem: dict[str, Any] = {
            "path": relative,
            "kind": kind,
            "expected_sha256": entry["sha256"],
            "owners": list(entry["owners"]),
        }
        if not (target.exists() or target.is_symlink()):
            problems.append({**problem, "status": "missing"})
            continue
        if target.is_symlink() or not target.is_file():
            problems.append(
                {**problem, "status": "modified", "reason": "not-regular-file"}
            )
            continue
        try:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            problems.append(
                {**problem, "status": "modified", "reason": "unreadable"}
            )
            continue
        if digest != entry["sha256"]:
            problems.append(
                {
                    **problem,
                    "status": "modified",
                    "actual_sha256": digest,
                }
            )
        else:
            verified += 1
    missing = sum(1 for problem in problems if problem["status"] == "missing")
    modified = sum(1 for problem in problems if problem["status"] == "modified")
    version_matches = (
        running.get("xc_version") is not None
        and running.get("xc_version") == manifest.get("version")
    )
    bundle_matches = (
        running.get("bundle_manifest_sha256") is not None
        and running.get("bundle_manifest_sha256")
        == manifest.get("bundle_manifest_sha256")
    )
    if not version_matches or not bundle_matches:
        status = "stale"
    elif missing:
        status = "missing"
    elif modified:
        status = "modified"
    else:
        status = "current"
    return {
        **base,
        "installed": True,
        "status": status,
        "generation": manifest.get("generation"),
        "hosts": list(manifest.get("hosts", [])),
        "manifest_version": manifest.get("version"),
        "running_version": running.get("xc_version"),
        "version_matches": version_matches,
        "manifest_bundle_manifest_sha256": manifest.get(
            "bundle_manifest_sha256"
        ),
        "running_bundle_manifest_sha256": running.get(
            "bundle_manifest_sha256"
        ),
        "bundle_matches": bundle_matches,
        "counts": {
            "total": len(files),
            "verified": verified,
            "modified": modified,
            "missing": missing,
        },
        "kinds": kinds,
        "problems": problems,
        "running": running,
        "ownership": {
            "manifest_owned": len(files),
            "unowned": "preserved",
            "note": (
                "files outside the setup manifest are not owned by XC and are "
                "never changed by install or uninstall"
            ),
        },
    }


def doctor_report(target_root: Path | None = None) -> dict[str, Any]:
    """Run only read-only probes and return or raise with the complete report."""
    inspection = inspect_installed_bundle()
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    implementation = platform.python_implementation()
    python_status = python_readiness(
        implementation,
        tuple(sys.version_info[:3]),
    )
    checks.append(
        _check(
            "python",
            required=True,
            status="pass" if python_status["ready"] else "fail",
            details={
                "implementation": implementation,
                "version": platform.python_version(),
                "executable": sys.executable,
                "base_executable": getattr(
                    sys,
                    "_base_executable",
                    sys.executable,
                ),
                "required": inspection.manifest.python_requires,
                **python_status,
            },
        )
    )

    path_value = os.environ.get("PATH", "")
    path_ready = bool(path_value)
    launcher = shutil.which("xcoding")
    checks.append(
        _check(
            "path",
            required=True,
            status="pass" if path_ready else "fail",
            details={
                "configured": path_ready,
                "xcoding_launcher": launcher,
            },
        )
    )
    if path_ready and launcher is None:
        warnings.append(
            {
                "code": "xcoding-not-on-path",
                "message": (
                    "the xcoding console launcher is not currently on PATH"
                ),
            }
        )

    git = shutil.which("git")
    checks.append(
        _check(
            "git",
            required=True,
            status="pass" if git else "fail",
            details={"executable": git},
        )
    )

    try:
        tk_available = importlib.util.find_spec("tkinter") is not None
    except (ImportError, AttributeError, ValueError):
        tk_available = False
    checks.append(
        _check(
            "tk",
            required=False,
            status="pass" if tk_available else "warning",
            details={"available": tk_available, "imported": False},
        )
    )
    if not tk_available:
        warnings.append(
            {
                "code": "tk-unavailable",
                "message": "optional Tk support is unavailable",
            }
        )

    checks.append(
        _check(
            "bundle",
            required=True,
            status="pass",
            details=inspection.as_dict(),
        )
    )

    delegation_adapters = delegation_adapter_readiness(
        inspection,
        installed_bundle_root(),
    )
    checks.append(
        _check(
            "delegation-adapters",
            required=True,
            status="pass" if delegation_adapters["ready"] else "fail",
            details=delegation_adapters,
        )
    )
    for statement in delegation_adapters["statements"]:
        if statement["mode"] != "enforced":
            warnings.append(
                {
                    "code": "delegation-adapter-not-enforced",
                    "message": (
                        f"{statement['adapter_id']} delegation mode is "
                        f"{statement['mode']}; no host enforcement is claimed"
                    ),
                }
            )

    if target_root is None:
        checks.append(
            _check(
                "target",
                required=False,
                status="not-requested",
                details={"target_root": None},
            )
        )
        checks.append(
            _check(
                "payload",
                required=False,
                status="not-requested",
                details={"target_root": None},
            )
        )
    else:
        target = inspect_target_readiness(target_root)
        checks.append(
            _check(
                "target",
                required=True,
                status="pass" if target["ready"] else "fail",
                details=target,
            )
        )
        payload = payload_readiness(target_root, inspection=inspection)
        if payload["status"] == "legacy":
            # The 0.3.6 layout is real installed drift, not a clean machine:
            # it must fail readiness until the explicit adoption runs.
            checks.append(
                _check(
                    "payload",
                    required=True,
                    status="fail",
                    details=payload,
                )
            )
        elif not payload["installed"]:
            checks.append(
                _check(
                    "payload",
                    required=False,
                    status="not-installed",
                    details=payload,
                )
            )
            warnings.append(
                {
                    "code": "payload-not-installed",
                    "message": (
                        "no setup manifest is installed at the target root; "
                        "payload consistency was not evaluated"
                    ),
                }
            )
        else:
            checks.append(
                _check(
                    "payload",
                    required=True,
                    status=(
                        "pass" if payload["status"] == "current" else "fail"
                    ),
                    details=payload,
                )
            )

    ready = all(
        check["status"] == "pass"
        for check in checks
        if check["required"]
    )
    report = {"ready": ready, "checks": checks, "warnings": warnings}
    if not ready:
        raise DoctorReadinessError(report)
    return report


__all__ = [
    "DoctorReadinessError",
    "FORMAL_VERIFICATION_BASELINE",
    "MINIMUM_PYTHON",
    "delegation_adapter_readiness",
    "doctor_report",
    "payload_readiness",
    "python_readiness",
]
