#!/usr/bin/env python3
"""Contract tests for the test-suite support layer.

`tests/support/` decides which tests run, where they find the repository, and how
in-process CLI calls report exit codes. If it silently degrades, the suite still
reports success while covering less. These tests make that failure mode fail.

They are deliberately cheap and in-process, so they belong to the `gate` tier:
they are the first thing that should break when the structure drifts.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support import paths, tiers
from tests.support.cli import CliResult, _normalise_exit, run_in_process, run_runtime_in_process


def _json_or_none(result: CliResult) -> dict | None:
    """Parse a payload when the invocation produced one.

    A parse error from `argparse` is reported on stderr as usage text rather than
    as a JSON envelope, so callers must not assume stdout is JSON.
    """
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class PathContractTests(unittest.TestCase):
    """`paths` resolves the repository independently of module depth."""

    def test_repository_root_contains_the_project_markers(self) -> None:
        self.assertTrue((paths.REPO_ROOT / "pyproject.toml").is_file())
        self.assertTrue((paths.SRC_ROOT / "xcoding").is_dir())
        self.assertEqual(paths.TESTS_ROOT, paths.REPO_ROOT / "tests")

    def test_resolution_does_not_count_parents(self) -> None:
        """A support module must not derive the root from its own depth."""
        import ast

        tree = ast.parse(Path(paths.__file__).read_text(encoding="utf-8"))
        offenders = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "parents"
        ]
        self.assertEqual(offenders, [])

    def test_cluster_local_fixture_wins_over_the_shared_directory(self) -> None:
        """`fixture_path` prefers a fixture that moved with its cluster."""
        delegation = paths.fixture_path("delegation")
        self.assertTrue(delegation.is_dir(), delegation)
        self.assertEqual(delegation, paths.TESTS_ROOT / "delegation" / "fixtures")
        self.assertTrue((delegation / "node-packet-v1.json").is_file())

    def test_shared_fixture_group_still_resolves(self) -> None:
        """A fixture owned by more than one cluster stays in the shared root."""
        shared = paths.fixture_path("model_robust_workflow", "scenarios-v1.json")
        self.assertTrue(shared.is_file(), shared)
        self.assertEqual(shared.parent.parent, paths.TESTS_ROOT / "fixtures")

    def test_unknown_fixture_group_resolves_without_raising(self) -> None:
        """An absent group yields the shared path rather than an exception."""
        candidate = paths.fixture_path("absent-group", "x.json")
        self.assertEqual(candidate, paths.TESTS_ROOT / "fixtures" / "absent-group" / "x.json")


class PlanContractTests(unittest.TestCase):
    """The plan stays coherent and the selection rules fail closed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = tiers.load_plan()

    def test_declared_count_matches_discovery(self) -> None:
        """The declared collected count is the guard against duplicate collection."""
        suite = tiers.discover_suite(self.plan)
        collected = len(list(tiers.iter_tests(suite)))
        expected = self.plan.expected_collected_tests
        self.assertIsNotNone(expected, "the plan must declare expected_collected_tests")
        self.assertEqual(collected, expected)

    def test_every_declared_module_file_exists(self) -> None:
        for short in self.plan.all_test_modules():
            with self.subTest(module=short):
                self.assertIsNotNone(self.plan.module_file(short), short)

    def test_every_module_has_exactly_one_cluster(self) -> None:
        for short in self.plan.all_test_modules():
            matches = [
                name for name, body in self.plan.clusters.items() if short in body["modules"]
            ]
            if short in self.plan.kernel_modules:
                matches.append("governance")
            with self.subTest(module=short):
                self.assertEqual(len(matches), 1, f"{short} -> {matches}")

    def test_every_cluster_is_reachable_from_a_rule(self) -> None:
        reachable = set(self.plan.global_clusters)
        for rule in self.plan.selection_rules:
            clusters = rule.get("clusters", [])
            if tiers.ALL_CLUSTERS_SENTINEL in clusters:
                reachable.update(self.plan.clusters)
            else:
                reachable.update(clusters)
        self.assertEqual(sorted(set(self.plan.clusters) - reachable), [])

    def test_unmatched_path_escalates_to_every_cluster(self) -> None:
        """An unknown path must escalate the tier, never silently select nothing.

        `clusters_for_paths` reports the unmatched path and adds only the global
        clusters; `tier_roots` is what turns an unmatched path into the full
        cluster set. Both halves are asserted so neither can regress silently.
        """
        clusters, unmatched = tiers.clusters_for_paths(
            self.plan, ["some/unknown/location.txt"]
        )
        self.assertEqual(unmatched, ["some/unknown/location.txt"])
        self.assertEqual(sorted(clusters), sorted(self.plan.global_clusters))
        resolution = tiers.tier_roots(
            self.plan, "focused", ["some/unknown/location.txt"]
        )
        self.assertEqual(sorted(resolution["clusters"]), sorted(self.plan.clusters))
        self.assertEqual(resolution["escalated"], ["some/unknown/location.txt"])

    def test_longest_prefix_wins(self) -> None:
        """A specific rule beats a general one regardless of declaration order."""
        clusters, unmatched = tiers.clusters_for_paths(
            self.plan, ["src/xcoding/runtime/core.py"]
        )
        self.assertEqual(unmatched, [])
        self.assertIn("runtime", clusters)
        # The generic `src/xcoding/` rule does not select the daemon or viewer
        # clusters, so specificity is observable even though it does name the
        # runtime cluster.
        generic, _ = tiers.clusters_for_paths(self.plan, ["src/xcoding/version.py"])
        self.assertNotIn("daemon", generic)
        self.assertNotIn("viewer", generic)
        self.assertIn("packaging", generic)

    def test_representative_path_per_cluster(self) -> None:
        representatives = {
            "runtime": "src/xcoding/runtime/core.py",
            "governance": "skills/xc-analysis/SKILL.md",
            "change_report": "skills/xc-change-report/scripts/build_manifest.py",
            "documents": "skills/xc-document/scripts/validate_document.py",
            "packaging": "pyproject.toml",
            "daemon": "src/xcoding/daemon/server.py",
            "viewer": "src/xcoding/viewer/server.py",
            "delegation": "src/xcoding/delegation/gateway.py",
        }
        for cluster, path in representatives.items():
            with self.subTest(cluster=cluster):
                clusters, unmatched = tiers.clusters_for_paths(self.plan, [path])
                self.assertEqual(unmatched, [])
                self.assertIn(cluster, clusters)

    def test_gate_tier_is_a_strict_subset_of_full(self) -> None:
        suite = tiers.discover_suite(self.plan)
        gate = tiers.select_for_tier(self.plan, "gate", suite)
        full = tiers.select_for_tier(self.plan, "full", suite)
        self.assertTrue(set(gate.included) <= set(full.included) | set(full.excluded))

    def test_release_tier_includes_release_only_tests(self) -> None:
        suite = tiers.discover_suite(self.plan)
        full = tiers.select_for_tier(self.plan, "full", suite)
        release = tiers.select_for_tier(self.plan, "release", suite)
        release_only = set(self.plan.release_only.get("modules", []))
        full_modules = {tiers.module_of(item).rsplit(".", 1)[-1] for item in full.included}
        release_modules = {tiers.module_of(item).rsplit(".", 1)[-1] for item in release.included}
        for module in release_only:
            with self.subTest(module=module):
                self.assertNotIn(module, full_modules)
                self.assertIn(module, release_modules)

    def test_default_worker_count_respects_the_bound(self) -> None:
        workers = tiers.default_workers()
        body = self.plan.raw["worker_default"]
        self.assertGreaterEqual(workers, int(body["floor"]))
        self.assertLessEqual(workers, int(body["ceiling"]))


class InProcessCliContractTests(unittest.TestCase):
    """The in-process CLI form preserves what tests assert on."""

    def test_exit_code_normalisation_covers_every_systemexit_shape(self) -> None:
        self.assertEqual(_normalise_exit(None), 0)
        self.assertEqual(_normalise_exit(0), 0)
        self.assertEqual(_normalise_exit(2), 2)
        self.assertEqual(_normalise_exit("2"), 2)
        self.assertEqual(_normalise_exit(""), 0)
        self.assertEqual(_normalise_exit("boom"), 1)

    def test_runtime_help_raises_systemexit_and_is_normalised(self) -> None:
        """`argparse` raises on the help path; the wrapper must not swallow it."""
        result = run_runtime_in_process(["--help"])
        self.assertIsInstance(result, CliResult)
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", (result.stdout + result.stderr).lower())

    def test_unknown_subcommand_reports_an_input_error(self) -> None:
        result = run_runtime_in_process(["definitely-not-a-command"])
        self.assertNotEqual(result.returncode, 0)
        payload = _json_or_none(result)
        if payload is not None:
            self.assertFalse(payload["ok"])

    def test_missing_required_argument_reports_an_input_error(self) -> None:
        result = run_in_process(["runtime", "init"])
        self.assertNotEqual(result.returncode, 0)
        payload = _json_or_none(result)
        if payload is not None:
            self.assertFalse(payload["ok"])

    def test_streams_are_captured_separately(self) -> None:
        """In-process calls must not leak to the real stdout."""
        import contextlib
        import io

        outer = io.StringIO()
        with contextlib.redirect_stdout(outer):
            run_runtime_in_process(["--help"])
        self.assertEqual(outer.getvalue(), "")

    def test_in_process_exit_code_matches_a_real_process(self) -> None:
        """The parity assertion the design requires for every converted cluster."""
        from tests.support.cli import run_subprocess

        arguments = ["definitely-not-a-command"]
        in_process = run_runtime_in_process(arguments)
        subprocess_result = run_subprocess(arguments)
        self.assertEqual(in_process.returncode, subprocess_result.returncode)
        in_payload = _json_or_none(in_process)
        sub_payload = _json_or_none(subprocess_result)
        if in_payload is not None and sub_payload is not None:
            self.assertEqual(
                in_payload["error"]["code"], sub_payload["error"]["code"]
            )
        else:
            # A usage error is reported on stderr by both forms.
            self.assertTrue(in_process.output.strip())
            self.assertTrue(subprocess_result.output.strip())


if __name__ == "__main__":
    unittest.main()
