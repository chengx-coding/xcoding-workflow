"""Deterministic delegation envelope compiler."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from .capabilities import resolve_capabilities
from .errors import fail
from .json_codec import MAX_DEPTH, MAX_NODES, canonical_digest, canonical_json_bytes
from .model import CAPABILITY_VOCABULARY, ENVELOPE_KIND
from .resolver import validate_resolved_profile


COMPILER_ID = "xcoding-delegation-compiler/v1"


def _reject_host_absolute_values(
    value: Any,
    *,
    depth: int = 1,
    counter: list[int] | None = None,
    active: set[int] | None = None,
) -> None:
    if counter is None:
        counter = [0]
    if active is None:
        active = set()
    counter[0] += 1
    if depth > MAX_DEPTH or counter[0] > MAX_NODES:
        fail(
            "context_limit_exceeded",
            "compile",
            "selected context exceeds the structural limit",
        )
    if isinstance(value, str):
        if re.match(r"^(?:[A-Za-z]:[\\/]|\\\\|//|/)", value):
            fail(
                "context_absolute_path_forbidden",
                "compile",
                "selected context must not contain an absolute host path key or value",
            )
        return
    if isinstance(value, list):
        identity = id(value)
        if identity in active:
            fail("context_invalid", "compile", "selected context must not contain a cycle")
        active.add(identity)
        try:
            for item in value:
                _reject_host_absolute_values(
                    item,
                    depth=depth + 1,
                    counter=counter,
                    active=active,
                )
        finally:
            active.remove(identity)
        return
    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            fail("context_invalid", "compile", "selected context must not contain a cycle")
        active.add(identity)
        try:
            for key, item in value.items():
                _reject_host_absolute_values(
                    key,
                    depth=depth + 1,
                    counter=counter,
                    active=active,
                )
                _reject_host_absolute_values(
                    item,
                    depth=depth + 1,
                    counter=counter,
                    active=active,
                )
        finally:
            active.remove(identity)


def _validate_bindings(
    profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
) -> dict[str, Any]:
    declared = {item["id"]: item for item in profile["context"]["bindings"]}
    references = node_profile_ref["context_bindings"]
    values = node_packet["context"]
    if set(references) - declared.keys() or set(values) - declared.keys():
        fail("context_binding_undeclared", "compile", "node supplied a context binding not declared by the profile")
    required = {identifier for identifier, item in declared.items() if item["required"]}
    if not required <= references.keys() or not required <= values.keys():
        fail("context_binding_missing", "compile", "required profile context is missing")
    if set(references) != set(values):
        fail("context_binding_mismatch", "compile", "context references and selected values must have identical keys")
    selected = {key: values[key] for key in sorted(values)}
    _reject_host_absolute_values(selected)
    if len(canonical_json_bytes(selected)) > profile["context"]["max_bytes"]:
        fail("context_limit_exceeded", "compile", "selected context exceeds the profile byte limit")
    return {
        "bindings": [
            {
                "id": key,
                "source": dict(references[key]),
                "value": selected[key],
            }
            for key in sorted(selected)
        ],
        "max_bytes": profile["context"]["max_bytes"],
    }


def _validate_outputs(profile: Mapping[str, Any], capabilities: Mapping[str, Any]) -> dict[str, Any]:
    grant = next(
        (
            set(item["values"])
            for item in capabilities["granted"]
            if item["id"] == "workbench.write.artifact"
        ),
        set(),
    )
    unauthorized_required = sorted(
        item["id"]
        for item in profile["outputs"]["artifacts"]
        if item["required"] and item["path"] not in grant
    )
    if unauthorized_required:
        fail(
            "output_not_authorized",
            "compile",
            "profile output is outside the effective artifact capability",
            outputs=unauthorized_required,
            remediation_category="policy",
        )
    return {
        "artifacts": [
            dict(item)
            for item in profile["outputs"]["artifacts"]
            if item["path"] in grant
        ],
        "result_fields": list(profile["outputs"]["result_fields"]),
    }


def _validate_overlay_target(resolved: Mapping[str, Any], node_packet: Mapping[str, Any]) -> None:
    overlay = resolved["overlay"]
    if overlay is None:
        return
    expected = {
        "work_order_id": node_packet["work_order_id"],
        "node_id": node_packet["node_id"],
        "attempt": node_packet["attempt"],
    }
    if overlay["target"] != expected:
        fail("overlay_target_mismatch", "compile", "resolved overlay targets a different node attempt")
    try:
        expiry = datetime.fromisoformat(str(overlay["expires_at"])[:-1] + "+00:00")
    except ValueError:
        fail("overlay_expiry_invalid", "compile", "resolved overlay expiry is invalid")
    if expiry <= datetime.now(timezone.utc):
        fail("overlay_expired", "compile", "resolved overlay has expired", remediation_category="runtime-state")


def _compile_envelope(
    resolved_profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
    *,
    dispatch_authoritative: bool,
) -> dict[str, Any]:
    """Compile one byte-stable envelope from already validated inputs."""
    resolved = validate_resolved_profile(resolved_profile)
    profile = resolved["profile"]
    if (
        node_profile_ref["owner_skill"] != profile["owner_skill"]
        or node_profile_ref["profile_id"] != profile["profile_id"]
    ):
        fail("profile_reference_mismatch", "compile", "node profile reference does not match the resolved owner and profile")
    _validate_overlay_target(resolved, node_packet)
    capabilities = resolve_capabilities(
        profile,
        project_policy,
        node_packet,
        caller_constraints,
        adapter_statement,
        security_mode=node_profile_ref["security_mode"],
    )
    context = _validate_bindings(profile, node_packet, node_profile_ref)
    outputs = _validate_outputs(profile, capabilities)
    terminal_grant = next(
        (
            set(item["values"])
            for item in capabilities["granted"]
            if item["id"] == "runtime.terminal.assigned-node"
        ),
        set(),
    )
    terminal_operations = sorted(
        terminal_grant & set(node_packet["allowed_terminal_operations"])
    )
    if dispatch_authoritative and not terminal_operations:
        fail(
            "terminal_authority_empty",
            "compile",
            "authoritative preparation requires a terminal capability that overlaps runtime-authorized operations",
            remediation_category="policy",
        )
    skill_grant = next(
        (
            set(item["values"])
            for item in capabilities["granted"]
            if item["id"] == "skill.invoke.declared"
        ),
        set(),
    )
    missing_required_skills = sorted(set(profile["required_skills"]) - skill_grant)
    if dispatch_authoritative and missing_required_skills:
        fail(
            "required_skill_not_authorized",
            "compile",
            "authoritative preparation requires an effective Skill grant for every required Skill",
            remediation_category="policy",
            missing=missing_required_skills,
        )

    resource_digests = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in resolved["resources"]
    ]
    envelope = {
        "schema_version": 1,
        "kind": ENVELOPE_KIND,
        "compiler": {"id": COMPILER_ID, "schema_version": 1},
        "profile": {
            "owner_skill": profile["owner_skill"],
            "profile_id": profile["profile_id"],
            "description": profile["description"],
            "base_profile_sha256": resolved["base_profile_sha256"],
            "resolved_profile_sha256": resolved["resolved_profile_sha256"],
            "resources": resource_digests,
            "required_skills": list(profile["required_skills"]),
        },
        "instructions": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "content": item["content"],
            }
            for item in resolved["resources"]
        ],
        "target": {
            "work_order_id": node_packet["work_order_id"],
            "node_id": node_packet["node_id"],
            "attempt": node_packet["attempt"],
        },
        "policy_inputs": {
            "adapter_capabilities_sha256": canonical_digest(adapter_statement),
            "caller_constraints_sha256": canonical_digest(caller_constraints),
            "node_packet_sha256": canonical_digest(node_packet),
            "node_profile_ref_sha256": canonical_digest(node_profile_ref),
            "overlay_sha256": None if resolved["overlay"] is None else resolved["overlay"]["sha256"],
            "project_policy_sha256": canonical_digest(project_policy),
        },
        "capabilities": {
            "vocabulary": CAPABILITY_VOCABULARY,
            **capabilities,
        },
        "context": context,
        "outputs": outputs,
        "authority": {
            "dispatch_authoritative": dispatch_authoritative,
            "terminal_operations": terminal_operations,
        },
        "compatibility": {
            "legacy_fallback": False,
            "on_unsupported": "block",
            "mode": "profile-v1",
        },
        "overlay": None
        if resolved["overlay"] is None
        else {
            "sha256": resolved["overlay"]["sha256"],
            "cleanup_required": True,
        },
        "adapter": {
            "id": adapter_statement["adapter_id"],
            "version": adapter_statement["adapter_version"],
            "declared_mode": adapter_statement["mode"],
        },
    }
    return envelope


def compile_envelope(
    resolved_profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile a diagnostic envelope that cannot authorize dispatch."""
    return _compile_envelope(
        resolved_profile,
        node_packet,
        node_profile_ref,
        project_policy,
        adapter_statement,
        caller_constraints,
        dispatch_authoritative=False,
    )


def _compile_prepared_envelope(
    resolved_profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
) -> dict[str, Any]:
    """Internal implementation used only by application.prepare."""
    return _compile_envelope(
        resolved_profile,
        node_packet,
        node_profile_ref,
        project_policy,
        adapter_statement,
        caller_constraints,
        dispatch_authoritative=True,
    )


__all__ = ["COMPILER_ID", "compile_envelope"]
