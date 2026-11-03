#!/usr/bin/env python3
"""Check that a sample project is not derived from a prior artifact.

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--prior", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    seed = manifest(args.seed)
    project = manifest(args.project)
    prior = manifest(args.prior)
    overlap = {
        path: digest
        for path, digest in project.items()
        if path in prior and prior[path] == digest and seed.get(path) != digest
    }
    report = {
        "seed_files": len(seed),
        "project_files": len(project),
        "prior_files": len(prior),
        "overlap": sorted(overlap),
        "clean": not overlap,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if not overlap else 1


if __name__ == "__main__":
    raise SystemExit(main())
