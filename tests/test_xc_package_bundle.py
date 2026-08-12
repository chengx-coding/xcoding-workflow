from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from build_support import bundle as bundle_builder
from build_support.bundle import (
    BundleBuildError,
    CandidateProvenance,
    canonical_json_bytes,
    collect_bundle,
    validate_path_set,
)
from xcoding.bundle import manifest as bundle_manifest
from xcoding.bundle.manifest import (
    BundleValidationError,
    inspect_bundle,
    parse_manifest,
)
from xcoding.bundle import resources as bundle_resources


BASELINE_REVISION = "1" * 40
CANDIDATE_TREE_SHA256 = "2" * 64
CANDIDATE_ARCHIVE_SHA256 = "3" * 64
PROVENANCE = CandidateProvenance(
    baseline_revision=BASELINE_REVISION,
    candidate_tree_sha256=CANDIDATE_TREE_SHA256,
    candidate_source_archive_sha256=CANDIDATE_ARCHIVE_SHA256,
)
EXPECTED_PROVENANCE = {
    "baseline_revision": BASELINE_REVISION,
    "source_state": "work-order-candidate",
    "candidate_tree_sha256": CANDIDATE_TREE_SHA256,
    "candidate_source_archive_sha256": CANDIDATE_ARCHIVE_SHA256,
}

SKILL_PATH = "skills/xc-alpha/SKILL.md"
ADAPTER_PATH = "adapters/test-host/delegate-agent.md"


class CandidateRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.write(
            "pyproject.toml",
            """[project]
name = "xcoding-workflow"
version = "0.1.0"
requires-python = ">=3.12"
""",
        )
        self.write("skills/xc-alpha/SKILL.md", "alpha\r\nbytes\r\n")
        self.write(
            "agents-src/agents/delegate-agent.md",
            "---\nname: delegate-agent\n---\nbody\n",
        )
        self.write(
            "agents-src/generated-agents/delegate-agent.md",
            "generated\n",
        )
        self.write(
            "agents-src/export_agents.py",
            """from pathlib import Path
import sys

root = Path(__file__).resolve().parent
expected = "generated\\n"
actual = (root / "generated-agents" / "delegate-agent.md").read_text(encoding="utf-8")
if "--check" not in sys.argv or actual != expected:
    raise SystemExit(1)
print("exported 1 agents")
""",
        )
        self.write_json(
            "build_support/host_adapters.json",
            {
                "schema_version": 1,
                "purpose": "test",
                "canonical_agents": {
                    "root": "agents-src/agents",
                    "filename_suffix": ".md",
                },
                "exporter_check": {
                    "argv": [
                        "python",
                        "agents-src/export_agents.py",
                        "--check",
                    ]
                },
                "exact_set_policy": {
                    "derive_from_canonical_agent_stems": True,
                    "require_tracked_regular_files": True,
                    "reject_missing": True,
                    "reject_changed": True,
                    "reject_extra": True,
                },
                "adapters": [
                    {
                        "adapter_id": "test-host",
                        "generated_root": "agents-src/generated-agents",
                        "generated_filename_suffix": ".md",
                        "bundle_root": "adapters/test-host",
                        "project_agents_root": ".test-host/agents",
                        "project_skills_root": ".agents/skills",
                    }
                ],
            },
        )
        self.git("init", "-q")
        self.git("add", ".")
        self.commit("fixture")

    def write(self, relative: str, content: str) -> None:
        path = self.root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")

    def write_bytes(self, relative: str, content: bytes) -> None:
        path = self.root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def write_json(self, relative: str, value: object) -> None:
        self.write_bytes(relative, canonical_json_bytes(value))

    def read_json(self, relative: str) -> dict[str, object]:
        return json.loads(
            self.root.joinpath(*relative.split("/")).read_text(encoding="utf-8")
        )

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        return result

    def commit(self, message: str) -> None:
        self.git(
            "-c",
            "user.name=XC Test",
            "-c",
            "user.email=xc-test@example.invalid",
            "commit",
            "-q",
            "-m",
            message,
        )


class BundleTestCase(unittest.TestCase):
    def create_candidate(self, parent: Path) -> CandidateRepository:
        root = parent / "candidate"
        root.mkdir()
        return CandidateRepository(root)

    def collect(
        self,
        candidate: CandidateRepository,
        parent: Path,
        name: str = "stage",
    ) -> Path:
        stage = parent / name
        stage.mkdir()
        return collect_bundle(candidate.root, stage, PROVENANCE)

    def copy_bundle(self, source: Path, parent: Path, name: str) -> Path:
        target = parent / name
        shutil.copytree(source, target)
        return target

    def assert_validation_code(
        self,
        code: str,
        callable_object,
        *arguments,
        **keywords,
    ) -> BundleValidationError:
        with self.assertRaises(BundleValidationError) as raised:
            callable_object(*arguments, **keywords)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def assert_build_code(
        self,
        code: str,
        callable_object,
        *arguments,
        **keywords,
    ) -> BundleBuildError:
        with self.assertRaises(BundleBuildError) as raised:
            callable_object(*arguments, **keywords)
        self.assertEqual(raised.exception.code, code)
        return raised.exception


class CollectorTests(BundleTestCase):
    def test_collects_deterministic_disjoint_exact_inventory_externally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            candidate = self.create_candidate(parent)

            first = self.collect(candidate, parent, "stage-a")
            second = self.collect(candidate, parent, "stage-b")

            first_files = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second).as_posix(): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)
            self.assertEqual(
                set(first_files),
                {
                    "bundle-manifest.json",
                    SKILL_PATH,
                    ADAPTER_PATH,
                },
            )
            inspection = inspect_bundle(
                first,
                expected_version="0.1.0",
                expected_provenance=EXPECTED_PROVENANCE,
            )
            self.assertEqual(
                inspection.partition_counts,
                {"skill": 1, "viewer": 0, "host-adapter": 1},
            )
            self.assertEqual(
                inspection.adapter_partition_counts,
                {"test-host": 1},
            )
            self.assertEqual(inspection.resource_count, 2)
            self.assertFalse((candidate.root / "src" / "xcoding" / "_bundle").exists())
            manifest_bytes = (first / "bundle-manifest.json").read_bytes()
            self.assertTrue(manifest_bytes.endswith(b"\n"))
            self.assertNotIn(b"\r", manifest_bytes)
            self.assertEqual(
                canonical_json_bytes(json.loads(manifest_bytes)),
                manifest_bytes,
            )

    def test_rejects_untracked_skill_and_tracked_generated_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            candidate = self.create_candidate(parent)
            candidate.write("skills/xc-alpha/EXTRA.md", "extra\n")

            stage = parent / "untracked-stage"
            stage.mkdir()
            error = self.assert_build_code(
                "source_mismatch",
                collect_bundle,
                candidate.root,
                stage,
                PROVENANCE,
            )
            self.assertIn("EXTRA.md", str(error.details))

            (candidate.root / "skills/xc-alpha/EXTRA.md").unlink()
            candidate.write(
                "agents-src/generated-agents/obsolete-agent.md",
                "obsolete\n",
            )
            candidate.git("add", ".")
            candidate.commit("add generated extra")
            second_stage = parent / "generated-stage"
            second_stage.mkdir()
            error = self.assert_build_code(
                "source_mismatch",
                collect_bundle,
                candidate.root,
                second_stage,
                PROVENANCE,
            )
            self.assertIn("obsolete-agent.md", str(error.details))

    def test_rejects_missing_changed_and_exporter_failed_generated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for state in ("missing", "changed", "exporter"):
                with self.subTest(state=state):
                    case_root = parent / state
                    case_root.mkdir()
                    candidate = self.create_candidate(case_root)
                    generated = (
                        candidate.root
                        / "agents-src"
                        / "generated-agents"
                        / "delegate-agent.md"
                    )
                    if state == "missing":
                        generated.unlink()
                    elif state == "changed":
                        generated.write_text("changed\n", encoding="utf-8")
                    else:
                        candidate.write(
                            "agents-src/export_agents.py",
                            "raise SystemExit(9)\n",
                        )
                        candidate.git("add", "agents-src/export_agents.py")
                        candidate.commit("failing exporter")
                    stage = case_root / "stage"
                    stage.mkdir()

                    self.assert_build_code(
                        "source_mismatch",
                        collect_bundle,
                        candidate.root,
                        stage,
                        PROVENANCE,
                    )

    def test_rejects_unsafe_config_paths_and_invalid_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            candidate = self.create_candidate(parent)
            config = candidate.read_json("build_support/host_adapters.json")
            config["adapters"][0]["generated_root"] = "../outside"
            candidate.write_json("build_support/host_adapters.json", config)
            stage = parent / "unsafe-stage"
            stage.mkdir()

            self.assert_build_code(
                "resource_path_unsafe",
                collect_bundle,
                candidate.root,
                stage,
                PROVENANCE,
            )

            config["adapters"][0]["generated_root"] = "agents-src/generated-agents"
            candidate.write_json("build_support/host_adapters.json", config)
            bad_provenance = CandidateProvenance(
                baseline_revision="ABC",
                candidate_tree_sha256=CANDIDATE_TREE_SHA256,
                candidate_source_archive_sha256=CANDIDATE_ARCHIVE_SHA256,
            )
            other_stage = parent / "provenance-stage"
            other_stage.mkdir()
            self.assert_build_code(
                "source_mismatch",
                collect_bundle,
                candidate.root,
                other_stage,
                bad_provenance,
            )

    def test_rejects_link_or_junction_and_non_regular_canonical_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            candidate = self.create_candidate(parent)
            skill = candidate.root / "skills" / "xc-alpha" / "SKILL.md"
            stage = parent / "link-stage"
            stage.mkdir()

            original_link_check = bundle_builder._path_is_link_or_junction

            def mark_skill_as_link(path: Path) -> bool:
                return path == skill or original_link_check(path)

            with mock.patch.object(
                bundle_builder,
                "_path_is_link_or_junction",
                side_effect=mark_skill_as_link,
            ):
                self.assert_build_code(
                    "resource_path_unsafe",
                    collect_bundle,
                    candidate.root,
                    stage,
                    PROVENANCE,
                )

            other_stage = parent / "non-file-stage"
            other_stage.mkdir()
            with mock.patch.object(bundle_builder.stat, "S_ISREG", return_value=False):
                self.assert_build_code(
                    "resource_path_unsafe",
                    collect_bundle,
                    candidate.root,
                    other_stage,
                    PROVENANCE,
                )

    def test_rejects_staging_inside_repository_or_preexisting_owned_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            candidate = self.create_candidate(parent)
            internal = candidate.root / "stage"
            internal.mkdir()
            self.assert_build_code(
                "resource_path_unsafe",
                collect_bundle,
                candidate.root,
                internal,
                PROVENANCE,
            )

            external = parent / "external"
            (external / "xcoding").mkdir(parents=True)
            self.assert_build_code(
                "resource_path_unsafe",
                collect_bundle,
                candidate.root,
                external,
                PROVENANCE,
            )

    def test_path_set_rejects_duplicate_casefold_and_nfc_collisions(self) -> None:
        cases = (
            (["skills/a", "skills/a"], "duplicate"),
            (["skills/A", "skills/a"], "casefold"),
            (["skills/Caf\u00e9", "skills/Cafe\u0301"], "nfc"),
        )
        for paths, collision in cases:
            with self.subTest(collision=collision):
                error = self.assert_build_code(
                    "resource_path_collision",
                    validate_path_set,
                    paths,
                    field="path",
                )
                self.assertEqual(error.details["collision"], collision)

    def test_build_hook_is_configured_without_checked_in_bundle(self) -> None:
        pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        hook = (REPOSITORY_ROOT / "build_support" / "hatch_build.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("[tool.hatch.build.hooks.custom]", pyproject)
        self.assertIn('path = "build_support/hatch_build.py"', pyproject)
        self.assertIn("XC_BUNDLE_STAGING_ROOT", hook)
        self.assertFalse((REPOSITORY_ROOT / "src" / "xcoding" / "_bundle").exists())


class ManifestVerificationTests(BundleTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.candidate = self.create_candidate(self.parent)
        self.bundle = self.collect(self.candidate, self.parent)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def manifest_value(self, root: Path | None = None) -> dict[str, object]:
        return json.loads(
            ((root or self.bundle) / "bundle-manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def write_manifest(self, root: Path, value: object) -> None:
        (root / "bundle-manifest.json").write_bytes(canonical_json_bytes(value))

    def test_manifest_has_exact_schema_provenance_and_no_self_hash(self) -> None:
        manifest_bytes = (self.bundle / "bundle-manifest.json").read_bytes()
        manifest = parse_manifest(manifest_bytes)
        raw = json.loads(manifest_bytes)

        self.assertEqual(manifest.baseline_revision, BASELINE_REVISION)
        self.assertEqual(manifest.source_state, "work-order-candidate")
        self.assertEqual(manifest.candidate_tree_sha256, CANDIDATE_TREE_SHA256)
        self.assertEqual(
            manifest.candidate_source_archive_sha256,
            CANDIDATE_ARCHIVE_SHA256,
        )
        self.assertEqual(manifest.xc_version, "0.1.0")
        self.assertEqual(manifest.python_requires, ">=3.12")
        self.assertEqual(
            [record.bundle_path for record in manifest.resources],
            sorted(record.bundle_path for record in manifest.resources),
        )
        self.assertNotIn(
            "bundle-manifest.json",
            {record["bundle_path"] for record in raw["resources"]},
        )

    def test_delete_tamper_and_extra_fail_for_each_resource_partition(self) -> None:
        cases = {
            "skill": SKILL_PATH,
            "host-adapter": ADAPTER_PATH,
        }
        for kind, relative in cases.items():
            with self.subTest(kind=kind, mutation="delete"):
                root = self.copy_bundle(
                    self.bundle,
                    self.parent,
                    f"{kind}-delete",
                )
                root.joinpath(*relative.split("/")).unlink()
                self.assert_validation_code(
                    "resource_missing",
                    inspect_bundle,
                    root,
                )
            with self.subTest(kind=kind, mutation="tamper"):
                root = self.copy_bundle(
                    self.bundle,
                    self.parent,
                    f"{kind}-tamper",
                )
                target = root.joinpath(*relative.split("/"))
                target.write_bytes(b"X" * len(target.read_bytes()))
                self.assert_validation_code(
                    "resource_hash_mismatch",
                    inspect_bundle,
                    root,
                )
            with self.subTest(kind=kind, mutation="extra"):
                root = self.copy_bundle(
                    self.bundle,
                    self.parent,
                    f"{kind}-extra",
                )
                if kind == "skill":
                    extra = root / "skills" / "xc-alpha" / "extra.txt"
                else:
                    extra = root / "adapters" / "test-host" / "extra.md"
                extra.write_bytes(b"extra")
                self.assert_validation_code(
                    "resource_unexpected",
                    inspect_bundle,
                    root,
                )

    def test_validation_order_distinguishes_size_and_hash_mismatch(self) -> None:
        malformed_root = self.copy_bundle(self.bundle, self.parent, "malformed-first")
        (malformed_root / "extra.txt").write_bytes(b"extra")
        value = self.manifest_value(malformed_root)
        (malformed_root / "bundle-manifest.json").write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )
        self.assert_validation_code(
            "manifest_invalid",
            inspect_bundle,
            malformed_root,
        )

        provenance_root = self.copy_bundle(self.bundle, self.parent, "source-first")
        (provenance_root / "extra.txt").write_bytes(b"extra")
        expected = dict(EXPECTED_PROVENANCE)
        expected["candidate_tree_sha256"] = "9" * 64
        self.assert_validation_code(
            "source_mismatch",
            inspect_bundle,
            provenance_root,
            expected_provenance=expected,
        )

        size_root = self.copy_bundle(self.bundle, self.parent, "size")
        size_target = size_root.joinpath(*SKILL_PATH.split("/"))
        size_target.write_bytes(size_target.read_bytes() + b"x")
        self.assert_validation_code(
            "resource_size_mismatch",
            inspect_bundle,
            size_root,
        )

        hash_root = self.copy_bundle(self.bundle, self.parent, "hash")
        hash_target = hash_root.joinpath(*SKILL_PATH.split("/"))
        hash_target.write_bytes(b"z" * len(hash_target.read_bytes()))
        self.assert_validation_code(
            "resource_hash_mismatch",
            inspect_bundle,
            hash_root,
        )

    def test_rejects_version_and_candidate_provenance_mismatch(self) -> None:
        self.assert_validation_code(
            "version_mismatch",
            inspect_bundle,
            self.bundle,
            expected_version="9.9",
        )
        expected = dict(EXPECTED_PROVENANCE)
        expected["candidate_tree_sha256"] = "4" * 64
        self.assert_validation_code(
            "source_mismatch",
            inspect_bundle,
            self.bundle,
            expected_provenance=expected,
        )

    def test_rejects_unsafe_manifest_paths(self) -> None:
        unsafe_paths = (
            "../escape",
            "/absolute",
            "C:/absolute",
            "skills\\xc-alpha\\SKILL.md",
            "skills//SKILL.md",
            "skills/./SKILL.md",
        )
        for index, unsafe in enumerate(unsafe_paths):
            with self.subTest(path=unsafe):
                root = self.copy_bundle(
                    self.bundle,
                    self.parent,
                    f"unsafe-{index}",
                )
                value = self.manifest_value(root)
                value["resources"][0]["source_path"] = unsafe
                self.write_manifest(root, value)
                self.assert_validation_code(
                    "resource_path_unsafe",
                    inspect_bundle,
                    root,
                )

    def test_rejects_duplicate_casefold_nfc_and_kind_collisions(self) -> None:
        cases: list[tuple[str, list[dict[str, object]]]] = []
        base = next(
            item
            for item in self.manifest_value()["resources"]
            if item["kind"] == "skill"
        )
        cases.append(("duplicate", [dict(base)]))

        casefold = dict(base)
        casefold["source_path"] = str(base["source_path"]).replace(
            "SKILL.md",
            "skill.md",
        )
        casefold["bundle_path"] = str(base["bundle_path"]).replace(
            "SKILL.md",
            "skill.md",
        )
        cases.append(("casefold", [casefold]))

        first_nfc = dict(base)
        first_nfc["source_path"] = "skills/xc-alpha/Caf\u00e9.md"
        first_nfc["bundle_path"] = "skills/xc-alpha/Caf\u00e9.md"
        second_nfc = dict(base)
        second_nfc["source_path"] = "skills/xc-alpha/Cafe\u0301.md"
        second_nfc["bundle_path"] = "skills/xc-alpha/Cafe\u0301.md"
        cases.append(("nfc", [first_nfc, second_nfc]))

        for index, (collision, additions) in enumerate(cases):
            with self.subTest(collision=collision):
                root = self.copy_bundle(
                    self.bundle,
                    self.parent,
                    f"collision-{index}",
                )
                value = self.manifest_value(root)
                value["resources"].extend(additions)
                value["resources"].sort(key=lambda item: item["bundle_path"])
                self.write_manifest(root, value)
                error = self.assert_validation_code(
                    "resource_path_collision",
                    inspect_bundle,
                    root,
                )
                self.assertEqual(error.details["collision"], collision)

        root = self.copy_bundle(self.bundle, self.parent, "kind")
        value = self.manifest_value(root)
        skill = next(
            item
            for item in value["resources"]
            if item["kind"] == "skill"
        )
        skill["kind"] = "viewer"
        self.write_manifest(root, value)
        self.assert_validation_code("manifest_invalid", inspect_bundle, root)

    def test_rejects_noncanonical_json_self_hash_and_invalid_hash_shape(self) -> None:
        noncanonical = self.copy_bundle(self.bundle, self.parent, "noncanonical")
        value = self.manifest_value(noncanonical)
        (noncanonical / "bundle-manifest.json").write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )
        self.assert_validation_code(
            "manifest_invalid",
            inspect_bundle,
            noncanonical,
        )

        self_hash = self.copy_bundle(self.bundle, self.parent, "self-hash")
        value = self.manifest_value(self_hash)
        record = dict(value["resources"][0])
        record["source_path"] = "bundle-manifest.json"
        record["bundle_path"] = "bundle-manifest.json"
        value["resources"].append(record)
        value["resources"].sort(key=lambda item: item["bundle_path"])
        self.write_manifest(self_hash, value)
        self.assert_validation_code(
            "manifest_invalid",
            inspect_bundle,
            self_hash,
        )

        invalid_hash = self.copy_bundle(self.bundle, self.parent, "invalid-hash")
        value = self.manifest_value(invalid_hash)
        value["resources"][0]["sha256"] = "A" * 64
        self.write_manifest(invalid_hash, value)
        self.assert_validation_code(
            "manifest_invalid",
            inspect_bundle,
            invalid_hash,
        )

    def test_rejects_link_or_non_file_in_installed_bundle(self) -> None:
        target = self.bundle.joinpath(*SKILL_PATH.split("/"))
        original_link_check = bundle_manifest._path_is_link_or_junction

        def mark_target_as_link(path: Path) -> bool:
            return path == target or original_link_check(path)

        with mock.patch.object(
            bundle_manifest,
            "_path_is_link_or_junction",
            side_effect=mark_target_as_link,
        ):
            self.assert_validation_code(
                "resource_path_unsafe",
                inspect_bundle,
                self.bundle,
            )

        class FakeEntry:
            def __init__(self, name: str, data: bytes | None) -> None:
                self.name = name
                self.data = data

            def is_dir(self) -> bool:
                return False

            def is_file(self) -> bool:
                return self.data is not None

            def read_bytes(self) -> bytes:
                assert self.data is not None
                return self.data

        class FakeRoot:
            def __init__(self, manifest_bytes: bytes) -> None:
                self.manifest = FakeEntry("bundle-manifest.json", manifest_bytes)
                self.device = FakeEntry("device", None)

            def joinpath(self, name: str) -> FakeEntry:
                assert name == "bundle-manifest.json"
                return self.manifest

            def iterdir(self) -> list[FakeEntry]:
                return [self.manifest, self.device]

        fake_root = FakeRoot((self.bundle / "bundle-manifest.json").read_bytes())
        self.assert_validation_code(
            "resource_path_unsafe",
            inspect_bundle,
            fake_root,
        )

    def test_installed_resource_primitive_uses_distribution_metadata(self) -> None:
        with (
            mock.patch.object(
                bundle_resources,
                "installed_bundle_root",
                return_value=self.bundle,
            ),
            mock.patch.object(
                bundle_resources,
                "installed_distribution_version",
                return_value="0.1.0",
            ),
        ):
            inspection = bundle_resources.inspect_installed_bundle(
                expected_provenance=EXPECTED_PROVENANCE
            )
        self.assertEqual(inspection.resource_count, 2)
        self.assertRegex(inspection.manifest_sha256, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
