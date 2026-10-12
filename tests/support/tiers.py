#!/usr/bin/env python3
"""Tier and selection resolution — the only implementation of the rules.

Both the tier runner and the manifest checker import this module, so the
selection rules exist in exactly one place. The manifest
(`tests/xc_test_plan.json`) is data; this module is the behaviour.
"""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from tests.support.paths import REPO_ROOT, SUPPORT_ROOT, TESTS_ROOT


MANIFEST_PATH = TESTS_ROOT / "xc_test_plan.json"

TIER_ORDER = ("gate", "focused", "full", "release")
ALL_CLUSTERS_SENTINEL = "__all__"


class PlanError(RuntimeError):
    """The manifest is missing, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class Plan:
    """Parsed manifest."""

    raw: dict
    path: Path

    @property
    def clusters(self) -> dict[str, dict]:
        return self.raw["clusters"]

    @property
    def kernel_modules(self) -> list[str]:
        return list(self.raw.get("kernel_modules", []))

    @property
    def resources(self) -> list[str]:
        return list(self.raw.get("resources", []))

    @property
    def frozen_paths(self) -> list[str]:
        return list(self.raw.get("frozen_paths", []))

    @property
    def coupled_modules(self) -> dict[str, dict]:
        return self.raw.get("coupled_modules", {})

    @property
    def selection_rules(self) -> list[dict]:
        return self.raw["selection_rules"]

    @property
    def global_clusters(self) -> list[str]:
        return list(self.raw.get("global_clusters", []))

    @property
    def tiers(self) -> dict[str, dict]:
        return self.raw["tiers"]

    @property
    def release_only(self) -> dict:
        return self.raw.get("release_only", {})

    @property
    def module_weights(self) -> dict[str, float]:
        """Measured per-module baseline seconds, used as the sharding model."""
        return {
            name: float(value)
            for name, value in (self.raw.get("module_weights_seconds") or {}).items()
        }

    def test_count_for_module(self, short_name: str) -> int:
        """Measured collected test count for a module, from the baseline profile."""
        counts = self.raw.get("module_test_counts") or {}
        if short_name in counts:
            return int(counts[short_name])
        return 0

    @property
    def expected_collected_tests(self) -> int | None:
        """The declared collected test count, or None when the plan omits it."""
        value = self.raw.get("expected_collected_tests")
        return int(value) if isinstance(value, int) else None

    def cluster_of_module(self, short_name: str) -> str:
        """Return the cluster owning a module, by short module name."""
        for name, body in self.clusters.items():
            if short_name in body["modules"]:
                return name
        if short_name in self.kernel_modules:
            # The frozen governance module belongs to the governance cluster
            # even though it lives at the tests root.
            return "governance"
        if short_name in self.resources:
            return "kernel"
        raise PlanError(f"module has no cluster in the plan: {short_name}")

    def directory_of_cluster(self, cluster: str) -> Path:
        return REPO_ROOT / self.clusters[cluster]["directory"]

    def module_file(self, short_name: str) -> Path | None:
        """Locate a module's file, or return None when it does not exist.

        Resolution order matches `dotted_name` so the plan, the runner and the
        checker always agree on where a module lives. A kernel module may sit at
        the tests root (the frozen governance module) or beside the support
        modules it covers.
        """
        if short_name in self.kernel_modules or short_name in self.resources:
            root_path = TESTS_ROOT / f"{short_name}.py"
            if root_path.is_file():
                return root_path
        for body in self.clusters.values():
            if short_name in body["modules"]:
                path = REPO_ROOT / body["directory"] / f"{short_name}.py"
                return path if path.is_file() else None
        support_path = SUPPORT_ROOT / f"{short_name}.py"
        if support_path.is_file():
            return support_path
        return None

    def dotted_name(self, short_name: str) -> str:
        """Return the dotted import name of a module under the tests package."""
        if short_name in self.kernel_modules or short_name in self.resources:
            path = TESTS_ROOT / f"{short_name}.py"
            if path.is_file():
                return f"tests.{short_name}"
        for body in self.clusters.values():
            if short_name in body["modules"]:
                relative = Path(body["directory"]).relative_to("tests")
                # `tests/support` style directories become dotted subpackages.
                parts = relative.parts
                prefix = ".".join(parts)
                return f"tests.{prefix}.{short_name}" if prefix else f"tests.{short_name}"
        if (SUPPORT_ROOT / f"{short_name}.py").is_file():
            return f"tests.support.{short_name}"
        raise PlanError(f"module has no import location in the plan: {short_name}")

    def all_test_modules(self) -> list[str]:
        """Every module that contains tests, in a deterministic order."""
        names: list[str] = []
        for cluster in sorted(self.clusters):
            names.extend(self.clusters[cluster]["modules"])
        names.extend(sorted(self.kernel_modules))
        return sorted(names)


def load_plan(path: Path | None = None) -> Plan:
    resolved = Path(path) if path is not None else MANIFEST_PATH
    if not resolved.is_file():
        raise PlanError(f"test plan not found: {resolved}")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PlanError(f"test plan is not valid JSON: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise PlanError("test plan must be an object with schema_version 1")
    for required in ("clusters", "tiers", "selection_rules"):
        if required not in raw:
            raise PlanError(f"test plan is missing required key: {required}")
    return Plan(raw=raw, path=resolved)


# --------------------------------------------------------------------------
# Selection rules
# --------------------------------------------------------------------------


def clusters_for_paths(plan: Plan, changed: Sequence[str]) -> tuple[set[str], list[str]]:
    """Resolve changed repository-relative paths to clusters.

    Returns the cluster set and the list of paths that matched no rule (which
    the caller must treat as a fail-closed escalation to the full tier).

    Longest matching prefix wins, so a specific rule beats a general one
    regardless of declaration order.
    """
    selected: set[str] = set(plan.global_clusters)
    unmatched: list[str] = []
    rules = sorted(
        plan.selection_rules,
        key=lambda rule: len(str(rule.get("prefix", ""))),
        reverse=True,
    )
    for raw_path in changed:
        normalised = str(raw_path).replace("\\", "/").lstrip("./")
        for rule in rules:
            prefix = str(rule.get("prefix", ""))
            if normalised == prefix or normalised.startswith(prefix):
                clusters = list(rule.get("clusters", []))
                if ALL_CLUSTERS_SENTINEL in clusters:
                    selected.update(plan.clusters)
                else:
                    selected.update(clusters)
                break
        else:
            unmatched.append(normalised)
    return selected, unmatched


def changed_paths_from_git(base: str = "HEAD") -> list[str]:
    """Return repository-relative paths changed against a Git revision."""
    import subprocess

    completed = subprocess.run(
        ["git", "diff", "--name-only", base],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise PlanError(f"git diff failed for {base}: {completed.stderr.strip()}")
    paths = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return paths


def tier_roots(plan: Plan, tier: str, changed: Sequence[str] | None = None) -> dict:
    """Resolve a tier into the clusters and module filters to execute.

    The return value is a description object rather than a test suite so the
    caller can print exactly what was included and excluded.
    """
    if tier not in plan.tiers:
        raise PlanError(f"unknown tier: {tier}")

    if tier == "gate":
        clusters: set[str] = set()
        return {
            "tier": tier,
            "clusters": clusters,
            "modules": [],
            "gate_only": True,
            "release_only": False,
            "escalated": [],
            "reason": "gate tier selects the declared guard and cheap in-process tests only",
        }

    if tier == "focused":
        if changed is None:
            changed = changed_paths_from_git()
        clusters, unmatched = clusters_for_paths(plan, changed)
        escalated = False
        if unmatched:
            clusters = set(plan.clusters)
            escalated = True
        return {
            "tier": tier,
            "clusters": clusters,
            "modules": [],
            "gate_only": False,
            "release_only": False,
            "escalated": unmatched,
            "changed": list(changed),
            "reason": (
                "changed paths matched no rule, so the selection escalated to every cluster"
                if escalated
                else "gate plus the clusters selected by the changed paths"
            ),
        }

    if tier == "full":
        return {
            "tier": tier,
            "clusters": set(plan.clusters),
            "modules": [],
            "gate_only": False,
            "release_only": False,
            "escalated": [],
            "reason": "every cluster",
        }

    if tier == "release":
        return {
            "tier": tier,
            "clusters": set(plan.clusters),
            "modules": [],
            "gate_only": False,
            "release_only": True,
            "escalated": [],
            "reason": "every cluster plus the release-only tests",
        }

    raise PlanError(f"unhandled tier: {tier}")


# --------------------------------------------------------------------------
# Test identity helpers
# --------------------------------------------------------------------------


@dataclass
class Selection:
    """A resolved, printable selection of tests."""

    tier: str
    included: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    escalated: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def included_count(self) -> int:
        return len(self.included)


def _matches(identity: str, dotted_module: str, selector: str) -> bool:
    if selector == dotted_module:
        return True
    return identity == selector or identity.startswith(selector + ".")


def select_for_tier(
    plan: Plan,
    tier: str,
    suite: unittest.TestSuite,
    changed: Sequence[str] | None = None,
) -> Selection:
    """Filter a fully discovered suite down to one tier.

    Discovery happens once over the whole package; this function decides what
    belongs to the tier. Keeping discovery and selection separate is what makes
    "the manifest covers every collected test" checkable.
    """
    resolution = tier_roots(plan, tier, changed)
    gate_tier = plan.tiers["gate"]
    gate_selectors: list[str] = []
    release_selectors: list[str] = []
    for entry in gate_tier["selection"]:
        value = entry["value"]
        gate_selectors.extend(value if isinstance(value, list) else [value])
    release_only = plan.release_only
    release_modules = set(release_only.get("modules", []))
    release_selectors.extend(release_only.get("tests", []))

    included: list[str] = []
    excluded: list[str] = []

    for test in iter_tests(suite):
        identity = test.id()
        dotted = module_of(identity)
        short = dotted.rsplit(".", 1)[-1]
        try:
            cluster = plan.cluster_of_module(short)
        except PlanError:
            cluster = ""
        in_gate = any(_matches(identity, dotted, selector) for selector in gate_selectors)
        is_release_only = short in release_modules or any(
            _matches(identity, dotted, selector) for selector in release_selectors
        )

        keep = False
        if tier == "gate":
            keep = in_gate
        elif tier == "focused":
            keep = in_gate or cluster in resolution["clusters"]
        elif tier == "full":
            keep = not is_release_only
        elif tier == "release":
            keep = True

        (included if keep else excluded).append(identity)

    return Selection(
        tier=tier,
        included=included,
        excluded=excluded,
        escalated=resolution.get("escalated", []),
        reason=resolution.get("reason", ""),
    )


def module_of(identity: str) -> str:
    """Return the dotted module of a test identity.

    Identities end with `.ClassName.method_name`, so stripping two components is
    exact and independent of how deep the module lives under `tests/`.
    """
    parts = identity.split(".")
    return ".".join(parts[:-2]) if len(parts) >= 3 else ""


def iter_tests(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def discover_suite(plan: Plan, pattern: str = "test_*.py") -> unittest.TestSuite:
    """Discover every test in the suite, once."""
    loader = unittest.TestLoader()
    return loader.discover(
        start_dir=str(TESTS_ROOT),
        pattern=pattern,
        top_level_dir=str(REPO_ROOT),
    )


def default_workers() -> int:
    """Worker count derived from the manifest's measured basis."""
    plan = load_plan()
    body = plan.raw.get("worker_default", {})
    ceiling = int(body.get("ceiling", 4))
    floor = int(body.get("floor", 2))
    return max(floor, min(ceiling, (os.cpu_count() or 4) // 4))
