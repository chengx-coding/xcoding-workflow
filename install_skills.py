#!/usr/bin/env python3
"""Replace installed xc-* Skill packages with the canonical target packages.

Usage:
    python install_skills.py --target-skills C:\\dev\\my-project\\.agents\\skills

Only the packages the previous install manifest owns are removed before the new
install, plus any directory whose name the canonical source set is about to
install. An xc-* directory the manifest does not own and the canonical source
set does not provide is preserved across the install and reported; --force
replaces it instead. Each preserved directory is recorded in the install
manifest as intentionally unowned, and the verification this script prints runs
after the preserved directories are restored, so the result describes the tree
the caller actually receives.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def absolute_path(path_value: str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(path_value)))


def canonical_package_names(source_skills: Path) -> set[str]:
    """Package names the canonical source set is about to install."""
    if not source_skills.is_dir():
        return set()
    return {
        entry.name
        for entry in source_skills.iterdir()
        if entry.is_dir() and entry.name.startswith("xc-")
    }


def installed_package_names(target_skills: Path) -> list[str]:
    return sorted(
        entry.name
        for entry in target_skills.iterdir()
        if entry.is_dir() and entry.name.startswith("xc-")
    )


def manifest_owned_packages(manifest: Path) -> set[str]:
    """Packages the previous install manifest owns.

    An absent, unreadable or malformed manifest owns nothing, so every xc-*
    directory already in the target counts as unowned and is guarded.
    """
    if not manifest.is_file():
        return set()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    packages = data.get("expected_packages")
    if not isinstance(packages, list):
        return set()
    return {name for name in packages if isinstance(name, str) and name.startswith("xc-")}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace installed xc-* Skill packages with the canonical target packages."
    )
    parser.add_argument(
        "--target-skills",
        required=True,
        help="Path to the target project's skills directory (e.g. C:\\dev\\my-project\\.agents\\skills).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace xc-* directories the previous install manifest does not own instead of preserving them.",
    )
    args = parser.parse_args()

    target_skills = absolute_path(args.target_skills)
    if not target_skills.is_dir():
        print(f"Error: target skills directory does not exist: {target_skills}", file=sys.stderr)
        return 1

    target_root = target_skills.parent
    manifest = target_root / ".xc-skill-install-manifest.json"

    source_root = Path(__file__).resolve().parent
    source_skills = source_root / "skills"

    # Step 1: Decide what may be removed. The previous install manifest owns its
    # recorded packages, and a directory whose name the canonical source set
    # installs is replaced by design - that is this installer's stated purpose.
    # Any other xc-* directory is unowned and is never deleted without --force.
    owned = manifest_owned_packages(manifest)
    canonical = canonical_package_names(source_skills)
    present = installed_package_names(target_skills)
    if args.force:
        replaced = list(present)
        unowned: list[str] = []
    else:
        replaced = [name for name in present if name in owned or name in canonical]
        unowned = [name for name in present if name not in owned and name not in canonical]
    removed = [name for name in replaced if name in owned]
    superseded = [name for name in replaced if name not in owned and name in canonical]
    forced = [name for name in replaced if name not in owned and name not in canonical]

    if replaced:
        print(f"Removing {len(replaced)} installed xc-* package(s):")
        for pkg in removed:
            shutil.rmtree(str(target_skills / pkg))
            print(f"  removed: {pkg} (owned by the previous install manifest)")
        for pkg in superseded:
            shutil.rmtree(str(target_skills / pkg))
            print(f"  removed: {pkg} (hand-installed copy, replaced by the canonical package)")
        for pkg in forced:
            shutil.rmtree(str(target_skills / pkg))
            print(f"  removed: {pkg} (unowned, removed because --force was given)")
    else:
        print("No installed xc-* packages to remove.")

    if unowned:
        print(
            f"Preserving {len(unowned)} xc-* directory(ies) this installer does not own "
            "(re-run with --force to replace them):"
        )
        for pkg in unowned:
            print(f"  preserved: {pkg}")

    # Step 2: Remove stale manifest if present
    if manifest.exists():
        manifest.unlink()
        print(f"  removed stale manifest: {manifest}")

    # Move the unowned directories aside for the duration of the install, because
    # the package installer refuses a target that holds xc-* packages it cannot
    # account for. They are restored below, so a plain install never deletes them.
    preserve_root: Path | None = None
    if unowned:
        preserve_root = Path(tempfile.mkdtemp(prefix=".xc-skill-preserve-", dir=target_root))
        for pkg in unowned:
            shutil.move(str(target_skills / pkg), str(preserve_root / pkg))

    try:
        # Step 3: Run the installer
        installer = source_root / "skills" / "xc-workflow-evolution" / "scripts" / "install_xc_skills.py"
        if not installer.is_file():
            print(f"Error: installer not found at {installer}", file=sys.stderr)
            return 1

        print(f"\nInstalling latest xc-* skills from {source_root} ...")
        command = [
            sys.executable,
            str(installer),
            "--source-root", str(source_root),
            "--target-root", str(target_root),
            "--manifest", str(manifest),
        ]
        # The preserved directories are part of the tree this run leaves behind, so the
        # install manifest declares them as intentionally unowned. Without that the
        # verification below would measure the restored tree and report them as
        # unexpected packages, which no caller of a plain install could ever satisfy.
        for pkg in unowned:
            command.extend(["--unowned-package", pkg])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode
    finally:
        if preserve_root is not None:
            for pkg in unowned:
                staged = preserve_root / pkg
                if not staged.exists():
                    continue
                if (target_skills / pkg).exists():
                    print(
                        f"Warning: {pkg} was reinstalled; the preserved copy stays at {staged}",
                        file=sys.stderr,
                    )
                    continue
                shutil.move(str(staged), str(target_skills / pkg))
            leftovers = sorted(entry.name for entry in preserve_root.iterdir())
            if leftovers:
                print(f"Warning: preserved copies remain under {preserve_root}", file=sys.stderr)
            else:
                preserve_root.rmdir()

    # Step 4: Verify the package set of the tree this run leaves behind, after the
    # preserved directories were put back. A check taken before the restoration
    # describes transient bytes, not the installation a caller receives.
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
    if check_result.returncode != 0:
        print(check_result.stderr, file=sys.stderr)
    return check_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
