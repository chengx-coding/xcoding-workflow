#!/usr/bin/env python3
"""Check that a sample project is not derived from prior artifacts.

No runtime coupling: compares file manifests. Exit 1 on unexplained overlap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def manifest(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel.startswith(".xcoding/"):
            continue
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def resolve_prior(value: Path) -> Path:
    """Accept a project root or the canonical <artifact>/project/ archive root."""
    if not value.is_dir():
        raise SystemExit(f"--prior is not a directory: {value}")
    nested = value / "project"
    return nested if nested.is_dir() else value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--prior", required=True, action="append", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not args.seed.is_dir() or not args.project.is_dir():
        raise SystemExit("--seed and --project must be existing directories")
    seed = manifest(args.seed)
    project = manifest(args.project)
    if not seed or not project:
        raise SystemExit("empty seed or project manifest; refusing to pass")

    overlaps: dict[str, list[str]] = {}
    prior_counts: list[int] = []
    for raw in args.prior:
        prior_root = resolve_prior(raw)
        prior = manifest(prior_root)
        if not prior:
            raise SystemExit(f"empty prior manifest: {raw}")
        prior_counts.append(len(prior))
        for path, digest in project.items():
            if path in prior and prior[path] == digest and seed.get(path) != digest:
                overlaps.setdefault(path, []).append(raw.as_posix())

    report = {
        "seed_files": len(seed),
        "project_files": len(project),
        "prior_files": prior_counts,
        "overlap": sorted(overlaps),
        "derived": bool(overlaps),
        "clean": not overlaps,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if not overlaps else 1


if __name__ == "__main__":
    raise SystemExit(main())
