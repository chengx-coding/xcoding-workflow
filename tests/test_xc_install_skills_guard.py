from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_INSTALLER = REPOSITORY_ROOT / "install_skills.py"
PACKAGE_INSTALLER = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-workflow-evolution"
    / "scripts"
    / "install_xc_skills.py"
)


class RootSkillInstallerGuardTests(unittest.TestCase):
    """The G-46 guard: no xc-* directory is deleted that the manifest does not own."""

    def build_source(self, source: Path) -> None:
        shutil.copy2(ROOT_INSTALLER, source / "install_skills.py")
        package = source / "skills" / "xc-workflow-evolution"
        (package / "scripts").mkdir(parents=True)
        (package / "SKILL.md").write_text(
            "---\nname: xc-workflow-evolution\n---\n# Workflow Evolution\n",
            encoding="utf-8",
        )
        shutil.copy2(PACKAGE_INSTALLER, package / "scripts" / "install_xc_skills.py")
        for command in (
            ["git", "init"],
            ["git", "config", "user.name", "XC Test"],
            ["git", "config", "user.email", "xc-test@example.invalid"],
            ["git", "add", "."],
            ["git", "commit", "-m", "test source"],
        ):
            completed = subprocess.run(
                command,
                cwd=source,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def install(self, source: Path, target_skills: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(source / "install_skills.py"),
                "--target-skills",
                str(target_skills),
                *extra,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def create_roots(self, temporary: str) -> tuple[Path, Path, Path, Path]:
        root = Path(temporary)
        source = root / "source"
        target = root / "target"
        target_skills = target / "skills"
        source.mkdir()
        target_skills.mkdir(parents=True)
        self.build_source(source)
        return source, target, target / ".xc-skill-install-manifest.json", target_skills

    def test_unmanaged_directory_is_not_deleted_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, _target, _manifest, target_skills = self.create_roots(temporary)
            foreign = target_skills / ("xc-" + "create-run")
            foreign.mkdir()
            (foreign / "SKILL.md").write_text("retired\n", encoding="utf-8")

            result = self.install(source, target_skills)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue(foreign.is_dir(), result.stdout)
            self.assertEqual((foreign / "SKILL.md").read_text(encoding="utf-8"), "retired\n")
            self.assertIn(f"preserved: {foreign.name}", result.stdout)
            self.assertIn("--force", result.stdout)
            self.assertTrue((target_skills / "xc-workflow-evolution" / "SKILL.md").is_file())
            # The preserved directory is outside the manifest by definition, and no
            # scratch staging directory is left behind next to the target.
            leftovers = sorted(
                entry.name for entry in target_skills.parent.iterdir() if entry.name.startswith(".xc-skill-")
            )
            self.assertEqual(leftovers, [".xc-skill-install-manifest.json"])

    def test_force_replaces_the_unmanaged_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, _target, _manifest, target_skills = self.create_roots(temporary)
            foreign = target_skills / ("xc-" + "create-run")
            foreign.mkdir()
            (foreign / "SKILL.md").write_text("retired\n", encoding="utf-8")

            result = self.install(source, target_skills, "--force")

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertFalse(foreign.exists())
            self.assertIn("--force was given", result.stdout)
            self.assertTrue((target_skills / "xc-workflow-evolution" / "SKILL.md").is_file())

    def test_manifest_owned_directory_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, target, manifest, target_skills = self.create_roots(temporary)
            first = self.install(source, target_skills)
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            installed = target_skills / "xc-workflow-evolution" / "SKILL.md"
            installed.write_text("locally modified\n", encoding="utf-8")

            second = self.install(source, target_skills)

            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
            self.assertIn("owned by the previous install manifest", second.stdout)
            self.assertEqual(
                installed.read_text(encoding="utf-8"),
                "---\nname: xc-workflow-evolution\n---\n# Workflow Evolution\n",
            )
            stored = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(stored["expected_packages"], ["xc-workflow-evolution"])

    def test_hand_installed_canonical_directory_is_replaced_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, _target, _manifest, target_skills = self.create_roots(temporary)
            hand_installed = target_skills / "xc-workflow-evolution"
            hand_installed.mkdir()
            (hand_installed / "SKILL.md").write_text("hand installed\n", encoding="utf-8")

            result = self.install(source, target_skills)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("hand-installed copy, replaced by the canonical package", result.stdout)
            self.assertEqual(
                (hand_installed / "SKILL.md").read_text(encoding="utf-8"),
                "---\nname: xc-workflow-evolution\n---\n# Workflow Evolution\n",
            )


if __name__ == "__main__":
    unittest.main()
