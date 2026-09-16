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

            # Corrected expectation. The previous version of this test asserted
            # that a plain install deleted this directory, which is exactly the
            # unconditional delete G-46 measured; the guard makes the survival
            # the expected outcome and requires the report to name it.
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue(retired.is_dir(), result.stdout)
            self.assertEqual((retired / "SKILL.md").read_text(encoding="utf-8"), "retired\n")
            self.assertIn(f"preserved: {retired.name}", result.stdout)
            self.assertIn("--force", result.stdout)
            self.assertTrue((target_skills / "xc-workflow-evolution" / "SKILL.md").is_file())
            manifest = json.loads((target / ".xc-skill-install-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["expected_packages"], ["xc-workflow-evolution"])

            forced = subprocess.run(
                [
                    sys.executable,
                    str(source / "install_skills.py"),
                    "--target-skills",
                    str(target_skills),
                    "--force",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(forced.returncode, 0, forced.stderr or forced.stdout)
            self.assertFalse(retired.exists())
            self.assertTrue((target_skills / "xc-workflow-evolution" / "SKILL.md").is_file())

    def test_verification_describes_the_tree_the_install_leaves_behind(self) -> None:
        """R-03: the printed verification is about the final state, not a transient one.

        The preserved directories are moved aside for the install pass and restored
        afterwards, so a verification taken before the restoration measures bytes no
        caller ever sees: it printed `problems: []` while the public installer's own
        `--check` refused the identical final tree with `unexpected_package`. The
        receipt printed here must describe what is on disk when this script returns.
        """
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

            preserved = target_skills / ("xc-" + "consumer-private")
            preserved.mkdir()
            (preserved / "SKILL.md").write_text("private\n", encoding="utf-8")

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
            receipt = self.check_receipt(result.stdout)
            self.assertTrue(receipt["ok"], result.stdout)
            self.assertEqual(receipt["problems"], [], result.stdout)

            # The receipt is about the tree this run leaves behind, so the same public
            # check run afterwards on that tree agrees with it.
            manifest = target / ".xc-skill-install-manifest.json"
            after = subprocess.run(
                [
                    sys.executable,
                    str(package / "scripts" / "install_xc_skills.py"),
                    "--source-root",
                    str(source),
                    "--target-root",
                    str(target),
                    "--manifest",
                    str(manifest),
                    "--check",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            after_payload = json.loads(after.stdout)
            self.assertEqual(after.returncode, 0, after.stdout)
            self.assertTrue(after_payload["ok"], after_payload)
            self.assertEqual(after_payload["problems"], [])
            self.assertEqual(
                json.loads(manifest.read_text(encoding="utf-8"))["unowned_packages"],
                [preserved.name],
            )
            self.assertTrue(preserved.is_dir())
            self.assertEqual((preserved / "SKILL.md").read_text(encoding="utf-8"), "private\n")

    def check_receipt(self, stdout: str) -> dict:
        """The `--check` receipt this script printed, taken from its own output."""
        decoder = json.JSONDecoder()
        receipt: dict | None = None
        for index, character in enumerate(stdout):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(stdout[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("operation") == "check":
                receipt = candidate
        self.assertIsNotNone(receipt, stdout)
        return receipt


if __name__ == "__main__":
    unittest.main()
