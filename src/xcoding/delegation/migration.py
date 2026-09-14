"""Read-only legacy delegation producer discovery."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from .errors import fail
from .paths import _is_link_or_junction


LEGACY_MARKERS = ("<agent_definition>", "<agent_prompt>", "xc-delegated-agent")


def _read_public_text(path: Path) -> str:
    if _is_link_or_junction(path):
        fail("path_reparse_forbidden", "legacy-scan", "legacy scan candidate must not be a link")
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            fail("path_not_regular", "legacy-scan", "legacy scan candidate must be a regular file")
        data = path.read_bytes()
    except OSError:
        fail("path_unavailable", "legacy-scan", "legacy scan candidate could not be read")
    if len(data) > 64 * 1024:
        fail("resource_limit_exceeded", "legacy-scan", "legacy scan candidate exceeds 64 KiB")
    try:
        return data.decode("utf-8")
    except UnicodeError:
        fail("resource_encoding_invalid", "legacy-scan", "legacy scan candidates must be UTF-8")


def scan_legacy(source_root: Path | str) -> dict[str, Any]:
    """Report marker locations without returning prompt or instruction content."""
    root = Path(source_root)
    if not root.is_absolute():
        fail("path_unsafe", "legacy-scan", "source_root must be absolute")
    if _is_link_or_junction(root):
        fail("path_reparse_forbidden", "legacy-scan", "source_root must not be a link or junction")
    try:
        if not stat.S_ISDIR(root.lstat().st_mode):
            fail("path_not_regular", "legacy-scan", "source_root must be a directory")
    except OSError:
        fail("path_unavailable", "legacy-scan", "source_root is unavailable")

    candidates: list[Path] = []
    canonical_agent = root / "agents-src" / "agents" / "xc-delegated-agent.md"
    if canonical_agent.exists():
        candidates.append(canonical_agent)
    skills_root = root / "skills"
    if skills_root.is_dir() and not _is_link_or_junction(skills_root):
        for package in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if package.name.startswith("xc-") and package.is_dir() and not _is_link_or_junction(package):
                public_contract = package / "SKILL.md"
                if public_contract.exists():
                    candidates.append(public_contract)

    findings: list[dict[str, Any]] = []
    for path in candidates:
        text = _read_public_text(path)
        markers: dict[str, list[int]] = {}
        for marker in LEGACY_MARKERS:
            lines = [
                index
                for index, line in enumerate(text.splitlines(), start=1)
                if marker in line
            ]
            if lines:
                markers[marker] = lines
        if markers:
            findings.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "markers": [
                        {"id": marker, "lines": markers[marker]}
                        for marker in sorted(markers)
                    ],
                }
            )
    return {
        "schema_version": 1,
        "kind": "xc-delegation-legacy-scan/v1",
        "writes_performed": False,
        "scanned_contracts": len(candidates),
        "findings": findings,
        "content_included": False,
    }


__all__ = ["LEGACY_MARKERS", "scan_legacy"]
