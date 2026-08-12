#!/usr/bin/env python3
"""Export canonical subagent definitions to supported Agent tool formats."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "agents"
CLAUDE_DIR = ROOT / "claude-agents"
OPENCODE_DIR = ROOT / "opencode-agents"
CODEX_DIR = ROOT / "codex-agents"
TRAE_DIR = ROOT / "trae-agents"


@dataclass
class AgentDefinition:
    name: str
    description: str
    body: str
    claude_tools: str | None
    claude_model: str | None
    claude_color: str | None
    opencode_color: str | None
    opencode_permissions: list[tuple[str, str]]
    codex_model: str | None
    codex_sandbox_mode: str | None


def split_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError(f"{path}: frontmatter is not closed")
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :]).strip() + "\n"
    return metadata, body


def parse_permissions(raw: str | None) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        name, value = (item.split("=", 1) if "=" in item else (item, "allow"))
        name = name.strip()
        value = value.strip()
        if value not in {"allow", "deny"}:
            raise ValueError(f"invalid OpenCode permission value for {name}: {value}")
        result.append((name, value))
    return result


def parse_agent(path: Path) -> AgentDefinition:
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8-sig"), path)
    for required in ("name", "description"):
        if not metadata.get(required):
            raise ValueError(f"{path}: missing {required}")
    return AgentDefinition(
        name=metadata["name"],
        description=metadata["description"],
        body=body,
        claude_tools=metadata.get("claude_tools"),
        claude_model=metadata.get("claude_model"),
        claude_color=metadata.get("claude_color"),
        opencode_color=metadata.get("opencode_color"),
        opencode_permissions=parse_permissions(metadata.get("opencode_permissions")),
        codex_model=metadata.get("codex_model"),
        codex_sandbox_mode=metadata.get("codex_sandbox_mode"),
    )


def quote_if_needed(value: str) -> str:
    return f'"{value}"' if value.startswith("#") else value


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def toml_multiline(value: str) -> str:
    if '"""' not in value:
        return '"""\n' + value.rstrip() + '\n"""'
    return '"' + toml_escape(value) + '"'


def render_claude(agent: AgentDefinition) -> str:
    lines = ["---", f"name: {agent.name}", f"description: {agent.description}"]
    if agent.claude_tools:
        lines.append(f"tools: {agent.claude_tools}")
    if agent.claude_model:
        lines.append(f"model: {agent.claude_model}")
    if agent.claude_color:
        lines.append(f"color: {agent.claude_color}")
    return "\n".join([*lines, "---", "", agent.body.rstrip(), ""])


def render_opencode(agent: AgentDefinition) -> str:
    lines = ["---", f"description: {agent.description}", "mode: subagent"]
    if agent.opencode_color:
        lines.append(f"color: {quote_if_needed(agent.opencode_color)}")
    if agent.opencode_permissions:
        lines.append("permission:")
        lines.extend(f"  {name}: {value}" for name, value in agent.opencode_permissions)
    return "\n".join([*lines, "---", "", agent.body.rstrip(), ""])


def render_codex(agent: AgentDefinition) -> str:
    lines = [f'name = "{toml_escape(agent.name)}"', f'description = "{toml_escape(agent.description)}"']
    if agent.codex_model:
        lines.append(f'model = "{toml_escape(agent.codex_model)}"')
    if agent.codex_sandbox_mode:
        lines.append(f'sandbox_mode = "{toml_escape(agent.codex_sandbox_mode)}"')
    lines.append(f"developer_instructions = {toml_multiline(agent.body)}")
    return "\n".join([*lines, ""])


def render_trae(agent: AgentDefinition) -> str:
    lines = [
        "---",
        f"name: {agent.name}",
        f"description: {agent.description}",
        "---",
        "",
        agent.body.rstrip(),
        "",
    ]
    return "\n".join(lines)


def write_output(path: Path, content: str, check: bool) -> bool:
    if check:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        return current != content
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return False


def export_agents(check: bool) -> int:
    if not SOURCE_DIR.is_dir():
        print(f"ERROR: source directory not found: {SOURCE_DIR}", file=sys.stderr)
        return 1
    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        print(f"ERROR: no canonical agents under {SOURCE_DIR}", file=sys.stderr)
        return 1
    output_directories = (CLAUDE_DIR, OPENCODE_DIR, CODEX_DIR, TRAE_DIR)
    if not check:
        for directory in output_directories:
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)

    stale: list[str] = []
    expected: set[Path] = set()
    for source in sources:
        agent = parse_agent(source)
        outputs = {
            CLAUDE_DIR / source.name: render_claude(agent),
            OPENCODE_DIR / source.name: render_opencode(agent),
            CODEX_DIR / f"{source.stem}.toml": render_codex(agent),
            TRAE_DIR / source.name: render_trae(agent),
        }
        expected.update(outputs)
        for path, content in outputs.items():
            if write_output(path, content, check):
                stale.append(path.relative_to(ROOT).as_posix())
    if check:
        actual = {
            path
            for directory in output_directories
            if directory.is_dir()
            for path in directory.rglob("*")
            if path.is_file()
        }
        stale.extend(
            path.relative_to(ROOT).as_posix()
            for path in sorted(actual - expected)
        )
    if stale:
        print("Generated agents are out of date:", file=sys.stderr)
        print("\n".join(f"  {path}" for path in stale), file=sys.stderr)
        return 1
    print(f"exported {len(sources)} agents")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export canonical agent definitions to Claude Code, OpenCode, "
            "Codex, and Trae."
        )
    )
    parser.add_argument("--check", action="store_true")
    return export_agents(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
