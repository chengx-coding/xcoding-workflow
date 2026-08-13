#!/usr/bin/env python3
"""Read-only governance statistics collector for managed runtime trees.

This helper aggregates closed-loop governance evidence from one or more
managed runtime trees without touching the tree files themselves. Every
read goes through the public runtime CLI's read-only ``snapshot`` command
(the engine-owned viewer-snapshot export); no mutation command is invoked
and no managed file is opened directly.

Aggregated evidence per included tree:

- gate outcomes recorded on gate results (``result.gate_outcome``)
- archived retry attempts and retried node counts
- blocked, failed, and succeeded node counts plus the full status map
- route share: ``route=direct`` / ``route=managed`` values recorded
  textually in node result summaries (``result.summary`` only, including
  archived attempt summaries)

Unreadable, sealed, or non-runtime trees are skipped with a stable
per-tree skip reason. Output is one deterministic compact JSON object with
sorted keys and a sorted per-tree list. Invalid input exits 0 with an
``ok:false`` payload (stable contract); internal failures exit 1.

CLI resolution order: the ``XC_RUNTIME_CLI`` environment variable (shlex
argv), then an ``xcoding`` executable on PATH, then ``python -m xcoding``.
Every candidate is an argv prefix that already includes the runtime
subcommand (for example ``xcoding runtime`` or a tool-specific runtime
runner); the collector appends only the read-only ``snapshot`` command.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence

SCHEMA_VERSION = 1
SNAPSHOT_TIMEOUT_SECONDS = 60
CLI_ENV_VAR = "XC_RUNTIME_CLI"
ROUTE_PATTERN = re.compile(r"\broute=(direct|managed)\b")


class GovernanceStatsInputError(ValueError):
    """Stable invalid-input result returned by the collector."""

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
    """Parse repeatable --trees values: paths or JSON lists of paths."""
    if not values:
        raise GovernanceStatsInputError("governance_stats_input_missing")
    paths: list[str] = []
    for value in values:
        if not value.strip():
            raise GovernanceStatsInputError("governance_stats_input_invalid")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            paths.append(value)
            continue
        if parsed is None:
            raise GovernanceStatsInputError("governance_stats_input_invalid")
        if isinstance(parsed, str):
            if not parsed.strip():
                raise GovernanceStatsInputError("governance_stats_input_invalid")
            paths.append(parsed)
            continue
        if isinstance(parsed, list):
            if not parsed:
                raise GovernanceStatsInputError("governance_stats_input_empty")
            if any(not isinstance(item, str) or not item.strip() for item in parsed):
                raise GovernanceStatsInputError("governance_stats_input_invalid")
            paths.extend(parsed)
            continue
        raise GovernanceStatsInputError("governance_stats_input_invalid")
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
    return code if isinstance(code, str) and code else "snapshot_failed"


def run_snapshot(
    prefix: list[str],
    tree_path: str,
) -> tuple[str, dict[str, object] | None]:
    """Run one read-only snapshot; return ("" | skip_reason, payload)."""
    argv = [*prefix, "snapshot", "--tree", tree_path]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=SNAPSHOT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return "snapshot_timeout", None
    except OSError:
        return "runtime_cli_unavailable", None
    payload = parse_object(completed.stdout)
    if completed.returncode != 0:
        if payload is not None and payload.get("ok") is False:
            return "tree_unreadable", {
                "error": {"code": extract_error_code(completed.stdout)}
            }
        return "snapshot_malformed", None
    if payload is None or payload.get("ok") is not True:
        return "snapshot_malformed", None
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


def result_fields(node: dict[str, object]) -> list[dict[str, object]]:
    """Current and archived attempt result dicts of one node."""
    results: list[dict[str, object]] = []
    result = node.get("result")
    if isinstance(result, dict):
        results.append(result)
    attempts = node.get("attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if isinstance(attempt, dict) and isinstance(attempt.get("result"), dict):
                results.append(attempt["result"])
    return results


def aggregate_tree(payload: dict[str, object]) -> dict[str, object]:
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    if metadata.get("artifact_kind") != "runtime":
        raise GovernanceStatsInputError("not_runtime_tree")
    status = str(metadata.get("status", "pending"))
    sealed_at = str(metadata.get("sealed_at", ""))
    if sealed_at or status == "succeeded":
        raise GovernanceStatsInputError("tree_sealed")
    root = payload.get("root")
    nodes = walk_nodes(root) if isinstance(root, dict) else []
    gate_outcomes: dict[str, int] = {}
    node_statuses: dict[str, int] = {}
    routes: dict[str, int] = {}
    retry_attempts = 0
    retried_nodes = 0
    for node in nodes:
        node_status = str(node.get("status", "pending"))
        node_statuses[node_status] = node_statuses.get(node_status, 0) + 1
        for result in result_fields(node):
            outcome = result.get("gate_outcome")
            if isinstance(outcome, str) and outcome:
                gate_outcomes[outcome] = gate_outcomes.get(outcome, 0) + 1
            summary = result.get("summary")
            if isinstance(summary, str) and summary:
                for match in ROUTE_PATTERN.finditer(summary):
                    value = match.group(1)
                    routes[value] = routes.get(value, 0) + 1
        attempts = node.get("attempts")
        if isinstance(attempts, list):
            count = sum(1 for attempt in attempts if isinstance(attempt, dict))
            retry_attempts += count
            if count:
                retried_nodes += 1
    integrity = payload.get("integrity")
    integrity = integrity if isinstance(integrity, dict) else {}
    return {
        "gate_outcomes": gate_outcomes,
        "node_statuses": node_statuses,
        "blocked_nodes": node_statuses.get("blocked", 0),
        "failed_nodes": node_statuses.get("failed", 0),
        "succeeded_nodes": node_statuses.get("succeeded", 0),
        "retry_attempts": retry_attempts,
        "retried_nodes": retried_nodes,
        "routes": routes,
        "status": status,
        "revision": int(metadata.get("revision", 0) or 0),
        "node_count": len(nodes),
        "integrity_status": str(integrity.get("status", "")),
    }


def merge_counts(aggregates: list[dict[str, object]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for aggregate in aggregates:
        for key in ("gate_outcomes", "node_statuses", "routes"):
            values = aggregate.get(key)
            if not isinstance(values, dict):
                continue
            for name, value in values.items():
                if isinstance(value, int):
                    merged[f"{key}.{name}"] = merged.get(f"{key}.{name}", 0) + value
        for key in (
            "blocked_nodes",
            "failed_nodes",
            "succeeded_nodes",
            "retry_attempts",
            "retried_nodes",
        ):
            value = aggregate.get(key)
            if isinstance(value, int):
                merged[key] = merged.get(key, 0) + value
    return merged


def collect(
    tree_paths: Sequence[str],
) -> dict[str, object]:
    candidates = candidate_prefixes()
    working: list[str] | None = None
    used_cli: str | None = None
    entries: list[dict[str, object]] = []
    aggregates: list[dict[str, object]] = []
    for tree_path in tree_paths:
        entry: dict[str, object] | None = None
        if working is None:
            for prefix in candidates:
                reason, payload = run_snapshot(prefix, tree_path)
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
            reason, payload = run_snapshot(working, tree_path)
            if reason == "runtime_cli_unavailable":
                working = None
                used_cli = None
                for prefix in candidates:
                    probe_reason, probe_payload = run_snapshot(prefix, tree_path)
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
                try:
                    aggregate = aggregate_tree(payload or {})
                except GovernanceStatsInputError as exc:
                    entry = {
                        "path": tree_path,
                        "included": False,
                        "skip_reason": exc.code,
                    }
                else:
                    entry = {
                        "path": tree_path,
                        "included": True,
                        "sealed": False,
                        **aggregate,
                    }
                    aggregates.append(aggregate)
        entries.append(entry)
    merged = merge_counts(aggregates)
    gate_outcomes = {
        key[14:]: value
        for key, value in sorted(merged.items())
        if key.startswith("gate_outcomes.")
    }
    node_statuses = {
        key[14:]: value
        for key, value in sorted(merged.items())
        if key.startswith("node_statuses.")
    }
    routes = {
        key[7:]: value for key, value in sorted(merged.items()) if key.startswith("routes.")
    }
    included = sum(1 for entry in entries if entry.get("included") is True)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "runtime_cli": used_cli,
        "trees_total": len(entries),
        "trees_included": included,
        "trees_skipped": len(entries) - included,
        "gate_outcomes": gate_outcomes,
        "node_statuses": node_statuses,
        "blocked_nodes": merged.get("blocked_nodes", 0),
        "failed_nodes": merged.get("failed_nodes", 0),
        "succeeded_nodes": merged.get("succeeded_nodes", 0),
        "retry_attempts": merged.get("retry_attempts", 0),
        "retried_nodes": merged.get("retried_nodes", 0),
        "routes": routes,
        "trees": entries,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    values: list[str] = []
    index = 0
    while index < len(arguments):
        if arguments[index] == "--trees" and index + 1 < len(arguments):
            values.append(arguments[index + 1])
            index += 2
            continue
        emit(invalid_payload("governance_stats_input_invalid"))
        return 0
    try:
        tree_paths = parse_trees(values)
    except GovernanceStatsInputError as exc:
        emit(invalid_payload(exc.code))
        return 0
    except Exception:
        emit(invalid_payload("governance_stats_failed"))
        return 1
    try:
        payload = collect(tree_paths)
    except Exception:
        emit(invalid_payload("governance_stats_failed"))
        return 1
    emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
