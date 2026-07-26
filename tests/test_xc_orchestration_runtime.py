from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SKILL = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime"
RUNTIME_SCRIPTS = RUNTIME_SKILL / "scripts"
RUNTIME_CLI = RUNTIME_SCRIPTS / "orchestration.py"

sys.path.insert(0, str(RUNTIME_SCRIPTS))
import runtime_core as core


class OrchestrationRuntimeCliTests(unittest.TestCase):
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
        root = ET.Element("orchestration", {"schema_version": "1", "name": "terminal-commit"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Terminal Commit",
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
                "template_id": "write-document",
                "title": "Write document",
                "type": "task",
                "role": "document-write",
                "executor": "main",
            },
        )
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def test_config_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = Path(temporary) / ".xcoding"
            context.mkdir()
            config_path = context / "xc-orchestration-runtime.toml"
            config_path.write_bytes(b"\xef\xbb\xbfschema_version = 1\n[git]\nauto_commit = false\n")

            config = core.load_config(context)

            self.assertFalse(config["git"]["auto_commit"])
            self.assertEqual(config["_source"], str(config_path))

    def test_terminal_checkpoint_rejects_artifact_outside_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            self.run_git(context, "init")
            self.run_git(context, "config", "user.name", "XC Test")
            self.run_git(context, "config", "user.email", "xc-test@example.invalid")
            config_path = context / "xc-orchestration-runtime.toml"
            config_path.write_text("[git]\nauto_commit = true\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            run_id = "20260726-1430-outside-artifact"
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / run_id / "runtime"),
                "--run-id",
                run_id,
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            ready = self.run_cli("next", "--tree", str(tree_path), cwd=project)
            node_id = str(ready["ready"][0]["id"])
            self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            outside_artifact = project / "outside-context.md"
            outside_artifact.write_text("# Outside context\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME_CLI),
                    "complete",
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--artifact",
                    str(outside_artifact),
                ],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(completed.returncode, 2, completed.stderr or completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["details"]["status"], "persisted_uncommitted")
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "1")
            self.assertTrue(outside_artifact.exists())

            node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
            self.assertEqual(node["status"], "running")

    def test_terminal_commit_contains_tree_and_declared_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            self.run_git(context, "init")
            self.run_git(context, "config", "user.name", "XC Test")
            self.run_git(context, "config", "user.email", "xc-test@example.invalid")
            config_path = context / "xc-orchestration-runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "schema_version = 1",
                        "",
                        "[git]",
                        "auto_commit = true",
                        'commit_message = "chore(orchestration): {operation} {run_id} [{checksum_short}]"',
                        'on_commit_failure = "warn"',
                        "",
                        "[integrity]",
                        'algorithm = "sha256"',
                        'canonicalization = "orchestration-tree-v1"',
                        'on_mismatch_read = "warn"',
                        'on_mismatch_write = "block"',
                        "",
                        "[viewer]",
                        'host = "127.0.0.1"',
                        "port = 10011",
                        "watch_interval_seconds = 1",
                        "heartbeat_seconds = 15",
                        "idle_shutdown_seconds = 120",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            run_id = "20260726-1430-terminal-commit"
            runtime_dir = context / "runs" / run_id / "runtime"

            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(runtime_dir),
                "--run-id",
                run_id,
                cwd=project,
            )
            self.assertEqual(initialized["status"], "persisted")
            self.assertEqual(initialized["commit"]["status"], "committed")
            tree_path = Path(str(initialized["tree_path"]))
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "1")

            ready = self.run_cli("next", "--tree", str(tree_path), cwd=project)
            node_id = str(ready["ready"][0]["id"])
            started = self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.assertEqual(started["commit"]["status"], "deferred")
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "1")

            artifact = context / "runs" / run_id / "artifacts" / "write-document" / "document.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Document\n", encoding="utf-8")
            unrelated = context / "unrelated-user-file.md"
            unrelated.write_text("# Preserve me\n", encoding="utf-8")

            completed = self.run_cli(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                node_id,
                "--summary",
                "Wrote the document.",
                "--validation",
                "passed",
                "--artifact",
                str(artifact),
                cwd=project,
            )
            self.assertEqual(completed["status"], "persisted")
            self.assertEqual(completed["commit"]["status"], "committed")
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "2")

            changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
            self.assertIn(f"runs/{run_id}/runtime/orchestration.xml", changed_paths)
            self.assertIn(f"runs/{run_id}/artifacts/write-document/document.md", changed_paths)
            self.assertNotIn("unrelated-user-file.md", changed_paths)
            self.assertIn("?? unrelated-user-file.md", self.run_git(context, "status", "--short"))

            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["counts"]["succeeded"], 2)


if __name__ == "__main__":
    unittest.main()
