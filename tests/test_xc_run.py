from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CREATE_RUN = REPOSITORY_ROOT / "skills" / "xc-run" / "scripts" / "create_run.py"


class XcRunTests(unittest.TestCase):
    def run_git(self, repository: Path, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=repository, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def invoke(self, *args: str, cwd: Path) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(CREATE_RUN), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_creates_standard_run_and_collision_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            context_repository = Path(temporary) / "workflow-context"
            context_repository.mkdir()
            self.run_git(context_repository, "init")
            context = context_repository / ".xcoding"
            context.mkdir()

            code, created = self.invoke(
                "--context-dir",
                str(context),
                "--project-root",
                str(project),
                "--topic",
                "Payment Refund",
                "--feature-id",
                "payment-refund",
                "--feature-id",
                "billing-ledger",
                cwd=project,
            )

            self.assertEqual(code, 0)
            self.assertTrue(created["ok"])
            self.assertRegex(str(created["run_id"]), r"^\d{8}-\d{4}-payment-refund$")
            self.assertEqual(created["feature_ids"], ["payment-refund", "billing-ledger"])
            self.assertTrue(Path(str(created["artifacts_dir"])).is_dir())
            self.assertTrue(Path(str(created["runtime_dir"])).is_dir())

            code, duplicate = self.invoke(
                "--context-dir",
                str(context),
                "--project-root",
                str(project),
                "--run-id",
                "explicit-run",
                cwd=project,
            )
            self.assertEqual(code, 0)
            self.assertEqual(duplicate["run_id"], "explicit-run")
            code, collision = self.invoke(
                "--context-dir",
                str(context),
                "--project-root",
                str(project),
                "--run-id",
                "explicit-run",
                cwd=project,
            )
            self.assertEqual(code, 0)
            self.assertEqual(collision["run_id"], "explicit-run-2")

    def test_rejects_context_in_business_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            context = project / ".xcoding"
            context.mkdir()

            code, payload = self.invoke(
                "--context-dir",
                str(context),
                "--project-root",
                str(project),
                cwd=project,
            )

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertIn("independent", payload["error"]["message"])

    def test_rejects_context_outside_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = Path(temporary) / ".xcoding"
            context.mkdir()

            code, payload = self.invoke("--context-dir", str(context), cwd=Path(temporary))

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "run_creation_error")


if __name__ == "__main__":
    unittest.main()
