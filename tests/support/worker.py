#!/usr/bin/env python3
"""Isolated worker used by the tier runner.

Runs one shard of already-selected tests in its own interpreter and writes a
JSON report. The shard is passed by file through `--selection`, and the report
is written by file, so the parent can start this process with non-piped stdio.
That matters on this platform: the console-script shim splits multi-word
arguments, and buffered pipes hide progress until exit.

Usage:
    python -m tests.support.worker --selection shard.json --report report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (str(REPO_ROOT / "src"), str(REPO_ROOT / "tests"), str(REPO_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from tests.support import tiers  # noqa: E402


def short_module(identity: str) -> str:
    parts = identity.split(".")
    return parts[-3] if len(parts) >= 3 else ""


class CollectingResult(unittest.TextTestResult):
    """Record a duration and an outcome for every executed test."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.records: dict[str, dict] = {}

    def _slot(self, test) -> dict:
        identity = test.id()
        slot = self.records.get(identity)
        if slot is None:
            slot = {"identity": identity, "seconds": None, "outcome": "ok", "detail": ""}
            self.records[identity] = slot
        return slot

    def startTest(self, test) -> None:  # noqa: N802
        self._slot(test)
        super().startTest(test)

    def addDuration(self, test, elapsed) -> None:  # noqa: N802
        self._slot(test)["seconds"] = round(float(elapsed), 6)

    def addError(self, test, err) -> None:  # noqa: N802
        if not isinstance(err[1], unittest.SkipTest):
            self._slot(test)["outcome"] = "error"
            self._slot(test)["detail"] = self._exc_info_to_string(err, test)[-2000:]
        super().addError(test, err)

    def addFailure(self, test, err) -> None:  # noqa: N802
        self._slot(test)["outcome"] = "fail"
        self._slot(test)["detail"] = self._exc_info_to_string(err, test)[-2000:]
        super().addFailure(test, err)

    def addSkip(self, test, reason) -> None:  # noqa: N802
        self._slot(test)["outcome"] = "skip"
        self._slot(test)["detail"] = reason
        super().addSkip(test, reason)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    shard = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    plan = tiers.load_plan()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    errors: list[str] = []
    # Load each selected test by its exact identity. Loading whole modules would
    # run tests the tier deliberately excluded, which would defeat the tiering.
    for identity in shard["tests"]:
        try:
            suite.addTests(loader.loadTestsFromName(identity))
        except Exception as error:  # noqa: BLE001 - report, never abort the shard
            errors.append(f"{identity}: {type(error).__name__}: {error}")
    for short_name in shard.get("module_errors", []):
        errors.append(f"module not loadable: {short_name}")

    runner = unittest.TextTestRunner(verbosity=0, resultclass=CollectingResult)
    started = time.perf_counter()
    result = runner.run(suite)
    wall = time.perf_counter() - started

    report = {
        "modules": sorted({short_module(identity) for identity in shard["tests"]}),
        "pid": os.getpid(),
        "wall_seconds": round(wall, 3),
        "tests_run": result.testsRun,
        "load_errors": errors,
        "failures": [str(case) for case, _ in result.failures],
        "errors": [str(case) for case, _ in result.errors],
        "skipped": [str(case) for case, _ in result.skipped],
        "expected_failures": [str(case) for case, _ in result.expectedFailures],
        "unexpected_successes": [str(case) for case in result.unexpectedSuccesses],
        "records": sorted(result.records.values(), key=lambda item: item["identity"]),
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    # The report is the authoritative result; the caller aggregates outcomes from
    # it. A non-zero exit here means "the shard could not be run", not "a test
    # failed", so a test failure never depends on how the interpreter exited.
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
