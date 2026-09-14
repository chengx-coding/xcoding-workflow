"""Fail-closed dynamic narrowing overlays for worker profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .errors import fail
from .model import (
    CAPABILITY_IDS,
    require_array,
    require_exact_fields,
    require_integer,
    require_object,
    require_string,
)
from .paths import validate_slug


OVERLAY_KIND = "xc-worker-profile-overlay/v1"
OVERLAY_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "owner_skill",
        "profile_id",
        "target",
        "expires_at",
        "description",
        "optional_capabilities",
        "context_binding_ids",
        "output_ids",
        "limits",
    }
)


def _sorted_slugs(value: object, *, field: str, maximum: int) -> list[str]:
    raw = require_array(value, field=field, maximum=maximum)
    items = [validate_slug(item, field=f"{field}[]") for item in raw]
    if items != sorted(set(items)):
        fail("schema_order_invalid", "overlay", f"{field} must be sorted and unique")
    return items


def _parse_expiry(value: object) -> datetime:
    text = require_string(value, field="expires_at", maximum=40)
    if not text.endswith("Z"):
        fail("overlay_expiry_invalid", "overlay", "overlay expiry must be UTC with a Z suffix")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        fail("overlay_expiry_invalid", "overlay", "overlay expiry is not an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        fail("overlay_expiry_invalid", "overlay", "overlay expiry must be UTC")
    return parsed


def validate_overlay(
    value: object,
    *,
    expected_target: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    overlay = require_object(value, field="overlay")
    require_exact_fields(overlay, OVERLAY_FIELDS, label="overlay")
    if overlay["schema_version"] != 1 or overlay["kind"] != OVERLAY_KIND:
        fail("schema_version_unsupported", "overlay", "overlay must use xc-worker-profile-overlay/v1")
    owner = validate_slug(overlay["owner_skill"], field="owner_skill", prefix="xc-")
    profile_id = validate_slug(overlay["profile_id"], field="profile_id")
    target = require_object(overlay["target"], field="target")
    require_exact_fields(target, {"work_order_id", "node_id", "attempt"}, label="target")
    work_order_id = require_string(target["work_order_id"], field="target.work_order_id", maximum=160)
    node_id = require_string(target["node_id"], field="target.node_id", maximum=512)
    attempt = require_integer(target["attempt"], field="target.attempt", minimum=1, maximum=1_000_000)
    normalized_target = {
        "work_order_id": work_order_id,
        "node_id": node_id,
        "attempt": attempt,
    }
    if expected_target is not None and normalized_target != dict(expected_target):
        fail("overlay_target_mismatch", "overlay", "overlay is not bound to the dispatched node attempt")
    expiry = _parse_expiry(overlay["expires_at"])
    current = now or datetime.now(timezone.utc)
    if expiry <= current:
        fail(
            "overlay_expired",
            "overlay",
            "dynamic overlay has expired",
            remediation_category="runtime-state",
        )
    description = require_string(overlay["description"], field="description", maximum=4096)
    raw_optional = require_array(
        overlay["optional_capabilities"],
        field="optional_capabilities",
        maximum=10,
    )
    optional = [
        require_string(item, field="optional_capabilities[]", maximum=64)
        for item in raw_optional
    ]
    if optional != sorted(set(optional)) or any(item not in CAPABILITY_IDS for item in optional):
        fail(
            "schema_value_invalid",
            "overlay",
            "optional_capabilities must be sorted unique v1 capability IDs",
        )
    context = _sorted_slugs(overlay["context_binding_ids"], field="context_binding_ids", maximum=64)
    outputs = _sorted_slugs(overlay["output_ids"], field="output_ids", maximum=32)
    limits = require_object(overlay["limits"], field="limits")
    require_exact_fields(limits, {"context_max_bytes"}, label="limits")
    context_max = require_integer(limits["context_max_bytes"], field="limits.context_max_bytes", maximum=65536)
    return {
        "schema_version": 1,
        "kind": OVERLAY_KIND,
        "owner_skill": owner,
        "profile_id": profile_id,
        "target": normalized_target,
        "expires_at": overlay["expires_at"],
        "description": description,
        "optional_capabilities": optional,
        "context_binding_ids": context,
        "output_ids": outputs,
        "limits": {"context_max_bytes": context_max},
    }


def apply_overlay(profile: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Apply only monotonic narrowing; reject every attempted expansion."""
    if overlay["owner_skill"] != profile["owner_skill"] or overlay["profile_id"] != profile["profile_id"]:
        fail("overlay_profile_mismatch", "overlay", "overlay does not belong to the resolved profile")
    if not str(profile["description"]).startswith(str(overlay["description"])):
        fail(
            "unsafe_overlay_widening",
            "overlay",
            "overlay description must be a literal prefix shortening",
        )

    required_capabilities = {
        item["id"] for item in profile["capabilities"] if item["requirement"] == "required"
    }
    available_optional = {
        item["id"] for item in profile["capabilities"] if item["requirement"] == "optional"
    }
    selected_optional = set(overlay["optional_capabilities"])
    if not selected_optional <= available_optional:
        fail("unsafe_overlay_widening", "overlay", "overlay requested a capability outside the optional profile set")
    capabilities = [
        dict(item)
        for item in profile["capabilities"]
        if item["id"] in required_capabilities or item["id"] in selected_optional
    ]

    context_items = {item["id"]: item for item in profile["context"]["bindings"]}
    selected_context = set(overlay["context_binding_ids"])
    if not selected_context <= context_items.keys():
        fail("unsafe_overlay_widening", "overlay", "overlay requested an undeclared context binding")
    required_context = {identifier for identifier, item in context_items.items() if item["required"]}
    if not required_context <= selected_context:
        fail("unsafe_overlay_narrowing", "overlay", "overlay cannot remove required context")
    context_limit = overlay["limits"]["context_max_bytes"]
    if context_limit > profile["context"]["max_bytes"]:
        fail("unsafe_overlay_widening", "overlay", "overlay cannot increase the context byte limit")

    output_items = {item["id"]: item for item in profile["outputs"]["artifacts"]}
    selected_outputs = set(overlay["output_ids"])
    if not selected_outputs <= output_items.keys():
        fail("unsafe_overlay_widening", "overlay", "overlay requested an undeclared output")
    required_outputs = {identifier for identifier, item in output_items.items() if item["required"]}
    if not required_outputs <= selected_outputs:
        fail("unsafe_overlay_narrowing", "overlay", "overlay cannot remove required outputs")

    narrowed = dict(profile)
    narrowed["description"] = overlay["description"]
    narrowed["capabilities"] = capabilities
    narrowed["context"] = {
        "bindings": [dict(context_items[key]) for key in sorted(selected_context)],
        "max_bytes": context_limit,
    }
    narrowed["outputs"] = {
        "artifacts": [dict(output_items[key]) for key in sorted(selected_outputs)],
        "result_fields": list(profile["outputs"]["result_fields"]),
    }
    return narrowed


__all__ = ["OVERLAY_FIELDS", "OVERLAY_KIND", "apply_overlay", "validate_overlay"]
