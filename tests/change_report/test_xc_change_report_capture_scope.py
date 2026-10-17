"""Tests for the proportional baseline capture: capture scope, hybrid digest, fail-closed.

The capture used to mirror **every** tracked path's bytes into the workbench, whether or not
version control already held them. The proportional capture mirrors only what version control
cannot reproduce, and this module asserts each half of that change against a real repository and
a real capture run rather than against an argument:

* a clean open state mirrors nothing for tracked paths, and the manifest still reads the snapshot
  `complete` because the commit already holds every tracked byte;
* an untracked-at-open path is still mirrored byte for byte, because those bytes exist nowhere
  else;
* a tracked path that was absent from the worktree at open is recorded as a fact
  (`deleted_paths`) instead of being mirrored or degraded;
* the published digest is still one digest over every tracked path's open bytes and is
  recomputable from the frozen scope **plus the baseline commit** - and V15 refuses it when
  either side is damaged;
* the baseline commit's availability is now a real precondition, so a commit that can no longer
  supply the clean-path bytes is a *named* degradation rather than a silent success;
* a tree with no usable version control fails closed, copies nothing, and copies only under the
  one explicit consent-carrying opt-in.

Standard library only.
"""

from __future__ import annotations
from tests.support.paths import REPO_ROOT  # noqa: E402

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = REPO_ROOT
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
CAPTURE_SCRIPT = SCRIPTS / "capture_baseline.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_manifest as bm  # noqa: E402
import capture_baseline as cb  # noqa: E402
import validate_report as vr  # noqa: E402

WORK_ORDER_ID = "20260915-2215-change-report-full-rollout"
CONSENT = "owner-decision-2026-10-16-no-version-control-capture"


def _git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


class CaptureScopeCase(unittest.TestCase):
    """A scratch repository, a workbench, and the real capture tool."""

    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-scope-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.root = root
        self.repo = root / "repo"
        self.workbench = root / "workbench"

        self.repo.mkdir(parents=True)
        self.workbench.mkdir(parents=True)
        _git(self.repo, "init", "-q")
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "config", "user.email", "probe@example.invalid")
        _git(self.repo, "config", "user.name", "probe")
        _git(self.repo, "config", "core.autocrlf", "false")
        self.write("src/app.py", "def main():\n    return 0\n")
        self.write("src/other.py", "def other():\n    return 1\n")
        self.write("README.md", "# probe\n")
        self.commit = self.commit_all()

    # -- scratch repository ------------------------------------------------------------

    def write(self, relative: str, payload: str | bytes) -> Path:
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload.encode("utf-8") if isinstance(payload, str) else payload)
        return target

    def commit_all(self, message: str = "baseline") -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)
        return _git(self.repo, "rev-parse", "HEAD").decode().strip()

    # -- capture ----------------------------------------------------------------------

    @property
    def record_path(self) -> Path:
        return self.workbench / "tmp" / "baseline-open-state.json"

    @property
    def worktree_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-worktree"

    @property
    def untracked_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-untracked"

    def run_capture(self, *extra: str, repo: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(CAPTURE_SCRIPT),
                "--repo",
                str(repo if repo is not None else self.repo),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                WORK_ORDER_ID,
                *extra,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )

    def capture(self, *extra: str, repo: Path | None = None) -> dict[str, Any]:
        proc = self.run_capture(*extra, repo=repo)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def snapshot_files(self, directory: Path) -> list[str]:
        return sorted(
            item.relative_to(directory).as_posix()
            for item in directory.rglob("*")
            if item.is_file()
        )

    def build_manifest(self, commit: str | None = None) -> dict[str, Any]:
        return bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=commit if commit is not None else self.commit,
            baseline_digest=json.loads(self.record_path.read_text(encoding="utf-8"))[
                "expected_digest"
            ],
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=self.worktree_snapshot,
            baseline_untracked_dir=self.untracked_snapshot,
            tmp_dir=self.workbench / "tmp",
            captured_at="2026-10-16T00:00:00Z",
            generated_at="2026-10-16T01:00:00Z",
            strength="standard",
        )

    def independent_digest(self, payloads: dict[str, bytes]) -> str:
        """C4's digest written here from scratch, over named payloads."""
        records = bytearray()
        for path in sorted(payloads, key=lambda item: item.encode("utf-8")):
            records.extend(path.encode("utf-8"))
            records.extend(b"\x00")
            records.extend(hashlib.sha256(payloads[path]).hexdigest().encode("ascii"))
            records.extend(b"\n")
        return hashlib.sha256(bytes(records)).hexdigest()

    def commit_blob(self, path: str, commit: str | None = None) -> bytes:
        reference = f"{commit if commit is not None else self.commit}:{path}"
        return _git(self.repo, "cat-file", "blob", reference)

    def v15(self, manifest: dict[str, Any]) -> tuple[dict[str, Any], vr.Checker]:
        checker = vr.Checker()
        outcome = vr.check_v15(checker, manifest, self.repo)
        return outcome, checker


# --------------------------------------------------------------------------------------
# The capture scope: mirror only what the commit cannot reproduce
# --------------------------------------------------------------------------------------


class DirtyOnlyMirrorTests(CaptureScopeCase):
    def test_a_clean_repository_mirrors_nothing_for_tracked_paths(self) -> None:
        self.assertEqual(_git(self.repo, "status", "--porcelain"), b"")

        receipt = self.capture()

        self.assertEqual(receipt["tracked_files"], 3)
        self.assertEqual(receipt["copied_files"], 0)
        self.assertEqual(receipt["dirty_paths"], [])
        self.assertEqual(receipt["deleted_paths"], [])
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), [])
        # The digest is still over every tracked path's open bytes, which the commit holds.
        self.assertEqual(
            receipt["expected_digest"],
            self.independent_digest(
                {
                    path: self.commit_blob(path)
                    for path in ("README.md", "src/app.py", "src/other.py")
                }
            ),
        )

        manifest = self.build_manifest()
        documented = manifest["baseline"]["worktree_snapshot"]
        # An empty mirror is complete here: the frozen scope is empty and the commit supplies
        # the rest. That is the state the old "a zero-file capture is unusable" rule would have
        # called a broken capture.
        self.assertEqual(documented["state"], "complete")
        self.assertTrue(documented["available"])
        self.assertEqual(documented["scope"], "proportional")
        self.assertEqual(documented["captured_paths"], 0)
        self.assertEqual(manifest["degradations"], [])

    def test_only_the_dirty_paths_are_mirrored(self) -> None:
        self.write("src/app.py", "def main():\n    return 42\n")
        dirty_bytes = (self.repo / "src" / "app.py").read_bytes()

        receipt = self.capture()

        self.assertEqual(receipt["dirty_paths"], ["src/app.py"])
        self.assertEqual(receipt["copied_files"], 1)
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), ["src/app.py"])
        self.assertEqual((self.worktree_snapshot / "src" / "app.py").read_bytes(), dirty_bytes)
        # The clean paths are neither copied nor forgotten: they are in the digest from the
        # commit, and the count still reports the whole tracked set.
        self.assertEqual(receipt["tracked_files"], 3)
        self.assertEqual(
            receipt["expected_digest"],
            self.independent_digest(
                {
                    "src/app.py": dirty_bytes,
                    "src/other.py": self.commit_blob("src/other.py"),
                    "README.md": self.commit_blob("README.md"),
                }
            ),
        )

        manifest = self.build_manifest()
        documented = manifest["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "complete")
        self.assertEqual(documented["dirty_paths"], ["src/app.py"])
        self.assertEqual(documented["captured_paths"], 1)
        self.assertEqual(manifest["baseline"]["worktree_digest"], receipt["expected_digest"])


class UntrackedAtOpenTests(CaptureScopeCase):
    def test_an_untracked_at_open_file_is_still_mirrored(self) -> None:
        payload = b"\x00\x01untracked bytes that exist nowhere else\xff"
        self.write("assets/logo.bin", payload)

        receipt = self.capture()

        self.assertEqual(receipt["untracked_files"], 1)
        self.assertEqual(receipt["untracked_paths"], ["assets/logo.bin"])
        self.assertEqual(self.snapshot_files(self.untracked_snapshot), ["assets/logo.bin"])
        # Byte for byte, because the commit cannot reproduce these bytes.
        self.assertEqual((self.untracked_snapshot / "assets" / "logo.bin").read_bytes(), payload)
        # ... and the tracked side stays empty on a clean tree.
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), [])


class DeletedAtOpenTests(CaptureScopeCase):
    def test_a_deleted_at_open_path_is_recorded_as_a_fact(self) -> None:
        (self.repo / "README.md").unlink()

        receipt = self.capture()

        self.assertEqual(receipt["deleted_paths"], ["README.md"])
        self.assertEqual(receipt["dirty_paths"], [])
        # Not mirrored, and not degraded: an absent path is a fact, not a snapshot failure.
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), [])
        self.assertEqual(receipt["degradations"], [])
        self.assertNotIn("README.md", receipt["dirty_paths"])

        manifest = self.build_manifest()
        documented = manifest["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "complete")
        self.assertEqual(documented["deleted_paths"], ["README.md"])
        self.assertEqual(manifest["degradations"], [])
        # The path is in the change set as a deletion, which is what the fact is for.
        entries = {entry["path"]: entry for entry in manifest["files"]}
        self.assertIn("README.md", entries)
        self.assertEqual(entries["README.md"]["change_kind"], "deleted")

    def test_the_absent_path_is_omitted_from_the_digest_on_every_side(self) -> None:
        """F1: the digest's input set is one definition, applied by capture, verify and V15.

        The absent path had no bytes at open, so it contributes no record. The repair's
        predecessor hashed it from the baseline commit -- the blob is still there -- in the
        verification mode and in V15 only, so the record the capture wrote failed its own
        `--verify-existing` and the validator, and `files[].baseline_sha256` said the commit's
        content while the published digest had been computed over something else.
        """
        (self.repo / "README.md").unlink()

        receipt = self.capture()

        # The digest the capture published covers exactly the two paths that had open bytes.
        readable = {
            "src/app.py": self.commit_blob("src/app.py"),
            "src/other.py": self.commit_blob("src/other.py"),
        }
        self.assertEqual(receipt["expected_digest"], self.independent_digest(readable))
        # The pre-repair rule provably could not reproduce it: the commit still holds a blob for
        # the absent path, so hashing it there yields a different digest.
        self.assertEqual(self.commit_blob("README.md"), b"# probe\n")
        from_commit = dict(readable)
        from_commit["README.md"] = self.commit_blob("README.md")
        self.assertNotEqual(receipt["expected_digest"], self.independent_digest(from_commit))

        proc = self.run_capture("--verify-existing")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout)["recomputed_digest"], receipt["expected_digest"]
        )

        manifest = self.build_manifest()
        self.assertEqual(manifest["baseline"]["worktree_digest"], receipt["expected_digest"])
        # The manifest publishes the same value for the path's baseline content as the digest
        # used: no bytes, which is the empty hash and never the commit's blob.
        entry = {item["path"]: item for item in manifest["files"]}["README.md"]
        self.assertEqual(
            entry["baseline_sha256"], hashlib.sha256(b"").hexdigest(), entry
        )
        self.assertNotEqual(
            entry["baseline_sha256"], hashlib.sha256(self.commit_blob("README.md")).hexdigest()
        )

        outcome, checker = self.v15(manifest)

        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(outcome["status"], "checked")
        self.assertEqual(outcome["recomputed_digest"], receipt["expected_digest"])
        self.assertEqual(outcome["commit_paths"], 2)


class CheckedOutGitlinkTests(CaptureScopeCase):
    """F2: a tracked path that is present but unopenable is skipped on every side."""

    def add_checked_out_gitlink(self, relative: str = "vendor-sub") -> str:
        """A `160000` gitlink committed into the tree and index, checked out as a directory.

        The directory is created *after* the commit, so the recorded tree really holds a gitlink
        and the worktree path really exists -- the two halves of the measured shape: bytes that
        exist but cannot be read by opening the path.
        """
        source = self.root / "submodule-source"
        source.mkdir()
        _git(source, "init", "-q")
        _git(source, "config", "user.email", "probe@example.invalid")
        _git(source, "config", "user.name", "probe")
        (source / "lib.txt").write_text("submodule content\n", encoding="utf-8")
        _git(source, "add", "-A")
        _git(source, "commit", "-q", "-m", "submodule baseline")
        revision = _git(source, "rev-parse", "HEAD").decode("utf-8").strip()

        _git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{revision},{relative}")
        _git(self.repo, "commit", "-q", "-m", "baseline with a gitlink")
        self.commit = _git(self.repo, "rev-parse", "HEAD").decode("utf-8").strip()
        checkout = self.repo / relative
        checkout.mkdir()
        (checkout / "checked-out.txt").write_text("checked out\n", encoding="utf-8")
        return revision

    def test_a_checked_out_gitlink_is_omitted_from_the_digest_on_every_side(self) -> None:
        self.add_checked_out_gitlink()
        self.assertIsNotNone(self.repo / "vendor-sub")
        self.assertTrue((self.repo / "vendor-sub").is_dir())

        receipt = self.capture()

        # The path exists, so it is not a deletion-at-open; its bytes cannot be read, so it is
        # the named unopenable skip this class is.
        self.assertEqual(receipt["deleted_paths"], [])
        self.assertEqual(receipt["degradations"], ["tracked_path_unreadable:vendor-sub"])
        self.assertTrue(receipt["match"])
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), [])
        self.assertEqual(
            receipt["expected_digest"],
            self.independent_digest(
                {
                    path: self.commit_blob(path)
                    for path in ("README.md", "src/app.py", "src/other.py")
                }
            ),
        )
        # The baseline commit cannot supply this path either: a gitlink's entry is a commit id,
        # so the pre-repair recomputation had no bytes to read and could not reproduce the
        # record the capture wrote.
        self.assertIsNone(bm.git_show_bytes(self.repo, self.commit, "vendor-sub"))

        proc = self.run_capture("--verify-existing")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout)["recomputed_digest"], receipt["expected_digest"]
        )

        manifest = self.build_manifest()
        documented = manifest["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "complete")
        self.assertTrue(documented["available"])
        self.assertEqual(manifest["baseline"]["worktree_digest"], receipt["expected_digest"])
        self.assertIn("tracked_path_unreadable:vendor-sub", manifest["degradations"])

        outcome, checker = self.v15(manifest)

        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(outcome["status"], "checked")
        self.assertEqual(outcome["recomputed_digest"], receipt["expected_digest"])
        self.assertEqual(outcome["commit_paths"], 3)

    def test_a_pre_scope_record_naming_the_unopenable_path_still_verifies(self) -> None:
        """The reachable half of F1's evidence: old records carry only the degradation note.

        A record written before the capture froze its scope says nothing about which paths were
        captured; its only statement about a byte-less path is the `tracked_path_unreadable:`
        note. Such a record must still verify, and the note is what tells the recomputation to
        omit the path instead of reading it from the commit.
        """
        self.add_checked_out_gitlink()
        receipt = self.capture()
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        legacy = {
            key: value
            for key, value in record.items()
            if key not in ("dirty_paths", "deleted_paths")
        }
        self.record_path.write_text(
            json.dumps(legacy, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )

        proc = self.run_capture("--verify-existing")

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout)["recomputed_digest"], receipt["expected_digest"]
        )


# --------------------------------------------------------------------------------------
# The digest: recomputable from the frozen scope plus the commit, and from nothing less
# --------------------------------------------------------------------------------------


class HybridDigestTests(CaptureScopeCase):
    def test_v15_recomputes_the_digest_from_the_scope_plus_the_commit(self) -> None:
        self.write("src/app.py", "def main():\n    return 3\n")
        self.write("notes/open.md", "untracked at open\n")
        receipt = self.capture()
        manifest = self.build_manifest()

        outcome, checker = self.v15(manifest)

        self.assertTrue(checker.ok, checker.errors)
        self.assertEqual(outcome["status"], "checked")
        self.assertEqual(outcome["scope"], "proportional")
        self.assertEqual(outcome["recomputed_digest"], receipt["expected_digest"])
        self.assertEqual(outcome["snapshot_paths"], 1)
        self.assertEqual(outcome["commit_paths"], 2)

    def test_v15_fails_when_the_snapshot_loses_a_scoped_path(self) -> None:
        self.write("src/app.py", "def main():\n    return 4\n")
        self.capture()
        manifest = self.build_manifest()

        (self.worktree_snapshot / "src" / "app.py").unlink()

        _, checker = self.v15(manifest)

        # The scope says the snapshot holds this path, so its absence is damage that V15 names,
        # and the digest no longer covers the bytes the record published.
        self.assertFalse(checker.ok)
        self.assertIn("incomplete", checker.errors[0]["message"])
        self.assertNotIn("src/app.py", self.snapshot_files(self.worktree_snapshot))

    def test_v15_fails_when_the_snapshot_bytes_change(self) -> None:
        self.write("src/app.py", "def main():\n    return 5\n")
        self.capture()
        manifest = self.build_manifest()

        victim = self.worktree_snapshot / "src" / "app.py"
        victim.write_bytes(victim.read_bytes() + b"# tampered\n")

        outcome, checker = self.v15(manifest)

        self.assertFalse(checker.ok)
        self.assertIn("not reproducible", checker.errors[0]["message"])

    def test_verify_existing_accepts_the_record_it_wrote_after_an_edit(self) -> None:
        self.write("src/app.py", "def main():\n    return 6\n")
        receipt = self.capture()
        # The work order then edits the clean path; the recorded open state must still verify.
        self.write("src/other.py", "def other():\n    return 9\n")

        proc = self.run_capture("--verify-existing")

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout)["recomputed_digest"], receipt["expected_digest"]
        )

    def test_v1_requires_content_only_when_the_scope_declares_it(self) -> None:
        """The empty-snapshot rule, re-aimed at the published scope.

        A zero-file capture must not be able to claim it produced files; but a clean open state
        legitimately produces none, so the requirement is the scope's own `captured_paths` and
        not the tracked set the snapshot no longer mirrors.
        """
        self.capture()
        manifest = self.build_manifest()
        snapshot = manifest["baseline"]["worktree_snapshot"]

        self.assertEqual(snapshot["captured_paths"], 0)
        checker = vr.Checker()
        vr.check_v1(checker, manifest, WORK_ORDER_ID)
        self.assertFalse(
            [item for item in checker.errors if "holds no captured path" in item["message"]],
            checker.errors,
        )

        # The same empty directory with a scope that says one path belongs in it must fail.
        snapshot["captured_paths"] = 1
        strict = vr.Checker()
        vr.check_v1(strict, manifest, WORK_ORDER_ID)
        self.assertTrue(
            any("holds no captured path" in item["message"] for item in strict.errors),
            strict.errors,
        )


# --------------------------------------------------------------------------------------
# The commit is now a source, so its unavailability is a named degradation
# --------------------------------------------------------------------------------------


class CommitUnavailableTests(CaptureScopeCase):
    def test_an_unresolvable_commit_fails_the_manifest_closed(self) -> None:
        """R3: the whole clean-path half is gone, so the manifest refuses to be built.

        A baseline commit that no longer resolves leaves no tracked set: `units_total` would be
        a fabricated zero, `run_required` a fabricated `false`, and the package's own zero-unit
        rule would turn that into the legal `zero_analyzable_units` skip -- a work order whose
        code changed closing with no report and no failing check. The manifest therefore stops
        here and names the cause, instead of publishing a decision from an enumeration that
        never happened. The other half of the class stays a *named degradation*: a commit that
        resolves but can no longer supply one clean path's blob is the case below.
        """
        self.write("src/app.py", "def main():\n    return 7\n")
        self.capture()

        with self.assertRaises(bm.ManifestError) as raised:
            self.build_manifest("0" * 40)

        message = str(raised.exception)
        self.assertIn(bm.BASELINE_SNAPSHOT_COMMIT_UNAVAILABLE, message)
        self.assertIn("0" * 40, message)

    def test_v15_fails_when_the_commit_can_no_longer_supply_a_clean_path(self) -> None:
        """The measured failure: the commit id stopped resolving after a history rewrite.

        The proportional snapshot deliberately did not copy a clean path's bytes, so the commit
        is the only place they exist. V15 must fail and must name that cause: a note that the
        snapshot is merely "unavailable" would read as a degraded-but-complete proof.
        """
        self.write("src/app.py", "def main():\n    return 8\n")
        self.capture()
        manifest = self.build_manifest()

        # The rewrite: the recorded commit id no longer resolves, while the snapshot and the
        # worktree are untouched. `git cat-file blob` on a missing object is the reader's path.
        manifest["baseline"]["commit"] = "0" * 40

        _, checker = self.v15(manifest)

        self.assertFalse(checker.ok)
        self.assertTrue(
            any(
                "baseline_worktree_snapshot_commit_unavailable" in item["message"]
                for item in checker.errors
            ),
            checker.errors,
        )


class LegacyScopeCountTests(CaptureScopeCase):
    """R4: the published count is the count the record actually holds.

    An unpruned record -- the shape every capture written before the proportional change has --
    publishes `scope: full` and froze no `dirty_paths` list, so the count cannot come from that
    list. It must come from the mirror, which is the thing the count describes: publishing the
    tracked set of `baseline.commit` there reads as zero whenever that commit cannot be
    enumerated, while the mirror holds the whole tracked set.
    """

    def legacy_record(self) -> dict[str, Any]:
        """An unpruned record whose mirror holds every tracked path: the pre-change shape."""
        tracked = sorted(
            bm.tracked_paths(self.repo, self.commit), key=lambda item: item.encode("utf-8")
        )
        # The pre-change capture mirrored every tracked path and froze no scope. Rebuild exactly
        # that mirror from the commit, so the fixture is the old shape and not a damaged new one.
        for path in tracked:
            target = self.worktree_snapshot / Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.commit_blob(path))
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), tracked)

        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        for field in ("dirty_paths", "deleted_paths"):
            record.pop(field, None)
        record["copied_files"] = len(tracked)
        self.record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    def test_an_unpruned_record_publishes_the_count_its_mirror_holds(self) -> None:
        self.write("src/app.py", "def main():\n    return 9\n")
        self.capture()
        record = self.legacy_record()
        mirrored = self.snapshot_files(self.worktree_snapshot)

        manifest = self.build_manifest()
        snapshot = manifest["baseline"]["worktree_snapshot"]

        self.assertEqual(snapshot["scope"], "full")
        self.assertEqual(snapshot["captured_paths"], len(mirrored))
        self.assertEqual(snapshot["captured_paths"], record["copied_files"])
        self.assertGreater(snapshot["captured_paths"], 0, "the mirror holds the recorded set")

        # The same record read through a directory that holds nothing publishes zero, because
        # zero is then the truth about the mirror rather than a count taken from a commit.
        elsewhere = self.root / "empty-mirror"
        elsewhere.mkdir()
        empty = bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=self.commit,
            baseline_digest=record["expected_digest"],
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=elsewhere,
            baseline_untracked_dir=self.untracked_snapshot,
            tmp_dir=self.workbench / "tmp",
            captured_at="2026-10-16T00:00:00Z",
            generated_at="2026-10-16T01:00:00Z",
            strength="standard",
        )
        self.assertEqual(empty["baseline"]["worktree_snapshot"]["captured_paths"], 0)
        self.assertEqual(empty["baseline"]["worktree_snapshot"]["state"], "empty")


# --------------------------------------------------------------------------------------
# R1/R2: a clean path is read by object id, not through a worktree spelling
# --------------------------------------------------------------------------------------


class LongPathCleanReadTests(CaptureScopeCase):
    """A `commit:path` spell past the host path limit must not defeat the capture.

    `git show <commit>:<path>` resolves its argument as a *worktree* spelling, so on a checkout
    whose combined repository + object name + relative path length crosses the host's path limit
    the read fails on a path whose bytes the object database holds intact -- and because the
    capture's own digest self-check used that reader, the whole capture aborted before writing
    any record, which is what made a work order in such a repository impossible to open. The
    fixture computes its own lengths; a hard-coded length would be a host-dependent test.

    The limit's *existence* is host-specific, so the premise that crosses it is asserted only on a
    host that enforces it (`test_the_worktree_spelling_reader_fails_past_the_limit`, guarded by the
    repository's `skipUnless(os.name == "nt", ...)` convention for host-specific contracts). The
    fixture's geometry and the digest equality the long path produces run on every host.
    """

    # The Windows path limit this fixture has to cross, and enough room under it for the
    # directory *and* the file to remain readable by `open` and by `git cat-file blob`.
    HOST_PATH_LIMIT = 260

    def long_path_fixture(self) -> tuple[str, int, int]:
        """A tracked path whose worktree read succeeds and whose `commit:path` spell is long."""
        blob = self.commit_blob("README.md", self.commit)
        # `git show <commit>:<path>` takes a *worktree* spelling and stats it as
        # `<worktree>/<path>`; the object-database read never sees the path at all. So the
        # spelling to push past the limit is the worktree spelling, and the same path is what
        # the worktree read has to keep under it. Both margins are measured on the limit, never
        # on a constant that a different host or a different temp root would invalidate.
        worktree_room = self.HOST_PATH_LIMIT - 40 - len(str(self.repo))
        relative_length = max(12, worktree_room)
        segment_count = max(4, (relative_length - len("leaf.txt")) // 2)
        relative = "/".join(["d"] * segment_count + ["leaf.txt"])
        self.write(relative, blob)
        self.commit = self.commit_all("long path")

        absolute = len(str(self.repo / relative))
        spelling = len(str(self.repo)) + 1 + 40 + 1 + len(relative)
        self.assertLess(absolute, self.HOST_PATH_LIMIT, "the worktree path must stay readable")
        self.assertGreater(
            spelling, self.HOST_PATH_LIMIT, "the `commit:path` spell must cross the host limit"
        )
        # The geometry is host-independent, and so is this positive control: the object database
        # returns the path's bytes by object id on every host. Whether the host path limit
        # *defeats the worktree spelling* is the host-dependent half, asserted by the guarded test
        # below instead of here.
        self.assertEqual(bm.blob_bytes(self.repo, self.object_id(relative)), blob)
        return relative, absolute, spelling

    @unittest.skipUnless(
        os.name == "nt", "the host path limit this premise depends on is a Windows contract"
    )
    def test_the_worktree_spelling_reader_fails_past_the_limit(self) -> None:
        """The host-dependent half of the premise, measured rather than assumed.

        A host whose path limit is long enough resolves the same spelling and returns the blob,
        so only a host that enforces the limit can assert that `git show <commit>:<path>` is
        defeated while the object database still holds the bytes. The digest equality in
        `test_the_capture_records_a_clean_long_path_by_object_id` is the half that runs
        everywhere, so a non-Windows runner skips this premise rather than failing it.
        """
        relative, absolute, spelling = self.long_path_fixture()

        self.assertLess(absolute, self.HOST_PATH_LIMIT)
        self.assertGreater(spelling, self.HOST_PATH_LIMIT)
        self.assertIsNone(
            bm.git_show_bytes(self.repo, self.commit, relative),
            "`git show <commit>:<path>` must be defeated by the host path limit on this path",
        )

    def object_id(self, relative: str) -> str:
        listing = _git(self.repo, "ls-tree", "-r", "-z", self.commit).decode("utf-8", "replace")
        for record in listing.split("\x00"):
            meta, _, raw_path = record.partition("\t")
            if raw_path == relative:
                return meta.split(" ")[2]
        raise AssertionError(f"{relative} is not in the tree of {self.commit}")

    def test_the_capture_records_a_clean_long_path_by_object_id(self) -> None:
        relative, _, _ = self.long_path_fixture()

        receipt = self.capture()

        self.assertEqual(receipt["tracked_files"], 4)
        self.assertEqual(receipt["copied_files"], 0, "a clean path is never mirrored")
        self.assertEqual(receipt["dirty_paths"], [])
        self.assertEqual(receipt["deleted_paths"], [])
        self.assertTrue(receipt["match"])
        self.assertTrue(self.record_path.is_file(), "the capture writes its record")
        self.assertEqual(
            self.commit_blob(relative),
            (self.repo / relative).read_bytes(),
            "the fixture's path really is clean",
        )

        # The three later recomputations of the same four bytes: this is the R1 equality.
        verified = self.run_capture("--verify-existing")
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual(
            json.loads(verified.stdout)["recomputed_digest"], receipt["expected_digest"]
        )

        manifest = self.build_manifest()
        self.assertEqual(manifest["baseline"]["worktree_digest"], receipt["expected_digest"])
        self.assertEqual(manifest["baseline"]["worktree_snapshot"]["state"], "complete")

        outcome, checker = self.v15(manifest)
        self.assertEqual(checker.errors, [])
        self.assertEqual(outcome["status"], "checked")
        self.assertEqual(outcome["recomputed_digest"], receipt["expected_digest"])
        self.assertGreaterEqual(outcome["commit_paths"], 1)


# --------------------------------------------------------------------------------------
# No usable version control: fail closed, and the one consent-carrying opt-in
# --------------------------------------------------------------------------------------


class VcsUnavailableTests(CaptureScopeCase):
    def plain_directory(self) -> Path:
        directory = self.root / "not-a-repository"
        directory.mkdir()
        (directory / "src").mkdir()
        (directory / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")
        return directory

    def unborn_head_repository(self) -> Path:
        """A git worktree whose `HEAD` does not resolve: version control exists, uselessly."""
        directory = self.root / "unborn-head"
        directory.mkdir()
        _git(directory, "init", "-q")
        (directory / "src").mkdir()
        (directory / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")
        return directory

    def test_no_version_control_fails_closed_and_copies_nothing(self) -> None:
        outside = self.plain_directory()

        proc = self.run_capture(repo=outside)

        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn(cb.VCS_UNAVAILABLE, payload["error"])
        self.assertFalse(self.record_path.exists(), "a fail-closed run writes no record")
        self.assertFalse(self.worktree_snapshot.exists(), "a fail-closed run mirrors nothing")
        self.assertFalse(self.untracked_snapshot.exists())

    def test_an_unresolvable_head_raises_the_same_named_error(self) -> None:
        """F3: the named error covers the class the contract promises, not only its first member.

        Five contract surfaces promise `baseline_vcs_unavailable` for version control that
        cannot supply the baseline side. An unborn `HEAD` is that class, and the pre-repair code
        raised a generic `git command failed` instead.
        """
        unborn = self.unborn_head_repository()

        proc = self.run_capture(repo=unborn)

        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        # The named error leads the message and carries the underlying git reason, which is what
        # a fail-closed report has to name. The pre-repair code raised the bare `git command
        # failed` text here and never consulted the consent opt-in.
        self.assertTrue(payload["error"].startswith(cb.VCS_UNAVAILABLE), payload["error"])
        self.assertIn("rev-parse HEAD", payload["error"])
        self.assertFalse(self.record_path.exists())
        self.assertFalse(self.worktree_snapshot.exists())

        # ... and the one authorisation applies on that path too: without a reference nothing is
        # copied, with one the whole tree is mirrored and the record carries the reference.
        without = self.run_capture("--full-tracked-mirror", repo=unborn)
        self.assertNotEqual(without.returncode, 0, without.stdout)
        self.assertIn(cb.VCS_UNAVAILABLE, json.loads(without.stdout)["error"])

        consented = self.capture(
            "--full-tracked-mirror", "--consent-reference", CONSENT, repo=unborn
        )
        self.assertEqual(consented["head"], "")
        self.assertEqual(consented["copied_files"], 1)
        self.assertEqual(consented["consent_reference"], CONSENT)
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), ["src/app.py"])
        # The `.git` store is not worktree content and is not mirrored.
        self.assertNotIn(".git", self.snapshot_files(self.worktree_snapshot))

        # F4: the record the consent path wrote is verifiable by the package's own verification
        # mode, which consults no version control when the record holds no commit.
        verified = self.run_capture("--verify-existing", repo=unborn)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual(
            json.loads(verified.stdout)["recomputed_digest"], consented["expected_digest"]
        )

    def test_the_opt_in_requires_a_non_empty_consent_reference(self) -> None:
        outside = self.plain_directory()

        without = self.run_capture("--full-tracked-mirror", repo=outside)
        self.assertNotEqual(without.returncode, 0, without.stdout)
        self.assertIn(cb.VCS_UNAVAILABLE, json.loads(without.stdout)["error"])
        self.assertFalse(self.record_path.exists())

        blank = self.run_capture(
            "--full-tracked-mirror", "--consent-reference", "   ", repo=outside
        )
        self.assertNotEqual(blank.returncode, 0, blank.stdout)
        self.assertIn(cb.VCS_UNAVAILABLE, json.loads(blank.stdout)["error"])
        self.assertFalse(self.record_path.exists())

    def test_the_opt_in_with_a_reference_mirrors_the_whole_tree_and_records_it(self) -> None:
        outside = self.plain_directory()
        (outside / "notes.md").write_text("not tracked by anything\n", encoding="utf-8")

        receipt = self.capture(
            "--full-tracked-mirror", "--consent-reference", CONSENT, repo=outside
        )

        self.assertEqual(receipt["tracked_files"], 2)
        self.assertEqual(receipt["copied_files"], 2)
        self.assertEqual(receipt["head"], "")
        self.assertEqual(receipt["consent_reference"], CONSENT)
        self.assertEqual(
            self.snapshot_files(self.worktree_snapshot), ["notes.md", "src/app.py"]
        )
        # The consent travels into the record, so a reviewer reads what authorised the copy.
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["consent_reference"], CONSENT)
        # The `.git` store is not worktree content and is not mirrored.
        self.assertNotIn(".git", self.snapshot_files(self.worktree_snapshot))

        # F4: the same record is consumable by `--verify-existing`. The report pipeline's
        # manifest build is the honest limit -- it enumerates a change set against a baseline
        # commit, which this tree does not have -- and C4c states it.
        verified = self.run_capture("--verify-existing", repo=outside)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual(
            json.loads(verified.stdout)["recomputed_digest"], receipt["expected_digest"]
        )


if __name__ == "__main__":
    unittest.main()
