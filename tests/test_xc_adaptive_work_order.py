from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = ROOT / "tests" / "runtime_cli.py"
PLANNER_SCRIPTS = ROOT / "skills" / "xc-work" / "scripts"
SPEC = ROOT / "skills" / "xc-work" / "assets" / "adaptive-work-order-flow.json"
TEMPLATE = ROOT / "skills" / "xc-work" / "assets" / "adaptive-work-order-template.xml"
WORK_SKILL = ROOT / "skills" / "xc-work" / "SKILL.md"
CHANGE_REPORT_TEMPLATE = (
    ROOT / "skills" / "xc-change-report" / "assets" / "change-report-template.xml"
)
sys.path.insert(0, str(PLANNER_SCRIPTS))

import plan_work_policy as policy

# The declared source key G-37 made enforceable, and a well-formed
# `commit:digest:algorithm` value that satisfies it without implying a real capture.
BASELINE_KEY = "work_order.report_baseline"
BASELINE_VALUE = (
    "ac583c3646122ae35159c64c8c7143def4f17885:"
    "cf190d29e21631fade7e12783febbe6614c02d37bf2c98b5b0f8fac31289f7aa:"
    "sha256(path-nul-contenthash-lf/v1)"
)


class AdaptiveWorkOrderTests(unittest.TestCase):
    def run_raw(self, script: Path, *arguments: str) -> tuple[int, dict[str, object]]:
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
        return completed.returncode, payload

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
        runtime_path = workshop / "work-orders" / "adaptive" / "runtime"
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(TEMPLATE),
            "--runtime-path",
            str(runtime_path),
            "--work-order-id",
            "20260803-0000-adaptive",
            "--name",
            "Adaptive Test",
        )
        return Path(str(initialized["tree_path"])), workshop

    def find_group(self, tree: Path) -> str:
        payload = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            "work-group",
        )
        return str(payload["nodes"][0]["id"])

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
            self.assertTrue(validated["valid"])
            rebuilt = root / "adaptive.xml"
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

    def test_initial_tree_is_only_an_open_planned_work_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree, _ = self.environment(Path(temporary))
            payload = self.run_json(RUNTIME, "next", "--tree", str(tree))
            self.assertEqual(payload["ready"], [])
            self.assertEqual(
                [item["template_id"] for item in payload["awaiting_dynamic_groups"]],
                ["work-group"],
            )
            self.assertEqual(payload["counts"], {"pending": 2})

    def test_minimal_managed_path_has_the_plan_required_leaves(self) -> None:
        """Corrected fixture: the finalizer publishes the report's declared source key.

        The finalizer previously declared `blackboard_keys=["work_order.plan_id"]` and the tree
        published no baseline, so the manifest was accepted only because G-37's check did not
        exist: the plan's `report` node declares `work_order.report_baseline`, and an
        unpublished declared key is now refused with `missing_required_source_key`. The
        baseline is published on the live tree and projected into the finalizer's packet, and
        the packet is asserted to carry it.
        """
        with tempfile.TemporaryDirectory() as temporary:
            tree, workshop = self.environment(Path(temporary))
            group = self.find_group(tree)
            artifact = (
                workshop
                / "work-orders"
                / "adaptive"
                / "artifacts"
                / "combined-work.md"
            )
            worker = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--logical-key",
                "implementation-1",
                "--title",
                "Implement and verify",
                "--type",
                "task",
                "--role",
                "implementation",
                "--executor",
                "subagent",
                "--instructions",
                "Apply the exact bounded edit and run focused verification.",
                "--deliverables",
                str(artifact),
                "--acceptance",
                "The requested change and focused verification both succeed.",
                "--metadata",
                'metadata.completion.required_fields=["summary","validation"]',
                "--metadata",
                "metadata.completion.artifacts.min=1",
                "--metadata",
                "metadata.completion.artifacts.max=1",
                "--metadata",
                f"metadata.completion.artifacts.path=literal:{artifact}",
            )
            worker_id = str(worker["node"]["id"])
            report_artifact = (
                workshop
                / "work-orders"
                / "adaptive"
                / "artifacts"
                / "change-report.html"
            )
            reporter = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--logical-key",
                "report",
                "--title",
                "Produce change report",
                "--type",
                "task",
                "--role",
                "report",
                "--executor",
                "subagent",
                "--instructions",
                "Produce the minimal-strength change report from the recorded baseline.",
                "--deliverables",
                str(report_artifact),
                "--acceptance",
                "The report covers every analyzable change unit of this work order.",
                "--metadata",
                'metadata.completion.required_fields=["summary","validation"]',
                "--metadata",
                "metadata.completion.artifacts.min=1",
                "--metadata",
                "metadata.completion.artifacts.max=1",
                "--metadata",
                f"metadata.completion.artifacts.path=literal:{report_artifact}",
            )
            reporter_id = str(reporter["node"]["id"])
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f'adaptive.sources.implementation-1=["{worker_id}"]',
                "--set",
                f'adaptive.sources.report=["{reporter_id}"]',
                "--set",
                "work_order.plan_id=" + "a" * 64,
                "--set",
                f"{BASELINE_KEY}={BASELINE_VALUE}",
            )
            finalizer = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--logical-key",
                "finalize",
                "--title",
                "Finalize adaptive work",
                "--type",
                "task",
                "--role",
                "work-order-finalize",
                "--executor",
                "main",
                "--instructions",
                "Confirm planned sources, verification, and residual risk.",
                "--deliverables",
                "A sealed adaptive work order.",
                "--acceptance",
                "Every plan-required source and check is accepted.",
                "--metadata",
                'metadata.control_packet.category.plan-implementation-1.selectors=["bb:adaptive.sources.implementation-1"]',
                "--metadata",
                "metadata.control_packet.category.plan-implementation-1.min_sources=1",
                "--metadata",
                "metadata.control_packet.category.plan-implementation-1.artifact_min=1",
                "--metadata",
                'metadata.control_packet.category.plan-report.selectors=["bb:adaptive.sources.report"]',
                "--metadata",
                "metadata.control_packet.category.plan-report.min_sources=1",
                "--metadata",
                "metadata.control_packet.category.plan-report.artifact_min=1",
                "--metadata",
                'metadata.control_packet.blackboard_keys=["work_order.plan_id","'
                + BASELINE_KEY
                + '"]',
                "--metadata",
                'metadata.completion.required_fields=["summary","validation"]',
            )
            finalizer_id = str(finalizer["node"]["id"])
            self.run_json(
                RUNTIME,
                "close-group",
                "--tree",
                str(tree),
                "--group",
                group,
            )
            self.run_json(
                RUNTIME,
                "start",
                "--tree",
                str(tree),
                "--node",
                worker_id,
                "--agent",
                "combined-worker",
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Combined work\n\nFocused verification passed.\n", encoding="utf-8")
            self.run_json(
                RUNTIME,
                "complete",
                "--tree",
                str(tree),
                "--node",
                worker_id,
                "--summary",
                "Implemented the exact change.",
                "--validation",
                "Focused verification passed.",
                "--artifact",
                str(artifact),
            )
            self.run_json(
                RUNTIME,
                "start",
                "--tree",
                str(tree),
                "--node",
                reporter_id,
                "--agent",
                "report-author",
            )
            report_artifact.write_text(
                "<!doctype html><html lang=\"en\"></html>\n",
                encoding="utf-8",
            )
            self.run_json(
                RUNTIME,
                "complete",
                "--tree",
                str(tree),
                "--node",
                reporter_id,
                "--summary",
                "Produced the minimal-strength change report.",
                "--validation",
                "Coverage validation passed.",
                "--artifact",
                str(report_artifact),
            )
            facts = {
                "needs_persistence": "yes",
                "material_impact": "yes",
                "difficult_rollback": "no",
                "crosses_sessions": "no",
                "multiple_actors": "no",
                "audit_required": "no",
                "bridge_policy": "none",
                "scope": "single-location",
                "clarity": "exact",
                "risk": "low",
                "verification": "focused",
                "coordination": "single",
                "duration": "single-step",
                "audit": "runtime-only",
                "pace": "fast",
                "mode": "change",
                "request": "Change one local constant.",
                "bridge_sha256": "",
            }
            bridge = workshop / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts["bridge_sha256"] = hashlib.sha256(
                bridge.read_bytes()
            ).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f"work_order.plan_id={receipt['plan_id']}",
            )
            source_map = {
                "implementation-1": {
                    "node_id": worker_id,
                },
                "report": {
                    "node_id": reporter_id,
                },
            }
            packet = self.run_json(
                RUNTIME,
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                finalizer_id,
            )
            projected = {
                item["key"]: item["value"]
                for item in packet["packet"]["blackboard"]
            }
            self.assertEqual(
                projected.get(BASELINE_KEY),
                BASELINE_VALUE,
                "the finalizer's projection must carry the published baseline, which is the "
                "declared source key G-37 requires",
            )
            self.assertEqual(projected.get("work_order.plan_id"), receipt["plan_id"])
            manifest = self.run_json(
                PLANNER_SCRIPTS / "validate_adaptive_manifest.py",
                "--receipt-json",
                json.dumps(receipt, separators=(",", ":")),
                "--source-map-json",
                json.dumps(source_map, separators=(",", ":")),
                "--packet-json",
                json.dumps(packet, separators=(",", ":")),
                "--request",
                facts["request"],
                "--bridge",
                str(bridge),
            )
            self.assertEqual(manifest["source_ids"], [worker_id, reporter_id])
            self.assertEqual(manifest["min_sources"], 2)
            self.assertEqual(manifest["artifact_min"], 2)
            self.assertEqual(
                [
                    category["sources"][0]["node_id"]
                    for category in packet["packet"]["source_categories"]
                ],
                [worker_id, reporter_id],
            )
            self.assertEqual(
                [
                    category["sources"][0]["logical_key"]
                    for category in packet["packet"]["source_categories"]
                ],
                ["implementation-1", "report"],
            )
            self.run_json(
                RUNTIME,
                "start",
                "--tree",
                str(tree),
                "--node",
                finalizer_id,
                "--agent",
                "main-session",
            )
            completed = self.run_json(
                RUNTIME,
                "complete",
                "--tree",
                str(tree),
                "--node",
                finalizer_id,
                "--summary",
                "Accepted all planned work.",
                "--validation",
                "Required source and focused verification evidence are present.",
            )
            self.assertEqual(completed["counts"]["succeeded"], 5)
            summary = self.run_json(RUNTIME, "summary", "--tree", str(tree))
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["counts"]["succeeded"], 5)

    def test_embed_after_a_successful_leaf_is_sealed_and_documented(self) -> None:
        """G-21: the report node must exist before the first leaf starts, and the page says so.

        The runtime half is decisive against the pre-change tree only as a property of the
        engine (`core.py` `is_runtime_sealed`/`require_runtime_mutable`), which is not what this
        work order changed; what was missing is the *statement*, because the shipped sentence
        placed the report node "after the implementation and verification nodes" and said
        nothing about the moment it is added. Both halves are asserted here so the documented
        constraint and the mechanism it describes are pinned together.
        """
        adaptive = self.adaptive_section()
        self.assertIn("before the first leaf starts", adaptive)
        self.assertIn("a successful leaf seals the tree", adaptive)
        self.assertIn("tree_sealed", adaptive)
        self.assertIn("sequence position", adaptive)
        self.assertNotIn(
            "Embed the `xc-change-report` subtree once after the implementation "
            "and verification nodes",
            adaptive,
        )
        with tempfile.TemporaryDirectory() as temporary:
            tree, workshop = self.environment(Path(temporary))
            group = self.find_group(tree)
            artifact = (
                workshop
                / "work-orders"
                / "adaptive"
                / "artifacts"
                / "combined-work.md"
            )
            worker = self.run_json(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--logical-key",
                "implementation-1",
                "--title",
                "Implement and verify",
                "--type",
                "task",
                "--role",
                "implementation",
                "--executor",
                "subagent",
                "--instructions",
                "Apply the exact bounded edit and run focused verification.",
                "--deliverables",
                str(artifact),
                "--acceptance",
                "The requested change and focused verification both succeed.",
                "--metadata",
                'metadata.completion.required_fields=["summary","validation"]',
            )
            worker_id = str(worker["node"]["id"])
            self.run_json(
                RUNTIME,
                "close-group",
                "--tree",
                str(tree),
                "--group",
                group,
            )
            self.run_json(
                RUNTIME,
                "start",
                "--tree",
                str(tree),
                "--node",
                worker_id,
                "--agent",
                "combined-worker",
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "# Combined work\n\nFocused verification passed.\n", encoding="utf-8"
            )
            self.run_json(
                RUNTIME,
                "complete",
                "--tree",
                str(tree),
                "--node",
                worker_id,
                "--summary",
                "Implemented the exact change.",
                "--validation",
                "Focused verification passed.",
                "--artifact",
                str(artifact),
            )
            self.assertEqual(
                self.run_json(RUNTIME, "summary", "--tree", str(tree))["status"],
                "complete",
                "completing every planned leaf seals the tree",
            )

            # A plan-required node appended after the leaf succeeded is refused, which is the
            # mechanism the page's constraint describes.
            code, payload = self.run_raw(
                RUNTIME,
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--logical-key",
                "report",
                "--title",
                "Produce change report",
                "--type",
                "task",
                "--role",
                "report",
                "--executor",
                "subagent",
                "--instructions",
                "Produce the change report from the recorded baseline.",
                "--deliverables",
                str(workshop / "work-orders" / "adaptive" / "artifacts" / "change-report.html"),
                "--acceptance",
                "The report covers every analyzable change unit.",
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "tree_sealed")

            # Embedding the report subtree after the leaf succeeded is refused by the same
            # guard, so neither supported form can be added late.
            code, payload = self.run_raw(
                RUNTIME,
                "embed-subtree",
                "--tree",
                str(tree),
                "--parent",
                group,
                "--template",
                str(CHANGE_REPORT_TEMPLATE),
                "--instance-id",
                "report",
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "tree_sealed")

            # The blackboard write the report leaf would have needed is refused as well: the
            # sealed tree cannot be repaired into a reportable state after the fact.
            code, payload = self.run_raw(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f"{BASELINE_KEY}={BASELINE_VALUE}",
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "tree_sealed")

    def adaptive_section(self) -> str:
        """The adaptive contract text, so the assertion is scoped to this path's paragraph."""
        text = WORK_SKILL.read_text(encoding="utf-8")
        start = text.index("## Adaptive Run Operation")
        end = text.index("## Run Operation")
        return text[start:end]

    def test_sequence_group_exposes_only_the_first_planned_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree, _ = self.environment(Path(temporary))
            group = self.find_group(tree)
            ids: list[str] = []
            for key, role in (
                ("analysis", "analysis"),
                ("implementation", "implementation"),
                ("verification", "verification"),
            ):
                added = self.run_json(
                    RUNTIME,
                    "add-node",
                    "--tree",
                    str(tree),
                    "--parent",
                    group,
                    "--logical-key",
                    key,
                    "--title",
                    key.title(),
                    "--type",
                    "task",
                    "--role",
                    role,
                    "--executor",
                    "subagent",
                    "--instructions",
                    f"Execute planned {key} work.",
                    "--deliverables",
                    f"An artifact for {key}.",
                    "--acceptance",
                    f"Planned {key} acceptance is satisfied.",
                )
                ids.append(str(added["node"]["id"]))
            payload = self.run_json(RUNTIME, "next", "--tree", str(tree), "--limit", "5")
            self.assertEqual([item["id"] for item in payload["ready"]], [ids[0]])


if __name__ == "__main__":
    unittest.main()
