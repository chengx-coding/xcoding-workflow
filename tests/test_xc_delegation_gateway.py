from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding.delegation.gateway import TrustedDelegationGateway
from xcoding.delegation.json_codec import canonical_digest, canonical_json_bytes
from xcoding.runtime.terminal import TerminalAuthorityError


class _Capability:
    capability_id = "capability-test"


class _Broker:
    def __init__(self, result=None, error: BaseException | None = None) -> None:
        self.result = result or {
            "schema_version": 1,
            "kind": "xc-node-terminal-result/v1",
            "capability_id": "capability-test",
            "node_id": "node-1",
            "attempt": 1,
            "operation": "complete",
            "terminal_status": "succeeded",
            "revision": 4,
        }
        self.error = error
        self.state_value = "active"

    def issue(self, **_: object) -> _Capability:
        return _Capability()

    def consume(self, _capability: _Capability, _request: object) -> dict[str, object]:
        if self.state_value != "active":
            raise TerminalAuthorityError(
                "terminal authority is no longer active",
                {"reason": "authority_not_active", "state": self.state_value},
            )
        if self.error is not None:
            raise self.error
        self.state_value = "consumed"
        return self.result

    def revoke(self, _capability: _Capability) -> None:
        if self.state_value != "active":
            raise TerminalAuthorityError(
                "terminal authority is no longer active",
                {"reason": "authority_not_active", "state": self.state_value},
            )
        self.state_value = "revoked"


def _prepared(overlay_sha256: str) -> dict[str, object]:
    envelope = {
        "schema_version": 1,
        "kind": "xc-worker-envelope/v1",
        "target": {"work_order_id": "wo", "node_id": "node-1", "attempt": 1},
        "outputs": {"artifacts": [{"id": "report", "path": "artifacts/report.md", "required": False}]},
        "authority": {"terminal_operations": ["block", "complete", "fail"]},
        "adapter": {"id": "codex", "version": "unverified"},
        "capabilities": {"granted": []},
        "context": {},
    }
    receipt = {"schema_version": 1, "kind": "xc-delegation-prepare-receipt/v1", "claims": {}}
    return {
        "envelope": envelope,
        "envelope_sha256": "a" * 64,
        "prepare_receipt": receipt,
        "prepare_receipt_sha256": "b" * 64,
        "overlay_cleanup": {"required": True, "sha256": overlay_sha256},
    }


class GatewayTests(unittest.TestCase):
    def _session(self, root: Path, broker: _Broker, overlay: Path):
        overlay_value = {"kind": "overlay", "value": "narrow"}
        overlay.write_bytes(canonical_json_bytes(overlay_value))
        prepared = _prepared(canonical_digest(overlay_value))
        with mock.patch("xcoding.delegation.gateway.application.prepare", return_value=prepared):
            return TrustedDelegationGateway(broker=broker).prepare_dispatch(
                tree_path=root / "runtime" / "orchestration.xml",
                skill_root=root,
                profile_id="worker",
                node_packet={"node_id": "node-1", "attempt": 1},
                node_profile_ref={"security_mode": "validated-only"},
                project_policy={},
                adapter_id="codex",
                caller_constraints={},
                dynamic_overlay=overlay,
            )

    def test_success_emits_detached_receipt_and_cleans_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            gateway = TrustedDelegationGateway(broker=_Broker())
            session = self._session(root, gateway.broker, overlay)
            (root / "artifacts").mkdir()
            (root / "artifacts" / "report.md").write_text("evidence", encoding="utf-8")
            result = gateway.consume(
                session,
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "done",
                    "validation": "ok",
                    "artifacts": ["artifacts/report.md"],
                    "check_results": [],
                },
            )
            self.assertTrue(result["ok"])
            self.assertIn("detached_receipt", result)
            self.assertFalse(overlay.exists())
            self.assertTrue(session.closed)

    def test_authenticated_rejection_still_cleans_and_records_recovery(self) -> None:
        error = TerminalAuthorityError("completion rejected", {"reason": "completion_policy"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            broker = _Broker(error=error)
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)
            result = gateway.consume(
                session,
                {"schema_version": 1, "operation": "complete", "summary": "x", "validation": "y", "artifacts": [], "check_results": []},
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["recovery_evidence"]["error"]["reason"], "completion_policy")
            self.assertFalse(overlay.exists())
            self.assertEqual(gateway.records[-1]["kind"], "xc-delegation-recovery-evidence/v1")

    def test_cleanup_failure_is_visible_without_masking_terminal_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            broker = _Broker()
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)
            with mock.patch("xcoding.delegation.gateway.cleanup_dynamic_overlay", side_effect=TerminalAuthorityError("cleanup", {"reason": "residue"})):
                result = gateway.consume(
                    session,
                    {"schema_version": 1, "operation": "fail", "reason": "worker failed", "artifacts": []},
                )
            self.assertFalse(result["ok"])
            self.assertEqual(result["cleanup"]["status"], "failed")
            self.assertIn("recovery_evidence", result)

    def test_same_bytes_overlay_replacement_is_left_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            broker = _Broker()
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)
            replacement = root / "replacement.json"
            replacement.write_bytes(overlay.read_bytes())
            replacement.replace(overlay)

            result = gateway.consume(
                session,
                {"schema_version": 1, "operation": "fail", "reason": "done", "artifacts": []},
            )

            self.assertFalse(result["ok"])
            self.assertTrue(overlay.exists())
            self.assertEqual(result["cleanup"]["code"], "overlay_cleanup_mismatch")
            self.assertEqual(result["recovery_evidence"]["error"]["code"], "overlay_cleanup_failed")

    def test_abort_revokes_capability_and_later_consume_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            broker = _Broker()
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)

            aborted = gateway.abort(session, reason="worker stopped")

            self.assertEqual(aborted["recovery_evidence"]["revocation"]["status"], "revoked")
            self.assertEqual(broker.state_value, "revoked")
            with self.assertRaises(TerminalAuthorityError):
                broker.consume(
                    session.capability,
                    {"schema_version": 1, "operation": "fail", "reason": "late", "artifacts": []},
                )

    def test_artifact_disappearance_is_explicit_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            (root / "artifacts").mkdir()
            artifact = root / "artifacts" / "report.md"
            artifact.write_text("evidence", encoding="utf-8")
            broker = _Broker()
            original_consume = broker.consume

            def consume_then_remove(capability: _Capability, request: object) -> dict[str, object]:
                result = original_consume(capability, request)
                artifact.unlink()
                return result

            broker.consume = consume_then_remove  # type: ignore[method-assign]
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)
            result = gateway.consume(
                session,
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "done",
                    "validation": "ok",
                    "artifacts": ["artifacts/report.md"],
                    "check_results": [],
                },
            )

            self.assertFalse(result["ok"])
            self.assertIn("terminal_result", result)
            self.assertEqual(result["detached_receipt"]["artifacts"], [])
            self.assertEqual(
                result["detached_receipt"]["artifact_failures"][0]["path"],
                "artifacts/report.md",
            )
            self.assertEqual(result["recovery_evidence"]["error"]["code"], "artifact_digest_incomplete")

    def test_artifact_read_error_is_explicit_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "orchestration.xml").write_text("runtime", encoding="utf-8")
            overlay = root / "overlay.json"
            (root / "artifacts").mkdir()
            (root / "artifacts" / "report.md").write_text("evidence", encoding="utf-8")
            broker = _Broker()
            gateway = TrustedDelegationGateway(broker=broker)
            session = self._session(root, broker, overlay)
            with mock.patch(
                "xcoding.delegation.gateway.stable_read_bytes",
                side_effect=OSError("read denied"),
            ):
                result = gateway.consume(
                    session,
                    {
                        "schema_version": 1,
                        "operation": "complete",
                        "summary": "done",
                        "validation": "ok",
                        "artifacts": ["artifacts/report.md"],
                        "check_results": [],
                    },
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["recovery_evidence"]["error"]["code"], "artifact_digest_incomplete")
            self.assertEqual(
                result["detached_receipt"]["artifact_failures"][0]["path"],
                "artifacts/report.md",
            )


if __name__ == "__main__":
    unittest.main()
