"""Tests for the `xc-change-report` orchestration package's gate, latch and round convention.

The report subtree has two control-flow properties that the shipped specification must keep
and that no other suite asserts at the specification level:

* `report.gate_recovery_required` has exactly one publisher, `report-gate`.
  `report-gate-recovery-group` is driven by that key and must never reset it, because a
  reset in the round the gate terminated would let `validate-final` judge a round the gate
  already closed before the reworked report reached the gate again.
* `report.round` is the 1-based index of the pass being entered, published before
  `prepare-manifest` runs; no node pre-increments it.

The template is a generated artifact, so the same module also proves that the shipped
template is byte-identical to a fresh build of the shipped specification.

Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SPEC_PATH = SKILL_ROOT / "assets" / "change-report-flow.json"
TEMPLATE_PATH = SKILL_ROOT / "assets" / "change-report-template.xml"
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"

RECOVERY_KEY = "report.gate_recovery_required"
ROUND_KEY = "report.round"
PREPARE_NODE = "prepare-manifest"
CONTRACT_FIELDS = ("instructions", "inputs", "deliverables", "acceptance")

# A publish statement, in the vocabulary the rest of the package uses to identify a writer:
# `key=value` with a single `=`, so a guard's `key == value` is not mistaken for a write.
PUBLISHES_RECOVERY_KEY = re.compile(re.escape(RECOVERY_KEY) + r"\s*=\s*(true|false)")
PUBLISHES_ANY_REPORT_KEY = re.compile(r"report\.[A-Za-z0-9_.]+\s*=\s*[^\s=]")

PRE_INCREMENT_PHRASES = (
    "increment report.round",
    "report.round++",
    "report.round + 1",
    "report.round+1",
    "report.round = report.round",
)


def load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def iter_nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []) or []:
        yield from iter_nodes(child)


def nodes_by_template(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("template_id", "")): node
        for node in iter_nodes(spec.get("root", {}))
    }


def contract_text(node: dict[str, Any]) -> str:
    """The node's own contract text: what the node claims it will write."""
    return "\n".join(str(node.get(field, "")) for field in CONTRACT_FIELDS)


class ChangeReportFlowTests(unittest.TestCase):
    def test_the_gate_is_the_recovery_keys_only_publisher(self) -> None:
        """G-27: one publisher, so no round can be closed by a second writer."""
        spec = load_spec()
        publishers: dict[str, list[str]] = {}
        for node in iter_nodes(spec.get("root", {})):
            values = sorted({match.group(1) for match in PUBLISHES_RECOVERY_KEY.finditer(contract_text(node))})
            if values:
                publishers[str(node.get("template_id", ""))] = values
        self.assertEqual(
            publishers,
            {"report-gate": ["false", "true"]},
            "the recovery key must have exactly one publisher, report-gate, publishing true for "
            "the two reworking outcomes and false for the two accepting ones",
        )

    def test_the_recovery_group_publishes_nothing_and_forbids_the_reset(self) -> None:
        """G-27: the group's own contract must leave the key to the gate."""
        recovery = nodes_by_template(load_spec())["report-gate-recovery-group"]
        text = contract_text(recovery)
        self.assertIn("leave the key untouched", text)
        self.assertNotIn(RECOVERY_KEY + "=false", text)
        self.assertIsNone(
            PUBLISHES_ANY_REPORT_KEY.search(text),
            "report-gate-recovery-group must publish no report.* key at all",
        )
        acceptance = str(recovery["acceptance"])
        self.assertIn("resets nothing", acceptance)
        self.assertIn("publishes no report.* key", acceptance)
        self.assertEqual(recovery["when"], f"{RECOVERY_KEY} == true")

    def test_the_round_convention_is_the_pass_index_and_is_not_pre_incremented(self) -> None:
        """G-29: the pass publishes its own 1-based index, before prepare-manifest."""
        loop = nodes_by_template(load_spec())["report-pass-loop"]
        text = contract_text(loop)
        self.assertIn(f"{ROUND_KEY} as the 1-based index of the pass being entered", text)
        self.assertIn(f"before {PREPARE_NODE} runs", text)
        self.assertIn(
            f"{ROUND_KEY} is the 1-based index of the pass being entered",
            str(loop["acceptance"]),
        )
        lowered = text.lower()
        for phrase in PRE_INCREMENT_PHRASES:
            self.assertNotIn(phrase, lowered, f"{phrase!r} pre-increments {ROUND_KEY}")

    def test_the_shipped_template_is_the_build_of_the_shipped_spec(self) -> None:
        """The template is generated: a hand-edited template fails this test."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "author-config.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            rebuilt = root / "change-report-template.xml"
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(SPEC_PATH),
                    "--out",
                    str(rebuilt),
                    "--config",
                    str(config),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["commit"]["status"], "disabled", payload)
            self.assertEqual(rebuilt.read_bytes(), TEMPLATE_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
