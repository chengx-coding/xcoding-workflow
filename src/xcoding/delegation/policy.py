"""Strict policy parsing helpers for the six-layer capability resolver."""

from __future__ import annotations

from typing import Any, Mapping

from .errors import fail
from .model import (
    CALLER_CONSTRAINTS_KIND,
    PROJECT_POLICY_KIND,
    validate_policy,
)


def grant_map(policy: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        item["id"]: tuple(item["values"])
        for item in policy["grants"]
    }


def validate_project_policy(value: object) -> dict[str, Any]:
    return validate_policy(value, kind=PROJECT_POLICY_KIND)


def validate_caller_constraints(value: object) -> dict[str, Any]:
    return validate_policy(value, kind=CALLER_CONSTRAINTS_KIND)


def assert_monotonic_narrowing(
    profile: Mapping[str, Any],
    project: Mapping[str, Any],
    node: Mapping[str, Any],
    caller: Mapping[str, Any],
) -> None:
    """Reject node or caller grants that widen their approved predecessor."""
    requested = {item["id"]: set(item["values"]) for item in profile["capabilities"]}
    project_grants = {key: set(values) for key, values in grant_map(project).items()}
    node_grants = {
        item["id"]: set(item["values"])
        for item in node["authorization"]["capabilities"]
    }
    caller_grants = {key: set(values) for key, values in grant_map(caller).items()}

    for identifier, values in node_grants.items():
        if identifier not in requested or not values <= requested[identifier]:
            fail(
                "unsafe_capability_widening",
                "capability-policy",
                "node authorization exceeds the worker profile request",
                capability=identifier,
            )
        if identifier not in project_grants or not values <= project_grants[identifier]:
            fail(
                "unsafe_capability_widening",
                "capability-policy",
                "node authorization exceeds the project ceiling",
                capability=identifier,
            )
    for identifier, values in caller_grants.items():
        if identifier not in node_grants or not values <= node_grants[identifier]:
            fail(
                "unsafe_capability_widening",
                "capability-policy",
                "caller constraints exceed node authorization",
                capability=identifier,
            )


__all__ = [
    "assert_monotonic_narrowing",
    "grant_map",
    "validate_caller_constraints",
    "validate_project_policy",
]
