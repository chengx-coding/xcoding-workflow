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
        self.assertIn("blocks approval", work)
        for field in ("capability", "priority", "user_value", "acceptance", "verification"):
            self.assertIn(f"`{field}`", reference)
        self.assertIn("## Solution matrix", reference)
        self.assertIn("## Proportionality", reference)
        self.assertIn("no material exclusions", reference)
        self.assertIn("capability map", analysis)
        self.assertIn("goal-authored", analysis)
        self.assertIn("original request", analysis)
        self.assertIn("capability matrix", implementation)
        self.assertIn("silently drop", implementation)
        self.assertIn("must and should capability", verification)
        self.assertIn("passing test suite", verification)
        self.assertIn("original request plus the accepted capability matrix", review)
        self.assertIn("unsourced narrowing", review)

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
