#!/usr/bin/env python3
"""Deterministic, read-only project-convention candidate scanner for xc-conventions.

The scanner answers only mechanical questions:

* which convention candidate files exist,
* their authority tier (C1 declared instruction files vs C2 configured facts),
* how near each candidate is to the requested target paths,
* whether each candidate is readable.

It deliberately does NOT parse or interpret rule semantics. Applicability is an
agent judgment. It is read-only, deterministic (sorted output, no timestamps in
the result), honors ``.gitignore``, applies a file/time budget, and fails closed:
an unreadable project root or an internal error yields ``scan-unavailable``
rather than an empty "no conventions" result.

Only tool-neutral, ecosystem-wide file families live here. Language or framework
specific signal files are supplied through ``--bridge-location`` by the project
bridge; they are never hard-coded into the generic core.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

# Tool-neutral, ecosystem-wide declared instruction files (C1).
C1_FILES = frozenset(
    {
        "agents.md",
        "claude.md",
        "gemini.md",
        ".cursorrules",
        "copilot-instructions.md",
        "contributing.md",
    }
)
# Declared instruction directories whose contained files are all C1.
C1_RULE_DIRS = (".cursor/rules",)
# Tool-neutral machine-enforced facts (C2).
C2_FILES = frozenset({".editorconfig"})
C2_RULE_DIRS = (".github/workflows",)

DEFAULT_MAX_FILES = 4000
DEFAULT_DEADLINE_MS = 5000
MAX_HASH_BYTES = 2 * 1024 * 1024  # larger files are still reported, just not hashed


@dataclass(frozen=True)
class Candidate:
    path: str
    tier: str
    kind: str
    distance: int
    readable: bool

    def to_dict(self, sha256: str | None) -> dict[str, object]:
        item: dict[str, object] = {
            "path": self.path,
            "tier": self.tier,
            "kind": self.kind,
            "distance": self.distance,
            "readable": self.readable,
        }
        if sha256 is not None:
            item["sha256"] = sha256
        return item


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _norm_targets(root: Path, values: list[str]) -> list[Path]:
    """Resolve targets to their containing directories, constrained to root."""
    resolved_root = root.resolve()
    directories: list[Path] = []
    seen: set[Path] = set()

    def add(directory: Path) -> None:
        resolved = directory.resolve()
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            return
        if resolved not in seen:
            seen.add(resolved)
            directories.append(resolved)

    for value in values:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / value
        add(candidate if candidate.is_dir() else candidate.parent)
    if not directories:
        add(resolved_root)
    return directories


def _search_dirs(root: Path, target_dirs: list[Path]) -> list[Path]:
    """Each target directory plus every ancestor up to and including root."""
    resolved_root = root.resolve()
    ordered: list[Path] = []
    seen: set[Path] = set()

    def add(directory: Path) -> None:
        if directory not in seen:
            seen.add(directory)
            ordered.append(directory)

    for target in target_dirs:
        current = target
        while True:
            add(current)
            if current == resolved_root or current.parent == current:
                break
            current = current.parent
    add(resolved_root)
    return ordered


def _distance(directory: Path, anchors: list[Path]) -> int:
    """Directory-tree distance to the nearest anchor directory."""
    best: int | None = None
    for anchor in anchors:
        try:
            value = len(anchor.relative_to(directory).parts)
        except ValueError:
            try:
                value = len(directory.relative_to(anchor).parts)
            except ValueError:
                value = len(directory.parts) + len(anchor.parts)
        best = value if best is None else min(best, value)
    return 0 if best is None else best


class IgnoreMatcher:
    """Best-effort .gitignore decision, preferring the local Git CLI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.use_git = (root / ".git").exists()
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> list[str]:
        ignore = self.root / ".gitignore"
        if not ignore.is_file():
            return []
        try:
            lines = ignore.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        return [line.strip().rstrip("/") for line in lines if line.strip() and not line.strip().startswith("#")]

    def ignored(self, rel_path: str) -> bool:
        if self.use_git:
            try:
                proc = subprocess.run(
                    ["git", "check-ignore", "--quiet", "--", rel_path],
                    cwd=str(self.root),
                    timeout=10,
                )
                if proc.returncode == 0:
                    return True
                if proc.returncode == 1:
                    return False
            except (OSError, subprocess.SubprocessError):
                pass
        name = rel_path.rsplit("/", 1)[-1]
        for pattern in self.patterns:
            if "/" in pattern:
                token = pattern.lstrip("/")
                if rel_path == token or rel_path.startswith(token + "/"):
                    return True
            elif name == pattern or fnmatch.fnmatch(name, pattern):
                return True
        return False


def _sha256(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_HASH_BYTES:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _rule_dir_files(directory: Path, subdir: str) -> list[Path]:
    candidate = directory / subdir
    if not candidate.is_dir():
        return []
    try:
        return sorted((p for p in candidate.rglob("*") if p.is_file()), key=lambda p: str(p).lower())
    except OSError:
        return []


def scan(
    root: Path,
    targets: list[str],
    bridge_locations: list[str],
    tier: str,
    max_files: int,
    deadline_ms: int,
) -> dict[str, object]:
    matcher = IgnoreMatcher(root)
    anchors = _norm_targets(root, targets)
    directories = _search_dirs(root, anchors)
    deadline = time.monotonic() + deadline_ms / 1000.0

    candidates: dict[str, Candidate] = {}
    scanned_files = 0
    truncated = False

    def consider(path: Path, tier_value: str, kind: str, base_distance: int) -> bool:
        nonlocal scanned_files, truncated
        if time.monotonic() > deadline or scanned_files >= max_files:
            truncated = True
            return False
        scanned_files += 1
        try:
            rel = _rel(path, root)
        except ValueError:
            return True
        if matcher.ignored(rel):
            return True
        readable = path.is_file() and os.access(path, os.R_OK)
        distance = base_distance + (0 if path.parent == path.parent.anchor else 0)
        existing = candidates.get(rel)
        if existing is None or base_distance < existing.distance:
            candidates[rel] = Candidate(rel, tier_value, kind, base_distance, readable)
        return True

    for directory in directories:
        if time.monotonic() > deadline:
            truncated = True
            break
        base = _distance(directory, anchors)
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            entries = []
        for entry in entries:
            if not entry.is_file():
                continue
            lower = entry.name.lower()
            if lower in C1_FILES:
                consider(entry, "C1", lower, base)
            elif lower in C2_FILES:
                consider(entry, "C2", lower, base)
        for subdir in C1_RULE_DIRS:
            for path in _rule_dir_files(directory, subdir):
                if not consider(path, "C1", subdir, base + 1):
                    break
        for subdir in C2_RULE_DIRS:
            for path in _rule_dir_files(directory, subdir):
                if not consider(path, "C2", subdir, base + 1):
                    break

    c1: list[dict[str, object]] = []
    c2: list[dict[str, object]] = []
    for candidate in sorted(candidates.values(), key=lambda c: (c.tier, c.distance, c.path)):
        record = candidate.to_dict(_sha256(root / candidate.path) if candidate.readable else None)
        (c1 if candidate.tier == "C1" else c2).append(record)

    # Bridge-declared locations are always surfaced as C1 so the semantic read
    # cannot silently drop them; an unreadable one fails closed.
    unreadable_bridge: list[str] = []
    for location in bridge_locations:
        candidate = Path(location)
        if not candidate.is_absolute():
            candidate = root / location
        try:
            resolved = candidate.resolve()
            rel = _rel(resolved, root)
        except (OSError, ValueError):
            rel = str(candidate)
        readable = candidate.exists() and os.access(candidate, os.R_OK)
        c1.append(
            {
                "path": rel,
                "tier": "C1",
                "kind": "bridge-location",
                "distance": 0,
                "readable": readable,
            }
        )
        if not readable:
            unreadable_bridge.append(rel)
    c1.sort(key=lambda item: (item["distance"], item["path"]))

    status = "scan-unavailable" if unreadable_bridge else "scanned"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not unreadable_bridge,
        "status": status,
        "tier": tier,
        "project_root": str(root),
        "budget": {"max_files": max_files, "deadline_ms": deadline_ms},
        "truncated": truncated,
        "scanned_files": scanned_files,
        "c1": c1,
        "c2": c2,
        **({"unreadable_bridge_locations": sorted(unreadable_bridge)} if unreadable_bridge else {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--bridge-location", action="append", default=[])
    parser.add_argument("--tier", choices=["l0-tripwire", "l1-scan", "l2-study"], default="l1-scan")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--deadline-ms", type=int, default=DEFAULT_DEADLINE_MS)
    args = parser.parse_args(argv)

    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir():
            raise NotADirectoryError(str(root))
    except OSError:
        emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "status": "scan-unavailable",
                "reason": "project-root-unreadable",
            }
        )
        return 2

    try:
        payload = scan(
            root,
            args.target,
            args.bridge_location,
            args.tier,
            args.max_files,
            args.deadline_ms,
        )
        emit(payload)
        return 0 if payload["ok"] else 2
    except Exception as exc:  # fail closed: never silently report "no conventions"
        emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "status": "scan-unavailable",
                "reason": "scanner-error",
                "error": type(exc).__name__,
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
