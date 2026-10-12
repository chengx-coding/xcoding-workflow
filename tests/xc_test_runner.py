#!/usr/bin/env python3
"""Tiered, parallel runner for the xcoding-workflow test suite.

Discovery happens once in this process; the tier decides what is included; the
selection is sharded by module across worker processes. The selection is printed
before anything runs, so "what was not run" is visible rather than inferred.

Usage:
    python tests/xc_test_runner.py --tier gate
    python tests/xc_test_runner.py --tier focused --changed src/xcoding/runtime/core.py
    python tests/xc_test_runner.py --tier full --workers 4
    python tests/xc_test_runner.py --tier focused --explain
    python tests/xc_test_runner.py --tier full --serial
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for entry in (str(REPO_ROOT / "src"), str(REPO_ROOT / "tests"), str(REPO_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from tests.support import tiers  # noqa: E402


def short_module(identity: str, plan: tiers.Plan) -> str:
    return tiers.module_of(identity).rsplit(".", 1)[-1]


def shard_by_module(identities: list[str], plan: tiers.Plan, workers: int) -> list[list[str]]:
    """Greedy longest-processing-time sharding at module granularity.

    Modules are indivisible: a worker imports a module once and runs all of its
    selected tests. Weights come from the plan's measured per-module baseline,
    because the spread between modules is two orders of magnitude and a static
    per-cluster average leaves one worker as the straggler.
    """
    modules: dict[str, list[str]] = {}
    for identity in identities:
        modules.setdefault(short_module(identity, plan), []).append(identity)

    weights = plan.module_weights
    fallback = 5.0
    estimates: dict[str, float] = {}
    for name, ids in modules.items():
        # Price only what will actually run, using the measured per-module
        # baseline and the measured collected count for that module.
        total = float(weights.get(name, fallback))
        declared = plan.test_count_for_module(name)
        if declared:
            estimates[name] = total * len(ids) / declared
        else:
            estimates[name] = total if len(ids) == len(modules[name]) else fallback

    ordered = sorted(modules, key=lambda name: -estimates.get(name, fallback))
    shards: list[list[str]] = [[] for _ in range(max(1, workers))]
    load = [0.0] * len(shards)
    for name in ordered:
        index = load.index(min(load))
        shards[index].extend(modules[name])
        load[index] += estimates.get(name, fallback)
    return [shard for shard in shards if shard]


def _concurrency(results: list[dict], origin: float) -> dict:
    """Measure real worker overlap over the run window.

    The average number of workers executing at any instant is the honest measure
    of whether parallelism is delivering. Sum-of-walls equal to elapsed time
    means the workers never overlapped.
    """
    events: list[tuple[float, int]] = []
    for result in results:
        events.append((result["started_at"] - origin, 1))
        events.append((result["finished_at"] - origin, -1))
    events.sort()
    active = 0
    previous = 0.0
    area = 0.0
    peak = 0
    for moment, delta in events:
        area += active * max(0.0, moment - previous)
        previous = moment
        active += delta
        peak = max(peak, active)
    elapsed = max((result["finished_at"] for result in results), default=origin) - origin
    return {
        "elapsed_seconds": round(elapsed, 2),
        "sum_worker_walls": round(sum(result["wall_seconds"] for result in results), 2),
        "average_active_workers": round(area / elapsed, 2) if elapsed else 0.0,
        "peak_active_workers": peak,
    }


def launch_shard(shard: list[str], plan: tiers.Plan, workdir: Path, index: int) -> dict:
    """Write the shard file and start its worker without waiting.

    Launching and waiting in the same call would serialise the whole run: the
    first `wait` would block before the next worker ever started. Every shard is
    launched first, then all of them are awaited.
    """
    selection_path = workdir / f"shard-{index:02d}.json"
    report_path = workdir / f"report-{index:02d}.json"
    modules = sorted({short_module(identity, plan) for identity in shard})
    selection_path.write_text(
        json.dumps({"tests": sorted(shard), "modules": modules}), encoding="utf-8"
    )
    command = [
        sys.executable, "-m", "tests.support.worker",
        "--selection", str(selection_path),
        "--report", str(report_path),
    ]
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "index": index,
        "modules": modules,
        "process": process,
        "report_path": report_path,
        "started_at": started,
        "deadline": started + 0.0,
    }


def collect_shard(slot: dict, timeout: float) -> dict:
    """Await one launched worker and read its report."""
    process = slot["process"]
    started = slot["started_at"]
    try:
        code = process.wait(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        code = -1
        timed_out = True
    finished = time.perf_counter()
    payload: dict = {}
    report_path: Path = slot["report_path"]
    if report_path.is_file():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "index": slot["index"],
        "modules": slot["modules"],
        "exit_code": code,
        "timed_out": timed_out,
        "wall_seconds": round(finished - started, 3),
        "report": payload,
        "started_at": started,
        "finished_at": finished,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", required=True, choices=list(tiers.TIER_ORDER))
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--changed", action="append", default=None,
                        help="Repository-relative changed path; repeatable. Defaults to git diff against HEAD.")
    parser.add_argument("--serial", action="store_true", help="Force one worker.")
    parser.add_argument("--explain", action="store_true", help="Print the selection and exit.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary.")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Per-worker timeout in seconds.")
    parser.add_argument("--keep", action="store_true", help="Keep worker reports for inspection.")
    args = parser.parse_args()

    plan = tiers.load_plan()
    suite = tiers.discover_suite(plan)
    selection = tiers.select_for_tier(plan, args.tier, suite, args.changed)

    resolved = tiers.tier_roots(plan, args.tier, args.changed)
    selected_clusters = sorted(resolved["clusters"])
    all_clusters = sorted(plan.clusters)
    excluded_clusters = sorted(set(all_clusters) - set(selected_clusters))

    if args.explain:
        print(json.dumps(
            {
                "tier": args.tier,
                "reason": selection.reason,
                "selected_clusters": selected_clusters,
                "excluded_clusters": excluded_clusters,
                "escalated_paths": selection.escalated,
                "included_tests": selection.included_count,
                "excluded_tests": len(selection.excluded),
            },
            indent=2,
        ))
        return 0

    if not selection.included:
        payload = {
            "ok": False,
            "error": "tier selected no tests",
            "tier": args.tier,
            "reason": selection.reason,
            "selected_clusters": selected_clusters,
        }
        print(json.dumps(payload, indent=2) if args.json else f"ERROR: {payload['error']}")
        return 2

    workers = 1 if args.serial else (args.workers or tiers.default_workers())
    # Do not start more workers than there are tests to run: a process that
    # imports a module to execute one test pays full import cost for nothing.
    workers = max(1, min(workers, len(selection.included)))
    shards = shard_by_module(selection.included, plan, workers)

    if not args.json:
        print(f"tier={args.tier} workers={len(shards)} tests={selection.included_count}")
        print(f"  reason: {selection.reason}")
        print(f"  clusters selected: {', '.join(selected_clusters) or '(none)'}")
        print(f"  clusters excluded: {', '.join(excluded_clusters) or '(none)'}")
        if selection.escalated:
            print(f"  ESCALATED to every cluster; unmatched paths: {', '.join(selection.escalated)}")

    workdir = Path(tempfile.mkdtemp(prefix="xc-tier-run-"))
    started = time.perf_counter()
    try:
        # Launch every shard first so they overlap, then await them.
        slots = [
            launch_shard(shard, plan, workdir, index)
            for index, shard in enumerate(shards)
        ]
        results = [collect_shard(slot, args.timeout) for slot in slots]
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
    wall = time.perf_counter() - started

    records: list[dict] = []
    load_errors: list[str] = []
    worker_problems: list[str] = []
    for result in results:
        body = result.get("report") or {}
        records.extend(body.get("records", []))
        load_errors.extend(body.get("load_errors", []))
        if result["timed_out"]:
            worker_problems.append(f"worker {result['index']} timed out after {args.timeout}s")
        elif result["exit_code"] != 0:
            worker_problems.append(
                f"worker {result['index']} exited {result['exit_code']} without runnable tests"
            )
        elif not body:
            worker_problems.append(f"worker {result['index']} produced no report")

    by_outcome: dict[str, int] = {}
    for record in records:
        by_outcome[record["outcome"]] = by_outcome.get(record["outcome"], 0) + 1
    failed = [r for r in records if r["outcome"] in ("fail", "error")]

    summary = {
        "schema_version": 1,
        "ok": not failed and not load_errors and not worker_problems,
        "tier": args.tier,
        "workers": len(shards),
        "wall_seconds": round(wall, 3),
        "selected_clusters": selected_clusters,
        "excluded_clusters": excluded_clusters,
        "escalated_paths": selection.escalated,
        "selected_tests": selection.included_count,
        "executed_tests": len(records),
        "outcomes": by_outcome,
        "load_errors": load_errors,
        "worker_problems": worker_problems,
        "failed": [
            {"identity": r["identity"], "outcome": r["outcome"], "detail": r["detail"]}
            for r in failed
        ],
        "slowest": sorted(records, key=lambda r: -(r["seconds"] or 0))[:15],
        "worker_walls": [r["wall_seconds"] for r in results],
        "worker_exit_codes": [r["exit_code"] for r in results],
        "worker_modules": [r["modules"] for r in results],
        "worker_windows": [
            [round(r["started_at"] - started, 2), round(r["finished_at"] - started, 2)]
            for r in results
        ],
        "concurrency": _concurrency(results, started),
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"executed={summary['executed_tests']} wall={summary['wall_seconds']}s "
            f"outcomes={by_outcome}"
        )
        for worker in summary["slowest"][:10]:
            print(f"  {worker['seconds']:8.2f}s  {worker['identity']}")
        for problem in summary["load_errors"]:
            print(f"  LOAD ERROR: {problem}")
        for problem in summary["failed"]:
            print(f"  {problem['outcome'].upper()}: {problem['identity']}")
            print(f"    {problem['detail'].splitlines()[-1] if problem['detail'] else ''}")
        print("OK" if summary["ok"] else "FAILED")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
