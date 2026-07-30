from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OPEN_WORK_ORDER = REPOSITORY_ROOT / "skills" / "xc-open-work-order" / "scripts" / "open_work_order.py"


class XcOpenWorkOrderTests(unittest.TestCase):
    def run_git(self, repository: Path, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=repository, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def invoke(self, *args: str, cwd: Path) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(OPEN_WORK_ORDER), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_opens_standard_work_order_and_collision_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop_repository = Path(temporary) / "workflow-workshop"
            workshop_repository.mkdir()
            self.run_git(workshop_repository, "init")
            workshop = workshop_repository / ".xcoding"
            workshop.mkdir()

            code, created = self.invoke(
                "--workshop",
                str(workshop),
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
            self.assertRegex(str(created["work_order_id"]), r"^\d{8}-\d{4}-payment-refund$")
            self.assertEqual(created["feature_ids"], ["payment-refund", "billing-ledger"])
            self.assertTrue(Path(str(created["artifacts_path"])).is_dir())
            self.assertTrue(Path(str(created["runtime_path"])).is_dir())
            self.assertEqual(Path(str(created["workbench_path"])).parent, workshop / "work-orders")
            self.assertEqual(created["workshop_path"], str(workshop.resolve()))

            code, duplicate = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                "--work-order-id",
                "explicit-work-order",
                cwd=project,
            )
            self.assertEqual(code, 0)
            self.assertEqual(duplicate["work_order_id"], "explicit-work-order")
            code, collision = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                "--work-order-id",
                "explicit-work-order",
                cwd=project,
            )
            self.assertEqual(code, 0)
            self.assertEqual(collision["work_order_id"], "explicit-work-order-2")

    def test_rejects_workshop_in_business_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop = project / ".xcoding"
            workshop.mkdir()

            code, payload = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                cwd=project,
            )

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertIn("independent", payload["error"]["message"])

    def test_rejects_workshop_outside_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workshop = Path(temporary) / ".xcoding"
            workshop.mkdir()

            code, payload = self.invoke("--workshop", str(workshop), cwd=Path(temporary))

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "work_order_open_error")

    def test_rejects_retired_opener_flags(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(OPEN_WORK_ORDER),
                "--workshop",
                ".xcoding",
                "--context" + "-dir",
                ".xcoding",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --context" + "-dir", result.stderr)


if __name__ == "__main__":
    unittest.main()
