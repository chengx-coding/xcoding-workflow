"""Strict bounded JSON parsing and canonical JSON encoding."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from typing import Any

from .errors import DelegationError, fail


MAX_INPUT_BYTES = 64 * 1024
MAX_DEPTH = 32
MAX_NODES = 4096
MAX_STRING_BYTES = 16 * 1024


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON with one trailing LF."""
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        fail(
            "json_invalid",
            "encode",
            "value cannot be represented as canonical JSON",
            reason=type(error).__name__,
        )


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_digest(value: object) -> str:
    return sha256_hex(canonical_json_bytes(value))


def _validate_shape(
    value: Any,
    *,
    depth: int = 1,
    counter: list[int] | None = None,
    location: str = "$",
) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_NODES:
        fail("json_limit_exceeded", "parse", "JSON node limit exceeded")
    if depth > MAX_DEPTH:
        fail("json_limit_exceeded", "parse", "JSON depth limit exceeded")
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            fail(
                "json_not_nfc",
                "parse",
                "JSON strings and object keys must use Unicode NFC",
            )
        if len(value.encode("utf-8")) > MAX_STRING_BYTES:
            fail("json_limit_exceeded", "parse", "JSON string limit exceeded")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            fail("json_non_finite", "parse", "non-finite JSON numbers are forbidden")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_shape(
                item,
                depth=depth + 1,
                counter=counter,
                location=f"{location}[{index}]",
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                fail("json_invalid", "parse", "JSON object keys must be strings")
            _validate_shape(
                key,
                depth=depth + 1,
                counter=counter,
                location=f"{location}.<key>",
            )
            _validate_shape(
                item,
                depth=depth + 1,
                counter=counter,
                location=f"{location}.{key}",
            )
        return
    fail("json_invalid", "parse", "unsupported JSON value type")


def parse_json_bytes(
    data: bytes,
    *,
    require_object: bool = True,
    require_canonical: bool = True,
) -> dict[str, Any] | list[Any]:
    """Parse one bounded JSON document and reject ambiguous encodings."""
    if len(data) > MAX_INPUT_BYTES:
        fail("json_limit_exceeded", "parse", "JSON input exceeds 64 KiB")
    if data.startswith(b"\xef\xbb\xbf"):
        fail("json_bom_forbidden", "parse", "UTF-8 BOM is forbidden")

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                fail(
                    "json_duplicate_key",
                    "parse",
                    "duplicate JSON object key",
                )
            result[key] = value
        return result

    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=lambda _token: (_ for _ in ()).throw(ValueError()),
        )
    except DelegationError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError):
        fail("json_invalid", "parse", "input is not valid strict UTF-8 JSON")
    if require_object and not isinstance(value, dict):
        fail("json_root_invalid", "parse", "JSON root must be an object")
    if not isinstance(value, (dict, list)):
        fail("json_root_invalid", "parse", "JSON root must be an object or array")
    _validate_shape(value)
    if require_canonical and canonical_json_bytes(value) != data:
        fail(
            "json_not_canonical",
            "parse",
            "JSON must be canonical sorted UTF-8 with one LF terminator",
        )
    return value


__all__ = [
    "MAX_DEPTH",
    "MAX_INPUT_BYTES",
    "MAX_NODES",
    "MAX_STRING_BYTES",
    "canonical_digest",
    "canonical_json_bytes",
    "parse_json_bytes",
    "sha256_hex",
]
