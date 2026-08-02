from __future__ import annotations

import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPOSITORY_ROOT / "skills"
DOCUMENT_FLOW = SKILLS / "xc-document-evolution" / "assets" / "document-evolution-flow.json"


def find_node(node: dict[str, object], template_id: str) -> dict[str, object]:
    if node.get("template_id") == template_id:
        return node
    for child in node.get("children", []):
        if isinstance(child, dict):
            found = find_node(child, template_id)
            if found:
                return found
    return {}


class HumanReadableDocumentContractTests(unittest.TestCase):
    def test_central_contract_defines_default_override_and_evidence_boundary(self) -> None:
        document_skill = (SKILLS / "xc-document" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("## Default Human-Readable Authoring", document_skill)
        self.assertIn("Lead with the document's purpose, conclusion, or required reader action", document_skill)
        self.assertIn("Explicit user requirements", document_skill)
        self.assertIn("does not claim to score or mechanically prove readability", document_skill)

    def test_document_evolution_propagates_requirements_to_write_review_and_revision(self) -> None:
        flow = json.loads(DOCUMENT_FLOW.read_text(encoding="utf-8"))
        self.assertEqual(flow["blackboard"]["document.authoring_requirements"], "")

        writer = find_node(flow["root"], "write-document")
        reviewer = find_node(flow["root"], "review-document")
        reviser = find_node(flow["root"], "revise-document")

        self.assertIn("document.authoring_requirements", writer["instructions"])
        self.assertIn("human-readable authoring default", writer["instructions"])
        self.assertIn("audience fit", reviewer["instructions"])
        self.assertIn("progressive disclosure", reviewer["instructions"])
        self.assertIn("first-use terminology explanations", reviewer["instructions"])
        self.assertIn("document.authoring_requirements", reviser["instructions"])
        self.assertIn("preserves key information", writer["acceptance"])

    def test_review_contract_covers_human_readability_without_mechanical_scoring(self) -> None:
        review_skill = (SKILLS / "xc-review" / "SKILL.md").read_text(encoding="utf-8")

        for phrase in (
            "audience fit",
            "purpose or conclusion before detail",
            "progressive disclosure",
            "first-use terminology explanations",
            "concision",
            "preservation of material facts",
        ):
            self.assertIn(phrase, review_skill)
        self.assertIn("explicit user authoring requirements", review_skill)

    def test_every_user_facing_artifact_producer_references_the_public_contract(self) -> None:
        producers = (
            "xc-analysis",
            "xc-diagnosis",
            "xc-implementation",
            "xc-review",
            "xc-verification",
        )
        for name in producers:
            content = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(
                "public `xc-document` human-readable authoring default",
                content,
                name,
            )

        implementation = (SKILLS / "xc-implementation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("project documentation delivered through the work order", implementation)


if __name__ == "__main__":
    unittest.main()
