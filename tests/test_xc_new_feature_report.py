"""Tests for the new-feature mount of the `xc-change-report` stage.

The new-feature lifecycle is the second place the report obligation is mounted, and it
reproduced the defect the work-order mount fixed: an embedded subtree copies no blackboard
entry, so a guard reading a `report.*` key the parent never declared evaluates the empty
string, which equals neither `true` nor `false`. With `report.gate_recovery_required` absent
both of its reads fell false, so `report-gate-recovery-group` **and** `validate-final` were
skipped and the stage could end without final validation.

This module therefore asserts four properties at the specification level and two at the
runtime level:

* the specification declares a flat `report-group` between `verification-group` and
  `result-document` inside `approved-baseline-continuation`, gated on the commitment key;
* the declared caller-seeded `report.*` key set equals the frozen thirteen from §8 of the
  solution decision, and the mount instruction is the work-order mount's text verbatim, so
  the two lifecycles cannot drift apart;
* `prepare-feature` writes the mode-derived commitment and `finalize-feature` consumes the
  skip reason;
* an end-to-end drive that **never** sets `work_order.requires_report` selects
  `report-group` rather than silently skipping it;
* an end-to-end drive that embeds the report subtree and publishes **only** the thirteen
  caller-seeded keys reaches `validate-final == succeeded`. A selection-only assertion would
  pass while the final validation was still silently skippable, so the stage's completion is
  asserted separately from its selection.

The template is a generated artifact, so the same module also proves that the shipped
template is byte-identical to a fresh build of the shipped specification.

Standard library only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
OPEN_WORK_ORDER = REPOSITORY_ROOT / "skills" / "xc-open-work-order" / "scripts" / "open_work_order.py"
FEATURE = REPOSITORY_ROOT / "skills" / "xc-feature" / "scripts" / "manage_feature.py"
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"

SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-new-feature"
SPEC_PATH = SKILL_ROOT / "assets" / "new-feature-flow.json"
TEMPLATE_PATH = SKILL_ROOT / "assets" / "new-feature-template.xml"
SKILL_PAGE = SKILL_ROOT / "SKILL.md"

WORK_ORDER_SPEC_PATH = REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-flow.json"
CHANGE_REPORT_TEMPLATE = REPOSITORY_ROOT / "skills" / "xc-change-report" / "assets" / "change-report-template.xml"

COMMITMENT_KEY = "work_order.requires_report"
SKIP_REASON_KEY = "work_order.report_skip_reason"
BASELINE_KEY = "work_order.report_baseline"
REPORT_GROUP = "report-group"
PREPARE_NODE = "prepare-feature"
FINALIZE_NODE = "finalize-feature"
CONTRACT_FIELDS = ("instructions", "inputs", "deliverables", "acceptance")
MOUNT_TEXT_FIELDS = ("when", "instructions", "deliverables", "acceptance")

# The caller-seeded half of the report specification's declared key set, frozen by name and
# declared default. These are §8's values, and the work-order tree declares the same set with
# the same values, so the parent tree and the subtree it embeds cannot disagree about a key's
# starting value.
FROZEN_CALLER_KEYS: dict[str, str] = {
    "report.path": "",
    "report.manifest_path": "",
    "report.baseline_commit": "",
    "report.baseline_digest": "",
    "report.language": "en",
    "report.strength": "standard",
    "report.gate_required": "false",
    "report.gate_outcome": "not-run",
    "report.gate_rework_required": "false",
    "report.gate_recovery_required": "false",
    "report.round": "1",
    "report.refresh_count": "0",
    "report.refresh_reason": "initial",
}

# The recorded installation path, which the mount references instead of leaving the template
# discoverable only from a documentation table.
SETUP_RECORD = ".agents/.xcoding-setup/manifest.json"
TEMPLATE_FILE_NAME = "change-report-template.xml"

# The document groups the drive has to resolve before `approved-baseline-continuation` is
# selected. Each is closed empty, because this drive measures the report mount, not document
# evolution.
PRECEDING_DOCUMENT_GROUPS = (
    "goal-document",
    "analysis-group",
    "work-order-solution-document",
    "feature-contract-document",
    "feature-solution-document",
    "feature-verification-document",
)

# The completion receipt the report subtree's validators are given. The facts are exactly the
# eleven keys `validate-coverage` and `validate-final` resolve through `bb:` selectors.
REPORT_FACT_KEYS = (
    "units_total",
    "units_covered",
    "excluded_total",
    "pre_existing_total",
    "hash_bound",
    "token_bound",
    "coverage",
    "self_contained",
    "head_current",
    "strength",
    "rounds",
)


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []) or []:
        yield from iter_nodes(child)


def nodes_by_template(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("template_id", "")): node
        for node in iter_nodes(spec.get("root", {}))
    }


def contract_text(node: dict[str, Any]) -> str:
    """The node's own contract text: what the node claims it will do."""
    return "\n".join(str(node.get(field, "")) for field in CONTRACT_FIELDS)


def declared_report_keys(spec: dict[str, Any]) -> dict[str, str]:
    return {
        key: value
        for key, value in spec["blackboard"].items()
        if key.startswith("report.")
    }


class NewFeatureReportSpecTests(unittest.TestCase):
    """Specification-level assertions. These fail on the pre-change tree, which has no mount."""

    def test_the_report_group_is_declared_and_gated_on_the_commitment(self) -> None:
        """G-10, G-24: the group exists on this lifecycle and the guard is the commitment key."""
        spec = load_spec()
        matches = [node for node in iter_nodes(spec["root"]) if node.get("template_id") == REPORT_GROUP]
        self.assertEqual(
            len(matches),
            1,
            "the new-feature specification must declare exactly one report-group; before this "
            "change `git grep -ci report` over the specification and its template returned zero",
        )
        group = matches[0]
        self.assertEqual(group["type"], "composite")
        self.assertEqual(group["role"], "dynamic-group")
        self.assertEqual(group["mode"], "sequence")
        self.assertEqual(group["executor"], "main")
        self.assertEqual(group["when"], f"{COMMITMENT_KEY} == true")

    def test_the_report_group_sits_between_verification_and_result(self) -> None:
        """G-10: the mount is a flat node inside approved-baseline-continuation, not elsewhere."""
        spec = load_spec()
        by_id = nodes_by_template(spec)
        continuation = None
        for node in iter_nodes(spec["root"]):
            if node.get("template_id") == "approved-baseline-continuation":
                continuation = node
        self.assertIsNotNone(continuation, "approved-baseline-continuation must exist")
        self.assertIn(
            REPORT_GROUP,
            [child.get("template_id") for child in continuation["children"]],
            "report-group must be a direct child of approved-baseline-continuation",
        )
        order = [child.get("template_id") for child in continuation["children"]]
        self.assertEqual(
            order,
            [
                "implementation-group",
                "verification-group",
                REPORT_GROUP,
                "result-document",
                FINALIZE_NODE,
            ],
            "the report stage runs after verification and before the result document",
        )
        # The group is flat: it carries no children of its own and the subtree is embedded at
        # run time, exactly as on the work-order lifecycle.
        self.assertNotIn("children", by_id[REPORT_GROUP])
        self.assertEqual(by_id["verification-group"]["when"], "work_order.requires_verification == true")

    def test_the_commitment_keys_are_declared(self) -> None:
        """G-24: the three commitment keys are declared, and the commitment fails closed."""
        blackboard = load_spec()["blackboard"]
        self.assertEqual(blackboard[COMMITMENT_KEY], "true")
        self.assertEqual(blackboard[SKIP_REASON_KEY], "")
        self.assertEqual(blackboard[BASELINE_KEY], "")

    def test_the_declared_caller_key_set_equals_the_frozen_thirteen(self) -> None:
        """G-24: the caller half of the report key set is declared, by name and default."""
        declared = declared_report_keys(load_spec())
        self.assertEqual(
            declared,
            FROZEN_CALLER_KEYS,
            "the new-feature tree must declare exactly the thirteen caller-seeded report.* keys "
            "with their declared defaults and no other report.* key, because an embedded "
            "subtree's guards, loop condition and completion-fact selectors read this "
            "blackboard and nothing else",
        )
        self.assertEqual(len(declared), 13)

    def test_the_mount_text_is_the_work_order_mount_text(self) -> None:
        """G-24: the two mounts cannot drift apart, because one is the other's text."""
        ours = nodes_by_template(load_spec())[REPORT_GROUP]
        theirs = nodes_by_template(load_spec(WORK_ORDER_SPEC_PATH))[REPORT_GROUP]
        for field in MOUNT_TEXT_FIELDS:
            self.assertEqual(
                ours.get(field, ""),
                theirs.get(field, ""),
                f"report-group {field!r} must be the work-order mount's text verbatim",
            )
        self.assertEqual(ours["title"], theirs["title"])

    def test_mount_names_every_caller_key(self) -> None:
        """G-08, G-24: the caller's publication is named key by key, with edited values."""
        instructions = str(nodes_by_template(load_spec())[REPORT_GROUP]["instructions"])
        missing = sorted(key for key in FROZEN_CALLER_KEYS if key not in instructions)
        self.assertEqual(
            missing,
            [],
            "the mount instruction must name every caller-seeded report.* key, because a key "
            "the caller never publishes reads as an absent key inside the embedded subtree",
        )
        self.assertIn("thirteen caller-seeded keys", instructions)
        self.assertIn("never merely accepting their declared defaults", instructions)
        self.assertIn(
            "report.round is the 1-based index of the pass being entered",
            instructions,
            "the caller's share of the round convention is the pass index it publishes",
        )

    def test_mount_references_the_recorded_template_path(self) -> None:
        """G-48: the template path comes from the setup record, not a documentation table."""
        text = contract_text(nodes_by_template(load_spec())[REPORT_GROUP])
        self.assertIn(SETUP_RECORD, text)
        self.assertIn(TEMPLATE_FILE_NAME, text)
        self.assertIn("xc-change-report", text)

    def test_prepare_states_the_mode_derived_commitment_write(self) -> None:
        """G-10: the node that owns the commitment states the write, not only Skill prose."""
        node = nodes_by_template(load_spec())[PREPARE_NODE]
        instructions = str(node["instructions"])
        acceptance = str(node["acceptance"])

        self.assertIn(f"{COMMITMENT_KEY}=true", instructions)
        self.assertIn(f"{SKIP_REASON_KEY}=read_only_mode", instructions)
        self.assertIn(BASELINE_KEY, instructions)
        self.assertIn("missing commitment fails this node", instructions)

        self.assertIn(f"{COMMITMENT_KEY} carries the mode's value", acceptance)
        self.assertIn(f"{SKIP_REASON_KEY}=read_only_mode", acceptance)
        self.assertIn(f"{BASELINE_KEY} records the baseline commit", acceptance)
        self.assertIn("missing commitment fails this node", acceptance)

    def test_finalize_consumes_the_skip_reason(self) -> None:
        """G-10: the last node refuses a silent skip, so the obligation has a second reader."""
        node = nodes_by_template(load_spec())[FINALIZE_NODE]
        text = contract_text(node)
        self.assertIn(SKIP_REASON_KEY, text)
        self.assertIn(COMMITMENT_KEY, text)
        self.assertIn("must not close", str(node["instructions"]))

    def test_the_skill_page_states_the_report_obligation(self) -> None:
        """G-10: the lifecycle's public page names the obligation and its commitment."""
        page = SKILL_PAGE.read_text(encoding="utf-8")
        self.assertIn(COMMITMENT_KEY, page)
        self.assertIn(REPORT_GROUP, page)
        self.assertIn(SKIP_REASON_KEY, page)
        self.assertIn(f"{COMMITMENT_KEY}=true", page)

    def test_the_shipped_template_is_the_build_of_the_shipped_spec(self) -> None:
        """The template is generated: a hand-edited template fails this test."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "author-config.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            rebuilt = root / "new-feature-template.xml"
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(SPEC_PATH),
                    "--out",
                    str(rebuilt),
                    "--config",
                    str(config),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["commit"]["status"], "disabled", payload)
            self.assertEqual(rebuilt.read_bytes(), TEMPLATE_PATH.read_bytes())


class NewFeatureReportDriveTests(unittest.TestCase):
    """Runtime drives over the shipped template. These are the behavioural halves of G-10/G-24."""

    maxDiff = None

    def run_json(self, script: Path, *args: str, cwd: Path) -> dict[str, Any]:
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
        result = subprocess.run(
            ["git", *args], cwd=directory, capture_output=True, text=True, encoding="utf-8", check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def create_environment(self) -> tuple[Path, Path, Path]:
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
            json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8"
        )
        return root, project, workshop

    def set_values(self, project: Path, tree: Path, values: dict[str, str]) -> None:
        args = ["set", "--tree", str(tree)]
        for key, value in values.items():
            args.extend(["--set", f"{key}={value}"])
        self.run_json(RUNTIME, *args, cwd=project)

    def find_one(self, project: Path, tree: Path, template_id: str, instance_id: str = "") -> dict[str, Any]:
        args = ["find", "--tree", str(tree), "--template-id", template_id]
        if instance_id:
            args.extend(["--instance-id", instance_id])
        payload = self.run_json(RUNTIME, *args, cwd=project)
        self.assertEqual(len(payload["nodes"]), 1, payload)
        return payload["nodes"][0]

    def summary(self, project: Path, tree: Path) -> dict[str, Any]:
        return self.run_json(RUNTIME, "summary", "--tree", str(tree), cwd=project)

    def complete_ready_task(
        self,
        project: Path,
        tree: Path,
        expected_template_id: str,
        artifact: Path | None = None,
        check_result: dict[str, Any] | None = None,
        summary: str = "",
    ) -> str:
        ready = self.run_json(RUNTIME, "next", "--tree", str(tree), cwd=project)["ready"]
        self.assertEqual(
            [item["template_id"] for item in ready],
            [expected_template_id],
            f"expected {expected_template_id} to be the only ready node: {ready}",
        )
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
        if artifact is not None:
            args.extend(["--artifact", str(artifact)])
        if check_result is not None:
            args.extend(["--check-result-json", json.dumps(check_result, separators=(",", ":"))])
        self.run_json(RUNTIME, *args, cwd=project)
        return node_id

    def build_tree(self, work_order_id: str, feature_id: str) -> tuple[Path, Path, dict[str, Any], Path, Path]:
        """Open the work order, create the feature, initialise the shipped template."""
        _, project, workshop = self.create_environment()
        work_order = self.run_json(
            OPEN_WORK_ORDER,
            "--workshop",
            str(workshop),
            "--project-root",
            str(project),
            "--topic",
            work_order_id,
            "--work-order-id",
            work_order_id,
            "--feature-id",
            feature_id,
            cwd=project,
        )
        feature = self.run_json(
            FEATURE, "init", "--workshop", str(workshop), "--feature-id", feature_id, cwd=project
        )
        feature_dir = Path(str(feature["feature_dir"]))
        initialized = self.run_json(
            RUNTIME,
            "init",
            "--template",
            str(TEMPLATE_PATH),
            "--runtime-path",
            str(work_order["runtime_path"]),
            "--work-order-id",
            work_order_id,
            "--name",
            work_order_id,
            cwd=project,
        )
        tree = Path(str(initialized["tree_path"]))
        return project, tree, work_order, feature_dir, Path(str(work_order["workbench_path"]))

    def select_report_group(
        self, project: Path, tree: Path, feature_dir: Path, feature_id: str
    ) -> dict[str, Any]:
        """Drive the lifecycle to the point where `report-group` is the awaiting dynamic group.

        The commitment key is deliberately never written, so the group is selected by the
        declared default alone — which is the fail-closed property G-16/G-24 ask for.
        """
        self.set_values(
            project,
            tree,
            {
                "feature.id": feature_id,
                "work_order.document_language": "en",
                "feature.approval_required": "false",
                "work_order.requires_implementation": "false",
                "work_order.requires_verification": "false",
            },
        )
        self.complete_ready_task(project, tree, PREPARE_NODE, artifact=feature_dir)
        for template_id in PRECEDING_DOCUMENT_GROUPS:
            group = self.find_one(project, tree, template_id)
            self.run_json(
                RUNTIME, "close-group", "--tree", str(tree), "--group", str(group["id"]), cwd=project
            )
        summary = self.summary(project, tree)
        self.assertEqual(
            [item["template_id"] for item in summary["awaiting_dynamic_groups"]],
            [REPORT_GROUP],
            summary,
        )
        return summary

    def test_the_report_group_is_selected_without_a_preexisting_commitment(self) -> None:
        """G-10, G-16: an unwritten commitment selects the stage instead of skipping it."""
        project, tree, _, feature_dir, _ = self.build_tree("20260727-1000-nf-select", "payment-refund")
        summary = self.select_report_group(project, tree, feature_dir, "payment-refund")

        self.assertEqual(summary["blackboard"][COMMITMENT_KEY], "true", summary["blackboard"])
        group = self.find_one(project, tree, REPORT_GROUP)
        # An awaiting dynamic group is `pending` with an open dynamic state; what matters is
        # that it was selected rather than skipped by a guard that could not resolve its key.
        self.assertEqual(group["status"], "pending", group)
        self.assertEqual(group["attributes"]["dynamic.state"], "open", group)
        self.assertNotEqual(group["status"], "skipped")
        # The declared caller keys are present before any caller publication, which is the
        # half of the fix that survives embedding.
        self.assertEqual(declared_report_keys_from(summary["blackboard"]), FROZEN_CALLER_KEYS)

    def test_new_feature_embedded_report_group_reaches_validate_final(self) -> None:
        """G-24: the mounted subtree's final validation runs, not merely its group selection.

        A selection-only assertion passes while `validate-final` is still silently skippable:
        with `report.gate_recovery_required` absent, the recovery group's `== true` guard and
        `validate-final`'s `== false` guard both fall false. This drive publishes only the
        thirteen caller-seeded keys and requires `validate-final == succeeded`.
        """
        project, tree, _, feature_dir, workbench = self.build_tree(
            "20260727-1000-nf-report", "payment-refund"
        )
        self.select_report_group(project, tree, feature_dir, "payment-refund")
        group = self.find_one(project, tree, REPORT_GROUP)

        # Before the caller publishes anything the tree declares exactly the thirteen, so the
        # engine can resolve every guard, loop condition and completion-fact selector inside
        # the subtree it is about to embed.
        before = self.summary(project, tree)["blackboard"]
        self.assertEqual(declared_report_keys_from(before), FROZEN_CALLER_KEYS)

        report_dir = workbench / "artifacts" / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "change-report.html"
        manifest_path = report_dir / "change-report-manifest.json"
        report_path.write_text('<!doctype html><html lang="en"></html>\n', encoding="utf-8")
        manifest_path.write_text("{}\n", encoding="utf-8")

        self.run_json(
            RUNTIME,
            "embed-subtree",
            "--tree",
            str(tree),
            "--parent",
            str(group["id"]),
            "--template",
            str(CHANGE_REPORT_TEMPLATE),
            "--instance-id",
            "report",
            cwd=project,
        )

        # The caller's publication: exactly the thirteen caller-seeded keys, with the values
        # this work order uses. No other report.* key is touched.
        self.set_values(
            project,
            tree,
            {
                "report.path": str(report_path),
                "report.manifest_path": str(manifest_path),
                "report.baseline_commit": "0" * 40,
                "report.baseline_digest": "baseline-worktree-digest",
                "report.language": "en",
                "report.strength": "minimal",
                "report.gate_required": "false",
                "report.gate_outcome": "not-run",
                "report.gate_rework_required": "false",
                "report.gate_recovery_required": "false",
                "report.round": "1",
                "report.refresh_count": "0",
                "report.refresh_reason": "initial",
            },
        )
        published = self.summary(project, tree)["blackboard"]
        self.assertEqual(
            sorted(declared_report_keys_from(published)),
            sorted(FROZEN_CALLER_KEYS),
            "the caller publishes exactly the thirteen caller-seeded keys",
        )

        self.complete_ready_task(project, tree, "prepare-manifest", artifact=manifest_path)
        self.set_values(
            project,
            tree,
            {
                "report.units_total": "1",
                "report.units_covered": "1",
                "report.excluded_total": "0",
                "report.pre_existing_total": "0",
                "report.run_required": "true",
                "report.coverage": "complete",
                "report.self_contained": "true",
                "report.head_current": "true",
                "report.hash_bound": "1",
                "report.token_bound": "1",
            },
        )
        self.complete_ready_task(project, tree, "author-report", artifact=report_path)

        receipt = {
            "schema_version": 1,
            "check": "xc-change-report",
            "ok": True,
            "subject": str(report_path),
            "facts": {
                "units_total": "1",
                "units_covered": "1",
                "excluded_total": "0",
                "pre_existing_total": "0",
                "hash_bound": "1",
                "token_bound": "1",
                "coverage": "complete",
                "self_contained": "true",
                "head_current": "true",
                "strength": "minimal",
                "rounds": "1",
            },
        }
        self.assertEqual(sorted(receipt["facts"]), sorted(REPORT_FACT_KEYS))
        self.complete_ready_task(project, tree, "validate-coverage", check_result=receipt)

        review_artifact = report_dir / "review.md"
        review_artifact.write_text("# Review\n\nEvery unit matches the code.\n", encoding="utf-8")
        (report_dir / "change-report-verdicts.json").write_text(
            json.dumps(
                {"schema_version": 1, "verdicts": [{"unit_index": 1, "verdict": "accurate", "reason": ""}]}
            )
            + "\n",
            encoding="utf-8",
        )
        self.complete_ready_task(project, tree, "review-report", artifact=review_artifact)
        self.assertEqual(self.find_one(project, tree, "revise-report")["status"], "skipped")
        self.assertEqual(self.find_one(project, tree, "report-gate")["status"], "skipped")
        # The recovery group's guard reads the same key as validate-final's and must still be
        # false: the key is present and the guards resolve, rather than both falling absent.
        self.assertEqual(self.find_one(project, tree, "report-gate-recovery-group")["status"], "skipped")

        self.complete_ready_task(project, tree, "validate-final", check_result=receipt)

        pass_loop = self.find_one(project, tree, "report-pass-loop")
        self.assertEqual(pass_loop["status"], "succeeded", pass_loop)
        self.assertEqual(pass_loop["attributes"]["loop.terminal_reason"], "break")
        self.assertEqual(
            self.find_one(project, tree, "validate-final", "report")["status"],
            "succeeded",
            "the embedded subtree's final validation must run; `skipped` is the defect this "
            "mount exists to remove",
        )

        after = self.summary(project, tree)
        self.assertEqual(
            [item["template_id"] for item in after["awaiting_dynamic_groups"]],
            ["result-document"],
            "a completed report stage releases the result document",
        )


def declared_report_keys_from(blackboard: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in blackboard.items() if key.startswith("report.")}


if __name__ == "__main__":
    unittest.main()
