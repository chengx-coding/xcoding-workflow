"""Contract checks for the create scope-fidelity and capability-matrix rule."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CreateScopeFidelityContractTest(unittest.TestCase):
    def test_create_scope_contract_is_owned_by_each_stage(self):
        work = read(SKILLS / "xc-work" / "SKILL.md")
        reference = read(SKILLS / "xc-work" / "references" / "create-scope.md")
        analysis = read(SKILLS / "xc-analysis" / "SKILL.md")
        implementation = read(SKILLS / "xc-implementation" / "SKILL.md")
        verification = read(SKILLS / "xc-verification" / "SKILL.md")
        review = read(SKILLS / "xc-review" / "SKILL.md")

        self.assertIn("intended-capability-scope", work)
        self.assertIn("goal-authored", work)
        self.assertIn("capability matrix", work)
        self.assertIn("no credible reference", work)
        self.assertNotIn("novel task may record", work)
        for field in ("capability", "priority", "user_value", "acceptance", "verification"):
            self.assertIn(f"`{field}`", reference)
        self.assertIn("## Solution matrix", reference)
        self.assertIn("## Proportionality", reference)
        self.assertIn("no material exclusions", reference)
        self.assertIn("## Reference-informed signature experience", reference)
        reference_flat = " ".join(reference.split())
        self.assertIn("signature capability", reference)
        self.assertIn("no reference applies", reference_flat)
        self.assertIn("minimum feature count", reference)
        self.assertIn("canonical record", reference)
        self.assertIn("proposed should", reference)
        self.assertIn("sharpen", reference)
        review_flat = " ".join(review.split())
        self.assertIn("smallest decision-changing signature set", reference_flat)
        self.assertIn("credible reference exists but the task is small", reference_flat)
        self.assertIn("unless the accepted matrix records its deferral", reference_flat)
        self.assertIn("unless the accepted matrix records its deferral", review_flat)
        self.assertIn("## Prior capability preservation", reference)
        self.assertIn("preserve", reference)
        self.assertIn("replace", reference)
        self.assertIn("retire", reference)
        self.assertIn("not a ceiling", reference)
        self.assertIn("prior accepted capability inventory", work)
        self.assertIn("preservation", analysis)
        self.assertIn("prior accepted capability inventory", verification)
        self.assertIn("prior accepted capability inventory", review)
        self.assertIn("undispositioned", reference)
        self.assertIn("independent of the solution approval", reference)
        self.assertIn("prior `should`", reference_flat)
        self.assertIn("defer", reference)
        self.assertIn("mandatory", work)
        self.assertIn("capability map", analysis)
        self.assertIn("signature-experience", analysis)
        self.assertIn("signature table", analysis)
        self.assertIn("goal-authored", analysis)
        self.assertIn("original request", analysis)
        self.assertIn("capability matrix", implementation)
        self.assertIn("silently drop", implementation)
        self.assertIn("must and should capability", verification)
        self.assertIn("passing test suite", verification)
        self.assertIn("original request plus the accepted capability matrix", review)
        self.assertIn("unsourced narrowing", review)
        self.assertIn("signature-experience table", review)

    def test_generic_create_scope_assets_do_not_name_the_sample_domain(self):
        paths = [
            SKILLS / "xc-work" / "SKILL.md",
            SKILLS / "xc-work" / "references" / "create-scope.md",
            SKILLS / "xc-analysis" / "SKILL.md",
            SKILLS / "xc-implementation" / "SKILL.md",
            SKILLS / "xc-verification" / "SKILL.md",
            SKILLS / "xc-review" / "SKILL.md",
        ]
        forbidden = re.compile(r"\b(minecraft|minimap|crafting tree)\b", re.IGNORECASE)
        for path in paths:
            match = forbidden.search(read(path))
            self.assertIsNone(
                match,
                f"{path.relative_to(ROOT)} contains sample-specific term {match.group(0)!r}" if match else "",
            )


if __name__ == "__main__":
    unittest.main()
