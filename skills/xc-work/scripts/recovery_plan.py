#!/usr/bin/env python3
"""Deterministic recovery-pattern command planner for main sessions.

Translates one recovery pattern from references/recovery-patterns.md into an
ordered sequence of documented runtime commands plus the required evidence.
Pure translation: it reads one JSON object from stdin or --input-file, writes
one JSON object to stdout, executes nothing, and writes nothing.

Input object:

    pattern            "p1"|"p2"|"p3"|"p4"          required
    node_id            runtime node ID               required
                       p1: failed leaf to retry
                       p2: blocked original leaf to unblock
                       p3: successor approval gate to complete
                       p4: node to keep blocked
    tree               runtime tree reference        optional; commands omit
                       --tree when absent
    reason             recovery reason               required, non-empty
    expected_revision  non-negative integer          optional; emitted only on
                       the first command

Pattern-specific optional fields:

    p2: group_id (owning dynamic group), reopen_group (bool, default false),
        new_node {logical_key (required, kebab-case), title (defaults to
        logical_key), type, role, executor, instructions, deliverables,
        acceptance, metadata (scalar map)}, before (blocked direct child),
        sets (blackboard key to scalar map), unblock (bool, default true)
    p3: recovery_group_id (solution recovery group), reopen_group (bool,
        default false), revision_node (same shape as p2 new_node),
        successor_gate (same shape plus outcomes (required, unique
        lowercase-kebab string array), decision_required (required bool),
        outcome_key (required blackboard key); type is forced to gate),
        gate_outcome (default "approved"), decision (optional text)
    p4: artifacts (string array for --artifact)

Success output: {"schema_version":1,"ok":true,"pattern":<pattern>,
"commands":[{"command":...,"args":[...],"note":...}],
"evidence_required":[...]} with sorted keys. Invalid input returns
{"schema_version":1,"ok":false,"error_code":<stable-code>}. Exit code is
always zero.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence

PATTERNS = ("p1", "p2", "p3", "p4")
COMMON_FIELDS = frozenset({"pattern", "node_id", "tree", "reason", "expected_revision"})
PATTERN_FIELDS = {
    "p1": frozenset(),
    "p2": frozenset({"group_id", "reopen_group", "new_node", "before", "sets", "unblock"}),
    "p3": frozenset(
        {"recovery_group_id", "reopen_group", "revision_node", "successor_gate", "gate_outcome", "decision"}
    ),
    "p4": frozenset({"artifacts"}),
}
NODE_FIELDS = frozenset(
    {"logical_key", "title", "type", "role", "executor", "instructions", "deliverables", "acceptance", "metadata"}
)
GATE_FIELDS = NODE_FIELDS | frozenset({"outcomes", "decision_required", "outcome_key"})
NODE_TYPES = frozenset({"composite", "gate", "loop", "task"})
EXECUTORS = frozenset({"main", "service", "subagent", "tool"})
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
GATE_OUTCOME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
BLACKBOARD_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

EVIDENCE = {
    "p1": [
        "failed-attempt-recorded-summary-and-artifacts",
        "accepted-contract-unchanged-confirmation",
        "retry-safety-reason",
    ],
    "p2": [
        "revised-plan-artifact",
        "republished-source-keys",
        "recorded-what-changed-and-why-statement",
    ],
    "p3": [
        "gate-evidence-collected",
        "focused-question-answer-recorded-as-structured-state",
        "revised-solution-artifact",
    ],
    "p4": [
        "blocker-evidence-collected",
        "focused-question",
        "recorded-decision",
    ],
}

NOTE_P1_RETRY = (
    "Archive the failed attempt and return the same leaf to ordinary scheduling; "
    "only a failed executable task or gate leaf qualifies."
)
NOTE_REOPEN_GROUP = "Auditable reopening of a closed dynamic group before inserting recovery nodes."
NOTE_P2_ADD = "Insert the explicitly approved recovery node before the blocked direct child."
NOTE_SET = "Publish the revised plan and source keys as short blackboard values."
NOTE_UNBLOCK = "Return the original blocked leaf to pending after the recovery node publishes the revised plan."
NOTE_P3_REVISION = "Append the revision node inside the solution recovery group."
NOTE_P3_GATE_ADD = (
    "Append the successor approval gate; it must atomically publish its outcome "
    "before consequential work continues."
)
NOTE_P3_COMPLETE = (
    "Complete the successor gate with its declared outcome after the main session "
    "records the answer; include --decision when the gate requires it."
)
NOTE_P4_BLOCK = (
    "Keep the node blocked with the external prerequisite and its evidence; open a "
    "main-session user gate and record one focused decision."
)


class RecoveryPlanError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def error_payload(code: str) -> dict[str, object]:
    return {"schema_version": 1, "ok": False, "error_code": code}


def scalar_string(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(value)


def validate(data: Mapping[str, object]) -> str | None:
    if not isinstance(data, dict):
        return "input_not_object"
    pattern = data.get("pattern")
    if pattern is None:
        return "missing_pattern"
    if not isinstance(pattern, str) or pattern not in PATTERNS:
        return "unknown_pattern"
    node_id = data.get("node_id")
    if node_id is None:
        return "missing_node_id"
    if not isinstance(node_id, str) or not node_id.strip():
        return "invalid_node_id"
    reason = data.get("reason")
    if reason is None:
        return "missing_reason"
    if not isinstance(reason, str) or not reason.strip():
        return "invalid_reason"
    tree = data.get("tree")
    if tree is not None and (not isinstance(tree, str) or not tree.strip()):
        return "invalid_tree"
    revision = data.get("expected_revision")
    if revision is not None and (
        isinstance(revision, bool) or not isinstance(revision, int) or revision < 0
    ):
        return "invalid_expected_revision"
    unknown = set(data) - COMMON_FIELDS - PATTERN_FIELDS[pattern]
    if unknown:
        return "unknown_field"
    return validate_pattern(pattern, data)


def validate_pattern(pattern: str, data: Mapping[str, object]) -> str | None:
    if pattern == "p1":
        return None
    if pattern == "p4":
        artifacts = data.get("artifacts")
        if artifacts is not None:
            if (
                not isinstance(artifacts, list)
                or any(not isinstance(item, str) or not item.strip() for item in artifacts)
            ):
                return "p4_invalid_artifacts"
        return None
    if pattern == "p2":
        reopen = data.get("reopen_group")
        if reopen is not None and not isinstance(reopen, bool):
            return "p2_invalid_flag"
        unblock = data.get("unblock")
        if unblock is not None and not isinstance(unblock, bool):
            return "p2_invalid_flag"
        group_id = data.get("group_id")
        needs_group = reopen is True or "new_node" in data
        if needs_group and group_id is None:
            return "p2_missing_group_id"
        if group_id is not None and (not isinstance(group_id, str) or not group_id.strip()):
            return "p2_invalid_group_id"
        before = data.get("before")
        if before is not None:
            if not isinstance(before, str) or not before.strip():
                return "p2_invalid_before"
            if "new_node" not in data:
                return "p2_invalid_before"
        if "new_node" in data:
            node = validate_node_spec(data["new_node"], "p2_new_node_invalid", NODE_FIELDS)
            if node is None:
                return "p2_new_node_invalid"
        sets = data.get("sets")
        if sets is not None:
            error = validate_scalar_map(sets, "p2_invalid_sets")
            if error:
                return error
        return None
    reopen = data.get("reopen_group")
    if reopen is not None and not isinstance(reopen, bool):
        return "p3_invalid_flag"
    group_id = data.get("recovery_group_id")
    needs_group = reopen is True or "revision_node" in data or "successor_gate" in data
    if needs_group and group_id is None:
        return "p3_missing_group_id"
    if group_id is not None and (not isinstance(group_id, str) or not group_id.strip()):
        return "p3_invalid_group_id"
    if "revision_node" in data:
        if validate_node_spec(data["revision_node"], "p3_revision_node_invalid", NODE_FIELDS) is None:
            return "p3_revision_node_invalid"
    if "successor_gate" in data:
        try:
            validate_gate_spec(data["successor_gate"])
        except RecoveryPlanError as error:
            return error.code
    gate_outcome = data.get("gate_outcome", "approved")
    if not isinstance(gate_outcome, str) or not gate_outcome.strip():
        return "p3_invalid_gate_outcome"
    decision = data.get("decision")
    if decision is not None and (not isinstance(decision, str) or not decision.strip()):
        return "p3_invalid_decision"
    return None


def validate_scalar_map(value: object, code: str) -> str | None:
    if not isinstance(value, dict):
        return code
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            return code
        if not isinstance(item, (str, int, float, bool)):
            return code
    return None


def validate_node_spec(value: object, code: str, fields: frozenset[str]) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    if set(value) - fields:
        return None
    logical_key = value.get("logical_key")
    if not isinstance(logical_key, str) or not KEBAB_RE.fullmatch(logical_key):
        return None
    title = value.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return None
    node_type = value.get("type")
    if node_type is not None and node_type not in NODE_TYPES:
        return None
    executor = value.get("executor")
    if executor is not None and executor not in EXECUTORS:
        return None
    for field in ("role", "instructions", "deliverables", "acceptance"):
        item = value.get(field)
        if item is not None and (not isinstance(item, str) or not item.strip()):
            return None
    metadata = value.get("metadata")
    if metadata is not None and validate_scalar_map(metadata, code):
        return None
    return value


def validate_gate_spec(value: object) -> dict[str, object]:
    spec = validate_node_spec(value, "p3_successor_gate_invalid", GATE_FIELDS)
    if spec is None:
        raise RecoveryPlanError("p3_successor_gate_invalid")
    outcomes = spec.get("outcomes")
    if outcomes is None:
        raise RecoveryPlanError("p3_successor_gate_invalid")
    if (
        not isinstance(outcomes, list)
        or not outcomes
        or any(not isinstance(item, str) or not GATE_OUTCOME_RE.fullmatch(item) for item in outcomes)
        or len(outcomes) != len(set(outcomes))
    ):
        raise RecoveryPlanError("invalid_gate_outcomes")
    if spec.get("type") is not None and spec["type"] != "gate":
        raise RecoveryPlanError("p3_successor_gate_invalid")
    decision_required = spec.get("decision_required")
    if decision_required is None:
        raise RecoveryPlanError("p3_successor_gate_invalid")
    if not isinstance(decision_required, bool):
        raise RecoveryPlanError("invalid_gate_decision_required")
    outcome_key = spec.get("outcome_key")
    if outcome_key is None:
        raise RecoveryPlanError("p3_successor_gate_invalid")
    if not isinstance(outcome_key, str) or not BLACKBOARD_KEY_RE.fullmatch(outcome_key):
        raise RecoveryPlanError("invalid_gate_outcome_key")
    return spec


def add_node_args(
    parent: str,
    spec: dict[str, object],
    before: str | None = None,
    forced_type: str | None = None,
    default_executor: str | None = None,
    extra_metadata: Mapping[str, object] | None = None,
) -> list[str]:
    logical_key = spec["logical_key"]
    title = spec.get("title") or logical_key
    args = ["--parent", parent, "--logical-key", str(logical_key), "--title", str(title)]
    node_type = forced_type or spec.get("type")
    if node_type is not None:
        args += ["--type", str(node_type)]
    role = spec.get("role")
    if role is not None:
        args += ["--role", str(role)]
    executor = spec.get("executor") or default_executor
    if executor is not None:
        args += ["--executor", str(executor)]
    for field in ("instructions", "deliverables", "acceptance"):
        item = spec.get(field)
        if item is not None:
            args += [f"--{field}", str(item)]
    metadata: dict[str, object] = {}
    declared = spec.get("metadata")
    if declared:
        metadata.update(declared)
    if extra_metadata:
        metadata.update(extra_metadata)
    for key in sorted(metadata):
        args += ["--metadata", f"metadata.{key}={scalar_string(metadata[key])}"]
    if before is not None:
        args += ["--before", before]
    return args


def translate(payload: dict[str, object]) -> dict[str, object]:
    pattern = payload["pattern"]
    tree = payload.get("tree")
    node_id = payload["node_id"]
    reason = payload["reason"]
    revision = payload.get("expected_revision")
    sequence: list[tuple[str, list[str], str]] = []
    if pattern == "p1":
        sequence.append(("retry-failed", ["--node", str(node_id), "--reason", str(reason)], NOTE_P1_RETRY))
    elif pattern == "p2":
        group_id = payload.get("group_id")
        if payload.get("reopen_group") is True:
            sequence.append(
                ("reopen-group", ["--group", str(group_id), "--reason", str(reason)], NOTE_REOPEN_GROUP)
            )
        new_node = payload.get("new_node")
        if new_node is not None:
            sequence.append(
                (
                    "add-node",
                    add_node_args(str(group_id), new_node, before=payload.get("before")),
                    NOTE_P2_ADD,
                )
            )
        sets = payload.get("sets")
        if sets:
            set_args: list[str] = []
            for key in sorted(sets):
                set_args += ["--set", f"{key}={scalar_string(sets[key])}"]
            sequence.append(("set", set_args, NOTE_SET))
        if payload.get("unblock", True) is True:
            sequence.append(("unblock", ["--node", str(node_id)], NOTE_UNBLOCK))
    elif pattern == "p3":
        group_id = payload.get("recovery_group_id")
        if payload.get("reopen_group") is True:
            sequence.append(
                ("reopen-group", ["--group", str(group_id), "--reason", str(reason)], NOTE_REOPEN_GROUP)
            )
        revision_node = payload.get("revision_node")
        if revision_node is not None:
            sequence.append(
                (
                    "add-node",
                    add_node_args(str(group_id), revision_node),
                    NOTE_P3_REVISION,
                )
            )
        successor_gate = payload.get("successor_gate")
        if successor_gate is not None:
            gate = dict(successor_gate)
            gate.setdefault("executor", "main")
            gate_metadata: dict[str, object] = {
                "gate.outcomes": json.dumps(list(gate["outcomes"]), ensure_ascii=False, separators=(",", ":")),
                "gate.decision_required": scalar_string(gate["decision_required"]),
                "gate.outcome_key": str(gate["outcome_key"]),
            }
            sequence.append(
                (
                    "add-node",
                    add_node_args(
                        str(group_id),
                        gate,
                        forced_type="gate",
                        extra_metadata=gate_metadata,
                    ),
                    NOTE_P3_GATE_ADD,
                )
            )
        complete_args = ["--node", str(node_id), "--gate-outcome", str(payload.get("gate_outcome", "approved"))]
        decision = payload.get("decision")
        if decision is not None:
            complete_args += ["--decision", str(decision)]
        sequence.append(("complete", complete_args, NOTE_P3_COMPLETE))
    else:
        block_args = ["--node", str(node_id), "--reason", str(reason)]
        for artifact in payload.get("artifacts") or []:
            block_args += ["--artifact", str(artifact)]
        sequence.append(("block", block_args, NOTE_P4_BLOCK))
    commands = []
    for index, (command, args, note) in enumerate(sequence):
        if tree is not None:
            args = ["--tree", str(tree), *args]
        if index == 0 and revision is not None:
            insert = args.index("--tree") + 2 if tree is not None else 0
            args = [*args[:insert], "--expected-revision", str(revision), *args[insert:]]
        commands.append({"command": command, "args": args, "note": note})
    return {
        "schema_version": 1,
        "ok": True,
        "pattern": pattern,
        "commands": commands,
        "evidence_required": EVIDENCE[pattern],
    }


def plan(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return error_payload("input_not_object")
    code = validate(payload)
    if code is not None:
        return error_payload(code)
    return translate(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recovery_plan",
        description="Translate one recovery pattern into documented runtime commands.",
    )
    parser.add_argument(
        "--input-file",
        metavar="PATH",
        help="Read the incident JSON object from a file instead of stdin.",
    )
    options = parser.parse_args(list(argv) if argv is not None else None)
    if options.input_file:
        try:
            with open(options.input_file, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except OSError:
            print(compact_json(error_payload("input_file_unreadable")))
            return 0
    else:
        raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(compact_json(error_payload("input_not_json")))
        return 0
    print(compact_json(plan(payload)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
