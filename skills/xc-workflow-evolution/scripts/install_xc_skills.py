#!/usr/bin/env python3
"""Install complete xc-* Skill packages into an explicit consumer target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA_VERSION = 1
INSTALLER_VERSION = "1"
NOISE_DIRECTORY_NAMES = {"__pycache__"}
NOISE_FILE_SUFFIXES = {".pyc", ".pyo"}
RETIRED_SOURCE_PACKAGES = {
    "xc-" + "context-setup",
    "xc-" + "create-run",
    "xc-" + "run",
}


class InstallerError(RuntimeError):
    """A stable installer error with a machine-readable code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def resolved_directory(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_dir():
        raise InstallerError("invalid_directory", f"{label} must be an existing directory", {"path": str(path)})
    return path


def relative_to(path: Path, parent: Path, label: str) -> Path:
    try:
        return path.relative_to(parent)
    except ValueError as exc:
        raise InstallerError(
            "invalid_path",
            f"{label} must be inside its declared root",
            {"path": str(path), "root": str(parent)},
        ) from exc


def source_and_target_roots(source_value: str, target_value: str) -> tuple[Path, Path, Path, Path]:
    source_root = resolved_directory(source_value, "source root")
    target_root = resolved_directory(target_value, "target root")
    source_skills = source_root / "skills"
    target_skills = target_root / "skills"
    if not source_skills.is_dir():
        raise InstallerError(
            "invalid_source_root",
            "source root must contain a skills directory",
            {"source_root": str(source_root)},
        )
    if not target_skills.is_dir():
        raise InstallerError(
            "invalid_target_root",
            "target root must contain a skills directory",
            {"target_root": str(target_root)},
        )
    return source_root, target_root, source_skills, target_skills


def manifest_path(path_value: str, target_root: Path) -> Path:
    path = Path(path_value).expanduser().resolve()
    relative_to(path, target_root, "manifest")
    return path


def is_noise(path: Path) -> bool:
    return any(part in NOISE_DIRECTORY_NAMES for part in path.parts) or path.suffix.lower() in NOISE_FILE_SUFFIXES


def package_names(skills_root: Path) -> list[str]:
    packages = sorted(entry.name for entry in skills_root.iterdir() if entry.is_dir() and entry.name.startswith("xc-"))
    if not packages:
        raise InstallerError("missing_xc_packages", "source skills directory contains no xc-* packages")
    retired = sorted(set(packages).intersection(RETIRED_SOURCE_PACKAGES))
    if retired:
        raise InstallerError(
            "retired_xc_packages",
            "source skills directory contains retired package names",
            {"packages": retired},
        )
    for package in packages:
        skill_file = skills_root / package / "SKILL.md"
        if not skill_file.is_file():
            raise InstallerError(
                "invalid_xc_package",
                "each xc-* package must contain SKILL.md",
                {"package": package, "path": str(skill_file)},
            )
    return packages


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_files(skills_root: Path, packages: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for package in packages:
        package_root = skills_root / package
        for candidate in sorted(package_root.rglob("*")):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(skills_root)
            if is_noise(relative):
                continue
            files[relative.as_posix()] = sha256(candidate)
    return files


def target_package_names(target_skills: Path) -> list[str]:
    return sorted(entry.name for entry in target_skills.iterdir() if entry.is_dir() and entry.name.startswith("xc-"))


def git_details(source_root: Path, revision_override: str) -> tuple[str, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=source_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if revision_override:
        if status.returncode == 0:
            return revision_override, "dirty" if status.stdout.strip() else "clean"
        return revision_override, "not-git"
    if revision.returncode != 0 or status.returncode != 0:
        detail = revision.stderr.strip() or status.stderr.strip() or "git metadata unavailable"
        raise InstallerError("source_git_unavailable", "source Git revision is required without an override", {"detail": detail})
    return revision.stdout.strip(), "dirty" if status.stdout.strip() else "clean"


def source_snapshot(source_root: Path, source_skills: Path, revision_override: str) -> dict[str, Any]:
    packages = package_names(source_skills)
    revision, worktree_state = git_details(source_root, revision_override)
    files = inventory_files(source_skills, packages)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "installer_version": INSTALLER_VERSION,
        "source_root": str(source_root),
        "source_revision": revision,
        "source_worktree_state": worktree_state,
        "expected_packages": packages,
        "files": [{"path": path, "sha256": files[path]} for path in sorted(files)],
    }


def source_file_map(snapshot: dict[str, Any]) -> dict[str, str]:
    raw_files = snapshot.get("files")
    if not isinstance(raw_files, list):
        raise InstallerError("invalid_manifest", "manifest files must be a list")
    result: dict[str, str] = {}
    for record in raw_files:
        if not isinstance(record, dict):
            raise InstallerError("invalid_manifest", "manifest file records must be objects")
        path = record.get("path")
        digest = record.get("sha256")
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise InstallerError("invalid_manifest", "manifest file path is invalid", {"path": path})
        if not isinstance(digest, str) or len(digest) != 64:
            raise InstallerError("invalid_manifest", "manifest file hash is invalid", {"path": path})
        if path in result:
            raise InstallerError("invalid_manifest", "manifest contains duplicate file records", {"path": path})
        result[path] = digest
    return result


def load_manifest(path: Path, target_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise InstallerError("missing_manifest", "manifest does not exist", {"manifest": str(path)})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError("invalid_manifest", "manifest is not valid JSON", {"manifest": str(path), "detail": str(exc)}) from exc
    if not isinstance(data, dict):
        raise InstallerError("invalid_manifest", "manifest root must be an object", {"manifest": str(path)})
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise InstallerError("invalid_manifest", "manifest schema version is unsupported", {"manifest": str(path)})
    if not isinstance(data.get("installer_version"), str) or not data["installer_version"]:
        raise InstallerError("invalid_manifest", "manifest installer version is missing", {"manifest": str(path)})
    if Path(str(data.get("target_root", ""))).expanduser().resolve() != target_root:
        raise InstallerError(
            "foreign_manifest",
            "manifest target root does not match the requested target root",
            {"manifest_target_root": data.get("target_root"), "target_root": str(target_root)},
        )
    packages = data.get("expected_packages")
    if not isinstance(packages, list) or not packages or any(
        not isinstance(package, str) or not package.startswith("xc-") for package in packages
    ):
        raise InstallerError("invalid_manifest", "manifest expected packages are invalid", {"manifest": str(path)})
    if packages != sorted(set(packages)):
        raise InstallerError("invalid_manifest", "manifest expected packages must be sorted and unique", {"manifest": str(path)})
    source_file_map(data)
    return data


def target_drift(target_skills: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    expected_packages = list(manifest["expected_packages"])
    expected_files = source_file_map(manifest)
    problems: list[dict[str, str]] = []
    actual_packages = set(target_package_names(target_skills))
    expected_package_set = set(expected_packages)
    for package in sorted(expected_package_set - actual_packages):
        problems.append({"kind": "missing_package", "path": package})
    for package in sorted(actual_packages - expected_package_set):
        problems.append({"kind": "unexpected_package", "path": package})

    actual_files = inventory_files(target_skills, sorted(actual_packages.intersection(expected_package_set)))
    for path in sorted(set(expected_files) - set(actual_files)):
        problems.append({"kind": "missing_file", "path": path})
    for path in sorted(set(actual_files) - set(expected_files)):
        problems.append({"kind": "unexpected_file", "path": path})
    for path in sorted(set(expected_files).intersection(actual_files)):
        if expected_files[path] != actual_files[path]:
            problems.append({"kind": "changed_file", "path": path})
    return problems


def snapshot_mismatches(manifest: dict[str, Any], snapshot: dict[str, Any], target_root: Path) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    compared_fields = ("source_root", "source_revision", "source_worktree_state", "expected_packages")
    for field in compared_fields:
        if manifest.get(field) != snapshot.get(field):
            mismatches.append({"kind": "source_mismatch", "path": field})
    if Path(str(manifest.get("target_root", ""))).expanduser().resolve() != target_root:
        mismatches.append({"kind": "target_mismatch", "path": "target_root"})
    if source_file_map(manifest) != source_file_map(snapshot):
        mismatches.append({"kind": "source_mismatch", "path": "files"})
    return mismatches


def copy_ignore(_: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        path = Path(name)
        if name in NOISE_DIRECTORY_NAMES or path.suffix.lower() in NOISE_FILE_SUFFIXES:
            ignored.add(name)
    return ignored


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def install(source_root: Path, target_root: Path, source_skills: Path, target_skills: Path, manifest_path_value: Path, revision_override: str) -> dict[str, Any]:
    snapshot = source_snapshot(source_root, source_skills, revision_override)
    existing_manifest: dict[str, Any] | None = None
    existing_manifest_bytes: bytes | None = None
    if manifest_path_value.exists():
        existing_manifest = load_manifest(manifest_path_value, target_root)
        drift = target_drift(target_skills, existing_manifest)
        if drift:
            raise InstallerError("target_drift", "target differs from its existing manifest", {"problems": drift})
        existing_manifest_bytes = manifest_path_value.read_bytes()
    elif target_package_names(target_skills):
        raise InstallerError(
            "unmanaged_target_packages",
            "target already contains xc-* packages without a manifest",
            {"packages": target_package_names(target_skills)},
        )

    manifest = {
        **snapshot,
        "target_root": str(target_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    source_packages = list(snapshot["expected_packages"])
    previous_packages = list(existing_manifest["expected_packages"]) if existing_manifest else []
    stage_root = Path(tempfile.mkdtemp(prefix=".xc-skill-install-", dir=target_root))
    stage_packages = stage_root / "packages"
    backup_packages = stage_root / "backup"
    backed_up: list[str] = []
    installed: list[str] = []
    try:
        stage_packages.mkdir()
        backup_packages.mkdir()
        for package in source_packages:
            shutil.copytree(source_skills / package, stage_packages / package, ignore=copy_ignore, copy_function=shutil.copy2)

        for package in previous_packages:
            source = target_skills / package
            if source.exists():
                shutil.move(str(source), str(backup_packages / package))
                backed_up.append(package)
        for package in source_packages:
            destination = target_skills / package
            if destination.exists():
                raise InstallerError(
                    "unmanaged_target_packages",
                    "target contains an unexpected xc-* package during installation",
                    {"package": package},
                )
            shutil.move(str(stage_packages / package), str(destination))
            installed.append(package)
        write_manifest(manifest_path_value, manifest)
    except Exception:
        for package in installed:
            destination = target_skills / package
            if destination.exists():
                shutil.rmtree(destination)
        for package in backed_up:
            backup = backup_packages / package
            if backup.exists():
                shutil.move(str(backup), str(target_skills / package))
        if existing_manifest_bytes is None:
            if manifest_path_value.exists():
                manifest_path_value.unlink()
        else:
            manifest_path_value.write_bytes(existing_manifest_bytes)
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    return {
        "ok": True,
        "operation": "install",
        "manifest": str(manifest_path_value),
        "packages": source_packages,
        "removed_stale_packages": sorted(set(previous_packages) - set(source_packages)),
        "source_revision": snapshot["source_revision"],
        "source_worktree_state": snapshot["source_worktree_state"],
    }


def check(source_root: Path, target_root: Path, source_skills: Path, target_skills: Path, manifest_path_value: Path, revision_override: str) -> tuple[bool, dict[str, Any]]:
    try:
        manifest = load_manifest(manifest_path_value, target_root)
    except InstallerError as exc:
        return False, {"ok": False, "operation": "check", "problems": [{"kind": exc.code, "path": str(manifest_path_value)}]}
    snapshot = source_snapshot(source_root, source_skills, revision_override)
    problems = target_drift(target_skills, manifest)
    problems.extend(snapshot_mismatches(manifest, snapshot, target_root))
    return not problems, {
        "ok": not problems,
        "operation": "check",
        "manifest": str(manifest_path_value),
        "packages": snapshot["expected_packages"],
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install complete xc-* Skill packages into an explicit consumer target.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-revision", default="", help="Explicit source revision for non-Git or isolated test sources.")
    parser.add_argument("--check", action="store_true", help="Verify source, manifest, and target state without writing.")
    args = parser.parse_args(argv)
    try:
        source_root, target_root, source_skills, target_skills = source_and_target_roots(args.source_root, args.target_root)
        selected_manifest = manifest_path(args.manifest, target_root)
        if args.check:
            valid, payload = check(
                source_root,
                target_root,
                source_skills,
                target_skills,
                selected_manifest,
                args.source_revision,
            )
            json_print(payload)
            return 0 if valid else 1
        json_print(
            install(
                source_root,
                target_root,
                source_skills,
                target_skills,
                selected_manifest,
                args.source_revision,
            )
        )
        return 0
    except InstallerError as exc:
        json_print({"ok": False, "error": {"code": exc.code, "message": str(exc), "details": exc.details}})
        return 2
    except OSError as exc:
        json_print({"ok": False, "error": {"code": "io_error", "message": str(exc), "details": {}}})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
