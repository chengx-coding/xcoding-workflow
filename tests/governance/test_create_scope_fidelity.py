"""Contract checks for the single output-surface evidence owner and scope fidelity."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CreateScopeFidelityContractTest(unittest.TestCase):
    def test_output_surface_contract_is_single_source(self):
        work = read(SKILLS / "xc-work" / "SKILL.md")
        reference = read(SKILLS / "xc-work" / "references" / "create-scope.md")
        reference_flat = " ".join(reference.split())
        analysis = read(SKILLS / "xc-analysis" / "SKILL.md")
        verification = read(SKILLS / "xc-verification" / "SKILL.md")
        implementation = read(SKILLS / "xc-implementation" / "SKILL.md")
        review = read(SKILLS / "xc-review" / "SKILL.md")
        generality = read(
            SKILLS / "xc-workflow-evolution" / "references" / "generality-and-applicability.md"
        )
        detail = SKILLS / "xc-work" / "references" / "output-surface-evidence.md"
        experience = read(SKILLS / "xc-work" / "references" / "experience-quality.md")

        self.assertTrue(detail.is_file())
        self.assertIn("Output-Surface Evidence", work)
        self.assertIn("experience-quality.md", work)
        self.assertIn("| `experience` (task-class overlay, `proposed`)", work)
        self.assertNotIn("experience-quality.md", analysis)
        for profile in ("visual", "cli-library-api", "docs"):
            self.assertIn(profile, work)
            self.assertIn(profile, read(detail))
        self.assertFalse((SKILLS / "xc-work" / "references" / "profiles").exists())
        for text in (reference, analysis, verification, generality):
            self.assertNotIn("profiles/", text)
        self.assertIn("Observable-state", reference_flat)
        self.assertIn("experience-quality.md", reference_flat)
        self.assertIn("before/action/after", reference_flat)
        self.assertIn("capability map", reference_flat)
        self.assertIn("signature", reference_flat)
        self.assertIn("prior accepted capability inventory", reference_flat)
        self.assertIn("solution matrix", reference_flat)
        self.assertIn("Verification and review", reference_flat)
        self.assertIn("Output-Surface Evidence", verification)
        self.assertIn("Do not infer this profile", review)
        self.assertIn("data dashboard", experience)
        self.assertIn("**must** capability", reference_flat)
        self.assertIn("state-dependent backdrop is a **must**", verification)
        for heading in ("## 1. First-run discoverability", "## 2. Visual composition and review", "## 3. Visual-state backdrop (task-class must)", "## 4. Reference signature and progression", "## 5. Verification"):
            self.assertIn(heading, experience)
        self.assertIn("pass its checks into the analysis node inputs", work)
        self.assertIn("self-review limitation", verification)
        self.assertIn("Experience-product overlay", read(ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertIn("体验型产品 overlay", read(ROOT / "docs" / "zh-CN" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertIn("Promotion status:** `proposed`", experience)
        for phrase in ("Scope:** task-class", "First-run discoverability", "independent visual", "state-dependent backdrop", "Reference signature"):
            self.assertIn(phrase, experience)
        self.assertIn("capability matrix", implementation)
        self.assertIn("scope fidelity", review)

        evolution_skill = read(SKILLS / "xc-workflow-evolution" / "SKILL.md")
        discipline = read(
            SKILLS / "xc-workflow-evolution" / "references" / "self-evolution-discipline.md"
        )
        for text in (generality,):
            self.assertIn("demoted", text)
            self.assertIn("retired", text)
        self.assertIn("demote", evolution_skill)
        self.assertIn("line closure", evolution_skill.lower())
        self.assertIn("Meta-review", discipline)
        self.assertIn("refactor", discipline.lower())
        self.assertNotIn("internal-profile", work)

    def test_generic_assets_do_not_name_the_sample_domain(self):
        paths = [
            SKILLS / "xc-work" / "SKILL.md",
            SKILLS / "xc-work" / "references" / "create-scope.md",
            SKILLS / "xc-work" / "references" / "output-surface-evidence.md",
            SKILLS / "xc-work" / "references" / "experience-quality.md",
            SKILLS / "xc-workflow-evolution" / "SKILL.md",
            SKILLS / "xc-workflow-evolution" / "references" / "generality-and-applicability.md",
            SKILLS / "xc-workflow-evolution" / "references" / "self-evolution-discipline.md",
            SKILLS / "xc-analysis" / "SKILL.md",
            SKILLS / "xc-verification" / "SKILL.md",
        ]
        forbidden = re.compile(r"\b(minecraft|minimap|crafting tree)\b", re.IGNORECASE)
        for path in paths:
            self.assertIsNone(forbidden.search(read(path)), path)

    def test_runtime_archive_protocol_matches_terminal_statuses(self):
        protocol = read(
            SKILLS / "xc-orchestration-runtime" / "references" / "runtime-protocol.md"
        )
        section = protocol.split("## Subtree Archiving", 1)[1]
        self.assertIn("failed/blocked composite or loop", section)
