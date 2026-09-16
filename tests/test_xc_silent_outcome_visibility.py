"""Unit 2 - the two outcomes that used to happen with no record at all.

Both are fail-open, not fail-closed: the runtime permitted the action and said nothing. Neither
change here alters what is permitted; each only makes the unexpected case distinguishable from
the intended one, so a reviewer can tell them apart after the fact.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
RUNTIME_CLI = REPOSITORY_ROOT / "tests" / "runtime_cli.py"

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.runtime import core


class SilentOutcomeVisibilityTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_CLI), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def run_cli_error(self, *args: str, cwd: Path) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_CLI), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def write_template(self, path: Path, config: dict[str, object]) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": "visibility"})
        blackboard = ET.SubElement(root, "blackboard")
        # `published.flag` is written and false. `unwritten.flag` is declared nowhere, which is
        # the whole point: the two guards below are textually identical and resolve the same way.
        ET.SubElement(blackboard, "var", {"key": "published.flag"}).text = "false"
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Visibility",
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
                "template_id": "guarded-by-published-key",
                "title": "Guarded by a published key",
                "type": "task",
                "role": "worker",
                "executor": "main",
                "when": "published.flag == true",
            },
        )
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "guarded-by-unwritten-key",
                "title": "Guarded by an unwritten key",
                "type": "task",
                "role": "worker",
                "executor": "main",
                "when": "unwritten.flag == true",
            },
        )
        phase = ET.SubElement(
            children,
            "node",
            {
                "template_id": "phase",
                "title": "Phase",
                "type": "composite",
                "role": "phase",
                "mode": "sequence",
                "executor": "main",
            },
        )
        phase_children = ET.SubElement(phase, "children")
        ET.SubElement(
            phase_children,
            "node",
            {
                "template_id": "inner",
                "title": "Inner",
                "type": "task",
                "role": "worker",
                "executor": "main",
            },
        )
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "recovery-group",
                "title": "Recovery Group",
                "type": "composite",
                "role": "dynamic-group",
                "mode": "sequence",
                "executor": "main",
            },
        )
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def create_runtime(self, project: Path) -> Path:
        context = project / ".xcoding"
        context.mkdir(parents=True)
        (context / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        config = core.load_config(context)
        template = project / "template.xml"
        self.write_template(template, config)
        initialized = self.run_cli(
            "init",
            "--template",
            str(template),
            "--runtime-path",
            str(context / "work-orders" / "visibility" / "runtime"),
            "--work-order-id",
            "visibility",
            cwd=project,
        )
        return Path(str(initialized["tree_path"]))

    def node_by_template(self, project: Path, tree_path: Path, template_id: str) -> dict[str, object]:
        return self.run_cli(
            "find", "--tree", str(tree_path), "--template-id", template_id, cwd=project
        )["nodes"][0]

    def test_unwritten_guard_key_is_distinguishable_from_a_false_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            tree_path = self.create_runtime(project)

            published = self.node_by_template(project, tree_path, "guarded-by-published-key")
            unwritten = self.node_by_template(project, tree_path, "guarded-by-unwritten-key")

            # Both are skipped, and before this change both looked identical.
            self.assertEqual(published["status"], "skipped")
            self.assertEqual(unwritten["status"], "skipped")
            self.assertEqual(published["attributes"]["skip_reason"], "when")
            self.assertEqual(unwritten["attributes"]["skip_reason"], "when")

            # Only the unwritten one names the key nobody published.
            self.assertNotIn("skip_unwritten_key", published["attributes"])
            self.assertEqual(
                unwritten["attributes"]["skip_unwritten_key"],
                "unwritten.flag",
            )

    def test_publishing_the_missing_key_clears_the_unwritten_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            tree_path = self.create_runtime(project)

            self.run_cli("set", "--tree", str(tree_path), "--set", "unwritten.flag=true", cwd=project)
            recovered = self.node_by_template(project, tree_path, "guarded-by-unwritten-key")
            self.assertEqual(recovered["status"], "pending")
            self.assertNotIn("skip_unwritten_key", recovered["attributes"])

            # Publishing it as false is an intentional skip, so it carries no marker either.
            self.run_cli("set", "--tree", str(tree_path), "--set", "unwritten.flag=false", cwd=project)
            intentional = self.node_by_template(project, tree_path, "guarded-by-unwritten-key")
            self.assertEqual(intentional["status"], "skipped")
            self.assertEqual(intentional["attributes"]["skip_reason"], "when")
            self.assertNotIn("skip_unwritten_key", intentional["attributes"])

    def test_marking_an_unwritten_skip_keeps_the_tree_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            tree_path = self.create_runtime(project)
            self.run_cli("validate", "--tree", str(tree_path), cwd=project)
            self.assertEqual(
                self.run_cli("integrity-status", "--tree", str(tree_path), cwd=project)["integrity"][
                    "status"
                ],
                "valid",
            )

    def test_add_node_under_a_failed_ancestor_succeeds_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            tree_path = self.create_runtime(project)

            inner_id = str(self.node_by_template(project, tree_path, "inner")["id"])
            self.run_cli(
                "start", "--tree", str(tree_path), "--node", inner_id, "--agent", "tester", cwd=project
            )
            self.run_cli(
                "fail", "--tree", str(tree_path), "--node", inner_id, "--reason", "induced", cwd=project
            )

            group_id = str(self.node_by_template(project, tree_path, "recovery-group")["id"])
            added = self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "rescue",
                "--title",
                "Rescue",
                "--type",
                "task",
                "--role",
                "worker",
                "--executor",
                "main",
                cwd=project,
            )

            # The append still succeeds: building recovery work before clearing the ancestor is
            # legitimate, and refusing it would remove a working pattern.
            self.assertTrue(added["ok"])
            warning = added["warning"]
            self.assertEqual(warning["code"], "node_not_currently_schedulable")
            self.assertTrue(str(warning["reason"]).startswith("ancestor_"))
            self.assertTrue(warning["blocker_node_id"])
            self.assertIn(warning["blocker_status"], {"failed", "blocked"})

            # And the warning is accurate: the node really cannot start yet.
            refused = self.run_cli_error(
                "start",
                "--tree",
                str(tree_path),
                "--node",
                str(added["node"]["id"]),
                "--agent",
                "tester",
                cwd=project,
            )
            self.assertEqual(refused["error"]["code"], "node_not_ready")

    def test_add_node_under_a_healthy_ancestor_carries_no_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            tree_path = self.create_runtime(project)
            group_id = str(self.node_by_template(project, tree_path, "recovery-group")["id"])

            added = self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "ordinary",
                "--title",
                "Ordinary",
                "--type",
                "task",
                "--role",
                "worker",
                "--executor",
                "main",
                cwd=project,
            )
            self.assertNotIn("warning", added)


if __name__ == "__main__":
    unittest.main()
