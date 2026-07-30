from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"
RUNTIME = REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "scripts" / "orchestration.py"
WORKFLOWS = (
    (
        "document-evolution",
        REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-template.xml",
        "write-document",
    ),
    (
        "workshop-setup",
        REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-workshop-setup" / "assets" / "workshop-setup-template.xml",
        "prepare-workshop",
    ),
    (
        "new-feature",
        REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-new-feature" / "assets" / "new-feature-template.xml",
        "prepare-feature",
    ),
    (
        "feature-adoption",
        REPOSITORY_ROOT / "skills" / "xc-feature-adoption" / "assets" / "feature-adoption-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-feature-adoption" / "assets" / "feature-adoption-template.xml",
        "prepare-adoption",
    ),
    (
        "work-order",
        REPOSITORY_ROOT / "skills" / "xc-work-order" / "assets" / "work-order-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-work-order" / "assets" / "work-order-template.xml",
        "prepare-work-order",
    ),
    (
        "feature-reconciliation",
        REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-feature-reconciliation" / "assets" / "feature-reconciliation-template.xml",
        "load-feature-provenance",
    ),
    (
        "clarify",
        REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-flow.json",
        REPOSITORY_ROOT / "skills" / "xc-clarify" / "assets" / "clarify-template.xml",
        "open-session-record",
    ),
)


class XcLifecycleTemplateTests(unittest.TestCase):
    def run_json(self, command: list[str]) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_flow_specs_rebuild_current_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.toml"
            config.write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            for name, spec, template, _ in WORKFLOWS:
                code, payload = self.run_json([sys.executable, str(AUTHOR), "validate-spec", "--spec", str(spec)])
                self.assertEqual(code, 0, (name, payload))
                self.assertTrue(payload["valid"], (name, payload))

                rebuilt = root / f"{name}.xml"
                code, payload = self.run_json(
                    [
                        sys.executable,
                        str(AUTHOR),
                        "build",
                        "--spec",
                        str(spec),
                        "--out",
                        str(rebuilt),
                        "--config",
                        str(config),
                    ]
                )
                self.assertEqual(code, 0, (name, payload))
                self.assertEqual(rebuilt.read_bytes(), template.read_bytes(), name)

    def test_templates_initialize_and_expose_first_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workshop = root / ".xcoding"
            workshop.mkdir()
            (workshop / "xc-orchestration-runtime.toml").write_text("[git]\nauto_commit = false\n", encoding="utf-8")
            for name, _, template, first_template_id in WORKFLOWS:
                runtime_path = workshop / "work-orders" / name / "runtime"
                code, initialized = self.run_json(
                    [
                        sys.executable,
                        str(RUNTIME),
                        "init",
                        "--template",
                        str(template),
                        "--runtime-path",
                        str(runtime_path),
                        "--work-order-id",
                        f"20260727-1000-{name}",
                    ]
                )
                self.assertEqual(code, 0, (name, initialized))
                code, next_payload = self.run_json(
                    [sys.executable, str(RUNTIME), "next", "--tree", str(initialized["tree_path"])]
                )
                self.assertEqual(code, 0, (name, next_payload))
                self.assertEqual(next_payload["ready"][0]["template_id"], first_template_id, name)


if __name__ == "__main__":
    unittest.main()
