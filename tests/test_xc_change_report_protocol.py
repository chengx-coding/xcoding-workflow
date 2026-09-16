"""Normative-text and drift tests for the `xc-change-report` package.

The package's contract lives in prose (`SKILL.md` and the three reference documents) while the
behaviour lives in scripts and in `assets/change-report-flow.json`. Nothing in the ordinary suite
compares the two, so a contract sentence could describe a mechanism the package no longer has -
which is exactly what happened to the blackboard key list, the publisher table and the strength
matrix before this suite existed.

Every test here is a **text or drift** check: it reads a shipped document, extracts the claim it
makes, and compares that claim with the artefact that decides the same fact (the flow
specification, the generated template, `build_manifest.py`, `validate_report.py`, or the
shipped planning domain of `xc-work`). A prose statement that contradicts its arbiter fails the
suite instead of shipping.

Standard library only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
SKILL_PAGE = SKILL_ROOT / "SKILL.md"
PROTOCOL = SKILL_ROOT / "references" / "coverage-protocol.md"
CONTRACT = SKILL_ROOT / "references" / "change-report-contract.md"
# The rule the Skill page must agree with: embedding composes node structure and copies no child
# template defaults into the runtime blackboard, so the page may never promise a fallback value.
SUBTREE_EMBEDDING = (
    REPOSITORY_ROOT / "skills" / "xc-orchestration-runtime" / "references" / "subtree-embedding.md"
)
FLOW_SPEC = SKILL_ROOT / "assets" / "change-report-flow.json"
TEMPLATE = SKILL_ROOT / "assets" / "change-report-template.xml"
WORK_ORDER_SPEC = REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-flow.json"
PLAN_POLICY = REPOSITORY_ROOT / "skills" / "xc-work" / "scripts" / "plan_work_policy.py"
DOC_RUNNING = REPOSITORY_ROOT / "docs" / "workflows" / "running.md"
DOC_CHOOSING = REPOSITORY_ROOT / "docs" / "workflows" / "choosing.md"
DOC_SKILL_REFERENCE = REPOSITORY_ROOT / "docs" / "reference" / "skills" / "implementation-and-quality.md"
WORK_SKILL_PAGE = REPOSITORY_ROOT / "skills" / "xc-work" / "SKILL.md"

for entry in (str(SCRIPTS),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import build_manifest as bm  # noqa: E402
import validate_report as vr  # noqa: E402


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The caller-seeded key set, frozen by name and declared default in the solution decision's
# cross-unit interface section. It is quoted here rather than derived, because deriving it from
# the page it is supposed to check would make the check vacuous.
FROZEN_CALLER_KEYS: dict[str, str] = {
    "report.path": "",
    "report.manifest_path": "",
    "report.baseline_commit": "",
    "report.baseline_digest": "",
    "report.language": "en",
    "report.strength": "standard",
    "report.gate_required": "false",
    "report.gate_outcome": "not-run",
    "report.gate_rework_required": "false",
    "report.gate_recovery_required": "false",
    "report.round": "1",
    "report.refresh_count": "0",
    "report.refresh_reason": "initial",
}

# The ordering property, in place of the single literal the first guard matched. The register
# recorded the defect as a page claiming the report "runs before that review"; a literal cannot
# guard a claim, because rewording the same false statement - "produce the report before that
# review", "the report is produced ahead of that review" - walks straight past it. That is how the
# false claim survived into the shipped `xc-work` page while this suite passed. The guard below
# extracts the claim instead of the sentence:
#
#   * the `report ... <precedence marker> ... review` relation, with the marker joined to both
#     mentions by at most three words, so a marker that does not actually order the two mentions
#     is not read as one, and the correct shipped sentence ("the report group is the last group
#     before the result document ... mounts no top-level review node") is not read as a claim;
#   * the path the claim scopes itself to: the clause it sits in when that clause names a path,
#     otherwise the sentence it sits in.
#
# The property is the protocol's normative O9 clause and `work-order-flow.json` decides it: on the
# full lifecycle the report group is the last group before the result document and no review node
# is mounted on that path, so a report-before-review claim is true there only for the adaptive
# path, where O9 makes the order main-session policy. A claim scoped to the full lifecycle, to a
# bridge-required review, or to no path at all is the defect this test exists to fail.
ORDER_MARKERS = (
    r"before|prior to|ahead of|in advance of|earlier than|first|precedes|preceding|comes before|"
    r"runs before|is placed before|is sequenced before|goes before"
)
REPORT_MENTION = r"reports?(?:-[a-z]+)?"
REVIEW_MENTION = r"review(?:s|ed|ing|er|ers)?(?:-[a-z]+)?"
REPORT_ONLY = re.compile(rf"\b{REPORT_MENTION}\b", re.I)
REVIEW_ONLY = re.compile(rf"\b{REVIEW_MENTION}\b", re.I)
REPORT_BEFORE_REVIEW = re.compile(
    rf"\b{REPORT_MENTION}\b(?:\s+(?!(?:{ORDER_MARKERS})\b)\S+){{0,3}}\s+(?:{ORDER_MARKERS})\b"
    rf"(?:\s+(?!{REVIEW_MENTION}\b)\S+){{0,3}}\s+{REVIEW_MENTION}\b",
    re.I,
)
# The full lifecycle's own order, and the shape a document that raises the bridge case must carry.
REVIEW_BEFORE_REPORT = re.compile(
    rf"\b{REVIEW_MENTION}\b(?:(?!\b{REPORT_MENTION}\b).){{0,240}}?\b(?:{ORDER_MARKERS})\b"
    rf"(?:(?!\b{REPORT_MENTION}\b).){{0,80}}?\b{REPORT_MENTION}\b",
    re.I,
)
ADAPTIVE_PATH = re.compile(r"\badaptive\b", re.I)
FULL_LIFECYCLE_PATH = re.compile(r"\b(?:bridge|full lifecycle|full-lifecycle)\b", re.I)
MAIN_SESSION_POLICY = re.compile(r"main[\s-]session policy", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# A clause ends at `;`, `:`, or a table cell boundary: a Markdown table row carries several
# unrelated claims, and reading the whole row as one clause would attribute the path a cell names
# to a claim made in a different cell.
CLAUSE_SPLIT = re.compile(r"(?<=[;:])\s+|\s*\|\s*")


def fenced_block_containing(text: str, needle: str) -> str:
    for block in re.findall(r"```text\n(.*?)```", text, re.S):
        if needle in block:
            return block
    raise AssertionError(f"no fenced text block contains {needle!r}")


def protocol_publisher_rows(text: str) -> list[tuple[str, str, str]]:
    section = text.split("**O1**", 1)[1].split("**O1a**", 1)[0]
    rows: list[tuple[str, str, str]] = []
    for match in re.finditer(
        r"^\s*\|\s*`([a-z-]+)`\s*\|\s*`([a-z-]+)`\s*\|\s*`(true|false)`\s*\|\s*$",
        section,
        re.M,
    ):
        rows.append((match.group(1), match.group(2), match.group(3)))
    return rows


def calibration_rows(text: str, heading: str) -> dict[str, dict[str, str]]:
    section = text.split(heading, 1)[1]
    rows: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r"^\|\s*`([A-Za-z0-9_.\-]+)`\s*\|\s*`([^`]*)`\s*\|\s*`([^`]*)`\s*\|",
        section,
        re.M,
    ):
        rows[match.group(1)] = {"value": match.group(2), "declared_in": match.group(3)}
    return rows


def spec_nodes(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "template_id" in node:
            found.append(node)
        for child in node.get("children", []) or []:
            found.extend(spec_nodes(child))
    elif isinstance(node, list):
        for item in node:
            found.extend(spec_nodes(item))
    return found


def child_template_ids(spec_path: Path, parent_template_id: str) -> list[str]:
    spec = json.loads(read(spec_path))
    for node in spec_nodes(spec["root"]):
        if node.get("template_id") == parent_template_id:
            return [str(child.get("template_id", "")) for child in node.get("children", []) or []]
    raise AssertionError(f"the specification declares no {parent_template_id} node")


def flatten(text: str) -> str:
    """Collapse whitespace so a phrase can be asserted across the document's own line breaks."""
    return re.sub(r"\s+", " ", text)


def blackboard_section(text: str) -> str:
    """The Skill page's `## Blackboard` section, with its markup stripped to prose.

    The rule under test lives in this one section. Reading the whole page would let a claim
    elsewhere satisfy a requirement the blackboard section has stopped making.
    """
    if "## Blackboard" not in text:
        raise AssertionError("the Skill page no longer declares a Blackboard section")
    section = text.split("## Blackboard", 1)[1].split("\n## ", 1)[0]
    prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", section)
    prose = re.sub(r"```text\n.*?```", " ", prose, flags=re.S)
    return prose.replace("`", "").replace("**", "").replace("_", " ")


def prose_sentences(text: str) -> list[str]:
    """The section's sentences, flattened, so a claim can be matched across line breaks."""
    return [part.strip() for part in SENTENCE_SPLIT.split(flatten(text)) if part.strip()]


# The defect this guard exists to fail, expressed as a property rather than as one sentence.
#
# An earlier literal guard passed while the shipped page claimed that "a key that is declared but
# left unwritten reads as the empty string, so the caller half carries declared defaults". The
# runtime measures the opposite: embedding copies no child template defaults, so an unseeded
# caller key is absent. A literal cannot guard the rule, because rewording the same false
# statement - "an unwritten key reads as its declared default", "a key the caller never publishes
# resolves to the declared default" - walks straight past it. The guard below extracts the claim:
#
#   * a mention of a key that is unwritten, unset, never published or omitted, joined to a mention
#     of a declared or default value inside the same sentence and no more than about sixty
#     characters apart, in either order, so a sentence about something else that happens to
#     contain both words is not read as a claim;
#   * the mention of an empty string or a declared/default value, whichever the writer chose;
#   * no negation between the two, because the corrected page states the measured rule by denying
#     the old one - the key "is not the empty string", it "never reads as its declared default" -
#     and a guard that could not tell a claim from its denial would fail the true sentence.
UNWRITTEN_KEY_CLAIM = re.compile(
    r"(?:"
    r"\b(?:unwritten|unset|unpublished|omitted|unseeded)\b"
    r"|\bnever\b[^.;\n]{0,40}?\b(?:writ\w*|publish\w*|seed\w*|set)\b"
    r")"
    r"[^.;\n]{0,60}?\b(?:read\w*\s+as|resolve\w*\s+to|reach\w*|carr\w*|defaults?\s+to|takes|keeps|retains|remains)"
    r"[^.;\n]{0,60}?\b(?:empty\s+string|declared\s+(?:default|value|fallback)|default\s+value)\b"
    r"|"
    r"\b(?:read\w*\s+as|resolve\w*\s+to|carr\w*|defaults?\s+to|takes|keeps|retains|remains)"
    r"[^.;\n]{0,60}?\b(?:unwritten|unset|unpublished|omitted|unseeded)\b"
    r"(?!\W*(?:not|never|no)\b)[^.;\n]{0,60}?\b"
    r"(?:empty\s+string|declared\s+(?:default|value|fallback)|default\s+value)\b",
    re.I,
)

# The two consequences the page must name, each as the mechanism rather than as one sentence.
#
# The tokens are matched inside a single sentence, in any order, for the same reason the
# rejection guard is sentence-scoped: a `[^.;]` window over flattened text still crosses a
# sentence boundary, because the full stop that ends the sentence is not in the excluded set.
# Requiring both tokens of a consequence in one sentence is the tighter, and the truer, test.
GATE_CONSEQUENCE_TOKENS = ("gate", "skip")
SELECTOR_CONSEQUENCE_TOKENS = ("completion-fact", "fail")
PATH_CONSEQUENCE_TOKENS = ("empty path", "validator")


def sentences_naming(sentences: Iterable[str], tokens: tuple[str, ...]) -> list[str]:
    """The sentences that use every one of `tokens`, in any order."""
    found: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if all(token in lowered for token in tokens):
            found.append(sentence)
    return found


def claims_a_default_fills_an_unwritten_key(sentence: str) -> list[str]:
    """The claimed fallbacks in one sentence.

    An empty list means the sentence makes no such claim. The function is total over prose and
    is exercised by the shipped page and by the guard's own regression fixture.
    """
    return [match.group(0) for match in UNWRITTEN_KEY_CLAIM.finditer(flatten(sentence))]


def ordering_sentences(text: str) -> list[str]:
    """The document's prose as sentences, with the markup around it removed.

    A Markdown link keeps its visible text and loses its target; emphasis and code ticks are
    dropped; `_` becomes a space, so `independent_review` reads as the two words a human sees.
    """
    prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    prose = prose.replace("`", "").replace("**", "").replace("_", " ")
    return [part.strip() for part in SENTENCE_SPLIT.split(flatten(prose)) if part.strip()]


def ordering_clauses(text: str) -> list[tuple[str, str]]:
    """Every `(sentence, clause)` pair of the document's prose.

    The clause is the unit of the property, not the sentence: the shipped pages state both
    lifecycles inside one sentence, separated by `;` or `:`, and a rewording may move a claim
    anywhere inside its own clause without changing what it says.
    """
    return [
        (sentence, clause.strip())
        for sentence in ordering_sentences(text)
        for clause in CLAUSE_SPLIT.split(sentence)
        if clause.strip()
    ]


def path_scope(text: str) -> str:
    """Which lifecycle a piece of text says it is describing."""
    adaptive = ADAPTIVE_PATH.search(text) is not None
    full = FULL_LIFECYCLE_PATH.search(text) is not None
    if adaptive and full:
        return "both"
    if adaptive:
        return "adaptive"
    if full:
        return "full"
    return ""


def report_before_review_offences(name: str, text: str) -> list[str]:
    """Every clause that puts the report before a review on a path where that is false.

    A claim is legal only when it is scoped to the adaptive path. The clause's own scope wins; a
    clause that names no path inherits its sentence's scope, so a colon-separated sentence that
    names the path once still scopes the clause that carries the claim.
    """
    offences: list[str] = []
    for sentence, clause in ordering_clauses(text):
        if REPORT_BEFORE_REVIEW.search(clause) is None:
            continue
        scope = path_scope(clause) or path_scope(sentence)
        if scope == "adaptive":
            continue
        offences.append(
            f"{name}: report-before-review claim scoped to {scope or 'no path'}: {clause}"
        )
    return offences


def full_lifecycle_review_clauses(text: str) -> list[str]:
    """Clauses that tie a bridge-, solution- or full-lifecycle-scoped review to the report."""
    return [
        clause
        for _sentence, clause in ordering_clauses(text)
        if FULL_LIFECYCLE_PATH.search(clause)
        and REPORT_ONLY.search(clause)
        and REVIEW_ONLY.search(clause)
    ]


def top_level_template_ids(spec_path: Path) -> list[str]:
    spec = json.loads(read(spec_path))
    children = spec["root"].get("children", []) or []
    return [str(child.get("template_id", "")) for child in children]


def v12_declared_loop_bound(source: str) -> str:
    """Read the literal V12 compares the spec's loop bound against."""
    position = source.find("loop.max_iterations")
    if position < 0:
        raise AssertionError("validate_report.py no longer mentions loop.max_iterations")
    match = re.search(r'"(\d+)"', source[position : position + 400])
    if match is None:
        raise AssertionError("cannot find V12's declared loop bound literal")
    return match.group(1)


class BlackboardInventoryTests(unittest.TestCase):
    """G-25: the Skill page's blackboard block must be the specification's partition."""

    def setUp(self) -> None:
        self.page = read(SKILL_PAGE)
        self.spec = json.loads(read(FLOW_SPEC))
        self.spec_keys = set(self.spec["blackboard"])

    def test_skill_blackboard_block_matches_the_specification(self) -> None:
        caller_block = fenced_block_containing(self.page, 'report.path=""')
        caller = dict(re.findall(r'report\.([a-z_]+)="([^"]*)"', caller_block))
        caller = {f"report.{name}": value for name, value in caller.items()}

        node_block = fenced_block_containing(self.page, "report.head_current")
        node = {f"report.{name}" for name in re.findall(r"report\.([a-z_]+)", node_block)}

        self.assertEqual(
            caller,
            FROZEN_CALLER_KEYS,
            "the caller half of the blackboard block must equal the frozen thirteen-key set "
            "with its declared defaults",
        )
        self.assertEqual(
            len(FROZEN_CALLER_KEYS),
            13,
            "the frozen caller-seeded key set is thirteen keys",
        )
        self.assertEqual(
            caller.keys() & node,
            set(),
            "the caller half and the node half must be disjoint; the block is a partition",
        )
        self.assertEqual(
            caller.keys() | node,
            self.spec_keys,
            "the union of the two halves must equal the specification's declared key set",
        )
        self.assertEqual(
            node,
            self.spec_keys - set(FROZEN_CALLER_KEYS),
            "the node half is exactly the specification's keys the caller does not seed",
        )
        self.assertIn("partition", self.page)
        self.assertIn("26 keys", self.page)

    def test_every_declared_key_is_named_by_exactly_one_half(self) -> None:
        caller_block = fenced_block_containing(self.page, 'report.path=""')
        node_block = fenced_block_containing(self.page, "report.head_current")
        caller_names = [f"report.{name}" for name in re.findall(r"report\.([a-z_]+)", caller_block)]
        node_names = [f"report.{name}" for name in re.findall(r"report\.([a-z_]+)", node_block)]
        self.assertEqual(len(caller_names), len(set(caller_names)))
        self.assertEqual(len(node_names), len(set(node_names)))
        self.assertEqual(sorted(set(caller_names) | set(node_names)), sorted(self.spec_keys))


class EmbeddedSubtreeDefaultTests(unittest.TestCase):
    """The Skill page's blackboard rule must state the measured embedding behaviour."""

    def setUp(self) -> None:
        self.page = read(SKILL_PAGE)
        self.section = blackboard_section(self.page)

    def test_the_shipped_page_never_claims_a_default_fills_an_unwritten_key(self) -> None:
        offenders = [
            sentence
            for sentence in prose_sentences(self.section)
            if claims_a_default_fills_an_unwritten_key(sentence)
        ]
        self.assertEqual(
            offenders,
            [],
            "embedding a subtree copies no child template defaults, so the page must never claim "
            "that an unwritten caller key reads as, carries, or defaults to a declared value; it is "
            f"absent from the mounted blackboard: {offenders}",
        )

    def test_the_page_states_absence_and_both_consequences(self) -> None:
        section = flatten(self.section)
        sentences = prose_sentences(self.section)

        for token in ("unwritten", "declared", "absent"):
            self.assertIn(
                token,
                section,
                f"the blackboard section must state the rule in terms of {token!r}: an unwritten "
                "caller key is absent, not filled in from the child template's declaration",
            )

        for label, tokens, why in (
            (
                "the human-gate consequence",
                GATE_CONSEQUENCE_TOKENS,
                "the section must name the consequence of an omitted gate key: the absent key "
                "resolves the guard false, the gate is skipped, and the subtree still seals",
            ),
            (
                "the completion-fact selector consequence",
                SELECTOR_CONSEQUENCE_TOKENS,
                "the section must name the consequence of an unseeded completion-fact source: the "
                "node fails on a missing selector source instead of naming the key the caller owed",
            ),
            (
                "the empty-path consequence",
                PATH_CONSEQUENCE_TOKENS,
                "the section must name the consequence of an unwritten report.path: an empty path "
                "reaches the validator, which reports a generic file error",
            ),
        ):
            self.assertNotEqual(
                sentences_naming(sentences, tokens),
                [],
                f"{why}; no sentence of the blackboard section uses all of {tokens!r}",
            )

    def test_the_guard_fails_reworded_claims_and_spares_measured_ones(self) -> None:
        """The guard's own regression fixture: the property, not one phrasing, is what fails.

        The first sample is the pre-fix wording of the shipped page, kept as historical defect
        evidence - it is the claim this suite used to pass, not guidance. The samples after it
        are rewordings no literal match can reach. The control is the corrected sentence.
        """
        broken = {
            "the pre-fix shipped sentence": (
                'A key that is declared but left unwritten reads as the empty string, so the '
                'caller half carries declared defaults and the group depends on them.'
            ),
            "a template default": (
                "An unwritten caller key reads as its declared default."
            ),
            "a template look-behind": (
                "A caller key the work order never publishes resolves to the declared default it "
                "carries in the flow specification."
            ),
            "a published-on-demand claim": (
                "A caller key that the work order never publishes reaches the mounted blackboard "
                "carrying its declared default until some writer publishes it."
            ),
        }
        for label, sample in broken.items():
            self.assertNotEqual(
                claims_a_default_fills_an_unwritten_key(flatten(sample)),
                [],
                f"the guard must fail the claim reworded as {label!r}",
            )

        fixed = [
            "An unwritten caller key is absent from the mounted blackboard, not the empty string "
            "and not the declared value.",
            "A key the caller never publishes is simply absent: no guard resolves it and the "
            "declared value on the tree is never substituted for it.",
        ]
        for sample in fixed:
            self.assertEqual(
                claims_a_default_fills_an_unwritten_key(flatten(sample)),
                [],
                f"the guard must not read the measured statement as a false claim: {sample!r}",
            )
        self.assertNotEqual(
            claims_a_default_fills_an_unwritten_key(
                flatten("A key that is declared but left unwritten reads as the empty string.")
            ),
            [],
            "the guard must actually fire on the pre-fix shape, or the control proves nothing",
        )

    def test_the_arbiter_states_the_measured_behaviour(self) -> None:
        """The rule's arbiter is the runtime protocol, and the page must agree with it."""
        embedding = read(SUBTREE_EMBEDDING)
        self.assertIn(
            "Child template defaults are not copied into the runtime blackboard",
            flatten(embedding),
            "the subtree-embedding reference is the page's arbiter for this rule and must still "
            "state that embedding copies no child defaults",
        )


class TwoStepPublishTests(unittest.TestCase):
    """G-26: the two-step publish requirement is normative in both documents."""

    def test_two_step_publish_is_normative(self) -> None:
        protocol = read(PROTOCOL)
        page = read(SKILL_PAGE)

        self.assertIn("**C25a**", protocol)
        clause = protocol.split("**C25a**", 1)[1].split("**C26**", 1)[0]
        for token in (
            "two steps",
            "before",
            "check_fact_mismatch",
            ".receipt",
            "--check-result-json",
        ):
            self.assertIn(token, clause, f"the C25a clause must state {token!r}")
        self.assertIn("report.units_total", clause)
        self.assertIn("report.round", clause)

        self.assertIn("two steps", page)
        self.assertIn("check_fact_mismatch", page)
        self.assertIn("C25a", page)


class PublisherTableTests(unittest.TestCase):
    """G-28: the protocol's publisher table equals the shipped specification's declaration."""

    def setUp(self) -> None:
        self.protocol = read(PROTOCOL)
        self.spec = json.loads(read(FLOW_SPEC))

    def test_protocol_publishers_match_the_shipped_spec(self) -> None:
        outer = next(
            node
            for node in spec_nodes(self.spec["root"])
            if node.get("template_id") == "report-pass-loop"
        )
        declared = json.loads(outer["metadata"]["rework_publishers"])
        declared_rows = sorted(
            (
                str(item["terminates_round"]),
                str(item["node"]),
                str(item["publishes"]),
            )
            for item in declared
        )
        self.assertEqual(
            sorted(protocol_publisher_rows(self.protocol)),
            declared_rows,
            "the protocol's publisher table must equal metadata.rework_publishers row for row",
        )

    def test_each_latch_key_has_exactly_one_named_publisher(self) -> None:
        rework = bm.REWORK_KEY
        recovery = bm.RECOVERY_KEY

        def publishers(key: str) -> set[str]:
            found: set[str] = set()
            pattern = re.escape(key) + r"\s*=\s*(?:true|false)"
            for node in spec_nodes(self.spec["root"]):
                text = " ".join(
                    str(node.get(field, ""))
                    for field in ("instructions", "deliverables", "acceptance")
                )
                if re.search(pattern, text):
                    found.add(str(node.get("template_id", "")))
            return found

        self.assertEqual(
            publishers(recovery),
            {"report-gate"},
            "report.gate_recovery_required must have exactly one publisher: report-gate",
        )
        self.assertEqual(
            publishers(rework),
            {"report-gate", "validate-final"},
            "the refresh latch is published by the gate's rework path and by validate-final only",
        )
        self.assertNotIn(
            "report-gate-recovery-group",
            publishers(rework),
            "the recovery group publishes no key of the refresh latch",
        )

        rows = protocol_publisher_rows(self.protocol)
        self.assertEqual(
            {row[1] for row in rows} | {"report-gate"},
            {row[1] for row in rows},
            "the publisher table names the nodes that publish the refresh latch",
        )
        self.assertIn("exactly one publisher", self.protocol)
        self.assertIn("`report-gate` publishes `true` for the two reworking outcomes", self.protocol)

    def test_every_routing_sentence_matches_a_guard_in_the_spec(self) -> None:
        guards: set[str] = set()
        for node in spec_nodes(self.spec["root"]):
            for field in ("when", "loop.continue_when", "loop.break_when"):
                value = str(node.get(field, "")).strip()
                if value:
                    guards.add(value)
        self.assertTrue(guards, "the specification must declare at least one guard")

        quoted = {
            match.group(1).strip()
            for match in re.finditer(r"`(report\.[a-z_]+ == (?:true|false))`", self.protocol)
        }
        self.assertTrue(quoted, "the protocol must quote the guards it routes on")
        self.assertEqual(
            sorted(quoted - guards),
            [],
            "every guard the protocol quotes must exist as a guard in the shipped spec",
        )


class CalibrationRecordTests(unittest.TestCase):
    """G-31, G-32 and RF-1: the record names every acceptance-gating constant and cannot drift."""

    REQUIRED = (
        "MAX_WRONG",
        "MAX_MISLEADING",
        "MAX_UNITS_MINIMAL",
        "MAX_ADDED_UNIT_LINES",
        "ADDED_UNIT_BLOCK_LINES",
        "MAX_UNIT_LINES_SNIPPET",
        "MIN_FIELD_CHARS",
        "PLACEHOLDER_TOKENS",
        "SYMBOL_ONLY_RE",
        "VERDICTS",
        "report-pass-loop.loop.max_iterations",
        "report-review-loop.loop.max_iterations",
        "V12.loop_bound_literal",
        "MAX_CHECK_MESSAGE_CHARS",
    )

    def setUp(self) -> None:
        self.protocol = read(PROTOCOL)
        self.rows = calibration_rows(
            self.protocol, "## Calibration record of the acceptance-gating constants"
        )
        self.validator_source = read(SCRIPTS / "validate_report.py")
        self.spec = json.loads(read(FLOW_SPEC))

    def live_values(self) -> dict[str, str]:
        loops = {
            f"{node['template_id']}.loop.max_iterations": str(node["loop.max_iterations"])
            for node in spec_nodes(self.spec["root"])
            if node.get("type") == "loop"
        }
        return {
            "MAX_WRONG": str(bm.MAX_WRONG),
            "MAX_MISLEADING": str(bm.MAX_MISLEADING),
            "MAX_UNITS_MINIMAL": str(bm.MAX_UNITS_MINIMAL),
            "MAX_ADDED_UNIT_LINES": str(bm.MAX_ADDED_UNIT_LINES),
            "ADDED_UNIT_BLOCK_LINES": str(bm.ADDED_UNIT_BLOCK_LINES),
            "MAX_UNIT_LINES_SNIPPET": str(bm.MAX_UNIT_LINES_SNIPPET),
            "MIN_FIELD_CHARS": str(bm.MIN_FIELD_CHARS),
            "PLACEHOLDER_TOKENS": (
                f"{len(bm.PLACEHOLDER_TOKENS)} tokens ({', '.join(bm.PLACEHOLDER_TOKENS)})"
            ),
            "SYMBOL_ONLY_RE": bm.SYMBOL_ONLY_RE.pattern,
            "VERDICTS": ", ".join(bm.VERDICTS),
            "V12.loop_bound_literal": v12_declared_loop_bound(self.validator_source),
            "MAX_CHECK_MESSAGE_CHARS": str(
                load_module("_protocol_validate_report", SCRIPTS / "validate_report.py")
                .MAX_CHECK_MESSAGE_CHARS
            ),
            **loops,
        }

    def test_calibration_record_names_every_acceptance_gating_constant(self) -> None:
        for name in self.REQUIRED:
            self.assertIn(name, self.rows, f"the calibration record must name {name}")

    def test_every_recorded_value_equals_its_live_value(self) -> None:
        live = self.live_values()
        for name in self.REQUIRED:
            with self.subTest(constant=name):
                self.assertIn(name, live, f"{name} has no live value to compare against")
                self.assertEqual(
                    self.rows[name]["value"],
                    live[name],
                    f"the recorded value of {name} has drifted from its live value",
                )

    def test_record_names_the_missing_data_classes_and_the_future_procedure(self) -> None:
        section = flatten(
            self.protocol.split("## Calibration record of the acceptance-gating constants", 1)[1]
            .split("## Three failure states", 1)[0]
        )
        self.assertIn("The missing data classes", section)
        self.assertIn("procedure a future calibration must follow", section)
        self.assertIn("is a data point, never a base rate", section)
        for anchor_id in ("MAX_WRONG", "MAX_MISLEADING", "MAX_UNITS_MINIMAL"):
            self.assertIn(anchor_id, section)
        for data_class in (
            "error budget",
            "round-count distribution",
            "adjudication corpus",
        ):
            self.assertIn(data_class, section)
        self.assertIn("Inventing a number", section)
        self.assertIn("wrong > MAX_WRONG", section)
        self.assertIn("`wrong != MAX_WRONG`", section)

    def test_strength_constants_are_mirrored_in_the_contract(self) -> None:
        contract = read(CONTRACT)
        rows = calibration_rows(contract, "### Calibration record of the strength constants")
        self.assertEqual(rows["MAX_UNITS_MINIMAL"]["value"], str(bm.MAX_UNITS_MINIMAL))
        self.assertEqual(rows["STRENGTHS"]["value"], ", ".join(bm.STRENGTHS))
        self.assertIn("in one change", contract)


class PassBoundTests(unittest.TestCase):
    """G-33: one declared pass bound, agreed by the protocol, the spec, the template and V12."""

    def test_declared_pass_bound_matches_spec_and_validator(self) -> None:
        protocol = read(PROTOCOL)
        spec = json.loads(read(FLOW_SPEC))
        template = ElementTree.fromstring(read(TEMPLATE))

        outer = next(
            node
            for node in spec_nodes(spec["root"])
            if node.get("template_id") == "report-pass-loop"
        )
        self.assertEqual(str(outer["loop.max_iterations"]), "3")
        self.assertEqual(str(outer["loop.on_limit"]), "failed")

        template_bounds = [
            element.get("loop.max_iterations")
            for element in template.iter()
            if element.get("loop.max_iterations")
        ]
        self.assertEqual(template_bounds, ["3", "3"])

        validator_literal = v12_declared_loop_bound(read(SCRIPTS / "validate_report.py"))

        clause = protocol.split("**C19a**", 1)[1].split("**C20**", 1)[0]
        self.assertRegex(clause, r"max_iterations=3")
        self.assertIn("on_limit=failed", clause)

        self.assertEqual(
            {str(outer["loop.max_iterations"]), *template_bounds, validator_literal},
            {"3"},
            "the protocol's declared bound, the spec, the generated template and V12 must agree",
        )


class StrengthMatrixTests(unittest.TestCase):
    """G-35: every audit value the matrix names is a member of the shipped planning domain."""

    def test_strength_matrix_audit_values_are_in_the_shipped_domain(self) -> None:
        contract = read(CONTRACT)
        matrix = contract.split("## Strength matrix", 1)[1].split("### Calibration record", 1)[0]

        named: list[str] = []
        for match in re.finditer(r"`audit=([a-z-]+)`", matrix):
            named.append(match.group(1))
        for match in re.finditer(r"`audit in \{([^}]*)\}`", matrix):
            named.extend(
                item.strip().strip("`") for item in match.group(1).split(",") if item.strip()
            )
        self.assertTrue(named, "the strength matrix must select on at least one audit value")

        policy = load_module("_protocol_plan_work_policy", PLAN_POLICY)
        domain = set(policy.VALUES["audit"])
        self.assertEqual(domain, {"runtime-only", "result", "full", "unknown"})
        for value in named:
            self.assertIn(value, domain, f"the strength matrix names audit={value}")

        self.assertNotIn("audit=none", contract)
        self.assertNotIn("audit=required", contract)


class OrderingStatementTests(unittest.TestCase):
    """G-53: one ordering statement is normative and the affected documents agree with it."""

    def setUp(self) -> None:
        self.protocol = read(PROTOCOL)

    def test_normative_ordering_clause_agrees_with_the_shipped_topology(self) -> None:
        self.assertIn("**O9**", self.protocol)
        clause = flatten(
            self.protocol.split("**O9**", 1)[1].split("## Lifecycle coverage", 1)[0]
        )
        for token in (
            "full lifecycle",
            "last group before the result document",
            "no top-level review node",
            "adaptive path",
            "main-session policy",
        ):
            self.assertIn(token, clause, f"O9 must state {token!r}")

        page = flatten(read(SKILL_PAGE))
        for token in ("last group before the result document", "no top-level review node", "O9"):
            self.assertIn(token, page, f"the Skill page must state {token!r}")

        # The protocol's order is the shipped topology, not an opinion: the host template mounts
        # the groups in exactly this order and mounts no top-level review node.
        continuation = child_template_ids(WORK_ORDER_SPEC, "approved-solution-continuation")
        self.assertIn("report-group", continuation)
        report_position = continuation.index("report-group")
        self.assertEqual(continuation[report_position + 1], "result-document")
        self.assertEqual(continuation[report_position - 1], "verification-group")
        self.assertEqual(continuation[0], "implementation-group")
        for level, names in (
            ("root", top_level_template_ids(WORK_ORDER_SPEC)),
            ("approved-solution-continuation", continuation),
        ):
            self.assertEqual(
                [name for name in names if "review" in name],
                [],
                f"the full lifecycle mounts no top-level review node at the {level} level",
            )

    def test_one_ordering_statement_is_normative(self) -> None:
        documents = {
            "skills/xc-change-report/SKILL.md": read(SKILL_PAGE),
            "skills/xc-work/SKILL.md": read(WORK_SKILL_PAGE),
            "docs/workflows/running.md": read(DOC_RUNNING),
            "docs/workflows/choosing.md": read(DOC_CHOOSING),
            "docs/reference/skills/implementation-and-quality.md": read(DOC_SKILL_REFERENCE),
        }

        # The property is not an opinion: it is the specification's own order. If the shipped
        # topology ever gains a review node next to the report group, this test must be re-derived
        # instead of quietly passing.
        continuation = child_template_ids(WORK_ORDER_SPEC, "approved-solution-continuation")
        report_position = continuation.index("report-group")
        self.assertEqual(
            (continuation[report_position - 1], continuation[report_position + 1]),
            ("verification-group", "result-document"),
            "the report group's shipped position decides which order a document may claim for the "
            "full lifecycle",
        )
        self.assertEqual(
            [name for name in continuation if "review" in name],
            [],
            "the full lifecycle's approved continuation mounts no review node",
        )

        # Half one: the report-before-review order may be claimed only for the adaptive path. The
        # assertion is over the extracted claim, not over a phrasing, so a rewording of the false
        # statement fails exactly like the wording it replaced.
        offenders: list[str] = []
        for name, text in documents.items():
            offenders.extend(report_before_review_offences(name, text))
        self.assertEqual(
            offenders,
            [],
            "a document may put the report before a review only on the adaptive path, where O9 "
            "makes that order main-session policy; the full lifecycle mounts no review node "
            f"between the report group and the result document: {offenders}",
        )

        # Half two: a document that raises a bridge- or solution-required review next to the
        # report must state the full lifecycle's real order, in which that review is extra work
        # inside the implementation path and happens before the report rather than between the
        # report and the result document.
        unstated: list[str] = []
        for name, text in documents.items():
            bridge_clauses = full_lifecycle_review_clauses(text)
            if bridge_clauses and not any(
                REVIEW_BEFORE_REPORT.search(clause) for clause in bridge_clauses
            ):
                unstated.append(name)
        self.assertEqual(
            unstated,
            [],
            "a document that names a bridge- or solution-required review beside the report must "
            f"place that review before the report: {unstated}",
        )

        # The adaptive order is the other half of the same statement and the page that carries it
        # must name it as policy, not as a mechanism the engine enforces.
        self.assertRegex(
            read(WORK_SKILL_PAGE),
            MAIN_SESSION_POLICY,
            "the adaptive ordering must be declared main-session policy, not a runtime mechanism",
        )

    def test_the_ordering_guard_fails_reworded_claims_and_spares_correct_ones(self) -> None:
        """The guard's own regression fixture: the property, not one phrasing, is what fails.

        The first sample is the pre-fix wording of `skills/xc-work/SKILL.md`'s report paragraph,
        kept as historical defect evidence - it is the claim the literal guard could not see, not
        guidance. The samples after it are rewordings no literal match can reach. The controls are
        the shipped statements, which must not be read as claims of that shape.
        """
        reworded = {
            "the pre-fix xc-work sentence": (
                "When the adaptive path selects `independent_review`, or the project bridge adds "
                "a review step, produce the report before that review: the report is the "
                "reviewer's input, and a review that changes code refreshes it once more "
                "afterwards."
            ),
            "an imperative reordering": (
                "The project bridge may add a review step, so write the report first and let the "
                "review read it."
            ),
            "a verb marker": (
                "For the full lifecycle the report is produced ahead of that review, so the "
                "reviewer reads it."
            ),
            "an unscoped claim": (
                "The report is generated before the independent review of the change."
            ),
        }
        for label, sample in reworded.items():
            self.assertNotEqual(
                report_before_review_offences(label, sample),
                [],
                f"the guard must fail a report-before-review claim reworded as {label!r}",
            )

        full_lifecycle_control = (
            "In the full lifecycle the report group sits between the verification group and the "
            "result document: it is the last group before the result document, and that lifecycle "
            "mounts no top-level review node; a review a bridge or an approved solution requires "
            "is extra work inside the implementation path, so it happens before the report and "
            "never between the report and the result document."
        )
        adaptive_control = (
            "On the adaptive path the order is main-session policy, and there the report node is "
            "placed before an independent review leaf, so the reviewer reads the report."
        )
        for label, sample in (
            ("the shipped full-lifecycle sentence", full_lifecycle_control),
            ("the shipped adaptive sentence", adaptive_control),
        ):
            self.assertEqual(
                report_before_review_offences(label, sample),
                [],
                f"the guard must not read the shipped statement as a false claim: {label}",
            )
        self.assertTrue(
            REPORT_BEFORE_REVIEW.search(adaptive_control),
            "the adaptive control must actually carry a claim, or allowing it proves nothing",
        )
        self.assertTrue(
            REVIEW_BEFORE_REPORT.search(full_lifecycle_control),
            "the full-lifecycle control must actually carry the reverse order",
        )


class ContractInventoryTests(unittest.TestCase):
    """The contract-first vocabulary the implementation units are bound by."""

    def test_protocol_declares_the_new_categories_counters_and_checks(self) -> None:
        protocol = read(PROTOCOL)
        for token in (
            "`mode_change`",
            "`submodule`",
            "`adapter_install`",
            "ADAPTER_INSTALL_PATTERNS",
            "overlapped_pre_existing_total",
            "baseline_worktree_snapshot_empty",
            "baseline_worktree_snapshot_incomplete",
            "baseline_worktree_snapshot_missing",
            "baseline_untracked_snapshot_missing",
            "baseline_worktree_snapshot_unavailable",
            "**V15",
            "**V16",
            "**C4b**",
            "**C39**",
        ):
            self.assertIn(token, protocol, f"the protocol must declare {token}")

    def test_protocol_lifecycle_disposition_covers_every_entry_once(self) -> None:
        protocol = read(PROTOCOL)
        section = protocol.split("## Lifecycle coverage disposition", 1)[1]
        rows = re.findall(r"^\s*\|\s*(\d+)\s*\|", section, re.M)
        self.assertEqual([int(row) for row in rows], list(range(1, 17)))
        for disposition in ("produced-here", "produced-by-embedder", "none-and-not-needed"):
            self.assertIn(disposition, section)

    def test_exclusion_category_count_matches_the_declared_enumeration(self) -> None:
        protocol = read(PROTOCOL)
        clause = protocol.split("**C15**", 1)[1].split("**C16**", 1)[0]
        categories = re.findall(r"`([a-z_]+)`", clause.split("Adding a category", 1)[0])
        self.assertEqual(len(categories), 11)
        self.assertEqual(len(set(categories)), 11)
        for required in ("mode_change", "submodule", "adapter_install", "pre_existing_change"):
            self.assertIn(required, categories)

        # The implementation may only accept what the contract declares; the contract may not
        # lag the implementation. The comparison is a subset check in both directions of the
        # names, so a category added on either side without the other fails here.
        self.assertTrue(
            set(categories) >= set(bm.EXCLUSION_CATEGORIES),
            "the contract must declare every category the implementation accepts",
        )


# --------------------------------------------------------------------------------------
# V16: the clause, the failure-mode row and the check must state one relation
# --------------------------------------------------------------------------------------

# The property both sides of the V16 contract must carry: the index half of the relation is a
# relation of *change*, so an entry the baseline commit already records at that same mode and
# object is out of scope. It is extracted as a property rather than quoted as a literal, for the
# same reason the ordering guard above is: a literal matches one wording, and this binding exists
# because a sentence had drifted away from the check it describes while the suite stayed green.
# The window stops at a sentence or clause boundary, so the `baseline_commit` argument name in
# the command the clause quotes cannot satisfy it.
V16_CHANGE_TEST = re.compile(
    r"\bbaseline\b[^.;]{0,160}?\b(?:record\w*|hold\w*|held|unchanged|identical|"
    r"same mode and object|not a change)\b",
    re.I,
)

# The third V16 source, as the check runs it. The clause and the failure-mode row must name this
# exact command, because a sentence that still counts two sources describes a check nobody runs:
# with two sources a path that reaches the enumeration as an untracked file leaves `files[]` with
# no row, no exclusion and no degradation while the run still reports `coverage=complete`.
V16_UNTRACKED_COMMAND = "git ls-files --others --exclude-standard -z"


def protocol_v16_clause(protocol: str) -> str:
    """The V16 bullet of the check list: its heading plus its own continuation lines.

    The bullet is the last list item of the check list, so the end of it is the blank line that
    closes the list - not the next bullet, which does not exist below it.
    """
    marker = "**V16 Enumeration is complete**"
    if marker not in protocol:
        raise AssertionError("the protocol no longer declares a V16 clause")
    clause = marker + protocol.split(marker, 1)[1].split("\n\n", 1)[0]
    if "V16 runs at both stages." not in clause:
        raise AssertionError("the V16 clause is not the bullet this guard expects")
    return clause


def protocol_v16_failure_row(protocol: str) -> str:
    """The one failure-mode table row whose detector column is V16."""
    rows = [
        line
        for line in protocol.splitlines()
        if line.startswith("|") and re.search(r"\|\s*V16\s*\|", line)
    ]
    if len(rows) != 1:
        raise AssertionError(f"expected exactly one V16 failure-mode row, found {len(rows)}")
    return rows[0]


class EnumerationCompletenessContractTests(unittest.TestCase):
    """V16's normative text and V16's check must decide the same cases (G-30, G-38).

    The narrowing this binds: the index source of the completeness relation demands a `files[]`
    row only for an entry that actually **changed**, measured against the baseline commit's own
    mode and object id. The wide relation the clause used to state - every index entry whose mode
    is not `100644`/`100755`, with no change test - reported a complete manifest as incomplete,
    and the failure-mode row repeated the same wide claim.

    Both directions are pinned. The clause and the row must carry the change test, so a sentence
    that drifts back to the wide relation fails; and the check must implement exactly that change
    test on the cases the sentence describes, so a check that drifts fails too.
    """

    COMMIT = "5" * 40
    OBJECT = "a" * 40
    OTHER_OBJECT = "b" * 40
    # `git ls-files -s -z` output: one ordinary tracked file and one mode-`120000` entry, which is
    # the shape a byte diff of the worktree cannot see.
    INDEX_PAYLOAD = (
        b"100644 " + b"c" * 40 + b" 0\tsrc/app.py\x00"
        b"120000 " + b"a" * 40 + b" 0\tstable-link.txt\x00"
    )
    DIFF_PAYLOAD = b"M\x00src/app.py\x00"
    # `git ls-files --others --exclude-standard -z` output: the third V16 source. The second
    # `ls-files` form must never be served the index payload, so this stub discriminates on the
    # form before it answers and a case may supply its own bytes.
    UNTRACKED_PAYLOAD = b""

    def run_v16(
        self,
        baseline_entries: dict[str, dict[str, str]],
        files: list[str],
        untracked_payload: bytes | None = None,
        degradations: list[str] | None = None,
    ) -> tuple[vr.Checker, dict[str, Any]]:
        """`check_v16` with its three git reads supplied directly.

        The end-to-end form over a real repository - the one that proves git really reports these
        shapes - is `tests/test_xc_change_report_validation.py::EnumerationCompletenessTests`.
        This half supplies the payloads so the relation the sentence states can be tested case by
        case against the shipped check body.

        The stub answers the two `ls-files` forms differently: `--others` is the untracked
        enumeration and `-s` is the index, so a case that omits `untracked_payload` sees an
        untracked source that reports nothing rather than index records misread as paths.
        """
        manifest = {
            "baseline": {"commit": self.COMMIT},
            "files": [{"path": path} for path in files],
        }
        if degradations:
            manifest["degradations"] = list(degradations)

        def fake_run_git(repo: Path, args: list[str]) -> bytes:
            if args[0] == "diff":
                return self.DIFF_PAYLOAD
            if args[0] == "ls-files":
                if "--others" in args:
                    return self.UNTRACKED_PAYLOAD if untracked_payload is None else untracked_payload
                return self.INDEX_PAYLOAD
            raise AssertionError(f"unexpected git command: {args}")

        with mock.patch.object(vr, "run_git", fake_run_git), mock.patch.object(
            vr, "tree_entries", lambda repo, commit: baseline_entries
        ):
            checker = vr.Checker()
            status = vr.check_v16(checker, manifest, Path("."))
        return checker, status

    def test_the_v16_clause_and_row_state_the_change_test(self) -> None:
        protocol = read(PROTOCOL)
        clause = protocol_v16_clause(protocol)
        row = protocol_v16_failure_row(protocol)

        # The clause keeps the relation's own vocabulary: both scopes, and the modes the index
        # source is measured at.
        self.assertIn("every path changed `O -> H`", clause)
        self.assertIn("`100644`/`100755`", clause)
        self.assertRegex(
            clause,
            V16_CHANGE_TEST,
            "the V16 clause must state that an index entry the baseline commit already records "
            "at that same mode and object is not a dropped path",
        )
        self.assertRegex(
            row,
            V16_CHANGE_TEST,
            "the V16 failure-mode row must carry the same change test as the clause, not the wide "
            "claim that any path a git source reports is a dropped path",
        )

    def test_the_check_decides_the_cases_the_sentence_describes(self) -> None:
        recorded = {"stable-link.txt": {"mode": "120000", "sha": self.OBJECT}}
        files = ["src/app.py"]

        # 1. The entry the baseline already records at that same mode and object is not a change,
        #    so it owes no row. This is the case the wide relation got wrong: the manifest here is
        #    complete and used to be reported as incomplete.
        checker, status = self.run_v16(recorded, files)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["index_modes"], 0)
        self.assertEqual(status["unchanged_index_modes"], 1)
        self.assertEqual(status["missing"], [])

        # 2. The baseline does not record the path at all: the entry is a change.
        checker, status = self.run_v16({}, files)
        self.assertFalse(checker.ok, "a link the baseline does not record must fail V16")
        self.assertEqual(status["missing"], ["stable-link.txt"])

        # 3. Same mode, different object: a retargeted link is a change, so the object-id half of
        #    the test is not decoration.
        checker, status = self.run_v16(
            {"stable-link.txt": {"mode": "120000", "sha": self.OTHER_OBJECT}}, files
        )
        self.assertFalse(checker.ok, "a retargeted link must fail V16")
        self.assertEqual(status["missing"], ["stable-link.txt"])

        # 4. Same object, different mode: a mode change is a change.
        checker, status = self.run_v16(
            {"stable-link.txt": {"mode": "100644", "sha": self.OBJECT}}, files
        )
        self.assertFalse(checker.ok, "a mode change must fail V16")
        self.assertEqual(status["missing"], ["stable-link.txt"])

        # 5. The narrowing is the index source's alone: a changed path the diff reports and
        #    `files[]` omits still fails.
        checker, status = self.run_v16(recorded, [])
        self.assertFalse(checker.ok, "a dropped changed path must still fail V16")
        self.assertEqual(status["missing"], ["src/app.py"])

    def test_an_untracked_path_is_judged_by_the_untracked_form(self) -> None:
        """The third source is answered by `--others`, not by the index payload.

        The stub above used to answer every `ls-files` form with the index payload, so the check
        received index records where it expects untracked path names and reported two fabricated
        "paths" for a complete manifest. This is the pre-fix shape, pinned here: the untracked
        form's own payload is what decides the outcome, in both directions.
        """
        recorded = {"stable-link.txt": {"mode": "120000", "sha": self.OBJECT}}
        files = ["src/app.py"]

        # An untracked path with no row is the drop the third source exists to catch.
        checker, status = self.run_v16(
            recorded, files, untracked_payload=b"notes/scratch.md\x00"
        )
        self.assertFalse(checker.ok, "a dropped untracked path must fail V16")
        self.assertEqual(status["missing"], ["notes/scratch.md"])
        # `untracked_paths` counts the paths this source attributed - to a `files[]` row, to a
        # recorded-path degradation, or to the failed relation - so it is the number of untracked
        # paths the check judged, not a count of the ones it accepted.
        self.assertEqual(status["untracked_paths"], 1)
        self.assertEqual(status["recorded_unreadable"], [])
        self.assertEqual(status["unchanged_untracked"], 0)
        self.assertEqual(
            [item["message"] for item in checker.errors],
            [
                "the enumeration is incomplete: path 'notes/scratch.md' is reported by "
                f"{V16_UNTRACKED_COMMAND} but is absent from files[] and named by no "
                "recorded-path degradation"
            ],
        )

        # A recorded-path degradation names it, so the same path is accounted for.
        checker, status = self.run_v16(
            recorded,
            files,
            untracked_payload=b"notes/scratch.md\x00",
            degradations=["untracked_snapshot_path_lost:notes/scratch.md"],
        )
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["missing"], [])
        self.assertEqual(status["recorded_unreadable"], ["notes/scratch.md"])
        self.assertEqual(status["untracked_paths"], 1)

        # The exception is per path: the same payload with a degradation about another path
        # leaves `notes/scratch.md` unnamed, which is still the silent drop.
        checker, status = self.run_v16(
            recorded,
            files,
            untracked_payload=b"notes/scratch.md\x00",
            degradations=["untracked_snapshot_path_lost:other/elsewhere.md"],
        )
        self.assertFalse(checker.ok, "a note about another path names nothing")
        self.assertEqual(status["missing"], ["notes/scratch.md"])

        # A path `files[]` already carries needs no exception.
        checker, status = self.run_v16(
            recorded, ["src/app.py", "notes/scratch.md"], untracked_payload=b"notes/scratch.md\x00"
        )
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["untracked_paths"], 1)

    def test_the_v16_clause_and_row_name_the_third_source_and_the_exception(self) -> None:
        """G-30, G-38: the sentence's source list and exception must match the shipped check.

        The clause and the row are read through the same extractors as the change test above.
        The recorded-path reasons are enumerated from the implementation's own vocabulary rather
        than quoted, so a reason added to `RECORDED_PATH_REASONS` without the clause naming it
        fails here, and a clause that promises a reason the check does not accept fails too. The
        check accepts the reason as `<reason>:<path>`, so the row names the prefix only.
        """
        protocol = read(PROTOCOL)
        clause = protocol_v16_clause(protocol)
        row = protocol_v16_failure_row(protocol)

        self.assertIn(V16_UNTRACKED_COMMAND, clause)
        self.assertIn(V16_UNTRACKED_COMMAND.split("ls-files ", 1)[1], row)
        self.assertIn("three independent git sources", row)
        self.assertIn("recorded-path degradation", row)

        # The exception mechanism: a recorded-path reason names the path it excuses.
        self.assertIn("recorded-path", clause)
        for reason in bm.RECORDED_PATH_REASONS:
            self.assertIn(f"`{reason}:`", clause, f"the clause must name the {reason} reason")
            self.assertIn(reason, row, f"the row must name the {reason} reason")
        self.assertIn("names it", clause)

        # And the negative half, which is what keeps the exception from swallowing a real drop:
        # the sentence has to say a path named by no such reason, or by a note about another
        # path, is still a drop.
        self.assertRegex(
            clause,
            r"silent drop|still fails|still fail",
            "the clause must keep an unnamed untracked path a failure",
        )


if __name__ == "__main__":
    unittest.main()
