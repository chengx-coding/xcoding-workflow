#!/usr/bin/env python3
"""Deterministic per-file staleness tracking for verification surfaces.

Fail-closed contract:

- ``mark`` records one keyed entry: per-file sha256 hashes plus an entry
  hash over the canonical entry core. A duplicate key is refused without
  ``--replace``.
- ``query`` recomputes hashes for the requested keys. A key is stale when
  any tracked file hash differs or a file is missing; matching keys are
  current and requested keys absent from the store are unknown. Results
  are deterministically sorted.
- ``remove`` is the only mutation besides ``mark``: an explicit retire.
  Removing a missing key reports ``ok:false`` with a stable code.
- Every failure reports ``ok:false`` with a stable error code. Handled
  errors exit 0 so callers interpret the payload, not the exit code.
- The store is a single deterministic compact JSON file; writes are
  atomic via a temporary file plus ``os.replace``.

This script is a pure file-based mechanism. It never touches runtime
state and never calls the orchestration engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1
SUBCOMMANDS = ("mark", "query", "remove")
OPTIONS = {
    "--store": "store",
    "--key": "key",
    "--keys": "keys",
    "--verified-at": "verified_at",
    "--files": "files",
    "--replace": "replace",
}
REQUIRED_BY_COMMAND: dict[str, frozenset[str]] = {
    "mark": frozenset({"store", "key", "verified_at", "files"}),
    "query": frozenset({"store"}),
    "remove": frozenset({"store", "key"}),
}

_HEX_DIGESTS = frozenset("0123456789abcdef")


class StalenessInputError(ValueError):
    """Stable invalid-input result returned by the staleness tracker."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def emit(payload: dict[str, object]) -> None:
    print(compact_json(payload))


def error_payload(code: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "error": {"code": code},
    }


def parse_utc_timestamp(raw: str) -> datetime:
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StalenessInputError("staleness_input_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise StalenessInputError("staleness_input_invalid")
    return parsed


def valid_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(ord(char) >= 32 for char in value)
    )


def valid_path_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(ord(char) >= 32 for char in value)
    )


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in _HEX_DIGESTS for char in value)
    )


def parse_path_list(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(not part for part in parts):
        raise StalenessInputError("staleness_input_invalid")
    if len(set(parts)) != len(parts):
        raise StalenessInputError("staleness_input_invalid")
    return parts


def parse_key_list(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(not part for part in parts):
        raise StalenessInputError("staleness_input_invalid")
    return sorted(set(parts))


def entry_hash(verified_at: str, files: dict[str, str]) -> str:
    core = compact_json({"files": files, "verified_at": verified_at})
    return hashlib.sha256(core.encode("utf-8")).hexdigest()


def validate_entry(key: object, entry: object) -> bool:
    if not valid_identifier(key) or not isinstance(entry, dict):
        return False
    if set(entry) != {"files", "hash", "verified_at"}:
        return False
    verified_at = entry.get("verified_at")
    if not isinstance(verified_at, str):
        return False
    try:
        parse_utc_timestamp(verified_at)
    except StalenessInputError:
        return False
    files = entry.get("files")
    if not isinstance(files, dict) or not files:
        return False
    for path, digest in files.items():
        if not valid_path_name(path) or not valid_sha256(digest):
            return False
    recorded = entry.get("hash")
    if not valid_sha256(recorded):
        return False
    if recorded != entry_hash(verified_at, files):
        return False
    return True


def read_store(path: Path) -> dict[str, dict[str, object]]:
    """Return strictly validated entries.

    Returns an empty dict when the store does not exist. Raises
    StalenessInputError(staleness_store_corrupt) when contents fail
    validation and OSError when the file cannot be read.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StalenessInputError("staleness_store_corrupt") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise StalenessInputError("staleness_store_corrupt")
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise StalenessInputError("staleness_store_corrupt")
    validated: dict[str, dict[str, object]] = {}
    for key, entry in entries.items():
        if not validate_entry(key, entry):
            raise StalenessInputError("staleness_store_corrupt")
        assert isinstance(entry, dict)
        validated[str(key)] = entry
    return validated


def write_store(path: Path, entries: dict[str, dict[str, object]]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "entries": entries,
    }
    content = compact_json(payload) + "\n"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            stream.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_arguments(argv: Sequence[str]) -> tuple[str, dict[str, object]]:
    if not argv or argv[0] not in SUBCOMMANDS:
        raise StalenessInputError("staleness_input_invalid")
    command = argv[0]
    collected: dict[str, list[str]] = {name: [] for name in OPTIONS.values()}
    index = 1
    while index < len(argv):
        option = argv[index]
        name = OPTIONS.get(option)
        if name is None:
            raise StalenessInputError("staleness_input_invalid")
        if name == "replace":
            collected[name].append("true")
            index += 1
            continue
        if index + 1 >= len(argv):
            raise StalenessInputError("staleness_input_invalid")
        collected[name].append(argv[index + 1])
        index += 2
    if any(len(values) > 1 for values in collected.values()):
        raise StalenessInputError("staleness_input_invalid")
    supplied = {name: values[0] for name, values in collected.items() if values}
    missing = REQUIRED_BY_COMMAND[command] - set(supplied)
    if missing:
        raise StalenessInputError("staleness_input_invalid")
    store_path = str(supplied["store"])
    if not store_path.strip():
        raise StalenessInputError("staleness_input_invalid")
    parsed: dict[str, object] = {"store": store_path}
    if "replace" in supplied:
        parsed["replace"] = True
    key = supplied.get("key")
    if key is not None:
        if not valid_identifier(key):
            raise StalenessInputError("staleness_input_invalid")
        parsed["key"] = key
    if command == "mark":
        verified_at = supplied["verified_at"]
        assert isinstance(verified_at, str)
        parse_utc_timestamp(verified_at)
        parsed["verified_at"] = verified_at
        parsed["files"] = parse_path_list(supplied["files"])
    elif command == "query" and "keys" in supplied:
        parsed["keys"] = parse_key_list(supplied["keys"])
    return command, parsed


def run_mark(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["store"]))
    existing = read_store(path)
    key = str(inputs["key"])
    verified_at = str(inputs["verified_at"])
    file_paths = inputs["files"]
    assert isinstance(file_paths, list)
    replacing = key in existing
    if replacing and not inputs.get("replace"):
        raise StalenessInputError("staleness_key_duplicate")
    files: dict[str, str] = {}
    for raw_path in file_paths:
        file_path = Path(str(raw_path))
        try:
            files[str(raw_path)] = sha256_file(file_path)
        except OSError as exc:
            raise StalenessInputError("staleness_file_unavailable") from exc
    entry: dict[str, object] = {
        "verified_at": verified_at,
        "files": files,
        "hash": entry_hash(verified_at, files),
    }
    next_entries = dict(existing)
    next_entries[key] = entry
    write_store(path, next_entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "mark",
        "key": key,
        "status": "replaced" if replacing else "stored",
        "verified_at": verified_at,
        "files": sorted(files),
    }


def check_entry(entry: dict[str, object]) -> tuple[bool, list[dict[str, str]]]:
    files = entry["files"]
    assert isinstance(files, dict)
    problems: list[dict[str, str]] = []
    for raw_path in sorted(files):
        file_path = Path(raw_path)
        try:
            current_digest = sha256_file(file_path)
        except OSError:
            problems.append({"path": raw_path, "status": "missing"})
            continue
        if current_digest != files[raw_path]:
            problems.append({"path": raw_path, "status": "changed"})
    return (not problems, problems)


def run_query(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["store"]))
    existing = read_store(path)
    if "keys" in inputs:
        requested = inputs["keys"]
        assert isinstance(requested, list)
        keys = sorted({str(item) for item in requested})
    else:
        keys = sorted(existing)
    stale: list[dict[str, object]] = []
    current: list[dict[str, object]] = []
    unknown: list[dict[str, object]] = []
    for key in keys:
        entry = existing.get(key)
        if entry is None:
            unknown.append({"key": key})
            continue
        fresh, problems = check_entry(entry)
        if fresh:
            current.append({"key": key, "verified_at": entry["verified_at"]})
        else:
            stale.append({"key": key, "files": problems})
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "query",
        "stale": stale,
        "current": current,
        "unknown": unknown,
    }


def run_remove(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["store"]))
    existing = read_store(path)
    key = str(inputs["key"])
    if key not in existing:
        raise StalenessInputError("staleness_key_missing")
    next_entries = dict(existing)
    del next_entries[key]
    write_store(path, next_entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "remove",
        "key": key,
        "status": "removed",
    }


def run(command: str, inputs: dict[str, object]) -> dict[str, object]:
    if command == "mark":
        return run_mark(inputs)
    if command == "query":
        return run_query(inputs)
    return run_remove(inputs)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        command, inputs = parse_arguments(arguments)
        emit(run(command, inputs))
    except StalenessInputError as exc:
        emit(error_payload(exc.code))
    except OSError:
        emit(error_payload("staleness_store_unavailable"))
    except Exception:
        emit(error_payload("staleness_failed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
