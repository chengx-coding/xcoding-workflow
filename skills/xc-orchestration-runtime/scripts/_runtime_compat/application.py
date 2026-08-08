#!/usr/bin/env python3
"""Application service and legacy-compatible CLI for runtime trees.

This module owns runtime use cases and transaction boundaries. Schema,
scheduling, integrity, and persistence primitives remain in ``core``.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import core


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Adapter-owned resources used by one application execution."""

    default_template: Path
    config_path: Optional[Path] = None


@dataclass(frozen=True)
class CommandResult:
    """Stable non-printing result returned by the application service."""

    exit_code: int
    payload: Dict[str, Any]


_DEFAULT_ENVIRONMENT: Optional[RuntimeEnvironment] = None


def json_print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def configure_default_template(path: Path) -> None:
    """Set the adapter-owned default template for legacy-compatible init."""
    global _DEFAULT_ENVIRONMENT
    _DEFAULT_ENVIRONMENT = RuntimeEnvironment(default_template=path)


def default_template() -> Path:
    if _DEFAULT_ENVIRONMENT is None:
        raise core.ConfigError(
            "runtime default template is not configured",
            {"module": __name__},
        )
    return _DEFAULT_ENVIRONMENT.default_template


def _environment_for(args: argparse.Namespace) -> RuntimeEnvironment:
    environment = getattr(args, "_runtime_environment", None)
    if isinstance(environment, RuntimeEnvironment):
        return environment
    if _DEFAULT_ENVIRONMENT is not None:
        return _DEFAULT_ENVIRONMENT
    raise core.ConfigError(
        "runtime environment is not configured",
        {"module": __name__},
    )


def config_for(args: argparse.Namespace, path: Optional[Path]) -> Dict[str, Any]:
    raw_config = getattr(args, "config", "")
    config_path = (
        Path(raw_config)
        if raw_config
        else _environment_for(args).config_path
    )
    return core.load_config(path, config_path)


def parse_runtime_for_read(args: argparse.Namespace) -> Tuple[Path, Any, Dict[str, Any], Dict[str, Any]]:
    path = Path(args.tree)
    config = config_for(args, path)
    tree, integrity = core.read_tree_with_integrity(path, config, "runtime")
    core.require_target_runtime_schema(tree.getroot())
    return path, tree, config, integrity


def parse_runtime_for_write(args: argparse.Namespace) -> Tuple[Path, Any, Dict[str, Any]]:
    path, tree, config, integrity = parse_runtime_for_read(args)
    core.require_writable_integrity(integrity)
    core.require_valid_control_metadata(tree.getroot())
    errors = core.validate_runtime_root(tree.getroot(), check_integrity=False)
    if errors:
        raise core.TreeValidationError("runtime structural validation failed", {"errors": errors})
    core.require_expected_revision(tree.getroot(), getattr(args, "expected_revision", None))
    return path, tree, config


@contextmanager
def runtime_mutation(args: argparse.Namespace, operation: str, allow_sealed: bool = False) -> Any:
    path = Path(args.tree)
    with core.runtime_write_lock(path):
        parsed_path, tree, config = parse_runtime_for_write(args)
        if not allow_sealed:
            core.require_runtime_mutable(tree.getroot(), operation)
        yield parsed_path, tree, config


def write_runtime(
    tree: Any,
    path: Path,
    config: Dict[str, Any],
    operation: str,
    extra: Optional[Dict[str, Any]] = None,
    commit_paths: Optional[List[Path]] = None,
    commit_on_write: bool = True,
) -> Dict[str, Any]:
    original_tree = path.read_bytes() if path.exists() else None
    was_sealed = bool(tree.getroot().get("sealed_at"))
    revision = core.finalize_runtime_mutation(tree.getroot())
    newly_sealed = tree.getroot().get("status") == "succeeded" and not was_sealed
    svg_path = core.runtime_svg_path(path, tree.getroot()) if newly_sealed else None
    original_svg = svg_path.read_bytes() if svg_path is not None and svg_path.exists() else None

    def restore_newly_sealed_write() -> None:
        if original_tree is None:
            path.unlink(missing_ok=True)
        else:
            core.atomic_write_bytes(path, original_tree)
        if svg_path is None:
            return
        if original_svg is None:
            svg_path.unlink(missing_ok=True)
        else:
            core.atomic_write_bytes(svg_path, original_svg)

    errors = core.validate_runtime_root(tree.getroot(), check_integrity=False)
    if errors:
        raise core.TreeValidationError("runtime structural validation failed", {"errors": errors})
    try:
        persisted = core.write_managed_tree(
            tree,
            path,
            "runtime",
            config,
            operation,
            commit_paths=commit_paths,
            commit_on_write=commit_on_write or newly_sealed,
            export_runtime_svg=newly_sealed,
        )
    except Exception:
        if newly_sealed:
            restore_newly_sealed_write()
        raise
    if newly_sealed and persisted["status"] == "persisted_uncommitted":
        restore_newly_sealed_write()
        raise core.RuntimeErrorBase(
            "completed tree checkpoint could not be committed; runtime state was restored",
            {
                "status": "persisted_uncommitted",
                "operation": operation,
                "tree_path": str(path),
                "commit": persisted["commit"],
            },
        )
    payload: Dict[str, Any] = {
        "status": persisted["status"],
        "operation": operation,
        "tree_path": str(path),
        "checksum": persisted["checksum"],
        "integrity": persisted["integrity"],
        "commit": persisted["commit"],
        "revision": revision,
    }
    if persisted.get("svg_path"):
        payload["svg_path"] = persisted["svg_path"]
    if extra:
        payload.update(extra)
    return payload


def write_terminal_runtime(
    tree: Any,
    path: Path,
    config: Dict[str, Any],
    operation: str,
    extra: Optional[Dict[str, Any]] = None,
    commit_paths: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    original_tree = path.read_bytes()
    svg_path = (
        core.runtime_svg_path(path, tree.getroot())
        if tree.getroot().get("status") == "succeeded"
        else None
    )
    original_svg = svg_path.read_bytes() if svg_path is not None and svg_path.exists() else None

    def restore_checkpoint() -> None:
        core.atomic_write_bytes(path, original_tree)
        if svg_path is None:
            return
        if original_svg is None:
            svg_path.unlink(missing_ok=True)
        else:
            core.atomic_write_bytes(svg_path, original_svg)

    try:
        payload = write_runtime(
            tree,
            path,
            config,
            operation,
            extra,
            commit_paths=commit_paths,
        )
    except Exception:
        restore_checkpoint()
        raise
    if payload["status"] == "persisted_uncommitted":
        restore_checkpoint()
        raise core.RuntimeErrorBase(
            "terminal checkpoint could not be committed; runtime state was restored",
            {
                "status": "persisted_uncommitted",
                "operation": operation,
                "tree_path": str(path),
                "commit": payload["commit"],
            },
        )
    return payload


def snapshot_ready(root: Any, limit: int) -> List[Dict[str, Any]]:
    return [core.snapshot_node(root, node) for node in core.ready_from(root, core.root_node(root), limit)]


def cmd_init(args: argparse.Namespace) -> Dict[str, Any]:
    runtime_path = Path(args.runtime_path)
    config = config_for(args, runtime_path)
    template_path = (
        Path(args.template)
        if args.template
        else _environment_for(args).default_template
    )
    tree_path = runtime_path / "orchestration.xml"
    with core.runtime_write_lock(tree_path):
        template_tree = core.parse_xml(template_path)
        core.require_valid_control_metadata(template_tree.getroot())
        template_errors = core.validate_template_root(template_tree.getroot())
        if template_errors:
            raise core.TreeValidationError("template validation failed", {"errors": template_errors})
        work_order_id = args.work_order_id or (
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        )
        if tree_path.exists():
            raise core.RuntimeErrorBase("runtime tree already exists", {"path": str(tree_path)})
        tree = core.instantiate_runtime_tree(
            template_tree,
            work_order_id,
            args.name,
            core.parse_set_values(args.var),
            config,
        )
        core.stabilize(tree.getroot())
        return write_runtime(
            tree,
            tree_path,
            config,
            "init",
            {
                "work_order_id": work_order_id,
                "name": tree.getroot().get("name", ""),
                "template": str(template_path),
                "blackboard": core.blackboard(tree.getroot()),
            },
            commit_on_write=False,
        )


def cmd_next(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    root_status = root.get("status", "pending")
    return {
        "tree_path": str(path),
        "status": "complete" if root_status == "succeeded" else root_status,
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "counts": core.status_counts(root),
        "awaiting_dynamic_groups": core.awaiting_dynamic_groups(root),
        "ready": snapshot_ready(root, args.limit),
    }


def cmd_start(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "start") as (path, tree, config):
        node = core.begin_node(tree.getroot(), args.node, args.agent)
        return write_runtime(
            tree,
            path,
            config,
            "start",
            {"node": core.snapshot_node(tree.getroot(), node)},
            commit_on_write=False,
        )


def cmd_complete(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "complete") as (path, tree, config):
        node = core.complete_node(
            tree.getroot(),
            args.node,
            args.summary,
            args.artifact,
            args.validation,
            core.parse_set_values(args.set),
            args.check_result_json,
            args.gate_outcome,
            args.decision,
        )
        return write_terminal_runtime(
            tree,
            path,
            config,
            "complete",
            {
                "node": core.snapshot_node(tree.getroot(), node),
                "counts": core.status_counts(tree.getroot()),
            },
            commit_paths=[Path(item) for item in args.artifact],
        )


def cmd_fail(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "fail") as (path, tree, config):
        node = core.fail_node(tree.getroot(), args.node, args.reason, args.artifact)
        return write_terminal_runtime(
            tree,
            path,
            config,
            "fail",
            {"node": core.snapshot_node(tree.getroot(), node), "counts": core.status_counts(tree.getroot())},
            commit_paths=[Path(item) for item in args.artifact],
        )


def cmd_block(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "block") as (path, tree, config):
        node = core.block_node(tree.getroot(), args.node, args.reason, args.artifact)
        return write_terminal_runtime(
            tree,
            path,
            config,
            "block",
            {"node": core.snapshot_node(tree.getroot(), node), "counts": core.status_counts(tree.getroot())},
            commit_paths=[Path(item) for item in args.artifact],
        )


def cmd_unblock(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "unblock") as (path, tree, config):
        node = core.unblock_node(tree.getroot(), args.node)
        return write_runtime(
            tree,
            path,
            config,
            "unblock",
            {"node": core.snapshot_node(tree.getroot(), node), "counts": core.status_counts(tree.getroot())},
            commit_on_write=False,
        )


def cmd_retry_failed(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "retry-failed") as (path, tree, config):
        node, archived = core.retry_failed_node(tree.getroot(), args.node, args.reason)
        return write_runtime(
            tree,
            path,
            config,
            "retry-failed",
            {
                "node": core.snapshot_node(tree.getroot(), node),
                "archived_attempt": core.attempt_snapshot(archived),
                "counts": core.status_counts(tree.getroot()),
            },
            commit_on_write=False,
        )


def cmd_set(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "set") as (path, tree, config):
        root = tree.getroot()
        for key, value in core.parse_set_values(args.set):
            core.set_blackboard(root, key, value, "main")
        core.stabilize(root)
        return write_runtime(
            tree,
            path,
            config,
            "set",
            {"blackboard": core.blackboard(root), "counts": core.status_counts(root)},
            commit_on_write=False,
        )


def cmd_add_node(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "add-node") as (path, tree, config):
        node = core.create_dynamic_node(
            tree.getroot(),
            args.parent,
            args.logical_key,
            args.title,
            args.type,
            args.executor,
            args.role,
            args.mode,
            args.when,
            args.depends_on,
            args.instructions,
            args.inputs,
            args.deliverables,
            args.acceptance,
            core.parse_metadata_values(args.metadata),
            args.before,
        )
        core.stabilize(tree.getroot())
        return write_runtime(
            tree,
            path,
            config,
            "add-node",
            {"node": core.snapshot_node(tree.getroot(), node)},
            commit_on_write=False,
        )


def cmd_embed_subtree(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "embed-subtree") as (path, tree, config):
        embedded = core.embed_template_subtree(
            tree.getroot(),
            args.parent,
            core.parse_xml(Path(args.template)),
            config,
            args.instance_id or None,
        )
        core.stabilize(tree.getroot())
        return write_runtime(
            tree,
            path,
            config,
            "embed-subtree",
            {"node": core.snapshot_node(tree.getroot(), embedded), "template": args.template},
            commit_on_write=False,
        )


def cmd_close_group(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "close-group") as (path, tree, config):
        group = core.close_dynamic_group(tree.getroot(), args.group)
        return write_runtime(
            tree,
            path,
            config,
            "close-group",
            {
                "group": core.snapshot_node(tree.getroot(), group),
                "awaiting_dynamic_groups": core.awaiting_dynamic_groups(tree.getroot()),
            },
            commit_on_write=False,
        )


def cmd_reopen_group(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "reopen-group") as (path, tree, config):
        group = core.reopen_dynamic_group(tree.getroot(), args.group, args.reason)
        return write_runtime(
            tree,
            path,
            config,
            "reopen-group",
            {
                "group": core.snapshot_node(tree.getroot(), group),
                "reason": args.reason,
            },
            commit_on_write=False,
        )


def cmd_reopen(args: argparse.Namespace) -> Dict[str, Any]:
    with runtime_mutation(args, "reopen", allow_sealed=True) as (path, tree, config):
        core.reopen_runtime_tree(tree.getroot(), args.reason)
        return write_runtime(
            tree,
            path,
            config,
            "reopen",
            {
                "reason": args.reason,
                "epoch": tree.getroot().get("epoch", "0"),
            },
            commit_on_write=False,
        )


def cmd_summary(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    return {
        "tree_path": str(path),
        "status": "complete" if root.get("status") == "succeeded" else root.get("status"),
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "counts": core.status_counts(root),
        "blackboard": core.blackboard(root),
        "awaiting_dynamic_groups": core.awaiting_dynamic_groups(root),
        "ready": snapshot_ready(root, args.limit),
    }


def cmd_show(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    return {
        "tree_path": str(path),
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "node": core.snapshot_node(root, core.find_node(root, args.node)),
    }


def cmd_control_packet(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    return {
        "tree_path": str(path),
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "packet": core.build_control_packet(root, args.node),
    }


def cmd_find(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    nodes = [
        core.snapshot_node(root, node)
        for node in core.iter_nodes(root)
        if node.get("template_id") == args.template_id
        and (not args.instance_id or node.get("origin_instance_id") == args.instance_id)
    ]
    return {
        "tree_path": str(path),
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "template_id": args.template_id,
        "instance_id": args.instance_id,
        "nodes": nodes,
    }


def cmd_artifacts(args: argparse.Namespace) -> Dict[str, Any]:
    path, tree, _, integrity = parse_runtime_for_read(args)
    root = tree.getroot()
    return {
        "tree_path": str(path),
        "integrity": integrity,
        "revision": core.runtime_revision(root),
        "artifacts": core.declared_artifacts(root, args.audience),
    }


def cmd_snapshot(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.tree)
    config = config_for(args, path)
    return core.tree_snapshot(path, config)


def cmd_integrity_status(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.tree)
    config = config_for(args, path)
    tree = core.parse_xml(path)
    core.require_target_runtime_schema(tree.getroot())
    return {
        "tree_path": str(path),
        "config_source": config["_source"],
        "integrity": core.verify_integrity(tree.getroot(), "runtime"),
        "revision": core.runtime_revision(tree.getroot()),
    }


def cmd_repair_integrity(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.tree)
    config = config_for(args, path)
    with core.runtime_write_lock(path):
        tree = core.parse_xml(path)
        root = tree.getroot()
        core.require_target_runtime_schema(root)
        core.require_expected_revision(root, args.expected_revision)
        previous_integrity = core.verify_integrity(root, "runtime")
        core.stabilize(root)
        errors = core.validate_runtime_root(root, check_integrity=False)
        if errors:
            raise core.TreeValidationError("runtime structural validation failed", {"errors": errors})
        result = write_runtime(tree, path, config, "repair-integrity", {"reason": args.reason})
        result["previous_integrity"] = previous_integrity
        return result


def cmd_validate(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.tree)
    config = config_for(args, path)
    tree = core.parse_xml(path)
    root = tree.getroot()
    core.require_valid_control_metadata(root)
    kind = root.get("artifact_kind", "")
    if kind == "template":
        errors = core.validate_template_root(root)
    elif kind == "runtime":
        core.require_target_runtime_schema(root)
        errors = core.validate_runtime_root(root)
    else:
        errors = [f"unsupported or missing artifact_kind: {kind or '<missing>'}"]
    return {
        "tree_path": str(path),
        "artifact_kind": kind,
        "config_source": config["_source"],
        "valid": not errors,
        "errors": errors,
        "node_count": sum(1 for _ in core.iter_nodes(root)),
    }


def add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="", help="Optional xc-orchestration-runtime JSON path.")


def add_tree_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tree", required=True)
    add_config_argument(parser)
    parser.add_argument("--json", action="store_true", help="Accepted for agent protocol compatibility; JSON is always emitted.")


def add_mutation_tree_argument(parser: argparse.ArgumentParser) -> None:
    add_tree_argument(parser)
    parser.add_argument("--expected-revision", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage orchestration runtime trees.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a managed runtime tree from a managed template.")
    init.add_argument("--runtime-path", required=True)
    init.add_argument("--template", default="")
    init.add_argument("--work-order-id", default="")
    init.add_argument("--name", default="")
    init.add_argument("--var", action="append", default=[])
    add_config_argument(init)
    init.add_argument("--json", action="store_true", help="Accepted for agent protocol compatibility; JSON is always emitted.")
    init.set_defaults(func=cmd_init)

    next_cmd = sub.add_parser("next", help="Return ready nodes without changing the tree.")
    add_tree_argument(next_cmd)
    next_cmd.add_argument("--limit", type=int, default=8)
    next_cmd.set_defaults(func=cmd_next)

    start = sub.add_parser("start", help="Mark a ready task or gate as running.")
    add_mutation_tree_argument(start)
    start.add_argument("--node", required=True)
    start.add_argument("--agent", default="")
    start.set_defaults(func=cmd_start)

    complete = sub.add_parser("complete", help="Complete a task or gate and record outputs.")
    add_mutation_tree_argument(complete)
    complete.add_argument("--node", required=True)
    complete.add_argument("--summary", default="")
    complete.add_argument("--artifact", action="append", default=[])
    complete.add_argument("--validation", default="")
    complete.add_argument("--set", action="append", default=[])
    complete.add_argument("--check-result-json", action="append", default=[])
    complete.add_argument("--gate-outcome", default="")
    complete.add_argument("--decision", default="")
    complete.set_defaults(func=cmd_complete)

    fail = sub.add_parser("fail", help="Fail an executable leaf.")
    add_mutation_tree_argument(fail)
    fail.add_argument("--node", required=True)
    fail.add_argument("--reason", required=True)
    fail.add_argument("--artifact", action="append", default=[])
    fail.set_defaults(func=cmd_fail)

    block = sub.add_parser("block", help="Block an executable leaf.")
    add_mutation_tree_argument(block)
    block.add_argument("--node", required=True)
    block.add_argument("--reason", required=True)
    block.add_argument("--artifact", action="append", default=[])
    block.set_defaults(func=cmd_block)

    unblock = sub.add_parser("unblock", help="Return a blocked executable leaf to pending.")
    add_mutation_tree_argument(unblock)
    unblock.add_argument("--node", required=True)
    unblock.set_defaults(func=cmd_unblock)

    retry_failed = sub.add_parser(
        "retry-failed",
        help="Archive a failed executable-leaf attempt and return it to scheduling.",
    )
    add_mutation_tree_argument(retry_failed)
    retry_failed.add_argument("--node", required=True)
    retry_failed.add_argument("--reason", required=True)
    retry_failed.set_defaults(func=cmd_retry_failed)

    set_cmd = sub.add_parser("set", help="Set cross-node blackboard values.")
    add_mutation_tree_argument(set_cmd)
    set_cmd.add_argument("--set", action="append", required=True)
    set_cmd.set_defaults(func=cmd_set)

    add_node = sub.add_parser("add-node", help="Append a managed dynamic node.")
    add_mutation_tree_argument(add_node)
    add_node.add_argument("--parent", required=True)
    add_node.add_argument("--logical-key", required=True)
    add_node.add_argument("--title", required=True)
    add_node.add_argument("--type", default="task", choices=sorted(core.VALID_TYPES))
    add_node.add_argument("--role", default="")
    add_node.add_argument("--executor", default="subagent", choices=sorted(core.VALID_EXECUTORS))
    add_node.add_argument("--mode", default="", choices=sorted(core.VALID_MODES))
    add_node.add_argument("--when", default="")
    add_node.add_argument("--depends-on", dest="depends_on", default="")
    add_node.add_argument("--instructions", default="")
    add_node.add_argument("--inputs", default="")
    add_node.add_argument("--deliverables", default="")
    add_node.add_argument("--acceptance", default="")
    add_node.add_argument("--metadata", action="append", default=[])
    add_node.add_argument("--before", default="")
    add_node.set_defaults(func=cmd_add_node)

    embed = sub.add_parser("embed-subtree", help="Instantiate a managed template beneath a runtime parent.")
    add_mutation_tree_argument(embed)
    embed.add_argument("--parent", required=True)
    embed.add_argument("--template", required=True)
    embed.add_argument("--instance-id", default="")
    embed.set_defaults(func=cmd_embed_subtree)

    close_group = sub.add_parser("close-group", help="Close a dynamic group so no further nodes may be appended.")
    add_mutation_tree_argument(close_group)
    close_group.add_argument("--group", required=True)
    close_group.set_defaults(func=cmd_close_group)

    reopen_group = sub.add_parser(
        "reopen-group",
        help="Reopen a closed dynamic group for explicitly approved recovery work.",
    )
    add_mutation_tree_argument(reopen_group)
    reopen_group.add_argument("--group", required=True)
    reopen_group.add_argument("--reason", required=True)
    reopen_group.set_defaults(func=cmd_reopen_group)

    reopen = sub.add_parser("reopen", help="Reopen a sealed successful runtime tree with an auditable reason.")
    add_mutation_tree_argument(reopen)
    reopen.add_argument("--reason", required=True)
    reopen.set_defaults(func=cmd_reopen)

    summary = sub.add_parser("summary", help="Show runtime progress and ready nodes.")
    add_tree_argument(summary)
    summary.add_argument("--limit", type=int, default=8)
    summary.set_defaults(func=cmd_summary)

    show = sub.add_parser("show", help="Show a single runtime node.")
    add_tree_argument(show)
    show.add_argument("--node", required=True)
    show.set_defaults(func=cmd_show)

    control_packet = sub.add_parser(
        "control-packet",
        help="Project the scoped control packet declared by one executable leaf.",
    )
    add_tree_argument(control_packet)
    control_packet.add_argument("--node", required=True)
    control_packet.set_defaults(func=cmd_control_packet)

    find = sub.add_parser("find", help="Find runtime nodes by template ID.")
    add_tree_argument(find)
    find.add_argument("--template-id", required=True)
    find.add_argument("--instance-id", default="")
    find.set_defaults(func=cmd_find)

    artifacts = sub.add_parser("artifacts", help="List artifacts declared by terminal runtime nodes.")
    add_tree_argument(artifacts)
    artifacts.add_argument("--audience", choices=("internal", "user"), default="")
    artifacts.set_defaults(func=cmd_artifacts)

    snapshot = sub.add_parser("snapshot", help="Export the read-only viewer snapshot.")
    add_tree_argument(snapshot)
    snapshot.set_defaults(func=cmd_snapshot)

    integrity = sub.add_parser("integrity-status", help="Report runtime integrity without changing it.")
    add_tree_argument(integrity)
    integrity.set_defaults(func=cmd_integrity_status)

    repair = sub.add_parser("repair-integrity", help="Explicitly recreate runtime access metadata and checksum.")
    add_mutation_tree_argument(repair)
    repair.add_argument("--reason", required=True)
    repair.set_defaults(func=cmd_repair_integrity)

    validate = sub.add_parser("validate", help="Validate a managed template or runtime tree.")
    add_tree_argument(validate)
    validate.set_defaults(func=cmd_validate)
    return parser


def execute(
    argv: Optional[List[str]],
    environment: RuntimeEnvironment,
) -> CommandResult:
    """Execute one runtime command without writing process output."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args._runtime_environment = environment
    try:
        payload = args.func(args)
    except core.RuntimeErrorBase as exc:
        return CommandResult(
            exit_code=2,
            payload={
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": exc.details,
                },
            },
        )
    except OSError as exc:
        return CommandResult(
            exit_code=2,
            payload={
                "ok": False,
                "error": {
                    "code": "os_error",
                    "message": str(exc),
                    "details": {},
                },
            },
        )
    return CommandResult(
        exit_code=1 if payload.get("valid") is False else 0,
        payload={"ok": True, **payload},
    )


def main(
    argv: Optional[List[str]] = None,
    environment: Optional[RuntimeEnvironment] = None,
) -> int:
    resolved_environment = environment
    if resolved_environment is None:
        if _DEFAULT_ENVIRONMENT is None:
            result = CommandResult(
                exit_code=2,
                payload={
                    "ok": False,
                    "error": {
                        "code": "config_error",
                        "message": "runtime environment is not configured",
                        "details": {"module": __name__},
                    },
                },
            )
        else:
            resolved_environment = _DEFAULT_ENVIRONMENT
            result = execute(argv, resolved_environment)
    else:
        result = execute(argv, resolved_environment)
    json_print(result.payload)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
