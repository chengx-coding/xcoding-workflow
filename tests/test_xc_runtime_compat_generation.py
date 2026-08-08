from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
RUNTIME_SCRIPTS = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "scripts"
)
GENERATED_ROOT = RUNTIME_SCRIPTS / "_runtime_compat"
SYNC_SCRIPT = REPOSITORY_ROOT / "scripts" / "sync_runtime_compat.py"

sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(RUNTIME_SCRIPTS))

from xcoding.runtime import application as canonical_application
from xcoding.runtime import core as canonical_core

import orchestration as legacy_application
import runtime_core as legacy_core
from _runtime_compat import application as generated_application
from _runtime_compat import core as generated_core


def load_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_runtime_compat",
        SYNC_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load sync_runtime_compat")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeCompatibilityGenerationTests(unittest.TestCase):
    def test_checked_in_payload_matches_canonical_modules(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SYNC_SCRIPT), "--check"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["counts"]["missing"], 0)
        self.assertEqual(payload["counts"]["unexpected"], 0)
        self.assertEqual(payload["counts"]["mismatched"], 0)

        manifest = json.loads(
            (GENERATED_ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema_version"], 1)
        for record in manifest["files"]:
            source = REPOSITORY_ROOT / record["source"]
            generated = REPOSITORY_ROOT / record["generated"]
            self.assertEqual(generated.read_bytes(), source.read_bytes())

    def test_legacy_core_forwards_public_and_private_symbols(self) -> None:
        self.assertIs(legacy_core, generated_core)
        canonical_public = {
            name for name in dir(canonical_core) if not name.startswith("_")
        }
        legacy_public = {
            name for name in dir(legacy_core) if not name.startswith("_")
        }
        self.assertEqual(legacy_public, canonical_public)
        for name in (
            "RuntimeErrorBase",
            "load_config",
            "runtime_write_lock",
            "complete_node",
            "tree_snapshot",
        ):
            self.assertIs(getattr(legacy_core, name), getattr(generated_core, name))
        self.assertIs(
            legacy_core._json_string_list,
            generated_core._json_string_list,
        )

    def test_legacy_application_is_the_generated_application(self) -> None:
        self.assertIs(legacy_application, generated_application)
        self.assertIs(generated_application.core, generated_core)
        self.assertIs(canonical_application.core, canonical_core)
        self.assertEqual(
            legacy_application.default_template().name,
            "minimal-template.xml",
        )

        adapter_source = (
            RUNTIME_SCRIPTS / "orchestration.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def runtime_mutation", adapter_source)
        self.assertNotIn("def cmd_complete", adapter_source)

    def test_application_execute_is_non_printing_and_stable(self) -> None:
        environment = canonical_application.RuntimeEnvironment(
            default_template=(
                REPOSITORY_ROOT
                / "skills"
                / "xc-orchestration-runtime"
                / "assets"
                / "minimal-template.xml"
            )
        )
        output = io.StringIO()
        with redirect_stdout(output):
            success = canonical_application.execute(
                [
                    "validate",
                    "--tree",
                    str(environment.default_template),
                ],
                environment,
            )
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(success.exit_code, 0)
        self.assertTrue(success.payload["ok"])
        self.assertTrue(success.payload["valid"])

        missing = canonical_application.execute(
            [
                "summary",
                "--tree",
                str(REPOSITORY_ROOT / "missing-runtime.xml"),
            ],
            environment,
        )
        self.assertEqual(missing.exit_code, 2)
        self.assertFalse(missing.payload["ok"])
        self.assertEqual(missing.payload["error"]["code"], "runtime_error")

        with mock.patch.object(
            canonical_application,
            "cmd_validate",
            return_value={"valid": False},
        ):
            invalid = canonical_application.execute(
                ["validate", "--tree", "unused"],
                environment,
            )
        self.assertEqual(invalid.exit_code, 1)
        self.assertTrue(invalid.payload["ok"])
        self.assertFalse(invalid.payload["valid"])

        with mock.patch.object(
            canonical_application.core,
            "read_tree_with_integrity",
            side_effect=OSError("read failed"),
        ):
            os_error = canonical_application.execute(
                ["summary", "--tree", "unreadable"],
                environment,
            )
        self.assertEqual(os_error.exit_code, 2)
        self.assertEqual(os_error.payload["error"]["code"], "os_error")

    def test_application_environment_is_request_scoped(self) -> None:
        source_template = (
            REPOSITORY_ROOT
            / "skills"
            / "xc-orchestration-runtime"
            / "assets"
            / "minimal-template.xml"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_template = root / "first.xml"
            second_template = root / "second.xml"
            first_template.write_bytes(source_template.read_bytes())
            second_template.write_bytes(source_template.read_bytes())

            first = canonical_application.execute(
                [
                    "init",
                    "--runtime-path",
                    str(root / "first-runtime"),
                    "--work-order-id",
                    "first-work-order",
                ],
                canonical_application.RuntimeEnvironment(first_template),
            )
            second = canonical_application.execute(
                [
                    "init",
                    "--runtime-path",
                    str(root / "second-runtime"),
                    "--work-order-id",
                    "second-work-order",
                ],
                canonical_application.RuntimeEnvironment(second_template),
            )
            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            self.assertEqual(first.payload["template"], str(first_template))
            self.assertEqual(second.payload["template"], str(second_template))

    def test_sync_detects_tampering_without_writing(self) -> None:
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            canonical = project / module.CANONICAL_RELATIVE_ROOT
            target_parent = (
                project / module.GENERATED_RELATIVE_ROOT
            ).parent
            canonical.parent.mkdir(parents=True)
            target_parent.mkdir(parents=True)
            shutil.copytree(
                REPOSITORY_ROOT / module.CANONICAL_RELATIVE_ROOT,
                canonical,
            )

            synced = module.sync_payload(project)
            self.assertTrue(synced["valid"])
            generated_core_path = (
                project / module.GENERATED_RELATIVE_ROOT / "core.py"
            )
            generated_core_path.write_bytes(
                generated_core_path.read_bytes() + b"\n# tampered\n"
            )

            checked = module.check_payload(project)
            self.assertFalse(checked["valid"])
            self.assertEqual(
                [item["path"] for item in checked["mismatched"]],
                ["core.py"],
            )
            self.assertTrue(generated_core_path.read_bytes().endswith(b"tampered\n"))

    def test_legacy_cli_and_viewer_import_generated_core(self) -> None:
        help_result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(RUNTIME_SCRIPTS / "orchestration.py"),
                "--help",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            help_result.returncode,
            0,
            help_result.stderr or help_result.stdout,
        )
        self.assertIn("retry-failed", help_result.stdout)

        import_result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    "import sys;"
                    f"sys.path.insert(0, {str(RUNTIME_SCRIPTS)!r});"
                    "import viewer_server, runtime_core;"
                    "assert runtime_core.calculate_checksum"
                ),
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            import_result.returncode,
            0,
            import_result.stderr or import_result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
