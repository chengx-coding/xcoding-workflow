from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCANNER = REPOSITORY_ROOT / "skills" / "xc-conventions" / "scripts" / "scan_conventions.py"


def run_scanner(root: Path, *args: str) -> tuple[int, dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(SCANNER), "--project-root", str(root), *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, json.loads(proc.stdout)


def write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class ConventionScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _paths(self, payload: dict[str, object], tier: str) -> set[str]:
        return {str(item["path"]) for item in payload[tier]}  # type: ignore[index]

    def test_enumerates_declared_and_configured_families(self) -> None:
        write(self.root / "AGENTS.md")
        write(self.root / ".cursor" / "rules" / "style.mdc")
        write(self.root / ".github" / "workflows" / "ci.yml")
        write(self.root / ".editorconfig")
        code, payload = run_scanner(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "scanned")
        self.assertIn("AGENTS.md", self._paths(payload, "c1"))
        self.assertIn(".cursor/rules/style.mdc", self._paths(payload, "c1"))
        self.assertIn(".editorconfig", self._paths(payload, "c2"))
        self.assertIn(".github/workflows/ci.yml", self._paths(payload, "c2"))

    def test_nearest_neighbor_distance_orders_candidates(self) -> None:
        write(self.root / "AGENTS.md")
        nested = self.root / "pkg" / "deep"
        write(nested / "AGENTS.md")
        _, payload = run_scanner(self.root, "--target", "pkg/deep/module.py")
        c1 = {item["path"]: item for item in payload["c1"]}
        self.assertLess(c1["pkg/deep/AGENTS.md"]["distance"], c1["AGENTS.md"]["distance"])

    def test_gitignore_excludes_instruction_files_outside_git(self) -> None:
        write(self.root / "AGENTS.md")
        write(self.root / ".gitignore", "AGENTS.md\n")
        # No .git directory: the matcher falls back to .gitignore patterns.
        _, payload = run_scanner(self.root)
        self.assertNotIn("AGENTS.md", self._paths(payload, "c1"))

    def test_deterministic_sorted_output(self) -> None:
        write(self.root / "AGENTS.md")
        write(self.root / "CONTRIBUTING.md")
        write(self.root / "pkg" / "AGENTS.md")
        _, first = run_scanner(self.root)
        _, second = run_scanner(self.root)
        self.assertEqual(first, second)
        self.assertEqual(
            [item["path"] for item in first["c1"]],
            sorted(item["path"] for item in first["c1"]),
        )

    def test_budget_truncation_is_reported_not_silent(self) -> None:
        write(self.root / "AGENTS.md")
        write(self.root / "CONTRIBUTING.md")
        write(self.root / ".cursorrules")
        _, payload = run_scanner(self.root, "--max-files", "1", "--deadline-ms", "100000")
        self.assertTrue(payload["truncated"])

    def test_unreadable_bridge_location_fails_closed(self) -> None:
        code, payload = run_scanner(self.root, "--bridge-location", "docs/never.md")
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "scan-unavailable")
        self.assertIn("unreadable_bridge_locations", payload)

    def test_readable_bridge_location_surfaced_as_c1(self) -> None:
        write(self.root / "docs" / "rules.md")
        code, payload = run_scanner(self.root, "--bridge-location", "docs/rules.md")
        self.assertEqual(code, 0)
        self.assertIn("docs/rules.md", self._paths(payload, "c1"))

    def test_missing_project_root_is_scan_unavailable(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCANNER),
                "--project-root",
                str(self.root / "does-not-exist"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "scan-unavailable")
        self.assertEqual(payload["reason"], "project-root-unreadable")

    def test_semantic_rule_content_is_not_parsed(self) -> None:
        # The scanner reports the file and a content hash, never extracted rules.
        write(self.root / "AGENTS.md", "always use tabs and write tests\n")
        _, payload = run_scanner(self.root)
        candidate = next(item for item in payload["c1"] if item["path"] == "AGENTS.md")
        self.assertIn("sha256", candidate)
        flat = json.dumps(payload)
        self.assertNotIn("tabs", flat)


if __name__ == "__main__":
    unittest.main()
