from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
FLOW_SPEC = REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-flow.json"


class XcWorkshopSetupTests(unittest.TestCase):
    def run_author(self, *args: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(AUTHOR), *args],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_workshop_setup_flow_validates(self) -> None:
        code, payload = self.run_author("validate-spec", "--spec", str(FLOW_SPEC))
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["valid"])

        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "runtime.toml"
            config.write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            template = Path(temporary) / "workshop-setup-template.xml"
            code, payload = self.run_author("build", "--spec", str(FLOW_SPEC), "--out", str(template), "--config", str(config))
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "persisted")
            code, payload = self.run_author("validate-template", "--template", str(template))
            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["valid"])


if __name__ == "__main__":
    unittest.main()
