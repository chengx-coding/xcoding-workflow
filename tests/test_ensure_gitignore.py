from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "scripts" / "ensure_gitignore.py"
ENTRY = "/.xcoding/"


class EnsureGitignoreTests(unittest.TestCase):
    def run_script(self, project_root: Path, topology: str) -> tuple[int, dict[str, object]]:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project-root",
                str(project_root),
                "--topology",
                topology,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout)

    def gitignore(self, project_root: Path) -> Path:
        return project_root / ".gitignore"

    def test_append_creates_rule_and_file_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            code, payload = self.run_script(project, "independent-link")

            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "appended")
            gitignore = self.gitignore(project)
            self.assertTrue(gitignore.exists())
            self.assertEqual(gitignore.read_text(encoding="utf-8"), ENTRY + "\n")

    def test_second_run_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            first_code, first = self.run_script(project, "independent-link")
            self.assertEqual(first["status"], "appended")

            second_code, second = self.run_script(project, "independent-link")

            self.assertEqual(second_code, 0, second)
            self.assertEqual(second["status"], "already-present")
            self.assertEqual(
                self.gitignore(project).read_text(encoding="utf-8"),
                ENTRY + "\n",
            )

    def test_existing_equivalent_entry_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            gitignore = self.gitignore(project)
            gitignore.write_text("# header\n.xcoding/\n", encoding="utf-8")
            before = gitignore.read_bytes()

            code, payload = self.run_script(project, "independent-nested")

            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "already-present")
            self.assertEqual(gitignore.read_bytes(), before)

    def test_negation_conflict_leaves_file_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            gitignore = self.gitignore(project)
            gitignore.write_text("!.xcoding\n", encoding="utf-8")
            before = gitignore.read_bytes()

            code, payload = self.run_script(project, "independent-link")

            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "skipped-conflict")
            self.assertEqual(gitignore.read_bytes(), before)

    def test_same_repo_and_no_git_are_not_applicable_and_write_nothing(self) -> None:
        for topology in ("same-repo", "no-git"):
            with self.subTest(topology=topology), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                gitignore = self.gitignore(project)
                gitignore.write_text("existing\n", encoding="utf-8")
                before = gitignore.read_bytes()

                code, payload = self.run_script(project, topology)

                self.assertEqual(code, 0, payload)
                self.assertEqual(payload["status"], "not-applicable")
                self.assertEqual(gitignore.read_bytes(), before)

    def test_invalid_topology_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            gitignore = self.gitignore(project)
            code, payload = self.run_script(project, "bogus-topology")

            self.assertEqual(code, 2, payload)
            self.assertEqual(payload["status"], "error")
            self.assertFalse(gitignore.exists())


if __name__ == "__main__":
    unittest.main()
