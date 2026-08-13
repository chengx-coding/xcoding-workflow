#!/usr/bin/env python3
"""Read-only resume brief generator for managed runtime trees.

A resume brief is a derived cross-session handoff view of one or more
managed runtime trees. It gathers state exclusively through the public
runtime CLI's read-only commands (``snapshot`` and ``artifacts``); no
mutation command is invoked, and no managed tree file is opened directly.

Per included tree the brief reports:

- work_order_id, tree status, revision, and integrity status
- status counts, running nodes, blocked nodes (id + reason)
- awaiting dynamic groups and the top ready leaves
- the top recent terminal results (node id + status + summary snippet)
- declared artifacts from the runtime artifacts command
- a decision-registry path pointer when the workbench holds a registry
  file (a top-level ``*.jsonl`` whose first line carries decision-registry
  keys), otherwise null
- bounded next actions derived from blockers and ready leaves

Unreadable, non-runtime, or sealed trees are skipped with a stable
per-tree skip reason. Output is one deterministic compact JSON object
with sorted keys and bounded lists. Invalid input exits 0 with an
``ok:false`` payload (stable contract); internal failures exit 1.

CLI resolution order: the ``XC_RUNTIME_CLI`` environment variable (shlex
argv), then an ``xcoding`` executable on PATH, then ``python -m xcoding``.
Every candidate is an argv prefix that already includes the runtime
subcommand (for example ``xcoding runtime`` or a tool-specific runtime
runner); the generator appends only read-only commands.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCHEMA_VERSION = 1
SNAPSHOT_TIMEOUT_SECONDS = 60
CLI_ENV_VAR = "XC_RUNTIME_CLI"
READY_LIMIT = 10
TERMINAL_LIMIT = 10
NEXT_ACTIONS_MAX = 6
BLOCKED_ACTIONS_MAX = 3
SUMMARY_SNIPPET_MAX = 160
REASON_SNIPPET_MAX = 80
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "blocked", "skipped"})
REGISTRY_KEYS = frozenset({"id", "decision", "actor", "timestamp"})


class ResumeBriefInputError(ValueError):
    """Stable invalid-input result returned by the generator."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def emit(payload: dict[str, object]) -> None:
    print(compact_json(payload))


def invalid_payload(code: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "error": {"code": code},
    }


def candidate_prefixes() -> list[list[str]]:
    """Resolve runtime CLI argv prefixes (including the runtime subcommand)."""
    candidates: list[list[str]] = []
    env_value = os.environ.get(CLI_ENV_VAR, "").strip()
    if env_value:
        try:
            parsed = shlex.split(env_value)
        except ValueError:
            parsed = []
        if parsed:
            candidates.append(parsed)
    executable = shutil.which("xcoding")
    if executable:
        candidates.append([executable, "runtime"])
    candidates.append([sys.executable, "-m", "xcoding", "runtime"])
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def parse_trees(values: Sequence[str]) -> list[str]:
    """Parse repeatable --tree values: paths or JSON lists of paths."""
    if not values:
        raise ResumeBriefInputError("resume_brief_input_missing")
    paths: list[str] = []
    for value in values:
        if not value.strip():
            raise ResumeBriefInputError("resume_brief_input_invalid")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            paths.append(value)
            continue
        if parsed is None:
            raise ResumeBriefInputError("resume_brief_input_invalid")
        if isinstance(parsed, str):
            if not parsed.strip():
                raise ResumeBriefInputError("resume_brief_input_invalid")
            paths.append(parsed)
            continue
        if isinstance(parsed, list):
            if not parsed:
                raise ResumeBriefInputError("resume_brief_input_empty")
            if any(not isinstance(item, str) or not item.strip() for item in parsed):
                raise ResumeBriefInputError("resume_brief_input_invalid")
            paths.extend(parsed)
            continue
        raise ResumeBriefInputError("resume_brief_input_invalid")
    normalized: list[str] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normpath(path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return sorted(normalized)


def parse_object(output: str) -> dict[str, object] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_error_code(stdout: str) -> str:
    payload = parse_object(stdout)
    error = payload.get("error") if payload is not None else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) and code else "runtime_command_failed"


def decode_output(data: bytes) -> str:
    """Decode runtime CLI stdout: prefer UTF-8, fall back to legacy console codes."""
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return env


def run_read_command(
    prefix: list[str],
    command: str,
    tree_path: str,
) -> tuple[str, dict[str, object] | None]:
    """Run one read-only runtime command; return ("" | skip_reason, payload)."""
    argv = [*prefix, command, "--tree", tree_path]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            env=child_env(),
            check=False,
            timeout=SNAPSHOT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return "runtime_timeout", None
    except OSError:
        return "runtime_cli_unavailable", None
    payload = parse_object(decode_output(completed.stdout))
    if completed.returncode != 0:
        if payload is not None and payload.get("ok") is False:
            return "tree_unreadable", {
                "error": {"code": extract_error_code(decode_output(completed.stdout))}
            }
        return "runtime_malformed", None
    if payload is None or payload.get("ok") is not True:
        return "runtime_malformed", None
    return "", payload


def walk_nodes(root: dict[str, object]) -> list[dict[str, object]]:
    """Flatten the recursive node snapshot deterministically."""
    found: list[dict[str, object]] = []
    stack: list[dict[str, object]] = [root]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        found.append(current)
        children = current.get("children")
        if isinstance(children, list):
            stack.extend(reversed([child for child in children if isinstance(child, dict)]))
    return found


def snippet(text: str, limit: int) -> str:
    normalized = " ".join(str(text).split())
    return normalized if len(normalized) <= limit else normalized[:limit]


def attributes_of(node: dict[str, object]) -> dict[str, object]:
    attributes = node.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def terminal_timestamp(node: dict[str, object]) -> str:
    attributes = attributes_of(node)
    for key in ("completed_at", "failed_at", "blocked_at"):
        value = attributes.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def recent_terminal_results(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates: list[tuple[str, int, str, str, str]] = []
    for index, node in enumerate(nodes):
        status = str(node.get("status", ""))
        if status not in TERMINAL_STATUSES:
            continue
        result = node.get("result")
        result = result if isinstance(result, dict) else {}
        summary = result.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            continue
        candidates.append((terminal_timestamp(node), index, str(node.get("id", "")), status, summary))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        {"node_id": node_id, "status": status, "summary": snippet(summary, SUMMARY_SNIPPET_MAX)}
        for _, _, node_id, status, summary in candidates[:TERMINAL_LIMIT]
    ]


def normalize_artifacts(payload: dict[str, object]) -> list[dict[str, object]]:
    items = payload.get("artifacts")
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str):
            continue
        entry: dict[str, object] = {"path": path, "node_id": item.get("node_id", "")}
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and metadata:
            entry["metadata"] = dict(sorted(metadata.items()))
        normalized.append(dict(sorted(entry.items())))
    normalized.sort(key=lambda entry: (str(entry["path"]), str(entry["node_id"])))
    return normalized


def normalize_groups(payload: dict[str, object]) -> list[dict[str, object]]:
    groups = payload.get("awaiting_dynamic_groups")
    if not isinstance(groups, list):
        return []
    return [dict(sorted(item.items())) for item in groups if isinstance(item, dict)]


def ready_leaves(payload: dict[str, object]) -> list[dict[str, object]]:
    ready = payload.get("ready")
    if not isinstance(ready, list):
        return []
    leaves: list[dict[str, object]] = []
    for item in ready[:READY_LIMIT]:
        if not isinstance(item, dict):
            continue
        node_id = item.get("id")
        if not isinstance(node_id, str):
            continue
        leaves.append({"id": node_id, "title": item.get("title", "")})
    return leaves


def blocked_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for node in nodes:
        if str(node.get("status", "")) != "blocked":
            continue
        found.append(
            {
                "id": str(node.get("id", "")),
                "title": str(node.get("title", "")),
                "reason": str(attributes_of(node).get("block_reason", "")),
            }
        )
    found.sort(key=lambda entry: str(entry["id"]))
    return found


def running_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for node in nodes:
        if str(node.get("status", "")) != "running":
            continue
        found.append(
            {
                "id": str(node.get("id", "")),
                "title": str(node.get("title", "")),
                "role": str(node.get("role", "")),
            }
        )
    found.sort(key=lambda entry: str(entry["id"]))
    return found


def next_actions(
    blocked: list[dict[str, object]],
    ready: list[dict[str, object]],
) -> list[str]:
    actions: list[str] = []
    for item in blocked[:BLOCKED_ACTIONS_MAX]:
        reason = snippet(str(item.get("reason") or "(no reason)"), REASON_SNIPPET_MAX)
        actions.append(f"blocked {item['id']}: {reason}")
    for item in ready:
        if len(actions) >= NEXT_ACTIONS_MAX:
            break
        actions.append(f"start {item['id']}")
    return actions[:NEXT_ACTIONS_MAX]


def find_decision_registry(workbench: str | None) -> str | None:
    """Detect a decision-registry file at the top level of the workbench."""
    if not workbench or not workbench.strip():
        return None
    directory = Path(workbench)
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob("*.jsonl")):
        first_line = ""
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    if raw.strip():
                        first_line = raw
                        break
        except OSError:
            continue
        if not first_line:
            continue
        try:
            record = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and REGISTRY_KEYS.issubset(record.keys()):
            return str(candidate.resolve())
    return None


def build_brief(
    snapshot_payload: dict[str, object],
    artifacts_entries: list[dict[str, object]],
    warnings: list[str],
    workbench: str | None,
) -> dict[str, object]:
    metadata = snapshot_payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    integrity = snapshot_payload.get("integrity")
    integrity = integrity if isinstance(integrity, dict) else {}
    root = snapshot_payload.get("root")
    nodes = walk_nodes(root) if isinstance(root, dict) else []
    counts = snapshot_payload.get("counts")
    if not isinstance(counts, dict):
        counts = {}
    status_counts = {str(key): int(value) for key, value in counts.items() if isinstance(value, int)}
    blocked = blocked_nodes(nodes)
    ready = ready_leaves(snapshot_payload)
    brief: dict[str, object] = {
        "work_order_id": str(metadata.get("work_order_id") or metadata.get("name") or ""),
        "status": str(metadata.get("status", "pending")),
        "revision": int(metadata.get("revision", 0) or 0),
        "integrity_status": str(integrity.get("status", "")),
        "status_counts": dict(sorted(status_counts.items())),
        "running_nodes": running_nodes(nodes),
        "blocked_nodes": blocked,
        "awaiting_dynamic_groups": normalize_groups(snapshot_payload),
        "ready_leaves": ready,
        "recent_terminal_results": recent_terminal_results(nodes),
        "declared_artifacts": artifacts_entries,
        "decision_registry": find_decision_registry(workbench),
        "next_actions": next_actions(blocked, ready),
    }
    if warnings:
        brief["warnings"] = sorted(warnings)
    return brief


def collect(
    tree_paths: Sequence[str],
    workbench: str | None,
) -> dict[str, object]:
    candidates = candidate_prefixes()
    working: list[str] | None = None
    used_cli: str | None = None
    entries: list[dict[str, object]] = []
    for tree_path in tree_paths:
        entry: dict[str, object] | None = None
        if working is None:
            for prefix in candidates:
                reason, payload = run_read_command(prefix, "snapshot", tree_path)
                if reason == "runtime_cli_unavailable":
                    continue
                working = prefix
                used_cli = " ".join(prefix)
                break
            else:
                entry = {
                    "path": tree_path,
                    "included": False,
                    "skip_reason": "runtime_cli_unavailable",
                }
        if working is not None and entry is None:
            reason, payload = run_read_command(working, "snapshot", tree_path)
            if reason == "runtime_cli_unavailable":
                working = None
                used_cli = None
                for prefix in candidates:
                    probe_reason, probe_payload = run_read_command(prefix, "snapshot", tree_path)
                    if probe_reason != "runtime_cli_unavailable":
                        working = prefix
                        used_cli = " ".join(prefix)
                        reason, payload = probe_reason, probe_payload
                        break
            if working is None and entry is None:
                entry = {
                    "path": tree_path,
                    "included": False,
                    "skip_reason": "runtime_cli_unavailable",
                }
        if entry is None:
            if reason:
                entry = {"path": tree_path, "included": False, "skip_reason": reason}
                if payload is not None:
                    entry.update(payload)
            else:
                assert payload is not None
                metadata = payload.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                if metadata.get("artifact_kind") != "runtime":
                    entry = {
                        "path": tree_path,
                        "included": False,
                        "skip_reason": "not_runtime_tree",
                    }
                elif metadata.get("sealed_at") or str(metadata.get("status", "")) == "succeeded":
                    entry = {
                        "path": tree_path,
                        "included": False,
                        "skip_reason": "tree_sealed",
                    }
                else:
                    assert working is not None
                    artifacts_reason, artifacts_payload = run_read_command(
                        working, "artifacts", tree_path
                    )
                    artifacts_entries: list[dict[str, object]] = []
                    warnings: list[str] = []
                    if artifacts_reason:
                        warnings.append(f"artifacts_unavailable:{artifacts_reason}")
                    elif artifacts_payload is not None:
                        artifacts_entries = normalize_artifacts(artifacts_payload)
                    brief = build_brief(payload, artifacts_entries, warnings, workbench)
                    entry = {"path": tree_path, "included": True, **brief}
        entries.append(entry)
    included = sum(1 for item in entries if item.get("included") is True)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "runtime_cli": used_cli,
        "workbench": workbench or None,
        "trees_total": len(entries),
        "trees_included": included,
        "trees_skipped": len(entries) - included,
        "briefs": entries,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    tree_values: list[str] = []
    workbench: str | None = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--tree" and index + 1 < len(arguments):
            tree_values.append(arguments[index + 1])
            index += 2
            continue
        if argument == "--workbench" and index + 1 < len(arguments):
            workbench = arguments[index + 1]
            index += 2
            continue
        emit(invalid_payload("resume_brief_input_invalid"))
        return 0
    try:
        tree_paths = parse_trees(tree_values)
    except ResumeBriefInputError as exc:
        emit(invalid_payload(exc.code))
        return 0
    except Exception:
        emit(invalid_payload("resume_brief_failed"))
        return 1
    try:
        payload = collect(tree_paths, workbench)
    except Exception:
        emit(invalid_payload("resume_brief_failed"))
        return 1
    emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
