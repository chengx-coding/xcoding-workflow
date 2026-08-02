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
WORK_ORDER_FLOW = REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-flow.json"
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

    def start_and_complete(
        self,
        tree: Path,
        expected_template_id: str,
        *,
        values: list[str] | None = None,
        artifact: Path | None = None,
    ) -> dict[str, object]:
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
        if artifact:
            command.extend(["--artifact", str(artifact)])
        self.run_json(command)
        return node

    def initialize_until_seed(self) -> tuple[Path, Path, Path, str]:
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
        session_artifact = workshop / "work-orders" / "clarify" / "artifacts" / "open-session-record" / "decision-session.md"
        session_artifact.parent.mkdir(parents=True)
        session_artifact.write_text("# Decision Session\n\nClarification evidence.\n", encoding="utf-8")
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "set",
                "--tree",
                str(tree),
                "--set",
                "clarification.mode=discover",
                "--set",
                "clarification.subject=Choose a compatible behavior",
                "--set",
                f"clarification.session_artifact={session_artifact}",
            ]
        )
        map_id = ""
        for template_id in ("open-session-record", "gather-context", "map-decisions"):
            node = self.start_and_complete(tree, template_id, artifact=session_artifact)
            if template_id == "map-decisions":
                map_id = str(node["id"])
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
        return tree, Path(str(group["id"])), session_artifact, map_id

    def add_gate(
        self,
        tree: Path,
        group_id: Path,
        logical_key: str,
        title: str,
        source_ids: list[str],
        *,
        outcomes: list[str],
        depends_on: str = "",
    ) -> dict[str, object]:
        source_key = f"clarification.sources.{logical_key}"
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "set",
                "--tree",
                str(tree),
                "--set",
                f"{source_key}={json.dumps(source_ids, separators=(',', ':'))}",
            ]
        )
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
            "--metadata",
            f'metadata.control_packet.category.decision-context.selectors=["bb:{source_key}"]',
            "--metadata",
            "metadata.control_packet.category.decision-context.min_sources=1",
            "--metadata",
            "metadata.control_packet.category.decision-context.artifact_min=1",
            "--metadata",
            'metadata.control_packet.blackboard_keys=["clarification.mode","clarification.subject","clarification.pending_material"]',
            "--metadata",
            'metadata.completion.required_fields=["summary","validation"]',
            "--metadata",
            "metadata.completion.artifacts.min=1",
            "--metadata",
            "metadata.completion.artifacts.max=1",
            "--metadata",
            "metadata.completion.artifacts.path=bb:clarification.session_artifact",
            "--metadata",
            f"metadata.gate.outcomes={json.dumps(outcomes, separators=(',', ':'))}",
            "--metadata",
            "metadata.gate.decision_required=true",
            "--metadata",
            "metadata.gate.outcome_key=clarification.outcome",
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
        tree, group_id, session_artifact, map_id = self.initialize_until_seed()
        decision_outcomes = [
            "accepted-recommendation",
            "selected-alternative",
            "accepted-risk",
            "bounded-experiment",
            "deferred",
        ]
        first = self.add_gate(
            tree,
            group_id,
            "clarify-first",
            "Clarify first decision",
            [map_id],
            outcomes=decision_outcomes,
        )
        self.complete_seed(tree)

        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-first", ready)
        first_packet = self.run_json(
            [sys.executable, str(RUNTIME), "control-packet", "--tree", str(tree), "--node", str(first["id"])]
        )["packet"]
        self.assertEqual(first_packet["source_categories"][0]["sources"][0]["node_id"], map_id)
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
            [str(first["id"])],
            outcomes=decision_outcomes,
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
                "--artifact",
                str(session_artifact),
                "--gate-outcome",
                "selected-alternative",
                "--decision",
                "Use the compatible alternative.",
            ]
        )

        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-second", ready)
        second_packet = self.run_json(
            [sys.executable, str(RUNTIME), "control-packet", "--tree", str(tree), "--node", str(second["id"])]
        )["packet"]
        self.assertEqual(second_packet["source_categories"][0]["sources"][0]["node_id"], first["id"])
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
                "--artifact",
                str(session_artifact),
                "--gate-outcome",
                "accepted-recommendation",
                "--decision",
                "Accept the recommended final decision.",
            ]
        )
        completed_second = self.run_json(
            [sys.executable, str(RUNTIME), "show", "--tree", str(tree), "--node", str(second["id"])]
        )["node"]
        self.assertEqual(completed_second["result"]["gate_outcome"], "accepted-recommendation")
        self.start_and_complete(tree, "synthesize-session", artifact=session_artifact)
        self.start_and_complete(tree, "finalize-clarification", artifact=session_artifact)
        summary = self.run_json([sys.executable, str(RUNTIME), "summary", "--tree", str(tree)])
        self.assertEqual(summary["status"], "complete", summary)

    def test_seeded_no_material_confirmation_closes_question_group(self) -> None:
        tree, group_id, session_artifact, map_id = self.initialize_until_seed()
        closing = self.add_gate(
            tree,
            group_id,
            "clarify-no-material",
            "Confirm no material decision",
            [map_id],
            outcomes=["confirmed", "revision-required"],
        )
        self.complete_seed(tree)
        ready = self.run_json([sys.executable, str(RUNTIME), "next", "--tree", str(tree)])["ready"]
        self.assertEqual(ready[0]["logical_key"], "clarify-no-material", ready)
        packet = self.run_json(
            [sys.executable, str(RUNTIME), "control-packet", "--tree", str(tree), "--node", str(closing["id"])]
        )["packet"]
        self.assertEqual(packet["blackboard"][0]["key"], "clarification.mode")
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
                "--artifact",
                str(session_artifact),
                "--gate-outcome",
                "confirmed",
                "--decision",
                "Confirm that no material decision remains.",
            ]
        )
        self.start_and_complete(tree, "synthesize-session", artifact=session_artifact)
        self.start_and_complete(tree, "finalize-clarification", artifact=session_artifact)
        summary = self.run_json([sys.executable, str(RUNTIME), "summary", "--tree", str(tree)])
        self.assertEqual(summary["status"], "complete", summary)

    def test_revision_required_clarification_opens_recovery_before_synthesis(self) -> None:
        tree, group_id, session_artifact, map_id = self.initialize_until_seed()
        closing = self.add_gate(
            tree,
            group_id,
            "clarify-revision-required",
            "Confirm no material decision",
            [map_id],
            outcomes=["confirmed", "revision-required"],
        )
        self.complete_seed(tree)
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
                "A material revision is still required.",
                "--validation",
                "clarification remains unresolved",
                "--artifact",
                str(session_artifact),
                "--gate-outcome",
                "revision-required",
                "--decision",
                "Revise the decision map before handoff.",
            ]
        )
        waiting = self.run_json([sys.executable, str(RUNTIME), "summary", "--tree", str(tree)])
        self.assertEqual(
            [item["template_id"] for item in waiting["awaiting_dynamic_groups"]],
            ["clarification-recovery-group"],
            waiting,
        )
        synthesis = self.run_json(
            [sys.executable, str(RUNTIME), "find", "--tree", str(tree), "--template-id", "synthesize-session"]
        )["nodes"][0]
        rejected = subprocess.run(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(synthesis["id"]),
                "--agent",
                "negative-gate-test",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr or rejected.stdout)
        self.assertEqual(json.loads(rejected.stdout)["error"]["code"], "node_not_ready")

        recovery_group = self.run_json(
            [sys.executable, str(RUNTIME), "find", "--tree", str(tree), "--template-id", "clarification-recovery-group"]
        )["nodes"][0]
        recovered = self.add_gate(
            tree,
            Path(str(recovery_group["id"])),
            "clarify-recovered",
            "Confirm recovered clarification",
            [str(closing["id"])],
            outcomes=["confirmed", "revision-required"],
        )
        self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(recovered["id"]),
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
                str(recovered["id"]),
                "--summary",
                "Confirmed recovered clarification.",
                "--validation",
                "no material decision remains",
                "--set",
                "clarification.status=ready",
                "--set",
                "clarification.pending_material=false",
                "--artifact",
                str(session_artifact),
                "--gate-outcome",
                "confirmed",
                "--decision",
                "Confirm the revised decision map.",
            ]
        )
        self.start_and_complete(tree, "synthesize-session", artifact=session_artifact)
        self.start_and_complete(tree, "finalize-clarification", artifact=session_artifact)
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
