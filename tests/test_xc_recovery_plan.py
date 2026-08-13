from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "xc-work" / "scripts"
SCRIPT = SCRIPTS / "recovery_plan.py"
sys.path.insert(0, str(SCRIPTS))

import recovery_plan


P1_EVIDENCE = [
    "failed-attempt-recorded-summary-and-artifacts",
    "accepted-contract-unchanged-confirmation",
    "retry-safety-reason",
]
P2_EVIDENCE = [
    "revised-plan-artifact",
    "republished-source-keys",
    "recorded-what-changed-and-why-statement",
]
P3_EVIDENCE = [
    "gate-evidence-collected",
    "focused-question-answer-recorded-as-structured-state",
    "revised-solution-artifact",
]
P4_EVIDENCE = ["blocker-evidence-collected", "focused-question", "recorded-decision"]

NODE_ID = "rt_wo-20260813__dyn-1__impl-x"
TREE = "C:/workshop/work-orders/wo-1/runtime/orchestration.xml"


class RecoveryPlanMappingTests(unittest.TestCase):
    def plan(self, payload: dict[str, object]) -> dict[str, object]:
        result = recovery_plan.plan(payload)
        self.assertIsInstance(result, dict)
        return result

    def test_p1_minimal_mapping(self) -> None:
        result = self.plan({"pattern": "p1", "node_id": NODE_ID, "reason": "transient timeout"})
        self.assertEqual(
            result,
            {
                "schema_version": 1,
                "ok": True,
                "pattern": "p1",
                "commands": [
                    {
                        "command": "retry-failed",
                        "args": ["--node", NODE_ID, "--reason", "transient timeout"],
                        "note": recovery_plan.NOTE_P1_RETRY,
                    }
                ],
                "evidence_required": P1_EVIDENCE,
            },
        )

    def test_p1_with_tree_and_expected_revision(self) -> None:
        result = self.plan(
            {
                "pattern": "p1",
                "node_id": NODE_ID,
                "tree": TREE,
                "reason": "worker crash",
                "expected_revision": 7,
            }
        )
        self.assertEqual(
            result["commands"][0]["args"],
            [
                "--tree",
                TREE,
                "--expected-revision",
                "7",
                "--node",
                NODE_ID,
                "--reason",
                "worker crash",
            ],
        )

    def test_p2_full_mapping(self) -> None:
        payload = {
            "pattern": "p2",
            "node_id": NODE_ID,
            "tree": TREE,
            "reason": "approach changed",
            "group_id": "rt_wo__dyn-1__work-group",
            "reopen_group": True,
            "new_node": {
                "logical_key": "recovery-revision",
                "title": "Recovery revision",
                "type": "task",
                "executor": "subagent",
                "instructions": "Revise the plan",
                "metadata": {"artifact.audience": "internal", "depth": 2},
            },
            "before": "rt_wo__dyn-1__impl-b",
            "sets": {"plan.updated": True, "work_order.solution_source_ids": '["rt_a"]'},
            "unblock": True,
        }
        result = self.plan(payload)
        commands = result["commands"]
        self.assertEqual([item["command"] for item in commands], ["reopen-group", "add-node", "set", "unblock"])
        self.assertEqual(
            commands[0]["args"],
            [
                "--tree",
                TREE,
                "--group",
                "rt_wo__dyn-1__work-group",
                "--reason",
                "approach changed",
            ],
        )
        self.assertEqual(
            commands[1]["args"],
            [
                "--tree",
                TREE,
                "--parent",
                "rt_wo__dyn-1__work-group",
                "--logical-key",
                "recovery-revision",
                "--title",
                "Recovery revision",
                "--type",
                "task",
                "--executor",
                "subagent",
                "--instructions",
                "Revise the plan",
                "--metadata",
                "metadata.artifact.audience=internal",
                "--metadata",
                "metadata.depth=2",
                "--before",
                "rt_wo__dyn-1__impl-b",
            ],
        )
        self.assertEqual(
            commands[2]["args"],
            [
                "--tree",
                TREE,
                "--set",
                'plan.updated=true',
                "--set",
                'work_order.solution_source_ids=["rt_a"]',
            ],
        )
        self.assertEqual(commands[3]["args"], ["--tree", TREE, "--node", NODE_ID])
        self.assertEqual(result["evidence_required"], P2_EVIDENCE)

    def test_p2_unblock_disabled_and_group_absent(self) -> None:
        result = self.plan(
            {
                "pattern": "p2",
                "node_id": NODE_ID,
                "reason": "approach changed",
                "sets": {"plan.updated": True},
                "unblock": False,
            }
        )
        self.assertEqual([item["command"] for item in result["commands"]], ["set"])
        self.assertEqual(result["commands"][0]["args"], ["--set", "plan.updated=true"])

    def test_p3_full_mapping(self) -> None:
        payload = {
            "pattern": "p3",
            "node_id": "rt_wo__dyn-1__successor-gate",
            "tree": TREE,
            "reason": "gate rejected the solution",
            "expected_revision": 11,
            "recovery_group_id": "rt_wo__dyn-1__solution-recovery-group",
            "reopen_group": True,
            "revision_node": {"logical_key": "solution-revision", "title": "Revise solution"},
            "successor_gate": {
                "logical_key": "successor-approval",
                "title": "Successor approval",
                "outcomes": ["approved", "rejected"],
                "decision_required": True,
                "outcome_key": "work_order.solution_gate_outcome",
            },
            "gate_outcome": "approved",
            "decision": "revised scope accepted",
        }
        result = self.plan(payload)
        commands = result["commands"]
        self.assertEqual(
            [item["command"] for item in commands],
            ["reopen-group", "add-node", "add-node", "complete"],
        )
        self.assertEqual(
            commands[0]["args"],
            [
                "--tree",
                TREE,
                "--expected-revision",
                "11",
                "--group",
                "rt_wo__dyn-1__solution-recovery-group",
                "--reason",
                "gate rejected the solution",
            ],
        )
        self.assertEqual(
            commands[1]["args"],
            [
                "--tree",
                TREE,
                "--parent",
                "rt_wo__dyn-1__solution-recovery-group",
                "--logical-key",
                "solution-revision",
                "--title",
                "Revise solution",
            ],
        )
        self.assertEqual(
            commands[2]["args"],
            [
                "--tree",
                TREE,
                "--parent",
                "rt_wo__dyn-1__solution-recovery-group",
                "--logical-key",
                "successor-approval",
                "--title",
                "Successor approval",
                "--type",
                "gate",
                "--executor",
                "main",
                "--metadata",
                "metadata.gate.decision_required=true",
                "--metadata",
                "metadata.gate.outcome_key=work_order.solution_gate_outcome",
                "--metadata",
                'metadata.gate.outcomes=["approved","rejected"]',
            ],
        )
        self.assertEqual(
            commands[3]["args"],
            [
                "--tree",
                TREE,
                "--node",
                "rt_wo__dyn-1__successor-gate",
                "--gate-outcome",
                "approved",
                "--decision",
                "revised scope accepted",
            ],
        )
        self.assertEqual(result["evidence_required"], P3_EVIDENCE)

    def test_p3_minimal_defaults(self) -> None:
        result = self.plan({"pattern": "p3", "node_id": NODE_ID, "reason": "rescope"})
        self.assertEqual(
            result["commands"],
            [
                {
                    "command": "complete",
                    "args": ["--node", NODE_ID, "--gate-outcome", "approved"],
                    "note": recovery_plan.NOTE_P3_COMPLETE,
                }
            ],
        )

    def test_p4_mapping(self) -> None:
        result = self.plan(
            {
                "pattern": "p4",
                "node_id": NODE_ID,
                "tree": TREE,
                "reason": "external service unavailable",
                "artifacts": ["evidence.md", "trace.log"],
            }
        )
        self.assertEqual(
            result["commands"],
            [
                {
                    "command": "block",
                    "args": [
                        "--tree",
                        TREE,
                        "--node",
                        NODE_ID,
                        "--reason",
                        "external service unavailable",
                        "--artifact",
                        "evidence.md",
                        "--artifact",
                        "trace.log",
                    ],
                    "note": recovery_plan.NOTE_P4_BLOCK,
                }
            ],
        )
        self.assertEqual(result["evidence_required"], P4_EVIDENCE)


class RecoveryPlanDeterminismTests(unittest.TestCase):
    def test_sorted_keys_and_repeatable_output(self) -> None:
        first = {
            "pattern": "p2",
            "node_id": "rt_wo__dyn-1__impl-a",
            "reason": "approach changed",
            "group_id": "rt_wo__dyn-1__work-group",
            "sets": {"b.key": 1, "a.key": "value"},
        }
        reordered = {
            "sets": {"a.key": "value", "b.key": 1},
            "reason": "approach changed",
            "group_id": "rt_wo__dyn-1__work-group",
            "node_id": "rt_wo__dyn-1__impl-a",
            "pattern": "p2",
        }
        first_raw = recovery_plan.compact_json(recovery_plan.plan(first))
        reordered_raw = recovery_plan.compact_json(recovery_plan.plan(reordered))
        self.assertEqual(first_raw, reordered_raw)
        self.assertEqual(recovery_plan.plan(first), recovery_plan.plan(first))
        self.assertTrue(first_raw.startswith('{"commands":'))
        self.assertTrue(first_raw.endswith('"schema_version":1}'))
        self.assertEqual(
            first_raw,
            json.dumps(json.loads(first_raw), separators=(",", ":"), sort_keys=True, ensure_ascii=False),
        )

    def test_expected_revision_only_on_first_command(self) -> None:
        result = recovery_plan.plan(
            {
                "pattern": "p3",
                "node_id": "rt_gate",
                "reason": "rescope",
                "expected_revision": 5,
                "recovery_group_id": "rt_group",
                "revision_node": {"logical_key": "revision-1"},
                "successor_gate": {
                    "logical_key": "gate-2",
                    "outcomes": ["approved", "revision-required"],
                    "decision_required": True,
                    "outcome_key": "work_order.gate_outcome",
                },
            }
        )
        first_args = result["commands"][0]["args"]
        self.assertEqual(first_args[:2], ["--expected-revision", "5"])
        for command in result["commands"][1:]:
            self.assertNotIn("--expected-revision", command["args"])
        gate_add = result["commands"][1]
        self.assertEqual(gate_add["command"], "add-node")
        gate_metadata = {
            gate_add["args"][index + 1] for index in range(len(gate_add["args"]) - 1) if gate_add["args"][index] == "--metadata"
        }
        self.assertEqual(
            gate_metadata,
            {
                "metadata.gate.decision_required=true",
                "metadata.gate.outcome_key=work_order.gate_outcome",
                'metadata.gate.outcomes=["approved","revision-required"]',
            },
        )


class RecoveryPlanRejectionTests(unittest.TestCase):
    def assert_code(self, payload: object, code: str) -> None:
        self.assertEqual(recovery_plan.plan(payload), {"schema_version": 1, "ok": False, "error_code": code})

    def test_non_object_input(self) -> None:
        self.assert_code(["p1"], "input_not_object")

    def test_missing_and_unknown_pattern(self) -> None:
        self.assert_code({"node_id": NODE_ID, "reason": "r"}, "missing_pattern")
        self.assert_code({"pattern": "p9", "node_id": NODE_ID, "reason": "r"}, "unknown_pattern")
        self.assert_code({"pattern": 1, "node_id": NODE_ID, "reason": "r"}, "unknown_pattern")

    def test_missing_and_invalid_node_id(self) -> None:
        self.assert_code({"pattern": "p1", "reason": "r"}, "missing_node_id")
        self.assert_code({"pattern": "p1", "node_id": "  ", "reason": "r"}, "invalid_node_id")
        self.assert_code({"pattern": "p1", "node_id": 5, "reason": "r"}, "invalid_node_id")

    def test_missing_and_invalid_reason(self) -> None:
        self.assert_code({"pattern": "p1", "node_id": NODE_ID}, "missing_reason")
        self.assert_code({"pattern": "p1", "node_id": NODE_ID, "reason": ""}, "invalid_reason")
        self.assert_code({"pattern": "p1", "node_id": NODE_ID, "reason": 7}, "invalid_reason")

    def test_invalid_tree_and_expected_revision(self) -> None:
        self.assert_code({"pattern": "p1", "node_id": NODE_ID, "reason": "r", "tree": ""}, "invalid_tree")
        for revision in (-1, 1.5, "3", True):
            self.assert_code(
                {"pattern": "p1", "node_id": NODE_ID, "reason": "r", "expected_revision": revision},
                "invalid_expected_revision",
            )

    def test_unknown_top_level_field(self) -> None:
        self.assert_code({"pattern": "p1", "node_id": NODE_ID, "reason": "r", "extra": 1}, "unknown_field")
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "artifacts": []}, "unknown_field"
        )

    def test_p2_field_rejections(self) -> None:
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "reopen_group": True},
            "p2_missing_group_id",
        )
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "new_node": {"logical_key": "n-1"}},
            "p2_missing_group_id",
        )
        self.assert_code(
            {
                "pattern": "p2",
                "node_id": NODE_ID,
                "reason": "r",
                "group_id": "g",
                "new_node": {"logical_key": "Not-Kebab"},
            },
            "p2_new_node_invalid",
        )
        self.assert_code(
            {
                "pattern": "p2",
                "node_id": NODE_ID,
                "reason": "r",
                "group_id": "g",
                "new_node": {"logical_key": "n-1", "executor": "unknown"},
            },
            "p2_new_node_invalid",
        )
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "before": "rt_x"},
            "p2_invalid_before",
        )
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "sets": {"k": None}},
            "p2_invalid_sets",
        )
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "sets": {"k": ["a"]}},
            "p2_invalid_sets",
        )
        self.assert_code(
            {"pattern": "p2", "node_id": NODE_ID, "reason": "r", "unblock": "yes"},
            "p2_invalid_flag",
        )

    def test_p3_field_rejections(self) -> None:
        self.assert_code(
            {"pattern": "p3", "node_id": NODE_ID, "reason": "r", "reopen_group": True},
            "p3_missing_group_id",
        )
        self.assert_code(
            {
                "pattern": "p3",
                "node_id": NODE_ID,
                "reason": "r",
                "recovery_group_id": "g",
                "successor_gate": {"logical_key": "gate-1"},
            },
            "p3_successor_gate_invalid",
        )
        self.assert_code(
            {
                "pattern": "p3",
                "node_id": NODE_ID,
                "reason": "r",
                "recovery_group_id": "g",
                "successor_gate": {
                    "logical_key": "gate-1",
                    "outcomes": ["approved"],
                    "type": "task",
                },
            },
            "p3_successor_gate_invalid",
        )
        self.assert_code(
            {
                "pattern": "p3",
                "node_id": NODE_ID,
                "reason": "r",
                "recovery_group_id": "g",
                "revision_node": {"logical_key": "rev-1", "metadata": {"k": []}},
            },
            "p3_revision_node_invalid",
        )
        self.assert_code(
            {"pattern": "p3", "node_id": NODE_ID, "reason": "r", "gate_outcome": ""},
            "p3_invalid_gate_outcome",
        )
        self.assert_code(
            {"pattern": "p3", "node_id": NODE_ID, "reason": "r", "decision": 5},
            "p3_invalid_decision",
        )
        self.assert_code(
            {"pattern": "p3", "node_id": NODE_ID, "reason": "r", "reopen_group": "yes"},
            "p3_invalid_flag",
        )

    def test_p3_successor_gate_rejections(self) -> None:
        def successor_gate(spec: dict[str, object]) -> dict[str, object]:
            return {
                "pattern": "p3",
                "node_id": NODE_ID,
                "reason": "r",
                "recovery_group_id": "g",
                "successor_gate": spec,
            }

        base = {
            "logical_key": "gate-1",
            "outcomes": ["approved", "revision-required"],
            "decision_required": True,
            "outcome_key": "work_order.gate_outcome",
        }
        self.assert_code(
            successor_gate({**base, "outcomes": ["Approved"]}),
            "invalid_gate_outcomes",
        )
        self.assert_code(
            successor_gate({**base, "outcomes": ["approved", "approved"]}),
            "invalid_gate_outcomes",
        )
        self.assert_code(
            successor_gate({**base, "outcomes": ["approved", "Bad Outcome"]}),
            "invalid_gate_outcomes",
        )
        self.assert_code(
            successor_gate({**base, "decision_required": "yes"}),
            "invalid_gate_decision_required",
        )
        self.assert_code(
            successor_gate({**base, "outcome_key": "Not A Key!"}),
            "invalid_gate_outcome_key",
        )
        self.assert_code(
            successor_gate({**base, "outcome_key": ""}),
            "invalid_gate_outcome_key",
        )
        del base["decision_required"]
        self.assert_code(successor_gate(base), "p3_successor_gate_invalid")

    def test_p4_field_rejections(self) -> None:
        self.assert_code(
            {"pattern": "p4", "node_id": NODE_ID, "reason": "r", "artifacts": "evidence.md"},
            "p4_invalid_artifacts",
        )
        self.assert_code(
            {"pattern": "p4", "node_id": NODE_ID, "reason": "r", "artifacts": [""]},
            "p4_invalid_artifacts",
        )


class RecoveryPlanCliTests(unittest.TestCase):
    def run_cli(self, arguments: list[str], *, stdin_text: str | None = None, cwd: Path) -> tuple[int, str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=cwd,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return completed.returncode, completed.stdout

    def test_stdin_and_input_file_agree(self) -> None:
        payload = {
            "pattern": "p1",
            "node_id": NODE_ID,
            "reason": "retry",
            "expected_revision": 2,
        }
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            input_file = directory / "incident.json"
            input_file.write_text(json.dumps(payload), encoding="utf-8")
            returncode, stdout = self.run_cli(["--input-file", str(input_file)], cwd=directory)
            self.assertEqual(returncode, 0)
            from_file = json.loads(stdout)
            _, stdin_stdout = self.run_cli([], stdin_text=json.dumps(payload), cwd=directory)
            self.assertEqual(json.loads(stdin_stdout), from_file)
            self.assertTrue(from_file["ok"])
            self.assertEqual(
                from_file["commands"][0]["args"],
                ["--expected-revision", "2", "--node", NODE_ID, "--reason", "retry"],
            )

    def test_invalid_input_exits_zero_with_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            returncode, stdout = self.run_cli([], stdin_text="not json", cwd=directory)
            self.assertEqual(returncode, 0)
            self.assertEqual(json.loads(stdout), {"schema_version": 1, "ok": False, "error_code": "input_not_json"})
            returncode, stdout = self.run_cli([], stdin_text='{"pattern": "p9", "node_id": "n", "reason": "r"}', cwd=directory)
            self.assertEqual(returncode, 0)
            self.assertEqual(json.loads(stdout), {"schema_version": 1, "ok": False, "error_code": "unknown_pattern"})

    def test_unreadable_input_file_returns_stable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            returncode, stdout = self.run_cli(
                ["--input-file", str(directory / "missing.json")], cwd=directory
            )
            self.assertEqual(returncode, 0)
            self.assertEqual(
                json.loads(stdout),
                {"schema_version": 1, "ok": False, "error_code": "input_file_unreadable"},
            )

    def test_no_side_effects(self) -> None:
        payload = {
            "pattern": "p2",
            "node_id": NODE_ID,
            "reason": "approach changed",
            "group_id": "rt_wo__dyn-1__work-group",
            "new_node": {"logical_key": "recovery-1", "title": "Recovery"},
            "before": "rt_wo__dyn-1__impl-b",
            "sets": {"plan.updated": True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            input_file = directory / "incident.json"
            input_file.write_text(json.dumps(payload), encoding="utf-8")
            for _ in range(2):
                returncode, stdout = self.run_cli(["--input-file", str(input_file)], cwd=directory)
                self.assertEqual(returncode, 0)
                self.assertTrue(json.loads(stdout)["ok"])
            self.assertEqual(
                sorted(os.listdir(directory)),
                ["incident.json"],
            )


if __name__ == "__main__":
    unittest.main()
