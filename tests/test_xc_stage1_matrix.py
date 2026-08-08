from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPOSITORY_ROOT / "scripts" / "run_stage1_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_stage1_matrix", DRIVER_PATH)
assert SPEC is not None and SPEC.loader is not None
matrix = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = matrix
SPEC.loader.exec_module(matrix)


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_digest(files: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"xc-candidate-tree-v1\0")
    for item in files:
        path_bytes = str(item["path"]).encode("utf-8")
        digest.update(str(item["mode"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(len(path_bytes)).encode("ascii"))
        digest.update(b"\0")
        digest.update(path_bytes)
        digest.update(b"\0")
        digest.update(bytes.fromhex(str(item["sha256"])))
    return digest.hexdigest()


class Stage1MatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.archive = self.root / "candidate-source.zip"
        self.descriptor = self.root / "candidate-descriptor.json"
        self.wheel = self.root / matrix.EXPECTED_WHEEL_FILENAME
        self._write_inputs()
        self.verified = matrix.verify_inputs(
            candidate_archive=self.archive,
            candidate_archive_sha256=self.archive_sha256,
            candidate_descriptor=self.descriptor,
            candidate_descriptor_sha256=self.descriptor_sha256,
            candidate_tree_sha256=self.candidate_tree_sha256,
            wheel=self.wheel,
            wheel_sha256=self.wheel_sha256,
        )
        self.attestation_keys = {
            cell_id: hashlib.sha256(
                f"trusted-test-key:{cell_id}".encode("utf-8")
            ).digest()
            for cell_id in matrix.REQUIRED_CELLS
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_inputs(self) -> None:
        toolchain = {
            "schema_version": 1,
            "pin_status": "provisional",
            "promotion_gate": "I6-windows-linux-macos-matrix",
            "fallback_policy": {
                "allow_latest": False,
                "allow_ambient_uv": False,
                "allow_system_python": False,
            },
            "uv": {
                "version": "0.11.15",
                "artifacts": [
                    {
                        "platform_id": "windows-x86_64",
                        "filename": "uv-windows.zip",
                        "sha256": "1" * 64,
                    },
                    {
                        "platform_id": "linux-x86_64-gnu",
                        "filename": "uv-linux.tar.gz",
                        "sha256": "2" * 64,
                    },
                    {
                        "platform_id": "macos-aarch64",
                        "filename": "uv-macos.tar.gz",
                        "sha256": "3" * 64,
                    },
                ],
            },
            "python": {
                "request": "cpython@3.12.13",
                "downloads": [
                    {
                        "platform_id": "windows-x86_64",
                        "build_identity": "python-windows-x86_64",
                    },
                    {
                        "platform_id": "linux-x86_64-gnu",
                        "build_identity": "python-linux-x86_64-gnu",
                    },
                    {
                        "platform_id": "macos-aarch64",
                        "build_identity": "python-macos-aarch64",
                    },
                ],
            },
        }
        source = {
            matrix.TOOLCHAIN_MEMBER: (
                json.dumps(toolchain, sort_keys=True, indent=2) + "\n"
            ).encode("utf-8"),
            "scripts/run_stage1_matrix.py": b"# candidate driver\n",
        }
        files = [
            {
                "mode": "100644",
                "path": path,
                "size": len(data),
                "sha256": sha256(data),
            }
            for path, data in sorted(
                source.items(),
                key=lambda item: item[0].encode("utf-8"),
            )
        ]
        self.candidate_tree_sha256 = tree_digest(files)
        with zipfile.ZipFile(
            self.archive,
            "x",
            compression=zipfile.ZIP_STORED,
        ) as archive:
            for item in files:
                info = zipfile.ZipInfo(
                    str(item["path"]),
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = int(str(item["mode"]), 8) << 16
                info.internal_attr = 0
                info.comment = b""
                info.extra = b""
                archive.writestr(info, source[str(item["path"])])
        self.archive_sha256 = sha256(self.archive.read_bytes())
        descriptor = {
            "schema_version": 1,
            "baseline_revision": "a" * 40,
            "source_state": "work-order-candidate",
            "candidate_tree_sha256": self.candidate_tree_sha256,
            "candidate_source_archive_sha256": self.archive_sha256,
            "candidate_git_tree": "b" * 40,
            "candidate_paths": ["scripts/run_stage1_matrix.py"],
            "tree_digest_format": "xc-candidate-tree-v1",
            "archive_format": "zip-stored-fixed-metadata-v1",
            "files": files,
        }
        self.descriptor.write_bytes(canonical_json(descriptor))
        self.descriptor_sha256 = sha256(self.descriptor.read_bytes())
        manifest = {
            "baseline_revision": "a" * 40,
            "source_state": "work-order-candidate",
            "candidate_tree_sha256": self.candidate_tree_sha256,
            "candidate_source_archive_sha256": self.archive_sha256,
        }
        with zipfile.ZipFile(self.wheel, "w") as wheel:
            wheel.writestr(matrix.MANIFEST_MEMBER, canonical_json(manifest))
        self.wheel_sha256 = sha256(self.wheel.read_bytes())

    def _platform(self, cell_id: str) -> tuple[str, str, str, str]:
        if cell_id == "windows-x86_64":
            return (
                "windows",
                "x86_64",
                "not-applicable",
                "windows-x86_64",
            )
        if cell_id == "linux-x86_64-gnu":
            return (
                "linux",
                "x86_64",
                "glibc:2.39",
                "linux-x86_64-gnu",
            )
        return (
            "macos",
            "aarch64",
            "not-applicable",
            "macos-aarch64",
        )

    def _pin(self, platform_id: str) -> tuple[str, str, str]:
        toolchain = self.verified["toolchain"]
        uv, python, version, request = matrix._toolchain_records(
            toolchain,
            platform_id,
        )
        return (
            str(uv["filename"]),
            str(uv["sha256"]),
            str(python["build_identity"]),
        )

    def _evidence(
        self,
        cell_id: str,
        *,
        status: str = "passed",
        execution_id: str | None = None,
        runner_name: str | None = None,
    ) -> dict[str, object]:
        runner_os, architecture, libc, platform_id = self._platform(cell_id)
        uv_filename, uv_sha256, python_build = self._pin(platform_id)
        started = "2026-08-07T01:00:00Z"
        finished = "2026-08-07T01:10:00Z"
        command_ids = list(matrix.REQUIRED_COMMANDS)
        if cell_id == "windows-x86_64":
            command_ids.append(matrix.WINDOWS_COMMAND)
        commands = [
            {
                "id": command_id,
                "argv": [
                    sys.executable,
                    "-B",
                    str(DRIVER_PATH),
                    "trusted-cell-step",
                    command_id,
                ],
                "cwd": "/external/candidate",
                "expected_exit": (
                    "nonzero"
                    if command_id == "failure-injections"
                    else "zero"
                ),
                "exit_code": (
                    4
                    if status == "passed"
                    and command_id == "failure-injections"
                    else (0 if status == "passed" else None)
                ),
                "status": "passed" if status == "passed" else "unrun",
                "started_at_utc": started,
                "duration_ms": 1 if status == "passed" else None,
                "stdout_sha256": (
                    sha256(f"{cell_id}:{command_id}:stdout\n".encode("utf-8"))
                    if status == "passed"
                    else None
                ),
                "stderr_sha256": (
                    sha256(f"{cell_id}:{command_id}:stderr\n".encode("utf-8"))
                    if status == "passed"
                    else None
                ),
                "stdout_b64": (
                    base64.b64encode(
                        f"{cell_id}:{command_id}:stdout\n".encode("utf-8")
                    ).decode("ascii")
                    if status == "passed"
                    else None
                ),
                "stderr_b64": (
                    base64.b64encode(
                        f"{cell_id}:{command_id}:stderr\n".encode("utf-8")
                    ).decode("ascii")
                    if status == "passed"
                    else None
                ),
            }
            for command_id in command_ids
        ]
        checks = {
            name: (
                "not-applicable"
                if name == "windows-console-oracle"
                and cell_id != "windows-x86_64"
                else ("passed" if status == "passed" else "unrun")
            )
            for name in matrix.REQUIRED_CHECKS
        }
        return {
            "schema_version": 1,
            "evidence_kind": matrix.CELL_EVIDENCE_KIND,
            "cell_id": cell_id,
            "status": status,
            "execution": {
                "execution_id": execution_id or str(uuid.uuid4()),
                "provider": "external-test-runner",
                "run_id": "42",
                "run_attempt": 1,
                "job_id": f"job-{cell_id}",
                "runner_name": runner_name or f"runner-{cell_id}",
                "started_at_utc": started,
                "finished_at_utc": finished,
            },
            "bindings": dict(self.verified["bindings"]),
            "environment": {
                "runner_os": runner_os,
                "os_name": f"{runner_os}-test",
                "os_version": "1",
                "os_image": "test-image",
                "architecture": architecture,
                "libc": libc,
                "standard_user": True,
                "is_root": False,
                "long_paths_supported": True,
                "sys_executable": "/external/fixture/python",
                "sys_base_executable": "/external/managed/python",
                "sys_version": "3.12.13",
                "fixture_root": "/external/fixture",
                "uv_python_install_dir": "/external/fixture/uv/python",
                "uv_tool_dir": "/external/fixture/uv/tools",
                "uv_tool_bin_dir": "/external/fixture/uv/bin",
            },
            "provenance": {
                "candidate_archive_verified": status == "passed",
                "candidate_descriptor_verified": status == "passed",
                "candidate_tree_verified": status == "passed",
                "wheel_verified": status == "passed",
                "uv_version": "0.11.15",
                "uv_version_output": "uv 0.11.15 (test)",
                "uv_artifact_filename": uv_filename,
                "uv_artifact_sha256": uv_sha256,
                "uv_artifact_verified": status == "passed",
                "python_request": "cpython@3.12.13",
                "python_build_identity": python_build,
                "managed_python_find": "/external/managed/python",
                "managed_python_verified": status == "passed",
            },
            "commands": commands,
            "checks": checks,
            "cleanup": {
                "attempted": status == "passed",
                "fixture_removed": status == "passed",
                "candidate_staging_removed": status == "passed",
                "unexpected_preserved": status == "passed",
                "status": "passed" if status == "passed" else "unrun",
            },
            "failure": (
                None
                if status == "passed"
                else {
                    "code": f"cell-{status}",
                    "message": f"cell is {status}",
                }
            ),
            "attestation": None,
        }

    def _trusted_evidence(
        self,
        cell_id: str,
        evidence: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], str, dict[str, bytes]]:
        value = evidence or self._evidence(cell_id)
        contract = matrix._command_contract_sha256(value["commands"])
        key = self.attestation_keys[cell_id]
        runner_os, architecture, libc, _ = self._platform(cell_id)
        with mock.patch.object(
            matrix,
            "_current_platform",
            return_value=(runner_os, architecture, libc),
        ):
            signed = matrix._attest_cell_evidence(
                value,
                key=key,
                expected_command_contract_sha256=contract,
            )
        key_id = matrix._attestation_key_id(key)
        return signed, contract, {key_id: key}

    def _trusted_matrix(
        self,
    ) -> tuple[
        dict[str, dict[str, object]],
        dict[str, str],
        dict[str, dict[str, bytes]],
        dict[str, str],
    ]:
        evidence: dict[str, dict[str, object]] = {}
        contracts: dict[str, str] = {}
        keys: dict[str, dict[str, bytes]] = {}
        identities: dict[str, str] = {}
        for cell_id in matrix.REQUIRED_CELLS:
            signed, contract, trusted = self._trusted_evidence(cell_id)
            evidence[cell_id] = signed
            contracts[cell_id] = contract
            keys[cell_id] = trusted
            identities[cell_id] = matrix._runner_identity_sha256(
                signed["execution"]
            )
        return evidence, contracts, keys, identities

    def _write_evidence(
        self,
        cell_id: str,
        evidence: dict[str, object],
    ) -> Path:
        path = self.root / f"{cell_id}.json"
        path.write_bytes(canonical_json(evidence))
        return path

    def test_verifies_digest_addressed_candidate_and_wheel(self) -> None:
        self.assertEqual(
            self.verified["bindings"]["candidate_tree_sha256"],
            self.candidate_tree_sha256,
        )
        self.assertEqual(
            self.verified["bindings"]["wheel_sha256"],
            self.wheel_sha256,
        )
        self.assertEqual(self.verified["candidate_file_count"], 2)

    def test_rejects_archive_descriptor_and_wheel_mismatches(self) -> None:
        cases = (
            ("candidate_archive_sha256", "0" * 64, "descriptor_mismatch"),
            ("candidate_descriptor_sha256", "0" * 64, "descriptor_digest_mismatch"),
            ("candidate_tree_sha256", "0" * 64, "descriptor_mismatch"),
            ("wheel_sha256", "0" * 64, "wheel_digest_mismatch"),
        )
        base = {
            "candidate_archive": self.archive,
            "candidate_archive_sha256": self.archive_sha256,
            "candidate_descriptor": self.descriptor,
            "candidate_descriptor_sha256": self.descriptor_sha256,
            "candidate_tree_sha256": self.candidate_tree_sha256,
            "wheel": self.wheel,
            "wheel_sha256": self.wheel_sha256,
        }
        for field, value, code in cases:
            with self.subTest(field=field):
                arguments = dict(base)
                arguments[field] = value
                with self.assertRaises(matrix.MatrixError) as raised:
                    matrix.verify_inputs(**arguments)
                self.assertEqual(raised.exception.code, code)

    def test_validates_each_fixed_cell_with_recorded_macos_arch(self) -> None:
        for cell_id in matrix.REQUIRED_CELLS:
            with self.subTest(cell_id=cell_id):
                evidence, contract, keys = self._trusted_evidence(cell_id)
                result = matrix.validate_cell_evidence(
                    evidence,
                    expected_cell=cell_id,
                    expected_bindings=self.verified["bindings"],
                    toolchain=self.verified["toolchain"],
                    expected_run_id="42",
                    trusted_attestation_keys=keys,
                    expected_command_contract_sha256=contract,
                    expected_runner_identity_sha256=(
                        matrix._runner_identity_sha256(evidence["execution"])
                    ),
                )
                self.assertTrue(result["promotion_eligible"])
        mac = self._evidence("macos-recorded-arch")
        self.assertEqual(mac["environment"]["architecture"], "aarch64")

    def test_rejects_cell_environment_and_binding_reuse(self) -> None:
        evidence = self._evidence("linux-x86_64-gnu")
        evidence["environment"]["architecture"] = "aarch64"
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.validate_cell_evidence(
                evidence,
                expected_cell="linux-x86_64-gnu",
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
            )
        self.assertEqual(raised.exception.code, "cell_mismatch")

        evidence = self._evidence("windows-x86_64")
        evidence["bindings"]["wheel_sha256"] = "0" * 64
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.validate_cell_evidence(
                evidence,
                expected_cell="windows-x86_64",
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
            )
        self.assertEqual(raised.exception.code, "binding_mismatch")

        evidence = self._evidence("windows-x86_64")
        evidence["commands"][0]["exit_code"] = 7
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.validate_cell_evidence(
                evidence,
                expected_cell="windows-x86_64",
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
            )
        self.assertEqual(raised.exception.code, "command_failed")

    def test_failed_and_unrun_evidence_are_valid_but_not_promotable(self) -> None:
        for status in ("failed", "unrun"):
            with self.subTest(status=status):
                result = matrix.validate_cell_evidence(
                    self._evidence("windows-x86_64", status=status),
                    expected_cell="windows-x86_64",
                    expected_bindings=self.verified["bindings"],
                    toolchain=self.verified["toolchain"],
                )
                self.assertTrue(result["valid"])
                self.assertFalse(result["promotion_eligible"])

    def test_summary_promotes_only_three_distinct_trusted_passes(self) -> None:
        evidence, contracts, keys, identities = self._trusted_matrix()
        evidence_paths = {
            cell_id: self._write_evidence(
                cell_id,
                evidence[cell_id],
            )
            for cell_id in matrix.REQUIRED_CELLS
        }
        result = matrix.summarize_evidence(
            evidence_paths=evidence_paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            expected_run_id="42",
            trusted_attestation_keys=keys,
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(result["decision"], "promote")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["pin_status"], "fixed")
        self.assertTrue(result["promotion_eligible"])
        self.assertEqual(
            [cell["outcome"] for cell in result["cells"]],
            ["passed", "passed", "passed"],
        )
        self.assertEqual(
            len({cell["runner_identity_sha256"] for cell in result["cells"]}),
            3,
        )
        self.assertEqual(
            len({cell["attestation_key_id"] for cell in result["cells"]}),
            3,
        )

    def test_missing_failed_and_mismatched_cells_are_unknown_no_go(self) -> None:
        trusted, contracts, keys, identities = self._trusted_matrix()
        windows_evidence = trusted["windows-x86_64"]
        windows = self._write_evidence(
            "windows-x86_64",
            windows_evidence,
        )
        linux = self._write_evidence(
            "linux-x86_64-gnu",
            self._evidence("linux-x86_64-gnu", status="failed"),
        )
        mac_evidence = self._evidence("macos-recorded-arch")
        mac_evidence["bindings"]["candidate_tree_sha256"] = "0" * 64
        mac = self._write_evidence("macos-recorded-arch", mac_evidence)
        result = matrix.summarize_evidence(
            evidence_paths={
                "windows-x86_64": windows,
                "linux-x86_64-gnu": linux,
                "macos-recorded-arch": mac,
            },
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys=keys,
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["pin_status"], "provisional")
        self.assertEqual(
            [cell["outcome"] for cell in result["cells"]],
            ["passed", "unknown", "unknown"],
        )
        self.assertIn("cell-failed", result["reason_codes"])
        self.assertIn("cell-mismatched", result["reason_codes"])

        missing = matrix.summarize_evidence(
            evidence_paths={"windows-x86_64": windows},
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys=keys,
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(missing["decision"], "no-go")
        self.assertIn("cell-unrun", missing["reason_codes"])

    def test_summary_rejects_reused_execution_or_runner(self) -> None:
        execution_id = str(uuid.uuid4())
        paths = {}
        keys: dict[str, dict[str, bytes]] = {}
        contracts: dict[str, str] = {}
        identities: dict[str, str] = {}
        for cell_id in matrix.REQUIRED_CELLS:
            evidence = self._evidence(
                cell_id,
                execution_id=execution_id,
                runner_name="same-runner",
            )
            signed, contract, trusted = self._trusted_evidence(cell_id, evidence)
            paths[cell_id] = self._write_evidence(cell_id, signed)
            contracts[cell_id] = contract
            keys[cell_id] = trusted
            identities[cell_id] = matrix._runner_identity_sha256(
                signed["execution"]
            )
        result = matrix.summarize_evidence(
            evidence_paths=paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys=keys,
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertIn("execution-reused", result["reason_codes"])
        self.assertIn("runner-reused", result["reason_codes"])

    def test_summary_rejects_reused_trusted_runner_key(self) -> None:
        shared_key = hashlib.sha256(b"shared-runner-key").digest()
        paths: dict[str, Path] = {}
        contracts: dict[str, str] = {}
        identities: dict[str, str] = {}
        for cell_id in matrix.REQUIRED_CELLS:
            evidence = self._evidence(cell_id)
            contract = matrix._command_contract_sha256(evidence["commands"])
            runner_os, architecture, libc, _ = self._platform(cell_id)
            with mock.patch.object(
                matrix,
                "_current_platform",
                return_value=(runner_os, architecture, libc),
            ):
                signed = matrix._attest_cell_evidence(
                    evidence,
                    key=shared_key,
                    expected_command_contract_sha256=contract,
                )
            paths[cell_id] = self._write_evidence(cell_id, signed)
            contracts[cell_id] = contract
            identities[cell_id] = matrix._runner_identity_sha256(
                signed["execution"]
            )
        key_id = matrix._attestation_key_id(shared_key)
        result = matrix.summarize_evidence(
            evidence_paths=paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys={
                cell_id: {key_id: shared_key}
                for cell_id in matrix.REQUIRED_CELLS
            },
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertIn("attestation-key-reused", result["reason_codes"])

    def test_three_cell_cyclic_key_swap_cannot_promote(self) -> None:
        evidence, contracts, keys, identities = self._trusted_matrix()
        paths = {
            cell_id: self._write_evidence(cell_id, evidence[cell_id])
            for cell_id in matrix.REQUIRED_CELLS
        }
        cells = list(matrix.REQUIRED_CELLS)
        cyclic_keys = {
            cell_id: keys[cells[(index + 1) % len(cells)]]
            for index, cell_id in enumerate(cells)
        }
        result = matrix.summarize_evidence(
            evidence_paths=paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys=cyclic_keys,
            expected_command_contracts=contracts,
            expected_runner_identities=identities,
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertFalse(result["promotion_eligible"])
        self.assertEqual(
            [cell["outcome"] for cell in result["cells"]],
            ["unknown", "unknown", "unknown"],
        )

    def test_cross_cell_runner_credentials_cannot_promote(self) -> None:
        evidence, contracts, keys, identities = self._trusted_matrix()
        paths = {
            cell_id: self._write_evidence(cell_id, evidence[cell_id])
            for cell_id in matrix.REQUIRED_CELLS
        }
        cells = list(matrix.REQUIRED_CELLS)
        cyclic_identities = {
            cell_id: identities[cells[(index + 1) % len(cells)]]
            for index, cell_id in enumerate(cells)
        }
        result = matrix.summarize_evidence(
            evidence_paths=paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
            trusted_attestation_keys=keys,
            expected_command_contracts=contracts,
            expected_runner_identities=cyclic_identities,
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertFalse(result["promotion_eligible"])
        self.assertEqual(
            [cell["outcome"] for cell in result["cells"]],
            ["unknown", "unknown", "unknown"],
        )

    def test_trust_configuration_rejects_missing_and_duplicate_cells(self) -> None:
        _, contracts, keys, identities = self._trusted_matrix()
        windows = "windows-x86_64"
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.summarize_evidence(
                evidence_paths={},
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
                trusted_attestation_keys={windows: keys[windows]},
                expected_command_contracts={windows: contracts[windows]},
                expected_runner_identities={windows: identities[windows]},
            )
        self.assertEqual(raised.exception.code, "argument_invalid")

        output = self.root / "summary.json"
        common = [
            "--candidate-archive",
            str(self.archive),
            "--candidate-archive-sha256",
            self.archive_sha256,
            "--candidate-descriptor",
            str(self.descriptor),
            "--candidate-descriptor-sha256",
            self.descriptor_sha256,
            "--candidate-tree-sha256",
            self.candidate_tree_sha256,
            "--wheel",
            str(self.wheel),
            "--wheel-sha256",
            self.wheel_sha256,
        ]
        with mock.patch.dict(os.environ, {"WINDOWS_TEST_KEY": "k" * 32}):
            with mock.patch.object(matrix, "_emit") as emit:
                exit_code = matrix.main(
                    [
                        "summarize",
                        *common,
                        "--trusted-attestation-key-env",
                        f"{windows}=WINDOWS_TEST_KEY",
                        "--trusted-attestation-key-env",
                        f"{windows}=WINDOWS_TEST_KEY",
                        "--output",
                        str(output),
                    ]
                )
        self.assertEqual(exit_code, 2)
        payload = emit.call_args.args[0]
        self.assertEqual(payload["error"]["code"], "argument_invalid")

    def test_placeholder_and_unattested_evidence_never_promote(self) -> None:
        paths = {
            cell_id: self._write_evidence(cell_id, self._evidence(cell_id))
            for cell_id in matrix.REQUIRED_CELLS
        }
        result = matrix.summarize_evidence(
            evidence_paths=paths,
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
        )
        self.assertEqual(result["decision"], "no-go")
        self.assertFalse(result["promotion_eligible"])
        self.assertIn("cell-mismatched", result["reason_codes"])

        no_cells = matrix.summarize_evidence(
            evidence_paths={},
            expected_bindings=self.verified["bindings"],
            toolchain=self.verified["toolchain"],
        )
        self.assertEqual(no_cells["status"], "unknown")
        self.assertEqual(no_cells["decision"], "no-go")
        self.assertFalse(no_cells["promotion_eligible"])

        placeholder = self._evidence("windows-x86_64")
        approved_contract = matrix._command_contract_sha256(
            placeholder["commands"]
        )
        placeholder["commands"][0]["argv"] = ["runner", "candidate-preflight"]
        with mock.patch.object(
            matrix,
            "_current_platform",
            return_value=("windows", "x86_64", "not-applicable"),
        ):
            with self.assertRaises(matrix.MatrixError) as raised:
                matrix._attest_cell_evidence(
                    placeholder,
                    key=self.attestation_keys["windows-x86_64"],
                    expected_command_contract_sha256=approved_contract,
                )
        self.assertEqual(raised.exception.code, "command_contract_mismatch")

    def test_tampered_attested_evidence_cannot_promote(self) -> None:
        cases = (
            ("argv", "command_contract_mismatch"),
            ("output", "output_digest_mismatch"),
            ("platform", "cell_mismatch"),
            ("cleanup", "cleanup_failed"),
            ("binding", "binding_mismatch"),
        )
        for case, code in cases:
            with self.subTest(case=case):
                evidence, contract, keys = self._trusted_evidence(
                    "windows-x86_64"
                )
                if case == "argv":
                    evidence["commands"][0]["argv"].append("--tampered")
                elif case == "output":
                    evidence["commands"][0]["stdout_b64"] = base64.b64encode(
                        b"tampered"
                    ).decode("ascii")
                elif case == "platform":
                    evidence["environment"]["architecture"] = "aarch64"
                elif case == "cleanup":
                    evidence["cleanup"]["fixture_removed"] = False
                else:
                    evidence["bindings"]["wheel_sha256"] = "0" * 64
                with self.assertRaises(matrix.MatrixError) as raised:
                    matrix.validate_cell_evidence(
                        evidence,
                        expected_cell="windows-x86_64",
                        expected_bindings=self.verified["bindings"],
                        toolchain=self.verified["toolchain"],
                        trusted_attestation_keys=keys,
                        expected_command_contract_sha256=contract,
                        expected_runner_identity_sha256=(
                            matrix._runner_identity_sha256(
                                evidence["execution"]
                            )
                        ),
                    )
                self.assertEqual(raised.exception.code, code)

    def test_trusted_contract_binds_runner_identity_and_exact_output(self) -> None:
        evidence, contract, keys = self._trusted_evidence("windows-x86_64")
        evidence["execution"]["runner_name"] = "tampered-runner"
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.validate_cell_evidence(
                evidence,
                expected_cell="windows-x86_64",
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
                trusted_attestation_keys=keys,
                expected_command_contract_sha256=contract,
                expected_runner_identity_sha256=(
                    matrix._runner_identity_sha256(evidence["execution"])
                ),
            )
        self.assertEqual(
            raised.exception.code,
            "attestation_identity_mismatch",
        )

    def test_current_platform_check_does_not_cross_claim_another_cell(self) -> None:
        current = platform.system().lower()
        other = (
            "windows-x86_64"
            if current != "windows"
            else "linux-x86_64-gnu"
        )
        with self.assertRaises(matrix.MatrixError) as raised:
            matrix.validate_cell_evidence(
                self._evidence(other),
                expected_cell=other,
                expected_bindings=self.verified["bindings"],
                toolchain=self.verified["toolchain"],
                require_current_platform=True,
            )
        self.assertEqual(raised.exception.code, "current_platform_mismatch")

    def test_cli_describes_protocol_without_claiming_execution(self) -> None:
        process = subprocess.run(
            [sys.executable, str(DRIVER_PATH), "describe"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["ok"])
        result = payload["result"]
        self.assertEqual(result["required_cells"], list(matrix.REQUIRED_CELLS))
        self.assertIn("missing", result["non_promotion_rule"])
        self.assertTrue(result["trust_binding_required"])

    def test_workflow_is_a_read_only_evidence_wrapper(self) -> None:
        workflow = (
            REPOSITORY_ROOT
            / ".github"
            / "workflows"
            / "xc-stage1-package-spike.yml"
        )
        source = workflow.read_text(encoding="utf-8")
        lower = source.lower()
        self.assertIn("permissions:", source)
        self.assertIn("contents: read", source)
        self.assertIn("actions: read", source)
        self.assertNotIn("contents: write", lower)
        self.assertNotIn("packages: write", lower)
        self.assertNotIn("id-token: write", lower)
        self.assertNotIn("/releases", lower)
        self.assertNotIn("pypi", lower)
        self.assertNotIn("twine", lower)
        self.assertIn("windows-x86_64", source)
        self.assertIn("linux-x86_64-gnu", source)
        self.assertIn("macos-recorded-arch", source)
        self.assertGreaterEqual(source.count("run_stage1_matrix.py"), 3)
        self.assertIn("summarize", source)
        self.assertNotIn("--trusted-attestation-key-env", source)
        self.assertNotIn("uv build", source)


if __name__ == "__main__":
    unittest.main()
