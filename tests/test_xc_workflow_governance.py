from __future__ import annotations

import importlib.util
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

import workflow_scenario_harness as harness


SCENARIOS = REPOSITORY_ROOT / "tests" / "fixtures" / "model_robust_workflow" / "scenarios-v1.json"
HISTORICAL_MANIFEST = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "model_robust_workflow" / "baseline-v1.json"
)
CURRENT_MANIFEST = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "model_robust_workflow" / "post-change-v1.json"
)
CLASSIFIER = REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "classify_governance.py"
PUBLIC_CLASSIFIER = REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "classify.py"
WORK_SKILL = REPOSITORY_ROOT / "skills" / "xc-work" / "SKILL.md"
WORKFLOW_EVOLUTION_SKILL = REPOSITORY_ROOT / "skills" / "xc-workflow-evolution" / "SKILL.md"
FACT_ORDER = [
    "needs_persistence",
    "material_impact",
    "difficult_rollback",
    "crosses_sessions",
    "multiple_actors",
    "audit_required",
]
EXPECTED_VECTORS = {
    "T0": ["no", "no", "no", "no", "no", "no"],
    "T1": ["no", "no", "no", "no", "no", "no"],
    "T1-M": ["no", "no", "no", "no", "no", "no"],
    "T2": ["yes", "yes", "no", "unknown", "no", "yes"],
    "T3": ["yes", "yes", "yes", "no", "yes", "yes"],
    "T4": ["yes", "yes", "unknown", "yes", "yes", "yes"],
    "T-U": ["unknown", "unknown", "unknown", "unknown", "unknown", "unknown"],
}
EXPECTED_ROUTES = {
    "T0": "direct",
    "T1": "direct",
    "T1-M": "managed",
    "T2": "managed",
    "T3": "managed",
    "T4": "managed",
    "T-U": "managed",
}
STRUCTURAL_METRICS = {
    "T1-M": {
        "runtime_calls": 35,
        "explicit_transitions": 16,
        "delegations": 6,
        "subagent_delegations": 2,
        "tool_delegations": 4,
        "nodes": 32,
        "executable_nodes": 15,
        "artifacts": 2,
        "documents": 2,
        "gates": 0,
        "terminal_operations": 8,
    },
    "T2": {
        "runtime_calls": 47,
        "explicit_transitions": 22,
        "delegations": 9,
        "subagent_delegations": 3,
        "tool_delegations": 6,
        "nodes": 41,
        "executable_nodes": 21,
        "artifacts": 3,
        "documents": 3,
        "gates": 0,
        "terminal_operations": 11,
    },
    "T3": {
        "runtime_calls": 74,
        "explicit_transitions": 34,
        "delegations": 14,
        "subagent_delegations": 6,
        "tool_delegations": 8,
        "nodes": 52,
        "executable_nodes": 29,
        "artifacts": 6,
        "documents": 4,
        "gates": 1,
        "terminal_operations": 17,
    },
    "T4": {
        "runtime_calls": 89,
        "explicit_transitions": 40,
        "delegations": 17,
        "subagent_delegations": 9,
        "tool_delegations": 8,
        "nodes": 55,
        "executable_nodes": 32,
        "artifacts": 9,
        "documents": 4,
        "gates": 1,
        "terminal_operations": 20,
    },
}
EXPECTED_CHECKPOINTS = {
    "T0": 0,
    "T1": 0,
    "T1-M": 8,
    "T2": 11,
    "T3": 17,
    "T4": 20,
}


def load_classifier_module():
    specification = importlib.util.spec_from_file_location("xc_work_governance_classifier", CLASSIFIER)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load classifier module: {CLASSIFIER}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


classifier = load_classifier_module()


class WorkflowGovernanceFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario_payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        cls.historical_manifest = json.loads(
            HISTORICAL_MANIFEST.read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(CURRENT_MANIFEST.read_text(encoding="utf-8"))

    def test_scenario_fixture_has_complete_evidence_and_confirmed_vectors(self) -> None:
        self.assertEqual(self.scenario_payload["schema_version"], 1)
        self.assertEqual(self.scenario_payload["fact_order"], FACT_ORDER)
        self.assertEqual(self.scenario_payload["fact_values"], ["no", "yes", "unknown"])
        scenarios = self.scenario_payload["scenarios"]
        self.assertEqual([item["id"] for item in scenarios], list(EXPECTED_VECTORS))

        for scenario in scenarios:
            scenario_id = scenario["id"]
            with self.subTest(scenario=scenario_id):
                self.assertTrue(scenario["raw_request"].strip())
                self.assertEqual(list(scenario["confirmed_facts"]), FACT_ORDER)
                self.assertEqual(list(scenario["evidence"]), FACT_ORDER)
                self.assertEqual(
                    [scenario["confirmed_facts"][name] for name in FACT_ORDER],
                    EXPECTED_VECTORS[scenario_id],
                )
                for fact in FACT_ORDER:
                    evidence = scenario["evidence"][fact]
                    self.assertTrue(evidence["source"].strip())
                    self.assertTrue(evidence["statement"].strip())
                self.assertEqual(scenario["expected_route"], EXPECTED_ROUTES[scenario_id])
                self.assertTrue(scenario["expected_reason_codes"])
                self.assertTrue(scenario["profile"])
                self.assertGreaterEqual(scenario["dynamic_nodes"]["count"], 0)
                self.assertTrue(scenario["dynamic_nodes"]["description"])
                self.assertTrue(scenario["maintenance_families"])

    def test_only_all_no_uses_direct_route_and_explicit_run_stays_managed(self) -> None:
        scenarios = {item["id"]: item for item in self.scenario_payload["scenarios"]}
        for scenario_id, scenario in scenarios.items():
            all_no = all(value == "no" for value in scenario["confirmed_facts"].values())
            with self.subTest(scenario=scenario_id):
                if scenario_id == "T1-M":
                    self.assertTrue(all_no)
                    self.assertEqual(scenario["governance_selection"], "explicit-run")
                    self.assertEqual(scenario["expected_route"], "managed")
                else:
                    self.assertEqual(scenario["expected_route"] == "direct", all_no)

    def test_current_manifest_identity_and_input_hashes_are_current(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 2)
        self.assertEqual(self.manifest["manifest_id"], harness.CURRENT_MANIFEST_ID)
        self.assertEqual(self.manifest["manifest_role"], harness.CURRENT_MANIFEST_ROLE)
        self.assertEqual(self.manifest["normalization_version"], harness.NORMALIZATION_VERSION)
        self.assertEqual(self.manifest["python_version"], harness.platform.python_version())
        self.assertNotIn("baseline_commit", self.manifest)
        self.assertRegex(self.manifest["recording_base_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(self.manifest["input_hashes"], harness.input_hashes())
        self.assertEqual(
            self.manifest["scenario_fixture"],
            "tests/fixtures/model_robust_workflow/scenarios-v1.json",
        )

    def test_historical_manifest_has_frozen_identity_and_bytes(self) -> None:
        before = HISTORICAL_MANIFEST.read_bytes()
        code, payload = harness.validate_historical_manifest(HISTORICAL_MANIFEST)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["manifest_role"], harness.HISTORICAL_MANIFEST_ROLE)
        self.assertEqual(payload["manifest_id"], harness.HISTORICAL_MANIFEST_ID)
        self.assertEqual(payload["sha256"], harness.HISTORICAL_MANIFEST_SHA256)
        self.assertEqual(harness.sha256_bytes(before), harness.HISTORICAL_MANIFEST_SHA256)
        self.assertEqual(HISTORICAL_MANIFEST.read_bytes(), before)
        self.assertEqual(self.historical_manifest["schema_version"], 1)
        self.assertEqual(
            self.historical_manifest["manifest_id"],
            harness.HISTORICAL_MANIFEST_ID,
        )

    def test_current_manifest_links_explained_deltas_to_historical_manifest(self) -> None:
        comparison = self.manifest["comparison"]
        self.assertEqual(
            comparison["historical_manifest"],
            harness.historical_descriptor(),
        )
        expected = harness.build_measurement_deltas(
            self.historical_manifest["measurements"],
            self.manifest["measurements"],
            self.manifest["change_note"]["reason"],
        )
        self.assertEqual(comparison["measurement_deltas"], expected)
        self.assertTrue(expected)
        self.assertTrue(
            all(item["explanation"].strip() for item in expected)
        )

    def test_profile_structure_and_auto_commit_results_are_explicit(self) -> None:
        measurements = self.manifest["measurements"]
        profiles = measurements["profiles"]
        self.assertEqual(list(profiles), ["T0", "T1", "T1-M", "T2", "T3", "T4"])
        for scenario_id in ("T0", "T1"):
            for configuration in ("auto_commit_false", "auto_commit_true"):
                metrics = profiles[scenario_id][configuration]["metrics"]
                for name, value in metrics.items():
                    if name == "maintenance_families":
                        self.assertEqual(value, 1)
                    else:
                        self.assertEqual(value, 0, (scenario_id, configuration, name))

        for scenario_id, expected in STRUCTURAL_METRICS.items():
            for configuration in ("auto_commit_false", "auto_commit_true"):
                metrics = profiles[scenario_id][configuration]["metrics"]
                with self.subTest(scenario=scenario_id, configuration=configuration):
                    for name, value in expected.items():
                        self.assertEqual(metrics[name], value, name)
                    self.assertGreater(metrics["context_bytes"], 0)
                    self.assertEqual(metrics["snapshot_calls"], 0)
                    self.assertEqual(metrics["direct_runtime_xml_reads"], 0)

        self.assertEqual(
            measurements["checkpoint_commits"]["auto_commit_false"],
            {scenario_id: 0 for scenario_id in EXPECTED_CHECKPOINTS},
        )
        self.assertEqual(
            measurements["checkpoint_commits"]["auto_commit_true"],
            EXPECTED_CHECKPOINTS,
        )

    def test_semantic_negative_baseline_is_scoped_without_snapshot_or_xml_access(self) -> None:
        semantic = self.manifest["measurements"]["semantic_negative_baseline"]
        self.assertEqual(semantic["sibling_count"], 128)
        self.assertEqual(semantic["target_projection_count"], 1)
        self.assertEqual(semantic["target_forbidden_sibling_id_occurrences"], 0)
        self.assertEqual(semantic["manual_source_ids_required"], 5)
        self.assertEqual(semantic["target_to_source_bindings"], 0)
        self.assertEqual(semantic["scoped_decision_bindings"], 0)
        self.assertEqual(semantic["scoped_evidence_bindings"], 0)
        self.assertEqual(semantic["scoped_blocker_recovery_bindings"], 0)
        self.assertTrue(semantic["full_blackboard_exposes_unselected_value"])
        self.assertEqual(semantic["snapshot_calls"], 0)
        self.assertEqual(semantic["direct_runtime_xml_reads"], 0)

    def test_every_fixture_reports_no_undeclared_cleanup_paths(self) -> None:
        measurements = self.manifest["measurements"]
        cleanups = [
            configuration["cleanup"]
            for profile in measurements["profiles"].values()
            for configuration in profile.values()
        ]
        cleanups.append(measurements["semantic_negative_baseline"]["cleanup"])
        for cleanup in cleanups:
            self.assertEqual(cleanup["project_undeclared_paths"], [])
            self.assertEqual(cleanup["workshop_undeclared_paths"], [])

    def test_normalization_is_deterministic_and_replaces_volatile_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "path": str(root / "project" / "runtime"),
                "repository": str(REPOSITORY_ROOT / "skills"),
                "timestamp": "2026-08-01T12:34:56.123456+00:00",
                "checksum": "a" * 64,
                "ordered": {"z": 1, "a": 2},
            }
            first = harness.compact_json(harness.normalize_payload(payload, root))
            second = harness.compact_json(harness.normalize_payload(payload, root))
        self.assertEqual(first, second)
        self.assertIn("<TEMP_ROOT>", first)
        self.assertIn("<REPOSITORY_ROOT>", first)
        self.assertIn("<TIMESTAMP>", first)
        self.assertIn("<SHA256>", first)
        self.assertLess(first.index('"a":2'), first.index('"z":1'))

    def test_record_requires_reason_and_records_old_new_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = Path(temporary) / "baseline.json"
            code, payload = harness.record_manifest(manifest_path, " ")
            self.assertEqual(code, 2)
            self.assertEqual(payload["error"]["code"], "record_reason_required")
            self.assertFalse(manifest_path.exists())

            first = {"profiles": {"T0": {"value": 0}}}
            second = {"profiles": {"T0": {"value": 1}}}
            with mock.patch.object(harness, "collect_measurements", return_value=first):
                code, _ = harness.record_manifest(manifest_path, "Initial explicit record")
            self.assertEqual(code, 0)
            with mock.patch.object(harness, "collect_measurements", return_value=second):
                code, _ = harness.record_manifest(manifest_path, "Approved baseline adjustment")
            self.assertEqual(code, 0)
            recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(recorded["change_note"]["reason"], "Approved baseline adjustment")
            self.assertEqual(
                recorded["change_note"]["old_value"],
                self.historical_manifest["measurements"],
            )
            self.assertEqual(recorded["change_note"]["new_value"], second)
            self.assertEqual(recorded["change_note"]["input_hashes"], harness.input_hashes())
            self.assertEqual(recorded["manifest_role"], harness.CURRENT_MANIFEST_ROLE)
            self.assertEqual(recorded["recording_base_commit"], harness.repository_head())
            self.assertEqual(
                recorded["comparison"]["historical_manifest"],
                harness.historical_descriptor(),
            )
            self.assertTrue(recorded["comparison"]["measurement_deltas"])
            self.assertTrue(
                all(
                    item["explanation"] == "Approved baseline adjustment"
                    for item in recorded["comparison"]["measurement_deltas"]
                )
            )

        with self.assertRaises(SystemExit) as raised:
            harness.build_parser().parse_args(["record", "--manifest", "baseline.json"])
        self.assertEqual(raised.exception.code, 2)

    def test_record_refuses_to_overwrite_historical_manifest(self) -> None:
        before = HISTORICAL_MANIFEST.read_bytes()
        with mock.patch.object(harness, "collect_measurements") as collect:
            code, payload = harness.record_manifest(
                HISTORICAL_MANIFEST,
                "Must not overwrite history",
            )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "historical_manifest_immutable")
        collect.assert_not_called()
        self.assertEqual(HISTORICAL_MANIFEST.read_bytes(), before)

    def test_verify_reports_input_drift_without_collecting_or_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = Path(temporary) / "baseline.json"
            changed = json.loads(CURRENT_MANIFEST.read_text(encoding="utf-8"))
            first_input = next(iter(changed["input_hashes"]))
            changed["input_hashes"][first_input] = "0" * 64
            changed["change_note"]["input_hashes"][first_input] = "0" * 64
            manifest_path.write_text(json.dumps(changed), encoding="utf-8")
            before = manifest_path.read_bytes()
            with mock.patch.object(harness, "collect_measurements") as collect:
                code, payload = harness.verify_manifest(manifest_path)
            self.assertEqual(code, 1)
            self.assertEqual(payload["error"]["code"], "current_input_drift")
            self.assertIn(f"input_hashes.{first_input}", {item["field"] for item in payload["drift"]})
            collect.assert_not_called()
            self.assertEqual(manifest_path.read_bytes(), before)

    def test_verification_is_not_bound_to_current_head(self) -> None:
        with mock.patch.object(
            harness,
            "repository_head",
            return_value="f" * 40,
        ) as repository_head, mock.patch.object(
            harness,
            "collect_measurements",
            return_value=self.manifest["measurements"],
        ):
            code, payload = harness.verify_manifest(CURRENT_MANIFEST)
        self.assertEqual(code, 0, payload)
        repository_head.assert_not_called()

    def test_forbidden_runtime_access_mutations_fail_collection_and_verification(self) -> None:
        expected = {
            "direct-runtime-xml-read": (0, 1),
            "snapshot": (1, 0),
        }
        for action, counters in expected.items():
            with self.subTest(action=action, phase="collection"):
                with self.assertRaises(harness.HarnessBoundaryViolation) as raised:
                    harness.exercise_boundary_mutation(action)
                self.assertEqual(raised.exception.operation, action)
                self.assertEqual(raised.exception.snapshot_calls, counters[0])
                self.assertEqual(
                    raised.exception.direct_runtime_xml_reads,
                    counters[1],
                )

            output = io.StringIO()
            with self.subTest(action=action, phase="verification"):
                with mock.patch.object(
                    harness,
                    "collect_measurements",
                    side_effect=lambda action=action: harness.exercise_boundary_mutation(
                        action
                    ),
                ), redirect_stdout(output):
                    code = harness.main(
                        ["verify", "--manifest", str(CURRENT_MANIFEST)]
                    )
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 1)
                self.assertEqual(
                    payload["error"]["code"],
                    "baseline_collection_failed",
                )
                self.assertIn(action, payload["error"]["message"])

    def test_public_verify_command_matches_checked_in_measurements(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(TESTS_ROOT / "workflow_scenario_harness.py"),
                "verify",
                "--manifest",
                str(CURRENT_MANIFEST),
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["drift"], [])
        self.assertEqual(
            payload["measurements_sha256"],
            harness.sha256_json(self.manifest["measurements"]),
        )
        self.assertEqual(
            payload["historical_manifest_sha256"],
            harness.HISTORICAL_MANIFEST_SHA256,
        )


class WorkflowGovernanceClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario_payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))

    @staticmethod
    def classifier_arguments(facts: dict[str, str]) -> list[str]:
        arguments: list[str] = []
        for name in FACT_ORDER:
            arguments.extend([f"--{name.replace('_', '-')}", facts[name]])
        return arguments

    def invoke_classifier(
        self,
        arguments: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        process_environment = os.environ.copy()
        if environment:
            process_environment.update(environment)
        completed = subprocess.run(
            [sys.executable, str(CLASSIFIER), *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=process_environment,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return completed, json.loads(completed.stdout)

    def invoke_public_classifier(
        self,
        arguments: list[str],
        *,
        executable: Path = PUBLIC_CLASSIFIER,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, str(executable), *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=10,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return completed, json.loads(completed.stdout)

    def invoke_public_with_low_level_payload(
        self,
        arguments: list[str],
        payload: dict[str, object],
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = root / "classify.py"
            shutil.copyfile(PUBLIC_CLASSIFIER, adapter)
            encoded = json.dumps(json.dumps(payload, separators=(",", ":")))
            (root / "classify_governance.py").write_text(
                f"print({encoded})\n",
                encoding="utf-8",
            )
            return self.invoke_public_classifier(arguments, executable=adapter)

    @staticmethod
    def public_success_payload(facts: dict[str, str]) -> dict[str, object]:
        triggers = [
            f"fact-{facts[name]}:{name}"
            for name in FACT_ORDER
            if facts[name] in {"yes", "unknown"}
        ]
        route = "managed" if triggers else "direct"
        return {
            "schema_version": 1,
            "ok": True,
            "route": route,
            "facts": dict(facts),
            "triggers": triggers or ["all-facts-no"],
            "unknowns": [name for name in FACT_ORDER if facts[name] == "unknown"],
            "escalation": {"entry_point": "xc-work"} if route == "managed" else None,
        }

    def assert_public_escalation(
        self,
        completed: subprocess.CompletedProcess[str],
        payload: dict[str, object],
        expected_code: str,
    ) -> None:
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["route"], "managed")
        self.assertEqual(payload["classification_status"], "escalated")
        self.assertEqual(payload["reason_codes"], ["classification-unavailable"])
        self.assertEqual(payload["diagnostic"]["input_error"], expected_code)

    def assert_input_error(
        self,
        arguments: list[str],
        expected_code: str,
    ) -> dict[str, object]:
        completed, payload = self.invoke_classifier(arguments)
        self.assertEqual(completed.returncode, 2, completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], expected_code)
        self.assertNotIn("route", payload)
        return payload

    def test_raw_scenario_fact_vectors_match_routes_and_reason_codes(self) -> None:
        for scenario in self.scenario_payload["scenarios"]:
            scenario_id = scenario["id"]
            arguments = self.classifier_arguments(scenario["confirmed_facts"])
            completed, payload = self.invoke_classifier(arguments)
            with self.subTest(scenario=scenario_id):
                self.assertEqual(completed.returncode, 0, completed.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(list(payload["facts"]), FACT_ORDER)
                if scenario.get("governance_selection") == "explicit-run":
                    self.assertEqual(payload["route"], "direct")
                    self.assertEqual(payload["triggers"], ["all-facts-no"])
                    self.assertEqual(scenario["expected_route"], "managed")
                    self.assertEqual(scenario["expected_reason_codes"], ["explicit-managed-run"])
                else:
                    self.assertEqual(payload["route"], scenario["expected_route"])
                    self.assertEqual(payload["triggers"], scenario["expected_reason_codes"])

    def test_every_fact_combination_is_fail_closed_except_all_no(self) -> None:
        for values in itertools.product(("no", "yes", "unknown"), repeat=len(FACT_ORDER)):
            facts = dict(zip(FACT_ORDER, values, strict=True))
            payload = classifier.classify(facts)
            expected_route = "direct" if all(value == "no" for value in values) else "managed"
            with self.subTest(values=values):
                self.assertEqual(payload["route"], expected_route)
                self.assertEqual(list(payload["facts"]), FACT_ORDER)
                self.assertEqual(
                    payload["unknowns"],
                    [name for name in FACT_ORDER if facts[name] == "unknown"],
                )
                self.assertEqual(
                    payload["escalation"],
                    None if expected_route == "direct" else {"entry_point": "xc-work"},
                )

    def test_each_yes_and_unknown_boundary_routes_to_managed(self) -> None:
        for name in FACT_ORDER:
            for value in ("yes", "unknown"):
                facts = {fact: "no" for fact in FACT_ORDER}
                facts[name] = value
                completed, payload = self.invoke_classifier(self.classifier_arguments(facts))
                with self.subTest(fact=name, value=value):
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(payload["route"], "managed")
                    self.assertEqual(payload["triggers"], [f"fact-{value}:{name}"])

    def test_each_omitted_flag_returns_stable_missing_input_error(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        complete_arguments = self.classifier_arguments(facts)
        for index, name in enumerate(FACT_ORDER):
            offset = index * 2
            arguments = complete_arguments[:offset] + complete_arguments[offset + 2 :]
            payload = self.assert_input_error(arguments, "classification_input_missing")
            with self.subTest(fact=name):
                self.assertEqual(payload["error"]["facts"], [name])

    def test_each_malformed_or_misspelled_flag_returns_invalid_input_error(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        complete_arguments = self.classifier_arguments(facts)
        for index, name in enumerate(FACT_ORDER):
            offset = index * 2
            invalid_value = complete_arguments.copy()
            invalid_value[offset + 1] = "maybe"
            payload = self.assert_input_error(invalid_value, "classification_input_invalid")
            with self.subTest(fact=name, case="invalid-value"):
                self.assertEqual(payload["error"]["facts"], [name])

            non_scalar = complete_arguments.copy()
            non_scalar[offset + 1] = '["no"]'
            payload = self.assert_input_error(non_scalar, "classification_input_invalid")
            with self.subTest(fact=name, case="non-scalar"):
                self.assertEqual(payload["error"]["facts"], [name])

            missing_value = complete_arguments.copy()
            del missing_value[offset + 1]
            payload = self.assert_input_error(missing_value, "classification_input_invalid")
            with self.subTest(fact=name, case="missing-value"):
                self.assertEqual(payload["error"]["facts"], [name])

            misspelled = complete_arguments.copy()
            misspelled[offset] = f"{misspelled[offset]}-typo"
            payload = self.assert_input_error(misspelled, "classification_input_invalid")
            with self.subTest(fact=name, case="misspelled-flag"):
                self.assertIn(misspelled[offset], payload["error"]["arguments"])

    def test_each_duplicate_and_contradictory_flag_has_distinct_error(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        complete_arguments = self.classifier_arguments(facts)
        for name in FACT_ORDER:
            option = f"--{name.replace('_', '-')}"
            duplicate = [*complete_arguments, option, "no"]
            payload = self.assert_input_error(duplicate, "classification_input_duplicate")
            with self.subTest(fact=name, case="duplicate"):
                self.assertEqual(payload["error"]["facts"], [name])

            contradictory = [*complete_arguments, option, "yes"]
            payload = self.assert_input_error(
                contradictory,
                "classification_input_contradictory",
            )
            with self.subTest(fact=name, case="contradictory"):
                self.assertEqual(payload["error"]["facts"], [name])

    def test_success_and_error_json_are_deterministic_and_ordered(self) -> None:
        facts = {
            "needs_persistence": "yes",
            "material_impact": "no",
            "difficult_rollback": "unknown",
            "crosses_sessions": "no",
            "multiple_actors": "yes",
            "audit_required": "unknown",
        }
        arguments = self.classifier_arguments(facts)
        first, first_payload = self.invoke_classifier(arguments)
        second, second_payload = self.invoke_classifier(arguments)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(
            list(first_payload),
            ["schema_version", "ok", "route", "facts", "triggers", "unknowns", "escalation"],
        )
        self.assertEqual(
            first_payload["triggers"],
            [
                "fact-yes:needs_persistence",
                "fact-unknown:difficult_rollback",
                "fact-yes:multiple_actors",
                "fact-unknown:audit_required",
            ],
        )
        error_arguments = arguments[:-2]
        first_error, first_error_payload = self.invoke_classifier(error_arguments)
        second_error, second_error_payload = self.invoke_classifier(error_arguments)
        self.assertEqual(first_error.returncode, 2)
        self.assertEqual(first_error.stdout, second_error.stdout)
        self.assertEqual(first_error_payload, second_error_payload)

    def test_unexpected_failure_returns_stable_nonzero_json(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        output = io.StringIO()
        with mock.patch.object(classifier, "classify", side_effect=RuntimeError("unstable detail")):
            with redirect_stdout(output):
                code = classifier.main(self.classifier_arguments(facts))
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(
            payload,
            {
                "schema_version": 1,
                "ok": False,
                "error": {"code": "classification_failed", "facts": []},
            },
        )

    def test_project_tightening_can_only_preserve_or_raise_governance(self) -> None:
        direct_facts = {name: "no" for name in FACT_ORDER}
        self.assertEqual(classifier.classify(direct_facts)["route"], "direct")
        for name in FACT_ORDER:
            for tightened_value in ("unknown", "yes"):
                tightened = dict(direct_facts)
                tightened[name] = tightened_value
                with self.subTest(fact=name, transition=f"no->{tightened_value}"):
                    self.assertEqual(classifier.classify(tightened)["route"], "managed")

            unknown = dict(direct_facts)
            unknown[name] = "unknown"
            raised = dict(unknown)
            raised[name] = "yes"
            with self.subTest(fact=name, transition="unknown->yes"):
                self.assertEqual(classifier.classify(unknown)["route"], "managed")
                self.assertEqual(classifier.classify(raised)["route"], "managed")

        contract = WORK_SKILL.read_text(encoding="utf-8")
        self.assertIn("A bridge may only tighten facts", contract)
        self.assertIn("It must not change `yes` or `unknown` to `no`", contract)

    def test_model_vendor_context_and_stack_do_not_change_the_route(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        facts["audit_required"] = "unknown"
        arguments = self.classifier_arguments(facts)
        baseline, baseline_payload = self.invoke_classifier(arguments)
        variants = (
            {
                "XC_MODEL_NAME": "small-model",
                "XC_MODEL_VENDOR": "vendor-a",
                "XC_CONTEXT_WINDOW": "4096",
                "XC_PROJECT_STACK": "python",
            },
            {
                "XC_MODEL_NAME": "frontier-model",
                "XC_MODEL_VENDOR": "vendor-b",
                "XC_CONTEXT_WINDOW": "1000000",
                "XC_PROJECT_STACK": "rust",
            },
        )
        for environment in variants:
            completed, payload = self.invoke_classifier(arguments, environment=environment)
            with self.subTest(environment=environment):
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, baseline.stdout)
                self.assertEqual(payload, baseline_payload)
                self.assertEqual(payload["route"], "managed")

    def test_public_skill_contract_fails_closed_and_preserves_managed_run(self) -> None:
        contract = WORK_SKILL.read_text(encoding="utf-8")
        self.assertIn("defaults to `run`", contract)
        self.assertIn("Omitting `operation` or specifying `operation=run`", contract)
        self.assertIn("It never invokes classification or downgrades to direct", contract)
        self.assertIn("The adapter fills omitted facts with `unknown`", contract)
        self.assertIn("malformed, duplicate, or contradictory public input", contract)
        self.assertIn('"classification_status":"escalated"', contract)
        self.assertIn('"reason_codes":["classification-unavailable"]', contract)
        self.assertIn("scripts/classify.py", contract)
        for name in FACT_ORDER:
            self.assertIn(f"`{name}` - `enum`", contract)

        scenarios = {
            scenario["id"]: scenario
            for scenario in self.scenario_payload["scenarios"]
        }
        self.assertEqual(scenarios["T1-M"]["expected_route"], "managed")
        self.assertEqual(scenarios["T1-M"]["governance_selection"], "explicit-run")

    def test_public_classifier_fills_missing_facts_and_preserves_all_no_direct(self) -> None:
        completed, payload = self.invoke_public_classifier([])
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["route"], "managed")
        self.assertEqual(payload["unknowns"], FACT_ORDER)

        facts = {name: "no" for name in FACT_ORDER}
        completed, payload = self.invoke_public_classifier(
            self.classifier_arguments(facts)
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["route"], "direct")
        self.assertEqual(payload["triggers"], ["all-facts-no"])

    def test_public_classifier_invalid_inputs_always_escalate_successfully(self) -> None:
        facts = {name: "no" for name in FACT_ORDER}
        valid = self.classifier_arguments(facts)
        cases = {
            "invalid": [*valid, "--unknown-fact", "no"],
            "malformed": [*valid[:-1]],
            "duplicate": [*valid, "--needs-persistence", "no"],
            "contradictory": [*valid, "--needs-persistence", "yes"],
        }
        expected_codes = {
            "invalid": "classification_input_invalid",
            "malformed": "classification_input_invalid",
            "duplicate": "classification_input_duplicate",
            "contradictory": "classification_input_contradictory",
        }
        for name, arguments in cases.items():
            completed, payload = self.invoke_public_classifier(arguments)
            with self.subTest(case=name):
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(payload["route"], "managed")
                self.assertEqual(payload["classification_status"], "escalated")
                self.assertEqual(
                    payload["reason_codes"],
                    ["classification-unavailable"],
                )
                self.assertEqual(
                    payload["diagnostic"]["input_error"],
                    expected_codes[name],
                )

    def test_public_classifier_rejects_each_mismatched_fact_end_to_end(self) -> None:
        for name in FACT_ORDER:
            requested = {fact: "no" for fact in FACT_ORDER}
            requested[name] = "yes"
            returned = {fact: "no" for fact in FACT_ORDER}
            completed, payload = self.invoke_public_with_low_level_payload(
                self.classifier_arguments(requested),
                self.public_success_payload(returned),
            )
            with self.subTest(fact=name):
                self.assert_public_escalation(
                    completed,
                    payload,
                    "classification_output_facts_mismatch",
                )

    def test_public_classifier_rejects_each_unknown_downgrade_end_to_end(self) -> None:
        returned = {fact: "no" for fact in FACT_ORDER}
        forged_direct = self.public_success_payload(returned)
        for name in FACT_ORDER:
            requested = dict(returned)
            requested[name] = "unknown"
            explicit_arguments = self.classifier_arguments(requested)
            omitted_arguments = self.classifier_arguments(returned)
            option_index = omitted_arguments.index(f"--{name.replace('_', '-')}")
            del omitted_arguments[option_index : option_index + 2]

            for input_mode, arguments in (
                ("explicit", explicit_arguments),
                ("omitted-default", omitted_arguments),
            ):
                completed, payload = self.invoke_public_with_low_level_payload(
                    arguments,
                    forged_direct,
                )
                with self.subTest(fact=name, input_mode=input_mode):
                    self.assert_public_escalation(
                        completed,
                        payload,
                        "classification_output_facts_mismatch",
                    )

    def test_public_classifier_rejects_forged_material_impact_all_no(self) -> None:
        requested = {name: "no" for name in FACT_ORDER}
        requested["material_impact"] = "yes"
        forged = {name: "no" for name in FACT_ORDER}
        completed, payload = self.invoke_public_with_low_level_payload(
            self.classifier_arguments(requested),
            self.public_success_payload(forged),
        )
        self.assert_public_escalation(
            completed,
            payload,
            "classification_output_facts_mismatch",
        )

    def test_public_classifier_rejects_malformed_fact_mappings_end_to_end(self) -> None:
        requested = {name: "no" for name in FACT_ORDER}
        cases: dict[str, dict[str, object]] = {}
        missing = self.public_success_payload(requested)
        missing["facts"] = {
            name: value
            for name, value in requested.items()
            if name != "audit_required"
        }
        cases["missing-key"] = missing
        extra = self.public_success_payload(requested)
        extra["facts"] = {**requested, "forged_fact": "no"}
        cases["extra-key"] = extra
        invalid = self.public_success_payload(requested)
        invalid["facts"] = {**requested, "audit_required": ["no"]}
        cases["invalid-value"] = invalid

        for name, returned in cases.items():
            completed, payload = self.invoke_public_with_low_level_payload(
                self.classifier_arguments(requested),
                returned,
            )
            with self.subTest(case=name):
                self.assert_public_escalation(
                    completed,
                    payload,
                    "classification_output_invalid",
                )

    def test_public_classifier_rejects_route_trigger_and_unknown_inconsistency(self) -> None:
        managed = {name: "no" for name in FACT_ORDER}
        managed["material_impact"] = "yes"
        unknown = {name: "no" for name in FACT_ORDER}
        unknown["audit_required"] = "unknown"
        cases: list[tuple[str, dict[str, str], dict[str, object], str]] = []

        wrong_route = self.public_success_payload(managed)
        wrong_route["route"] = "direct"
        cases.append(("route", managed, wrong_route, "classification_output_route"))
        wrong_trigger = self.public_success_payload(managed)
        wrong_trigger["triggers"] = ["all-facts-no"]
        cases.append(("trigger", managed, wrong_trigger, "classification_output_invalid"))
        wrong_unknowns = self.public_success_payload(unknown)
        wrong_unknowns["unknowns"] = []
        cases.append(("unknowns", unknown, wrong_unknowns, "classification_output_invalid"))

        for name, requested, returned, expected_code in cases:
            completed, payload = self.invoke_public_with_low_level_payload(
                self.classifier_arguments(requested),
                returned,
            )
            with self.subTest(case=name):
                self.assert_public_escalation(completed, payload, expected_code)

    def test_public_classifier_accepts_matching_direct_and_managed_results(self) -> None:
        direct = {name: "no" for name in FACT_ORDER}
        managed = {name: "no" for name in FACT_ORDER}
        managed["crosses_sessions"] = "unknown"
        for name, requested in (("direct", direct), ("managed", managed)):
            returned = self.public_success_payload(requested)
            returned["facts"] = dict(reversed(list(requested.items())))
            completed, payload = self.invoke_public_with_low_level_payload(
                self.classifier_arguments(requested),
                returned,
            )
            with self.subTest(case=name):
                self.assertEqual(completed.returncode, 0, completed.stdout)
                self.assertEqual(payload["route"], name)
                self.assertNotIn("classification_status", payload)
                self.assertEqual(payload["facts"], requested)

    def test_public_classifier_low_level_failure_modes_escalate_end_to_end(self) -> None:
        fake_scripts = {
            "low-level-nonzero": (
                'import json\nprint(json.dumps({"schema_version":1,"ok":False,'
                '"error":{"code":"classification_failed"}}))\nraise SystemExit(7)\n',
                "classification_failed",
            ),
            "malformed-json": ('print("not-json")\n', "classification_output_malformed"),
            "unknown-schema": (
                'import json\nprint(json.dumps({"schema_version":2,"ok":True,'
                '"route":"direct"}))\n',
                "classification_output_schema",
            ),
            "unknown-route": (
                'import json\nprint(json.dumps({"schema_version":1,"ok":True,'
                '"route":"surprise"}))\n',
                "classification_output_route",
            ),
            "timeout": (
                "import time\ntime.sleep(6)\n",
                "classification_timeout",
            ),
        }
        all_no = self.classifier_arguments({name: "no" for name in FACT_ORDER})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = root / "classify.py"
            shutil.copyfile(PUBLIC_CLASSIFIER, adapter)

            completed, payload = self.invoke_public_classifier(
                all_no,
                executable=adapter,
            )
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(
                payload["diagnostic"]["input_error"],
                "classification_executable_missing",
            )

            low_level = root / "classify_governance.py"
            for name, (source, expected_code) in fake_scripts.items():
                low_level.write_text(source, encoding="utf-8")
                completed, payload = self.invoke_public_classifier(
                    all_no,
                    executable=adapter,
                )
                with self.subTest(case=name):
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(payload["route"], "managed")
                    self.assertEqual(payload["classification_status"], "escalated")
                    self.assertEqual(
                        payload["diagnostic"]["input_error"],
                        expected_code,
                    )

    def test_workflow_evolution_uses_only_the_public_xc_work_boundary(self) -> None:
        contract = WORKFLOW_EVOLUTION_SKILL.read_text(encoding="utf-8")
        self.assertIn("public Skill boundary with `operation=classify`", contract)
        self.assertIn("public `xc-work operation=run`", contract)
        self.assertIn("do not create a work order", contract)
        self.assertIn("depends only on the documented `xc-work` Skill name and public parameters", contract)
        self.assertNotIn("classify_governance.py", contract)

    def test_generic_governance_contract_is_model_and_vendor_independent(self) -> None:
        contract = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("### Proportional Governance", contract)
        self.assertIn("independent of model name, model vendor, context-window size", contract)
        self.assertIn("Missing, unavailable, malformed, or conflicting evidence", contract)


if __name__ == "__main__":
    unittest.main()
