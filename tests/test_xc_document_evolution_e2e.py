from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "scripts" / "orchestration.py"
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
        (workshop / "xc-orchestration-runtime.toml").write_text(
            "[git]\nauto_commit = false\n",
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
                "document.review_required": str(review_required).lower(),
                "document.gate_required": str(gate_required).lower(),
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
        self.run_json(
            VALIDATE,
            "--document",
            str(document_path),
            "--expected-kind",
            "work-order-goal",
            cwd=project,
        )
        self.complete_node(project, tree, node_id, f"{expected_template_id} passed.", "xc-document validation passed")

    def assert_complete(self, project: Path, tree: Path) -> None:
        summary = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(summary["status"], "complete", summary)
        self.assertEqual(summary["ready"], [], summary)

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
        self.complete_node(project, tree, gate, gate_summary, "user decision recorded")
        gate_node = self.run_json(RUNTIME, "show", "--tree", str(tree), "--node", gate, cwd=project)["node"]
        self.assertEqual(gate_node["result"]["summary"], gate_summary)

        self.complete_validation(project, tree, "validate-final", document_path)
        self.assertIn("Revision applied from review findings.", document_path.read_text(encoding="utf-8"))
        self.assert_complete(project, tree)


if __name__ == "__main__":
    unittest.main()
