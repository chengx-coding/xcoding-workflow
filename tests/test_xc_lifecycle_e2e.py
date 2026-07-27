from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "scripts" / "orchestration.py"
RUN = REPOSITORY_ROOT / "skills" / "xc-create-run" / "scripts" / "create_run.py"
FEATURE = REPOSITORY_ROOT / "skills" / "xc-feature" / "scripts" / "manage_feature.py"
RENDER = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "render_document.py"
VALIDATE = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"
DOCUMENT_EVOLUTION_TEMPLATE = REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-template.xml"
DOCUMENT_TEMPLATES = REPOSITORY_ROOT / "skills" / "xc-document" / "assets" / "templates"
RUN_DOCUMENT_HEADINGS = {
    "run-goal": {
        "document_title": "Run Goal",
        "requested_outcome_heading": "Requested Outcome",
        "scope_and_constraints_heading": "Scope and Constraints",
        "acceptance_conditions_heading": "Acceptance Conditions",
    },
    "run-analysis": {
        "document_title": "Run Analysis",
        "evidence_and_current_state_heading": "Evidence and Current State",
        "reconciliation_heading": "Reconciliation",
        "impact_and_risks_heading": "Impact and Risks",
        "alternatives_heading": "Alternatives",
    },
    "run-solution": {
        "document_title": "Run Solution",
        "selected_change_heading": "Selected Change",
        "feature_baseline_impact_heading": "Feature Baseline Impact",
        "implementation_and_migration_strategy_heading": "Implementation and Migration Strategy",
        "verification_strategy_heading": "Verification Strategy",
    },
    "run-result": {
        "document_title": "Run Result",
        "actual_changes_heading": "Actual Changes",
        "validation_evidence_heading": "Validation Evidence",
        "baseline_synchronization_heading": "Baseline Synchronization",
        "deviations_and_residual_risks_heading": "Deviations and Residual Risks",
    },
}
ZH_RUN_DOCUMENT_HEADINGS = {
    "run-goal": {
        "document_title": "运行目标",
        "requested_outcome_heading": "请求结果",
        "scope_and_constraints_heading": "范围与约束",
        "acceptance_conditions_heading": "验收条件",
    },
    "run-analysis": {
        "document_title": "运行分析",
        "evidence_and_current_state_heading": "证据与当前状态",
        "reconciliation_heading": "对齐",
        "impact_and_risks_heading": "影响与风险",
        "alternatives_heading": "备选方案",
    },
    "run-solution": {
        "document_title": "运行方案",
        "selected_change_heading": "选定变更",
        "feature_baseline_impact_heading": "Feature 基线影响",
        "implementation_and_migration_strategy_heading": "实施与迁移策略",
        "verification_strategy_heading": "验证策略",
    },
    "run-result": {
        "document_title": "运行结果",
        "actual_changes_heading": "实际变更",
        "validation_evidence_heading": "验证证据",
        "baseline_synchronization_heading": "基线同步",
        "deviations_and_residual_risks_heading": "偏差与剩余风险",
    },
}


class XcLifecycleEndToEndTests(unittest.TestCase):
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

    def create_environment(self) -> tuple[Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project = root / "project"
        project.mkdir()
        self.run_git(project, "init")
        context_repo = root / "context"
        context = context_repo / ".xcoding"
        context.mkdir(parents=True)
        self.run_git(context_repo, "init")
        (context / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
        return root, project, context

    def create_run(self, context: Path, project: Path, run_id: str, feature_ids: list[str]) -> dict[str, object]:
        args = [
            "--context-dir",
            str(context),
            "--project-root",
            str(project),
            "--topic",
            run_id,
            "--run-id",
            run_id,
        ]
        for feature_id in feature_ids:
            args.extend(["--feature-id", feature_id])
        return self.run_json(RUN, *args, cwd=project)

    def initialize_tree(self, project: Path, template: Path, run: dict[str, object]) -> Path:
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(template),
            "--runtime-dir",
            str(run["runtime_dir"]),
            "--run-id",
            str(run["run_id"]),
            "--name",
            str(run["run_id"]),
            cwd=project,
        )
        return Path(str(initialized["tree_path"]))

    def set_values(self, project: Path, tree: Path, values: dict[str, str]) -> None:
        args = ["set", "--tree", str(tree)]
        for key, value in values.items():
            args.extend(["--set", f"{key}={value}"])
        self.run_json(RUNTIME, *args, cwd=project)

    def find_one(self, project: Path, tree: Path, template_id: str, instance_id: str = "") -> dict[str, object]:
        args = ["find", "--tree", str(tree), "--template-id", template_id]
        if instance_id:
            args.extend(["--instance-id", instance_id])
        payload = self.run_json(RUNTIME, *args, cwd=project)
        self.assertEqual(len(payload["nodes"]), 1, payload)
        return payload["nodes"][0]

    def complete_ready_task(
        self,
        project: Path,
        tree: Path,
        expected_template_id: str,
        artifact: Path | None = None,
        summary: str = "",
    ) -> None:
        ready = self.run_json(RUNTIME, "next", "--tree", str(tree), cwd=project)["ready"]
        self.assertEqual(ready[0]["template_id"], expected_template_id, ready)
        node_id = str(ready[0]["id"])
        self.run_json(RUNTIME, "start", "--tree", str(tree), "--node", node_id, "--agent", "test", cwd=project)
        args = [
            "complete",
            "--tree",
            str(tree),
            "--node",
            node_id,
            "--summary",
            summary or f"Completed {expected_template_id}.",
            "--validation",
            "test workflow step",
        ]
        if artifact:
            args.extend(["--artifact", str(artifact)])
        self.run_json(RUNTIME, *args, cwd=project)

    def complete_document(
        self,
        project: Path,
        tree: Path,
        run: dict[str, object],
        group_template_id: str,
        document_kind: str,
        document_path: Path,
        feature_ids: list[str],
        feature_id: str = "",
        instance_id: str = "",
        parent_instance_id: str = "",
        content_language: str = "en",
    ) -> None:
        parent = self.find_one(project, tree, group_template_id, parent_instance_id)
        instance_id = instance_id or group_template_id
        self.run_json(
            RUNTIME,
            "embed-subtree",
            "--tree",
            str(tree),
            "--parent",
            str(parent["id"]),
            "--template",
            str(DOCUMENT_EVOLUTION_TEMPLATE),
            "--instance-id",
            instance_id,
            cwd=project,
        )
        self.set_values(
            project,
            tree,
            {
                "document.path": str(document_path),
                "document.kind": document_kind,
                "document.template": str(DOCUMENT_TEMPLATES / f"{document_kind}.md"),
                "document.inputs": "none",
                "document.contract": "none",
                "document.content_language": content_language if document_kind in RUN_DOCUMENT_HEADINGS else "",
                "document.review_required": "false",
                "document.gate_required": "false",
                "document.review.open_issues": "false",
            },
        )
        writer = self.find_one(project, tree, "write-document", instance_id)
        self.run_json(
            RUNTIME,
            "start",
            "--tree",
            str(tree),
            "--node",
            str(writer["id"]),
            "--agent",
            "test",
            cwd=project,
        )
        render_args = [
            "--template",
            str(DOCUMENT_TEMPLATES / f"{document_kind}.md"),
            "--out",
            str(document_path),
            "--set",
            f"run_id={run['run_id']}",
            "--set",
            f"tree_ref={tree}",
        ]
        if document_kind.startswith("feature-"):
            render_args.extend(
                [
                    "--set",
                    f"feature_id={feature_id}",
                    "--set",
                    f"feature_title={feature_id}",
                    "--set",
                    f"node_id={writer['id']}",
                ]
            )
        elif document_kind in RUN_DOCUMENT_HEADINGS:
            render_args.extend(
                [
                    "--set",
                    f"content_language={content_language}",
                    "--set-json",
                    f"feature_ids={json.dumps(feature_ids)}",
                ]
            )
            headings = ZH_RUN_DOCUMENT_HEADINGS[document_kind] if content_language == "zh-CN" else RUN_DOCUMENT_HEADINGS[document_kind]
            for key, value in headings.items():
                render_args.extend(["--set", f"{key}={value}"])
        self.run_json(RENDER, *render_args, cwd=project)
        self.run_json(VALIDATE, "--document", str(document_path), "--expected-kind", document_kind, cwd=project)
        self.run_json(
            RUNTIME,
            "complete",
            "--tree",
            str(tree),
            "--node",
            str(writer["id"]),
            "--summary",
            f"Wrote {document_kind}.",
            "--validation",
            "document validation passed",
            "--artifact",
            str(document_path),
            cwd=project,
        )
        for template_id in ("validate-draft", "validate-final"):
            validator = self.find_one(project, tree, template_id, instance_id)
            self.run_json(
                RUNTIME,
                "start",
                "--tree",
                str(tree),
                "--node",
                str(validator["id"]),
                "--agent",
                "xc-document",
                cwd=project,
            )
            self.run_json(VALIDATE, "--document", str(document_path), "--expected-kind", document_kind, cwd=project)
            self.run_json(
                RUNTIME,
                "complete",
                "--tree",
                str(tree),
                "--node",
                str(validator["id"]),
                "--summary",
                f"Validated {document_kind}.",
                "--validation",
                "document validation passed",
                cwd=project,
            )

    def assert_complete(self, project: Path, tree: Path) -> None:
        summary = self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)
        self.assertEqual(summary["status"], "complete", summary)
        self.assertEqual(summary["ready"], [], summary)

    def test_new_feature_run_creates_baselines_and_closes(self) -> None:
        _, project, context = self.create_environment()
        feature_id = "payment-refund"
        run = self.create_run(context, project, "20260727-1000-new-feature", [feature_id])
        feature = self.run_json(FEATURE, "init", "--context-dir", str(context), "--feature-id", feature_id, cwd=project)
        feature_dir = Path(str(feature["feature_dir"]))
        tree = self.initialize_tree(project, REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-template.xml", run)
        self.set_values(
            project,
            tree,
            {
                "feature.approval_required": "false",
                "run.document_language": "zh-CN",
                "run.requires_implementation": "false",
                "run.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, "prepare-feature", feature_dir)
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", [feature_id], content_language="zh-CN")
        self.complete_document(project, tree, run, "analysis-group", "run-analysis", Path(str(run["run_dir"])) / "analysis.md", [feature_id], content_language="zh-CN")
        self.complete_document(project, tree, run, "run-solution-document", "run-solution", Path(str(run["run_dir"])) / "solution.md", [feature_id], content_language="zh-CN")
        self.complete_document(project, tree, run, "feature-contract-document", "feature-contract", feature_dir / "contract.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "feature-solution-document", "feature-solution", feature_dir / "solution.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "feature-verification-document", "feature-verification", feature_dir / "verification.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", [feature_id], content_language="zh-CN")
        self.assertIn("content_language: zh-CN", (Path(str(run["run_dir"])) / "goal.md").read_text(encoding="utf-8"))
        self.assertIn("# 运行结果", (Path(str(run["run_dir"])) / "result.md").read_text(encoding="utf-8"))
        self.complete_ready_task(project, tree, "finalize-feature")
        self.assert_complete(project, tree)

    def test_feature_adoption_run_creates_code_derived_baselines_and_closes(self) -> None:
        _, project, context = self.create_environment()
        feature_id = "legacy-ledger"
        run = self.create_run(context, project, "20260727-1000-feature-adoption", [feature_id])
        feature = self.run_json(FEATURE, "init", "--context-dir", str(context), "--feature-id", feature_id, cwd=project)
        feature_dir = Path(str(feature["feature_dir"]))
        tree = self.initialize_tree(
            project,
            REPOSITORY_ROOT / "skills" / "xc-feature-adoption" / "assets" / "feature-adoption-template.xml",
            run,
        )
        self.set_values(project, tree, {"feature.adoption_approval_required": "false", "run.document_language": "zh-CN"})
        self.complete_ready_task(project, tree, "prepare-adoption", feature_dir)
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", [feature_id], content_language="zh-CN")
        self.complete_document(project, tree, run, "analysis-group", "run-analysis", Path(str(run["run_dir"])) / "analysis.md", [feature_id], content_language="zh-CN")
        self.complete_document(project, tree, run, "feature-contract-document", "feature-contract", feature_dir / "contract.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "feature-solution-document", "feature-solution", feature_dir / "solution.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "feature-verification-document", "feature-verification", feature_dir / "verification.md", [feature_id], feature_id)
        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", [feature_id], content_language="zh-CN")
        self.assertIn("content_language: zh-CN", (Path(str(run["run_dir"])) / "analysis.md").read_text(encoding="utf-8"))
        self.assertNotIn("content_language:", (feature_dir / "contract.md").read_text(encoding="utf-8"))
        self.complete_ready_task(project, tree, "finalize-adoption")
        self.assert_complete(project, tree)

    def test_ordinary_run_without_feature_closes_without_creating_feature(self) -> None:
        _, project, context = self.create_environment()
        run = self.create_run(context, project, "20260727-1000-ordinary-run", [])
        tree = self.initialize_tree(project, REPOSITORY_ROOT / "skills" / "xc-run" / "assets" / "run-template.xml", run)
        self.set_values(
            project,
            tree,
            {
                "run.document_language": "zh-CN",
                "run.requires_analysis": "false",
                "run.requires_solution": "false",
                "run.solution_gate_required": "false",
                "run.requires_implementation": "false",
                "run.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, "prepare-run")
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", [], content_language="zh-CN")
        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", [], content_language="zh-CN")
        self.complete_ready_task(project, tree, "finalize-run")
        self.assertFalse((context / "features").exists())
        self.assertIn("# 运行目标", (Path(str(run["run_dir"])) / "goal.md").read_text(encoding="utf-8"))
        self.assert_complete(project, tree)

    def test_ordinary_run_reconciles_multiple_features_sequentially(self) -> None:
        _, project, context = self.create_environment()
        feature_ids = ["payment-refund", "ledger-report"]
        feature_dirs = [
            Path(str(self.run_json(FEATURE, "init", "--context-dir", str(context), "--feature-id", feature_id, cwd=project)["feature_dir"]))
            for feature_id in feature_ids
        ]
        run = self.create_run(context, project, "20260727-1000-multi-feature", feature_ids)
        tree = self.initialize_tree(project, REPOSITORY_ROOT / "skills" / "xc-run" / "assets" / "run-template.xml", run)
        self.set_values(
            project,
            tree,
            {
                "run.has_features": "true",
                "run.requires_analysis": "false",
                "run.requires_solution": "false",
                "run.solution_gate_required": "false",
                "run.requires_implementation": "false",
                "run.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, "prepare-run")
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", feature_ids)
        parent = self.find_one(project, tree, "reconciliation-group")
        reconciliation_template = REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-template.xml"

        for index, feature_id in enumerate(feature_ids):
            instance_id = f"reconcile-{feature_id}"
            self.run_json(
                RUNTIME,
                "embed-subtree",
                "--tree",
                str(tree),
                "--parent",
                str(parent["id"]),
                "--template",
                str(reconciliation_template),
                "--instance-id",
                instance_id,
                cwd=project,
            )
            self.set_values(
                project,
                tree,
                {
                    "reconciliation.feature_id": feature_id,
                    "reconciliation.needs_baseline_sync": "false",
                    "reconciliation.has_ambiguous_conflict": "false",
                },
            )
            self.complete_ready_task(project, tree, "load-feature-provenance")
            self.complete_ready_task(project, tree, "inspect-current-state")
            self.complete_document(
                project,
                tree,
                run,
                "analysis-document",
                "run-analysis",
                Path(str(run["run_dir"])) / "analysis.md",
                feature_ids,
                instance_id=f"{instance_id}-analysis",
                parent_instance_id=instance_id,
            )
            self.complete_ready_task(project, tree, "finalize-reconciliation")
            self.assertTrue(feature_dirs[index].is_dir())

        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", feature_ids)
        self.complete_ready_task(project, tree, "finalize-run")
        self.assert_complete(project, tree)

    def test_ordinary_run_synchronizes_evidence_backed_baseline_drift(self) -> None:
        _, project, context = self.create_environment()
        feature_id = "payment-refund"
        feature_dir = Path(
            str(self.run_json(FEATURE, "init", "--context-dir", str(context), "--feature-id", feature_id, cwd=project)["feature_dir"])
        )
        contract_path = feature_dir / "contract.md"
        self.run_json(
            RENDER,
            "--template",
            str(DOCUMENT_TEMPLATES / "feature-contract.md"),
            "--out",
            str(contract_path),
            "--set",
            "run_id=20260726-0900-original-baseline",
            "--set",
            "tree_ref=none",
            "--set",
            f"feature_id={feature_id}",
            "--set",
            f"feature_title={feature_id}",
            "--set",
            "node_id=original-baseline",
            cwd=project,
        )
        original_contract = contract_path.read_text(encoding="utf-8")
        run = self.create_run(context, project, "20260727-1000-baseline-sync", [feature_id])
        tree = self.initialize_tree(project, REPOSITORY_ROOT / "skills" / "xc-run" / "assets" / "run-template.xml", run)
        self.set_values(
            project,
            tree,
            {
                "run.has_features": "true",
                "run.requires_analysis": "false",
                "run.requires_solution": "false",
                "run.solution_gate_required": "false",
                "run.requires_implementation": "false",
                "run.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, "prepare-run")
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", [feature_id])
        reconciliation_group = self.find_one(project, tree, "reconciliation-group")
        reconciliation_instance = "reconcile-payment-refund"
        self.run_json(
            RUNTIME,
            "embed-subtree",
            "--tree",
            str(tree),
            "--parent",
            str(reconciliation_group["id"]),
            "--template",
            str(REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-template.xml"),
            "--instance-id",
            reconciliation_instance,
            cwd=project,
        )
        self.set_values(
            project,
            tree,
            {
                "reconciliation.feature_id": feature_id,
                "reconciliation.needs_baseline_sync": "true",
                "reconciliation.has_ambiguous_conflict": "false",
            },
        )
        self.complete_ready_task(project, tree, "load-feature-provenance")
        self.complete_ready_task(project, tree, "inspect-current-state")
        self.complete_document(
            project,
            tree,
            run,
            "analysis-document",
            "run-analysis",
            Path(str(run["run_dir"])) / "analysis.md",
            [feature_id],
            instance_id=f"{reconciliation_instance}-analysis",
            parent_instance_id=reconciliation_instance,
        )
        self.complete_document(
            project,
            tree,
            run,
            "baseline-sync",
            "feature-contract",
            contract_path,
            [feature_id],
            feature_id,
            instance_id=f"{reconciliation_instance}-contract-sync",
            parent_instance_id=reconciliation_instance,
        )
        self.assertNotEqual(contract_path.read_text(encoding="utf-8"), original_contract)
        self.assertEqual(self.find_one(project, tree, "baseline-sync", reconciliation_instance)["status"], "succeeded")
        self.assertEqual(self.find_one(project, tree, "conflict-gate", reconciliation_instance)["status"], "skipped")
        self.complete_ready_task(project, tree, "finalize-reconciliation")
        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", [feature_id])
        self.complete_ready_task(project, tree, "finalize-run")
        self.assert_complete(project, tree)

    def test_ordinary_run_resolves_conflict_before_synchronizing_baseline(self) -> None:
        _, project, context = self.create_environment()
        feature_id = "ledger-report"
        feature_dir = Path(
            str(self.run_json(FEATURE, "init", "--context-dir", str(context), "--feature-id", feature_id, cwd=project)["feature_dir"])
        )
        run = self.create_run(context, project, "20260727-1000-conflict-gate", [feature_id])
        tree = self.initialize_tree(project, REPOSITORY_ROOT / "skills" / "xc-run" / "assets" / "run-template.xml", run)
        self.set_values(
            project,
            tree,
            {
                "run.has_features": "true",
                "run.requires_analysis": "false",
                "run.requires_solution": "false",
                "run.solution_gate_required": "false",
                "run.requires_implementation": "false",
                "run.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, "prepare-run")
        self.complete_document(project, tree, run, "goal-document", "run-goal", Path(str(run["run_dir"])) / "goal.md", [feature_id])
        reconciliation_group = self.find_one(project, tree, "reconciliation-group")
        reconciliation_instance = "reconcile-ledger-report"
        self.run_json(
            RUNTIME,
            "embed-subtree",
            "--tree",
            str(tree),
            "--parent",
            str(reconciliation_group["id"]),
            "--template",
            str(REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-template.xml"),
            "--instance-id",
            reconciliation_instance,
            cwd=project,
        )
        self.set_values(
            project,
            tree,
            {
                "reconciliation.feature_id": feature_id,
                "reconciliation.needs_baseline_sync": "false",
                "reconciliation.has_ambiguous_conflict": "true",
            },
        )
        self.complete_ready_task(project, tree, "load-feature-provenance")
        self.complete_ready_task(project, tree, "inspect-current-state")
        self.complete_document(
            project,
            tree,
            run,
            "analysis-document",
            "run-analysis",
            Path(str(run["run_dir"])) / "analysis.md",
            [feature_id],
            instance_id=f"{reconciliation_instance}-analysis",
            parent_instance_id=reconciliation_instance,
        )
        self.complete_ready_task(
            project,
            tree,
            "conflict-gate",
            summary="User approved synchronizing the contract baseline after reviewing the conflict.",
        )
        conflict_gate = self.find_one(project, tree, "conflict-gate", reconciliation_instance)
        self.assertEqual(conflict_gate["result"]["summary"], "User approved synchronizing the contract baseline after reviewing the conflict.")
        self.set_values(project, tree, {"reconciliation.needs_baseline_sync": "true"})
        self.assertEqual(self.find_one(project, tree, "baseline-sync", reconciliation_instance)["status"], "pending")
        self.complete_document(
            project,
            tree,
            run,
            "baseline-sync",
            "feature-contract",
            feature_dir / "contract.md",
            [feature_id],
            feature_id,
            instance_id=f"{reconciliation_instance}-contract-sync",
            parent_instance_id=reconciliation_instance,
        )
        self.complete_ready_task(project, tree, "finalize-reconciliation")
        self.complete_document(project, tree, run, "result-document", "run-result", Path(str(run["run_dir"])) / "result.md", [feature_id])
        self.complete_ready_task(project, tree, "finalize-run")
        self.assert_complete(project, tree)


if __name__ == "__main__":
    unittest.main()
