#!/usr/bin/env python3
"""Validate an adaptive plan receipt against its request and bridge bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import plan_work_policy as policy


def fail(code: str) -> int:
    print(
        json.dumps(
            {"schema_version": 1, "ok": False, "error": {"code": code}},
            separators=(",", ":"),
        )
    )
    return 2


def validate_receipt(
    receipt: object,
    request: str,
    bridge_bytes: bytes,
) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(receipt, dict) or receipt.get("schema_version") != 1:
        return None, "invalid_plan_receipt"
    actual_bridge = hashlib.sha256(bridge_bytes).hexdigest()
    try:
        nested = receipt["facts"]
        governance = nested["governance"]
        task = nested["task"]
        facts = {
            **{name: governance[name] for name in policy.GOVERNANCE_FACTS},
            "bridge_policy": nested["bridge_policy"],
            **{name: task[name] for name in policy.TASK_FACTS},
            "pace": receipt["pace"],
            "mode": receipt["mode"],
            "request": request,
            "bridge_sha256": actual_bridge,
        }
        expected = policy.build_plan(facts)["plan_receipt"]
    except (KeyError, TypeError, policy.PlanningInputError):
        return None, "invalid_plan_receipt"
    if receipt != expected:
        if receipt.get("request_sha256") != expected.get("request_sha256"):
            return None, "plan_request_mismatch"
        if receipt.get("bridge_sha256") != expected.get("bridge_sha256"):
            return None, "plan_bridge_mismatch"
        return None, "plan_policy_mismatch"
    return expected, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-json", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--bridge", required=True)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt_json)
    except json.JSONDecodeError:
        return fail("invalid_plan_receipt")
    bridge = Path(args.bridge)
    try:
        bridge_bytes = bridge.read_bytes()
    except OSError:
        return fail("plan_bridge_unavailable")
    expected, error = validate_receipt(receipt, args.request, bridge_bytes)
    if error is not None or expected is None:
        return fail(error or "invalid_plan_receipt")
    print(
        json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "plan_id": expected["plan_id"],
                "request_sha256": expected["request_sha256"],
                "bridge_sha256": expected["bridge_sha256"],
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
