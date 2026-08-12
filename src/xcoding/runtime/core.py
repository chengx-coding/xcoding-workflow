#!/usr/bin/env python3
"""Shared orchestration runtime model, persistence, and integrity helpers.

This module owns runtime tree semantics. CLI commands, the local viewer, and
template tooling use these helpers instead of parsing or writing managed XML
independently.
"""

from __future__ import annotations

import copy
import errno
import html
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


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

RUNTIME_NOTICE = (
    "ATTENTION: AGENTS MUST ONLY READ OR OPERATE THIS RUNTIME TREE THROUGH "
    "THE xc-orchestration-runtime SKILL AND ITS PUBLIC COMMANDS. DO NOT OPEN, "
    "SUMMARIZE, EDIT, PATCH, OR REFORMAT THIS FILE DIRECTLY."
)
TEMPLATE_NOTICE = (
    "ATTENTION: AGENTS MUST ONLY READ OR OPERATE THIS TEMPLATE THROUGH THE "
    "xc-orchestration-author SKILL AND ITS PUBLIC COMMANDS. DO NOT OPEN, "
    "SUMMARIZE, EDIT, PATCH, OR REFORMAT THIS FILE DIRECTLY."
)

SUCCESS_STATUSES = {"succeeded", "skipped"}
TERMINAL_STATUSES = {"succeeded", "failed", "blocked", "skipped"}
RUNNABLE_STATUSES = {"pending", "ready"}
VALID_STATUSES = {"pending", "ready", "running", "succeeded", "failed", "blocked", "skipped"}
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
CHECK_RESULT_MAX_BYTES = 8192
ATOMIC_REPLACE_ATTEMPTS = 5
ATOMIC_REPLACE_RETRY_DELAY_SECONDS = 0.05
TRANSIENT_REPLACE_WINERRORS = {5, 32}
RUNTIME_LOCK_TIMEOUT_SECONDS = 15
RUNTIME_LOCK_RETRY_SECONDS = 0.05
CONFIG_FILENAME = "xc-orchestration-runtime.json"
LEGACY_CONFIG_FILENAME = "xc-orchestration-runtime.toml"
SVG_NODE_WIDTH = 232
SVG_NODE_HEIGHT = 86
SVG_COLUMN_GAP = 112
SVG_ROW_GAP = 30
SVG_PADDING = 42
SVG_HEADER_HEIGHT = 72


class RuntimeErrorBase(RuntimeError):
    """Base error carrying a stable machine-readable error code."""

    code = "runtime_error"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConfigError(RuntimeErrorBase):
    code = "config_error"


class IntegrityError(RuntimeErrorBase):
    code = "integrity_write_blocked"


class TreeValidationError(RuntimeErrorBase):
    code = "tree_validation_error"


class StateConflictError(RuntimeErrorBase):
    code = "state_conflict"


class TreeSealedError(RuntimeErrorBase):
    code = "tree_sealed"


class DynamicGroupClosedError(RuntimeErrorBase):
    code = "group_closed"


class InvalidTransitionError(RuntimeErrorBase):
    code = "invalid_transition"


class NodeNotReadyError(RuntimeErrorBase):
    code = "node_not_ready"


class LegacySchemaError(RuntimeErrorBase):
    code = "legacy_schema_rejected"


class InvalidControlMetadataError(RuntimeErrorBase):
    code = "invalid_control_metadata"


class ControlPacketNotDeclaredError(RuntimeErrorBase):
    code = "control_packet_not_declared"


class ControlPacketUnavailableError(RuntimeErrorBase):
    code = "control_packet_unavailable"


class InvalidCheckResultError(RuntimeErrorBase):
    code = "invalid_check_result"


class CompletionRequirementsFailedError(RuntimeErrorBase):
    code = "completion_requirements_failed"


class GateOutcomeRequiredError(RuntimeErrorBase):
    code = "gate_outcome_required"


class InvalidGateOutcomeError(RuntimeErrorBase):
    code = "invalid_gate_outcome"


class GateDecisionRequiredError(RuntimeErrorBase):
    code = "gate_decision_required"


class GateOutcomeConflictError(RuntimeErrorBase):
    code = "gate_outcome_conflict"


class GateOutcomeNotAllowedError(RuntimeErrorBase):
    code = "gate_outcome_not_allowed"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slug(value: str, fallback: str = "node") -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = fallback
    if not normalized[0].isalpha():
        normalized = f"{fallback}-{normalized}"
    return normalized


def json_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


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
    if tree_path is None:
        current = Path.cwd().resolve()
    else:
        resolved = tree_path.resolve()
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


def parse_set_values(values: Optional[Sequence[str]]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for item in values or []:
        if "=" not in item:
            raise RuntimeErrorBase("--set/--var expects key=value", {"value": item})
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RuntimeErrorBase("--set/--var key cannot be empty", {"value": item})
        result.append((key, value))
    return result


def parse_metadata_values(values: Optional[Sequence[str]]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in parse_set_values(values):
        if not key.startswith("metadata.") or key == "metadata." or ".." in key:
            raise RuntimeErrorBase("--metadata expects a non-empty metadata.<key>=value entry", {"key": key})
        if key in seen:
            raise RuntimeErrorBase("--metadata keys must be unique", {"key": key})
        seen.add(key)
        result.append((key, value))
    return result


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


def _deduplicate_control_violations(violations: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
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
        fact_match = re.fullmatch(r"metadata\.completion\.check\.([^.]+)\.facts\.([^.]+)", key)
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
            violations.append(_control_violation(path_key, "invalid_artifact_path_selector"))
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
        check_entries = [
            entry
            for entry in (
                [check_subjects.get(check)]
                + list(check_facts.get(check, {}).values())
            )
            if entry is not None
        ]
        if not CHECK_NAME_RE.fullmatch(check):
            for key, _ in check_entries:
                violations.append(_control_violation(key, "invalid_check_names"))
        if check not in declared_check_set:
            for key, _ in check_entries:
                violations.append(_control_violation(key, "invalid_check_names"))
        if check in declared_check_set and check not in check_subjects:
            violations.append(
                _control_violation(
                    f"metadata.completion.check.{check}.subject",
                    "missing_check_subject",
                )
            )
    for check, (key, value) in check_subjects.items():
        if not _value_selector_valid(value):
            violations.append(_control_violation(key, "invalid_check_subject_selector"))
    for facts in check_facts.values():
        for fact, (key, value) in facts.items():
            if not CHECK_FACT_RE.fullmatch(fact):
                violations.append(_control_violation(key, "invalid_check_fact_name"))
            if not _value_selector_valid(value):
                violations.append(_control_violation(key, "invalid_check_fact_selector"))

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
        violations.extend(_control_violation(key, "invalid_metadata_owner") for key in gate_keys)
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
        violations.append(_control_violation(decision_key, "invalid_gate_decision_required"))
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


def parse_xml(path: Path) -> ET.ElementTree:
    if not path.exists():
        raise RuntimeErrorBase("orchestration file not found", {"path": str(path)})
    try:
        return ET.parse(path)
    except ET.ParseError as exc:
        raise RuntimeErrorBase("XML parse error", {"path": str(path), "error": str(exc)}) from exc


def find_direct(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in list(parent):
        if child.tag == tag:
            return child
    return None


def ensure_direct(parent: ET.Element, tag: str, insert_at: Optional[int] = None) -> ET.Element:
    existing = find_direct(parent, tag)
    if existing is not None:
        return existing
    child = ET.Element(tag)
    if insert_at is None:
        parent.append(child)
    else:
        parent.insert(insert_at, child)
    return child


def children(node: ET.Element) -> List[ET.Element]:
    holder = find_direct(node, "children")
    if holder is None:
        return []
    return [child for child in list(holder) if child.tag == "node"]


def iter_nodes(root: ET.Element) -> Iterator[ET.Element]:
    yield from root.iter("node")


def root_node(root: ET.Element) -> ET.Element:
    node = find_direct(root, "node")
    if node is None:
        raise TreeValidationError("orchestration has no root node")
    return node


def child_text(node: ET.Element, tag: str) -> str:
    child = find_direct(node, tag)
    return (child.text or "").strip() if child is not None else ""


def ensure_node_child(node: ET.Element, tag: str) -> ET.Element:
    return ensure_direct(node, tag)


def normalize_type(node_type: str, role: str = "") -> Tuple[str, str]:
    if node_type not in VALID_TYPES:
        raise TreeValidationError("invalid node type", {"type": node_type})
    return node_type, role


def node_type(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[0]


def node_role(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[1]


def find_meta(root: ET.Element) -> Optional[ET.Element]:
    return find_direct(root, "meta")


def notice_for(artifact_kind: str) -> Tuple[str, str, str]:
    if artifact_kind == "template":
        return "xc-orchestration-author", "author-skill-only", TEMPLATE_NOTICE
    if artifact_kind == "runtime":
        return "xc-orchestration-runtime", "runtime-skill-only", RUNTIME_NOTICE
    raise TreeValidationError("invalid artifact kind", {"artifact_kind": artifact_kind})


def ensure_managed_metadata(root: ET.Element, artifact_kind: str, config: Dict[str, Any]) -> ET.Element:
    skill, read_policy, notice = notice_for(artifact_kind)
    root.set("artifact_kind", artifact_kind)
    root.set("managed_by_skill", skill)
    root.set("read_policy", read_policy)
    meta = find_meta(root)
    if meta is None:
        meta = ET.Element("meta")
        root.insert(0, meta)
    policy = ensure_direct(meta, "access_policy")
    policy.set("required_skill", skill)
    policy.set("read_policy", read_policy)
    policy.text = notice
    integrity = ensure_direct(meta, "integrity")
    integrity.set("algorithm", str(config["integrity"]["algorithm"]))
    integrity.set("canonicalization", str(config["integrity"]["canonicalization"]))
    return meta


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
    canonical = canonical_element(root)
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def integrity_element(root: ET.Element) -> Optional[ET.Element]:
    meta = find_meta(root)
    return find_direct(meta, "integrity") if meta is not None else None


def verify_integrity(root: ET.Element, artifact_kind: Optional[str] = None) -> Dict[str, Any]:
    kind = artifact_kind or root.get("artifact_kind", "runtime")
    skill, read_policy, _ = notice_for(kind)
    errors: List[str] = []
    meta = find_meta(root)
    if meta is None:
        return {"status": "missing", "reason": "missing meta element", "expected_checksum": "", "actual_checksum": ""}
    policy = find_direct(meta, "access_policy")
    integrity = find_direct(meta, "integrity")
    if policy is None:
        errors.append("missing meta.access_policy")
    else:
        if policy.get("required_skill") != skill:
            errors.append(f"access policy requires {policy.get('required_skill')}, expected {skill}")
        if policy.get("read_policy") != read_policy:
            errors.append("access policy read_policy mismatch")
    if root.get("managed_by_skill") != skill:
        errors.append("root managed_by_skill mismatch")
    if root.get("read_policy") != read_policy:
        errors.append("root read_policy mismatch")
    if root.get("artifact_kind") != kind:
        errors.append(f"root artifact_kind mismatch: expected {kind}")
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


def apply_integrity(root: ET.Element, artifact_kind: str, config: Dict[str, Any]) -> str:
    ensure_managed_metadata(root, artifact_kind, config)
    root.set("updated_at", TEMPLATE_UPDATED_AT if artifact_kind == "template" else utc_now())
    integrity = integrity_element(root)
    if integrity is None:
        raise RuntimeErrorBase("managed metadata missing integrity")
    checksum = calculate_checksum(root)
    integrity.set("checksum", checksum)
    return checksum


def xml_warning(artifact_kind: str) -> str:
    _, _, notice = notice_for(artifact_kind)
    return notice


def serialize_xml(root: ET.Element, artifact_kind: str) -> str:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="utf-8"?>\n<!-- {xml_warning(artifact_kind)} -->\n{body}\n'


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
                retryable = exc.errno in {errno.EACCES, errno.EPERM} or getattr(exc, "winerror", None) in TRANSIENT_REPLACE_WINERRORS
                if not retryable or attempt == ATOMIC_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(ATOMIC_REPLACE_RETRY_DELAY_SECONDS * (attempt + 1))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def runtime_lock_path(tree_path: Path) -> Path:
    resolved = str(tree_path.resolve()).encode("utf-8")
    digest = hashlib.sha256(resolved).hexdigest()
    return Path(tempfile.gettempdir()) / f"xc-orchestration-{digest}.lock"


@contextmanager
def runtime_write_lock(tree_path: Path) -> Iterator[None]:
    """Serialize runtime mutations for one local managed tree."""

    lock_path = runtime_lock_path(tree_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + RUNTIME_LOCK_TIMEOUT_SECONDS
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise StateConflictError(
                        "timed out waiting for the runtime mutation lock",
                        {"tree_path": str(tree_path), "lock_path": str(lock_path)},
                    )
                time.sleep(RUNTIME_LOCK_RETRY_SECONDS)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_git(args: Sequence[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
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


def commit_managed_paths(
    paths: Sequence[Path],
    operation: str,
    work_order_id: str,
    checksum: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    if not config["git"]["auto_commit"]:
        return {"status": "disabled"}
    if not paths:
        return {"status": "no_changes"}
    repo_root = git_root_for(paths[0])
    if repo_root is None:
        return {"status": "not_applicable"}
    rel_paths: List[str] = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.exists():
            return {"status": "failed", "error": f"managed path does not exist: {resolved}"}
        try:
            rel = resolved.relative_to(repo_root).as_posix()
        except ValueError:
            return {
                "status": "failed",
                "error": f"managed path is outside the workshop Git repository: {resolved}",
            }
        if rel not in rel_paths:
            rel_paths.append(rel)

    temp_index = Path(tempfile.gettempdir()) / f"orchestration-index-{uuid.uuid4().hex}"
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        head = run_git(["rev-parse", "--verify", "HEAD"], repo_root, env)
        if head.returncode == 0:
            read_tree = run_git(["read-tree", "HEAD"], repo_root, env)
            if read_tree.returncode != 0:
                return {"status": "failed", "error": read_tree.stderr.strip()}
        add = run_git(["add", "--", *rel_paths], repo_root, env)
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip()}
        diff = run_git(["diff", "--cached", "--quiet", "--", *rel_paths], repo_root, env)
        if diff.returncode == 0:
            return {"status": "no_changes"}
        if diff.returncode != 1:
            return {"status": "failed", "error": diff.stderr.strip()}
        message_template = str(config["git"]["commit_message"])
        message = message_template.format(
            operation=operation,
            work_order_id=work_order_id or "template",
            checksum_short=checksum[:12],
        )
        commit = run_git(["commit", "-m", message], repo_root, env)
        if commit.returncode != 0:
            return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}
        sha = run_git(["rev-parse", "HEAD"], repo_root, env)
        index_sync = run_git(["reset", "--mixed", "HEAD", "--", *rel_paths], repo_root)
        result = {"status": "committed", "sha": sha.stdout.strip()}
        if index_sync.returncode != 0:
            result["index_sync"] = {"status": "failed", "error": index_sync.stderr.strip()}
        else:
            result["index_sync"] = {"status": "synced"}
        return result
    finally:
        if temp_index.exists():
            temp_index.unlink()
        lock = Path(f"{temp_index}.lock")
        if lock.exists():
            lock.unlink()


def write_managed_tree(
    tree: ET.ElementTree,
    path: Path,
    artifact_kind: str,
    config: Dict[str, Any],
    operation: str,
    commit_paths: Optional[Sequence[Path]] = None,
    commit_on_write: bool = True,
    export_runtime_svg: bool = False,
) -> Dict[str, Any]:
    root = tree.getroot()
    checksum = apply_integrity(root, artifact_kind, config)
    atomic_write_text(path, serialize_xml(root, artifact_kind))
    reloaded = parse_xml(path)
    integrity = verify_integrity(reloaded.getroot(), artifact_kind)
    if integrity["status"] != "valid":
        raise RuntimeErrorBase("checksum verification failed after write", {"path": str(path), "integrity": integrity})
    generated_paths: List[Path] = []
    if artifact_kind == "runtime" and export_runtime_svg:
        svg_path = runtime_svg_path(path, reloaded.getroot())
        snapshot = snapshot_from_root(reloaded.getroot(), path, integrity)
        atomic_write_text(svg_path, render_snapshot_svg(snapshot))
        generated_paths.append(svg_path)
    if commit_on_write:
        commit = commit_managed_paths(
            [path, *generated_paths, *(commit_paths or [])],
            operation,
            root.get("work_order_id", ""),
            checksum,
            config,
        )
    else:
        commit = {"status": "deferred"}
    result: Dict[str, Any] = {
        "path": str(path),
        "checksum": checksum,
        "integrity": integrity,
        "commit": commit,
    }
    if generated_paths:
        result["svg_path"] = str(generated_paths[0])
    if commit["status"] == "failed":
        result["status"] = "persisted_uncommitted"
    else:
        result["status"] = "persisted"
    return result


def read_tree_with_integrity(path: Path, config: Dict[str, Any], artifact_kind: Optional[str] = None) -> Tuple[ET.ElementTree, Dict[str, Any]]:
    tree = parse_xml(path)
    integrity = verify_integrity(tree.getroot(), artifact_kind)
    return tree, integrity


def require_writable_integrity(integrity: Dict[str, Any]) -> None:
    if integrity.get("status") != "valid":
        raise IntegrityError(
            "integrity mismatch blocks tree modification; inspect then run repair-integrity explicitly",
            {"integrity": integrity},
        )


def require_target_runtime_schema(root: ET.Element) -> None:
    if root.get("artifact_kind") != "runtime":
        return
    legacy_fields = {
        "run_" + "id",
        "runtime_" + "dir",
        "artifacts_" + "dir",
        "runs_" + "dir",
        "run" + ".document_language",
        "run" + ".has_features",
        "run" + ".requires_analysis",
        "run" + ".requires_clarification",
        "run" + ".requires_solution",
        "run" + ".solution_gate_required",
        "run" + ".requires_implementation",
        "run" + ".requires_verification",
        "context" + ".setup.ready",
    }
    legacy_paths: List[str] = []
    for element in root.iter():
        for key in element.attrib:
            if key in legacy_fields:
                legacy_paths.append(f"{element.tag}/@{key}")
        if element.tag == "var" and element.get("key") in legacy_fields:
            legacy_paths.append(f"blackboard/{element.get('key')}")
    if not root.get("work_order_id") or legacy_paths:
        raise LegacySchemaError(
            "ordinary runtime commands accept only the work-order schema",
            {
                "required_field": "work_order_id",
                "legacy_fields": sorted(set(legacy_paths)),
            },
        )


def blackboard(root: ET.Element) -> Dict[str, str]:
    holder = find_direct(root, "blackboard")
    result: Dict[str, str] = {}
    if holder is None:
        return result
    for var in holder.findall("var"):
        key = var.get("key")
        if key:
            result[key] = (var.text or "").strip()
    return result


def blackboard_updated_at(root: ET.Element) -> str:
    holder = find_direct(root, "blackboard")
    if holder is None:
        return ""
    timestamps = [variable.get("updated_at", "") for variable in holder.findall("var")]
    return max((timestamp for timestamp in timestamps if timestamp), default="")


def ensure_blackboard(root: ET.Element) -> ET.Element:
    return ensure_direct(root, "blackboard", insert_at=1)


def set_blackboard(root: ET.Element, key: str, value: str, source: str = "script") -> None:
    holder = ensure_blackboard(root)
    target = None
    for var in holder.findall("var"):
        if var.get("key") == key:
            target = var
            break
    if target is None:
        target = ET.SubElement(holder, "var", {"key": key})
    target.text = value
    target.set("updated_at", utc_now())
    target.set("source", source)


def root_node(root: ET.Element) -> ET.Element:
    node = find_direct(root, "node")
    if node is None:
        raise TreeValidationError("orchestration has no root node")
    return node


def runtime_revision(root: ET.Element) -> int:
    raw = root.get("revision", "0")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise TreeValidationError("runtime revision must be a non-negative integer", {"revision": raw}) from exc
    if revision < 0:
        raise TreeValidationError("runtime revision must be a non-negative integer", {"revision": raw})
    return revision


def require_expected_revision(root: ET.Element, expected_revision: Optional[int]) -> None:
    current = runtime_revision(root)
    if expected_revision is not None and expected_revision != current:
        raise StateConflictError(
            "runtime revision does not match the expected revision",
            {"expected_revision": expected_revision, "actual_revision": current},
        )


def is_runtime_sealed(root: ET.Element) -> bool:
    return root.get("status") == "succeeded" or bool(root.get("sealed_at"))


def require_runtime_mutable(root: ET.Element, operation: str) -> None:
    if is_runtime_sealed(root):
        raise TreeSealedError(
            "successful runtime trees are sealed; reopen explicitly before mutating them",
            {
                "operation": operation,
                "sealed_at": root.get("sealed_at", ""),
                "revision": runtime_revision(root),
            },
        )


def finalize_runtime_mutation(root: ET.Element) -> int:
    revision = runtime_revision(root) + 1
    root.set("revision", str(revision))
    if root.get("status") == "succeeded" and not root.get("sealed_at"):
        root.set("sealed_at", utc_now())
        root.set("sealed_revision", str(revision))
        root.set("sealed_epoch", root.get("epoch", "0"))
    return revision


def reopen_runtime_tree(root: ET.Element, reason: str) -> None:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise TreeValidationError("reopen reason must not be empty")
    if root.get("status") != "succeeded":
        raise InvalidTransitionError(
            "only successful runtime trees can be reopened",
            {"status": root.get("status", "pending")},
        )

    try:
        next_epoch = int(root.get("epoch", "0")) + 1
    except ValueError as exc:
        raise TreeValidationError("runtime epoch must be a non-negative integer", {"epoch": root.get("epoch", "")}) from exc

    metadata = find_meta(root)
    if metadata is None:
        raise TreeValidationError("runtime metadata is missing")
    history = ensure_direct(metadata, "reopen_history")
    ET.SubElement(
        history,
        "reopen",
        {
            "epoch": str(next_epoch),
            "reopened_at": utc_now(),
            "reason": normalized_reason,
            "sealed_at": root.get("sealed_at", ""),
            "sealed_revision": root.get("sealed_revision", ""),
        },
    )
    for key in ("sealed_at", "sealed_revision", "sealed_epoch"):
        root.attrib.pop(key, None)
    root.set("epoch", str(next_epoch))
    root.set("reopen_pending", "true")
    root.set("status", "running")
    root_node(root).set("status", "running")


def parent_map(root: ET.Element) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}

    def walk(node: ET.Element, parent_id: Optional[str]) -> None:
        node_id = node.get("id")
        if node_id:
            result[node_id] = parent_id
        for child in children(node):
            walk(child, node_id)

    walk(root_node(root), None)
    return result


def element_parent_map(root: ET.Element) -> Dict[str, ET.Element]:
    result: Dict[str, ET.Element] = {}

    def walk(node: ET.Element) -> None:
        for child in children(node):
            if child.get("id"):
                result[child.get("id", "")] = node
            walk(child)

    walk(root_node(root))
    return result


def nodes_by_id(root: ET.Element) -> Dict[str, ET.Element]:
    return {node.get("id", ""): node for node in iter_nodes(root) if node.get("id")}


def find_node(root: ET.Element, node_id: str) -> ET.Element:
    node = nodes_by_id(root).get(node_id)
    if node is None:
        raise RuntimeErrorBase("node not found", {"node_id": node_id})
    return node


def is_dynamic_group(node: ET.Element) -> bool:
    return node_type(node) == "composite" and node_role(node) == "dynamic-group"


def dynamic_group_state(node: ET.Element) -> str:
    if not is_dynamic_group(node):
        return ""
    return node.get("dynamic.state", "open")


def close_dynamic_group(root: ET.Element, group_id: str) -> ET.Element:
    group = find_node(root, group_id)
    if not is_dynamic_group(group):
        raise TreeValidationError("close-group requires a dynamic-group composite", {"group_id": group_id})
    state = dynamic_group_state(group)
    if state not in VALID_DYNAMIC_GROUP_STATES:
        raise TreeValidationError("dynamic group has invalid state", {"group_id": group_id, "state": state})
    if state == "closed":
        return group
    group.set("dynamic.state", "closed")
    group.attrib.pop("recovery.open", None)
    stabilize(root)
    return group


def reopen_dynamic_group(root: ET.Element, group_id: str, reason: str) -> ET.Element:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise TreeValidationError("reopen-group reason must not be empty")
    group = find_node(root, group_id)
    if not is_dynamic_group(group):
        raise TreeValidationError("reopen-group requires a dynamic-group composite", {"group_id": group_id})
    state = dynamic_group_state(group)
    if state != "closed":
        raise InvalidTransitionError(
            "only a closed dynamic group can be reopened",
            {"group_id": group_id, "state": state},
        )
    metadata = find_meta(root)
    if metadata is None:
        raise TreeValidationError("runtime metadata is missing")
    history = ensure_direct(metadata, "dynamic_group_reopen_history")
    ET.SubElement(
        history,
        "reopen",
        {
            "group_id": group_id,
            "reopened_at": utc_now(),
            "reason": normalized_reason,
            "revision": str(runtime_revision(root)),
        },
    )
    group.set("dynamic.state", "open")
    group.set("recovery.open", "true")
    stabilize(root)
    return group


def require_dynamic_group_open(parent: ET.Element) -> None:
    if not is_dynamic_group(parent):
        return
    state = dynamic_group_state(parent)
    if state == "closed":
        raise DynamicGroupClosedError(
            "cannot append work to a closed dynamic group",
            {"group_id": parent.get("id", ""), "state": state},
        )
    if state != "open":
        raise TreeValidationError("dynamic group has invalid state", {"group_id": parent.get("id", ""), "state": state})


def normalize_value(value: str) -> str:
    return value.strip().strip('"').strip("'").lower()


def eval_when(expression: str, bb: Dict[str, str]) -> bool:
    expr = expression.strip()
    if not expr:
        return True
    if "==" in expr:
        key, expected = expr.split("==", 1)
        return normalize_value(bb.get(key.strip(), "")) == normalize_value(expected)
    if "!=" in expr:
        key, expected = expr.split("!=", 1)
        return normalize_value(bb.get(key.strip(), "")) != normalize_value(expected)
    if expr.startswith("!"):
        return normalize_value(bb.get(expr[1:].strip(), "")) not in {"1", "true", "yes", "y"}
    return normalize_value(bb.get(expr, "")) in {"1", "true", "yes", "y"}


def when_policy(node: ET.Element) -> str:
    return node.get("when.policy", "reactive")


def when_result(node: ET.Element, bb: Dict[str, str]) -> bool:
    latched = node.get("when.latched", "")
    if when_policy(node) == "latched" and latched in {"true", "false"}:
        return latched == "true"
    return eval_when(node.get("when", ""), bb)


def incomplete_dependency_ids(
    root: ET.Element,
    node: ET.Element,
    lookup: Optional[Dict[str, ET.Element]] = None,
) -> List[str]:
    raw = node.get("depends_on", "").strip()
    if not raw:
        return []
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    incomplete: List[str] = []
    for dep_id in [item.strip() for item in raw.split(",") if item.strip()]:
        dep = node_lookup.get(dep_id)
        if dep is None or dep.get("status", "pending") not in SUCCESS_STATUSES:
            incomplete.append(dep_id)
    return incomplete


def dependencies_satisfied(root: ET.Element, node: ET.Element) -> bool:
    return not incomplete_dependency_ids(root, node)


def ancestor_readiness_blocker(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    parent_lookup = parents if parents is not None else element_parent_map(root)
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    current = node
    current_id = current.get("id", "")
    while current_id in parent_lookup:
        parent = parent_lookup[current_id]
        parent_id = parent.get("id", "")
        parent_status = parent.get("status", "pending")
        if parent_status == "skipped":
            reason = (
                "ancestor_condition_false"
                if parent.get("skip_reason") == "when"
                else "ancestor_skipped"
            )
            return {
                "reason": reason,
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        if parent_status in {"failed", "blocked"}:
            return {
                "reason": f"ancestor_{parent_status}",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        when = parent.get("when")
        if when and not when_result(parent, blackboard_values):
            return {
                "reason": "ancestor_condition_false",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        incomplete = incomplete_dependency_ids(root, parent, node_lookup)
        if incomplete:
            return {
                "reason": "ancestor_dependency_incomplete",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
                "dependency_ids": incomplete,
            }
        if parent.get("mode", "sequence") == "sequence":
            for sibling in children(parent):
                if sibling is current:
                    break
                sibling_status = sibling.get("status", "pending")
                if sibling_status not in SUCCESS_STATUSES:
                    return {
                        "reason": "sequence_predecessor_incomplete",
                        "blocker_node_id": sibling.get("id", ""),
                        "blocker_status": sibling_status,
                    }
        current = parent
        current_id = current.get("id", "")
    return None


def node_readiness_blocker(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    status = node.get("status", "pending")
    if status not in RUNNABLE_STATUSES:
        reason = "condition_false" if status == "skipped" and node.get("skip_reason") == "when" else "node_status"
        return {"reason": reason}
    when = node.get("when")
    if when and not when_result(node, blackboard_values):
        return {"reason": "condition_false"}
    incomplete = incomplete_dependency_ids(root, node, node_lookup)
    if incomplete:
        return {"reason": "dependency_incomplete", "dependency_ids": incomplete}
    return ancestor_readiness_blocker(root, node, parents, node_lookup, blackboard_values)


def is_unlocked_by_ancestors(root: ET.Element, node: ET.Element) -> bool:
    lookup = nodes_by_id(root)
    return not incomplete_dependency_ids(root, node, lookup) and ancestor_readiness_blocker(
        root,
        node,
        lookup=lookup,
    ) is None


def reset_subtree(node: ET.Element) -> None:
    node.set("status", "pending")
    for attr in [
        "started_at",
        "completed_at",
        "failed_at",
        "blocked_at",
        "agent",
        "skipped_at",
        "skip_reason",
        "failure_reason",
        "when.latched",
    ]:
        node.attrib.pop(attr, None)
    result = find_direct(node, "result")
    if result is not None:
        node.remove(result)
    if node_type(node) == "loop":
        node.set("loop.iteration", "1")
        node.attrib.pop("loop.last_completed_iteration", None)
        node.attrib.pop("loop.terminal_iteration", None)
        node.attrib.pop("loop.terminal_reason", None)
        node.attrib.pop("loop.terminal_status", None)
        history = find_direct(node, "history")
        if history is not None:
            node.remove(history)
    for child in children(node):
        reset_subtree(child)


def apply_switches(root: ET.Element) -> bool:
    changed = False
    bb = blackboard(root)
    for node in iter_nodes(root):
        if node.get("mode") != "switch" or not children(node):
            continue
        if node.get("status") in TERMINAL_STATUSES:
            continue
        if not is_unlocked_by_ancestors(root, node):
            continue
        key = node.get("switch.key", "")
        value = bb.get(key, "")
        selected: Optional[ET.Element] = None
        default: Optional[ET.Element] = None
        for child in children(node):
            role = node_role(child)
            if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                default = child
            if normalize_value(child.get("case.value", "")) == normalize_value(value):
                if selected is not None:
                    node.set("status", "failed")
                    node.set("failure_reason", "switch has multiple matching cases")
                    changed = True
                    selected = None
                    break
                selected = child
        if node.get("status") == "failed":
            continue
        if selected is None:
            selected = default
        if selected is None:
            outcome = node.get("switch.no_match", node.get("switch_no_match", "failed"))
            node.set("status", "blocked" if outcome == "blocked" else "failed")
            node.set("failure_reason", f"switch has no matching case for {key}={value}")
            changed = True
            continue
        for child in children(node):
            status = child.get("status", "pending")
            if child is selected:
                if status == "skipped" and child.get("skip_reason") == "switch":
                    child.set("status", "pending")
                    child.attrib.pop("skip_reason", None)
                    changed = True
            elif status not in TERMINAL_STATUSES:
                child.set("status", "skipped")
                child.set("skip_reason", "switch")
                child.set("skipped_at", utc_now())
                changed = True
    return changed


def normalize_conditions(root: ET.Element) -> bool:
    bb = blackboard(root)
    changed = False
    for node in iter_nodes(root):
        when = node.get("when")
        if not when:
            continue
        status = node.get("status", "pending")
        was_conditionally_skipped = status == "skipped" and node.get("skip_reason") == "when"
        if (status not in RUNNABLE_STATUSES and not was_conditionally_skipped) or not is_unlocked_by_ancestors(root, node):
            continue
        should_run = when_result(node, bb)
        if when_policy(node) == "latched" and "when.latched" not in node.attrib:
            node.set("when.latched", "true" if should_run else "false")
            changed = True
        if not should_run and status in RUNNABLE_STATUSES:
            node.set("status", "skipped")
            node.set("skip_reason", "when")
            node.set("skipped_at", utc_now())
            changed = True
        elif should_run and was_conditionally_skipped and when_policy(node) == "reactive":
            node.set("status", "pending")
            node.attrib.pop("skip_reason", None)
            node.attrib.pop("skipped_at", None)
            changed = True
    return changed


def record_loop_history(node: ET.Element, reason: str) -> None:
    history = ensure_node_child(node, "history")
    ET.SubElement(
        history,
        "iteration",
        {
            "index": node.get("loop.iteration", "1"),
            "completed_at": utc_now(),
            "reason": reason,
        },
    )


def loop_terminal_decision(node: ET.Element) -> Optional[Tuple[str, str, str]]:
    status = node.get("loop.terminal_status", "")
    reason = node.get("loop.terminal_reason", "")
    iteration = node.get("loop.terminal_iteration", "")
    if status in {"succeeded", "failed", "blocked"} and reason in {"break", "natural", "limit"}:
        return status, reason, iteration or node.get("loop.iteration", "1")

    current = node.get("loop.iteration", "1")
    if node.get("loop.last_completed_iteration", "") != current:
        return None
    history = find_direct(node, "history")
    if history is None:
        return None
    entries = history.findall("iteration")
    if not entries or entries[-1].get("index") != current:
        return None
    inferred_reason = entries[-1].get("reason", "")
    if inferred_reason in {"break", "natural"}:
        return "succeeded", inferred_reason, current
    if inferred_reason == "limit":
        return node.get("loop.on_limit", "failed"), inferred_reason, current
    return None


def close_loop_descendants(node: ET.Element) -> bool:
    changed = False
    for child in children(node):
        for descendant in iter_nodes(child):
            if descendant.get("status", "pending") in TERMINAL_STATUSES:
                continue
            descendant.set("status", "skipped")
            descendant.set("skip_reason", "loop_closed")
            descendant.set("skipped_at", utc_now())
            for attr in ("started_at", "failed_at", "blocked_at", "agent", "failure_reason"):
                descendant.attrib.pop(attr, None)
            changed = True
    return changed


def persist_loop_terminal_decision(
    node: ET.Element,
    status: str,
    reason: str,
    iteration: str,
) -> bool:
    changed = False
    for key, value in (
        ("loop.terminal_iteration", iteration),
        ("loop.terminal_reason", reason),
        ("loop.terminal_status", status),
    ):
        if node.get(key) != value:
            node.set(key, value)
            changed = True
    return close_loop_descendants(node) or changed


def recompute_containers(root: ET.Element) -> bool:
    changed = False
    for node in reversed(list(iter_nodes(root))):
        kids = children(node)
        if not kids:
            old_status = node.get("status", "pending")
            if old_status == "skipped" and node.get("skip_reason") in {"switch", "when", "loop_closed"}:
                continue
            if is_dynamic_group(node) and dynamic_group_state(node) == "closed":
                if old_status != "succeeded":
                    node.set("status", "succeeded")
                    changed = True
            continue
        old_status = node.get("status", "pending")
        if old_status == "skipped" and node.get("skip_reason") in {"switch", "when", "loop_closed"}:
            continue
        statuses = [child.get("status", "pending") for child in kids]
        ntype = node_type(node)
        if ntype == "loop":
            terminal = loop_terminal_decision(node)
            if terminal is not None:
                terminal_status, terminal_reason, terminal_iteration = terminal
                changed = persist_loop_terminal_decision(
                    node,
                    terminal_status,
                    terminal_reason,
                    terminal_iteration,
                ) or changed
                if old_status != terminal_status:
                    node.set("status", terminal_status)
                    changed = True
                continue
        if ntype == "loop" and all(status in SUCCESS_STATUSES for status in statuses):
            iteration = int(node.get("loop.iteration", "1"))
            maximum = int(node.get("loop.max_iterations", "1"))
            last_completed = node.get("loop.last_completed_iteration", "")
            if last_completed == str(iteration):
                new_status = old_status if old_status in TERMINAL_STATUSES else "succeeded"
                if old_status != new_status:
                    node.set("status", new_status)
                    changed = True
                continue
            break_when = node.get("loop.break_when", "")
            continue_when = node.get("loop.continue_when", "")
            should_break = bool(break_when and eval_when(break_when, blackboard(root)))
            should_continue = bool(continue_when and eval_when(continue_when, blackboard(root)))
            node.set("loop.last_completed_iteration", str(iteration))
            if should_break:
                record_loop_history(node, "break")
                new_status = "succeeded"
                changed = persist_loop_terminal_decision(
                    node,
                    new_status,
                    "break",
                    str(iteration),
                ) or changed
            elif should_continue and iteration < maximum:
                record_loop_history(node, "continue")
                for child in kids:
                    reset_subtree(child)
                node.set("loop.iteration", str(iteration + 1))
                node.set("status", "running")
                changed = True
                continue
            elif should_continue and iteration >= maximum:
                record_loop_history(node, "limit")
                new_status = node.get("loop.on_limit", "failed")
                if new_status not in {"failed", "blocked", "succeeded"}:
                    new_status = "failed"
                changed = persist_loop_terminal_decision(
                    node,
                    new_status,
                    "limit",
                    str(iteration),
                ) or changed
            else:
                record_loop_history(node, "natural")
                new_status = "succeeded"
                changed = persist_loop_terminal_decision(
                    node,
                    new_status,
                    "natural",
                    str(iteration),
                ) or changed
        elif any(status == "failed" for status in statuses):
            new_status = "failed"
        elif any(status == "blocked" for status in statuses):
            new_status = "blocked"
        elif (
            node is root_node(root)
            and root.get("reopen_pending") == "true"
            and all(status in SUCCESS_STATUSES for status in statuses)
        ):
            new_status = "running"
        elif all(status in SUCCESS_STATUSES for status in statuses):
            new_status = "succeeded"
        elif any(status in {"running", "succeeded", "ready"} for status in statuses):
            new_status = "running"
        else:
            new_status = "pending"
        if old_status != new_status:
            node.set("status", new_status)
            changed = True
    root.set("status", root_node(root).get("status", "pending"))
    return changed


def stabilize(root: ET.Element) -> bool:
    changed = False
    for _ in range(32):
        round_changed = apply_switches(root)
        round_changed = normalize_conditions(root) or round_changed
        round_changed = recompute_containers(root) or round_changed
        changed = changed or round_changed
        if not round_changed:
            break
    return changed


def is_runnable(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> bool:
    if node_type(node) in {"composite", "loop"} or children(node):
        return False
    return node_readiness_blocker(root, node, parents, lookup, bb) is None


def ready_from(
    root: ET.Element,
    node: ET.Element,
    limit: int,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> List[ET.Element]:
    parent_lookup = parents if parents is not None else element_parent_map(root)
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    if limit <= 0 or node.get("status") in TERMINAL_STATUSES:
        return []
    kids = children(node)
    if not kids:
        return [node] if is_runnable(root, node, parent_lookup, node_lookup, blackboard_values) else []
    mode = node.get("mode", "sequence")
    if mode == "parallel":
        ready: List[ET.Element] = []
        for child in kids:
            ready.extend(
                ready_from(
                    root,
                    child,
                    limit - len(ready),
                    parent_lookup,
                    node_lookup,
                    blackboard_values,
                )
            )
            if len(ready) >= limit:
                break
        return ready[:limit]
    if mode == "switch":
        for child in kids:
            if child.get("status") != "skipped":
                return ready_from(root, child, limit, parent_lookup, node_lookup, blackboard_values)
        return []
    for child in kids:
        if child.get("status", "pending") in SUCCESS_STATUSES:
            continue
        return ready_from(root, child, limit, parent_lookup, node_lookup, blackboard_values)
    return []


def node_path(root: ET.Element, node: ET.Element) -> List[str]:
    parent_ids = parent_map(root)
    lookup = nodes_by_id(root)
    result: List[str] = []
    current = node.get("id", "")
    while current:
        item = lookup.get(current)
        if item is not None:
            result.append(item.get("title", current))
        current = parent_ids.get(current) or ""
    return list(reversed(result))


def result_snapshot(node: ET.Element) -> Dict[str, Any]:
    result = find_direct(node, "result")
    if result is None:
        return {}
    payload: Dict[str, Any] = {}
    for child in list(result):
        if child.tag == "artifacts":
            payload["artifacts"] = [artifact.get("path", "") for artifact in child.findall("artifact")]
        elif child.tag == "checks":
            payload["checks"] = [
                json.loads((check.text or "").strip())
                for check in child.findall("check")
            ]
        else:
            payload[child.tag] = (child.text or "").strip()
    return payload


def attempt_number(node: ET.Element) -> int:
    raw = node.get("attempt", "1")
    try:
        value = int(raw)
    except ValueError as exc:
        raise TreeValidationError(
            "node attempt must be a positive integer",
            {"node_id": node.get("id", ""), "attempt": raw},
        ) from exc
    if value < 1:
        raise TreeValidationError(
            "node attempt must be a positive integer",
            {"node_id": node.get("id", ""), "attempt": raw},
        )
    return value


def attempt_snapshot(attempt: ET.Element) -> Dict[str, Any]:
    return {
        "number": int(attempt.get("number", "0")),
        "status": attempt.get("status", ""),
        "agent": attempt.get("agent", ""),
        "started_at": attempt.get("started_at", ""),
        "failed_at": attempt.get("failed_at", ""),
        "retried_at": attempt.get("retried_at", ""),
        "retry_reason": attempt.get("retry_reason", ""),
        "result": result_snapshot(attempt),
    }


def attempt_history(node: ET.Element) -> List[Dict[str, Any]]:
    holder = find_direct(node, "attempts")
    if holder is None:
        return []
    return [attempt_snapshot(attempt) for attempt in holder.findall("attempt")]


def validate_attempt_history(node: ET.Element) -> List[str]:
    node_id = node.get("id", "")
    errors: List[str] = []
    holder = find_direct(node, "attempts")
    try:
        current = attempt_number(node)
    except TreeValidationError as exc:
        errors.append(f"{node_id}: {exc}")
        return errors
    if holder is None:
        return errors
    if node_type(node) not in {"task", "gate"} or children(node):
        return [f"{node_id}: attempt history requires an executable leaf"]
    if node.get("attempt") is None:
        errors.append(f"{node_id}: attempt history requires an explicit current attempt")
    previous = 0
    seen: set[int] = set()
    for item in list(holder):
        if item.tag != "attempt":
            errors.append(f"{node_id}: invalid attempts child {item.tag}")
            continue
        raw_number = item.get("number", "")
        try:
            number = int(raw_number)
        except ValueError:
            errors.append(f"{node_id}: archived attempt number must be a positive integer")
            continue
        if number < 1:
            errors.append(f"{node_id}: archived attempt number must be a positive integer")
        if number in seen:
            errors.append(f"{node_id}: duplicate archived attempt {number}")
        if number <= previous:
            errors.append(f"{node_id}: archived attempts must be strictly increasing")
        if number >= current:
            errors.append(f"{node_id}: archived attempt {number} must precede current attempt {current}")
        seen.add(number)
        previous = number
        if item.get("status") != "failed":
            errors.append(f"{node_id}: archived attempt {number} must have status failed")
        for field in ("started_at", "failed_at", "retried_at", "retry_reason"):
            if not item.get(field, "").strip():
                errors.append(f"{node_id}: archived attempt {number} missing {field}")
        result = find_direct(item, "result")
        if result is None:
            errors.append(f"{node_id}: archived attempt {number} missing result")
        elif find_direct(result, "failure_reason") is None:
            errors.append(f"{node_id}: archived attempt {number} missing failure_reason")
        if any(child.tag != "result" for child in list(item)):
            errors.append(f"{node_id}: archived attempt {number} has unsupported children")
    return errors


def _packet_violation(
    code: str,
    *,
    category: str = "",
    selector: str = "",
    source_index: int = -1,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "category": category,
        "selector": selector,
        "source_index": source_index,
        "code": code,
        **extra,
    }


def _sorted_packet_violations(violations: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        violations,
        key=lambda item: (
            str(item.get("category", "")),
            str(item.get("selector", "")),
            int(item.get("source_index", -1)),
            str(item.get("code", "")),
        ),
    )


def _parse_source_list(value: str) -> Optional[List[str]]:
    parsed = _json_string_list(value, nonempty=True)
    if parsed is None or len(parsed) != len(set(parsed)):
        return None
    return parsed


def _source_projection(node: ET.Element) -> Dict[str, Any]:
    result = result_snapshot(node)
    projected: Dict[str, Any] = {
        "node_id": node.get("id", ""),
        "logical_key": node.get("logical_key", ""),
        "title": node.get("title", ""),
        "role": node_role(node),
        "status": node.get("status", "pending"),
    }
    for key in (
        "summary",
        "artifacts",
        "gate_outcome",
        "decision",
        "failure_reason",
        "checks",
    ):
        if key in result:
            projected[key] = result[key]
    if node.get("block_reason"):
        projected["block_reason"] = node.get("block_reason", "")
    return projected


def _target_blockers(root: ET.Element, node: ET.Element) -> List[Dict[str, Any]]:
    status = node.get("status", "pending")
    if status == "blocked":
        return [{"reason": "node_status", "block_reason": node.get("block_reason", "")}]
    if status not in RUNNABLE_STATUSES:
        return []
    blocker = node_readiness_blocker(root, node)
    if blocker is None:
        return []
    allowed = {
        key: blocker[key]
        for key in ("reason", "blocker_node_id", "blocker_status", "dependency_ids")
        if key in blocker
    }
    return [allowed]


def _control_projection(root: ET.Element, node: ET.Element) -> Dict[str, Any]:
    status = node.get("status", "pending")
    ready = status in RUNNABLE_STATUSES and node_readiness_blocker(root, node) is None
    if ready:
        action = "start"
    elif status == "running":
        action = "finish"
    elif status == "blocked":
        action = "resolve-and-unblock"
    elif status == "failed":
        action = "retry-failed"
    elif status in TERMINAL_STATUSES:
        action = "none"
    else:
        action = "wait"
    return {
        "action": action,
        "ready": ready,
        "expected_revision": runtime_revision(root),
        "allowed_terminal_operations": (
            ["complete", "fail", "block"] if status == "running" else []
        ),
    }


def build_control_packet(root: ET.Element, node_id: str) -> Dict[str, Any]:
    target = require_executable_leaf(root, node_id)
    require_valid_control_metadata(root)
    control_metadata = {
        key: value
        for key, value in target.attrib.items()
        if key.startswith("metadata.control_packet.")
    }
    if not control_metadata:
        raise ControlPacketNotDeclaredError(
            "target leaf does not declare a control packet",
            {"node_id": node_id},
        )
    categories: Dict[str, Dict[str, Any]] = {}
    for key, value in control_metadata.items():
        match = re.fullmatch(
            r"metadata\.control_packet\.category\.([^.]+)\.(selectors|min_sources|artifact_min)",
            key,
        )
        if match:
            category, member = match.groups()
            categories.setdefault(category, {})[member] = value

    lookup = nodes_by_id(root)
    bb = blackboard(root)
    violations: List[Dict[str, Any]] = []
    source_categories: List[Dict[str, Any]] = []
    for category in sorted(categories):
        declaration = categories[category]
        selectors = _json_string_list(declaration["selectors"], nonempty=True) or []
        expanded: List[Tuple[str, str, int]] = []
        for selector in selectors:
            if selector.startswith("node:"):
                expanded.append((selector[5:], selector, len(expanded)))
                continue
            key = selector[3:]
            if key not in bb:
                violations.append(
                    _packet_violation(
                        "blackboard_source_missing",
                        category=category,
                        selector=selector,
                        source_index=len(expanded),
                        key=key,
                    )
                )
                continue
            source_ids = _parse_source_list(bb[key])
            if source_ids is None:
                violations.append(
                    _packet_violation(
                        "invalid_blackboard_source_list",
                        category=category,
                        selector=selector,
                        source_index=len(expanded),
                        key=key,
                    )
                )
                continue
            first_source_index = len(expanded)
            expanded.extend(
                (source_id, selector, first_source_index + index)
                for index, source_id in enumerate(source_ids)
            )

        occurrences: Dict[str, List[Tuple[str, int]]] = {}
        for source_id, selector, source_index in expanded:
            occurrences.setdefault(source_id, []).append((selector, source_index))
        for source_id, entries in occurrences.items():
            if len(entries) > 1:
                violations.extend(
                    _packet_violation(
                        "duplicate_source",
                        category=category,
                        selector=selector,
                        source_index=source_index,
                        source_id=source_id,
                    )
                    for selector, source_index in entries
                )

        sources: List[Dict[str, Any]] = []
        artifact_count = 0
        for source_id, selector, source_index in expanded:
            source = lookup.get(source_id)
            if source is None:
                violations.append(
                    _packet_violation(
                        "source_not_found",
                        category=category,
                        selector=selector,
                        source_index=source_index,
                        source_id=source_id,
                    )
                )
                continue
            if source.get("status", "pending") not in TERMINAL_STATUSES:
                violations.append(
                    _packet_violation(
                        "source_not_terminal",
                        category=category,
                        selector=selector,
                        source_index=source_index,
                        source_id=source_id,
                        status=source.get("status", "pending"),
                    )
                )
                continue
            projected = _source_projection(source)
            if not any(
                key in projected
                for key in (
                    "summary",
                    "gate_outcome",
                    "decision",
                    "failure_reason",
                    "block_reason",
                )
            ):
                violations.append(
                    _packet_violation(
                        "source_has_no_projectable_result",
                        category=category,
                        selector=selector,
                        source_index=source_index,
                        source_id=source_id,
                    )
                )
                continue
            artifact_count += len(projected.get("artifacts", []))
            sources.append(projected)
        minimum = int(declaration["min_sources"])
        artifact_minimum = int(declaration["artifact_min"])
        if len(set(source_id for source_id, _, _ in expanded)) < minimum:
            violations.append(
                _packet_violation(
                    "min_sources_not_met",
                    category=category,
                    minimum=minimum,
                    actual=len(set(source_id for source_id, _, _ in expanded)),
                )
            )
        if artifact_count < artifact_minimum:
            violations.append(
                _packet_violation(
                    "artifact_min_not_met",
                    category=category,
                    minimum=artifact_minimum,
                    actual=artifact_count,
                )
            )
        source_categories.append(
            {
                "name": category,
                "min_sources": minimum,
                "artifact_min": artifact_minimum,
                "sources": sources,
            }
        )

    selected_blackboard: List[Dict[str, str]] = []
    blackboard_keys = _json_string_list(
        control_metadata.get("metadata.control_packet.blackboard_keys", "[]")
    ) or []
    for index, key in enumerate(blackboard_keys):
        if key not in bb:
            violations.append(
                _packet_violation(
                    "blackboard_key_missing",
                    selector=f"bb:{key}",
                    source_index=index,
                    key=key,
                )
            )
        else:
            selected_blackboard.append({"key": key, "value": bb[key]})
    if violations:
        raise ControlPacketUnavailableError(
            "control packet requirements are not satisfied",
            {"node_id": node_id, "violations": _sorted_packet_violations(violations)},
        )
    return {
        "schema_version": 1,
        "target": {
            "id": target.get("id", ""),
            "logical_key": target.get("logical_key", ""),
            "role": node_role(target),
            "status": target.get("status", "pending"),
            "executor": target.get("executor", ""),
            "path": node_path(root, target),
            "instructions": child_text(target, "instructions"),
            "inputs": child_text(target, "inputs"),
            "deliverables": child_text(target, "deliverables"),
            "acceptance": child_text(target, "acceptance"),
        },
        "source_categories": source_categories,
        "blackboard": selected_blackboard,
        "blockers": _target_blockers(root, target),
        "control": _control_projection(root, target),
    }


def declared_artifacts(root: ET.Element, audience: str = "") -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for node in iter_nodes(root):
        metadata = {
            key: value
            for key, value in node.attrib.items()
            if key.startswith("metadata.artifact.")
        }
        artifact_audience = metadata.get("metadata.artifact.audience", "internal")
        if audience and artifact_audience != audience:
            continue
        results: List[Tuple[int, ET.Element, bool]] = []
        attempts = find_direct(node, "attempts")
        if attempts is not None:
            for attempt in attempts.findall("attempt"):
                result = find_direct(attempt, "result")
                if result is not None:
                    results.append((int(attempt.get("number", "0")), result, True))
        current_result = find_direct(node, "result")
        if current_result is not None:
            results.append((attempt_number(node), current_result, False))
        for number, result, archived in results:
            artifacts = find_direct(result, "artifacts")
            if artifacts is None:
                continue
            for artifact in artifacts.findall("artifact"):
                path = artifact.get("path", "")
                if path:
                    entry = {
                        "path": path,
                        "node_id": node.get("id", ""),
                        "metadata": dict(sorted(metadata.items())),
                    }
                    if archived or number != 1:
                        entry["attempt"] = number
                    entries.append(entry)
    return entries


def snapshot_node(root: ET.Element, node: ET.Element) -> Dict[str, Any]:
    payload = {
        "id": node.get("id", ""),
        "template_id": node.get("template_id", ""),
        "origin_template_id": node.get("origin_template_id", ""),
        "origin_instance_id": node.get("origin_instance_id", ""),
        "logical_key": node.get("logical_key", ""),
        "title": node.get("title", ""),
        "type": node_type(node),
        "role": node_role(node),
        "executor": node.get("executor", ""),
        "status": node.get("status", "pending"),
        "mode": node.get("mode", ""),
        "path": node_path(root, node),
        "attributes": dict(sorted(node.attrib.items())),
        "instructions": child_text(node, "instructions"),
        "inputs": child_text(node, "inputs"),
        "deliverables": child_text(node, "deliverables"),
        "acceptance": child_text(node, "acceptance"),
        "result": result_snapshot(node),
        "children": [snapshot_node(root, child) for child in children(node)],
    }
    if node_type(node) in {"task", "gate"} and not children(node):
        payload["attempt"] = attempt_number(node)
        payload["attempts"] = attempt_history(node)
    return payload


def status_counts(root: ET.Element) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for node in iter_nodes(root):
        status = node.get("status", "pending")
        result[status] = result.get(status, 0) + 1
    return result


def awaiting_dynamic_groups(root: ET.Element) -> List[Dict[str, str]]:
    groups: List[Dict[str, str]] = []
    for node in iter_nodes(root):
        if (
            not is_dynamic_group(node)
            or dynamic_group_state(node) != "open"
            or children(node)
            or node.get("status", "pending") not in RUNNABLE_STATUSES
            or not is_unlocked_by_ancestors(root, node)
        ):
            continue
        groups.append(
            {
                "id": node.get("id", ""),
                "template_id": node.get("template_id", ""),
                "title": node.get("title", ""),
                "path": " / ".join(node_path(root, node)),
                "state": "open",
            }
        )
    return groups


def snapshot_from_root(root: ET.Element, path: Path, integrity: Dict[str, Any]) -> Dict[str, Any]:
    root_n = root_node(root)
    return {
        "tree_path": str(path.resolve()),
        "version": integrity.get("actual_checksum") or root.get("updated_at", ""),
        "integrity": integrity,
        "metadata": {
            "name": root.get("name", ""),
            "work_order_id": root.get("work_order_id", ""),
            "schema_version": root.get("schema_version", ""),
            "artifact_kind": root.get("artifact_kind", ""),
            "status": root.get("status", "pending"),
            "updated_at": root.get("updated_at", ""),
            "blackboard_updated_at": blackboard_updated_at(root),
            "revision": runtime_revision(root),
            "sealed_at": root.get("sealed_at", ""),
            "epoch": root.get("epoch", "0"),
        },
        "blackboard": blackboard(root),
        "counts": status_counts(root),
        "awaiting_dynamic_groups": awaiting_dynamic_groups(root),
        "ready": [
            {"id": node.get("id"), "title": node.get("title"), "executor": node.get("executor")}
            for node in ready_from(root, root_n, 256)
        ],
        "root": snapshot_node(root, root_n),
    }


def tree_snapshot(path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    tree, integrity = read_tree_with_integrity(path, config)
    require_target_runtime_schema(tree.getroot())
    return snapshot_from_root(tree.getroot(), path, integrity)


def runtime_svg_filename(name: str, work_order_id: str) -> str:
    fallback = slug(work_order_id, "orchestration")
    return f"{slug(name or work_order_id, fallback)}.svg"


def runtime_svg_path(tree_path: Path, root: ET.Element) -> Path:
    return tree_path.parent / runtime_svg_filename(
        root.get("name", ""),
        root.get("work_order_id", ""),
    )


def _svg_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) > limit:
        text = f"{text[: max(limit - 1, 0)]}\u2026"
    return html.escape(text)


def _layout_snapshot_tree(root: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    heights: Dict[str, int] = {}

    def measure(node: Dict[str, Any]) -> int:
        child_nodes = node.get("children") or []
        if not child_nodes:
            heights[str(node.get("id", ""))] = SVG_NODE_HEIGHT
            return SVG_NODE_HEIGHT
        child_height = sum(measure(child) for child in child_nodes)
        height = max(SVG_NODE_HEIGHT, child_height + SVG_ROW_GAP * max(len(child_nodes) - 1, 0))
        heights[str(node.get("id", ""))] = height
        return height

    root_height = measure(root)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    max_depth = 0

    def place(node: Dict[str, Any], depth: int, top: int, parent_id: str = "") -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        node_id = str(node.get("id", ""))
        subtree_height = heights[node_id]
        position = {
            "node": node,
            "x": SVG_PADDING + depth * (SVG_NODE_WIDTH + SVG_COLUMN_GAP),
            "y": SVG_HEADER_HEIGHT + SVG_PADDING + top + (subtree_height - SVG_NODE_HEIGHT) / 2,
        }
        nodes.append(position)
        if parent_id:
            edges.append({"source_id": parent_id, "target_id": node_id, "status": node.get("status", "")})
        child_top = top
        for child in node.get("children") or []:
            place(child, depth + 1, child_top, node_id)
            child_top += heights[str(child.get("id", ""))] + SVG_ROW_GAP

    place(root, 0, 0)
    width = SVG_PADDING * 2 + (max_depth + 1) * SVG_NODE_WIDTH + max_depth * SVG_COLUMN_GAP
    height = SVG_HEADER_HEIGHT + SVG_PADDING * 2 + root_height
    return nodes, edges, width, height


def render_snapshot_svg(snapshot: Dict[str, Any]) -> str:
    root = snapshot.get("root")
    if not isinstance(root, dict):
        raise RuntimeErrorBase("snapshot has no root node")
    nodes, edges, width, height = _layout_snapshot_tree(root)
    positions = {str(item["node"].get("id", "")): item for item in nodes}
    metadata = snapshot.get("metadata") or {}
    status_colors = {
        "succeeded": "#4ade80",
        "running": "#60a5fa",
        "ready": "#60a5fa",
        "failed": "#f87171",
        "blocked": "#f87171",
        "skipped": "#fbbf24",
        "pending": "#94a3b8",
    }
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">'
        ),
        f'  <title id="title">{_svg_text(metadata.get("name") or "Orchestration", 160)}</title>',
        (
            '  <desc id="description">Complete orchestration tree for '
            f'{_svg_text(metadata.get("work_order_id"), 160)}.</desc>'
        ),
        '  <rect width="100%" height="100%" fill="#0b1220"/>',
        (
            f'  <text x="{SVG_PADDING}" y="31" fill="#f8fafc" '
            'font-family="Segoe UI,Arial,sans-serif" font-size="18" font-weight="700">'
            f'{_svg_text(metadata.get("name") or "Orchestration", 100)}</text>'
        ),
        (
            f'  <text x="{SVG_PADDING}" y="53" fill="#94a3b8" '
            'font-family="Segoe UI,Arial,sans-serif" font-size="12">'
            f'Work order {_svg_text(metadata.get("work_order_id"), 80)} '
            f'\u00b7 {_svg_text(metadata.get("status"), 24)}</text>'
        ),
    ]
    for edge in edges:
        source = positions[edge["source_id"]]
        target = positions[edge["target_id"]]
        start_x = source["x"] + SVG_NODE_WIDTH
        start_y = source["y"] + SVG_NODE_HEIGHT / 2
        end_x = target["x"]
        end_y = target["y"] + SVG_NODE_HEIGHT / 2
        control = max((end_x - start_x) * 0.5, 36)
        color = status_colors.get(str(edge["status"]), "#4b607a")
        dash = ' stroke-dasharray="6 5"' if edge["status"] == "skipped" else ""
        lines.append(
            f'  <path d="M {start_x:g} {start_y:g} C {start_x + control:g} {start_y:g}, '
            f'{end_x - control:g} {end_y:g}, {end_x:g} {end_y:g}" fill="none" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
    for item in nodes:
        node = item["node"]
        x = item["x"]
        y = item["y"]
        status = str(node.get("status", "pending"))
        color = status_colors.get(status, "#94a3b8")
        role = " / ".join(part for part in (node.get("type"), node.get("role")) if part)
        lines.extend(
            [
                f'  <g data-node-id="{html.escape(str(node.get("id", "")), quote=True)}" data-status="{html.escape(status, quote=True)}">',
                f'    <title>{html.escape(str(node.get("title") or node.get("id") or ""))}</title>',
                (
                    f'    <rect x="{x:g}" y="{y:g}" width="{SVG_NODE_WIDTH}" height="{SVG_NODE_HEIGHT}" '
                    'rx="9" fill="#172033" stroke="#475569"/>'
                ),
                f'    <rect x="{x:g}" y="{y:g}" width="4" height="{SVG_NODE_HEIGHT}" rx="2" fill="{color}"/>',
                (
                    f'    <text x="{x + 14:g}" y="{y + 27:g}" fill="#f8fafc" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700">'
                    f'{_svg_text(node.get("title") or node.get("id"), 30)}</text>'
                ),
                (
                    f'    <text x="{x + 14:g}" y="{y + 49:g}" fill="#94a3b8" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="11">'
                    f'{_svg_text(role, 35)}</text>'
                ),
                (
                    f'    <text x="{x + 14:g}" y="{y + 70:g}" fill="{color}" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700">'
                    f'{_svg_text(status.upper(), 24)}</text>'
                ),
                "  </g>",
            ]
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def template_id(node: ET.Element) -> str:
    value = node.get("template_id", "")
    if not value or not NODE_KEY_RE.match(value):
        raise TreeValidationError("template node missing valid template_id", {"value": value})
    return value


def copy_node_payload(template_node: ET.Element, runtime_node: ET.Element) -> None:
    for child in list(template_node):
        if child.tag == "children":
            continue
        if child.tag in {"result", "history"}:
            continue
        runtime_node.append(copy.deepcopy(child))


def instantiate_template_node(
    template_node: ET.Element,
    work_order_id: str,
    instance_id: str,
    mapping: Dict[str, str],
    pending_references: List[Tuple[ET.Element, List[str]]],
) -> ET.Element:
    tid = template_id(template_node)
    if tid in mapping:
        raise TreeValidationError("duplicate template_id in template instance", {"template_id": tid})
    canonical_type, role = normalize_type(template_node.get("type", "task"), template_node.get("role", ""))
    runtime_id = (
        f"rt_{slug(work_order_id, 'work-order')}__"
        f"{slug(instance_id, 'instance')}__{tid}"
    )
    mapping[tid] = runtime_id
    attrs = {
        "id": runtime_id,
        "template_id": tid,
        "origin_template_id": tid,
        "origin_instance_id": instance_id,
        "title": template_node.get("title", tid),
        "type": canonical_type,
        "executor": template_node.get("executor", "subagent"),
        "status": "pending",
    }
    if role:
        attrs["role"] = role
    excluded = {
        "id",
        "template_id",
        "origin_template_id",
        "origin_instance_id",
        "status",
        "depends_on",
        "depends_on_template",
        "iteration",
        "loop.iteration",
        "when.latched",
        "loop.terminal_iteration",
        "loop.terminal_reason",
        "loop.terminal_status",
    }
    for key, value in template_node.attrib.items():
        if key not in excluded:
            attrs[key] = value
    if role == "dynamic-group":
        attrs["dynamic.state"] = template_node.get("dynamic.state", "open")
    if canonical_type == "loop":
        attrs["loop.iteration"] = "1"
        attrs["loop.max_iterations"] = template_node.get("loop.max_iterations", "1")
        attrs["loop.continue_when"] = template_node.get("loop.continue_when", "")
        attrs["loop.break_when"] = template_node.get("loop.break_when", "")
        attrs["loop.on_limit"] = template_node.get("loop.on_limit", "failed")
    node = ET.Element("node", attrs)
    copy_node_payload(template_node, node)
    raw_refs = template_node.get("depends_on_template", "")
    if raw_refs:
        pending_references.append((node, [item.strip() for item in raw_refs.split(",") if item.strip()]))
    template_children = children(template_node)
    if template_children:
        holder = ET.SubElement(node, "children")
        for child in template_children:
            holder.append(
                instantiate_template_node(
                    child,
                    work_order_id,
                    instance_id,
                    mapping,
                    pending_references,
                )
            )
    return node


def rewrite_template_references(mapping: Dict[str, str], pending: List[Tuple[ET.Element, List[str]]]) -> None:
    for node, references in pending:
        rewritten: List[str] = []
        for reference in references:
            if not reference.startswith("local:"):
                raise TreeValidationError("template references must use local:", {"reference": reference, "node": node.get("id")})
            target = reference.split(":", 1)[1]
            if target not in mapping:
                raise TreeValidationError("unresolved template reference", {"reference": reference, "node": node.get("id")})
            rewritten.append(mapping[target])
        node.set("depends_on", ",".join(rewritten))
        node.attrib.pop("depends_on_template", None)


def instantiate_runtime_tree(
    template_tree: ET.ElementTree,
    work_order_id: str,
    name: str,
    variables: Sequence[Tuple[str, str]],
    config: Dict[str, Any],
) -> ET.ElementTree:
    template_root = template_tree.getroot()
    validation_errors = validate_template_root(template_root)
    if validation_errors:
        raise TreeValidationError("template validation failed", {"errors": validation_errors})
    source_root = root_node(template_root)
    runtime_root = ET.Element(
        "orchestration",
        {
            "schema_version": "1",
            "name": name or template_root.get("name", "orchestration"),
            "work_order_id": work_order_id,
            "status": "pending",
            "created_at": utc_now(),
            "revision": "0",
        },
    )
    template_bb = find_direct(template_root, "blackboard")
    bb = ET.SubElement(runtime_root, "blackboard")
    if template_bb is not None:
        for var in template_bb.findall("var"):
            copied = ET.SubElement(bb, "var", dict(var.attrib))
            copied.text = var.text
    set_blackboard(runtime_root, "work_order_id", work_order_id, "init")
    set_blackboard(runtime_root, "today", today(), "init")
    for key, value in variables:
        set_blackboard(runtime_root, key, value, "init")
    mapping: Dict[str, str] = {}
    pending: List[Tuple[ET.Element, List[str]]] = []
    runtime_node = instantiate_template_node(
        source_root,
        work_order_id,
        "root",
        mapping,
        pending,
    )
    rewrite_template_references(mapping, pending)
    runtime_root.append(runtime_node)
    meta = ensure_managed_metadata(runtime_root, "runtime", config)
    instances = ensure_direct(meta, "template_instances")
    ET.SubElement(
        instances,
        "instance",
        {
            "id": "root",
            "template_name": template_root.get("name", ""),
            "template_root_id": template_id(source_root),
        },
    )
    runtime_root.set("status", "pending")
    return ET.ElementTree(runtime_root)


def validate_template_root(root: ET.Element, check_integrity: bool = True) -> List[str]:
    errors: List[str] = []
    if root.tag != "orchestration":
        errors.append("template root element must be orchestration")
        return errors
    if root.get("schema_version") != "1":
        errors.append("template schema_version must be 1")
    if check_integrity:
        integrity = verify_integrity(root, "template")
        if integrity["status"] != "valid":
            errors.append(f"template integrity {integrity['status']}: {integrity['reason']}")
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
            normalized_type, _ = normalize_type(node.get("type", ""), node.get("role", ""))
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
        for runtime_key in (
            "when.latched",
            "loop.terminal_iteration",
            "loop.terminal_reason",
            "loop.terminal_status",
        ):
            if node.get(runtime_key) is not None:
                errors.append(f"{tid}: {runtime_key} is runtime-owned")
        dynamic_state = node.get("dynamic.state", "")
        if dynamic_state and (node_role(node) != "dynamic-group" or dynamic_state not in VALID_DYNAMIC_GROUP_STATES):
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
                errors.append(f"{tid}: loop.on_limit must be failed, blocked, or succeeded")
            if not node_children:
                errors.append(f"{tid}: loop requires at least one child")
        if normalized_type == "composite" and not node_children and node_role(node) != "dynamic-group":
            errors.append(f"{tid}: composite without children must have role=dynamic-group")
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
                if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                    default_count += 1
                elif role != "case" or not child.get("case.value"):
                    errors.append(f"{tid}: switch children must be role=case with case.value or role=default")
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


def validate_runtime_root(root: ET.Element, check_integrity: bool = True) -> List[str]:
    errors: List[str] = []
    if root.tag != "orchestration":
        return ["runtime root element must be orchestration"]
    if root.get("schema_version") != "1":
        errors.append("runtime schema_version must be 1")
    if not root.get("work_order_id"):
        errors.append("runtime missing work_order_id")
    try:
        runtime_revision(root)
    except TreeValidationError as exc:
        errors.append(str(exc))
    if check_integrity:
        integrity = verify_integrity(root, "runtime")
        if integrity["status"] != "valid":
            errors.append(f"runtime integrity {integrity['status']}: {integrity['reason']}")
    try:
        runtime_root = root_node(root)
    except TreeValidationError as exc:
        return errors + [str(exc)]
    errors.extend(
        f"{item['node']}: {item['key']}: {item['code']}"
        for item in validate_control_metadata_tree(root)
    )
    ids: set[str] = set()
    logical_keys: set[str] = set()
    references: List[Tuple[str, str]] = []
    for node in iter_nodes(runtime_root):
        node_id = node.get("id", "")
        if not node_id:
            errors.append("runtime node missing id")
            continue
        if node_id in ids:
            errors.append(f"duplicate runtime node id: {node_id}")
        ids.add(node_id)
        try:
            normalized_type, _ = normalize_type(node.get("type", ""), node.get("role", ""))
        except TreeValidationError as exc:
            errors.append(f"{node_id}: {exc}")
            continue
        executor = node.get("executor", "")
        if executor not in VALID_EXECUTORS:
            errors.append(f"{node_id}: invalid executor {executor}")
        status = node.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(f"{node_id}: invalid status {status}")
        errors.extend(validate_attempt_history(node))
        node_children = children(node)
        mode = node.get("mode", "")
        if mode not in VALID_MODES:
            errors.append(f"{node_id}: invalid mode {mode}")
        policy = node.get("when.policy", "")
        if policy and policy not in VALID_WHEN_POLICIES:
            errors.append(f"{node_id}: invalid when.policy {policy}")
        if policy and not node.get("when"):
            errors.append(f"{node_id}: when.policy requires when")
        latched = node.get("when.latched", "")
        if "when.latched" in node.attrib and (
            policy != "latched" or latched not in {"true", "false"}
        ):
            errors.append(f"{node_id}: invalid when.latched")
        dynamic_state = node.get("dynamic.state", "")
        if dynamic_state and (node_role(node) != "dynamic-group" or dynamic_state not in VALID_DYNAMIC_GROUP_STATES):
            errors.append(f"{node_id}: invalid dynamic.state {dynamic_state}")
        if normalized_type in {"task", "gate"} and node_children:
            errors.append(f"{node_id}: {normalized_type} cannot have children")
        if normalized_type in {"task", "gate"} and mode:
            errors.append(f"{node_id}: {normalized_type} cannot set mode")
        if normalized_type in {"composite", "loop"} and executor != "main":
            errors.append(f"{node_id}: {normalized_type} executor must be main")
        if normalized_type == "gate" and executor != "main":
            errors.append(f"{node_id}: gate executor must be main")
        if normalized_type == "loop":
            raw_maximum = node.get("loop.max_iterations", "")
            try:
                if int(raw_maximum) < 1:
                    errors.append(f"{node_id}: loop.max_iterations must be positive")
            except ValueError:
                errors.append(f"{node_id}: loop.max_iterations must be an integer")
            if node.get("loop.on_limit") not in {"failed", "blocked", "succeeded"}:
                errors.append(f"{node_id}: invalid loop.on_limit")
            if not node_children:
                errors.append(f"{node_id}: loop requires at least one child")
            terminal_status = node.get("loop.terminal_status", "")
            terminal_reason = node.get("loop.terminal_reason", "")
            terminal_iteration = node.get("loop.terminal_iteration", "")
            if any((terminal_status, terminal_reason, terminal_iteration)) and not all(
                (terminal_status, terminal_reason, terminal_iteration)
            ):
                errors.append(f"{node_id}: incomplete loop terminal decision")
            if terminal_status and terminal_status not in {"succeeded", "failed", "blocked"}:
                errors.append(f"{node_id}: invalid loop.terminal_status")
            if terminal_reason and terminal_reason not in {"break", "natural", "limit"}:
                errors.append(f"{node_id}: invalid loop.terminal_reason")
            if terminal_iteration:
                try:
                    if int(terminal_iteration) < 1:
                        errors.append(f"{node_id}: loop.terminal_iteration must be positive")
                    elif terminal_iteration != node.get("loop.iteration", "1"):
                        errors.append(f"{node_id}: loop terminal iteration must match loop.iteration")
                except ValueError:
                    errors.append(f"{node_id}: loop.terminal_iteration must be an integer")
            if terminal_status and terminal_status != status:
                errors.append(f"{node_id}: loop terminal status does not match node status")
            if terminal_reason in {"break", "natural"} and terminal_status != "succeeded":
                errors.append(f"{node_id}: {terminal_reason} loop decision must succeed")
            if terminal_reason == "limit" and terminal_status != node.get("loop.on_limit"):
                errors.append(f"{node_id}: limit loop decision must match loop.on_limit")
        elif any(key.startswith("loop.terminal_") for key in node.attrib):
            errors.append(f"{node_id}: loop terminal decision requires type=loop")
        if normalized_type == "composite" and not node_children and node_role(node) != "dynamic-group":
            errors.append(f"{node_id}: composite without children must have role=dynamic-group")
        if mode == "switch":
            if normalized_type != "composite":
                errors.append(f"{node_id}: switch mode requires type=composite")
            if not node.get("switch.key"):
                errors.append(f"{node_id}: switch mode requires switch.key")
            default_count = 0
            for child in node_children:
                role = node_role(child)
                if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                    default_count += 1
                elif role != "case" or not child.get("case.value"):
                    errors.append(f"{node_id}: invalid switch child {child.get('id', '')}")
            if default_count > 1:
                errors.append(f"{node_id}: switch has multiple default cases")
        if not node_children and executor == "subagent":
            for field in ("instructions", "deliverables", "acceptance"):
                if not child_text(node, field):
                    errors.append(f"{node_id}: subagent leaf missing {field}")
        logical_key = node.get("logical_key", "")
        if logical_key:
            if not NODE_KEY_RE.match(logical_key):
                errors.append(f"{node_id}: invalid logical_key")
            elif logical_key in logical_keys:
                errors.append(f"duplicate runtime logical_key: {logical_key}")
            logical_keys.add(logical_key)
        if node.get("depends_on_template"):
            errors.append(f"{node_id}: unresolved depends_on_template")
        references.extend((node_id, ref) for ref in node.get("depends_on", "").split(",") if ref)
    for owner, reference in references:
        if reference.strip() not in ids:
            errors.append(f"{owner}: unresolved runtime dependency {reference.strip()}")
    try:
        root_type = node_type(runtime_root)
        root_role = node_role(runtime_root)
    except TreeValidationError as exc:
        errors.append(f"runtime root node: {exc}")
    else:
        if root_type != "composite" or root_role != "root":
            errors.append("runtime root node must be type=composite role=root")
    if runtime_root.get("executor") != "main":
        errors.append("runtime root node executor must be main")
    if runtime_root.get("mode", "sequence") not in {"sequence", "parallel"}:
        errors.append("runtime root node mode must be sequence or parallel")
    if root.get("status") != runtime_root.get("status"):
        errors.append("runtime root status does not match root node status")
    return errors


def create_dynamic_node(
    root: ET.Element,
    parent_id: str,
    logical_key: str,
    title: str,
    node_type_value: str,
    executor: str,
    role: str = "",
    mode: str = "",
    when: str = "",
    depends_on: str = "",
    instructions: str = "",
    inputs: str = "",
    deliverables: str = "",
    acceptance: str = "",
    metadata: Optional[Sequence[Tuple[str, str]]] = None,
    before_id: str = "",
) -> ET.Element:
    if not NODE_KEY_RE.match(logical_key):
        raise TreeValidationError("logical_key must be lowercase kebab-case", {"logical_key": logical_key})
    parent = find_node(root, parent_id)
    if node_type(parent) not in {"composite", "loop"}:
        raise TreeValidationError("dynamic node parent must be composite or loop", {"parent_id": parent_id})
    require_dynamic_group_open(parent)
    if any(existing.get("logical_key") == logical_key for existing in iter_nodes(root)):
        raise TreeValidationError("logical_key already exists in runtime tree", {"logical_key": logical_key})
    canonical_type, normalized_role = normalize_type(node_type_value, role)
    if executor not in VALID_EXECUTORS:
        raise TreeValidationError("invalid dynamic node executor", {"executor": executor})
    if mode not in VALID_MODES:
        raise TreeValidationError("invalid dynamic node mode", {"mode": mode})
    if canonical_type in {"composite", "loop"} and executor != "main":
        raise TreeValidationError("composite and loop dynamic nodes require executor=main")
    if canonical_type == "gate" and executor != "main":
        raise TreeValidationError("dynamic gate requires executor=main")
    if canonical_type in {"task", "gate"} and mode:
        raise TreeValidationError("dynamic task and gate nodes cannot set mode")
    if executor == "subagent":
        missing = [
            field
            for field, value in (
                ("instructions", instructions),
                ("deliverables", deliverables),
                ("acceptance", acceptance),
            )
            if not value
        ]
        if missing:
            raise TreeValidationError("dynamic subagent node missing required fields", {"fields": missing})
    if depends_on:
        missing_dependencies = [
            dependency.strip()
            for dependency in depends_on.split(",")
            if dependency.strip() and dependency.strip() not in nodes_by_id(root)
        ]
        if missing_dependencies:
            raise TreeValidationError("dynamic node has unresolved dependencies", {"dependencies": missing_dependencies})
    work_order_id = root.get("work_order_id", "work-order")
    sequence = 1
    while True:
        instance_id = f"dyn-{sequence}"
        runtime_id = (
            f"rt_{slug(work_order_id, 'work-order')}__"
            f"{instance_id}__{logical_key}"
        )
        if runtime_id not in nodes_by_id(root):
            break
        sequence += 1
    attrs = {
        "id": runtime_id,
        "logical_key": logical_key,
        "origin_instance_id": instance_id,
        "title": title,
        "type": canonical_type,
        "executor": executor,
        "status": "pending",
    }
    if normalized_role:
        attrs["role"] = normalized_role
    if normalized_role == "dynamic-group":
        attrs["dynamic.state"] = "open"
    if mode:
        attrs["mode"] = mode
    if when:
        attrs["when"] = when
    if depends_on:
        attrs["depends_on"] = depends_on
    for key, value in metadata or []:
        attrs[key] = value
    node = ET.Element("node", attrs)
    violations = validate_control_metadata_for_node(node)
    if violations:
        raise InvalidControlMetadataError(
            "control metadata declaration is invalid",
            {
                "violations": [
                    {"node": logical_key, **violation}
                    for violation in violations
                ]
            },
        )
    holder = find_direct(parent, "children")
    insertion_index: Optional[int] = None
    if before_id:
        direct_children = list(holder.findall("node")) if holder is not None else []
        for index, existing in enumerate(direct_children):
            if existing.get("id") == before_id:
                insertion_index = index
                break
        if insertion_index is None:
            raise TreeValidationError(
                "before node must be a direct child of the dynamic parent",
                {"parent_id": parent_id, "before_id": before_id},
            )
    if holder is None:
        holder = ET.SubElement(parent, "children")
    root.attrib.pop("reopen_pending", None)
    if insertion_index is None:
        holder.append(node)
    else:
        holder.insert(insertion_index, node)
    for tag, value in (
        ("instructions", instructions),
        ("inputs", inputs),
        ("deliverables", deliverables),
        ("acceptance", acceptance),
    ):
        if value:
            child = ET.SubElement(node, tag)
            child.text = value
    return node


def embed_template_subtree(
    root: ET.Element,
    parent_id: str,
    template_tree: ET.ElementTree,
    config: Dict[str, Any],
    instance_id: Optional[str] = None,
) -> ET.Element:
    require_valid_control_metadata(template_tree.getroot())
    validation_errors = validate_template_root(template_tree.getroot())
    if validation_errors:
        raise TreeValidationError("template validation failed", {"errors": validation_errors})
    parent = find_node(root, parent_id)
    if node_type(parent) not in {"composite", "loop"}:
        raise TreeValidationError("subtree parent must be composite or loop", {"parent_id": parent_id})
    require_dynamic_group_open(parent)
    holder = ensure_direct(parent, "children")
    meta = ensure_managed_metadata(root, "runtime", config)
    instances = ensure_direct(meta, "template_instances")
    sequence = len(instances.findall("instance")) + 1
    instance = instance_id or f"subtree-{sequence}"
    if not NODE_KEY_RE.match(instance):
        raise TreeValidationError("instance_id must be lowercase kebab-case", {"instance_id": instance})
    if any(item.get("id") == instance for item in instances.findall("instance")):
        raise TreeValidationError("instance_id already exists", {"instance_id": instance})
    mapping: Dict[str, str] = {}
    pending: List[Tuple[ET.Element, List[str]]] = []
    child_root = instantiate_template_node(
        root_node(template_tree.getroot()),
        root.get("work_order_id", "work-order"),
        instance,
        mapping,
        pending,
    )
    rewrite_template_references(mapping, pending)
    existing_ids = nodes_by_id(root)
    collisions = sorted(set(mapping.values()) & set(existing_ids))
    if collisions:
        raise TreeValidationError("embedded runtime IDs would collide", {"ids": collisions})
    holder.append(child_root)
    root.attrib.pop("reopen_pending", None)
    ET.SubElement(
        instances,
        "instance",
        {
            "id": instance,
            "template_name": template_tree.getroot().get("name", ""),
            "template_root_id": template_id(root_node(template_tree.getroot())),
        },
    )
    return child_root


def require_executable_leaf(root: ET.Element, node_id: str) -> ET.Element:
    node = find_node(root, node_id)
    if node_type(node) not in {"task", "gate"} or children(node):
        raise RuntimeErrorBase("operation requires an executable task or gate leaf", {"node_id": node_id})
    return node


def begin_node(root: ET.Element, node_id: str, agent: str = "") -> ET.Element:
    node = require_executable_leaf(root, node_id)
    blocker = node_readiness_blocker(root, node)
    if blocker is not None:
        raise NodeNotReadyError(
            "node is not ready",
            {
                "node_id": node_id,
                "status": node.get("status", "pending"),
                **blocker,
            },
        )
    node.set("status", "running")
    node.set("started_at", utc_now())
    if agent:
        node.set("agent", agent)
    stabilize(root)
    return node


def append_result_artifacts(result: ET.Element, artifacts: Optional[Sequence[str]] = None) -> None:
    if not artifacts:
        return
    holder = ensure_direct(result, "artifacts")
    for artifact in artifacts:
        ET.SubElement(holder, "artifact", {"path": artifact})


def append_result_checks(result: ET.Element, receipts: Sequence[Dict[str, Any]]) -> None:
    if not receipts:
        return
    holder = ET.SubElement(result, "checks")
    for receipt in receipts:
        check = ET.SubElement(holder, "check")
        check.text = json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))


def _load_receipt_json(raw: str) -> Any:
    def reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid number: {value}")),
    )


def parse_check_results(values: Optional[Sequence[str]]) -> List[Dict[str, Any]]:
    receipts: List[Dict[str, Any]] = []
    seen: set[str] = set()
    violations: List[Dict[str, Any]] = []
    expected_keys = {"schema_version", "check", "ok", "subject", "facts"}
    for index, raw in enumerate(values or []):
        if len(raw.encode("utf-8")) > CHECK_RESULT_MAX_BYTES:
            violations.append({"index": index, "code": "check_result_too_large"})
            continue
        try:
            parsed = _load_receipt_json(raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            violations.append({"index": index, "code": "malformed_check_result"})
            continue
        if not isinstance(parsed, dict) or set(parsed) != expected_keys:
            violations.append({"index": index, "code": "invalid_check_result_shape"})
            continue
        check = parsed.get("check")
        facts = parsed.get("facts")
        if (
            type(parsed.get("schema_version")) is not int
            or parsed["schema_version"] != 1
            or not isinstance(check, str)
            or not CHECK_NAME_RE.fullmatch(check)
            or type(parsed.get("ok")) is not bool
            or not isinstance(parsed.get("subject"), str)
            or not isinstance(facts, dict)
            or any(not isinstance(key, str) or not CHECK_FACT_RE.fullmatch(key) for key in facts)
            or any(isinstance(value, (dict, list)) for value in facts.values())
            or any(isinstance(value, float) and not math.isfinite(value) for value in facts.values())
        ):
            violations.append({"index": index, "code": "invalid_check_result_shape"})
            continue
        if check in seen:
            violations.append({"index": index, "check": check, "code": "duplicate_check_result"})
            continue
        seen.add(check)
        receipts.append(
            {
                "schema_version": 1,
                "check": check,
                "ok": parsed["ok"],
                "subject": parsed["subject"],
                "facts": {key: facts[key] for key in sorted(facts)},
            }
        )
    if violations:
        raise InvalidCheckResultError(
            "one or more check results are invalid",
            {"violations": violations},
        )
    return receipts


def _resolve_value_selector(root: ET.Element, selector: str) -> Tuple[bool, str]:
    if selector.startswith("literal:"):
        return True, selector[8:]
    key = selector[3:]
    values = blackboard(root)
    return (key in values, values.get(key, ""))


def _completion_metadata(node: ET.Element) -> Dict[str, str]:
    return {
        key: value
        for key, value in node.attrib.items()
        if key.startswith("metadata.completion.")
    }


def validate_completion_requirements(
    root: ET.Element,
    node: ET.Element,
    summary: str,
    artifacts: Sequence[str],
    validation: str,
    receipts: Sequence[Dict[str, Any]],
) -> None:
    metadata = _completion_metadata(node)
    if not metadata:
        if receipts:
            raise InvalidCheckResultError(
                "check results are not declared for this node",
                {"violations": [{"code": "check_result_not_declared"}]},
            )
        return
    violations: List[Dict[str, Any]] = []
    required_fields = _json_string_list(
        metadata.get("metadata.completion.required_fields", "[]")
    ) or []
    for field, value in (("summary", summary), ("validation", validation)):
        if field in required_fields and not value.strip():
            violations.append({"code": "required_field_missing", "field": field})

    minimum_key = "metadata.completion.artifacts.min"
    maximum_key = "metadata.completion.artifacts.max"
    if minimum_key in metadata:
        minimum = int(metadata[minimum_key])
        maximum = int(metadata[maximum_key])
        if not minimum <= len(artifacts) <= maximum:
            violations.append(
                {
                    "code": "artifact_cardinality_mismatch",
                    "minimum": minimum,
                    "maximum": maximum,
                    "actual": len(artifacts),
                }
            )
    path_selector = metadata.get("metadata.completion.artifacts.path")
    if path_selector:
        available, expected_path = _resolve_value_selector(root, path_selector)
        if not available:
            violations.append(
                {"code": "artifact_path_source_missing", "selector": path_selector}
            )
        else:
            for index, artifact in enumerate(artifacts):
                if artifact != expected_path:
                    violations.append(
                        {
                            "code": "artifact_path_mismatch",
                            "index": index,
                            "expected": expected_path,
                            "actual": artifact,
                        }
                    )

    declared_checks = _json_string_list(metadata.get("metadata.completion.checks", "[]")) or []
    receipt_by_check = {receipt["check"]: receipt for receipt in receipts}
    unexpected = sorted(set(receipt_by_check).difference(declared_checks))
    if unexpected:
        raise InvalidCheckResultError(
            "check results include undeclared checks",
            {"violations": [{"code": "unexpected_check", "check": check} for check in unexpected]},
        )
    for check in declared_checks:
        receipt = receipt_by_check.get(check)
        if receipt is None:
            violations.append({"code": "required_check_missing", "check": check})
            continue
        if not receipt["ok"]:
            violations.append({"code": "required_check_failed", "check": check})
        subject_selector = metadata[f"metadata.completion.check.{check}.subject"]
        available, expected_subject = _resolve_value_selector(root, subject_selector)
        if not available:
            violations.append(
                {
                    "code": "check_subject_source_missing",
                    "check": check,
                    "selector": subject_selector,
                }
            )
        elif receipt["subject"] != expected_subject:
            violations.append(
                {
                    "code": "check_subject_mismatch",
                    "check": check,
                    "expected": expected_subject,
                    "actual": receipt["subject"],
                }
            )
        fact_prefix = f"metadata.completion.check.{check}.facts."
        expected_fact_selectors = {
            key[len(fact_prefix) :]: value
            for key, value in metadata.items()
            if key.startswith(fact_prefix)
        }
        if set(receipt["facts"]) != set(expected_fact_selectors):
            violations.append(
                {
                    "code": "check_facts_shape_mismatch",
                    "check": check,
                    "expected": sorted(expected_fact_selectors),
                    "actual": sorted(receipt["facts"]),
                }
            )
            continue
        for fact, selector in sorted(expected_fact_selectors.items()):
            available, expected_value = _resolve_value_selector(root, selector)
            if not available:
                violations.append(
                    {
                        "code": "check_fact_source_missing",
                        "check": check,
                        "fact": fact,
                        "selector": selector,
                    }
                )
            elif receipt["facts"][fact] != expected_value:
                violations.append(
                    {
                        "code": "check_fact_mismatch",
                        "check": check,
                        "fact": fact,
                        "expected": expected_value,
                        "actual": receipt["facts"][fact],
                    }
                )
    if violations:
        raise CompletionRequirementsFailedError(
            "completion requirements are not satisfied",
            {"violations": violations},
        )


def validate_gate_completion(
    node: ET.Element,
    gate_outcome: str,
    decision: str,
    variables: Sequence[Tuple[str, str]],
) -> str:
    metadata = {
        key: value
        for key, value in node.attrib.items()
        if key.startswith("metadata.gate.")
    }
    if not metadata:
        if gate_outcome or decision:
            raise GateOutcomeNotAllowedError(
                "structured gate fields are not allowed for this node",
                {"node_id": node.get("id", "")},
            )
        return ""
    outcomes = _json_string_list(metadata["metadata.gate.outcomes"], nonempty=True) or []
    if not gate_outcome:
        raise GateOutcomeRequiredError(
            "gate outcome is required",
            {"node_id": node.get("id", ""), "allowed": outcomes},
        )
    if gate_outcome not in outcomes:
        raise InvalidGateOutcomeError(
            "gate outcome is not allowed",
            {"node_id": node.get("id", ""), "outcome": gate_outcome, "allowed": outcomes},
        )
    if metadata["metadata.gate.decision_required"] == "true" and not decision.strip():
        raise GateDecisionRequiredError(
            "gate decision is required",
            {"node_id": node.get("id", "")},
        )
    outcome_key = metadata.get("metadata.gate.outcome_key", "")
    if outcome_key and any(key == outcome_key for key, _ in variables):
        raise GateOutcomeConflictError(
            "gate outcome key conflicts with an explicit blackboard update",
            {"node_id": node.get("id", ""), "key": outcome_key},
        )
    return outcome_key


def complete_node(
    root: ET.Element,
    node_id: str,
    summary: str = "",
    artifacts: Optional[Sequence[str]] = None,
    validation: str = "",
    variables: Optional[Sequence[Tuple[str, str]]] = None,
    check_results: Optional[Sequence[str]] = None,
    gate_outcome: str = "",
    decision: str = "",
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "complete requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    require_valid_control_metadata(root)
    artifact_values = list(artifacts or [])
    variable_values = list(variables or [])
    receipts = parse_check_results(check_results)
    validate_completion_requirements(
        root,
        node,
        summary,
        artifact_values,
        validation,
        receipts,
    )
    outcome_key = validate_gate_completion(
        node,
        gate_outcome,
        decision,
        variable_values,
    )
    node.set("status", "succeeded")
    node.set("completed_at", utc_now())
    result = ensure_node_child(node, "result")
    if summary:
        ensure_node_child(result, "summary").text = summary
    append_result_artifacts(result, artifact_values)
    if validation:
        ensure_node_child(result, "validation").text = validation
    append_result_checks(result, receipts)
    if gate_outcome:
        ensure_node_child(result, "gate_outcome").text = gate_outcome
    if decision:
        ensure_node_child(result, "decision").text = decision
    for key, value in variable_values:
        set_blackboard(root, key, value, node_id)
    if outcome_key:
        set_blackboard(root, outcome_key, gate_outcome, node_id)
    stabilize(root)
    return node


def fail_node(
    root: ET.Element,
    node_id: str,
    reason: str,
    artifacts: Optional[Sequence[str]] = None,
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "fail requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    node.set("status", "failed")
    node.set("failed_at", utc_now())
    result = ensure_node_child(node, "result")
    ensure_node_child(result, "failure_reason").text = reason
    append_result_artifacts(result, artifacts)
    stabilize(root)
    return node


def retry_failed_node(root: ET.Element, node_id: str, reason: str) -> Tuple[ET.Element, ET.Element]:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise TreeValidationError("retry reason must not be empty", {"node_id": node_id})
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "failed":
        raise InvalidTransitionError(
            "retry-failed requires a failed executable leaf",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    result = find_direct(node, "result")
    if result is None or find_direct(result, "failure_reason") is None:
        raise TreeValidationError(
            "failed executable leaf is missing failure evidence",
            {"node_id": node_id},
        )

    number = attempt_number(node)
    attempts = ensure_node_child(node, "attempts")
    if any(item.get("number") == str(number) for item in attempts.findall("attempt")):
        raise TreeValidationError(
            "current attempt is already archived",
            {"node_id": node_id, "attempt": number},
        )
    retried_at = utc_now()
    attributes = {
        "number": str(number),
        "status": "failed",
        "started_at": node.get("started_at", ""),
        "failed_at": node.get("failed_at", ""),
        "retried_at": retried_at,
        "retry_reason": normalized_reason,
    }
    if node.get("agent"):
        attributes["agent"] = node.get("agent", "")
    archived = ET.SubElement(attempts, "attempt", attributes)
    archived.append(copy.deepcopy(result))
    node.remove(result)

    node.set("attempt", str(number + 1))
    node.set("status", "pending")
    for key in (
        "agent",
        "started_at",
        "completed_at",
        "failed_at",
        "blocked_at",
        "block_reason",
    ):
        node.attrib.pop(key, None)
    stabilize(root)
    return node, archived


def block_node(
    root: ET.Element,
    node_id: str,
    reason: str,
    artifacts: Optional[Sequence[str]] = None,
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "block requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    node.set("status", "blocked")
    node.set("blocked_at", utc_now())
    node.set("block_reason", reason)
    append_result_artifacts(ensure_node_child(node, "result"), artifacts)
    stabilize(root)
    return node


def unblock_node(root: ET.Element, node_id: str) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "blocked":
        raise RuntimeErrorBase("node is not blocked", {"node": node_id, "status": node.get("status")})
    node.set("status", "pending")
    for key in ("blocked_at", "block_reason"):
        node.attrib.pop(key, None)
    stabilize(root)
    return node
