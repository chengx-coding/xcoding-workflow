from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_SCRIPTS = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts"
RENDER_DOCUMENT = DOCUMENT_SCRIPTS / "render_document.py"
WORK_ORDER_GOAL_TEMPLATE = (
    REPOSITORY_ROOT / "skills" / "xc-document" / "assets" / "templates" / "work-order-goal.md"
)

sys.path.insert(0, str(DOCUMENT_SCRIPTS))
from frontmatter_yaml import loads


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
                loads(frontmatter)["tree_ref"],
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
            self.assertEqual(loads(frontmatter)["feature_ids"], ["payment-refund", "ledger"])

    def test_renders_non_english_work_order_headings_without_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "goal.md"

            code, payload = self.invoke(
                "--template",
                str(WORK_ORDER_GOAL_TEMPLATE),
                "--out",
                str(output),
                "--set",
                "content_language=zh-CN",
                "--set",
                "work_order_id=20260727-1200-language",
                "--set",
                "tree_ref=xc://work-order/20260727-1200-language/main",
                "--set",
                "document_title=语言契约目标",
                "--set",
                "requested_outcome_heading=请求结果",
                "--set",
                "scope_and_constraints_heading=范围与约束",
                "--set",
                "acceptance_conditions_heading=验收条件",
                "--set-json",
                "feature_ids=[]",
            )

            self.assertEqual(code, 0, payload)
            rendered = output.read_text(encoding="utf-8")
            self.assertEqual(loads(rendered.split("---", 2)[1])["content_language"], "zh-CN")
            self.assertIn("# 语言契约目标", rendered)
            self.assertIn("## 请求结果", rendered)


if __name__ == "__main__":
    unittest.main()
