from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from scripts import verify_wheel
from scripts.verify_wheel import VerificationError


BASELINE = "1" * 40
CANDIDATE_TREE = "2" * 64
CANDIDATE_ARCHIVE = "3" * 64
RESOURCE_PATH = "skills/xc-alpha/SKILL.md"
RESOURCE_DATA = b"---\nname: xc-alpha\n---\n"


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(
        hashlib.sha256(data).digest()
    ).rstrip(b"=").decode("ascii")


def manifest_bytes(
    *,
    candidate_tree: str = CANDIDATE_TREE,
) -> bytes:
    return canonical_json_bytes(
        {
            "bundle_schema_version": 1,
            "xc_version": verify_wheel.EXPECTED_VERSION,
            "baseline_revision": BASELINE,
            "source_state": "work-order-candidate",
            "candidate_tree_sha256": candidate_tree,
            "candidate_source_archive_sha256": CANDIDATE_ARCHIVE,
            "python_requires": ">=3.12",
            "runtime_tree_schema": 1,
            "resources": [
                {
                    "kind": "skill",
                    "adapter_id": None,
                    "source_path": RESOURCE_PATH,
                    "bundle_path": RESOURCE_PATH,
                    "size": len(RESOURCE_DATA),
                    "sha256": hashlib.sha256(RESOURCE_DATA).hexdigest(),
                }
            ],
        }
    )


def write_test_wheel(
    output: Path,
    *,
    timestamp: tuple[int, int, int, int, int, int] = (2026, 1, 2, 3, 4, 6),
    unsafe_member: str | None = None,
    metadata_version: str = verify_wheel.EXPECTED_VERSION,
    candidate_tree: str = CANDIDATE_TREE,
    bad_record_hash: bool = False,
    bad_record_size: bool = False,
    omitted_member: str | None = None,
) -> Path:
    dist_info = verify_wheel.EXPECTED_DIST_INFO
    members = {
        "xcoding/__init__.py": b"",
        "xcoding/__main__.py": b"from .cli import main\n",
        "xcoding/cli.py": b"def main():\n    return 0\n",
        "xcoding/runtime/__init__.py": b"",
        "xcoding/runtime/application.py": b"def execute():\n    return None\n",
        "xcoding/runtime/commands.py": b"COMMAND_NAMES = ()\n",
        "xcoding/runtime/core.py": b"SCHEMA_VERSION = 1\n",
        "xcoding/runtime/query.py": b"READ_ONLY_COMMANDS = ()\n",
        "xcoding/runtime/assets/minimal-template.xml": b"<orchestration />\n",
        "xcoding/viewer/__init__.py": b"",
        "xcoding/viewer/cli.py": b"def main():\n    return 0\n",
        "xcoding/viewer/picker.py": b"def main():\n    return 0\n",
        "xcoding/viewer/server.py": b"def main():\n    return 0\n",
        "xcoding/viewer/static/app.css": b"",
        "xcoding/viewer/static/app.js": b"",
        "xcoding/viewer/static/index.html": b"",
        "xcoding/daemon/__init__.py": b"",
        "xcoding/daemon/cli.py": b"def main():\n    return 0\n",
        "xcoding/daemon/protocol.py": b"SCHEMA_VERSION = 1\n",
        "xcoding/daemon/server.py": b"DEFAULT_HOST = '127.0.0.1'\n",
        f"xcoding/_bundle/{RESOURCE_PATH}": RESOURCE_DATA,
        verify_wheel.MANIFEST_MEMBER: manifest_bytes(
            candidate_tree=candidate_tree,
        ),
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.3\n"
            "Name: xcoding-workflow\n"
            f"Version: {metadata_version}\n"
            "Requires-Python: >=3.12\n"
            "\n"
        ).encode("utf-8"),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: test\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
            "\n"
        ).encode("utf-8"),
        f"{dist_info}/entry_points.txt": (
            "[console_scripts]\nxcoding = xcoding.cli:main\n"
        ).encode("utf-8"),
    }
    if omitted_member is not None:
        members.pop(omitted_member)
    if unsafe_member is not None:
        members[unsafe_member] = b"unsafe"

    record_name = f"{dist_info}/RECORD"
    rows: list[list[str]] = []
    for name, data in members.items():
        digest = record_hash(data)
        size = str(len(data))
        if bad_record_hash and name == "xcoding/cli.py":
            digest = "sha256=" + "A" * 43
        if bad_record_size and name == "xcoding/cli.py":
            size = str(len(data) + 1)
        rows.append([name, digest, size])
    rows.append([record_name, "", ""])
    record_stream = io.StringIO(newline="")
    csv.writer(record_stream, lineterminator="\n").writerows(rows)
    members[record_name] = record_stream.getvalue().encode("utf-8")

    wheel_path = output / verify_wheel.EXPECTED_WHEEL_FILENAME
    with zipfile.ZipFile(
        wheel_path,
        "x",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return wheel_path


class WheelVerifierTests(unittest.TestCase):
    def assert_code(self, code: str, callable_object, *args, **kwargs) -> None:
        with self.assertRaises(VerificationError) as raised:
            callable_object(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def verify(self, root: Path, first: Path, second: Path) -> dict[str, object]:
        return verify_wheel.verify_reproducible_wheels(
            project_root=REPOSITORY_ROOT,
            disposable_root=root,
            first_directory=first,
            second_directory=second,
            expected_tag="py3-none-any",
            baseline_revision=BASELINE,
            candidate_tree_sha256=CANDIDATE_TREE,
            candidate_source_archive_sha256=CANDIDATE_ARCHIVE,
        )

    def test_accepts_two_byte_identical_universal_wheels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            first_wheel = write_test_wheel(first)
            second_wheel = write_test_wheel(second)

            result = self.verify(root, first, second)

            self.assertEqual(
                result["wheel_sha256"],
                hashlib.sha256(first_wheel.read_bytes()).hexdigest(),
            )
            self.assertEqual(first_wheel.read_bytes(), second_wheel.read_bytes())
            self.assertIs(result["wheel_byte_identical"], True)
            self.assertIs(result["zip_metadata_byte_identical"], True)

    def test_rejects_non_exact_output_and_unsafe_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            write_test_wheel(first)
            write_test_wheel(second)
            (first / "unexpected.tar.gz").write_bytes(b"extra")
            self.assert_code(
                "wheel_output_invalid",
                self.verify,
                root,
                first,
                second,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            write_test_wheel(first, unsafe_member="../escape")
            write_test_wheel(second, unsafe_member="../escape")
            self.assert_code("path_unsafe", self.verify, root, first, second)

    def test_rejects_metadata_record_and_candidate_mismatches(self) -> None:
        cases = (
            ({"metadata_version": "9.9"}, "metadata_invalid"),
            ({"bad_record_hash": True}, "record_invalid"),
            ({"bad_record_size": True}, "record_invalid"),
            ({"candidate_tree": "4" * 64}, "manifest_invalid"),
            (
                {"omitted_member": "xcoding/runtime/commands.py"},
                "member_missing",
            ),
            (
                {"omitted_member": "xcoding/daemon/server.py"},
                "member_missing",
            ),
            (
                {"omitted_member": "xcoding/viewer/server.py"},
                "member_missing",
            ),
        )
        for index, (options, code) in enumerate(cases):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                first = root / f"first-{index}"
                second = root / f"second-{index}"
                first.mkdir()
                second.mkdir()
                write_test_wheel(first, **options)
                write_test_wheel(second, **options)
                self.assert_code(code, self.verify, root, first, second)

    def test_rejects_zip_metadata_and_final_byte_differences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            write_test_wheel(first)
            write_test_wheel(second, timestamp=(2026, 1, 2, 3, 4, 8))
            self.assert_code(
                "wheel_not_reproducible",
                self.verify,
                root,
                first,
                second,
            )


class CandidateIdentityTests(unittest.TestCase):
    def git(self, project: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(project), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def seal(
        self,
        project: Path,
        root: Path,
        baseline: str,
    ) -> dict[str, object]:
        root.mkdir()
        return verify_wheel.seal_candidate(
            project_root=project,
            disposable_root=root,
            baseline_revision=baseline,
            candidate_paths=["base.txt", "new.txt"],
            archive_path=root / "candidate.zip",
            descriptor_path=root / "candidate.json",
        )

    def initialize_project(self, parent: Path) -> tuple[Path, str]:
        project = parent / "project"
        project.mkdir()
        self.git(project, "init", "-q")
        (project / "base.txt").write_bytes(b"baseline\n")
        self.git(project, "add", "base.txt")
        self.git(
            project,
            "-c",
            "user.name=XC Test",
            "-c",
            "user.email=xc-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
        )
        return project, self.git(project, "rev-parse", "HEAD")

    def seal_clean(
        self,
        project: Path,
        root: Path,
        baseline: str,
        *,
        candidate_paths: list[str] | None = None,
    ) -> dict[str, object]:
        root.mkdir()
        return verify_wheel.seal_candidate(
            project_root=project,
            disposable_root=root,
            baseline_revision=baseline,
            candidate_paths=candidate_paths,
            clean_head=True,
            archive_path=root / "candidate.zip",
            descriptor_path=root / "candidate.json",
        )

    def assert_candidate_invalid(self, callable_object, *args, **kwargs) -> None:
        with self.assertRaises(VerificationError) as raised:
            callable_object(*args, **kwargs)
        self.assertEqual(raised.exception.code, "candidate_invalid")

    def test_candidate_identity_is_deterministic_and_byte_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            (project / "base.txt").write_bytes(b"candidate\n")
            (project / "new.txt").write_bytes(b"new\n")

            first = self.seal(project, parent / "seal-a", baseline)
            second = self.seal(project, parent / "seal-b", baseline)

            self.assertEqual(
                first["candidate_tree_sha256"],
                second["candidate_tree_sha256"],
            )
            self.assertEqual(
                first["candidate_source_archive_sha256"],
                second["candidate_source_archive_sha256"],
            )
            self.assertEqual(
                (parent / "seal-a" / "candidate.zip").read_bytes(),
                (parent / "seal-b" / "candidate.zip").read_bytes(),
            )
            self.assertEqual(
                (parent / "seal-a" / "candidate.json").read_bytes(),
                (parent / "seal-b" / "candidate.json").read_bytes(),
            )

            (project / "new.txt").write_bytes(b"changed\n")
            changed = self.seal(project, parent / "seal-c", baseline)
            self.assertNotEqual(
                first["candidate_tree_sha256"],
                changed["candidate_tree_sha256"],
            )
            self.assertNotEqual(
                first["candidate_source_archive_sha256"],
                changed["candidate_source_archive_sha256"],
            )

            descriptor = json.loads(
                (parent / "seal-a" / "candidate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(descriptor["schema_version"], 2)
            self.assertEqual(descriptor["candidate_origin"], "dirty-worktree")
            self.assertEqual(descriptor["source_state"], "work-order-candidate")

    def test_clean_head_is_deterministic_and_bound_to_commit_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            baseline_tree = self.git(project, "rev-parse", f"{baseline}^{{tree}}")

            first = self.seal_clean(project, parent / "seal-a", baseline)
            second = self.seal_clean(project, parent / "seal-b", baseline)

            self.assertEqual(
                (parent / "seal-a" / "candidate.zip").read_bytes(),
                (parent / "seal-b" / "candidate.zip").read_bytes(),
            )
            self.assertEqual(
                (parent / "seal-a" / "candidate.json").read_bytes(),
                (parent / "seal-b" / "candidate.json").read_bytes(),
            )
            self.assertEqual(first["candidate_origin"], "clean-head")
            self.assertEqual(first["candidate_git_tree"], baseline_tree)
            self.assertEqual(first["baseline_git_tree"], baseline_tree)
            self.assertEqual(first["candidate_path_count"], 0)
            descriptor = json.loads(
                (parent / "seal-a" / "candidate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(descriptor["candidate_paths"], [])
            self.assertEqual(descriptor["candidate_git_tree"], baseline_tree)
            self.assertEqual(descriptor["baseline_git_tree"], baseline_tree)
            self.assertEqual(descriptor["source_state"], "work-order-candidate")

    def test_clean_head_rejects_every_git_status_category(self) -> None:
        mutations = {
            "staged": lambda project: (
                (project / "staged.txt").write_bytes(b"staged\n"),
                self.git(project, "add", "staged.txt"),
            ),
            "tracked": lambda project: (project / "base.txt").write_bytes(b"changed\n"),
            "deleted": lambda project: (project / "base.txt").unlink(),
            "untracked": lambda project: (project / "new.txt").write_bytes(b"new\n"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                project, baseline = self.initialize_project(parent)
                mutate(project)
                self.assert_candidate_invalid(
                    self.seal_clean,
                    project,
                    parent / "seal",
                    baseline,
                )

    def test_candidate_modes_and_baseline_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            self.assert_candidate_invalid(
                self.seal_clean,
                project,
                parent / "both",
                baseline,
                candidate_paths=["base.txt"],
            )
            neither = parent / "neither"
            neither.mkdir()
            self.assert_candidate_invalid(
                verify_wheel.seal_candidate,
                project_root=project,
                disposable_root=neither,
                baseline_revision=baseline,
                archive_path=neither / "candidate.zip",
                descriptor_path=neither / "candidate.json",
            )
            self.assert_candidate_invalid(
                self.seal_clean,
                project,
                parent / "wrong-head",
                "0" * 40,
            )

    def test_dirty_mode_preserves_exact_status_matching(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            (project / "base.txt").write_bytes(b"candidate\n")
            (project / "new.txt").write_bytes(b"new\n")
            for label, paths in (
                ("missing", ["base.txt"]),
                ("extra", ["base.txt", "new.txt", "other.txt"]),
            ):
                with self.subTest(label=label):
                    root = parent / label
                    root.mkdir()
                    self.assert_candidate_invalid(
                        verify_wheel.seal_candidate,
                        project_root=project,
                        disposable_root=root,
                        baseline_revision=baseline,
                        candidate_paths=paths,
                        archive_path=root / "candidate.zip",
                        descriptor_path=root / "candidate.json",
                    )

    def test_clean_head_rejects_repository_change_during_sealing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            root = parent / "seal"
            original_write = verify_wheel._write_candidate_archive

            def write_then_mutate(path, inventory) -> None:
                original_write(path, inventory)
                (project / "changed-during-seal.txt").write_bytes(b"changed\n")

            with mock.patch.object(
                verify_wheel,
                "_write_candidate_archive",
                side_effect=write_then_mutate,
            ):
                self.assert_candidate_invalid(
                    self.seal_clean,
                    project,
                    root,
                    baseline,
                )
            self.assertFalse((root / "candidate.zip").exists())
            self.assertFalse((root / "candidate.json").exists())

    def test_clean_head_rejects_clean_commit_transition_between_final_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            project, baseline = self.initialize_project(parent)
            root = parent / "seal"
            original_snapshot = verify_wheel._git_snapshot
            calls = 0

            def snapshot_then_commit(repository: Path) -> tuple[str, list[str]]:
                nonlocal calls
                calls += 1
                if calls == 3:
                    (project / "second-commit.txt").write_bytes(b"second\n")
                    self.git(project, "add", "second-commit.txt")
                    self.git(
                        project,
                        "-c",
                        "user.name=XC Test",
                        "-c",
                        "user.email=xc-test@example.invalid",
                        "commit",
                        "-q",
                        "-m",
                        "second",
                    )
                return original_snapshot(repository)

            with mock.patch.object(
                verify_wheel,
                "_git_snapshot",
                side_effect=snapshot_then_commit,
            ):
                self.assert_candidate_invalid(
                    self.seal_clean,
                    project,
                    root,
                    baseline,
                )
            self.assertEqual(calls, 3)
            self.assertFalse((root / "candidate.zip").exists())
            self.assertFalse((root / "candidate.json").exists())

    def test_candidate_cli_requires_exactly_one_origin_mode(self) -> None:
        parser = verify_wheel._parser()
        common = [
            "candidate",
            "--project-root",
            str(REPOSITORY_ROOT),
            "--disposable-root",
            str(REPOSITORY_ROOT.parent),
            "--baseline-revision",
            "0" * 40,
            "--archive",
            str(REPOSITORY_ROOT.parent / "candidate.zip"),
            "--descriptor",
            str(REPOSITORY_ROOT.parent / "candidate.json"),
        ]
        with mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(common)
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    common + ["--clean-head", "--candidate-path", "base.txt"]
                )


if __name__ == "__main__":
    unittest.main()
