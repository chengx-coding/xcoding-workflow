"""Deterministic integrity receipts without authentication claims."""

from __future__ import annotations

from typing import Any, Mapping

from .json_codec import canonical_digest
from .errors import fail
from .model import require_exact_fields, require_object, require_sha256, require_string
from .paths import validate_relative_path, validate_slug


INTEGRITY_CLAIMS = {
    "execution_attestation": False,
    "integrity_and_audit_linkage_only": True,
    "publisher_authentication": False,
}


def prepare_receipt(
    envelope: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the deterministic receipt returned by authoritative prepare."""
    return {
        "schema_version": 1,
        "kind": "xc-delegation-prepare-receipt/v1",
        "envelope_sha256": canonical_digest(envelope),
        "adapter": {
            "id": adapter_statement["adapter_id"],
            "version": adapter_statement["adapter_version"],
            "mode": adapter_statement["mode"],
        },
        "capability_resolution_sha256": canonical_digest(envelope["capabilities"]),
        "claims": dict(INTEGRITY_CLAIMS),
    }


def detached_receipt(
    *,
    envelope_sha256: str,
    prepare_receipt_sha256: str,
    adapter_id: str,
    adapter_version: str,
    security_mode: str,
    capability_resolution: Mapping[str, Any],
    context_sha256: str,
    artifact_sha256: Mapping[str, str],
    terminal: Mapping[str, Any],
    artifact_failures: list[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Build terminal audit linkage; callers persist it outside the envelope."""
    require_sha256(envelope_sha256, field="envelope_sha256")
    require_sha256(prepare_receipt_sha256, field="prepare_receipt_sha256")
    require_sha256(context_sha256, field="context_sha256")
    validate_slug(adapter_id, field="adapter_id")
    require_string(adapter_version, field="adapter_version", maximum=128)
    if security_mode not in {"enforced", "validated-only"}:
        fail("security_mode_invalid", "receipt", "receipt security mode is invalid")
    terminal_value = require_object(terminal, field="terminal")
    require_exact_fields(
        terminal_value,
        {"authority_id", "node_id", "attempt", "operation", "result_sha256"},
        label="terminal",
    )
    if terminal_value["operation"] not in {"block", "complete", "fail"}:
        fail("terminal_operation_invalid", "receipt", "terminal operation is unsupported")
    require_string(terminal_value["authority_id"], field="terminal.authority_id", maximum=128)
    require_string(terminal_value["node_id"], field="terminal.node_id", maximum=512)
    if isinstance(terminal_value["attempt"], bool) or not isinstance(terminal_value["attempt"], int) or terminal_value["attempt"] < 1:
        fail("terminal_attempt_invalid", "receipt", "terminal attempt must be positive")
    require_sha256(terminal_value["result_sha256"], field="terminal.result_sha256")
    artifacts = []
    for path in sorted(artifact_sha256):
        validate_relative_path(path, field="artifact path")
        artifacts.append(
            {
                "path": path,
                "sha256": require_sha256(
                    artifact_sha256[path],
                    field="artifact_sha256",
                ),
            }
        )
    failures = []
    for index, raw in enumerate(artifact_failures or []):
        if not isinstance(raw, Mapping):
            fail("artifact_failure_invalid", "receipt", f"artifact failure {index} is invalid")
        path = validate_relative_path(raw.get("path"), field="artifact failure path")
        code = require_string(raw.get("code"), field="artifact failure code", maximum=128)
        reason = require_string(raw.get("reason"), field="artifact failure reason", maximum=256)
        failures.append({"path": path, "code": code, "reason": reason})
    failures.sort(key=lambda item: item["path"])
    return {
        "schema_version": 1,
        "kind": "xc-delegation-detached-receipt/v1",
        "envelope_sha256": envelope_sha256,
        "prepare_receipt_sha256": prepare_receipt_sha256,
        "adapter": {
            "id": adapter_id,
            "version": adapter_version,
            "security_mode": security_mode,
        },
        "capability_resolution_sha256": canonical_digest(capability_resolution),
        "context_sha256": context_sha256,
        "artifacts": artifacts,
        "artifact_failures": failures,
        "terminal": dict(terminal_value),
        "claims": dict(INTEGRITY_CLAIMS),
    }


__all__ = ["INTEGRITY_CLAIMS", "detached_receipt", "prepare_receipt"]
