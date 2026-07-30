from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = REPOSITORY_ROOT / "skills" / "xc-workflow-evolution" / "scripts"
CHECKER = SCRIPT_DIRECTORY / "check_skill_mirror.py"

sys.path.insert(0, str(SCRIPT_DIRECTORY))
import check_skill_mirror as checker


class SkillMirrorCheckerTests(unittest.TestCase):
    def create_package(self, root: Path, name: str, content: str = "body") -> None:
        package = root / name
        (package / "references").mkdir(parents=True)
        (package / "SKILL.md").write_text(
            f"---\nname: {name}\n---\n{content}\n",
            encoding="utf-8",
        )
        (package / "references" / "contract.md").write_text(
            f"{name} contract\n",
            encoding="utf-8",
        )

    def invoke(self, canonical: Path, mirror: Path) -> tuple[int, dict[str, object]]:
        completed = subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--canonical-root",
                str(canonical),
                "--mirror-root",
                str(mirror),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout)

    def test_exact_mirror_passes_and_ignores_non_xc_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            mirror = Path(temporary) / "mirror"
            self.create_package(canonical, "xc-alpha")
            shutil.copytree(canonical, mirror)
            project_only = mirror / "project-only"
            project_only.mkdir()
            (project_only / "SKILL.md").write_text("local\n", encoding="utf-8")

            code, payload = self.invoke(canonical, mirror)

            self.assertEqual(code, 0)
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["counts"]["canonical_files"], 2)
            self.assertEqual(payload["counts"]["mirror_files"], 2)

    def test_exact_mirror_ignores_python_cache_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            mirror = Path(temporary) / "mirror"
            self.create_package(canonical, "xc-alpha")
            shutil.copytree(canonical, mirror)
            cache = canonical / "xc-alpha" / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "helper.cpython-312.pyc").write_bytes(b"cache")

            code, payload = self.invoke(canonical, mirror)

            self.assertEqual(code, 0)
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["counts"]["canonical_files"], 2)

    def test_missing_unexpected_and_changed_files_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            mirror = Path(temporary) / "mirror"
            self.create_package(canonical, "xc-alpha")
            self.create_package(canonical, "xc-beta")
            shutil.copytree(canonical, mirror)
            (mirror / "xc-alpha" / "SKILL.md").write_text("changed\n", encoding="utf-8")
            (mirror / "xc-beta" / "references" / "contract.md").unlink()
            self.create_package(mirror, "xc-extra")

            code, payload = self.invoke(canonical, mirror)

            self.assertEqual(code, 1)
            self.assertFalse(payload["valid"])
            self.assertEqual(payload["counts"]["mismatched"], 1)
            self.assertEqual(
                payload["missing"],
                ["xc-beta/references/contract.md"],
            )
            self.assertEqual(
                payload["unexpected"],
                [
                    "xc-extra/SKILL.md",
                    "xc-extra/references/contract.md",
                ],
            )

    def test_retired_package_fails_closed_even_when_both_sides_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            mirror = Path(temporary) / "mirror"
            retired_package = "xc-" + "create-run"
            self.create_package(canonical, retired_package)
            shutil.copytree(canonical, mirror)

            code, payload = self.invoke(canonical, mirror)

            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "retired_xc_packages")
            self.assertEqual(payload["error"]["details"]["packages"], [retired_package])

    def test_package_without_skill_contract_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            canonical = Path(temporary) / "canonical"
            mirror = Path(temporary) / "mirror"
            (canonical / "xc-alpha").mkdir(parents=True)
            mirror.mkdir()

            with self.assertRaises(checker.MirrorError) as raised:
                checker.skill_manifest(canonical)

            self.assertEqual(raised.exception.code, "skill_contract_missing")


if __name__ == "__main__":
    unittest.main()
