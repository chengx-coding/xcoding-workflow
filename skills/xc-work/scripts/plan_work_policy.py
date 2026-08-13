#!/usr/bin/env python3
"""Strict deterministic planner for adaptive managed work."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Sequence


GOVERNANCE_FACTS = (
    "needs_persistence",
    "material_impact",
    "difficult_rollback",
    "crosses_sessions",
    "multiple_actors",
    "audit_required",
)
TASK_FACTS = (
    "scope",
    "clarity",
    "risk",
    "verification",
    "coordination",
    "duration",
    "audit",
)
CAPABILITIES = (
    "goal_document",
    "analysis",
    "clarification",
    "solution",
    "approval",
    "split_implementation",
    "separate_verification",
    "independent_review",
    "result_document",
    "resumable_recovery",
)
VERIFICATION_SCOPES = ("focused", "regression", "multi-environment")
VERIFICATION_SCOPE_LADDER = ("smoke", *VERIFICATION_SCOPES, "performance")
DOCUMENTATION_GRADES = ("none", "inline", "spec-design", "full-user")
DECOMPOSITION_GRADES = (
    "single-node",
    "sequence",
    "milestone-subtrees",
    "feature-farms",
)
REVIEW_GRADES = ("none", "self-check", "independent", "architecture-gate")
MODES = ("investigation", "change", "repair", "review", "maintenance")
MUTATION_MODES = frozenset({"change", "repair", "maintenance"})
MUTATION_ONLY_CAPABILITIES = frozenset(
    {"split_implementation", "separate_verification"}
)
PACE_VALUES = ("adaptive", "fast", "thorough")
OPTIONAL_DEPTH_FLOORS: dict[str, dict[str, object]] = {
    "analysis_perspectives": {"enabled_capability": "analysis"},
    "review_passes": {"enabled_capability": "independent_review"},
    "recovery_exercises": {"enabled_capability": None},
    "regression_scope": {"fact_required_scopes": True},
}


def compute_optional_depth_floors(
    capabilities: dict[str, bool],
    fact_required_scopes: Sequence[str],
) -> dict[str, object]:
    floors: dict[str, object] = {}
    for name, spec in OPTIONAL_DEPTH_FLOORS.items():
        capability = spec.get("enabled_capability")
        if capability is not None:
            floors[name] = 1 if capabilities[capability] else 0
        elif spec.get("fact_required_scopes"):
            floors[name] = list(fact_required_scopes)
        else:
            floors[name] = 0
    return floors


def derive_documentation_grade(capabilities: dict[str, bool]) -> str:
    goal = capabilities["goal_document"]
    result = capabilities["result_document"]
    design = capabilities["analysis"] or capabilities["solution"]
    if goal and result:
        return "full-user"
    if goal or design:
        return "spec-design"
    if result:
        return "inline"
    return "none"


def derive_decomposition_grade(facts: dict[str, str], units: int) -> str:
    if facts["mode"] not in MUTATION_MODES:
        return "single-node"
    if facts["scope"] == "cross-cutting":
        return "feature-farms"
    if facts["duration"] == "cross-session" or facts["coordination"] == "multi-party":
        return "milestone-subtrees"
    if units >= 2:
        return "sequence"
    return "single-node"


def derive_review_grade(
    capabilities: dict[str, bool],
    facts: dict[str, str],
) -> str:
    if facts["risk"] == "high" and facts["audit"] == "full":
        return "architecture-gate"
    if capabilities["independent_review"]:
        return "independent"
    if capabilities["separate_verification"]:
        return "self-check"
    return "none"


OPTIONS = {
    **{f"--{name.replace('_', '-')}": name for name in GOVERNANCE_FACTS},
    "--bridge-policy": "bridge_policy",
    "--scope": "scope",
    "--clarity": "clarity",
    "--risk": "risk",
    "--verification": "verification",
    "--coordination": "coordination",
    "--duration": "duration",
    "--audit": "audit",
    "--pace": "pace",
    "--mode": "mode",
    "--request": "request",
    "--bridge-sha256": "bridge_sha256",
}
VALUES = {
    **{name: frozenset({"no", "yes", "unknown"}) for name in GOVERNANCE_FACTS},
    "bridge_policy": frozenset({"none", "commit", "review", "approval", "full", "unknown"}),
    "scope": frozenset({"single-location", "module", "cross-cutting", "unknown"}),
    "clarity": frozenset({"exact", "known-root", "uncertain", "unknown"}),
    "risk": frozenset({"low", "medium", "high", "unknown"}),
    "verification": frozenset({"focused", "regression", "multi-environment", "smoke", "performance", "unknown"}),
    "coordination": frozenset({"single", "review", "multi-party", "unknown"}),
    "duration": frozenset({"single-step", "multi-step", "cross-session", "unknown"}),
    "audit": frozenset({"runtime-only", "result", "full", "unknown"}),
    "pace": frozenset(PACE_VALUES),
    "mode": frozenset(MODES),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PlanningInputError(ValueError):
    def __init__(self, code: str, fields: Sequence[str] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.fields = tuple(fields)


def compact_json(value: object, *, sort_keys: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=sort_keys,
    )


def emit(payload: dict[str, object]) -> None:
    print(compact_json(payload))


def parse_arguments(argv: Sequence[str]) -> dict[str, str]:
    fields = (*GOVERNANCE_FACTS, "bridge_policy", *TASK_FACTS, "pace", "mode", "request", "bridge_sha256")
    occurrences: dict[str, list[str]] = {name: [] for name in fields}
    invalid_arguments: list[str] = []
    index = 0
    while index < len(argv):
        option = argv[index]
        field = OPTIONS.get(option)
        if field is None:
            invalid_arguments.append(option)
            index += 1
            continue
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            raise PlanningInputError("planning_input_invalid", [field])
        occurrences[field].append(argv[index + 1])
        index += 2

    contradictory = [
        name
        for name in fields
        if len(occurrences[name]) > 1 and len(set(occurrences[name])) > 1
    ]
    if contradictory:
        raise PlanningInputError("planning_input_contradictory", contradictory)
    duplicate = [name for name in fields if len(occurrences[name]) > 1]
    if duplicate:
        raise PlanningInputError("planning_input_duplicate", duplicate)
    missing = [name for name in fields if not occurrences[name]]
    if missing:
        raise PlanningInputError("planning_input_missing", missing)
    invalid = [
        name
        for name in VALUES
        if occurrences[name][0] not in VALUES[name]
    ]
    if invalid_arguments or invalid:
        raise PlanningInputError(
            "planning_input_invalid",
            [*invalid, *invalid_arguments],
        )
    if not occurrences["request"][0].strip():
        raise PlanningInputError("planning_input_invalid", ["request"])
    if not SHA256_RE.fullmatch(occurrences["bridge_sha256"][0]):
        raise PlanningInputError("planning_input_invalid", ["bridge_sha256"])
    return {name: occurrences[name][0] for name in fields}


def _contradictions(facts: dict[str, str]) -> list[str]:
    issues: list[str] = []
    if facts["crosses_sessions"] == "yes" and facts["duration"] != "cross-session":
        issues.append("crosses_sessions")
    if facts["crosses_sessions"] == "no" and facts["duration"] == "cross-session":
        issues.append("duration")
    if facts["multiple_actors"] == "yes" and facts["coordination"] == "single":
        issues.append("multiple_actors")
    if facts["multiple_actors"] == "no" and facts["coordination"] == "multi-party":
        issues.append("coordination")
    if facts["difficult_rollback"] == "yes" and facts["risk"] == "low":
        issues.append("risk")
    if facts["audit_required"] == "no" and (
        facts["bridge_policy"] != "none" or facts["audit"] != "runtime-only"
    ):
        issues.append("audit_required")
    if facts["audit_required"] == "yes" and facts["audit"] == "runtime-only":
        issues.append("audit")
    if facts["verification"] == "smoke" and (
        facts["risk"] != "low" or facts["scope"] != "single-location"
    ):
        issues.append("verification")
    return list(dict.fromkeys(issues))


def build_plan(facts: dict[str, str]) -> dict[str, object]:
    expected_fields = {
        *GOVERNANCE_FACTS,
        "bridge_policy",
        *TASK_FACTS,
        "pace",
        "mode",
        "request",
        "bridge_sha256",
    }
    if set(facts) != expected_fields:
        raise PlanningInputError(
            "planning_input_invalid",
            sorted(expected_fields.symmetric_difference(facts)),
        )
    invalid = [
        name
        for name, allowed in VALUES.items()
        if not isinstance(facts[name], str) or facts[name] not in allowed
    ]
    if invalid:
        raise PlanningInputError("planning_input_invalid", invalid)
    if not isinstance(facts["request"], str) or not facts["request"].strip():
        raise PlanningInputError("planning_input_invalid", ["request"])
    if not isinstance(facts["bridge_sha256"], str) or not SHA256_RE.fullmatch(
        facts["bridge_sha256"]
    ):
        raise PlanningInputError("planning_input_invalid", ["bridge_sha256"])

    contradictions = _contradictions(facts)
    if contradictions:
        raise PlanningInputError("planning_input_contradictory", contradictions)

    capabilities = {name: False for name in CAPABILITIES}
    provenance: dict[str, list[str]] = {name: [] for name in CAPABILITIES}
    reasons: list[str] = []
    scopes: list[str] = []
    units = 1 if facts["mode"] in MUTATION_MODES else 0

    def reason(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    def enable(names: Sequence[str], code: str) -> None:
        reason(code)
        for name in names:
            if (
                facts["mode"] not in MUTATION_MODES
                and name in MUTATION_ONLY_CAPABILITIES
            ):
                continue
            capabilities[name] = True
            if code not in provenance[name]:
                provenance[name].append(code)

    def add_scope(name: str, code: str) -> None:
        reason(code)
        if name not in scopes:
            scopes.append(name)

    def require_all(code: str) -> None:
        nonlocal units
        enable(CAPABILITIES, code)
        if facts["mode"] in MUTATION_MODES:
            units = max(units, 2)
            for name in VERIFICATION_SCOPES:
                add_scope(name, code)

    if facts["mode"] in {"investigation", "review"}:
        enable(("analysis",), f"mode:{facts['mode']}")
    elif facts["mode"] in MUTATION_MODES:
        base_scope = "smoke" if facts["verification"] == "smoke" else "focused"
        add_scope(base_scope, f"mode:{facts['mode']}")

    for name in GOVERNANCE_FACTS:
        value = facts[name]
        code = f"governance:{name}:{value}"
        if value == "unknown":
            require_all(code)
        elif name == "difficult_rollback" and value == "yes":
            enable(("solution", "approval", "separate_verification", "result_document", "resumable_recovery"), code)
        elif name == "crosses_sessions" and value == "yes":
            enable(("goal_document", "result_document", "resumable_recovery"), code)
        elif name == "multiple_actors" and value == "yes":
            enable(("goal_document", "split_implementation", "independent_review", "result_document"), code)
            if facts["mode"] in MUTATION_MODES:
                units = max(units, 2)
        elif name == "audit_required" and value == "yes":
            enable(("result_document",), code)

    bridge_map = {
        "none": (),
        "commit": ("result_document",),
        "review": ("result_document", "independent_review"),
        "approval": ("goal_document", "solution", "approval", "result_document"),
        "full": CAPABILITIES,
    }
    if facts["bridge_policy"] == "unknown":
        require_all("bridge:unknown")
    elif bridge_map[facts["bridge_policy"]]:
        enable(bridge_map[facts["bridge_policy"]], f"bridge:{facts['bridge_policy']}")

    fact_maps: dict[str, dict[str, tuple[str, ...]]] = {
        "scope": {
            "single-location": (),
            "module": ("split_implementation", "separate_verification"),
            "cross-cutting": (
                "goal_document",
                "analysis",
                "solution",
                "split_implementation",
                "separate_verification",
                "independent_review",
                "result_document",
                "resumable_recovery",
            ),
        },
        "clarity": {
            "exact": (),
            "known-root": (),
            "uncertain": ("analysis", "clarification", "solution"),
        },
        "risk": {
            "low": (),
            "medium": ("separate_verification", "result_document"),
            "high": (
                "goal_document",
                "analysis",
                "solution",
                "approval",
                "separate_verification",
                "independent_review",
                "result_document",
                "resumable_recovery",
            ),
        },
        "verification": {
            "smoke": (),
            "focused": (),
            "regression": ("separate_verification",),
            "multi-environment": ("separate_verification", "independent_review"),
            "performance": ("separate_verification",),
        },
        "coordination": {
            "single": (),
            "review": ("independent_review",),
            "multi-party": (
                "goal_document",
                "split_implementation",
                "independent_review",
                "result_document",
                "resumable_recovery",
            ),
        },
        "duration": {
            "single-step": (),
            "multi-step": ("result_document",),
            "cross-session": ("goal_document", "result_document", "resumable_recovery"),
        },
        "audit": {
            "runtime-only": (),
            "result": ("result_document",),
            "full": (
                "goal_document",
                "analysis",
                "solution",
                "approval",
                "independent_review",
                "result_document",
                "resumable_recovery",
            ),
        },
    }
    for name in TASK_FACTS:
        value = facts[name]
        code = f"task:{name}:{value}"
        if value == "unknown":
            require_all(code)
            continue
        mapped = fact_maps[name][value]
        if mapped:
            enable(mapped, code)
        if name == "scope" and value in {"module", "cross-cutting"} and facts["mode"] in MUTATION_MODES:
            units = max(units, 2)
            add_scope("regression", code)
        if name == "coordination" and value == "multi-party" and facts["mode"] in MUTATION_MODES:
            units = max(units, 2)
        if name == "verification":
            add_scope(value, code)

    if capabilities["split_implementation"] and facts["mode"] in MUTATION_MODES:
        units = max(units, 2)
    if facts["mode"] not in MUTATION_MODES:
        units = 0
        scopes = []

    fact_required_scopes = [
        name for name in VERIFICATION_SCOPE_LADDER if name in scopes
    ]
    floors = compute_optional_depth_floors(capabilities, fact_required_scopes)
    depth = {
        "analysis_perspectives": 1 if capabilities["analysis"] else 0,
        "review_passes": 1 if capabilities["independent_review"] else 0,
        "recovery_exercises": 0,
    }
    if facts["pace"] == "thorough":
        code = "pace:thorough"
        reason(code)
        if capabilities["analysis"]:
            depth["analysis_perspectives"] += 1
        if capabilities["independent_review"]:
            depth["review_passes"] += 1
        if capabilities["resumable_recovery"]:
            depth["recovery_exercises"] += 1
        if facts["mode"] in MUTATION_MODES:
            capabilities["separate_verification"] = True
            if code not in provenance["separate_verification"]:
                provenance["separate_verification"].append(code)
            add_scope("regression", code)
            add_scope("performance", code)
    elif facts["pace"] == "fast":
        depth = {
            "analysis_perspectives": floors["analysis_perspectives"],
            "review_passes": floors["review_passes"],
            "recovery_exercises": floors["recovery_exercises"],
        }

    if capabilities["analysis"] != (depth["analysis_perspectives"] >= 1):
        raise PlanningInputError("planning_invariant_failed", ["analysis_perspectives"])
    if capabilities["independent_review"] != (depth["review_passes"] >= 1):
        raise PlanningInputError("planning_invariant_failed", ["review_passes"])
    if capabilities["split_implementation"] and (
        facts["mode"] not in MUTATION_MODES or units < 2
    ):
        raise PlanningInputError("planning_invariant_failed", ["implementation_units_min"])

    ordered_scopes = [name for name in VERIFICATION_SCOPE_LADDER if name in scopes]
    optional_depth: dict[str, dict[str, object]] = {
        "analysis_perspectives": {
            "floor": floors["analysis_perspectives"],
            "value": depth["analysis_perspectives"],
            "trimmed": facts["pace"] == "fast",
        },
        "review_passes": {
            "floor": floors["review_passes"],
            "value": depth["review_passes"],
            "trimmed": facts["pace"] == "fast",
        },
        "recovery_exercises": {
            "floor": floors["recovery_exercises"],
            "value": depth["recovery_exercises"],
            "trimmed": facts["pace"] == "fast",
        },
        "regression_scope": {
            "floor": floors["regression_scope"],
            "value": ordered_scopes,
            "trimmed": facts["pace"] == "fast",
        },
    }
    if facts["pace"] == "fast":
        for name in OPTIONAL_DEPTH_FLOORS:
            if optional_depth[name]["value"] != optional_depth[name]["floor"]:
                raise PlanningInputError("planning_invariant_failed", [name])
    required_nodes: list[dict[str, object]] = []

    def add_required(
        logical_key: str,
        role: str,
        *,
        artifact_min: int = 1,
        verification_scope: str = "",
    ) -> None:
        item: dict[str, object] = {
            "logical_key": logical_key,
            "role": role,
            "artifact_min": artifact_min,
        }
        if verification_scope:
            item["verification_scope"] = verification_scope
        required_nodes.append(item)

    if capabilities["goal_document"]:
        add_required("goal-document", "document")
    for index in range(depth["analysis_perspectives"]):
        add_required(f"analysis-{index + 1}", "analysis")
    if capabilities["clarification"]:
        add_required("clarification", "clarification", artifact_min=0)
    if capabilities["solution"]:
        add_required("solution-document", "document")
    if capabilities["approval"]:
        add_required("solution-approval", "approval", artifact_min=0)
    for index in range(units):
        verification_scope = (
            ("smoke" if facts["verification"] == "smoke" else "focused")
            if index == 0
            and facts["mode"] in MUTATION_MODES
            and not capabilities["separate_verification"]
            else ""
        )
        add_required(
            f"implementation-{index + 1}",
            "implementation",
            verification_scope=verification_scope,
        )
    if capabilities["separate_verification"]:
        for name in ordered_scopes:
            add_required(
                f"verification-{name}",
                "verification",
                verification_scope=name,
            )
    for index in range(depth["review_passes"]):
        add_required(f"review-{index + 1}", "review")
    if capabilities["result_document"]:
        add_required("result-document", "document")
    add_required("finalize", "finalizer", artifact_min=0)

    nested_facts = {
        "governance": {name: facts[name] for name in GOVERNANCE_FACTS},
        "bridge_policy": facts["bridge_policy"],
        "task": {name: facts[name] for name in TASK_FACTS},
    }
    documentation_grade = derive_documentation_grade(capabilities)
    decomposition_grade = derive_decomposition_grade(facts, units)
    review_grade = derive_review_grade(capabilities, facts)
    receipt_body = {
        "schema_version": 1,
        "request_sha256": hashlib.sha256(facts["request"].encode("utf-8")).hexdigest(),
        "bridge_sha256": facts["bridge_sha256"],
        "mode": facts["mode"],
        "pace": facts["pace"],
        "capabilities": capabilities,
        "implementation_units_min": units,
        "verification_scopes": ordered_scopes,
        "depth": depth,
        "optional_depth": optional_depth,
        "required_nodes": required_nodes,
        "facts": nested_facts,
    }
    if decomposition_grade != "single-node":
        receipt_body["decomposition_grade"] = decomposition_grade
    if review_grade != "none":
        receipt_body["review_grade"] = review_grade
    plan_id = hashlib.sha256(
        compact_json(receipt_body, sort_keys=True).encode("utf-8")
    ).hexdigest()
    plan_receipt = {**receipt_body, "plan_id": plan_id}
    payload = {
        "schema_version": 1,
        "ok": True,
        "mode": facts["mode"],
        "pace": facts["pace"],
        "capabilities": capabilities,
        "implementation_units_min": units,
        "verification_scopes": ordered_scopes,
        "depth": depth,
        "optional_depth": optional_depth,
        "required_nodes": required_nodes,
        "required_provenance": provenance,
        "facts": nested_facts,
        "reason_codes": reasons,
        "planning_status": "planned",
        "diagnostic": None,
        "plan_receipt": plan_receipt,
    }
    if documentation_grade != "none":
        payload["documentation_grade"] = documentation_grade
    if decomposition_grade != "single-node":
        payload["decomposition_grade"] = decomposition_grade
    if review_grade != "none":
        payload["review_grade"] = review_grade
    return payload


def error_payload(error: PlanningInputError) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": False,
        "error": {"code": error.code, "fields": list(error.fields)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        emit(build_plan(parse_arguments(tuple(sys.argv[1:] if argv is None else argv))))
    except PlanningInputError as exc:
        emit(error_payload(exc))
        return 2
    except Exception:
        emit(
            {
                "schema_version": 1,
                "ok": False,
                "error": {"code": "planning_failed", "fields": []},
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
