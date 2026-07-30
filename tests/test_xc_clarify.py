from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "scripts" / "orchestration.py"
FLOW = REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-flow.json"
TEMPLATE = REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-template.xml"
WORK_ORDER_FLOW = REPOSITORY_ROOT / "skills" / "xc-work-order" / "assets" / "work-order-flow.json"
NEW_FEATURE_FLOW = REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-flow.json"


class XcClarifyTests(unittest.TestCase):
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

    def start_and_complete(self, tree: Path, expected_template_id: str, *, values: list[str] | None = None) -> dict[str, object]:
        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["template_id"], expected_template_id, ready)
        node = ready[0]
        node_id = str(node["id"])
        self.run_json([sys.executable, str(RUNTIME), "start", "--tree", str(tree), "--node", node_id, "--agent", "test"])
        command = [
            sys.executable,
            str(RUNTIME),
            "complete",
            "--tree",
            str(tree),
            "--node",
            node_id,
            "--summary",
            f"Completed {expected_template_id}.",
            "--validation",
            "test workflow step",
        ]
        for value in values or []:
            command.extend(["--set", value])
        self.run_json(command)
        return node

    def initialize_until_seed(self) -> tuple[Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        workshop = root / ".xcoding"
        workshop.mkdir()
        (workshop / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
        initialized = self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "init",
                "--template",
                str(TEMPLATE),
                "--runtime-path",
                str(workshop / "work-orders" / "clarify" / "runtime"),
                "--work-order-id",
                "20260727-1000-clarify",
            ]
        )
        tree = Path(str(initialized["tree_path"]))
        for template_id in ("open-session-record", "gather-context", "map-decisions"):
            self.start_and_complete(tree, template_id)
        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["template_id"], "seed-questioning", ready)
        seed = ready[0]
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(seed["id"]),
                "--agent",
                "test",
            ]
        )
        group = self.run_json(
            [sys.executable, str(RUNTIME), "find", "--tree", str(tree), "--template-id", "question-group"]
        )["nodes"][0]
        return tree, Path(str(group["id"]))

    def add_gate(self, tree: Path, group_id: Path, logical_key: str, title: str, depends_on: str = "") -> dict[str, object]:
        command = [
            sys.executable,
            str(RUNTIME),
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            str(group_id),
            "--logical-key",
            logical_key,
            "--title",
            title,
            "--type",
            "gate",
            "--role",
            "clarification-decision",
            "--executor",
            "main",
            "--instructions",
            "Ask one decision question.",
            "--deliverables",
            "A recorded user decision.",
            "--acceptance",
            "The decision is explicit.",
        ]
        if depends_on:
            command.extend(["--depends-on", depends_on])
        return self.run_json(command)["node"]

    def complete_seed(self, tree: Path) -> None:
        seed = self.run_json(
            [sys.executable, str(RUNTIME), "find", "--tree", str(tree), "--template-id", "seed-questioning"]
        )["nodes"][0]
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(seed["id"]),
                "--summary",
                "Seeded clarification gate.",
                "--validation",
                "A dynamic gate was added before seed completion.",
            ]
        )

    def test_flow_rebuilds_current_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.toml"
            config.write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            validation = self.run_json([sys.executable, str(AUTHOR), "validate-spec", "--spec", str(FLOW)])
            self.assertTrue(validation["valid"], validation)
            rebuilt = root / "clarify-template.xml"
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

    def test_seeded_dynamic_gates_run_sequentially_before_synthesis(self) -> None:
        tree, group_id = self.initialize_until_seed()
        first = self.add_gate(tree, group_id, "clarify-first", "Clarify first decision")
        self.complete_seed(tree)

        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-first", ready)
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(first["id"]),
                "--agent",
                "test",
            ]
        )
        second = self.add_gate(
            tree,
            group_id,
            "clarify-second",
            "Clarify second decision",
            depends_on=str(first["id"]),
        )
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(first["id"]),
                "--summary",
                "Recorded first decision.",
                "--validation",
                "successor was created before completion",
                "--set",
                "clarification.question_count=1",
            ]
        )

        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-second", ready)
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(second["id"]),
                "--agent",
                "test",
            ]
        )
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(second["id"]),
                "--summary",
                "Recorded final decision.",
                "--validation",
                "no material decision remains",
                "--set",
                "clarification.status=ready",
                "--set",
                "clarification.pending_material=false",
            ]
        )
        self.start_and_complete(tree, "synthesize-session")
        self.start_and_complete(tree, "finalize-clarification")
        summary = self.run_json([sys.executable, str(RUNTIME), "summary", "--tree", str(tree)])
        self.assertEqual(summary["status"], "complete", summary)

    def test_seeded_no_material_confirmation_closes_question_group(self) -> None:
        tree, group_id = self.initialize_until_seed()
        closing = self.add_gate(tree, group_id, "clarify-no-material", "Confirm no material decision")
        self.complete_seed(tree)
        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-no-material", ready)
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(closing["id"]),
                "--agent",
                "test",
            ]
        )
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(closing["id"]),
                "--summary",
                "Confirmed no material decision.",
                "--validation",
                "clarification is ready",
                "--set",
                "clarification.status=ready",
                "--set",
                "clarification.pending_material=false",
            ]
        )
        self.start_and_complete(tree, "synthesize-session")
        self.start_and_complete(tree, "finalize-clarification")
        summary = self.run_json([sys.executable, str(RUNTIME), "summary", "--tree", str(tree)])
        self.assertEqual(summary["status"], "complete", summary)

    def test_lifecycle_flows_conditionally_place_clarification_before_solution(self) -> None:
        work_order_flow = json.loads(WORK_ORDER_FLOW.read_text(encoding="utf-8"))
        new_feature_flow = json.loads(NEW_FEATURE_FLOW.read_text(encoding="utf-8"))
        self.assertEqual(work_order_flow["blackboard"]["work_order.requires_clarification"], "false")
        self.assertEqual(new_feature_flow["blackboard"]["work_order.requires_clarification"], "false")

        for flow, preceding in ((work_order_flow, "reconciliation-group"), (new_feature_flow, "analysis-group")):
            children = flow["root"]["children"]
            ids = [child["template_id"] for child in children]
            clarification = children[ids.index("clarification-group")]
            self.assertGreater(ids.index("clarification-group"), ids.index(preceding))
            self.assertLess(ids.index("clarification-group"), ids.index("work-order-solution-document"))
            self.assertEqual(clarification["when"], "work_order.requires_clarification == true")


if __name__ == "__main__":
    unittest.main()
