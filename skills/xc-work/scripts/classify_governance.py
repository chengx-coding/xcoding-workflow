#!/usr/bin/env python3
"""Classify an explicit six-fact governance vector."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence


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


class ClassificationInputError(ValueError):
    """Stable invalid-input result returned by the low-level classifier."""

    def __init__(
        self,
        code: str,
        facts: Sequence[str] = (),
        arguments: Sequence[str] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.facts = tuple(facts)
        self.arguments = tuple(arguments)


def emit(payload: dict[str, object]) -> None:
    """Emit one deterministic JSON object."""
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def error_payload(error: ClassificationInputError) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": error.code,
        "facts": list(error.facts),
    }
    if error.arguments:
        detail["arguments"] = list(error.arguments)
    return {
        "schema_version": 1,
        "ok": False,
        "error": detail,
    }


def parse_arguments(argv: Sequence[str]) -> dict[str, str]:
    """Parse required flags while retaining duplicate and conflict evidence."""
    occurrences: dict[str, list[str]] = {name: [] for name in FACT_ORDER}
    invalid_arguments: list[str] = []
    invalid_facts: list[str] = []
    index = 0
    while index < len(argv):
        option = argv[index]
        fact = FACT_OPTIONS.get(option)
        if fact is None:
            invalid_arguments.append(option)
            index += 1
            continue
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            invalid_facts.append(fact)
            index += 1
            continue
        occurrences[fact].append(argv[index + 1])
        index += 2

    contradictory = [
        name
        for name in FACT_ORDER
        if len(occurrences[name]) > 1 and len(set(occurrences[name])) > 1
    ]
    if contradictory:
        raise ClassificationInputError(
            "classification_input_contradictory",
            contradictory,
        )

    duplicate = [name for name in FACT_ORDER if len(occurrences[name]) > 1]
    if duplicate:
        raise ClassificationInputError("classification_input_duplicate", duplicate)

    invalid_facts.extend(
        name
        for name in FACT_ORDER
        if occurrences[name] and occurrences[name][0] not in FACT_VALUES
    )
    ordered_invalid = [name for name in FACT_ORDER if name in set(invalid_facts)]
    if invalid_arguments or ordered_invalid:
        raise ClassificationInputError(
            "classification_input_invalid",
            ordered_invalid,
            invalid_arguments,
        )

    missing = [name for name in FACT_ORDER if not occurrences[name]]
    if missing:
        raise ClassificationInputError("classification_input_missing", missing)

    return {name: occurrences[name][0] for name in FACT_ORDER}


def classify(facts: dict[str, str]) -> dict[str, object]:
    """Return the deterministic route and ordered reason codes."""
    triggers = [
        f"fact-{facts[name]}:{name}"
        for name in FACT_ORDER
        if facts[name] in {"yes", "unknown"}
    ]
    route = "managed" if triggers else "direct"
    if not triggers:
        triggers = ["all-facts-no"]
    return {
        "schema_version": 1,
        "ok": True,
        "route": route,
        "facts": {name: facts[name] for name in FACT_ORDER},
        "triggers": triggers,
        "unknowns": [name for name in FACT_ORDER if facts[name] == "unknown"],
        "escalation": {"entry_point": "xc-work"} if route == "managed" else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        facts = parse_arguments(arguments)
        emit(classify(facts))
    except ClassificationInputError as exc:
        emit(error_payload(exc))
        return 2
    except Exception:
        emit(
            {
                "schema_version": 1,
                "ok": False,
                "error": {
                    "code": "classification_failed",
                    "facts": [],
                },
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
