from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
FLOW_SPEC = REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-flow.json"
SKILL = REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "SKILL.md"
RUNTIME_ASSET = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "assets"
    / "xc-orchestration-runtime.json"
)


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

    def build_flow(self, spec: Path, temporary: Path) -> Path:
        config = temporary / "runtime.json"
        config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
        template = temporary / "workshop-setup-template.xml"
        code, payload = self.run_author(
            "build", "--spec", str(spec), "--out", str(template), "--config", str(config)
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "persisted")
        return template

    def template_topology(self, template: Path) -> str | None:
        root = ET.parse(template).getroot()
        blackboard = root.find("blackboard")
        if blackboard is None:
            return None
        for var in blackboard.findall("var"):
            if var.get("key") == "workshop.topology":
                return var.text or ""
        return None

    def test_workshop_setup_flow_validates(self) -> None:
        code, payload = self.run_author("validate-spec", "--spec", str(FLOW_SPEC))
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["valid"])

        with tempfile.TemporaryDirectory() as temporary:
            template = self.build_flow(FLOW_SPEC, Path(temporary))
            code, payload = self.run_author("validate-template", "--template", str(template))
            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["valid"])

    def test_flow_spec_default_topology_is_independent_link(self) -> None:
        spec = json.loads(FLOW_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(spec["blackboard"]["workshop.topology"], "independent-link")

    def test_runtime_asset_default_topology_is_independent_link(self) -> None:
        asset = json.loads(RUNTIME_ASSET.read_text(encoding="utf-8"))
        self.assertEqual(asset["workshop"]["topology"], "independent-link")

    def test_built_template_records_default_topology_blackboard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            template = self.build_flow(FLOW_SPEC, Path(temporary))
            self.assertEqual(self.template_topology(template), "independent-link")

    def test_pinned_workshop_topology_is_preserved_in_template(self) -> None:
        spec = json.loads(FLOW_SPEC.read_text(encoding="utf-8"))
        spec["blackboard"]["workshop.topology"] = "same-repo"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pinned = root / "workshop-setup-flow.json"
            pinned.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            code, payload = self.run_author("validate-spec", "--spec", str(pinned))
            self.assertEqual(code, 0, payload)
            template = self.build_flow(pinned, root)
            self.assertEqual(self.template_topology(template), "same-repo")

    def test_skill_documents_workshop_topology_parameter(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        self.assertIn("workshop_topology", content)
        for value in ("independent-link", "independent-nested", "same-repo", "no-git"):
            self.assertIn(value, content)


if __name__ == "__main__":
    unittest.main()
