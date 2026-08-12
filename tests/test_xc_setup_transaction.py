from __future__ import annotations

import json
import io
import os
import subprocess
import ctypes
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding.bundle.manifest import ResourceRecord
from xcoding import setup_transaction as setup_module
from xcoding import cli as cli_module


class SetupTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.bundle = Path(self.temporary.name) / "bundle"
        self.root.mkdir()
        resources = []
        entries = {
            "skills/xc-alpha/SKILL.md": ("skill", None, b"alpha\n"),
            "adapters/codex/delegate-agent.toml": (
                "host-adapter",
                "codex",
                b"developer_instructions = \"delegate\"\n",
            ),
            "adapters/trae/delegate-agent.md": (
                "host-adapter",
                "trae",
                b"---\nname: delegate-agent\n---\ndelegate\n",
            ),
            "adapters/claude-code/delegate-agent.md": (
                "host-adapter",
                "claude-code",
                b"---\nname: delegate-agent\n---\ndelegate\n",
            ),
            "adapters/opencode/delegate-agent.md": (
                "host-adapter",
                "opencode",
                b"---\ndescription: delegate\n---\ndelegate\n",
            ),
        }
        for bundle_path, (kind, adapter_id, data) in entries.items():
            path = self.bundle.joinpath(*bundle_path.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            resources.append(
                ResourceRecord(
                    kind=kind,
                    adapter_id=adapter_id,
                    source_path=bundle_path,
                    bundle_path=bundle_path,
                    size=len(data),
                    sha256=setup_module._sha256(data),
                )
            )
        self.inspection = SimpleNamespace(
            manifest=SimpleNamespace(resources=tuple(resources), xc_version="0.1.0"),
            manifest_sha256="a" * 64,
        )
        self.patches = (
            mock.patch.object(
                setup_module,
                "inspect_installed_bundle",
                return_value=self.inspection,
            ),
            mock.patch.object(
                setup_module,
                "installed_bundle_root",
                return_value=self.bundle,
            ),
        )
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def manifest(self) -> dict[str, object]:
        return json.loads(
            (self.root / ".agents/.xcoding-setup/manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_dry_run_is_zero_write_and_reports_stable_lock_identity(self) -> None:
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))

        result = setup_module.setup(
            self.root,
            ["trae", "codex", "trae"],
            dry_run=True,
        )

        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["hosts"], ["codex", "trae"])
        self.assertTrue(result["root_identity"])
        self.assertIn("lock_identity", result)
        self.assertEqual(
            before,
            sorted(path.relative_to(self.root) for path in self.root.rglob("*")),
        )
        self.assertFalse((self.root / ".agents").exists())

    def test_runtime_host_mapping_matches_bundle_build_contract(self) -> None:
        configuration = json.loads(
            (REPOSITORY_ROOT / "build_support/host_adapters.json").read_text(
                encoding="utf-8"
            )
        )
        configured = {
            item["adapter_id"]: (
                item["project_agents_root"],
                item["project_skills_root"],
            )
            for item in configuration["adapters"]
        }
        self.assertEqual(
            configured,
            {
                host: (agents.as_posix(), skills.as_posix())
                for host, (agents, skills) in setup_module.HOST_TARGETS.items()
            },
        )

    def test_install_upgrade_and_rollback_preserve_shared_ownership(self) -> None:
        installed = setup_module.setup(self.root, ["codex", "trae"])

        self.assertTrue(installed["committed"])
        self.assertTrue((self.root / ".codex/agents/delegate-agent.toml").is_file())
        self.assertTrue((self.root / ".trae/agents/delegate-agent.md").is_file())
        shared = self.root / ".agents/skills/xc-alpha/SKILL.md"
        self.assertTrue(shared.is_file())
        first = self.manifest()
        skill = next(item for item in first["files"] if item["path"].endswith("SKILL.md"))
        self.assertEqual(skill["owners"], ["codex", "trae"])

        upgraded = setup_module.setup(self.root, ["codex"])

        self.assertTrue(upgraded["committed"])
        self.assertFalse((self.root / ".trae/agents/delegate-agent.md").exists())
        self.assertTrue(shared.is_file())
        second = self.manifest()
        skill = next(item for item in second["files"] if item["path"].endswith("SKILL.md"))
        self.assertEqual(skill["owners"], ["codex"])
        backup_root = self.root / ".agents/.xcoding-setup/backup"
        self.assertEqual(
            [path.name for path in backup_root.iterdir()],
            [second["generation"]],
        )

        rolled_back = setup_module.rollback(self.root)

        self.assertTrue(rolled_back["rollback"])
        self.assertTrue((self.root / ".trae/agents/delegate-agent.md").is_file())
        restored = self.manifest()
        skill = next(item for item in restored["files"] if item["path"].endswith("SKILL.md"))
        self.assertEqual(skill["owners"], ["codex", "trae"])
        self.assertEqual(
            [path.name for path in backup_root.iterdir()],
            [restored["generation"]],
        )

    def test_unmanaged_and_managed_drift_fail_without_writes(self) -> None:
        unmanaged = self.root / ".trae/agents/delegate-agent.md"
        unmanaged.parent.mkdir(parents=True)
        unmanaged.write_text("user\n", encoding="utf-8")
        snapshot = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

        with self.assertRaises(setup_module.SetupTransactionError) as raised:
            setup_module.setup(self.root, ["trae"], dry_run=True)

        self.assertEqual(raised.exception.code, "unmanaged_conflict")
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(
            snapshot,
            {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()},
        )

        unmanaged.unlink()
        setup_module.setup(self.root, ["trae"])
        target = self.root / ".trae/agents/delegate-agent.md"
        target.write_text("changed\n", encoding="utf-8")
        with self.assertRaises(setup_module.SetupTransactionError) as changed:
            setup_module.setup(self.root, ["trae"], dry_run=True)
        self.assertEqual(changed.exception.code, "managed_content_changed")
        self.assertEqual(target.read_text(encoding="utf-8"), "changed\n")

    def test_post_validation_create_race_preserves_competing_bytes(self) -> None:
        target = self.root / ".trae/agents/delegate-agent.md"
        injected = False

        def race(stage: str, details: object) -> None:
            nonlocal injected
            if (
                stage == "mutation-boundary"
                and isinstance(details, dict)
                and details.get("path") == ".trae/agents/delegate-agent.md"
                and not injected
            ):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("competing\n", encoding="utf-8")
                injected = True

        with mock.patch.object(setup_module, "_transaction_test_hook", race):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"])

        self.assertEqual(raised.exception.code, "path_identity_changed")
        self.assertTrue(raised.exception.details["rolled_back"])
        self.assertTrue(injected)
        self.assertEqual(target.read_text(encoding="utf-8"), "competing\n")
        self.assertFalse((self.root / ".agents/.xcoding-setup/journal.json").exists())

    def test_post_validation_replace_and_remove_races_preserve_competing_bytes(self) -> None:
        setup_module.setup(self.root, ["codex", "trae"])
        skill = self.root / ".agents/skills/xc-alpha/SKILL.md"
        self.bundle.joinpath("skills/xc-alpha/SKILL.md").write_bytes(b"alpha-v2\n")

        def replace_race(stage: str, details: object) -> None:
            if (
                stage == "mutation-boundary"
                and isinstance(details, dict)
                and details.get("path") == ".agents/skills/xc-alpha/SKILL.md"
            ):
                skill.unlink()
                skill.write_text("replace-race\n", encoding="utf-8")

        with mock.patch.object(setup_module, "_transaction_test_hook", replace_race):
            with self.assertRaises(setup_module.SetupTransactionError) as replaced:
                setup_module.setup(self.root, ["codex", "trae"])
        self.assertEqual(replaced.exception.code, "rollback_failed")
        self.assertEqual(skill.read_text(encoding="utf-8"), "replace-race\n")

        # Resolve the retained recovery conflict without weakening ownership,
        # then exercise the same identity-boundary rule for removal.
        skill.unlink()
        setup_module.recover(self.root)
        trae = self.root / ".trae/agents/delegate-agent.md"

        def remove_race(stage: str, details: object) -> None:
            if (
                stage == "mutation-boundary"
                and isinstance(details, dict)
                and details.get("path") == ".trae/agents/delegate-agent.md"
            ):
                trae.unlink()
                trae.write_text("remove-race\n", encoding="utf-8")

        with mock.patch.object(setup_module, "_transaction_test_hook", remove_race):
            with self.assertRaises(setup_module.SetupTransactionError) as removed:
                setup_module.setup(self.root, ["codex"])
        self.assertEqual(removed.exception.code, "rollback_failed")
        self.assertEqual(trae.read_text(encoding="utf-8"), "remove-race\n")

    def test_final_inventory_validation_rejects_late_create_drift(self) -> None:
        for stage in ("operation-applied", "manifest-publication-boundary"):
            with self.subTest(stage=stage):
                project = Path(self.temporary.name) / f"late-create-{stage}"
                project.mkdir()
                target = project / ".trae/agents/delegate-agent.md"
                injected = False

                def race(current: str, details: object) -> None:
                    nonlocal injected
                    if (
                        current == stage
                        and not injected
                        and (
                            current == "manifest-publication-boundary"
                            or (
                                isinstance(details, dict)
                                and details.get("path")
                                == ".trae/agents/delegate-agent.md"
                            )
                        )
                    ):
                        target.write_text("late-create-drift\n", encoding="utf-8")
                        injected = True

                with mock.patch.object(setup_module, "_transaction_test_hook", race):
                    with self.assertRaises(setup_module.SetupTransactionError) as raised:
                        setup_module.setup(project, ["trae"])

                self.assertEqual(raised.exception.code, "rollback_failed")
                self.assertEqual(
                    raised.exception.details["original_code"],
                    "path_identity_changed",
                )
                self.assertTrue(injected)
                self.assertEqual(target.read_text(encoding="utf-8"), "late-create-drift\n")
                self.assertFalse(
                    (project / ".agents/.xcoding-setup/manifest.json").exists()
                )
                self.assertTrue(
                    (project / ".agents/.xcoding-setup/journal.json").is_file()
                )

    def test_final_inventory_validation_rejects_late_replace_and_remove_drift(self) -> None:
        adapter = self.bundle / "adapters/trae/delegate-agent.md"
        original_adapter = adapter.read_bytes()

        replace_project = Path(self.temporary.name) / "late-replace"
        replace_project.mkdir()
        setup_module.setup(replace_project, ["trae"])
        previous_generation = json.loads(
            (replace_project / ".agents/.xcoding-setup/manifest.json").read_text(
                encoding="utf-8"
            )
        )["generation"]
        adapter.write_bytes(b"---\nname: delegate-agent\n---\nupgrade\n")
        replace_target = replace_project / ".trae/agents/delegate-agent.md"

        def replace_race(stage: str, details: object) -> None:
            if (
                stage == "operation-applied"
                and isinstance(details, dict)
                and details.get("path") == ".trae/agents/delegate-agent.md"
            ):
                replace_target.write_text("late-replace-drift\n", encoding="utf-8")

        with mock.patch.object(setup_module, "_transaction_test_hook", replace_race):
            with self.assertRaises(setup_module.SetupTransactionError) as replaced:
                setup_module.setup(replace_project, ["trae"])
        self.assertEqual(replaced.exception.code, "rollback_failed")
        self.assertEqual(
            json.loads(
                (replace_project / ".agents/.xcoding-setup/manifest.json").read_text(
                    encoding="utf-8"
                )
            )["generation"],
            previous_generation,
        )
        self.assertEqual(
            replace_target.read_text(encoding="utf-8"),
            "late-replace-drift\n",
        )

        adapter.write_bytes(original_adapter)
        remove_project = Path(self.temporary.name) / "late-remove"
        remove_project.mkdir()
        setup_module.setup(remove_project, ["codex", "trae"])
        previous_generation = json.loads(
            (remove_project / ".agents/.xcoding-setup/manifest.json").read_text(
                encoding="utf-8"
            )
        )["generation"]
        remove_target = remove_project / ".trae/agents/delegate-agent.md"

        def remove_race(stage: str, details: object) -> None:
            if (
                stage == "operation-applied"
                and isinstance(details, dict)
                and details.get("path") == ".trae/agents/delegate-agent.md"
            ):
                remove_target.parent.mkdir(parents=True, exist_ok=True)
                remove_target.write_text("late-remove-drift\n", encoding="utf-8")

        with mock.patch.object(setup_module, "_transaction_test_hook", remove_race):
            with self.assertRaises(setup_module.SetupTransactionError) as removed:
                setup_module.setup(remove_project, ["codex"])
        self.assertEqual(removed.exception.code, "rollback_failed")
        self.assertEqual(
            json.loads(
                (remove_project / ".agents/.xcoding-setup/manifest.json").read_text(
                    encoding="utf-8"
                )
            )["generation"],
            previous_generation,
        )
        self.assertEqual(remove_target.read_text(encoding="utf-8"), "late-remove-drift\n")

    def test_final_inventory_validation_covers_unchanged_desired_files(self) -> None:
        setup_module.setup(self.root, ["trae"])
        previous_generation = self.manifest()["generation"]
        unchanged = self.root / ".agents/skills/xc-alpha/SKILL.md"
        self.bundle.joinpath("adapters/trae/delegate-agent.md").write_bytes(
            b"---\nname: delegate-agent\n---\nupgrade\n"
        )

        def race(stage: str, details: object) -> None:
            if stage == "manifest-publication-boundary":
                unchanged.write_text("late-unchanged-drift\n", encoding="utf-8")

        with mock.patch.object(setup_module, "_transaction_test_hook", race):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"])

        self.assertEqual(raised.exception.code, "rollback_failed")
        self.assertEqual(
            raised.exception.details["original_code"],
            "path_identity_changed",
        )
        self.assertEqual(self.manifest()["generation"], previous_generation)
        self.assertEqual(
            unchanged.read_text(encoding="utf-8"),
            "late-unchanged-drift\n",
        )
        self.assertTrue(
            (self.root / ".agents/.xcoding-setup/journal.json").is_file()
        )

    @unittest.skipUnless(os.name == "nt", "Windows planned-absent namespace contract")
    def test_planned_absent_target_is_protected_during_manifest_publication(self) -> None:
        setup_module.setup(self.root, ["codex", "trae"])
        removed = self.root / ".trae/agents/delegate-agent.md"
        original_atomic_json = setup_module._atomic_relative_json
        attempted = False
        excluded_during_publication = False

        def publish_with_race(
            root: Path,
            lock: object,
            relative: object,
            value: object,
        ) -> None:
            nonlocal attempted, excluded_during_publication
            if str(relative).replace("\\", "/") == ".agents/.xcoding-setup/manifest.json":
                attempted = True
                excluded_during_publication = True
                try:
                    removed.write_text("recreated-in-publication-window\n", encoding="utf-8")
                except PermissionError:
                    excluded_during_publication = True
                else:
                    excluded_during_publication = False
            original_atomic_json(root, lock, relative, value)

        with mock.patch.object(
            setup_module,
            "_atomic_relative_json",
            publish_with_race,
        ):
            result = setup_module.setup(self.root, ["codex"])

        self.assertTrue(attempted)
        self.assertTrue(excluded_during_publication)
        self.assertTrue(result["committed"])
        self.assertFalse(removed.exists())
        self.assertNotIn(
            ".trae/agents/delegate-agent.md",
            {item["path"] for item in self.manifest()["files"]},
        )
        self.assertFalse(
            (self.root / ".agents/.xcoding-setup/journal.json").exists()
        )

    @unittest.skipUnless(os.name == "nt", "Windows planned-absent provider contract")
    def test_planned_absent_provider_error_recovers_automatically(self) -> None:
        setup_module.setup(self.root, ["codex", "trae"])
        previous_generation = self.manifest()["generation"]
        removed = self.root / ".trae/agents/delegate-agent.md"
        original_open = setup_module._windows_open_relative
        injected = False

        def fail_tombstone(*args: object, **kwargs: object) -> int:
            nonlocal injected
            if kwargs.get("create") and kwargs.get("delete_on_close") and not injected:
                injected = True
                raise PermissionError(13, "injected tombstone provider denial", str(args[2]))
            return original_open(*args, **kwargs)

        with mock.patch.object(setup_module, "_windows_open_relative", fail_tombstone):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["codex"])

        self.assertTrue(injected)
        self.assertEqual(raised.exception.code, "path_identity_changed")
        self.assertEqual(raised.exception.details["path"], ".trae/agents/delegate-agent.md")
        self.assertEqual(raised.exception.details["platform"], sys.platform)
        self.assertEqual(raised.exception.details["exception"], "PermissionError")
        self.assertTrue(raised.exception.details["rolled_back"])
        self.assertEqual(self.manifest()["generation"], previous_generation)
        self.assertTrue(removed.is_file())
        self.assertFalse((self.root / ".agents/.xcoding-setup/journal.json").exists())

    def test_recovery_detects_drift_before_write_and_then_finishes_idempotently(self) -> None:
        setup_module.setup(self.root, ["trae"])
        target = self.root / ".trae/agents/delegate-agent.md"
        original = target.read_bytes()
        upgraded = b"---\nname: delegate-agent\n---\nupgraded\n"
        self.bundle.joinpath("adapters/trae/delegate-agent.md").write_bytes(upgraded)

        applied_path = ""

        def interrupt(stage: str, details: object) -> None:
            nonlocal applied_path
            if stage == "operation-applied" and isinstance(details, dict):
                applied_path = str(details["path"])
                raise RuntimeError("forced termination after upgrade mutation")

        with mock.patch.object(setup_module, "_transaction_test_hook", interrupt):
            with self.assertRaises(RuntimeError):
                setup_module.setup(self.root, ["trae"])

        applied = self.root.joinpath(*applied_path.split("/"))
        after = applied.read_bytes()
        applied.write_text("user-change-after-crash\n", encoding="utf-8")
        with self.assertRaises(setup_module.SetupTransactionError) as conflict:
            setup_module.recover(self.root)
        self.assertEqual(conflict.exception.code, "recovery_conflict")
        self.assertEqual(applied.read_text(encoding="utf-8"), "user-change-after-crash\n")

        applied.write_bytes(after)
        recovered = setup_module.recover(self.root)
        again = setup_module.recover(self.root)
        self.assertEqual(recovered["direction"], "rollback")
        self.assertFalse(again["recovered"])
        self.assertEqual(target.read_bytes(), original)

    def test_ordinary_transaction_error_rolls_back_automatically(self) -> None:
        def fail(stage: str, details: object) -> None:
            if stage == "operation-applied":
                raise setup_module.SetupTransactionError(
                    "path_identity_changed",
                    "injected ordinary transaction failure",
                )

        with mock.patch.object(setup_module, "_transaction_test_hook", fail):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"])

        self.assertEqual(raised.exception.code, "path_identity_changed")
        self.assertTrue(raised.exception.details["rolled_back"])
        self.assertFalse((self.root / ".agents/.xcoding-setup/journal.json").exists())
        self.assertFalse((self.root / ".trae/agents/delegate-agent.md").exists())

    def test_first_install_rollback_is_zero_write_and_preexisting_host_directories_survive(self) -> None:
        for directory in (".agents", ".codex", ".opencode", ".claude", ".trae"):
            (self.root / directory).mkdir()
        setup_module.setup(self.root, ["trae"])
        before_files = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        before_directories = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_dir()
        }

        with self.assertRaises(setup_module.SetupTransactionError) as unavailable:
            setup_module.rollback(self.root)

        self.assertEqual(unavailable.exception.code, "rollback_unavailable")
        self.assertEqual(
            before_files,
            {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*")
                if path.is_file()
            },
        )
        self.assertEqual(
            before_directories,
            {
                path.relative_to(self.root).as_posix()
                for path in self.root.rglob("*")
                if path.is_dir()
            },
        )

        setup_module.setup(self.root, ["codex"])
        for directory in (".agents", ".codex", ".opencode", ".claude", ".trae"):
            self.assertTrue((self.root / directory).is_dir())

    def test_unexpected_idle_state_fails_closed(self) -> None:
        setup_module.setup(self.root, ["trae"])
        unexpected = self.root / ".agents/.xcoding-setup/unmanaged.txt"
        unexpected.write_text("preserve\n", encoding="utf-8")

        with self.assertRaises(setup_module.SetupTransactionError) as raised:
            setup_module.setup(self.root, ["trae"], dry_run=True)

        self.assertEqual(raised.exception.code, "manifest_invalid")
        self.assertEqual(unexpected.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((self.root / ".agents/.xcoding-setup/journal.json").exists())

    def test_interrupted_precommit_transaction_recovers_idempotently(self) -> None:
        def interrupt(stage: str, details: object) -> None:
            if stage == "operation-applied":
                raise RuntimeError("forced termination")

        with mock.patch.object(setup_module, "_transaction_test_hook", interrupt):
            with self.assertRaises(RuntimeError):
                setup_module.setup(self.root, ["trae"])

        journal = self.root / ".agents/.xcoding-setup/journal.json"
        self.assertTrue(journal.is_file())
        with self.assertRaises(setup_module.SetupTransactionError) as blocked:
            setup_module.setup(self.root, ["trae"])
        self.assertEqual(blocked.exception.code, "recovery_required")

        recovered = setup_module.recover(self.root)
        again = setup_module.recover(self.root)

        self.assertEqual(recovered["direction"], "rollback")
        self.assertFalse(journal.exists())
        self.assertFalse((self.root / ".trae/agents/delegate-agent.md").exists())
        self.assertFalse(again["recovered"])

    def test_preparation_interruptions_have_durable_cleanup_authority(self) -> None:
        for stage in ("preparing", "prepared"):
            with self.subTest(stage=stage):
                project = Path(self.temporary.name) / f"project-{stage}"
                project.mkdir()

                def interrupt(current: str, details: object) -> None:
                    if current == stage:
                        raise RuntimeError(f"forced termination at {stage}")

                with mock.patch.object(setup_module, "_transaction_test_hook", interrupt):
                    with self.assertRaises(RuntimeError):
                        setup_module.setup(project, ["trae"])

                journal = project / ".agents/.xcoding-setup/journal.json"
                self.assertTrue(journal.is_file())
                recovered = setup_module.recover(project)
                self.assertEqual(recovered["direction"], "rollback")
                self.assertFalse(journal.exists())
                self.assertFalse((project / ".trae").exists())

    def test_manifest_publication_is_the_recovery_commit_point(self) -> None:
        def interrupt(stage: str, details: object) -> None:
            if stage == "manifest-published":
                raise RuntimeError("forced termination after commit point")

        with mock.patch.object(setup_module, "_transaction_test_hook", interrupt):
            with self.assertRaises(RuntimeError):
                setup_module.setup(self.root, ["trae"])

        recovered = setup_module.recover(self.root)

        self.assertEqual(recovered["direction"], "complete")
        self.assertTrue((self.root / ".trae/agents/delegate-agent.md").is_file())
        self.assertEqual(self.manifest()["hosts"], ["trae"])

    def test_post_commit_transaction_errors_return_the_committed_generation(self) -> None:
        for stage in ("manifest-published", "committed", "cleanup-complete"):
            with self.subTest(stage=stage):
                project = Path(self.temporary.name) / f"post-commit-{stage}"
                project.mkdir()

                def fail(current: str, details: object) -> None:
                    if current == stage:
                        raise setup_module.SetupTransactionError(
                            f"injected-{stage}",
                            "injected post-commit failure",
                        )

                with mock.patch.object(setup_module, "_transaction_test_hook", fail):
                    result = setup_module.setup(project, ["trae"])

                manifest = json.loads(
                    (project / ".agents/.xcoding-setup/manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertTrue(result["committed"])
                self.assertTrue(result["recovered"])
                self.assertEqual(result["recovery_direction"], "complete")
                self.assertEqual(result["generation"], manifest["generation"])
                self.assertEqual(result["recovered_from_error"], f"injected-{stage}")
                self.assertTrue(
                    (project / ".trae/agents/delegate-agent.md").is_file()
                )
                self.assertFalse(
                    (project / ".agents/.xcoding-setup/journal.json").exists()
                )
                retry = setup_module.setup(project, ["trae"], dry_run=True)
                self.assertEqual(retry["source_generation"], manifest["generation"])
                self.assertFalse(retry["writes_performed"])

    def test_post_commit_recovery_rejects_inventory_drift(self) -> None:
        target = self.root / ".trae/agents/delegate-agent.md"

        def interrupt(stage: str, details: object) -> None:
            if stage == "manifest-published":
                raise RuntimeError("forced termination after commit point")

        with mock.patch.object(setup_module, "_transaction_test_hook", interrupt):
            with self.assertRaises(RuntimeError):
                setup_module.setup(self.root, ["trae"])

        target.write_text("post-commit-drift\n", encoding="utf-8")
        with self.assertRaises(setup_module.SetupTransactionError) as conflict:
            setup_module.recover(self.root)

        self.assertEqual(conflict.exception.code, "path_identity_changed")
        self.assertEqual(target.read_text(encoding="utf-8"), "post-commit-drift\n")
        self.assertTrue(
            (self.root / ".agents/.xcoding-setup/journal.json").is_file()
        )

    def test_forced_process_termination_releases_kernel_lock_and_recovers(self) -> None:
        project = Path(self.temporary.name) / "forced-process-project"
        project.mkdir()
        program = r'''
import hashlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, sys.argv[1])
from xcoding.bundle.manifest import ResourceRecord
from xcoding import setup_transaction as setup

bundle = Path(sys.argv[2])
project = Path(sys.argv[3])
records = []
for bundle_path, kind, adapter in (
    ("skills/xc-alpha/SKILL.md", "skill", None),
    ("adapters/trae/delegate-agent.md", "host-adapter", "trae"),
):
    data = bundle.joinpath(*bundle_path.split("/")).read_bytes()
    records.append(ResourceRecord(kind, adapter, bundle_path, bundle_path, len(data), hashlib.sha256(data).hexdigest()))
inspection = SimpleNamespace(
    manifest=SimpleNamespace(resources=tuple(records), xc_version="0.1.0"),
    manifest_sha256="a" * 64,
)

def terminate(stage, details):
    if stage == "operation-applied":
        os._exit(73)

with mock.patch.object(setup, "inspect_installed_bundle", return_value=inspection), mock.patch.object(setup, "installed_bundle_root", return_value=bundle), mock.patch.object(setup, "_transaction_test_hook", terminate):
    setup.setup(project, ["trae"])
raise SystemExit(74)
'''
        terminated = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                program,
                str(REPOSITORY_ROOT / "src"),
                str(self.bundle),
                str(project),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        self.assertEqual(terminated.returncode, 73, terminated.stderr)

        recovered = setup_module.recover(project)
        dry_run = setup_module.setup(project, ["trae"], dry_run=True)

        self.assertEqual(recovered["direction"], "rollback")
        self.assertFalse((project / ".trae/agents/delegate-agent.md").exists())
        self.assertFalse((project / ".agents/.xcoding-setup/journal.json").exists())
        self.assertFalse(dry_run["writes_performed"])

    def test_post_preflight_ancestor_replacement_fails_before_target_write(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        def replace(stage: str, details: object) -> None:
            if stage != "operation-intent":
                return
            link = self.root / ".trae"
            if link.exists() or link.is_symlink():
                return
            if os.name == "nt":
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                if created.returncode != 0:
                    self.fail(created.stderr or created.stdout)
            else:
                link.symlink_to(outside, target_is_directory=True)

        with mock.patch.object(setup_module, "_transaction_test_hook", replace):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"])

        self.assertEqual(raised.exception.code, "path_identity_changed")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertEqual(
            list(path for path in outside.rglob("*") if path != sentinel),
            [],
        )

    def test_unsupported_lock_provider_fails_before_state_creation(self) -> None:
        error = setup_module.SetupTransactionError(
            "lock_provider_unsupported",
            "unsupported",
        )
        target = (
            "_acquire_windows_lock" if setup_module.os.name == "nt" else "_acquire_posix_lock"
        )
        with mock.patch.object(setup_module, target, side_effect=error):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"], dry_run=True)

        self.assertEqual(raised.exception.code, "lock_provider_unsupported")
        self.assertFalse((self.root / ".agents").exists())

    @unittest.skipUnless(os.name == "nt", "Windows named-object contract")
    def test_existing_mutex_with_unverified_security_fails_closed(self) -> None:
        root_handle, identity = setup_module._windows_open_root(self.root)
        kernel32 = setup_module._windows_kernel32()
        kernel32.CloseHandle(root_handle)
        name = "Global\\XcodingSetup-v1-" + "-".join(
            f"{part:08x}" for part in identity
        )
        mutex = kernel32.CreateMutexExW(None, name, 0, 0x001F0001)
        self.assertTrue(mutex)
        try:
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"], dry_run=True)
        finally:
            kernel32.CloseHandle(mutex)
        self.assertEqual(raised.exception.code, "lock_provider_unsupported")
        self.assertFalse((self.root / ".agents").exists())

    @unittest.skipUnless(os.name == "nt", "Windows named-object contract")
    def test_named_non_mutex_collision_fails_closed(self) -> None:
        root_handle, identity = setup_module._windows_open_root(self.root)
        kernel32 = setup_module._windows_kernel32()
        kernel32.CloseHandle(root_handle)
        name = "Global\\XcodingSetup-v1-" + "-".join(
            f"{part:08x}" for part in identity
        )
        kernel32.CreateEventW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_wchar_p,
        ]
        kernel32.CreateEventW.restype = ctypes.c_void_p
        event = kernel32.CreateEventW(None, 0, 0, name)
        self.assertTrue(event)
        try:
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                setup_module.setup(self.root, ["trae"], dry_run=True)
        finally:
            kernel32.CloseHandle(event)
        self.assertEqual(raised.exception.code, "lock_name_collision")
        self.assertFalse((self.root / ".agents").exists())

    def test_lock_is_nonblocking_across_threads(self) -> None:
        root = setup_module._resolve_project_root(self.root)
        outcomes: list[str] = []
        with setup_module.project_lock(root):
            def contend() -> None:
                try:
                    with setup_module.project_lock(root):
                        outcomes.append("acquired")
                except setup_module.SetupTransactionError as error:
                    outcomes.append(error.code)

            thread = threading.Thread(target=contend)
            thread.start()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes, ["setup_locked"])

    def test_cli_requires_explicit_mode_inputs_and_routes_transactions(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = cli_module.main(["setup", "--json", "--host", "trae"])
        self.assertEqual(code, cli_module.EXIT_INPUT)
        self.assertEqual(
            json.loads(stream.getvalue())["error"]["code"],
            "project_root_required",
        )

        cases = (
            (
                [
                    "setup",
                    "--json",
                    "--project-root",
                    str(self.root),
                    "--host",
                    "trae",
                    "--dry-run",
                ],
                "run_setup",
            ),
            (
                ["setup", "--json", "--project-root", str(self.root), "--rollback"],
                "rollback_setup",
            ),
            (
                ["setup", "--json", "--project-root", str(self.root), "--recover"],
                "recover_setup",
            ),
        )
        for arguments, target in cases:
            with self.subTest(target=target):
                stream = io.StringIO()
                with mock.patch.object(
                    cli_module,
                    target,
                    return_value={"writes_performed": target != "run_setup"},
                ) as invoked, redirect_stdout(stream):
                    code = cli_module.main(arguments)
                self.assertEqual(code, cli_module.EXIT_SUCCESS)
                self.assertTrue(json.loads(stream.getvalue())["ok"])
                invoked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
