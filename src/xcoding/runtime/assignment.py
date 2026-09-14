"""Read-only, least-context assignment packets for Skill-local workers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from xcoding.delegation import (
    DelegationError,
    NODE_PACKET_KIND,
    NODE_PROFILE_REF_KIND,
    validate_node_packet,
    validate_node_profile_ref,
)

from . import core


ASSIGNMENT_KIND = "xc-runtime-assignment/v1"


class AssignmentError(core.RuntimeErrorBase):
    """The requested node cannot produce a valid worker assignment."""

    code = "assignment_invalid"


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical UTF-8 JSON with the contract-required final LF."""
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise AssignmentError(
            "assignment value is not canonical JSON",
            {"reason": type(exc).__name__},
        ) from exc


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _authorization(node: ET.Element) -> dict[str, Any]:
    raw = node.get(core.DELEGATION_AUTHORIZATION_KEY)
    if raw is None:
        return {"capabilities": []}
    try:
        value = core._strict_json_value(raw)
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise AssignmentError(
            "node delegation authorization is invalid",
            {"node_id": node.get("id", ""), "reason": type(exc).__name__},
        ) from exc
    if canonical != raw or not isinstance(value, dict):
        raise AssignmentError(
            "node delegation authorization is not canonical",
            {"node_id": node.get("id", "")},
        )
    return value


def _target_contract(node: ET.Element) -> dict[str, str]:
    return {
        "role": core.node_role(node),
        "instructions": core.child_text(node, "instructions"),
        "inputs": core.child_text(node, "inputs"),
        "deliverables": core.child_text(node, "deliverables"),
        "acceptance": core.child_text(node, "acceptance"),
    }


def _minimized_control_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_categories": list(packet["source_categories"]),
        "blackboard": list(packet["blackboard"]),
    }


def _selected_context(
    reference: Mapping[str, Any],
    target_contract: Mapping[str, Any],
    control_packet: Mapping[str, Any],
) -> dict[str, Any]:
    categories = {
        item["name"]: item
        for item in control_packet["source_categories"]
    }
    blackboard = {
        item["key"]: item["value"]
        for item in control_packet["blackboard"]
    }
    selected: dict[str, Any] = {}
    for binding_id, binding in reference["context_bindings"].items():
        source = binding["source"]
        if source == "target-contract":
            selected[binding_id] = dict(target_contract)
        elif source == "control-packet":
            category = binding["category"]
            if category not in categories:
                raise AssignmentError(
                    "declared control-packet context is unavailable",
                    {"binding_id": binding_id, "category": category},
                )
            selected[binding_id] = categories[category]
        elif source == "blackboard":
            key = binding["key"]
            if key not in blackboard:
                raise AssignmentError(
                    "declared blackboard context is unavailable",
                    {"binding_id": binding_id, "key": key},
                )
            selected[binding_id] = blackboard[key]
        else:  # The public validator should make this unreachable.
            raise AssignmentError(
                "worker context binding source is unsupported",
                {"binding_id": binding_id},
            )
    return selected


def build_assignment_packet(
    root: ET.Element,
    node_id: str,
    attempt: int,
) -> dict[str, Any]:
    """Build an exact read-only assignment after the target was started."""
    core.require_valid_control_metadata(root)
    node = core.require_executable_leaf(root, node_id)
    if (
        core.node_type(node) != "task"
        or node.get("executor") != "subagent"
        or node.get("status") != "running"
    ):
        raise AssignmentError(
            "assignment requires a running subagent task leaf",
            {
                "node_id": node_id,
                "status": node.get("status", "pending"),
                "executor": node.get("executor", ""),
                "type": core.node_type(node),
            },
        )
    current_attempt = core.attempt_number(node)
    if attempt != current_attempt:
        raise AssignmentError(
            "assignment attempt does not match the running node",
            {
                "node_id": node_id,
                "expected_attempt": current_attempt,
                "actual_attempt": attempt,
            },
        )

    target_contract = _target_contract(node)
    full_control_packet = core.build_control_packet(root, node_id)
    control_packet = _minimized_control_packet(full_control_packet)
    reference = core.worker_profile_ref_for_node(node)
    reference["kind"] = NODE_PROFILE_REF_KIND
    context = _selected_context(reference, target_contract, control_packet)
    packet = {
        "schema_version": 1,
        "kind": NODE_PACKET_KIND,
        "work_order_id": root.get("work_order_id", ""),
        "node_id": node_id,
        "attempt": current_attempt,
        "status": "running",
        "executor": "subagent",
        "authorization": _authorization(node),
        "context": context,
        "allowed_terminal_operations": ["block", "complete", "fail"],
    }
    try:
        reference = validate_node_profile_ref(reference)
        packet = validate_node_packet(packet)
    except DelegationError as exc:
        raise AssignmentError(
            "runtime node cannot produce a valid delegation contract",
            {"node_id": node_id, "delegation_error": exc.as_dict()},
        ) from exc

    digests = {
        "node_packet_sha256": canonical_digest(packet),
        "node_profile_ref_sha256": canonical_digest(reference),
        "target_contract_sha256": canonical_digest(target_contract),
        "control_packet_sha256": canonical_digest(control_packet),
    }
    return {
        "schema_version": 1,
        "kind": ASSIGNMENT_KIND,
        "revision": core.runtime_revision(root),
        "node_packet": packet,
        "node_profile_ref": reference,
        "target_contract": target_contract,
        "control_packet": control_packet,
        "digests": digests,
    }


__all__ = [
    "ASSIGNMENT_KIND",
    "AssignmentError",
    "build_assignment_packet",
    "canonical_digest",
    "canonical_json_bytes",
]
