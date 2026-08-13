from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SCRIPT = (
    REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "decision_registry.py"
)
ENTRY_KEYS = (
    "id",
    "work_order_id",
    "timestamp",
    "decision",
    "rationale",
    "evidence_refs",
    "actor",
)


def run_registry(*arguments: str) -> tuple[int, dict[str, object], str]:
    completed = subprocess.run(
        [sys.executable, str(REGISTRY_SCRIPT), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict), completed.stderr or completed.stdout
    return completed.returncode, payload, completed.stdout


class DecisionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xc-decision-registry-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.registry = self.root / "decisions.jsonl"

    def record(self, decision_id: str = "dec-1", **overrides: object):
        arguments = [
            "record",
            "--path",
            str(overrides.get("path", self.registry)),
            "--work-order-id",
            str(overrides.get("work_order_id", "wo-1")),
            "--decision-id",
            decision_id,
            "--decision",
            str(overrides.get("decision", "Use JSONL registry")),
            "--rationale",
            str(overrides.get("rationale", "Append-only replay")),
            "--evidence-refs",
            overrides.get("evidence_refs", '["e1"]'),
            "--actor",
            str(overrides.get("actor", "planner")),
        ]
        timestamp = overrides.get("timestamp")
        if timestamp is not None:
            arguments += ["--timestamp", str(timestamp)]
        return run_registry(*arguments)

    def list_registry(self, path: Path | None = None):
        return run_registry("list", "--path", str(path or self.registry))

    def get(self, decision_id: str, path: Path | None = None):
        return run_registry(
            "get", "--path", str(path or self.registry), "--decision-id", decision_id
        )

    def test_record_appends_one_strict_jsonl_line(self) -> None:
        code, payload, _ = self.record(timestamp="2026-08-14T10:00:00+00:00")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "stored")
        lines = self.registry.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(set(entry), set(ENTRY_KEYS))
        self.assertEqual(entry["id"], "dec-1")
        self.assertEqual(entry["work_order_id"], "wo-1")
        self.assertEqual(entry["evidence_refs"], ["e1"])

    def test_append_never_rewrites_existing_lines(self) -> None:
        self.record("dec-1", timestamp="2026-08-14T10:00:00+00:00")
        first = self.registry.read_bytes()
        self.record("dec-2", timestamp="2026-08-14T11:00:00+00:00")
        final = self.registry.read_bytes()
        self.assertTrue(final.startswith(first))
        self.assertEqual(len(final.splitlines()), 2)

    def test_no_update_or_delete_subcommand_exists(self) -> None:
        for command in ("update", "delete"):
            with self.subTest(command=command):
                code, payload, _ = run_registry(
                    command,
                    "--path",
                    str(self.registry),
                    "--decision-id",
                    "dec-1",
                    "--decision",
                    "changed",
                )
                self.assertEqual(code, 2)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "decision_input_invalid")
        self.assertFalse(self.registry.exists())

    def test_duplicate_id_rejected_with_stable_error(self) -> None:
        self.record("dec-1", timestamp="2026-08-14T10:00:00+00:00")
        before = self.registry.read_bytes()
        code, payload, _ = self.record(
            "dec-1",
            decision="Contradicting rewrite",
            timestamp="2026-08-14T12:00:00+00:00",
        )
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "decision_duplicate")
        self.assertEqual(self.registry.read_bytes(), before)

    def test_list_replays_sorted_by_timestamp_then_id(self) -> None:
        self.record("dec-b", timestamp="2026-08-14T11:00:00+00:00")
        self.record("dec-a", timestamp="2026-08-14T10:00:00+00:00")
        self.record("dec-c", timestamp="2026-08-14T10:00:00+00:00")
        code, payload, _ = self.list_registry()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        decisions = payload["decisions"]
        assert isinstance(decisions, list)
        self.assertEqual([entry["id"] for entry in decisions], ["dec-a", "dec-c", "dec-b"])

    def test_list_output_is_deterministic(self) -> None:
        self.record("dec-b", timestamp="2026-08-14T11:00:00+00:00")
        self.record("dec-a", timestamp="2026-08-14T10:00:00+00:00")
        _, _, first = self.list_registry()
        _, _, second = self.list_registry()
        self.assertEqual(first, second)
        parsed = json.loads(first)
        self.assertEqual(list(parsed), sorted(parsed))

    def test_list_and_get_are_read_only(self) -> None:
        self.record("dec-1", timestamp="2026-08-14T10:00:00+00:00")
        before = self.registry.read_bytes()
        self.list_registry()
        self.assertEqual(self.registry.read_bytes(), before)
        self.get("dec-1")
        self.assertEqual(self.registry.read_bytes(), before)

    def test_get_returns_entry_and_missing_reason(self) -> None:
        self.record("dec-1", timestamp="2026-08-14T10:00:00+00:00")
        code, payload, _ = self.get("dec-1")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reason"], "found")
        decision = payload["decision"]
        assert isinstance(decision, dict)
        self.assertEqual(decision["decision"], "Use JSONL registry")
        code, payload, _ = self.get("dec-missing")
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["decision"])
        self.assertEqual(payload["reason"], "no_entry")

    def test_invalid_input_fails_closed(self) -> None:
        cases = [
            ["mutate", "--path", str(self.registry)],
            ["record", "--path", str(self.registry), "--bogus", "x"],
            [
                "record",
                "--path",
                str(self.registry),
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "x",
                "--rationale",
                "y",
                "--evidence-refs",
                '["e1"]',
            ],
            [
                "record",
                "--path",
                str(self.registry),
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "x",
                "--rationale",
                "y",
                "--evidence-refs",
                "not-json",
                "--actor",
                "planner",
            ],
            [
                "record",
                "--path",
                str(self.registry),
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "x",
                "--rationale",
                "y",
                "--evidence-refs",
                '["e1","e1"]',
                "--actor",
                "planner",
            ],
            [
                "record",
                "--path",
                str(self.registry),
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "   ",
                "--rationale",
                "y",
                "--evidence-refs",
                '["e1"]',
                "--actor",
                "planner",
            ],
            [
                "record",
                "--path",
                str(self.registry),
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "x",
                "--rationale",
                "y",
                "--evidence-refs",
                '["e1"]',
                "--actor",
                "planner",
                "--timestamp",
                "2026-08-14T10:00:00+02:00",
            ],
            [
                "record",
                "--path",
                "  ",
                "--work-order-id",
                "wo-1",
                "--decision-id",
                "dec-1",
                "--decision",
                "x",
                "--rationale",
                "y",
                "--evidence-refs",
                '["e1"]',
                "--actor",
                "planner",
            ],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                code, payload, _ = run_registry(*arguments)
                self.assertEqual(code, 2)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "decision_input_invalid")
        self.assertFalse(self.registry.exists())

    def test_default_timestamp_is_utc(self) -> None:
        code, payload, _ = self.record()
        self.assertEqual(code, 0)
        lines = self.registry.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        parsed = datetime.fromisoformat(entry["timestamp"])
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_corrupt_registry_fails_closed(self) -> None:
        corrupt_lines = [
            "not-json\n",
            '{"id": "dec-1", "extra": true}\n',
        ]
        for content in corrupt_lines:
            with self.subTest(content=content):
                path = self.root / f"corrupt-{abs(hash(content))}.jsonl"
                path.write_text(content, encoding="utf-8")
                for operation in (
                    lambda: self.list_registry(path),
                    lambda: self.get("dec-1", path),
                    lambda: self.record(
                        "dec-2", path=path, timestamp="2026-08-14T10:00:00+00:00"
                    ),
                ):
                    code, payload, _ = operation()
                    self.assertEqual(code, 2)
                    self.assertFalse(payload["ok"])
                    self.assertEqual(payload["error"]["code"], "decision_store_corrupt")

    def test_duplicate_ids_inside_file_fail_closed(self) -> None:
        entry = {
            "id": "dec-1",
            "work_order_id": "wo-1",
            "timestamp": "2026-08-14T10:00:00+00:00",
            "decision": "x",
            "rationale": "y",
            "evidence_refs": ["e1"],
            "actor": "planner",
        }
        self.registry.write_text(
            json.dumps(entry) + "\n" + json.dumps(entry) + "\n", encoding="utf-8"
        )
        code, payload, _ = self.list_registry()
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "decision_store_corrupt")

    def test_missing_store_replays_empty(self) -> None:
        code, payload, _ = self.list_registry()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decisions"], [])
        self.assertEqual(payload["reason"], "store_missing")
        code, payload, _ = self.get("dec-1")
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["decision"])
        self.assertEqual(payload["reason"], "store_missing")

    def test_read_unavailability_reports_store_unavailable_not_corrupt(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "xc_decision_registry", REGISTRY_SCRIPT
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class UnreadableStore:
            def read_text(self, encoding=None):
                raise OSError("store unavailable")

        with self.assertRaises(OSError):
            module.read_registry(UnreadableStore())  # type: ignore[arg-type]

    def test_record_into_directory_reports_store_unavailable(self) -> None:
        directory = self.root / "store-as-directory"
        directory.mkdir()
        code, payload, _ = self.record("dec-1", path=directory)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "decision_store_unavailable")


if __name__ == "__main__":
    unittest.main()
