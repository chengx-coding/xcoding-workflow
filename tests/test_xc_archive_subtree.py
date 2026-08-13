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


class ArchiveSubtreeCliTests(unittest.TestCase):
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

    def run_cli_validation(self, *args: str, cwd: Path) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_CLI), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def run_git(self, repository: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout.strip()

    def write_template(self, path: Path, config: dict[str, object]) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": "archive-subtree"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Archive Subtree",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(workflow, "children")
        phase_a = ET.SubElement(
            children,
            "node",
            {
                "template_id": "phase-a",
                "title": "Phase A",
                "type": "composite",
                "role": "phase-a",
                "mode": "sequence",
                "executor": "main",
            },
        )
        phase_a_children = ET.SubElement(phase_a, "children")
        ET.SubElement(
            phase_a_children,
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
                "template_id": "archive-group",
                "title": "Archive Group",
                "type": "composite",
                "role": "dynamic-group",
                "mode": "sequence",
                "executor": "main",
            },
        )
        phase_b = ET.SubElement(
            children,
            "node",
            {
                "template_id": "phase-b",
                "title": "Phase B",
                "type": "composite",
                "role": "phase-b",
                "mode": "sequence",
                "executor": "main",
            },
        )
        phase_b_children = ET.SubElement(phase_b, "children")
        ET.SubElement(
            phase_b_children,
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

    def create_runtime(
        self,
        project: Path,
        work_order_id: str,
        auto_commit: bool,
    ) -> tuple[Path, Path]:
        context = project / ".xcoding"
        context.mkdir(parents=True)
        if auto_commit:
            self.run_git(context, "init")
            self.run_git(context, "config", "user.name", "XC Test")
            self.run_git(context, "config", "user.email", "xc-test@example.invalid")
        (context / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": auto_commit}}) + "\n",
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
            str(context / "work-orders" / work_order_id / "runtime"),
            "--work-order-id",
            work_order_id,
            cwd=project,
        )
        return context, Path(str(initialized["tree_path"]))

    def node_by_template(self, project: Path, tree_path: Path, template_id: str) -> dict[str, object]:
        return self.run_cli(
            "find",
            "--tree",
            str(tree_path),
            "--template-id",
            template_id,
            cwd=project,
        )["nodes"][0]

    def complete_first_ready(
        self,
        project: Path,
        tree_path: Path,
        *,
        artifacts: tuple[Path, ...] = (),
        sets: tuple[str, ...] = (),
    ) -> dict[str, object]:
        node_id = str(self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]["id"])
        self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
        argv = ["complete", "--tree", str(tree_path), "--node", node_id]
        for artifact in artifacts:
            argv.extend(["--artifact", str(artifact)])
        for entry in sets:
            argv.extend(["--set", entry])
        return self.run_cli(*argv, cwd=project)

    def integrity_status(self, project: Path, tree_path: Path) -> str:
        return str(
            self.run_cli("integrity-status", "--tree", str(tree_path), cwd=project)["integrity"]["status"]
        )

    def write_dependent_template(self, path: Path, config: dict[str, object]) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": "dependent-archive"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Dependent Archive",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(workflow, "children")
        phase_a = ET.SubElement(
            children,
            "node",
            {
                "template_id": "phase-a",
                "title": "Phase A",
                "type": "composite",
                "role": "phase-a",
                "mode": "sequence",
                "executor": "main",
            },
        )
        phase_a_children = ET.SubElement(phase_a, "children")
        ET.SubElement(
            phase_a_children,
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
                "template_id": "finish",
                "title": "Finish",
                "type": "task",
                "role": "finish",
                "executor": "main",
                "depends_on_template": "local:prepare",
            },
        )
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def test_archive_refuses_subtree_with_live_dependents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.json").write_text(
                json.dumps({"git": {"auto_commit": False}}) + "\n",
                encoding="utf-8",
            )
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_dependent_template(template, config)
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-path",
                str(context / "work-orders" / "dependent" / "runtime"),
                "--work-order-id",
                "dependent",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            before = tree_path.read_bytes()

            refused = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(refused["error"]["code"], "archive_dependency_target")
            self.assertEqual(tree_path.read_bytes(), before)

    def test_archive_roundtrip_replaces_subtree_with_stub_and_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, tree_path = self.create_runtime(project, "roundtrip", auto_commit=False)
            artifact_dir = context / "work-orders" / "roundtrip" / "artifacts"
            artifact_dir.mkdir(parents=True)
            artifact = artifact_dir / "report.md"
            artifact.write_text("# Phase A report\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(artifact,), sets=("progress.a=done",))
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            prepare_id = str(self.node_by_template(project, tree_path, "prepare")["id"])

            archived = self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Phase A is complete and closed for scheduling.",
                cwd=project,
            )
            self.assertEqual(archived["operation"], "archive-subtree")
            self.assertEqual(archived["node"]["id"], phase_a_id)
            self.assertEqual(archived["node"]["status"], "archived")
            self.assertEqual(archived["node"]["template_id"], "phase-a")
            self.assertEqual(archived["node"]["role"], "phase-a")
            self.assertEqual(archived["archived_subtrees"], 1)
            self.assertNotIn("archived", archived["counts"])
            self.assertEqual(archived["counts"]["running"], 1)
            self.assertEqual(archived["counts"]["pending"], 3)

            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["archived_subtrees"], 1)
            self.assertNotIn("archived", summary["counts"])
            self.assertEqual(summary["ready"], [])
            self.assertEqual(
                [item["id"] for item in summary["awaiting_dynamic_groups"]],
                [str(self.node_by_template(project, tree_path, "archive-group")["id"])],
            )

            found = self.run_cli("find", "--tree", str(tree_path), "--template-id", "phase-a", cwd=project)
            self.assertEqual(len(found["nodes"]), 1)
            stub = found["nodes"][0]
            self.assertEqual(stub["status"], "archived")
            record = stub["archived_record"]
            self.assertEqual(record["record"]["id"], phase_a_id)
            self.assertEqual(record["record"]["status"], "succeeded")
            record_children = record["record"]["children"]
            self.assertEqual(len(record_children), 1)
            self.assertEqual(record_children[0]["id"], prepare_id)
            self.assertNotIn("summary", record_children[0]["result"])
            self.assertEqual(record_children[0]["result"]["artifacts"], [str(artifact)])
            self.assertEqual(record["reason"], "Phase A is complete and closed for scheduling.")

            shown = self.run_cli("show", "--tree", str(tree_path), "--node", phase_a_id, cwd=project)
            self.assertEqual(shown["node"]["status"], "archived")
            self.assertEqual(shown["archived_record"]["record"]["status"], "succeeded")

            self.assertEqual(self.integrity_status(project, tree_path), "valid")
            validated = self.run_cli("validate", "--tree", str(tree_path), cwd=project)
            self.assertTrue(validated["valid"], validated["errors"])

            parsed = core.parse_xml(tree_path)
            root = parsed.getroot()
            registry = core.archived_registry(root)
            self.assertIsNotNone(registry)
            entries = registry.findall(core.ARCHIVED_ENTRY_TAG)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry.get("id"), phase_a_id)
            self.assertEqual(entry.get("reason"), "Phase A is complete and closed for scheduling.")
            record_xml = ET.fromstring((entry.text or "").strip())
            self.assertEqual(record_xml.tag, "node")
            self.assertEqual(record_xml.get("id"), phase_a_id)
            record_children = core.children(record_xml)
            self.assertEqual(len(record_children), 1)
            self.assertEqual(record_children[0].get("id"), prepare_id)

            live_ids = core.nodes_by_id(root)
            self.assertIn(phase_a_id, live_ids)
            self.assertNotIn(prepare_id, live_ids)
            stub_element = live_ids[phase_a_id]
            self.assertEqual(stub_element.get("status"), "archived")
            self.assertEqual(stub_element.get("archived.record_id"), phase_a_id)
            self.assertEqual(stub_element.get("archived_reason"), "Phase A is complete and closed for scheduling.")

    def test_archive_refuses_root_and_missing_and_pending_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "refusals", auto_commit=False)
            before = tree_path.read_bytes()
            root_id = str(self.node_by_template(project, tree_path, "root")["id"])

            refused_root = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                root_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(refused_root["error"]["code"], "archive_root_refused")
            self.assertEqual(tree_path.read_bytes(), before)

            missing = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                "rt_refusals__root__missing",
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(missing["error"]["code"], "archive_node_not_found")
            self.assertEqual(tree_path.read_bytes(), before)

            phase_b_id = str(self.node_by_template(project, tree_path, "phase-b")["id"])
            pending = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_b_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(pending["error"]["code"], "archive_status_refused")
            self.assertEqual(tree_path.read_bytes(), before)

    def test_archive_refuses_closed_group_with_ready_or_running_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "active-leaves", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            group_id = str(self.node_by_template(project, tree_path, "archive-group")["id"])
            self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "dyn-work",
                "--title",
                "Dynamic work",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.run_cli("close-group", "--tree", str(tree_path), "--group", group_id, cwd=project)
            dyn_work_id = str(self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]["id"])
            before = tree_path.read_bytes()

            ready_leaf = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                group_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(ready_leaf["error"]["code"], "archive_ready_leaf")
            self.assertEqual(
                ready_leaf["error"]["details"]["leaves"][0]["id"],
                dyn_work_id,
            )
            self.assertEqual(tree_path.read_bytes(), before)

            self.run_cli("start", "--tree", str(tree_path), "--node", dyn_work_id, cwd=project)
            running_leaf = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                group_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(running_leaf["error"]["code"], "archive_running_leaf")
            self.assertEqual(
                running_leaf["error"]["details"]["leaves"][0]["id"],
                dyn_work_id,
            )

    def test_archive_requires_reason_and_respects_expected_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "guards", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            before = tree_path.read_bytes()
            current_revision = int(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["revision"])

            empty_reason = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "   ",
                cwd=project,
            )
            self.assertEqual(empty_reason["error"]["code"], "archive_reason_required")
            self.assertEqual(tree_path.read_bytes(), before)

            conflicted = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "cleanup",
                "--expected-revision",
                str(current_revision + 5),
                cwd=project,
            )
            self.assertEqual(conflicted["error"]["code"], "state_conflict")
            self.assertEqual(tree_path.read_bytes(), before)

            accepted = self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "cleanup with matching revision",
                "--expected-revision",
                str(current_revision),
                cwd=project,
            )
            self.assertEqual(int(accepted["revision"]), current_revision + 1)

    def test_archived_artifacts_remain_discoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, tree_path = self.create_runtime(project, "artifact-visibility", auto_commit=False)
            artifact_dir = context / "work-orders" / "artifact-visibility" / "artifacts"
            artifact_dir.mkdir(parents=True)
            artifact = artifact_dir / "evidence.md"
            artifact.write_text("# Evidence\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(artifact,))
            prepare_id = str(self.node_by_template(project, tree_path, "prepare")["id"])
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Phase A closed.",
                cwd=project,
            )

            listed = self.run_cli("artifacts", "--tree", str(tree_path), cwd=project)["artifacts"]
            entries = [entry for entry in listed if entry["path"] == str(artifact)]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["node_id"], prepare_id)
            self.assertTrue(entries[0]["archived"])

    def test_scheduling_excludes_archived_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "scheduling", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            group_id = str(self.node_by_template(project, tree_path, "archive-group")["id"])
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "First archive.",
                cwd=project,
            )
            self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "dyn-work",
                "--title",
                "Dynamic work",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.run_cli("close-group", "--tree", str(tree_path), "--group", group_id, cwd=project)
            self.complete_first_ready(project, tree_path)
            second = self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                group_id,
                "--reason",
                "Second archive.",
                cwd=project,
            )
            self.assertEqual(second["archived_subtrees"], 2)
            self.assertNotIn("archived", second["counts"])

            next_payload = self.run_cli("next", "--tree", str(tree_path), cwd=project)
            self.assertEqual(len(next_payload["ready"]), 1)
            self.assertEqual(next_payload["ready"][0]["template_id"], "finish")
            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["archived_subtrees"], 2)
            self.assertNotIn("archived", summary["counts"])

            double_archive = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "again",
                cwd=project,
            )
            self.assertEqual(double_archive["error"]["code"], "archive_status_refused")

            readonly_stub = self.run_cli_error(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "late-work",
                "--title",
                "Late work",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.assertEqual(readonly_stub["error"]["code"], "archived_stub_read_only")

            shown = self.run_cli("show", "--tree", str(tree_path), "--node", group_id, cwd=project)
            record_children = shown["archived_record"]["record"]["children"]
            self.assertEqual(record_children[0]["logical_key"], "dyn-work")

            self.complete_first_ready(project, tree_path)
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            final_counts = self.run_cli("summary", "--tree", str(tree_path), cwd=project)["counts"]
            self.assertNotIn("archived", final_counts)

            phase_b_id = str(self.node_by_template(project, tree_path, "phase-b")["id"])
            sealed = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_b_id,
                "--reason",
                "after seal",
                cwd=project,
            )
            self.assertEqual(sealed["error"]["code"], "tree_sealed")

    def test_archive_refuses_subtree_containing_archived_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "nested-refusal", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            group_id = str(self.node_by_template(project, tree_path, "archive-group")["id"])
            self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "dyn-work",
                "--title",
                "Dynamic work",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.run_cli("close-group", "--tree", str(tree_path), "--group", group_id, cwd=project)
            dyn_work_id = str(self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]["id"])
            self.complete_first_ready(project, tree_path)
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                dyn_work_id,
                "--reason",
                "Archive the inner task first.",
                cwd=project,
            )
            before = tree_path.read_bytes()

            refused = self.run_cli_error(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                group_id,
                "--reason",
                "cleanup",
                cwd=project,
            )
            self.assertEqual(refused["error"]["code"], "archive_nested_archived_stub")
            self.assertEqual(refused["error"]["details"]["nested_stubs"], [dyn_work_id])
            self.assertEqual(tree_path.read_bytes(), before)
            self.assertEqual(self.integrity_status(project, tree_path), "valid")

    def test_archived_stubs_refuse_all_four_mutating_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "readonly-guards", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Archive phase-a stub.",
                cwd=project,
            )
            group_id = str(self.node_by_template(project, tree_path, "archive-group")["id"])
            self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "dyn-work",
                "--title",
                "Dynamic work",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.run_cli("close-group", "--tree", str(tree_path), "--group", group_id, cwd=project)
            self.complete_first_ready(project, tree_path)
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                group_id,
                "--reason",
                "Archive group stub.",
                cwd=project,
            )
            template = project / "template.xml"
            before = tree_path.read_bytes()

            add_phase_stub = self.run_cli_error(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                phase_a_id,
                "--logical-key",
                "late-a",
                "--title",
                "Late A",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.assertEqual(add_phase_stub["error"]["code"], "archived_stub_read_only")
            self.assertEqual(tree_path.read_bytes(), before)

            add_group_stub = self.run_cli_error(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "late-b",
                "--title",
                "Late B",
                "--type",
                "task",
                "--executor",
                "main",
                cwd=project,
            )
            self.assertEqual(add_group_stub["error"]["code"], "archived_stub_read_only")
            self.assertEqual(tree_path.read_bytes(), before)

            embed_stub = self.run_cli_error(
                "embed-subtree",
                "--tree",
                str(tree_path),
                "--parent",
                phase_a_id,
                "--template",
                str(template),
                cwd=project,
            )
            self.assertEqual(embed_stub["error"]["code"], "archived_stub_read_only")
            self.assertEqual(tree_path.read_bytes(), before)

            close_stub = self.run_cli_error(
                "close-group",
                "--tree",
                str(tree_path),
                "--group",
                group_id,
                cwd=project,
            )
            self.assertEqual(close_stub["error"]["code"], "archived_stub_read_only")
            self.assertEqual(tree_path.read_bytes(), before)

            reopen_stub = self.run_cli_error(
                "reopen-group",
                "--tree",
                str(tree_path),
                "--group",
                group_id,
                "--reason",
                "recovery",
                cwd=project,
            )
            self.assertEqual(reopen_stub["error"]["code"], "archived_stub_read_only")
            self.assertEqual(tree_path.read_bytes(), before)
            self.assertEqual(self.integrity_status(project, tree_path), "valid")

    def reseal_tampered_tree(self, tree_path: Path, mutate) -> None:
        parsed = core.parse_xml(tree_path)
        root = parsed.getroot()
        mutate(root)
        config = core.load_config(tree_path)
        core.apply_integrity(root, "runtime", config)
        core.atomic_write_text(tree_path, core.serialize_xml(root, "runtime"))

    def test_repair_integrity_restores_recoverable_recordless_stub_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "recoverable-link", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Archive phase-a.",
                cwd=project,
            )

            def corrupt_entry_id(root) -> None:
                entry = core.archived_registry(root).findall(core.ARCHIVED_ENTRY_TAG)[0]
                entry.set("id", "corrupted-id")

            self.reseal_tampered_tree(tree_path, corrupt_entry_id)

            validated = self.run_cli_validation("validate", "--tree", str(tree_path), cwd=project)
            self.assertFalse(validated["valid"])
            self.assertIn(
                f"archived stub {phase_a_id} has no matching registry entry for record {phase_a_id}",
                validated["errors"],
            )

            repaired = self.run_cli(
                "repair-integrity",
                "--tree",
                str(tree_path),
                "--reason",
                "Restore the recoverable registry link.",
                cwd=project,
            )
            self.assertEqual(
                repaired["archived_registry_repairs"],
                [{"stub_id": phase_a_id, "entry_id": phase_a_id}],
            )
            self.assertEqual(self.integrity_status(project, tree_path), "valid")
            revalidated = self.run_cli("validate", "--tree", str(tree_path), cwd=project)
            self.assertTrue(revalidated["valid"], revalidated["errors"])

    def test_repair_integrity_rejects_unrecoverable_recordless_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "unrecoverable-link", auto_commit=False)
            self.complete_first_ready(project, tree_path)
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Archive phase-a.",
                cwd=project,
            )

            def strip_entry(root) -> None:
                registry = core.archived_registry(root)
                entry = registry.findall(core.ARCHIVED_ENTRY_TAG)[0]
                registry.remove(entry)

            self.reseal_tampered_tree(tree_path, strip_entry)

            validated = self.run_cli_validation("validate", "--tree", str(tree_path), cwd=project)
            self.assertFalse(validated["valid"])
            self.assertIn(
                f"archived stub {phase_a_id} has no matching registry entry for record {phase_a_id}",
                validated["errors"],
            )

            before = tree_path.read_bytes()
            rejected = self.run_cli_error(
                "repair-integrity",
                "--tree",
                str(tree_path),
                "--reason",
                "Attempt an unrecoverable repair.",
                cwd=project,
            )
            self.assertEqual(rejected["error"]["code"], "archived_stub_record_missing")
            self.assertEqual(tree_path.read_bytes(), before)

    def test_archive_is_deterministic_and_integrity_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "determinism", auto_commit=False)
            self.complete_first_ready(project, tree_path, sets=("progress.a=done",))
            phase_a_id = str(self.node_by_template(project, tree_path, "phase-a")["id"])
            before_tree = core.parse_xml(tree_path)
            expected_record = ET.tostring(
                core.nodes_by_id(before_tree.getroot())[phase_a_id],
                encoding="unicode",
            ).strip()

            self.run_cli(
                "archive-subtree",
                "--tree",
                str(tree_path),
                "--subtree",
                phase_a_id,
                "--reason",
                "Deterministic archive.",
                cwd=project,
            )
            self.assertEqual(self.integrity_status(project, tree_path), "valid")

            parsed = core.parse_xml(tree_path)
            root = parsed.getroot()
            entries = core.archived_registry(root).findall(core.ARCHIVED_ENTRY_TAG)
            self.assertEqual(len(entries), 1)
            self.assertEqual((entries[0].text or "").strip(), expected_record)

            first = core.serialize_xml(root, "runtime")
            second = core.serialize_xml(root, "runtime")
            self.assertEqual(first, second)
            reparsed = ET.fromstring(first)
            self.assertEqual(
                core.calculate_checksum(reparsed),
                core.calculate_checksum(parsed.getroot()),
            )


if __name__ == "__main__":
    unittest.main()
