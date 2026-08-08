#!/usr/bin/env python3
"""Generate the Skill-only runtime payload from canonical package modules."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CANONICAL_RELATIVE_ROOT = Path("src/xcoding/runtime")
GENERATED_RELATIVE_ROOT = Path(
    "skills/xc-orchestration-runtime/scripts/_runtime_compat"
)
MANIFEST_NAME = "manifest.json"


class SyncError(RuntimeError):
    """The compatibility payload cannot be generated or checked safely."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _regular_file(path: Path, *, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise SyncError(
            f"{label}_unreadable",
            f"{label} cannot be inspected",
            {"path": str(path), "error": str(error)},
        ) from error
    if path.is_symlink() or not stat.S_ISREG(mode):
        raise SyncError(
            f"{label}_unsafe",
            f"{label} must be a regular file",
            {"path": str(path)},
        )


def _canonical_modules(project_root: Path) -> list[Path]:
    root = project_root / CANONICAL_RELATIVE_ROOT
    if root.is_symlink() or not root.is_dir():
        raise SyncError(
            "canonical_root_missing",
            "canonical runtime root must be a regular directory",
            {"path": str(root)},
        )
    modules = sorted(root.glob("*.py"), key=lambda item: item.name)
    if not modules or not any(path.name == "core.py" for path in modules):
        raise SyncError(
            "canonical_modules_missing",
            "canonical runtime modules must include core.py",
            {"path": str(root)},
        )
    for path in modules:
        _regular_file(path, label="canonical_module")
    return modules


def _manifest_bytes(records: list[dict[str, Any]]) -> bytes:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "canonical_root": CANONICAL_RELATIVE_ROOT.as_posix(),
        "generated_root": GENERATED_RELATIVE_ROOT.as_posix(),
        "files": records,
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def expected_payload(project_root: Path) -> dict[str, bytes]:
    """Return the complete deterministic generated payload by relative path."""
    root = project_root.resolve()
    records: list[dict[str, Any]] = []
    expected: dict[str, bytes] = {}
    for source in _canonical_modules(root):
        data = source.read_bytes()
        target_relative = source.name
        expected[target_relative] = data
        records.append(
            {
                "source": (
                    CANONICAL_RELATIVE_ROOT / source.name
                ).as_posix(),
                "generated": (
                    GENERATED_RELATIVE_ROOT / source.name
                ).as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    expected[MANIFEST_NAME] = _manifest_bytes(records)
    return dict(sorted(expected.items()))


def _generated_files(target: Path) -> dict[str, Path]:
    if not target.exists():
        return {}
    if target.is_symlink() or not target.is_dir():
        raise SyncError(
            "generated_root_unsafe",
            "generated runtime root must be a regular directory",
            {"path": str(target)},
        )
    result: dict[str, Path] = {}
    for path in sorted(target.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(target)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            raise SyncError(
                "generated_entry_unsafe",
                "generated runtime entries must not be symlinks",
                {"path": str(path)},
            )
        if path.is_dir():
            continue
        _regular_file(path, label="generated_entry")
        result[relative.as_posix()] = path
    return result


def check_payload(project_root: Path) -> dict[str, Any]:
    """Compare the generated payload with canonical source bytes."""
    root = project_root.resolve()
    target = root / GENERATED_RELATIVE_ROOT
    expected = expected_payload(root)
    actual = _generated_files(target)
    expected_paths = set(expected)
    actual_paths = set(actual)
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    mismatched: list[dict[str, str]] = []
    for relative in sorted(expected_paths & actual_paths):
        actual_bytes = actual[relative].read_bytes()
        if actual_bytes != expected[relative]:
            mismatched.append(
                {
                    "path": relative,
                    "expected_sha256": hashlib.sha256(
                        expected[relative]
                    ).hexdigest(),
                    "actual_sha256": hashlib.sha256(
                        actual_bytes
                    ).hexdigest(),
                }
            )
    return {
        "ok": True,
        "valid": not missing and not unexpected and not mismatched,
        "canonical_root": str(root / CANONICAL_RELATIVE_ROOT),
        "generated_root": str(target),
        "counts": {
            "expected": len(expected),
            "actual": len(actual),
            "missing": len(missing),
            "unexpected": len(unexpected),
            "mismatched": len(mismatched),
        },
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }


def sync_payload(project_root: Path) -> dict[str, Any]:
    """Replace the generated payload from a fully prepared temporary tree."""
    root = project_root.resolve()
    target = root / GENERATED_RELATIVE_ROOT
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise SyncError(
            "generated_parent_unsafe",
            "generated runtime parent must be a regular directory",
            {"path": str(parent)},
        )
    if target.exists() and (target.is_symlink() or not target.is_dir()):
        raise SyncError(
            "generated_root_unsafe",
            "generated runtime root must be a regular directory",
            {"path": str(target)},
        )

    expected = expected_payload(root)
    with tempfile.TemporaryDirectory(
        prefix=".runtime-compat-",
        dir=parent,
    ) as temporary:
        prepared = Path(temporary) / "payload"
        prepared.mkdir()
        for relative, data in expected.items():
            destination = prepared / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(prepared, target)

    result = check_payload(root)
    if not result["valid"]:
        raise SyncError(
            "generated_verification_failed",
            "generated runtime payload failed post-write verification",
            {"result": result},
        )
    return result


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or check the fixed Skill runtime compatibility payload."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare canonical and generated files without writing.",
    )
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    try:
        payload = (
            check_payload(project_root)
            if arguments.check
            else sync_payload(project_root)
        )
    except SyncError as error:
        emit(
            {
                "ok": False,
                "valid": False,
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "details": error.details,
                },
            }
        )
        return 2
    emit(payload)
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
