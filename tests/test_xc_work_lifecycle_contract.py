"""Contract tests for the work lifecycle's report-commitment statement (recovery 2).

`work_order.requires_report` is the commitment that mounts the full lifecycle's
`report-group`. Its shipped default was flipped from `false` to `true`, so a work order
whose preparation step never writes the field selects the report stage instead of
silently skipping it. The lifecycle contract kept the pre-flip explanation - that the
default is `false` and that `false` means only that the field has not been written yet -
in the very paragraph that describes the commitment write, which tells every reader of
the contract the opposite of what the shipped template does.

This module binds that paragraph to the shipped default:

* The page half is decisive. Before the correction the preparation-step paragraph carried
  the `false` default and the "not been written yet" explanation, so those assertions
  fail, and the paragraph said nothing about what makes the commitment.
* The specification half is an anchor, not a defect proof. `work-order-flow.json` already
  declared `true` when this test was written, so it pins the value the page must describe
  and the test cannot pass by asserting the page against itself.

Standard library only.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_PAGE = REPOSITORY_ROOT / "skills" / "xc-work" / "SKILL.md"
WORK_ORDER_SPEC = REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-flow.json"

COMMITMENT_KEY = "work_order.requires_report"
REPORT_GROUP = "report-group"

# The preparation-step paragraph is the contract's own statement of the commitment: the mode
# derivation, the baseline, the strength tier, and the default that decides what happens when
# the write never happens.
PARAGRAPH_ANCHOR = "In the same preparation step, write the mode-derived commitment"

# The refuted claim, in the two spellings the page used: the default value itself, and the
# explanation that made an unwritten field read as "no report needed".
REFUTED_DEFAULT = re.compile(r"default\s+`false`")
REFUTED_EXPLANATION = "has not been written yet"


def page_text() -> str:
    return SKILL_PAGE.read_text(encoding="utf-8")


def commitment_paragraph(text: str) -> str:
    """The preparation-step paragraph, isolated from the rest of the contract.

    The end is the next numbered step of the same operation rather than the next newline,
    so the assertions survive a rewrap of the paragraph and cannot be satisfied by a
    fragment of it.
    """
    start = text.index(PARAGRAPH_ANCHOR)
    rest = text[start:]
    following_step = re.search(r"\n\d+\.\s", rest)
    return rest if following_step is None else rest[: following_step.start()]


class ReportCommitmentContractTests(unittest.TestCase):
    def test_the_commitment_default_is_stated_as_fail_closed(self) -> None:
        """Decisive: the paragraph must describe the shipped `true` default, not `false`.

        `false` as the field's default is what made the mount's only fail-closed property
        unreachable, and an unwritten commitment is not "no report needed".
        """
        paragraph = commitment_paragraph(page_text())
        self.assertNotRegex(
            paragraph,
            REFUTED_DEFAULT,
            "the commitment's declared default is `true`; a paragraph that still gives "
            "`false` describes a default the shipped template no longer carries",
        )
        self.assertNotIn(
            REFUTED_EXPLANATION,
            paragraph,
            "an unwritten commitment selects report-group, so its absence must not be "
            "explained as a field that was simply not written yet",
        )
        self.assertRegex(
            paragraph,
            r"default is `true`",
            "the paragraph must state the declared default that decides the unwritten case",
        )
        self.assertIn(
            REPORT_GROUP,
            paragraph,
            "the fail-closed consequence must be named: the unwritten commitment selects "
            "the report stage instead of skipping it",
        )

    def test_the_preparation_write_is_named_as_what_makes_the_commitment(self) -> None:
        """Decisive: the paragraph must say what makes the commitment, not only its default."""
        paragraph = commitment_paragraph(page_text())
        self.assertIn(
            f"write the mode-derived commitment `{COMMITMENT_KEY}`",
            paragraph,
            "the preparation step's own write is the commitment; the paragraph must keep "
            "naming it",
        )
        self.assertIn(
            "makes the commitment",
            paragraph,
            "the paragraph must state that the preparation-step write is what makes the "
            "commitment, so the default is read as the unwritten fallback rather than as "
            "the commitment itself",
        )

    def test_no_line_of_the_contract_repeats_the_refuted_default(self) -> None:
        """Every place in the contract, not only the preparation-step paragraph."""
        offenders = [
            f"line {number}: {line.strip()}"
            for number, line in enumerate(page_text().splitlines(), start=1)
            if REFUTED_DEFAULT.search(line) or REFUTED_EXPLANATION in line
        ]
        self.assertEqual(
            offenders,
            [],
            "the contract must not repeat the pre-flip default anywhere: a second copy "
            f"misleads exactly like the first one did: {offenders}",
        )

    def test_the_page_describes_the_default_the_template_declares(self) -> None:
        """Anchor: the value the paragraph must describe is the shipped default."""
        blackboard = json.loads(WORK_ORDER_SPEC.read_text(encoding="utf-8"))["blackboard"]
        self.assertEqual(
            blackboard[COMMITMENT_KEY],
            "true",
            "the shipped template's declared default is the value the contract describes",
        )
        self.assertIn(
            "`true`",
            commitment_paragraph(page_text()),
            "the paragraph must carry the same value the template declares",
        )


if __name__ == "__main__":
    unittest.main()
