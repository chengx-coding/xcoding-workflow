from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CLI = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
GOVERNANCE_STATS = (
    REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "governance_stats.py"
)
MINIMAL_TEMPLATE = (
    REPOSITORY_ROOT
    / "src"
    / "xcoding"
    / "runtime"
    / "assets"
    / "minimal-template.xml"
)
CONFIG_OVERRIDE = {"schema_version": 1, "git": {"auto_commit": False}}


class GovernanceStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.scratch = Path(self._temporary.name)
        config = self.scratch / "runtime-config.json"
        config.write_text(json.dumps(CONFIG_OVERRIDE), encoding="utf-8")
        self.config_path = str(config)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def run_cli(self, *args: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_CLI), *args],
            cwd=self.scratch,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def tree_path(self, name: str) -> Path:
        return self.scratch / name / "runtime" / "orchestration.xml"

    def tree_argument(self, name: str) -> str:
        return str(self.tree_path(name))

    def init_tree(self, name: str) -> Path:
        self.run_cli(
            "init",
            "--runtime-path",
            str(self.scratch / name / "runtime"),
            "--template",
            str(MINIMAL_TEMPLATE),
            "--config",
            self.config_path,
            "--work-order-id",
            f"gov-{name}",
            "--name",
            f"Gov {name}",
        )
        return self.tree_path(name)

    def leaf(self, name: str, template_id: str) -> str:
        payload = self.run_cli(
            "find",
            "--tree",
            self.tree_argument(name),
            "--config",
            self.config_path,
            "--template-id",
            template_id,
        )
        nodes = payload["nodes"]
        assert isinstance(nodes, list) and nodes
        return str(nodes[0]["id"])

    def complete_investigation(self, name: str, summary: str) -> None:
        node = self.leaf(name, "investigation")
        self.run_cli(
            "start", "--tree", self.tree_argument(name), "--config", self.config_path, "--node", node
        )
        self.run_cli(
            "complete",
            "--tree",
            self.tree_argument(name),
            "--config",
            self.config_path,
            "--node",
            node,
            "--summary",
            summary,
            "--validation",
            "ok",
            "--artifact",
            "artifacts/investigation/analysis.md",
        )

    def complete_scope_gate(self, name: str, outcome: str, decision: str) -> None:
        node = self.leaf(name, "scope-gate")
        self.run_cli(
            "start", "--tree", self.tree_argument(name), "--config", self.config_path, "--node", node
        )
        self.run_cli(
            "complete",
            "--tree",
            self.tree_argument(name),
            "--config",
            self.config_path,
            "--node",
            node,
            "--gate-outcome",
            outcome,
            "--decision",
            decision,
            "--summary",
            "Scope gate completed",
            "--validation",
            "gate recorded",
        )

    def collect(self, *paths: str) -> tuple[str, dict[str, object]]:
        env = os.environ.copy()
        env["XC_RUNTIME_CLI"] = " ".join(
            shlex.quote(part) for part in [sys.executable, str(RUNTIME_CLI)]
        )
        arguments: list[str] = []
        for path in paths:
            arguments.extend(["--trees", path])
        result = subprocess.run(
            [sys.executable, str(GOVERNANCE_STATS), *arguments],
            cwd=self.scratch,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout, json.loads(result.stdout)

    def build_blocked_tree(self, name: str, gate_outcome: str, decision: str) -> None:
        self.init_tree(name)
        self.complete_investigation(name, "Investigation done; route=direct recorded")
        self.complete_scope_gate(name, gate_outcome, decision)
        review = self.leaf(name, "review")
        self.run_cli(
            "start", "--tree", self.tree_argument(name), "--config", self.config_path, "--node", review
        )
        self.run_cli(
            "block",
            "--tree",
            self.tree_argument(name),
            "--config",
            self.config_path,
            "--node",
            review,
            "--reason",
            "waiting on external evidence",
        )

    def build_retry_tree(self) -> None:
        self.init_tree("b")
        self.run_cli(
            "set",
            "--tree",
            self.tree_argument("b"),
            "--config",
            self.config_path,
            "--set",
            "review.open_issues=true",
        )
        self.complete_investigation("b", "Investigation done; route=managed recorded")
        self.complete_scope_gate("b", "revision-required", "Needs changes")
        review = self.leaf("b", "review")
        self.run_cli(
            "start", "--tree", self.tree_argument("b"), "--config", self.config_path, "--node", review
        )
        self.run_cli(
            "fail",
            "--tree",
            self.tree_argument("b"),
            "--config",
            self.config_path,
            "--node",
            review,
            "--reason",
            "flaky environment",
        )
        self.run_cli(
            "retry-failed",
            "--tree",
            self.tree_argument("b"),
            "--config",
            self.config_path,
            "--node",
            review,
            "--reason",
            "retry after environment reset",
        )
        self.run_cli(
            "start", "--tree", self.tree_argument("b"), "--config", self.config_path, "--node", review
        )
        self.run_cli(
            "complete",
            "--tree",
            self.tree_argument("b"),
            "--config",
            self.config_path,
            "--node",
            review,
            "--summary",
            "Review passed after retry; route=managed",
            "--validation",
            "ok",
        )
        rework = self.leaf("b", "rework")
        self.run_cli(
            "start", "--tree", self.tree_argument("b"), "--config", self.config_path, "--node", rework
        )
        self.run_cli(
            "block",
            "--tree",
            self.tree_argument("b"),
            "--config",
            self.config_path,
            "--node",
            rework,
            "--reason",
            "blocked for external decision",
        )

    def build_failed_tree(self) -> None:
        self.init_tree("c")
        self.complete_investigation("c", "Investigation done; route=direct recorded")
        self.complete_scope_gate("c", "approved", "Approved")
        review = self.leaf("c", "review")
        self.run_cli(
            "start", "--tree", self.tree_argument("c"), "--config", self.config_path, "--node", review
        )
        self.run_cli(
            "fail",
            "--tree",
            self.tree_argument("c"),
            "--config",
            self.config_path,
            "--node",
            review,
            "--reason",
            "contract violation",
        )

    def test_aggregate_counts_gate_outcomes_retries_and_routes(self) -> None:
        self.build_blocked_tree("a", "approved", "Approved")
        self.build_retry_tree()
        self.build_failed_tree()
        _, payload = self.collect(
            self.tree_argument("a"),
            self.tree_argument("b"),
            self.tree_argument("c"),
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_total"], 3)
        self.assertEqual(payload["trees_included"], 3)
        self.assertEqual(payload["trees_skipped"], 0)
        self.assertEqual(
            payload["gate_outcomes"], {"approved": 2, "revision-required": 1}
        )
        self.assertEqual(
            payload["node_statuses"],
            {"blocked": 6, "failed": 3, "pending": 2, "succeeded": 7},
        )
        self.assertEqual(payload["blocked_nodes"], 6)
        self.assertEqual(payload["failed_nodes"], 3)
        self.assertEqual(payload["succeeded_nodes"], 7)
        self.assertEqual(payload["retry_attempts"], 1)
        self.assertEqual(payload["retried_nodes"], 1)
        self.assertEqual(payload["routes"], {"direct": 2, "managed": 2})
        trees = payload["trees"]
        self.assertTrue(all(entry["included"] is True for entry in trees))
        by_name = {Path(str(entry["path"])).parent.parent.name: entry for entry in trees}
        self.assertEqual(by_name["a"]["blocked_nodes"], 3)
        self.assertEqual(by_name["a"]["gate_outcomes"], {"approved": 1})
        self.assertEqual(by_name["a"]["routes"], {"direct": 1})
        self.assertEqual(by_name["b"]["retry_attempts"], 1)
        self.assertEqual(by_name["b"]["retried_nodes"], 1)
        self.assertEqual(by_name["b"]["gate_outcomes"], {"revision-required": 1})
        self.assertEqual(by_name["b"]["routes"], {"managed": 2})
        self.assertEqual(by_name["c"]["failed_nodes"], 3)
        self.assertEqual(by_name["c"]["gate_outcomes"], {"approved": 1})

    def test_missing_tree_is_skipped_with_reason(self) -> None:
        self.build_blocked_tree("a", "approved", "Approved")
        missing = self.tree_argument("missing")
        _, payload = self.collect(self.tree_argument("a"), missing)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_total"], 2)
        self.assertEqual(payload["trees_included"], 1)
        self.assertEqual(payload["trees_skipped"], 1)
        skipped = [entry for entry in payload["trees"] if entry["included"] is False]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["path"], missing)
        self.assertEqual(skipped[0]["skip_reason"], "tree_unreadable")
        error = skipped[0].get("error")
        self.assertIsInstance(error, dict)
        self.assertIsInstance(error.get("code"), str)
        self.assertTrue(error["code"])

    def test_sealed_tree_is_skipped_with_reason(self) -> None:
        self.init_tree("d")
        self.complete_investigation("d", "Investigation done")
        self.complete_scope_gate("d", "approved", "Approved")
        review = self.leaf("d", "review")
        self.run_cli(
            "start", "--tree", self.tree_argument("d"), "--config", self.config_path, "--node", review
        )
        self.run_cli(
            "complete",
            "--tree",
            self.tree_argument("d"),
            "--config",
            self.config_path,
            "--node",
            review,
            "--summary",
            "Review passed",
            "--validation",
            "ok",
        )
        status = self.run_cli(
            "summary", "--tree", self.tree_argument("d"), "--config", self.config_path
        )
        self.assertEqual(status["status"], "complete")
        _, payload = self.collect(self.tree_argument("d"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_included"], 0)
        self.assertEqual(payload["trees_skipped"], 1)
        self.assertEqual(payload["trees"][0]["skip_reason"], "tree_sealed")
        self.assertEqual(payload["blocked_nodes"], 0)
        self.assertEqual(payload["gate_outcomes"], {})

    def test_json_list_input_and_deduplication(self) -> None:
        self.build_blocked_tree("a", "approved", "Approved")
        self.build_failed_tree()
        encoded = json.dumps([self.tree_argument("a"), self.tree_argument("c")])
        _, payload = self.collect(encoded, self.tree_argument("a"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_total"], 2)
        self.assertEqual(payload["trees_included"], 2)
        self.assertEqual(
            payload["gate_outcomes"], {"approved": 2}
        )
        self.assertEqual(payload["routes"], {"direct": 2})

    def test_collector_never_mutates_trees(self) -> None:
        self.build_blocked_tree("a", "approved", "Approved")
        tree = self.tree_path("a")
        before_files = sorted(path.name for path in tree.parent.iterdir())
        digest_before = hashlib.sha256(tree.read_bytes()).hexdigest()
        _, payload = self.collect(self.tree_argument("a"))
        self.assertTrue(payload["ok"])
        after_files = sorted(path.name for path in tree.parent.iterdir())
        digest_after = hashlib.sha256(tree.read_bytes()).hexdigest()
        self.assertEqual(digest_before, digest_after)
        self.assertEqual(before_files, after_files)

    def test_deterministic_output(self) -> None:
        self.build_blocked_tree("a", "approved", "Approved")
        missing = self.tree_argument("missing")
        first, payload = self.collect(self.tree_argument("a"), missing)
        second, _ = self.collect(self.tree_argument("a"), missing)
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        expected_cli = " ".join([sys.executable, str(RUNTIME_CLI)])
        self.assertEqual(payload["runtime_cli"], expected_cli)

    def test_invalid_input_exits_zero_with_failure_payload(self) -> None:
        env = os.environ.copy()
        env["XC_RUNTIME_CLI"] = " ".join(
            shlex.quote(part) for part in [sys.executable, str(RUNTIME_CLI)]
        )
        cases = (
            ([], "governance_stats_input_missing"),
            (["--trees", "[]"], "governance_stats_input_empty"),
            (["--trees", "{}"], "governance_stats_input_invalid"),
            (["--trees", "null"], "governance_stats_input_invalid"),
            (["--trees", '["only", 2]'], "governance_stats_input_invalid"),
            (["--trees"], "governance_stats_input_invalid"),
        )
        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(GOVERNANCE_STATS), *arguments],
                    cwd=self.scratch,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                payload = json.loads(result.stdout)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], expected_code)


if __name__ == "__main__":
    unittest.main()
