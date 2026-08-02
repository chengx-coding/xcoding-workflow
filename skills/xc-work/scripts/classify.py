#!/usr/bin/env python3
"""Public fail-closed adapter for xc-work governance classification."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


FACT_ORDER = (
    "needs_persistence",
    "material_impact",
    "difficult_rollback",
    "crosses_sessions",
    "multiple_actors",
    "audit_required",
)
FACT_OPTIONS = {f"--{name.replace('_', '-')}": name for name in FACT_ORDER}
FACT_VALUES = frozenset({"no", "yes", "unknown"})
CLASSIFIER_TIMEOUT_SECONDS = 5


class PublicInputError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def escalation(code: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": True,
        "route": "managed",
        "classification_status": "escalated",
        "reason_codes": ["classification-unavailable"],
        "escalation": {"entry_point": "xc-work"},
        "diagnostic": {"input_error": code},
    }


def parse_public_arguments(argv: Sequence[str]) -> dict[str, str]:
    occurrences: dict[str, list[str]] = {name: [] for name in FACT_ORDER}
    invalid = False
    index = 0
    while index < len(argv):
        option = argv[index]
        fact = FACT_OPTIONS.get(option)
        if fact is None:
            invalid = True
            index += 1
            continue
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            invalid = True
            index += 1
            continue
        occurrences[fact].append(argv[index + 1])
        index += 2

    if any(len(values) > 1 and len(set(values)) > 1 for values in occurrences.values()):
        raise PublicInputError("classification_input_contradictory")
    if any(len(values) > 1 for values in occurrences.values()):
        raise PublicInputError("classification_input_duplicate")
    if invalid or any(values and values[0] not in FACT_VALUES for values in occurrences.values()):
        raise PublicInputError("classification_input_invalid")
    return {
        name: occurrences[name][0] if occurrences[name] else "unknown"
        for name in FACT_ORDER
    }


def classifier_arguments(facts: dict[str, str]) -> list[str]:
    arguments: list[str] = []
    for name in FACT_ORDER:
        arguments.extend([f"--{name.replace('_', '-')}", facts[name]])
    return arguments


def parse_object(output: str) -> dict[str, object] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def validate_success(
    payload: dict[str, object],
    expected_facts: dict[str, str],
) -> str | None:
    if payload.get("schema_version") != 1:
        return "classification_output_schema"
    if payload.get("route") not in {"direct", "managed"}:
        return "classification_output_route"
    if payload.get("ok") is not True:
        return "classification_output_invalid"
    facts = payload.get("facts")
    if (
        not isinstance(facts, dict)
        or set(facts) != set(FACT_ORDER)
        or any(
            not isinstance(facts.get(name), str)
            or facts[name] not in FACT_VALUES
            for name in FACT_ORDER
        )
    ):
        return "classification_output_invalid"
    if any(facts[name] != expected_facts[name] for name in FACT_ORDER):
        return "classification_output_facts_mismatch"
    expected_triggers = [
        f"fact-{expected_facts[name]}:{name}"
        for name in FACT_ORDER
        if expected_facts[name] in {"yes", "unknown"}
    ]
    if not expected_triggers:
        expected_triggers = ["all-facts-no"]
    triggers = payload.get("triggers")
    unknowns = payload.get("unknowns")
    if (
        triggers != expected_triggers
        or unknowns
        != [name for name in FACT_ORDER if expected_facts[name] == "unknown"]
    ):
        return "classification_output_invalid"
    expected_route = (
        "direct"
        if all(expected_facts[name] == "no" for name in FACT_ORDER)
        else "managed"
    )
    if payload["route"] != expected_route:
        return "classification_output_route"
    expected_escalation = (
        None if expected_route == "direct" else {"entry_point": "xc-work"}
    )
    if payload.get("escalation") != expected_escalation:
        return "classification_output_invalid"
    return None


def classify(argv: Sequence[str]) -> dict[str, object]:
    try:
        facts = parse_public_arguments(argv)
    except PublicInputError as exc:
        return escalation(exc.code)

    classifier = Path(__file__).with_name("classify_governance.py")
    if not classifier.is_file():
        return escalation("classification_executable_missing")
    try:
        completed = subprocess.run(
            [sys.executable, str(classifier), *classifier_arguments(facts)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=CLASSIFIER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return escalation("classification_timeout")
    except OSError:
        return escalation("classification_executable_unavailable")

    payload = parse_object(completed.stdout)
    if completed.returncode != 0:
        error = payload.get("error") if payload is not None else None
        code = error.get("code") if isinstance(error, dict) else None
        return escalation(code if isinstance(code, str) and code else "classification_process_failed")
    if payload is None:
        return escalation("classification_output_malformed")
    validation_error = validate_success(payload, facts)
    return escalation(validation_error) if validation_error else payload


def main(argv: Sequence[str] | None = None) -> int:
    try:
        payload = classify(tuple(sys.argv[1:] if argv is None else argv))
    except Exception:
        payload = escalation("classification_adapter_failed")
    print(compact_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
