"""Typed read-only query facade for runtime transports."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from . import application, commands, core


READ_ONLY_COMMANDS = (
    "next",
    "summary",
    "show",
    "control-packet",
    "find",
    "artifacts",
    "snapshot",
    "integrity-status",
    "validate",
)

MAX_QUERY_SCALAR_BYTES = 4096
MAX_QUERY_PARAMETER_COUNT = 8


class QueryInputError(core.RuntimeErrorBase):
    """A read-only transport request is outside the query contract."""

    code = "invalid_query"


def _reject(message: str, reason: str, **details: Any) -> None:
    raise QueryInputError(message, {"reason": reason, **details})


def _identifier(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _reject(
            f"{label} must be a non-empty string",
            f"{label}_invalid",
        )
    if "\x00" in value or "\r" in value or "\n" in value:
        _reject(
            f"{label} contains a prohibited control character",
            f"{label}_control_character",
        )
    if len(value.encode("utf-8")) > MAX_QUERY_SCALAR_BYTES:
        _reject(
            f"{label} exceeds the query scalar limit",
            f"{label}_too_large",
            maximum_bytes=MAX_QUERY_SCALAR_BYTES,
        )
    return value


def _parameters(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _reject(
            "query parameters must be an object",
            "parameters_not_object",
        )
    if len(value) > MAX_QUERY_PARAMETER_COUNT:
        _reject(
            "query contains too many parameters",
            "too_many_parameters",
            maximum=MAX_QUERY_PARAMETER_COUNT,
        )
    result = dict(value)
    if any(not isinstance(key, str) for key in result):
        _reject(
            "query parameter names must be strings",
            "parameter_name_not_string",
        )
    for key in result:
        _identifier(key, label="parameter_name")
    return result


def _fields(
    parameters: dict[str, object],
    *,
    allowed: tuple[str, ...],
    required: tuple[str, ...] = (),
) -> None:
    unexpected = sorted(set(parameters) - set(allowed))
    if unexpected:
        _reject(
            "query contains unknown parameters",
            "unknown_parameters",
            unexpected=unexpected,
        )
    missing = [name for name in required if name not in parameters]
    if missing:
        _reject(
            "query is missing required parameters",
            "missing_parameters",
            missing=missing,
        )


def _string(
    parameters: dict[str, object],
    name: str,
    *,
    default: str | None = None,
    required: bool = False,
) -> str:
    if name not in parameters:
        if required:
            _reject(
                f"{name} is required",
                "missing_parameter",
                parameter=name,
            )
        return "" if default is None else default
    value = parameters[name]
    if not isinstance(value, str):
        _reject(
            f"{name} must be a string",
            "parameter_not_string",
            parameter=name,
        )
    if required and not value:
        _reject(
            f"{name} must not be empty",
            "parameter_empty",
            parameter=name,
        )
    if "\x00" in value or "\r" in value or "\n" in value:
        _reject(
            f"{name} contains a prohibited control character",
            "parameter_control_character",
            parameter=name,
        )
    if len(value.encode("utf-8")) > MAX_QUERY_SCALAR_BYTES:
        _reject(
            f"{name} exceeds the query scalar limit",
            "parameter_too_large",
            parameter=name,
            maximum_bytes=MAX_QUERY_SCALAR_BYTES,
        )
    return value


def _limit(parameters: dict[str, object]) -> int:
    value = parameters.get("limit", 8)
    if type(value) is not int:
        _reject(
            "limit must be an integer",
            "parameter_not_integer",
            parameter="limit",
        )
    if value < 1 or value > 64:
        _reject(
            "limit must be between 1 and 64",
            "parameter_out_of_range",
            parameter="limit",
            minimum=1,
            maximum=64,
        )
    return value


def _base_namespace(
    tree_path: Path,
    environment: application.RuntimeEnvironment,
) -> argparse.Namespace:
    return argparse.Namespace(
        tree=str(tree_path),
        config="",
        json=False,
        _runtime_environment=environment,
    )


def _build_namespace(
    command: str,
    tree_path: Path,
    parameters: object,
    environment: application.RuntimeEnvironment,
) -> argparse.Namespace:
    command = _identifier(command, label="command")
    if command not in READ_ONLY_COMMANDS:
        reason = (
            "command_not_read_only"
            if command in commands.COMMAND_NAMES
            else "command_unknown"
        )
        _reject(
            "query command is not available",
            reason,
            command=command,
        )
    values = _parameters(parameters)
    namespace = _base_namespace(tree_path, environment)

    if command in {"next", "summary"}:
        _fields(values, allowed=("limit",))
        namespace.limit = _limit(values)
    elif command in {"show", "control-packet"}:
        _fields(values, allowed=("node",), required=("node",))
        namespace.node = _string(values, "node", required=True)
    elif command == "find":
        _fields(
            values,
            allowed=("template_id", "instance_id"),
            required=("template_id",),
        )
        namespace.template_id = _string(
            values,
            "template_id",
            required=True,
        )
        namespace.instance_id = _string(
            values,
            "instance_id",
            default="",
        )
    elif command == "artifacts":
        _fields(values, allowed=("audience",))
        namespace.audience = _string(
            values,
            "audience",
            default="",
        )
        if namespace.audience not in {"", "internal", "user"}:
            _reject(
                "audience must be empty, internal, or user",
                "parameter_invalid_choice",
                parameter="audience",
            )
    else:
        _fields(values, allowed=())

    handlers: dict[
        str,
        Callable[[argparse.Namespace], dict[str, Any]],
    ] = {
        "next": application.cmd_next,
        "summary": application.cmd_summary,
        "show": application.cmd_show,
        "control-packet": application.cmd_control_packet,
        "find": application.cmd_find,
        "artifacts": application.cmd_artifacts,
        "snapshot": application.cmd_snapshot,
        "integrity-status": application.cmd_integrity_status,
        "validate": application.cmd_validate,
    }
    namespace.func = handlers[command]
    return namespace


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    namespace = _build_namespace(
        args.query_command,
        args.query_tree_path,
        args.query_parameters,
        args._runtime_environment,
    )
    return namespace.func(namespace)


def execute_query(
    command: str,
    tree_path: Path,
    parameters: Mapping[str, object],
    environment: application.RuntimeEnvironment,
) -> application.CommandResult:
    """Execute one typed read-only query without process output."""
    args = argparse.Namespace(
        func=_dispatch,
        query_command=command,
        query_tree_path=tree_path,
        query_parameters=parameters,
    )
    return application.execute_parsed(args, environment)


__all__ = [
    "MAX_QUERY_PARAMETER_COUNT",
    "MAX_QUERY_SCALAR_BYTES",
    "QueryInputError",
    "READ_ONLY_COMMANDS",
    "execute_query",
]
