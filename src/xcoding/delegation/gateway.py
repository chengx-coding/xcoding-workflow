"""Trusted same-process gateway for profile dispatch and terminal cleanup.

The gateway is deliberately an application-facing helper rather than a new
runtime transport.  It keeps host-only state (the exact overlay path and
artifact bindings) outside the worker envelope, delegates terminal mutation to
``TerminalBroker``, and guarantees that an overlay cleanup attempt follows
every authenticated terminal call.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from . import application
from .errors import DelegationError, fail
from .json_codec import canonical_digest
from .paths import pinned_identity, stable_read_bytes
from .receipt import detached_receipt
from .resolver import cleanup_dynamic_overlay
from ..runtime.terminal import TerminalAuthorityError, TerminalBroker, TerminalCapability


@dataclass
class GatewaySession:
    """Host-only state for one prepared node attempt.

    The session is intentionally not serializable.  In particular, the raw
    terminal bearer remains inside :class:`TerminalCapability` and the exact
    overlay path never enters the worker-visible envelope.
    """

    prepared: dict[str, Any]
    capability: TerminalCapability
    workbench_root: Path
    artifact_bindings: dict[str, Path]
    overlay_path: Path | None
    overlay_sha256: str | None
    overlay_identity: tuple[int, int] | None
    security_mode: str
    closed: bool = False
    records: list[dict[str, Any]] = field(default_factory=list)

    def __getstate__(self) -> Any:  # pragma: no cover - defensive API guard
        raise TypeError("gateway sessions must remain process-local")


class TrustedDelegationGateway:
    """Prepare, run, and close one Skill-local delegated worker attempt."""

    def __init__(
        self,
        *,
        broker: TerminalBroker | None = None,
        evidence_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.broker = broker or TerminalBroker()
        self.evidence_sink = evidence_sink
        self.records: list[dict[str, Any]] = []

    def _record(self, record: dict[str, Any]) -> None:
        self.records.append(record)
        if self.evidence_sink is not None:
            self.evidence_sink(record)

    @staticmethod
    def _workbench_root(tree_path: Path) -> Path:
        resolved = tree_path.resolve(strict=True)
        if resolved.name != "orchestration.xml" or resolved.parent.name != "runtime":
            fail("invalid_runtime_layout", "gateway", "runtime tree does not use the managed workbench layout")
        return resolved.parent.parent.resolve(strict=True)

    @staticmethod
    def _artifact_bindings(workbench_root: Path, envelope: Mapping[str, Any]) -> dict[str, Path]:
        outputs = envelope.get("outputs", {})
        artifacts = outputs.get("artifacts", []) if isinstance(outputs, Mapping) else []
        if not isinstance(artifacts, list):
            fail("output_schema_invalid", "gateway", "prepared artifact outputs are invalid")
        bindings: dict[str, Path] = {}
        for item in artifacts:
            if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
                fail("output_schema_invalid", "gateway", "prepared artifact output is invalid")
            logical = str(item["path"])
            bindings[logical] = workbench_root.joinpath(*logical.split("/"))
        return bindings

    def prepare_dispatch(
        self,
        *,
        tree_path: Path | str,
        skill_root: Path | str,
        profile_id: str,
        node_packet: Mapping[str, Any],
        node_profile_ref: Mapping[str, Any],
        project_policy: Mapping[str, Any],
        adapter_id: str,
        caller_constraints: Mapping[str, Any],
        dynamic_overlay: Path | str | None = None,
    ) -> GatewaySession:
        """Prepare one authoritative envelope and issue its host-only bearer."""

        resolved_tree = Path(tree_path).resolve(strict=True)
        workbench_root = self._workbench_root(resolved_tree)
        # Keep the lexical path supplied by the trusted host.  Resolving it
        # before the pinned read would follow a symlink/reparse point and
        # defeat the resolver's explicit reparse rejection.
        overlay_path = Path(dynamic_overlay).absolute() if dynamic_overlay is not None else None
        overlay_identity: tuple[int, int] | None = None
        if overlay_path is not None:
            overlay_identity = pinned_identity(overlay_path.parent, overlay_path.name)
            if overlay_identity is None:
                fail("overlay_unavailable", "gateway", "dynamic overlay is unavailable", remediation_category="runtime-state")

        prepared = application.prepare(
            skill_root=Path(skill_root).absolute(),
            profile_id=profile_id,
            node_packet=node_packet,
            node_profile_ref=node_profile_ref,
            project_policy=project_policy,
            adapter_id=adapter_id,
            caller_constraints=caller_constraints,
            dynamic_overlay=overlay_path,
        )
        envelope = prepared["envelope"]
        if overlay_path is not None:
            current_identity = pinned_identity(overlay_path.parent, overlay_path.name)
            if current_identity != overlay_identity:
                fail("overlay_cleanup_mismatch", "gateway", "dynamic overlay changed during preparation", retryable=True)
        bindings = self._artifact_bindings(workbench_root, envelope)
        allowed = envelope["authority"]["terminal_operations"]
        receipt = prepared["prepare_receipt"]
        receipt_id = canonical_digest(receipt)[:64]
        capability = self.broker.issue(
            tree_path=resolved_tree,
            node_id=str(node_packet["node_id"]),
            attempt=int(node_packet["attempt"]),
            allowed_operations=allowed,
            artifact_bindings=bindings,
            envelope_sha256=prepared["envelope_sha256"],
            prepare_receipt_id=receipt_id,
            prepare_receipt_sha256=prepared["prepare_receipt_sha256"],
        )
        return GatewaySession(
            prepared=prepared,
            capability=capability,
            workbench_root=workbench_root,
            artifact_bindings=bindings,
            overlay_path=overlay_path,
            overlay_sha256=(prepared.get("overlay_cleanup") or {}).get("sha256") if overlay_path else None,
            overlay_identity=overlay_identity,
            security_mode=str(node_profile_ref["security_mode"]),
        )

    @staticmethod
    def _error_record(error: BaseException) -> dict[str, Any]:
        if isinstance(error, TerminalAuthorityError):
            details = getattr(error, "details", {})
            return {
                "code": getattr(error, "code", "terminal_authority_error"),
                "reason": details.get("reason", "terminal_authority_error"),
            }
        if isinstance(error, DelegationError):
            return {"code": error.code, "reason": error.code}
        return {"code": type(error).__name__, "reason": "gateway_error"}

    def _cleanup(self, session: GatewaySession) -> dict[str, Any]:
        if session.overlay_path is None or session.overlay_sha256 is None:
            return {"status": "not-required"}
        try:
            cleanup_dynamic_overlay(
                session.overlay_path,
                session.overlay_sha256,
                session.overlay_identity,
            )
        except Exception as error:  # cleanup failures are recovery evidence, never silent
            return {"status": "failed", **self._error_record(error)}
        return {"status": "removed", "sha256": session.overlay_sha256}

    def _artifact_digests(
        self,
        session: GatewaySession,
        logical_paths: list[str],
    ) -> tuple[dict[str, str], list[dict[str, str]]]:
        result: dict[str, str] = {}
        failures: list[dict[str, str]] = []
        for logical in logical_paths:
            target = session.artifact_bindings.get(logical)
            if target is None:
                failures.append(
                    {
                        "path": logical,
                        "code": "artifact_not_bound",
                        "reason": "requested artifact has no prepared binding",
                    }
                )
                continue
            try:
                root_relative = target.resolve(strict=False).relative_to(session.workbench_root).as_posix()
                data = stable_read_bytes(session.workbench_root, root_relative, max_bytes=None)
            except Exception as error:
                code = getattr(error, "code", None)
                if not isinstance(code, str) or not code:
                    code = "artifact_unavailable"
                failures.append(
                    {
                        "path": logical,
                        "code": str(code),
                        "reason": "artifact digest could not be read",
                    }
                )
                continue
            result[logical] = hashlib.sha256(data).hexdigest()
        return result, failures

    def consume(self, session: GatewaySession, request: Mapping[str, Any]) -> dict[str, Any]:
        """Consume the one-shot authority and always attempt overlay cleanup."""

        if session.closed:
            fail("gateway_session_closed", "gateway", "gateway session is already closed")
        terminal_result: dict[str, Any] | None = None
        terminal_error: BaseException | None = None
        cleanup: dict[str, Any] = {"status": "not-required"}
        try:
            terminal_result = self.broker.consume(session.capability, request)
            operation = str(request.get("operation", ""))
            artifacts = request.get("artifacts", [])
            artifact_paths = [item for item in artifacts if isinstance(item, str)] if isinstance(artifacts, list) else []
            terminal = {
                "authority_id": session.capability.capability_id,
                "node_id": str(session.prepared["envelope"]["target"]["node_id"]),
                "attempt": int(session.prepared["envelope"]["target"]["attempt"]),
                "operation": operation,
                "result_sha256": canonical_digest(terminal_result),
            }
            envelope = session.prepared["envelope"]
            artifact_digests, artifact_failures = self._artifact_digests(session, artifact_paths)
            receipt = detached_receipt(
                envelope_sha256=session.prepared["envelope_sha256"],
                prepare_receipt_sha256=session.prepared["prepare_receipt_sha256"],
                adapter_id=str(envelope["adapter"]["id"]),
                adapter_version=str(envelope["adapter"]["version"]),
                security_mode=session.security_mode,
                capability_resolution=envelope["capabilities"],
                context_sha256=canonical_digest(envelope["context"]),
                artifact_sha256=artifact_digests,
                artifact_failures=artifact_failures,
                terminal=terminal,
            )
        except BaseException as error:
            terminal_error = error
            receipt = None
        finally:
            cleanup = self._cleanup(session)
            session.closed = True

        if terminal_error is not None:
            recovery = {
                "schema_version": 1,
                "kind": "xc-delegation-recovery-evidence/v1",
                "authority_id": session.capability.capability_id,
                "node_id": str(session.prepared["envelope"]["target"]["node_id"]),
                "attempt": int(session.prepared["envelope"]["target"]["attempt"]),
                "error": self._error_record(terminal_error),
                "cleanup": cleanup,
                "overlay_sha256": session.overlay_sha256,
            }
            self._record(recovery)
            return {
                "ok": False,
                "error": recovery["error"],
                "cleanup": cleanup,
                "recovery_evidence": recovery,
            }

        assert terminal_result is not None
        artifact_failures = []
        if receipt is not None:
            artifact_failures = list(receipt.get("artifact_failures", []))
        result = {
            "ok": cleanup["status"] in {"removed", "not-required"} and not artifact_failures,
            "terminal_result": terminal_result,
            "detached_receipt": receipt,
            "cleanup": cleanup,
        }
        if cleanup["status"] == "failed" or artifact_failures:
            if cleanup["status"] == "failed":
                error = {"code": "overlay_cleanup_failed", "reason": cleanup.get("reason", "cleanup_failed")}
            else:
                error = {"code": "artifact_digest_incomplete", "reason": "one or more requested artifact digests could not be collected"}
            recovery = {
                "schema_version": 1,
                "kind": "xc-delegation-recovery-evidence/v1",
                "authority_id": session.capability.capability_id,
                "node_id": str(session.prepared["envelope"]["target"]["node_id"]),
                "attempt": int(session.prepared["envelope"]["target"]["attempt"]),
                "error": error,
                "cleanup": cleanup,
                "overlay_sha256": session.overlay_sha256,
            }
            if artifact_failures:
                recovery["artifact_failures"] = artifact_failures
            self._record(recovery)
            result["recovery_evidence"] = recovery
        else:
            assert receipt is not None
            self._record(receipt)
        return result

    def abort(self, session: GatewaySession, *, reason: str = "dispatch_aborted") -> dict[str, Any]:
        """Close a prepared session that never reached terminal consumption."""

        if session.closed:
            return {"status": "already-closed"}
        revocation: dict[str, str]
        try:
            self.broker.revoke(session.capability)
            revocation = {"status": "revoked"}
        except TerminalAuthorityError as error:
            details = getattr(error, "details", {})
            state = details.get("state")
            if state in {"revoked", "consumed", "expired"}:
                revocation = {
                    "status": "already-inactive",
                    "state": str(state),
                    "code": getattr(error, "code", "authority_not_active"),
                }
            else:
                revocation = {
                    "status": "failed",
                    "code": getattr(error, "code", "terminal_authority_error"),
                }
        except Exception as error:
            revocation = {"status": "failed", "code": type(error).__name__}
        cleanup = self._cleanup(session)
        session.closed = True
        evidence = {
            "schema_version": 1,
            "kind": "xc-delegation-recovery-evidence/v1",
            "authority_id": session.capability.capability_id,
            "node_id": str(session.prepared["envelope"]["target"]["node_id"]),
            "attempt": int(session.prepared["envelope"]["target"]["attempt"]),
            "error": {"code": "dispatch_aborted", "reason": reason},
            "revocation": revocation,
            "cleanup": cleanup,
            "overlay_sha256": session.overlay_sha256,
        }
        self._record(evidence)
        return {"status": cleanup["status"], "recovery_evidence": evidence}

    def dispatch(self, *, worker: Callable[[Mapping[str, Any], TerminalCapability], Mapping[str, Any]], **prepare_kwargs: Any) -> dict[str, Any]:
        """Prepare, invoke a callable worker, consume, and close in one call."""

        session = self.prepare_dispatch(**prepare_kwargs)
        try:
            request = worker(session.prepared["envelope"], session.capability)
            return self.consume(session, request)
        except BaseException:
            if not session.closed:
                self.abort(session)
            raise


__all__ = ["GatewaySession", "TrustedDelegationGateway"]
