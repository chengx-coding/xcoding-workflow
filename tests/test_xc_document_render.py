from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RENDER_DOCUMENT = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "render_document.py"


class XcDocumentRenderTests(unittest.TestCase):
    def invoke(self, *args: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(RENDER_DOCUMENT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_renders_known_placeholders_and_rejects_unknown_ones(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.md"
            output = root / "output.md"
            template.write_text("# {{title}}\n\n{{body}}\n", encoding="utf-8")

            code, payload = self.invoke(
                "--template",
                str(template),
                "--out",
                str(output),
                "--set",
                "title=Workflow",
                "--set",
                "body=Ready",
            )

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(output.read_text(encoding="utf-8"), "# Workflow\n\nReady\n")

            code, payload = self.invoke(
                "--template",
                str(template),
                "--out",
                str(output),
                "--set",
                "title=Workflow",
            )
            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertIn("unresolved placeholders", payload["error"]["message"])

    def test_renders_windows_paths_in_yaml_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.md"
            output = root / "output.md"
            template.write_text(
                "\n".join(
                    [
                        "---",
                        "schema_version: 1",
                        'tree_ref: "{{tree_ref}}"',
                        "---",
                        "",
                        "# Document",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            code, payload = self.invoke(
                "--template",
                str(template),
                "--out",
                str(output),
                "--set",
                r"tree_ref=C:\dev\xcoding-workflow\runtime\orchestration.xml",
            )

            self.assertEqual(code, 0, payload)
            rendered = output.read_text(encoding="utf-8")
            frontmatter = rendered.split("---", 2)[1]
            self.assertEqual(
                yaml.safe_load(frontmatter)["tree_ref"],
                r"C:\dev\xcoding-workflow\runtime\orchestration.xml",
            )

    def test_renders_json_values_as_structured_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.md"
            output = root / "output.md"
            template.write_text(
                "\n".join(
                    [
                        "---",
                        'feature_ids: "{{feature_ids}}"',
                        "---",
                        "",
                        "# Document",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            code, payload = self.invoke(
                "--template",
                str(template),
                "--out",
                str(output),
                "--set-json",
                'feature_ids=["payment-refund","ledger"]',
            )

            self.assertEqual(code, 0, payload)
            frontmatter = output.read_text(encoding="utf-8").split("---", 2)[1]
            self.assertEqual(yaml.safe_load(frontmatter)["feature_ids"], ["payment-refund", "ledger"])


if __name__ == "__main__":
    unittest.main()
