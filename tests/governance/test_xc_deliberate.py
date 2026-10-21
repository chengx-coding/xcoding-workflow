from __future__ import annotations
from tests.support.paths import REPO_ROOT  # noqa: E402

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = REPO_ROOT
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-deliberate"
FLOW = SKILL_ROOT / "assets" / "debate-flow.json"
TEMPLATE = SKILL_ROOT / "assets" / "debate-template.xml"
WORK_ORDER_ID = "20260727-1000-deliberate"

GATE_METADATA = (
    'metadata.gate.outcomes=["continue","exhausted","cost-accepted","time-up"]\n'
    "metadata.gate.decision_required=true\n"
    "metadata.gate.outcome_key=debate.outcome\n"
)

REBUTTAL = {
    "--instructions": "Challenge the reasoning or report a new fact, and say which.",
    "--deliverables": "one rebuttal artefact",
    "--acceptance": "independent, sourced, in scope",
}


class XcDeliberateTests(unittest.TestCase):
    """The debate template's round protocol, exercised through the public runtime."""

    def run_json(self, command: list[str]) -> dict[str, object]:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def run_failure(self, command: list[str]) -> dict[str, object]:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout or result.stderr)
        return json.loads(result.stdout)["error"]

    def next_payload(self, tree: Path) -> dict[str, object]:
        return self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])

    def complete_node(self, tree: Path, node: str, extra: list[str] | None = None) -> None:
        command = [
            sys.executable,
            str(RUNTIME),
            "complete",
            "--tree",
            str(tree),
            "--node",
            node,
            "--summary",
            "test step",
            "--validation",
            "test step",
        ]
        self.run_json(command + (extra or []))

    def start_and_complete(self, tree: Path, node: str, extra: list[str] | None = None) -> None:
        self.run_json(
            [sys.executable, str(RUNTIME), "start", "--tree", str(tree), "--node", node, "--agent", "test"]
        )
        self.complete_node(tree, node, extra)

    def find_node(self, tree: Path, template_id: str) -> dict[str, object]:
        nodes = self.run_json(
            [sys.executable, str(RUNTIME), "find", "--tree", str(tree), "--template-id", template_id]
        )["nodes"]
        self.assertTrue(nodes, f"template node {template_id} not found")
        return nodes[0]

    def initialize(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workshop = Path(temporary.name) / ".xcoding"
        workshop.mkdir()
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8"
        )
        initialized = self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "init",
                "--template",
                str(TEMPLATE),
                "--runtime-path",
                str(workshop / "work-orders" / "deliberate" / "runtime"),
                "--work-order-id",
                WORK_ORDER_ID,
            ]
        )
        return Path(str(initialized["tree_path"]))

    def add_rebuttal(self, tree: Path, group: str, key: str) -> dict[str, object]:
        command = [
            sys.executable,
            str(RUNTIME),
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            group,
            "--logical-key",
            key,
            "--title",
            key,
            "--type",
            "task",
            "--role",
            "deliberation-rebuttal",
            "--executor",
            "subagent",
        ]
        for flag, value in REBUTTAL.items():
            command.extend([flag, value])
        return self.run_json(command)["node"]

    def reach_round_one_group(self) -> tuple[Path, str]:
        tree = self.initialize()
        plan = self.next_payload(tree)["ready"][0]
        self.assertEqual(plan["template_id"], "r01-plan")
        self.start_and_complete(tree, str(plan["id"]), ["--set", "debate.number=01", "--set", "debate.round=1"])
        awaiting = self.next_payload(tree)["awaiting_dynamic_groups"]
        self.assertEqual([item["template_id"] for item in awaiting], ["r01-debaters"], awaiting)
        return tree, str(awaiting[0]["id"])

    def test_flow_rebuilds_current_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            validation = self.run_json([sys.executable, str(AUTHOR), "validate-spec", "--spec", str(FLOW)])
            self.assertTrue(validation["valid"], validation)
            rebuilt = root / "debate-template.xml"
            self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(FLOW),
                    "--out",
                    str(rebuilt),
                    "--config",
                    str(config),
                ]
            )
            self.assertEqual(rebuilt.read_bytes(), TEMPLATE.read_bytes())

    def test_round_one_gate_declares_the_answer_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            rebuilt = root / "debate-template.xml"
            self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(FLOW),
                    "--out",
                    str(rebuilt),
                    "--config",
                    str(config),
                ]
            )
            document = ET.parse(rebuilt).getroot()
            gate = next(node for node in document.iter("node") if node.get("template_id") == "r01-wait")
            self.assertEqual(gate.get("type"), "gate")
            self.assertEqual(gate.get("executor"), "main")
            self.assertEqual(gate.get("metadata.gate.outcome_key"), "debate.outcome")
            self.assertEqual(gate.get("metadata.gate.decision_required"), "true")
            self.assertEqual(
                json.loads(gate.get("metadata.gate.outcomes", "[]")),
                ["continue", "exhausted", "cost-accepted", "time-up"],
            )
            rounds = next(node for node in document.iter("node") if node.get("template_id") == "rounds")
            children = rounds.find("children")
            self.assertIsNotNone(children)
            self.assertEqual(
                [child.get("template_id") for child in children],
                ["r01-plan", "r01-debaters", "r01-summary", "r01-wait", "rounds-open"],
            )
            root = document.find("node")
            self.assertIsNotNone(root)
            self.assertEqual(root.get("role"), "root")
            root_children = root.find("children")
            self.assertIsNotNone(root_children)
            self.assertEqual(
                [child.get("template_id") for child in root_children],
                ["rounds", "finalize", "merge", "follow-ups"],
            )

    def test_first_ready_node_is_the_round_one_plan(self) -> None:
        tree = self.initialize()
        ready = self.next_payload(tree)["ready"]
        self.assertEqual([item["template_id"] for item in ready], ["r01-plan"])

    def test_rebuttal_group_returns_two_leaves_in_one_batch(self) -> None:
        tree, group = self.reach_round_one_group()
        self.add_rebuttal(tree, group, "r01-debate-01")
        self.add_rebuttal(tree, group, "r01-debate-02")
        ready = self.next_payload(tree)["ready"]
        self.assertEqual([item["logical_key"] for item in ready], ["r01-debate-01", "r01-debate-02"])

    def test_nine_rebuttals_never_return_more_than_eight_in_one_batch(self) -> None:
        tree, group = self.reach_round_one_group()
        nodes = [self.add_rebuttal(tree, group, f"r01-debate-{index:02d}") for index in range(1, 10)]
        ready = self.next_payload(tree)["ready"]
        self.assertEqual(len(ready), 8)
        self.assertLessEqual(len(ready), 8)
        self.assertEqual(len(nodes), 9)

    def test_duplicate_key_and_gate_parent_are_refused(self) -> None:
        tree, group = self.reach_round_one_group()
        self.add_rebuttal(tree, group, "r01-debate-01")
        duplicate = [
            sys.executable,
            str(RUNTIME),
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            group,
            "--logical-key",
            "r01-debate-01",
            "--title",
            "duplicate",
            "--type",
            "task",
            "--executor",
            "main",
        ]
        self.assertIn("logical_key", self.run_failure(duplicate)["message"])
        gate = self.find_node(tree, "r01-wait")
        under_gate = [
            sys.executable,
            str(RUNTIME),
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            str(gate["id"]),
            "--logical-key",
            "under-gate",
            "--title",
            "under gate",
            "--type",
            "task",
            "--executor",
            "main",
        ]
        self.assertIn("composite or loop", self.run_failure(under_gate)["message"])

    def test_empty_plain_composite_is_refused_and_the_tree_stays_valid(self) -> None:
        tree, group = self.reach_round_one_group()
        empty = [
            sys.executable,
            str(RUNTIME),
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            group,
            "--logical-key",
            "plain-empty",
            "--title",
            "plain empty",
            "--type",
            "composite",
            "--mode",
            "sequence",
            "--executor",
            "main",
        ]
        error = self.run_failure(empty)
        self.assertIn("composite without children", json.dumps(error["details"]))
        validation = self.run_json([sys.executable, str(RUNTIME), "validate", "--tree", str(tree)])
        self.assertTrue(validation["valid"], validation)

    def test_sentinel_holds_the_terminal_nodes_until_it_closes(self) -> None:
        tree, group = self.reach_round_one_group()
        self.add_rebuttal(tree, group, "r01-debate-01")
        ready = self.next_payload(tree)["ready"]
        self.start_and_complete(tree, str(ready[0]["id"]))
        summary = self.next_payload(tree)["ready"][0]
        self.assertEqual(summary["template_id"], "r01-summary")
        self.start_and_complete(tree, str(summary["id"]))
        gate = self.next_payload(tree)["ready"][0]
        self.assertEqual(gate["template_id"], "r01-wait")
        self.start_and_complete(tree, str(gate["id"]), ["--gate-outcome", "continue", "--decision", "keep going"])

        awaiting = self.next_payload(tree)["awaiting_dynamic_groups"]
        self.assertEqual([item["template_id"] for item in awaiting], ["rounds-open"])
        for template_id in ("finalize", "merge", "follow-ups"):
            node = self.find_node(tree, template_id)
            self.assertEqual(node["status"], "pending", template_id)

        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "close-group",
                "--tree",
                str(tree),
                "--group",
                str(awaiting[0]["id"]),
            ]
        )
        ready = self.next_payload(tree)["ready"]
        self.assertEqual([item["template_id"] for item in ready], ["finalize"])

    def test_second_round_is_inserted_before_the_sentinel_and_round_one_is_untouched(self) -> None:
        tree, group = self.reach_round_one_group()
        self.add_rebuttal(tree, group, "r01-debate-01")
        ready = self.next_payload(tree)["ready"]
        self.start_and_complete(tree, str(ready[0]["id"]))
        self.start_and_complete(tree, str(self.next_payload(tree)["ready"][0]["id"]))
        gate = self.next_payload(tree)["ready"][0]
        self.start_and_complete(tree, str(gate["id"]), ["--gate-outcome", "continue", "--decision", "keep going"])
        sentinel = self.next_payload(tree)["awaiting_dynamic_groups"][0]
        rounds = self.find_node(tree, "rounds")

        with tempfile.TemporaryDirectory() as temporary:
            metadata = Path(temporary) / "gate-metadata.txt"
            metadata.write_text(GATE_METADATA, encoding="utf-8")
            self.run_json(
                [
                    sys.executable, str(RUNTIME), "add-node", "--tree", str(tree),
                    "--parent", str(rounds["id"]), "--before", str(sentinel["id"]),
                    "--logical-key", "r02-plan", "--title", "Round 02: record the plan",
                    "--type", "task", "--executor", "main",
                ]
            )
            self.run_json(
                [
                    sys.executable, str(RUNTIME), "add-node", "--tree", str(tree),
                    "--parent", str(rounds["id"]), "--before", str(sentinel["id"]),
                    "--logical-key", "r02-wait", "--title", "Round 02: await the answer",
                    "--type", "gate", "--executor", "main", "--metadata-file", str(metadata),
                ]
            )
        self.assertEqual(self.next_payload(tree)["ready"][0]["logical_key"], "r02-plan")
        for template_id in ("r01-plan", "r01-debaters", "r01-summary", "r01-wait"):
            self.assertEqual(self.find_node(tree, template_id)["status"], "succeeded", template_id)

    def test_embedded_template_starts_at_round_one_plan(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        config = root / "runtime.json"
        config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
        outer_spec = root / "outer-flow.json"
        outer_spec.write_text(
            json.dumps(
                {
                    "name": "outer",
                    "schema_version": 1,
                    "blackboard": {},
                    "root": {
                        "template_id": "root",
                        "title": "Outer",
                        "type": "composite",
                        "role": "root",
                        "mode": "sequence",
                        "executor": "main",
                        "children": [
                            {
                                "template_id": "container",
                                "title": "Deliberation container",
                                "type": "composite",
                                "role": "dynamic-group",
                                "mode": "sequence",
                                "executor": "main",
                            }
                        ],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        outer_template = root / "outer-template.xml"
        self.run_json(
            [
                sys.executable, str(AUTHOR), "build", "--spec", str(outer_spec),
                "--out", str(outer_template), "--config", str(config),
            ]
        )
        workshop = root / ".xcoding"
        workshop.mkdir()
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8"
        )
        initialized = self.run_json(
            [
                sys.executable, str(RUNTIME), "init", "--template", str(outer_template),
                "--runtime-path", str(workshop / "work-orders" / "mount" / "runtime"),
                "--work-order-id", WORK_ORDER_ID,
            ]
        )
        tree = Path(str(initialized["tree_path"]))
        container = self.next_payload(tree)["awaiting_dynamic_groups"][0]
        self.run_json(
            [
                sys.executable, str(RUNTIME), "embed-subtree", "--tree", str(tree),
                "--parent", str(container["id"]), "--template", str(TEMPLATE),
                "--instance-id", "deliberation-01",
            ]
        )
        ready = self.next_payload(tree)["ready"]
        self.assertEqual([item["template_id"] for item in ready], ["r01-plan"])


if __name__ == "__main__":
    unittest.main()
