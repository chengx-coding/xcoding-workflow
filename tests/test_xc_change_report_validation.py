"""Focused tests for the `xc-change-report` validator's baseline and enumeration proofs.

This file is the acceptance test for one implementation unit: the validator's V1 content and
consistency tiers, the new V15 baseline-digest recomputation, the new V16 enumeration
completeness check, the `MAX_WRONG` ceiling, the V11 message bound, and the validator's half of
the refresh-pass bound.

Every assertion here is written against the *correct* behaviour, so each test fails against the
pre-change validator and passes after the change. The positive controls inside each test exist to
prove the check is not simply rejecting everything.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
FLOW_SPEC = SKILL_ROOT / "assets" / "change-report-flow.json"
TEMPLATE = SKILL_ROOT / "assets" / "change-report-template.xml"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_manifest as bm  # noqa: E402
import build_skeleton as bs  # noqa: E402
import validate_report as vr  # noqa: E402


WORK_ORDER_ID = "20260915-2215-change-report-full-rollout"
# The degenerate shape the gap register measured: one 240 001-character single line, which the
# pre-change V11 reported in a 120 144-character failure message.
DEGENERATE_LINE_CHARS = 240001


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if proc.returncode not in (0, 1):
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace")


def _init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "config", "core.autocrlf", "false")
    return repo


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def c4_from_pairs(pairs: Iterable[tuple[str, str]]) -> str:
    """The C4 construction, written from the protocol rather than called from the package.

    V15 must reproduce a digest the package computes with `digest_from_hashes`; an independent
    construction here is what keeps the test from agreeing with a wrong implementation twice.
    """
    payload = bytearray()
    for path, digest in sorted(pairs, key=lambda item: item[0].encode("utf-8")):
        payload.extend(path.encode("utf-8"))
        payload.extend(b"\x00")
        payload.extend(digest.encode("ascii"))
        payload.extend(b"\n")
    return hashlib.sha256(bytes(payload)).hexdigest()


def base_manifest(
    commit: str = "0" * 40,
    worktree_snapshot: dict[str, Any] | None = None,
    untracked_snapshot: dict[str, Any] | None = None,
    degradations: list[str] | None = None,
) -> dict[str, Any]:
    """A minimal V1-clean manifest: no files, two snapshots that are unavailable-and-explained."""
    if worktree_snapshot is None:
        worktree_snapshot = {
            "path": "",
            "available": False,
            "state": "absent",
            "algorithm": bm.DIGEST_ALGORITHM,
        }
    if untracked_snapshot is None:
        untracked_snapshot = {
            "path": "",
            "files": 0,
            "algorithm": bm.SOURCE_HASH_ALGORITHM,
            "available": False,
        }
    if degradations is None:
        degradations = [
            "baseline_worktree_snapshot_missing",
            "baseline_untracked_snapshot_missing",
        ]
    return {
        "schema_version": bm.SCHEMA_VERSION,
        "enumeration": {"version": bm.ENUMERATION_VERSION},
        "work_order_id": WORK_ORDER_ID,
        "baseline": {
            "kind": "work-order-open-snapshot",
            "commit": commit,
            "worktree_digest": "a" * 64,
            "algorithm": bm.DIGEST_ALGORITHM,
            "captured_at": "2026-09-15T16:13:18Z",
            "worktree_snapshot": worktree_snapshot,
            "untracked_snapshot": untracked_snapshot,
        },
        "head": {"kind": "worktree", "digest": "b" * 64, "algorithm": bm.DIGEST_ALGORITHM},
        "files": [],
        "units_total": 0,
        "excluded_total": 0,
        "pre_existing_total": 0,
        "degradations": list(degradations),
    }


def error_ids(checker: vr.Checker) -> set[str]:
    return {error["id"] for error in checker.errors}


def messages_for(checker: vr.Checker, check: str) -> list[str]:
    return [error["message"] for error in checker.errors if error["id"] == check]


def index_page(markup: str) -> vr.HtmlIndex:
    index = vr.HtmlIndex(markup)
    index.feed(markup)
    index.close()
    index.close_open()
    return index


class ScratchRoot(unittest.TestCase):
    """A temporary directory outside the repository, removed on teardown."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="xc-report-u3-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)


# --------------------------------------------------------------------------------------
# G-03, the V1 content and consistency tiers
# --------------------------------------------------------------------------------------


class BaselineIdentityTests(unittest.TestCase):
    def check(self, manifest: dict[str, Any]) -> vr.Checker:
        checker = vr.Checker()
        vr.check_v1(checker, manifest, WORK_ORDER_ID)
        return checker

    def test_v1_rejects_an_empty_or_wrong_baseline_identity(self) -> None:
        """The A3-1 content tier: key presence is not identity."""
        # Control first: the tier must accept the shape it is meant to accept, otherwise every
        # assertion below would pass for the wrong reason.
        self.assertTrue(self.check(base_manifest()).ok, "the control manifest must be V1-clean")

        cases: dict[str, dict[str, Any]] = {}

        empty_digest = base_manifest()
        empty_digest["baseline"]["worktree_digest"] = ""
        cases["empty-worktree-digest"] = empty_digest

        # The measured corruption: the shipped string with the closing parenthesis removed.
        wrong_algorithm = base_manifest()
        wrong_algorithm["baseline"]["algorithm"] = "sha256(path-nul-contenthash-lf/v1"
        cases["wrong-algorithm"] = wrong_algorithm

        empty_captured_at = base_manifest()
        empty_captured_at["baseline"]["captured_at"] = "   "
        cases["empty-captured-at"] = empty_captured_at

        missing_snapshot = base_manifest()
        del missing_snapshot["baseline"]["worktree_snapshot"]
        cases["missing-worktree-snapshot"] = missing_snapshot

        snapshot_not_an_object = base_manifest()
        snapshot_not_an_object["baseline"]["worktree_snapshot"] = "tmp/baseline-worktree"
        cases["worktree-snapshot-not-an-object"] = snapshot_not_an_object

        for name, manifest in cases.items():
            with self.subTest(name=name):
                checker = self.check(manifest)
                self.assertFalse(checker.ok, f"{name} must fail V1")
                self.assertEqual(error_ids(checker), {"V1"}, name)

    def test_v1_rejects_an_inconsistent_snapshot_availability(self) -> None:
        """The A3-2 consistency tier: `available` and `degradations` must tell one story."""
        root = Path(tempfile.mkdtemp(prefix="xc-report-u3-v1-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        empty_dir = root / "empty"
        empty_dir.mkdir()
        populated_dir = root / "populated"
        populated_dir.mkdir()
        (populated_dir / "a.py").write_text("a = 1\n", encoding="utf-8")

        unexplained_unavailable = base_manifest(
            worktree_snapshot={"path": "", "available": False, "state": "empty"},
            degradations=["baseline_untracked_snapshot_missing"],
        )
        available_but_absent = base_manifest(
            worktree_snapshot={"path": "", "available": True, "state": "absent"},
        )
        available_with_empty_directory = base_manifest(
            worktree_snapshot={
                "path": str(empty_dir),
                "available": True,
                "state": "complete",
            },
        )
        unknown_state = base_manifest(
            worktree_snapshot={"path": "", "available": False, "state": "partial"},
        )
        undocumented_untracked = base_manifest(
            untracked_snapshot={"path": str(empty_dir), "files": 0, "available": False},
            degradations=["baseline_worktree_snapshot_missing"],
        )
        for name, manifest in {
            "unexplained-unavailable": unexplained_unavailable,
            "available-but-absent": available_but_absent,
            "available-with-empty-directory": available_with_empty_directory,
            "unknown-state": unknown_state,
            "unavailable-untracked-without-degradation": undocumented_untracked,
        }.items():
            with self.subTest(name=name):
                checker = self.check(manifest)
                self.assertFalse(checker.ok, f"{name} must fail V1")
                self.assertEqual(error_ids(checker), {"V1"}, name)

        # Control: an available, populated worktree snapshot and an untracked snapshot that is
        # legitimately empty (a clean tree at open) are both correct.
        acceptable = base_manifest(
            worktree_snapshot={
                "path": str(populated_dir),
                "available": True,
                "state": "complete",
            },
            untracked_snapshot={"path": str(empty_dir), "files": 0, "available": True},
            degradations=[],
        )
        self.assertTrue(self.check(acceptable).ok, "an available populated snapshot must pass V1")


# --------------------------------------------------------------------------------------
# G-03, V15: the baseline digest recomputed from the recorded snapshot
# --------------------------------------------------------------------------------------


class BaselineDigestTests(ScratchRoot):
    TRACKED = ("alpha.py", "beta.py")

    def setUp(self) -> None:
        super().setUp()
        self.repo = _init_repo(self.root)
        for name in self.TRACKED:
            (self.repo / name).write_text(f"{name} = 1\n", encoding="utf-8")
        self.commit = _commit(self.repo, "baseline")
        self.snapshot = self.root / "baseline-worktree"
        self.snapshot.mkdir()
        for name in self.TRACKED:
            shutil.copy2(self.repo / name, self.snapshot / name)
        self.declared = self.c4()
        self.untracked = self.root / "baseline-untracked"
        self.untracked.mkdir()

    def c4(self) -> str:
        return c4_from_pairs(
            (name, hashlib.sha256((self.snapshot / name).read_bytes()).hexdigest())
            for name in self.TRACKED
        )

    def manifest(
        self,
        *,
        available: bool,
        state: str,
        path: str,
        digest: str,
        degradations: list[str],
    ) -> dict[str, Any]:
        manifest = base_manifest(
            commit=self.commit,
            worktree_snapshot={
                "path": path,
                "available": available,
                "state": state,
                "algorithm": bm.DIGEST_ALGORITHM,
            },
            untracked_snapshot={
                "path": str(self.untracked),
                "files": 0,
                "algorithm": bm.SOURCE_HASH_ALGORITHM,
                "available": True,
            },
            degradations=degradations,
        )
        manifest["baseline"]["worktree_digest"] = digest
        return manifest

    def healthy(self) -> dict[str, Any]:
        return self.manifest(
            available=True,
            state="complete",
            path=str(self.snapshot),
            digest=self.declared,
            degradations=[],
        )

    def test_v15_recomputes_the_baseline_digest_from_the_snapshot(self) -> None:
        # Control: the recorded digest really is C4 over the tracked path list, and V15 accepts it.
        self.assertEqual(
            self.declared,
            bm.digest_from_hashes(
                [(name, bm.sha256_hex((self.snapshot / name).read_bytes())) for name in self.TRACKED]
            ),
            "the independent C4 construction must agree with the package's",
        )
        healthy = self.healthy()
        checker = vr.Checker()
        vr.check_v1(checker, healthy, WORK_ORDER_ID)
        status = vr.check_v15(checker, healthy, self.repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["status"], "checked")
        self.assertEqual(status["recomputed_digest"], self.declared)

        # One tracked path's snapshot bytes are mutated: the declared identity no longer describes
        # the recorded bytes, so the check must fail rather than trust the manifest.
        (self.snapshot / "beta.py").write_text("beta = 999\n", encoding="utf-8")
        checker = vr.Checker()
        status = vr.check_v15(checker, healthy, self.repo)
        self.assertFalse(checker.ok, "a mutated snapshot must fail V15")
        self.assertEqual(error_ids(checker), {"V15"})
        self.assertIn("not reproducible", messages_for(checker, "V15")[0])

        # A tracked path with no captured file is an incomplete snapshot, not a digest mismatch.
        (self.snapshot / "beta.py").unlink()
        checker = vr.Checker()
        vr.check_v15(checker, healthy, self.repo)
        self.assertFalse(checker.ok)
        self.assertEqual(error_ids(checker), {"V15"})
        self.assertIn("incomplete", messages_for(checker, "V15")[0])
        self.assertIn("beta.py", messages_for(checker, "V15")[0])

        # An unavailable snapshot is the C4a "not recomputable" case: the manifest already carries
        # the degradation, and V15 adds a note instead of failing the work order.
        absent = self.manifest(
            available=False,
            state="absent",
            path="",
            digest=self.declared,
            degradations=["baseline_worktree_snapshot_missing"],
        )
        checker = vr.Checker()
        vr.check_v1(checker, absent, WORK_ORDER_ID)
        status = vr.check_v15(checker, absent, self.repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["status"], "not_recomputable")
        self.assertEqual(status["reason"], vr.BASELINE_NOT_RECOMPUTABLE)
        self.assertEqual(status["degradation"], "baseline_worktree_snapshot_missing")


# --------------------------------------------------------------------------------------
# G-30, V16: the enumeration recomputed from git
# --------------------------------------------------------------------------------------


class EnumerationCompletenessTests(ScratchRoot):
    def setUp(self) -> None:
        super().setUp()
        self.repo = _init_repo(self.root)
        (self.repo / "a.py").write_text("a = 1\n", encoding="utf-8")
        (self.repo / "b.py").write_text("b = 1\n", encoding="utf-8")
        (self.repo / "c.txt").write_text("c\n", encoding="utf-8")
        self.commit = _commit(self.repo, "baseline")
        (self.repo / "b.py").write_text("b = 2\n", encoding="utf-8")

    def manifest(self, paths: Iterable[str]) -> dict[str, Any]:
        manifest = base_manifest(commit=self.commit)
        manifest["files"] = [{"path": path} for path in paths]
        return manifest

    def test_v16_detects_a_dropped_path(self) -> None:
        """A path the repository reports but `files[]` omits is a silent omission."""
        complete = self.manifest(["a.py", "b.py", "c.txt"])
        checker = vr.Checker()
        status = vr.check_v16(checker, complete, self.repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["status"], "checked")
        self.assertEqual(status["missing"], [])

        dropped = self.manifest(["a.py", "c.txt"])
        checker = vr.Checker()
        vr.check_v16(checker, dropped, self.repo)
        self.assertFalse(checker.ok, "a dropped path must fail V16")
        self.assertEqual(error_ids(checker), {"V16"})
        message = messages_for(checker, "V16")[0]
        self.assertIn("b.py", message)
        self.assertIn(f"git diff --no-renames --name-status -z {self.commit} --", message)

        # The second source: an index entry whose mode a byte diff of the worktree cannot see.
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=str(self.repo),
            input=b"target\n",
            capture_output=True,
        )
        self.assertEqual(blob.returncode, 0, blob.stderr.decode("utf-8", "replace"))
        sha = blob.stdout.decode("ascii").strip()
        _git(self.repo, "update-index", "--add", "--cacheinfo", f"120000,{sha},link.txt")
        checker = vr.Checker()
        status = vr.check_v16(checker, dropped, self.repo)
        self.assertFalse(checker.ok, "a mode-120000 index entry must fail V16")
        self.assertEqual(status["index_modes"], 1)
        link_messages = [item for item in messages_for(checker, "V16") if "link.txt" in item]
        self.assertTrue(link_messages, messages_for(checker, "V16"))
        self.assertIn("git ls-files -s", link_messages[0])
        # The standard modes stay out of the index source: `a.py` is comparably unchanged and the
        # check must not demand a row for every tracked file in the repository.
        self.assertNotIn("a.py", [item for item in status["missing"]])
        self.assertNotIn("c.txt", [item for item in status["missing"]])

    def test_v16_accepts_a_paired_rename_as_an_enumerated_path(self) -> None:
        """C11 pairs an exact-content rename into one entry; its deletion side is enumerated."""
        rename_repo = _init_repo(self.root / "rename-case")
        (rename_repo / "keep.txt").write_text("keep\n", encoding="utf-8")
        (rename_repo / "old_name.py").write_text("payload\n", encoding="utf-8")
        rename_commit = _commit(rename_repo, "baseline")
        (rename_repo / "old_name.py").unlink()
        (rename_repo / "new_name.py").write_text("payload\n", encoding="utf-8")

        # `git ls-files -s` still lists the stale index entry until it is refreshed, so refresh the
        # index the way the enumeration's own diff does before the check runs.
        _git(rename_repo, "add", "-A")
        manifest = base_manifest(commit=rename_commit)
        manifest["files"] = [
            {"path": "new_name.py", "change_kind": "renamed", "renamed_from": "old_name.py"}
        ]
        checker = vr.Checker()
        status = vr.check_v16(checker, manifest, rename_repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["missing"], [])

        # The pair is not a blanket exemption: an entry that names neither side still fails.
        dropped = base_manifest(commit=rename_commit)
        dropped["files"] = [{"path": "keep.txt"}]
        checker = vr.Checker()
        vr.check_v16(checker, dropped, rename_repo)
        self.assertFalse(checker.ok)
        self.assertTrue(
            any("old_name.py" in item for item in messages_for(checker, "V16")),
            messages_for(checker, "V16"),
        )

    def test_v16_ignores_a_link_the_baseline_already_holds_untouched(self) -> None:
        """The index source is a source of *change*: an untouched link owes no `files[]` row.

        The measured defect: the index source required every index entry whose mode is neither
        `100644` nor `100755` with no change test, so a repository whose baseline commit already
        carries a mode-`120000` entry that the work order never retargets was reported as having
        dropped a path from a manifest that was complete. The manifest in this case is the whole
        change set — one ordinary tracked file — and the link appears in neither the commit-to-head
        diff nor the manifest, because nothing about it changed.
        """
        repo = _init_repo(self.root / "link-case")
        # A host without symbolic links (and every Windows host by default) represents a
        # `120000` index entry as a regular file holding the target text. Pinning the setting
        # makes the "untouched" shape below identical on every host instead of depending on
        # whether this one can create real symlinks.
        _git(repo, "config", "core.symlinks", "false")
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_bytes(b"value = 1\n")
        # A real symlink's content is its target text and carries no trailing newline; Windows
        # text mode would translate "\n" to os.linesep and make git report the worktree file as
        # modified, which is not the shape under test.
        (repo / "stable-link.txt").write_bytes(b"target.txt")
        _git(repo, "add", "-A")
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=str(repo),
            input=b"target.txt",
            capture_output=True,
        )
        self.assertEqual(blob.returncode, 0, blob.stderr.decode("utf-8", "replace"))
        _git(
            repo,
            "update-index",
            "--cacheinfo",
            f"120000,{blob.stdout.decode('ascii').strip()},stable-link.txt",
        )
        # Commit without re-staging: `git add -A` would put the regular file back as mode 100644.
        _git(repo, "commit", "-q", "-m", "baseline")
        commit = _git(repo, "rev-parse", "HEAD").strip()

        # The fixture is the measured shape only when the link really is untouched.
        self.assertEqual(_git(repo, "status", "--porcelain"), "")
        self.assertIn(
            f"120000 {blob.stdout.decode('ascii').strip()} 0\tstable-link.txt",
            _git(repo, "ls-files", "-s"),
        )

        (repo / "src" / "app.py").write_bytes(b"value = 2\n")
        # ... and the commit-to-head diff, the check's first source, does not name it either.
        self.assertEqual(
            _git(repo, "diff", "--no-renames", "--name-status", commit, "--"),
            "M\tsrc/app.py\n",
        )

        manifest = base_manifest(commit=commit)
        manifest["files"] = [{"path": "src/app.py", "change_kind": "modified"}]
        checker = vr.Checker()
        status = vr.check_v16(checker, manifest, repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["missing"], [])
        self.assertEqual(status["diff_paths"], 1)
        # The entry is counted rather than silently ignored, so a receipt still shows it.
        self.assertEqual(status["index_modes"], 0)
        self.assertEqual(status["unchanged_index_modes"], 1)

        # Non-vacuity, both directions. A link the work order really adds is still a shape change.
        added = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=str(repo),
            input=b"other-target",
            capture_output=True,
        )
        self.assertEqual(added.returncode, 0, added.stderr.decode("utf-8", "replace"))
        _git(
            repo,
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{added.stdout.decode('ascii').strip()},new-link.txt",
        )
        checker = vr.Checker()
        status = vr.check_v16(checker, manifest, repo)
        self.assertFalse(checker.ok, "an added link must still fail V16")
        self.assertEqual(error_ids(checker), {"V16"})
        self.assertEqual(status["missing"], ["new-link.txt"])
        self.assertEqual(status["index_modes"], 1)
        self.assertIn("git ls-files -s", messages_for(checker, "V16")[0])

        # ... and the diff source is untouched by the narrowing.
        dropped = base_manifest(commit=commit)
        dropped["files"] = []
        checker = vr.Checker()
        vr.check_v16(checker, dropped, repo)
        self.assertFalse(checker.ok, "a dropped changed path must still fail V16")
        self.assertTrue(
            any("src/app.py" in item for item in messages_for(checker, "V16")),
            messages_for(checker, "V16"),
        )


# --------------------------------------------------------------------------------------
# F1: V16 reconciles the untracked source as well as the two index/commit relations
# --------------------------------------------------------------------------------------


class UntrackedSourceTests(ScratchRoot):
    """A path `git ls-files --others` reports may leave `files[]` only when it is named."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = _init_repo(self.root)
        (self.repo / "a.py").write_text("a = 1\n", encoding="utf-8")
        self.commit = _commit(self.repo, "baseline")
        # Untracked at manifest time: the third enumeration step's own output.
        (self.repo / "src").mkdir()
        (self.repo / "src" / "scratch.py").write_text("scratch = 1\n", encoding="utf-8")

    def manifest(self, files: list[dict[str, Any]], degradations: list[str]) -> dict[str, Any]:
        manifest = base_manifest(commit=self.commit, degradations=degradations)
        manifest["files"] = files
        return manifest

    def test_v16_reconciles_the_untracked_source(self) -> None:
        """The untracked half of the enumeration is recomputed, so an F1 drop cannot pass.

        Before this check the validator's two sources were both index/commit relations, so a
        path the untracked enumeration reports and the manifest drops -- the measured F1
        shape -- left the run `ok=true` with `coverage=complete`.
        """
        dropped = self.manifest([{"path": "a.py"}], ["baseline_untracked_snapshot_missing"])
        checker = vr.Checker()
        status = vr.check_v16(checker, dropped, self.repo)
        self.assertFalse(checker.ok, "a dropped untracked path must fail V16")
        self.assertEqual(error_ids(checker), {"V16"})
        message = messages_for(checker, "V16")[0]
        self.assertIn("src/scratch.py", message)
        self.assertIn("git ls-files --others --exclude-standard -z", message)
        self.assertEqual(status["missing"], ["src/scratch.py"])
        self.assertEqual(status["untracked_paths"], 1)

        # Control: the same repository with the path enumerated passes.
        complete = self.manifest(
            [{"path": "a.py"}, {"path": "src/scratch.py", "change_kind": "added"}],
            ["baseline_untracked_snapshot_missing"],
        )
        checker = vr.Checker()
        status = vr.check_v16(checker, complete, self.repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["missing"], [])

        # The measured F1 shape: the path reaches the manifest through git's lossy spelling
        # and cannot be opened, so it is recorded as a degradation that names it instead of a
        # row. Naming it is what keeps the omission out of the silent class.
        recorded = self.manifest(
            [{"path": "a.py"}],
            ["baseline_untracked_snapshot_missing", "path_unreadable:src/scratch.py"],
        )
        checker = vr.Checker()
        status = vr.check_v16(checker, recorded, self.repo)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(status["missing"], [])
        self.assertEqual(status["recorded_unreadable"], ["src/scratch.py"])

        # ... and the note must name *this* path: a degradation about another path is still a
        # silent drop for the one that left the enumeration.
        unrelated = self.manifest(
            [{"path": "a.py"}],
            ["baseline_untracked_snapshot_missing", "path_unreadable:src/other.py"],
        )
        checker = vr.Checker()
        vr.check_v16(checker, unrelated, self.repo)
        self.assertFalse(checker.ok)
        self.assertEqual(error_ids(checker), {"V16"})


# --------------------------------------------------------------------------------------
# G-31, the accuracy ceiling
# --------------------------------------------------------------------------------------


class AccuracyCeilingTests(ScratchRoot):
    MANIFEST: dict[str, Any] = {
        "files": [{"path": "a.py", "hunks": [{"unit_index": 1, "excluded": False}]}]
    }

    def verdicts(self, name: str, verdict: str) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": bm.SCHEMA_VERSION,
                    "verdicts": [{"unit_index": 1, "verdict": verdict, "reason": "probe"}],
                }
            ),
            encoding="utf-8",
        )
        return path

    def check(self, verdicts: Path, accuracy: str) -> vr.Checker:
        checker = vr.Checker()
        vr.check_v14(checker, deepcopy(self.MANIFEST), verdicts, accuracy)
        return checker

    def test_max_wrong_is_a_ceiling(self) -> None:
        """`MAX_WRONG` is a maximum: fewer wrong verdicts than the ceiling is inside it."""
        accurate = self.verdicts("accurate", "accurate")
        wrong = self.verdicts("wrong", "wrong")

        # The shipped value: one wrong verdict is above the ceiling of zero.
        self.assertFalse(self.check(wrong, "true").ok)

        # A calibrated ceiling of one: zero wrong verdicts is inside it, and the pre-change `!=`
        # rejected exactly this case.
        with mock.patch.object(vr, "MAX_WRONG", 1):
            inside = self.check(accurate, "false")
            self.assertTrue(inside.ok, inside.errors)
            # ... and the ceiling still bites above itself, so the fix is not a disabling.
            above = self.check(wrong, "true")
            self.assertFalse(above.ok)
            self.assertEqual(error_ids(above), {"V14"})


# --------------------------------------------------------------------------------------
# G-41, the bounded V11 failure text
# --------------------------------------------------------------------------------------


class BoundedFailureTextTests(ScratchRoot):
    def test_v11_failure_message_is_bounded(self) -> None:
        """A 240 001-character single-line unit must not produce a 120 144-character message."""
        repo = _init_repo(self.root)
        target = repo / "degenerate.py"
        target.write_text("value = 0\n", encoding="utf-8")
        commit = _commit(repo, "baseline")

        snapshot = self.root / "baseline-worktree"
        snapshot.mkdir()
        shutil.copy2(target, snapshot / "degenerate.py")
        untracked = self.root / "baseline-untracked"
        untracked.mkdir()

        target.write_text("x" * DEGENERATE_LINE_CHARS + "\n", encoding="utf-8")
        manifest = bm.build_manifest(
            repo_path=repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=commit,
            baseline_digest=bm.digest_from_hashes(
                [("degenerate.py", bm.sha256_hex((snapshot / "degenerate.py").read_bytes()))]
            ),
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=snapshot,
            baseline_untracked_dir=untracked,
            tmp_dir=self.root / "tmp",
            captured_at="2026-09-15T16:13:18Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )
        units = [
            hunk for entry in manifest["files"] for hunk in entry["hunks"] if not hunk["excluded"]
        ]
        self.assertEqual(len(units), 1, f"the degenerate file must yield one unit: {manifest['files']}")
        unit_index = units[0]["unit_index"]

        # A page whose unit section carries no analysis text shares no token with the diff, which
        # is the shape that produced the oversized message.
        page = f"<html><body><section id=\"unit-{unit_index}\"></section></body></html>"
        checker = vr.Checker()
        bound = vr.check_v11(checker, index_page(page), manifest, repo)
        self.assertEqual(bound, 0)
        self.assertEqual(error_ids(checker), {"V11"})
        message = messages_for(checker, "V11")[0]
        # The defect is that the message grew with the evidence it quotes. This assertion fails
        # against the pre-change validator on its own, before the cap is even read.
        self.assertLess(
            len(message),
            DEGENERATE_LINE_CHARS,
            "the failure text must be bounded by a cap, not by the size of the unit",
        )
        self.assertLessEqual(len(message), vr.MAX_CHECK_MESSAGE_CHARS, len(message))
        self.assertIn(f"unit {unit_index}", message)
        self.assertIn("shares no token", message)
        self.assertIn("truncated", message)
        # The declared cap is what bounds it, not an accident of this fixture.
        self.assertGreater(DEGENERATE_LINE_CHARS, vr.MAX_CHECK_MESSAGE_CHARS)


# --------------------------------------------------------------------------------------
# G-33, the validator's half of the refresh-pass bound
# --------------------------------------------------------------------------------------


class PassBoundTests(ScratchRoot):
    LOOPS = ("report-pass-loop", "report-review-loop")

    def declared_bounds(self, spec: dict[str, Any]) -> dict[str, str]:
        found: dict[str, str] = {}
        stack = [spec.get("root", {})]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            template_id = str(node.get("template_id", ""))
            if template_id in self.LOOPS:
                found[template_id] = str(node.get("loop.max_iterations", ""))
            for value in node.values():
                if isinstance(value, dict):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(item for item in value if isinstance(item, dict))
        return found

    def test_pass_bound_agrees_across_spec_template_and_validator(self) -> None:
        """The spec, the generated template and V12's literal must state one bound.

        Regression-only, and labelled as such: the solution decision classifies this half of G-33
        as coverage of an untested path, not as a defect proof, because the three artefacts
        already agree. It is what makes a later divergence land as a failure instead of silence.
        """
        spec = json.loads(FLOW_SPEC.read_text(encoding="utf-8"))
        bounds = self.declared_bounds(spec)
        self.assertEqual(set(bounds), set(self.LOOPS), bounds)
        for template_id, bound in bounds.items():
            with self.subTest(template_id=template_id):
                self.assertEqual(bound, "3")

        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(template.count('loop.max_iterations="3"'), len(self.LOOPS))

        # V12's own expectation is the literal 3, not a value read back from the artefact under
        # test: a spec that declares 4 must be rejected, and the message must state the literal.
        for template_id in self.LOOPS:
            with self.subTest(divergent=template_id):
                divergent = deepcopy(spec)
                stack = [divergent.get("root", {})]
                while stack:
                    node = stack.pop()
                    if not isinstance(node, dict):
                        continue
                    if str(node.get("template_id", "")) == template_id:
                        node["loop.max_iterations"] = "4"
                    stack.extend(
                        value for value in node.values() if isinstance(value, dict)
                    )
                    stack.extend(
                        item
                        for value in node.values()
                        if isinstance(value, list)
                        for item in value
                        if isinstance(item, dict)
                    )
                path = self.root / f"{template_id}.json"
                path.write_text(json.dumps(divergent), encoding="utf-8")
                checker = vr.Checker()
                vr.check_v12(checker, path)
                self.assertFalse(checker.ok, f"{template_id} with a bound of 4 must fail V12")
                self.assertTrue(
                    any("loop.max_iterations=3" in item for item in messages_for(checker, "V12")),
                    messages_for(checker, "V12"),
                )


# --------------------------------------------------------------------------------------
# G-43, V5: the unsubstituted-placeholder rule is scoped to the page's own text
# --------------------------------------------------------------------------------------


class PlaceholderScopeTests(ScratchRoot):
    """A placeholder-shaped literal a unit *quotes* is content; a real leftover token still fails.

    The measured defect: V5 searched the whole assembled page for `{{NAME}}`, so a change set that
    quotes such a literal in its own source - a message template, an f-string, a JSON sample - was
    rejected as carrying an unsubstituted placeholder, while the builder accepted the very same
    page. Two rules about one page disagreed, in the direction of rejecting a correct report. The
    rule now reuses V7's H37a element-interval exclusion, so a token in the page's own text is
    still found and a code block cannot be used to hide one.
    """

    BASELINE = 'GREETING = "hello"\n'
    HEAD = 'GREETING = "hello {{USER_NAME}}"\nFOOTER = "bye"\n'
    QUOTED = "{{USER_NAME}}"

    def setUp(self) -> None:
        super().setUp()
        self.repo = _init_repo(self.root)
        source = self.repo / "src" / "messages.py"
        source.parent.mkdir()
        source.write_bytes(self.BASELINE.encode("utf-8"))
        self.commit = _commit(self.repo, "baseline")

        self.snapshot = self.root / "baseline-worktree"
        (self.snapshot / "src").mkdir(parents=True)
        (self.snapshot / "src" / "messages.py").write_bytes(self.BASELINE.encode("utf-8"))
        self.untracked = self.root / "baseline-untracked"
        self.untracked.mkdir()

        source.write_bytes(self.HEAD.encode("utf-8"))

        self.manifest = bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=self.commit,
            baseline_digest=bm.digest_from_hashes(
                [
                    (
                        "src/messages.py",
                        bm.sha256_hex((self.snapshot / "src" / "messages.py").read_bytes()),
                    )
                ]
            ),
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=self.snapshot,
            baseline_untracked_dir=self.untracked,
            tmp_dir=self.root / "tmp",
            captured_at="2026-09-15T17:45:00Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )
        self.manifest_path = self.root / "change-report-manifest.json"
        self.manifest_path.write_bytes(
            (json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )

        # The page is the shipped builder's own output for this change set, produced by the CLI
        # entry point, so the two rules are compared over one real page rather than two fixtures.
        self.page_path = self.root / "change-report.html"
        self.build_exit = bs.main(
            [
                "--repo",
                str(self.repo),
                "--manifest",
                str(self.manifest_path),
                "--out",
                str(self.page_path),
                "--generated-at",
                "2026-09-15T18:00:00Z",
                "--tmp-dir",
                str(self.root / "tmp"),
            ]
        )
        self.page = self.page_path.read_text(encoding="utf-8")

    def check_v5(self, page: str) -> vr.Checker:
        checker = vr.Checker()
        vr.check_v5(checker, index_page(page), self.manifest, self.manifest_path.read_bytes())
        return checker

    def test_v5_ignores_a_placeholder_shaped_literal_inside_a_code_block(self) -> None:
        # Control first: the builder really does accept this change set, and the literal really is
        # quoted source, so the assertion below is about a page worth accepting.
        self.assertEqual(self.build_exit, 0, "the builder must accept a quoted placeholder literal")
        self.assertEqual(self.page.count(self.QUOTED), 1, self.page.count(self.QUOTED))
        blocks = re.findall(r'<pre class="report-code"[^>]*>.*?</pre>', self.page, re.S)
        self.assertEqual(
            sum(block.count(self.QUOTED) for block in blocks),
            1,
            "the literal must be inside the unit's code block, or this proves nothing",
        )

        checker = self.check_v5(self.page)
        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(vr.unsubstituted_placeholders(index_page(self.page)), [])

        # Non-vacuity: a genuine unsubstituted placeholder in the page's own text still fails, and
        # the failure names the token. This is the shape the rule exists for - a template token the
        # substitution loop never resolved.
        leftover = self.page.replace("</body>", "<p>{{UNITS_TTILE}}</p></body>", 1)
        self.assertNotEqual(leftover, self.page, "the page must have a closing body tag")
        checker = self.check_v5(leftover)
        self.assertFalse(checker.ok, "a leftover token outside a code block must still fail V5")
        self.assertEqual(error_ids(checker), {"V5"})
        self.assertIn("{{UNITS_TTILE}}", messages_for(checker, "V5")[0])
        self.assertEqual(
            vr.unsubstituted_placeholders(index_page(leftover)), ["{{UNITS_TTILE}}"]
        )

    def test_an_unclosed_code_block_cannot_hide_a_leftover_token(self) -> None:
        """Fail-closed: the exemption is an interval an element really owns (H37a).

        The exclusion V7 already uses bounds an unclosed element at its first structural boundary.
        Without that bound, a page whose code block was never closed would exempt everything after
        it, and the narrowed rule could then be used to hide a genuine leftover token.
        """
        unclosed = (
            '<html><body><pre class="report-code"><code>{{QUOTED}}</code>'
            "<p>{{LEFTOVER}}</p></body></html>"
        )
        index = index_page(unclosed)
        intervals = vr.exclusion_intervals(index)
        self.assertEqual(len(intervals), 1, intervals)
        start, end = intervals[0]
        self.assertLess(start, unclosed.index("{{QUOTED}}"), "the block's own text is exempt")
        self.assertLess(
            end,
            unclosed.index("{{LEFTOVER}}"),
            "an unclosed code block must not exempt the rest of the page",
        )
        self.assertEqual(vr.unsubstituted_placeholders(index), ["{{LEFTOVER}}"])


if __name__ == "__main__":
    unittest.main()
