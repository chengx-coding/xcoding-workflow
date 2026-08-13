#!/usr/bin/env python3
"""Bounded additive fact cache for confirmed small-task governance facts.

Fail-closed contract:

- Only confirmed facts (yes/no) are cacheable. ``unknown`` is never cached;
  a store carrying any unknown fact is refused.
- Every entry carries an evidence fingerprint over the bridge sha256, the
  fact-source identifiers, and the requested flags. Any fingerprint mismatch
  or new evidence is a miss (re-check).
- Corruption, carrier mismatch, or a missing store is a miss, never an
  answer. A hit returns only the exact confirmed facts that were stored
  under the matching fingerprint.

Carriers:

- ``session-file``: a JSON file in a session-scoped location owned by the
  tool session state. The file is bare session state (entries only) and is
  expected to die with the session.
- ``store``: a dedicated cache file managed by this script on behalf of the
  runtime owner. The file carries store metadata (``carrier``) asserting
  runtime ownership.

This script is an additive wrapper. It never changes classify.py behavior
and never invokes the classifier.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import plan_work_policy as policy


SCHEMA_VERSION = 1
CARRIERS = ("session-file", "store")
FACT_NAMES = policy.GOVERNANCE_FACTS
CONFIRMED_VALUES = frozenset({"yes", "no"})
SUBCOMMANDS = ("store", "get", "invalidate")
VALUE_OPTIONS = {
    "--carrier": "carrier",
    "--path": "path",
    "--bridge-sha256": "bridge_sha256",
    "--fact-sources": "fact_sources",
    "--requested-flags": "requested_flags",
    "--facts": "facts",
}
REQUIRED_BY_COMMAND: dict[str, frozenset[str]] = {
    "store": frozenset(
        {"carrier", "path", "bridge_sha256", "fact_sources", "requested_flags", "facts"}
    ),
    "get": frozenset({"carrier", "path", "bridge_sha256", "fact_sources", "requested_flags"}),
    "invalidate": frozenset({"carrier", "path", "bridge_sha256", "fact_sources", "requested_flags"}),
}


class CacheInputError(ValueError):
    """Strict invalid-input result returned by the fact cache."""

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


def parse_string_list(raw: str, code: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CacheInputError(code) from exc
    if (
        not isinstance(payload, list)
        or any(not isinstance(item, str) or not item for item in payload)
        or len(set(payload)) != len(payload)
    ):
        raise CacheInputError(code)
    return payload


def parse_facts(raw: str) -> dict[str, str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CacheInputError("cache_facts_invalid") from exc
    if not isinstance(payload, dict) or any(
        not isinstance(value, str) for value in payload.values()
    ):
        raise CacheInputError("cache_facts_invalid")
    if set(payload) != set(FACT_NAMES):
        raise CacheInputError("cache_facts_invalid")
    if any(value not in policy.VALUES[name] for name, value in payload.items()):
        raise CacheInputError("cache_facts_invalid")
    return {name: payload[name] for name in FACT_NAMES}


def parse_arguments(
    argv: Sequence[str],
) -> tuple[str, dict[str, str | list[str]]]:
    if not argv or argv[0] not in SUBCOMMANDS:
        raise CacheInputError("cache_input_invalid")
    command = argv[0]
    collected: dict[str, list[str]] = {name: [] for name in VALUE_OPTIONS.values()}
    index = 1
    while index < len(argv):
        option = argv[index]
        name = VALUE_OPTIONS.get(option)
        if name is None or index + 1 >= len(argv):
            raise CacheInputError("cache_input_invalid")
        collected[name].append(argv[index + 1])
        index += 2
    if any(len(values) > 1 for values in collected.values()):
        raise CacheInputError("cache_input_invalid")
    supplied = {name: values[0] for name, values in collected.items() if values}
    missing = REQUIRED_BY_COMMAND[command] - set(supplied)
    if missing:
        raise CacheInputError("cache_input_invalid")
    carrier = supplied["carrier"]
    if carrier not in CARRIERS:
        raise CacheInputError("cache_input_invalid")
    if not supplied["path"].strip():
        raise CacheInputError("cache_input_invalid")
    if not policy.SHA256_RE.fullmatch(supplied["bridge_sha256"]):
        raise CacheInputError("cache_input_invalid")
    try:
        parsed: dict[str, str | list[str]] = {
            "carrier": carrier,
            "path": supplied["path"],
            "bridge_sha256": supplied["bridge_sha256"],
            "fact_sources": parse_string_list(
                supplied["fact_sources"], "cache_input_invalid"
            ),
            "requested_flags": parse_string_list(
                supplied["requested_flags"], "cache_input_invalid"
            ),
        }
    except CacheInputError as exc:
        raise CacheInputError(exc.code) from exc
    if command == "store":
        parsed["facts"] = parse_facts(supplied["facts"])
    return command, parsed


def fingerprint(inputs: dict[str, str | list[str]]) -> str:
    canonical = {
        "bridge_sha256": inputs["bridge_sha256"],
        "fact_source_ids": sorted(inputs["fact_sources"]),
        "requested_flags": sorted(inputs["requested_flags"]),
    }
    return hashlib.sha256(compact_json(canonical).encode("utf-8")).hexdigest()


def validate_entry(entry: object) -> dict[str, str] | None:
    """Return the confirmed facts of a strict valid entry, else None."""
    if (
        not isinstance(entry, dict)
        or not isinstance(entry.get("fingerprint"), str)
        or len(entry["fingerprint"]) != 64
        or not isinstance(entry.get("facts"), dict)
    ):
        return None
    facts = entry["facts"]
    if (
        set(facts) != set(FACT_NAMES)
        or any(
            not isinstance(facts[name], str) or facts[name] not in CONFIRMED_VALUES
            for name in FACT_NAMES
        )
    ):
        return None
    return {name: facts[name] for name in FACT_NAMES}


def read_store(path: Path, carrier: str) -> list[dict[str, object]] | None:
    """Return entries for a valid readable store, else None (corrupt)."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if payload.get("carrier") not in {None, carrier}:
        return None
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return None
    if any(validate_entry(entry) is None for entry in entries):
        return None
    return [entry for entry in entries if isinstance(entry, dict)]


def write_store(path: Path, carrier: str, entries: list[dict[str, object]]) -> None:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "entries": entries,
    }
    if carrier == "store":
        payload["carrier"] = "store"
    content = compact_json(payload) + "\n"
    temporary = path.with_name(f".{path.name}.fact-cache.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def entry_payload(entry: dict[str, object]) -> dict[str, object]:
    return {
        "fingerprint": entry["fingerprint"],
        "facts": entry["facts"],
    }


def run_store(inputs: dict[str, str | list[str]]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    facts = inputs["facts"]
    assert isinstance(facts, dict)
    unknowns = [name for name in FACT_NAMES if facts[name] == "unknown"]
    if unknowns:
        raise CacheInputError("store_facts_unknown")
    entry_fingerprint = fingerprint(inputs)
    existing: list[dict[str, object]]
    if path.is_file():
        entries = read_store(path, str(inputs["carrier"]))
        if entries is None:
            raise CacheInputError("cache_store_corrupt")
        existing = entries
    else:
        existing = []
    for entry in existing:
        if entry.get("fingerprint") != entry_fingerprint:
            continue
        if entry.get("facts") != facts:
            raise CacheInputError("cache_store_conflict")
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "command": "store",
            "carrier": inputs["carrier"],
            "fingerprint": entry_fingerprint,
            "facts": facts,
            "status": "stored",
            "changed": False,
        }
    stored = entry_payload({"fingerprint": entry_fingerprint, "facts": facts})
    write_store(path, str(inputs["carrier"]), [*existing, stored])
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "store",
        "carrier": inputs["carrier"],
        "fingerprint": entry_fingerprint,
        "facts": facts,
        "status": "stored",
        "changed": True,
    }


def run_get(inputs: dict[str, str | list[str]]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    entry_fingerprint = fingerprint(inputs)
    base: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "hit": False,
        "facts": None,
    }
    if not path.is_file():
        return {**base, "reason": "store_missing"}
    entries = read_store(path, str(inputs["carrier"]))
    if entries is None:
        return {**base, "reason": "store_corrupt"}
    for entry in entries:
        if entry.get("fingerprint") != entry_fingerprint:
            continue
        facts = validate_entry(entry)
        if facts is None:
            return {**base, "reason": "store_corrupt"}
        return {**base, "hit": True, "facts": facts, "reason": "cache_hit"}
    return {**base, "reason": "no_entry"}


def run_invalidate(inputs: dict[str, str | list[str]]) -> dict[str, object]:
    path = Path(str(inputs["path"]))
    entry_fingerprint = fingerprint(inputs)
    base: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "invalidate",
        "carrier": inputs["carrier"],
        "fingerprint": entry_fingerprint,
        "removed": False,
    }
    if not path.is_file():
        return {**base, "reason": "store_missing"}
    entries = read_store(path, str(inputs["carrier"]))
    if entries is None:
        path.unlink()
        return {**base, "removed": True, "reason": "store_corrupt_removed"}
    kept = [entry for entry in entries if entry.get("fingerprint") != entry_fingerprint]
    if len(kept) == len(entries):
        return {**base, "reason": "no_entry"}
    write_store(path, str(inputs["carrier"]), kept)
    return {**base, "removed": True, "reason": "entry_removed"}


def run(command: str, inputs: dict[str, str | list[str]]) -> dict[str, object]:
    if command == "store":
        return run_store(inputs)
    if command == "get":
        return run_get(inputs)
    return run_invalidate(inputs)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        command, inputs = parse_arguments(arguments)
        emit(run(command, inputs))
    except CacheInputError as exc:
        emit(error_payload(exc.code))
        return 2
    except OSError:
        emit(error_payload("cache_store_unavailable"))
        return 1
    except Exception:
        emit(error_payload("fact_cache_failed"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
