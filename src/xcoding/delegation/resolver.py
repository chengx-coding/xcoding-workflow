"""Logical owning-Skill worker profile resolution."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, Mapping

from .errors import fail
from .json_codec import canonical_digest, parse_json_bytes, sha256_hex
from .model import RESOLVED_PROFILE_KIND, require_exact_fields, require_object, require_sha256, validate_profile
from .overlay import apply_overlay, validate_overlay
from .paths import (
    PinnedPathError,
    delete_pinned_file,
    _is_link_or_junction,
    load_strict_json_path,
    pinned_identity,
    profile_relative_path,
    stable_read_bytes,
    validate_relative_path,
    validate_slug,
)


MAX_INSTRUCTION_BYTES = 16 * 1024
MAX_TOTAL_INSTRUCTION_BYTES = 64 * 1024
RESOLVED_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "profile",
        "base_profile_sha256",
        "resolved_profile_sha256",
        "resources",
        "overlay",
    }
)


def _read_external_json(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        fail("path_unsafe", "overlay", "dynamic overlay path must be absolute")
    return load_strict_json_path(path.parent, path.name)


def resolve_profile(
    skill_root: Path | str,
    profile_id: str,
    *,
    dynamic_overlay: Path | str | None = None,
    expected_target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a logical profile only within its owning Skill root."""
    root = Path(skill_root)
    if not root.is_absolute():
        fail("path_unsafe", "resolve", "skill_root must be absolute")
    validate_slug(profile_id, field="profile_id")
    raw_profile = load_strict_json_path(root, profile_relative_path(profile_id))
    profile = validate_profile(raw_profile)
    if root.name != profile["owner_skill"]:
        fail("owner_skill_mismatch", "resolve", "profile owner does not match the supplied Skill root")
    if profile["profile_id"] != profile_id:
        fail("profile_id_mismatch", "resolve", "profile content does not match the requested logical identifier")
    base_digest = canonical_digest(profile)

    overlay_record: dict[str, Any] | None = None
    if dynamic_overlay is not None:
        overlay_path = Path(dynamic_overlay)
        raw_overlay = _read_external_json(overlay_path)
        overlay = validate_overlay(raw_overlay, expected_target=expected_target)
        profile = apply_overlay(profile, overlay)
        overlay_record = {
            "sha256": canonical_digest(overlay),
            "expires_at": overlay["expires_at"],
            "target": dict(overlay["target"]),
            "cleanup_required": True,
        }

    resources: list[dict[str, str]] = []
    total = 0
    for relative in profile["instruction_resources"]:
        data = stable_read_bytes(root, relative, max_bytes=MAX_INSTRUCTION_BYTES)
        if data.startswith(b"\xef\xbb\xbf"):
            fail("resource_bom_forbidden", "resolve", "instruction resources must not use a UTF-8 BOM")
        try:
            content = data.decode("utf-8")
        except UnicodeError:
            fail("resource_encoding_invalid", "resolve", "instruction resources must be UTF-8")
        if unicodedata.normalize("NFC", content) != content:
            fail("resource_not_nfc", "resolve", "instruction resources must use Unicode NFC")
        total += len(data)
        if total > MAX_TOTAL_INSTRUCTION_BYTES:
            fail("resource_limit_exceeded", "resolve", "instruction resources exceed the aggregate byte limit")
        resources.append({"path": relative, "sha256": sha256_hex(data), "content": content})

    return {
        "schema_version": 1,
        "kind": RESOLVED_PROFILE_KIND,
        "profile": profile,
        "base_profile_sha256": base_digest,
        "resolved_profile_sha256": canonical_digest(profile),
        "resources": resources,
        "overlay": overlay_record,
    }


def validate_resolved_profile(value: object) -> dict[str, Any]:
    resolved = require_object(value, field="resolved_profile")
    require_exact_fields(resolved, RESOLVED_FIELDS, label="resolved_profile")
    if resolved["schema_version"] != 1 or resolved["kind"] != RESOLVED_PROFILE_KIND:
        fail("schema_version_unsupported", "compile", "resolved profile kind is unsupported")
    profile = validate_profile(resolved["profile"])
    base_digest = require_sha256(resolved["base_profile_sha256"], field="base_profile_sha256")
    resolved_digest = require_sha256(resolved["resolved_profile_sha256"], field="resolved_profile_sha256")
    if canonical_digest(profile) != resolved_digest:
        fail("digest_mismatch", "compile", "resolved profile digest does not match its content")
    raw_resources = resolved["resources"]
    if not isinstance(raw_resources, list) or len(raw_resources) != len(profile["instruction_resources"]):
        fail("resource_set_mismatch", "compile", "resolved instruction resource set is incomplete")
    resources: list[dict[str, str]] = []
    seen: list[str] = []
    for index, raw in enumerate(raw_resources):
        item = require_object(raw, field=f"resources[{index}]")
        require_exact_fields(item, {"path", "sha256", "content"}, label=f"resources[{index}]")
        path = validate_relative_path(item["path"], field=f"resources[{index}].path")
        digest = require_sha256(item["sha256"], field=f"resources[{index}].sha256")
        content = item["content"]
        if not isinstance(content, str):
            fail("schema_type_invalid", "compile", "resolved instruction content must be a string")
        if sha256_hex(content.encode("utf-8")) != digest:
            fail("digest_mismatch", "compile", "instruction resource digest does not match its content")
        seen.append(path)
        resources.append({"path": path, "sha256": digest, "content": content})
    if seen != profile["instruction_resources"]:
        fail("resource_set_mismatch", "compile", "resolved instruction resources do not match the profile")
    overlay = resolved["overlay"]
    if overlay is not None:
        overlay = require_object(overlay, field="overlay")
        require_exact_fields(
            overlay,
            {"sha256", "expires_at", "target", "cleanup_required"},
            label="overlay",
        )
        require_sha256(overlay["sha256"], field="overlay.sha256")
        if overlay["cleanup_required"] is not True:
            fail("overlay_cleanup_invalid", "compile", "dynamic overlay must require cleanup")
        target = require_object(overlay["target"], field="overlay.target")
        require_exact_fields(target, {"work_order_id", "node_id", "attempt"}, label="overlay.target")
        if not isinstance(overlay["expires_at"], str) or not overlay["expires_at"].endswith("Z"):
            fail("overlay_expiry_invalid", "compile", "resolved overlay expiry must be UTC")
    elif base_digest != resolved_digest:
        fail("digest_mismatch", "compile", "base and resolved profile digests must match without an overlay")
    return {
        "schema_version": 1,
        "kind": RESOLVED_PROFILE_KIND,
        "profile": profile,
        "base_profile_sha256": base_digest,
        "resolved_profile_sha256": resolved_digest,
        "resources": resources,
        "overlay": overlay,
    }


def cleanup_dynamic_overlay(
    path: Path | str,
    expected_sha256: str,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    """Delete only the validated overlay instance and verify its removal.

    ``expected_identity`` is captured by the trusted gateway before
    preparation.  Supplying it pins cleanup to that exact directory entry;
    a replacement containing identical bytes is still a mismatch and is
    deliberately left in place for recovery.
    """
    overlay_path = Path(path)
    require_sha256(expected_sha256, field="expected_sha256")
    if not overlay_path.is_absolute():
        fail("path_unsafe", "overlay-cleanup", "dynamic overlay path must be absolute")
    relative = overlay_path.name
    parent = overlay_path.parent
    try:
        identity = pinned_identity(parent, relative)
    except PinnedPathError as exc:
        fail(
            "overlay_cleanup_failed",
            "overlay-cleanup",
            "dynamic overlay could not be opened safely",
            remediation_category="recovery",
            error=exc.code,
        )
    if identity is None:
        fail(
            "overlay_cleanup_failed",
            "overlay-cleanup",
            "dynamic overlay is unavailable",
            remediation_category="recovery",
        )
    if expected_identity is not None and identity != expected_identity:
        fail(
            "overlay_cleanup_mismatch",
            "overlay-cleanup",
            "dynamic overlay identity changed before cleanup",
            remediation_category="recovery",
        )
    pinned = expected_identity if expected_identity is not None else identity
    data = stable_read_bytes(parent, relative, expected_identity=pinned)
    raw = parse_json_bytes(data)
    assert isinstance(raw, dict)
    if canonical_digest(raw) != expected_sha256:
        fail("overlay_cleanup_mismatch", "overlay-cleanup", "overlay changed before cleanup")
    try:
        delete_pinned_file(parent, relative, pinned)
    except PinnedPathError as exc:
        if exc.code == "resource_changed":
            fail("overlay_cleanup_mismatch", "overlay-cleanup", "overlay changed before cleanup")
        fail(
            "overlay_cleanup_failed",
            "overlay-cleanup",
            "dynamic overlay could not be removed",
            remediation_category="recovery",
        )
    if overlay_path.exists() or _is_link_or_junction(overlay_path):
        fail(
            "overlay_cleanup_failed",
            "overlay-cleanup",
            "dynamic overlay remains after cleanup",
            remediation_category="recovery",
        )


__all__ = [
    "MAX_INSTRUCTION_BYTES",
    "MAX_TOTAL_INSTRUCTION_BYTES",
    "RESOLVED_FIELDS",
    "cleanup_dynamic_overlay",
    "resolve_profile",
    "validate_resolved_profile",
]
