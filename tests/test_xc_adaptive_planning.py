from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "xc-work" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan_work
import plan_work_policy as policy


class AdaptivePlanningTests(unittest.TestCase):
    def base_facts(self) -> dict[str, str]:
        return {
            "needs_persistence": "yes",
            "material_impact": "yes",
            "difficult_rollback": "no",
            "crosses_sessions": "no",
            "multiple_actors": "no",
            "audit_required": "no",
            "bridge_policy": "none",
            "scope": "single-location",
            "clarity": "exact",
            "risk": "low",
            "verification": "focused",
            "coordination": "single",
            "duration": "single-step",
            "audit": "runtime-only",
            "pace": "fast",
            "mode": "change",
            "request": "Change one local constant and run its focused check.",
            "bridge_sha256": "a" * 64,
        }

    def arguments(self, facts: dict[str, str]) -> list[str]:
        return plan_work.strict_arguments(facts)

    def invoke(self, script: Path, arguments: list[str]) -> tuple[int, dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, str(script), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout)

    def test_minimal_mutation_has_no_optional_capabilities(self) -> None:
        payload = policy.build_plan(self.base_facts())
        self.assertEqual(payload["implementation_units_min"], 1)
        self.assertEqual(payload["verification_scopes"], ["focused"])
        self.assertFalse(any(payload["capabilities"].values()))
        self.assertEqual(
            payload["depth"],
            {
                "analysis_perspectives": 0,
                "review_passes": 0,
                "recovery_exercises": 0,
            },
        )
        self.assertRegex(payload["plan_receipt"]["plan_id"], r"^[0-9a-f]{64}$")

    def test_module_scope_splits_implementation_and_verification(self) -> None:
        facts = self.base_facts()
        facts["scope"] = "module"
        payload = policy.build_plan(facts)
        self.assertTrue(payload["capabilities"]["split_implementation"])
        self.assertTrue(payload["capabilities"]["separate_verification"])
        self.assertEqual(payload["implementation_units_min"], 2)
        self.assertEqual(payload["verification_scopes"], ["focused", "regression"])

    def test_generic_audit_requires_result_independent_of_bridge(self) -> None:
        facts = self.base_facts()
        facts["audit_required"] = "yes"
        facts["audit"] = "result"
        payload = policy.build_plan(facts)
        self.assertTrue(payload["capabilities"]["result_document"])
        self.assertIn(
            "governance:audit_required:yes",
            payload["required_provenance"]["result_document"],
        )

    def test_runtime_only_audit_contradicts_required_audit(self) -> None:
        facts = self.base_facts()
        facts["audit_required"] = "yes"
        with self.assertRaises(policy.PlanningInputError) as context:
            policy.build_plan(facts)
        self.assertEqual(context.exception.code, "planning_input_contradictory")

    def test_unknowns_fail_closed_to_full_capabilities(self) -> None:
        facts = self.base_facts()
        for name in (*policy.GOVERNANCE_FACTS, *policy.TASK_FACTS):
            facts[name] = "unknown"
        facts["bridge_policy"] = "unknown"
        payload = policy.build_plan(facts)
        self.assertTrue(all(payload["capabilities"].values()))
        self.assertGreaterEqual(payload["implementation_units_min"], 2)
        self.assertEqual(payload["verification_scopes"], list(policy.VERIFICATION_SCOPES))
        self.assertGreaterEqual(payload["depth"]["analysis_perspectives"], 1)
        self.assertGreaterEqual(payload["depth"]["review_passes"], 1)

    def test_thorough_only_adds_depth_and_regression(self) -> None:
        facts = self.base_facts()
        facts["risk"] = "high"
        facts["pace"] = "adaptive"
        adaptive = policy.build_plan(facts)
        facts["pace"] = "thorough"
        thorough = policy.build_plan(facts)
        for name in policy.CAPABILITIES:
            self.assertGreaterEqual(
                int(thorough["capabilities"][name]),
                int(adaptive["capabilities"][name]),
            )
        self.assertEqual(
            thorough["depth"]["analysis_perspectives"],
            adaptive["depth"]["analysis_perspectives"] + 1,
        )
        self.assertEqual(
            thorough["depth"]["review_passes"],
            adaptive["depth"]["review_passes"] + 1,
        )
        self.assertIn("regression", thorough["verification_scopes"])

    def test_governance_tightening_never_removes_capabilities(self) -> None:
        base = policy.build_plan(self.base_facts())
        for name in (
            "difficult_rollback",
            "crosses_sessions",
            "multiple_actors",
            "audit_required",
        ):
            facts = self.base_facts()
            facts[name] = "yes"
            if name == "difficult_rollback":
                facts["risk"] = "high"
            elif name == "crosses_sessions":
                facts["duration"] = "cross-session"
            elif name == "multiple_actors":
                facts["coordination"] = "multi-party"
            else:
                facts["audit"] = "result"
            tightened = policy.build_plan(facts)
            for capability in policy.CAPABILITIES:
                self.assertGreaterEqual(
                    int(tightened["capabilities"][capability]),
                    int(base["capabilities"][capability]),
                    (name, capability),
                )

    def test_strict_cli_rejects_missing_and_duplicate_inputs(self) -> None:
        facts = self.base_facts()
        arguments = self.arguments(facts)
        code, payload = self.invoke(
            SCRIPTS / "plan_work_policy.py",
            arguments[:-2],
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "planning_input_missing")
        code, payload = self.invoke(
            SCRIPTS / "plan_work_policy.py",
            [*arguments, "--scope", facts["scope"]],
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "planning_input_duplicate")

    def test_public_adapter_returns_success_and_always_exits_zero(self) -> None:
        facts = self.base_facts()
        code, payload = self.invoke(
            SCRIPTS / "plan_work.py",
            self.arguments(facts),
        )
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["planning_status"], "planned")
        code, payload = self.invoke(
            SCRIPTS / "plan_work.py",
            ["--scope", "module"],
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["planning_status"], "escalated")
        self.assertEqual(payload["reason_codes"], ["execution-planning-unavailable"])
        self.assertTrue(all(payload["capabilities"].values()))

    def test_public_adapter_rejects_forged_success_output(self) -> None:
        facts = self.base_facts()
        forged = policy.build_plan(facts)
        forged["implementation_units_min"] = 0
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(forged),
            stderr="",
        )
        with mock.patch.object(plan_work.subprocess, "run", return_value=completed):
            payload = plan_work.plan(self.arguments(facts))
        self.assertEqual(payload["planning_status"], "escalated")
        self.assertEqual(
            payload["diagnostic"]["input_error"],
            "planning_output_invalid",
        )

    def test_read_only_fail_closed_plan_never_enables_mutation(self) -> None:
        facts = self.base_facts()
        facts["mode"] = "review"
        for name in (*policy.GOVERNANCE_FACTS, *policy.TASK_FACTS):
            facts[name] = "unknown"
        facts["bridge_policy"] = "unknown"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["mode"], "review")
        self.assertEqual(payload["implementation_units_min"], 0)
        self.assertEqual(payload["verification_scopes"], [])
        self.assertFalse(payload["capabilities"]["split_implementation"])
        self.assertFalse(payload["capabilities"]["separate_verification"])

        with mock.patch.object(
            plan_work.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("planner", 5),
        ):
            escalated = plan_work.plan(self.arguments(facts))
        self.assertEqual(escalated["mode"], "review")
        self.assertEqual(escalated["implementation_units_min"], 0)
        self.assertEqual(escalated["verification_scopes"], [])

    def test_plan_receipt_binds_request_and_bridge_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(
                bridge.read_bytes()
            ).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            code, payload = self.invoke(
                SCRIPTS / "validate_plan_receipt.py",
                [
                    "--receipt-json",
                    json.dumps(receipt, separators=(",", ":")),
                    "--request",
                    facts["request"],
                    "--bridge",
                    str(bridge),
                ],
            )
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            code, payload = self.invoke(
                SCRIPTS / "validate_plan_receipt.py",
                [
                    "--receipt-json",
                    json.dumps(receipt, separators=(",", ":")),
                    "--request",
                    facts["request"] + " changed",
                    "--bridge",
                    str(bridge),
                ],
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "plan_request_mismatch")

    def test_receipt_validator_rejects_policy_consistent_self_hash_forgery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            forged = dict(receipt)
            forged["capabilities"] = dict(receipt["capabilities"])
            forged["capabilities"]["result_document"] = True
            body = dict(forged)
            body.pop("plan_id")
            forged["plan_id"] = hashlib.sha256(
                json.dumps(
                    body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            code, payload = self.invoke(
                SCRIPTS / "validate_plan_receipt.py",
                [
                    "--receipt-json",
                    json.dumps(forged, separators=(",", ":")),
                    "--request",
                    facts["request"],
                    "--bridge",
                    str(bridge),
                ],
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "plan_policy_mismatch")

    def test_adaptive_manifest_requires_every_planned_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["scope"] = "module"
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            source_map: dict[str, dict[str, object]] = {}
            packet_categories: list[dict[str, object]] = []
            for index, item in enumerate(receipt["required_nodes"]):
                if item["role"] == "finalizer":
                    continue
                node_id = f"rt_source_{index}"
                source_map[item["logical_key"]] = {
                    "node_id": node_id,
                }
                packet_categories.append(
                    {
                        "name": f"plan-{item['logical_key']}",
                        "sources": [
                            {
                                "node_id": node_id,
                                "logical_key": item["logical_key"],
                                "role": item["role"],
                                "status": "succeeded",
                                "artifacts": [
                                    f"artifact-{index}-{item_index}"
                                    for item_index in range(item["artifact_min"])
                                ],
                            }
                        ],
                    }
                )
            packet = {
                "packet": {
                    "target": {
                        "logical_key": "finalize",
                        "role": "work-order-finalize",
                    },
                    "blackboard": [
                        {"key": "work_order.plan_id", "value": receipt["plan_id"]}
                    ],
                    "source_categories": packet_categories,
                }
            }
            arguments = [
                "--receipt-json",
                json.dumps(receipt, separators=(",", ":")),
                "--source-map-json",
                json.dumps(source_map, separators=(",", ":")),
                "--packet-json",
                json.dumps(packet, separators=(",", ":")),
                "--request",
                facts["request"],
                "--bridge",
                str(bridge),
            ]
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                arguments,
            )
            self.assertEqual(code, 0)
            self.assertEqual(payload["min_sources"], len(source_map))
            missing_map = dict(source_map)
            missing_map.pop(next(iter(missing_map)))
            arguments[3] = json.dumps(missing_map, separators=(",", ":"))
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                arguments,
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "missing_required_source")
            forged_packet = json.loads(json.dumps(packet))
            forged_packet["packet"]["target"]["role"] = "implementation"
            arguments[3] = json.dumps(source_map, separators=(",", ":"))
            arguments[5] = json.dumps(forged_packet, separators=(",", ":"))
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                arguments,
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "invalid_adaptive_manifest")

    def test_receipt_validator_rejects_invalid_fact_domains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            forged = json.loads(json.dumps(receipt))
            forged["facts"]["governance"]["needs_persistence"] = "invalid"
            body = dict(forged)
            body.pop("plan_id")
            forged["plan_id"] = hashlib.sha256(
                json.dumps(
                    body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            code, payload = self.invoke(
                SCRIPTS / "validate_plan_receipt.py",
                [
                    "--receipt-json",
                    json.dumps(forged, separators=(",", ":")),
                    "--request",
                    facts["request"],
                    "--bridge",
                    str(bridge),
                ],
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "invalid_plan_receipt")

    def test_manifest_rejects_finalizer_only_forged_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            forged = {
                "schema_version": 1,
                "plan_id": "a" * 64,
                "required_nodes": [
                    {
                        "logical_key": "finalize",
                        "role": "finalizer",
                        "artifact_min": 0,
                    }
                ],
            }
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                [
                    "--receipt-json",
                    json.dumps(forged, separators=(",", ":")),
                    "--source-map-json",
                    "{}",
                    "--packet-json",
                    json.dumps(
                        {
                            "packet": {
                                "blackboard": [
                                    {
                                        "key": "work_order.plan_id",
                                        "value": "a" * 64,
                                    }
                                ],
                                "source_categories": [],
                            }
                        },
                        separators=(",", ":"),
                    ),
                    "--request",
                    "No-op",
                    "--bridge",
                    str(bridge),
                ],
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "invalid_plan_receipt")


if __name__ == "__main__":
    unittest.main()
