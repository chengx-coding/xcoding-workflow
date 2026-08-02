from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
FLOW_SPEC = REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-flow.json"


class XcDocumentEvolutionTests(unittest.TestCase):
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

    def test_flow_spec_and_generated_template_validate(self) -> None:
        code, validation = self.run_author("validate-spec", "--spec", str(FLOW_SPEC))
        self.assertEqual(code, 0, validation)
        self.assertTrue(validation["valid"])

        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            template = Path(temporary) / "document-evolution-template.xml"
            code, built = self.run_author("build", "--spec", str(FLOW_SPEC), "--out", str(template), "--config", str(config))
            self.assertEqual(code, 0, built)
            self.assertTrue(built["integrity"]["status"] == "valid")
            code, template_validation = self.run_author("validate-template", "--template", str(template))
            self.assertEqual(code, 0, template_validation)
            self.assertTrue(template_validation["valid"])

    def test_optional_review_and_gate_stages_are_latched(self) -> None:
        flow = json.loads(FLOW_SPEC.read_text(encoding="utf-8"))
        nodes = {node["template_id"]: node for node in flow["root"]["children"]}

        self.assertEqual(nodes["review-loop"]["when.policy"], "latched")
        self.assertEqual(nodes["document-gate"]["when.policy"], "latched")


if __name__ == "__main__":
    unittest.main()
