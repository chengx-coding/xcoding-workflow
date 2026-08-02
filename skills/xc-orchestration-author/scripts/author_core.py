#!/usr/bin/env python3
"""Author-owned validation, integrity, and persistence for managed templates."""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": 1,
    "git": {
        "auto_commit": True,
        "commit_message": "chore(orchestration): {operation} {work_order_id} [{checksum_short}]",
        "on_commit_failure": "warn",
    },
    "integrity": {
        "algorithm": "sha256",
        "canonicalization": "orchestration-tree-v1",
        "on_mismatch_read": "warn",
        "on_mismatch_write": "block",
    },
    "viewer": {
        "host": "127.0.0.1",
        "port": 20668,
        "watch_interval_seconds": 1,
        "heartbeat_seconds": 15,
        "idle_shutdown_seconds": 120,
    },
}

TEMPLATE_UPDATED_AT = "1970-01-01T00:00:00+00:00"
TEMPLATE_NOTICE = (
    "ATTENTION: AGENTS MUST ONLY READ OR OPERATE THIS TEMPLATE THROUGH THE "
    "xc-orchestration-author SKILL AND ITS PUBLIC COMMANDS. DO NOT OPEN, "
    "SUMMARIZE, EDIT, PATCH, OR REFORMAT THIS FILE DIRECTLY."
)
VALID_TYPES = {"composite", "task", "gate", "loop"}
VALID_MODES = {"", "sequence", "parallel", "switch"}
VALID_EXECUTORS = {"main", "subagent", "tool", "service"}
VALID_WHEN_POLICIES = {"reactive", "latched"}
VALID_DYNAMIC_GROUP_STATES = {"open", "closed"}
NODE_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
CONTROL_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
CHECK_NAME_RE = CONTROL_CATEGORY_RE
CHECK_FACT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BLACKBOARD_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CONTROL_METADATA_PREFIXES = (
    "metadata.control_packet.",
    "metadata.completion.",
    "metadata.gate.",
)
ATOMIC_REPLACE_ATTEMPTS = 5
ATOMIC_REPLACE_RETRY_DELAY_SECONDS = 0.05
TRANSIENT_REPLACE_WINERRORS = {5, 32}
CONFIG_FILENAME = "xc-orchestration-runtime.json"
LEGACY_CONFIG_FILENAME = "xc-orchestration-runtime.toml"


class AuthorError(RuntimeError):
    """Base author error with a stable machine-readable code."""

    code = "author_error"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConfigError(AuthorError):
    code = "config_error"


class TreeValidationError(AuthorError):
    code = "tree_validation_error"


class InvalidControlMetadataError(AuthorError):
    code = "invalid_control_metadata"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def strict_json_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite number is not allowed: {value}")


def parse_json_config(source_path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(
            source_path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=strict_json_object,
            parse_constant=reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ConfigError(
            "invalid JSON configuration",
            {"path": str(source_path), "error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be an object", {"path": str(source_path)})
    return data


def find_workspace_config(tree_path: Optional[Path]) -> Optional[Path]:
    resolved = (tree_path or Path.cwd()).resolve()
    current = resolved if resolved.is_dir() else resolved.parent
    while True:
        candidates = [(current / ".xcoding" / CONFIG_FILENAME, current / ".xcoding" / LEGACY_CONFIG_FILENAME)]
        if current.name == ".xcoding":
            candidates.insert(0, (current / CONFIG_FILENAME, current / LEGACY_CONFIG_FILENAME))
        for candidate, legacy_candidate in candidates:
            if candidate.exists() and legacy_candidate.exists():
                raise ConfigError(
                    "both JSON and legacy TOML configuration files exist",
                    {"path": str(candidate), "legacy_path": str(legacy_candidate)},
                )
            if candidate.exists():
                return candidate
            if legacy_candidate.exists():
                raise ConfigError(
                    "legacy TOML configuration is no longer supported; migrate it to JSON",
                    {"path": str(legacy_candidate), "expected_path": str(candidate)},
                )
        if current.parent == current:
            return None
        current = current.parent


def validate_config(config: Dict[str, Any], source: str) -> None:
    if not isinstance(config.get("schema_version"), int):
        raise ConfigError("schema_version must be an integer", {"source": source})
    git = config.get("git")
    integrity = config.get("integrity")
    viewer = config.get("viewer")
    if not isinstance(git, dict) or not isinstance(git.get("auto_commit"), bool):
        raise ConfigError("git.auto_commit must be a boolean", {"source": source})
    if git.get("on_commit_failure") not in {"warn", "fail"}:
        raise ConfigError("git.on_commit_failure must be warn or fail", {"source": source})
    if not isinstance(integrity, dict):
        raise ConfigError("integrity must be an object", {"source": source})
    if integrity.get("algorithm") != "sha256":
        raise ConfigError("only integrity.algorithm=sha256 is supported", {"source": source})
    if integrity.get("canonicalization") != "orchestration-tree-v1":
        raise ConfigError("unsupported integrity.canonicalization", {"source": source})
    if integrity.get("on_mismatch_read") != "warn":
        raise ConfigError("integrity.on_mismatch_read must be warn", {"source": source})
    if integrity.get("on_mismatch_write") != "block":
        raise ConfigError("integrity.on_mismatch_write must be block", {"source": source})
    if not isinstance(viewer, dict):
        raise ConfigError("viewer must be an object", {"source": source})
    if viewer.get("host") != "127.0.0.1":
        raise ConfigError("viewer.host must be 127.0.0.1 for local mode", {"source": source})
    for key in ("port", "watch_interval_seconds", "heartbeat_seconds", "idle_shutdown_seconds"):
        if not isinstance(viewer.get(key), int) or viewer[key] < 0:
            raise ConfigError(f"viewer.{key} must be a non-negative integer", {"source": source})


def load_config(tree_path: Optional[Path] = None, config_path: Optional[Path] = None) -> Dict[str, Any]:
    source_path = config_path.resolve() if config_path else find_workspace_config(tree_path)
    config = copy.deepcopy(DEFAULT_CONFIG)
    source = "builtin defaults"
    if source_path:
        if not source_path.exists():
            raise ConfigError("config file not found", {"path": str(source_path)})
        if source_path.suffix.lower() != ".json":
            raise ConfigError(
                "configuration path must use JSON",
                {"path": str(source_path), "expected_suffix": ".json"},
            )
        data = parse_json_config(source_path)
        config = deep_merge(config, data)
        source = str(source_path)
    validate_config(config, source)
    config["_source"] = source
    return config


def find_direct(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in list(parent):
        if child.tag == tag:
            return child
    return None


def ensure_direct(parent: ET.Element, tag: str) -> ET.Element:
    existing = find_direct(parent, tag)
    if existing is not None:
        return existing
    child = ET.Element(tag)
    parent.append(child)
    return child


def children(node: ET.Element) -> List[ET.Element]:
    holder = find_direct(node, "children")
    if holder is None:
        return []
    return [child for child in list(holder) if child.tag == "node"]


def iter_nodes(root: ET.Element) -> Iterable[ET.Element]:
    yield from root.iter("node")


def root_node(root: ET.Element) -> ET.Element:
    node = find_direct(root, "node")
    if node is None:
        raise TreeValidationError("orchestration has no root node")
    return node


def child_text(node: ET.Element, tag: str) -> str:
    child = find_direct(node, tag)
    return (child.text or "").strip() if child is not None else ""


def normalize_type(node_type_value: str, role: str = "") -> Tuple[str, str]:
    if node_type_value not in VALID_TYPES:
        raise TreeValidationError("invalid node type", {"type": node_type_value})
    return node_type_value, role


def node_type(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[0]


def node_role(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[1]


def template_id(node: ET.Element) -> str:
    value = node.get("template_id", "")
    if not value or not NODE_KEY_RE.match(value):
        raise TreeValidationError("template node missing valid template_id", {"value": value})
    return value


def normalize_value(value: str) -> str:
    return value.strip().strip('"').strip("'").lower()


def _json_string_list(value: str, *, nonempty: bool = False) -> Optional[List[str]]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    if (
        not isinstance(parsed, list)
        or (nonempty and not parsed)
        or any(not isinstance(item, str) or not item for item in parsed)
        or json.dumps(parsed, ensure_ascii=False, separators=(",", ":")) != value
    ):
        return None
    return parsed


def _non_negative_integer(value: str) -> Optional[int]:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        return None
    return int(value)


def _value_selector_valid(value: str) -> bool:
    if value.startswith("bb:"):
        return bool(BLACKBOARD_KEY_RE.fullmatch(value[3:]))
    return value.startswith("literal:") and bool(value[8:])


def _source_selector_valid(value: str) -> bool:
    if value.startswith("node:"):
        return bool(value[5:])
    if value.startswith("bb:"):
        return bool(BLACKBOARD_KEY_RE.fullmatch(value[3:]))
    return False


def _control_violation(key: str, code: str) -> Dict[str, str]:
    return {"key": key, "code": code}


def _deduplicate_control_violations(
    violations: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    unique = {(item["key"], item["code"]) for item in violations}
    return [{"key": key, "code": code} for key, code in sorted(unique)]


def validate_control_metadata_for_node(node: ET.Element) -> List[Dict[str, str]]:
    metadata = {
        key: value
        for key, value in node.attrib.items()
        if key.startswith(CONTROL_METADATA_PREFIXES)
    }
    if not metadata:
        return []
    violations: List[Dict[str, str]] = []
    leaf_owner = node_type(node) in {"task", "gate"} and not children(node)
    for key in metadata:
        if not leaf_owner:
            violations.append(_control_violation(key, "invalid_metadata_owner"))

    control_keys = {
        key: value
        for key, value in metadata.items()
        if key.startswith("metadata.control_packet.")
    }
    category_members: Dict[str, Dict[str, Tuple[str, str]]] = {}
    blackboard_key = "metadata.control_packet.blackboard_keys"
    for key, value in control_keys.items():
        match = re.fullmatch(
            r"metadata\.control_packet\.category\.([^.]+)\.(selectors|min_sources|artifact_min)",
            key,
        )
        if match:
            category, member = match.groups()
            if not CONTROL_CATEGORY_RE.fullmatch(category):
                violations.append(_control_violation(key, "invalid_control_packet_category"))
            category_members.setdefault(category, {})[member] = (key, value)
        elif key == blackboard_key:
            parsed = _json_string_list(value)
            if (
                parsed is None
                or len(parsed) != len(set(parsed))
                or any(not BLACKBOARD_KEY_RE.fullmatch(item) for item in parsed)
            ):
                violations.append(_control_violation(key, "invalid_blackboard_keys"))
        else:
            violations.append(_control_violation(key, "unknown_control_metadata_key"))
    if control_keys and not category_members:
        violations.append(
            _control_violation(
                sorted(control_keys)[0],
                "missing_control_packet_category_member",
            )
        )
    for category, members in category_members.items():
        category_prefix = f"metadata.control_packet.category.{category}"
        for member in ("selectors", "min_sources", "artifact_min"):
            if member not in members:
                violations.append(
                    _control_violation(
                        f"{category_prefix}.{member}",
                        "missing_control_packet_category_member",
                    )
                )
        if "selectors" in members:
            key, value = members["selectors"]
            selectors = _json_string_list(value, nonempty=True)
            if selectors is None or any(not _source_selector_valid(item) for item in selectors):
                violations.append(_control_violation(key, "invalid_selector_list"))
            elif len(selectors) != len(set(selectors)):
                violations.append(_control_violation(key, "duplicate_selector"))
        if "min_sources" in members:
            key, value = members["min_sources"]
            if _non_negative_integer(value) is None:
                violations.append(_control_violation(key, "invalid_min_sources"))
        if "artifact_min" in members:
            key, value = members["artifact_min"]
            if _non_negative_integer(value) is None:
                violations.append(_control_violation(key, "invalid_artifact_min"))

    completion_keys = {
        key: value
        for key, value in metadata.items()
        if key.startswith("metadata.completion.")
    }
    completion_allowed = {
        "metadata.completion.required_fields",
        "metadata.completion.artifacts.min",
        "metadata.completion.artifacts.max",
        "metadata.completion.artifacts.path",
        "metadata.completion.checks",
    }
    check_subjects: Dict[str, Tuple[str, str]] = {}
    check_facts: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for key, value in completion_keys.items():
        subject_match = re.fullmatch(r"metadata\.completion\.check\.([^.]+)\.subject", key)
        fact_match = re.fullmatch(
            r"metadata\.completion\.check\.([^.]+)\.facts\.([^.]+)",
            key,
        )
        if key in completion_allowed:
            continue
        if subject_match:
            check_subjects[subject_match.group(1)] = (key, value)
        elif fact_match:
            check, fact = fact_match.groups()
            check_facts.setdefault(check, {})[fact] = (key, value)
        else:
            violations.append(_control_violation(key, "unknown_control_metadata_key"))

    required_fields_key = "metadata.completion.required_fields"
    if required_fields_key in completion_keys:
        fields = _json_string_list(completion_keys[required_fields_key])
        if (
            fields is None
            or len(fields) != len(set(fields))
            or any(item not in {"summary", "validation"} for item in fields)
        ):
            violations.append(_control_violation(required_fields_key, "invalid_required_fields"))

    minimum_key = "metadata.completion.artifacts.min"
    maximum_key = "metadata.completion.artifacts.max"
    minimum = _non_negative_integer(completion_keys.get(minimum_key, ""))
    maximum = _non_negative_integer(completion_keys.get(maximum_key, ""))
    if minimum_key in completion_keys or maximum_key in completion_keys:
        if (
            minimum_key not in completion_keys
            or maximum_key not in completion_keys
            or minimum is None
            or maximum is None
            or minimum > maximum
        ):
            violations.extend(
                _control_violation(key, "invalid_artifact_bounds")
                for key in (minimum_key, maximum_key)
                if key in completion_keys
            )

    path_key = "metadata.completion.artifacts.path"
    if path_key in completion_keys:
        if minimum_key not in completion_keys or maximum_key not in completion_keys:
            violations.append(_control_violation(path_key, "invalid_artifact_bounds"))
        if not _value_selector_valid(completion_keys[path_key]):
            violations.append(
                _control_violation(path_key, "invalid_artifact_path_selector")
            )

    checks_key = "metadata.completion.checks"
    declared_checks: Optional[List[str]] = []
    if checks_key in completion_keys:
        declared_checks = _json_string_list(completion_keys[checks_key])
        if (
            declared_checks is None
            or len(declared_checks) != len(set(declared_checks))
            or any(not CHECK_NAME_RE.fullmatch(item) for item in declared_checks)
        ):
            violations.append(_control_violation(checks_key, "invalid_check_names"))
            declared_checks = None
    referenced_checks = set(check_subjects) | set(check_facts)
    declared_check_set = set(declared_checks or [])
    for check in sorted(referenced_checks | declared_check_set):
        entries = [
            entry
            for entry in [check_subjects.get(check), *check_facts.get(check, {}).values()]
            if entry is not None
        ]
        if not CHECK_NAME_RE.fullmatch(check):
            for key, _ in entries:
                violations.append(_control_violation(key, "invalid_check_names"))
        if check not in declared_check_set:
            for key, _ in entries:
                violations.append(_control_violation(key, "invalid_check_names"))
        if check in declared_check_set and check not in check_subjects:
            violations.append(
                _control_violation(
                    f"metadata.completion.check.{check}.subject",
                    "missing_check_subject",
                )
            )
    for key, value in check_subjects.values():
        if not _value_selector_valid(value):
            violations.append(
                _control_violation(key, "invalid_check_subject_selector")
            )
    for facts in check_facts.values():
        for fact, (key, value) in facts.items():
            if not CHECK_FACT_RE.fullmatch(fact):
                violations.append(_control_violation(key, "invalid_check_fact_name"))
            if not _value_selector_valid(value):
                violations.append(
                    _control_violation(key, "invalid_check_fact_selector")
                )

    gate_keys = {
        key: value
        for key, value in metadata.items()
        if key.startswith("metadata.gate.")
    }
    gate_allowed = {
        "metadata.gate.outcomes",
        "metadata.gate.decision_required",
        "metadata.gate.outcome_key",
    }
    for key in gate_keys:
        if key not in gate_allowed:
            violations.append(_control_violation(key, "unknown_control_metadata_key"))
    if gate_keys and (node_type(node) != "gate" or children(node)):
        violations.extend(
            _control_violation(key, "invalid_metadata_owner") for key in gate_keys
        )
    outcomes_key = "metadata.gate.outcomes"
    outcomes = _json_string_list(gate_keys.get(outcomes_key, ""), nonempty=True)
    if gate_keys and (
        outcomes_key not in gate_keys
        or outcomes is None
        or len(outcomes) != len(set(outcomes))
        or any(not CONTROL_CATEGORY_RE.fullmatch(item) for item in outcomes)
    ):
        violations.append(_control_violation(outcomes_key, "invalid_gate_outcomes"))
    decision_key = "metadata.gate.decision_required"
    if gate_keys and gate_keys.get(decision_key) not in {"true", "false"}:
        violations.append(
            _control_violation(decision_key, "invalid_gate_decision_required")
        )
    outcome_key = "metadata.gate.outcome_key"
    if outcome_key in gate_keys and not BLACKBOARD_KEY_RE.fullmatch(gate_keys[outcome_key]):
        violations.append(_control_violation(outcome_key, "invalid_gate_outcome_key"))
    return _deduplicate_control_violations(violations)


def validate_control_metadata_tree(root: ET.Element) -> List[Dict[str, str]]:
    violations: List[Dict[str, str]] = []
    for node in iter_nodes(root):
        node_id = node.get("id") or node.get("template_id") or "<unknown>"
        for violation in validate_control_metadata_for_node(node):
            violations.append({"node": node_id, **violation})
    unique = {
        (item["node"], item["key"], item["code"])
        for item in violations
    }
    return [
        {"node": node, "key": key, "code": code}
        for node, key, code in sorted(unique, key=lambda item: (item[1], item[2], item[0]))
    ]


def require_valid_control_metadata(root: ET.Element) -> None:
    violations = validate_control_metadata_tree(root)
    if violations:
        raise InvalidControlMetadataError(
            "control metadata declaration is invalid",
            {"violations": violations},
        )


def validate_template_root(root: ET.Element, check_integrity: bool = True) -> List[str]:
    errors: List[str] = []
    if root.tag != "orchestration":
        return ["template root element must be orchestration"]
    if root.get("schema_version") != "1":
        errors.append("template schema_version must be 1")
    if check_integrity:
        integrity = verify_integrity(root)
        if integrity["status"] != "valid":
            errors.append(
                f"template integrity {integrity['status']}: {integrity['reason']}"
            )
    try:
        template_root = root_node(root)
    except TreeValidationError as exc:
        return errors + [str(exc)]

    errors.extend(
        f"{item['node']}: {item['key']}: {item['code']}"
        for item in validate_control_metadata_tree(root)
    )
    seen: set[str] = set()
    references: List[Tuple[str, str]] = []
    for node in iter_nodes(template_root):
        try:
            tid = template_id(node)
        except TreeValidationError as exc:
            errors.append(str(exc))
            continue
        if node.get("id"):
            errors.append(f"{tid}: templates must use template_id, not id")
        if tid in seen:
            errors.append(f"duplicate template_id: {tid}")
        seen.add(tid)
        try:
            normalized_type, _ = normalize_type(
                node.get("type", ""),
                node.get("role", ""),
            )
        except TreeValidationError as exc:
            errors.append(str(exc))
            continue
        executor = node.get("executor", "")
        if executor not in VALID_EXECUTORS:
            errors.append(f"{tid}: invalid executor {executor}")
        mode = node.get("mode", "")
        if mode not in VALID_MODES:
            errors.append(f"{tid}: invalid mode {mode}")
        policy = node.get("when.policy", "")
        if policy and policy not in VALID_WHEN_POLICIES:
            errors.append(f"{tid}: invalid when.policy {policy}")
        if policy and not node.get("when"):
            errors.append(f"{tid}: when.policy requires when")
        dynamic_state = node.get("dynamic.state", "")
        if dynamic_state and (
            node_role(node) != "dynamic-group"
            or dynamic_state not in VALID_DYNAMIC_GROUP_STATES
        ):
            errors.append(f"{tid}: invalid dynamic.state {dynamic_state}")
        status = node.get("status")
        if status not in (None, "pending"):
            errors.append(f"{tid}: template status must be omitted or pending")
        node_children = children(node)
        if normalized_type in {"task", "gate"} and node_children:
            errors.append(f"{tid}: {normalized_type} cannot have children")
        if normalized_type in {"composite", "loop"} and executor != "main":
            errors.append(f"{tid}: {normalized_type} executor must be main")
        if normalized_type == "gate" and executor != "main":
            errors.append(f"{tid}: gate executor must be main")
        if normalized_type == "loop":
            raw_maximum = node.get("loop.max_iterations", "")
            if not raw_maximum:
                errors.append(f"{tid}: loop missing loop.max_iterations")
            else:
                try:
                    if int(raw_maximum) < 1:
                        errors.append(f"{tid}: loop.max_iterations must be positive")
                except ValueError:
                    errors.append(f"{tid}: loop.max_iterations must be an integer")
            if node.get("loop.on_limit") not in {"failed", "blocked", "succeeded"}:
                errors.append(
                    f"{tid}: loop.on_limit must be failed, blocked, or succeeded"
                )
            if not node_children:
                errors.append(f"{tid}: loop requires at least one child")
        if (
            normalized_type == "composite"
            and not node_children
            and node_role(node) != "dynamic-group"
        ):
            errors.append(
                f"{tid}: composite without children must have role=dynamic-group"
            )
        if mode == "switch":
            if normalized_type != "composite":
                errors.append(f"{tid}: switch mode requires type=composite")
            if not node.get("switch.key"):
                errors.append(f"{tid}: switch mode requires switch.key")
            if not node_children:
                errors.append(f"{tid}: switch requires at least one case")
            default_count = 0
            for child in node_children:
                role = node_role(child)
                if role == "default" or normalize_value(
                    child.get("case.default", "")
                ) in {"true", "1", "yes"}:
                    default_count += 1
                elif role != "case" or not child.get("case.value"):
                    errors.append(
                        f"{tid}: switch children must be role=case with case.value or role=default"
                    )
            if default_count > 1:
                errors.append(f"{tid}: switch has multiple default cases")
        if not node_children and executor == "subagent":
            for field in ("instructions", "deliverables", "acceptance"):
                if not child_text(node, field):
                    errors.append(f"{tid}: subagent leaf missing {field}")
        if node.get("depends_on"):
            errors.append(f"{tid}: templates must use depends_on_template")
        raw = node.get("depends_on_template", "")
        for ref in [item.strip() for item in raw.split(",") if item.strip()]:
            if not ref.startswith("local:"):
                errors.append(f"{tid}: only local: template references are supported")
            references.append((tid, ref))
    for owner, ref in references:
        target = ref.split(":", 1)[1] if ref.startswith("local:") else ""
        if target not in seen:
            errors.append(f"{owner}: unresolved template reference {ref}")
    try:
        root_type = node_type(template_root)
        root_role = node_role(template_root)
    except TreeValidationError as exc:
        errors.append(f"template root node: {exc}")
    else:
        if root_type != "composite" or root_role != "root":
            errors.append("template root node must be type=composite role=root")
    if template_root.get("executor") != "main":
        errors.append("template root node executor must be main")
    if template_root.get("mode", "sequence") not in {"sequence", "parallel"}:
        errors.append("template root node mode must be sequence or parallel")
    return errors


def ensure_managed_metadata(root: ET.Element, config: Dict[str, Any]) -> None:
    root.set("artifact_kind", "template")
    root.set("managed_by_skill", "xc-orchestration-author")
    root.set("read_policy", "author-skill-only")
    meta = find_direct(root, "meta")
    if meta is None:
        meta = ET.Element("meta")
        root.insert(0, meta)
    policy = ensure_direct(meta, "access_policy")
    policy.set("required_skill", "xc-orchestration-author")
    policy.set("read_policy", "author-skill-only")
    policy.text = TEMPLATE_NOTICE
    integrity = ensure_direct(meta, "integrity")
    integrity.set("algorithm", str(config["integrity"]["algorithm"]))
    integrity.set(
        "canonicalization",
        str(config["integrity"]["canonicalization"]),
    )


def _canonical_text(value: Optional[str], has_children: bool) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    if has_children and not text.strip():
        return ""
    return text


def canonical_element(element: ET.Element) -> Dict[str, Any]:
    attrs = dict(element.attrib)
    if element.tag == "integrity":
        attrs.pop("checksum", None)
    child_items = list(element)
    return {
        "tag": element.tag,
        "attrs": {key: attrs[key] for key in sorted(attrs)},
        "text": _canonical_text(element.text, bool(child_items)),
        "children": [canonical_element(child) for child in child_items],
    }


def calculate_checksum(root: ET.Element) -> str:
    payload = json.dumps(
        canonical_element(root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def integrity_element(root: ET.Element) -> Optional[ET.Element]:
    meta = find_direct(root, "meta")
    return find_direct(meta, "integrity") if meta is not None else None


def verify_integrity(root: ET.Element) -> Dict[str, Any]:
    errors: List[str] = []
    meta = find_direct(root, "meta")
    if meta is None:
        return {
            "status": "missing",
            "reason": "missing meta element",
            "expected_checksum": "",
            "actual_checksum": "",
        }
    policy = find_direct(meta, "access_policy")
    integrity = find_direct(meta, "integrity")
    if policy is None:
        errors.append("missing meta.access_policy")
    else:
        if policy.get("required_skill") != "xc-orchestration-author":
            errors.append(
                f"access policy requires {policy.get('required_skill')}, expected xc-orchestration-author"
            )
        if policy.get("read_policy") != "author-skill-only":
            errors.append("access policy read_policy mismatch")
    if root.get("managed_by_skill") != "xc-orchestration-author":
        errors.append("root managed_by_skill mismatch")
    if root.get("read_policy") != "author-skill-only":
        errors.append("root read_policy mismatch")
    if root.get("artifact_kind") != "template":
        errors.append("root artifact_kind mismatch: expected template")
    if integrity is None:
        return {
            "status": "missing",
            "reason": "; ".join(errors + ["missing meta.integrity"]),
            "expected_checksum": "",
            "actual_checksum": "",
        }
    algorithm = integrity.get("algorithm", "")
    canonicalization = integrity.get("canonicalization", "")
    expected = integrity.get("checksum", "")
    if algorithm != "sha256" or canonicalization != "orchestration-tree-v1":
        return {
            "status": "unsupported",
            "reason": "; ".join(errors + ["unsupported integrity metadata"]),
            "expected_checksum": expected,
            "actual_checksum": "",
            "algorithm": algorithm,
            "canonicalization": canonicalization,
        }
    actual = calculate_checksum(root)
    if not expected:
        errors.append("missing checksum")
    elif expected != actual:
        errors.append("checksum mismatch")
    return {
        "status": "valid" if not errors else "mismatch",
        "reason": "; ".join(errors) if errors else "checksum verified",
        "expected_checksum": expected,
        "actual_checksum": actual,
        "algorithm": algorithm,
        "canonicalization": canonicalization,
    }


def apply_integrity(root: ET.Element, config: Dict[str, Any]) -> str:
    ensure_managed_metadata(root, config)
    root.set("updated_at", TEMPLATE_UPDATED_AT)
    integrity = integrity_element(root)
    if integrity is None:
        raise AuthorError("managed metadata missing integrity")
    checksum = calculate_checksum(root)
    integrity.set("checksum", checksum)
    return checksum


def serialize_xml(root: ET.Element) -> str:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<!-- {TEMPLATE_NOTICE} -->\n"
        f"{body}\n"
    )


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
            try:
                os.replace(temp_name, path)
                break
            except OSError as exc:
                retryable = (
                    exc.errno in {errno.EACCES, errno.EPERM}
                    or getattr(exc, "winerror", None) in TRANSIENT_REPLACE_WINERRORS
                )
                if not retryable or attempt == ATOMIC_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(ATOMIC_REPLACE_RETRY_DELAY_SECONDS * (attempt + 1))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_xml(path: Path) -> ET.ElementTree:
    if not path.exists():
        raise AuthorError("template file not found", {"path": str(path)})
    try:
        return ET.parse(path)
    except ET.ParseError as exc:
        raise AuthorError(
            "XML parse error",
            {"path": str(path), "error": str(exc)},
        ) from exc


def run_git(
    args: Sequence[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_root_for(path: Path) -> Optional[Path]:
    result = run_git(["rev-parse", "--show-toplevel"], path.parent)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def commit_template(
    path: Path,
    operation: str,
    checksum: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    if not config["git"]["auto_commit"]:
        return {"status": "disabled"}
    repo_root = git_root_for(path)
    if repo_root is None:
        return {"status": "not_applicable"}
    resolved = path.resolve()
    if not resolved.exists():
        return {"status": "failed", "error": f"managed path does not exist: {resolved}"}
    try:
        relative = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return {
            "status": "failed",
            "error": f"managed path is outside the workshop Git repository: {resolved}",
        }

    temp_index = Path(tempfile.gettempdir()) / f"orchestration-index-{uuid.uuid4().hex}"
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        head = run_git(["rev-parse", "--verify", "HEAD"], repo_root, env)
        if head.returncode == 0:
            read_tree = run_git(["read-tree", "HEAD"], repo_root, env)
            if read_tree.returncode != 0:
                return {"status": "failed", "error": read_tree.stderr.strip()}
        add = run_git(["add", "--", relative], repo_root, env)
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip()}
        diff = run_git(["diff", "--cached", "--quiet", "--", relative], repo_root, env)
        if diff.returncode == 0:
            return {"status": "no_changes"}
        if diff.returncode != 1:
            return {"status": "failed", "error": diff.stderr.strip()}
        message = str(config["git"]["commit_message"]).format(
            operation=operation,
            work_order_id="template",
            checksum_short=checksum[:12],
        )
        commit = run_git(["commit", "-m", message], repo_root, env)
        if commit.returncode != 0:
            return {
                "status": "failed",
                "error": commit.stderr.strip() or commit.stdout.strip(),
            }
        sha = run_git(["rev-parse", "HEAD"], repo_root, env)
        index_sync = run_git(["reset", "--mixed", "HEAD", "--", relative], repo_root)
        result: Dict[str, Any] = {
            "status": "committed",
            "sha": sha.stdout.strip(),
        }
        result["index_sync"] = (
            {"status": "synced"}
            if index_sync.returncode == 0
            else {"status": "failed", "error": index_sync.stderr.strip()}
        )
        return result
    finally:
        if temp_index.exists():
            temp_index.unlink()
        lock = Path(f"{temp_index}.lock")
        if lock.exists():
            lock.unlink()


def persist_template(
    root: ET.Element,
    path: Path,
    config: Dict[str, Any],
    operation: str,
) -> Dict[str, Any]:
    checksum = apply_integrity(root, config)
    atomic_write_bytes(path, serialize_xml(root).encode("utf-8"))
    integrity = verify_integrity(parse_xml(path).getroot())
    if integrity["status"] != "valid":
        raise AuthorError(
            "checksum verification failed after write",
            {"path": str(path), "integrity": integrity},
        )
    commit = commit_template(path, operation, checksum, config)
    return {
        "status": "persisted_uncommitted" if commit["status"] == "failed" else "persisted",
        "path": str(path),
        "checksum": checksum,
        "integrity": integrity,
        "commit": commit,
    }
