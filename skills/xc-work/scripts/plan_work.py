#!/usr/bin/env python3
"""Public fail-closed adapter for adaptive work planning."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import plan_work_policy as policy


TIMEOUT_SECONDS = 5
DEFAULTS = {
    **{name: "unknown" for name in policy.GOVERNANCE_FACTS},
    "bridge_policy": "unknown",
    **{name: "unknown" for name in policy.TASK_FACTS},
    "pace": "adaptive",
    "mode": "change",
    "request": "",
    "bridge_sha256": "0" * 64,
}


class PublicInputError(ValueError):
    def __init__(
        self,
        code: str,
        facts: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.facts = facts


def compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_public_arguments(argv: Sequence[str]) -> dict[str, str]:
    occurrences: dict[str, list[str]] = {name: [] for name in DEFAULTS}
    invalid = False
    index = 0
    while index < len(argv):
        option = argv[index]
        field = policy.OPTIONS.get(option)
        if field is None:
            invalid = True
            index += 1
            continue
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            invalid = True
            index += 1
            continue
        occurrences[field].append(argv[index + 1])
        index += 2
    values = {
        name: occurrences[name][0] if occurrences[name] else default
        for name, default in DEFAULTS.items()
    }
    if any(len(items) > 1 and len(set(items)) > 1 for items in occurrences.values()):
        raise PublicInputError("planning_input_contradictory", values)
    if any(len(items) > 1 for items in occurrences.values()):
        raise PublicInputError("planning_input_duplicate", values)
    if invalid:
        raise PublicInputError("planning_input_invalid", values)
    if not values["request"].strip():
        raise PublicInputError("planning_input_missing", values)
    for name, allowed in policy.VALUES.items():
        if values[name] not in allowed:
            raise PublicInputError("planning_input_invalid", values)
    if not policy.SHA256_RE.fullmatch(values["bridge_sha256"]):
        raise PublicInputError("planning_input_invalid", values)
    return values


def strict_arguments(facts: dict[str, str]) -> list[str]:
    arguments: list[str] = []
    ordered = (
        *policy.GOVERNANCE_FACTS,
        "bridge_policy",
        *policy.TASK_FACTS,
        "pace",
        "mode",
        "request",
        "bridge_sha256",
    )
    option_for = {field: option for option, field in policy.OPTIONS.items()}
    for field in ordered:
        arguments.extend([option_for[field], facts[field]])
    return arguments


def escalation(code: str, facts: dict[str, str] | None = None) -> dict[str, object]:
    fallback = dict(DEFAULTS if facts is None else facts)
    if not fallback["request"].strip():
        fallback["request"] = "<unavailable-request>"
    fallback.update(
        {
            name: "unknown"
            for name in (*policy.GOVERNANCE_FACTS, *policy.TASK_FACTS)
        }
    )
    fallback["bridge_policy"] = "unknown"
    fallback["pace"] = (
        fallback["pace"]
        if fallback["pace"] in policy.PACE_VALUES
        else "adaptive"
    )
    fallback["mode"] = (
        fallback["mode"] if fallback["mode"] in policy.MODES else "change"
    )
    fallback["bridge_sha256"] = (
        fallback["bridge_sha256"]
        if policy.SHA256_RE.fullmatch(fallback["bridge_sha256"])
        else "0" * 64
    )
    payload = policy.build_plan(fallback)
    payload["reason_codes"] = ["execution-planning-unavailable"]
    payload["planning_status"] = "escalated"
    payload["diagnostic"] = {"input_error": code}
    return payload


def parse_object(output: str) -> dict[str, object] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def plan(argv: Sequence[str]) -> dict[str, object]:
    try:
        facts = parse_public_arguments(argv)
    except PublicInputError as exc:
        return escalation(exc.code, exc.facts)
    low_level = Path(__file__).with_name("plan_work_policy.py")
    if not low_level.is_file():
        return escalation("planning_executable_missing", facts)
    try:
        completed = subprocess.run(
            [sys.executable, str(low_level), *strict_arguments(facts)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return escalation("planning_timeout", facts)
    except OSError:
        return escalation("planning_executable_unavailable", facts)
    payload = parse_object(completed.stdout)
    if completed.returncode != 0:
        error = payload.get("error") if payload is not None else None
        code = error.get("code") if isinstance(error, dict) else None
        return escalation(
            code if isinstance(code, str) and code else "planning_process_failed",
            facts,
        )
    if payload is None:
        return escalation("planning_output_malformed", facts)
    try:
        expected = policy.build_plan(facts)
    except policy.PlanningInputError as exc:
        return escalation(exc.code, facts)
    if payload != expected:
        return escalation("planning_output_invalid", facts)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    try:
        payload = plan(tuple(sys.argv[1:] if argv is None else argv))
    except Exception:
        payload = escalation("planning_adapter_failed")
    print(compact_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
