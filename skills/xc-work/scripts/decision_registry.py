#!/usr/bin/env python3
"""Append-only JSONL decision registry for managed work orders.

Fail-closed contract:

- ``record`` appends exactly one JSON line per decision. The file is never
  rewritten, so no update or delete path exists by construction.
- ``list`` and ``get`` replay the file read-only and never modify it.
- A duplicate decision id is refused with a stable error; invalid input
  reports ``ok:false``.
- A store whose contents fail validation reports ``decision_store_corrupt``;
  a store that exists but cannot be read or appended reports
  ``decision_store_unavailable``. Both fail closed before any write.
- Every stored line carries exactly: id, work_order_id, timestamp (UTC
  ISO-8601), decision, rationale, evidence_refs, actor.
- Payloads use deterministic compact JSON. ``list`` sorts decisions by
  timestamp then id, independent of file order.

This script assumes a single writer. Concurrent ``record`` invocations
against the same file are not supported: the duplicate-id check is not
atomic against concurrent appends, so two simultaneous records with the
same id could both be appended.

This script is a pure file-based mechanism. It never touches runtime state
and never calls the orchestration engine.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
SUBCOMMANDS = ("record", "list", "get")
ENTRY_KEYS = (
    "id",
    "work_order_id",
    "timestamp",
    "decision",
    "rationale",
    "evidence_refs",
    "actor",
)
OPTIONS = {
    "--path": "path",
    "--work-order-id": "work_order_id",
    "--decision-id": "decision_id",
    "--decision": "decision",
    "--rationale": "rationale",
    "--evidence-refs": "evidence_refs",
    "--actor": "actor",
    "--timestamp": "timestamp",
}
REQUIRED_BY_COMMAND: dict[str, frozenset[str]] = {
    "record": frozenset(
        {"path", "work_order_id", "decision_id", "decision", "rationale",
         "evidence_refs", "actor"}
    ),
    "list": frozenset({"path"}),
    "get": frozenset({"path", "decision_id"}),
}


class RegistryInputError(ValueError):
    """Stable invalid-input result returned by the decision registry."""

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
        raise RegistryInputError("decision_input_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise RegistryInputError("decision_input_invalid")
    return parsed


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_evidence_refs(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistryInputError("decision_input_invalid") from exc
    if (
        not isinstance(payload, list)
        or any(not isinstance(item, str) or not item.strip() for item in payload)
        or len(set(payload)) != len(payload)
    ):
        raise RegistryInputError("decision_input_invalid")
    return payload


def valid_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and all(ord(char) >= 32 for char in value)
    )


def valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_entry(entry: object) -> bool:
    if not isinstance(entry, dict) or set(entry) != set(ENTRY_KEYS):
        return False
    for name in ("id", "work_order_id"):
        if not valid_identifier(entry.get(name)):
            return False
    for name in ("decision", "rationale", "actor"):
        if not valid_text(entry.get(name)):
            return False
    refs = entry.get("evidence_refs")
    if (
        not isinstance(refs, list)
        or any(not isinstance(item, str) or not item.strip() for item in refs)
        or len(set(refs)) != len(refs)
    ):
        return False
    timestamp = entry.get("timestamp")
    if not isinstance(timestamp, str):
        return False
    try:
        parse_utc_timestamp(timestamp)
    except RegistryInputError:
        return False
    return True


def parse_arguments(argv: Sequence[str]) -> tuple[str, dict[str, object]]:
    if not argv or argv[0] not in SUBCOMMANDS:
        raise RegistryInputError("decision_input_invalid")
    command = argv[0]
    collected: dict[str, list[str]] = {name: [] for name in OPTIONS.values()}
    index = 1
    while index < len(argv):
        option = argv[index]
        name = OPTIONS.get(option)
        if name is None or index + 1 >= len(argv):
            raise RegistryInputError("decision_input_invalid")
        collected[name].append(argv[index + 1])
        index += 2
    if any(len(values) > 1 for values in collected.values()):
        raise RegistryInputError("decision_input_invalid")
    supplied = {name: values[0] for name, values in collected.items() if values}
    missing = REQUIRED_BY_COMMAND[command] - set(supplied)
    if missing:
        raise RegistryInputError("decision_input_invalid")
    if not supplied["path"].strip():
        raise RegistryInputError("decision_input_invalid")
    parsed: dict[str, object] = {"path": supplied["path"]}
    if command == "record":
        parsed.update(
            {
                "work_order_id": supplied["work_order_id"],
                "decision_id": supplied["decision_id"],
                "decision": supplied["decision"],
                "rationale": supplied["rationale"],
                "evidence_refs": parse_evidence_refs(supplied["evidence_refs"]),
                "actor": supplied["actor"],
            }
        )
        if "timestamp" in supplied:
            parsed["timestamp"] = supplied["timestamp"]
    elif command == "get":
        parsed["decision_id"] = supplied["decision_id"]
    return command, parsed


def read_registry(path: Path) -> list[dict[str, object]] | None:
    """Return strict valid entries in file order.

    Raises OSError when the store cannot be read (unavailable); returns
    None when the contents fail validation (corrupt).
    """
    content = path.read_text(encoding="utf-8")
    entries: list[dict[str, object]] = []
    for line in content.splitlines():
        if not line.strip():
            return None
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not validate_entry(entry):
            return None
        assert isinstance(entry, dict)
        entries.append(entry)
    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        return None
    return entries


def sort_key(entry: dict[str, object]) -> tuple[datetime, str]:
    raw = entry["timestamp"]
    assert isinstance(raw, str)
    try:
        stamp = parse_utc_timestamp(raw)
    except RegistryInputError:
        stamp = datetime.min.replace(tzinfo=timezone.utc)
    assert isinstance(entry["id"], str)
    return (stamp, entry["id"])


def run_record(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    existing: list[dict[str, object]] = []
    if path.is_file():
        entries = read_registry(path)
        if entries is None:
            raise RegistryInputError("decision_store_corrupt")
        existing = entries
    timestamp = inputs.get("timestamp")
    entry: dict[str, object] = {
        "id": inputs["decision_id"],
        "work_order_id": inputs["work_order_id"],
        "timestamp": timestamp if isinstance(timestamp, str) else utc_now(),
        "decision": inputs["decision"],
        "rationale": inputs["rationale"],
        "evidence_refs": inputs["evidence_refs"],
        "actor": inputs["actor"],
    }
    if not validate_entry(entry):
        raise RegistryInputError("decision_input_invalid")
    if any(previous["id"] == entry["id"] for previous in existing):
        raise RegistryInputError("decision_duplicate")
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write(compact_json(entry) + "\n")
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "record",
        "id": entry["id"],
        "status": "stored",
    }


def run_list(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    base: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "list",
        "reason": "replayed",
    }
    if not path.is_file():
        return {**base, "decisions": [], "reason": "store_missing"}
    entries = read_registry(path)
    if entries is None:
        raise RegistryInputError("decision_store_corrupt")
    decisions = sorted(entries, key=sort_key)
    return {**base, "decisions": decisions}


def run_get(inputs: dict[str, object]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    decision_id = str(inputs["decision_id"])
    base: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "get",
        "id": decision_id,
        "decision": None,
        "reason": "no_entry",
    }
    if not path.is_file():
        return {**base, "reason": "store_missing"}
    entries = read_registry(path)
    if entries is None:
        raise RegistryInputError("decision_store_corrupt")
    for entry in entries:
        if entry["id"] == decision_id:
            return {**base, "decision": entry, "reason": "found"}
    return base


def run(command: str, inputs: dict[str, object]) -> dict[str, object]:
    if command == "record":
        return run_record(inputs)
    if command == "list":
        return run_list(inputs)
    return run_get(inputs)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        command, inputs = parse_arguments(arguments)
        emit(run(command, inputs))
    except RegistryInputError as exc:
        emit(error_payload(exc.code))
        return 2
    except OSError:
        emit(error_payload("decision_store_unavailable"))
        return 1
    except Exception:
        emit(error_payload("decision_registry_failed"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
