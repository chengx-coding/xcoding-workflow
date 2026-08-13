from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STALENESS_SCRIPT = (
    REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "verification_staleness.py"
)
TIMESTAMP = "2026-08-14T10:00:00+00:00"


def run_staleness(*arguments: str) -> tuple[int, dict[str, object], str]:
    completed = subprocess.run(
        [sys.executable, str(STALENESS_SCRIPT), *arguments],
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


class VerificationStalenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xc-verification-staleness-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = self.root / "staleness.json"
        self.file_a = self.root / "a.txt"
        self.file_b = self.root / "b.txt"
        self.file_a.write_text("alpha", encoding="utf-8")
        self.file_b.write_text("beta", encoding="utf-8")

    def files_arg(self) -> str:
        return f"{self.file_a},{self.file_b}"

    def mark(self, key: str = "milestone-1", **overrides: object) -> tuple:
        arguments = [
            "mark",
            "--store",
            str(overrides.get("store", self.store)),
            "--key",
            key,
            "--verified-at",
            str(overrides.get("verified_at", TIMESTAMP)),
            "--files",
            str(overrides.get("files", self.files_arg())),
        ]
        if overrides.get("replace"):
            arguments.append("--replace")
        return run_staleness(*arguments)

    def query(self, keys: str | None = None) -> tuple:
        arguments = ["query", "--store", str(self.store)]
        if keys is not None:
            arguments += ["--keys", keys]
        return run_staleness(*arguments)

    def remove(self, key: str) -> tuple:
        return run_staleness("remove", "--store", str(self.store), "--key", key)

    def test_mark_then_query_reports_current(self) -> None:
        code, payload, _ = self.mark()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "stored")
        self.assertEqual(payload["files"], sorted(self.files_arg().split(",")))
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stale"], [])
        self.assertEqual(payload["unknown"], [])
        self.assertEqual(payload["current"], [{"key": "milestone-1", "verified_at": TIMESTAMP}])

    def test_staleness_on_content_change(self) -> None:
        self.mark()
        self.file_a.write_text("changed-alpha", encoding="utf-8")
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["stale"],
            [{"key": "milestone-1", "files": [{"path": str(self.file_a), "status": "changed"}]}],
        )
        self.assertEqual(payload["current"], [])
        self.assertEqual(payload["unknown"], [])

    def test_staleness_on_file_deletion(self) -> None:
        self.mark()
        self.file_b.unlink()
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertEqual(
            payload["stale"],
            [{"key": "milestone-1", "files": [{"path": str(self.file_b), "status": "missing"}]}],
        )

    def test_remove_explicit_retire(self) -> None:
        self.mark()
        code, payload, _ = self.remove("milestone-1")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "removed")
        code, payload, _ = self.query()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stale"], [])
        self.assertEqual(payload["current"], [])

    def test_duplicate_key_refused_without_replace(self) -> None:
        self.mark()
        code, payload, _ = self.mark()
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_key_duplicate")
        code, payload, _ = self.query()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["current"]), 1)

    def test_duplicate_key_replaced_with_replace(self) -> None:
        self.mark()
        code, payload, _ = self.mark(replace=True, verified_at="2026-08-15T09:00:00+00:00")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "replaced")
        code, payload, _ = self.query()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["current"], [{"key": "milestone-1", "verified_at": "2026-08-15T09:00:00+00:00"}])

    def test_deterministic_store_and_output(self) -> None:
        self.mark()
        first_store = self.store.read_bytes()
        code, payload_a, stdout_a = self.query()
        code, payload_b, stdout_b = self.query()
        self.assertEqual(payload_a, payload_b)
        self.assertEqual(stdout_a, stdout_b)
        self.assertEqual(code, 0)
        other_root = self.root / "other"
        other_root.mkdir()
        other_store = other_root / "staleness.json"
        self.mark(store=other_store)
        self.assertEqual(other_store.read_bytes(), first_store)

    def test_invalid_verified_at_rejected(self) -> None:
        code, payload, _ = self.mark(verified_at="not-a-timestamp")
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_input_invalid")
        self.assertFalse(self.store.exists())

    def test_missing_file_at_mark_rejected(self) -> None:
        missing = self.root / "missing.txt"
        code, payload, _ = self.mark(files=f"{self.file_a},{missing}")
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_file_unavailable")

    def test_empty_and_duplicate_files_rejected(self) -> None:
        for files in ("", f"{self.file_a},{self.file_a}"):
            with self.subTest(files=files):
                code, payload, _ = self.mark(files=files)
                self.assertEqual(code, 0)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "staleness_input_invalid")

    def test_remove_missing_key_reports_stable_code(self) -> None:
        self.mark()
        code, payload, _ = self.remove("never-marked")
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_key_missing")
        code, payload, _ = self.query()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["current"]), 1)

    def test_query_keys_selects_unknown_and_current(self) -> None:
        self.mark(key="milestone-1")
        self.mark(key="milestone-2")
        code, payload, _ = self.query(keys="milestone-2,never-marked")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["unknown"], [{"key": "never-marked"}])
        self.assertEqual(payload["current"], [{"key": "milestone-2", "verified_at": TIMESTAMP}])
        self.assertEqual(payload["stale"], [])

    def test_multi_file_detail_lists_both_problems_sorted(self) -> None:
        self.mark()
        self.file_a.write_text("changed", encoding="utf-8")
        self.file_b.unlink()
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertEqual(
            payload["stale"],
            [
                {
                    "key": "milestone-1",
                    "files": [
                        {"path": str(self.file_a), "status": "changed"},
                        {"path": str(self.file_b), "status": "missing"},
                    ],
                }
            ],
        )

    def test_corrupt_store_rejected(self) -> None:
        self.store.write_text('{"entries": "not a dict"}', encoding="utf-8")
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_store_corrupt")

    def test_tampered_entry_hash_rejected(self) -> None:
        self.mark()
        store_bytes = self.store.read_text(encoding="utf-8")
        self.store.write_text(store_bytes.replace(TIMESTAMP, "2026-01-01T00:00:00+00:00"), encoding="utf-8")
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_store_corrupt")

    def test_unknown_option_rejected(self) -> None:
        code, payload, _ = run_staleness("query", "--store", str(self.store), "--bogus", "x")
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "staleness_input_invalid")

    def test_query_missing_store_reports_empty(self) -> None:
        code, payload, _ = self.query()
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stale"], [])
        self.assertEqual(payload["current"], [])
        self.assertEqual(payload["unknown"], [])


if __name__ == "__main__":
    unittest.main()
