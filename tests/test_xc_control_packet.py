from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCRIPTS = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "scripts"
RUNTIME_CLI = RUNTIME_SCRIPTS / "orchestration.py"
DOCUMENT_VALIDATOR = (
    REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"
)
sys.path.insert(0, str(RUNTIME_SCRIPTS))
import runtime_core as core


class ControlPacketRuntimeTests(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        cwd: Path,
        expected_code: int = 0,
    ) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_CLI), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, expected_code, result.stderr or result.stdout)
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

    def prepare_context(self, project: Path, auto_commit: bool = False) -> tuple[Path, dict[str, object]]:
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
        return context, core.load_config(context)

    def write_template(
        self,
        path: Path,
        config: dict[str, object],
        specs: list[dict[str, str]],
        *,
        blackboard: dict[str, str] | None = None,
    ) -> None:
        root = ET.Element("orchestration", {"schema_version": "1", "name": path.stem})
        bb = ET.SubElement(root, "blackboard")
        for key, value in (blackboard or {}).items():
            ET.SubElement(bb, "var", {"key": key}).text = value
        workflow = ET.SubElement(
            root,
            "node",
            {
                "template_id": "root",
                "title": "Root",
                "type": "composite",
                "role": "root",
                "mode": "parallel",
                "executor": "main",
            },
        )
        holder = ET.SubElement(workflow, "children")
        for spec in specs:
            payload_fields = {"instructions", "inputs", "deliverables", "acceptance"}
            attributes = {
                "template_id": spec["template_id"],
                "title": spec.get("title", spec["template_id"]),
                "type": spec.get("type", "task"),
                "role": spec.get("role", spec["template_id"]),
                "executor": spec.get("executor", "main"),
            }
            attributes.update(
                {
                    key: value
                    for key, value in spec.items()
                    if key not in {
                        "template_id",
                        "title",
                        "type",
                        "role",
                        "executor",
                        *payload_fields,
                    }
                }
            )
            node = ET.SubElement(holder, "node", attributes)
            for field in payload_fields:
                if spec.get(field):
                    ET.SubElement(node, field).text = spec[field]
        core.apply_integrity(root, "template", config)
        core.atomic_write_text(path, core.serialize_xml(root, "template"))

    def init_runtime(
        self,
        project: Path,
        context: Path,
        template: Path,
        work_order_id: str,
    ) -> Path:
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
        return Path(str(initialized["tree_path"]))

    def find(self, project: Path, tree: Path, template_id: str) -> dict[str, object]:
        return self.run_cli(
            "find",
            "--tree",
            str(tree),
            "--template-id",
            template_id,
            cwd=project,
        )["nodes"][0]

    def test_scoped_packet_orders_sources_projects_blockers_and_excludes_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, config = self.prepare_context(project)
            work_order_id = "packet-scope"
            runtime_id = lambda template_id: f"rt_{work_order_id}__root__{template_id}"
            artifact_root = context / "work-orders" / work_order_id / "artifacts"
            source_a_artifact = artifact_root / "source-a.md"
            source_b_artifact = artifact_root / "source-b.md"
            source_a_artifact.parent.mkdir(parents=True)
            source_a_artifact.write_text("source a\n", encoding="utf-8")
            source_b_artifact.write_text("source b\n", encoding="utf-8")
            specs = [
                *[
                    {
                        "template_id": f"unrelated-{index:03d}",
                        "title": f"Unrelated sibling {index:03d}",
                    }
                    for index in range(128)
                ],
                {"template_id": "source-a", "instructions": "private source instructions"},
                {"template_id": "source-b"},
                {
                    "template_id": "decision-gate",
                    "type": "gate",
                    "metadata.gate.outcomes": '["approved","rejected"]',
                    "metadata.gate.decision_required": "true",
                    "metadata.gate.outcome_key": "gate.outcome",
                },
                {"template_id": "blocker"},
                {
                    "template_id": "target",
                    "depends_on_template": "local:blocker",
                    "instructions": "Execute only the target.",
                    "inputs": "Scoped sources.",
                    "deliverables": "Target result.",
                    "acceptance": "Packet remains scoped.",
                    "metadata.control_packet.category.decision-records.selectors": (
                        f'["node:{runtime_id("decision-gate")}"]'
                    ),
                    "metadata.control_packet.category.decision-records.min_sources": "1",
                    "metadata.control_packet.category.decision-records.artifact_min": "0",
                    "metadata.control_packet.category.supporting-records.selectors": (
                        f'["node:{runtime_id("source-a")}","bb:source.ids"]'
                    ),
                    "metadata.control_packet.category.supporting-records.min_sources": "2",
                    "metadata.control_packet.category.supporting-records.artifact_min": "2",
                    "metadata.control_packet.blackboard_keys": '["decision.outcome"]',
                },
            ]
            template = project / "packet.xml"
            self.write_template(
                template,
                config,
                specs,
                blackboard={
                    "source.ids": json.dumps([runtime_id("source-b")], separators=(",", ":")),
                    "decision.outcome": "approved",
                    "unselected.secret": "must-not-leak",
                },
            )
            tree = self.init_runtime(project, context, template, work_order_id)
            target = self.find(project, tree, "target")

            unavailable = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(unavailable["error"]["code"], "control_packet_unavailable")
            self.assertIn(
                "source_not_terminal",
                {item["code"] for item in unavailable["error"]["details"]["violations"]},
            )

            source_a = self.find(project, tree, "source-a")
            self.run_cli("start", "--tree", str(tree), "--node", str(source_a["id"]), cwd=project)
            self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(source_a["id"]),
                "--summary",
                "Source A is complete.",
                "--artifact",
                str(source_a_artifact),
                cwd=project,
            )
            source_b = self.find(project, tree, "source-b")
            self.run_cli("start", "--tree", str(tree), "--node", str(source_b["id"]), cwd=project)
            self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(source_b["id"]),
                "--summary",
                "Source B is complete.",
                "--artifact",
                str(source_b_artifact),
                cwd=project,
            )
            gate = self.find(project, tree, "decision-gate")
            self.run_cli("start", "--tree", str(tree), "--node", str(gate["id"]), cwd=project)
            self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(gate["id"]),
                "--summary",
                "The gate approved the target.",
                "--gate-outcome",
                "approved",
                "--decision",
                "Proceed with scoped work.",
                cwd=project,
            )

            response = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                cwd=project,
            )
            packet = response["packet"]
            self.assertEqual(packet["schema_version"], 1)
            self.assertEqual(packet["target"]["id"], target["id"])
            self.assertNotIn("children", packet["target"])
            self.assertEqual(
                [category["name"] for category in packet["source_categories"]],
                ["decision-records", "supporting-records"],
            )
            supporting = packet["source_categories"][1]
            self.assertEqual(
                [source["node_id"] for source in supporting["sources"]],
                [source_a["id"], source_b["id"]],
            )
            self.assertEqual(supporting["sources"][1]["summary"], "Source B is complete.")
            self.assertNotIn("instructions", supporting["sources"][0])
            self.assertNotIn("attributes", supporting["sources"][0])
            self.assertEqual(packet["blackboard"], [{"key": "decision.outcome", "value": "approved"}])
            self.assertEqual(packet["control"]["action"], "wait")
            self.assertFalse(packet["control"]["ready"])
            self.assertEqual(packet["blockers"][0]["reason"], "dependency_incomplete")
            self.assertEqual(packet["blockers"][0]["dependency_ids"], [runtime_id("blocker")])

            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            self.assertNotIn("unselected.secret", serialized)
            self.assertNotIn("must-not-leak", serialized)
            self.assertNotIn('"source.ids"', serialized)
            for index in range(128):
                self.assertNotIn(runtime_id(f"unrelated-{index:03d}"), serialized)
            snapshot = self.run_cli("snapshot", "--tree", str(tree), cwd=project)
            packet_bytes = len(serialized.encode("utf-8"))
            snapshot_bytes = len(
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            self.assertLess(packet_bytes / snapshot_bytes, 0.25)

            blocker = self.find(project, tree, "blocker")
            self.run_cli("start", "--tree", str(tree), "--node", str(blocker["id"]), cwd=project)
            self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(blocker["id"]),
                "--summary",
                "Dependency resolved.",
                cwd=project,
            )
            ready_packet = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                cwd=project,
            )["packet"]
            self.assertEqual(ready_packet["blockers"], [])
            self.assertEqual(ready_packet["control"]["action"], "start")
            self.assertTrue(ready_packet["control"]["ready"])
            self.run_cli("start", "--tree", str(tree), "--node", str(target["id"]), cwd=project)
            self.run_cli(
                "block",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                "--reason",
                "A recoverable external prerequisite is missing.",
                cwd=project,
            )
            blocked_packet = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                cwd=project,
            )["packet"]
            self.assertEqual(blocked_packet["control"]["action"], "resolve-and-unblock")
            self.assertEqual(
                blocked_packet["blockers"],
                [
                    {
                        "reason": "node_status",
                        "block_reason": "A recoverable external prerequisite is missing.",
                    }
                ],
            )

            unrelated = self.find(project, tree, "unrelated-000")
            not_declared = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(unrelated["id"]),
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(not_declared["error"]["code"], "control_packet_not_declared")

            self.run_cli(
                "set",
                "--tree",
                str(tree),
                "--set",
                "source.ids="
                + json.dumps(
                    [runtime_id("source-a"), runtime_id("source-b")],
                    separators=(",", ":"),
                ),
                cwd=project,
            )
            duplicate = self.run_cli(
                "control-packet",
                "--tree",
                str(tree),
                "--node",
                str(target["id"]),
                cwd=project,
                expected_code=2,
            )
            duplicate_violations = duplicate["error"]["details"]["violations"]
            self.assertEqual(
                len([item for item in duplicate_violations if item["code"] == "duplicate_source"]),
                2,
            )

    def write_valid_document(self, path: Path, tree_ref: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"""---
schema_version: 1
document_kind: node-artifact
work_order_id: completion-receipt
node_id: validate-output
feature_ids: []
orchestration:
  tree_ref: '{tree_ref.as_posix()}'
---

# Validation Output

The document is valid.
""",
            encoding="utf-8",
        )

    def completion_template(
        self,
        project: Path,
        context: Path,
        config: dict[str, object],
        document: Path,
        name: str,
    ) -> Path:
        template = project / f"{name}.xml"
        subject = str(document.resolve())
        self.write_template(
            template,
            config,
            [
                {
                    "template_id": "checked",
                    "metadata.completion.required_fields": '["summary","validation"]',
                    "metadata.completion.artifacts.min": "1",
                    "metadata.completion.artifacts.max": "1",
                    "metadata.completion.artifacts.path": f"literal:{subject}",
                    "metadata.completion.checks": '["xc-document"]',
                    "metadata.completion.check.xc-document.subject": f"literal:{subject}",
                    "metadata.completion.check.xc-document.facts.document_kind": "literal:node-artifact",
                    "metadata.completion.check.xc-document.facts.content_language": "literal:en",
                    "metadata.completion.check.xc-document.facts.audience": "literal:internal",
                }
            ],
        )
        return template

    def validate_document(self, document: Path) -> tuple[int, dict[str, object], str]:
        result = subprocess.run(
            [sys.executable, str(DOCUMENT_VALIDATOR), "--document", str(document)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout), result.stdout

    def test_completion_receipts_are_normalized_untrusted_and_atomically_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, config = self.prepare_context(project)
            document = context / "artifacts" / "checked.md"
            template = self.completion_template(project, context, config, document, "completion")
            tree = self.init_runtime(project, context, template, "completion-receipt")
            self.write_valid_document(document, tree)
            node = self.find(project, tree, "checked")
            self.run_cli("start", "--tree", str(tree), "--node", str(node["id"]), cwd=project)
            code, validator, raw_validator = self.validate_document(document)
            self.assertEqual(code, 0)
            self.assertTrue(validator["ok"])
            self.assertEqual(validator["receipt"]["subject"], validator["path"])
            normalized = json.dumps(
                validator["receipt"],
                ensure_ascii=False,
                separators=(",", ":"),
            )

            before = tree.read_bytes()
            revision = self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"]
            requirement_cases = (
                (
                    [
                        "--validation",
                        "passed",
                        "--artifact",
                        str(document.resolve()),
                        "--check-result-json",
                        normalized,
                    ],
                    "required field",
                ),
                (
                    [
                        "--summary",
                        "Validated.",
                        "--validation",
                        "passed",
                        "--check-result-json",
                        normalized,
                    ],
                    "artifact cardinality",
                ),
                (
                    [
                        "--summary",
                        "Validated.",
                        "--validation",
                        "passed",
                        "--artifact",
                        str(document.with_name("wrong.md").resolve()),
                        "--check-result-json",
                        normalized,
                    ],
                    "artifact path",
                ),
            )
            for arguments, label in requirement_cases:
                with self.subTest(requirement=label):
                    rejected = self.run_cli(
                        "complete",
                        "--tree",
                        str(tree),
                        "--node",
                        str(node["id"]),
                        *arguments,
                        cwd=project,
                        expected_code=2,
                    )
                    self.assertEqual(rejected["error"]["code"], "completion_requirements_failed")
                    self.assertEqual(tree.read_bytes(), before)
            raw_rejected = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Validated.",
                "--validation",
                "passed",
                "--artifact",
                str(document.resolve()),
                "--check-result-json",
                raw_validator,
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(raw_rejected["error"]["code"], "invalid_check_result")
            self.assertEqual(tree.read_bytes(), before)
            self.assertEqual(
                self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"],
                revision,
            )

            false_receipt = dict(validator["receipt"])
            false_receipt["ok"] = False
            failed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Validated.",
                "--validation",
                "passed",
                "--artifact",
                str(document.resolve()),
                "--check-result-json",
                json.dumps(false_receipt),
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(failed["error"]["code"], "completion_requirements_failed")
            self.assertEqual(tree.read_bytes(), before)

            extra = dict(validator["receipt"])
            extra["extra"] = "not allowed"
            extra_rejected = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Validated.",
                "--validation",
                "passed",
                "--artifact",
                str(document.resolve()),
                "--check-result-json",
                json.dumps(extra),
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(extra_rejected["error"]["code"], "invalid_check_result")
            oversized = json.dumps(
                {
                    "schema_version": 1,
                    "check": "xc-document",
                    "ok": True,
                    "subject": "x" * 9000,
                    "facts": {},
                }
            )
            size_rejected = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--check-result-json",
                oversized,
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(size_rejected["error"]["code"], "invalid_check_result")

            duplicate_rejected = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Validated.",
                "--validation",
                "passed",
                "--artifact",
                str(document.resolve()),
                "--check-result-json",
                normalized,
                "--check-result-json",
                normalized,
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(duplicate_rejected["error"]["code"], "invalid_check_result")
            completed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Validated.",
                "--validation",
                "passed",
                "--artifact",
                str(document.resolve()),
                "--check-result-json",
                normalized,
                cwd=project,
            )
            self.assertEqual(completed["node"]["result"]["checks"], [validator["receipt"]])

            forged_document = context / "artifacts" / "forged.md"
            forged_template = self.completion_template(
                project,
                context,
                config,
                forged_document,
                "forged-completion",
            )
            forged_tree = self.init_runtime(project, context, forged_template, "forged-receipt")
            forged_node = self.find(project, forged_tree, "checked")
            self.run_cli(
                "start",
                "--tree",
                str(forged_tree),
                "--node",
                str(forged_node["id"]),
                cwd=project,
            )
            forged_receipt = {
                "schema_version": 1,
                "check": "xc-document",
                "ok": True,
                "subject": str(forged_document.resolve()),
                "facts": {
                    "document_kind": "node-artifact",
                    "content_language": "en",
                    "audience": "internal",
                },
            }
            forged = self.run_cli(
                "complete",
                "--tree",
                str(forged_tree),
                "--node",
                str(forged_node["id"]),
                "--summary",
                "Caller self-reported success.",
                "--validation",
                "self-reported",
                "--artifact",
                str(forged_document.resolve()),
                "--check-result-json",
                json.dumps(forged_receipt),
                cwd=project,
            )
            self.assertEqual(forged["node"]["status"], "succeeded")
            self.assertFalse(forged_document.exists())

            for operation in ("fail", "block"):
                bypass_document = context / "artifacts" / f"{operation}.md"
                bypass_template = self.completion_template(
                    project,
                    context,
                    config,
                    bypass_document,
                    f"{operation}-completion",
                )
                bypass_tree = self.init_runtime(
                    project,
                    context,
                    bypass_template,
                    f"{operation}-completion",
                )
                bypass_node = self.find(project, bypass_tree, "checked")
                self.run_cli(
                    "start",
                    "--tree",
                    str(bypass_tree),
                    "--node",
                    str(bypass_node["id"]),
                    cwd=project,
                )
                terminal = self.run_cli(
                    operation,
                    "--tree",
                    str(bypass_tree),
                    "--node",
                    str(bypass_node["id"]),
                    "--reason",
                    f"{operation} bypasses success requirements",
                    cwd=project,
                )
                self.assertEqual(
                    terminal["node"]["status"],
                    "failed" if operation == "fail" else "blocked",
                )

    def test_opt_in_completion_rolls_back_failed_commit_and_legacy_shape_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, config = self.prepare_context(project, auto_commit=True)
            outside = project / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            template = project / "rollback.xml"
            self.write_template(
                template,
                config,
                [
                    {
                        "template_id": "checked",
                        "metadata.completion.required_fields": '["summary"]',
                        "metadata.completion.artifacts.min": "1",
                        "metadata.completion.artifacts.max": "1",
                        "metadata.completion.artifacts.path": f"literal:{outside.resolve()}",
                    }
                ],
            )
            tree = self.init_runtime(project, context, template, "completion-rollback")
            node = self.find(project, tree, "checked")
            self.run_cli("start", "--tree", str(tree), "--node", str(node["id"]), cwd=project)
            before = tree.read_bytes()
            revision = self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"]
            rejected = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                "--summary",
                "Requirements match before persistence.",
                "--artifact",
                str(outside.resolve()),
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(rejected["error"]["details"]["status"], "persisted_uncommitted")
            self.assertEqual(tree.read_bytes(), before)
            shown = self.run_cli(
                "show",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                cwd=project,
            )["node"]
            self.assertEqual(shown["status"], "running")
            self.assertEqual(shown["result"], {})
            self.assertEqual(
                self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"],
                revision,
            )
            committed_artifact = context / "artifacts" / "committed.md"
            committed_artifact.parent.mkdir(parents=True, exist_ok=True)
            committed_artifact.write_text("committed\n", encoding="utf-8")
            committed_template = project / "committed.xml"
            self.write_template(
                committed_template,
                config,
                [
                    {
                        "template_id": "checked",
                        "metadata.completion.required_fields": '["summary"]',
                        "metadata.completion.artifacts.min": "1",
                        "metadata.completion.artifacts.max": "1",
                        "metadata.completion.artifacts.path": f"literal:{committed_artifact.resolve()}",
                    }
                ],
            )
            committed_tree = self.init_runtime(
                project,
                context,
                committed_template,
                "completion-commit",
            )
            committed_node = self.find(project, committed_tree, "checked")
            self.run_cli(
                "start",
                "--tree",
                str(committed_tree),
                "--node",
                str(committed_node["id"]),
                cwd=project,
            )
            committed = self.run_cli(
                "complete",
                "--tree",
                str(committed_tree),
                "--node",
                str(committed_node["id"]),
                "--summary",
                "Committed with requirements.",
                "--artifact",
                str(committed_artifact.resolve()),
                cwd=project,
            )
            self.assertEqual(committed["commit"]["status"], "committed")

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "legacy"
            context, config = self.prepare_context(project)
            template = project / "legacy.xml"
            self.write_template(template, config, [{"template_id": "legacy"}])
            tree = self.init_runtime(project, context, template, "legacy-complete")
            next_payload = self.run_cli("next", "--tree", str(tree), cwd=project)
            self.assertEqual(
                set(next_payload),
                {
                    "ok",
                    "tree_path",
                    "status",
                    "integrity",
                    "revision",
                    "counts",
                    "awaiting_dynamic_groups",
                    "ready",
                },
            )
            node = next_payload["ready"][0]
            self.run_cli("start", "--tree", str(tree), "--node", str(node["id"]), cwd=project)
            completed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(node["id"]),
                cwd=project,
            )
            self.assertEqual(completed["node"]["result"], {})

    def test_structured_gate_outcomes_are_atomic_and_legacy_gates_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            context, config = self.prepare_context(project)
            template = project / "gates.xml"
            self.write_template(
                template,
                config,
                [
                    {
                        "template_id": "structured-gate",
                        "type": "gate",
                        "metadata.gate.outcomes": '["approved","rejected"]',
                        "metadata.gate.decision_required": "true",
                        "metadata.gate.outcome_key": "gate.outcome",
                    },
                    {"template_id": "legacy-gate", "type": "gate"},
                    {"template_id": "ordinary-task"},
                ],
            )
            tree = self.init_runtime(project, context, template, "gate-outcomes")
            gate = self.find(project, tree, "structured-gate")
            self.run_cli("start", "--tree", str(tree), "--node", str(gate["id"]), cwd=project)
            before = tree.read_bytes()
            revision = self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"]
            cases = (
                ([], "gate_outcome_required"),
                (["--gate-outcome", "unknown", "--decision", "No."], "invalid_gate_outcome"),
                (["--gate-outcome", "approved"], "gate_decision_required"),
                (
                    [
                        "--gate-outcome",
                        "approved",
                        "--decision",
                        "Proceed.",
                        "--set",
                        "gate.outcome=rejected",
                    ],
                    "gate_outcome_conflict",
                ),
            )
            for arguments, code in cases:
                rejected = self.run_cli(
                    "complete",
                    "--tree",
                    str(tree),
                    "--node",
                    str(gate["id"]),
                    *arguments,
                    cwd=project,
                    expected_code=2,
                )
                self.assertEqual(rejected["error"]["code"], code)
                self.assertEqual(tree.read_bytes(), before)
                self.assertEqual(
                    self.run_cli("summary", "--tree", str(tree), cwd=project)["revision"],
                    revision,
                )
            completed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(gate["id"]),
                "--summary",
                "Approved.",
                "--gate-outcome",
                "approved",
                "--decision",
                "Proceed.",
                cwd=project,
            )
            self.assertEqual(completed["node"]["result"]["gate_outcome"], "approved")
            self.assertEqual(completed["node"]["result"]["decision"], "Proceed.")
            self.assertEqual(
                self.run_cli("summary", "--tree", str(tree), cwd=project)["blackboard"]["gate.outcome"],
                "approved",
            )

            legacy = self.find(project, tree, "legacy-gate")
            self.run_cli("start", "--tree", str(tree), "--node", str(legacy["id"]), cwd=project)
            legacy_completed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(legacy["id"]),
                cwd=project,
            )
            self.assertEqual(legacy_completed["node"]["result"], {})

            ordinary = self.find(project, tree, "ordinary-task")
            self.run_cli("start", "--tree", str(tree), "--node", str(ordinary["id"]), cwd=project)
            not_allowed = self.run_cli(
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(ordinary["id"]),
                "--gate-outcome",
                "approved",
                cwd=project,
                expected_code=2,
            )
            self.assertEqual(not_allowed["error"]["code"], "gate_outcome_not_allowed")


if __name__ == "__main__":
    unittest.main()
