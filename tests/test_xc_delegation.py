from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-delegation"
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "delegation"

import sys

sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding.delegation.adapters import load_adapter_statement
from xcoding.delegation.application import compile_diagnostic, prepare
from xcoding.delegation.errors import DelegationError
from xcoding.delegation.json_codec import (
    MAX_INPUT_BYTES,
    canonical_digest,
    canonical_json_bytes,
    parse_json_bytes,
)
from xcoding.delegation.migration import scan_legacy
from xcoding.delegation.model import (
    ADAPTER_EVIDENCE_COVERAGE,
    ADAPTER_EVIDENCE_KIND,
    CAPABILITY_IDS,
    validate_adapter_statement,
    validate_profile,
)
from xcoding.delegation.overlay import apply_overlay, validate_overlay
from xcoding.delegation.receipt import detached_receipt
from xcoding.delegation.resolver import (
    cleanup_dynamic_overlay,
    resolve_profile,
    validate_resolved_profile,
)
from xcoding.delegation.paths import stable_read_bytes, validate_relative_path
import xcoding.delegation.paths as delegation_paths


def load_fixture(name: str) -> dict[str, object]:
    value = parse_json_bytes((FIXTURE_ROOT / name).read_bytes())
    assert isinstance(value, dict)
    return value


def enforced_adapter_statement(
    adapter_version: str = "1.2.3",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "xc-delegation-adapter-capabilities/v1",
        "adapter_id": "test-host",
        "adapter_version": adapter_version,
        "mode": "enforced",
        "evidence": [
            {
                "schema_version": 1,
                "kind": ADAPTER_EVIDENCE_KIND,
                "adapter_version": adapter_version,
                "coverage": coverage,
                "artifact": f"evidence/{coverage}.json",
                "sha256": f"{index + 1}" * 64,
            }
            for index, coverage in enumerate(ADAPTER_EVIDENCE_COVERAGE)
        ],
        "capabilities": [
            {"id": identifier, "support": "enforced", "values": ["*"]}
            for identifier in CAPABILITY_IDS
        ],
    }


class DelegationTestCase(unittest.TestCase):
    def assert_code(self, code: str, function, *args, **kwargs) -> DelegationError:
        with self.assertRaises(DelegationError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def inputs(self) -> dict[str, dict[str, object]]:
        return {
            "node": load_fixture("node-packet-v1.json"),
            "reference": load_fixture("node-profile-ref-v1.json"),
            "project": load_fixture("project-policy-v1.json"),
            "caller": load_fixture("caller-constraints-v1.json"),
        }


class StrictJsonTests(DelegationTestCase):
    def test_canonical_round_trip_and_digest_are_stable(self) -> None:
        value = {"a": [1, True, None], "b": "é"}
        data = canonical_json_bytes(value)
        self.assertEqual(data, b'{"a":[1,true,null],"b":"\xc3\xa9"}\n')
        self.assertEqual(parse_json_bytes(data), value)
        self.assertEqual(canonical_digest(value), canonical_digest(value))

    def test_rejects_bom_duplicate_nonfinite_nonnfc_and_noncanonical(self) -> None:
        cases = (
            ("json_bom_forbidden", b"\xef\xbb\xbf{}\n"),
            ("json_duplicate_key", b'{"a":1,"a":2}\n'),
            ("json_invalid", b'{"a":NaN}\n'),
            ("json_not_nfc", '{"value":"e\u0301"}\n'.encode("utf-8")),
            ("json_not_canonical", b'{ "a": 1 }\n'),
        )
        for code, data in cases:
            with self.subTest(code=code):
                self.assert_code(code, parse_json_bytes, data)

    def test_rejects_size_depth_node_and_string_limits(self) -> None:
        self.assert_code(
            "json_limit_exceeded",
            parse_json_bytes,
            b"{" + b" " * MAX_INPUT_BYTES + b"}",
        )
        nested: object = {}
        for _ in range(34):
            nested = [nested]
        self.assert_code(
            "json_limit_exceeded",
            parse_json_bytes,
            canonical_json_bytes({"nested": nested}),
        )
        nodes = {f"k{index:04d}": index for index in range(4096)}
        self.assert_code("json_limit_exceeded", parse_json_bytes, canonical_json_bytes(nodes))
        self.assert_code(
            "json_limit_exceeded",
            parse_json_bytes,
            canonical_json_bytes({"value": "x" * (16 * 1024 + 1)}),
        )


class ProfileResolverTests(DelegationTestCase):
    def test_resolves_only_the_logical_owned_profile_and_resources(self) -> None:
        resolved = resolve_profile(SKILL_ROOT, "read-only-evidence")
        self.assertEqual(resolved["kind"], "xc-resolved-worker-profile/v1")
        self.assertEqual(resolved["profile"]["owner_skill"], "xc-delegation")
        self.assertEqual(len(resolved["resources"]), 1)
        self.assertEqual(
            resolved["resources"][0]["path"],
            "assets/workers/read-only-evidence/instructions.md",
        )
        self.assertEqual(
            validate_resolved_profile(resolved)["resolved_profile_sha256"],
            resolved["resolved_profile_sha256"],
        )

    def test_rejects_owner_mismatch_unknown_fields_unsafe_paths_and_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            other = Path(temporary) / "xc-other"
            shutil.copytree(SKILL_ROOT, other)
            self.assert_code("owner_skill_mismatch", resolve_profile, other, "read-only-evidence")

            profile_path = other / "assets/workers/read-only-evidence/profile.json"
            value = json.loads(profile_path.read_text(encoding="utf-8"))
            value["owner_skill"] = "xc-other"
            value["unexpected"] = True
            profile_path.write_bytes(canonical_json_bytes(value))
            self.assert_code("schema_fields_invalid", resolve_profile, other, "read-only-evidence")

            value.pop("unexpected")
            value["instruction_resources"] = ["../escape.md"]
            profile_path.write_bytes(canonical_json_bytes(value))
            self.assert_code("path_unsafe", resolve_profile, other, "read-only-evidence")

            value["instruction_resources"] = [
                "assets/workers/read-only-evidence/A.md",
                "assets/workers/read-only-evidence/a.md",
            ]
            profile_path.write_bytes(canonical_json_bytes(value))
            self.assert_code("path_collision", resolve_profile, other, "read-only-evidence")

    def test_rejects_reparse_path_and_resolved_digest_mismatch(self) -> None:
        instruction = SKILL_ROOT / "assets/workers/read-only-evidence/instructions.md"
        original = __import__("xcoding.delegation.paths", fromlist=["_is_link_or_junction"])._is_link_or_junction

        def marked(path: Path) -> bool:
            return path == instruction or original(path)

        with mock.patch("xcoding.delegation.paths._is_link_or_junction", side_effect=marked):
            self.assert_code("path_reparse_forbidden", resolve_profile, SKILL_ROOT, "read-only-evidence")

        fake_path = mock.Mock()
        fake_path.is_symlink.return_value = False
        fake_path.is_junction.return_value = False
        fake_path.lstat.return_value = SimpleNamespace(st_file_attributes=0x400)
        path_module = __import__("xcoding.delegation.paths", fromlist=["_is_link_or_junction"])
        with mock.patch("xcoding.delegation.paths.os.path.isjunction", return_value=False):
            self.assertTrue(path_module._is_link_or_junction(fake_path))

        resolved = resolve_profile(SKILL_ROOT, "read-only-evidence")
        resolved["resources"][0]["content"] += "changed"
        self.assert_code("digest_mismatch", validate_resolved_profile, resolved)

    def test_rejects_absolute_unc_drive_backslash_dot_and_changed_reads(self) -> None:
        unsafe = (
            "/absolute",
            "//server/share",
            "C:/drive",
            "assets\\worker.md",
            "assets/../worker.md",
            "assets/./worker.md",
            "assets/carrier.txt:worker",
            "assets/NUL.txt",
            "assets/trailing.",
            "assets/trailing ",
        )
        for value in unsafe:
            with self.subTest(value=value):
                self.assert_code("path_unsafe", validate_relative_path, value, field="test")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "input.txt"
            target.write_bytes(b"stable")
            original = os.fstat

            def changed(descriptor: int):
                metadata = original(descriptor)
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino,
                    st_size=metadata.st_size,
                    st_mtime_ns=metadata.st_mtime_ns + 1,
                )

            with mock.patch("xcoding.delegation.paths.os.fstat", side_effect=changed):
                self.assert_code("resource_changed", stable_read_bytes, root, "input.txt")

    def test_rejects_trusted_root_replacement_after_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "root"
            root.mkdir()
            (root / "input.txt").write_bytes(b"original")
            snapshot = delegation_paths._component_snapshot(root, "input.txt")
            moved = parent / "root-old"
            root.rename(moved)
            root.mkdir()
            (root / "input.txt").write_bytes(b"replacement")
            with mock.patch.object(delegation_paths, "_component_snapshot", return_value=snapshot):
                self.assert_code("resource_changed", stable_read_bytes, root, "input.txt")

    def test_rejects_intermediate_directory_replacement_after_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "root"
            nested = root / "nested"
            nested.mkdir(parents=True)
            (nested / "input.txt").write_bytes(b"original")
            snapshot = delegation_paths._component_snapshot(root, "nested/input.txt")
            moved = root / "nested-old"
            nested.rename(moved)
            nested.mkdir()
            (nested / "input.txt").write_bytes(b"replacement")
            with mock.patch.object(delegation_paths, "_component_snapshot", return_value=snapshot):
                self.assert_code("resource_changed", stable_read_bytes, root, "nested/input.txt")

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_real_ntfs_alternate_stream_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            carrier = root / "carrier.txt"
            carrier.write_text("carrier\n", encoding="utf-8")
            stream = Path(str(carrier) + ":worker")
            try:
                stream.write_text("hidden\n", encoding="utf-8")
            except OSError:
                self.skipTest("temporary filesystem does not support alternate streams")
            self.assert_code(
                "path_unsafe",
                stable_read_bytes,
                root,
                "carrier.txt:worker",
            )

    def test_overlay_only_narrows_and_cleanup_is_digest_bound(self) -> None:
        profile = resolve_profile(SKILL_ROOT, "read-only-evidence")["profile"]
        target = {
            "work_order_id": "20260913-2242-delegation-fixture",
            "node_id": "rt_work-order-20260913-2242-delegation-fixture__root__evidence",
            "attempt": 1,
        }
        overlay = {
            "schema_version": 1,
            "kind": "xc-worker-profile-overlay/v1",
            "owner_skill": "xc-delegation",
            "profile_id": "read-only-evidence",
            "target": target,
            "expires_at": "2099-01-01T00:00:00Z",
            "description": "Collect read-only evidence",
            "optional_capabilities": [],
            "context_binding_ids": ["target-contract"],
            "output_ids": ["evidence"],
            "limits": {"context_max_bytes": 4096},
        }
        validated = validate_overlay(overlay, expected_target=target)
        narrowed = apply_overlay(profile, validated)
        self.assertNotIn("optional", {item["requirement"] for item in narrowed["capabilities"]})
        self.assertEqual(narrowed["context"]["max_bytes"], 4096)

        widened = copy.deepcopy(overlay)
        widened["limits"]["context_max_bytes"] = 9000
        self.assert_code("unsafe_overlay_widening", apply_overlay, profile, validate_overlay(widened))
        mismatched = dict(target)
        mismatched["attempt"] = 2
        self.assert_code("overlay_target_mismatch", validate_overlay, overlay, expected_target=mismatched)
        expired = copy.deepcopy(overlay)
        expired["expires_at"] = "2000-01-01T00:00:00Z"
        self.assert_code("overlay_expired", validate_overlay, expired)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overlay.json"
            path.write_bytes(canonical_json_bytes(overlay))
            digest = canonical_digest(overlay)
            changed = copy.deepcopy(overlay)
            changed["description"] = "Collect read-only evidence for one"
            path.write_bytes(canonical_json_bytes(changed))
            self.assert_code("overlay_cleanup_mismatch", cleanup_dynamic_overlay, path, digest)
            path.write_bytes(canonical_json_bytes(overlay))
            cleanup_dynamic_overlay(path, digest)
            self.assertFalse(path.exists())


class CapabilityCompilerTests(DelegationTestCase):
    def test_prepare_is_deterministic_authoritative_and_records_omissions(self) -> None:
        inputs = self.inputs()
        first = prepare(
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=inputs["node"],
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=inputs["caller"],
        )
        second = prepare(
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=inputs["node"],
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=inputs["caller"],
        )
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        envelope = first["envelope"]
        self.assertIs(envelope["authority"]["dispatch_authoritative"], True)
        self.assertEqual(envelope["compatibility"]["mode"], "prepared-profile")
        self.assertEqual(
            [item["id"] for item in envelope["capabilities"]["omitted"]],
            ["process.exec.named"],
        )
        serialized = canonical_json_bytes(envelope).decode("utf-8")
        self.assertNotIn(str(REPOSITORY_ROOT), serialized)
        self.assertNotIn("timestamp", serialized)
        self.assertNotIn("token", serialized)
        self.assertIs(first["prepare_receipt"]["claims"]["publisher_authentication"], False)
        self.assertIs(first["prepare_receipt"]["claims"]["execution_attestation"], False)

    def test_diagnostic_compile_cannot_authorize_dispatch(self) -> None:
        inputs = self.inputs()
        resolved = resolve_profile(SKILL_ROOT, "read-only-evidence")
        adapter = load_adapter_statement("codex")
        envelope = compile_diagnostic(
            resolved_profile=resolved,
            node_packet=inputs["node"],
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_statement=adapter,
            caller_constraints=inputs["caller"],
        )
        self.assertIs(envelope["authority"]["dispatch_authoritative"], False)

    def test_authoritative_prepare_requires_terminal_and_required_skills(
        self,
    ) -> None:
        inputs = self.inputs()
        denied_skill = copy.deepcopy(inputs["caller"])
        denied_skill["grants"] = [
            item
            for item in denied_skill["grants"]
            if item["id"] != "skill.invoke.declared"
        ]
        self.assert_code(
            "required_skill_not_authorized",
            prepare,
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=inputs["node"],
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=denied_skill,
        )

        with tempfile.TemporaryDirectory() as temporary:
            skill_root = Path(temporary) / "xc-delegation"
            shutil.copytree(SKILL_ROOT, skill_root)
            profile_path = (
                skill_root
                / "assets"
                / "workers"
                / "read-only-evidence"
                / "profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["required_skills"] = []
            profile["capabilities"] = [
                item
                for item in profile["capabilities"]
                if item["id"] != "runtime.terminal.assigned-node"
            ]
            profile_path.write_bytes(canonical_json_bytes(profile))
            no_terminal_node = copy.deepcopy(inputs["node"])
            no_terminal_node["authorization"]["capabilities"] = [
                item
                for item in no_terminal_node["authorization"]["capabilities"]
                if item["id"] != "runtime.terminal.assigned-node"
            ]
            no_terminal_project = copy.deepcopy(inputs["project"])
            no_terminal_project["grants"] = [
                item
                for item in no_terminal_project["grants"]
                if item["id"] != "runtime.terminal.assigned-node"
            ]
            no_terminal_caller = copy.deepcopy(inputs["caller"])
            no_terminal_caller["grants"] = [
                item
                for item in no_terminal_caller["grants"]
                if item["id"] != "runtime.terminal.assigned-node"
            ]
            resolved = resolve_profile(skill_root, "read-only-evidence")
            diagnostic = compile_diagnostic(
                resolved_profile=resolved,
                node_packet=no_terminal_node,
                node_profile_ref=inputs["reference"],
                project_policy=no_terminal_project,
                adapter_statement=load_adapter_statement("codex"),
                caller_constraints=no_terminal_caller,
            )
            self.assertIs(
                diagnostic["authority"]["dispatch_authoritative"],
                False,
            )
            self.assertEqual(
                diagnostic["authority"]["terminal_operations"],
                [],
            )
            self.assert_code(
                "terminal_authority_empty",
                prepare,
                skill_root=skill_root,
                profile_id="read-only-evidence",
                node_packet=no_terminal_node,
                node_profile_ref=inputs["reference"],
                project_policy=no_terminal_project,
                adapter_id="codex",
                caller_constraints=no_terminal_caller,
            )

    def test_optional_skill_may_be_omitted_when_no_skill_is_required(self) -> None:
        inputs = self.inputs()
        with tempfile.TemporaryDirectory() as temporary:
            skill_root = Path(temporary) / "xc-delegation"
            shutil.copytree(SKILL_ROOT, skill_root)
            profile_path = (
                skill_root
                / "assets"
                / "workers"
                / "read-only-evidence"
                / "profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["required_skills"] = []
            profile_path.write_bytes(canonical_json_bytes(profile))
            caller = copy.deepcopy(inputs["caller"])
            caller["grants"] = [
                item
                for item in caller["grants"]
                if item["id"] != "skill.invoke.declared"
            ]
            result = prepare(
                skill_root=skill_root,
                profile_id="read-only-evidence",
                node_packet=inputs["node"],
                node_profile_ref=inputs["reference"],
                project_policy=inputs["project"],
                adapter_id="codex",
                caller_constraints=caller,
            )
        self.assertIs(
            result["envelope"]["authority"]["dispatch_authoritative"],
            True,
        )
        self.assertIn(
            "skill.invoke.declared",
            {
                item["id"]
                for item in result["envelope"]["capabilities"]["omitted"]
            },
        )

    def test_blocks_required_denial_widening_and_unproven_enforced_mode(self) -> None:
        inputs = self.inputs()
        denied = copy.deepcopy(inputs["caller"])
        denied["grants"] = [
            item for item in denied["grants"] if item["id"] != "project.read.declared"
        ]
        self.assert_code(
            "required_capability_denied",
            prepare,
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=inputs["node"],
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=denied,
        )

        widened = copy.deepcopy(inputs["node"])
        grant = next(item for item in widened["authorization"]["capabilities"] if item["id"] == "project.read.declared")
        grant["values"] = ["README.md", "docs/extra.md"]
        project = copy.deepcopy(inputs["project"])
        next(item for item in project["grants"] if item["id"] == "project.read.declared")["values"] = [
            "README.md",
            "docs/extra.md",
        ]
        self.assert_code(
            "unsafe_capability_widening",
            prepare,
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=widened,
            node_profile_ref=inputs["reference"],
            project_policy=project,
            adapter_id="codex",
            caller_constraints=inputs["caller"],
        )

        absolute_context = copy.deepcopy(inputs["node"])
        absolute_context["context"]["target-contract"]["scope"] = "C:\\private\\source"
        self.assert_code(
            "context_absolute_path_forbidden",
            prepare,
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=absolute_context,
            node_profile_ref=inputs["reference"],
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=inputs["caller"],
        )

        for absolute_key in (
            "C:\\private\\source",
            "\\\\server\\share\\source",
            "/private/source",
        ):
            with self.subTest(absolute_key=absolute_key):
                absolute_context_key = copy.deepcopy(inputs["node"])
                absolute_context_key["context"]["target-contract"] = {
                    "nested": {absolute_key: "value"}
                }
                self.assert_code(
                    "context_absolute_path_forbidden",
                    prepare,
                    skill_root=SKILL_ROOT,
                    profile_id="read-only-evidence",
                    node_packet=absolute_context_key,
                    node_profile_ref=inputs["reference"],
                    project_policy=inputs["project"],
                    adapter_id="codex",
                    caller_constraints=inputs["caller"],
                )

        enforced = copy.deepcopy(inputs["reference"])
        enforced["security_mode"] = "enforced"
        self.assert_code(
            "required_capability_denied",
            prepare,
            skill_root=SKILL_ROOT,
            profile_id="read-only-evidence",
            node_packet=inputs["node"],
            node_profile_ref=enforced,
            project_policy=inputs["project"],
            adapter_id="codex",
            caller_constraints=inputs["caller"],
        )

    def test_adapter_statements_are_calibrated_and_default_sensitive_access_off(self) -> None:
        for adapter_id in ("claude-code", "codex", "opencode", "trae"):
            with self.subTest(adapter=adapter_id):
                statement = load_adapter_statement(adapter_id)
                self.assertEqual(statement["mode"], "validated-only")
                support = {item["id"]: item["support"] for item in statement["capabilities"]}
                self.assertEqual(support["network.outbound.allowlisted"], "unsupported")
                self.assertEqual(support["secret.use.named"], "unsupported")
                self.assertNotIn("enforced", support.values())

    def test_enforced_adapter_requires_pinned_complete_structured_evidence(
        self,
    ) -> None:
        valid = enforced_adapter_statement()
        normalized = validate_adapter_statement(valid)
        self.assertEqual(normalized["mode"], "enforced")
        self.assertEqual(
            [item["coverage"] for item in normalized["evidence"]],
            list(ADAPTER_EVIDENCE_COVERAGE),
        )

        self.assert_code(
            "adapter_version_unpinned",
            validate_adapter_statement,
            enforced_adapter_statement("unverified"),
        )
        for evidence in ([], valid["evidence"][:-1]):
            with self.subTest(evidence_count=len(evidence)):
                incomplete = copy.deepcopy(valid)
                incomplete["evidence"] = evidence
                self.assert_code(
                    "adapter_evidence_incomplete",
                    validate_adapter_statement,
                    incomplete,
                )

        unknown_evidence_version = copy.deepcopy(valid)
        unknown_evidence_version["evidence"][0]["schema_version"] = 2
        self.assert_code(
            "schema_version_unsupported",
            validate_adapter_statement,
            unknown_evidence_version,
        )
        mismatched_evidence_version = copy.deepcopy(valid)
        mismatched_evidence_version["evidence"][0]["adapter_version"] = "1.2.4"
        self.assert_code(
            "adapter_evidence_version_mismatch",
            validate_adapter_statement,
            mismatched_evidence_version,
        )
        mixed_support = copy.deepcopy(valid)
        mixed_support["capabilities"][0]["support"] = "validated-only"
        self.assert_code(
            "security_mode_invalid",
            validate_adapter_statement,
            mixed_support,
        )
        partial_capabilities = copy.deepcopy(valid)
        partial_capabilities["capabilities"] = partial_capabilities[
            "capabilities"
        ][:-1]
        self.assert_code(
            "adapter_capabilities_incomplete",
            validate_adapter_statement,
            partial_capabilities,
        )

        with tempfile.TemporaryDirectory() as temporary:
            adapter_root = Path(temporary) / "adapters"
            adapter_root.mkdir()
            unsubstantiated = enforced_adapter_statement("unverified")
            (adapter_root / "test-host.json").write_bytes(
                canonical_json_bytes(unsubstantiated)
            )
            inputs = self.inputs()
            with mock.patch(
                "xcoding.delegation.adapters._source_asset_root",
                return_value=adapter_root,
            ):
                self.assert_code(
                    "adapter_version_unpinned",
                    prepare,
                    skill_root=SKILL_ROOT,
                    profile_id="read-only-evidence",
                    node_packet=inputs["node"],
                    node_profile_ref=inputs["reference"],
                    project_policy=inputs["project"],
                    adapter_id="test-host",
                    caller_constraints=inputs["caller"],
                )

    def test_detached_receipt_makes_only_integrity_and_audit_claims(self) -> None:
        receipt = detached_receipt(
            envelope_sha256="1" * 64,
            prepare_receipt_sha256="2" * 64,
            adapter_id="codex",
            adapter_version="unverified",
            security_mode="validated-only",
            capability_resolution={"granted": []},
            context_sha256="3" * 64,
            artifact_sha256={"artifacts/evidence.md": "4" * 64},
            terminal={
                "authority_id": "capability-1",
                "node_id": "rt_work-order-example__root__node",
                "attempt": 1,
                "operation": "complete",
                "result_sha256": "5" * 64,
            },
        )
        self.assertEqual(
            receipt["claims"],
            {
                "execution_attestation": False,
                "integrity_and_audit_linkage_only": True,
                "publisher_authentication": False,
            },
        )


class ContractAssetAndMigrationTests(DelegationTestCase):
    def test_three_schema_assets_are_strict_roots(self) -> None:
        schema_root = SKILL_ROOT / "assets" / "schemas"
        self.assertEqual(
            sorted(path.name for path in schema_root.glob("*.json")),
            [
                "delegation-envelope-v1.schema.json",
                "dynamic-overlay-v1.schema.json",
                "worker-profile.schema.json",
            ],
        )
        for path in schema_root.glob("*.json"):
            value = parse_json_bytes(path.read_bytes())
            self.assertIs(value["additionalProperties"], False)
            self.assertEqual(value["type"], "object")

    def test_worker_profile_schema_matches_representable_validator_rules(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        schema = json.loads(
            (SKILL_ROOT / "assets/schemas/worker-profile.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        valid = json.loads(
            (SKILL_ROOT / "assets/workers/read-only-evidence/profile.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(list(validator.iter_errors(valid)), [])
        validate_profile(valid)
        self.assertNotIn("schema_version", valid)

        invalid_profiles: list[dict[str, object]] = []
        retired = copy.deepcopy(valid)
        retired["schema_version"] = 1
        invalid_profiles.append(retired)

        escaped = copy.deepcopy(valid)
        escaped["instruction_resources"] = ["../escape.md"]
        invalid_profiles.append(escaped)
        wildcard = copy.deepcopy(valid)
        wildcard["capabilities"][1]["values"] = ["*"]
        invalid_profiles.append(wildcard)
        bad_terminal = copy.deepcopy(valid)
        bad_terminal["capabilities"][2]["values"] = ["delete"]
        invalid_profiles.append(bad_terminal)
        bad_artifact = copy.deepcopy(valid)
        bad_artifact["outputs"]["artifacts"][0]["path"] = "artifacts/NUL.txt"
        invalid_profiles.append(bad_artifact)
        bad_identifier = copy.deepcopy(valid)
        bad_identifier["outputs"]["artifacts"][0]["id"] = "Not-Portable"
        invalid_profiles.append(bad_identifier)

        for profile in invalid_profiles:
            with self.subTest(profile=profile):
                self.assertTrue(list(validator.iter_errors(profile)))
                with self.assertRaises(DelegationError):
                    validate_profile(profile)

    def test_retired_profile_schema_version_is_rejected(self) -> None:
        current = json.loads(
            (SKILL_ROOT / "assets/workers/read-only-evidence/profile.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("schema_version", current)
        retired = copy.deepcopy(current)
        retired["schema_version"] = 1
        self.assert_code("schema_fields_invalid", validate_profile, retired)

    def test_legacy_scan_is_read_only_bounded_and_never_returns_content(self) -> None:
        tracked = REPOSITORY_ROOT / "agents-src" / "agents" / "xc-delegated-agent.md"
        before = tracked.read_bytes()
        result = scan_legacy(REPOSITORY_ROOT)
        self.assertIs(result["writes_performed"], False)
        self.assertIs(result["content_included"], False)
        self.assertEqual(tracked.read_bytes(), before)
        serialized = json.dumps(result)
        self.assertNotIn("You execute one delegated task", serialized)
        self.assertTrue(any(item["path"] == "agents-src/agents/xc-delegated-agent.md" for item in result["findings"]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "skills/xc-private/assets/workers/role/instructions.md"
            private.parent.mkdir(parents=True)
            private.write_text("<agent_definition>private</agent_definition>\n", encoding="utf-8")
            public = root / "skills/xc-private/SKILL.md"
            public.write_text("public contract\n", encoding="utf-8")
            private_result = scan_legacy(root)
            self.assertEqual(private_result["findings"], [])


if __name__ == "__main__":
    unittest.main()
