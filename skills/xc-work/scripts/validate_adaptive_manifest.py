#!/usr/bin/env python3
"""Validate finalizer sources against an adaptive plan's required nodes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from validate_plan_receipt import validate_receipt

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def fail(code: str, keys: list[str] | None = None) -> int:
    emit(
        {
            "schema_version": 1,
            "ok": False,
            "error": {"code": code, "keys": keys or []},
        }
    )
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-json", required=True)
    parser.add_argument("--source-map-json", required=True)
    parser.add_argument("--packet-json", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--bridge", required=True)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt_json)
        source_map = json.loads(args.source_map_json)
        packet_payload = json.loads(args.packet_json)
    except json.JSONDecodeError:
        return fail("invalid_adaptive_manifest")
    try:
        bridge_bytes = Path(args.bridge).read_bytes()
    except OSError:
        return fail("plan_bridge_unavailable")
    receipt, receipt_error = validate_receipt(
        receipt,
        args.request,
        bridge_bytes,
    )
    if receipt_error is not None or receipt is None:
        return fail(receipt_error or "invalid_plan_receipt")
    if (
        not SHA256_RE.fullmatch(str(receipt.get("plan_id", "")))
        or not isinstance(receipt.get("required_nodes"), list)
        or not isinstance(source_map, dict)
        or not isinstance(packet_payload, dict)
    ):
        return fail("invalid_adaptive_manifest")
    packet = packet_payload.get("packet")
    if not isinstance(packet, dict):
        return fail("invalid_adaptive_manifest")
    blackboard = packet.get("blackboard")
    categories = packet.get("source_categories")
    target = packet.get("target")
    if (
        not isinstance(blackboard, list)
        or not isinstance(categories, list)
        or not isinstance(target, dict)
        or target.get("role") != "work-order-finalize"
        or target.get("logical_key") != "finalize"
    ):
        return fail("invalid_adaptive_manifest")
    selected_plan_ids = [
        item.get("value")
        for item in blackboard
        if isinstance(item, dict) and item.get("key") == "work_order.plan_id"
    ]
    if selected_plan_ids != [receipt["plan_id"]]:
        return fail("stale_plan_id")
    packet_categories: dict[str, list[dict[str, object]]] = {}
    for category in categories:
        if not isinstance(category, dict) or not isinstance(category.get("sources"), list):
            return fail("invalid_adaptive_manifest")
        name = category.get("name")
        if not isinstance(name, str) or not name or name in packet_categories:
            return fail("invalid_adaptive_manifest")
        projected_sources: list[dict[str, object]] = []
        for source in category["sources"]:
            if not isinstance(source, dict) or not isinstance(source.get("node_id"), str):
                return fail("invalid_adaptive_manifest")
            projected_sources.append(source)
        packet_categories[name] = projected_sources

    required: list[dict[str, object]] = []
    for item in receipt["required_nodes"]:
        if not isinstance(item, dict):
            return fail("invalid_adaptive_manifest")
        key = item.get("logical_key")
        role = item.get("role")
        artifact_min = item.get("artifact_min")
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(role, str)
            or not role
            or not isinstance(artifact_min, int)
            or artifact_min < 0
        ):
            return fail("invalid_adaptive_manifest")
        if role != "finalizer":
            required.append(item)

    expected_keys = [str(item["logical_key"]) for item in required]
    if not expected_keys:
        return fail("empty_required_manifest")
    if len(expected_keys) != len(set(expected_keys)):
        return fail("duplicate_required_logical_key", expected_keys)
    actual_keys = list(source_map)
    missing = [key for key in expected_keys if key not in source_map]
    extra = [key for key in actual_keys if key not in set(expected_keys)]
    if missing:
        return fail("missing_required_source", missing)
    if extra:
        return fail("unexpected_source", extra)
    expected_categories = [f"plan-{key}" for key in expected_keys]
    missing_categories = [
        name for name in expected_categories if name not in packet_categories
    ]
    extra_categories = [
        name for name in packet_categories if name not in set(expected_categories)
    ]
    if missing_categories:
        return fail("missing_required_category", missing_categories)
    if extra_categories:
        return fail("unexpected_category", extra_categories)

    source_ids: list[str] = []
    artifact_min = 0
    for item in required:
        key = str(item["logical_key"])
        record = source_map[key]
        if not isinstance(record, dict):
            return fail("invalid_source_record", [key])
        node_id = record.get("node_id")
        if (
            not isinstance(node_id, str)
            or not node_id
            or set(record) != {"node_id"}
        ):
            return fail("invalid_source_record", [key])
        category_sources = packet_categories[f"plan-{key}"]
        if len(category_sources) != 1:
            return fail("invalid_category_cardinality", [key])
        projected = category_sources[0]
        artifacts = projected.get("artifacts", [])
        if (
            projected.get("node_id") != node_id
            or projected.get("logical_key") != key
            or projected.get("role") != item["role"]
            or projected.get("status") != "succeeded"
            or not isinstance(artifacts, list)
            or len(artifacts) < int(item["artifact_min"])
        ):
            return fail("invalid_packet_source", [key])
        expected_scope = item.get("verification_scope")
        if expected_scope and not (
            key == f"verification-{expected_scope}"
            or (
                key.startswith("implementation-")
                and expected_scope == "focused"
            )
        ):
            return fail("invalid_verification_binding", [key])
        source_ids.append(node_id)
        artifact_min += int(item["artifact_min"])
    if len(source_ids) != len(set(source_ids)):
        return fail("duplicate_source_id", source_ids)
    emit(
        {
            "schema_version": 1,
            "ok": True,
            "plan_id": receipt["plan_id"],
            "source_ids": source_ids,
            "min_sources": len(source_ids),
            "artifact_min": artifact_min,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
