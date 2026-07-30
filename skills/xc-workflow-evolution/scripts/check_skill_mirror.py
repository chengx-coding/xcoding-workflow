#!/usr/bin/env python3
"""Check that a discovery mirror exactly matches canonical XC Skill packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence


RETIRED_PACKAGES = {
    "xc-" + "context-setup",
    "xc-" + "create-run",
    "xc-" + "run",
}


class MirrorError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def digest_file(path: Path) -> dict[str, object]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MirrorError(
            "mirror_file_unreadable",
            "Skill file cannot be read",
            {"path": str(path), "error": str(exc)},
        ) from exc
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def package_names(root: Path) -> list[str]:
    names: list[str] = []
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        raise MirrorError(
            "skill_root_unreadable",
            "Skill root cannot be read",
            {"root": str(root), "error": str(exc)},
        ) from exc
    for entry in entries:
        if not entry.name.startswith("xc-"):
            continue
        if entry.is_symlink() or not entry.is_dir():
            raise MirrorError(
                "invalid_skill_package",
                "XC Skill package must be a regular directory",
                {"path": str(entry)},
            )
        names.append(entry.name)
    return sorted(names)


def skill_manifest(root: Path) -> dict[str, dict[str, object]]:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise MirrorError(
            "skill_root_missing",
            "Skill root does not exist",
            {"root": str(resolved)},
        )
    packages = package_names(resolved)
    retired = sorted(RETIRED_PACKAGES.intersection(packages))
    if retired:
        raise MirrorError(
            "retired_xc_packages",
            "Skill root contains retired XC packages",
            {"root": str(resolved), "packages": retired},
        )

    manifest: dict[str, dict[str, object]] = {}
    for package in packages:
        package_root = resolved / package
        if not (package_root / "SKILL.md").is_file():
            raise MirrorError(
                "skill_contract_missing",
                "XC Skill package has no SKILL.md",
                {"package": package, "root": str(resolved)},
            )
        for path in sorted(package_root.rglob("*"), key=lambda item: item.as_posix()):
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise MirrorError(
                    "skill_symlink_not_allowed",
                    "XC Skill manifests do not accept symbolic links",
                    {"path": str(path)},
                )
            if path.is_dir():
                continue
            if not path.is_file():
                raise MirrorError(
                    "invalid_skill_entry",
                    "XC Skill manifest entry is not a regular file",
                    {"path": str(path)},
                )
            relative = path.relative_to(resolved).as_posix()
            manifest[relative] = digest_file(path)
    return dict(sorted(manifest.items()))


def check_mirror(canonical_root: Path, mirror_root: Path) -> dict[str, object]:
    canonical = skill_manifest(canonical_root)
    mirror = skill_manifest(mirror_root)
    canonical_paths = set(canonical)
    mirror_paths = set(mirror)
    missing = sorted(canonical_paths - mirror_paths)
    unexpected = sorted(mirror_paths - canonical_paths)
    mismatched = [
        {
            "path": path,
            "canonical": canonical[path],
            "mirror": mirror[path],
        }
        for path in sorted(canonical_paths & mirror_paths)
        if canonical[path] != mirror[path]
    ]
    valid = not missing and not unexpected and not mismatched
    return {
        "ok": True,
        "valid": valid,
        "canonical_root": str(canonical_root.expanduser().resolve()),
        "mirror_root": str(mirror_root.expanduser().resolve()),
        "counts": {
            "canonical_files": len(canonical),
            "mirror_files": len(mirror),
            "missing": len(missing),
            "unexpected": len(unexpected),
            "mismatched": len(mismatched),
        },
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a discovery mirror against canonical XC Skill packages.",
    )
    parser.add_argument(
        "--canonical-root",
        required=True,
        help="Directory containing canonical xc-* package directories.",
    )
    parser.add_argument(
        "--mirror-root",
        required=True,
        help="Directory containing mirrored xc-* package directories.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = check_mirror(Path(args.canonical_root), Path(args.mirror_root))
    except MirrorError as exc:
        emit(
            {
                "ok": False,
                "valid": False,
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": exc.details,
                },
            }
        )
        return 2
    emit(payload)
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
