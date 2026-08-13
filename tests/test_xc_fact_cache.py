from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FACT_CACHE = REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "fact_cache.py"
FACT_NAMES = [
    "needs_persistence",
    "material_impact",
    "difficult_rollback",
    "crosses_sessions",
    "multiple_actors",
    "audit_required",
]
CONFIRMED_FACTS = {
    "needs_persistence": "yes",
    "material_impact": "yes",
    "difficult_rollback": "yes",
    "crosses_sessions": "no",
    "multiple_actors": "yes",
    "audit_required": "yes",
}
ALL_NO_FACTS = {name: "no" for name in FACT_NAMES}
BRIDGE_A = "a" * 64
BRIDGE_B = "b" * 64
SOURCES_A = '["task-request","bridge-read"]'
SOURCES_B = '["task-request","bridge-read","prior-work-order"]'
FLAGS_A = '["--needs-persistence","--material-impact","--difficult-rollback"]'
FLAGS_B = '["--audit-required"]'


def facts_json(facts: dict[str, str]) -> str:
    return json.dumps(facts, separators=(",", ":"))


def run_cache(*arguments: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(FACT_CACHE), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    self_ref = completed
    assert isinstance(payload, dict), self_ref.stderr or self_ref.stdout
    return completed.returncode, payload


def evidence(bridge: str, sources: str, flags: str) -> list[str]:
    return [
        "--bridge-sha256",
        bridge,
        "--fact-sources",
        sources,
        "--requested-flags",
        flags,
    ]


class FactCacheUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xc-fact-cache-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.session_path = self.root / "session-facts.json"
        self.store_path = self.root / "runtime-facts.json"

    def store(self, carrier: str, *, facts: dict[str, str], bridge: str = BRIDGE_A,
              sources: str = SOURCES_A, flags: str = FLAGS_A,
              path: Path | None = None) -> tuple[int, dict[str, object]]:
        return run_cache(
            "store",
            "--carrier",
            carrier,
            "--path",
            str(path if path is not None else self.cache_path(carrier)),
            *evidence(bridge, sources, flags),
            "--facts",
            facts_json(facts),
        )

    def cache_path(self, carrier: str) -> Path:
        return self.session_path if carrier == "session-file" else self.store_path

    def get(self, carrier: str, *, bridge: str = BRIDGE_A, sources: str = SOURCES_A,
            flags: str = FLAGS_A, path: Path | None = None) -> tuple[int, dict[str, object]]:
        return run_cache(
            "get",
            "--carrier",
            carrier,
            "--path",
            str(path if path is not None else self.cache_path(carrier)),
            *evidence(bridge, sources, flags),
        )

    def invalidate(self, carrier: str, *, bridge: str = BRIDGE_A, sources: str = SOURCES_A,
                   flags: str = FLAGS_A) -> tuple[int, dict[str, object]]:
        return run_cache(
            "invalidate",
            "--carrier",
            carrier,
            "--path",
            str(self.cache_path(carrier)),
            *evidence(bridge, sources, flags),
        )

    def test_unknown_fact_is_never_cached(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                unknown = dict(ALL_NO_FACTS, needs_persistence="unknown")
                code, payload = self.store(carrier, facts=unknown)
                self.assertEqual(code, 2)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "store_facts_unknown")
                self.assertFalse(self.cache_path(carrier).exists())
                code, payload = self.get(carrier)
                self.assertEqual(code, 0)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])

    def test_confirmed_facts_round_trip_identically(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                code, payload = self.store(carrier, facts=CONFIRMED_FACTS)
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["facts"], CONFIRMED_FACTS)
                code, payload = self.get(carrier)
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
                self.assertTrue(payload["hit"])
                self.assertEqual(payload["facts"], CONFIRMED_FACTS)
                self.assertEqual(set(payload["facts"]), set(FACT_NAMES))
                self.assertTrue(
                    all(value in {"yes", "no"} for value in payload["facts"].values())
                )

    def test_fingerprint_mismatch_is_a_miss(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                code, payload = self.get(carrier, bridge=BRIDGE_B)
                self.assertEqual(code, 0)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])
                self.assertEqual(payload["reason"], "no_entry")
                code, payload = self.get(carrier, sources=SOURCES_B)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])
                code, payload = self.get(carrier, flags=FLAGS_B)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])

    def test_invalidation_removes_entry(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                code, payload = self.invalidate(carrier)
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
                self.assertTrue(payload["removed"])
                code, payload = self.get(carrier)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])
                self.assertEqual(payload["reason"], "no_entry")
                code, payload = self.invalidate(carrier)
                self.assertEqual(code, 0)
                self.assertFalse(payload["removed"])

    def test_corrupted_store_is_a_miss(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                path = self.cache_path(carrier)
                path.write_text("{not valid json", encoding="utf-8")
                code, payload = self.get(carrier)
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])
                self.assertEqual(payload["reason"], "store_corrupt")

    def test_tampered_entry_with_unknown_value_is_a_miss(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                path = self.cache_path(carrier)
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["entries"][0]["facts"]["needs_persistence"] = "unknown"
                path.write_text(
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    encoding="utf-8",
                )
                code, payload = self.get(carrier)
                self.assertEqual(code, 0)
                self.assertFalse(payload["hit"])
                self.assertIsNone(payload["facts"])
                self.assertEqual(payload["reason"], "store_corrupt")

    def test_corrupted_store_blocks_store_and_is_removable_by_invalidate(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                path = self.cache_path(carrier)
                path.write_text("{broken", encoding="utf-8")
                code, payload = self.store(carrier, facts=ALL_NO_FACTS)
                self.assertEqual(code, 2)
                self.assertEqual(payload["error"]["code"], "cache_store_corrupt")
                code, payload = self.invalidate(carrier)
                self.assertEqual(code, 0)
                self.assertTrue(payload["removed"])
                self.assertFalse(path.exists())
                code, payload = self.get(carrier)
                self.assertFalse(payload["hit"])
                self.assertEqual(payload["reason"], "store_missing")

    def test_carriers_behave_identically(self) -> None:
        transcripts: dict[str, list[dict[str, object]]] = {}
        for carrier in ("session-file", "store"):
            operations = [
                self.get(carrier)[1],
                self.store(carrier, facts=CONFIRMED_FACTS)[1],
                self.get(carrier)[1],
                self.store(carrier, facts=CONFIRMED_FACTS)[1],
                self.get(carrier, bridge=BRIDGE_B)[1],
                self.invalidate(carrier)[1],
                self.get(carrier)[1],
            ]
            transcripts[carrier] = operations
        session_transcript = transcripts["session-file"]
        store_transcript = transcripts["store"]
        for session_op, store_op in zip(session_transcript, store_transcript):
            comparable_session = {
                key: value for key, value in session_op.items() if key != "carrier"
            }
            comparable_store = {
                key: value for key, value in store_op.items() if key != "carrier"
            }
            self.assertEqual(comparable_session, comparable_store)
            if "carrier" in session_op:
                self.assertEqual(session_op["carrier"], "session-file")
            if "carrier" in store_op:
                self.assertEqual(store_op["carrier"], "store")

    def test_store_metadata_differs_between_carriers(self) -> None:
        self.store("session-file", facts=CONFIRMED_FACTS)
        self.store("store", facts=CONFIRMED_FACTS)
        session_payload = json.loads(self.session_path.read_text(encoding="utf-8"))
        store_payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertNotIn("carrier", session_payload)
        self.assertEqual(store_payload["carrier"], "store")
        self.assertEqual(session_payload["entries"], store_payload["entries"])

    def test_carrier_mismatch_is_a_miss(self) -> None:
        self.store("store", facts=CONFIRMED_FACTS)
        code, payload = run_cache(
            "get",
            "--carrier",
            "session-file",
            "--path",
            str(self.store_path),
            *evidence(BRIDGE_A, SOURCES_A, FLAGS_A),
        )
        self.assertEqual(code, 0)
        self.assertFalse(payload["hit"])
        self.assertIsNone(payload["facts"])
        self.assertEqual(payload["reason"], "store_corrupt")

    def test_conflicting_reconfirmation_is_rejected(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                code, payload = self.store(carrier, facts=ALL_NO_FACTS)
                self.assertEqual(code, 2)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "cache_store_conflict")
                code, payload = self.get(carrier)
                self.assertTrue(payload["hit"])
                self.assertEqual(payload["facts"], CONFIRMED_FACTS)

    def test_idempotent_reconfirmation_is_accepted(self) -> None:
        for carrier in ("session-file", "store"):
            with self.subTest(carrier=carrier):
                self.store(carrier, facts=CONFIRMED_FACTS)
                code, payload = self.store(carrier, facts=CONFIRMED_FACTS)
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
                self.assertFalse(payload["changed"])

    def test_strict_input_validation(self) -> None:
        cases: dict[str, tuple[str, ...]] = {
            "invalid_carrier": (
                "get",
                "--carrier",
                "session",
                "--path",
                str(self.store_path),
                *evidence(BRIDGE_A, SOURCES_A, FLAGS_A),
            ),
            "invalid_bridge_sha256": (
                "get",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
                "--bridge-sha256",
                "not-a-sha256",
                "--fact-sources",
                SOURCES_A,
                "--requested-flags",
                FLAGS_A,
            ),
            "malformed_fact_sources": (
                "get",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
                "--bridge-sha256",
                BRIDGE_A,
                "--fact-sources",
                "{not-json",
                "--requested-flags",
                FLAGS_A,
            ),
            "duplicate_fact_sources": (
                "get",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
                "--bridge-sha256",
                BRIDGE_A,
                "--fact-sources",
                '["task-request","task-request"]',
                "--requested-flags",
                FLAGS_A,
            ),
            "incomplete_facts": (
                "store",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
                *evidence(BRIDGE_A, SOURCES_A, FLAGS_A),
                "--facts",
                facts_json({"needs_persistence": "no"}),
            ),
            "invalid_fact_value": (
                "store",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
                *evidence(BRIDGE_A, SOURCES_A, FLAGS_A),
                "--facts",
                facts_json(dict(ALL_NO_FACTS, needs_persistence="maybe")),
            ),
            "missing_path": (
                "get",
                "--carrier",
                "store",
                *evidence(BRIDGE_A, SOURCES_A, FLAGS_A),
            ),
            "unknown_subcommand": (
                "fetch",
                "--carrier",
                "store",
                "--path",
                str(self.store_path),
            ),
        }
        expected_error_codes = {
            "incomplete_facts": "cache_facts_invalid",
            "invalid_fact_value": "cache_facts_invalid",
        }
        for case, arguments in cases.items():
            with self.subTest(case=case):
                code, payload = run_cache(*arguments)
                self.assertEqual(code, 2, payload)
                self.assertFalse(payload["ok"])
                self.assertEqual(
                    payload["error"]["code"],
                    expected_error_codes.get(case, "cache_input_invalid"),
                )

    def test_unknown_fact_refusal_is_not_an_input_error(self) -> None:
        code, payload = self.store(
            "store", facts=dict(ALL_NO_FACTS, audit_required="unknown")
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"]["code"], "store_facts_unknown")

    def test_second_entry_under_new_evidence_coexists(self) -> None:
        self.store("store", facts=CONFIRMED_FACTS)
        code, payload = self.store("store", facts=ALL_NO_FACTS, bridge=BRIDGE_B)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        code, payload = self.get("store")
        self.assertTrue(payload["hit"])
        self.assertEqual(payload["facts"], CONFIRMED_FACTS)
        code, payload = self.get("store", bridge=BRIDGE_B)
        self.assertTrue(payload["hit"])
        self.assertEqual(payload["facts"], ALL_NO_FACTS)


if __name__ == "__main__":
    unittest.main()
