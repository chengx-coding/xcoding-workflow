from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OPEN_WORK_ORDER = REPOSITORY_ROOT / "skills" / "xc-open-work-order" / "scripts" / "open_work_order.py"
SOURCE_ROOT = REPOSITORY_ROOT / "src"

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.runtime import core


class XcOpenWorkOrderTests(unittest.TestCase):
    def run_git(self, repository: Path, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=repository, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def create_directory_link(self, target: Path, link: Path) -> None:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if result.returncode != 0:
                raise unittest.SkipTest(result.stderr or result.stdout or "junction creation failed")
            return
        try:
            os.symlink(target, link, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            raise unittest.SkipTest(f"directory symlink creation failed: {exc}") from exc

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

    def test_opens_logical_workshop_link_with_non_dot_xcoding_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop_repository = Path(temporary) / "workflow-workshop"
            workshop_repository.mkdir()
            self.run_git(workshop_repository, "init")
            target = workshop_repository / "managed-context"
            target.mkdir()
            workshop = project / ".xcoding"
            self.create_directory_link(target, workshop)

            code, created = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                "--work-order-id",
                "linked-workshop",
                cwd=project,
            )

            self.assertEqual(code, 0)
            self.assertTrue(created["ok"])
            self.assertEqual(created["workshop_path"], str(target.resolve()))
            self.assertEqual(Path(str(created["workbench_path"])).parent, target.resolve() / "work-orders")
            self.assertTrue(Path(str(created["runtime_path"])).is_dir())

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

    def write_config(self, workshop: Path, config: dict[str, object]) -> None:
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps(config), encoding="utf-8"
        )

    def test_opens_same_repo_workshop_with_explicit_auto_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop = project / ".xcoding"
            workshop.mkdir()
            self.write_config(
                workshop,
                {
                    "schema_version": 1,
                    "git": {"auto_commit": True, "on_commit_failure": "warn"},
                    "workshop": {"topology": "same-repo"},
                },
            )

            code, created = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                "--work-order-id",
                "same-repo-work",
                cwd=project,
            )

            self.assertEqual(code, 0)
            self.assertTrue(created["ok"])
            self.assertEqual(created["workshop_repo_root"], str(project.resolve()))

    def test_rejects_same_repo_workshop_without_explicit_auto_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop = project / ".xcoding"
            workshop.mkdir()
            self.write_config(
                workshop,
                {
                    "schema_version": 1,
                    "git": {"on_commit_failure": "warn"},
                    "workshop": {"topology": "same-repo"},
                },
            )

            code, payload = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                cwd=project,
            )

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "explicit git.auto_commit declaration", payload["error"]["message"]
            )

    def test_opens_no_git_workshop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "base"
            base.mkdir()
            workshop = base / ".xcoding"
            workshop.mkdir()
            self.write_config(
                workshop,
                {"schema_version": 1, "workshop": {"topology": "no-git"}},
            )

            code, created = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(base),
                "--work-order-id",
                "no-git-work",
                cwd=base,
            )

            self.assertEqual(code, 0)
            self.assertTrue(created["ok"])
            self.assertIsNone(created["workshop_repo_root"])

    def test_opens_nested_independent_workshop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            self.run_git(project, "init")
            workshop_repo = project / "workshop-repo"
            workshop_repo.mkdir()
            self.run_git(workshop_repo, "init")
            workshop = workshop_repo / ".xcoding"
            workshop.mkdir()
            self.write_config(
                workshop,
                {"schema_version": 1, "workshop": {"topology": "independent-nested"}},
            )

            code, created = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(project),
                "--work-order-id",
                "nested-work",
                cwd=project,
            )

            self.assertEqual(code, 0)
            self.assertTrue(created["ok"])
            self.assertEqual(created["workshop_repo_root"], str(workshop_repo.resolve()))

    def test_rejects_config_with_non_object_workshop(self) -> None:
        # F1: a `workshop` section that is present but not an object must fail
        # closed with the parity message, rather than silently using the default.
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "base"
            base.mkdir()
            workshop = base / ".xcoding"
            workshop.mkdir()
            self.write_config(workshop, {"schema_version": 1, "workshop": "same-repo"})

            code, payload = self.invoke(
                "--workshop",
                str(workshop),
                "--project-root",
                str(base),
                cwd=base,
            )

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["message"], "workshop must be an object")

    def test_core_rejects_same_non_object_workshop_fixture(self) -> None:
        # F1 parity: the fixture that open_work_order rejects as a WorkOrderError
        # must also be rejected by the runtime config loader (ConfigError). Mirrors
        # the config-contract drift-test style.
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "xc-orchestration-runtime.json"
            config_path.write_text(json.dumps({"workshop": "same-repo"}), encoding="utf-8")

            with self.assertRaises(core.ConfigError) as ctx:
                core.load_config(config_path=config_path)
            self.assertEqual(str(ctx.exception), "workshop must be an object")


if __name__ == "__main__":
    unittest.main()
