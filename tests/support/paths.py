#!/usr/bin/env python3
"""Single source of truth for test-suite paths.

Every test module derives the repository root from here instead of counting
`Path(__file__).resolve().parents[N]`. Counting parents makes a module's path
semantics depend on its directory depth, which is exactly what blocked the
cluster reorganisation: moving a file silently changed what `ROOT / "src"`
meant.

Importing this module also prepares `sys.path` so that `build_support`,
`support`, `tests.support` and the `xcoding` package all resolve, whether the
caller is `unittest` discovery, the tier runner, or a direct file execution.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _repository_root() -> Path:
    """Locate the repository root by walking up to its marker files.

    Depth-independent on purpose: the suite's own directory layout has changed
    once already, and counting parents from a module's own location is what made
    that change risky. The marker pair is unambiguous in a checkout.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src").is_dir():
            return candidate
    raise RuntimeError(
        "cannot locate the repository root from tests/support/paths.py; "
        "expected an ancestor containing pyproject.toml and src/"
    )


REPO_ROOT = _repository_root()
TESTS_ROOT = REPO_ROOT / "tests"
SRC_ROOT = REPO_ROOT / "src"
SUPPORT_ROOT = TESTS_ROOT / "support"
#: Shared fixtures that do not belong to a single behaviour cluster. Fixtures
#: owned by one cluster live beside it under `tests/<cluster>/fixtures/`.
SHARED_FIXTURES_ROOT = TESTS_ROOT / "fixtures"


def _prepare_path() -> None:
    """Reproduce the `unittest discover` resolution order, idempotently.

    `unittest discover -s tests -t .` puts the top-level directory first and the
    start directory second. Tests import their siblings by bare name (for
    example `workflow_scenario_harness`) and the product by package name, so
    both entries are required. `src` is added because the source tree is the
    product under test in a checkout.
    """
    for entry in (str(SRC_ROOT), str(TESTS_ROOT), str(REPO_ROOT)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


_prepare_path()


def fixture_path(*parts: str) -> Path:
    """Resolve a fixture owned by a cluster or shared between clusters.

    `fixture_path("delegation", "x.json")` prefers
    `tests/delegation/fixtures/x.json` and falls back to the shared
    `tests/fixtures/delegation/x.json`, so a fixture can move with its cluster
    without touching call sites.
    """
    if not parts:
        raise ValueError("fixture_path requires at least a fixture group name")
    cluster_local = TESTS_ROOT.joinpath(parts[0], "fixtures", *parts[1:])
    if cluster_local.exists():
        return cluster_local
    return SHARED_FIXTURES_ROOT.joinpath(*parts)


def test_path(*parts: str) -> Path:
    """Resolve a path under this suite directory."""
    return TESTS_ROOT.joinpath(*parts)


def repo_path(*parts: str) -> Path:
    """Resolve a path under the repository root."""
    return REPO_ROOT.joinpath(*parts)
