#!/usr/bin/env python3
"""Render a managed Markdown template with explicit placeholder values."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from frontmatter_yaml import FrontmatterYamlError, dumps, loads


PLACEHOLDER = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")


def parse_assignment(value: str, option: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"{option} expects name=value")
    name, replacement = value.split("=", 1)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError(f"invalid placeholder name: {name}")
    return name, replacement


def parse_values(values: list[str], json_values: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        name, replacement = parse_assignment(value, "--set")
        if name in result:
            raise ValueError(f"duplicate placeholder value: {name}")
        result[name] = replacement
    for value in json_values:
        name, replacement = parse_assignment(value, "--set-json")
        if name in result:
            raise ValueError(f"duplicate placeholder value: {name}")
        try:
            result[name] = json.loads(replacement)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--set-json value for {name} is not valid JSON: {exc.msg}") from exc
    return result


def text_replacement(match: re.Match[str], values: dict[str, Any]) -> str:
    replacement = values[match.group(1)]
    if not isinstance(replacement, str):
        raise ValueError(f"placeholder {match.group(1)} is used in Markdown body and must be a string")
    return replacement


def frontmatter_bounds(content: str) -> tuple[int, int] | None:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return None
    closing_index = next((index for index, line in enumerate(lines[1:], start=1) if line == "---"), None)
    if closing_index is None:
        raise ValueError("frontmatter is not closed")
    return 0, closing_index


def replace_placeholders(value: object, values: dict[str, Any]) -> object:
    if isinstance(value, str):
        whole_placeholder = PLACEHOLDER.fullmatch(value)
        if whole_placeholder:
            return values[whole_placeholder.group(1)]
        return PLACEHOLDER.sub(lambda match: text_replacement(match, values), value)
    if isinstance(value, list):
        return [replace_placeholders(item, values) for item in value]
    if isinstance(value, dict):
        return {key: replace_placeholders(item, values) for key, item in value.items()}
    return value


def render(template: Path, output: Path, values: dict[str, Any]) -> dict[str, object]:
    if not template.is_file():
        raise ValueError(f"template does not exist: {template}")
    content = template.read_text(encoding="utf-8-sig")
    unresolved = sorted(set(PLACEHOLDER.findall(content)).difference(values))
    if unresolved:
        raise ValueError(f"unresolved placeholders: {', '.join(unresolved)}")
    bounds = frontmatter_bounds(content)
    if bounds is None:
        rendered = PLACEHOLDER.sub(lambda match: text_replacement(match, values), content)
    else:
        lines = content.splitlines()
        _, closing_index = bounds
        try:
            frontmatter = loads("\n".join(lines[1:closing_index]))
        except FrontmatterYamlError as exc:
            raise ValueError(f"invalid YAML frontmatter template: {exc}") from exc
        if not isinstance(frontmatter, dict):
            raise ValueError("frontmatter template must be a YAML object")
        rendered_frontmatter = dumps(replace_placeholders(frontmatter, values)).rstrip()
        rendered_body = PLACEHOLDER.sub(lambda match: text_replacement(match, values), "\n".join(lines[closing_index + 1 :]))
        rendered = f"---\n{rendered_frontmatter}\n---\n{rendered_body}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    return {"ok": True, "template": str(template), "document": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an XC managed document template.")
    parser.add_argument("--template", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--set", action="append", default=[])
    parser.add_argument("--set-json", action="append", default=[])
    args = parser.parse_args()
    try:
        payload = render(Path(args.template), Path(args.out), parse_values(args.set, args.set_json))
    except ValueError as exc:
        payload = {"ok": False, "error": {"code": "document_render_error", "message": str(exc)}}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
