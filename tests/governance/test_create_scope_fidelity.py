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
        self.assertIn("**must** capabilities", reference_flat)
        self.assertIn("validated-in-class", experience)
        self.assertIn("must owned by the visual output-surface", experience)
        self.assertIn("mode/theme/time/viewport", reference_flat)
        self.assertIn("first-run affordance", work)
        self.assertIn("first-run affordance", verification)
        self.assertNotIn("fresh first-run discoverability", verification)
        self.assertIn("validated-in-class", read(detail))
        self.assertIn("first-run affordance", read(ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertIn("interactive visual experience", read(ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertNotIn("2D sandbox", read(ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertNotIn("block-or-tile", read(ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertIn("交互式视觉体验产品", read(ROOT / "docs" / "zh-CN" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertNotIn("2D 沙盒", read(ROOT / "docs" / "zh-CN" / "reference" / "skills" / "implementation-and-quality.md"))
        self.assertIn("visual-state backdrop", verification)
        self.assertIn("mode/theme/time/viewport", verification)
        for heading in ("## 1. First-run discoverability", "## 2. Visual composition and review", "## 3. Visual-state backdrop", "## 4. Reference signature and progression", "## 5. Verification"):
            self.assertIn(heading, experience)
        self.assertIn("pass its checks into the analysis node inputs", work)
        self.assertIn("independent critic is required", verification)
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
        paths = sorted(SKILLS.rglob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
        forbidden = re.compile(
            r"(2D sandbox|2D-sandbox|block-or-tile|2D 沙盒|game/sandbox/simulation|games, sandboxes|面向游戏、沙盒|game/UI|in-game|gameplay|crafting, survival|save/reload|a game|simulations|game UI|minecraft|minimap|crafting tree|Wildgrove|Blockhaven|Cubewood|MOSSWILD)",
            re.IGNORECASE,
        )
        for path in paths:
            self.assertIsNone(forbidden.search(read(path)), path)

    def test_runtime_archive_protocol_matches_terminal_statuses(self):
        protocol = read(
            SKILLS / "xc-orchestration-runtime" / "references" / "runtime-protocol.md"
        )
        section = protocol.split("## Subtree Archiving", 1)[1]
        self.assertIn("failed/blocked composite or loop", section)

    def test_visual_design_skill_is_generic_and_dual_gated(self):
        skill = read(SKILLS / "xc-visual-design" / "SKILL.md")
        critic = read(SKILLS / "xc-visual-design" / "references" / "critic-loop.md")
        record = read(SKILLS / "xc-visual-design" / "references" / "review-record.md")
        self.assertIn('name: "xc-visual-design"', skill)
        self.assertIn("independent critic", skill)
        self.assertIn("functional preservation", skill.lower())
        self.assertIn("do not prescribe a specific style", skill.lower())
        self.assertNotIn("D5 =", skill)
        self.assertIn("independent", critic.lower())
        self.assertIn("at least two", critic)
        self.assertIn("functional gate", record)
        for term in ("Minecraft", "minimap", "2D sandbox", "Cubewood", "MOSSWILD"):
            self.assertNotIn(term, skill)
