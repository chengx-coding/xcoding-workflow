from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FEATURE_CLI = REPOSITORY_ROOT / "skills" / "xc-feature" / "scripts" / "manage_feature.py"


class XcFeatureTests(unittest.TestCase):
    def run_git(self, directory: Path, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def invoke(self, *args: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(FEATURE_CLI), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_initializes_one_explicit_feature_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workshop = root / ".xcoding"
            workshop.mkdir()
            self.run_git(root, "init")

            code, payload = self.invoke("init", "--workshop", str(workshop), "--feature-id", "payment-refund")

            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["feature_id"], "payment-refund")
            self.assertTrue((workshop / "features" / "payment-refund").is_dir())
            self.assertEqual(payload["workshop_path"], str(workshop.resolve()))

    def test_rejects_implicit_path_traversal_and_existing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workshop = root / ".xcoding"
            workshop.mkdir()
            self.run_git(root, "init")

            code, payload = self.invoke("init", "--workshop", str(workshop), "--feature-id", "../outside")
            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])

            code, payload = self.invoke("init", "--workshop", str(workshop), "--feature-id", "payment-refund")
            self.assertEqual(code, 0, payload)
            code, payload = self.invoke("init", "--workshop", str(workshop), "--feature-id", "payment-refund")
            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
