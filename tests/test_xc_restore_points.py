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
from xcoding.runtime import restore_points


class RestorePointCliTests(unittest.TestCase):
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
        root = ET.Element("orchestration", {"schema_version": "1", "name": "restore-points"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Restore Points",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(workflow, "children")
        for template_id, title in (("prepare", "Prepare"), ("finish", "Finish")):
            ET.SubElement(
                children,
                "node",
                {
                    "template_id": template_id,
                    "title": title,
                    "type": "task",
                    "role": template_id,
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

    def restore_point_directory(self, tree_path: Path, restore_point_id: str) -> Path:
        return tree_path.parent / "restore-points" / restore_point_id

    def integrity_status(self, project: Path, tree_path: Path) -> str:
        return str(
            self.run_cli("integrity-status", "--tree", str(tree_path), cwd=project)["integrity"]["status"]
        )

    def test_create_list_and_restore_roundtrip_reverts_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, tree_path = self.create_runtime(project, "roundtrip", auto_commit=False)
            self.complete_first_ready(project, tree_path, sets=("progress.state=prepared",))
            prepare_id = str(self.node_by_template(project, tree_path, "prepare")["id"])

            created = self.run_cli(
                "restore-point",
                "create",
                "--tree",
                str(tree_path),
                "--name",
                "after-prepare",
                cwd=project,
            )
            restore_point_id = str(created["restore_point"]["id"])
            self.assertTrue(restore_points.RESTORE_POINT_ID_RE.fullmatch(restore_point_id))
            self.assertEqual(created["restore_point"]["name"], "after-prepare")
            restore_dir = self.restore_point_directory(tree_path, restore_point_id)
            self.assertTrue((restore_dir / "manifest.json").is_file())
            self.assertTrue((restore_dir / "tree.xml").is_file())
            stored_manifest = json.loads((restore_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(stored_manifest["id"], restore_point_id)
            self.assertEqual(stored_manifest["tree_sha256"], created["restore_point"]["tree_sha256"])
            self.assertEqual(
                stored_manifest["tree_sha256"],
                restore_points.sha256_file(restore_dir / "tree.xml"),
            )

            second = self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)
            second_id = str(second["restore_point"]["id"])

            listed = self.run_cli("restore-point", "list", "--tree", str(tree_path), cwd=project)
            entries = listed["restore_points"]
            self.assertEqual({entry["id"] for entry in entries}, {restore_point_id, second_id})
            self.assertEqual(
                entries,
                sorted(entries, key=lambda item: (str(item.get("created_at", "")), str(item.get("id", "")))),
            )
            self.assertTrue(all(entry["status"] == "valid" for entry in entries))
            self.assertEqual(listed, self.run_cli("restore-point", "list", "--tree", str(tree_path), cwd=project))

            self.complete_first_ready(project, tree_path)
            sealed_revision = int(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["revision"])
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")

            restored = self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "The user approved reverting the finish completion.",
                cwd=project,
            )
            self.assertEqual(restored["operation"], "restore-point-restore")
            self.assertEqual(restored["restore_point_id"], restore_point_id)
            self.assertEqual(restored["epoch"], "1")
            self.assertGreater(int(restored["revision"]), sealed_revision)

            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertNotEqual(summary["status"], "complete")
            self.assertEqual(self.node_by_template(project, tree_path, "prepare")["status"], "succeeded")
            self.assertEqual(self.node_by_template(project, tree_path, "finish")["status"], "pending")
            self.assertEqual(summary["blackboard"]["progress.state"], "prepared")
            self.assertEqual(self.run_cli("snapshot", "--tree", str(tree_path), cwd=project)["metadata"]["epoch"], "1")
            self.assertEqual(self.integrity_status(project, tree_path), "valid")

            parsed = core.parse_xml(tree_path)
            root = parsed.getroot()
            meta = core.find_meta(root)
            history = core.find_direct(meta, "restore_history")
            restores = history.findall("restore")
            self.assertEqual(len(restores), 1)
            self.assertEqual(restores[0].get("restore_point_id"), restore_point_id)
            self.assertEqual(restores[0].get("reason"), "The user approved reverting the finish completion.")
            self.assertEqual(restores[0].get("previous_revision"), str(sealed_revision))
            self.assertIn(prepare_id, core.nodes_by_id(root))

    def test_restore_fails_closed_on_checksum_mismatch_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "fail-closed", auto_commit=False)
            created = self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)
            restore_point_id = str(created["restore_point"]["id"])
            restore_dir = self.restore_point_directory(tree_path, restore_point_id)
            before = tree_path.read_bytes()

            tampered_tree = restore_dir / "tree.xml"
            tampered_tree.write_bytes(tampered_tree.read_bytes() + b"tampered")

            mismatched = self.run_cli_error(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "recovery",
                cwd=project,
            )
            self.assertEqual(mismatched["error"]["code"], "restore_point_checksum_mismatch")
            self.assertEqual(tree_path.read_bytes(), before)

            tampered_tree.unlink()
            missing = self.run_cli_error(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "recovery",
                cwd=project,
            )
            self.assertEqual(missing["error"]["code"], "restore_point_file_missing")
            self.assertEqual(tree_path.read_bytes(), before)

    def test_restore_rejects_unknown_and_invalid_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "unknown-ids", auto_commit=False)
            self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)

            unknown = self.run_cli_error(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                "rp_20200101-000000_00000000",
                "--reason",
                "recovery",
                cwd=project,
            )
            self.assertEqual(unknown["error"]["code"], "restore_point_not_found")

            for invalid_id in ("garbage", "../escape", "RP_20200101-000000_00000000", "rp_20200101-000000_xyz"):
                with self.subTest(invalid_id=invalid_id):
                    invalid = self.run_cli_error(
                        "restore-point",
                        "restore",
                        "--tree",
                        str(tree_path),
                        "--restore-point",
                        invalid_id,
                        "--reason",
                        "recovery",
                        cwd=project,
                    )
                    self.assertEqual(invalid["error"]["code"], "restore_point_invalid_id")

    def test_sealed_tree_restore_requires_reason_and_records_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "sealed-restore", auto_commit=False)
            created = self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)
            restore_point_id = str(created["restore_point"]["id"])
            self.complete_first_ready(project, tree_path)
            self.complete_first_ready(project, tree_path)
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            before = tree_path.read_bytes()

            empty_reason = self.run_cli_error(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "   ",
                cwd=project,
            )
            self.assertEqual(empty_reason["error"]["code"], "tree_validation_error")
            self.assertEqual(tree_path.read_bytes(), before)

            restored = self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "The user approved reverting the sealed completion.",
                cwd=project,
            )
            self.assertEqual(restored["epoch"], "1")
            self.assertNotEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            self.assertEqual(self.integrity_status(project, tree_path), "valid")

            mutable = self.run_cli(
                "set",
                "--tree",
                str(tree_path),
                "--set",
                "late.change=true",
                cwd=project,
            )
            self.assertIn("late.change", mutable["blackboard"])

            self.complete_first_ready(project, tree_path)
            self.complete_first_ready(project, tree_path)
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            sealed = self.run_cli(
                "restore-point",
                "create",
                "--tree",
                str(tree_path),
                "--name",
                "sealed-snapshot",
                cwd=project,
            )
            sealed_id = str(sealed["restore_point"]["id"])
            reopened = self.run_cli(
                "reopen",
                "--tree",
                str(tree_path),
                "--reason",
                "Approved post-restore correction.",
                cwd=project,
            )
            self.assertEqual(reopened["epoch"], "2")

            resealed = self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                sealed_id,
                "--reason",
                "The user approved restoring the sealed snapshot.",
                cwd=project,
            )
            self.assertEqual(resealed["epoch"], "3")
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            still_sealed = self.run_cli_error(
                "set",
                "--tree",
                str(tree_path),
                "--set",
                "late.change=true",
                cwd=project,
            )
            self.assertEqual(still_sealed["error"]["code"], "tree_sealed")
            parsed = core.parse_xml(tree_path)
            history = core.find_direct(core.find_meta(parsed.getroot()), "restore_history")
            self.assertEqual(len(history.findall("restore")), 2)

    def test_artifact_restoration_roundtrip_and_manifest_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, tree_path = self.create_runtime(project, "artifact-restore", auto_commit=False)
            artifact_dir = context / "work-orders" / "artifact-restore" / "artifacts"
            artifact_dir.mkdir(parents=True)
            artifact = artifact_dir / "report.md"
            artifact.write_text("# Original report\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(artifact,))

            created = self.run_cli(
                "restore-point",
                "create",
                "--tree",
                str(tree_path),
                "--name",
                "with-report",
                cwd=project,
            )
            restore_point_id = str(created["restore_point"]["id"])
            manifest_artifacts = created["restore_point"]["artifacts"]
            self.assertEqual(len(manifest_artifacts), 1)
            self.assertEqual(manifest_artifacts[0]["path"], str(artifact))
            self.assertEqual(manifest_artifacts[0]["sha256"], restore_points.sha256_file(artifact))
            stored_copy = self.restore_point_directory(tree_path, restore_point_id) / str(
                manifest_artifacts[0]["stored_as"]
            )
            self.assertEqual(stored_copy.read_bytes(), artifact.read_bytes())

            artifact.write_text("# Corrupted\n", encoding="utf-8")
            self.assertNotEqual(artifact.read_bytes(), b"# Original report\n")

            self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "The user approved restoring the original report.",
                cwd=project,
            )
            self.assertEqual(artifact.read_text(encoding="utf-8"), "# Original report\n")
            self.assertEqual(self.integrity_status(project, tree_path), "valid")
            self.assertEqual(
                self.run_cli("artifacts", "--tree", str(tree_path), cwd=project)["artifacts"][0]["path"],
                str(artifact),
            )

    def test_create_requires_valid_tree_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "integrity-gate", auto_commit=False)
            tampered = tree_path.read_text(encoding="utf-8").replace(
                'status="pending"',
                'status="running"',
                1,
            )
            tree_path.write_text(tampered, encoding="utf-8")

            rejected = self.run_cli_error(
                "restore-point",
                "create",
                "--tree",
                str(tree_path),
                cwd=project,
            )
            self.assertEqual(rejected["error"]["code"], "integrity_write_blocked")
            self.assertFalse((tree_path.parent / "restore-points").exists())

    def test_restore_expected_revision_conflict_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "revision-guard", auto_commit=False)
            created = self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)
            restore_point_id = str(created["restore_point"]["id"])
            current_revision = int(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["revision"])
            before = tree_path.read_bytes()

            conflicted = self.run_cli_error(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "recovery",
                "--expected-revision",
                str(current_revision + 5),
                cwd=project,
            )
            self.assertEqual(conflicted["error"]["code"], "state_conflict")
            self.assertEqual(tree_path.read_bytes(), before)

            accepted = self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "recovery with matching revision",
                "--expected-revision",
                str(current_revision),
                cwd=project,
            )
            self.assertEqual(int(accepted["revision"]), current_revision + 1)

    def test_restore_commits_path_scoped_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, tree_path = self.create_runtime(project, "commit-checkpoint", auto_commit=True)
            artifact_dir = context / "work-orders" / "commit-checkpoint" / "artifacts"
            artifact_dir.mkdir(parents=True)
            artifact = artifact_dir / "evidence.md"
            artifact.write_text("# Evidence\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(artifact,))
            created = self.run_cli("restore-point", "create", "--tree", str(tree_path), cwd=project)
            restore_point_id = str(created["restore_point"]["id"])

            artifact.write_text("# Changed\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(artifact,))
            unrelated = context / "unrelated-user-file.md"
            unrelated.write_text("# Preserve me\n", encoding="utf-8")

            restored = self.run_cli(
                "restore-point",
                "restore",
                "--tree",
                str(tree_path),
                "--restore-point",
                restore_point_id,
                "--reason",
                "The user approved the checkpoint recovery.",
                cwd=project,
            )
            self.assertEqual(restored["commit"]["status"], "committed")
            self.assertEqual(artifact.read_text(encoding="utf-8"), "# Evidence\n")
            changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
            self.assertIn("work-orders/commit-checkpoint/runtime/orchestration.xml", changed_paths)
            self.assertIn(artifact.relative_to(context).as_posix(), changed_paths)
            self.assertNotIn("unrelated-user-file.md", changed_paths)

    def test_create_rejects_declared_artifact_outside_workshop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _, tree_path = self.create_runtime(project, "outside-artifact", auto_commit=False)
            outside = Path(temporary) / "outside-workshop.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            self.complete_first_ready(project, tree_path, artifacts=(outside,))

            rejected = self.run_cli_error(
                "restore-point",
                "create",
                "--tree",
                str(tree_path),
                cwd=project,
            )
            self.assertEqual(rejected["error"]["code"], "restore_point_path_violation")
            self.assertFalse((tree_path.parent / "restore-points").exists())


if __name__ == "__main__":
    unittest.main()
