#!/usr/bin/env python3
"""Build managed orchestration templates from JSON flow specifications."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

RUNTIME_SCRIPTS = Path(__file__).resolve().parents[2] / "xc-orchestration-runtime" / "scripts"
if str(RUNTIME_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SCRIPTS))

import runtime_core as core


NODE_ATTRIBUTE_KEYS = {
    "template_id",
    "title",
    "type",
    "role",
    "executor",
    "mode",
    "depends_on_template",
    "when",
    "loop.max_iterations",
    "loop.continue_when",
    "loop.break_when",
    "loop.on_limit",
    "switch.key",
    "switch.no_match",
    "case.value",
    "case.default",
}
NODE_TEXT_KEYS = ("instructions", "inputs", "deliverables", "acceptance")
NODE_ALLOWED_KEYS = NODE_ATTRIBUTE_KEYS | set(NODE_TEXT_KEYS) | {"children", "metadata"}


def json_print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise core.RuntimeErrorBase("flow spec not found", {"path": str(path)})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise core.RuntimeErrorBase("invalid flow spec JSON", {"path": str(path), "error": str(exc)}) from exc
    if not isinstance(data, dict):
        raise core.RuntimeErrorBase("flow spec root must be an object", {"path": str(path)})
    return data


def flatten_metadata(value: Dict[str, Any], prefix: str = "metadata") -> Dict[str, str]:
    flattened: Dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise core.TreeValidationError("metadata keys must be non-empty strings")
        qualified = f"{prefix}.{key}"
        if isinstance(item, dict):
            flattened.update(flatten_metadata(item, qualified))
        elif item is None:
            continue
        elif isinstance(item, (str, int, float, bool)):
            flattened[qualified] = str(item).lower() if isinstance(item, bool) else str(item)
        else:
            raise core.TreeValidationError("metadata values must be scalar or object", {"key": qualified})
    return flattened


def spec_template() -> Dict[str, Any]:
    return {
        "name": "example-workflow",
        "schema_version": 1,
        "blackboard": {
            "scope.confirmed": "false",
            "review.open_issues": "false",
        },
        "root": {
            "template_id": "root",
            "title": "Example Workflow",
            "type": "composite",
            "role": "root",
            "mode": "sequence",
            "executor": "main",
            "children": [
                {
                    "template_id": "investigation",
                    "title": "Investigate context",
                    "type": "task",
                    "role": "research",
                    "executor": "subagent",
                    "instructions": "Inspect the current project context and write a concise report.",
                    "deliverables": "artifacts/investigation/analysis.md",
                    "acceptance": "Report exists, cites source files, and distinguishes facts from assumptions.",
                },
                {
                    "template_id": "scope-gate",
                    "title": "Confirm scope",
                    "type": "gate",
                    "role": "scope-confirmation",
                    "executor": "main",
                    "instructions": "Ask the user to confirm the scope after investigation.",
                    "deliverables": "Set scope.confirmed=true in the blackboard.",
                    "acceptance": "User has confirmed scope or supplied corrections.",
                },
                {
                    "template_id": "review-loop",
                    "title": "Review and rework",
                    "type": "loop",
                    "role": "quality-loop",
                    "mode": "sequence",
                    "executor": "main",
                    "loop.max_iterations": "3",
                    "loop.continue_when": "review.open_issues == true",
                    "loop.break_when": "review.open_issues == false",
                    "loop.on_limit": "blocked",
                    "children": [
                        {
                            "template_id": "review",
                            "title": "Review output",
                            "type": "task",
                            "role": "review",
                            "executor": "subagent",
                            "instructions": "Review current artifacts and set review.open_issues true or false.",
                            "deliverables": "artifacts/review-loop/review-{iteration}.md",
                            "acceptance": "Review findings are prioritized and include closure criteria.",
                        },
                        {
                            "template_id": "rework",
                            "title": "Rework output",
                            "type": "task",
                            "role": "rework",
                            "executor": "subagent",
                            "when": "review.open_issues == true",
                            "depends_on_template": "local:review",
                            "instructions": "Address the current review findings.",
                            "deliverables": "artifacts/review-loop/rework-{iteration}.md",
                            "acceptance": "Required findings are fixed or explicitly deferred.",
                        },
                    ],
                },
            ],
        },
    }


def node_to_xml(spec: Dict[str, Any]) -> ET.Element:
    unknown = sorted(set(spec) - NODE_ALLOWED_KEYS)
    if unknown:
        raise core.TreeValidationError("flow spec node has unknown fields", {"fields": unknown})
    attrs: Dict[str, str] = {}
    for key in sorted(NODE_ATTRIBUTE_KEYS):
        value = spec.get(key)
        if value not in (None, ""):
            attrs[key] = str(value)
    metadata = spec.get("metadata", {})
    if metadata not in ({}, None):
        if not isinstance(metadata, dict):
            raise core.TreeValidationError("node metadata must be an object")
        attrs.update(flatten_metadata(metadata))
    node = ET.Element("node", attrs)
    for key in NODE_TEXT_KEYS:
        value = spec.get(key)
        if value not in (None, ""):
            child = ET.SubElement(node, key)
            child.text = str(value)
    children = spec.get("children", [])
    if children not in (None, []):
        if not isinstance(children, list):
            raise core.TreeValidationError("node children must be an array", {"template_id": attrs.get("template_id", "")})
        holder = ET.SubElement(node, "children")
        for child_spec in children:
            if not isinstance(child_spec, dict):
                raise core.TreeValidationError("node child must be an object", {"template_id": attrs.get("template_id", "")})
            holder.append(node_to_xml(child_spec))
    return node


def build_template(spec: Dict[str, Any]) -> ET.Element:
    unknown = sorted(set(spec) - {"name", "schema_version", "blackboard", "root"})
    if unknown:
        raise core.TreeValidationError("flow spec has unknown top-level fields", {"fields": unknown})
    root_spec = spec.get("root")
    if not isinstance(root_spec, dict):
        raise core.TreeValidationError("flow spec must contain an object root")
    blackboard = spec.get("blackboard", {})
    if not isinstance(blackboard, dict):
        raise core.TreeValidationError("flow spec blackboard must be an object")
    root = ET.Element(
        "orchestration",
        {
            "schema_version": str(spec.get("schema_version", "1")),
            "name": str(spec.get("name", "")),
        },
    )
    blackboard_element = ET.SubElement(root, "blackboard")
    for key, value in blackboard.items():
        if not isinstance(key, str) or not key:
            raise core.TreeValidationError("blackboard keys must be non-empty strings")
        variable = ET.SubElement(blackboard_element, "var", {"key": key})
        variable.text = "" if value is None else str(value)
    root.append(node_to_xml(root_spec))
    return root


def validate_spec_data(spec: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not spec.get("name"):
        errors.append("missing spec.name")
    try:
        root = build_template(spec)
    except core.RuntimeErrorBase as exc:
        return errors + [str(exc)]
    errors.extend(core.validate_template_root(root, check_integrity=False))
    return errors


def persist_template(root: ET.Element, out: Path, config_path: str, operation: str) -> Dict[str, Any]:
    config = core.load_config(out, Path(config_path) if config_path else None)
    errors = core.validate_template_root(root, check_integrity=False)
    if errors:
        raise core.TreeValidationError("template validation failed", {"errors": errors})
    persisted = core.write_managed_tree(ET.ElementTree(root), out, "template", config, operation)
    return {
        "status": persisted["status"],
        "path": str(out),
        "checksum": persisted["checksum"],
        "integrity": persisted["integrity"],
        "commit": persisted["commit"],
    }


def cmd_new_spec(args: argparse.Namespace) -> Dict[str, Any]:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec_template(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "created", "path": str(out)}


def cmd_build(args: argparse.Namespace) -> Dict[str, Any]:
    spec = load_json(Path(args.spec))
    errors = validate_spec_data(spec)
    if errors:
        raise core.TreeValidationError("flow spec validation failed", {"errors": errors})
    return persist_template(build_template(spec), Path(args.out), args.config, "build-template")


def cmd_validate_spec(args: argparse.Namespace) -> Dict[str, Any]:
    errors = validate_spec_data(load_json(Path(args.spec)))
    return {"valid": not errors, "errors": errors, "path": args.spec}


def cmd_validate_template(args: argparse.Namespace) -> Dict[str, Any]:
    template = core.parse_xml(Path(args.template))
    errors = core.validate_template_root(template.getroot())
    return {"valid": not errors, "errors": errors, "path": args.template}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build managed orchestration templates from JSON flow specs.")
    sub = parser.add_subparsers(dest="command", required=True)

    new_spec = sub.add_parser("new-spec", help="Create a new-format flow spec skeleton.")
    new_spec.add_argument("--out", required=True)
    new_spec.set_defaults(func=cmd_new_spec)

    build = sub.add_parser("build", help="Build and persist a managed orchestration template.")
    build.add_argument("--spec", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--config", default="")
    build.set_defaults(func=cmd_build)

    validate_spec = sub.add_parser("validate-spec", help="Validate a JSON flow spec before building.")
    validate_spec.add_argument("--spec", required=True)
    validate_spec.set_defaults(func=cmd_validate_spec)

    validate_template = sub.add_parser("validate-template", help="Validate a managed template.")
    validate_template.add_argument("--template", required=True)
    validate_template.set_defaults(func=cmd_validate_template)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.func(args)
    except core.RuntimeErrorBase as exc:
        json_print({"ok": False, "error": {"code": exc.code, "message": str(exc), "details": exc.details}})
        return 2
    json_print({"ok": True, **payload})
    return 1 if payload.get("valid") is False else 0


if __name__ == "__main__":
    sys.exit(main())
