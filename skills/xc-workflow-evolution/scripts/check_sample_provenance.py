#!/usr/bin/env python3
"""Check that a sample project is not derived from prior artifacts.

Exit codes: 0 clean, 1 derived overlap, 2 input error.
No runtime coupling: compares file manifests.
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
        raise ValueError(f"--prior is not a directory: {value}")
    nested = value / "project"
    if nested.is_dir():
        return nested
    if (value / "metadata.json").exists():
        raise ValueError(f"archive root has metadata.json but no project/: {value}")
    return value


def write_report(out: Path, report: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    # Clear a stale report before argparse can fail; a missing/error record must not leave clean.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--out", type=Path)
    pre_args, _ = pre.parse_known_args()
    if pre_args.out and pre_args.out.exists():
        pre_args.out.unlink()

    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--prior", action="append", type=Path, default=[])
    parser.add_argument("--no-prior", action="store_true", help="first sample; no prior artifact exists")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.out.exists():
        args.out.unlink()
    try:
        if not args.seed.is_dir() or not args.project.is_dir():
            raise ValueError("--seed and --project must be existing directories")
        if args.prior and args.no_prior:
            raise ValueError("use either --prior or --no-prior, not both")
        if not args.prior and not args.no_prior:
            raise ValueError("missing prior evidence: pass --prior or --no-prior")
        seed = manifest(args.seed)
        project = manifest(args.project)
        if not seed or not project:
            raise ValueError("empty seed or project manifest; refusing to pass")

        overlaps: dict[str, list[str]] = {}
        prior_counts: list[int] = []
        for raw in args.prior:
            prior_root = resolve_prior(raw)
            prior = manifest(prior_root)
            if not prior:
                raise ValueError(f"empty prior manifest: {raw}")
            prior_counts.append(len(prior))
            for path, digest in project.items():
                if path in prior and prior[path] == digest and seed.get(path) != digest:
                    overlaps.setdefault(path, []).append(raw.as_posix())
    except ValueError as exc:
        write_report(args.out, {"status": "error", "error": str(exc), "clean": False, "derived": False})
        print(f"error: {exc}")
        return 2

    status = "derived" if overlaps else "clean"
    report = {
        "status": status,
        "seed_files": len(seed),
        "project_files": len(project),
        "prior_files": prior_counts,
        "no_prior": args.no_prior,
        "overlap": sorted(overlaps),
        "derived": bool(overlaps),
        "clean": not overlaps,
    }
    write_report(args.out, report)
    print(json.dumps(report))
    return 1 if overlaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
