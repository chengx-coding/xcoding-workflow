from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPOSITORY_ROOT / "scripts" / "xc_package_install.py"
SPEC = importlib.util.spec_from_file_location("xc_package_install", HELPER_PATH)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


TERMINAL_CLEANUP_STRESS_REPETITIONS = 12
OWNERSHIP_TRANSITION_KILL_REPETITIONS = 3
OPERATION_LOCK_RACE_REPETITIONS = 30
OWNERSHIP_TRANSITION_KILL_BOUNDARIES = (
    "after-journal",
    "after-next-manifest",
    "before-active-replace",
    "after-active-replace",
    "before-old-manifest-delete",
    "after-old-manifest-delete",
    "before-journal-delete",
)
TERMINAL_CLEANUP_FAULT_CHILD = r"""
import importlib.util
import json
import pathlib
import sys

helper = pathlib.Path(sys.argv[1])
fixture = pathlib.Path(sys.argv[2])
boundary = sys.argv[3]
spec = importlib.util.spec_from_file_location("xc_package_install_fault", helper)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
paths = module._fixture_paths(fixture)
marker_path = module._terminal_cleanup_path(paths)
marker_relative = marker_path.relative_to(fixture)
observed = {}

def remember(value):
    observed["candidate_root"] = value["candidate_root"]
    observed["ownership_manifest"] = value["ownership_manifest"]

original_atomic = module._atomic_write
original_delete = module._delete_control_file

def inject_atomic(path, value):
    digest = original_atomic(path, value)
    if path == marker_path and boundary == "after-marker":
        remember(value)
        raise OSError("injected after terminal marker")
    return digest

def inject_delete(root, relative, **kwargs):
    if relative == marker_relative and boundary == "after-final-marker":
        remember(json.loads((root / relative).read_text(encoding="utf-8")))
        original_delete(root, relative, **kwargs)
        raise OSError("injected after terminal marker cleanup")
    return original_delete(root, relative, **kwargs)

module._atomic_write = inject_atomic
module._delete_control_file = inject_delete
try:
    module.uninstall_fixture(fixture_root_value=str(fixture))
except OSError as error:
    if "candidate_root" not in observed:
        raise
    observed["injected"] = True
    observed["error"] = str(error)
    print(json.dumps(observed, sort_keys=True, separators=(",", ":")))
else:
    raise SystemExit("terminal cleanup fault was not injected")
"""
OWNERSHIP_TRANSITION_KILL_CHILD = r"""
import importlib.util
import json
import pathlib
import sys
import time

helper = pathlib.Path(sys.argv[1])
fixture = pathlib.Path(sys.argv[2])
evidence_path = pathlib.Path(sys.argv[3])
boundary = sys.argv[4]
spec = importlib.util.spec_from_file_location("xc_package_install_kill", helper)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
paths = module._fixture_paths(fixture)
journal_path = module._ownership_transition_path(paths)
journal_relative = journal_path.relative_to(fixture)
active_path = module._active_path(paths)
original_atomic = module._atomic_write
original_delete = module._delete_control_file
last_journal = None

def current_journal():
    global last_journal
    if journal_path.is_file():
        last_journal = json.loads(journal_path.read_text(encoding="utf-8"))
    return last_journal

def pause(at):
    if boundary != at:
        return
    journal = current_journal()
    if not isinstance(journal, dict):
        raise SystemExit(f"missing journal at {at}")
    active = None
    if active_path.is_file():
        active = json.loads(active_path.read_text(encoding="utf-8"))
    evidence_path.write_text(
        json.dumps(
            {"boundary": at, "journal": journal, "active": active},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    time.sleep(300)

def inject_atomic(path, value):
    global last_journal
    if path == active_path:
        pause("before-active-replace")
    digest = original_atomic(path, value)
    if path == journal_path:
        last_journal = value
        pause("after-journal")
    journal = current_journal()
    if isinstance(journal, dict):
        new_path = fixture / journal["new_manifest"]["path"]
        if path == new_path:
            pause("after-next-manifest")
    if path == active_path:
        pause("after-active-replace")
    return digest

def inject_delete(root, relative, **kwargs):
    journal = current_journal()
    if not isinstance(journal, dict):
        return original_delete(root, relative, **kwargs)
    old_relative = pathlib.Path(journal["old_manifest"]["path"])
    if relative == old_relative:
        pause("before-old-manifest-delete")
    if relative == journal_relative:
        pause("before-journal-delete")
    result = original_delete(root, relative, **kwargs)
    if relative == old_relative:
        pause("after-old-manifest-delete")
    return result

module._atomic_write = inject_atomic
module._delete_control_file = inject_delete
module.uninstall_fixture(fixture_root_value=str(fixture))
raise SystemExit("ownership transition kill boundary was not reached")
"""
OPERATION_LOCK_RACE_CHILD = r"""
import importlib.util
import json
import pathlib
import sys
import time

helper = pathlib.Path(sys.argv[1])
fixture = pathlib.Path(sys.argv[2])
start = pathlib.Path(sys.argv[3])
release = pathlib.Path(sys.argv[4])
result = pathlib.Path(sys.argv[5])
spec = importlib.util.spec_from_file_location("xc_package_install_race", helper)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
while not start.exists():
    time.sleep(0.002)
try:
    with module._fixture_operation_lock(fixture, "race-holder") as owner:
        result.write_text(
            json.dumps(
                {"outcome": "entered", "owner": owner},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        while not release.exists():
            time.sleep(0.002)
except module.InstallerError as error:
    result.write_text(
        json.dumps(
            {
                "outcome": "rejected",
                "code": error.code,
                "owner": error.details.get("owner"),
                "reason": error.details.get("reason"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
"""
POSIX_ENTRY_REPLACEMENT_CHILD = r"""
import os
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
os.replace(source, target)
"""


class PackageInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.fixture = self.root / "fixture"
        self.fixture.mkdir()
        self.wheel = self.root / (
            "xcoding_workflow_spike-0.0.0.dev0-py3-none-any.whl"
        )
        self._write_wheel(self.wheel)
        self.wheel_sha256 = sha256(self.wheel)
        self.uv_artifact = self.root / "fake-uv.zip"
        with zipfile.ZipFile(self.uv_artifact, "w") as archive:
            archive.writestr("uv.exe" if os.name == "nt" else "uv", b"fake uv")
        self.toolchain = self.root / "toolchain.json"
        self._write_toolchain()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _platform_id(self) -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        if machine in {"amd64", "x86_64"}:
            architecture = "x86_64"
        elif machine in {"arm64", "aarch64"}:
            architecture = "aarch64"
        else:
            architecture = machine
        return {
            ("windows", "x86_64"): "windows-x86_64",
            ("linux", "x86_64"): "linux-x86_64-gnu",
            ("darwin", "aarch64"): "macos-aarch64",
            ("darwin", "x86_64"): "macos-x86_64",
        }[(system, architecture)]

    def _write_toolchain(self) -> None:
        platform_id = self._platform_id()
        value = {
            "schema_version": 1,
            "pin_status": "provisional",
            "fallback_policy": {
                "allow_latest": False,
                "allow_ambient_uv": False,
                "allow_system_python": False,
            },
            "uv": {
                "version": "0.11.15",
                "artifacts": [
                    {
                        "platform_id": platform_id,
                        "filename": self.uv_artifact.name,
                        "sha256": sha256(self.uv_artifact),
                    }
                ],
            },
            "python": {
                "request": "cpython@3.12.13",
                "managed_only": True,
                "downloads": [
                    {
                        "platform_id": platform_id,
                        "build_identity": (
                            "cpython-3.12.13+test-platform-install_only_stripped"
                        ),
                    }
                ],
            },
        }
        self.toolchain.write_text(
            json.dumps(value, sort_keys=True),
            encoding="utf-8",
        )

    def _write_wheel(self, path: Path) -> None:
        metadata = (
            "Metadata-Version: 2.3\n"
            "Name: xcoding-workflow-spike\n"
            "Version: 0.0.0.dev0\n"
            "\n"
        )
        bundle_manifest = {
            "resources": [
                {
                    "kind": "host-adapter",
                    "adapter_id": "test-adapter",
                }
            ]
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "xcoding_workflow_spike-0.0.0.dev0.dist-info/METADATA",
                metadata,
            )
            archive.writestr(
                "xcoding/_bundle/bundle-manifest.json",
                json.dumps(bundle_manifest),
            )

    def _fake_prepare_uv(
        self,
        artifact: Path,
        uv_record: dict[str, object],
        uv_version: str,
        paths: dict[str, Path],
        environment: dict[str, str],
        *,
        failure_point: str | None,
    ) -> tuple[Path, dict[str, object]]:
        if failure_point == "download":
            raise installer.InstallerError(
                "injected_download_failure",
                "download",
                exit_code=installer.EXIT_ENVIRONMENT,
            )
        if failure_point == "uv-hash":
            raise installer.InstallerError(
                "uv_artifact_hash_mismatch",
                "uv hash",
                exit_code=installer.EXIT_VERIFY,
            )
        uv = paths["uv_artifacts"] / uv_version / "test" / (
            "uv.exe" if os.name == "nt" else "uv"
        )
        uv.parent.mkdir(parents=True, exist_ok=True)
        uv.write_bytes(b"verified uv")
        return uv, {
            "artifact": str(artifact),
            "artifact_sha256": uv_record["sha256"],
            "version_output": f"uv {uv_version} (test)",
        }

    def _fake_managed_python(
        self,
        uv: Path,
        request: str,
        build_identity: str,
        paths: dict[str, Path],
        environment: dict[str, str],
        *,
        failure_point: str | None,
    ) -> tuple[Path, dict[str, object]]:
        if failure_point == "python-install":
            raise installer.InstallerError(
                "injected_python_install_failure",
                "python",
                exit_code=installer.EXIT_ENVIRONMENT,
            )
        python = paths["uv_python"] / "test-build" / (
            "python.exe" if os.name == "nt" else "bin/python"
        )
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_bytes(b"managed python")
        return python, {
            "request": request,
            "build_identity": build_identity,
            "executable": str(python),
        }

    def _fake_install_tool(
        self,
        uv: Path,
        wheel: Path,
        python_request: str,
        candidate: dict[str, Path],
        paths: dict[str, Path],
        environment: dict[str, str],
    ) -> tuple[Path, Path]:
        candidate["root"].mkdir(parents=True)
        candidate["bin"].mkdir()
        tool_environment = candidate["tools"] / installer.DISTRIBUTION
        tool_python = tool_environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        tool_python.parent.mkdir(parents=True)
        launcher = candidate["bin"] / (
            "xc.exe" if os.name == "nt" else "xc"
        )
        launcher.write_bytes(b"absolute launcher")
        tool_python.write_bytes(b"candidate managed python")
        return launcher.resolve(), tool_python.resolve()

    def _fake_health(
        self,
        launcher: Path,
        tool_python: Path,
        managed_python_root: Path,
        wheel: Path,
        paths: dict[str, Path],
        environment: dict[str, str],
        *,
        failure_point: str | None,
    ) -> dict[str, object]:
        if failure_point == "launcher":
            raise installer.InstallerError(
                "injected_launcher_failure",
                "launcher",
                exit_code=installer.EXIT_ENVIRONMENT,
            )
        if failure_point == "post-check":
            raise installer.InstallerError(
                "injected_post_check_failure",
                "post check",
                exit_code=installer.EXIT_ENVIRONMENT,
            )
        return {
            "version": {"ok": True},
            "bundle": {"ok": True},
            "doctor": {"ok": True},
            "setup": {"ok": True, "writes_performed": False},
        }

    def _patch_runtime(self) -> tuple[mock._patch, ...]:
        return (
            mock.patch.object(
                installer,
                "_prepare_uv",
                side_effect=self._fake_prepare_uv,
            ),
            mock.patch.object(
                installer,
                "_ensure_managed_python",
                side_effect=self._fake_managed_python,
            ),
            mock.patch.object(
                installer,
                "_install_tool",
                side_effect=self._fake_install_tool,
            ),
            mock.patch.object(
                installer,
                "_health_gate",
                side_effect=self._fake_health,
            ),
        )

    def _snapshot_tree_no_follow(
        self,
        root: Path,
    ) -> dict[str, tuple[str, bytes | None]]:
        result: dict[str, tuple[str, bytes | None]] = {}

        def visit(directory: Path) -> None:
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
            for entry in children:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                value = entry.stat(follow_symlinks=False)
                if installer._unsafe_directory_entry(value):
                    result[relative] = (
                        "link",
                        os.fsencode(os.readlink(path)),
                    )
                elif stat.S_ISDIR(value.st_mode):
                    result[relative] = ("directory", None)
                    visit(path)
                else:
                    result[relative] = ("file", path.read_bytes())

        visit(root)
        return result

    def _create_directory_link(self, link: Path, target: Path) -> None:
        if os.name == "nt":
            junction = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if junction.returncode != 0:
                self.skipTest(
                    f"junction creation is unavailable: {junction.stderr}"
                )
            return
        os.symlink(target, link, target_is_directory=True)

    def _remove_directory_link(self, link: Path) -> None:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()

    def _replace_from_separate_process(
        self,
        source: Path,
        target: Path,
    ) -> None:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                POSIX_ENTRY_REPLACEMENT_CHILD,
                str(source),
                str(target),
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"stdout={completed.stdout}\nstderr={completed.stderr}",
        )

    def _posix_delete_quarantines(
        self,
        parent: Path,
        name: str,
    ) -> list[Path]:
        prefix = installer._posix_delete_quarantine_prefix(name)
        return sorted(
            path
            for path in parent.iterdir()
            if path.name.startswith(prefix)
        )

    def _assert_empty_directory_cleanup_swap_is_confined(
        self,
        swap_class: str,
    ) -> None:
        if swap_class == "candidate-root":
            cleanup_root = self.fixture / "versions" / "candidate"
            swap_path = cleanup_root
        elif swap_class == "nested-candidate":
            cleanup_root = self.fixture / "versions" / "candidate"
            swap_path = cleanup_root / "outer" / "nested"
        elif swap_class == "manifests-root":
            cleanup_root = self.fixture / "state" / "manifests"
            swap_path = cleanup_root
        else:
            raise AssertionError(f"unknown cleanup swap class: {swap_class}")
        (swap_path / "owned-empty").mkdir(parents=True)
        moved = swap_path.with_name(f"{swap_path.name}-moved")

        outside = self.root / f"outside-cleanup-{swap_class}"
        outside_target = outside / "target"
        protected = outside_target / "protected-empty"
        link_destination = outside / "link-destination"
        retained_link = outside / "retained-link"
        protected.mkdir(parents=True)
        link_destination.mkdir()
        sentinel = outside / "sentinel.bin"
        sentinel_bytes = b"outside cleanup sentinel\x00\xff\r\n"
        sentinel.write_bytes(sentinel_bytes)
        (link_destination / "link-sentinel.bin").write_bytes(
            b"outside link sentinel\x00\xff\n"
        )
        self._create_directory_link(retained_link, link_destination)
        retained_link_target = os.readlink(retained_link)
        outside_before = self._snapshot_tree_no_follow(outside)

        attempted = False
        swapped = False
        blocked: OSError | None = None

        def swap_after_validation(
            boundary: str,
            root: Path,
            directory: Path,
        ) -> None:
            nonlocal attempted, swapped, blocked
            if (
                attempted
                or boundary != "before-directory-scan"
                or root != cleanup_root
                or directory != swap_path
            ):
                return
            attempted = True
            try:
                os.replace(swap_path, moved)
            except OSError as error:
                blocked = error
                if os.name != "nt":
                    raise
                return
            self._create_directory_link(swap_path, outside_target)
            swapped = True

        failure: installer.InstallerError | None = None
        try:
            with mock.patch.object(
                installer,
                "_empty_directory_cleanup_test_hook",
                side_effect=swap_after_validation,
            ):
                try:
                    installer._remove_empty_directories(cleanup_root)
                except installer.InstallerError as error:
                    failure = error

            self.assertTrue(attempted)
            if os.name == "nt":
                self.assertIsNotNone(blocked)
                self.assertFalse(swapped)
                self.assertIsNone(failure)
            else:
                self.assertTrue(swapped)
                self.assertIsNotNone(failure)
                assert failure is not None
                self.assertEqual(failure.code, "ownership_path_unsafe")
                self.assertEqual(
                    os.path.abspath(os.readlink(swap_path)),
                    str(outside_target),
                )
                self.assertTrue(moved.is_dir())
            self.assertEqual(
                self._snapshot_tree_no_follow(outside),
                outside_before,
            )
            self.assertTrue(outside_target.is_dir())
            self.assertTrue(protected.is_dir())
            self.assertEqual(sentinel.read_bytes(), sentinel_bytes)
            self.assertEqual(
                os.readlink(retained_link),
                retained_link_target,
            )
        finally:
            if swapped:
                self._remove_directory_link(swap_path)
                if moved.exists():
                    os.replace(moved, swap_path)
            if retained_link.exists():
                self._remove_directory_link(retained_link)

    def _assert_posix_probe_descriptors_closed(
        self,
        descriptors: list[int],
        real_fstat: object,
    ) -> None:
        self.assertEqual(len(descriptors), len(set(descriptors)))
        for descriptor in descriptors:
            with self.assertRaises(OSError) as closed:
                real_fstat(descriptor)  # type: ignore[operator]
            self.assertEqual(closed.exception.errno, errno.EBADF)

    def _cleanup_posix_probe_descriptors(
        self,
        descriptors: list[int],
        real_fstat: object,
        real_close: object,
    ) -> None:
        for descriptor in set(descriptors):
            try:
                real_fstat(descriptor)  # type: ignore[operator]
            except OSError as error:
                if error.errno == errno.EBADF:
                    continue
            try:
                real_close(descriptor)  # type: ignore[operator]
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise

    def _run_terminal_cleanup_fault_process(
        self,
        boundary: str,
    ) -> dict[str, object]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                TERMINAL_CLEANUP_FAULT_CHILD,
                str(HELPER_PATH),
                str(self.fixture),
                boundary,
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"stdout={completed.stdout}\nstderr={completed.stderr}",
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            self.fail(
                "fault subprocess did not emit one JSON object: "
                f"{error}\nstdout={completed.stdout}\nstderr={completed.stderr}"
            )
        self.assertTrue(payload["injected"])
        self.assertIsInstance(payload["candidate_root"], str)
        self.assertIsInstance(payload["ownership_manifest"], str)
        return payload

    def _run_uninstall_process(self) -> dict[str, object]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HELPER_PATH),
                "uninstall",
                "--fixture-root",
                str(self.fixture),
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"stdout={completed.stdout}\nstderr={completed.stderr}",
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            self.fail(
                "uninstall subprocess did not emit one JSON object: "
                f"{error}\nstdout={completed.stdout}\nstderr={completed.stderr}"
            )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["result"]["uninstalled"])
        return payload["result"]

    def _start_ownership_transition_kill_process(
        self,
        boundary: str,
    ) -> tuple[subprocess.Popen[str], dict[str, object]]:
        evidence_path = self.root / (
            f"ownership-transition-{boundary}-{time.time_ns()}.json"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                OWNERSHIP_TRANSITION_KILL_CHILD,
                str(HELPER_PATH),
                str(self.fixture),
                str(evidence_path),
                boundary,
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        deadline = time.monotonic() + 15
        while not evidence_path.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(
                    f"ownership transition child exited early at {boundary}: "
                    f"{process.returncode}\nstdout={stdout}\nstderr={stderr}"
                )
            time.sleep(0.02)
        if not evidence_path.exists():
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            self.fail(
                f"ownership transition child did not reach {boundary}\n"
                f"stdout={stdout}\nstderr={stderr}"
            )
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["boundary"], boundary)
        self.assertIsInstance(payload["journal"], dict)
        return process, payload

    def _assert_exact_terminal_state_removed(
        self,
        paths: dict[str, Path],
        *,
        candidate_relative: str,
        manifest_relative: str,
    ) -> None:
        self.assertFalse((paths["state"] / "active.json").exists())
        self.assertFalse(
            installer._terminal_cleanup_path(paths).exists(),
        )
        self.assertFalse(installer._ownership_transition_path(paths).exists())
        self.assertFalse((self.fixture / candidate_relative).exists())
        self.assertFalse((self.fixture / manifest_relative).exists())
        self.assertFalse(
            paths["manifests"].exists(),
            (
                sorted(path.name for path in paths["manifests"].iterdir())
                if paths["manifests"].exists()
                else []
            ),
        )

    def _install(
        self,
        *,
        failure_point: str | None = None,
        force_candidate: bool = False,
    ) -> dict[str, object]:
        return installer.install_fixture(
            wheel_value=str(self.wheel),
            wheel_sha256=self.wheel_sha256,
            uv_artifact_value=str(self.uv_artifact),
            fixture_root_value=str(self.fixture),
            toolchain_value=str(self.toolchain),
            failure_point=failure_point,
            force_candidate=force_candidate,
        )

    def test_wrappers_are_explicit_unsupported_local_fixture_only(self) -> None:
        sources = [
            (REPOSITORY_ROOT / "install" / "install.ps1").read_text(
                encoding="utf-8"
            ),
            (REPOSITORY_ROOT / "install" / "install.sh").read_text(
                encoding="utf-8"
            ),
            HELPER_PATH.read_text(encoding="utf-8"),
        ]
        combined = "\n".join(sources).lower()
        self.assertIn("unsupported public installation", combined)
        self.assertIn("--no-index", combined)
        self.assertIn("--no-python-downloads", combined)
        self.assertIn("--no-config", combined)
        self.assertIn("--no-registry", combined)
        self.assertNotIn("https://", combined)
        self.assertNotIn("http://", combined)
        self.assertNotIn("pypi", combined)
        self.assertNotIn("urllib", combined)
        self.assertNotIn("requests", combined)

        powershell = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-File",
                str(REPOSITORY_ROOT / "install" / "install.ps1"),
                "--help",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(powershell.returncode, 0, powershell.stderr)
        self.assertIn(
            "UNSUPPORTED PUBLIC INSTALLATION",
            powershell.stdout,
        )

    def test_install_repeat_activation_and_fixture_environment(self) -> None:
        prepare, python, tool, health = self._patch_runtime()
        with prepare as prepare_mock, python, tool as tool_mock, health:
            first = self._install()
            active_before = (
                self.fixture / "state" / "active.json"
            ).read_bytes()
            repeated = self._install()

        self.assertFalse(first["repeated"])
        self.assertTrue(first["activated"])
        self.assertTrue(repeated["repeated"])
        self.assertEqual(tool_mock.call_count, 1)
        self.assertEqual(prepare_mock.call_count, 2)
        self.assertEqual(
            (self.fixture / "state" / "active.json").read_bytes(),
            active_before,
        )
        active = json.loads(active_before)
        manifest = self.fixture / active["ownership_manifest"]
        self.assertEqual(
            sha256(manifest),
            active["ownership_manifest_sha256"],
        )
        self.assertEqual(
            len(list((self.fixture / "versions").iterdir())),
            1,
        )

        paths = installer._fixture_paths(self.fixture)
        environment = installer._fixture_environment(paths)
        expected = {
            "HOME": paths["home"],
            "USERPROFILE": paths["home"],
            "XDG_CACHE_HOME": paths["xdg_cache"],
            "XDG_CONFIG_HOME": paths["xdg_config"],
            "XDG_DATA_HOME": paths["xdg_data"],
            "XDG_STATE_HOME": paths["xdg_state"],
            "APPDATA": paths["appdata"],
            "LOCALAPPDATA": paths["localappdata"],
            "TEMP": paths["temp"],
            "TMP": paths["temp"],
            "TMPDIR": paths["temp"],
            "UV_PYTHON_INSTALL_DIR": paths["uv_python"],
            "UV_TOOL_DIR": paths["uv_tools"],
            "UV_TOOL_BIN_DIR": paths["uv_bin"],
            "UV_CACHE_DIR": paths["uv_cache"],
        }
        for name, path in expected.items():
            self.assertEqual(environment[name], str(path))
            self.assertTrue(path.is_relative_to(self.fixture))
        self.assertEqual(environment.get("PATH"), os.environ.get("PATH"))
        self.assertNotIn("PYTHONPATH", environment)

    def test_all_failure_points_preserve_active_and_clean_candidate(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            self._install()
            active_path = self.fixture / "state" / "active.json"
            active_before = active_path.read_bytes()
            versions_before = {
                path.name for path in (self.fixture / "versions").iterdir()
            }
            expected_codes = {
                "download": "injected_download_failure",
                "uv-hash": "uv_artifact_hash_mismatch",
                "python-install": "injected_python_install_failure",
                "wheel-hash": "wheel_hash_mismatch",
                "wheel-install": "injected_wheel_install_failure",
                "launcher": "injected_launcher_failure",
                "post-check": "injected_post_check_failure",
                "activation": "injected_activation_failure",
            }
            for failure_point, code in expected_codes.items():
                with self.subTest(failure_point=failure_point):
                    with self.assertRaises(installer.InstallerError) as raised:
                        self._install(
                            failure_point=failure_point,
                            force_candidate=True,
                        )
                    self.assertEqual(raised.exception.code, code)
                    self.assertEqual(active_path.read_bytes(), active_before)
                    self.assertEqual(
                        {
                            path.name
                            for path in (self.fixture / "versions").iterdir()
                        },
                        versions_before,
                    )

    def test_corrupt_local_wheel_is_rejected_before_candidate(self) -> None:
        expected = self.wheel_sha256
        self.wheel.write_bytes(self.wheel.read_bytes() + b"corrupt")
        with self.assertRaises(installer.InstallerError) as raised:
            installer.install_fixture(
                wheel_value=str(self.wheel),
                wheel_sha256=expected,
                uv_artifact_value=str(self.uv_artifact),
                fixture_root_value=str(self.fixture),
                toolchain_value=str(self.toolchain),
            )
        self.assertEqual(raised.exception.code, "wheel_hash_mismatch")
        self.assertFalse((self.fixture / "versions").exists())

    def test_clean_uninstall_uses_manifest_and_preserves_shared_state(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        sentinels = {
            "uv": self.fixture / "uv" / "shared.txt",
            "python": self.fixture / "uv" / "python" / "shared.txt",
            "cache": self.fixture / "uv" / "cache" / "shared.txt",
            "user": self.fixture / "user" / "content.txt",
            "runtime": self.fixture / "runtime" / "orchestration.xml",
            "workshop": self.fixture / "workshop" / "history.txt",
        }
        for path in sentinels.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(path.name, encoding="utf-8")

        result = installer.uninstall_fixture(
            fixture_root_value=str(self.fixture)
        )
        self.assertTrue(result["uninstalled"])
        self.assertFalse(Path(installed["launcher"]).exists())
        self.assertFalse((self.fixture / "state" / "active.json").exists())
        for path in sentinels.values():
            self.assertTrue(path.is_file(), path)

    def test_uninstall_preserves_changed_unexpected_and_user_content(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        healthy = Path(installed["tool_python"])
        healthy_before = healthy.read_bytes()
        launcher.write_bytes(b"user changed launcher")
        candidate_root = launcher.parent.parent
        unexpected = candidate_root / "user-created.txt"
        unexpected.write_text("keep", encoding="utf-8")
        user = self.fixture / "user" / "notes.txt"
        user.parent.mkdir()
        user.write_text("keep", encoding="utf-8")

        with self.assertRaises(installer.InstallerError) as raised:
            installer.uninstall_fixture(
                fixture_root_value=str(self.fixture)
            )
        self.assertEqual(raised.exception.code, "uninstall_drift")
        details = raised.exception.details
        self.assertIn(
            launcher.relative_to(candidate_root).as_posix(),
            details["changed_preserved"],
        )
        self.assertIn("user-created.txt", details["unexpected_preserved"])
        self.assertTrue(launcher.is_file())
        self.assertEqual(healthy.read_bytes(), healthy_before)
        self.assertTrue(unexpected.is_file())
        self.assertTrue(user.is_file())
        self.assertTrue((self.fixture / "state" / "active.json").is_file())

    def test_repaired_uninstall_drift_is_retryable(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        original = launcher.read_bytes()
        launcher.write_bytes(b"drift")

        with self.assertRaises(installer.InstallerError) as raised:
            installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertEqual(raised.exception.code, "uninstall_drift")
        self.assertTrue(Path(installed["tool_python"]).is_file())

        launcher.write_bytes(original)
        result = installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertTrue(result["uninstalled"])
        self.assertFalse((self.fixture / "state" / "active.json").exists())

    def test_locked_uninstall_entry_preserves_all_content_and_retries(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        candidate_root = Path(installed["launcher"]).parent.parent
        before = {
            path.relative_to(candidate_root).as_posix(): path.read_bytes()
            for path in candidate_root.rglob("*")
            if path.is_file()
        }
        original = installer._owned_entry_state

        def locked(
            candidate: Path,
            relative: str,
            **kwargs: object,
        ) -> tuple[str, str]:
            if kwargs.get("delete") and candidate == candidate_root:
                raise PermissionError("simulated locked entry")
            return original(candidate, relative, **kwargs)

        with mock.patch.object(
            installer,
            "_owned_entry_state",
            side_effect=locked,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertEqual(raised.exception.code, "uninstall_interrupted")
        self.assertEqual(
            {
                path.relative_to(candidate_root).as_posix(): path.read_bytes()
                for path in candidate_root.rglob("*")
                if path.is_file()
            },
            before,
        )

        result = installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertTrue(result["uninstalled"])

    def test_interrupted_uninstall_persists_residual_ownership_for_retry(
        self,
    ) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        candidate_root = Path(installed["launcher"]).parent.parent
        original = installer._owned_entry_state
        interrupted = False

        def interrupt_after_delete(
            candidate: Path,
            relative: str,
            **kwargs: object,
        ) -> tuple[str, str]:
            nonlocal interrupted
            result = original(candidate, relative, **kwargs)
            if (
                kwargs.get("delete")
                and candidate == candidate_root
                and not interrupted
            ):
                interrupted = True
                raise OSError("simulated interruption after deletion")
            return result

        with mock.patch.object(
            installer,
            "_owned_entry_state",
            side_effect=interrupt_after_delete,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertEqual(raised.exception.code, "uninstall_interrupted")
        self.assertTrue((self.fixture / "state" / "active.json").is_file())

        result = installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertTrue(result["uninstalled"])
        self.assertTrue(result["removed"])

    def test_concurrent_fixture_operation_is_rejected_without_mutation(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        before = launcher.read_bytes()

        with installer._fixture_operation_lock(
            self.fixture,
            "test-holder",
        ) as owner:
            lock_path = self.fixture / ".xc-package-operation.lock"
            entries = installer._operation_lock_entries(
                lock_path,
                "test-holder",
                require_published=True,
                require_single_links=True,
            )
            lock_state = os.lstat(lock_path)
            self.assertTrue(stat.S_ISDIR(lock_state.st_mode))
            self.assertFalse(installer._is_reparse_point(lock_state))
            self.assertEqual(entries["record"], owner)
            self.assertEqual(owner["state"], "held")
            self.assertEqual(owner["pid"], os.getpid())
            self.assertTrue(owner["token"])
            kernel = lock_path / "kernel"
            marker = (
                lock_path / str(entries["owner_name"]) / "published"
            )
            self.assertEqual(kernel.stat().st_size, 0)
            self.assertEqual(marker.read_bytes(), b"")
            self.assertEqual(kernel.stat().st_nlink, 1)
            self.assertEqual(marker.stat().st_nlink, 1)
            self.assertEqual(
                installer._operation_owner_record(str(entries["owner_name"])),
                owner,
            )
            with self.assertRaises(installer.InstallerError) as raised:
                installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertEqual(raised.exception.code, "operation_in_progress")
        self.assertEqual(launcher.read_bytes(), before)
        self.assertTrue((self.fixture / "state" / "active.json").is_file())
        self.assertFalse(lock_path.exists())

    def _assert_operation_lock_real_process_race_has_one_winner(
        self,
        repetition: int,
    ) -> None:
        start = self.root / f"operation-lock-race-{repetition}-start"
        release = self.root / f"operation-lock-race-{repetition}-release"
        results = [
            self.root / f"operation-lock-race-{repetition}-{index}.json"
            for index in range(6)
        ]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    OPERATION_LOCK_RACE_CHILD,
                    str(HELPER_PATH),
                    str(self.fixture),
                    str(start),
                    str(release),
                    str(result),
                ],
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for result in results
        ]
        try:
            start.write_text("start", encoding="utf-8")
            deadline = time.monotonic() + 20
            while (
                sum(result.exists() for result in results) < len(results)
                and time.monotonic() < deadline
            ):
                for process in processes:
                    if process.poll() not in {None, 0}:
                        stdout, stderr = process.communicate()
                        self.fail(
                            "operation lock race child failed early: "
                            f"{process.returncode}\nstdout={stdout}\n"
                            f"stderr={stderr}"
                        )
                time.sleep(0.01)
            self.assertTrue(
                all(result.exists() for result in results),
                [result.exists() for result in results],
            )
            payloads = [
                json.loads(result.read_text(encoding="utf-8"))
                for result in results
            ]
            entered = [
                payload for payload in payloads
                if payload["outcome"] == "entered"
            ]
            rejected = [
                payload for payload in payloads
                if payload["outcome"] == "rejected"
            ]
            self.assertEqual(len(entered), 1, payloads)
            self.assertEqual(len(rejected), len(results) - 1, payloads)
            self.assertTrue(
                all(
                    payload["code"] == "operation_in_progress"
                    for payload in rejected
                ),
                payloads,
            )
            winner = entered[0]["owner"]
            reported_owners = [
                payload["owner"] for payload in rejected
                if isinstance(payload["owner"], dict)
            ]
            self.assertTrue(
                all(
                    owner["token"] == winner["token"]
                    for owner in reported_owners
                ),
                payloads,
            )
        finally:
            release.write_text("release", encoding="utf-8")
            for process in processes:
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(
                    process.returncode,
                    0,
                    f"stdout={stdout}\nstderr={stderr}",
                )
        self.assertFalse(
            (self.fixture / ".xc-package-operation.lock").exists()
        )

    def test_operation_lock_real_process_race_has_one_winner(self) -> None:
        for repetition in range(OPERATION_LOCK_RACE_REPETITIONS):
            with self.subTest(repetition=repetition):
                self._assert_operation_lock_real_process_race_has_one_winner(
                    repetition
                )

    def test_operation_lock_persistent_incomplete_publication_fails_closed(
        self,
    ) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        lock_path.mkdir()
        identity = installer._operation_lock_identity(os.lstat(lock_path))
        started = time.monotonic()

        with self.assertRaises(installer.InstallerError) as raised:
            with installer._fixture_operation_lock(
                self.fixture,
                "incomplete-publication-probe",
            ):
                self.fail("persistent incomplete publication was accepted")

        elapsed = time.monotonic() - started
        self.assertEqual(raised.exception.code, "operation_lock_invalid")
        self.assertEqual(
            raised.exception.details.get("reason"),
            "publication_incomplete",
        )
        self.assertGreaterEqual(
            elapsed,
            installer._OPERATION_LOCK_PUBLICATION_TIMEOUT_SECONDS,
        )
        self.assertLess(
            elapsed,
            installer._OPERATION_LOCK_PUBLICATION_TIMEOUT_SECONDS + 2.0,
        )
        self.assertEqual(
            installer._operation_lock_identity(os.lstat(lock_path)),
            identity,
        )
        self.assertEqual(list(lock_path.iterdir()), [])

    def test_operation_lock_rejects_hardlink_without_external_write(
        self,
    ) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        outside = self.root / "outside-lock-owner.bin"
        outside_bytes = b"external owner bytes\x00\xff\r\n"
        outside.write_bytes(outside_bytes)
        outside_digest = sha256(outside)
        lock_path.hardlink_to(outside)
        self.assertTrue(lock_path.samefile(outside))
        self.assertEqual(outside.stat().st_nlink, 2)

        with self.assertRaises(installer.InstallerError) as raised:
            with installer._fixture_operation_lock(
                self.fixture,
                "hardlink-probe",
            ):
                self.fail("multiply linked operation lock was accepted")

        self.assertEqual(raised.exception.code, "operation_lock_invalid")
        self.assertEqual(
            raised.exception.details.get("reason"),
            "fixed_path_not_directory",
        )
        self.assertEqual(outside.read_bytes(), outside_bytes)
        self.assertEqual(lock_path.read_bytes(), outside_bytes)
        self.assertEqual(sha256(outside), outside_digest)
        self.assertEqual(outside.stat().st_nlink, 2)

    def test_operation_lock_hardlink_races_never_mutate_outside_inode(
        self,
    ) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        empty_digest = hashlib.sha256(b"").hexdigest()
        for boundary in installer._OPERATION_LOCK_FORMER_WRITE_BOUNDARIES:
            with self.subTest(boundary=boundary):
                outside = self.root / f"outside-{boundary}.bin"
                body_entered = False
                injected = False

                def add_hardlink(
                    current: str,
                    kernel_path: Path,
                    owner_marker_path: Path,
                ) -> None:
                    nonlocal injected
                    del kernel_path
                    if current == boundary:
                        os.link(owner_marker_path, outside)
                        injected = True

                with mock.patch.object(
                    installer,
                    "_operation_lock_test_hook",
                    side_effect=add_hardlink,
                ):
                    with self.assertRaises(installer.InstallerError) as raised:
                        with installer._fixture_operation_lock(
                            self.fixture,
                            f"race-{boundary}",
                        ):
                            body_entered = True

                self.assertTrue(injected)
                self.assertFalse(body_entered)
                self.assertEqual(raised.exception.code, "operation_lock_invalid")
                self.assertEqual(
                    raised.exception.details.get("reason"),
                    "multiple_links",
                )
                self.assertEqual(outside.read_bytes(), b"")
                self.assertEqual(sha256(outside), empty_digest)
                self.assertEqual(outside.stat().st_nlink, 1)
                self.assertFalse(lock_path.exists())

        outside = self.root / "outside-after-final-validation.bin"
        with installer._fixture_operation_lock(
            self.fixture,
            "post-validation-race",
        ):
            entries = installer._operation_lock_entries(
                lock_path,
                "post-validation-race",
                require_published=True,
                require_single_links=True,
            )
            marker = (
                lock_path / str(entries["owner_name"]) / "published"
            )
            os.link(marker, outside)
            self.assertEqual(outside.read_bytes(), b"")
        self.assertEqual(outside.read_bytes(), b"")
        self.assertEqual(sha256(outside), empty_digest)
        self.assertEqual(outside.stat().st_nlink, 1)
        self.assertFalse(lock_path.exists())

        source = HELPER_PATH.read_text(encoding="utf-8")
        lock_source = source[
            source.index("def _operation_lock_invalid"):
            source.index("class _WindowsByHandleFileInformation")
        ]
        self.assertNotIn("def _write_lock_file_record", source)
        self.assertNotIn(".truncate(", lock_source)
        self.assertNotIn(".write(", lock_source)

    def test_operation_lock_parent_swaps_are_handle_bound(self) -> None:
        publication_boundaries = (
            "before-fixed-directory-mkdir",
            "before-fixed-directory-open",
            "before-kernel-open",
            "before-owner-directory-mkdir",
            "before-owner-directory-open",
            "before-published-open",
        )
        cleanup_boundaries = (
            "before-published-unlink",
            "before-owner-directory-rmdir",
            "before-kernel-unlink",
            "before-fixed-directory-rmdir",
        )

        def snapshot(root: Path) -> dict[str, tuple[str, bytes | None]]:
            result: dict[str, tuple[str, bytes | None]] = {}
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    result[relative] = (
                        "symlink",
                        os.fsencode(os.readlink(path)),
                    )
                elif path.is_dir():
                    result[relative] = ("directory", None)
                else:
                    result[relative] = ("file", path.read_bytes())
            return result

        for boundary in (*publication_boundaries, *cleanup_boundaries):
            with self.subTest(boundary=boundary):
                if self.fixture.exists():
                    shutil.rmtree(self.fixture)
                self.fixture.mkdir()
                lock_path = self.fixture / ".xc-package-operation.lock"
                if boundary == "before-fixed-directory-open":
                    lock_path.mkdir()
                outside_root = self.root / f"outside-root-{boundary}"
                outside_fixed = self.root / f"outside-fixed-{boundary}"
                outside_owner = self.root / f"outside-owner-{boundary}"
                outside_root.mkdir()
                outside_fixed.mkdir()
                outside_owner.mkdir()
                (outside_root / "sentinel.bin").write_bytes(
                    b"outside root sentinel\x00\xff\n"
                )
                (outside_fixed / "kernel").write_bytes(
                    b"outside kernel sentinel\x00\xff\n"
                )
                (outside_fixed / "sentinel.bin").write_bytes(
                    b"outside fixed sentinel\x00\xff\n"
                )
                (outside_owner / "published").write_bytes(
                    b"outside published sentinel\x00\xff\n"
                )
                outside_before = {
                    outside_root: snapshot(outside_root),
                    outside_fixed: snapshot(outside_fixed),
                    outside_owner: snapshot(outside_owner),
                }
                swapped: list[tuple[Path, Path]] = []
                attempted = False
                body_entered = False

                def swap_parent(
                    current: str,
                    current_lock: Path,
                    owner_name: str | None,
                ) -> None:
                    nonlocal attempted
                    if current != boundary:
                        return
                    attempted = True
                    if current == "before-fixed-directory-mkdir":
                        original = self.fixture
                        moved = self.root / f"fixture-moved-{boundary}"
                        target = outside_root
                    elif current in {
                        "before-owner-directory-open",
                        "before-published-open",
                        "before-published-unlink",
                        "before-owner-directory-rmdir",
                    }:
                        assert owner_name is not None
                        original = current_lock / owner_name
                        moved = current_lock / f"{owner_name}-moved"
                        target = outside_owner
                    else:
                        original = current_lock
                        moved = current_lock.with_name(
                            f"{current_lock.name}-moved-{boundary}"
                        )
                        target = outside_fixed
                    try:
                        os.replace(original, moved)
                    except OSError as error:
                        if os.name != "nt":
                            raise
                        if boundary in cleanup_boundaries:
                            return
                        raise OSError(
                            "Windows retained handle blocked parent swap"
                        ) from error
                    swapped.append((original, moved))
                    if os.name == "nt":
                        junction = subprocess.run(
                            [
                                "cmd",
                                "/c",
                                "mklink",
                                "/J",
                                str(original),
                                str(target),
                            ],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            check=False,
                        )
                        self.assertEqual(
                            junction.returncode,
                            0,
                            junction.stderr,
                        )
                    else:
                        os.symlink(target, original, target_is_directory=True)

                def force_cleanup(
                    current: str,
                    kernel_path: Path,
                    marker_path: Path,
                ) -> None:
                    del kernel_path, marker_path
                    if (
                        boundary in cleanup_boundaries
                        and current
                        == installer._OPERATION_LOCK_FORMER_WRITE_BOUNDARIES[0]
                    ):
                        raise RuntimeError("force handle-bound cleanup")

                try:
                    with mock.patch.object(
                        installer,
                        "_operation_lock_mutation_test_hook",
                        side_effect=swap_parent,
                    ), mock.patch.object(
                        installer,
                        "_operation_lock_test_hook",
                        side_effect=force_cleanup,
                    ):
                        with self.assertRaises(
                            (installer.InstallerError, OSError, RuntimeError)
                        ):
                            with installer._fixture_operation_lock(
                                self.fixture,
                                f"parent-swap-{boundary}",
                            ):
                                body_entered = True
                    self.assertTrue(attempted)
                    self.assertFalse(body_entered)
                    for outside, expected in outside_before.items():
                        self.assertEqual(snapshot(outside), expected)
                finally:
                    for original, moved in reversed(swapped):
                        if original.is_symlink():
                            original.unlink()
                        elif os.name == "nt" and original.exists():
                            try:
                                os.rmdir(original)
                            except OSError:
                                pass
                        if moved.exists() and not original.exists():
                            os.replace(moved, original)

    def test_empty_directory_cleanup_candidate_root_swap_is_handle_bound(
        self,
    ) -> None:
        self._assert_empty_directory_cleanup_swap_is_confined(
            "candidate-root"
        )

    def test_empty_directory_cleanup_nested_candidate_swap_is_handle_bound(
        self,
    ) -> None:
        self._assert_empty_directory_cleanup_swap_is_confined(
            "nested-candidate"
        )

    def test_empty_directory_cleanup_manifests_root_swap_is_handle_bound(
        self,
    ) -> None:
        self._assert_empty_directory_cleanup_swap_is_confined(
            "manifests-root"
        )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_fstat_failures_close_all_descriptors(self) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        for failure_site in ("anchor", "component", "child"):
            with self.subTest(failure_site=failure_site):
                cleanup_root = self.fixture / f"fstat-failure-{failure_site}"
                cleanup_root.mkdir()
                if failure_site == "child":
                    (cleanup_root / "empty-child").mkdir()
                target_open_count = {
                    "anchor": 1,
                    "component": len(cleanup_root.parts),
                    "child": len(cleanup_root.parts) + 1,
                }[failure_site]
                opened_descriptors: list[int] = []
                close_attempts: list[int] = []
                successful_closes: list[int] = []
                failed_descriptor: int | None = None

                def record_open(*args: object, **kwargs: object) -> int:
                    descriptor = real_open(*args, **kwargs)
                    opened_descriptors.append(descriptor)
                    return descriptor

                def record_close(descriptor: int) -> None:
                    close_attempts.append(descriptor)
                    real_close(descriptor)
                    successful_closes.append(descriptor)

                def fail_target_fstat(descriptor: int) -> os.stat_result:
                    nonlocal failed_descriptor
                    if (
                        failed_descriptor is None
                        and len(opened_descriptors) == target_open_count
                        and descriptor == opened_descriptors[-1]
                    ):
                        failed_descriptor = descriptor
                        raise OSError(
                            errno.EIO,
                            f"injected {failure_site} fstat failure",
                        )
                    return real_fstat(descriptor)

                try:
                    with mock.patch.object(
                        installer.os,
                        "open",
                        side_effect=record_open,
                    ), mock.patch.object(
                        installer.os,
                        "fstat",
                        side_effect=fail_target_fstat,
                    ), mock.patch.object(
                        installer.os,
                        "close",
                        side_effect=record_close,
                    ):
                        with self.assertRaises(
                            installer.InstallerError
                        ) as raised:
                            installer._remove_empty_directories_posix(
                                cleanup_root
                            )

                    self.assertEqual(
                        raised.exception.code,
                        "ownership_path_unsafe",
                    )
                    self.assertEqual(
                        len(opened_descriptors),
                        target_open_count,
                    )
                    self.assertEqual(
                        failed_descriptor,
                        opened_descriptors[-1],
                    )
                    self.assertEqual(
                        close_attempts,
                        list(reversed(opened_descriptors)),
                    )
                    self.assertEqual(
                        successful_closes,
                        list(reversed(opened_descriptors)),
                    )
                    self._assert_posix_probe_descriptors_closed(
                        opened_descriptors,
                        real_fstat,
                    )
                finally:
                    self._cleanup_posix_probe_descriptors(
                        opened_descriptors,
                        real_fstat,
                        real_close,
                    )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_component_memory_error_before_registration(
        self,
    ) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        cleanup_root = self.fixture / "component-memory-error"
        cleanup_root.mkdir()
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []
        triggered = False

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def record_close(descriptor: int) -> None:
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)

        def inject_before_registration(
            frame: object,
            event: str,
            argument: object,
        ) -> object:
            del argument
            nonlocal triggered
            if (
                not triggered
                and event == "line"
                and frame.f_code  # type: ignore[attr-defined]
                is installer._open_posix_cleanup_chain.__code__
            ):
                local = frame.f_locals  # type: ignore[attr-defined]
                node = local.get("node")
                nodes = local.get("nodes")
                handle = local.get("handle")
                if (
                    isinstance(node, dict)
                    and node.get("path") == cleanup_root
                    and isinstance(nodes, list)
                    and not any(registered is node for registered in nodes)
                    and isinstance(handle, int)
                ):
                    triggered = True
                    raise MemoryError("injected before component registration")
            return inject_before_registration

        previous_trace = sys.gettrace()
        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ), mock.patch.object(
                installer.os,
                "close",
                side_effect=record_close,
            ):
                sys.settrace(inject_before_registration)
                try:
                    with self.assertRaises(MemoryError) as raised:
                        installer._remove_empty_directories_posix(cleanup_root)
                finally:
                    sys.settrace(previous_trace)
            self.assertEqual(
                str(raised.exception),
                "injected before component registration",
            )
            self.assertTrue(triggered)
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors)),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            sys.settrace(previous_trace)
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_append_clear_interruptions_close_exactly_once(
        self,
    ) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        for boundary in ("anchor", "component", "child"):
            with self.subTest(boundary=boundary):
                cleanup_root = self.fixture / f"append-clear-{boundary}"
                cleanup_root.mkdir()
                child_path = cleanup_root / "empty-child"
                if boundary == "child":
                    child_path.mkdir()
                opened_descriptors: list[int] = []
                close_attempts: list[int] = []
                successful_closes: list[int] = []
                triggered = False

                def record_open(*args: object, **kwargs: object) -> int:
                    descriptor = real_open(*args, **kwargs)
                    opened_descriptors.append(descriptor)
                    return descriptor

                def record_close(descriptor: int) -> None:
                    close_attempts.append(descriptor)
                    real_close(descriptor)
                    successful_closes.append(descriptor)

                def inject_after_append(
                    frame: object,
                    event: str,
                    argument: object,
                ) -> object:
                    del argument
                    nonlocal triggered
                    if triggered or event != "line":
                        return inject_after_append
                    local = frame.f_locals  # type: ignore[attr-defined]
                    nodes = local.get("nodes")
                    if not isinstance(nodes, list) or not nodes:
                        return inject_after_append
                    registered = nodes[-1]
                    matched = False
                    if (
                        boundary == "anchor"
                        and frame.f_code  # type: ignore[attr-defined]
                        is installer._open_posix_cleanup_chain.__code__
                    ):
                        matched = (
                            local.get("parent") is registered
                            and registered.get("path") == Path(cleanup_root.anchor)
                            and isinstance(local.get("anchor_handle"), int)
                        )
                    elif (
                        boundary == "component"
                        and frame.f_code  # type: ignore[attr-defined]
                        is installer._open_posix_cleanup_chain.__code__
                    ):
                        matched = (
                            local.get("node") is registered
                            and registered.get("path") == cleanup_root
                            and isinstance(local.get("handle"), int)
                        )
                    elif (
                        boundary == "child"
                        and frame.f_code  # type: ignore[attr-defined]
                        is installer._open_posix_cleanup_child.__code__
                    ):
                        matched = (
                            local.get("child") is registered
                            and registered.get("path") == child_path
                            and isinstance(local.get("handle"), int)
                        )
                    if matched:
                        triggered = True
                        raise InterruptedError(
                            errno.EINTR,
                            f"injected after {boundary} append",
                        )
                    return inject_after_append

                previous_trace = sys.gettrace()
                try:
                    with mock.patch.object(
                        installer.os,
                        "open",
                        side_effect=record_open,
                    ), mock.patch.object(
                        installer.os,
                        "close",
                        side_effect=record_close,
                    ):
                        sys.settrace(inject_after_append)
                        try:
                            with self.assertRaises(
                                installer.InstallerError
                            ) as raised:
                                installer._remove_empty_directories_posix(
                                    cleanup_root
                                )
                        finally:
                            sys.settrace(previous_trace)
                    original = raised.exception.__cause__
                    self.assertIsInstance(original, InterruptedError)
                    assert isinstance(original, InterruptedError)
                    self.assertEqual(original.errno, errno.EINTR)
                    self.assertTrue(triggered)
                    self.assertEqual(
                        close_attempts,
                        list(reversed(opened_descriptors)),
                    )
                    self.assertEqual(
                        successful_closes,
                        list(reversed(opened_descriptors)),
                    )
                    self._assert_posix_probe_descriptors_closed(
                        opened_descriptors,
                        real_fstat,
                    )
                finally:
                    sys.settrace(previous_trace)
                    self._cleanup_posix_probe_descriptors(
                        opened_descriptors,
                        real_fstat,
                        real_close,
                    )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_child_post_registration_exception_closes_all(
        self,
    ) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        cleanup_root = self.fixture / "child-pre-index"
        child_path = cleanup_root / "empty-child"
        child_path.mkdir(parents=True)
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []
        triggered = False

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def record_close(descriptor: int) -> None:
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)

        def inject_before_child_index(
            frame: object,
            event: str,
            argument: object,
        ) -> object:
            del argument
            nonlocal triggered
            if (
                not triggered
                and event == "line"
                and frame.f_code  # type: ignore[attr-defined]
                is installer._open_posix_cleanup_child.__code__
            ):
                local = frame.f_locals  # type: ignore[attr-defined]
                child = local.get("child")
                parent = local.get("parent")
                nodes = local.get("nodes")
                if (
                    isinstance(child, dict)
                    and child.get("path") == child_path
                    and isinstance(parent, dict)
                    and isinstance(nodes, list)
                    and any(registered is child for registered in nodes)
                    and local.get("handle") is None
                    and not any(
                        indexed is child
                        for indexed in parent.get("children", [])
                    )
                ):
                    triggered = True
                    raise RuntimeError(
                        "injected after child registration before index"
                    )
            return inject_before_child_index

        previous_trace = sys.gettrace()
        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ), mock.patch.object(
                installer.os,
                "close",
                side_effect=record_close,
            ):
                sys.settrace(inject_before_child_index)
                try:
                    with self.assertRaises(RuntimeError) as raised:
                        installer._remove_empty_directories_posix(cleanup_root)
                finally:
                    sys.settrace(previous_trace)
            self.assertEqual(
                str(raised.exception),
                "injected after child registration before index",
            )
            self.assertTrue(triggered)
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors)),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            sys.settrace(previous_trace)
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_missing_root_closes_opened_ancestors(self) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        existing = self.fixture / "missing-root-parent"
        existing.mkdir()
        cleanup_root = existing / "absent"
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def record_close(descriptor: int) -> None:
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)

        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ), mock.patch.object(
                installer.os,
                "close",
                side_effect=record_close,
            ):
                opened = installer._open_posix_cleanup_chain(cleanup_root)
            self.assertIsNone(opened)
            self.assertTrue(opened_descriptors)
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors)),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_stale_node_does_not_skip_ancestors(self) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        cleanup_root = self.fixture / "stale-node"
        cleanup_root.mkdir()
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def record_close(descriptor: int) -> None:
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)

        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ):
                opened = installer._open_posix_cleanup_chain(cleanup_root)
            assert opened is not None
            nodes, _ = opened
            stale = nodes[-1]["handle"]
            real_close(stale)
            with mock.patch.object(
                installer.os,
                "close",
                side_effect=record_close,
            ):
                installer._close_posix_cleanup_nodes(nodes)
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors[:-1])),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_close_error_surfaces_after_all_closes(self) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        cleanup_root = self.fixture / "normal-close-error"
        cleanup_root.mkdir()
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []
        injected = False

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def close_then_fail(descriptor: int) -> None:
            nonlocal injected
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)
            if not injected:
                injected = True
                raise OSError(errno.EIO, "injected close failure")

        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ):
                opened = installer._open_posix_cleanup_chain(cleanup_root)
            assert opened is not None
            nodes, _ = opened
            with mock.patch.object(
                installer.os,
                "close",
                side_effect=close_then_fail,
            ):
                with self.assertRaises(installer.InstallerError) as raised:
                    installer._close_posix_cleanup_nodes(nodes)
            self.assertTrue(injected)
            self.assertEqual(
                raised.exception.code,
                "ownership_path_unsafe",
            )
            self.assertEqual(
                raised.exception.details.get("reason"),
                "directory_handle_close_failed",
            )
            self.assertIsInstance(raised.exception.__cause__, OSError)
            assert isinstance(raised.exception.__cause__, OSError)
            self.assertEqual(raised.exception.__cause__.errno, errno.EIO)
            self.assertEqual(
                raised.exception.details["cleanup_close_errors"][0]["errno"],
                errno.EIO,
            )
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors)),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor semantics required")
    def test_posix_cleanup_close_error_preserves_active_exception(self) -> None:
        real_open = os.open
        real_fstat = os.fstat
        real_close = os.close
        cleanup_root = self.fixture / "active-close-error"
        cleanup_root.mkdir()
        opened_descriptors: list[int] = []
        close_attempts: list[int] = []
        successful_closes: list[int] = []
        close_failure_injected = False

        def record_open(*args: object, **kwargs: object) -> int:
            descriptor = real_open(*args, **kwargs)
            opened_descriptors.append(descriptor)
            return descriptor

        def close_then_fail(descriptor: int) -> None:
            nonlocal close_failure_injected
            close_attempts.append(descriptor)
            real_close(descriptor)
            successful_closes.append(descriptor)
            if not close_failure_injected:
                close_failure_injected = True
                raise OSError(errno.EIO, "injected cleanup close failure")

        def interrupt_scan(
            boundary: str,
            root: Path,
            directory: Path,
        ) -> None:
            if (
                boundary == "before-directory-scan"
                and root == cleanup_root
                and directory == cleanup_root
            ):
                raise InterruptedError(
                    errno.EINTR,
                    "injected primary interruption",
                )

        try:
            with mock.patch.object(
                installer.os,
                "open",
                side_effect=record_open,
            ), mock.patch.object(
                installer.os,
                "close",
                side_effect=close_then_fail,
            ), mock.patch.object(
                installer,
                "_empty_directory_cleanup_test_hook",
                side_effect=interrupt_scan,
            ):
                with self.assertRaises(InterruptedError) as raised:
                    installer._remove_empty_directories_posix(cleanup_root)
            self.assertEqual(raised.exception.errno, errno.EINTR)
            self.assertTrue(close_failure_injected)
            notes = "\n".join(getattr(raised.exception, "__notes__", []))
            self.assertIn("POSIX cleanup close failures", notes)
            self.assertIn('"errno":5', notes)
            self.assertIn('"exception":"OSError"', notes)
            self.assertEqual(
                close_attempts,
                list(reversed(opened_descriptors)),
            )
            self.assertEqual(
                successful_closes,
                list(reversed(opened_descriptors)),
            )
            self._assert_posix_probe_descriptors_closed(
                opened_descriptors,
                real_fstat,
            )
        finally:
            self._cleanup_posix_probe_descriptors(
                opened_descriptors,
                real_fstat,
                real_close,
            )

    def test_operation_lock_rejects_symlink_without_external_write(self) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        outside = self.root / "outside-symlink-owner.bin"
        outside_bytes = b"symlink target bytes\x00\xff\n"
        outside.write_bytes(outside_bytes)
        try:
            os.symlink(outside, lock_path)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"file symlink creation is unavailable: {error}")
        try:
            with self.assertRaises(installer.InstallerError) as raised:
                with installer._fixture_operation_lock(
                    self.fixture,
                    "symlink-probe",
                ):
                    self.fail("symlink operation lock was accepted")
            self.assertEqual(raised.exception.code, "operation_lock_invalid")
            self.assertEqual(outside.read_bytes(), outside_bytes)
            self.assertTrue(lock_path.is_symlink())
        finally:
            lock_path.unlink(missing_ok=True)

    @unittest.skipUnless(os.name == "nt", "real Windows junction required")
    def test_windows_operation_lock_rejects_junction_without_external_write(
        self,
    ) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        outside = self.root / "outside-junction-owner"
        outside.mkdir()
        sentinel = outside / "sentinel.bin"
        sentinel_bytes = b"junction target bytes\x00\xff\n"
        sentinel.write_bytes(sentinel_bytes)
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(lock_path), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if junction.returncode != 0:
            self.skipTest(f"junction creation is unavailable: {junction.stderr}")
        try:
            with self.assertRaises(installer.InstallerError) as raised:
                with installer._fixture_operation_lock(
                    self.fixture,
                    "junction-probe",
                ):
                    self.fail("junction operation lock was accepted")
            self.assertEqual(raised.exception.code, "operation_lock_invalid")
            self.assertEqual(sentinel.read_bytes(), sentinel_bytes)
            self.assertTrue(lock_path.exists())
        finally:
            os.rmdir(lock_path)

    def test_operation_lock_rejects_directory_without_mutation(self) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        lock_path.mkdir()
        sentinel = lock_path / "sentinel.bin"
        sentinel_bytes = b"directory sentinel\x00\xff\n"
        sentinel.write_bytes(sentinel_bytes)

        with self.assertRaises(installer.InstallerError) as raised:
            with installer._fixture_operation_lock(
                self.fixture,
                "directory-probe",
            ):
                self.fail("directory operation lock was accepted")

        self.assertEqual(raised.exception.code, "operation_lock_invalid")
        self.assertEqual(sentinel.read_bytes(), sentinel_bytes)
        self.assertTrue(lock_path.is_dir())

    @unittest.skipIf(os.name == "nt", "POSIX special file required")
    def test_operation_lock_rejects_fifo_without_mutation(self) -> None:
        lock_path = self.fixture / ".xc-package-operation.lock"
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        os.mkfifo(lock_path)

        with self.assertRaises(installer.InstallerError) as raised:
            with installer._fixture_operation_lock(
                self.fixture,
                "fifo-probe",
            ):
                self.fail("FIFO operation lock was accepted")

        self.assertEqual(raised.exception.code, "operation_lock_invalid")
        self.assertTrue(stat.S_ISFIFO(os.lstat(lock_path).st_mode))

    @unittest.skipIf(os.name == "nt", "POSIX symlink semantics required")
    def test_uninstall_rejects_intermediate_posix_symlink_escape(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        candidate_bin = launcher.parent
        outside = self.root / "outside-posix"
        outside.mkdir()
        victim = outside / launcher.name
        victim.write_bytes(launcher.read_bytes())
        launcher.unlink()
        candidate_bin.rmdir()
        os.symlink(outside, candidate_bin, target_is_directory=True)
        try:
            with self.assertRaises(installer.InstallerError) as raised:
                installer.uninstall_fixture(fixture_root_value=str(self.fixture))
            self.assertEqual(raised.exception.code, "uninstall_drift")
            self.assertTrue(victim.is_file())
            self.assertEqual(victim.read_bytes(), b"absolute launcher")
        finally:
            candidate_bin.unlink(missing_ok=True)

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_identity_bound_delete_removes_owned_file_and_symlink(
        self,
    ) -> None:
        owned = self.fixture / "owned.bin"
        owned_bytes = b"owned file bytes\x00\xff\r\n"
        owned.write_bytes(owned_bytes)
        installer._owned_entry_state(
            self.fixture,
            owned.name,
            expected_kind="file",
            expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
            delete=True,
        )
        self.assertFalse(owned.exists())
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

        link = self.fixture / "owned-link"
        link_target = "../outside-target"
        outside = self.root / "outside-target"
        outside_bytes = b"outside symlink target\x00\xfe\n"
        outside.write_bytes(outside_bytes)
        os.symlink(link_target, link)
        installer._owned_entry_state(
            self.fixture,
            link.name,
            expected_kind="symlink",
            expected_digest=hashlib.sha256(
                link_target.encode("utf-8")
            ).hexdigest(),
            delete=True,
        )
        self.assertFalse(link.is_symlink())
        self.assertEqual(outside.read_bytes(), outside_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, link.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_identity_bound_delete_missing_path_has_no_quarantine(
        self,
    ) -> None:
        with self.assertRaises(FileNotFoundError):
            installer._owned_entry_state(
                self.fixture,
                "missing.bin",
                expected_kind="file",
                expected_digest=hashlib.sha256(b"missing").hexdigest(),
                delete=True,
            )
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, "missing.bin"),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_owned_file_real_process_replacement_is_restored(
        self,
    ) -> None:
        owned = self.fixture / "owned.bin"
        owned_bytes = b"verified owned bytes\x00\xff\r\n"
        replacement_bytes = b"external replacement bytes\x00\xfe\n"
        owned.write_bytes(owned_bytes)
        replacement = self.root / "owned-replacement.bin"
        replacement.write_bytes(replacement_bytes)
        outside = self.root / "outside-owned-sentinel.bin"
        outside_bytes = b"outside sentinel\x00\xfd\n"
        outside.write_bytes(outside_bytes)
        boundaries: list[str] = []

        def replace_after_final_read(
            boundary: str,
            candidate_root: Path,
            relative: Path,
        ) -> None:
            self.assertEqual(candidate_root, self.fixture)
            self.assertEqual(relative, Path(owned.name))
            boundaries.append(boundary)
            if boundary == "after-final-read":
                self._replace_from_separate_process(replacement, owned)

        with mock.patch.object(
            installer,
            "_owned_entry_delete_test_hook",
            side_effect=replace_after_final_read,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._owned_entry_state(
                    self.fixture,
                    owned.name,
                    expected_kind="file",
                    expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
                    delete=True,
                )

        self.assertEqual(raised.exception.code, "ownership_entry_changed")
        self.assertEqual(boundaries, ["after-final-read", "after-quarantine-rename"])
        self.assertEqual(owned.read_bytes(), replacement_bytes)
        self.assertFalse(replacement.exists())
        self.assertEqual(outside.read_bytes(), outside_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_control_file_real_process_replacement_is_restored(
        self,
    ) -> None:
        state = self.fixture / "state"
        state.mkdir()
        relative = Path("state/control.json")
        control = self.fixture / relative
        control_bytes = b'{"owned":true}\n'
        replacement_bytes = b'{"external":true}\n'
        control.write_bytes(control_bytes)
        replacement = self.root / "control-replacement.json"
        replacement.write_bytes(replacement_bytes)
        replaced = False

        def replace_after_final_read(
            boundary: str,
            candidate_root: Path,
            current_relative: Path,
        ) -> None:
            nonlocal replaced
            self.assertEqual(candidate_root, self.fixture)
            self.assertEqual(current_relative, relative)
            if boundary == "after-final-read":
                self.assertFalse(replaced)
                replaced = True
                self._replace_from_separate_process(replacement, control)

        with mock.patch.object(
            installer,
            "_owned_entry_delete_test_hook",
            side_effect=replace_after_final_read,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._delete_control_file(
                    self.fixture,
                    relative,
                    expected_digest=hashlib.sha256(control_bytes).hexdigest(),
                )

        self.assertTrue(replaced)
        self.assertEqual(raised.exception.code, "ownership_entry_changed")
        self.assertEqual(control.read_bytes(), replacement_bytes)
        self.assertFalse(replacement.exists())
        self.assertEqual(
            self._posix_delete_quarantines(state, control.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_quarantine_detects_same_inode_digest_change(self) -> None:
        owned = self.fixture / "digest-race.bin"
        owned_bytes = b"verified digest bytes\x00\xff\n"
        changed_bytes = b"same inode changed bytes\x00\xfe\n"
        owned.write_bytes(owned_bytes)

        def change_after_final_read(
            boundary: str,
            candidate_root: Path,
            relative: Path,
        ) -> None:
            self.assertEqual(candidate_root, self.fixture)
            self.assertEqual(relative, Path(owned.name))
            if boundary == "after-final-read":
                owned.write_bytes(changed_bytes)

        with mock.patch.object(
            installer,
            "_owned_entry_delete_test_hook",
            side_effect=change_after_final_read,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._owned_entry_state(
                    self.fixture,
                    owned.name,
                    expected_kind="file",
                    expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
                    delete=True,
                )

        self.assertEqual(raised.exception.code, "ownership_entry_changed")
        self.assertEqual(owned.read_bytes(), changed_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_quarantine_cleanup_failure_recovers_on_retry(self) -> None:
        owned = self.fixture / "cleanup-retry.bin"
        owned_bytes = b"owned cleanup retry bytes\x00\xff\n"
        owned.write_bytes(owned_bytes)
        digest = hashlib.sha256(owned_bytes).hexdigest()
        real_unlink = os.unlink
        injected = False

        def fail_verified_quarantine_cleanup(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal injected
            if (
                not injected
                and os.fspath(path).startswith(
                    installer._posix_delete_quarantine_prefix(owned.name)
                )
                and kwargs.get("dir_fd") is not None
            ):
                injected = True
                raise PermissionError(
                    errno.EACCES,
                    "injected quarantine cleanup failure",
                )
            real_unlink(path, *args, **kwargs)

        with mock.patch.object(
            installer.os,
            "unlink",
            side_effect=fail_verified_quarantine_cleanup,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._owned_entry_state(
                    self.fixture,
                    owned.name,
                    expected_kind="file",
                    expected_digest=digest,
                    delete=True,
                )

        self.assertTrue(injected)
        self.assertEqual(
            raised.exception.code,
            "ownership_quarantine_recovery_required",
        )
        self.assertEqual(
            raised.exception.details["reason"],
            "verified_quarantine_cleanup_failed",
        )
        self.assertTrue(raised.exception.details["verified_entry_restored"])
        self.assertEqual(owned.read_bytes(), owned_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

        installer._owned_entry_state(
            self.fixture,
            owned.name,
            expected_kind="file",
            expected_digest=digest,
            delete=True,
        )
        self.assertFalse(owned.exists())
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_restore_conflict_preserves_both_entries_and_retries(
        self,
    ) -> None:
        owned = self.fixture / "restore-conflict.bin"
        owned_bytes = b"verified owned bytes\x00\xff\n"
        replacement_bytes = b"first external replacement\x00\xfe\n"
        conflict_bytes = b"second external replacement\x00\xfd\n"
        owned.write_bytes(owned_bytes)
        replacement = self.root / "first-replacement.bin"
        replacement.write_bytes(replacement_bytes)
        conflict = self.root / "second-replacement.bin"
        conflict.write_bytes(conflict_bytes)

        def create_restore_conflict(
            boundary: str,
            candidate_root: Path,
            relative: Path,
        ) -> None:
            self.assertEqual(candidate_root, self.fixture)
            self.assertEqual(relative, Path(owned.name))
            if boundary == "after-final-read":
                self._replace_from_separate_process(replacement, owned)
            elif boundary == "after-quarantine-rename":
                self._replace_from_separate_process(conflict, owned)

        with mock.patch.object(
            installer,
            "_owned_entry_delete_test_hook",
            side_effect=create_restore_conflict,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._owned_entry_state(
                    self.fixture,
                    owned.name,
                    expected_kind="file",
                    expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
                    delete=True,
                )

        self.assertEqual(
            raised.exception.code,
            "ownership_quarantine_recovery_required",
        )
        self.assertEqual(
            raised.exception.details["reason"],
            "restore_target_conflict",
        )
        quarantines = self._posix_delete_quarantines(
            self.fixture,
            owned.name,
        )
        self.assertEqual(len(quarantines), 1)
        self.assertEqual(owned.read_bytes(), conflict_bytes)
        self.assertEqual(quarantines[0].read_bytes(), replacement_bytes)

        with self.assertRaises(installer.InstallerError) as stable:
            installer._owned_entry_state(
                self.fixture,
                owned.name,
                expected_kind="file",
                expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
                delete=True,
            )
        self.assertEqual(
            stable.exception.code,
            "ownership_quarantine_recovery_required",
        )
        self.assertEqual(
            stable.exception.details["reason"],
            "restore_target_conflict",
        )
        self.assertEqual(owned.read_bytes(), conflict_bytes)
        self.assertEqual(quarantines[0].read_bytes(), replacement_bytes)

        preserved_conflict = self.root / "preserved-conflict.bin"
        os.replace(owned, preserved_conflict)
        with self.assertRaises(installer.InstallerError) as retried:
            installer._owned_entry_state(
                self.fixture,
                owned.name,
                expected_kind="file",
                expected_digest=hashlib.sha256(owned_bytes).hexdigest(),
                delete=True,
            )
        self.assertEqual(retried.exception.code, "ownership_entry_changed")
        self.assertEqual(owned.read_bytes(), replacement_bytes)
        self.assertEqual(preserved_conflict.read_bytes(), conflict_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

    @unittest.skipIf(os.name == "nt", "POSIX quarantine semantics required")
    def test_posix_verified_quarantine_conflict_preserves_both_entries(
        self,
    ) -> None:
        owned = self.fixture / "verified-conflict.bin"
        owned_bytes = b"verified conflict bytes\x00\xff\n"
        conflict_bytes = b"concurrent target bytes\x00\xfe\n"
        owned.write_bytes(owned_bytes)
        digest = hashlib.sha256(owned_bytes).hexdigest()

        def create_conflict(
            boundary: str,
            candidate_root: Path,
            relative: Path,
        ) -> None:
            self.assertEqual(candidate_root, self.fixture)
            self.assertEqual(relative, Path(owned.name))
            if boundary == "after-quarantine-rename":
                owned.write_bytes(conflict_bytes)

        with mock.patch.object(
            installer,
            "_owned_entry_delete_test_hook",
            side_effect=create_conflict,
        ):
            with self.assertRaises(installer.InstallerError) as raised:
                installer._owned_entry_state(
                    self.fixture,
                    owned.name,
                    expected_kind="file",
                    expected_digest=digest,
                    delete=True,
                )

        self.assertEqual(
            raised.exception.code,
            "ownership_quarantine_recovery_required",
        )
        self.assertEqual(
            raised.exception.details["reason"],
            "restore_target_conflict",
        )
        quarantines = self._posix_delete_quarantines(
            self.fixture,
            owned.name,
        )
        self.assertEqual(len(quarantines), 1)
        self.assertEqual(owned.read_bytes(), conflict_bytes)
        self.assertEqual(quarantines[0].read_bytes(), owned_bytes)

        with self.assertRaises(installer.InstallerError) as stable:
            installer._owned_entry_state(
                self.fixture,
                owned.name,
                expected_kind="file",
                expected_digest=digest,
                delete=True,
            )
        self.assertEqual(
            stable.exception.code,
            "ownership_quarantine_recovery_required",
        )
        self.assertEqual(
            stable.exception.details["reason"],
            "restore_target_conflict",
        )

        preserved_conflict = self.root / "preserved-verified-conflict.bin"
        os.replace(owned, preserved_conflict)
        installer._owned_entry_state(
            self.fixture,
            owned.name,
            expected_kind="file",
            expected_digest=digest,
            delete=True,
        )
        self.assertFalse(owned.exists())
        self.assertEqual(preserved_conflict.read_bytes(), conflict_bytes)
        self.assertEqual(
            self._posix_delete_quarantines(self.fixture, owned.name),
            [],
        )

    @unittest.skipUnless(os.name == "nt", "real Windows junction required")
    def test_uninstall_rejects_intermediate_windows_junction_escape(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        candidate_bin = launcher.parent
        outside = self.root / "outside-junction"
        outside.mkdir()
        victim = outside / launcher.name
        victim.write_bytes(launcher.read_bytes())
        launcher.unlink()
        candidate_bin.rmdir()
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(candidate_bin), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if junction.returncode != 0:
            self.skipTest(f"junction creation is unavailable: {junction.stderr}")
        try:
            with self.assertRaises(installer.InstallerError) as raised:
                installer.uninstall_fixture(fixture_root_value=str(self.fixture))
            self.assertEqual(raised.exception.code, "uninstall_drift")
            self.assertTrue(victim.is_file())
            self.assertEqual(victim.read_bytes(), b"absolute launcher")
        finally:
            os.rmdir(candidate_bin)

    @unittest.skipUnless(os.name == "nt", "Windows handle semantics required")
    def test_windows_parent_swap_hardlink_escape_is_handle_bound(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        launcher = Path(installed["launcher"])
        candidate_bin = launcher.parent
        moved = candidate_bin.with_name(f"{candidate_bin.name}-moved")
        outside = self.root / "outside-race"
        outside.mkdir()
        victim = outside / launcher.name
        os.link(launcher, victim)
        original = installer._windows_regular_file_digest
        attempted = False
        swap_error: OSError | None = None

        def swap_parent(handle: int, path: Path) -> str:
            nonlocal attempted, swap_error
            if path == launcher and not attempted:
                attempted = True
                try:
                    os.replace(candidate_bin, moved)
                except OSError as error:
                    swap_error = error
                else:
                    junction = subprocess.run(
                        [
                            "cmd",
                            "/c",
                            "mklink",
                            "/J",
                            str(candidate_bin),
                            str(outside),
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=False,
                    )
                    self.assertEqual(junction.returncode, 0, junction.stderr)
            return original(handle, path)

        try:
            with mock.patch.object(
                installer,
                "_windows_regular_file_digest",
                side_effect=swap_parent,
            ):
                result = installer.uninstall_fixture(
                    fixture_root_value=str(self.fixture)
                )
            self.assertTrue(result["uninstalled"])
            self.assertTrue(attempted)
            self.assertIsNotNone(swap_error)
            self.assertTrue(victim.is_file())
            self.assertEqual(victim.read_bytes(), b"absolute launcher")
        finally:
            if candidate_bin.exists() and candidate_bin.is_dir():
                try:
                    os.rmdir(candidate_bin)
                except OSError:
                    pass
            if moved.exists():
                shutil.rmtree(moved, ignore_errors=True)

    def test_terminal_cleanup_fault_boundaries_are_idempotent(self) -> None:
        boundaries = (
            "before-marker",
            "after-marker",
            "after-active",
            "after-manifest",
            "after-final-marker",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                if self.fixture.exists():
                    shutil.rmtree(self.fixture)
                self.fixture.mkdir()
                patches = self._patch_runtime()
                with patches[0], patches[1], patches[2], patches[3]:
                    self._install()
                paths = installer._fixture_paths(self.fixture)
                original_atomic = installer._atomic_write
                original_delete = installer._delete_control_file
                terminal_state: dict[str, str] = {}
                injected = False

                def remember_terminal_state(value: object) -> None:
                    self.assertIsInstance(value, dict)
                    assert isinstance(value, dict)
                    candidate_root = value.get("candidate_root")
                    ownership_manifest = value.get("ownership_manifest")
                    self.assertIsInstance(candidate_root, str)
                    self.assertIsInstance(ownership_manifest, str)
                    assert isinstance(candidate_root, str)
                    assert isinstance(ownership_manifest, str)
                    terminal_state["candidate_root"] = candidate_root
                    terminal_state["ownership_manifest"] = ownership_manifest

                def inject_atomic(path: Path, value: object) -> str:
                    nonlocal injected
                    is_marker = path == installer._terminal_cleanup_path(paths)
                    if is_marker:
                        remember_terminal_state(value)
                    if is_marker and boundary == "before-marker":
                        injected = True
                        raise OSError("injected before terminal marker")
                    digest = original_atomic(path, value)
                    if is_marker and boundary == "after-marker":
                        injected = True
                        raise OSError("injected after terminal marker")
                    return digest

                def inject_delete(
                    root: Path,
                    relative: Path,
                    **kwargs: object,
                ) -> None:
                    nonlocal injected
                    target = root / relative
                    is_active = relative.as_posix() == "state/active.json"
                    is_marker = (
                        relative.as_posix() == "state/uninstall-finalize.json"
                    )
                    if is_marker:
                        remember_terminal_state(
                            json.loads(target.read_text(encoding="utf-8"))
                        )
                    is_final_manifest = False
                    if (
                        relative.parent.as_posix() == "state/manifests"
                        and target.is_file()
                    ):
                        value = json.loads(target.read_text(encoding="utf-8"))
                        is_final_manifest = (
                            value.get("entries") == []
                            and value.get("uninstall_pending") is None
                        )
                    original_delete(root, relative, **kwargs)
                    if is_active and boundary == "after-active":
                        injected = True
                        raise OSError("injected after active cleanup")
                    if is_final_manifest and boundary == "after-manifest":
                        injected = True
                        raise OSError("injected after manifest cleanup")
                    if is_marker and boundary == "after-final-marker":
                        injected = True
                        raise OSError("injected after terminal marker cleanup")

                with mock.patch.object(
                    installer,
                    "_atomic_write",
                    side_effect=inject_atomic,
                ), mock.patch.object(
                    installer,
                    "_delete_control_file",
                    side_effect=inject_delete,
                ):
                    with self.assertRaises(OSError):
                        installer.uninstall_fixture(
                            fixture_root_value=str(self.fixture)
                        )
                self.assertTrue(injected)

                result = installer.uninstall_fixture(
                    fixture_root_value=str(self.fixture)
                )
                self.assertTrue(result["uninstalled"])
                self._assert_exact_terminal_state_removed(
                    paths,
                    candidate_relative=terminal_state["candidate_root"],
                    manifest_relative=terminal_state["ownership_manifest"],
                )

        for boundary in ("after-marker", "after-final-marker"):
            for repetition in range(TERMINAL_CLEANUP_STRESS_REPETITIONS):
                with self.subTest(
                    boundary=boundary,
                    fresh_process_repetition=repetition,
                ):
                    if self.fixture.exists():
                        shutil.rmtree(self.fixture)
                    self.fixture.mkdir()
                    patches = self._patch_runtime()
                    with patches[0], patches[1], patches[2], patches[3]:
                        self._install()
                    paths = installer._fixture_paths(self.fixture)
                    terminal_state = self._run_terminal_cleanup_fault_process(
                        boundary
                    )
                    self._run_uninstall_process()
                    self._assert_exact_terminal_state_removed(
                        paths,
                        candidate_relative=str(
                            terminal_state["candidate_root"]
                        ),
                        manifest_relative=str(
                            terminal_state["ownership_manifest"]
                        ),
                    )

        with self.subTest(transient_active_replace=True):
            if self.fixture.exists():
                shutil.rmtree(self.fixture)
            self.fixture.mkdir()
            patches = self._patch_runtime()
            with patches[0], patches[1], patches[2], patches[3]:
                installed = self._install()
            paths = installer._fixture_paths(self.fixture)
            candidate_root = Path(installed["launcher"]).parent.parent
            original_replace = os.replace
            transient_failure = False

            def fail_first_active_replace(
                source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            ) -> None:
                nonlocal transient_failure
                if (
                    Path(destination) == paths["state"] / "active.json"
                    and not transient_failure
                ):
                    transient_failure = True
                    raise PermissionError("injected active replacement contention")
                original_replace(source, destination)

            with mock.patch.object(
                installer.os,
                "replace",
                side_effect=fail_first_active_replace,
            ):
                result = installer.uninstall_fixture(
                    fixture_root_value=str(self.fixture)
                )
            self.assertTrue(transient_failure)
            self.assertTrue(result["uninstalled"])
            self.assertFalse(candidate_root.exists())
            self.assertFalse((paths["state"] / "active.json").exists())
            self.assertFalse(installer._terminal_cleanup_path(paths).exists())
            self.assertFalse(installer._ownership_transition_path(paths).exists())
            self.assertFalse(paths["manifests"].exists())

        with self.subTest(active_replace_failure_rolls_back_manifest=True):
            if self.fixture.exists():
                shutil.rmtree(self.fixture)
            self.fixture.mkdir()
            patches = self._patch_runtime()
            with patches[0], patches[1], patches[2], patches[3]:
                installed = self._install()
            paths = installer._fixture_paths(self.fixture)
            active_path = paths["state"] / "active.json"
            active_before = active_path.read_bytes()
            active = json.loads(active_before)
            original_manifest = self.fixture / active["ownership_manifest"]
            candidate_root = Path(installed["launcher"]).parent.parent
            original_replace = os.replace

            def reject_active_replace(
                source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            ) -> None:
                if Path(destination) == active_path:
                    raise PermissionError("injected persistent active contention")
                original_replace(source, destination)

            with mock.patch.object(
                installer,
                "_CONTROL_FILE_CONVERGENCE_TIMEOUT_SECONDS",
                0.0,
            ), mock.patch.object(
                installer.os,
                "replace",
                side_effect=reject_active_replace,
            ):
                with self.assertRaises(PermissionError):
                    installer.uninstall_fixture(
                        fixture_root_value=str(self.fixture)
                    )
            self.assertEqual(active_path.read_bytes(), active_before)
            self.assertEqual(
                list(paths["manifests"].iterdir()),
                [original_manifest],
            )
            self.assertFalse(installer._ownership_transition_path(paths).exists())
            result = installer.uninstall_fixture(
                fixture_root_value=str(self.fixture)
            )
            self.assertTrue(result["uninstalled"])
            self.assertFalse(candidate_root.exists())
            self.assertFalse(active_path.exists())
            self.assertFalse(installer._terminal_cleanup_path(paths).exists())
            self.assertFalse(paths["manifests"].exists())

    def test_terminal_cleanup_preserves_unbound_manifest(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            self._install()
        paths = installer._fixture_paths(self.fixture)
        unrelated = paths["manifests"] / "user-maintained.json"
        unrelated_bytes = b'{"owner":"user"}\n'
        unrelated.write_bytes(unrelated_bytes)

        terminal_state = self._run_terminal_cleanup_fault_process("after-marker")
        self._run_uninstall_process()

        self.assertFalse((paths["state"] / "active.json").exists())
        self.assertFalse(installer._terminal_cleanup_path(paths).exists())
        self.assertFalse(installer._ownership_transition_path(paths).exists())
        self.assertFalse(
            (self.fixture / str(terminal_state["candidate_root"])).exists()
        )
        self.assertFalse(
            (self.fixture / str(terminal_state["ownership_manifest"])).exists()
        )
        self.assertEqual(unrelated.read_bytes(), unrelated_bytes)
        self.assertEqual(list(paths["manifests"].iterdir()), [unrelated])

    def test_hard_killed_ownership_transitions_recover_exactly(self) -> None:
        old_active_boundaries = {
            "after-journal",
            "after-next-manifest",
            "before-active-replace",
        }
        old_manifest_absent_boundaries = {
            "after-old-manifest-delete",
            "before-journal-delete",
        }
        for boundary in OWNERSHIP_TRANSITION_KILL_BOUNDARIES:
            for repetition in range(OWNERSHIP_TRANSITION_KILL_REPETITIONS):
                with self.subTest(boundary=boundary, repetition=repetition):
                    if self.fixture.exists():
                        shutil.rmtree(self.fixture)
                    self.fixture.mkdir()
                    patches = self._patch_runtime()
                    with patches[0], patches[1], patches[2], patches[3]:
                        self._install()
                    paths = installer._fixture_paths(self.fixture)
                    unrelated = paths["manifests"] / "user-maintained.json"
                    unrelated_bytes = (
                        f'{{"owner":"user","repetition":{repetition}}}\n'.encode(
                            "utf-8"
                        )
                    )
                    unrelated.write_bytes(unrelated_bytes)

                    process, evidence = (
                        self._start_ownership_transition_kill_process(boundary)
                    )
                    journal = evidence["journal"]
                    assert isinstance(journal, dict)
                    journal_path = installer._ownership_transition_path(paths)
                    self.assertEqual(
                        journal_path.read_bytes(),
                        installer._canonical_json(journal),
                    )
                    self.assertEqual(
                        journal["intended_active_sha256"],
                        installer._canonical_sha256(journal["intended_active"]),
                    )
                    old_relative = Path(journal["old_manifest"]["path"])
                    new_relative = Path(journal["new_manifest"]["path"])
                    old_manifest = self.fixture / old_relative
                    new_manifest = self.fixture / new_relative
                    active = evidence["active"]
                    assert isinstance(active, dict)
                    expected_pointer = (
                        journal["old_manifest"]
                        if boundary in old_active_boundaries
                        else journal["new_manifest"]
                    )
                    self.assertEqual(
                        active["ownership_manifest"],
                        expected_pointer["path"],
                    )
                    self.assertEqual(
                        active["ownership_manifest_sha256"],
                        expected_pointer["sha256"],
                    )
                    self.assertEqual(
                        new_manifest.exists(),
                        boundary != "after-journal",
                    )
                    self.assertEqual(
                        old_manifest.exists(),
                        boundary not in old_manifest_absent_boundaries,
                    )

                    process.kill()
                    process.communicate(timeout=10)
                    result = self._run_uninstall_process()
                    self.assertTrue(result["uninstalled"])
                    self.assertFalse((paths["state"] / "active.json").exists())
                    self.assertFalse(journal_path.exists())
                    self.assertFalse(
                        installer._terminal_cleanup_path(paths).exists()
                    )
                    self.assertFalse(
                        (self.fixture / journal["candidate_root"]).exists()
                    )
                    self.assertFalse(old_manifest.exists())
                    self.assertFalse(new_manifest.exists())
                    self.assertEqual(unrelated.read_bytes(), unrelated_bytes)
                    self.assertEqual(
                        list(paths["manifests"].iterdir()),
                        [unrelated],
                    )

    def test_ownership_transition_recovery_fails_closed_when_ambiguous(
        self,
    ) -> None:
        scenarios = {
            "new-manifest-changed": "after-next-manifest",
            "old-manifest-changed": "after-active-replace",
            "active-missing": "after-next-manifest",
            "active-intermediate": "after-next-manifest",
        }
        for scenario, boundary in scenarios.items():
            with self.subTest(scenario=scenario):
                if self.fixture.exists():
                    shutil.rmtree(self.fixture)
                self.fixture.mkdir()
                patches = self._patch_runtime()
                with patches[0], patches[1], patches[2], patches[3]:
                    self._install()
                paths = installer._fixture_paths(self.fixture)
                unrelated = paths["manifests"] / "user-maintained.json"
                unrelated_bytes = b'{"owner":"user"}\n'
                unrelated.write_bytes(unrelated_bytes)
                process, evidence = self._start_ownership_transition_kill_process(
                    boundary
                )
                journal = evidence["journal"]
                assert isinstance(journal, dict)
                process.kill()
                process.communicate(timeout=10)

                old_manifest = self.fixture / journal["old_manifest"]["path"]
                new_manifest = self.fixture / journal["new_manifest"]["path"]
                journal_path = installer._ownership_transition_path(paths)
                if scenario == "new-manifest-changed":
                    new_manifest.write_bytes(new_manifest.read_bytes() + b" ")
                elif scenario == "old-manifest-changed":
                    old_manifest.write_bytes(old_manifest.read_bytes() + b" ")
                elif scenario == "active-intermediate":
                    active_path = paths["state"] / "active.json"
                    active = json.loads(active_path.read_text(encoding="utf-8"))
                    active["transition_state"] = "intermediate"
                    active_path.write_bytes(installer._canonical_json(active))
                else:
                    (paths["state"] / "active.json").unlink()

                with self.assertRaises(installer.InstallerError) as raised:
                    installer.uninstall_fixture(
                        fixture_root_value=str(self.fixture)
                    )
                self.assertEqual(
                    raised.exception.code,
                    "ownership_transition_invalid",
                )
                self.assertTrue(journal_path.is_file())
                self.assertTrue(old_manifest.is_file())
                self.assertTrue(new_manifest.is_file())
                self.assertTrue(
                    (self.fixture / journal["candidate_root"]).is_dir()
                )
                self.assertEqual(unrelated.read_bytes(), unrelated_bytes)

    def test_hard_terminated_uninstall_reclaims_lock_and_converges(self) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            self._install()
        ready = self.root / "uninstall-paused"
        child_code = r"""
import importlib.util
import pathlib
import sys
import time

helper = pathlib.Path(sys.argv[1])
fixture = pathlib.Path(sys.argv[2])
ready = pathlib.Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("xc_package_install_child", helper)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
original = module._persist_ownership_state

def pause_after_pending(*args, **kwargs):
    result = original(*args, **kwargs)
    if kwargs.get("pending") is not None and not ready.exists():
        ready.write_text("ready", encoding="utf-8")
        time.sleep(300)
    return result

module._persist_ownership_state = pause_after_pending
module.uninstall_fixture(fixture_root_value=str(fixture))
"""
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                child_code,
                str(HELPER_PATH),
                str(self.fixture),
                str(ready),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        deadline = time.monotonic() + 15
        while not ready.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(
                    f"uninstall child exited early: {process.returncode}\n"
                    f"stdout={stdout}\nstderr={stderr}"
                )
            time.sleep(0.05)
        if not ready.exists():
            process.kill()
            process.communicate(timeout=10)
            self.fail("uninstall child did not reach the persisted pending state")

        lock_path = self.fixture / ".xc-package-operation.lock"
        stale_entries = installer._operation_lock_entries(
            lock_path,
            "uninstall",
            require_published=True,
            require_single_links=True,
        )
        stale = stale_entries["record"]
        assert isinstance(stale, dict)
        self.assertEqual(stale["state"], "held")
        self.assertEqual(stale["pid"], process.pid)
        with self.assertRaises(installer.InstallerError) as raised:
            installer.uninstall_fixture(fixture_root_value=str(self.fixture))
        self.assertEqual(raised.exception.code, "operation_in_progress")
        self.assertTrue((self.fixture / "state" / "active.json").is_file())
        process.kill()
        process.communicate(timeout=10)

        published: list[dict[str, object]] = []
        original_publish = installer._publish_operation_owner

        def capture_reclaimed_owner(
            directory: dict[str, object],
            path: Path,
            operation: str,
            record: dict[str, object],
        ) -> dict[str, object]:
            published.append(dict(record))
            return original_publish(
                directory,
                path,
                operation,
                record,
            )

        with mock.patch.object(
            installer,
            "_publish_operation_owner",
            side_effect=capture_reclaimed_owner,
        ):
            result = installer.uninstall_fixture(
                fixture_root_value=str(self.fixture)
            )
        self.assertTrue(result["uninstalled"])
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["reclaimed_token"], stale["token"])
        self.assertFalse((self.fixture / "state" / "active.json").exists())
        self.assertFalse(
            installer._ownership_transition_path(
                installer._fixture_paths(self.fixture)
            ).exists()
        )
        self.assertFalse(lock_path.exists())

    def test_uninstall_rejects_changed_ownership_manifest_without_deletion(
        self,
    ) -> None:
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3]:
            installed = self._install()
        active = json.loads(
            (self.fixture / "state" / "active.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = self.fixture / active["ownership_manifest"]
        manifest.write_bytes(manifest.read_bytes() + b" ")

        with self.assertRaises(installer.InstallerError) as raised:
            installer.uninstall_fixture(
                fixture_root_value=str(self.fixture)
            )
        self.assertEqual(
            raised.exception.code,
            "ownership_manifest_hash_mismatch",
        )
        self.assertTrue(Path(installed["launcher"]).is_file())

    def test_fixture_root_rejects_project_and_workshop_overlap(self) -> None:
        for value in (
            REPOSITORY_ROOT,
            REPOSITORY_ROOT / "tests",
            REPOSITORY_ROOT / ".xcoding",
        ):
            with self.subTest(value=value):
                with self.assertRaises(installer.InstallerError) as raised:
                    installer._fixture_root(str(value.resolve()))
                self.assertEqual(
                    raised.exception.code,
                    "fixture_root_not_isolated",
                )

    def test_windows_console_oracle_is_real_not_mock_contract(self) -> None:
        source = HELPER_PATH.read_text(encoding="utf-8")
        self.assertIn("GetConsoleWindow()", source)
        self.assertIn("CREATE_NO_WINDOW", source)
        self.assertIn("importlib.metadata.version", source)
        self.assertNotIn("mock", source)


if __name__ == "__main__":
    unittest.main()
