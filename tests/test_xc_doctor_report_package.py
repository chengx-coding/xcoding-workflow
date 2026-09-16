"""Tests for the report-package readiness probe and the recorded install path.

Two facts a consumer needs before a work order reaches `report-group`:

* `xcoding doctor --target-root <project>` names a missing `xc-change-report` package as a
  finding, so the failure a supported install can deliver is diagnosable before the work
  order reaches the node that mounts the report.
* `xcoding setup` records the resolved absolute path of the installed report package and the
  template inside it, which is the record the mount instruction resolves the subtree
  template from instead of a host-to-Skill-root documentation table.

The installed Bundle describes this `xcoding` installation and not the probed project, so
the tests replace that one seam and leave the probe under test as the only variable; the
setup tests build their own Bundle fixture for the same reason.

Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding import doctor as doctor_module
from xcoding import setup_transaction as setup_module
from xcoding.bundle.manifest import ResourceRecord


PROBE_CHECK = "skill-packages"
PACKAGE_MISSING = "report-package-missing"
TEMPLATE_MISSING = "report-template-missing"
PATH_MISMATCH = "report-package-path-mismatch"
PACKAGES_ABSENT = "skill-packages-absent"


def _record(
    kind: str,
    bundle_path: str,
    data: bytes,
    adapter_id: str | None = None,
) -> ResourceRecord:
    return ResourceRecord(
        kind=kind,
        adapter_id=adapter_id,
        source_path=bundle_path,
        bundle_path=bundle_path,
        size=len(data),
        sha256=setup_module._sha256(data),
    )


def _statement(adapter_id: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "xc-delegation-adapter-capabilities/v1",
        "adapter_id": adapter_id,
        "adapter_version": "fixture",
        "mode": "validated-only",
        "evidence": [],
        "capabilities": [],
    }


def _installed_bundle_inspection() -> SimpleNamespace:
    """The Bundle seam of the running `xcoding`, replaced by one host adapter partition."""
    data = b"developer_instructions = \"delegate\"\n"
    record = _record("host-adapter", "adapters/codex/delegate-agent.toml", data, "codex")
    return SimpleNamespace(
        manifest=SimpleNamespace(
            resources=(record,),
            xc_version="0.1.0",
            python_requires=">=3.12",
        ),
        manifest_sha256="a" * 64,
        as_dict=lambda: {"resource_count": 1, "xc_version": "0.1.0"},
    )


class DoctorReportPackageTests(unittest.TestCase):
    """The probe that reports the report capability of a probed project."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.patches = (
            mock.patch.object(
                doctor_module,
                "inspect_installed_bundle",
                return_value=_installed_bundle_inspection(),
            ),
            mock.patch.object(
                doctor_module,
                "installed_bundle_root",
                return_value=self.root / "bundle",
            ),
            mock.patch.object(
                doctor_module,
                "load_bundle_adapter_statement",
                side_effect=lambda _root, adapter_id: _statement(adapter_id),
            ),
        )
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def install(self, skill_root: str, package: str) -> Path:
        directory = self.project.joinpath(*skill_root.split("/"), package)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {package}\n---\n",
            encoding="utf-8",
        )
        return directory

    def record(self, **fields: object) -> Path:
        path = self.project / ".agents/.xcoding-setup/manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(fields, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="",
        )
        return path

    def check(self, report: dict[str, object]) -> dict[str, object]:
        return next(
            item for item in report["checks"] if item["id"] == PROBE_CHECK
        )

    def test_missing_report_package_is_a_named_finding(self) -> None:
        """G-47: a Skill root that holds XC packages but not the report package fails."""
        self.install(".agents/skills", "xc-analysis")
        package_path = self.project / ".agents/skills" / setup_module.REPORT_PACKAGE

        with self.assertRaises(doctor_module.DoctorReadinessError) as caught:
            doctor_module.doctor_report(self.project)

        self.assertEqual(caught.exception.code, "readiness-failed")
        report = caught.exception.details["report"]
        self.assertIs(report["ready"], False)
        check = self.check(report)
        self.assertEqual(check["status"], "fail")
        self.assertIs(check["required"], True)
        self.assertEqual(check["details"]["findings"], [PACKAGE_MISSING])
        finding = check["details"]["missing"][0]
        self.assertEqual(finding["code"], PACKAGE_MISSING)
        self.assertEqual(finding["artifact"], "package")
        self.assertEqual(finding["path"], str(package_path))
        self.assertTrue(Path(finding["path"]).is_absolute(), finding)
        self.assertIn(setup_module.REPORT_PACKAGE, finding["message"])
        self.assertIn(
            PACKAGE_MISSING,
            [warning["code"] for warning in report["warnings"]],
        )

    def test_present_report_package_names_the_resolved_template(self) -> None:
        """The package and its template make the probe pass and report both paths."""
        package = self.install(".agents/skills", setup_module.REPORT_PACKAGE)
        template = package / "assets" / "change-report-template.xml"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text("<root/>\n", encoding="utf-8")

        report = doctor_module.doctor_report(self.project)

        self.assertIs(report["ready"], True)
        check = self.check(report)
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["details"]["findings"], [])
        self.assertEqual(check["details"]["missing"], [])
        installed = check["details"]["installed_roots"][0]
        self.assertEqual(installed["host"], "codex")
        self.assertEqual(installed["package_path"], str(package))
        self.assertIs(installed["package_present"], True)
        self.assertEqual(installed["template_path"], str(template))
        self.assertIs(installed["template_present"], True)

    def test_template_missing_inside_the_package_is_a_finding(self) -> None:
        """A package without the subtree template fails with its own named finding."""
        package = self.install(".agents/skills", setup_module.REPORT_PACKAGE)

        with self.assertRaises(doctor_module.DoctorReadinessError) as caught:
            doctor_module.doctor_report(self.project)

        check = self.check(caught.exception.details["report"])
        self.assertEqual(check["details"]["findings"], [TEMPLATE_MISSING])
        finding = check["details"]["missing"][0]
        self.assertEqual(finding["artifact"], "template")
        self.assertEqual(
            finding["path"],
            str(package / "assets" / "change-report-template.xml"),
        )

    def test_recorded_host_without_the_package_is_named(self) -> None:
        """The setup record names the installed hosts, so drift on one of them is reported."""
        package = self.install(".agents/skills", setup_module.REPORT_PACKAGE)
        template = package / "assets" / "change-report-template.xml"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text("<root/>\n", encoding="utf-8")
        self.install(".claude/skills", "xc-analysis")
        self.record(
            hosts=["claude-code", "codex"],
            report_package={
                "name": setup_module.REPORT_PACKAGE,
                "template_file": setup_module.REPORT_TEMPLATE_RELATIVE.as_posix(),
                "paths": {"codex": str(package)},
            },
        )

        with self.assertRaises(doctor_module.DoctorReadinessError) as caught:
            doctor_module.doctor_report(self.project)

        check = self.check(caught.exception.details["report"])
        self.assertEqual(check["details"]["findings"], [PACKAGE_MISSING])
        self.assertEqual(
            check["details"]["missing"][0]["path"],
            str(self.project / ".claude/skills" / setup_module.REPORT_PACKAGE),
        )
        self.assertEqual(check["details"]["record"]["hosts"], ["claude-code", "codex"])
        self.assertEqual(
            check["details"]["record"]["report_package_paths"],
            {"codex": str(package)},
        )

    def test_recorded_package_path_that_disagrees_with_the_host_table_is_named(self) -> None:
        """R-06: a record that names a different directory than the disk is a finding.

        The mount resolves the subtree template from the record, so a wrong recorded path
        used to be invisible here: the probe echoed the value back while probing the
        table-derived directory, and the disagreement surfaced only when the report node ran.
        """
        package = self.install(".agents/skills", setup_module.REPORT_PACKAGE)
        template = package / "assets" / "change-report-template.xml"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text("<root/>\n", encoding="utf-8")
        elsewhere = self.root / "elsewhere" / setup_module.REPORT_PACKAGE

        def record_with(codex_path: str) -> None:
            self.record(
                hosts=["codex"],
                report_package={
                    "name": setup_module.REPORT_PACKAGE,
                    "template_file": setup_module.REPORT_TEMPLATE_RELATIVE.as_posix(),
                    "paths": {"codex": codex_path},
                },
            )

        record_with(str(elsewhere))

        with self.assertRaises(doctor_module.DoctorReadinessError) as caught:
            doctor_module.doctor_report(self.project)

        check = self.check(caught.exception.details["report"])
        self.assertEqual(check["status"], "fail")
        self.assertEqual(check["details"]["findings"], [PATH_MISMATCH])
        finding = check["details"]["missing"][0]
        self.assertEqual(finding["code"], PATH_MISMATCH)
        self.assertEqual(finding["artifact"], "record")
        self.assertEqual(finding["path"], str(elsewhere))
        self.assertIn(str(package), finding["message"])
        installed = check["details"]["installed_roots"][0]
        self.assertEqual(installed["package_path"], str(package))
        self.assertEqual(installed["recorded_package_path"], str(elsewhere))
        self.assertIs(installed["recorded_path_matches"], False)
        self.assertIs(installed["package_present"], True)

        # The same project with the recorded directory the host table resolves carries no
        # finding: the probe compares the record against the disk, it does not merely echo it.
        record_with(str(package))

        report = doctor_module.doctor_report(self.project)

        check = self.check(report)
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["details"]["findings"], [])
        self.assertIs(check["details"]["installed_roots"][0]["recorded_path_matches"], True)

    def test_project_without_a_skill_root_is_not_reported_as_missing(self) -> None:
        """A project that holds no XC package is not a project with a missing package."""
        report = doctor_module.doctor_report(self.project)

        self.assertIs(report["ready"], True)
        check = self.check(report)
        self.assertEqual(check["status"], "pass")
        self.assertIs(check["details"]["installed"], False)
        self.assertEqual(check["details"]["installed_roots"], [])
        self.assertEqual(check["details"]["missing"], [])
        self.assertIn(
            PACKAGES_ABSENT,
            [warning["code"] for warning in report["warnings"]],
        )

    def test_doctor_without_a_target_root_does_not_probe_a_project(self) -> None:
        """`xcoding doctor` without a target root keeps its previous probe set."""
        report = doctor_module.doctor_report()

        check = self.check(report)
        self.assertEqual(check["status"], "not-requested")
        self.assertIs(check["required"], False)
        self.assertNotIn(
            PACKAGES_ABSENT,
            [warning["code"] for warning in report["warnings"]],
        )


class SetupReportPackageRecordTests(unittest.TestCase):
    """The setup record the mount instruction resolves the subtree template from."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.bundle = Path(self.temporary.name) / "bundle"
        entries: dict[str, tuple[str, str | None, bytes]] = {
            "skills/xc-alpha/SKILL.md": ("skill", None, b"---\nname: xc-alpha\n---\n"),
            "skills/xc-change-report/SKILL.md": (
                "skill",
                None,
                b"---\nname: xc-change-report\n---\n",
            ),
            "skills/xc-change-report/assets/change-report-template.xml": (
                "skill",
                None,
                b"<root/>\n",
            ),
        }
        for adapter_id in setup_module.HOST_ORDER:
            entries[
                f"skills/xc-delegation/assets/adapters/{adapter_id}.json"
            ] = (
                "skill",
                None,
                (
                    json.dumps(
                        _statement(adapter_id),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8"),
            )
            entries[f"adapters/{adapter_id}/delegate-agent.toml"] = (
                "host-adapter",
                adapter_id,
                b"developer_instructions = \"delegate\"\n",
            )
        resources = []
        for bundle_path, (kind, adapter_id, data) in entries.items():
            path = self.bundle.joinpath(*bundle_path.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            resources.append(_record(kind, bundle_path, data, adapter_id))
        self.inspection = SimpleNamespace(
            manifest=SimpleNamespace(resources=tuple(resources), xc_version="0.1.0"),
            manifest_sha256="a" * 64,
        )
        self.patches = (
            mock.patch.object(
                setup_module,
                "inspect_installed_bundle",
                return_value=self.inspection,
            ),
            mock.patch.object(
                setup_module,
                "installed_bundle_root",
                return_value=self.bundle,
            ),
        )
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def record_path(self) -> Path:
        return self.root / ".agents/.xcoding-setup/manifest.json"

    def manifest(self) -> dict[str, object]:
        return json.loads(self.record_path().read_text(encoding="utf-8"))

    def test_setup_records_the_installed_template_path(self) -> None:
        """G-48: the record holds the resolved absolute path of the installed package."""
        setup_module.setup(self.root, ["codex", "claude-code"])

        record = self.manifest()["report_package"]
        self.assertEqual(record["name"], setup_module.REPORT_PACKAGE)
        self.assertEqual(
            record["template_file"],
            setup_module.REPORT_TEMPLATE_RELATIVE.as_posix(),
        )
        resolved_root = Path(os.path.realpath(self.root))
        self.assertEqual(
            record["paths"],
            {
                "codex": str(resolved_root / ".agents/skills/xc-change-report"),
                "claude-code": str(resolved_root / ".claude/skills/xc-change-report"),
            },
        )
        for host, path in record["paths"].items():
            with self.subTest(host=host):
                package = Path(path)
                self.assertTrue(package.is_absolute(), path)
                self.assertEqual(package, Path(os.path.realpath(package)), path)
                self.assertTrue(package.is_relative_to(resolved_root), path)
                self.assertTrue((package / "SKILL.md").is_file(), path)
                self.assertTrue((package / record["template_file"]).is_file(), path)

    def test_dry_run_reports_the_path_the_transaction_would_record(self) -> None:
        """The plan of a zero-write dry run states the same resolved path."""
        plan = setup_module.setup(self.root, ["codex"], dry_run=True)

        self.assertIs(plan["writes_performed"], False)
        self.assertEqual(
            plan["report_package"]["paths"],
            {
                "codex": str(
                    Path(os.path.realpath(self.root))
                    / ".agents/skills/xc-change-report"
                )
            },
        )
        self.assertFalse(self.record_path().exists())

    def test_record_without_the_report_package_field_still_loads(self) -> None:
        """A record written before the field existed keeps working, so upgrades are safe."""
        setup_module.setup(self.root, ["codex"])
        record = self.manifest()
        del record["report_package"]
        self.record_path().write_bytes(setup_module._canonical_json(record))

        setup_module.setup(self.root, ["codex"])

        self.assertIn("report_package", self.manifest())

    def test_tampered_report_package_record_is_rejected(self) -> None:
        """The record is validated when present, so a corrupt path is not silently used."""
        setup_module.setup(self.root, ["codex"])
        record = self.manifest()
        record["report_package"]["paths"] = {"trae": "C:/elsewhere/xc-change-report"}
        self.record_path().write_bytes(setup_module._canonical_json(record))

        with self.assertRaises(setup_module.SetupTransactionError) as caught:
            setup_module.setup(self.root, ["codex"])

        self.assertEqual(caught.exception.code, "manifest_invalid")

    def test_probe_reads_the_path_the_setup_record_wrote(self) -> None:
        """The record and the probe agree: the recorded package is the probed package."""
        setup_module.setup(self.root, ["codex"])
        record = self.manifest()["report_package"]
        with (
            mock.patch.object(
                doctor_module,
                "inspect_installed_bundle",
                return_value=_installed_bundle_inspection(),
            ),
            mock.patch.object(
                doctor_module,
                "installed_bundle_root",
                return_value=self.root / "bundle",
            ),
            mock.patch.object(
                doctor_module,
                "load_bundle_adapter_statement",
                side_effect=lambda _root, adapter_id: _statement(adapter_id),
            ),
        ):
            report = doctor_module.doctor_report(self.root)

        check = next(
            item for item in report["checks"] if item["id"] == PROBE_CHECK
        )
        self.assertEqual(check["status"], "pass")
        self.assertEqual(
            check["details"]["record"]["report_package_paths"],
            record["paths"],
        )
        self.assertEqual(
            check["details"]["installed_roots"][0]["package_path"],
            record["paths"]["codex"],
        )


if __name__ == "__main__":
    unittest.main()
