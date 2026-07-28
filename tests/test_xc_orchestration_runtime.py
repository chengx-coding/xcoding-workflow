from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SKILL = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime"
RUNTIME_SCRIPTS = RUNTIME_SKILL / "scripts"
RUNTIME_CLI = RUNTIME_SCRIPTS / "orchestration.py"
VIEWER_SERVER = RUNTIME_SCRIPTS / "viewer_server.py"

sys.path.insert(0, str(RUNTIME_SCRIPTS))
import orchestration as runtime_cli
import runtime_core as core
import viewer_server


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

    def create_terminal_runtime(
        self,
        project: Path,
        run_id: str,
        auto_commit: bool,
    ) -> tuple[Path, Path, str]:
        context = project / ".xcoding"
        context.mkdir(parents=True)
        if auto_commit:
            self.run_git(context, "init")
            self.run_git(context, "config", "user.name", "XC Test")
            self.run_git(context, "config", "user.email", "xc-test@example.invalid")
        (context / "xc-orchestration-runtime.toml").write_text(
            f"[git]\nauto_commit = {'true' if auto_commit else 'false'}\n",
            encoding="utf-8",
        )
        config = core.load_config(context)
        template = project / "template.xml"
        self.write_template(template, config)
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
        node_id = str(self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]["id"])
        return context, tree_path, node_id

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

    def write_flow_template(
        self,
        path: Path,
        config: dict[str, object],
        child_specs: list[dict[str, object]],
        *,
        mode: str = "sequence",
        blackboard: dict[str, str] | None = None,
    ) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": path.stem})
        variables = ET.SubElement(root, "blackboard")
        for key, value in (blackboard or {}).items():
            ET.SubElement(variables, "var", {"key": key}).text = value
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": path.stem,
                "type": "composite",
                "role": "root",
                "mode": mode,
                "executor": "main",
            },
        )
        holder = ET.SubElement(workflow, "children")

        def append_node(parent: ET.Element, spec: dict[str, object]) -> None:
            nested = list(spec.get("children", []))
            template_id = str(spec["template_id"])
            attributes = {
                "template_id": template_id,
                "title": str(spec.get("title", template_id)),
                "type": str(spec.get("type", "composite" if nested else "task")),
                "role": str(spec.get("role", template_id)),
                "executor": str(spec.get("executor", "main")),
            }
            for key, value in spec.items():
                if key not in {"template_id", "title", "type", "role", "executor", "children"}:
                    attributes[key] = str(value)
            if nested and "mode" not in attributes:
                attributes["mode"] = "sequence"
            node = ET.SubElement(parent, "node", attributes)
            if nested:
                nested_holder = ET.SubElement(node, "children")
                for child in nested:
                    append_node(nested_holder, child)

        for child_spec in child_specs:
            append_node(holder, child_spec)
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def init_flow(
        self,
        project: Path,
        context: Path,
        config: dict[str, object],
        run_id: str,
        child_specs: list[dict[str, object]],
        *,
        mode: str = "sequence",
        blackboard: dict[str, str] | None = None,
    ) -> Path:
        template = project / f"{run_id}.xml"
        self.write_flow_template(template, config, child_specs, mode=mode, blackboard=blackboard)
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
        return Path(str(initialized["tree_path"]))

    def assert_start_not_ready(
        self,
        project: Path,
        tree_path: Path,
        node_id: str,
        reason: str,
    ) -> dict[str, object]:
        before_summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
        before_node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
        self.assertNotIn(node_id, {node["id"] for node in before_summary["ready"]})
        rejected = self.run_cli_error("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
        self.assertEqual(rejected["error"]["code"], "node_not_ready")
        self.assertEqual(rejected["error"]["details"]["reason"], reason)
        self.assertEqual(rejected["error"]["details"]["status"], before_node["status"])
        after_summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
        after_node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
        self.assertEqual(after_summary["revision"], before_summary["revision"])
        self.assertEqual(after_node["status"], before_node["status"])
        return rejected

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

    def test_snapshot_svg_is_complete_parseable_and_escaped(self) -> None:
        snapshot = {
            "metadata": {"name": "A & B", "run_id": "svg-run", "status": "running"},
            "root": {
                "id": "root",
                "title": "Root <node>",
                "type": "composite",
                "role": "root",
                "status": "running",
                "children": [
                    {
                        "id": "child",
                        "title": "Child & work",
                        "type": "task",
                        "role": "work",
                        "status": "succeeded",
                        "children": [],
                    }
                ],
            },
        }

        rendered = core.render_snapshot_svg(snapshot)
        parsed = ET.fromstring(rendered)

        self.assertEqual(parsed.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(len(parsed.findall(".//{http://www.w3.org/2000/svg}g")), 2)
        self.assertEqual(len(parsed.findall(".//{http://www.w3.org/2000/svg}path")), 1)
        self.assertIn("A &amp; B", rendered)
        self.assertIn("Root &lt;node&gt;", rendered)
        self.assertEqual(core.runtime_svg_filename("Viewer Run", "fallback"), "viewer-run.svg")

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
            self.assertFalse((tree_path.parent / "terminal-commit.svg").exists())

            node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
            self.assertEqual(node["status"], "running")

    def test_fail_and_block_checkpoint_declared_artifacts_only(self) -> None:
        for operation, terminal_status in (("fail", "failed"), ("block", "blocked")):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary) / "project"
                run_id = f"terminal-{operation}-artifacts"
                context, tree_path, node_id = self.create_terminal_runtime(project, run_id, auto_commit=True)
                self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)

                artifact_dir = context / "runs" / run_id / "artifacts" / operation
                artifact_dir.mkdir(parents=True)
                artifacts = [artifact_dir / "evidence.md", artifact_dir / "diagnostic.txt"]
                artifacts[0].write_text("# Evidence\n", encoding="utf-8")
                artifacts[1].write_text("diagnostic\n", encoding="utf-8")
                unrelated = context / "unrelated-user-file.md"
                unrelated.write_text("# Preserve me\n", encoding="utf-8")

                terminal = self.run_cli(
                    operation,
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--reason",
                    f"{operation} evidence",
                    "--artifact",
                    str(artifacts[0]),
                    "--artifact",
                    str(artifacts[1]),
                    cwd=project,
                )
                self.assertEqual(terminal["commit"]["status"], "committed")
                self.assertEqual(terminal["node"]["status"], terminal_status)
                self.assertEqual(terminal["node"]["result"]["artifacts"], [str(path) for path in artifacts])

                declared = self.run_cli("artifacts", "--tree", str(tree_path), cwd=project)["artifacts"]
                self.assertEqual([item["path"] for item in declared], [str(path) for path in artifacts])
                changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
                self.assertIn(f"runs/{run_id}/runtime/orchestration.xml", changed_paths)
                for artifact in artifacts:
                    self.assertIn(artifact.relative_to(context).as_posix(), changed_paths)
                self.assertNotIn("unrelated-user-file.md", changed_paths)
                self.assertIn("?? unrelated-user-file.md", self.run_git(context, "status", "--short"))

    def test_fail_and_block_without_artifacts_remain_compatible(self) -> None:
        for operation, terminal_status in (("fail", "failed"), ("block", "blocked")):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary) / "project"
                _, tree_path, node_id = self.create_terminal_runtime(
                    project,
                    f"legacy-{operation}",
                    auto_commit=False,
                )
                self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
                terminal = self.run_cli(
                    operation,
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--reason",
                    f"legacy {operation}",
                    cwd=project,
                )
                self.assertEqual(terminal["commit"]["status"], "disabled")
                self.assertEqual(terminal["node"]["status"], terminal_status)
                self.assertNotIn("artifacts", terminal["node"]["result"])

    def test_auto_commit_disabled_records_unvalidated_terminal_artifacts(self) -> None:
        for operation, terminal_status in (("fail", "failed"), ("block", "blocked")):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary) / "project"
                _, tree_path, node_id = self.create_terminal_runtime(
                    project,
                    f"disabled-{operation}",
                    auto_commit=False,
                )
                self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
                missing_outside_path = project / "missing-outside.md"
                terminal = self.run_cli(
                    operation,
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--reason",
                    f"disabled {operation}",
                    "--artifact",
                    str(missing_outside_path),
                    cwd=project,
                )
                self.assertEqual(terminal["commit"]["status"], "disabled")
                self.assertEqual(terminal["node"]["status"], terminal_status)
                self.assertEqual(terminal["node"]["result"]["artifacts"], [str(missing_outside_path)])

    def test_fail_and_block_restore_tree_when_artifact_checkpoint_fails(self) -> None:
        for operation in ("fail", "block"):
            for path_kind in ("outside", "missing"):
                with (
                    self.subTest(operation=operation, path_kind=path_kind),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    project = Path(temporary) / "project"
                    context, tree_path, node_id = self.create_terminal_runtime(
                        project,
                        f"rollback-{operation}-{path_kind}",
                        auto_commit=True,
                    )
                    self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
                    before = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
                    if path_kind == "outside":
                        artifact = project / "outside.md"
                        artifact.write_text("# Outside\n", encoding="utf-8")
                    else:
                        artifact = context / "missing.md"

                    rejected = self.run_cli_error(
                        operation,
                        "--tree",
                        str(tree_path),
                        "--node",
                        node_id,
                        "--reason",
                        f"{path_kind} artifact",
                        "--artifact",
                        str(artifact),
                        cwd=project,
                    )
                    self.assertEqual(rejected["error"]["details"]["status"], "persisted_uncommitted")
                    after = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
                    node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
                    self.assertEqual(after["revision"], before["revision"])
                    self.assertEqual(node["status"], "running")
                    self.assertNotIn("artifacts", node["result"])
                    self.assertFalse(self.git_has_head(context))

    def test_rejected_fail_and_block_with_artifact_do_not_mutate_tree(self) -> None:
        for operation in ("fail", "block"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary) / "project"
                _, tree_path, node_id = self.create_terminal_runtime(
                    project,
                    f"rejected-{operation}",
                    auto_commit=False,
                )
                artifact = project / "unused.md"
                artifact.write_text("# Unused\n", encoding="utf-8")
                before = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
                self.run_cli_error(
                    operation,
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--reason",
                    f"rejected {operation}",
                    "--artifact",
                    str(artifact),
                    cwd=project,
                )
                after = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
                node = self.run_cli("show", "--tree", str(tree_path), "--node", node_id, cwd=project)["node"]
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(node["status"], "pending")
                self.assertEqual(node["result"], {})

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

    def test_start_rejects_sequence_condition_and_switch_bypasses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)

            sequence_tree = self.init_flow(
                project,
                context,
                config,
                "sequence-readiness",
                [
                    {"template_id": "first"},
                    {"template_id": "second"},
                ],
            )
            second = self.run_cli(
                "find",
                "--tree",
                str(sequence_tree),
                "--template-id",
                "second",
                cwd=project,
            )["nodes"][0]
            sequence_rejection = self.assert_start_not_ready(
                project,
                sequence_tree,
                str(second["id"]),
                "sequence_predecessor_incomplete",
            )
            self.assertEqual(sequence_rejection["error"]["details"]["blocker_status"], "pending")

            revision = int(self.run_cli("summary", "--tree", str(sequence_tree), cwd=project)["revision"])
            self.run_cli("set", "--tree", str(sequence_tree), "--set", "unrelated.change=true", cwd=project)
            before_stale = self.run_cli("summary", "--tree", str(sequence_tree), cwd=project)
            before_second = self.run_cli(
                "show",
                "--tree",
                str(sequence_tree),
                "--node",
                str(second["id"]),
                cwd=project,
            )["node"]
            stale = self.run_cli_error(
                "start",
                "--tree",
                str(sequence_tree),
                "--node",
                str(second["id"]),
                "--expected-revision",
                str(revision),
                cwd=project,
            )
            self.assertEqual(stale["error"]["code"], "state_conflict")
            after_stale = self.run_cli("summary", "--tree", str(sequence_tree), cwd=project)
            after_second = self.run_cli(
                "show",
                "--tree",
                str(sequence_tree),
                "--node",
                str(second["id"]),
                cwd=project,
            )["node"]
            self.assertEqual(after_stale["revision"], before_stale["revision"])
            self.assertEqual(after_second["status"], before_second["status"])

            condition_tree = self.init_flow(
                project,
                context,
                config,
                "condition-readiness",
                [
                    {"template_id": "conditional", "when": "work.enabled == true"},
                    {"template_id": "control"},
                ],
                mode="parallel",
                blackboard={"work.enabled": "false"},
            )
            conditional = self.run_cli(
                "find",
                "--tree",
                str(condition_tree),
                "--template-id",
                "conditional",
                cwd=project,
            )["nodes"][0]
            self.assert_start_not_ready(project, condition_tree, str(conditional["id"]), "condition_false")

            ancestor_condition_tree = self.init_flow(
                project,
                context,
                config,
                "ancestor-condition-readiness",
                [
                    {
                        "template_id": "conditional-group",
                        "when": "group.enabled == true",
                        "children": [{"template_id": "conditional-child"}],
                    },
                    {"template_id": "control"},
                ],
                mode="parallel",
                blackboard={"group.enabled": "false"},
            )
            conditional_child = self.run_cli(
                "find",
                "--tree",
                str(ancestor_condition_tree),
                "--template-id",
                "conditional-child",
                cwd=project,
            )["nodes"][0]
            self.assert_start_not_ready(
                project,
                ancestor_condition_tree,
                str(conditional_child["id"]),
                "ancestor_condition_false",
            )

            switch_tree = self.init_flow(
                project,
                context,
                config,
                "switch-readiness",
                [
                    {
                        "template_id": "route",
                        "mode": "switch",
                        "switch.key": "route.selected",
                        "children": [
                            {
                                "template_id": "selected-case",
                                "role": "case",
                                "case.value": "selected",
                                "children": [{"template_id": "selected-work"}],
                            },
                            {
                                "template_id": "unselected-case",
                                "role": "case",
                                "case.value": "unselected",
                                "children": [{"template_id": "unselected-work"}],
                            },
                        ],
                    },
                    {"template_id": "control"},
                ],
                mode="parallel",
                blackboard={"route.selected": "selected"},
            )
            unselected = self.run_cli(
                "find",
                "--tree",
                str(switch_tree),
                "--template-id",
                "unselected-work",
                cwd=project,
            )["nodes"][0]
            self.assert_start_not_ready(project, switch_tree, str(unselected["id"]), "ancestor_skipped")

    def test_start_rejects_failed_blocked_terminal_and_sealed_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)

            for terminal_command, reason in (("fail", "ancestor_failed"), ("block", "ancestor_blocked")):
                with self.subTest(terminal_command=terminal_command):
                    tree_path = self.init_flow(
                        project,
                        context,
                        config,
                        f"{terminal_command}-ancestor",
                        [
                            {"template_id": "first"},
                            {"template_id": "second"},
                        ],
                    )
                    first = self.run_cli("next", "--tree", str(tree_path), cwd=project)["ready"][0]
                    second = self.run_cli(
                        "find",
                        "--tree",
                        str(tree_path),
                        "--template-id",
                        "second",
                        cwd=project,
                    )["nodes"][0]
                    self.run_cli("start", "--tree", str(tree_path), "--node", str(first["id"]), cwd=project)
                    self.run_cli(
                        terminal_command,
                        "--tree",
                        str(tree_path),
                        "--node",
                        str(first["id"]),
                        "--reason",
                        "test outcome",
                        cwd=project,
                    )
                    self.assert_start_not_ready(project, tree_path, str(second["id"]), reason)

            parallel_tree = self.init_flow(
                project,
                context,
                config,
                "parallel-readiness",
                [
                    {"template_id": "left"},
                    {"template_id": "right"},
                ],
                mode="parallel",
            )
            ready = self.run_cli("next", "--tree", str(parallel_tree), cwd=project)["ready"]
            self.assertEqual({node["template_id"] for node in ready}, {"left", "right"})
            by_template = {str(node["template_id"]): node for node in ready}
            self.run_cli("start", "--tree", str(parallel_tree), "--node", str(by_template["left"]["id"]), cwd=project)
            self.run_cli("start", "--tree", str(parallel_tree), "--node", str(by_template["right"]["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(parallel_tree), "--node", str(by_template["left"]["id"]), cwd=project)
            self.assert_start_not_ready(project, parallel_tree, str(by_template["left"]["id"]), "node_status")

            sealed_tree = self.init_flow(
                project,
                context,
                config,
                "sealed-start",
                [{"template_id": "only"}],
            )
            only = self.run_cli("next", "--tree", str(sealed_tree), cwd=project)["ready"][0]
            self.run_cli("start", "--tree", str(sealed_tree), "--node", str(only["id"]), cwd=project)
            self.run_cli("complete", "--tree", str(sealed_tree), "--node", str(only["id"]), cwd=project)
            sealed = self.run_cli_error("start", "--tree", str(sealed_tree), "--node", str(only["id"]), cwd=project)
            self.assertEqual(sealed["error"]["code"], "tree_sealed")

    def test_start_rejects_leaf_and_ancestor_dependency_bypasses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            config = core.load_config(context)

            leaf_tree = self.init_flow(
                project,
                context,
                config,
                "leaf-dependency",
                [
                    {"template_id": "dependency"},
                    {"template_id": "dependent", "depends_on_template": "local:dependency"},
                ],
                mode="parallel",
            )
            leaf_ready = self.run_cli("next", "--tree", str(leaf_tree), cwd=project)["ready"]
            self.assertEqual([node["template_id"] for node in leaf_ready], ["dependency"])
            dependent = self.run_cli(
                "find",
                "--tree",
                str(leaf_tree),
                "--template-id",
                "dependent",
                cwd=project,
            )["nodes"][0]
            leaf_rejection = self.assert_start_not_ready(
                project,
                leaf_tree,
                str(dependent["id"]),
                "dependency_incomplete",
            )
            self.assertEqual(len(leaf_rejection["error"]["details"]["dependency_ids"]), 1)

            ancestor_tree = self.init_flow(
                project,
                context,
                config,
                "ancestor-dependency",
                [
                    {"template_id": "dependency"},
                    {
                        "template_id": "dependent-group",
                        "depends_on_template": "local:dependency",
                        "children": [{"template_id": "dependent-child"}],
                    },
                ],
                mode="parallel",
            )
            ancestor_ready = self.run_cli("next", "--tree", str(ancestor_tree), cwd=project)["ready"]
            self.assertEqual([node["template_id"] for node in ancestor_ready], ["dependency"])
            dependent_child = self.run_cli(
                "find",
                "--tree",
                str(ancestor_tree),
                "--template-id",
                "dependent-child",
                cwd=project,
            )["nodes"][0]
            ancestor_rejection = self.assert_start_not_ready(
                project,
                ancestor_tree,
                str(dependent_child["id"]),
                "ancestor_dependency_incomplete",
            )
            self.assertEqual(len(ancestor_rejection["error"]["details"]["dependency_ids"]), 1)

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
            first_completion = self.run_cli(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                str(first["id"]),
                cwd=project,
            )
            svg_path = Path(str(first_completion["svg_path"]))
            first_svg = svg_path.read_text(encoding="utf-8")

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
            self.run_cli("start", "--tree", str(tree_path), "--node", str(correction["id"]), cwd=project)
            second_completion = self.run_cli(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                str(correction["id"]),
                cwd=project,
            )
            self.assertEqual(Path(str(second_completion["svg_path"])), svg_path)
            second_svg = svg_path.read_text(encoding="utf-8")
            self.assertNotEqual(second_svg, first_svg)
            self.assertIn("Approved correction", second_svg)

    def test_non_terminal_close_group_seals_with_svg_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            self.run_git(context, "init")
            self.run_git(context, "config", "user.name", "XC Test")
            self.run_git(context, "config", "user.email", "xc-test@example.invalid")
            (context / "xc-orchestration-runtime.toml").write_text(
                "[git]\nauto_commit = true\n",
                encoding="utf-8",
            )
            config = core.load_config(context)
            tree_path = self.init_flow(
                project,
                context,
                config,
                "close-group-seal",
                [
                    {
                        "template_id": "work-group",
                        "title": "Work group",
                        "type": "composite",
                        "role": "dynamic-group",
                        "mode": "sequence",
                    }
                ],
            )
            group = self.run_cli(
                "find",
                "--tree",
                str(tree_path),
                "--template-id",
                "work-group",
                cwd=project,
            )["nodes"][0]

            closed = self.run_cli(
                "close-group",
                "--tree",
                str(tree_path),
                "--group",
                str(group["id"]),
                cwd=project,
            )

            svg_path = Path(str(closed["svg_path"]))
            self.assertEqual(closed["commit"]["status"], "committed")
            self.assertTrue(svg_path.is_file())
            self.assertEqual(self.run_cli("summary", "--tree", str(tree_path), cwd=project)["status"], "complete")
            changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
            self.assertIn("runs/close-group-seal/runtime/orchestration.xml", changed_paths)
            self.assertIn("runs/close-group-seal/runtime/close-group-seal.svg", changed_paths)

    def test_non_terminal_seal_restores_tree_when_svg_render_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context = project / ".xcoding"
            context.mkdir(parents=True)
            (context / "xc-orchestration-runtime.toml").write_text(
                "[git]\nauto_commit = false\n",
                encoding="utf-8",
            )
            config = core.load_config(context)
            tree_path = self.init_flow(
                project,
                context,
                config,
                "close-group-rollback",
                [
                    {
                        "template_id": "work-group",
                        "title": "Work group",
                        "type": "composite",
                        "role": "dynamic-group",
                        "mode": "sequence",
                    }
                ],
            )
            group = self.run_cli(
                "find",
                "--tree",
                str(tree_path),
                "--template-id",
                "work-group",
                cwd=project,
            )["nodes"][0]
            before = tree_path.read_bytes()
            args = argparse.Namespace(
                tree=str(tree_path),
                config="",
                expected_revision=None,
                group=str(group["id"]),
            )

            with mock.patch.object(core, "render_snapshot_svg", side_effect=RuntimeError("render failed")):
                with self.assertRaisesRegex(RuntimeError, "render failed"):
                    runtime_cli.cmd_close_group(args)

            self.assertEqual(tree_path.read_bytes(), before)
            self.assertFalse((tree_path.parent / "close-group-rollback.svg").exists())
            summary = self.run_cli("summary", "--tree", str(tree_path), cwd=project)
            self.assertEqual(summary["status"], "pending")
            self.assertEqual(summary["awaiting_dynamic_groups"][0]["state"], "open")

    def test_non_utf8_existing_svg_is_overwritten_or_restored_as_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "success"
            _, tree_path, node_id = self.create_terminal_runtime(project, "binary-success", auto_commit=False)
            svg_path = tree_path.parent / "terminal-commit.svg"
            svg_path.write_bytes(b"\xff\xfeold-sidecar")
            self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.run_cli("complete", "--tree", str(tree_path), "--node", node_id, cwd=project)
            self.assertTrue(svg_path.read_bytes().startswith(b'<?xml version="1.0"'))

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "rollback"
            _, tree_path, node_id = self.create_terminal_runtime(project, "binary-rollback", auto_commit=True)
            svg_path = tree_path.parent / "terminal-commit.svg"
            previous = b"\xff\xfeold-sidecar"
            svg_path.write_bytes(previous)
            outside = project / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            self.run_cli("start", "--tree", str(tree_path), "--node", node_id, cwd=project)
            rejected = self.run_cli_error(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                node_id,
                "--artifact",
                str(outside),
                cwd=project,
            )
            self.assertEqual(rejected["error"]["details"]["status"], "persisted_uncommitted")
            self.assertEqual(svg_path.read_bytes(), previous)

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
            svg_path = Path(str(completed["svg_path"]))
            self.assertEqual(svg_path, tree_path.parent / "terminal-commit.svg")
            self.assertTrue(svg_path.is_file())
            ET.fromstring(svg_path.read_text(encoding="utf-8"))
            self.assertTrue(self.git_has_head(context))
            self.assertEqual(self.run_git(context, "rev-list", "--count", "HEAD"), "1")

            changed_paths = self.run_git(context, "show", "--format=", "--name-only", "HEAD").splitlines()
            self.assertIn(f"runs/{run_id}/runtime/orchestration.xml", changed_paths)
            self.assertIn(f"runs/{run_id}/runtime/terminal-commit.svg", changed_paths)
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

    def start_test_server(
        self,
        root: Path,
        tree_path: Path | None = None,
    ) -> tuple[viewer_server.ViewerState, object, threading.Thread, str]:
        config_path = self.write_config(root, idle_shutdown_seconds=30)
        config = core.load_config(root, config_path)
        registry = viewer_server.TreeRegistry(config, [root])
        if tree_path is not None:
            registry.register(str(tree_path), add_parent_root=True)
        state = viewer_server.ViewerState(registry, config)
        server = viewer_server.create_server("127.0.0.1", 0, state)
        state.server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        return state, server, thread, url

    def write_runtime_tree(self, root: Path, name: str = "viewer-tree") -> Path:
        config = core.load_config(root, self.write_config(root, idle_shutdown_seconds=30))
        template = core.parse_xml(RUNTIME_SKILL / "assets" / "minimal-template.xml")
        tree = core.instantiate_runtime_tree(template, "viewer-run", name, [], config)
        core.stabilize(tree.getroot())
        tree_path = root / "runtime" / "orchestration.xml"
        core.write_managed_tree(
            tree,
            tree_path,
            "runtime",
            config,
            "test",
            commit_on_write=False,
        )
        return tree_path

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

    def test_viewer_serves_svg_for_registered_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree_path = self.write_runtime_tree(root)
            state, server, thread, url = self.start_test_server(root, tree_path)
            try:
                tree_id = state.registry.list()[0]["tree_id"]
                with urllib.request.urlopen(f"{url}api/trees/{tree_id}/svg", timeout=2) as response:
                    rendered = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                    self.assertIn('filename="viewer-tree.svg"', response.headers["Content-Disposition"])
                parsed = ET.fromstring(rendered)
                self.assertEqual(parsed.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertEqual(
                    len(parsed.findall(".//{http://www.w3.org/2000/svg}g")),
                    sum(1 for _ in core.iter_nodes(core.parse_xml(tree_path).getroot())),
                )
            finally:
                state.request_shutdown()
                thread.join(timeout=3)
                server.server_close()

    def test_tree_picker_registers_selected_path_and_handles_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_root = root / "selected"
            selected_root.mkdir()
            tree_path = self.write_runtime_tree(selected_root, "picked-tree")
            state, server, thread, url = self.start_test_server(root)
            try:
                with mock.patch.object(viewer_server, "select_tree_file", return_value=str(tree_path)):
                    picked = self.post_json(f"{url}api/tree-picker")
                self.assertTrue(picked["selected"])
                self.assertEqual(picked["tree"]["path"], str(tree_path.resolve()))
                self.assertIn(tree_path.parent.resolve(), state.registry.allow_roots)

                with mock.patch.object(viewer_server, "select_tree_file", return_value=None):
                    canceled = self.post_json(f"{url}api/tree-picker")
                self.assertFalse(canceled["selected"])
            finally:
                state.request_shutdown()
                thread.join(timeout=3)
                server.server_close()

    def test_tree_picker_helper_reports_failure_and_serializes_requests(self) -> None:
        failed = subprocess.CompletedProcess(
            args=["tree-picker"],
            returncode=2,
            stdout='{"ok": false, "error": "no desktop"}\n',
            stderr="",
        )
        with mock.patch.object(viewer_server.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(core.RuntimeErrorBase, "unavailable"):
                viewer_server.select_tree_file()

        active = 0
        max_active = 0
        active_lock = threading.Lock()

        def run_picker(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with active_lock:
                active -= 1
            return subprocess.CompletedProcess(
                args=["tree-picker"],
                returncode=0,
                stdout='{"ok": true, "selected": false, "path": ""}\n',
                stderr="",
            )

        results: list[str | None] = []
        errors: list[str] = []

        def invoke_picker() -> None:
            try:
                results.append(viewer_server.select_tree_file())
            except core.RuntimeErrorBase as exc:
                errors.append(str(exc))

        with mock.patch.object(viewer_server.subprocess, "run", side_effect=run_picker):
            threads = [threading.Thread(target=invoke_picker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(max_active, 1)
        self.assertEqual(results, [None])
        self.assertEqual(errors, ["a native file selection dialog is already active"])

    def test_tree_picker_rejects_foreign_browser_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, server, thread, url = self.start_test_server(root)
            try:
                with mock.patch.object(viewer_server, "select_tree_file") as picker:
                    for host, origin in (
                        (urlparse(url).netloc, "https://example.invalid"),
                        ("attacker.invalid", "http://attacker.invalid"),
                    ):
                        request = urllib.request.Request(
                            f"{url}api/tree-picker",
                            data=b"{}",
                            headers={
                                "Content-Type": "application/json",
                                "Host": host,
                                "Origin": origin,
                            },
                            method="POST",
                        )
                        with self.assertRaises(urllib.error.HTTPError) as raised:
                            urllib.request.urlopen(request, timeout=2)
                        self.assertEqual(raised.exception.code, 403)
                    picker.assert_not_called()
            finally:
                state.request_shutdown()
                thread.join(timeout=3)
                server.server_close()

    def test_static_viewer_assets_define_refresh_resize_zoom_picker_and_svg_controls(self) -> None:
        static_dir = RUNTIME_SKILL / "viewer" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app = (static_dir / "app.js").read_text(encoding="utf-8")
        css = (static_dir / "app.css").read_text(encoding="utf-8")

        self.assertIn('id="server-status-label"', index)
        self.assertNotIn("graph-pan-handle", index)
        self.assertIn("function scheduleReconnect()", app)
        self.assertIn('setConnectionStatus("disconnected")', app)
        self.assertNotIn("graphPanHandle", app)
        self.assertIn('id="save-svg-button"', index)
        self.assertIn('id="pick-tree-button"', index)
        self.assertIn('id="zoom-slider"', index)
        self.assertIn('id="graph-resize-handle"', index)
        self.assertIn("const AUTO_REFRESH_MS = 20000", app)
        self.assertIn("window.setInterval(refreshTrees, AUTO_REFRESH_MS)", app)
        self.assertIn("elements.zoomSlider.value", app)
        self.assertIn("function zoomAroundViewportCenter(scale)", app)
        self.assertIn("function startResizing(event)", app)
        self.assertIn("/api/tree-picker", app)
        self.assertIn("/svg`", app)
        self.assertIn('.server-status[data-connection="connected"]', css)
        self.assertNotIn(".graph-pan-handle", css)
        self.assertIn("height: clamp(680px, 76vh, 1080px)", css)
        self.assertIn(".graph-resize-handle", css)


if __name__ == "__main__":
    unittest.main()
