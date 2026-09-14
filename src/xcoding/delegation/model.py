"""Exact v1 delegation data contracts and validators."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .errors import fail
from .paths import validate_path_set, validate_relative_path, validate_slug


PROFILE_SCHEMA_VERSION = 1
CAPABILITY_VOCABULARY = "xc-delegation-capabilities/v1"
RESOLVED_PROFILE_KIND = "xc-resolved-worker-profile/v1"
NODE_PACKET_KIND = "xc-delegation-node-packet/v1"
NODE_PROFILE_REF_KIND = "xc-node-worker-profile-ref/v1"
PROJECT_POLICY_KIND = "xc-project-delegation-policy/v1"
CALLER_CONSTRAINTS_KIND = "xc-delegation-caller-constraints/v1"
ADAPTER_STATEMENT_KIND = "xc-delegation-adapter-capabilities/v1"
ADAPTER_EVIDENCE_KIND = "xc-delegation-adapter-evidence/v1"
ENVELOPE_KIND = "xc-delegation-envelope/v1"

ADAPTER_EVIDENCE_COVERAGE = (
    "allow",
    "bypass",
    "deny",
    "path-isolation",
    "secret-visibility",
    "terminal-binding-visibility",
)

CAPABILITY_IDS = (
    "network.outbound.allowlisted",
    "process.exec.named",
    "project.read.declared",
    "project.write.owned",
    "runtime.terminal.assigned-node",
    "secret.use.named",
    "skill.invoke.declared",
    "workbench.read.declared",
    "workbench.write.artifact",
    "workbench.write.tmp",
)
_CAPABILITY_SET = frozenset(CAPABILITY_IDS)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PINNED_ADAPTER_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")
_ADAPTER_VERSION_PLACEHOLDERS = frozenset(
    {
        "any",
        "current",
        "dev",
        "development",
        "fixture",
        "latest",
        "placeholder",
        "test",
        "unknown",
        "unverified",
    }
)
_WORK_ORDER_ID = re.compile(r"[0-9]{8}-[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_NODE_ID = re.compile(r"rt_[A-Za-z0-9][A-Za-z0-9_.:-]*(?:__[A-Za-z0-9][A-Za-z0-9_.:-]*)+\Z")

PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_id",
        "owner_skill",
        "description",
        "instruction_resources",
        "required_skills",
        "capability_vocabulary",
        "capabilities",
        "context",
        "outputs",
        "delegation",
        "failure_policy",
        "compatibility",
    }
)
NODE_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "work_order_id",
        "node_id",
        "attempt",
        "status",
        "executor",
        "authorization",
        "context",
        "allowed_terminal_operations",
    }
)
NODE_PROFILE_REF_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "owner_skill",
        "profile_id",
        "security_mode",
        "context_bindings",
    }
)


def require_exact_fields(value: Mapping[str, Any], fields: Iterable[str], *, label: str) -> None:
    expected = set(fields)
    actual = set(value)
    if actual != expected:
        fail(
            "schema_fields_invalid",
            "validate",
            f"{label} has invalid fields",
            missing=sorted(expected - actual),
            unexpected_count=len(actual - expected),
        )


def require_object(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("schema_type_invalid", "validate", f"{field} must be an object")
    return value


def require_array(value: object, *, field: str, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        fail("schema_type_invalid", "validate", f"{field} must be an array with at most {maximum} items")
    return value


def require_string(
    value: object,
    *,
    field: str,
    maximum: int = 4096,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value) or len(value.encode("utf-8")) > maximum:
        fail("schema_type_invalid", "validate", f"{field} must be a bounded string")
    return value


def require_integer(value: object, *, field: str, minimum: int = 0, maximum: int = 2**31 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        fail("schema_type_invalid", "validate", f"{field} must be an integer from {minimum} to {maximum}")
    return value


def require_boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        fail("schema_type_invalid", "validate", f"{field} must be a boolean")
    return value


def _require_schema_one(value: Mapping[str, Any], *, label: str) -> None:
    if value.get("schema_version") != PROFILE_SCHEMA_VERSION:
        fail("schema_version_unsupported", "validate", f"{label}.schema_version must be 1")


def _require_sorted_unique_strings(
    value: object,
    *,
    field: str,
    maximum: int,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    items = require_array(value, field=field, maximum=maximum)
    strings = tuple(require_string(item, field=f"{field}[]", maximum=1024) for item in items)
    if not allow_empty and not strings:
        fail("schema_value_invalid", "validate", f"{field} must not be empty")
    if list(strings) != sorted(set(strings)):
        fail("schema_order_invalid", "validate", f"{field} must be sorted and unique")
    return strings


def _validate_capability_values(identifier: str, raw_values: object, *, wildcard: bool = False) -> tuple[str, ...]:
    values = _require_sorted_unique_strings(
        raw_values,
        field=f"capabilities[{identifier}].values",
        maximum=128,
        allow_empty=False,
    )
    if "*" in values and (not wildcard or values != ("*",)):
        fail("capability_value_invalid", "validate", "wildcard is reserved for adapter statements")
    if values == ("*",):
        return values
    for value in values:
        if identifier in {
            "project.read.declared",
            "project.write.owned",
            "workbench.read.declared",
            "workbench.write.artifact",
            "workbench.write.tmp",
        }:
            if value != "*":
                validate_relative_path(value, field=f"capabilities[{identifier}].values[]")
        elif identifier == "runtime.terminal.assigned-node":
            if value not in {"block", "complete", "fail"}:
                fail("capability_value_invalid", "validate", "terminal operation is unsupported")
        elif identifier == "network.outbound.allowlisted":
            if value != "*" and ("/" in value or "://" in value or not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]{1,5})?", value)):
                fail("capability_value_invalid", "validate", "network values must be lowercase host allowlist entries")
        else:
            if value != "*":
                validate_slug(value, field=f"capabilities[{identifier}].values[]")
    return values


def validate_capability_requests(value: object) -> tuple[dict[str, Any], ...]:
    items = require_array(value, field="capabilities", maximum=len(CAPABILITY_IDS))
    normalized: list[dict[str, Any]] = []
    identifiers: list[str] = []
    for index, raw in enumerate(items):
        item = require_object(raw, field=f"capabilities[{index}]")
        require_exact_fields(item, {"id", "requirement", "values"}, label=f"capabilities[{index}]")
        identifier = require_string(item["id"], field=f"capabilities[{index}].id", maximum=64)
        if identifier not in _CAPABILITY_SET:
            fail("capability_unknown", "validate", "capability identifier is not in the v1 vocabulary")
        requirement = item["requirement"]
        if requirement not in {"optional", "required"}:
            fail("schema_value_invalid", "validate", "capability requirement must be optional or required")
        values = _validate_capability_values(identifier, item["values"])
        identifiers.append(identifier)
        normalized.append({"id": identifier, "requirement": requirement, "values": list(values)})
    if identifiers != sorted(set(identifiers)):
        fail("schema_order_invalid", "validate", "capabilities must be sorted and unique by id")
    return tuple(normalized)


def validate_grants(value: object, *, wildcard: bool = False) -> tuple[dict[str, Any], ...]:
    items = require_array(value, field="grants", maximum=len(CAPABILITY_IDS))
    normalized: list[dict[str, Any]] = []
    identifiers: list[str] = []
    for index, raw in enumerate(items):
        item = require_object(raw, field=f"grants[{index}]")
        require_exact_fields(item, {"id", "values"}, label=f"grants[{index}]")
        identifier = require_string(item["id"], field=f"grants[{index}].id", maximum=64)
        if identifier not in _CAPABILITY_SET:
            fail("capability_unknown", "validate", "grant uses an unknown capability identifier")
        values = _validate_capability_values(identifier, item["values"], wildcard=wildcard)
        identifiers.append(identifier)
        normalized.append({"id": identifier, "values": list(values)})
    if identifiers != sorted(set(identifiers)):
        fail("schema_order_invalid", "validate", "grants must be sorted and unique by id")
    return tuple(normalized)


def _validate_context(value: object) -> dict[str, Any]:
    context = require_object(value, field="context")
    require_exact_fields(context, {"bindings", "max_bytes"}, label="context")
    raw_bindings = require_array(context["bindings"], field="context.bindings", maximum=64)
    bindings: list[dict[str, Any]] = []
    identifiers: list[str] = []
    for index, raw in enumerate(raw_bindings):
        item = require_object(raw, field=f"context.bindings[{index}]")
        require_exact_fields(item, {"id", "required"}, label=f"context.bindings[{index}]")
        identifier = validate_slug(item["id"], field=f"context.bindings[{index}].id")
        required = require_boolean(item["required"], field=f"context.bindings[{index}].required")
        identifiers.append(identifier)
        bindings.append({"id": identifier, "required": required})
    if identifiers != sorted(set(identifiers)):
        fail("schema_order_invalid", "validate", "context bindings must be sorted and unique by id")
    maximum = require_integer(context["max_bytes"], field="context.max_bytes", maximum=65536)
    return {"bindings": bindings, "max_bytes": maximum}


def _validate_outputs(value: object) -> dict[str, Any]:
    outputs = require_object(value, field="outputs")
    require_exact_fields(outputs, {"artifacts", "result_fields"}, label="outputs")
    raw_artifacts = require_array(outputs["artifacts"], field="outputs.artifacts", maximum=32)
    artifacts: list[dict[str, Any]] = []
    identifiers: list[str] = []
    paths: list[str] = []
    for index, raw in enumerate(raw_artifacts):
        item = require_object(raw, field=f"outputs.artifacts[{index}]")
        require_exact_fields(item, {"id", "path", "required"}, label=f"outputs.artifacts[{index}]")
        identifier = validate_slug(item["id"], field=f"outputs.artifacts[{index}].id")
        path = validate_relative_path(item["path"], field=f"outputs.artifacts[{index}].path")
        required = require_boolean(item["required"], field=f"outputs.artifacts[{index}].required")
        identifiers.append(identifier)
        paths.append(path)
        artifacts.append({"id": identifier, "path": path, "required": required})
    if identifiers != sorted(set(identifiers)):
        fail("schema_order_invalid", "validate", "output artifacts must be sorted and unique by id")
    validate_path_set(paths, field="outputs.artifacts.path")
    fields = _require_sorted_unique_strings(outputs["result_fields"], field="outputs.result_fields", maximum=32)
    for field in fields:
        validate_slug(field, field="outputs.result_fields[]")
    return {"artifacts": artifacts, "result_fields": list(fields)}


def validate_profile(value: object) -> dict[str, Any]:
    profile = require_object(value, field="profile")
    require_exact_fields(profile, PROFILE_FIELDS, label="profile")
    _require_schema_one(profile, label="profile")
    profile_id = validate_slug(profile["profile_id"], field="profile_id")
    owner = validate_slug(profile["owner_skill"], field="owner_skill", prefix="xc-")
    description = require_string(profile["description"], field="description", maximum=4096)
    resources = list(
        _require_sorted_unique_strings(
            profile["instruction_resources"],
            field="instruction_resources",
            maximum=16,
            allow_empty=False,
        )
    )
    validate_path_set(resources, field="instruction_resources")
    for resource in resources:
        validate_relative_path(resource, field="instruction_resources[]")
        if not resource.startswith(f"assets/workers/{profile_id}/") or resource.endswith("/profile.json"):
            fail("resource_scope_invalid", "validate", "instruction resources must remain in the profile directory")
    required_skills = list(
        _require_sorted_unique_strings(profile["required_skills"], field="required_skills", maximum=32)
    )
    for skill in required_skills:
        validate_slug(skill, field="required_skills[]", prefix="xc-")
    if profile["capability_vocabulary"] != CAPABILITY_VOCABULARY:
        fail("capability_vocabulary_unsupported", "validate", "profile uses an unsupported capability vocabulary")
    capabilities = list(validate_capability_requests(profile["capabilities"]))
    context = _validate_context(profile["context"])
    outputs = _validate_outputs(profile["outputs"])
    delegation = require_object(profile["delegation"], field="delegation")
    require_exact_fields(delegation, {"allowed", "max_depth"}, label="delegation")
    if delegation != {"allowed": False, "max_depth": 0}:
        fail("nested_delegation_forbidden", "validate", "v1 profiles must disable nested delegation")
    failure_policy = require_object(profile["failure_policy"], field="failure_policy")
    require_exact_fields(
        failure_policy,
        {"on_invalid_input", "on_required_capability", "silent_fallback"},
        label="failure_policy",
    )
    if failure_policy != {
        "on_invalid_input": "block",
        "on_required_capability": "block",
        "silent_fallback": False,
    }:
        fail("failure_policy_invalid", "validate", "v1 failure policy must block without silent fallback")
    compatibility = require_object(profile["compatibility"], field="compatibility")
    require_exact_fields(compatibility, {"legacy_fallback", "on_unsupported"}, label="compatibility")
    if compatibility != {"legacy_fallback": False, "on_unsupported": "block"}:
        fail("compatibility_invalid", "validate", "v1 compatibility must block without legacy fallback")
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "owner_skill": owner,
        "description": description,
        "instruction_resources": resources,
        "required_skills": required_skills,
        "capability_vocabulary": CAPABILITY_VOCABULARY,
        "capabilities": capabilities,
        "context": context,
        "outputs": outputs,
        "delegation": {"allowed": False, "max_depth": 0},
        "failure_policy": dict(failure_policy),
        "compatibility": dict(compatibility),
    }


def _validate_work_order_id(value: object) -> str:
    text = require_string(value, field="work_order_id", maximum=160)
    if not _WORK_ORDER_ID.fullmatch(text):
        fail("identifier_invalid", "validate", "work_order_id is not canonical")
    return text


def _validate_node_id(value: object) -> str:
    text = require_string(value, field="node_id", maximum=512)
    if not _NODE_ID.fullmatch(text):
        fail("identifier_invalid", "validate", "node_id is not canonical")
    return text


def validate_node_packet(value: object) -> dict[str, Any]:
    packet = require_object(value, field="node_packet")
    require_exact_fields(packet, NODE_PACKET_FIELDS, label="node_packet")
    _require_schema_one(packet, label="node_packet")
    if packet["kind"] != NODE_PACKET_KIND:
        fail("schema_kind_invalid", "validate", f"node_packet.kind must be {NODE_PACKET_KIND}")
    work_order_id = _validate_work_order_id(packet["work_order_id"])
    node_id = _validate_node_id(packet["node_id"])
    attempt = require_integer(packet["attempt"], field="attempt", minimum=1, maximum=1_000_000)
    if packet["status"] != "running" or packet["executor"] != "subagent":
        fail("node_not_dispatchable", "validate", "node packet must identify a running subagent node", remediation_category="runtime-state")
    authorization = require_object(packet["authorization"], field="authorization")
    require_exact_fields(authorization, {"capabilities"}, label="authorization")
    capabilities = list(validate_grants(authorization["capabilities"]))
    context = require_object(packet["context"], field="node_packet.context")
    if len(context) > 64:
        fail("schema_limit_exceeded", "validate", "node context contains too many bindings")
    terminal = list(
        _require_sorted_unique_strings(
            packet["allowed_terminal_operations"],
            field="allowed_terminal_operations",
            maximum=3,
            allow_empty=False,
        )
    )
    if any(item not in {"block", "complete", "fail"} for item in terminal):
        fail("schema_value_invalid", "validate", "terminal operation is unsupported")
    return {
        "schema_version": 1,
        "kind": NODE_PACKET_KIND,
        "work_order_id": work_order_id,
        "node_id": node_id,
        "attempt": attempt,
        "status": "running",
        "executor": "subagent",
        "authorization": {"capabilities": capabilities},
        "context": dict(context),
        "allowed_terminal_operations": terminal,
    }


def validate_node_profile_ref(value: object) -> dict[str, Any]:
    reference = require_object(value, field="node_profile_ref")
    require_exact_fields(reference, NODE_PROFILE_REF_FIELDS, label="node_profile_ref")
    _require_schema_one(reference, label="node_profile_ref")
    if reference["kind"] != NODE_PROFILE_REF_KIND:
        fail("schema_kind_invalid", "validate", f"node_profile_ref.kind must be {NODE_PROFILE_REF_KIND}")
    owner = validate_slug(reference["owner_skill"], field="owner_skill", prefix="xc-")
    profile_id = validate_slug(reference["profile_id"], field="profile_id")
    security_mode = reference["security_mode"]
    if security_mode not in {"enforced", "validated-only"}:
        fail("security_mode_invalid", "validate", "profile security mode must be enforced or validated-only")
    raw_bindings = require_object(reference["context_bindings"], field="context_bindings")
    if len(raw_bindings) > 64:
        fail("schema_limit_exceeded", "validate", "too many context bindings")
    bindings: dict[str, Any] = {}
    for key in sorted(raw_bindings):
        validate_slug(key, field="context_bindings key")
        binding = require_object(raw_bindings[key], field=f"context_bindings.{key}")
        source = binding.get("source")
        if source == "target-contract":
            require_exact_fields(binding, {"source"}, label=f"context_bindings.{key}")
        elif source == "control-packet":
            require_exact_fields(binding, {"source", "category"}, label=f"context_bindings.{key}")
            validate_slug(binding["category"], field="context binding category")
        elif source == "blackboard":
            require_exact_fields(binding, {"source", "key"}, label=f"context_bindings.{key}")
            require_string(binding["key"], field="context binding blackboard key", maximum=256)
        else:
            fail("context_binding_invalid", "validate", "context binding source is unsupported")
        bindings[key] = dict(binding)
    return {
        "schema_version": 1,
        "kind": NODE_PROFILE_REF_KIND,
        "owner_skill": owner,
        "profile_id": profile_id,
        "security_mode": security_mode,
        "context_bindings": bindings,
    }


def validate_policy(value: object, *, kind: str) -> dict[str, Any]:
    policy = require_object(value, field=kind)
    require_exact_fields(policy, {"schema_version", "kind", "grants"}, label=kind)
    _require_schema_one(policy, label=kind)
    if policy["kind"] != kind:
        fail("schema_kind_invalid", "validate", f"policy kind must be {kind}")
    return {"schema_version": 1, "kind": kind, "grants": list(validate_grants(policy["grants"]))}


def _adapter_version_is_pinned(value: str) -> bool:
    if not _PINNED_ADAPTER_VERSION.fullmatch(value) or not any(
        character.isdigit() for character in value
    ):
        return False
    tokens = set(re.split(r"[._+-]+", value.casefold()))
    return not tokens & _ADAPTER_VERSION_PLACEHOLDERS


def _validate_adapter_evidence(
    value: object,
    *,
    adapter_version: str,
) -> list[dict[str, Any]]:
    raw_evidence = require_array(value, field="evidence", maximum=32)
    evidence: list[dict[str, Any]] = []
    coverage_values: list[str] = []
    for index, raw in enumerate(raw_evidence):
        item = require_object(raw, field=f"evidence[{index}]")
        require_exact_fields(
            item,
            {
                "schema_version",
                "kind",
                "adapter_version",
                "coverage",
                "artifact",
                "sha256",
            },
            label=f"evidence[{index}]",
        )
        _require_schema_one(item, label=f"evidence[{index}]")
        if item["kind"] != ADAPTER_EVIDENCE_KIND:
            fail(
                "schema_kind_invalid",
                "validate",
                f"adapter evidence kind must be {ADAPTER_EVIDENCE_KIND}",
            )
        evidence_version = require_string(
            item["adapter_version"],
            field=f"evidence[{index}].adapter_version",
            maximum=128,
        )
        if evidence_version != adapter_version:
            fail(
                "adapter_evidence_version_mismatch",
                "validate",
                "adapter evidence must target the statement adapter version",
            )
        coverage = require_string(
            item["coverage"],
            field=f"evidence[{index}].coverage",
            maximum=64,
        )
        if coverage not in ADAPTER_EVIDENCE_COVERAGE:
            fail(
                "adapter_evidence_coverage_invalid",
                "validate",
                "adapter evidence coverage is unsupported",
            )
        artifact = validate_relative_path(
            item["artifact"],
            field=f"evidence[{index}].artifact",
        )
        digest = require_sha256(item["sha256"], field=f"evidence[{index}].sha256")
        coverage_values.append(coverage)
        evidence.append(
            {
                "schema_version": 1,
                "kind": ADAPTER_EVIDENCE_KIND,
                "adapter_version": evidence_version,
                "coverage": coverage,
                "artifact": artifact,
                "sha256": digest,
            }
        )
    if coverage_values != sorted(set(coverage_values)):
        fail(
            "schema_order_invalid",
            "validate",
            "adapter evidence must be sorted and unique by coverage",
        )
    return evidence


def validate_adapter_statement(value: object) -> dict[str, Any]:
    statement = require_object(value, field="adapter_statement")
    require_exact_fields(
        statement,
        {"schema_version", "kind", "adapter_id", "adapter_version", "mode", "evidence", "capabilities"},
        label="adapter_statement",
    )
    _require_schema_one(statement, label="adapter_statement")
    if statement["kind"] != ADAPTER_STATEMENT_KIND:
        fail("schema_kind_invalid", "validate", f"adapter statement kind must be {ADAPTER_STATEMENT_KIND}")
    adapter_id = validate_slug(statement["adapter_id"], field="adapter_id")
    adapter_version = require_string(statement["adapter_version"], field="adapter_version", maximum=128)
    mode = statement["mode"]
    if mode not in {"enforced", "unsupported", "validated-only"}:
        fail("security_mode_invalid", "validate", "adapter mode is unsupported")
    evidence = _validate_adapter_evidence(
        statement["evidence"],
        adapter_version=adapter_version,
    )
    raw_capabilities = require_array(statement["capabilities"], field="capabilities", maximum=len(CAPABILITY_IDS))
    capabilities: list[dict[str, Any]] = []
    identifiers: list[str] = []
    for index, raw in enumerate(raw_capabilities):
        item = require_object(raw, field=f"capabilities[{index}]")
        require_exact_fields(item, {"id", "support", "values"}, label=f"capabilities[{index}]")
        identifier = require_string(item["id"], field="capability id", maximum=64)
        if identifier not in _CAPABILITY_SET:
            fail("capability_unknown", "validate", "adapter capability is unknown")
        support = item["support"]
        if support not in {"enforced", "unsupported", "validated-only"}:
            fail("security_mode_invalid", "validate", "adapter capability support is invalid")
        values = _validate_capability_values(identifier, item["values"], wildcard=True)
        identifiers.append(identifier)
        capabilities.append({"id": identifier, "support": support, "values": list(values)})
    if identifiers != sorted(set(identifiers)):
        fail("schema_order_invalid", "validate", "adapter capabilities must be sorted and unique by id")
    if mode == "enforced" and any(item["support"] != "enforced" for item in capabilities):
        fail("security_mode_invalid", "validate", "enforced adapter mode requires every declared capability to be enforced")
    if mode == "unsupported" and any(item["support"] != "unsupported" for item in capabilities):
        fail("security_mode_invalid", "validate", "unsupported adapter mode cannot declare supported capabilities")
    if mode == "enforced":
        if not _adapter_version_is_pinned(adapter_version):
            fail(
                "adapter_version_unpinned",
                "validate",
                "enforced adapter mode requires a pinned non-placeholder adapter version",
            )
        missing_capabilities = sorted(_CAPABILITY_SET - set(identifiers))
        if missing_capabilities:
            fail(
                "adapter_capabilities_incomplete",
                "validate",
                "enforced adapter mode requires an explicit claim for every v1 capability",
                missing=missing_capabilities,
            )
        coverage = {item["coverage"] for item in evidence}
        missing_evidence = sorted(set(ADAPTER_EVIDENCE_COVERAGE) - coverage)
        if missing_evidence:
            fail(
                "adapter_evidence_incomplete",
                "validate",
                "enforced adapter mode requires complete fixed-version evidence",
                missing=missing_evidence,
            )
    return {
        "schema_version": 1,
        "kind": ADAPTER_STATEMENT_KIND,
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "mode": mode,
        "evidence": evidence,
        "capabilities": capabilities,
    }


def require_sha256(value: object, *, field: str) -> str:
    text = require_string(value, field=field, maximum=64)
    if not _SHA256.fullmatch(text):
        fail("digest_invalid", "validate", f"{field} must be a lowercase SHA-256 digest")
    return text


__all__ = [
    "ADAPTER_EVIDENCE_COVERAGE",
    "ADAPTER_EVIDENCE_KIND",
    "ADAPTER_STATEMENT_KIND",
    "CALLER_CONSTRAINTS_KIND",
    "CAPABILITY_IDS",
    "CAPABILITY_VOCABULARY",
    "ENVELOPE_KIND",
    "NODE_PACKET_FIELDS",
    "NODE_PACKET_KIND",
    "NODE_PROFILE_REF_FIELDS",
    "NODE_PROFILE_REF_KIND",
    "PROFILE_FIELDS",
    "PROFILE_SCHEMA_VERSION",
    "PROJECT_POLICY_KIND",
    "RESOLVED_PROFILE_KIND",
    "require_exact_fields",
    "require_object",
    "require_sha256",
    "validate_adapter_statement",
    "validate_capability_requests",
    "validate_grants",
    "validate_node_packet",
    "validate_node_profile_ref",
    "validate_policy",
    "validate_profile",
]
