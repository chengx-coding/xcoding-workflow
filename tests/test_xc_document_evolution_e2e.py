from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RENDER = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "render_document.py"
VALIDATE = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"
DOCUMENT_EVOLUTION_TEMPLATE = REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-template.xml"
WORK_ORDER_GOAL_TEMPLATE = (
    REPOSITORY_ROOT / "skills" / "xc-document" / "assets" / "templates" / "work-order-goal.md"
)


class XcDocumentEvolutionEndToEndTests(unittest.TestCase):
    def run_json(self, script: Path, *args: str, cwd: Path) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def run_git(self, directory: Path, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def create_document_flow(
        self,
        work_order_id: str,
        review_required: bool,
        gate_required: bool,
    ) -> tuple[Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project = root / "project"
        project.mkdir()
        self.run_git(project, "init")
        workshop_repo = root / "workshop"
        workshop = workshop_repo / ".xcoding"
        workshop.mkdir(parents=True)
        self.run_git(workshop_repo, "init")
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        workbench_path = workshop / "work-orders" / work_order_id
        runtime_path = workbench_path / "runtime"
        runtime_path.mkdir(parents=True)
        document_path = workbench_path / "goal.md"
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(DOCUMENT_EVOLUTION_TEMPLATE),
            "--runtime-path",
            str(runtime_path),
            "--work-order-id",
            work_order_id,
            "--name",
            "document evolution test",
            cwd=project,
        )
        tree = Path(str(initialized["tree_path"]))
        self.set_values(
            project,
            tree,
            {
                "document.path": str(document_path),
                "document.kind": "work-order-goal",
                "document.template": str(WORK_ORDER_GOAL_TEMPLATE),
                "document.inputs": "none",
                "document.contract": "none",
                "document.content_language": "en",
                "document.receipt.content_language": "en",
                "document.receipt.audience": "",
                "document.review_required": str(review_required).lower(),
                "document.gate_required": str(gate_required).lower(),
                "document.gate_outcome": "accepted",
                "document.review.open_issues": "false",
            },
        )
        return project, tree, document_path

    def set_values(self, project: Path, tree: Path, values: dict[str, str]) -> None:
        args = ["set", "--tree", str(tree)]
        for key, value in values.items():
            args.extend(["--set", f"{key}={value}"])
        self.run_json(RUNTIME, *args, cwd=project)

    def start_ready(self, project: Path, tree: Path, expected_template_id: str, agent: str) -> str:
        ready = self.run_json(RUNTIME, "next", "--tree", str(tree), cwd=project)["ready"]
        self.assertEqual(ready[0]["template_id"], expected_template_id, ready)
        node_id = str(ready[0]["id"])
        self.run_json(RUNTIME, "start", "--tree", str(tree), "--node", node_id, "--agent", agent, cwd=project)
        return node_id

    def complete_node(
        self,
        project: Path,
        tree: Path,
        node_id: str,
        summary: str,
        validation: str,
        artifact: Path | None = None,
        check_receipt: dict[str, object] | None = None,
        gate_outcome: str = "",
        decision: str = "",
    ) -> None:
        args = [
            "complete",
            "--tree",
            str(tree),
            "--node",
            node_id,
            "--summary",
            summary,
            "--validation",
            validation,
        ]
        if artifact:
            args.extend(["--artifact", str(artifact)])
        if check_receipt:
            args.extend(["--check-result-json", json.dumps(check_receipt, separators=(",", ":"))])
        if gate_outcome:
            args.extend(["--gate-outcome", gate_outcome])
        if decision:
            args.extend(["--decision", decision])
        self.run_json(RUNTIME, *args, cwd=project)

    def render_and_validate_goal(
        self,
        project: Path,
        document_path: Path,
        tree: Path,
        work_order_id: str,
        content_language: str = "en",
    ) -> None:
        headings = (
            {
                "document_title": f"{work_order_id} Goal",
                "requested_outcome_heading": "Requested Outcome",
                "scope_and_constraints_heading": "Scope and Constraints",
                "acceptance_conditions_heading": "Acceptance Conditions",
            }
            if content_language == "en"
            else {
                "document_title": "工作订单目标",
                "requested_outcome_heading": "请求结果",
                "scope_and_constraints_heading": "范围与约束",
                "acceptance_conditions_heading": "验收条件",
            }
        )
        args = [
            "--template",
            str(WORK_ORDER_GOAL_TEMPLATE),
            "--out",
            str(document_path),
            "--set",
            f"work_order_id={work_order_id}",
            "--set",
            f"tree_ref={tree}",
            "--set",
            f"content_language={content_language}",
            "--set-json",
            "feature_ids=[]",
        ]
        for key, value in headings.items():
            args.extend(["--set", f"{key}={value}"])
        self.run_json(
            RENDER,
            *args,
            cwd=project,
        )
        self.run_json(
            VALIDATE,
            "--document",
            str(document_path),
            "--expected-kind",
            "work-order-goal",
            cwd=project,
        )

    def complete_validation(self, project: Path, tree: Path, expected_template_id: str, document_path: Path) -> None:
        node_id = self.start_ready(project, tree, expected_template_id, "xc-document")
        validated = self.run_json(
            VALIDATE,
            "--document",
            str(document_path),
            "--expected-kind",
            "work-order-goal",
            cwd=project,
        )
        self.complete_node(
            project,
            tree,
            node_id,
            f"{expected_template_id} passed.",
            "xc-document validation passed",
            check_receipt=validated["receipt"],
        )

    def assert_complete(self, project: Path, tree: Path) -> None:
        summary = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(summary["status"], "complete", summary)
        self.assertEqual(summary["ready"], [], summary)

    def test_authoring_requirements_default_and_explicit_override_are_available(self) -> None:
        project, tree, _ = self.create_document_flow(
            "20260727-1050-authoring-requirements",
            review_required=False,
            gate_required=False,
        )

        summary = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(summary["blackboard"]["document.authoring_requirements"], "")

        requirement = "Lead with a decision table and keep the report under two pages."
        self.set_values(project, tree, {"document.authoring_requirements": requirement})
        updated = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(updated["blackboard"]["document.authoring_requirements"], requirement)

        writer = self.start_ready(project, tree, "write-document", "xc-document")
        node = self.run_json(RUNTIME, "show", "--tree", str(tree), "--node", writer, cwd=project)["node"]
        self.assertIn("document.authoring_requirements", node["instructions"])
        self.assertIn("human-readable authoring default", node["instructions"])

    def test_recovers_document_written_before_terminal_completion(self) -> None:
        work_order_id = "20260727-1100-document-recovery"
        project, tree, document_path = self.create_document_flow(
            work_order_id,
            review_required=False,
            gate_required=False,
        )
        writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, document_path, tree, work_order_id)

        interrupted = self.run_json(RUNTIME, "show", "--tree", str(tree), "--node", writer, cwd=project)["node"]
        self.assertEqual(interrupted["status"], "running")
        self.assertTrue(document_path.is_file())

        self.run_json(
            VALIDATE,
            "--document",
            str(document_path),
            "--expected-kind",
            "work-order-goal",
            cwd=project,
        )
        self.complete_node(
            project,
            tree,
            writer,
            "Recovered the interrupted document write.",
            "xc-document validation passed after recovery",
            document_path,
        )
        self.complete_validation(project, tree, "validate-draft", document_path)
        self.complete_validation(project, tree, "validate-final", document_path)
        self.assert_complete(project, tree)

    def test_writes_non_english_work_order_document_with_declared_language(self) -> None:
        work_order_id = "20260727-1100-document-language"
        project, tree, document_path = self.create_document_flow(
            work_order_id,
            review_required=False,
            gate_required=False,
        )
        self.set_values(project, tree, {"document.content_language": "zh-CN"})
        self.set_values(project, tree, {"document.receipt.content_language": "zh-CN"})
        writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, document_path, tree, work_order_id, "zh-CN")

        self.complete_node(project, tree, writer, "Wrote the Chinese goal document.", "xc-document validation passed", document_path)
        self.complete_validation(project, tree, "validate-draft", document_path)
        self.complete_validation(project, tree, "validate-final", document_path)

        content = document_path.read_text(encoding="utf-8")
        self.assertIn("content_language: zh-CN", content)
        self.assertIn("# 工作订单目标", content)
        self.assert_complete(project, tree)

    def test_review_revision_and_gate_close_document_evolution(self) -> None:
        work_order_id = "20260727-1100-document-review"
        project, tree, document_path = self.create_document_flow(
            work_order_id,
            review_required=True,
            gate_required=True,
        )
        writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, document_path, tree, work_order_id)
        self.complete_node(project, tree, writer, "Wrote the initial goal document.", "xc-document validation passed", document_path)
        self.complete_validation(project, tree, "validate-draft", document_path)

        review_artifact = document_path.parent / "artifacts" / "document-review.md"
        review_artifact.parent.mkdir(parents=True)
        review_artifact.write_text("# Review\n\nA revision is required.\n", encoding="utf-8")
        first_review = self.start_ready(project, tree, "review-document", "xc-review")
        self.set_values(project, tree, {"document.review.open_issues": "true"})
        self.complete_node(project, tree, first_review, "One required revision was found.", "review findings recorded", review_artifact)

        revision = self.start_ready(project, tree, "revise-document", "xc-document")
        document_path.write_text(document_path.read_text(encoding="utf-8") + "\nRevision applied from review findings.\n", encoding="utf-8")
        self.run_json(
            VALIDATE,
            "--document",
            str(document_path),
            "--expected-kind",
            "work-order-goal",
            cwd=project,
        )
        self.complete_node(project, tree, revision, "Applied the required revision.", "xc-document validation passed", document_path)

        review_artifact.write_text("# Review\n\nAll required findings are closed.\n", encoding="utf-8")
        final_review = self.start_ready(project, tree, "review-document", "xc-review")
        self.set_values(project, tree, {"document.review.open_issues": "false"})
        self.complete_node(project, tree, final_review, "No review findings remain.", "review findings recorded", review_artifact)

        gate = self.start_ready(project, tree, "document-gate", "main")
        gate_summary = "User confirmed the revised document."
        self.complete_node(
            project,
            tree,
            gate,
            gate_summary,
            "user decision recorded",
            gate_outcome="accepted",
            decision="Accept the revised document.",
        )
        gate_node = self.run_json(RUNTIME, "show", "--tree", str(tree), "--node", gate, cwd=project)["node"]
        self.assertEqual(gate_node["result"]["summary"], gate_summary)
        self.assertEqual(gate_node["result"]["gate_outcome"], "accepted")
        self.assertEqual(gate_node["result"]["decision"], "Accept the revised document.")

        self.complete_validation(project, tree, "validate-final", document_path)
        self.assertIn("Revision applied from review findings.", document_path.read_text(encoding="utf-8"))
        self.assert_complete(project, tree)

    def test_serialized_instances_isolate_terminal_review_loop_and_recovery_conditions(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project = root / "project"
        project.mkdir()
        self.run_git(project, "init")
        workshop = root / "workshop" / ".xcoding"
        workshop.mkdir(parents=True)
        config_path = workshop / "xc-orchestration-runtime.json"
        config_path.write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        parent_spec = root / "serialized-documents.json"
        parent_spec.write_text(
            json.dumps(
                {
                    "name": "serialized document instances",
                    "schema_version": 1,
                    "blackboard": {},
                    "root": {
                        "template_id": "root",
                        "title": "Serialized document instances",
                        "type": "composite",
                        "role": "root",
                        "mode": "sequence",
                        "executor": "main",
                        "children": [
                            {
                                "template_id": "document-instances",
                                "title": "Document instances",
                                "type": "composite",
                                "role": "dynamic-group",
                                "mode": "sequence",
                                "executor": "main",
                            },
                            {
                                "template_id": "finish",
                                "title": "Finish",
                                "type": "task",
                                "role": "finish",
                                "executor": "main",
                            },
                        ],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        parent_template = root / "serialized-documents.xml"
        self.run_json(
            AUTHOR,
            "build",
            "--spec",
            str(parent_spec),
            "--out",
            str(parent_template),
            "--config",
            str(config_path),
            cwd=project,
        )
        work_order_id = "20260811-serialized-documents"
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(parent_template),
            "--runtime-path",
            str(workshop / "work-orders" / work_order_id / "runtime"),
            "--work-order-id",
            work_order_id,
            cwd=project,
        )
        tree = Path(str(initialized["tree_path"]))
        group = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            "document-instances",
            cwd=project,
        )["nodes"][0]
        group_id = str(group["id"])

        def configure_document(path: Path, *, gate_required: bool) -> None:
            self.set_values(
                project,
                tree,
                {
                    "document.path": str(path),
                    "document.kind": "work-order-goal",
                    "document.template": str(WORK_ORDER_GOAL_TEMPLATE),
                    "document.inputs": "none",
                    "document.contract": "none",
                    "document.content_language": "en",
                    "document.receipt.content_language": "en",
                    "document.receipt.audience": "",
                    "document.review_required": "true",
                    "document.gate_required": str(gate_required).lower(),
                    "document.gate_outcome": "accepted",
                    "document.review.open_issues": "false",
                },
            )

        def embed(instance_id: str) -> None:
            self.run_json(
                RUNTIME,
                "embed-subtree",
                "--tree",
                str(tree),
                "--parent",
                group_id,
                "--template",
                str(DOCUMENT_EVOLUTION_TEMPLATE),
                "--instance-id",
                instance_id,
                cwd=project,
            )

        def find_instance(template_id: str, instance_id: str) -> dict[str, object]:
            return self.run_json(
                RUNTIME,
                "find",
                "--tree",
                str(tree),
                "--template-id",
                template_id,
                "--instance-id",
                instance_id,
                cwd=project,
            )["nodes"][0]

        workbench = workshop / "work-orders" / work_order_id
        first_document = workbench / "first-goal.md"
        configure_document(first_document, gate_required=False)
        embed("first-document")
        first_writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, first_document, tree, work_order_id)
        self.complete_node(project, tree, first_writer, "Wrote first document.", "xc-document passed", first_document)
        self.complete_validation(project, tree, "validate-draft", first_document)
        first_review_artifact = workbench / "artifacts" / "first-review.md"
        first_review_artifact.parent.mkdir(parents=True)
        first_review_artifact.write_text("# Review\n\nNo findings.\n", encoding="utf-8")
        first_review = self.start_ready(project, tree, "review-document", "xc-review")
        self.set_values(project, tree, {"document.review.open_issues": "false"})
        self.complete_node(project, tree, first_review, "No findings remain.", "review recorded", first_review_artifact)
        self.complete_validation(project, tree, "validate-final", first_document)

        first_loop_before = find_instance("review-loop", "first-document")
        first_revise_before = find_instance("revise-document", "first-document")
        first_recovery_before = find_instance("document-gate-recovery-group", "first-document")
        self.assertEqual(first_loop_before["status"], "succeeded")
        self.assertEqual(first_loop_before["attributes"]["loop.terminal_reason"], "break")
        self.assertEqual(first_revise_before["status"], "skipped")
        self.assertEqual(first_revise_before["attributes"]["when.latched"], "false")
        self.assertEqual(first_recovery_before["status"], "skipped")
        self.assertEqual(first_recovery_before["attributes"]["when.latched"], "false")

        second_document = workbench / "second-goal.md"
        configure_document(second_document, gate_required=True)
        embed("second-document")
        second_writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, second_document, tree, work_order_id)
        self.complete_node(project, tree, second_writer, "Wrote second document.", "xc-document passed", second_document)
        self.complete_validation(project, tree, "validate-draft", second_document)
        second_review_artifact = workbench / "artifacts" / "second-review.md"
        second_review_artifact.write_text("# Review\n\nRevision required.\n", encoding="utf-8")
        second_review = self.start_ready(project, tree, "review-document", "xc-review")
        self.set_values(project, tree, {"document.review.open_issues": "true"})
        self.complete_node(project, tree, second_review, "Revision required.", "review recorded", second_review_artifact)

        ready = self.run_json(RUNTIME, "next", "--tree", str(tree), cwd=project)["ready"]
        self.assertEqual(len(ready), 1, ready)
        self.assertEqual(ready[0]["template_id"], "revise-document")
        self.assertEqual(ready[0]["origin_instance_id"], "second-document")
        second_revise = str(ready[0]["id"])
        self.run_json(RUNTIME, "start", "--tree", str(tree), "--node", second_revise, "--agent", "xc-document", cwd=project)
        second_document.write_text(second_document.read_text(encoding="utf-8") + "\nRevision applied.\n", encoding="utf-8")
        self.complete_node(project, tree, second_revise, "Applied revision.", "document remains valid", second_document)

        final_review_artifact = workbench / "artifacts" / "second-final-review.md"
        final_review_artifact.write_text("# Review\n\nNo findings.\n", encoding="utf-8")
        final_review = self.start_ready(project, tree, "review-document", "xc-review")
        self.set_values(project, tree, {"document.review.open_issues": "false"})
        self.complete_node(project, tree, final_review, "No findings remain.", "review recorded", final_review_artifact)
        gate = self.start_ready(project, tree, "document-gate", "main")
        self.complete_node(
            project,
            tree,
            gate,
            "Revision requested.",
            "decision recorded",
            gate_outcome="revision-required",
            decision="Request another revision before acceptance.",
        )

        first_loop_after = find_instance("review-loop", "first-document")
        first_revise_after = find_instance("revise-document", "first-document")
        first_recovery_after = find_instance("document-gate-recovery-group", "first-document")
        second_recovery = find_instance("document-gate-recovery-group", "second-document")
        summary = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(first_loop_after["status"], "succeeded")
        self.assertEqual(first_loop_after["attributes"]["loop.terminal_reason"], "break")
        self.assertEqual(first_revise_after["status"], "skipped")
        self.assertEqual(first_recovery_after["status"], "skipped")
        self.assertEqual(second_recovery["status"], "pending")
        self.assertEqual(second_recovery["attributes"]["when.latched"], "true")
        self.assertEqual(summary["integrity"]["status"], "valid")
        self.assertEqual(summary["ready"], [])
        self.assertEqual(
            [item["id"] for item in summary["awaiting_dynamic_groups"]],
            [second_recovery["id"]],
        )

    def test_revision_required_gate_blocks_final_validation_until_recovery(self) -> None:
        work_order_id = "20260727-1100-document-gate-recovery"
        project, tree, document_path = self.create_document_flow(
            work_order_id,
            review_required=False,
            gate_required=True,
        )
        writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, document_path, tree, work_order_id)
        self.complete_node(project, tree, writer, "Wrote the initial goal.", "xc-document validation passed", document_path)
        self.complete_validation(project, tree, "validate-draft", document_path)

        gate = self.start_ready(project, tree, "document-gate", "main")
        self.complete_node(
            project,
            tree,
            gate,
            "The document requires revision.",
            "non-accepting decision recorded",
            gate_outcome="revision-required",
            decision="Revise the requested outcome before final validation.",
        )
        waiting = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(
            [item["template_id"] for item in waiting["awaiting_dynamic_groups"]],
            ["document-gate-recovery-group"],
            waiting,
        )
        final_validator = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            "validate-final",
            cwd=project,
        )["nodes"][0]
        rejected_start = subprocess.run(
            [
                sys.executable,
                str(RUNTIME),
                "start",
                "--tree",
                str(tree),
                "--node",
                str(final_validator["id"]),
                "--agent",
                "negative-gate-test",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(rejected_start.returncode, 2, rejected_start.stderr or rejected_start.stdout)
        self.assertEqual(json.loads(rejected_start.stdout)["error"]["code"], "node_not_ready")

        recovery_group = self.run_json(
            RUNTIME,
            "find",
            "--tree",
            str(tree),
            "--template-id",
            "document-gate-recovery-group",
            cwd=project,
        )["nodes"][0]
        recovery_gate = self.run_json(
            RUNTIME,
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            str(recovery_group["id"]),
            "--logical-key",
            "accept-revised-document",
            "--title",
            "Accept revised document",
            "--type",
            "gate",
            "--role",
            "document-recovery",
            "--executor",
            "main",
            "--instructions",
            "Confirm the revised document.",
            "--deliverables",
            "An accepting document decision.",
            "--acceptance",
            "Final validation remains closed until acceptance.",
            "--metadata",
            'metadata.completion.required_fields=["summary","validation"]',
            "--metadata",
            'metadata.gate.outcomes=["accepted","rejected","revision-required"]',
            "--metadata",
            "metadata.gate.decision_required=true",
            "--metadata",
            "metadata.gate.outcome_key=document.gate_outcome",
            cwd=project,
        )["node"]
        self.run_json(
            RUNTIME,
            "start",
            "--tree",
            str(tree),
            "--node",
            str(recovery_gate["id"]),
            "--agent",
            "main",
            cwd=project,
        )
        self.complete_node(
            project,
            tree,
            str(recovery_gate["id"]),
            "Accepted the revised document.",
            "recovery decision recorded",
            gate_outcome="accepted",
            decision="Accept the revised document.",
        )
        self.complete_validation(project, tree, "validate-final", document_path)
        self.assert_complete(project, tree)

    def test_structurally_matching_untrusted_receipt_is_accepted(self) -> None:
        work_order_id = "20260727-1100-untrusted-receipt"
        project, tree, document_path = self.create_document_flow(
            work_order_id,
            review_required=False,
            gate_required=False,
        )
        writer = self.start_ready(project, tree, "write-document", "xc-document")
        self.render_and_validate_goal(project, document_path, tree, work_order_id)
        self.complete_node(project, tree, writer, "Wrote the goal.", "document rendered", document_path)

        validator = self.start_ready(project, tree, "validate-draft", "caller")
        fabricated = {
            "schema_version": 1,
            "check": "xc-document",
            "ok": True,
            "subject": str(document_path.resolve()),
            "facts": {
                "document_kind": "work-order-goal",
                "content_language": "en",
                "audience": "",
            },
        }
        self.complete_node(
            project,
            tree,
            validator,
            "Caller supplied a matching receipt.",
            "receipt shape matched",
            check_receipt=fabricated,
        )
        stored = self.run_json(RUNTIME, "show", "--tree", str(tree), "--node", validator, cwd=project)["node"]
        self.assertEqual(stored["result"]["checks"], [fabricated])
        self.complete_validation(project, tree, "validate-final", document_path)
        self.assert_complete(project, tree)


if __name__ == "__main__":
    unittest.main()
