#!/usr/bin/env python3
"""CLI invocation helpers for tests.

Two forms are deliberate:

- `run_in_process` calls the product's `main()` inside this interpreter. It
  removes the ~0.15 s interpreter start that dominates a suite built on
  subprocesses, and it is the default for tests that only assert on the exit
  code and the JSON payload.
- `run_subprocess` starts a real process. It is required for behaviour that
  cannot be reproduced in-process: forced process death, signals, a background
  launch and readiness handoff, a bare interpreter without `site`, a real
  listening socket, and the shape of the two output streams.

`run_in_process` normalises `SystemExit`, because `argparse` raises it on the
help and parse-error paths instead of returning a code. A broad `except` around
the call would turn a non-zero exit into a pass, so the exit code is always
normalised explicitly and returned as an integer.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tests.support.paths import REPO_ROOT, SRC_ROOT, TESTS_ROOT


@dataclass(frozen=True)
class CliResult:
    """The observable result of one CLI invocation."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout if self.stdout.strip() else self.stderr

    def json(self) -> object:
        import json

        return json.loads(self.stdout)


def _normalise_exit(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    if isinstance(code, str):
        stripped = code.strip()
        try:
            return int(stripped)
        except ValueError:
            return 1 if stripped else 0
    return 1


def runtime_arguments(arguments: list[str]) -> list[str]:
    """Return the `xcoding` argument vector that runs the runtime subcommand."""
    return ["runtime", *arguments]


def run_in_process(arguments: list[str]) -> CliResult:
    """Run `xcoding` in this interpreter and capture both streams."""
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    from xcoding.cli import main as cli_main  # imported late on purpose

    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_main(list(arguments))
    except SystemExit as error:  # argparse and explicit exits
        code = _normalise_exit(error.code)
    except BaseException as error:  # noqa: BLE001 - surface, do not swallow
        stderr.write(f"{type(error).__name__}: {error}\n")
        raise
    return CliResult(returncode=_normalise_exit(code), stdout=stdout.getvalue(), stderr=stderr.getvalue())


def run_runtime_in_process(arguments: list[str]) -> CliResult:
    """Run the runtime subcommand in-process."""
    return run_in_process(runtime_arguments(arguments))


def run_subprocess(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    timeout: float | None = None,
) -> CliResult:
    """Run the runtime source entry in a real interpreter process."""
    completed = subprocess.run(
        [sys.executable, str(TESTS_ROOT / "runtime_cli.py"), *arguments],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
        timeout=timeout,
    )
    return CliResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
