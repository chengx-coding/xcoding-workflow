from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_DOCUMENT = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"


class XcDocumentTests(unittest.TestCase):
    def validate(self, path: Path, expected_kind: str = "") -> tuple[int, dict[str, object]]:
        command = [sys.executable, str(VALIDATE_DOCUMENT), "--document", str(path)]
        if expected_kind:
            command.extend(["--expected-kind", expected_kind])
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        return result.returncode, json.loads(result.stdout)

    def write(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def test_accepts_valid_run_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "goal.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: run-goal
run_id: 20260727-1200-payment-refund
feature_ids:
  - payment-refund
orchestration:
  main_tree_ref: xc://run/20260727-1200-payment-refund/main
---

# Payment Refund Goal

Implement refund approval limits.
""",
            )

            code, payload = self.validate(document, "run-goal")

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_kind"], "run-goal")

    def test_accepts_node_artifact_without_feature_association(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "review.md"
            self.write(
                document,
                """---
schema_version: 1
document_kind: node-artifact
run_id: 20260727-1200-workflow-setup
node_id: review-workflow
feature_ids: []
orchestration:
  tree_ref: xc://run/20260727-1200-workflow-setup/main
---

# Workflow Review

No required findings.
""",
            )

            code, payload = self.validate(document, "node-artifact")

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_kind"], "node-artifact")

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
    run_id: 20260727-1200-payment-refund
    tree_ref: xc://run/20260727-1200-payment-refund/main
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
document_kind: run-result
run_id: 20260727-1200-payment-refund
feature_ids: []
status: running
orchestration:
  main_tree_ref: xc://run/20260727-1200-payment-refund/main
---

# Result
""",
            )

            code, payload = self.validate(document)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertIn("frontmatter must not duplicate dynamic orchestration state", payload["errors"])


if __name__ == "__main__":
    unittest.main()
