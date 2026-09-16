from __future__ import annotations

import importlib
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
WORKFLOWS = (
    (
        "document-evolution",
        REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-template.xml",
        "write-document",
    ),
    (
        "workshop-setup",
        REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-template.xml",
        "prepare-workshop",
    ),
    (
        "new-feature",
        REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-template.xml",
        "prepare-feature",
    ),
    (
        "feature-adoption",
        REPOSITORY_ROOT / "skills" / "xc-feature-adoption" / "assets" / "feature-adoption-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-feature-adoption" / "assets" / "feature-adoption-template.xml",
        "prepare-adoption",
    ),
    (
        "work",
        REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-template.xml",
        "prepare-work-order",
    ),
    (
        "feature-reconciliation",
        REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-template.xml",
        "load-feature-provenance",
    ),
    (
        "clarify",
        REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-template.xml",
        "open-session-record",
    ),
    (
        "change-report",
        REPOSITORY_ROOT / "skills" / "xc-change-report" / "assets" / "change-report-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-change-report" / "assets" / "change-report-template.xml",
        "prepare-manifest",
    ),
)

# The thirteen caller-seeded report keys, frozen by name and declared default by section 8 of
# the solution decision. The work-order and new-feature trees declare exactly this set so an
# embedded report subtree's guards, loop condition and completion-fact selectors can resolve
# every key they read; the generated template must carry the same set, not only the spec.
FROZEN_CALLER_KEYS = {
    "report.path": "",
    "report.manifest_path": "",
    "report.baseline_commit": "",
    "report.baseline_digest": "",
    "report.language": "en",
    "report.strength": "standard",
    "report.gate_required": "false",
    "report.gate_outcome": "not-run",
    "report.gate_rework_required": "false",
    "report.gate_recovery_required": "false",
    "report.round": "1",
    "report.refresh_count": "0",
    "report.refresh_reason": "initial",
}

# The templates the shared table does not carry, each covered by its own dedicated
# byte-reproducibility test. `test_every_skill_template_has_a_byte_reproducibility_owner`
# proves the map is complete and that each named owner really compares a fresh build of the
# spec against that template's bytes, so a new template with neither owner fails this module
# instead of silently shipping an unverified generated file.
DEDICATED_TEMPLATE_TESTS = {
    "skills/xc-work/assets/jit-milestone-template.xml": (
        "tests.test_xc_jit_milestone",
        "JitMilestoneTests",
        "test_flow_rebuilds_current_template",
    ),
    "skills/xc-work/assets/adaptive-work-order-template.xml": (
        "tests.test_xc_adaptive_work_order",
        "AdaptiveWorkOrderTests",
        "test_flow_rebuilds_current_template",
    ),
}


class XcLifecycleTemplateTests(unittest.TestCase):
    def run_json(self, command: list[str]) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_flow_specs_rebuild_current_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            for name, spec, template, _ in WORKFLOWS:
                code, payload = self.run_json([sys.executable, str(AUTHOR), "validate-spec", "--spec", str(spec)])
                self.assertEqual(code, 0, (name, payload))
                self.assertTrue(payload["valid"], (name, payload))

                rebuilt = root / f"{name}.xml"
                code, payload = self.run_json(
                    [
                        sys.executable,
                        str(AUTHOR),
                        "build",
                        "--spec",
                        str(spec),
                        "--out",
                        str(rebuilt),
                        "--config",
                        str(config),
                    ]
                )
                self.assertEqual(code, 0, (name, payload))
                self.assertEqual(rebuilt.read_bytes(), template.read_bytes(), name)

    def test_templates_initialize_and_expose_first_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workshop = root / ".xcoding"
            workshop.mkdir()
            (workshop / "xc-orchestration-runtime.json").write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            for name, _, template, first_template_id in WORKFLOWS:
                runtime_path = workshop / "work-orders" / name / "runtime"
                code, initialized = self.run_json(
                    [
                        sys.executable,
                        str(RUNTIME),
                        "init",
                        "--template",
                        str(template),
                        "--runtime-path",
                        str(runtime_path),
                        "--work-order-id",
                        f"20260727-1000-{name}",
                    ]
                )
                self.assertEqual(code, 0, (name, initialized))
                code, next_payload = self.run_json(
                    [sys.executable, str(RUNTIME), "next", "--tree", str(initialized["tree_path"])]
                )
                self.assertEqual(code, 0, (name, next_payload))
                self.assertEqual(next_payload["ready"][0]["template_id"], first_template_id, name)

    def test_work_skill_is_canonical_and_previous_package_is_absent(self) -> None:
        work_skill = REPOSITORY_ROOT / "skills" / "xc-work"
        self.assertTrue(work_skill.is_dir())
        self.assertFalse((REPOSITORY_ROOT / "skills" / "xc-work-order").exists())
        self.assertIn('name: "xc-work"', (work_skill / "SKILL.md").read_text(encoding="utf-8"))

    @staticmethod
    def node_children(node: ET.Element) -> list[str]:
        """The template_id of each direct child node, in declaration order."""
        wrapper = node.find("children")
        if wrapper is None:
            return []
        return [
            str(child.get("template_id"))
            for child in wrapper
            if child.tag == "node"
        ]

    def test_new_feature_row_mounts_the_report_stage(self) -> None:
        """G-10: the new-feature row's generated template carries a flat report stage.

        Before this work order the new-feature specification and its template contained zero
        `report` matches, so the row initialised a lifecycle whose change set no report stage
        could describe. The assertion is made on a fresh build of the row's own specification —
        an artifact this test produces — and the byte comparison ties that artifact to the
        shipped template, so no managed file is read structurally.
        """
        _, spec, template, _ = next(
            row for row in WORKFLOWS if row[0] == "new-feature"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(
                json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8"
            )
            rebuilt = root / "new-feature.xml"
            code, payload = self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(spec),
                    "--out",
                    str(rebuilt),
                    "--config",
                    str(config),
                ]
            )
            self.assertEqual(code, 0, payload)
            self.assertEqual(rebuilt.read_bytes(), template.read_bytes(), "new-feature")

            document = ET.parse(rebuilt).getroot()
            groups = [
                node
                for node in document.iter("node")
                if node.get("template_id") == "report-group"
            ]
            self.assertEqual(len(groups), 1, "exactly one report stage on this lifecycle")
            group = groups[0]
            self.assertEqual(group.get("type"), "composite")
            self.assertEqual(group.get("role"), "dynamic-group")
            self.assertEqual(group.get("mode"), "sequence")
            self.assertEqual(group.get("executor"), "main")
            self.assertEqual(group.get("when"), "work_order.requires_report == true")
            self.assertEqual(
                self.node_children(group),
                [],
                "the mount is flat: the report subtree is embedded under it at run time",
            )

            continuation = next(
                node
                for node in document.iter("node")
                if node.get("template_id") == "approved-baseline-continuation"
            )
            self.assertEqual(
                self.node_children(continuation),
                [
                    "implementation-group",
                    "verification-group",
                    "report-group",
                    "result-document",
                    "finalize-feature",
                ],
                "the report stage runs after verification and before the result document",
            )

            blackboard = document.find("blackboard")
            self.assertIsNotNone(blackboard, "the template must declare a blackboard")
            declared = {
                str(entry.get("key")): entry.text or "" for entry in blackboard
            }
            missing = sorted(
                key for key in FROZEN_CALLER_KEYS if key not in declared
            )
            self.assertEqual(
                missing,
                [],
                "the generated template must declare every caller-seeded report key, because "
                "an embedded subtree's guards read this tree's blackboard and nothing else",
            )
            for key, value in FROZEN_CALLER_KEYS.items():
                self.assertEqual(declared[key], value, key)

    def test_every_skill_template_has_a_byte_reproducibility_owner(self) -> None:
        """Every template under `skills/` is rebuilt from its spec and byte-compared.

        The plan requires a byte-reproducibility assertion for every template in the tree. Eight
        are rows of `WORKFLOWS`; the other two are owned by their own dedicated tests. This test
        makes that coverage mechanical in both directions: an unowned template fails, and a
        named owner whose module does not point its `TEMPLATE` constant at that template or does
        not compare raw bytes fails too.
        """
        table = {
            template.relative_to(REPOSITORY_ROOT).as_posix()
            for _, _, template, _ in WORKFLOWS
        }
        discovered = {
            path.relative_to(REPOSITORY_ROOT).as_posix()
            for path in (REPOSITORY_ROOT / "skills").rglob("*-template.xml")
        }
        self.assertGreater(len(discovered), 0, "no templates discovered under skills/")
        self.assertEqual(
            discovered - table,
            set(DEDICATED_TEMPLATE_TESTS),
            "every template under skills/ must be covered by the shared table or by a named "
            "dedicated test",
        )
        for relative, (module_name, class_name, method_name) in sorted(
            DEDICATED_TEMPLATE_TESTS.items()
        ):
            with self.subTest(template=relative):
                module = importlib.import_module(module_name)
                self.assertEqual(
                    Path(module.TEMPLATE).resolve(),
                    (REPOSITORY_ROOT / relative).resolve(),
                    f"{module_name}.TEMPLATE must name the template it covers",
                )
                owner = getattr(module, class_name)
                method = getattr(owner, method_name)
                self.assertTrue(callable(method))
                source = inspect.getsource(method)
                self.assertIn("read_bytes()", source)
                self.assertIn(
                    "TEMPLATE.read_bytes()",
                    source,
                    f"{module_name}.{class_name}.{method_name} must byte-compare a fresh "
                    "build against the tracked template",
                )


if __name__ == "__main__":
    unittest.main()
