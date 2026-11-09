"""Install lifecycle contract: user scope, legacy adoption, uninstall, doctor.

The setup transaction owns every payload write; ``lifecycle`` only selects the
scope root, validates the host set, and sequences the external CLI step.  These
tests keep the lifecycle layer honest against temporary roots only: the real
user home is never read or written.
"""

from __future__ import annotations
from tests.support.paths import REPO_ROOT  # noqa: E402

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest import mock

REPOSITORY_ROOT = REPO_ROOT
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding.bundle.manifest import ResourceRecord
from xcoding import cli as cli_module
from xcoding import doctor as doctor_module
from xcoding import lifecycle as lifecycle_module
from xcoding import setup_transaction as setup_module


class LifecycleTestBase(unittest.TestCase):
    """A fake bundle, an isolated home/project root, and no real bundle access."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xc-lifecycle-")
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "project"
        self.project.mkdir()
        self.bundle = self.base / "bundle"
        resources = []
        entries = {
            "skills/xc-alpha/SKILL.md": ("skill", None, b"alpha\n"),
            "adapters/codex/delegate-agent.toml": (
                "host-adapter",
                "codex",
                b'developer_instructions = "delegate"\n',
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
        for adapter_id in setup_module.HOST_ORDER:
            statement = {
                "schema_version": 1,
                "kind": "xc-delegation-adapter-capabilities/v1",
                "adapter_id": adapter_id,
                "adapter_version": "fixture",
                "mode": "validated-only",
                "evidence": [],
                "capabilities": [],
            }
            entries[
                f"skills/xc-delegation/assets/adapters/{adapter_id}.json"
            ] = (
                "skill",
                None,
                (
                    json.dumps(
                        statement,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8"),
            )
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
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
        self.inspection = SimpleNamespace(
            manifest=SimpleNamespace(
                resources=tuple(resources),
                xc_version="0.1.0",
                python_requires=">=3.12",
            ),
            manifest_sha256="a" * 64,
            as_dict=lambda: {
                "manifest_sha256": "a" * 64,
                "xc_version": "0.1.0",
                "fixture": True,
            },
        )
        self.running = {
            "xc_version": "0.1.0",
            "bundle_manifest_sha256": "a" * 64,
        }
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
            mock.patch.object(
                doctor_module,
                "inspect_installed_bundle",
                return_value=self.inspection,
            ),
            mock.patch.object(
                doctor_module,
                "installed_bundle_root",
                return_value=self.bundle,
            ),
            mock.patch.object(
                lifecycle_module,
                "version_report",
                return_value=self.running,
            ),
            mock.patch.object(Path, "home", return_value=self.home),
        )
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    # -- helpers ---------------------------------------------------------
    def manifest_path(self, root: Path | None = None) -> Path:
        return (root or self.home) / ".agents" / ".xcoding-setup" / "manifest.json"

    def manifest(self, root: Path | None = None) -> dict[str, object]:
        return json.loads(
            self.manifest_path(root).read_text(encoding="utf-8")
        )

    def target(self, root: Path, relative: str) -> Path:
        return root.joinpath(*PurePosixPath(relative).parts)

    def write_file(self, root: Path, relative: str, data: bytes) -> Path:
        path = self.target(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_cli(self, arguments: list[str]) -> tuple[int, dict[str, object]]:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = cli_module.main(arguments)
        output = stream.getvalue()
        self.assertEqual(len(output.splitlines()), 1, output)
        return code, json.loads(output)

    def install_user(
        self,
        hosts: list[str] | None = None,
        *,
        dry_run: bool = False,
        adopt_legacy: bool = False,
    ) -> dict[str, object]:
        return lifecycle_module.install(
            "user",
            hosts=hosts if hosts is not None else ["claude-code", "codex"],
            dry_run=dry_run,
            adopt_legacy=adopt_legacy,
        )

    def write_legacy_fixture(self, *, drift: bool = True) -> None:
        alpha = b"alpha\n"
        old_package = b"old package\n"
        claude_alpha = b"alpha-v1\n"
        drifted = b"drifted\n"
        self.write_file(self.home, ".agents/skills/xc-alpha/SKILL.md", alpha)
        self.write_file(self.home, ".agents/skills/xc-old/SKILL.md", old_package)
        self.write_file(
            self.home,
            ".claude/skills/xc-alpha/SKILL.md",
            claude_alpha,
        )
        claude_records = [
            {
                "path": "xc-alpha/SKILL.md",
                "sha256": hashlib.sha256(claude_alpha).hexdigest(),
            },
        ]
        if drift:
            self.write_file(
                self.home,
                ".claude/skills/xc-drift/SKILL.md",
                drifted,
            )
            claude_records.append(
                {
                    "path": "xc-drift/SKILL.md",
                    "sha256": hashlib.sha256(b"original\n").hexdigest(),
                }
            )
        agents_manifest = {
            "schema_version": 1,
            "installer_version": "1",
            "source_revision": "fixture-legacy",
            "expected_packages": ["xc-alpha", "xc-old"],
            "files": [
                {
                    "path": "xc-alpha/SKILL.md",
                    "sha256": hashlib.sha256(alpha).hexdigest(),
                },
                {
                    "path": "xc-old/SKILL.md",
                    "sha256": hashlib.sha256(old_package).hexdigest(),
                },
            ],
        }
        claude_manifest = {
            "schema_version": 1,
            "installer_version": "1",
            "source_revision": "fixture-legacy",
            "expected_packages": ["xc-alpha", "xc-drift"],
            "files": claude_records,
        }
        self.write_file(
            self.home,
            ".agents/.xc-skill-install-manifest.json",
            setup_module._canonical_json(agents_manifest),
        )
        self.write_file(
            self.home,
            ".claude/.xc-skill-install-manifest.json",
            setup_module._canonical_json(claude_manifest),
        )

    def write_legacy_manifest(
        self,
        root: Path,
        location: str,
        packages: list[str],
        files: dict[str, bytes],
        *,
        revision: str = "fixture-legacy",
        installer_version: object = "1",
    ) -> None:
        """Write one 0.3.6 ownership manifest under ``.agents`` or ``.claude``."""

        manifest = {
            "schema_version": 1,
            "installer_version": installer_version,
            "source_revision": revision,
            "expected_packages": list(packages),
            "files": [
                {
                    "path": path,
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for path, data in files.items()
            ],
        }
        self.write_file(
            root,
            f".{location}/.xc-skill-install-manifest.json",
            setup_module._canonical_json(manifest),
        )


class UserScopeInstallTests(LifecycleTestBase):
    def test_user_install_dry_run_plans_without_writing(self) -> None:
        lark = self.write_file(
            self.home,
            ".agents/skills/lark-like/SKILL.md",
            b"user-owned\n",
        )

        result = self.install_user(dry_run=True)

        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["scope"], "user")
        self.assertEqual(Path(str(result["root"])).resolve(), self.home.resolve())
        self.assertEqual(result["version"], "0.1.0")
        self.assertEqual(result["bundle_manifest_sha256"], "a" * 64)
        self.assertTrue(result["operations"])
        self.assertEqual(
            {operation["action"] for operation in result["operations"]},
            {"create"},
        )
        self.assertFalse(self.manifest_path().exists())
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".codex").exists())
        self.assertEqual(lark.read_bytes(), b"user-owned\n")
        self.assertFalse(result["adoption"]["requested"])
        self.assertEqual(result["adoption"]["counts"]["total"], 0)

    def test_user_install_writes_manifest_and_preserves_unowned_files(self) -> None:
        lark_agents = self.write_file(
            self.home,
            ".agents/skills/lark-like/SKILL.md",
            b"user-owned-agents\n",
        )
        lark_claude = self.write_file(
            self.home,
            ".claude/skills/lark-claude/SKILL.md",
            b"user-owned-claude\n",
        )

        result = self.install_user()

        self.assertTrue(result["writes_performed"])
        self.assertTrue(result["committed"])
        self.assertEqual(result["scope"], "user")
        manifest = self.manifest()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["distribution"], "xcoding-workflow")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["bundle_manifest_sha256"], "a" * 64)
        self.assertEqual(manifest["hosts"], ["claude-code", "codex"])
        self.assertEqual(len(manifest["generation"]), 32)
        self.assertIsNone(manifest["previous_generation"])
        self.assertEqual(len(manifest["files"]), 12)
        paths = {item["path"] for item in manifest["files"]}
        self.assertNotIn(".agents/skills/lark-like/SKILL.md", paths)
        self.assertNotIn(".claude/skills/lark-claude/SKILL.md", paths)
        for relative in (
            ".agents/skills/xc-alpha/SKILL.md",
            ".agents/skills/xc-delegation/assets/adapters/codex.json",
            ".claude/skills/xc-alpha/SKILL.md",
            ".claude/agents/delegate-agent.md",
            ".codex/agents/delegate-agent.toml",
        ):
            self.assertTrue(
                self.target(self.home, relative).is_file(),
                relative,
            )
        owners = {
            item["path"]: item["owners"] for item in manifest["files"]
        }
        self.assertEqual(
            owners[".agents/skills/xc-alpha/SKILL.md"],
            ["codex"],
        )
        self.assertEqual(
            owners[".claude/skills/xc-alpha/SKILL.md"],
            ["claude-code"],
        )
        self.assertEqual(lark_agents.read_bytes(), b"user-owned-agents\n")
        self.assertEqual(lark_claude.read_bytes(), b"user-owned-claude\n")
        self.assertFalse(result["adoption"]["requested"])

    def test_repeat_install_reports_only_unchanged_operations(self) -> None:
        self.install_user()
        before = {
            path.relative_to(self.home).as_posix(): path.read_bytes()
            for path in self.home.rglob("*")
            if path.is_file()
            and ".xcoding-setup" not in path.relative_to(self.home).parts
        }

        result = self.install_user()

        self.assertTrue(result["writes_performed"])
        self.assertEqual(len(result["operations"]), 12)
        self.assertEqual(
            {operation["action"] for operation in result["operations"]},
            {"unchanged"},
        )
        after = {
            path.relative_to(self.home).as_posix(): path.read_bytes()
            for path in self.home.rglob("*")
            if path.is_file()
            and ".xcoding-setup" not in path.relative_to(self.home).parts
        }
        self.assertEqual(before, after)

    def test_install_refuses_a_competing_project_lock(self) -> None:
        root = setup_module._resolve_project_root(self.home)
        outcomes: list[str] = []

        with setup_module.project_lock(root):
            def contend() -> None:
                try:
                    lifecycle_module.install(
                        "user",
                        hosts=["codex"],
                        dry_run=True,
                    )
                except setup_module.SetupTransactionError as error:
                    outcomes.append(error.code)
                else:
                    outcomes.append("acquired")

            thread = threading.Thread(target=contend)
            thread.start()
            thread.join(timeout=15)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes, ["setup_locked"])


class LegacyAdoptionTests(LifecycleTestBase):
    def test_adopt_legacy_dry_run_reports_claims_without_writing(self) -> None:
        self.write_legacy_fixture()
        before = {
            path.relative_to(self.home).as_posix(): path.read_bytes()
            for path in self.home.rglob("*")
            if path.is_file()
        }

        result = self.install_user(dry_run=True, adopt_legacy=True)

        self.assertFalse(result["writes_performed"])
        adoption = result["adoption"]
        self.assertTrue(adoption["requested"])
        self.assertEqual(
            adoption["claims"],
            {"legacy": 3, "current": 0, "total": 3},
        )
        self.assertEqual(
            adoption["counts"],
            {"legacy": 3, "current": 0, "total": 3, "preserved": 1},
        )
        self.assertEqual(adoption["preserved_count"], 1)
        self.assertEqual(
            adoption["preserved"][0]["path"],
            ".claude/skills/xc-drift/SKILL.md",
        )
        self.assertEqual(adoption["preserved"][0]["reason"], "legacy_drift")
        self.assertFalse(adoption["archive"]["performed"])
        self.assertIsNone(adoption["archive"]["directory"])
        self.assertEqual(
            adoption["archive"]["sources"],
            [".agents/.xc-skill-install-manifest.json"],
        )
        self.assertEqual(adoption["archive"]["archived"], [])
        self.assertEqual(
            [
                (entry["source"], entry["archived"], entry["reason"])
                for entry in adoption["archive"]["retained"]
            ],
            [
                (
                    ".claude/.xc-skill-install-manifest.json",
                    False,
                    "records-preserved",
                ),
            ],
        )
        self.assertEqual(
            adoption["archive"]["retained"][0]["preserved_reasons"],
            ["legacy_drift"],
        )
        actions = {
            operation["path"]: operation["action"]
            for operation in result["operations"]
        }
        self.assertEqual(
            actions[".agents/skills/xc-alpha/SKILL.md"],
            "unchanged",
        )
        self.assertEqual(
            actions[".claude/skills/xc-alpha/SKILL.md"],
            "replace",
        )
        self.assertEqual(
            actions[".agents/skills/xc-old/SKILL.md"],
            "remove",
        )
        self.assertNotIn(".claude/skills/xc-drift/SKILL.md", actions)
        self.assertEqual(
            before,
            {
                path.relative_to(self.home).as_posix(): path.read_bytes()
                for path in self.home.rglob("*")
                if path.is_file()
            },
        )

    def test_adopt_legacy_commits_claims_removals_and_archive(self) -> None:
        self.write_legacy_fixture()

        result = self.install_user(adopt_legacy=True)

        self.assertTrue(result["writes_performed"])
        adoption = result["adoption"]
        self.assertEqual(adoption["claims"]["legacy"], 3)
        self.assertEqual(adoption["counts"]["preserved"], 1)
        self.assertTrue(adoption["archive"]["performed"])
        self.assertEqual(
            adoption["archive"]["sources"],
            [".agents/.xc-skill-install-manifest.json"],
        )
        self.assertEqual(
            adoption["archive"]["archived"],
            [".agents/.xc-skill-install-manifest.json"],
        )
        self.assertEqual(
            [
                (entry["source"], entry["archived"], entry["reason"])
                for entry in adoption["archive"]["retained"]
            ],
            [
                (
                    ".claude/.xc-skill-install-manifest.json",
                    False,
                    "records-preserved",
                ),
            ],
        )
        archive = PurePosixPath(adoption["archive"]["directory"])
        state_directory = PurePosixPath(".agents/.xcoding-setup")
        self.assertTrue(
            archive.as_posix().startswith(".agents/.xcoding-setup-legacy-")
        )
        self.assertNotEqual(archive, state_directory)
        self.assertNotIn(state_directory, archive.parents)
        self.assertNotIn(".coding-setup/", archive.as_posix())
        self.assertTrue(
            self.target(
                self.home,
                f"{archive.as_posix()}/agents/.xc-skill-install-manifest.json",
            ).is_file()
        )
        self.assertFalse(
            self.target(
                self.home,
                f"{archive.as_posix()}/claude/.xc-skill-install-manifest.json",
            ).exists()
        )
        self.assertFalse(
            (self.home / ".agents" / ".xc-skill-install-manifest.json").exists()
        )
        self.assertTrue(
            (self.home / ".claude" / ".xc-skill-install-manifest.json").is_file()
        )
        self.assertFalse(
            self.target(self.home, ".agents/skills/xc-old/SKILL.md").exists()
        )
        self.assertEqual(
            self.target(
                self.home,
                ".claude/skills/xc-alpha/SKILL.md",
            ).read_bytes(),
            b"alpha\n",
        )
        self.assertEqual(
            self.target(
                self.home,
                ".claude/skills/xc-drift/SKILL.md",
            ).read_bytes(),
            b"drifted\n",
        )
        manifest = self.manifest()
        paths = {item["path"] for item in manifest["files"]}
        self.assertEqual(len(paths), 12)
        self.assertNotIn(".agents/skills/xc-old/SKILL.md", paths)
        self.assertNotIn(".claude/skills/xc-drift/SKILL.md", paths)
        self.assertEqual(
            [item["path"] for item in manifest["files"]].count(
                ".agents/skills/xc-alpha/SKILL.md"
            ),
            1,
        )

    def test_retired_package_cache_is_removed_after_adoption(self) -> None:
        self.write_legacy_fixture(drift=False)
        cache = self.write_file(
            self.home,
            ".agents/skills/xc-old/scripts/__pycache__/old.cpython-312.pyc",
            b"generated cache\n",
        )

        result = self.install_user(
            hosts=["claude-code", "codex"],
            adopt_legacy=True,
        )

        cleanup = result["adoption"]["cleanup"]
        self.assertEqual(cleanup["requested"], True)
        self.assertEqual(cleanup["status"], "complete")
        self.assertEqual(
            cleanup["retired_package_names"],
            ["xc-drift", "xc-old"],
        )
        self.assertEqual(
            cleanup["removed_cache_paths"],
            [".agents/skills/xc-old/scripts/__pycache__/old.cpython-312.pyc"],
        )
        self.assertEqual(cleanup["removed_cache_count"], 1)
        self.assertEqual(cleanup["preserved"], [])
        self.assertEqual(cleanup["errors"], [])
        self.assertIn(
            ".agents/skills/xc-old",
            cleanup["removed_directories"],
        )
        self.assertIn(
            ".agents/skills/xc-old/scripts/__pycache__",
            cleanup["removed_directories"],
        )
        self.assertFalse(cache.exists())
        self.assertFalse(
            self.target(self.home, ".agents/skills/xc-old").exists()
        )
        for root in (".agents/skills", ".claude/skills"):
            self.assertEqual(
                sorted(
                    item.name
                    for item in self.target(self.home, root).iterdir()
                    if item.is_dir()
                ),
                ["xc-alpha", "xc-delegation"],
                root,
            )

    def test_retired_package_unrecorded_file_is_preserved_and_reported(
        self,
    ) -> None:
        self.write_legacy_fixture(drift=False)
        cache = self.write_file(
            self.home,
            ".agents/skills/xc-old/scripts/__pycache__/old.cpython-312.pyc",
            b"generated cache\n",
        )
        notes = self.write_file(
            self.home,
            ".agents/skills/xc-old/user-notes.txt",
            b"user notes\n",
        )

        result = self.install_user(
            hosts=["claude-code", "codex"],
            adopt_legacy=True,
        )

        cleanup = result["adoption"]["cleanup"]
        self.assertEqual(cleanup["status"], "preserved")
        self.assertEqual(cleanup["errors"], [])
        self.assertFalse(cache.exists())
        self.assertTrue(notes.is_file())
        self.assertTrue(
            self.target(self.home, ".agents/skills/xc-old").is_dir()
        )
        unrecorded = [
            entry
            for entry in cleanup["preserved"]
            if entry["path"] == ".agents/skills/xc-old/user-notes.txt"
        ]
        self.assertEqual(len(unrecorded), 1)
        self.assertEqual(unrecorded[0]["reason"], "unrecorded")
        self.assertFalse(unrecorded[0]["recorded"])
        self.assertEqual(unrecorded[0]["package"], "xc-old")
        self.assertEqual(
            cleanup["preserved_count"],
            len(cleanup["preserved"]),
        )
        # The cleanup report is separate from the legacy-record preservation
        # report; an unrecorded file is not a preserved legacy record.
        self.assertNotIn(
            ".agents/skills/xc-old/user-notes.txt",
            [
                entry["path"]
                for entry in result["adoption"]["preserved"]
            ],
        )

    def test_adoption_cleanup_is_planned_in_dry_run(self) -> None:
        self.write_legacy_fixture(drift=False)

        result = self.install_user(
            hosts=["claude-code", "codex"],
            dry_run=True,
            adopt_legacy=True,
        )

        cleanup = result["adoption"]["cleanup"]
        self.assertEqual(cleanup["status"], "planned")
        self.assertEqual(
            cleanup["retired_package_names"],
            ["xc-drift", "xc-old"],
        )
        self.assertEqual(cleanup["removed_cache_paths"], [])
        self.assertEqual(cleanup["removed_directories"], [])
        self.assertEqual(cleanup["preserved"], [])
        self.assertFalse(result["writes_performed"])
        self.assertTrue(
            self.target(self.home, ".agents/skills/xc-old").is_dir()
        )

    def test_narrowed_host_adoption_retains_unselected_legacy_manifest(
        self,
    ) -> None:
        self.write_legacy_fixture(drift=False)
        agents_manifest = (
            self.home / ".agents" / ".xc-skill-install-manifest.json"
        )
        original_manifest = agents_manifest.read_bytes()

        result = self.install_user(hosts=["claude-code"], adopt_legacy=True)

        adoption = result["adoption"]
        self.assertTrue(adoption["requested"])
        retained_source = ".agents/.xc-skill-install-manifest.json"
        archived_source = ".claude/.xc-skill-install-manifest.json"
        self.assertEqual(adoption["archive"]["sources"], [archived_source])
        self.assertEqual(adoption["archive"]["archived"], [archived_source])
        self.assertEqual(
            [
                (entry["source"], entry["archived"], entry["reason"])
                for entry in adoption["archive"]["retained"]
            ],
            [(retained_source, False, "records-preserved")],
        )
        self.assertEqual(
            adoption["archive"]["retained"][0]["preserved_reasons"],
            ["host-not-selected"],
        )
        self.assertTrue(agents_manifest.is_file())
        self.assertEqual(agents_manifest.read_bytes(), original_manifest)
        self.assertFalse(
            (self.home / ".claude" / ".xc-skill-install-manifest.json").exists()
        )
        first_archive = PurePosixPath(adoption["archive"]["directory"])
        self.assertTrue(
            self.target(
                self.home,
                f"{first_archive.as_posix()}/claude/.xc-skill-install-manifest.json",
            ).is_file()
        )

        # The retained record is still readable, so the documented all-host
        # adoption can complete the migration afterwards.
        second = self.install_user(
            hosts=list(setup_module.HOST_ORDER),
            adopt_legacy=True,
        )

        second_adoption = second["adoption"]
        self.assertEqual(second_adoption["archive"]["sources"], [retained_source])
        self.assertTrue(second_adoption["archive"]["performed"])
        self.assertFalse(agents_manifest.exists())
        second_archive = PurePosixPath(second_adoption["archive"]["directory"])
        self.assertTrue(
            self.target(
                self.home,
                f"{second_archive.as_posix()}/agents/.xc-skill-install-manifest.json",
            ).is_file()
        )
        self.assertFalse(
            self.target(self.home, ".agents/skills/xc-old/SKILL.md").exists()
        )
        self.assertEqual(
            self.target(
                self.home,
                ".agents/skills/xc-alpha/SKILL.md",
            ).read_bytes(),
            b"alpha\n",
        )

    def test_all_host_adoption_archives_complete_manifests(self) -> None:
        self.write_legacy_fixture(drift=False)

        result = self.install_user(
            hosts=list(setup_module.HOST_ORDER),
            adopt_legacy=True,
        )

        adoption = result["adoption"]
        expected = [
            ".agents/.xc-skill-install-manifest.json",
            ".claude/.xc-skill-install-manifest.json",
        ]
        self.assertTrue(adoption["archive"]["performed"])
        self.assertEqual(adoption["archive"]["sources"], expected)
        self.assertEqual(adoption["archive"]["archived"], expected)
        self.assertEqual(adoption["archive"]["retained"], [])
        self.assertEqual(
            [entry["archived"] for entry in adoption["archive"]["manifests"]],
            [True, True],
        )
        archive = PurePosixPath(adoption["archive"]["directory"])
        for label in ("agents", "claude"):
            self.assertTrue(
                self.target(
                    self.home,
                    (
                        f"{archive.as_posix()}/{label}/"
                        ".xc-skill-install-manifest.json"
                    ),
                ).is_file()
            )
        for relative in expected:
            self.assertFalse(self.target(self.home, relative).exists())

    def test_drifted_record_keeps_its_legacy_manifest(self) -> None:
        self.write_legacy_manifest(
            self.home,
            "agents",
            ["xc-alpha", "xc-drift"],
            {
                "xc-alpha/SKILL.md": b"alpha\n",
                "xc-drift/SKILL.md": b"original\n",
            },
        )
        self.write_file(
            self.home,
            ".agents/skills/xc-alpha/SKILL.md",
            b"alpha\n",
        )
        self.write_file(
            self.home,
            ".agents/skills/xc-drift/SKILL.md",
            b"drifted\n",
        )

        result = self.install_user(
            hosts=list(setup_module.HOST_ORDER),
            adopt_legacy=True,
        )

        adoption = result["adoption"]
        self.assertEqual(adoption["counts"]["preserved"], 1)
        self.assertFalse(adoption["archive"]["performed"])
        self.assertIsNone(adoption["archive"]["directory"])
        self.assertEqual(adoption["archive"]["sources"], [])
        self.assertEqual(
            [
                (entry["source"], entry["archived"], entry["reason"])
                for entry in adoption["archive"]["retained"]
            ],
            [
                (
                    ".agents/.xc-skill-install-manifest.json",
                    False,
                    "records-preserved",
                ),
            ],
        )
        self.assertEqual(
            adoption["archive"]["retained"][0]["preserved_reasons"],
            ["legacy_drift"],
        )
        self.assertTrue(
            (self.home / ".agents" / ".xc-skill-install-manifest.json").is_file()
        )
        self.assertEqual(
            self.target(
                self.home,
                ".agents/skills/xc-drift/SKILL.md",
            ).read_bytes(),
            b"drifted\n",
        )

    def test_apply_failure_carries_the_adoption_summary(self) -> None:
        self.write_legacy_fixture(drift=False)

        def fail(stage: str, details: object) -> None:
            if stage == "operation-applied":
                raise setup_module.SetupTransactionError(
                    "path_identity_changed",
                    "injected apply failure",
                )

        with mock.patch.object(setup_module, "_transaction_test_hook", fail):
            with self.assertRaises(setup_module.SetupTransactionError) as raised:
                self.install_user(
                    hosts=list(setup_module.HOST_ORDER),
                    adopt_legacy=True,
                )

        error = raised.exception
        self.assertEqual(error.code, "path_identity_changed")
        self.assertTrue(error.details["rolled_back"])
        self.assertEqual(error.details["phase"], "apply")
        adoption = error.details["adoption"]
        self.assertTrue(adoption["requested"])
        self.assertEqual(adoption["claims"]["legacy"], 3)
        self.assertEqual(adoption["counts"]["preserved"], 0)
        self.assertFalse(adoption["archive"]["performed"])
        for relative in (
            ".agents/.xc-skill-install-manifest.json",
            ".claude/.xc-skill-install-manifest.json",
        ):
            self.assertTrue(self.target(self.home, relative).is_file(), relative)


class UninstallTests(LifecycleTestBase):
    def test_uninstall_removes_verified_files_and_preserves_modified_and_unowned(
        self,
    ) -> None:
        self.install_user()
        generation = self.manifest()["generation"]
        modified = self.target(
            self.home,
            ".claude/skills/xc-alpha/SKILL.md",
        )
        modified.write_bytes(b"user-modified\n")
        lark = self.write_file(
            self.home,
            ".agents/skills/lark-like/SKILL.md",
            b"lark-owned\n",
        )

        result = lifecycle_module.uninstall("user")

        self.assertEqual(result["scope"], "user")
        self.assertTrue(result["installed"])
        self.assertTrue(result["writes_performed"])
        self.assertEqual(result["generation"], generation)
        self.assertEqual(
            result["counts"],
            {"remove": 11, "preserve": 1, "missing": 0, "total": 12},
        )
        self.assertEqual((result["removed"], result["preserved"]), (11, 1))
        self.assertEqual(
            [operation["action"] for operation in result["operations"]].count(
                "preserve"
            ),
            1,
        )
        self.assertFalse(
            self.target(self.home, ".agents/skills/xc-alpha/SKILL.md").exists()
        )
        self.assertFalse(
            self.target(self.home, ".agents/skills/xc-alpha").exists()
        )
        self.assertTrue(self.target(self.home, ".agents/skills").is_dir())
        self.assertEqual(lark.read_bytes(), b"lark-owned\n")
        self.assertEqual(modified.read_bytes(), b"user-modified\n")
        self.assertFalse(
            (self.home / ".agents" / ".xcoding-setup").exists()
        )
        archive = (
            self.home
            / ".agents"
            / f".xcoding-setup-uninstalled-{generation}"
        )
        self.assertTrue(archive.is_dir())
        self.assertTrue((archive / "manifest.json").is_file())
        self.assertTrue((archive / "backup").is_dir())
        self.assertEqual(
            Path(str(result["archive_path"])).resolve(),
            archive.resolve(),
        )
        self.assertTrue(result["state_archive"]["performed"])
        self.assertTrue(result["state_archive"]["keep_state"])

    def test_uninstall_keep_state_false_writes_receipt_and_drops_backup(self) -> None:
        self.install_user()
        generation = self.manifest()["generation"]

        result = lifecycle_module.uninstall("user", keep_state=False)

        self.assertFalse(result["state_archive"]["keep_state"])
        archive = (
            self.home
            / ".agents"
            / f".xcoding-setup-uninstalled-{generation}"
        )
        receipt = json.loads(
            (archive / "receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["kind"], "xcoding-uninstall-receipt")
        self.assertEqual(receipt["generation"], generation)
        self.assertEqual(receipt["removed"], 12)
        self.assertFalse((archive / "backup").exists())
        self.assertFalse((archive / "staging").exists())
        self.assertEqual(
            result["state_archive"]["receipt"],
            f".agents/.xcoding-setup-uninstalled-{generation}/receipt.json",
        )

    def test_second_uninstall_is_a_noop(self) -> None:
        self.install_user()
        generation = self.manifest()["generation"]
        first = lifecycle_module.uninstall("user")

        second = lifecycle_module.uninstall("user")

        self.assertTrue(first["installed"])
        self.assertFalse(second["installed"])
        self.assertFalse(second["writes_performed"])
        self.assertEqual(second["operations"], [])
        self.assertEqual(
            second["counts"],
            {"remove": 0, "preserve": 0, "missing": 0, "total": 0},
        )
        self.assertFalse(second["state_archive"]["performed"])
        self.assertIsNone(second["archive_path"])
        self.assertTrue(
            (
                self.home
                / ".agents"
                / f".xcoding-setup-uninstalled-{generation}"
            ).is_dir()
        )

    def test_uninstall_legacy_only_root_fails_with_legacy_payload_present(
        self,
    ) -> None:
        self.write_legacy_fixture(drift=False)
        agents_manifest = (
            self.home / ".agents" / ".xc-skill-install-manifest.json"
        )
        original_manifest = agents_manifest.read_bytes()

        with self.assertRaises(setup_module.SetupTransactionError) as raised:
            lifecycle_module.uninstall("user")

        error = raised.exception
        self.assertEqual(error.code, "legacy_payload_present")
        self.assertTrue(error.details["legacy"]["detected"])
        self.assertEqual(
            error.details["legacy"]["manifest_paths"],
            [
                ".agents/.xc-skill-install-manifest.json",
                ".claude/.xc-skill-install-manifest.json",
            ],
        )
        self.assertEqual(
            error.details["next_action"],
            "xcoding install --scope user --adopt-legacy, then xcoding uninstall",
        )
        self.assertTrue(agents_manifest.is_file())
        self.assertEqual(agents_manifest.read_bytes(), original_manifest)
        self.assertTrue(
            self.target(
                self.home,
                ".agents/skills/xc-alpha/SKILL.md",
            ).is_file()
        )
        self.assertFalse(self.manifest_path().exists())
        self.assertFalse((self.home / ".agents" / ".xcoding-setup").exists())

    def test_uninstall_clean_root_remains_a_noop(self) -> None:
        result = lifecycle_module.uninstall("user")

        self.assertFalse(result["installed"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["operations"], [])
        self.assertIsNone(result["archive_path"])
        self.assertFalse(result["state_archive"]["performed"])
        self.assertFalse((self.home / ".agents").exists())

    def test_uninstall_cli_legacy_only_exits_readiness_without_cli_removal(
        self,
    ) -> None:
        self.write_legacy_fixture(drift=False)

        with mock.patch.object(cli_module, "_uninstall_cli") as cli_removal:
            code, payload = self.run_cli(["uninstall", "--json", "--all"])

        self.assertEqual(code, cli_module.EXIT_READINESS)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "legacy_payload_present")
        self.assertEqual(
            payload["error"]["details"]["next_action"],
            "xcoding install --scope user --adopt-legacy, then xcoding uninstall",
        )
        cli_removal.assert_not_called()

    def test_uninstall_refuses_an_open_journal(self) -> None:
        journal = (
            self.home / ".agents" / ".xcoding-setup" / "journal.json"
        )
        journal.parent.mkdir(parents=True)
        journal.write_bytes(
            setup_module._canonical_json(
                {"schema_version": 1, "state": "preparing"}
            )
        )

        with self.assertRaises(setup_module.SetupTransactionError) as raised:
            lifecycle_module.uninstall("user")

        self.assertEqual(raised.exception.code, "recovery_required")
        self.assertTrue(journal.is_file())
        self.assertFalse(self.manifest_path().exists())


class DoctorPayloadTests(LifecycleTestBase):
    def test_payload_readiness_not_installed(self) -> None:
        self.assertEqual(
            doctor_module.payload_readiness(self.home),
            {"installed": False, "status": "not-installed"},
        )

    def test_payload_readiness_marks_an_agents_only_legacy_tree_as_drift(
        self,
    ) -> None:
        alpha = b"alpha\n"
        self.write_file(self.home, ".agents/skills/xc-alpha/SKILL.md", alpha)
        self.write_legacy_manifest(
            self.home,
            "agents",
            ["xc-alpha"],
            {"xc-alpha/SKILL.md": alpha},
        )

        payload = doctor_module.payload_readiness(self.home)

        self.assertFalse(payload["installed"])
        self.assertEqual(payload["status"], "legacy")
        legacy = payload["legacy"]
        self.assertTrue(legacy["detected"])
        self.assertEqual(
            legacy["manifest_paths"],
            [".agents/.xc-skill-install-manifest.json"],
        )
        self.assertEqual(legacy["source_revisions"], ["fixture-legacy"])
        self.assertEqual(
            legacy["package_counts"],
            {"total": 1, "by_manifest": {"agents": 1, "claude": 0}},
        )
        self.assertEqual(
            legacy["file_counts"],
            {"total": 1, "by_manifest": {"agents": 1, "claude": 0}},
        )
        self.assertEqual(legacy["errors"], [])
        self.assertEqual(
            [problem["code"] for problem in payload["problems"]],
            ["legacy-install-detected"],
        )
        self.assertIn(
            "xcoding install --scope user --adopt-legacy",
            payload["next_action"],
        )
        # Detection is read-only: no setup state and no adoption happened.
        self.assertFalse((self.home / ".agents" / ".xcoding-setup").exists())

    def test_legacy_install_status_summarizes_both_manifests_read_only(
        self,
    ) -> None:
        self.write_legacy_fixture()
        recorded = {
            path: path.read_bytes()
            for path in (
                self.home / ".agents" / ".xc-skill-install-manifest.json",
                self.home / ".claude" / ".xc-skill-install-manifest.json",
            )
        }

        status = setup_module.legacy_install_status(self.home)

        self.assertTrue(status["detected"])
        self.assertEqual(
            status["manifest_paths"],
            [
                ".agents/.xc-skill-install-manifest.json",
                ".claude/.xc-skill-install-manifest.json",
            ],
        )
        self.assertEqual(status["source_revisions"], ["fixture-legacy"])
        self.assertEqual(status["package_counts"]["total"], 4)
        self.assertEqual(status["file_counts"]["total"], 4)
        self.assertEqual(
            [entry["package_count"] for entry in status["manifests"]],
            [2, 2],
        )
        self.assertEqual(status["errors"], [])
        for path, data in recorded.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertFalse((self.home / ".agents" / ".xcoding-setup").exists())

        payload = doctor_module.payload_readiness(self.home)
        self.assertEqual(payload["status"], "legacy")
        self.assertEqual(len(payload["legacy"]["manifest_paths"]), 2)

    def test_malformed_legacy_manifest_is_reported_per_manifest(self) -> None:
        cases = {
            "invalid-json": b"{not json\n",
            "missing-installer-version": setup_module._canonical_json(
                {
                    "schema_version": 1,
                    "source_revision": "fixture-legacy",
                    "expected_packages": ["xc-alpha"],
                    "files": [],
                }
            ),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                root = self.base / f"legacy-{name}"
                root.mkdir()
                self.write_file(
                    root,
                    ".agents/.xc-skill-install-manifest.json",
                    data,
                )

                payload = doctor_module.payload_readiness(root)

                self.assertFalse(payload["installed"])
                self.assertEqual(payload["status"], "legacy")
                legacy = payload["legacy"]
                self.assertTrue(legacy["detected"])
                self.assertEqual(
                    legacy["manifest_paths"],
                    [".agents/.xc-skill-install-manifest.json"],
                )
                self.assertEqual(len(legacy["errors"]), 1)
                error = legacy["errors"][0]
                self.assertEqual(error["code"], "legacy_manifest_invalid")
                self.assertEqual(
                    error["path"],
                    ".agents/.xc-skill-install-manifest.json",
                )
                self.assertEqual(
                    legacy["manifests"][0]["error"]["code"],
                    "legacy_manifest_invalid",
                )
                self.assertEqual(
                    payload["problems"][0]["code"],
                    "legacy-install-detected",
                )

    def test_doctor_report_fails_for_legacy_only_but_warns_for_clean(
        self,
    ) -> None:
        with mock.patch.object(
            doctor_module.shutil,
            "which",
            side_effect=lambda name: f"/fake/{name}",
        ):
            clean = doctor_module.doctor_report(self.home)
            self.assertTrue(clean["ready"])
            payload = next(
                check
                for check in clean["checks"]
                if check["id"] == "payload"
            )
            self.assertFalse(payload["required"])
            self.assertEqual(payload["status"], "not-installed")
            self.assertIn(
                "payload-not-installed",
                {warning["code"] for warning in clean["warnings"]},
            )

            alpha = b"alpha\n"
            self.write_file(
                self.home,
                ".agents/skills/xc-alpha/SKILL.md",
                alpha,
            )
            self.write_legacy_manifest(
                self.home,
                "agents",
                ["xc-alpha"],
                {"xc-alpha/SKILL.md": alpha},
            )
            with self.assertRaises(
                doctor_module.DoctorReadinessError
            ) as raised:
                doctor_module.doctor_report(self.home)

        report = raised.exception.details["report"]
        self.assertFalse(report["ready"])
        payload = next(
            check for check in report["checks"] if check["id"] == "payload"
        )
        self.assertTrue(payload["required"])
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["details"]["status"], "legacy")
        self.assertEqual(
            payload["details"]["problems"][0]["code"],
            "legacy-install-detected",
        )

        code, envelope = self.run_cli(
            ["doctor", "--target-root", str(self.home), "--json"]
        )
        self.assertEqual(code, 4)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["error"]["code"], "readiness-failed")
        payload = next(
            check
            for check in envelope["error"]["details"]["report"]["checks"]
            if check["id"] == "payload"
        )
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["details"]["status"], "legacy")

    def test_payload_readiness_current_verifies_every_owned_file(self) -> None:
        self.install_user()

        payload = doctor_module.payload_readiness(
            self.home,
            inspection=self.inspection,
        )

        self.assertTrue(payload["installed"])
        self.assertEqual(payload["status"], "current")
        self.assertTrue(payload["version_matches"])
        self.assertTrue(payload["bundle_matches"])
        self.assertEqual(
            payload["counts"],
            {"total": 12, "verified": 12, "modified": 0, "missing": 0},
        )
        self.assertEqual(
            payload["kinds"],
            {"skill": 10, "agent-definition": 2},
        )
        self.assertEqual(payload["problems"], [])
        self.assertEqual(payload["hosts"], ["claude-code", "codex"])

    def test_payload_readiness_is_stale_on_version_or_bundle_mismatch(self) -> None:
        self.install_user()
        original = self.manifest()
        for field, value in (
            ("version", "9.9.9"),
            ("bundle_manifest_sha256", "b" * 64),
        ):
            with self.subTest(field=field):
                changed = dict(original)
                changed[field] = value
                self.manifest_path().write_bytes(
                    setup_module._canonical_json(changed)
                )

                payload = doctor_module.payload_readiness(
                    self.home,
                    inspection=self.inspection,
                )

                self.assertEqual(payload["status"], "stale")
                self.assertEqual(payload["problems"], [])
                if field == "version":
                    self.assertFalse(payload["version_matches"])
                    self.assertTrue(payload["bundle_matches"])
                else:
                    self.assertTrue(payload["version_matches"])
                    self.assertFalse(payload["bundle_matches"])
                self.manifest_path().write_bytes(
                    setup_module._canonical_json(original)
                )

    def test_payload_readiness_reports_modified_and_missing_files(self) -> None:
        for state in ("modified", "missing"):
            with self.subTest(state=state):
                root = self.base / f"payload-{state}"
                root.mkdir()
                setup_module.setup(root, ["claude-code", "codex"])
                relative = ".claude/skills/xc-alpha/SKILL.md"
                if state == "modified":
                    self.target(root, relative).write_bytes(b"changed\n")
                else:
                    self.target(root, relative).unlink()

                payload = doctor_module.payload_readiness(
                    root,
                    inspection=self.inspection,
                )

                self.assertTrue(payload["installed"])
                self.assertEqual(payload["status"], state)
                self.assertEqual(payload["counts"][state], 1)
                self.assertEqual(
                    [problem["status"] for problem in payload["problems"]],
                    [state],
                )
                self.assertEqual(
                    payload["problems"][0]["path"],
                    relative,
                )

    def test_doctor_report_fails_only_when_installed_payload_is_not_current(
        self,
    ) -> None:
        with mock.patch.object(
            doctor_module.shutil,
            "which",
            side_effect=lambda name: f"/fake/{name}",
        ):
            report = doctor_module.doctor_report(self.home)
            self.assertTrue(report["ready"])
            payload = next(
                check for check in report["checks"] if check["id"] == "payload"
            )
            self.assertFalse(payload["required"])
            self.assertEqual(payload["status"], "not-installed")
            self.assertIn(
                "payload-not-installed",
                {warning["code"] for warning in report["warnings"]},
            )

            self.install_user()

            report = doctor_module.doctor_report(self.home)
            self.assertTrue(report["ready"])
            payload = next(
                check for check in report["checks"] if check["id"] == "payload"
            )
            self.assertTrue(payload["required"])
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["details"]["status"], "current")

            manifest = self.manifest()
            manifest["version"] = "9.9.9"
            self.manifest_path().write_bytes(
                setup_module._canonical_json(manifest)
            )
            with self.assertRaises(doctor_module.DoctorReadinessError) as raised:
                doctor_module.doctor_report(self.home)
            failed = raised.exception.details["report"]
            self.assertFalse(failed["ready"])
            payload = next(
                check for check in failed["checks"] if check["id"] == "payload"
            )
            self.assertEqual(payload["status"], "fail")
            self.assertEqual(payload["details"]["status"], "stale")

            no_target = doctor_module.doctor_report(None)
            payload = next(
                check
                for check in no_target["checks"]
                if check["id"] == "payload"
            )
            self.assertFalse(payload["required"])
            self.assertEqual(payload["status"], "not-requested")


class LifecycleGuardTests(LifecycleTestBase):
    def test_scope_and_root_guards(self) -> None:
        with self.assertRaises(lifecycle_module.LifecycleError) as unknown:
            lifecycle_module.install("bogus", hosts=["codex"])
        self.assertEqual(unknown.exception.code, "scope_unknown")
        self.assertEqual(
            unknown.exception.details["available"],
            ["user", "project"],
        )

        with self.assertRaises(lifecycle_module.LifecycleError) as required:
            lifecycle_module.install("project", hosts=["codex"])
        self.assertEqual(required.exception.code, "project_root_required")

        with self.assertRaises(lifecycle_module.LifecycleError) as forbidden:
            lifecycle_module.install(
                "user",
                project_root=str(self.project),
                hosts=["codex"],
            )
        self.assertEqual(forbidden.exception.code, "project_root_not_allowed")

        with self.assertRaises(lifecycle_module.LifecycleError) as missing:
            lifecycle_module.uninstall("project")
        self.assertEqual(missing.exception.code, "project_root_required")

    def test_host_guards(self) -> None:
        with self.assertRaises(lifecycle_module.LifecycleError) as unknown:
            lifecycle_module.install("user", hosts=["unknown-host"])
        self.assertEqual(unknown.exception.code, "host_unknown")
        self.assertEqual(unknown.exception.details["unknown"], ["unknown-host"])

        with self.assertRaises(lifecycle_module.LifecycleError) as empty:
            lifecycle_module.install("user", hosts=[])
        self.assertEqual(empty.exception.code, "host_required")

    def test_adopt_legacy_is_user_scope_only(self) -> None:
        with self.assertRaises(lifecycle_module.LifecycleError) as raised:
            lifecycle_module.install(
                "project",
                project_root=str(self.project),
                hosts=["codex"],
                adopt_legacy=True,
            )
        self.assertEqual(
            raised.exception.code,
            "adopt_legacy_requires_user_scope",
        )
        self.assertEqual(raised.exception.details["scope"], "project")

        with self.assertRaises(lifecycle_module.LifecycleError) as upgrade:
            lifecycle_module.upgrade(
                "project",
                project_root=str(self.project),
                hosts=["codex"],
                adopt_legacy=True,
            )
        self.assertEqual(
            upgrade.exception.code,
            "adopt_legacy_requires_user_scope",
        )


class UpgradeTests(LifecycleTestBase):
    def make_wheel(
        self,
        version: str,
        name: str = "xcoding_workflow",
        distribution: str = "xcoding-workflow",
    ) -> Path:
        path = self.base / f"{name}-{version}.whl"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                f"{name}-{version}.dist-info/METADATA",
                (
                    "Metadata-Version: 2.1\n"
                    f"Name: {distribution}\n"
                    f"Version: {version}\n"
                ),
            )
        return path

    def test_wheel_validation_rejects_invalid_archives(self) -> None:
        missing = self.base / "missing.whl"
        not_zip = self.base / "broken.whl"
        not_zip.write_bytes(b"not a zip archive\n")
        no_metadata = self.base / "no-metadata.whl"
        with zipfile.ZipFile(no_metadata, "w") as archive:
            archive.writestr("README.txt", "nothing\n")
        not_a_file = self.base / "directory.whl"
        not_a_file.mkdir()

        for path in (missing, not_zip, no_metadata, not_a_file):
            with self.subTest(wheel=path.name):
                with self.assertRaises(
                    lifecycle_module.LifecycleError
                ) as raised:
                    lifecycle_module.upgrade(
                        "user",
                        hosts=["codex"],
                        wheel=str(path),
                    )
                self.assertEqual(raised.exception.code, "wheel_invalid")

    def test_wheel_validation_rejects_an_unrelated_distribution(self) -> None:
        wheel = self.make_wheel("9.9.9", distribution="some-other-package")

        with self.assertRaises(lifecycle_module.LifecycleError) as raised:
            lifecycle_module.upgrade(
                "user",
                hosts=["codex"],
                wheel=str(wheel),
            )

        self.assertEqual(raised.exception.code, "wheel_invalid")
        self.assertEqual(raised.exception.details["name"], "some-other-package")

    def test_wheel_name_matching_is_normalized(self) -> None:
        wheel = self.make_wheel("9.9.9", distribution="Xcoding_Workflow")
        with mock.patch.object(
            lifecycle_module.shutil,
            "which",
            return_value=None,
        ):
            with self.assertRaises(lifecycle_module.LifecycleError) as raised:
                lifecycle_module.upgrade(
                    "user",
                    hosts=["codex"],
                    wheel=str(wheel),
                )

        # The normalized name is accepted, so the failure comes from the
        # missing uv executable rather than from wheel validation.
        self.assertEqual(raised.exception.code, "uv_unavailable")

    def test_equal_version_wheel_skips_uv_and_reconciles_payload(self) -> None:
        wheel = self.make_wheel("0.1.0")
        with (
            mock.patch.object(
                lifecycle_module,
                "install",
                return_value={
                    "root": str(self.home),
                    "operations": [{"action": "unchanged"}],
                    "writes_performed": False,
                },
            ) as install_mock,
            mock.patch.object(lifecycle_module.shutil, "which") as which,
        ):
            result = lifecycle_module.upgrade(
                "user",
                hosts=["codex"],
                wheel=str(wheel),
            )

        self.assertEqual(result["status"], "up-to-date")
        self.assertEqual(result["cli"]["step"], "skipped-equal-version")
        self.assertFalse(result["writes_performed"])
        install_mock.assert_called_once()
        which.assert_not_called()

    def test_uv_absent_fails_before_any_payload_write(self) -> None:
        wheel = self.make_wheel("9.9.9")
        with (
            mock.patch.object(lifecycle_module.shutil, "which", return_value=None),
            mock.patch.object(lifecycle_module, "install") as install_mock,
        ):
            with self.assertRaises(lifecycle_module.LifecycleError) as raised:
                lifecycle_module.upgrade(
                    "user",
                    hosts=["codex"],
                    wheel=str(wheel),
                )

        self.assertEqual(raised.exception.code, "uv_unavailable")
        install_mock.assert_not_called()

    def test_file_in_use_failure_is_classified_as_external_step(self) -> None:
        wheel = self.make_wheel("9.9.9")
        with (
            mock.patch.object(
                lifecycle_module.shutil,
                "which",
                return_value="C:\\fake\\uv.exe",
            ),
            mock.patch.object(
                lifecycle_module.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="Access is denied. (os error 32)",
                ),
            ),
            mock.patch.object(lifecycle_module, "install") as install_mock,
        ):
            with self.assertRaises(lifecycle_module.LifecycleError) as raised:
                lifecycle_module.upgrade(
                    "user",
                    hosts=["codex"],
                    wheel=str(wheel),
                )

        self.assertEqual(
            raised.exception.code,
            "cli_upgrade_requires_external_step",
        )
        self.assertEqual(raised.exception.details["signature"], "access is denied")
        self.assertEqual(
            raised.exception.details["uv"]["returncode"],
            1,
        )
        install_mock.assert_not_called()

    def test_payload_failure_after_cli_upgrade_is_never_success(self) -> None:
        wheel = self.make_wheel("9.9.9")
        cli_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        payload_cases = (
            SimpleNamespace(returncode=1, stdout="", stderr="payload failed"),
            SimpleNamespace(returncode=0, stdout="not json", stderr=""),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {"ok": False, "error": {"code": "payload_error"}}
                ),
                stderr="",
            ),
        )
        for payload_result in payload_cases:
            with self.subTest(result=payload_result.returncode):
                with (
                    mock.patch.object(
                        lifecycle_module.shutil,
                        "which",
                        side_effect=lambda name: f"C:\\fake\\{name}.exe",
                    ),
                    mock.patch.object(
                        lifecycle_module.subprocess,
                        "run",
                        side_effect=[cli_ok, payload_result],
                    ),
                    mock.patch.object(
                        lifecycle_module,
                        "install",
                    ) as install_mock,
                ):
                    with self.assertRaises(
                        lifecycle_module.LifecycleError
                    ) as raised:
                        lifecycle_module.upgrade(
                            "user",
                            hosts=["codex"],
                            wheel=str(wheel),
                        )

                self.assertEqual(
                    raised.exception.code,
                    "cli_upgraded_payload_failed",
                )
                self.assertIn("cli", raised.exception.details)
                install_mock.assert_not_called()

    def test_payload_envelope_with_old_version_is_never_success(self) -> None:
        wheel = self.make_wheel("9.9.9")
        cli_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        envelope = {
            "ok": True,
            "result": {
                "project_root": str(self.home),
                "version": "0.1.0",
                "writes_performed": True,
                "bundle_manifest_sha256": "b" * 64,
            },
        }
        payload_ok = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )
        with (
            mock.patch.object(
                lifecycle_module.shutil,
                "which",
                side_effect=lambda name: f"C:\\fake\\{name}.exe",
            ),
            mock.patch.object(
                lifecycle_module.subprocess,
                "run",
                side_effect=[cli_ok, payload_ok],
            ),
        ):
            code, payload = self.run_cli(
                [
                    "upgrade",
                    "--scope",
                    "user",
                    "--host",
                    "codex",
                    "--wheel",
                    str(wheel),
                    "--json",
                ]
            )

        self.assertEqual(code, cli_module.EXIT_READINESS)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["code"],
            "cli_upgraded_payload_failed",
        )
        details = payload["error"]["details"]
        self.assertIn("uv", details)
        self.assertIn("cli", details)
        self.assertEqual(
            details["verification"]["version"],
            {"expected": "9.9.9", "actual": "0.1.0"},
        )

    def test_payload_envelope_with_unchanged_bundle_is_never_success(self) -> None:
        wheel = self.make_wheel("9.9.9")
        cli_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        envelope = {
            "ok": True,
            "result": {
                "project_root": str(self.home),
                "version": "9.9.9",
                "writes_performed": True,
                "bundle_manifest_sha256": "a" * 64,
            },
        }
        payload_ok = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )
        with (
            mock.patch.object(
                lifecycle_module.shutil,
                "which",
                side_effect=lambda name: f"C:\\fake\\{name}.exe",
            ),
            mock.patch.object(
                lifecycle_module.subprocess,
                "run",
                side_effect=[cli_ok, payload_ok],
            ),
        ):
            with self.assertRaises(lifecycle_module.LifecycleError) as raised:
                lifecycle_module.upgrade(
                    "user",
                    hosts=["codex"],
                    wheel=str(wheel),
                )

        self.assertEqual(
            raised.exception.code,
            "cli_upgraded_payload_failed",
        )
        self.assertEqual(
            raised.exception.details["verification"][
                "bundle_manifest_sha256"
            ],
            {
                "expected_different_from": "a" * 64,
                "expected_any": None,
                "actual": "a" * 64,
            },
        )

    def test_upgrade_success_runs_uv_then_the_installed_cli(self) -> None:
        wheel = self.make_wheel("9.9.9")
        cli_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        envelope = {
            "ok": True,
            "result": {
                "project_root": str(self.home),
                "version": "9.9.9",
                "writes_performed": True,
                "bundle_manifest_sha256": "b" * 64,
            },
        }
        payload_ok = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )
        with (
            mock.patch.object(
                lifecycle_module.shutil,
                "which",
                side_effect=lambda name: f"C:\\fake\\{name}.exe",
            ),
            mock.patch.object(
                lifecycle_module.subprocess,
                "run",
                side_effect=[cli_ok, payload_ok],
            ) as run_mock,
        ):
            result = lifecycle_module.upgrade(
                "user",
                hosts=["codex"],
                wheel=str(wheel),
            )

        self.assertEqual(result["status"], "upgraded")
        self.assertEqual(result["version"], "9.9.9")
        self.assertTrue(result["writes_performed"])
        self.assertEqual(result["cli"]["step"], "uv-tool-install")
        self.assertEqual(run_mock.call_count, 2)
        payload_command = run_mock.call_args_list[1].args[0]
        self.assertEqual(payload_command[1:4], ["install", "--scope", "user"])
        self.assertIn("--host", payload_command)
        self.assertIn("codex", payload_command)
        # A user-scope upgrade must not adopt the legacy layout unless the
        # caller passed the explicit flag.
        self.assertNotIn("--adopt-legacy", payload_command)

    def test_upgrade_with_adopt_legacy_flag_passes_it_to_the_payload_phase(
        self,
    ) -> None:
        wheel = self.make_wheel("9.9.9")
        cli_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        envelope = {
            "ok": True,
            "result": {
                "project_root": str(self.home),
                "version": "9.9.9",
                "writes_performed": True,
                "bundle_manifest_sha256": "b" * 64,
            },
        }
        payload_ok = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )
        with (
            mock.patch.object(
                lifecycle_module.shutil,
                "which",
                side_effect=lambda name: f"C:\\fake\\{name}.exe",
            ),
            mock.patch.object(
                lifecycle_module.subprocess,
                "run",
                side_effect=[cli_ok, payload_ok],
            ) as run_mock,
        ):
            result = lifecycle_module.upgrade(
                "user",
                hosts=["codex"],
                wheel=str(wheel),
                adopt_legacy=True,
            )

        self.assertEqual(result["status"], "upgraded")
        payload_command = run_mock.call_args_list[1].args[0]
        self.assertIn("--adopt-legacy", payload_command)

    def test_user_scope_upgrade_needs_the_explicit_adopt_flag(self) -> None:
        self.write_legacy_fixture()
        agents_manifest = (
            self.home / ".agents" / ".xc-skill-install-manifest.json"
        )
        original_manifest = agents_manifest.read_bytes()

        # Without the explicit flag the payload phase never adopts: the
        # unowned legacy bytes that collide with the desired Bundle fail
        # closed instead of being claimed or deleted.
        with self.assertRaises(setup_module.SetupTransactionError) as raised:
            lifecycle_module.upgrade("user", hosts=["codex"])

        self.assertEqual(raised.exception.code, "unmanaged_conflict")
        self.assertTrue(agents_manifest.is_file())
        self.assertEqual(agents_manifest.read_bytes(), original_manifest)
        self.assertFalse(self.manifest_path().exists())
        self.assertTrue(
            self.target(
                self.home,
                ".agents/skills/xc-old/SKILL.md",
            ).is_file()
        )

        adopted = lifecycle_module.upgrade(
            "user",
            hosts=["codex"],
            adopt_legacy=True,
        )

        self.assertTrue(adopted["payload"]["adoption"]["requested"])
        self.assertEqual(adopted["payload"]["adoption"]["claims"]["legacy"], 2)
        self.assertFalse(agents_manifest.exists())
        self.assertFalse(
            self.target(
                self.home,
                ".agents/skills/xc-old/SKILL.md",
            ).exists()
        )


class CliLifecycleTests(LifecycleTestBase):
    def test_root_help_lists_install_upgrade_and_uninstall(self) -> None:
        code, payload = self.run_cli(["--help"])

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertEqual(payload["command"], "help")
        commands = {
            entry["command"] for entry in payload["result"]["commands"]
        }
        self.assertLessEqual(
            {"install", "upgrade", "uninstall"},
            commands,
        )
        summaries = {
            entry["command"]: entry["summary"]
            for entry in payload["result"]["commands"]
        }
        for command in ("install", "upgrade", "uninstall"):
            self.assertTrue(summaries[command].strip())

    def test_lifecycle_commands_require_explicit_json(self) -> None:
        cases = (
            (["install"], "install"),
            (["upgrade"], "upgrade"),
            (["uninstall"], "uninstall"),
        )
        for arguments, command in cases:
            with self.subTest(command=command):
                with (
                    mock.patch.object(cli_module.lifecycle, "install") as install,
                    mock.patch.object(cli_module.lifecycle, "upgrade") as upgrade,
                    mock.patch.object(
                        cli_module.lifecycle, "uninstall"
                    ) as uninstall,
                ):
                    code, payload = self.run_cli(arguments)
                self.assertEqual(code, cli_module.EXIT_INPUT)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["command"], command)
                self.assertEqual(payload["error"]["code"], "json-required")
                install.assert_not_called()
                upgrade.assert_not_called()
                uninstall.assert_not_called()

    def test_install_project_scope_requires_an_explicit_root(self) -> None:
        code, payload = self.run_cli(
            ["install", "--scope", "project", "--json"]
        )

        self.assertEqual(code, cli_module.EXIT_READINESS)
        self.assertEqual(payload["command"], "install")
        self.assertEqual(
            payload["error"]["code"],
            "project_root_required",
        )

    def test_invalid_scope_is_an_input_error(self) -> None:
        for command in ("install", "upgrade", "uninstall"):
            with self.subTest(command=command):
                code, payload = self.run_cli(
                    [command, "--scope", "bogus", "--json"]
                )
                self.assertEqual(code, cli_module.EXIT_INPUT)
                self.assertEqual(
                    payload["error"]["code"],
                    "invalid_arguments",
                )

    def test_install_dispatch_passes_every_lifecycle_argument(self) -> None:
        with mock.patch.object(
            cli_module.lifecycle,
            "install",
            return_value={"writes_performed": False},
        ) as installed:
            code, payload = self.run_cli(
                [
                    "install",
                    "--json",
                    "--dry-run",
                    "--host",
                    "claude-code",
                    "--adopt-legacy",
                ]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertTrue(payload["ok"])
        installed.assert_called_once_with(
            scope="user",
            project_root=None,
            hosts=["claude-code"],
            dry_run=True,
            adopt_legacy=True,
        )

    def test_upgrade_dispatch_passes_wheel_and_defaults(self) -> None:
        with mock.patch.object(
            cli_module.lifecycle,
            "upgrade",
            return_value={"status": "up-to-date"},
        ) as upgraded:
            code, payload = self.run_cli(
                [
                    "upgrade",
                    "--json",
                    "--scope",
                    "project",
                    "--project-root",
                    str(self.project),
                    "--wheel",
                    "upgrade.whl",
                    "--force",
                ]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertTrue(payload["ok"])
        upgraded.assert_called_once_with(
            scope="project",
            project_root=str(self.project),
            hosts=None,
            wheel="upgrade.whl",
            force=True,
            dry_run=False,
            adopt_legacy=False,
        )

    def test_upgrade_dispatch_passes_the_adopt_flag_when_requested(self) -> None:
        with mock.patch.object(
            cli_module.lifecycle,
            "upgrade",
            return_value={"status": "up-to-date"},
        ) as upgraded:
            code, payload = self.run_cli(
                ["upgrade", "--json", "--adopt-legacy"]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertTrue(payload["ok"])
        self.assertTrue(upgraded.call_args.kwargs["adopt_legacy"])

    def test_uninstall_dispatch_maps_keep_state_and_reports_external_step(
        self,
    ) -> None:
        payload_result = {"installed": True, "writes_performed": True}
        with (
            mock.patch.object(
                cli_module.lifecycle,
                "uninstall",
                return_value=dict(payload_result),
            ) as uninstalled,
            mock.patch.object(cli_module.shutil, "which", return_value=None),
            mock.patch.object(cli_module, "import_module") as import_module,
        ):
            code, payload = self.run_cli(["uninstall", "--json"])
            state_code, state_payload = self.run_cli(
                ["uninstall", "--json", "--keep-state"]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertEqual(state_code, cli_module.EXIT_SUCCESS)
        self.assertEqual(
            uninstalled.call_args_list[0].kwargs["keep_state"],
            False,
        )
        self.assertEqual(
            uninstalled.call_args_list[1].kwargs["keep_state"],
            True,
        )
        self.assertEqual(
            payload["result"]["cli_removal"],
            "external-required",
        )
        self.assertFalse(
            payload["result"]["cli_removal_details"]["available"]
        )
        self.assertEqual(
            payload["result"]["cli_removal_details"]["command"],
            ["uv", "tool", "uninstall", "xcoding-workflow"],
        )
        import_module.assert_not_called()
        self.assertEqual(
            state_payload["result"]["cli_removal"],
            "external-required",
        )

    def _fake_subprocess(self, result: object) -> SimpleNamespace:
        return SimpleNamespace(
            DEVNULL=-3,
            TimeoutExpired=subprocess.TimeoutExpired,
            run=mock.Mock(return_value=result),
        )

    def test_uninstall_all_with_fake_uv_success(self) -> None:
        fake = self._fake_subprocess(
            SimpleNamespace(returncode=0, stdout="removed\n", stderr="")
        )
        with (
            mock.patch.object(
                cli_module.lifecycle,
                "uninstall",
                return_value={"installed": True, "writes_performed": True},
            ),
            mock.patch.object(
                cli_module.shutil,
                "which",
                return_value="C:\\fake\\uv.exe",
            ),
            mock.patch.object(
                cli_module,
                "import_module",
                return_value=fake,
            ),
        ):
            code, payload = self.run_cli(
                ["uninstall", "--json", "--all"]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertEqual(payload["result"]["cli_removal"], "removed")
        details = payload["result"]["cli_removal_details"]
        self.assertTrue(details["attempted"])
        self.assertEqual(details["returncode"], 0)
        self.assertEqual(details["stdout"], "removed\n")
        self.assertEqual(
            details["command"],
            [
                "C:\\fake\\uv.exe",
                "tool",
                "uninstall",
                "xcoding-workflow",
            ],
        )
        fake.run.assert_called_once()

    def test_uninstall_all_failure_preserves_the_payload_result(self) -> None:
        cases = (
            (
                "nonzero",
                "C:\\fake\\uv.exe",
                SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="uv refused\n",
                ),
            ),
            ("absent", None, None),
        )
        for name, uv, process_result in cases:
            with self.subTest(case=name):
                payload_result = {
                    "installed": True,
                    "writes_performed": True,
                    "generation": "f" * 32,
                }
                fake = (
                    self._fake_subprocess(process_result)
                    if process_result is not None
                    else None
                )
                with (
                    mock.patch.object(
                        cli_module.lifecycle,
                        "uninstall",
                        return_value=dict(payload_result),
                    ),
                    mock.patch.object(
                        cli_module.shutil,
                        "which",
                        return_value=uv,
                    ),
                    mock.patch.object(
                        cli_module,
                        "import_module",
                        return_value=fake,
                    ) if fake is not None else contextlib.nullcontext(),
                ):
                    code, payload = self.run_cli(
                        ["uninstall", "--json", "--all"]
                    )

                self.assertEqual(code, cli_module.EXIT_READINESS)
                self.assertFalse(payload["ok"])
                self.assertEqual(
                    payload["error"]["code"],
                    "cli_removal_failed",
                )
                details = payload["error"]["details"]
                preserved = details["payload"]
                self.assertTrue(preserved["installed"])
                self.assertEqual(preserved["generation"], "f" * 32)
                self.assertEqual(
                    preserved["cli_removal"],
                    "external-required",
                )
                self.assertEqual(
                    details["cli_removal"],
                    "external-required",
                )
                self.assertEqual(
                    details["cli_removal_details"]["available"],
                    uv is not None,
                )
                if name == "absent":
                    self.assertFalse(
                        details["cli_removal_details"]["attempted"]
                    )

    def test_uninstall_all_dry_run_never_spawns_a_process(self) -> None:
        with (
            mock.patch.object(
                cli_module.lifecycle,
                "uninstall",
                return_value={"installed": True, "writes_performed": False},
            ),
            mock.patch.object(
                cli_module.shutil,
                "which",
                return_value=None,
            ) as which,
            mock.patch.object(cli_module, "import_module") as import_module,
        ):
            code, payload = self.run_cli(
                ["uninstall", "--json", "--all", "--dry-run"]
            )

        self.assertEqual(code, cli_module.EXIT_SUCCESS)
        self.assertEqual(payload["result"]["cli_removal"], "dry-run")
        self.assertFalse(
            payload["result"]["cli_removal_details"]["attempted"]
        )
        import_module.assert_not_called()
        which.assert_called_once_with("uv")


class PublicSourceBoundaryTests(unittest.TestCase):
    def test_lifecycle_command_sources_keep_the_read_only_boundary(self) -> None:
        """The new command surface must not reach tree, network, or daemon code.

        ``lifecycle.py`` is the only new public command source.  Its approved
        contract runs ``uv`` and the installed CLI as bounded subprocesses, so
        it is an explicit exception to the process-import rule exactly like the
        existing setup transaction.
        """

        public_sources = (
            "cli.py",
            "doctor.py",
            "lifecycle.py",
            "setup_plan.py",
            "setup_transaction.py",
            "version.py",
            "__main__.py",
        )
        for name in public_sources:
            with self.subTest(source=name):
                source = (
                    REPOSITORY_ROOT / "src" / "xcoding" / name
                ).read_text(encoding="utf-8")
                self.assertNotIn("import socket", source)
                self.assertNotIn("import urllib", source)
                if name not in {"setup_transaction.py", "lifecycle.py"}:
                    self.assertNotIn("import subprocess", source)
                self.assertNotIn("orchestration.xml", source)
                self.assertNotIn("runtime_core", source)


if __name__ == "__main__":
    unittest.main()
