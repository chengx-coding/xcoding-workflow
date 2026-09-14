"""Six-layer capability intersection with stable omission provenance."""

from __future__ import annotations

from typing import Any, Mapping

from .errors import fail
from .policy import assert_monotonic_narrowing, grant_map


LAYERS = ("profile", "xc-ceiling", "project", "node", "caller", "host")


def _host_map(statement: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item["id"]: item for item in statement["capabilities"]}


def _intersect(sets: list[set[str]]) -> list[str]:
    if not sets:
        return []
    result = set(sets[0])
    for values in sets[1:]:
        result &= values
    return sorted(result)


def resolve_capabilities(
    profile: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    *,
    security_mode: str,
) -> dict[str, Any]:
    """Return the exact six-layer intersection or block required denials."""
    assert_monotonic_narrowing(profile, project_policy, node_packet, caller_constraints)
    project = grant_map(project_policy)
    node = {
        item["id"]: tuple(item["values"])
        for item in node_packet["authorization"]["capabilities"]
    }
    caller = grant_map(caller_constraints)
    host = _host_map(adapter_statement)
    granted: list[dict[str, Any]] = []
    omitted: list[dict[str, str]] = []
    provenance: list[dict[str, Any]] = []
    denied_required: list[dict[str, str]] = []

    for request in profile["capabilities"]:
        identifier = request["id"]
        requested = set(request["values"])
        project_values = set(project.get(identifier, ()))
        node_values = set(node.get(identifier, ()))
        caller_values = set(caller.get(identifier, ()))
        host_entry = host.get(identifier)
        support = "unsupported" if host_entry is None else str(host_entry["support"])
        host_values: set[str] = set()
        if host_entry is not None and support != "unsupported":
            raw_host = set(host_entry["values"])
            host_values = requested if raw_host == {"*"} else raw_host
        accepted_support = (
            support == "enforced"
            and adapter_statement["mode"] == "enforced"
            if security_mode == "enforced"
            else support in {"enforced", "validated-only"}
            and adapter_statement["mode"] in {"enforced", "validated-only"}
        )
        xc_ceiling = requested
        effective = _intersect(
            [
                requested,
                xc_ceiling,
                project_values,
                node_values,
                caller_values,
                host_values if accepted_support else set(),
            ]
        )
        layer_values = {
            "profile": sorted(requested),
            "xc-ceiling": sorted(xc_ceiling),
            "project": sorted(project_values),
            "node": sorted(node_values),
            "caller": sorted(caller_values),
            "host": sorted(host_values) if accepted_support else [],
        }
        reason = "granted"
        if not accepted_support:
            reason = "host-security-mode-unsupported"
        elif not project_values:
            reason = "project-denied"
        elif not node_values:
            reason = "node-denied"
        elif not caller_values:
            reason = "caller-omitted"
        elif not effective:
            reason = "parameter-intersection-empty"
        provenance.append(
            {
                "id": identifier,
                "requirement": request["requirement"],
                "layers": [
                    {"layer": layer, "values": layer_values[layer]}
                    for layer in LAYERS
                ],
                "host_support": support,
                "effective_values": effective,
                "reason": reason,
            }
        )
        if effective:
            granted.append(
                {
                    "id": identifier,
                    "requirement": request["requirement"],
                    "values": effective,
                    "host_support": support,
                }
            )
        elif request["requirement"] == "required":
            denied_required.append({"id": identifier, "reason": reason})
        else:
            omitted.append({"id": identifier, "reason": reason})

    if denied_required:
        fail(
            "required_capability_denied",
            "capability-policy",
            "one or more required capabilities were denied or unsupported",
            remediation_category="policy",
            denied=denied_required,
        )
    return {
        "security_mode": security_mode,
        "granted": granted,
        "omitted": omitted,
        "provenance": provenance,
    }


__all__ = ["LAYERS", "resolve_capabilities"]
