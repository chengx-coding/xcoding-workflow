"""Read-only environment and Bundle readiness reporting."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .bundle.resources import inspect_installed_bundle
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

    if target_root is None:
        checks.append(
            _check(
                "target",
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
    "doctor_report",
    "python_readiness",
]
