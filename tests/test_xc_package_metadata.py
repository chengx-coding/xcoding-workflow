from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding import doctor
from xcoding.bundle.resources import DISTRIBUTION_NAME
from xcoding.delegation.errors import DelegationError


class PackageMetadataTests(unittest.TestCase):
    def test_formal_distribution_metadata(self) -> None:
        project = tomllib.loads(
            (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]

        self.assertEqual(project["name"], "xcoding-workflow")
        self.assertEqual(DISTRIBUTION_NAME, project["name"])
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.12")
        self.assertNotIn(
            "Development Status :: 2 - Pre-Alpha",
            project["classifiers"],
        )

    def test_python_readiness_boundaries_and_evidence_tiers(self) -> None:
        cases = (
            ("CPython", (3, 12, 0), True, "accepted-not-formally-verified"),
            ("CPython", (3, 12, 13), True, "formal-verification-baseline"),
            ("CPython", (3, 14, 3), True, "accepted-not-formally-verified"),
            ("CPython", (3, 11, 9), False, "unsupported"),
            ("PyPy", (3, 12, 13), False, "unsupported"),
        )
        for implementation, version, ready, evidence_tier in cases:
            with self.subTest(implementation=implementation, version=version):
                status = doctor.python_readiness(implementation, version)
                self.assertIs(status["ready"], ready)
                self.assertEqual(status["minimum_version"], "3.12")
                self.assertEqual(
                    status["formal_verification_baseline"],
                    "3.12.13",
                )
                self.assertEqual(status["evidence_tier"], evidence_tier)
                self.assertIs(
                    status["matches_formal_verification_baseline"],
                    implementation == "CPython" and version == (3, 12, 13),
                )

    def test_doctor_reports_non_formal_accepted_runtime_evidence(self) -> None:
        inspection = mock.Mock()
        inspection.manifest = SimpleNamespace(
            python_requires=">=3.12",
            resources=tuple(
                SimpleNamespace(
                    kind="host-adapter",
                    adapter_id=adapter_id,
                )
                for adapter_id in (
                    "claude-code",
                    "codex",
                    "opencode",
                    "trae",
                )
            ),
        )
        inspection.as_dict.return_value = {"resource_count": 1}
        with (
            mock.patch.object(
                doctor,
                "inspect_installed_bundle",
                return_value=inspection,
            ),
            mock.patch.object(
                doctor.platform,
                "python_implementation",
                return_value="CPython",
            ),
            mock.patch.object(
                doctor.platform,
                "python_version",
                return_value="3.14.3",
            ),
            mock.patch.object(doctor.sys, "version_info", (3, 14, 3)),
            mock.patch.object(
                doctor.shutil,
                "which",
                side_effect=lambda name: f"/{name}",
            ),
            mock.patch.object(
                doctor.importlib.util,
                "find_spec",
                return_value=None,
            ),
            mock.patch.object(
                doctor,
                "installed_bundle_root",
                return_value=object(),
            ),
            mock.patch.object(
                doctor,
                "load_bundle_adapter_statement",
                side_effect=lambda _root, adapter_id: {
                    "adapter_id": adapter_id,
                    "adapter_version": "unverified",
                    "mode": "validated-only",
                    "evidence": [],
                    "capabilities": [],
                },
            ),
        ):
            report = doctor.doctor_report()

        python_check = next(
            check for check in report["checks"] if check["id"] == "python"
        )
        self.assertEqual(python_check["status"], "pass")
        self.assertEqual(
            python_check["details"]["evidence_tier"],
            "accepted-not-formally-verified",
        )
        self.assertIs(
            python_check["details"][
                "matches_formal_verification_baseline"
            ],
            False,
        )
        adapter_check = next(
            check
            for check in report["checks"]
            if check["id"] == "delegation-adapters"
        )
        self.assertEqual(adapter_check["status"], "pass")
        self.assertEqual(
            [
                statement["adapter_id"]
                for statement in adapter_check["details"]["statements"]
            ],
            ["claude-code", "codex", "opencode", "trae"],
        )
        self.assertTrue(
            all(
                statement["mode"] == "validated-only"
                for statement in adapter_check["details"]["statements"]
            )
        )
        self.assertEqual(
            sum(
                warning["code"] == "delegation-adapter-not-enforced"
                for warning in report["warnings"]
            ),
            4,
        )

    def test_doctor_fails_closed_on_invalid_adapter_statement(self) -> None:
        inspection = SimpleNamespace(
            manifest=SimpleNamespace(
                resources=(
                    SimpleNamespace(
                        kind="host-adapter",
                        adapter_id="codex",
                    ),
                )
            )
        )
        error = DelegationError(
            "json_not_canonical",
            "adapter",
            "invalid statement",
        )
        with mock.patch.object(
            doctor,
            "load_bundle_adapter_statement",
            side_effect=error,
        ):
            result = doctor.delegation_adapter_readiness(
                inspection,
                object(),
            )

        self.assertFalse(result["ready"])
        self.assertEqual(result["statements"], [])
        self.assertEqual(
            result["errors"],
            [
                {
                    "adapter_id": "codex",
                    "code": "json_not_canonical",
                    "phase": "adapter",
                    "message": "invalid statement",
                }
            ],
        )

    def test_doctor_rejects_unsubstantiated_enforced_adapter_statement(
        self,
    ) -> None:
        inspection = SimpleNamespace(
            manifest=SimpleNamespace(
                resources=(
                    SimpleNamespace(
                        kind="host-adapter",
                        adapter_id="codex",
                    ),
                )
            )
        )
        source = json.loads(
            (
                REPOSITORY_ROOT
                / "skills"
                / "xc-delegation"
                / "assets"
                / "adapters"
                / "codex.json"
            ).read_text(encoding="utf-8")
        )
        source["mode"] = "enforced"
        for capability in source["capabilities"]:
            capability["support"] = "enforced"

        with tempfile.TemporaryDirectory() as temporary:
            bundle_root = Path(temporary)
            target = (
                bundle_root
                / "skills"
                / "xc-delegation"
                / "assets"
                / "adapters"
                / "codex.json"
            )
            target.parent.mkdir(parents=True)
            target.write_text(
                json.dumps(
                    source,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
                newline="",
            )
            result = doctor.delegation_adapter_readiness(
                inspection,
                bundle_root,
            )

        self.assertFalse(result["ready"])
        self.assertEqual(result["statements"], [])
        self.assertEqual(
            result["errors"][0]["code"],
            "adapter_version_unpinned",
        )


if __name__ == "__main__":
    unittest.main()
