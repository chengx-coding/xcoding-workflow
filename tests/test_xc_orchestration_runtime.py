from __future__ import annotations

import errno
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SKILL = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime"
RUNTIME_SCRIPTS = RUNTIME_SKILL / "scripts"
RUNTIME_CLI = RUNTIME_SCRIPTS / "orchestration.py"
VIEWER_SERVER = RUNTIME_SCRIPTS / "viewer_server.py"

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

    def git_has_head(self, repository: Path) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode == 0

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

    def write_conditional_template(self, path: Path, config: dict[str, object], when_policy: str = "") -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": "conditional-group"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Conditional Group",
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
                "template_id": "prepare",
                "title": "Prepare",
                "type": "task",
                "role": "prepare",
                "executor": "main",
            },
        )
        optional_attributes = {
            "template_id": "optional-group",
            "title": "Optional group",
            "type": "composite",
            "role": "optional",
            "mode": "sequence",
            "executor": "main",
            "when": "optional.enabled == true",
        }
        if when_policy:
            optional_attributes["when.policy"] = when_policy
        optional = ET.SubElement(
            children,
            "node",
            optional_attributes,
        )
        optional_children = ET.SubElement(optional, "children")
        ET.SubElement(
            optional_children,
            "node",
            {
                "template_id": "optional-work",
                "title": "Optional work",
                "type": "task",
                "role": "optional-work",
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
            },
        )
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def write_dynamic_group_template(self, path: Path, config: dict[str, object]) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": "dynamic-group"})
        ET.SubElement(root, "blackboard")
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Dynamic Group",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(workflow, "children")
        for template_id, title in (("prepare", "Prepare"), ("finish", "Finish")):
            if template_id == "finish":
                ET.SubElement(
                    children,
                    "node",
                    {
                        "template_id": "work-group",
                        "title": "Work group",
                        "type": "composite",
                        "role": "dynamic-group",
                        "mode": "sequence",
                        "executor": "main",
                    },
                )
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

    def test_config_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = Path(temporary) / ".xcoding"
            context.mkdir()
            config_path = context / "xc-orchestration-runtime.toml"
            config_path.write_bytes(b"\xef\xbb\xbfschema_version = 1\n[git]\nauto_commit = false\n")

            config = core.load_config(context)

            self.assertFalse(config["git"]["auto_commit"])
            self.assertEqual(config["_source"], str(config_path))

    def test_atomic_write_retries_transient_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "orchestration.xml"
            real_replace = core.os.replace
            attempts = 0

            def replace_once_locked(source: str, destination: str) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError(errno.EACCES, "temporary sharing conflict")
                real_replace(source, destination)

            with mock.patch.object(core.os, "replace", side_effect=replace_once_locked), mock.patch.object(core.time, "sleep") as sleep:
                core.atomic_write_text(target, "recovered\n")

            self.assertEqual(attempts, 2)
            sleep.assert_called_once_with(core.ATOMIC_REPLACE_RETRY_DELAY_SECONDS)
            self.assertEqual(target.read_text(encoding="utf-8"), "recovered\n")

    def test_blackboard_updated_at_uses_latest_variable_timestamp(self) -> None:
        root = ET.Element("orchestration")
        blackboard = ET.SubElement(root, "blackboard")
        ET.SubElement(blackboard, "var", {"key": "first", "updated_at": "2026-07-27T10:00:00+00:00"}).text = "one"
        ET.SubElement(blackboard, "var", {"key": "second", "updated_at": "2026-07-27T10:05:00+00:00"}).text = "two"
        ET.SubElement(blackboard, "var", {"key": "legacy"}).text = "three"

        self.assertEqual(core.blackboard_updated_at(root), "2026-07-27T10:05:00+00:00")

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
            self.assertFalse(self.git_has_head(context))
            self.assertTrue(outside_artifact.exists())

            node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
            self.assertEqual(node["status"], "running")

    def test_false_conditional_composite_skips_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_conditional_template(template, config)

            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / "conditional" / "runtime"),
                "--run-id",
                "conditional",
                "--var",
                "optional.enabled=false",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            prepare = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.assertEqual(prepare["template_id"], "prepare")
            self.run_cli("start", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)

            optional = self.run_cli(
                "find",
                "--tree",
                str(tree_path),
                "--template-id",
                "optional-group",
                cwd=project,
            )["nodes"][0]
            self.assertEqual(optional["status"], "skipped")
            ready = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"]
            self.assertEqual([node["template_id"] for node in ready], ["finish"])

    def test_dynamic_artifact_metadata_and_declared_artifact_query(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            run_id = "20260727-1200-artifact-query"
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
            root = self.run_cli("find", "--tree", str(tree_path), "--template-id", "root", cwd=project)["nodes"][0]

            added = self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                str(root["id"]),
                "--logical-key",
                "write-user-report",
                "--title",
                "Write user report",
                "--type",
                "task",
                "--executor",
                "main",
                "--metadata",
                "metadata.artifact.audience=user",
                "--metadata",
                "metadata.artifact.content_language=run.document_language",
                cwd=project,
            )
            self.assertEqual(added["node"]["attributes"]["metadata.artifact.audience"], "user")

            first = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.run_cli("start", "--tree", str(tree_path), "--node", str(first["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", str(first["id"]), cwd=project)

            user_node = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.assertEqual(user_node["logical_key"], "write-user-report")
            artifact = context / "runs" / run_id / "artifacts" / "user-report.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# User report\n", encoding="utf-8")
            unrelated = context / "runs" / run_id / "unmanaged.md"
            unrelated.write_text("# Unmanaged\n", encoding="utf-8")
            self.run_cli("start", "--tree", str(tree_path), "--node", str(user_node["id"]), cwd=project)
            self.run_cli(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                str(user_node["id"]),
                "--artifact",
                str(artifact),
                cwd=project,
            )

            queried = self.run_cli("artifacts", "--tree", str(tree_path), "--audience", "user", cwd=project)["artifacts"]
            self.assertEqual(queried, [{
                "path": str(artifact),
                "node_id": str(user_node["id"]),
                "metadata": {
                    "metadata.artifact.audience": "user",
                    "metadata.artifact.content_language": "run.document_language",
                },
            }])

            invalid = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME_CLI),
                    "add-node",
                    "--tree",
                    str(tree_path),
                    "--parent",
                    str(root["id"]),
                    "--logical-key",
                    "invalid-metadata",
                    "--title",
                    "Invalid metadata",
                    "--executor",
                    "main",
                    "--metadata",
                    "artifact.audience=user",
                ],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            payload = json.loads(invalid.stdout)
            self.assertEqual(invalid.returncode, 2, invalid.stderr or invalid.stdout)
            self.assertEqual(payload["error"]["code"], "tree_sealed")

    def test_mutations_serialize_and_reject_stale_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / "revision" / "runtime"),
                "--run-id",
                "revision",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            first_revision = int(initialized["revision"])

            updated = self.run_cli(
                "set",
                "--tree",
                str(tree_path),
                "--expected-revision",
                str(first_revision),
                "--set",
                "scope.confirmed=true",
                cwd=project,
            )
            stale = self.run_cli_error(
                "set",
                "--tree",
                str(tree_path),
                "--expected-revision",
                str(first_revision),
                "--set",
                "scope.stale=true",
                cwd=project,
            )
            self.assertEqual(stale["error"]["code"], "state_conflict")

            commands = [
                [
                    sys.executable,
                    str(RUNTIME_CLI),
                    "set",
                    "--tree",
                    str(tree_path),
                    "--set",
                    "parallel.left=true",
                ],
                [
                    sys.executable,
                    str(RUNTIME_CLI),
                    "set",
                    "--tree",
                    str(tree_path),
                    "--set",
                    "parallel.right=true",
                ],
            ]
            processes = [
                subprocess.Popen(
                    command,
                    cwd=project,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                for command in commands
            ]
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stderr or stdout)
                self.assertTrue(json.loads(stdout)["ok"])

            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["blackboard"]["parallel.left"], "true")
            self.assertEqual(summary["blackboard"]["parallel.right"], "true")
            self.assertEqual(int(summary["revision"]), int(updated["revision"]) + 2)

    def test_terminal_commands_require_running_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / "transition" / "runtime"),
                "--run-id",
                "transition",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            node_id = str(self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]["id"])

            for command, extra in (
                ("complete", []),
                ("fail", ["--reason", "unexpected"]),
                ("block", ["--reason", "unexpected"]),
            ):
                rejected = self.run_cli_error(command, "--tree", str(tree_path), "--node", node_id, *extra, cwd=project)
                self.assertEqual(rejected["error"]["code"], "invalid_transition")

            self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")

    def test_latched_conditions_do_not_reactivate_after_a_shared_value_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)

            def ready_after_enable(policy: str) -> list[str]:
                template = project / f"{policy or 'reactive'}.xml"
                self.write_conditional_template(template, config, policy)
                initialized = self.run_cli(
                    "init",
                    "--template",
                    str(template),
                    "--runtime-dir",
                    str(context / "runs" / (policy or "reactive") / "runtime"),
                    "--run-id",
                    policy or "reactive",
                    "--var",
                    "optional.enabled=false",
                    cwd=project,
                )
                tree_path = Path(str(initialized["tree_path"]))
                prepare = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
                self.run_cli("start", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)
                self.run_cli("complete", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)
                self.run_cli("set", "--tree", str(tree_path), "--set", "optional.enabled=true", cwd=project)
                return [
                    str(node["template_id"])
                    for node in self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"]
                ]

            self.assertEqual(ready_after_enable(""), ["optional-work"])
            self.assertEqual(ready_after_enable("latched"), ["finish"])

    def test_dynamic_groups_report_waiting_state_and_reject_closed_appends(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "dynamic.xml"
            self.write_dynamic_group_template(template, config)
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / "dynamic" / "runtime"),
                "--run-id",
                "dynamic",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            prepare = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.run_cli("start", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", str(prepare["id"]), cwd=project)

            waiting = self.run_cli("next", "--tree", str(tree_path), cwd=project)
            self.assertEqual(waiting["ready"], [])
            self.assertEqual([item["template_id"] for item in waiting["awaiting_dynamic_groups"]], ["work-group"])
            group_id = str(waiting["awaiting_dynamic_groups"][0]["id"])
            self.run_cli("close-group", "--tree", str(tree_path), "--group", group_id, cwd=project)

            rejected = self.run_cli_error(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                group_id,
                "--logical-key",
                "late-work",
                "--title",
                "Late work",
                "--executor",
                "main",
                cwd=project,
            )
            self.assertEqual(rejected["error"]["code"], "group_closed")
            self.assertEqual(
                [node["template_id"] for node in self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"]],
                ["finish"],
            )

    def test_successful_trees_require_explicit_reopen_before_new_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)
            template = project / "template.xml"
            self.write_template(template, config)
            initialized = self.run_cli(
                "init",
                "--template",
                str(template),
                "--runtime-dir",
                str(context / "runs" / "sealed" / "runtime"),
                "--run-id",
                "sealed",
                cwd=project,
            )
            tree_path = Path(str(initialized["tree_path"]))
            root_id = str(self.run_cli("find", "--tree", str(tree_path), "--template-id", "root", cwd=project)["nodes"][0]["id"])
            first = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.run_cli("start", "--tree", str(tree_path), "--node", str(first["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", str(first["id"]), cwd=project)

            sealed = self.run_cli_error("set", "--tree", str(tree_path), "--set", "late.change=true", cwd=project)
            self.assertEqual(sealed["error"]["code"], "tree_sealed")
            reopened = self.run_cli(
                "reopen",
                "--tree",
                str(tree_path),
                "--reason",
                "The user approved a documented correction.",
                cwd=project,
            )
            self.assertEqual(reopened["epoch"], "1")
            self.assertEqual(self.run_cli("snapshot", "--tree", str(tree_path), cwd=project)["metadata"]["epoch"], "1")
            self.run_cli(
                "add-node",
                "--tree",
                str(tree_path),
                "--parent",
                root_id,
                "--logical-key",
                "approved-correction",
                "--title",
                "Approved correction",
                "--executor",
                "main",
                cwd=project,
            )
            correction = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
            self.assertEqual(correction["logical_key"], "approved-correction")

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
                        "port = 20668",
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
            self.assertEqual(initialized["commit"]["status"], "deferred")
            tree_path = Path(str(initialized["tree_path"]))
            self.assertFalse(self.git_has_head(context))

            found = self.run_cli("find", "--tree", str(tree_path), "--template-id", "write-document", cwd=project)
            self.assertEqual(len(found["nodes"]), 1)
            self.assertEqual(found["nodes"][0]["title"], "Write document")

            ready = self.run_cli("next", "--tree", str(tree_path), cwd=project)
            node_id = str(ready["ready"][0]["id"])
            started = self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.assertEqual(started["commit"]["status"], "deferred")
            self.assertFalse(self.git_has_head(context))

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
            self.assertEqual(completed["commit"]["index_sync"]["status"], "synced")
            self.assertTrue(self.git_has_head(context))
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "1")

            changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
            self.assertIn(f"runs/{run_id}/runtime/orchestration.xml", changed_paths)
            self.assertIn(f"runs/{run_id}/artifacts/write-document/document.md", changed_paths)
            self.assertNotIn("unrelated-user-file.md", changed_paths)
            self.assertIn("?? unrelated-user-file.md", self.run_git(context, "status", "--short"))
            self.assertEqual(self.run_git(context, "diff", "--cached", "--name-only"), "")

            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["counts"]["succeeded"], 2)


class ViewerServerTests(unittest.TestCase):
    def write_config(self, directory: Path, idle_shutdown_seconds: int) -> Path:
        config_path = directory / "viewer.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[viewer]",
                    "port = 0",
                    "watch_interval_seconds = 1",
                    "heartbeat_seconds = 1",
                    f"idle_shutdown_seconds = {idle_shutdown_seconds}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def request_json(self, url: str) -> dict[str, object]:
        with urllib.request.urlopen(url, timeout=2) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            self.assertIn(response.status, {200, 201})
            return json.loads(response.read().decode("utf-8"))

    def is_healthy(self, url: str) -> bool:
        try:
            return bool(self.request_json(f"{url}api/health").get("ok"))
        except (OSError, urllib.error.URLError, ValueError):
            return False

    def stop_background_process(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/pid", str(pid), "/t", "/f"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            return
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            return

    def test_background_launch_returns_one_json_result_and_falls_back_from_occupied_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            root = Path(temporary)
            config_path = self.write_config(root, idle_shutdown_seconds=30)
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            requested_port = occupied.getsockname()[1]

            result = subprocess.run(
                [
                    sys.executable,
                    str(VIEWER_SERVER),
                    "--no-browser",
                    "--config",
                    str(config_path),
                    "--port",
                    str(requested_port),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=15,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(len(result.stdout.splitlines()), 1)
            payload = json.loads(result.stdout)
            try:
                self.assertTrue(payload["ok"])
                self.assertEqual(set(payload), {"ok", "mode", "pid", "url", "trees"})
                self.assertEqual(payload["mode"], "background")
                self.assertNotEqual(int(payload["url"].rsplit(":", 1)[1].rstrip("/")), requested_port)
                self.assertTrue(self.is_healthy(str(payload["url"])))
            finally:
                self.stop_background_process(int(payload["pid"]))

    def test_background_server_closes_after_configured_idle_period(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.write_config(Path(temporary), idle_shutdown_seconds=1)
            result = subprocess.run(
                [sys.executable, str(VIEWER_SERVER), "--no-browser", "--config", str(config_path)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            url = str(payload["url"])
            try:
                self.assertTrue(self.is_healthy(url))
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and self.is_healthy(url):
                    time.sleep(0.1)
                self.assertFalse(self.is_healthy(url))
            finally:
                self.stop_background_process(int(payload["pid"]))

    def test_foreground_mode_emits_lifecycle_events_and_serves_health(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.write_config(Path(temporary), idle_shutdown_seconds=2)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(VIEWER_SERVER),
                    "--foreground",
                    "--no-browser",
                    "--config",
                    str(config_path),
                ],
                cwd=REPOSITORY_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            assert process.stdout is not None
            started = json.loads(process.stdout.readline())
            self.assertEqual(started["event"], "viewer_started")
            self.assertTrue(self.is_healthy(str(started["url"])))
            client = self.post_json(f"{started['url']}api/clients")
            self.assertTrue(client["client_id"])
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            events = [started, *(json.loads(line) for line in stdout.splitlines())]
            event_names = [event["event"] for event in events]
            self.assertIn("client_connected", event_names)
            self.assertIn("client_expired", event_names)
            self.assertIn("idle_shutdown", event_names)
            self.assertIn("viewer_stopped", event_names)

    def test_static_viewer_assets_define_connection_badge_without_pan_handle(self) -> None:
        static_dir = RUNTIME_SKILL / "viewer" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app = (static_dir / "app.js").read_text(encoding="utf-8")
        css = (static_dir / "app.css").read_text(encoding="utf-8")

        self.assertIn('id="server-status-label"', index)
        self.assertNotIn("graph-pan-handle", index)
        self.assertIn("function scheduleReconnect()", app)
        self.assertIn('setConnectionStatus("disconnected")', app)
        self.assertNotIn("graphPanHandle", app)
        self.assertIn('.server-status[data-connection="connected"]', css)
        self.assertNotIn(".graph-pan-handle", css)


if __name__ == "__main__":
    unittest.main()
