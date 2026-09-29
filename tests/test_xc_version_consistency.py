from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_support.version import parse_project_version, validate_version
from scripts.check_version import CURRENT_PAGES, check, main


class VersionConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "xcoding-workflow"\nversion = "0.7.3"\n', encoding="utf-8")
        for name in CURRENT_PAGES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Current: <!-- xc:version -->0.7.3<!-- /xc:version -->\n"
                              "xcoding_workflow-0.7.3-py3-none-any.whl\n", encoding="utf-8")

    def test_future_release_and_unmarked_history(self) -> None:
        (self.root / "historical.md").write_text("0.1.0 xcoding_workflow-0.1.0-py3-none-any.whl", encoding="utf-8")
        self.assertEqual(check(self.root), [])

    def test_missing_malformed_stale_and_invalid_markers(self) -> None:
        target = self.root / CURRENT_PAGES[0]
        for content in ("No marker", "<!-- xc:version -->0.7.3", "<!-- /xc:version -->",
                        "<!-- xc:version -->0.7.2<!-- /xc:version -->",
                        "<!-- xc:version -->00.7.3<!-- /xc:version -->",
                        "<!-- xc:version -->0.7.3<!-- /xc:version --><!-- xc:version -->"):
            with self.subTest(content=content):
                target.write_text(content, encoding="utf-8")
                self.assertTrue(check(self.root))
        target.unlink()
        self.assertTrue(check(self.root))

    def test_stale_current_wheel(self) -> None:
        target = self.root / CURRENT_PAGES[0]
        target.write_text(target.read_text().replace("xcoding_workflow-0.7.3", "xcoding_workflow-0.1.0"), encoding="utf-8")
        self.assertTrue(check(self.root))

    def test_explicit_release_inputs(self) -> None:
        notes = self.root / "notes.md"
        notes.write_text("## 0.7.3\nRelease notes\n", encoding="utf-8")
        self.assertEqual(check(self.root, tag="v0.7.3", release_notes=(notes,)), [])
        self.assertTrue(check(self.root, tag="v0.7.2"))
        notes.write_text("## 0.7.30\n", encoding="utf-8")
        self.assertTrue(check(self.root, release_notes=(notes,)))

    def test_each_supplied_release_notes_file_is_checked(self) -> None:
        first, second = self.root / "en.md", self.root / "zh.md"
        first.write_text("## 0.7.3\n", encoding="utf-8")
        second.write_text("## 0.7.2\n", encoding="utf-8")
        self.assertTrue(check(self.root, release_notes=(first, second)))
        second.write_text("## 0.7.3\n", encoding="utf-8")
        self.assertEqual(main(["--project-root", str(self.root), "--release-notes", str(first), "--release-notes", str(second)]), 0)

    def test_inspection_rejects_invalid_trusted_version_before_opening_wheel(self) -> None:
        from scripts.verify_wheel import inspect_wheel, VerificationError
        with self.assertRaises(VerificationError) as raised:
            inspect_wheel(self.root / "absent.whl", expected_version="../1.2.3",
                          expected_tag="py3-none-any", baseline_revision="a" * 40,
                          candidate_tree_sha256="b" * 64,
                          candidate_source_archive_sha256="c" * 64)
        self.assertEqual(raised.exception.code, "metadata_invalid")

    def test_bundle_build_rejects_noncanonical_version(self) -> None:
        from build_support.bundle import BundleBuildError, load_project_metadata
        target = self.root / "pyproject.toml"
        target.write_text('[project]\nversion="1.2.3rc1"\nrequires-python=">=3.12"\n', encoding="utf-8")
        with self.assertRaises(BundleBuildError):
            load_project_metadata(self.root)

    def test_invalid_project_versions_fail_closed(self) -> None:
        for version in (None, 1, "", "1.2", "01.2.3", "1.2.3rc1", "1.2.3\n", "../1.2.3"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_version(version)
        for data in (b"bad toml", b"[project]", b'project="bad"', b'[project]\nname="other"\nversion="1.2.3"'):
            with self.subTest(data=data), self.assertRaises((ValueError, KeyError)):
                parse_project_version(data)
        (self.root / "pyproject.toml").write_text("bad toml", encoding="utf-8")
        self.assertEqual(main(["--project-root", str(self.root)]), 1)
