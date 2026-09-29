"""Check explicit current release references against pyproject.toml."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_support.version import read_project_version, validate_version, wheel_filename


CURRENT_PAGES = (
    "README.md", "README.zh-CN.md",
    "docs/development/versioning.md", "docs/zh-CN/development/versioning.md",
)
MARKER = re.compile(r"<!-- xc:version -->(.*?)<!-- /xc:version -->", re.DOTALL)


def check(root: Path, *, tag: str | None = None, release_notes: tuple[Path, ...] = ()) -> list[str]:
    errors: list[str] = []
    version = read_project_version(root)
    for name in CURRENT_PAGES:
        try:
            content = (root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"{name}: cannot read current release references: {error}")
            continue
        values = MARKER.findall(content)
        remaining = MARKER.sub("", content)
        if not values or re.search(r"<!--\s*/?\s*xc:version", remaining):
            errors.append(f"{name}: missing or malformed current-version markers")
        for value in values:
            try:
                validate_version(value)
            except ValueError:
                errors.append(f"{name}: invalid marked version {value!r}")
            if value != version:
                errors.append(f"{name}: current version {value!r} differs from {version}")
        # Only these current-reference pages carry current wheel examples.
        for filename in re.findall(r"xcoding_workflow-[^\s`<>/]+\.whl", content):
            if filename != wheel_filename(version):
                errors.append(f"{name}: stale or invalid current wheel example {filename}")
    if tag is not None and tag != f"v{version}":
        errors.append(f"tag must be v{version}")
    for notes in release_notes:
        text = notes.read_text(encoding="utf-8")
        if f"## {version}" not in text.splitlines():
            errors.append(f"release notes must contain exact heading: ## {version}")
    return errors


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag", help="Explicit candidate tag, spelled vMAJOR.MINOR.PATCH")
    parser.add_argument("--release-notes", type=Path, action="append", default=[], help="Explicit notes file containing an exact ## MAJOR.MINOR.PATCH heading")
    options = parser.parse_args(arguments)
    try:
        errors = check(options.project_root, tag=options.tag, release_notes=options.release_notes)
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        errors = [str(error)]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Version references are consistent with pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
