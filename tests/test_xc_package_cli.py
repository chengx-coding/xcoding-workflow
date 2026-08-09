from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from build_support.bundle import CandidateProvenance, collect_bundle
from xcoding import cli
from xcoding import doctor as doctor_module
from xcoding import setup_plan as setup_module
from xcoding.bundle.manifest import inspect_bundle


PROVENANCE = CandidateProvenance(
    baseline_revision="1" * 40,
    candidate_tree_sha256="2" * 64,
    candidate_source_archive_sha256="3" * 64,
)
VERSION = "0.0.0.dev0"
ADAPTER = "claude-code"


def snapshot(root: Path) -> dict[str, object]:
    if not root.exists():
        return {"exists": False}
    entries: dict[str, object] = {}
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else path.relative_to(root).as_posix()
        metadata = path.lstat()
        if path.is_symlink():
            value: object = {
                "kind": "link",
                "mode": stat.S_IMODE(metadata.st_mode),
                "target": os.readlink(path),
            }
        elif path.is_file():
            value = {
                "kind": "file",
                "mode": stat.S_IMODE(metadata.st_mode),
                "bytes": path.read_bytes().hex(),
            }
        else:
            value = {
                "kind": "directory",
                "mode": stat.S_IMODE(metadata.st_mode),
            }
        entries[relative] = value
    return {"exists": True, "entries": entries}


class PackageCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        staging = cls.root / "bundle-staging"
        staging.mkdir()
        cls.bundle = collect_bundle(REPOSITORY_ROOT, staging, PROVENANCE)
        cls.install = cls._make_install("installed")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def _make_install(cls, name: str) -> Path:
        install = cls.root / name
        shutil.copytree(REPOSITORY_ROOT / "src" / "xcoding", install / "xcoding")
        shutil.copytree(cls.bundle, install / "xcoding" / "_bundle")
        metadata = install / f"xcoding_workflow_spike-{VERSION}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            "Metadata-Version: 2.3\n"
            "Name: xcoding-workflow-spike\n"
            f"Version: {VERSION}\n",
            encoding="utf-8",
            newline="",
        )
        return install

    def cli_environment(
        self,
        install: Path | None = None,
        *,
        path: str | None = None,
    ) -> dict[str, str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(install or self.install)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONNOUSERSITE"] = "1"
        if path is not None:
            environment["PATH"] = path
        return environment

    def run_cli(
        self,
        *arguments: str,
        install: Path | None = None,
        cwd: Path | None = None,
        path: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "xcoding", *arguments],
            cwd=cwd or self.root,
            env=self.cli_environment(install, path=path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.stderr, "")
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1, result.stdout)
        return result, json.loads(lines[0])

    def test_four_commands_emit_stable_success_envelopes(self) -> None:
        target = self.root / "success-target"
        commands = (
            ("version", ["version", "--json"]),
            ("bundle inspect", ["bundle", "inspect", "--json"]),
            ("doctor", ["doctor", "--json"]),
            (
                "setup",
                [
                    "setup",
                    "--dry-run",
                    "--json",
                    "--adapter",
                    ADAPTER,
                    "--target-root",
                    str(target),
                ],
            ),
        )
        for command, arguments in commands:
            with self.subTest(command=command):
                result, payload = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    set(payload),
                    {"schema_version", "ok", "command", "result"},
                )
                self.assertEqual(payload["schema_version"], 1)
                self.assertIs(payload["ok"], True)
                self.assertEqual(payload["command"], command)
        self.assertFalse(target.exists())

    def test_input_bundle_readiness_and_internal_exit_codes(self) -> None:
        cases = (
            (
                ["setup", "--dry-run", "--json", "--adapter", ADAPTER],
                "setup",
                "target-required",
            ),
            (
                [
                    "setup",
                    "--dry-run",
                    "--json",
                    "--target-root",
                    str(self.root / "target"),
                ],
                "setup",
                "adapter-required",
            ),
            (["version"], "version", "json-required"),
            (["next", "--json"], "", "invalid_arguments"),
        )
        for arguments, command, code in cases:
            with self.subTest(arguments=arguments):
                result, payload = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIs(payload["ok"], False)
                self.assertEqual(payload["command"], command)
                self.assertEqual(payload["error"]["code"], code)
                if code.endswith("-required") and command == "setup":
                    self.assertEqual(
                        payload["error"]["details"]["plan"]["operations"],
                        [],
                    )

        tampered = self._make_install("tampered")
        target = (
            tampered
            / "xcoding"
            / "_bundle"
            / "skills"
            / "xc-analysis"
            / "SKILL.md"
        )
        data = target.read_bytes()
        target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        result, payload = self.run_cli(
            "bundle",
            "inspect",
            "--json",
            install=tampered,
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["error"]["code"], "resource_hash_mismatch")

        result, payload = self.run_cli("doctor", "--json", path="")
        self.assertEqual(result.returncode, 4)
        self.assertEqual(payload["error"]["code"], "readiness-failed")

        output = io.StringIO()
        with (
            mock.patch.object(
                cli,
                "_execute",
                side_effect=RuntimeError("test failure"),
            ),
            contextlib.redirect_stdout(output),
        ):
            exit_code = cli.main(["version", "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 5)
        self.assertEqual(payload["error"]["code"], "internal_error")

    def test_setup_dry_run_reports_drift_without_any_write(self) -> None:
        controlled = self.root / "controlled"
        controlled.mkdir()
        missing = controlled / "missing-target"
        before = snapshot(controlled)
        result, payload = self.run_cli(
            "setup",
            "--dry-run",
            "--json",
            "--adapter",
            ADAPTER,
            "--target-root",
            str(missing),
        )
        self.assertEqual(result.returncode, 0)
        self.assertGreater(payload["result"]["drift"]["create"], 0)
        self.assertIs(payload["result"]["writes_performed"], False)
        self.assertEqual(snapshot(controlled), before)

        existing = controlled / "existing-target"
        existing.mkdir()
        record = next(
            record
            for record in inspect_bundle(
                self.bundle,
                expected_version=VERSION,
            ).manifest.resources
            if record.adapter_id == ADAPTER
        )
        relative = record.bundle_path.removeprefix(f"adapters/{ADAPTER}/")
        drifted = existing.joinpath(*relative.split("/"))
        drifted.parent.mkdir(parents=True, exist_ok=True)
        drifted.write_bytes(b"drift")
        before = snapshot(controlled)
        result, payload = self.run_cli(
            "setup",
            "--dry-run",
            "--json",
            "--adapter",
            ADAPTER,
            "--target-root",
            str(existing),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["result"]["drift"]["replace"], 1)
        self.assertEqual(snapshot(controlled), before)

    def test_read_only_target_is_reported_without_write_probe(self) -> None:
        target_root = self.root / "read-only-target"
        target_root.mkdir()
        record = next(
            record
            for record in inspect_bundle(
                self.bundle,
                expected_version=VERSION,
            ).manifest.resources
            if record.adapter_id == ADAPTER
        )
        relative = record.bundle_path.removeprefix(f"adapters/{ADAPTER}/")
        target = target_root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"drift")
        before = snapshot(target_root)
        inspection = inspect_bundle(self.bundle, expected_version=VERSION)

        with (
            mock.patch.object(
                setup_module,
                "inspect_installed_bundle",
                return_value=inspection,
            ),
            mock.patch.object(
                setup_module,
                "installed_bundle_root",
                return_value=self.bundle,
            ),
            mock.patch.object(setup_module.os, "access", return_value=False),
        ):
            with self.assertRaises(setup_module.SetupReadinessError) as raised:
                setup_module.setup_plan(ADAPTER, target_root)

        self.assertIs(
            raised.exception.details["plan"]["writes_performed"],
            False,
        )
        self.assertEqual(snapshot(target_root), before)

    def test_doctor_tk_absence_is_optional_and_never_imported(self) -> None:
        self.assertNotIn("tkinter", sys.modules)
        inspection = inspect_bundle(self.bundle, expected_version=VERSION)

        def which(name: str) -> str | None:
            return str(REPOSITORY_ROOT / "git") if name == "git" else None

        with (
            mock.patch.object(
                doctor_module,
                "inspect_installed_bundle",
                return_value=inspection,
            ),
            mock.patch.object(
                doctor_module.importlib.util,
                "find_spec",
                return_value=None,
            ),
            mock.patch.object(doctor_module.shutil, "which", side_effect=which),
        ):
            report = doctor_module.doctor_report()

        self.assertTrue(report["ready"])
        self.assertIn(
            "tk-unavailable",
            {warning["code"] for warning in report["warnings"]},
        )
        self.assertNotIn("tkinter", sys.modules)

    def test_public_commands_do_not_touch_tree_network_or_daemon_surfaces(self) -> None:
        sandbox = self.root / "public-boundary"
        sandbox.mkdir()
        tree = sandbox / "orchestration.xml"
        tree.write_bytes(b"sentinel")
        target = sandbox / "target"
        before = snapshot(sandbox)
        for arguments in (
            ["version", "--json"],
            ["bundle", "inspect", "--json"],
            ["doctor", "--json"],
            [
                "setup",
                "--dry-run",
                "--json",
                "--adapter",
                ADAPTER,
                "--target-root",
                str(target),
            ],
        ):
            result, _ = self.run_cli(*arguments, cwd=sandbox)
            self.assertEqual(result.returncode, 0)
        self.assertEqual(snapshot(sandbox), before)

        public_sources = (
            "cli.py",
            "doctor.py",
            "setup_plan.py",
            "version.py",
            "__main__.py",
        )
        for name in public_sources:
            source = (REPOSITORY_ROOT / "src" / "xcoding" / name).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("import socket", source)
            self.assertNotIn("import urllib", source)
            self.assertNotIn("import subprocess", source)
            self.assertNotIn("orchestration.xml", source)
            self.assertNotIn("runtime_core", source)

    def test_installed_runtime_init_uses_package_template(self) -> None:
        runtime_root = self.root / "installed-runtime-cli"
        initialized = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "runtime",
                "init",
                "--runtime-path",
                str(runtime_root),
                "--work-order-id",
                "installed-runtime-test",
                "--name",
                "Installed Runtime Test",
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            initialized.returncode,
            0,
            initialized.stderr or initialized.stdout,
        )
        self.assertEqual(initialized.stderr, "")
        payload = json.loads(initialized.stdout)
        expected_template = (
            self.install
            / "xcoding"
            / "runtime"
            / "assets"
            / "minimal-template.xml"
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(
            Path(str(payload["template"])).resolve(),
            expected_template.resolve(),
        )
        tree = runtime_root / "orchestration.xml"
        self.assertTrue(tree.is_file())

        queried = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "runtime",
                "next",
                "--tree",
                str(tree),
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            queried.returncode,
            0,
            queried.stderr or queried.stdout,
        )
        self.assertEqual(queried.stderr, "")
        next_payload = json.loads(queried.stdout)
        self.assertTrue(next_payload["ok"])
        self.assertEqual(len(next_payload["ready"]), 1)

    def test_installed_viewer_background_serves_health(self) -> None:
        runtime_root = self.root / "installed-viewer-runtime"
        initialized = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "runtime",
                "init",
                "--runtime-path",
                str(runtime_root),
                "--work-order-id",
                "installed-viewer-test",
                "--name",
                "Installed Viewer Test",
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            initialized.returncode,
            0,
            initialized.stderr or initialized.stdout,
        )
        tree = runtime_root / "orchestration.xml"
        launched = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "viewer",
                "--tree",
                str(tree),
                "--port",
                "0",
                "--no-browser",
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
        self.assertEqual(
            launched.returncode,
            0,
            launched.stderr or launched.stdout,
        )
        self.assertEqual(launched.stderr, "")
        lines = launched.stdout.splitlines()
        self.assertEqual(len(lines), 1, launched.stdout)
        payload = json.loads(lines[0])
        address = str(payload["url"]).removeprefix("http://").rstrip("/")
        host, raw_port = address.split(":", 1)
        connection = http.client.HTTPConnection(host, int(raw_port), timeout=2)
        try:
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            health = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(health["ok"])
        finally:
            connection.close()
            try:
                os.kill(int(payload["pid"]), signal.SIGTERM)
            except OSError:
                pass

    def test_installed_daemon_route_reports_bounded_startup_error(self) -> None:
        result, payload = self.run_cli(
            "daemon",
            "serve",
            "--tree",
            "relative.xml",
            "--foreground",
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["code"],
            "invalid_tree_path",
        )
        self.assertNotIn("Traceback", result.stdout)

    def test_installed_daemon_background_serves_authenticated_health(
        self,
    ) -> None:
        runtime_root = self.root / "installed-daemon-runtime"
        initialized = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "runtime",
                "init",
                "--runtime-path",
                str(runtime_root),
                "--work-order-id",
                "installed-daemon-test",
                "--name",
                "Installed Daemon Test",
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(
            initialized.returncode,
            0,
            initialized.stderr or initialized.stdout,
        )
        tree = runtime_root / "orchestration.xml"

        launched = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "daemon",
                "serve",
                "--tree",
                str(tree),
                "--port",
                "0",
            ],
            cwd=self.root,
            env=self.cli_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
        self.assertEqual(
            launched.returncode,
            0,
            launched.stderr or launched.stdout,
        )
        self.assertEqual(launched.stderr, "")
        lines = launched.stdout.splitlines()
        self.assertEqual(len(lines), 1, launched.stdout)
        payload = json.loads(lines[0])
        parsed = str(payload["url"]).removeprefix("http://")
        host, raw_port = parsed.split(":", 1)
        connection = http.client.HTTPConnection(
            host,
            int(raw_port),
            timeout=2,
        )
        try:
            connection.request(
                "GET",
                "/v1/health",
                headers={
                    "Host": parsed,
                    "Authorization": f"Bearer {payload['token']}",
                },
            )
            response = connection.getresponse()
            health = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(health["ok"])
        finally:
            connection.close()
            pid = int(payload["pid"])
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
                time.sleep(0.05)

if __name__ == "__main__":
    unittest.main()
