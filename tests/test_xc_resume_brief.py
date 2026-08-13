from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
RUNTIME_CLI = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
RESUME_BRIEF = (
    REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "resume_brief.py"
)
MINIMAL_TEMPLATE = (
    SOURCE_ROOT / "xcoding" / "runtime" / "assets" / "minimal-template.xml"
)
CONFIG_OVERRIDE = {"schema_version": 1, "git": {"auto_commit": False}}

sys.path.insert(0, str(SOURCE_ROOT))
from xcoding.runtime import core


class ResumeBriefTests(unittest.TestCase):
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
            f"rb-{name}",
            "--name",
            f"RB {name}",
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

    def complete_investigation(self, name: str, summary: str) -> str:
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
        return node

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

    def brief(self, *paths: str, workbench: str | None = None) -> tuple[str, dict[str, object]]:
        env = os.environ.copy()
        env["XC_RUNTIME_CLI"] = " ".join(
            shlex.quote(part) for part in [sys.executable, str(RUNTIME_CLI)]
        )
        arguments: list[str] = []
        for path in paths:
            arguments.extend(["--tree", path])
        if workbench is not None:
            arguments.extend(["--workbench", workbench])
        result = subprocess.run(
            [sys.executable, str(RESUME_BRIEF), *arguments],
            cwd=self.scratch,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout, json.loads(result.stdout)

    def build_blocked_tree(self, name: str) -> str:
        self.init_tree(name)
        self.complete_investigation(name, "Investigation done; route=direct recorded")
        self.complete_scope_gate(name, "approved", "Approved")
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
        return review

    def write_dynamic_group_template(self, path: Path) -> None:
        config = core.load_config(config_path=Path(self.config_path))
        root = ET.Element("orchestration", {"schema_version": "1", "name": "dynamic-group"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Dynamic Group",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(workflow, "children")
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "prepare",
                "title": "Prepare",
                "type": "task",
                "role": "prepare",
                "executor": "main",
            },
        )
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "work-group",
                "title": "Work group",
                "type": "composite",
                "role": "dynamic-group",
                "mode": "sequence",
                "executor": "main",
            },
        )
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "finish",
                "title": "Finish",
                "type": "task",
                "role": "finish",
                "executor": "main",
            },
        )
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def test_brief_sections_counts_blocked_reasons_and_next_actions(self) -> None:
        review_id = self.build_blocked_tree("a")
        investigation_id = self.leaf("a", "investigation")
        _, payload = self.brief(self.tree_argument("a"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["trees_total"], 1)
        self.assertEqual(payload["trees_included"], 1)
        self.assertEqual(payload["trees_skipped"], 0)
        briefs = payload["briefs"]
        self.assertEqual(len(briefs), 1)
        brief = briefs[0]
        self.assertIs(brief["included"], True)
        self.assertEqual(brief["path"], self.tree_argument("a"))
        self.assertEqual(brief["work_order_id"], "rb-a")
        self.assertEqual(brief["status"], "blocked")
        self.assertIsInstance(brief["revision"], int)
        self.assertGreaterEqual(brief["revision"], 1)
        self.assertEqual(brief["integrity_status"], "valid")
        self.assertEqual(brief["status_counts"]["blocked"], 3)
        self.assertEqual(brief["status_counts"]["succeeded"], 2)
        self.assertEqual(brief["status_counts"]["pending"], 1)
        self.assertEqual(brief["running_nodes"], [])
        blocked = brief["blocked_nodes"]
        self.assertEqual(len(blocked), 3)
        for entry in blocked:
            self.assertTrue(entry["id"])
            self.assertIn("reason", entry)
        with_reason = [entry for entry in blocked if entry["reason"]]
        self.assertEqual(len(with_reason), 1)
        self.assertEqual(with_reason[0]["id"], review_id)
        self.assertEqual(with_reason[0]["reason"], "waiting on external evidence")
        self.assertIsInstance(brief["awaiting_dynamic_groups"], list)
        self.assertEqual(brief["awaiting_dynamic_groups"], [])
        self.assertEqual(brief["ready_leaves"], [])
        results = brief["recent_terminal_results"]
        self.assertTrue(results)
        self.assertEqual(results[0]["node_id"], self.leaf("a", "scope-gate"))
        self.assertEqual(results[0]["status"], "succeeded")
        self.assertEqual(results[0]["summary"], "Scope gate completed")
        self.assertTrue(
            any(entry["node_id"] == investigation_id for entry in results)
        )
        self.assertLessEqual(len(results), 10)
        artifacts = brief["declared_artifacts"]
        self.assertTrue(
            any(
                str(entry["path"]).endswith("artifacts/investigation/analysis.md")
                for entry in artifacts
            )
        )
        self.assertIsNone(brief["decision_registry"])
        actions = brief["next_actions"]
        self.assertEqual(
            actions[0], f"blocked {review_id}: waiting on external evidence"
        )
        self.assertLessEqual(len(actions), 6)

    def test_running_nodes_reported_while_leaf_in_flight(self) -> None:
        self.init_tree("r")
        self.complete_investigation("r", "Investigation done")
        self.complete_scope_gate("r", "approved", "Approved")
        review = self.leaf("r", "review")
        self.run_cli(
            "start", "--tree", self.tree_argument("r"), "--config", self.config_path, "--node", review
        )
        _, payload = self.brief(self.tree_argument("r"))
        self.assertTrue(payload["ok"])
        brief = payload["briefs"][0]
        running = brief["running_nodes"]
        self.assertIn(review, [entry["id"] for entry in running])
        self.assertTrue(
            any(
                entry["id"] == review and entry["role"] == "review"
                for entry in running
            )
        )
        self.assertGreaterEqual(brief["status_counts"].get("running", 0), 1)
        self.assertEqual(brief["ready_leaves"], [])
        self.assertEqual(brief["blocked_nodes"], [])
        self.assertEqual(brief["next_actions"], [])

    def test_missing_tree_is_skipped_with_reason(self) -> None:
        self.build_blocked_tree("a")
        missing = self.tree_argument("missing")
        _, payload = self.brief(self.tree_argument("a"), missing)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_total"], 2)
        self.assertEqual(payload["trees_included"], 1)
        self.assertEqual(payload["trees_skipped"], 1)
        skipped = [entry for entry in payload["briefs"] if entry["included"] is False]
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
        _, payload = self.brief(self.tree_argument("d"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_included"], 0)
        self.assertEqual(payload["trees_skipped"], 1)
        self.assertEqual(payload["briefs"][0]["skip_reason"], "tree_sealed")

    def test_json_list_input_and_deduplication(self) -> None:
        self.build_blocked_tree("a")
        self.build_blocked_tree("c")
        encoded = json.dumps([self.tree_argument("a"), self.tree_argument("c")])
        _, payload = self.brief(encoded, self.tree_argument("a"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["trees_total"], 2)
        self.assertEqual(payload["trees_included"], 2)
        paths = [entry["path"] for entry in payload["briefs"]]
        self.assertEqual(paths, [self.tree_argument("a"), self.tree_argument("c")])

    def test_collector_never_mutates_trees(self) -> None:
        self.build_blocked_tree("a")
        tree = self.tree_path("a")
        before_files = sorted(path.name for path in tree.parent.iterdir())
        digest_before = hashlib.sha256(tree.read_bytes()).hexdigest()
        _, payload = self.brief(self.tree_argument("a"))
        self.assertTrue(payload["ok"])
        after_files = sorted(path.name for path in tree.parent.iterdir())
        digest_after = hashlib.sha256(tree.read_bytes()).hexdigest()
        self.assertEqual(digest_before, digest_after)
        self.assertEqual(before_files, after_files)

    def test_deterministic_output(self) -> None:
        self.build_blocked_tree("a")
        missing = self.tree_argument("missing")
        first, payload = self.brief(self.tree_argument("a"), missing)
        second, _ = self.brief(self.tree_argument("a"), missing)
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

    def test_decision_registry_pointer_detected_in_workbench(self) -> None:
        self.build_blocked_tree("w")
        workbench = self.scratch / "w"
        registry = workbench / "decision-registry.jsonl"
        registry.write_text(
            json.dumps(
                {
                    "id": "d1",
                    "work_order_id": "rb-w",
                    "timestamp": "2026-08-13T00:00:00+00:00",
                    "decision": "Use X",
                    "rationale": "Because",
                    "evidence_refs": [],
                    "actor": "main",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workbench / "other.jsonl").write_text(
            json.dumps({"foo": 1}) + "\n",
            encoding="utf-8",
        )
        _, payload = self.brief(self.tree_argument("w"), workbench=str(workbench))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["workbench"], str(workbench))
        brief = payload["briefs"][0]
        self.assertEqual(brief["decision_registry"], str(registry.resolve()))

    def test_decision_registry_pointer_absent_without_registry_file(self) -> None:
        self.build_blocked_tree("x")
        workbench = self.scratch / "x"
        (workbench / "other.jsonl").write_text(
            json.dumps({"foo": 1}) + "\n",
            encoding="utf-8",
        )
        _, payload = self.brief(self.tree_argument("x"), workbench=str(workbench))
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["briefs"][0]["decision_registry"])
        _, payload = self.brief(self.tree_argument("x"))
        self.assertIsNone(payload["briefs"][0]["decision_registry"])

    def test_awaiting_dynamic_groups_reported(self) -> None:
        template = self.scratch / "dynamic-template.xml"
        self.write_dynamic_group_template(template)
        self.run_cli(
            "init",
            "--runtime-path",
            str(self.scratch / "g" / "runtime"),
            "--template",
            str(template),
            "--config",
            self.config_path,
            "--work-order-id",
            "rb-g",
            "--name",
            "RB g",
        )
        prepare = self.leaf("g", "prepare")
        self.run_cli(
            "start", "--tree", self.tree_argument("g"), "--config", self.config_path, "--node", prepare
        )
        self.run_cli(
            "complete",
            "--tree",
            self.tree_argument("g"),
            "--config",
            self.config_path,
            "--node",
            prepare,
            "--summary",
            "Prepare done",
            "--validation",
            "ok",
        )
        _, payload = self.brief(self.tree_argument("g"))
        self.assertTrue(payload["ok"])
        brief = payload["briefs"][0]
        groups = brief["awaiting_dynamic_groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["template_id"], "work-group")
        self.assertEqual(groups[0]["state"], "open")
        self.assertEqual(brief["ready_leaves"], [])

    def test_invalid_input_exits_zero_with_failure_payload(self) -> None:
        env = os.environ.copy()
        env["XC_RUNTIME_CLI"] = " ".join(
            shlex.quote(part) for part in [sys.executable, str(RUNTIME_CLI)]
        )
        cases = (
            ([], "resume_brief_input_missing"),
            (["--tree", "[]"], "resume_brief_input_empty"),
            (["--tree", "{}"], "resume_brief_input_invalid"),
            (["--tree", "null"], "resume_brief_input_invalid"),
            (["--tree", '["only", 2]'], "resume_brief_input_invalid"),
            (["--tree"], "resume_brief_input_invalid"),
            (["--tree", "x", "--workbench"], "resume_brief_input_invalid"),
        )
        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(RESUME_BRIEF), *arguments],
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
                self.assertEqual(payload["schema_version"], 1)
                self.assertEqual(payload["error"]["code"], expected_code)
                self.assertNotIn("briefs", payload)


if __name__ == "__main__":
    unittest.main()
