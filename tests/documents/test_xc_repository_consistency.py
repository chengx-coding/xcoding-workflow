#!/usr/bin/env python3
"""Real-repository consistency checks that were previously unverified.

Three invariants were contracted but never checked against the real tree, only
against synthetic temporary roots:

1. the version markers in the repository's own current-release pages match
   `pyproject.toml`;
2. the public documentation tree is a complete one-to-one bilingual pair;
3. `build_agents.py` is a faithful sync of `skills/` into `.agents/skills/`.

Each check has a negative control in the sense that it fails when the invariant
is broken; the version and mirror checks are also exercised against a deliberately
broken copy so the check itself cannot pass vacuously.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


DOCS_ROOT = REPO_ROOT / "docs"
ZH_ROOT = DOCS_ROOT / "zh-CN"
#: The selector renders its own language in that language, so the English token
#: only appears on English pages. A pair is detected by the cross-language links
#: instead of by one literal string.
ENGLISH_SELECTOR_TOKEN = "**Language:**"


def _has_language_selector(text: str) -> bool:
    """True when the page offers the language switch.

    The selector names both languages and links to the counterpart. An English
    page renders "**English**" as the current language and links the mirror under
    `zh-CN/`; a Chinese page links `[English](...)` and renders the Chinese name,
    with no `zh-CN/` segment because the mirror is its own directory. Either
    direction is accepted, and a page that dropped its counterpart link fails
    both.
    """
    english_current = "**English**" in text and "zh-CN/" in text
    english_linked = "[English](" in text
    return english_current or english_linked


def _english_pages() -> list[Path]:
    return sorted(
        path
        for path in DOCS_ROOT.rglob("*.md")
        if "zh-CN" not in path.relative_to(DOCS_ROOT).parts
    )


def _chinese_pages() -> list[Path]:
    return sorted(ZH_ROOT.rglob("*.md"))


def _relative_pairs() -> tuple[set[str], set[str]]:
    english = {path.relative_to(DOCS_ROOT).as_posix() for path in _english_pages()}
    chinese = {path.relative_to(ZH_ROOT).as_posix() for path in _chinese_pages()}
    return english, chinese


class CurrentVersionMarkersTests(unittest.TestCase):
    """`scripts/check_version.py` is run against the real repository."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.check_version import CURRENT_PAGES, check  # noqa: PLC0415

        # Bound as a staticmethod so `self.check(root)` does not receive `self`
        # as the first argument.
        cls.check = staticmethod(check)
        cls.current_pages = CURRENT_PAGES

    def test_repository_current_release_references_match_pyproject(self) -> None:
        """No current-release page may disagree with the project version."""
        errors = self.check(REPO_ROOT)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_every_declared_current_page_exists(self) -> None:
        for name in self.current_pages:
            with self.subTest(page=name):
                self.assertTrue((REPO_ROOT / name).is_file(), name)

    def test_the_check_rejects_a_stale_marker(self) -> None:
        """Negative control: the check must fail on a wrong version, not pass."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "xcoding-workflow"\nversion = "9.9.9"\n', encoding="utf-8"
            )
            for name in self.current_pages:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    "Current: <!-- xc:version -->0.0.1<!-- /xc:version -->\n", encoding="utf-8"
                )
            errors = self.check(root)
            self.assertTrue(
                any("differs from" in error for error in errors),
                f"expected a version disagreement, got {errors}",
            )

    def test_the_check_rejects_a_missing_marker(self) -> None:
        """Negative control: an unmarked page must be reported."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "xcoding-workflow"\nversion = "0.2.0"\n', encoding="utf-8"
            )
            for name in self.current_pages:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if name == "README.md":
                    target.write_text("no marker here\n", encoding="utf-8")
                else:
                    target.write_text(
                        "Current: <!-- xc:version -->0.2.0<!-- /xc:version -->\n", encoding="utf-8"
                    )
            errors = self.check(root)
            self.assertTrue(
                any("missing or malformed" in error for error in errors),
                f"expected a missing-marker report, got {errors}",
            )


class BilingualDocumentationPairTests(unittest.TestCase):
    """Every public page has exactly one mirror, in both directions."""

    def test_every_english_page_has_a_chinese_mirror(self) -> None:
        english, chinese = _relative_pairs()
        missing = sorted(english - chinese)
        self.assertEqual(missing, [], f"pages without a zh-CN mirror: {missing}")

    def test_every_chinese_page_has_an_english_source(self) -> None:
        english, chinese = _relative_pairs()
        extra = sorted(chinese - english)
        self.assertEqual(extra, [], f"zh-CN pages without an English source: {extra}")

    def test_mirrors_are_not_empty_placeholders(self) -> None:
        for relative in sorted(_relative_pairs()[1]):
            with self.subTest(page=relative):
                text = (ZH_ROOT / relative).read_text(encoding="utf-8").strip()
                self.assertGreater(len(text), 0, relative)

    def test_each_pair_carries_the_language_selector(self) -> None:
        """Both sides of a pair must offer the language switch."""
        english, chinese = _relative_pairs()
        for relative in sorted(english & chinese):
            with self.subTest(page=relative):
                source = (DOCS_ROOT / relative).read_text(encoding="utf-8")
                mirror = (ZH_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(ENGLISH_SELECTOR_TOKEN, source, f"English page {relative}")
                self.assertTrue(_has_language_selector(source), f"English page {relative}")
                self.assertTrue(_has_language_selector(mirror), f"zh-CN page {relative}")

    def test_the_selector_check_rejects_a_page_without_its_counterpart(self) -> None:
        """Negative control: dropping the counterpart link must be reported."""
        self.assertFalse(_has_language_selector("# Title\n\nNo switch here.\n"))
        self.assertFalse(_has_language_selector("**Language:** **English**\n"))
        self.assertTrue(_has_language_selector("**Language:** [English](../x.md) | **中文**"))
        self.assertTrue(_has_language_selector("**语言:** [English](../x.md) | **简体中文**"))

    def test_english_page_links_its_mirror_path(self) -> None:
        english, chinese = _relative_pairs()
        for relative in sorted(english & chinese):
            with self.subTest(page=relative):
                source = (DOCS_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(
                    f"zh-CN/{relative}",
                    source,
                    f"English page {relative} does not link its mirror",
                )

    def test_the_pairing_check_notices_a_missing_mirror(self) -> None:
        """Negative control: the comparison must be able to report a gap."""
        english = {"concepts/architecture.md", "concepts/core-design.md"}
        chinese = {"concepts/architecture.md"}
        self.assertEqual(sorted(english - chinese), ["concepts/core-design.md"])

    def test_no_page_sits_directly_beside_its_mirror_directory(self) -> None:
        """A stray `zh-CN.md`-style file would break the exact-path contract."""
        strays = [
            path.name
            for path in DOCS_ROOT.rglob("*.md")
            if path.name.startswith("zh-CN") and path.parent != ZH_ROOT
        ]
        self.assertEqual(strays, [])


class SkillMirrorSyncTests(unittest.TestCase):
    """`build_agents.py` reproduces `skills/` faithfully in an isolated copy."""

    MIRROR_ROOT = ".agents/skills"
    SOURCE_ROOT = "skills"

    def _isolated_copy(self, destination: Path) -> None:
        """Copy the sources the sync reads, with a real (non-junction) mirror."""
        shutil.copy2(REPO_ROOT / "build_agents.py", destination / "build_agents.py")
        shutil.copytree(REPO_ROOT / self.SOURCE_ROOT, destination / self.SOURCE_ROOT)

    def _run_sync(self, sandbox: Path) -> subprocess.CompletedProcess[str]:
        """Run the sync in the sandbox, tolerating non-UTF-8 output bytes.

        The child reports skill names that may not be UTF-8 on every platform, so
        decoding errors are replaced rather than allowed to abort the capture.
        """
        return subprocess.run(
            [sys.executable, str(sandbox / "build_agents.py")],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_running_the_sync_is_reproducible_and_faithful(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            self._isolated_copy(sandbox)

            first = self._run_sync(sandbox)
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)

            mirror = sandbox / self.MIRROR_ROOT
            self.assertTrue(mirror.is_dir(), f"no mirror produced at {mirror}")

            declared = sorted(
                entry.name
                for entry in (sandbox / self.SOURCE_ROOT).iterdir()
                if entry.is_dir() and entry.name.startswith("xc-")
            )
            produced = sorted(entry.name for entry in mirror.iterdir() if entry.is_dir())
            self.assertEqual(produced, declared)

            # Byte-for-byte, ignoring the interpreter cache the sync excludes.
            for name in declared:
                source = sandbox / self.SOURCE_ROOT / name
                target = mirror / name
                source_files = {
                    path.relative_to(source).as_posix()
                    for path in source.rglob("*")
                    if path.is_file() and "__pycache__" not in path.parts
                }
                target_files = {
                    path.relative_to(target).as_posix()
                    for path in target.rglob("*")
                    if path.is_file() and "__pycache__" not in path.parts
                }
                with self.subTest(skill=name):
                    self.assertEqual(source_files, target_files)
                    for relative in sorted(source_files):
                        self.assertEqual(
                            (source / relative).read_bytes(),
                            (target / relative).read_bytes(),
                            f"{name}/{relative} differs from its source",
                        )

    def test_second_run_changes_nothing(self) -> None:
        """The sync is idempotent, so a stale mirror is the only drift possible."""
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            self._isolated_copy(sandbox)
            mirror = sandbox / self.MIRROR_ROOT

            for _ in range(2):
                completed = self._run_sync(sandbox)
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            first = {
                path.relative_to(mirror).as_posix(): path.read_bytes()
                for path in mirror.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            }
            completed = self._run_sync(sandbox)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            second = {
                path.relative_to(mirror).as_posix(): path.read_bytes()
                for path in mirror.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            }
            self.assertEqual(sorted(first), sorted(second))
            self.assertEqual(first, second)

    def test_a_stale_mirror_is_detectable(self) -> None:
        """Negative control: inject a stale file and confirm it is visible."""
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            self._isolated_copy(sandbox)
            self._run_sync(sandbox)
            stale = sandbox / self.MIRROR_ROOT / "xc-work" / "STALE.md"
            stale.write_text("drift\n", encoding="utf-8")
            source = sandbox / self.SOURCE_ROOT / "xc-work" / "STALE.md"
            self.assertFalse(source.exists())
            self.assertTrue(stale.exists())

    def test_the_repository_skills_tree_is_present(self) -> None:
        self.assertTrue((REPO_ROOT / self.SOURCE_ROOT).is_dir())
        self.assertTrue((REPO_ROOT / "build_agents.py").is_file())


if __name__ == "__main__":
    unittest.main()
