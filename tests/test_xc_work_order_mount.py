"""Tests for the work-order mount of the `xc-change-report` stage.

The full lifecycle's report obligation has three properties that the shipped
specification must keep and that no other suite asserts at the specification level:

* `work_order.requires_report` defaults to `true`, so an unwritten commitment selects
  `report-group` instead of silently skipping it. A false default made the mount's only
  fail-closed property unreachable.
* `prepare-work-order` states the mode-derived commitment write, so the rule is executed
  by the node that owns it rather than described only in Skill prose.
* The `report-group` instruction names every caller-seeded `report.*` key and publishes
  the values this work order uses. Declaring the same thirteen keys on the parent tree is
  what makes an embedded subtree's guards, loop condition and completion-fact selectors
  resolve, because an embedded subtree brings no blackboard entry of its own; the parent
  key set is therefore the caller half of the report specification's 26-key set, frozen
  by name and declared default.

The template is a generated artifact, so the same module also proves that the shipped
template is byte-identical to a fresh build of the shipped specification.

Standard library only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-work"
SPEC_PATH = SKILL_ROOT / "assets" / "work-order-flow.json"
TEMPLATE_PATH = SKILL_ROOT / "assets" / "work-order-template.xml"
AUTHOR = REPOSITORY_ROOT / "skills" / "xc-orchestration-author" / "scripts" / "template_builder.py"

COMMITMENT_KEY = "work_order.requires_report"
SKIP_REASON_KEY = "work_order.report_skip_reason"
BASELINE_KEY = "work_order.report_baseline"
REPORT_GROUP = "report-group"
PREPARE_NODE = "prepare-work-order"
CONTRACT_FIELDS = ("instructions", "inputs", "deliverables", "acceptance")

# The caller-seeded half of the report specification's declared key set, frozen by name and
# declared default. The values are the report specification's own declared defaults, so the
# parent tree and the subtree it embeds cannot disagree about a key's starting value.
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

# The recorded installation path, which the mount references instead of leaving the template
# discoverable only from a documentation table.
SETUP_RECORD = ".agents/.xcoding-setup/manifest.json"
TEMPLATE_FILE_NAME = "change-report-template.xml"


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
    """The node's own contract text: what the node claims it will do."""
    return "\n".join(str(node.get(field, "")) for field in CONTRACT_FIELDS)


class WorkOrderMountTests(unittest.TestCase):
    def test_the_report_commitment_defaults_to_true(self) -> None:
        """G-16: an unwritten commitment selects the group instead of skipping it."""
        blackboard = load_spec()["blackboard"]
        self.assertIn(COMMITMENT_KEY, blackboard)
        self.assertEqual(
            blackboard[COMMITMENT_KEY],
            "true",
            "the commitment's default must be true, so a mode-derived value that was never "
            "written fails closed by selecting report-group",
        )
        group = nodes_by_template(load_spec())[REPORT_GROUP]
        self.assertEqual(group["when"], f"{COMMITMENT_KEY} == true")

    def test_the_declared_caller_key_set_equals_the_frozen_thirteen(self) -> None:
        """G-24: the caller half of the report key set is declared, by name and default."""
        declared = {
            key: value
            for key, value in load_spec()["blackboard"].items()
            if key.startswith("report.")
        }
        self.assertEqual(
            declared,
            FROZEN_CALLER_KEYS,
            "the work-order tree must declare exactly the thirteen caller-seeded report.* keys "
            "with their declared defaults and no other report.* key",
        )

    def test_prepare_states_the_mode_derived_commitment_write(self) -> None:
        """G-16: the node that owns the commitment states the write, not only Skill prose."""
        node = nodes_by_template(load_spec())[PREPARE_NODE]
        instructions = str(node["instructions"])
        acceptance = str(node["acceptance"])

        self.assertIn(f"{COMMITMENT_KEY}=true", instructions)
        self.assertIn(f"{SKIP_REASON_KEY}=read_only_mode", instructions)
        self.assertIn(BASELINE_KEY, instructions)
        self.assertIn("missing commitment fails this node", instructions)

        self.assertIn(f"{COMMITMENT_KEY} carries the mode's value", acceptance)
        self.assertIn(f"{SKIP_REASON_KEY}=read_only_mode", acceptance)
        self.assertIn(f"{BASELINE_KEY} records the baseline commit", acceptance)
        self.assertIn("missing commitment fails this node", acceptance)

    def test_mount_names_every_caller_key(self) -> None:
        """G-08, G-24: the caller's publication is named key by key, with edited values."""
        instructions = str(nodes_by_template(load_spec())[REPORT_GROUP]["instructions"])
        missing = sorted(key for key in FROZEN_CALLER_KEYS if key not in instructions)
        self.assertEqual(
            missing,
            [],
            "the mount instruction must name every caller-seeded report.* key, because a key "
            "the caller never publishes reads as an absent key inside the embedded subtree",
        )
        self.assertIn("thirteen caller-seeded keys", instructions)
        self.assertIn("never merely accepting their declared defaults", instructions)
        self.assertIn(
            "report.round is the 1-based index of the pass being entered",
            instructions,
            "the caller's share of the round convention is the pass index it publishes",
        )

    def test_mount_references_the_recorded_template_path(self) -> None:
        """G-48: the template path comes from the setup record, not a documentation table."""
        group = nodes_by_template(load_spec())[REPORT_GROUP]
        text = contract_text(group)
        self.assertIn(SETUP_RECORD, text)
        self.assertIn(TEMPLATE_FILE_NAME, text)
        self.assertIn("xc-change-report", text)

    def test_the_shipped_template_is_the_build_of_the_shipped_spec(self) -> None:
        """The template is generated: a hand-edited template fails this test."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "author-config.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            rebuilt = root / "work-order-template.xml"
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
