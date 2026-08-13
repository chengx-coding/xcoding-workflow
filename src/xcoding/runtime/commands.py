"""Shared command specification for legacy and package runtime adapters."""

from __future__ import annotations

import argparse

from . import core


COMMAND_NAMES = (
    "init",
    "next",
    "start",
    "complete",
    "fail",
    "block",
    "unblock",
    "retry-failed",
    "set",
    "add-node",
    "embed-subtree",
    "close-group",
    "reopen-group",
    "reopen",
    "summary",
    "show",
    "control-packet",
    "find",
    "artifacts",
    "snapshot",
    "integrity-status",
    "repair-integrity",
    "validate",
    "restore-point",
    "archive-subtree",
)


def add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default="",
        help="Optional xc-orchestration-runtime JSON path.",
    )


def add_tree_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tree", required=True)
    add_config_argument(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Accepted for agent protocol compatibility; "
            "JSON is always emitted."
        ),
    )


def add_mutation_tree_argument(parser: argparse.ArgumentParser) -> None:
    add_tree_argument(parser)
    parser.add_argument("--expected-revision", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    """Build the exact parser used by both runtime command adapters."""
    from . import application

    parser = argparse.ArgumentParser(
        description="Manage orchestration runtime trees."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser(
        "init",
        help="Create a managed runtime tree from a managed template.",
    )
    init.add_argument("--runtime-path", required=True)
    init.add_argument("--template", default="")
    init.add_argument("--work-order-id", default="")
    init.add_argument("--name", default="")
    init.add_argument("--var", action="append", default=[])
    add_config_argument(init)
    init.add_argument(
        "--json",
        action="store_true",
        help=(
            "Accepted for agent protocol compatibility; "
            "JSON is always emitted."
        ),
    )
    init.set_defaults(func=application.cmd_init)

    next_cmd = sub.add_parser(
        "next",
        help="Return ready nodes without changing the tree.",
    )
    add_tree_argument(next_cmd)
    next_cmd.add_argument("--limit", type=int, default=8)
    next_cmd.set_defaults(func=application.cmd_next)

    start = sub.add_parser(
        "start",
        help="Mark a ready task or gate as running.",
    )
    add_mutation_tree_argument(start)
    start.add_argument("--node", required=True)
    start.add_argument("--agent", default="")
    start.set_defaults(func=application.cmd_start)

    complete = sub.add_parser(
        "complete",
        help="Complete a task or gate and record outputs.",
    )
    add_mutation_tree_argument(complete)
    complete.add_argument("--node", required=True)
    complete.add_argument("--summary", default="")
    complete.add_argument("--artifact", action="append", default=[])
    complete.add_argument("--validation", default="")
    complete.add_argument("--set", action="append", default=[])
    complete.add_argument("--check-result-json", action="append", default=[])
    complete.add_argument("--gate-outcome", default="")
    complete.add_argument("--decision", default="")
    complete.set_defaults(func=application.cmd_complete)

    fail = sub.add_parser("fail", help="Fail an executable leaf.")
    add_mutation_tree_argument(fail)
    fail.add_argument("--node", required=True)
    fail.add_argument("--reason", required=True)
    fail.add_argument("--artifact", action="append", default=[])
    fail.set_defaults(func=application.cmd_fail)

    block = sub.add_parser("block", help="Block an executable leaf.")
    add_mutation_tree_argument(block)
    block.add_argument("--node", required=True)
    block.add_argument("--reason", required=True)
    block.add_argument("--artifact", action="append", default=[])
    block.set_defaults(func=application.cmd_block)

    unblock = sub.add_parser(
        "unblock",
        help="Return a blocked executable leaf to pending.",
    )
    add_mutation_tree_argument(unblock)
    unblock.add_argument("--node", required=True)
    unblock.set_defaults(func=application.cmd_unblock)

    retry_failed = sub.add_parser(
        "retry-failed",
        help=(
            "Archive a failed executable-leaf attempt and return it "
            "to scheduling."
        ),
    )
    add_mutation_tree_argument(retry_failed)
    retry_failed.add_argument("--node", required=True)
    retry_failed.add_argument("--reason", required=True)
    retry_failed.set_defaults(func=application.cmd_retry_failed)

    set_cmd = sub.add_parser("set", help="Set cross-node blackboard values.")
    add_mutation_tree_argument(set_cmd)
    set_cmd.add_argument("--set", action="append", required=True)
    set_cmd.set_defaults(func=application.cmd_set)

    add_node = sub.add_parser(
        "add-node",
        help="Append a managed dynamic node.",
    )
    add_mutation_tree_argument(add_node)
    add_node.add_argument("--parent", required=True)
    add_node.add_argument("--logical-key", required=True)
    add_node.add_argument("--title", required=True)
    add_node.add_argument(
        "--type",
        default="task",
        choices=sorted(core.VALID_TYPES),
    )
    add_node.add_argument("--role", default="")
    add_node.add_argument(
        "--executor",
        default="subagent",
        choices=sorted(core.VALID_EXECUTORS),
    )
    add_node.add_argument(
        "--mode",
        default="",
        choices=sorted(core.VALID_MODES),
    )
    add_node.add_argument("--when", default="")
    add_node.add_argument("--depends-on", dest="depends_on", default="")
    add_node.add_argument("--instructions", default="")
    add_node.add_argument("--inputs", default="")
    add_node.add_argument("--deliverables", default="")
    add_node.add_argument("--acceptance", default="")
    add_node.add_argument("--metadata", action="append", default=[])
    add_node.add_argument("--before", default="")
    add_node.set_defaults(func=application.cmd_add_node)

    embed = sub.add_parser(
        "embed-subtree",
        help="Instantiate a managed template beneath a runtime parent.",
    )
    add_mutation_tree_argument(embed)
    embed.add_argument("--parent", required=True)
    embed.add_argument("--template", required=True)
    embed.add_argument("--instance-id", default="")
    embed.set_defaults(func=application.cmd_embed_subtree)

    close_group = sub.add_parser(
        "close-group",
        help="Close a dynamic group so no further nodes may be appended.",
    )
    add_mutation_tree_argument(close_group)
    close_group.add_argument("--group", required=True)
    close_group.set_defaults(func=application.cmd_close_group)

    reopen_group = sub.add_parser(
        "reopen-group",
        help="Reopen a closed dynamic group for explicitly approved recovery.",
    )
    add_mutation_tree_argument(reopen_group)
    reopen_group.add_argument("--group", required=True)
    reopen_group.add_argument("--reason", required=True)
    reopen_group.set_defaults(func=application.cmd_reopen_group)

    reopen = sub.add_parser(
        "reopen",
        help="Reopen a sealed successful runtime tree with an auditable reason.",
    )
    add_mutation_tree_argument(reopen)
    reopen.add_argument("--reason", required=True)
    reopen.set_defaults(func=application.cmd_reopen)

    summary = sub.add_parser(
        "summary",
        help="Show runtime progress and ready nodes.",
    )
    add_tree_argument(summary)
    summary.add_argument("--limit", type=int, default=8)
    summary.set_defaults(func=application.cmd_summary)

    show = sub.add_parser("show", help="Show a single runtime node.")
    add_tree_argument(show)
    show.add_argument("--node", required=True)
    show.set_defaults(func=application.cmd_show)

    control_packet = sub.add_parser(
        "control-packet",
        help="Project the scoped control packet declared by one leaf.",
    )
    add_tree_argument(control_packet)
    control_packet.add_argument("--node", required=True)
    control_packet.set_defaults(func=application.cmd_control_packet)

    find = sub.add_parser("find", help="Find runtime nodes by template ID.")
    add_tree_argument(find)
    find.add_argument("--template-id", required=True)
    find.add_argument("--instance-id", default="")
    find.set_defaults(func=application.cmd_find)

    artifacts = sub.add_parser(
        "artifacts",
        help="List artifacts declared by terminal runtime nodes.",
    )
    add_tree_argument(artifacts)
    artifacts.add_argument(
        "--audience",
        choices=("internal", "user"),
        default="",
    )
    artifacts.set_defaults(func=application.cmd_artifacts)

    snapshot = sub.add_parser(
        "snapshot",
        help="Export the read-only viewer snapshot.",
    )
    add_tree_argument(snapshot)
    snapshot.set_defaults(func=application.cmd_snapshot)

    integrity = sub.add_parser(
        "integrity-status",
        help="Report runtime integrity without changing it.",
    )
    add_tree_argument(integrity)
    integrity.set_defaults(func=application.cmd_integrity_status)

    repair = sub.add_parser(
        "repair-integrity",
        help="Explicitly recreate runtime access metadata and checksum.",
    )
    add_mutation_tree_argument(repair)
    repair.add_argument("--reason", required=True)
    repair.set_defaults(func=application.cmd_repair_integrity)

    validate = sub.add_parser(
        "validate",
        help="Validate a managed template or runtime tree.",
    )
    add_tree_argument(validate)
    validate.set_defaults(func=application.cmd_validate)

    restore_point = sub.add_parser(
        "restore-point",
        help="Capture, list, or restore workshop-scoped restore points.",
    )
    restore_point_sub = restore_point.add_subparsers(
        dest="restore_point_command",
        required=True,
    )

    restore_point_create = restore_point_sub.add_parser(
        "create",
        help="Capture a verified restore point of a runtime tree.",
    )
    add_tree_argument(restore_point_create)
    restore_point_create.add_argument("--name", default="")
    restore_point_create.set_defaults(func=application.cmd_restore_point_create)

    restore_point_list = restore_point_sub.add_parser(
        "list",
        help="List captured restore points in deterministic order.",
    )
    add_tree_argument(restore_point_list)
    restore_point_list.set_defaults(func=application.cmd_restore_point_list)

    restore_point_restore = restore_point_sub.add_parser(
        "restore",
        help="Restore a verified restore point with an auditable reason.",
    )
    add_mutation_tree_argument(restore_point_restore)
    restore_point_restore.add_argument("--restore-point", required=True)
    restore_point_restore.add_argument("--reason", required=True)
    restore_point_restore.set_defaults(func=application.cmd_restore_point_restore)

    archive_subtree = sub.add_parser(
        "archive-subtree",
        help="Archive a succeeded or closed subtree into the read-only archived registry.",
    )
    add_mutation_tree_argument(archive_subtree)
    archive_subtree.add_argument("--subtree", required=True)
    archive_subtree.add_argument("--reason", required=True)
    archive_subtree.set_defaults(func=application.cmd_archive_subtree)

    if tuple(sub.choices) != COMMAND_NAMES:
        raise RuntimeError("runtime command specification is incomplete")
    return parser


__all__ = [
    "COMMAND_NAMES",
    "add_config_argument",
    "add_mutation_tree_argument",
    "add_tree_argument",
    "build_parser",
]
