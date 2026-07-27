#!/usr/bin/env python3
"""Validate managed XC workflow Markdown documents."""

from __future__ import annotations

import argparse
import json
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
    "run-goal",
    "run-analysis",
    "run-solution",
    "run-result",
    "node-artifact",
}
FEATURE_KINDS = {"feature-contract", "feature-solution", "feature-verification"}
RUN_KINDS = {"run-goal", "run-analysis", "run-solution", "run-result"}


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
    for key in ("run_id", "tree_ref", "node_id"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append(f"{field}.{key} must be a non-empty string")


def validate_document(metadata: dict[str, Any], expected_kind: str = "") -> list[str]:
    errors: list[str] = []
    if metadata.get("schema_version") != 1:
        errors.append("schema_version must be integer 1")
    kind = metadata.get("document_kind")
    if kind not in DOCUMENT_KINDS:
        errors.append(f"document_kind must be one of: {', '.join(sorted(DOCUMENT_KINDS))}")
        return errors
    if expected_kind and kind != expected_kind:
        errors.append(f"document_kind must be {expected_kind}")
    if any(field in metadata for field in ("status", "current_node", "task_progress", "loop_state", "blocker")):
        errors.append("frontmatter must not duplicate dynamic orchestration state")

    orchestration = metadata.get("orchestration")
    if not isinstance(orchestration, dict):
        errors.append("orchestration must be an object")
        return errors

    if kind in FEATURE_KINDS:
        require_string(metadata, "feature_id", errors)
        validate_provenance_entry(orchestration.get("initialized_by"), "orchestration.initialized_by", errors)
        validate_provenance_entry(orchestration.get("last_updated_by"), "orchestration.last_updated_by", errors)
    elif kind in RUN_KINDS:
        require_string(metadata, "run_id", errors)
        require_feature_ids(metadata, errors)
        require_string(orchestration, "main_tree_ref", errors)
    elif kind == "node-artifact":
        require_string(metadata, "run_id", errors)
        require_string(metadata, "node_id", errors)
        require_feature_ids(metadata, errors)
        require_string(orchestration, "tree_ref", errors)
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
    payload = {
        "ok": not errors,
        "path": str(path),
        "document_kind": metadata.get("document_kind", ""),
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
