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


MINIMAL_PLAN_SNAPSHOT = (
    '{"schema_version":1,"ok":true,"mode":"change","pace":"fast","c'
    'apabilities":{"goal_document":false,"analysis":false,"clarific'
    'ation":false,"solution":false,"approval":false,"split_implemen'
    'tation":false,"separate_verification":false,"independent_revie'
    'w":false,"result_document":false,"resumable_recovery":false,"c'
    'hange_report":true},"implementation_units_min":1,"verification'
    '_scopes":["focused"],"depth":{"analysis_perspectives":0,"revie'
    'w_passes":0,"recovery_exercises":0},"optional_depth":{"analysi'
    's_perspectives":{"floor":0,"value":0,"trimmed":true},"review_p'
    'asses":{"floor":0,"value":0,"trimmed":true},"recovery_exercise'
    's":{"floor":0,"value":0,"trimmed":true},"regression_scope":{"f'
    'loor":["focused"],"value":["focused"],"trimmed":true}},"requir'
    'ed_nodes":[{"logical_key":"implementation-1","role":"implement'
    'ation","artifact_min":1,"verification_scope":"focused"},{"logi'
    'cal_key":"report","role":"report","artifact_min":1,"source_key'
    's":["work_order.report_baseline"],"required_artifact_name":"change-r'
    'eport.html"},{"logical_key":"finalize","'
    'role":"finalizer","artifact_min":0}],"required_provenance":{"g'
    'oal_document":[],"analysis":[],"clarification":[],"solution":['
    '],"approval":[],"split_implementation":[],"separate_verificati'
    'on":[],"independent_review":[],"result_document":[],"resumable'
    '_recovery":[],"change_report":["mode:change"]},"facts":{"gover'
    'nance":{"needs_persistence":"yes","material_impact":"yes","dif'
    'ficult_rollback":"no","crosses_sessions":"no","multiple_actors'
    '":"no","audit_required":"no"},"bridge_policy":"none","task":{"'
    'scope":"single-location","clarity":"exact","risk":"low","verif'
    'ication":"focused","coordination":"single","duration":"single-'
    'step","audit":"runtime-only"}},"reason_codes":["mode:change","'
    'task:verification:focused"],"planning_status":"planned","diagn'
    'ostic":null,"plan_receipt":{"schema_version":1,"request_sha256'
    '":"0ba415c1d84b1c062757d9d8e908cac628f88c0a2f4c91de36192d87c40'
    'a2570","bridge_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    'aaaaaaaaaaaaaaaaaaaaaaaaaa","mode":"change","pace":"fast","cap'
    'abilities":{"goal_document":false,"analysis":false,"clarificat'
    'ion":false,"solution":false,"approval":false,"split_implementa'
    'tion":false,"separate_verification":false,"independent_review"'
    ':false,"result_document":false,"resumable_recovery":false,"cha'
    'nge_report":true},"implementation_units_min":1,"verification_s'
    'copes":["focused"],"depth":{"analysis_perspectives":0,"review_'
    'passes":0,"recovery_exercises":0},"optional_depth":{"analysis_'
    'perspectives":{"floor":0,"value":0,"trimmed":true},"review_pas'
    'ses":{"floor":0,"value":0,"trimmed":true},"recovery_exercises"'
    ':{"floor":0,"value":0,"trimmed":true},"regression_scope":{"flo'
    'or":["focused"],"value":["focused"],"trimmed":true}},"required'
    '_nodes":[{"logical_key":"implementation-1","role":"implementat'
    'ion","artifact_min":1,"verification_scope":"focused"},{"logica'
    'l_key":"report","role":"report","artifact_min":1,"source_keys"'
    ':["work_order.report_baseline"],"required_artifact_name":"change'
    '-report.html"},{"logical_key":"finalize","ro'
    'le":"finalizer","artifact_min":0}],"facts":{"governance":{"nee'
    'ds_persistence":"yes","material_impact":"yes","difficult_rollb'
    'ack":"no","crosses_sessions":"no","multiple_actors":"no","audi'
    't_required":"no"},"bridge_policy":"none","task":{"scope":"sing'
    'le-location","clarity":"exact","risk":"low","verification":"fo'
    'cused","coordination":"single","duration":"single-step","audit'
    '":"runtime-only"}},"report_strength":"minimal","plan_id":"007c'
    '494d41af983c8ed750b040a39539594885c2592840898f37b6da11dbbd4f'
    '"}'
    '}'
)


# The two declarations G-18 and G-37 made enforceable, spelled exactly as the
# solution decision freezes them: the report node names the artifact it must be
# given, and declares the blackboard key its consumer has to publish.
REPORT_ARTIFACT_NAME = "change-report.html"
BASELINE_KEY = "work_order.report_baseline"
# A syntactically well-formed `commit:digest:algorithm` baseline value. The
# validator's contract is non-emptiness, so the test supplies a value that is
# unmistakably a fixture rather than an implied real capture.
BASELINE_VALUE = (
    "ac583c3646122ae35159c64c8c7143def4f17885:"
    "cf190d29e21631fade7e12783febbe6614c02d37bf2c98b5b0f8fac31289f7aa:"
    "sha256(path-nul-contenthash-lf/v1)"
)


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
        self.assertEqual(
            {
                name
                for name, enabled in payload["capabilities"].items()
                if enabled
            },
            {"change_report"},
        )
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
        self.assertIn("performance", thorough["verification_scopes"])

    def test_fast_pins_optional_knobs_to_floors(self) -> None:
        facts = self.base_facts()
        facts["pace"] = "fast"
        payload = policy.build_plan(facts)
        optional = payload["optional_depth"]
        self.assertEqual(
            set(optional),
            set(policy.OPTIONAL_DEPTH_FLOORS),
        )
        for name, entry in optional.items():
            self.assertEqual(entry["value"], entry["floor"], name)
            self.assertTrue(entry["trimmed"], name)
        self.assertEqual(optional["analysis_perspectives"]["floor"], 0)
        self.assertEqual(optional["review_passes"]["floor"], 0)
        self.assertEqual(optional["recovery_exercises"]["floor"], 0)
        self.assertEqual(optional["regression_scope"]["floor"], ["focused"])
        self.assertEqual(
            payload["plan_receipt"]["optional_depth"],
            payload["optional_depth"],
        )

    def test_fast_with_fact_required_capabilities_never_trims_below_floor(self) -> None:
        facts = self.base_facts()
        facts["scope"] = "module"
        facts["risk"] = "high"
        facts["pace"] = "fast"
        payload = policy.build_plan(facts)
        self.assertTrue(payload["capabilities"]["analysis"])
        self.assertTrue(payload["capabilities"]["independent_review"])
        self.assertTrue(payload["capabilities"]["resumable_recovery"])
        self.assertTrue(payload["capabilities"]["split_implementation"])
        self.assertTrue(payload["capabilities"]["separate_verification"])
        self.assertIn("regression", payload["verification_scopes"])
        optional = payload["optional_depth"]
        self.assertEqual(
            optional["analysis_perspectives"],
            {"floor": 1, "value": 1, "trimmed": True},
        )
        self.assertEqual(
            optional["review_passes"],
            {"floor": 1, "value": 1, "trimmed": True},
        )
        self.assertEqual(
            optional["recovery_exercises"],
            {"floor": 0, "value": 0, "trimmed": True},
        )
        self.assertEqual(
            optional["regression_scope"]["floor"],
            ["focused", "regression"],
        )
        self.assertEqual(
            optional["regression_scope"]["value"],
            ["focused", "regression"],
        )
        self.assertTrue(optional["regression_scope"]["trimmed"])

    def test_thorough_raises_optional_knobs_above_floor(self) -> None:
        facts = self.base_facts()
        facts["risk"] = "high"
        facts["pace"] = "thorough"
        thorough = policy.build_plan(facts)
        optional = thorough["optional_depth"]
        self.assertGreater(
            optional["analysis_perspectives"]["value"],
            optional["analysis_perspectives"]["floor"],
        )
        self.assertGreater(
            optional["review_passes"]["value"],
            optional["review_passes"]["floor"],
        )
        self.assertGreater(
            optional["recovery_exercises"]["value"],
            optional["recovery_exercises"]["floor"],
        )
        self.assertEqual(
            optional["regression_scope"]["floor"],
            ["focused"],
        )
        self.assertEqual(
            optional["regression_scope"]["value"],
            ["focused", "regression", "performance"],
        )
        for name, entry in optional.items():
            self.assertFalse(entry["trimmed"], name)

    def test_optional_depth_floors_identical_across_paces(self) -> None:
        floors_by_pace: dict[str, dict[str, object]] = {}
        for pace in policy.PACE_VALUES:
            facts = self.base_facts()
            facts["scope"] = "module"
            facts["risk"] = "high"
            facts["pace"] = pace
            payload = policy.build_plan(facts)
            floors_by_pace[pace] = {
                name: payload["optional_depth"][name]["floor"]
                for name in payload["optional_depth"]
            }
        self.assertEqual(floors_by_pace["fast"], floors_by_pace["adaptive"])
        self.assertEqual(floors_by_pace["fast"], floors_by_pace["thorough"])

    def test_adaptive_optional_depth_matches_floor_untrimmed(self) -> None:
        facts = self.base_facts()
        facts["pace"] = "adaptive"
        payload = policy.build_plan(facts)
        for name, entry in payload["optional_depth"].items():
            self.assertEqual(entry["value"], entry["floor"], name)
            self.assertFalse(entry["trimmed"], name)

    def test_existing_fact_vectors_stay_byte_identical(self) -> None:
        payload = policy.build_plan(self.base_facts())
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.assertEqual(serialized, MINIMAL_PLAN_SNAPSHOT)
        for grade in (
            "documentation_grade",
            "decomposition_grade",
            "review_grade",
        ):
            self.assertNotIn(grade, payload)
            self.assertNotIn(grade, payload["plan_receipt"])

    def test_verification_ladder_extends_compat_tuple(self) -> None:
        self.assertEqual(
            policy.VERIFICATION_SCOPES,
            ("focused", "regression", "multi-environment"),
        )
        self.assertEqual(
            policy.VERIFICATION_SCOPE_LADDER,
            ("smoke", "focused", "regression", "multi-environment", "performance"),
        )

    def test_change_report_capability_is_mutation_only(self) -> None:
        self.assertIn("change_report", policy.CAPABILITIES)
        self.assertEqual(policy.CAPABILITIES[-1], "change_report")
        self.assertIn("change_report", policy.MUTATION_ONLY_CAPABILITIES)
        for mode in ("change", "repair", "maintenance"):
            facts = self.base_facts()
            facts["mode"] = mode
            payload = policy.build_plan(facts)
            self.assertTrue(payload["capabilities"]["change_report"], mode)
            self.assertIn(
                f"mode:{mode}",
                payload["required_provenance"]["change_report"],
            )
        for mode in ("investigation", "review"):
            facts = self.base_facts()
            facts["mode"] = mode
            payload = policy.build_plan(facts)
            self.assertFalse(payload["capabilities"]["change_report"], mode)

    def test_report_node_precedes_review_nodes_and_names_the_baseline_source(self) -> None:
        facts = self.base_facts()
        facts["risk"] = "high"
        payload = policy.build_plan(facts)
        keys = [item["logical_key"] for item in payload["required_nodes"]]
        self.assertIn("report", keys)
        self.assertLess(keys.index("report"), keys.index("review-1"))
        self.assertLess(keys.index("report"), keys.index("finalize"))
        report_node = next(
            item for item in payload["required_nodes"] if item["logical_key"] == "report"
        )
        self.assertEqual(report_node["role"], "report")
        self.assertEqual(report_node["artifact_min"], 1)
        self.assertEqual(report_node["source_keys"], ["work_order.report_baseline"])
        self.assertEqual(report_node["required_artifact_name"], REPORT_ARTIFACT_NAME)
        for item in payload["required_nodes"]:
            if item["logical_key"] != "report":
                self.assertNotIn("source_keys", item)
                self.assertNotIn("required_artifact_name", item)

    def test_read_only_plans_never_acquire_the_change_report_capability(self) -> None:
        facts = self.base_facts()
        facts["mode"] = "review"
        facts["material_impact"] = "unknown"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["planning_status"], "planned")
        self.assertTrue(payload["capabilities"]["analysis"])
        self.assertFalse(payload["capabilities"]["change_report"])
        self.assertNotIn("report_strength", payload["plan_receipt"])
        self.assertNotIn(
            "report",
            [item["logical_key"] for item in payload["required_nodes"]],
        )

    def test_report_strength_maps_confirmed_risk_and_audit_facts(self) -> None:
        expectations = (
            ({"risk": "low", "audit": "runtime-only"}, "minimal"),
            ({"risk": "medium", "audit": "runtime-only"}, "standard"),
            ({"risk": "low", "audit": "result"}, "full"),
            ({"risk": "low", "audit": "full"}, "full"),
            ({"risk": "high", "audit": "runtime-only"}, "full"),
        )
        for overrides, expected in expectations:
            facts = self.base_facts()
            facts.update(overrides)
            if overrides["audit"] != "runtime-only":
                facts["audit_required"] = "yes"
            payload = policy.build_plan(facts)
            with self.subTest(**overrides):
                self.assertTrue(payload["capabilities"]["change_report"])
                self.assertEqual(payload["plan_receipt"]["report_strength"], expected)
                self.assertEqual(policy.derive_report_strength(facts), expected)
        facts = self.base_facts()
        facts["mode"] = "investigation"
        self.assertFalse(policy.build_plan(facts)["capabilities"]["change_report"])
        for mode in policy.MODES:
            facts = self.base_facts()
            facts["mode"] = mode
            facts["risk"] = "high"
            with self.subTest(mode=mode):
                self.assertEqual(policy.derive_report_strength(facts), "full")

    def test_smoke_grade_combines_into_implementation_node(self) -> None:
        facts = self.base_facts()
        facts["verification"] = "smoke"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["verification_scopes"], ["smoke"])
        self.assertFalse(payload["capabilities"]["separate_verification"])
        implementation = [
            item
            for item in payload["required_nodes"]
            if item["logical_key"].startswith("implementation-")
        ]
        self.assertEqual(len(implementation), 1)
        self.assertEqual(implementation[0]["verification_scope"], "smoke")
        self.assertFalse(
            any(
                item["logical_key"].startswith("verification-")
                for item in payload["required_nodes"]
            )
        )

    def test_smoke_requires_tiny_scope_and_low_risk(self) -> None:
        facts = self.base_facts()
        facts["verification"] = "smoke"
        facts["risk"] = "medium"
        with self.assertRaises(policy.PlanningInputError) as context:
            policy.build_plan(facts)
        self.assertEqual(context.exception.code, "planning_input_contradictory")
        facts = self.base_facts()
        facts["verification"] = "smoke"
        facts["scope"] = "module"
        with self.assertRaises(policy.PlanningInputError) as context:
            policy.build_plan(facts)
        self.assertEqual(context.exception.code, "planning_input_contradictory")

    def test_performance_grade_only_via_thorough_or_explicit_fact(self) -> None:
        facts = self.base_facts()
        payload = policy.build_plan(facts)
        self.assertNotIn("performance", payload["verification_scopes"])
        facts = self.base_facts()
        facts["pace"] = "thorough"
        payload = policy.build_plan(facts)
        self.assertEqual(
            payload["verification_scopes"],
            ["focused", "regression", "performance"],
        )
        keys = [
            item["logical_key"]
            for item in payload["required_nodes"]
            if item["logical_key"].startswith("verification-")
        ]
        self.assertEqual(
            keys,
            ["verification-focused", "verification-regression", "verification-performance"],
        )
        facts = self.base_facts()
        facts["verification"] = "performance"
        payload = policy.build_plan(facts)
        self.assertEqual(
            payload["verification_scopes"],
            ["focused", "performance"],
        )
        keys = [
            item["logical_key"]
            for item in payload["required_nodes"]
            if item["logical_key"].startswith("verification-")
        ]
        self.assertEqual(keys, ["verification-focused", "verification-performance"])

    def test_documentation_grade_derived_and_payload_only(self) -> None:
        payload = policy.build_plan(self.base_facts())
        self.assertNotIn("documentation_grade", payload)
        facts = self.base_facts()
        facts["audit_required"] = "yes"
        facts["audit"] = "result"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["documentation_grade"], "inline")
        self.assertNotIn("documentation_grade", payload["plan_receipt"])
        facts = self.base_facts()
        facts["risk"] = "high"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["documentation_grade"], "full-user")
        facts = self.base_facts()
        facts["mode"] = "investigation"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["documentation_grade"], "spec-design")

    def test_decomposition_grade_recorded_in_receipt(self) -> None:
        payload = policy.build_plan(self.base_facts())
        self.assertNotIn("decomposition_grade", payload)
        self.assertNotIn("decomposition_grade", payload["plan_receipt"])
        facts = self.base_facts()
        facts["scope"] = "module"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["decomposition_grade"], "sequence")
        self.assertEqual(payload["plan_receipt"]["decomposition_grade"], "sequence")
        facts = self.base_facts()
        facts["scope"] = "cross-cutting"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["decomposition_grade"], "feature-farms")
        facts = self.base_facts()
        facts["crosses_sessions"] = "yes"
        facts["duration"] = "cross-session"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["decomposition_grade"], "milestone-subtrees")
        facts = self.base_facts()
        facts["multiple_actors"] = "yes"
        facts["coordination"] = "multi-party"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["decomposition_grade"], "milestone-subtrees")
        facts = self.base_facts()
        facts["mode"] = "review"
        facts["scope"] = "cross-cutting"
        payload = policy.build_plan(facts)
        self.assertNotIn("decomposition_grade", payload)

    def test_review_grade_mapping(self) -> None:
        payload = policy.build_plan(self.base_facts())
        self.assertNotIn("review_grade", payload)
        facts = self.base_facts()
        facts["risk"] = "medium"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["review_grade"], "self-check")
        facts = self.base_facts()
        facts["risk"] = "high"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["review_grade"], "independent")
        facts = self.base_facts()
        facts["coordination"] = "review"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["review_grade"], "independent")
        facts = self.base_facts()
        facts["audit_required"] = "yes"
        facts["risk"] = "high"
        facts["audit"] = "full"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["review_grade"], "architecture-gate")
        self.assertEqual(
            payload["plan_receipt"]["review_grade"],
            "architecture-gate",
        )

    def test_grade_floors_preserved_across_paces(self) -> None:
        grades_by_pace: dict[str, tuple[str, str, str]] = {}
        scopes_by_pace: dict[str, list[str]] = {}
        for pace in policy.PACE_VALUES:
            facts = self.base_facts()
            facts["scope"] = "module"
            facts["audit_required"] = "yes"
            facts["risk"] = "high"
            facts["audit"] = "full"
            facts["pace"] = pace
            payload = policy.build_plan(facts)
            grades_by_pace[pace] = (
                payload["documentation_grade"],
                payload["decomposition_grade"],
                payload["review_grade"],
            )
            scopes_by_pace[pace] = payload["verification_scopes"]
        self.assertEqual(
            grades_by_pace["fast"],
            ("full-user", "sequence", "architecture-gate"),
        )
        self.assertEqual(grades_by_pace["fast"], grades_by_pace["adaptive"])
        self.assertEqual(grades_by_pace["fast"], grades_by_pace["thorough"])

    def test_fast_never_downgrades_a_grade_below_its_fact_floor(self) -> None:
        facts = self.base_facts()
        facts["verification"] = "performance"
        facts["pace"] = "fast"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["verification_scopes"], ["focused", "performance"])
        self.assertEqual(
            payload["optional_depth"]["regression_scope"]["floor"],
            ["focused", "performance"],
        )
        self.assertEqual(
            payload["optional_depth"]["regression_scope"]["value"],
            ["focused", "performance"],
        )
        facts = self.base_facts()
        facts["audit_required"] = "yes"
        facts["risk"] = "high"
        facts["audit"] = "full"
        facts["pace"] = "fast"
        payload = policy.build_plan(facts)
        self.assertEqual(payload["review_grade"], "architecture-gate")
        self.assertEqual(payload["documentation_grade"], "full-user")
        self.assertTrue(payload["capabilities"]["independent_review"])

    def test_smoke_manifest_binds_the_planned_sources_and_requires_the_baseline_key(self) -> None:
        """Corrected expectation: the smoke path binds its two sources **and** publishes the
        report node's declared source key.

        The previous name — `test_smoke_manifest_binding_is_tolerated` — and its packet, whose
        blackboard carried only `work_order.plan_id`, encoded the tolerance G-37 removed: the
        validator accepted a plan-required report node whose declared `source_keys` entry was
        never published, so a manifest could pass with no baseline value at all. The positive
        half publishes the key; the negative half removes it again and asserts the refusal
        naming the key, so the test pins the new behaviour rather than the removed tolerance.
        """
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["verification"] = "smoke"
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            source_map = {
                "implementation-1": {"node_id": "rt_smoke_worker"},
                "report": {"node_id": "rt_smoke_report"},
            }
            packet = {
                "packet": {
                    "target": {
                        "logical_key": "finalize",
                        "role": "work-order-finalize",
                    },
                    "blackboard": [
                        {"key": "work_order.plan_id", "value": receipt["plan_id"]},
                        {"key": BASELINE_KEY, "value": BASELINE_VALUE},
                    ],
                    "source_categories": [
                        {
                            "name": "plan-implementation-1",
                            "sources": [
                                {
                                    "node_id": "rt_smoke_worker",
                                    "logical_key": "implementation-1",
                                    "role": "implementation",
                                    "status": "succeeded",
                                    "artifacts": ["smoke-artifact.md"],
                                }
                            ],
                        },
                        {
                            "name": "plan-report",
                            "sources": [
                                {
                                    "node_id": "rt_smoke_report",
                                    "logical_key": "report",
                                    "role": "report",
                                    "status": "succeeded",
                                    "artifacts": [REPORT_ARTIFACT_NAME],
                                }
                            ],
                        },
                    ],
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
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["min_sources"], 2)

            # The removed tolerance: the same smoke packet without the declared key is refused,
            # and the refusal names the key the caller failed to publish.
            unpublished = json.loads(json.dumps(packet))
            unpublished["packet"]["blackboard"] = [
                {"key": "work_order.plan_id", "value": receipt["plan_id"]}
            ]
            arguments[5] = json.dumps(unpublished, separators=(",", ":"))
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                arguments,
            )
            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["error"]["code"], "missing_required_source_key")
            self.assertEqual(payload["error"]["keys"], [BASELINE_KEY])

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
        self.assertFalse(payload["capabilities"]["change_report"])

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
        """Corrected fixture: the report slot delivers the artifact the plan names.

        The fixture previously gave every required node a generic `artifact-N-0` name and
        published only `work_order.plan_id`, so it asserted acceptance of a manifest in which
        the report's declared `source_keys` entry was never published — the tolerance G-37
        removed — and in which the report slot's artifact did not match the
        `required_artifact_name` G-18 added. Both halves of the fixture now satisfy the plan's
        own declaration, and every negative assertion is unchanged.
        """
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["scope"] = "module"
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            report_node = next(
                item
                for item in receipt["required_nodes"]
                if item["logical_key"] == "report"
            )
            self.assertEqual(report_node["required_artifact_name"], REPORT_ARTIFACT_NAME)
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
                                    item.get(
                                        "required_artifact_name",
                                        f"artifact-{index}-{item_index}",
                                    )
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
                        {"key": "work_order.plan_id", "value": receipt["plan_id"]},
                        {"key": BASELINE_KEY, "value": BASELINE_VALUE},
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

    def test_adaptive_manifest_accepts_the_planned_report_node(self) -> None:
        """Corrected fixture: the report node's slot carries the named artifact and the
        published baseline.

        The report sources were previously named `report-source-N-0` — an artifact name the
        plan's `report` entry does not declare — and the packet published only
        `work_order.plan_id`, so acceptance was asserted for a manifest that satisfied neither
        G-18's artifact identity nor G-37's published-key requirement. The missing-source
        negative half is unchanged.
        """
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            sources = [
                item
                for item in receipt["required_nodes"]
                if item["role"] != "finalizer"
            ]
            self.assertEqual(
                [item["logical_key"] for item in sources],
                ["implementation-1", "report"],
            )
            self.assertEqual(
                next(
                    item["required_artifact_name"]
                    for item in sources
                    if item["logical_key"] == "report"
                ),
                REPORT_ARTIFACT_NAME,
            )
            source_map: dict[str, dict[str, object]] = {}
            packet_categories: list[dict[str, object]] = []
            for index, item in enumerate(sources):
                node_id = f"rt_report_{index}"
                source_map[item["logical_key"]] = {"node_id": node_id}
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
                                    item.get(
                                        "required_artifact_name",
                                        f"report-source-{index}-{unit}",
                                    )
                                    for unit in range(item["artifact_min"])
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
                        {"key": "work_order.plan_id", "value": receipt["plan_id"]},
                        {"key": BASELINE_KEY, "value": BASELINE_VALUE},
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
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["min_sources"], 2)

            missing_map = {
                key: value for key, value in source_map.items() if key != "report"
            }
            arguments[3] = json.dumps(missing_map, separators=(",", ":"))
            code, payload = self.invoke(
                SCRIPTS / "validate_adaptive_manifest.py",
                arguments,
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "missing_required_source")
            self.assertEqual(payload["error"]["keys"], ["report"])

    def report_slot_manifest(
        self,
        receipt: dict[str, object],
        *,
        baseline: str | None,
        report_artifacts: list[str],
    ) -> tuple[dict[str, dict[str, str]], dict[str, object]]:
        """The minimal plan's two-source finalizer manifest.

        `baseline is None` omits the declared key from the blackboard entirely; any other
        value (including `""` and whitespace) is published as-is.
        """
        blackboard = [{"key": "work_order.plan_id", "value": receipt["plan_id"]}]
        if baseline is not None:
            blackboard.append({"key": BASELINE_KEY, "value": baseline})
        source_map = {
            "implementation-1": {"node_id": "rt_impl"},
            "report": {"node_id": "rt_report"},
        }
        packet = {
            "packet": {
                "target": {"logical_key": "finalize", "role": "work-order-finalize"},
                "blackboard": blackboard,
                "source_categories": [
                    {
                        "name": "plan-implementation-1",
                        "sources": [
                            {
                                "node_id": "rt_impl",
                                "logical_key": "implementation-1",
                                "role": "implementation",
                                "status": "succeeded",
                                "artifacts": ["implementation.md"],
                            }
                        ],
                    },
                    {
                        "name": "plan-report",
                        "sources": [
                            {
                                "node_id": "rt_report",
                                "logical_key": "report",
                                "role": "report",
                                "status": "succeeded",
                                "artifacts": list(report_artifacts),
                            }
                        ],
                    },
                ],
            }
        }
        return source_map, packet

    def validate_manifest(
        self,
        bridge: Path,
        facts: dict[str, str],
        receipt: dict[str, object],
        source_map: dict[str, object],
        packet: dict[str, object],
    ) -> tuple[int, dict[str, object]]:
        return self.invoke(
            SCRIPTS / "validate_adaptive_manifest.py",
            [
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
            ],
        )

    def test_report_slot_must_deliver_the_artifact_the_plan_names(self) -> None:
        """G-18 negative test: the report slot's artifact identity, not its count.

        Against the pre-change validator every packet below exited 0, because the only artifact
        check was `len(artifacts) < artifact_min`. The decoys are chosen so that a substring,
        prefix or suffix implementation cannot pass: each one shares characters with
        `change-report.html` while having a different basename. The positive half covers both
        path separators, because the runtime projects artifact paths as recorded strings.
        """
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            report_node = next(
                item
                for item in receipt["required_nodes"]
                if item["logical_key"] == "report"
            )
            self.assertEqual(report_node["required_artifact_name"], REPORT_ARTIFACT_NAME)
            source_map, _ = self.report_slot_manifest(
                receipt, baseline=BASELINE_VALUE, report_artifacts=[REPORT_ARTIFACT_NAME]
            )
            for delivered in (
                "notes.txt",
                "change-report.html.bak",
                "xchange-report.html",
                "change-report.htm",
                "C:\\wb\\artifacts\\rt_report\\notes.txt",
                "/wb/artifacts/rt_report/change-report.html.bak",
            ):
                with self.subTest(delivered=delivered):
                    _, packet = self.report_slot_manifest(
                        receipt, baseline=BASELINE_VALUE, report_artifacts=[delivered]
                    )
                    code, payload = self.validate_manifest(
                        bridge, facts, receipt, source_map, packet
                    )
                    self.assertEqual(code, 2, (delivered, payload))
                    self.assertEqual(payload["error"]["code"], "report_artifact_mismatch")
                    self.assertEqual(payload["error"]["keys"], ["report"])
            for delivered in (
                REPORT_ARTIFACT_NAME,
                "C:\\wb\\artifacts\\rt_report\\" + REPORT_ARTIFACT_NAME,
                "/wb/artifacts/rt_report/" + REPORT_ARTIFACT_NAME,
            ):
                with self.subTest(delivered=delivered):
                    _, packet = self.report_slot_manifest(
                        receipt, baseline=BASELINE_VALUE, report_artifacts=[delivered]
                    )
                    code, payload = self.validate_manifest(
                        bridge, facts, receipt, source_map, packet
                    )
                    self.assertEqual(code, 0, (delivered, payload))
                    self.assertTrue(payload["ok"])

    def test_unpublished_baseline_key_is_refused(self) -> None:
        """G-37 negative test: the report node's declared source key must be non-blank.

        Against the pre-change validator every packet below exited 0 — the validator never read
        `source_keys` — so a report slot could validate clean while proving no baseline at all.
        The blank and tab cases are included because a truthiness test would accept them; the
        check is `.strip()`-based, and the refusal names the key the caller failed to publish.
        """
        with tempfile.TemporaryDirectory() as temporary:
            bridge = Path(temporary) / "WORKFLOW.md"
            bridge.write_text("# Workflow\n", encoding="utf-8")
            facts = self.base_facts()
            facts["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            receipt = policy.build_plan(facts)["plan_receipt"]
            report_node = next(
                item
                for item in receipt["required_nodes"]
                if item["logical_key"] == "report"
            )
            self.assertEqual(report_node["source_keys"], [BASELINE_KEY])
            source_map, _ = self.report_slot_manifest(
                receipt, baseline=BASELINE_VALUE, report_artifacts=[REPORT_ARTIFACT_NAME]
            )
            for label, baseline in (
                ("absent", None),
                ("empty", ""),
                ("blank", "   "),
                ("tab", "\t"),
            ):
                with self.subTest(baseline=label):
                    _, packet = self.report_slot_manifest(
                        receipt,
                        baseline=baseline,
                        report_artifacts=[REPORT_ARTIFACT_NAME],
                    )
                    code, payload = self.validate_manifest(
                        bridge, facts, receipt, source_map, packet
                    )
                    self.assertEqual(code, 2, (label, payload))
                    self.assertEqual(payload["error"]["code"], "missing_required_source_key")
                    self.assertEqual(payload["error"]["keys"], [BASELINE_KEY])
            _, packet = self.report_slot_manifest(
                receipt, baseline=BASELINE_VALUE, report_artifacts=[REPORT_ARTIFACT_NAME]
            )
            code, payload = self.validate_manifest(
                bridge, facts, receipt, source_map, packet
            )
            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["min_sources"], 2)

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
