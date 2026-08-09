"""Strict JSON protocol primitives for the local read-only daemon."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


SCHEMA_VERSION = 1
MAX_BODY_BYTES = 32768
MAX_JSON_RESPONSE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ProtocolError(Exception):
    """A bounded client or transport error."""

    status: HTTPStatus
    code: str
    message: str
    details: dict[str, Any]

    def __str__(self) -> str:
        return self.message


def request_id() -> str:
    return uuid.uuid4().hex


def success_payload(identifier: str, result: object) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "request_id": identifier,
        "result": result,
    }


def error_payload(
    identifier: str,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "request_id": identifier,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "duplicate_json_key",
                "request JSON contains a duplicate key",
                {"key": key},
            )
        result[key] = value
    return result


def parse_json_object(data: bytes) -> dict[str, object]:
    if len(data) > MAX_BODY_BYTES:
        raise ProtocolError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "request_too_large",
            "request body exceeds the configured limit",
            {"maximum_bytes": MAX_BODY_BYTES},
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_json",
            "request body must be valid UTF-8 JSON",
            {},
        ) from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except ProtocolError:
        raise
    except (json.JSONDecodeError, ValueError) as error:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_json",
            "request body must be valid finite JSON",
            {},
        ) from error
    if not isinstance(value, dict):
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_json_root",
            "request JSON root must be an object",
            {},
        )
    return value


def parse_query_request(
    payload: dict[str, object],
) -> tuple[str, str, dict[str, object]]:
    expected = {"tree_id", "command", "parameters"}
    actual = set(payload)
    if actual != expected:
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_request_fields",
            "query request fields do not match the protocol",
            {
                "missing": sorted(expected - actual),
                "unexpected": sorted(actual - expected),
            },
        )
    tree_id = payload["tree_id"]
    command = payload["command"]
    parameters = payload["parameters"]
    if (
        not isinstance(tree_id, str)
        or not tree_id
        or len(tree_id.encode("utf-8")) > 128
        or any(character in tree_id for character in "\x00\r\n")
    ):
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_tree_id",
            "tree_id must be a bounded non-empty string",
            {},
        )
    if not isinstance(command, str):
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_command",
            "command must be a string",
            {},
        )
    if not isinstance(parameters, dict):
        raise ProtocolError(
            HTTPStatus.BAD_REQUEST,
            "invalid_parameters",
            "parameters must be an object",
            {},
        )
    return tree_id, command, parameters


__all__ = [
    "MAX_BODY_BYTES",
    "MAX_JSON_RESPONSE_BYTES",
    "ProtocolError",
    "SCHEMA_VERSION",
    "error_payload",
    "json_bytes",
    "parse_json_object",
    "parse_query_request",
    "request_id",
    "success_payload",
]
