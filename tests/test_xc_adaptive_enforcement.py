"""Enforcement tests for the adaptive planner's report declaration (U7).

Gaps covered: G-17, G-18, G-19, G-20, G-21, G-22, G-23, G-34, G-37.

Each decisive assertion is written so that it fails against the pre-change tree;
the docstrings name which half is decisive and which half is regression-only,
because a probe that also passes before the change proves nothing on its own.
"""

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
CHANGE_REPORT_SCRIPTS = ROOT / "skills" / "xc-change-report" / "scripts"
ADAPTIVE_SPEC = ROOT / "skills" / "xc-work" / "assets" / "adaptive-work-order-flow.json"
ADAPTIVE_TEMPLATE = (
    ROOT / "skills" / "xc-work" / "assets" / "adaptive-work-order-template.xml"
)
WORK_SKILL = ROOT / "skills" / "xc-work" / "SKILL.md"
VALIDATOR = PLANNER_SCRIPTS / "validate_adaptive_manifest.py"
sys.path.insert(0, str(PLANNER_SCRIPTS))
sys.path.insert(0, str(CHANGE_REPORT_SCRIPTS))

import build_manifest  # noqa: E402
import plan_work_policy as policy  # noqa: E402


# The frozen interface strings of the solution decision, section 8.
REPORT_ARTIFACT_NAME = "change-report.html"
BASELINE_KEY = "work_order.report_baseline"
BASELINE_VALUE = (
    "ac583c3646122ae35159c64c8c7143def4f17885:"
    "cf190d29e21631fade7e12783febbe6614c02d37bf2c98b5b0f8fac31289f7aa:"
    "sha256(path-nul-contenthash-lf/v1)"
)
# The adaptive blackboard declares the report commitment vocabulary plus the
# three keys the report stage is driven by. The three `report.*` values are the
# report specification's own declared defaults (`change-report-flow.json`), so
# the same key never carries two different declared values in two lifecycles.
DECLARED_VOCABULARY = {
    "work_order.requires_report": "true",
    "work_order.report_skip_reason": "",
    "work_order.report_baseline": "",
    "report.path": "",
    "report.strength": "standard",
    "report.round": "1",
}
REPORT_STRENGTH_TOKEN = "REPORT_" + "STRENGTH_GRADES"


class AdaptiveEnforcementTests(unittest.TestCase):
    def base_facts(self) -> dict[str, str]:
        return {
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
            "request": "Change one local constant and run its focused check.",
            "bridge_sha256": "a" * 64,
        }

    def run_raw(
        self, script: Path, *arguments: str
    ) -> tuple[int, dict[str, object]]:
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
        except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
            self.fail((completed.returncode, completed.stdout, completed.stderr, exc))
        return completed.returncode, payload

    def run_json(self, script: Path, *arguments: str) -> dict[str, object]:
        code, payload = self.run_raw(script, *arguments)
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        return payload

    def bridge_and_receipt(self, root: Path):
        bridge = root / "WORKFLOW.md"
        bridge.write_text("# Workflow\n", encoding="utf-8")
        facts = self.base_facts()
        facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
        return bridge, facts, policy.build_plan(facts)["plan_receipt"]

    def report_packet(
        self,
        receipt: dict[str, object],
        *,
        baseline: str | None,
        report_artifacts: list[str],
        report_source: dict[str, object] | None = None,
    ) -> dict[str, object]:
        blackboard = [{"key": "work_order.plan_id", "value": receipt["plan_id"]}]
        if baseline is not None:
            blackboard.append({"key": BASELINE_KEY, "value": baseline})
        source = report_source or {
            "node_id": "rt_report",
            "logical_key": "report",
            "role": "report",
            "status": "succeeded",
            "artifacts": list(report_artifacts),
        }
        return {
            "packet": {
                "target": {"logical_key": "finalize", "role": "work-order-finalize"},
                "blackboard": blackboard,
                "source_categories": [
                    {
                        "name": "plan-implementation-1",
                        "sources": [
                            {
                                "node_id": "rt_impl",
                                "logical_key": "implementation-1",
                                "role": "implementation",
                                "status": "succeeded",
                                "artifacts": ["work.md"],
                            }
                        ],
                    },
                    {"name": "plan-report", "sources": [source]},
                ],
            }
        }

    def validate(
        self,
        bridge: Path,
        facts: dict[str, str],
        receipt: dict[str, object],
        source_map: dict[str, object],
        packet: dict[str, object],
    ) -> tuple[int, dict[str, object]]:
        return self.run_raw(
            VALIDATOR,
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

    def environment(self, root: Path) -> tuple[Path, str, Path]:
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
            str(ADAPTIVE_TEMPLATE),
            "--runtime-path",
            str(runtime_path),
            "--work-order-id",
            "20260915-2215-adaptive-enforcement",
            "--name",
            "Adaptive Enforcement",
        )
        tree = Path(str(initialized["tree_path"]))
        group = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            "work-group",
        )
        return tree, str(group["nodes"][0]["id"]), workshop

    def add_leaf(
        self,
        tree: Path,
        group: str,
        *,
        logical_key: str,
        role: str,
        artifact: Path,
        blackboard_keys: tuple[str, ...] = (),
        consumes: str = "",
    ) -> str:
        arguments = [
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            group,
            "--logical-key",
            logical_key,
            "--title",
            logical_key.title(),
            "--type",
            "task",
            "--role",
            role,
            "--executor",
            "subagent",
            "--instructions",
            f"Execute the planned {logical_key} work.",
            "--deliverables",
            str(artifact),
            "--acceptance",
            f"The planned {logical_key} acceptance is satisfied.",
        ]
        metadata: list[str] = []
        category = "plan-implementation-1"
        if blackboard_keys or consumes:
            metadata.append(
                "metadata.control_packet.blackboard_keys="
                + json.dumps(list(blackboard_keys), separators=(",", ":"))
            )
        if consumes:
            metadata.extend(
                (
                    f"metadata.control_packet.category.{category}.selectors="
                    + json.dumps([consumes], separators=(",", ":")),
                    f"metadata.control_packet.category.{category}.min_sources=1",
                    f"metadata.control_packet.category.{category}.artifact_min=1",
                )
            )
        for entry in metadata:
            arguments.extend(("--metadata", entry))
        added = self.run_json(RUNTIME, *arguments)
        return str(added["node"]["id"])

    def publish_source(self, tree: Path, logical_key: str, node: str) -> None:
        self.run_json(
            RUNTIME,
            "set",
            "--tree",
            str(tree),
            "--set",
            f'adaptive.sources.{logical_key}=["{node}"]',
        )

    def run_leaf(self, tree: Path, node: str, artifact: Path, body: str) -> None:
        """Start and complete one leaf, recording its artifact.

        Every plan-required node must already exist when this runs: a tree whose
        remaining nodes have all succeeded is sealed, and a sealed tree refuses
        both further nodes and further blackboard writes (`tree_sealed`).
        """
        self.run_json(
            RUNTIME,
            "start",
            "--tree",
            str(tree),
            "--node",
            node,
            "--agent",
            "planned-worker",
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(body, encoding="utf-8")
        self.run_json(
            RUNTIME,
            "complete",
            "--tree",
            str(tree),
            "--node",
            node,
            "--summary",
            "Applied the bounded change.",
            "--validation",
            "Focused check passed.",
            "--artifact",
            str(artifact),
        )

    def packet_blackboard(self, tree: Path, node: str) -> dict[str, str]:
        packet = self.run_json(
            RUNTIME,
            "control-packet",
            "--tree",
            str(tree),
            "--node",
            node,
        )
        return {
            str(item["key"]): str(item["value"])
            for item in packet["packet"]["blackboard"]
        }

    def adaptive_section(self) -> str:
        text = WORK_SKILL.read_text(encoding="utf-8")
        start = text.index("## Adaptive Run Operation")
        end = text.index("## Run Operation")
        return text[start:end]

    def test_adaptive_template_declares_the_report_vocabulary(self) -> None:
        """G-17: decisive half is the declared key set.

        Fails pre-change: the spec declares none of the six keys, so the first
        assertion raises. The `grep -c report` half is decisive as well (zero
        matching lines today); the live-tree half re-proves that the rebuilt
        template carries the same declared values the spec declares.
        """
        spec = json.loads(ADAPTIVE_SPEC.read_text(encoding="utf-8"))
        declared = spec["blackboard"]
        for key, value in DECLARED_VOCABULARY.items():
            self.assertIn(key, declared, key)
            self.assertEqual(declared[key], value, key)
        for asset in (ADAPTIVE_SPEC, ADAPTIVE_TEMPLATE):
            matching = [
                line
                for line in asset.read_text(encoding="utf-8").splitlines()
                if "report" in line
            ]
            self.assertGreater(len(matching), 0, asset.name)
        with tempfile.TemporaryDirectory() as temporary:
            tree, _, _ = self.environment(Path(temporary))
            summary = self.run_json(RUNTIME, "summary", "--tree", str(tree))
            for key in declared:
                self.assertIn(key, summary["blackboard"], key)
            for key, value in DECLARED_VOCABULARY.items():
                self.assertEqual(summary["blackboard"][key], value, key)

    def test_report_artifact_name_is_enforced(self) -> None:
        """G-18: a report slot bound to a non-report artifact must fail.

        Fails pre-change: the negative packet exits 0 today, because only the
        artifact count was checked.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge, facts, receipt = self.bridge_and_receipt(root)
            report = next(
                item
                for item in receipt["required_nodes"]
                if item["logical_key"] == "report"
            )
            self.assertEqual(
                report["required_artifact_name"], REPORT_ARTIFACT_NAME
            )
            source_map = {
                "implementation-1": {"node_id": "rt_impl"},
                "report": {"node_id": "rt_report"},
            }
            code, payload = self.validate(
                bridge,
                facts,
                receipt,
                source_map,
                self.report_packet(
                    receipt, baseline=BASELINE_VALUE, report_artifacts=["notes.txt"]
                ),
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "report_artifact_mismatch")
            for delivered in (
                REPORT_ARTIFACT_NAME,
                "C:\\wb\\artifacts\\rt_report\\" + REPORT_ARTIFACT_NAME,
                "/wb/artifacts/rt_report/" + REPORT_ARTIFACT_NAME,
            ):
                with self.subTest(delivered=delivered):
                    code, payload = self.validate(
                        bridge,
                        facts,
                        receipt,
                        source_map,
                        self.report_packet(
                            receipt,
                            baseline=BASELINE_VALUE,
                            report_artifacts=[delivered],
                        ),
                    )
                    self.assertEqual(code, 0, payload)
                    self.assertTrue(payload["ok"])

    def test_subtree_form_is_recorded_as_unsupported(self) -> None:
        """G-19 + G-20: the shipped sentence states the measured mechanism.

        Decisive half: the page text. Pre-change it offers both forms and claims
        both produce exactly one report, which the mechanism refutes.
        Regression-only half: the validator already refuses a subtree root bound
        as the plan's report source, so this half passes before the change too.
        """
        adaptive = self.adaptive_section()
        self.assertIn("only supported form", adaptive)
        self.assertIn("role=report", adaptive)
        self.assertIn("cannot bind a subtree root", adaptive)
        self.assertNotIn("both forms produce exactly one report", adaptive)
        self.assertNotIn(
            "Embed the `xc-change-report` subtree once after the implementation "
            "and verification nodes",
            adaptive,
        )
        self.assertIn("before the first leaf starts", adaptive)
        self.assertIn("sequence position", adaptive)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge, facts, receipt = self.bridge_and_receipt(root)
            code, payload = self.validate(
                bridge,
                facts,
                receipt,
                {"implementation-1": {"node_id": "rt_impl"}, "report": {"node_id": "rt_subtree"}},
                self.report_packet(
                    receipt,
                    baseline=BASELINE_VALUE,
                    report_artifacts=[],
                    report_source={
                        "node_id": "rt_subtree",
                        "logical_key": "",
                        "role": "root",
                        "status": "succeeded",
                        "artifacts": [REPORT_ARTIFACT_NAME],
                    },
                ),
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "invalid_packet_source")
            self.assertEqual(payload["error"]["keys"], ["report"])

    def test_report_strength_reaches_the_report_packet(self) -> None:
        """G-22: the strength tier must have a declared carrier and reach the node.

        Decisive half: the first control-packet request, before anything is
        published. Pre-change it exits non-zero with `blackboard_key_missing`,
        because the adaptive tree declares no `report.strength`; the declared
        default now resolves it. The second half asserts that publishing the
        receipt's own tier replaces the default in the same packet.
        """
        spec = json.loads(ADAPTIVE_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["blackboard"]["report.strength"], "standard")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree, group, workshop = self.environment(root)
            artifacts = workshop / "work-orders" / "adaptive" / "artifacts"
            implementation = self.add_leaf(
                tree,
                group,
                logical_key="implementation-1",
                role="implementation",
                artifact=artifacts / "work.md",
            )
            reporter = self.add_leaf(
                tree,
                group,
                logical_key="report",
                role="report",
                artifact=artifacts / REPORT_ARTIFACT_NAME,
                blackboard_keys=("report.strength", "report.path"),
                consumes="bb:adaptive.sources.implementation-1",
            )
            self.publish_source(tree, "implementation-1", implementation)
            self.run_leaf(tree, implementation, artifacts / "work.md", "# Change\n")
            declared = self.packet_blackboard(tree, reporter)
            self.assertEqual(declared["report.strength"], "standard")
            tier = policy.build_plan(self.base_facts())["plan_receipt"][
                "report_strength"
            ]
            self.assertTrue(tier)
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f"report.strength={tier}",
            )
            published = self.packet_blackboard(tree, reporter)
            self.assertEqual(published["report.strength"], tier)
            self.assertTrue(published["report.strength"])

    def test_adaptive_ordering_is_declared_as_main_session_policy(self) -> None:
        """G-23: the ordering claim is policy, and a review leaf can read the report.

        Decisive half: `report.path` is declared on the adaptive tree and the
        page says the ordering has no runtime mechanism. Pre-change the spec
        declares no `report.path`, so the first packet request cannot even name
        the key.
        """
        adaptive = self.adaptive_section()
        self.assertRegex(adaptive, r"main-session policy with no runtime mechanism")
        self.assertIn("review leaf can read the report", adaptive)
        spec = json.loads(ADAPTIVE_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["blackboard"]["report.path"], "")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree, group, workshop = self.environment(root)
            artifacts = workshop / "work-orders" / "adaptive" / "artifacts"
            implementation = self.add_leaf(
                tree,
                group,
                logical_key="implementation-1",
                role="implementation",
                artifact=artifacts / "work.md",
            )
            reviewer = self.add_leaf(
                tree,
                group,
                logical_key="review-1",
                role="review",
                artifact=artifacts / "review.md",
                blackboard_keys=("report.path",),
                consumes="bb:adaptive.sources.implementation-1",
            )
            self.publish_source(tree, "implementation-1", implementation)
            self.run_leaf(tree, implementation, artifacts / "work.md", "# Change\n")
            self.assertEqual(self.packet_blackboard(tree, reviewer)["report.path"], "")
            report_path = str(
                workshop
                / "work-orders"
                / "adaptive"
                / "artifacts"
                / REPORT_ARTIFACT_NAME
            )
            self.run_json(
                RUNTIME,
                "set",
                "--tree",
                str(tree),
                "--set",
                f"report.path={report_path}",
            )
            self.assertEqual(
                self.packet_blackboard(tree, reviewer)["report.path"], report_path
            )

    def test_strength_vocabulary_has_one_named_owner(self) -> None:
        """G-34: one live strength vocabulary, owned by the report package.

        Fails pre-change: a tracked-content `git grep` for the retired tuple's
        name returns its definition line in `plan_work_policy.py`. That name is
        assembled at run time and never written contiguously in this file, so
        the test cannot make its own assertion fail once it is tracked.
        """
        completed = subprocess.run(
            ["git", "grep", "-n", REPORT_STRENGTH_TOKEN],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.returncode, 1, completed.stderr)
        planner_source = (PLANNER_SCRIPTS / "plan_work_policy.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(REPORT_STRENGTH_TOKEN, planner_source)
        self.assertEqual(build_manifest.STRENGTHS, ("minimal", "standard", "full"))
        for overrides, expected in (
            ({"risk": "low", "audit": "runtime-only"}, "minimal"),
            ({"risk": "medium", "audit": "runtime-only"}, "standard"),
            ({"risk": "high", "audit": "runtime-only"}, "full"),
        ):
            facts = self.base_facts()
            facts.update(overrides)
            self.assertIn(
                policy.derive_report_strength(facts), build_manifest.STRENGTHS
            )
            self.assertEqual(policy.derive_report_strength(facts), expected)

    def test_manifest_validation_requires_a_published_source_key(self) -> None:
        """G-37: a declared source key must be present and non-empty.

        Fails pre-change: both negative packets exit 0 today, because the
        validator never read `source_keys`.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge, facts, receipt = self.bridge_and_receipt(root)
            report = next(
                item
                for item in receipt["required_nodes"]
                if item["logical_key"] == "report"
            )
            self.assertEqual(report["source_keys"], [BASELINE_KEY])
            source_map = {
                "implementation-1": {"node_id": "rt_impl"},
                "report": {"node_id": "rt_report"},
            }
            for baseline in (None, ""):
                with self.subTest(baseline=baseline):
                    code, payload = self.validate(
                        bridge,
                        facts,
                        receipt,
                        source_map,
                        self.report_packet(
                            receipt,
                            baseline=baseline,
                            report_artifacts=[REPORT_ARTIFACT_NAME],
                        ),
                    )
                    self.assertEqual(code, 2, payload)
                    self.assertEqual(
                        payload["error"]["code"], "missing_required_source_key"
                    )
                    self.assertEqual(payload["error"]["keys"], [BASELINE_KEY])
            code, payload = self.validate(
                bridge,
                facts,
                receipt,
                source_map,
                self.report_packet(
                    receipt,
                    baseline=BASELINE_VALUE,
                    report_artifacts=[REPORT_ARTIFACT_NAME],
                ),
            )
            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["min_sources"], 2)

    def test_adaptive_spec_rebuilds_the_tracked_template(self) -> None:
        """U7's template-rebuild obligation: the tracked XML is generated output.

        This duplicates `tests/test_xc_adaptive_work_order.py`'s byte-identity
        assertion on purpose, so U7 owns a rebuild proof for the spec it edited.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(
                json.dumps({"git": {"auto_commit": False}}) + "\n",
                encoding="utf-8",
            )
            validated = self.run_json(
                AUTHOR, "validate-spec", "--spec", str(ADAPTIVE_SPEC)
            )
            self.assertTrue(validated["valid"])
            rebuilt = root / "adaptive.xml"
            self.run_json(
                AUTHOR,
                "build",
                "--spec",
                str(ADAPTIVE_SPEC),
                "--out",
                str(rebuilt),
                "--config",
                str(config),
            )
            self.assertEqual(rebuilt.read_bytes(), ADAPTIVE_TEMPLATE.read_bytes())


if __name__ == "__main__":
    unittest.main()
