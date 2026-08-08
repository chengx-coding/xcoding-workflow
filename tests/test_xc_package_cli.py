from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from build_support.bundle import CandidateProvenance, collect_bundle
from xcoding import cli
from xcoding import dispatch as dispatch_module
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

    def test_installed_runtime_init_uses_bundle_template(self) -> None:
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
            / "_bundle"
            / "skills"
            / "xc-orchestration-runtime"
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

    def test_installed_bundle_contains_runtime_compatibility_payload(self) -> None:
        runtime_scripts = (
            self.install
            / "xcoding"
            / "_bundle"
            / "skills"
            / "xc-orchestration-runtime"
            / "scripts"
        )
        expected = (
            "_runtime_compat/__init__.py",
            "_runtime_compat/application.py",
            "_runtime_compat/commands.py",
            "_runtime_compat/core.py",
            "_runtime_compat/manifest.json",
            "orchestration.py",
            "runtime_core.py",
        )
        self.assertEqual(
            [
                relative
                for relative in expected
                if not (runtime_scripts / relative).is_file()
            ],
            [],
        )

    def _runtime_script(self) -> Path:
        return (
            self.install
            / "xcoding"
            / "_bundle"
            / "skills"
            / "xc-orchestration-runtime"
            / "scripts"
            / "orchestration.py"
        )

    def _direct_runtime(
        self,
        operation: str,
        tree: Path,
        *,
        node: str | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        arguments = [
            sys.executable,
            str(self._runtime_script()),
            operation,
            "--tree",
            str(tree),
            "--json",
        ]
        if node is not None:
            arguments.extend(["--node", node])
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            arguments,
            capture_output=True,
            check=False,
            env=environment,
        )

    def _create_runtime(self) -> tuple[Path, str]:
        runtime_root = self.root / "dispatch-runtime"
        runtime_root.mkdir(exist_ok=True)
        tree = runtime_root / "orchestration.xml"
        template = (
            self.install
            / "xcoding"
            / "_bundle"
            / "skills"
            / "xc-orchestration-runtime"
            / "assets"
            / "minimal-template.xml"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        initialized = subprocess.run(
            [
                sys.executable,
                str(self._runtime_script()),
                "init",
                "--runtime-path",
                str(runtime_root),
                "--template",
                str(template),
                "--work-order-id",
                "cli-dispatch-test",
                "--name",
                "CLI Dispatch Test",
                "--json",
            ],
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        ready = self._direct_runtime("next", tree)
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        node = json.loads(ready.stdout)["ready"][0]["id"]
        return tree, node

    def test_dispatch_matches_direct_read_only_runtime_entry(self) -> None:
        tree, node = self._create_runtime()
        with mock.patch.object(
            dispatch_module,
            "installed_bundle_root",
            return_value=self.install / "xcoding" / "_bundle",
        ):
            for operation in ("next", "summary", "snapshot"):
                with self.subTest(operation=operation):
                    direct = self._direct_runtime(operation, tree)
                    dispatched = dispatch_module.dispatch_read_only(
                        operation,
                        tree=tree,
                    )
                    self.assertEqual(
                        (
                            dispatched.returncode,
                            dispatched.stdout,
                            dispatched.stderr,
                        ),
                        (direct.returncode, direct.stdout, direct.stderr),
                    )

            for selected_node in (node, "missing-node"):
                with self.subTest(operation="show", node=selected_node):
                    direct = self._direct_runtime(
                        "show",
                        tree,
                        node=selected_node,
                    )
                    dispatched = dispatch_module.dispatch_read_only(
                        "show",
                        tree=tree,
                        node=selected_node,
                    )
                    self.assertEqual(
                        (
                            dispatched.returncode,
                            dispatched.stdout,
                            dispatched.stderr,
                        ),
                        (direct.returncode, direct.stdout, direct.stderr),
                    )

    def test_dispatch_rejects_mutation_and_free_form_inputs(self) -> None:
        tree = self.root / "absolute-tree.xml"
        rejected = (
            ("start", {"tree": tree}),
            ("complete", {"tree": tree}),
            ("repair-integrity", {"tree": tree}),
            ("module.name", {"tree": tree}),
            ("summary", {"tree": "relative.xml"}),
            ("summary", {"tree": tree, "node": "extra"}),
            ("show", {"tree": tree}),
            ("show", {"tree": tree, "node": "bad\nnode"}),
        )
        with mock.patch.object(dispatch_module.subprocess, "run") as run:
            for operation, keywords in rejected:
                with self.subTest(operation=operation, keywords=keywords):
                    with self.assertRaises(dispatch_module.DispatchRejected):
                        dispatch_module.dispatch_read_only(
                            operation,
                            **keywords,
                        )
            run.assert_not_called()

        with (
            mock.patch.object(
                dispatch_module,
                "installed_bundle_root",
                return_value=self.install / "xcoding" / "_bundle",
            ),
            mock.patch.object(
                dispatch_module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, b"{}", b""),
            ) as run,
        ):
            dispatch_module.dispatch_read_only("summary", tree=tree)
        arguments = run.call_args.args[0]
        keywords = run.call_args.kwargs
        self.assertEqual(arguments[0], sys.executable)
        self.assertEqual(arguments[2], "summary")
        self.assertIs(keywords["shell"], False)
        self.assertIs(keywords["check"], False)
        self.assertEqual(keywords["env"]["PYTHONDONTWRITEBYTECODE"], "1")


if __name__ == "__main__":
    unittest.main()
