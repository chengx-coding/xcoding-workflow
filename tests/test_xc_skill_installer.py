from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPOSITORY_ROOT / "skills" / "xc-workflow-evolution" / "scripts" / "install_xc_skills.py"


class XcSkillInstallerTests(unittest.TestCase):
    def create_source_package(self, source: Path, name: str, content: str = "skill") -> None:
        package = source / "skills" / name
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(f"---\nname: {name}\n---\n{content}\n", encoding="utf-8")
        references = package / "references"
        references.mkdir()
        (references / "details.md").write_text(f"{name} details\n", encoding="utf-8")

    def create_roots(self, temporary: Path) -> tuple[Path, Path, Path]:
        source = temporary / "source"
        target = temporary / "target"
        (source / "skills").mkdir(parents=True)
        (target / "skills").mkdir(parents=True)
        (target / "skills" / "project-only").mkdir()
        (target / "skills" / "project-only" / "SKILL.md").write_text("project only\n", encoding="utf-8")
        manifest = target / "xc-skill-install-manifest.json"
        return source, target, manifest

    def invoke(self, source: Path, target: Path, manifest: Path, *extra: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                "--source-root",
                str(source),
                "--target-root",
                str(target),
                "--manifest",
                str(manifest),
                "--source-revision",
                "test-revision",
                *extra,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_first_install_copies_full_packages_and_preserves_non_xc_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            self.create_source_package(source, "xc-alpha")
            self.create_source_package(source, "xc-beta")

            code, payload = self.invoke(source, target, manifest)

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertTrue((target / "skills" / "xc-alpha" / "references" / "details.md").is_file())
            self.assertTrue((target / "skills" / "xc-beta" / "SKILL.md").is_file())
            self.assertTrue((target / "skills" / "project-only" / "SKILL.md").is_file())
            stored = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(stored["expected_packages"], ["xc-alpha", "xc-beta"])
            self.assertEqual(stored["source_revision"], "test-revision")
            self.assertEqual(stored["source_worktree_state"], "not-git")

            code, checked = self.invoke(source, target, manifest, "--check")

            self.assertEqual(code, 0)
            self.assertTrue(checked["ok"])

    def test_install_refuses_changed_tracked_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            self.create_source_package(source, "xc-alpha")
            self.assertEqual(self.invoke(source, target, manifest)[0], 0)
            tracked = target / "skills" / "xc-alpha" / "SKILL.md"
            tracked.write_text("changed locally\n", encoding="utf-8")

            code, payload = self.invoke(source, target, manifest)

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "target_drift")
            self.assertEqual(tracked.read_text(encoding="utf-8"), "changed locally\n")

    def test_install_refuses_unexpected_target_xc_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            self.create_source_package(source, "xc-alpha")
            self.assertEqual(self.invoke(source, target, manifest)[0], 0)
            unexpected = target / "skills" / "xc-unexpected"
            unexpected.mkdir()
            (unexpected / "SKILL.md").write_text("unexpected\n", encoding="utf-8")

            code, payload = self.invoke(source, target, manifest)

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "target_drift")
            self.assertTrue((unexpected / "SKILL.md").is_file())

    def test_install_refuses_retired_source_package_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            retired_package = "xc-" + "create-run"
            self.create_source_package(source, retired_package)

            code, payload = self.invoke(source, target, manifest)

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "retired_xc_packages")
            self.assertEqual(payload["error"]["details"]["packages"], [retired_package])

    def test_check_mode_writes_nothing_when_manifest_or_source_drift_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            self.create_source_package(source, "xc-alpha", "initial")

            code, payload = self.invoke(source, target, manifest, "--check")

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertFalse(manifest.exists())
            self.assertFalse((target / "skills" / "xc-alpha").exists())

            self.assertEqual(self.invoke(source, target, manifest)[0], 0)
            manifest_before = manifest.read_bytes()
            target_before = (target / "skills" / "xc-alpha" / "SKILL.md").read_bytes()
            (source / "skills" / "xc-alpha" / "SKILL.md").write_text("---\nname: xc-alpha\n---\nchanged\n", encoding="utf-8")

            code, payload = self.invoke(source, target, manifest, "--check")

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertEqual((target / "skills" / "xc-alpha" / "SKILL.md").read_bytes(), target_before)

    def test_install_removes_only_stale_manifest_managed_xc_packages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target, manifest = self.create_roots(Path(directory))
            self.create_source_package(source, "xc-alpha")
            self.create_source_package(source, "xc-beta")
            self.assertEqual(self.invoke(source, target, manifest)[0], 0)

            shutil.rmtree(source / "skills" / "xc-beta")
            code, payload = self.invoke(source, target, manifest)

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertTrue((target / "skills" / "xc-alpha").is_dir())
            self.assertFalse((target / "skills" / "xc-beta").exists())
            self.assertTrue((target / "skills" / "project-only" / "SKILL.md").is_file())
            self.assertEqual(payload["removed_stale_packages"], ["xc-beta"])


if __name__ == "__main__":
    unittest.main()
