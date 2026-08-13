from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = ROOT / "tests" / "runtime_cli.py"
SPEC = ROOT / "skills" / "xc-work" / "assets" / "jit-milestone-flow.json"
TEMPLATE = ROOT / "skills" / "xc-work" / "assets" / "jit-milestone-template.xml"


class JitMilestoneTests(unittest.TestCase):
    def run_json(self, script: Path, *arguments: str) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, str(script), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail((completed.returncode, completed.stdout, completed.stderr, exc))
        self.assertEqual(completed.returncode, 0, payload)
        self.assertTrue(payload["ok"], payload)
        return payload

    def environment(self, root: Path) -> tuple[Path, Path]:
        workshop = root / ".xcoding"
        workshop.mkdir()
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        runtime_path = workshop / "work-orders" / "jit-milestone" / "runtime"
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(TEMPLATE),
            "--runtime-path",
            str(runtime_path),
            "--work-order-id",
            "20260813-0000-jit-milestone",
            "--name",
            "JIT Milestone Test",
        )
        return Path(str(initialized["tree_path"])), workshop

    def find_node_id(self, tree: Path, template_id: str) -> str:
        payload = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            template_id,
        )
        return str(payload["nodes"][0]["id"])

    def start_and_complete(
        self,
        tree: Path,
        node_id: str,
        summary: str,
        validation: str,
        *,
        artifact: Path | None = None,
        gate_outcome: str = "",
        decision: str = "",
    ) -> None:
        self.run_json(
            RUNTIME,
            "start",
            "--tree",
            str(tree),
            "--node",
            node_id,
            "--agent",
            "test",
        )
        command = [
            str(RUNTIME),
            "complete",
            "--tree",
            str(tree),
            "--node",
            node_id,
            "--summary",
            summary,
            "--validation",
            validation,
        ]
        if artifact:
            command.extend(["--artifact", str(artifact)])
        if gate_outcome:
            command.extend(["--gate-outcome", gate_outcome])
        if decision:
            command.extend(["--decision", decision])
        self.run_json(*command)

    def test_flow_rebuilds_current_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(
                json.dumps({"git": {"auto_commit": False}}) + "\n",
                encoding="utf-8",
            )
            validated = self.run_json(
                AUTHOR,
                "validate-spec",
                "--spec",
                str(SPEC),
            )
            self.assertTrue(validated["valid"], validated)
            rebuilt = root / "jit-milestone-template.xml"
            self.run_json(
                AUTHOR,
                "build",
                "--spec",
                str(SPEC),
                "--out",
                str(rebuilt),
                "--config",
                str(config),
            )
            self.assertEqual(rebuilt.read_bytes(), TEMPLATE.read_bytes())

    def test_template_validates(self) -> None:
        validated = self.run_json(
            AUTHOR,
            "validate-template",
            "--template",
            str(TEMPLATE),
        )
        self.assertTrue(validated["valid"], validated)

    def test_built_template_declares_demo_evidence_on_acceptance_gate(self) -> None:
        root = ET.parse(TEMPLATE).getroot()
        gate = next(
            node
            for node in root.iter("node")
            if node.get("template_id") == "milestone-acceptance-gate"
        )
        self.assertEqual(
            gate.get("metadata.control_packet.category.demo-evidence.selectors"),
            '["bb:milestone.demo_sources"]',
        )
        self.assertEqual(
            gate.get("metadata.control_packet.category.demo-evidence.min_sources"),
            "1",
        )
        self.assertEqual(
            gate.get("metadata.control_packet.category.demo-evidence.artifact_min"),
            "1",
        )
        self.assertEqual(
            gate.get("metadata.control_packet.category.milestone-evidence.selectors"),
            '["bb:milestone.evidence_sources"]',
        )
        self.assertEqual(gate.get("metadata.gate.outcomes"), '["approved","revision-required"]')
        self.assertEqual(gate.get("metadata.gate.decision_required"), "true")
        self.assertEqual(gate.get("metadata.gate.outcome_key"), "milestone.accepted")
        finalizer = next(
            node
            for node in root.iter("node")
            if node.get("template_id") == "milestone-finalizer"
        )
        self.assertIsNone(
            finalizer.get("metadata.control_packet.category.demo-evidence.selectors")
        )
        self.assertEqual(
            finalizer.get("metadata.control_packet.category.milestone-evidence.selectors"),
            '["bb:milestone.evidence_sources"]',
        )

    def test_smoke_init_yields_expected_initial_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree, _ = self.environment(Path(temporary))
            payload = self.run_json(RUNTIME, "next", "--tree", str(tree))
            self.assertEqual(payload["ready"], [])
            self.assertEqual(
                [item["template_id"] for item in payload["awaiting_dynamic_groups"]],
                ["milestone-work-group"],
            )
            self.assertEqual(payload["counts"], {"pending": 5})
            milestone_group = self.run_json(
                RUNTIME,
                "show",
                "--tree",
                str(tree),
                "--node",
                self.find_node_id(tree, "milestone-group"),
            )["node"]
            self.assertEqual(milestone_group["role"], "dynamic-group")
            self.assertEqual(milestone_group["attributes"]["dynamic.state"], "open")
            self.assertEqual(milestone_group["status"], "pending")

    def test_jit_milestone_lifecycle_seals_after_approved_finalizer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree, workshop = self.environment(Path(temporary))
            work_group = self.find_node_id(tree, "milestone-work-group")
            artifact = (
                workshop
                / "work-orders"
                / "jit-milestone"
                / "artifacts"
                / "milestone-slice.md"
            )
            leaf = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                work_group,
                "--logical-key",
                "implementation-1",
                "--title",
                "Implement and verify milestone slice",
                "--type",
                "task",
                "--role",
                "implementation",
                "--executor",
                "subagent",
                "--instructions",
                "Apply one approved milestone slice and run its focused verification.",
                "--deliverables",
                str(artifact),
                "--acceptance",
                "The slice change and its focused verification both succeed.",
                "--metadata",
                'metadata.completion.required_fields=["summary","validation"]',
            )["node"]
            leaf_id = str(leaf["id"])
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f'milestone.evidence_sources=["{leaf_id}"]',
            )
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f'milestone.demo_sources=["{leaf_id}"]',
            )
            self.run_json(
                RUNTIME,
                "close-group",
                "--tree",
                str(tree),
                "--group",
                work_group,
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Milestone slice\n\nFocused verification passed.\n", encoding="utf-8")
            self.start_and_complete(
                tree,
                leaf_id,
                "Slice implemented and verified.",
                "Focused verification passed.",
                artifact=artifact,
            )
            gate_id = self.find_node_id(tree, "milestone-acceptance-gate")
            packet = self.run_json(
                RUNTIME,
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                gate_id,
            )["packet"]
            categories = {item["name"]: item for item in packet["source_categories"]}
            self.assertEqual(set(categories), {"demo-evidence", "milestone-evidence"})
            for category in categories.values():
                self.assertEqual(category["sources"][0]["node_id"], leaf_id)
            self.start_and_complete(
                tree,
                gate_id,
                "Milestone evidence accepted.",
                "Evidence sources resolved and accepted.",
                gate_outcome="approved",
                decision="Approve the milestone slice.",
            )
            finalizer_id = self.find_node_id(tree, "milestone-finalizer")
            self.start_and_complete(
                tree,
                finalizer_id,
                "Milestone finalized.",
                "Evidence threshold met and milestone.accepted=approved.",
            )
            summary = self.run_json(RUNTIME, "summary", "--tree", str(tree))
            self.assertEqual(summary["status"], "complete", summary)
            self.assertEqual(summary["counts"]["succeeded"], 6)

    def test_protocol_pins_seal_guard_as_main_session_discipline(self) -> None:
        protocol = (
            ROOT
            / "skills"
            / "xc-work"
            / "references"
            / "jit-milestone-protocol.md"
        ).read_text(encoding="utf-8")
        self.assertIn("advisory evidence projection", protocol)
        self.assertIn(
            "main session MUST verify the packet resolves before completing the finalizer",
            protocol,
        )
        self.assertNotIn("so a minimal tree cannot seal", protocol)
        self.assertNotIn("Follow recovery-patterns.md P3:", protocol)
        self.assertIn(
            "adaptation of recovery-patterns.md P3 (Rescope) with P2 (Alternate Approach)",
            protocol,
        )

    def test_revision_required_keeps_tree_open_for_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree, workshop = self.environment(Path(temporary))
            work_group = self.find_node_id(tree, "milestone-work-group")
            artifact = (
                workshop
                / "work-orders"
                / "jit-milestone"
                / "artifacts"
                / "milestone-slice.md"
            )
            leaf = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                work_group,
                "--logical-key",
                "implementation-1",
                "--title",
                "Implement milestone slice",
                "--type",
                "task",
                "--role",
                "implementation",
                "--executor",
                "subagent",
                "--instructions",
                "Apply one approved milestone slice.",
                "--deliverables",
                str(artifact),
                "--acceptance",
                "The slice change succeeds.",
            )["node"]
            leaf_id = str(leaf["id"])
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f'milestone.evidence_sources=["{leaf_id}"]',
            )
            self.run_json(
                RUNTIME,
                "close-group",
                "--tree",
                str(tree),
                "--group",
                work_group,
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Milestone slice\n", encoding="utf-8")
            self.start_and_complete(
                tree,
                leaf_id,
                "Slice implemented.",
                "Focused verification passed.",
                artifact=artifact,
            )
            gate_id = self.find_node_id(tree, "milestone-acceptance-gate")
            self.start_and_complete(
                tree,
                gate_id,
                "A material revision is still required.",
                "Evidence gap remains.",
                gate_outcome="revision-required",
                decision="Revise the slice before acceptance.",
            )
            summary = self.run_json(RUNTIME, "summary", "--tree", str(tree))
            self.assertNotEqual(summary["status"], "complete", summary)
            self.run_json(
                RUNTIME,
                "reopen-group",
                "--tree",
                str(tree),
                "--group",
                work_group,
                "--reason",
                "revision-required acceptance outcome",
            )
            successor = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                work_group,
                "--logical-key",
                "successor-acceptance",
                "--title",
                "Confirm revised milestone",
                "--type",
                "gate",
                "--role",
                "milestone-acceptance",
                "--executor",
                "main",
                "--instructions",
                "Confirm the revised milestone evidence.",
                "--deliverables",
                "milestone.accepted set to approved.",
                "--acceptance",
                "The revised evidence is accepted.",
                "--metadata",
                'metadata.gate.outcomes=["approved","revision-required"]',
                "--metadata",
                "metadata.gate.decision_required=true",
                "--metadata",
                "metadata.gate.outcome_key=milestone.accepted",
            )["node"]
            self.run_json(
                RUNTIME,
                "close-group",
                "--tree",
                str(tree),
                "--group",
                work_group,
            )
            self.start_and_complete(
                tree,
                str(successor["id"]),
                "Revised milestone evidence accepted.",
                "Successor gate published approved.",
                gate_outcome="approved",
                decision="Approve the revised slice.",
            )
            finalizer_id = self.find_node_id(tree, "milestone-finalizer")
            self.start_and_complete(
                tree,
                finalizer_id,
                "Milestone finalized.",
                "Evidence threshold met and milestone.accepted=approved.",
            )
            summary = self.run_json(RUNTIME, "summary", "--tree", str(tree))
            self.assertEqual(summary["status"], "complete", summary)


if __name__ == "__main__":
    unittest.main()
