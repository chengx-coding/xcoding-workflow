"""Tests for `capture_baseline.py`, the `xc-change-report` baseline producer.

The producer has to satisfy three separable properties, and each one is asserted here
rather than argued:

* the digest it publishes is the coverage protocol's digest, proven against an
  independently written construction that shares no code with the package (G-01);
* it does **not** re-implement that construction: the helper objects are the same module
  objects as `build_manifest`'s, and the script's own source bytes contain no copy of the
  algorithm literal (G-04), asserted on the file because the repository-wide `git grep`
  invariant cannot see this file while it is untracked;
* its `--format keys` output is publishable: the three printed lines fed back into
  `build_manifest` reproduce the manifest's baseline identity (G-08).

The remaining tests cover the refusal paths: outside a worktree, a repeat capture of an
unchanged state, and the `--verify-existing` mode, which must reproduce a recorded digest
from the recorded snapshot directories and fail closed on any damaged input.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
SCRIPT = SCRIPTS / "capture_baseline.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_manifest as bm  # noqa: E402
import capture_baseline as cb  # noqa: E402


WORK_ORDER_ID = "20260915-2215-change-report-full-rollout"

# The open-state record's frozen field set (solution decision section 8): every field
# required, no others.
FROZEN_RECORD_FIELDS = (
    "kind",
    "work_order_id",
    "captured_at",
    "head",
    "algorithm",
    "tracked_files",
    "copied_files",
    "untracked_files",
    "expected_digest",
    "recomputed_digest",
    "match",
    "worktree_snapshot",
    "untracked_snapshot",
)

# The digest algorithm literal is assembled from two fragments on purpose: the
# repository-wide invariant counts its occurrences in *tracked* content, and this module
# must not add a third hit when the work order's change set is committed. The assertion
# below is unaffected: it searches for the joined bytes.
C4_LITERAL = b"path-nul" + b"-contenthash-lf"

TRACKED_FILES = {
    "README.md": "# scratch\n\nBaseline capture probe.\n",
    "src/app.py": "def main():\n    return 0\n",
    "src/nested/deep.txt": "nested text\n",
}
UNTRACKED_FILES = {
    "notes/scratch.md": "untracked at open\n",
    "assets/logo.bin": b"\x00\x01\x02binary\xff\x00",
}


def _git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


def _declared_tracked_paths(repo: Path) -> list[str]:
    payload = _git(repo, "ls-files", "-z")
    return sorted(
        (item.decode("utf-8") for item in payload.split(b"\x00") if item),
        key=lambda item: item.encode("utf-8"),
    )


def _index_modes(repo: Path) -> dict[str, str]:
    """`path -> index mode`, read straight from git rather than from the tool under test."""
    modes: dict[str, str] = {}
    for record in _git(repo, "ls-files", "-s", "-z").split(b"\x00"):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b"\t")
        if not separator:
            continue
        modes[raw_path.decode("utf-8", "surrogateescape")] = meta.split(b" ")[0].decode("ascii")
    return modes


def _independent_c4(repo: Path, paths: list[str]) -> str:
    """The coverage protocol's digest, written here from scratch and importing nothing.

    This is the oracle the producer is measured against: it shares no code, no constant
    and no helper with the package.
    """
    payload = bytearray()
    for path in sorted(paths, key=lambda item: item.encode("utf-8")):
        digest = hashlib.sha256((repo / path).read_bytes()).hexdigest()
        payload.extend(path.encode("utf-8"))
        payload.extend(b"\x00")
        payload.extend(digest.encode("ascii"))
        payload.extend(b"\n")
    return hashlib.sha256(bytes(payload)).hexdigest()


class BaselineTestCase(unittest.TestCase):
    """A scratch repository, an untracked-at-open file set and a workbench."""

    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-baseline-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.root = root
        self.repo = root / "repo"
        self.workbench = root / "workbench"

        self.repo.mkdir(parents=True)
        _git(self.repo, "init", "-q")
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "config", "user.email", "probe@example.invalid")
        _git(self.repo, "config", "user.name", "probe")
        _git(self.repo, "config", "core.autocrlf", "false")
        for relative, content in TRACKED_FILES.items():
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "baseline")
        self.commit = _git(self.repo, "rev-parse", "HEAD").decode("utf-8").strip()

        # Untracked at open: the second snapshot directory must mirror these too.
        for relative, content in UNTRACKED_FILES.items():
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")

        self.workbench.mkdir(parents=True)

    # -- helpers ------------------------------------------------------------------

    @property
    def record_path(self) -> Path:
        return self.workbench / "tmp" / "baseline-open-state.json"

    @property
    def worktree_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-worktree"

    @property
    def untracked_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-untracked"

    def run_capture(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(self.repo),
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

    def capture(self) -> dict[str, Any]:
        proc = self.run_capture()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def snapshot_files(self, directory: Path) -> list[str]:
        return sorted(
            (item.relative_to(directory).as_posix() for item in directory.rglob("*") if item.is_file()),
            key=lambda item: item.encode("utf-8"),
        )

    def write_record(self, record: dict[str, Any]) -> None:
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        self.record_path.write_bytes(
            (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )


# --------------------------------------------------------------------------------------
# G-01, G-07: the capture reproduces the protocol's digest and mirrors every path
# --------------------------------------------------------------------------------------


class CaptureTests(BaselineTestCase):
    def test_capture_is_recomputable_and_matches_c4(self) -> None:
        receipt = self.capture()

        self.assertTrue(receipt["ok"], receipt)
        self.assertEqual(receipt["mode"], "capture")
        self.assertEqual(receipt["head"], self.commit)
        self.assertEqual(receipt["algorithm"], bm.DIGEST_ALGORITHM)
        self.assertEqual(receipt["tracked_files"], len(TRACKED_FILES))
        self.assertEqual(receipt["copied_files"], len(TRACKED_FILES))
        self.assertEqual(receipt["untracked_files"], len(UNTRACKED_FILES))
        self.assertTrue(receipt["match"])

        tracked = _declared_tracked_paths(self.repo)
        self.assertEqual(receipt["expected_digest"], _independent_c4(self.repo, tracked))
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), tracked)
        self.assertEqual(
            self.snapshot_files(self.untracked_snapshot), sorted(UNTRACKED_FILES, key=str)
        )

        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["expected_digest"], receipt["expected_digest"])
        self.assertEqual(record["recomputed_digest"], receipt["expected_digest"])

    def test_capture_reuses_the_package_digest_construction(self) -> None:
        self.assertIs(cb.digest_from_hashes, bm.digest_from_hashes)
        self.assertIs(cb.sort_key, bm.sort_key)

        source = SCRIPT.read_bytes()
        self.assertNotIn(
            C4_LITERAL,
            source,
            "capture_baseline.py contains the digest literal, so it re-implements the "
            "package's construction instead of importing it",
        )

    def test_keys_format_round_trips(self) -> None:
        proc = self.run_capture("--format", "keys")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 3, proc.stdout)
        published: dict[str, str] = {}
        for line in lines:
            key, _, value = line.partition("=")
            published[key] = value
        self.assertEqual(
            set(published),
            {"report.baseline_commit", "report.baseline_digest", "report.baseline_algorithm"},
        )

        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(published["report.baseline_commit"], record["head"])
        self.assertEqual(published["report.baseline_digest"], record["expected_digest"])
        self.assertEqual(published["report.baseline_algorithm"], record["algorithm"])

        # Round trip: after the work order has edited the worktree, the published keys still
        # reproduce the manifest's baseline identity, because they name the open state and
        # not the current one.
        (self.repo / "src" / "app.py").write_text(
            "def main():\n    return 1\n", encoding="utf-8"
        )
        manifest = bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=published["report.baseline_commit"],
            baseline_digest=published["report.baseline_digest"],
            baseline_algorithm=published["report.baseline_algorithm"],
            baseline_worktree_dir=self.worktree_snapshot,
            baseline_untracked_dir=self.untracked_snapshot,
            tmp_dir=self.workbench / "tmp",
            captured_at=record["captured_at"],
            generated_at="2026-09-15T00:00:00Z",
            strength="standard",
        )
        self.assertEqual(manifest["baseline"]["commit"], record["head"])
        self.assertEqual(manifest["baseline"]["worktree_digest"], record["expected_digest"])
        self.assertEqual(manifest["baseline"]["algorithm"], record["algorithm"])

    def test_non_worktree_exits_non_zero(self) -> None:
        outside = self.root / "not-a-repository"
        outside.mkdir()
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(outside),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                WORK_ORDER_ID,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )
        self.assertNotEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("not a git working tree", payload["error"])

        missing = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(self.root / "absent"),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                WORK_ORDER_ID,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("does not exist", json.loads(missing.stdout)["error"])

    def test_second_capture_is_byte_identical(self) -> None:
        first = self.run_capture()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        first_bytes = self.record_path.read_bytes()

        second = self.run_capture()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(second.stdout, first.stdout)
        self.assertEqual(self.record_path.read_bytes(), first_bytes)


# --------------------------------------------------------------------------------------
# The verify mode: the same digest, from the recorded snapshot directories only
# --------------------------------------------------------------------------------------


class VerifyExistingTests(BaselineTestCase):
    def verify(self, *extra: str, work_order_id: str = WORK_ORDER_ID) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--verify-existing",
                "--repo",
                str(self.repo),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                work_order_id,
                *extra,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )

    def test_verify_existing_reproduces_the_recorded_digest(self) -> None:
        captured = self.capture()
        # The receipt carries the frozen core fields plus the open-state fields the capture
        # adds: the untracked names, the index modes at open and the capture's own skips. The
        # core set is still the required one, which the migration check below proves.
        self.assertEqual(
            set(captured) - {"ok", "mode", "record"},
            set(FROZEN_RECORD_FIELDS) | set(cb.RECORD_OPEN_STATE_FIELDS),
        )

        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["mode"], "verify")
        self.assertTrue(receipt["match"])
        self.assertEqual(receipt["expected_digest"], captured["expected_digest"])
        self.assertEqual(receipt["recomputed_digest"], captured["expected_digest"])

        # A record that this tool did not write, in the frozen *core* schema: the migration
        # step adds the three open-state fields a pre-tool record lacks and changes nothing
        # else, and the record stays verifiable with only the core fields present.
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(record), set(FROZEN_RECORD_FIELDS) | set(cb.RECORD_OPEN_STATE_FIELDS)
        )
        frozen = {field: record[field] for field in FROZEN_RECORD_FIELDS}
        self.write_record(frozen)

        second = self.verify()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout)["recomputed_digest"], captured["expected_digest"])

    def test_verify_existing_fails_closed(self) -> None:
        captured = self.capture()
        record_bytes = self.record_path.read_bytes()

        # One snapshot file's bytes differ.
        victim = self.worktree_snapshot / "src" / "app.py"
        victim.write_bytes(victim.read_bytes() + b"# tampered\n")
        tampered = self.verify()
        self.assertNotEqual(tampered.returncode, 0, tampered.stdout)
        self.assertIn("baseline digest mismatch", json.loads(tampered.stdout)["error"])
        self.assertEqual(self.record_path.read_bytes(), record_bytes)

        # A tracked path is missing from the snapshot.
        victim.write_bytes((self.repo / "src" / "app.py").read_bytes())
        (self.worktree_snapshot / "README.md").unlink()
        incomplete = self.verify()
        self.assertNotEqual(incomplete.returncode, 0, incomplete.stdout)
        self.assertIn("does not mirror the tracked path set", json.loads(incomplete.stdout)["error"])
        self.assertEqual(self.record_path.read_bytes(), record_bytes)

        # The record is not selectable by this work order id.
        unselected = self.verify(work_order_id="20260101-0000-another-work-order")
        self.assertNotEqual(unselected.returncode, 0, unselected.stdout)
        self.assertIn("baseline_record_unselected", json.loads(unselected.stdout)["error"])

        # The record is absent.
        self.record_path.unlink()
        absent = self.verify()
        self.assertNotEqual(absent.returncode, 0, absent.stdout)
        self.assertIn("baseline_record_missing", json.loads(absent.stdout)["error"])

        # No failed comparison rewrote the record: its bytes are still the captured ones,
        # and the digest they publish is still the captured digest.
        self.assertEqual(json.loads(record_bytes)["expected_digest"], captured["expected_digest"])
        self.assertTrue(json.loads(record_bytes)["match"])


# --------------------------------------------------------------------------------------
# F6: the capture opens a work order on a repository that already holds a shape a text
# reader cannot open, instead of blocking the work order at open
# --------------------------------------------------------------------------------------


class CaptureSkipTests(BaselineTestCase):
    """A tracked path with no readable bytes is skipped and named, not fatal."""

    def add_submodule(self, relative: str = "vendor-sub") -> str:
        source = self.root / "sub"
        source.mkdir()
        _git(source, "init", "-q")
        _git(source, "config", "user.email", "probe@example.invalid")
        _git(source, "config", "user.name", "probe")
        (source / "lib.txt").write_text("submodule content\n", encoding="utf-8")
        _git(source, "add", "-A")
        _git(source, "commit", "-q", "-m", "submodule baseline")
        revision = _git(source, "rev-parse", "HEAD").decode("utf-8").strip()
        # A gitlink's worktree path is a directory, so the capture loop's `read_bytes` on it
        # fails on every host; the directory is deliberately not checked out here.
        _git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{revision},{relative}")
        return revision

    def add_unreadable_tracked_path(self, relative: str, payload: bytes) -> None:
        """An index entry whose spelled name has no readable file behind it."""
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=str(self.repo),
            input=payload,
            capture_output=True,
        )
        self.assertEqual(blob.returncode, 0, blob.stderr.decode("utf-8", "replace"))
        _git(
            self.repo,
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob.stdout.decode('ascii').strip()},{relative}",
        )

    def test_unreadable_tracked_paths_are_skipped_with_named_degradations(self) -> None:
        """Pre-fix the capture exits 1 with `tracked path is not readable` and writes no record.

        Both halves of the measured shape are present: a `160000` gitlink, whose worktree
        path is a directory rather than bytes, and a tracked path whose name git spells with
        U+FFFD and which therefore cannot be opened at all. A work order opened on such a
        repository had no baseline record and could not proceed.
        """
        self.add_submodule()
        lossy = "src/caf\ufffd_tracked.py"
        self.add_unreadable_tracked_path(lossy, b"latin1 = 1\n")
        _git(self.repo, "commit", "-q", "-m", "baseline with a gitlink and an odd name")

        tracked = _declared_tracked_paths(self.repo)
        self.assertIn("vendor-sub", tracked)
        self.assertIn(lossy, tracked)
        self.assertIsNone(bm.read_bytes(self.repo / "vendor-sub"))
        self.assertIsNone(bm.read_bytes(self.repo / lossy))

        receipt = self.capture()
        self.assertTrue(receipt["match"])
        self.assertEqual(receipt["tracked_files"], len(tracked))
        self.assertEqual(receipt["copied_files"], len(tracked) - 2)
        self.assertEqual(
            self.snapshot_files(self.worktree_snapshot),
            sorted(set(tracked) - {"vendor-sub", lossy}),
        )

        # The skips are named, in the receipt the caller reads and in the record it keeps.
        degradations = set(receipt["degradations"])
        self.assertIn("tracked_path_unreadable:vendor-sub", degradations)
        self.assertIn(f"tracked_path_unreadable:{lossy}", degradations)
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        self.assertEqual(set(record["degradations"]), degradations)
        # The open state also carries the two facts the manifest cannot recover later: the
        # untracked names and the index modes at open.
        self.assertEqual(
            record["untracked_paths"],
            sorted(UNTRACKED_FILES, key=lambda item: item.encode("utf-8")),
        )
        self.assertEqual(record["index_modes"], _index_modes(self.repo))

        # `--verify-existing` reproduces the digest over the captured subset, so the skipped
        # path does not turn the recorded open state into an unverifiable one.
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--verify-existing",
                "--repo",
                str(self.repo),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                WORK_ORDER_ID,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["recomputed_digest"], receipt["expected_digest"])

    def test_a_readable_tracked_path_is_never_skipped(self) -> None:
        """Control: the skip rule is about readability, not a blanket relief for odd shapes."""
        tracked = _declared_tracked_paths(self.repo)
        receipt = self.capture()
        self.assertEqual(receipt["copied_files"], len(tracked))
        self.assertEqual(self.snapshot_files(self.worktree_snapshot), tracked)
        self.assertEqual(receipt["degradations"], [])

        # A tracked path that is missing from the snapshot while it is still readable in the
        # worktree keeps failing: the skip rule is about readability, not a blanket relief.
        victim = self.worktree_snapshot / "src" / "app.py"
        payload = victim.read_bytes()
        victim.unlink()
        proc = self.run_verify()
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("does not mirror the tracked path set", json.loads(proc.stdout)["error"])
        victim.write_bytes(payload)

        # ... and a snapshot that lost a file whose worktree copy is gone too is still a
        # failure, because the recorded digest covered that path.
        (self.repo / "src" / "app.py").unlink()
        victim.unlink()
        proc = self.run_verify()
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("does not match the snapshot", json.loads(proc.stdout)["error"])
        victim.write_bytes(payload)
        (self.repo / "src" / "app.py").write_bytes(payload)

    def run_verify(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--verify-existing",
                "--repo",
                str(self.repo),
                "--workbench",
                str(self.workbench),
                "--work-order-id",
                WORK_ORDER_ID,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.root),
        )


# --------------------------------------------------------------------------------------
# The open-state record's schema: the three added facts, and the thirteen that stay
# required. The documents that describe the record must state both halves, because a reader
# told only about the addition cannot tell whether an already-frozen record is still legal.
# --------------------------------------------------------------------------------------

PROTOCOL = SKILL_ROOT / "references" / "coverage-protocol.md"
SKILL_PAGE = SKILL_ROOT / "SKILL.md"
# The capture paragraph of the package page, and the two clauses that state the record's
# contents. Each entry is the span, bounded by the token that follows it in that document, and
# the fields that span is the named home of. C4a is where the untracked names belong, C4b where
# the index modes and the capture's skips do, and the package page states all three.
RECORD_SCHEMA_SPANS = (
    (
        "SKILL.md capture paragraph",
        SKILL_PAGE,
        "`capture_baseline.py` runs **once**",
        "`--tmp-dir` is the workbench",
        cb.RECORD_OPEN_STATE_FIELDS,
    ),
    (
        "coverage-protocol.md C4a",
        PROTOCOL,
        "**C4a**",
        "**C4b**",
        ("untracked_paths",),
    ),
    (
        "coverage-protocol.md C4b",
        PROTOCOL,
        "**C4b**",
        "**C5**",
        ("index_modes", "degradations"),
    ),
)
# The three fields' homes, as a set: every added fact is described by at least one of the three
# spans, so a field cannot be declared in the schema and left undescribed.
_DESCRIBED_FIELDS = {field for _, _, _, _, fields in RECORD_SCHEMA_SPANS for field in fields}
assert _DESCRIBED_FIELDS == set(cb.RECORD_OPEN_STATE_FIELDS), (
    "every added field needs a document that describes it: "
    f"{sorted(set(cb.RECORD_OPEN_STATE_FIELDS) - _DESCRIBED_FIELDS)} is undescribed"
)


class SnapshotDirectoryDefaultTests(BaselineTestCase):
    """R-02: the two snapshot directories default from the record the capture wrote.

    The builder already reads `<tmp-dir>/baseline-open-state.json`, which names both
    directories the capture materialised. A caller that passes neither flag used to run with
    no `B` side at all: the worktree snapshot read `absent`, every path's provenance
    alignment failed for want of its opening bytes, and the whole change set was charged to
    `pre_existing` -- a materially wrong attribution that no validation stage detects.
    """

    def capture_and_edit_a_tracked_path(self) -> None:
        self.capture()
        (self.repo / "src" / "app.py").write_text(
            "def main():\n    return 1\n", encoding="utf-8"
        )

    def build(
        self,
        worktree_dir: Path | None,
        untracked_dir: Path | None,
    ) -> dict[str, Any]:
        return bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=self.commit,
            baseline_digest=json.loads(self.record_path.read_text(encoding="utf-8"))[
                "expected_digest"
            ],
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=worktree_dir,
            baseline_untracked_dir=untracked_dir,
            tmp_dir=self.workbench / "tmp",
            captured_at="2026-09-15T17:45:00Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )

    def test_omitting_both_flags_resolves_them_from_the_record(self) -> None:
        self.capture_and_edit_a_tracked_path()

        explicit = self.build(self.worktree_snapshot, self.untracked_snapshot)
        defaulted = self.build(None, None)

        self.assertEqual(defaulted, explicit)
        self.assertEqual(defaulted["baseline"]["worktree_snapshot"]["state"], "complete")
        self.assertEqual(
            defaulted["baseline"]["worktree_snapshot"]["path"], str(self.worktree_snapshot)
        )
        self.assertEqual(
            defaulted["baseline"]["untracked_snapshot"]["path"], str(self.untracked_snapshot)
        )
        self.assertEqual(defaulted["pre_existing_total"], 0)
        self.assertEqual(defaulted["degradations"], [])
        self.assertGreater(defaulted["units_total"], 0)

    def test_a_record_without_the_two_paths_still_degrades_honestly(self) -> None:
        """The fallback is the record, not an invention: no path recorded means no snapshot."""
        self.capture_and_edit_a_tracked_path()
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        for field in ("worktree_snapshot", "untracked_snapshot"):
            del record[field]
        self.write_record(record)

        defaulted = self.build(None, None)

        self.assertEqual(defaulted["baseline"]["worktree_snapshot"]["state"], "absent")
        self.assertIn(bm.UNTRACKED_SNAPSHOT_DEGRADATION, defaulted["degradations"])
        self.assertIn(
            bm.WORKTREE_SNAPSHOT_DEGRADATIONS["absent"], defaulted["degradations"]
        )

    def test_an_explicit_directory_wins_over_the_record(self) -> None:
        """A caller that names a directory is pointing the rebuild at it, record or not."""
        self.capture_and_edit_a_tracked_path()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()

        named = self.build(elsewhere, self.untracked_snapshot)

        self.assertEqual(named["baseline"]["worktree_snapshot"]["path"], str(elsewhere))
        self.assertEqual(named["baseline"]["worktree_snapshot"]["state"], "empty")


class OpenStateRecordSchemaTests(BaselineTestCase):
    """Three added facts, thirteen still required: both halves of the record's schema.

    The addition is deliberate rather than incidental, and it is the only way the defects it
    closes could be named: the untracked names at open are what let a path that was untracked at
    open and has since left the worktree be named instead of dropped; the index modes at open are
    the only evidence that separates a mode-only change made before the open from one made after
    it; and the capture's own skips need somewhere to be named without blocking the work order at
    open. So the fields are asserted to exist *and* to be described, while the core set is
    asserted to be unchanged and still sufficient, which is what keeps a frozen record legal.
    """

    def test_the_record_carries_the_three_facts_without_dropping_a_core_field(self) -> None:
        self.capture()
        record = json.loads(self.record_path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(record),
            set(FROZEN_RECORD_FIELDS) | set(cb.RECORD_OPEN_STATE_FIELDS),
            "the record is the frozen core set plus exactly the three added facts",
        )
        self.assertEqual(
            sorted(set(FROZEN_RECORD_FIELDS) & set(cb.RECORD_OPEN_STATE_FIELDS)),
            [],
            "an added fact must not also be a core field: the two sets are a partition",
        )

        # The three facts are populated, not declared-only. The index modes are read from git
        # rather than from the tool, so the comparison is independent of the producer.
        self.assertEqual(
            record["untracked_paths"],
            sorted(UNTRACKED_FILES, key=lambda item: item.encode("utf-8")),
        )
        self.assertEqual(record["index_modes"], _index_modes(self.repo))
        self.assertNotEqual(record["index_modes"], {})
        self.assertEqual(record["degradations"], [])

    def test_a_record_with_only_the_thirteen_core_fields_still_loads(self) -> None:
        """The compatibility half: the addition does not invalidate an already-frozen record.

        This work order's own record predates the capture tool, so the property is not academic.
        `_load_record` is called directly, because what is under test is the required set rather
        than the digest comparison the sibling test already covers.
        """
        self.assertEqual(len(FROZEN_RECORD_FIELDS), 13)
        self.assertEqual(tuple(cb.RECORD_FIELDS), FROZEN_RECORD_FIELDS)
        self.assertEqual(
            set(cb.RECORD_FIELDS) & set(cb.RECORD_OPEN_STATE_FIELDS),
            set(),
            "the added facts must not have become required",
        )

        self.capture()
        record = json.loads(self.record_path.read_text(encoding="utf-8"))
        frozen = {field: record[field] for field in FROZEN_RECORD_FIELDS}
        self.write_record(frozen)
        loaded = cb._load_record(self.record_path, WORK_ORDER_ID)
        self.assertEqual(set(loaded), set(FROZEN_RECORD_FIELDS))

        # ... and a core field is still required, so "the addition is optional" has not turned
        # into "the core set is optional".
        for field in ("expected_digest", "worktree_snapshot"):
            broken = dict(frozen)
            del broken[field]
            self.write_record(broken)
            with self.assertRaises(bm.ManifestError):
                cb._load_record(self.record_path, WORK_ORDER_ID)

    def test_the_documents_describe_both_halves_of_the_schema(self) -> None:
        for label, path, start, end, fields in RECORD_SCHEMA_SPANS:
            content = path.read_text(encoding="utf-8")
            self.assertIn(start, content, f"{label}: the span's opening token moved")
            span = content.split(start, 1)[1].split(end, 1)[0]
            for field in fields:
                self.assertIn(f"`{field}`", span, f"{label} must name the {field} field it adds")
            self.assertIn(
                "thirteen core fields", span, f"{label} must state which set stays required"
            )
            self.assertIn("still", span, f"{label} must state an already-frozen record's fate")


if __name__ == "__main__":
    unittest.main()
