#!/usr/bin/env python3
"""Convenience wrapper: clean old xc-* skills in a target project and install the latest from this repo.

Usage:
    python install_skills.py --target-skills C:\\dev\\my-project\\.agents\\skills
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean old xc-* skills in a target project and install the latest from this repo."
    )
    parser.add_argument(
        "--target-skills",
        required=True,
        help="Path to the target project's skills directory (e.g. C:\\dev\\my-project\\.agents\\skills).",
    )
    args = parser.parse_args()

    target_skills = Path(args.target_skills).expanduser().resolve()
    if not target_skills.is_dir():
        print(f"Error: target skills directory does not exist: {target_skills}", file=sys.stderr)
        return 1

    target_root = target_skills.parent
    manifest = target_root / ".xc-skill-install-manifest.json"

    source_root = Path(__file__).resolve().parent

    # Step 1: Clean old xc-* skills
    old_packages = sorted(
        d.name for d in target_skills.iterdir()
        if d.is_dir() and d.name.startswith("xc-")
    )
    if old_packages:
        print(f"Cleaning {len(old_packages)} old xc-* package(s):")
        for pkg in old_packages:
            pkg_path = target_skills / pkg
            shutil.rmtree(str(pkg_path))
            print(f"  removed: {pkg}")
    else:
        print("No old xc-* packages to clean.")

    # Step 2: Remove stale manifest if present
    if manifest.exists():
        manifest.unlink()
        print(f"  removed stale manifest: {manifest}")

    # Step 3: Run the installer
    installer = source_root / "skills" / "xc-workflow-evolution" / "scripts" / "install_xc_skills.py"
    if not installer.is_file():
        print(f"Error: installer not found at {installer}", file=sys.stderr)
        return 1

    print(f"\nInstalling latest xc-* skills from {source_root} ...")
    result = subprocess.run(
        [
            sys.executable,
            str(installer),
            "--source-root", str(source_root),
            "--target-root", str(target_root),
            "--manifest", str(manifest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    # Step 4: Verify
    print("Verifying installation ...")
    check_result = subprocess.run(
        [
            sys.executable,
            str(installer),
            "--source-root", str(source_root),
            "--target-root", str(target_root),
            "--manifest", str(manifest),
            "--check",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(check_result.stdout)
    return check_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
