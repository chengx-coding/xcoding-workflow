#!/usr/bin/env python3
"""Validate managed XC workflow Markdown documents."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


DOCUMENT_KINDS = {
    "project-workflow",
    "project-knowledge",
    "feature-contract",
    "feature-solution",
    "feature-verification",
    "work-order-goal",
    "work-order-analysis",
    "work-order-solution",
    "work-order-result",
    "node-artifact",
}
FEATURE_KINDS = {"feature-contract", "feature-solution", "feature-verification"}
WORK_ORDER_KINDS = {
    "work-order-goal",
    "work-order-analysis",
    "work-order-solution",
    "work-order-result",
}
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
NODE_ARTIFACT_AUDIENCES = {"internal", "user"}
PREVIOUS_MANAGED_IDENTITY = "run_" + "id"


def parse_document(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return {}, "", [f"document does not exist: {path}"]
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text, ["missing YAML frontmatter opening delimiter"]
    closing_index = next((index for index, line in enumerate(lines[1:], start=1) if line == "---"), None)
    if closing_index is None:
        return {}, text, ["missing YAML frontmatter closing delimiter"]
    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError as exc:
        return {}, text, [f"invalid YAML frontmatter: {exc}"]
    if not isinstance(metadata, dict):
        return {}, text, ["frontmatter must be a YAML object"]
    body = "\n".join(lines[closing_index + 1 :]).strip()
    if not body:
        errors.append("document body must not be empty")
    return metadata, body, errors


def require_string(metadata: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(metadata.get(field), str) or not metadata[field].strip():
        errors.append(f"{field} must be a non-empty string")


def require_feature_ids(metadata: dict[str, Any], errors: list[str]) -> None:
    feature_ids = metadata.get("feature_ids")
    if not isinstance(feature_ids, list) or any(not isinstance(item, str) or not item.strip() for item in feature_ids):
        errors.append("feature_ids must be a list of non-empty strings")


def validate_provenance_entry(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    if PREVIOUS_MANAGED_IDENTITY in value:
        errors.append(
            f"{field} contains unsupported managed identity field: "
            f"{PREVIOUS_MANAGED_IDENTITY}"
        )
    for key in ("work_order_id", "tree_ref", "node_id"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append(f"{field}.{key} must be a non-empty string")


def effective_content_language(metadata: dict[str, Any]) -> str:
    value = metadata.get("content_language")
    return value.strip() if isinstance(value, str) and value.strip() else "en"


def effective_audience(metadata: dict[str, Any]) -> str:
    value = metadata.get("audience")
    return value.strip() if isinstance(value, str) and value.strip() else "internal"


def validate_content_language(metadata: dict[str, Any], errors: list[str]) -> str:
    if "content_language" not in metadata:
        return "en"
    value = metadata.get("content_language")
    if not isinstance(value, str) or not LANGUAGE_TAG.fullmatch(value.strip()):
        errors.append("content_language must be a valid simplified BCP 47 language tag")
        return ""
    return value.strip()


def validate_node_artifact_language(metadata: dict[str, Any], content_language: str, errors: list[str]) -> None:
    if "audience" in metadata and not isinstance(metadata.get("audience"), str):
        errors.append("audience must be internal or user")
        return
    audience = effective_audience(metadata)
    if audience not in NODE_ARTIFACT_AUDIENCES:
        errors.append("audience must be internal or user")
        return
    if audience == "user" and "content_language" not in metadata:
        errors.append("user node-artifact documents must explicitly set content_language")
    if audience == "internal" and content_language and content_language.lower() != "en":
        errors.append("internal node-artifact documents must use content_language en")


def validate_document(metadata: dict[str, Any], expected_kind: str = "") -> list[str]:
    errors: list[str] = []
    if metadata.get("schema_version") != 1:
        errors.append("schema_version must be integer 1")
    if PREVIOUS_MANAGED_IDENTITY in metadata:
        errors.append(
            "frontmatter contains unsupported managed identity field: "
            f"{PREVIOUS_MANAGED_IDENTITY}"
        )
    kind = metadata.get("document_kind")
    if kind not in DOCUMENT_KINDS:
        errors.append(f"document_kind must be one of: {', '.join(sorted(DOCUMENT_KINDS))}")
        return errors
    if expected_kind and kind != expected_kind:
        errors.append(f"document_kind must be {expected_kind}")
    if any(field in metadata for field in ("status", "current_node", "task_progress", "loop_state", "blocker")):
        errors.append("frontmatter must not duplicate dynamic orchestration state")
    content_language = validate_content_language(metadata, errors)
    if kind != "node-artifact" and "audience" in metadata:
        errors.append("audience is only allowed for node-artifact documents")

    orchestration = metadata.get("orchestration")
    if not isinstance(orchestration, dict):
        errors.append("orchestration must be an object")
        return errors

    if kind in FEATURE_KINDS:
        require_string(metadata, "feature_id", errors)
        validate_provenance_entry(orchestration.get("initialized_by"), "orchestration.initialized_by", errors)
        validate_provenance_entry(orchestration.get("last_updated_by"), "orchestration.last_updated_by", errors)
    elif kind in WORK_ORDER_KINDS:
        require_string(metadata, "work_order_id", errors)
        require_feature_ids(metadata, errors)
        require_string(orchestration, "main_tree_ref", errors)
    elif kind == "node-artifact":
        require_string(metadata, "work_order_id", errors)
        require_string(metadata, "node_id", errors)
        require_feature_ids(metadata, errors)
        require_string(orchestration, "tree_ref", errors)
        validate_node_artifact_language(metadata, content_language, errors)
    else:
        validate_provenance_entry(orchestration.get("initialized_by"), "orchestration.initialized_by", errors)
        validate_provenance_entry(orchestration.get("last_updated_by"), "orchestration.last_updated_by", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate managed XC workflow Markdown documents.")
    parser.add_argument("--document", required=True)
    parser.add_argument("--expected-kind", default="")
    args = parser.parse_args()
    path = Path(args.document)
    metadata, _, errors = parse_document(path)
    errors.extend(validate_document(metadata, args.expected_kind) if not errors else [])
    normalized_path = str(path.resolve())
    document_kind = metadata.get("document_kind", "")
    content_language = effective_content_language(metadata)
    audience = effective_audience(metadata) if document_kind == "node-artifact" else ""
    receipt = {
        "schema_version": 1,
        "check": "xc-document",
        "ok": not errors,
        "subject": normalized_path,
        "facts": {
            "document_kind": document_kind,
            "content_language": content_language,
            "audience": audience,
        },
    }
    payload = {
        "ok": not errors,
        "path": normalized_path,
        "document_kind": document_kind,
        "content_language": content_language,
        "audience": audience,
        "errors": errors,
        "receipt": receipt,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
