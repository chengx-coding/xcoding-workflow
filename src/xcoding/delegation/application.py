"""Public delegation use cases shared by CLI and trusted host adapters."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .adapters import load_adapter_statement
from .compiler import _compile_prepared_envelope, compile_envelope
from .errors import DelegationError, fail
from .json_codec import canonical_digest, canonical_json_bytes, parse_json_bytes
from .migration import scan_legacy
from .model import (
    validate_adapter_statement,
    validate_node_packet,
    validate_node_profile_ref,
)
from .paths import _is_link_or_junction, stable_read_bytes
from .policy import validate_caller_constraints, validate_project_policy
from .receipt import prepare_receipt
from .resolver import resolve_profile, validate_resolved_profile


def load_input_document(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = (Path.cwd() / target).absolute()
    value = parse_json_bytes(stable_read_bytes(target.parent, target.name))
    assert isinstance(value, dict)
    return value


def _bounded_document(value: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the same bounds to trusted in-memory API inputs as CLI files."""
    parsed = parse_json_bytes(canonical_json_bytes(value))
    assert isinstance(parsed, dict)
    return parsed


def write_canonical_output(path: Path | str, value: Mapping[str, Any]) -> Path:
    """Atomically replace one caller-selected regular output file."""
    target = Path(path)
    if not target.is_absolute():
        target = (Path.cwd() / target).absolute()
    parent = target.parent
    if _is_link_or_junction(parent):
        fail("output_path_unsafe", "write", "output parent must not be a link or junction")
    try:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            fail("output_path_unsafe", "write", "output parent must be an existing directory")
        if target.exists() and (_is_link_or_junction(target) or not stat.S_ISREG(target.lstat().st_mode)):
            fail("output_path_unsafe", "write", "output target must be absent or a regular file")
    except OSError:
        fail("output_path_unavailable", "write", "output path is unavailable")
    temporary_path: Path | None = None
    try:
        descriptor, raw_temporary = tempfile.mkstemp(
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".xcoding-delegation-tmp",
        )
        temporary_path = Path(raw_temporary)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    except DelegationError:
        raise
    except OSError:
        fail("output_write_failed", "write", "canonical output could not be persisted", remediation_category="environment")
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return target


def _validated_compile_inputs(
    *,
    resolved_profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    return (
        validate_resolved_profile(_bounded_document(resolved_profile)),
        validate_node_packet(_bounded_document(node_packet)),
        validate_node_profile_ref(_bounded_document(node_profile_ref)),
        validate_project_policy(_bounded_document(project_policy)),
        validate_adapter_statement(_bounded_document(adapter_statement)),
        validate_caller_constraints(_bounded_document(caller_constraints)),
    )


def compile_diagnostic(
    *,
    resolved_profile: Mapping[str, Any],
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_statement: Mapping[str, Any],
    caller_constraints: Mapping[str, Any],
) -> dict[str, Any]:
    resolved, node, reference, project, adapter, caller = _validated_compile_inputs(
        resolved_profile=resolved_profile,
        node_packet=node_packet,
        node_profile_ref=node_profile_ref,
        project_policy=project_policy,
        adapter_statement=adapter_statement,
        caller_constraints=caller_constraints,
    )
    return compile_envelope(
        resolved,
        node,
        reference,
        project,
        adapter,
        caller,
    )


def prepare(
    *,
    skill_root: Path | str,
    profile_id: str,
    node_packet: Mapping[str, Any],
    node_profile_ref: Mapping[str, Any],
    project_policy: Mapping[str, Any],
    adapter_id: str,
    caller_constraints: Mapping[str, Any],
    dynamic_overlay: Path | str | None = None,
) -> dict[str, Any]:
    """The only dispatch-authoritative v1 operation."""
    node = validate_node_packet(_bounded_document(node_packet))
    reference = validate_node_profile_ref(_bounded_document(node_profile_ref))
    expected_target = {
        "work_order_id": node["work_order_id"],
        "node_id": node["node_id"],
        "attempt": node["attempt"],
    }
    resolved = resolve_profile(
        skill_root,
        profile_id,
        dynamic_overlay=dynamic_overlay,
        expected_target=expected_target,
    )
    project = validate_project_policy(_bounded_document(project_policy))
    caller = validate_caller_constraints(_bounded_document(caller_constraints))
    adapter = load_adapter_statement(adapter_id)
    if reference["owner_skill"] != Path(skill_root).name or reference["profile_id"] != profile_id:
        fail("profile_reference_mismatch", "prepare", "requested logical profile does not match the node reference")
    envelope = _compile_prepared_envelope(
        resolved,
        node,
        reference,
        project,
        adapter,
        caller,
    )
    receipt = prepare_receipt(envelope, adapter)
    return {
        "envelope": envelope,
        "envelope_sha256": canonical_digest(envelope),
        "prepare_receipt": receipt,
        "prepare_receipt_sha256": canonical_digest(receipt),
        "overlay_cleanup": None
        if resolved["overlay"] is None
        else {
            "required": True,
            "sha256": resolved["overlay"]["sha256"],
        },
    }


__all__ = [
    "compile_diagnostic",
    "load_input_document",
    "prepare",
    "resolve_profile",
    "scan_legacy",
    "write_canonical_output",
]
