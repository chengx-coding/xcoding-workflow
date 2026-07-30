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


class RootSkillInstallerTests(unittest.TestCase):
    def test_replaces_installed_packages_with_target_only_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            target = root / "target"
            target_skills = target / "skills"
            source.mkdir()
            target_skills.mkdir(parents=True)

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

            retired = target_skills / ("xc-" + "create-run")
            retired.mkdir()
            (retired / "SKILL.md").write_text("retired\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(source / "install_skills.py"),
                    "--target-skills",
                    str(target_skills),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertFalse(retired.exists())
            self.assertTrue((target_skills / "xc-workflow-evolution" / "SKILL.md").is_file())
            manifest = json.loads((target / ".xc-skill-install-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["expected_packages"], ["xc-workflow-evolution"])


if __name__ == "__main__":
    unittest.main()
