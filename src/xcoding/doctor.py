"""Read-only environment and Bundle readiness reporting."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .bundle.resources import inspect_installed_bundle, installed_bundle_root
from .delegation.adapters import load_bundle_adapter_statement
from .delegation.errors import DelegationError
from .setup_plan import inspect_target_readiness
from .setup_transaction import (
    HOST_ORDER,
    HOST_TARGETS,
    REPORT_PACKAGE,
    REPORT_PACKAGE_MARKER,
    REPORT_TEMPLATE_RELATIVE,
    STATE_RELATIVE,
)


MINIMUM_PYTHON = (3, 12)
FORMAL_VERIFICATION_BASELINE = (3, 12, 13)

# The probe reports the recorded installation paths next to what it found on disk, so a
# consumer sees when the setup record and the Skill root disagree.
SETUP_RECORD_RELATIVE = STATE_RELATIVE / "manifest.json"
REPORT_PACKAGE_MISSING = "report-package-missing"
REPORT_TEMPLATE_MISSING = "report-template-missing"
REPORT_PACKAGE_PATH_MISMATCH = "report-package-path-mismatch"
SKILL_PACKAGES_ABSENT = "skill-packages-absent"


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


def _read_setup_record(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Read the setup record of a probed project without trusting or failing on it."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, ""
    except OSError as error:
        return None, type(error).__name__
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        return None, type(error).__name__
    if not isinstance(value, dict):
        return None, "record-not-an-object"
    return value, ""


def _installed_packages(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    try:
        children = sorted(root.iterdir(), key=lambda entry: entry.name)
    except OSError:
        return []
    return [
        entry.name
        for entry in children
        if entry.name.startswith("xc-") and entry.is_dir()
    ]


def _same_directory(recorded: str, resolved: Path) -> bool:
    """Whether a recorded path names the directory the host table resolves.

    The record stores an absolute path and the host table resolves one, so the two
    spellings differ only by separators, case or a relative root. Anything else is the
    drift this probe exists to name.
    """
    try:
        recorded_path = Path(recorded)
    except (TypeError, ValueError):
        return False
    try:
        return os.path.normcase(str(recorded_path.resolve())) == os.path.normcase(
            str(resolved.resolve())
        )
    except OSError:
        return os.path.normcase(str(recorded_path)) == os.path.normcase(str(resolved))


def skill_package_readiness(project_root: Path) -> dict[str, Any]:
    """Report whether the project's Skill roots hold the mounted report package.

    A consumer cannot answer this from a documentation table: the mounted subtree reads its
    template from the installed `xc-change-report` package, and the setup record is the
    installed file that names where that package lives.

    The probed roots are the project's own: when the setup record names the hosts `xcoding
    setup` installed, exactly those hosts' Skill roots are checked, so a recorded host whose
    package is absent is drift rather than noise. A project without a record falls back to
    the Skill roots that already hold an `xc-*` package. A project with neither has no Skill
    root to be incomplete, so the check passes and the separate `skill-packages-absent`
    warning records that nothing was confirmed.

    A host the record carries a package path for is also probed against that path: the mount
    resolves its subtree template from the record, so a record that names a different
    directory than the host table resolves is the drift that would only surface when the
    report node ran.
    """
    record_path = project_root.joinpath(*SETUP_RECORD_RELATIVE.parts)
    record, record_error = _read_setup_record(record_path)
    recorded: dict[str, str] = {}
    recorded_hosts: list[str] = []
    if record is not None:
        report_record = record.get("report_package")
        if isinstance(report_record, dict):
            paths = report_record.get("paths")
            if isinstance(paths, dict):
                recorded = {
                    host: value
                    for host, value in paths.items()
                    if isinstance(host, str) and isinstance(value, str)
                }
        hosts = record.get("hosts")
        if isinstance(hosts, list):
            recorded_hosts = [
                host
                for host in HOST_ORDER
                if host in {value for value in hosts if isinstance(value, str)}
            ]

    candidates: list[tuple[str, Path, list[str]]] = []
    seen: set[str] = set()
    for host in recorded_hosts or list(HOST_ORDER):
        skill_root = HOST_TARGETS[host][1]
        key = skill_root.as_posix()
        if key in seen:
            continue
        root = project_root.joinpath(*skill_root.parts)
        packages = _installed_packages(root)
        if not recorded_hosts and not packages:
            continue
        seen.add(key)
        candidates.append((host, root, packages))

    installed_roots: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for host, root, packages in candidates:
        package_path = root / REPORT_PACKAGE
        template_path = package_path.joinpath(*REPORT_TEMPLATE_RELATIVE.parts)
        package_present = (package_path / REPORT_PACKAGE_MARKER).is_file()
        template_present = template_path.is_file()
        recorded_path = recorded.get(host, "")
        recorded_matches = not recorded_path or _same_directory(recorded_path, package_path)
        installed_roots.append(
            {
                "host": host,
                "skill_root": str(root),
                "package_count": len(packages),
                "package_path": str(package_path),
                "package_present": package_present,
                "template_path": str(template_path),
                "template_present": template_present,
                "recorded_package_path": recorded_path,
                "recorded_path_matches": recorded_matches,
            }
        )
        if not recorded_matches:
            # The record is what the mount reads its subtree template from, so a path that
            # disagrees with the host table is named here rather than left to the report node.
            missing.append(
                {
                    "code": REPORT_PACKAGE_PATH_MISMATCH,
                    "host": host,
                    "skill_root": str(root),
                    "path": recorded_path,
                    "artifact": "record",
                    "message": (
                        f"the setup record names {recorded_path} as the {REPORT_PACKAGE} "
                        f"package for {host}, but this project resolves it to {package_path}; "
                        "the report stage reads the subtree template from the record"
                    ),
                }
            )
        if not package_present:
            missing.append(
                {
                    "code": REPORT_PACKAGE_MISSING,
                    "host": host,
                    "skill_root": str(root),
                    "path": str(package_path),
                    "artifact": "package",
                    "message": (
                        f"the installed Skill root {root} does not hold the "
                        f"{REPORT_PACKAGE} package the report stage mounts"
                    ),
                }
            )
        elif not template_present:
            missing.append(
                {
                    "code": REPORT_TEMPLATE_MISSING,
                    "host": host,
                    "skill_root": str(root),
                    "path": str(template_path),
                    "artifact": "template",
                    "message": (
                        f"the {REPORT_PACKAGE} package installed at {package_path} "
                        f"does not hold {REPORT_TEMPLATE_RELATIVE.as_posix()}, the "
                        "subtree template the report stage reads from it"
                    ),
                }
            )
    return {
        "project_root": str(project_root),
        "package": REPORT_PACKAGE,
        "template_file": REPORT_TEMPLATE_RELATIVE.as_posix(),
        "installed": bool(installed_roots),
        "installed_roots": installed_roots,
        "missing": missing,
        "findings": sorted({entry["code"] for entry in missing}),
        "record": {
            "path": str(record_path),
            "present": record is not None,
            "error": record_error,
            "hosts": recorded_hosts,
            "report_package_paths": recorded,
        },
        "ready": not missing,
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
                "skill-packages",
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
        packages = skill_package_readiness(target_root)
        checks.append(
            _check(
                "skill-packages",
                required=True,
                status="pass" if packages["ready"] else "fail",
                details=packages,
            )
        )
        for entry in packages["missing"]:
            warnings.append(
                {"code": entry["code"], "message": entry["message"]}
            )
        if not packages["installed"]:
            warnings.append(
                {
                    "code": SKILL_PACKAGES_ABSENT,
                    "message": (
                        "the target root holds no installed xc-* Skill package; "
                        f"the {REPORT_PACKAGE} package could not be confirmed"
                    ),
                }
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
    "REPORT_PACKAGE",
    "REPORT_TEMPLATE_RELATIVE",
    "delegation_adapter_readiness",
    "doctor_report",
    "python_readiness",
    "skill_package_readiness",
]
