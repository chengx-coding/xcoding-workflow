from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_DOCUMENT = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"
VALIDATE_LANGUAGE = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_language.py"


class XcDocumentTests(unittest.TestCase):
    def validate(self, path: Path, expected_kind: str = "") -> tuple[int, dict[str, object]]:
        command = [sys.executable, str(VALIDATE_DOCUMENT), "--document", str(path)]
        if expected_kind:
            command.extend(["--expected-kind", expected_kind])
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        return result.returncode, json.loads(result.stdout)

    def write(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def validate_language(self, language: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(VALIDATE_LANGUAGE), "--language", language],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_accepts_valid_work_order_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "goal.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: work-order-goal
work_order_id: 20260727-1200-payment-refund
feature_ids:
  - payment-refund
orchestration:
  main_tree_ref: xc://work-order/20260727-1200-payment-refund/main
---

# Payment Refund Goal

Implement refund approval limits.
""",
            )

            code, payload = self.validate(document, "work-order-goal")

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_kind"], "work-order-goal")
            self.assertEqual(payload["content_language"], "en")

    def test_accepts_node_artifact_without_feature_association(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "review.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: node-artifact
work_order_id: 20260727-1200-workshop-setup
node_id: review-workflow
feature_ids: []
orchestration:
  tree_ref: xc://work-order/20260727-1200-workshop-setup/main
---

# Workflow Review

No required findings.
""",
            )

            code, payload = self.validate(document, "node-artifact")

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_kind"], "node-artifact")
            self.assertEqual(payload["audience"], "internal")

    def test_accepts_user_artifact_with_explicit_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "report.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: node-artifact
content_language: zh-CN
audience: user
work_order_id: 20260727-1200-workshop-setup
node_id: user-report
feature_ids: []
orchestration:
  tree_ref: xc://work-order/20260727-1200-workshop-setup/main
---

# 用户报告

已完成。
""",
            )

            code, payload = self.validate(document, "node-artifact")

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["content_language"], "zh-CN")
            self.assertEqual(payload["audience"], "user")

    def test_rejects_invalid_language_and_artifact_audience_contracts(self) -> None:
        base = """---
schema_version: 1
document_kind: node-artifact
{metadata}
work_order_id: 20260727-1200-workshop-setup
node_id: review-workflow
feature_ids: []
orchestration:
  tree_ref: xc://work-order/20260727-1200-workshop-setup/main
---

# Review
"""
        cases = (
            ("content_language: English\n", "content_language must be a valid simplified BCP 47 language tag"),
            ("audience: external\n", "audience must be internal or user"),
            ("audience: user\n", "user node-artifact documents must explicitly set content_language"),
            ("content_language: zh-CN\naudience: internal\n", "internal node-artifact documents must use content_language en"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for index, (metadata, expected_error) in enumerate(cases):
                document = Path(temporary) / f"invalid-{index}.md"
                self.write(document, base.format(metadata=metadata))

                code, payload = self.validate(document, "node-artifact")

                self.assertEqual(code, 1)
                self.assertFalse(payload["ok"])
                self.assertIn(expected_error, payload["errors"])

    def test_validates_explicit_work_order_language_tags(self) -> None:
        code, payload = self.validate_language("zh-CN")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["content_language"], "zh-CN")

        code, payload = self.validate_language("English")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    def test_rejects_feature_document_without_update_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "contract.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: feature-contract
feature_id: payment-refund
orchestration:
  initialized_by:
    work_order_id: 20260727-1200-payment-refund
    tree_ref: xc://work-order/20260727-1200-payment-refund/main
    node_id: write-contract
---

# Payment Refund
""",
            )

            code, payload = self.validate(document)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertIn("orchestration.last_updated_by must be an object", payload["errors"])

    def test_rejects_dynamic_state_in_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "result.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: work-order-result
work_order_id: 20260727-1200-payment-refund
feature_ids: []
status: running
orchestration:
  main_tree_ref: xc://work-order/20260727-1200-payment-refund/main
---

# Result
""",
            )

            code, payload = self.validate(document)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertIn("frontmatter must not duplicate dynamic orchestration state", payload["errors"])

    def test_rejects_retired_work_unit_document_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "goal.md"
            self.write(
                document,
                (
                    """---
schema_version: 1
document_kind: """
                    + "run-"
                    + """goal
"""
                    + "run_"
                    + """id: retired-contract
feature_ids: []
orchestration:
  main_tree_ref: retired
---

# Retired Contract
"""
                ),
            )

            code, payload = self.validate(document)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertTrue(
                any(
                    "document_kind must be one of" in error
                    for error in payload["errors"]
                )
            )

    def test_rejects_previous_identity_in_frontmatter_and_provenance(self) -> None:
        previous_identity = "run_" + "id"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_order_document = root / "goal.md"
            self.write(
                work_order_document,
                f"""---
schema_version: 1
document_kind: work-order-goal
work_order_id: target-order
{previous_identity}: previous-order
feature_ids: []
orchestration:
  main_tree_ref: target-tree
---

# Goal
""",
            )
            code, payload = self.validate(work_order_document, "work-order-goal")
            self.assertEqual(code, 1)
            self.assertIn(
                f"frontmatter contains unsupported managed identity field: {previous_identity}",
                payload["errors"],
            )

            workshop_document = root / "workflow.md"
            self.write(
                workshop_document,
                f"""---
schema_version: 1
document_kind: project-workflow
orchestration:
  initialized_by:
    work_order_id: target-order
    {previous_identity}: previous-order
    tree_ref: target-tree
    node_id: write-workflow
  last_updated_by:
    work_order_id: target-order
    tree_ref: target-tree
    node_id: write-workflow
---

# Workflow
""",
            )
            code, payload = self.validate(workshop_document, "project-workflow")
            self.assertEqual(code, 1)
            self.assertIn(
                "orchestration.initialized_by contains unsupported managed "
                f"identity field: {previous_identity}",
                payload["errors"],
            )


if __name__ == "__main__":
    unittest.main()
