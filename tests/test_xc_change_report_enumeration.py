"""Tests for `build_manifest.py`'s enumeration: the snapshot contract, path fidelity, the
change shapes a worktree byte diff cannot see, and the overlapped-region counter.

Each test names the gap it closes, because every one of them measures a behaviour the shipped
builder got wrong or never asserted:

* G-02 -- an existing but empty snapshot directory was read as a healthy capture, so a
  pre-existing edit was charged to the work order (`test_present_but_empty_snapshot_is_unusable`);
* G-05, G-06 -- path bytes were decoded lossily, so two distinct paths could collapse onto one
  entry and the digest followed a different ordering rule than the protocol's
  (`test_non_utf8_paths_stay_distinct`, `test_sort_key_is_byte_order`);
* G-07 -- the worktree snapshot's path and cardinality were fixed by no clause and exercised by
  no test (`test_capture_mirrors_every_tracked_path`);
* G-38, G-39 -- a mode-only change and a gitlink left `files[]` entirely, and a link was read by
  opening the path, which follows it
  (`test_mode_only_and_gitlink_changes_are_recorded`,
  `test_symlink_content_is_the_link_target_text`);
* G-13 -- the host-adapter roots no lifecycle node owns had no exclusion category
  (`test_adapter_install_paths_are_declared_exclusions`);
* G-40 -- the overlapped pre-existing region was flagged but never counted
  (`test_overlapped_pre_existing_region_is_counted`);
* G-42 -- the exclusion vocabulary and the modified-untracked case were exercised but asserted
  by no test (`test_every_exclusion_category_is_asserted_on_a_named_path`,
  `test_modified_untracked_file_keeps_the_snapshot_baseline`).

The scratch repositories are built under the test process's own temporary root; nothing is
written into the repository under test.

Standard library only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "change_report"
CAPTURE_SCRIPT = SCRIPTS / "capture_baseline.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_manifest as bm  # noqa: E402


WORK_ORDER_ID = "20260915-2215-change-report-full-rollout"
EXOTIC_SHAPES = "exotic-shapes"

# The non-UTF-8 path pair the C29 step-6 ordering rule discriminates on (G-05, G-06).
# `b"src/a\xc3"` is not valid UTF-8, so it survives only through `surrogateescape`: decoded
# with `replace` it becomes a replacement character and its digest record stops naming the
# file. By bytes it sorts before `b"src/a\xc3\xa9"`; as decoded text the surrogate (U+DCC3)
# sorts after the valid `é` (U+00E9), which is the divergence between the two rules.
NON_UTF8_RAW = (b"src/a\xc3", b"src/a\xc3\xa9")
NON_UTF8_TEXT = tuple(raw.decode("utf-8", "surrogateescape") for raw in NON_UTF8_RAW)
NON_UTF8_PAYLOAD = {NON_UTF8_RAW[0]: b"first\n", NON_UTF8_RAW[1]: b"second\n"}
# The path seam is reached with a full path, so the content map is keyed by the final segment:
# that is the only part that carries the raw bytes.
NON_UTF8_BY_NAME = {raw.rsplit(b"/", 1)[-1]: payload for raw, payload in NON_UTF8_PAYLOAD.items()}

# One named path per C15 exclusion category the `exotic-shapes` scenario carries. The
# eleventh category, `pre_existing_change`, is a hunk-level reason and is asserted separately.
NAMED_EXCLUSION_PATHS = {
    "generated": "schema/user.pb.go",
    "lockfile": "package-lock.json",
    "vendor": "vendor/lib.js",
    "binary": "assets/blob.bin",
    "minified": "assets/app.min.js",
    "sensitive": ".env",
    "encoding_unsupported": "src/legacy.dat",
    "mode_change": "bin/tool.sh",
    "submodule": "vendorlib",
    "adapter_install": ".codex/agents/reviewer.md",
}

# The C17 adapter-root table, which the contract declares normatively.
ADAPTER_ROOT_TABLE = {
    ".claude/*",
    "*/.claude/*",
    ".codex/*",
    "*/.codex/*",
    ".opencode/*",
    "*/.opencode/*",
    ".trae/*",
    "*/.trae/*",
    ".agents/*",
    "*/.agents/*",
}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def byte_order_digest(records: list[tuple[bytes, str]]) -> str:
    """The coverage protocol's C4 digest, written here from scratch and importing nothing.

    This is the oracle the builder's ordering is measured against: it shares no helper, no
    constant and no ordering function with the package.
    """
    payload = bytearray()
    for raw_path, digest in sorted(records, key=lambda item: item[0]):
        payload.extend(raw_path)
        payload.extend(b"\x00")
        payload.extend(digest.encode("ascii"))
        payload.extend(b"\n")
    return sha256_hex(bytes(payload))


def git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, input=stdin)
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {repo}: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    git(repo, "config", "core.autocrlf", "false")


def decode_paths(payload: bytes) -> list[str]:
    return [item.decode("utf-8", "surrogateescape") for item in payload.split(b"\x00") if item]


def index_modes(repo: Path) -> dict[str, str]:
    """`path -> mode` straight from the index, the source C17 assigns the shape categories."""
    modes: dict[str, str] = {}
    for record in git(repo, "ls-files", "-s", "-z").split(b"\x00"):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b"\t")
        if not separator:
            continue
        modes[raw_path.decode("utf-8", "surrogateescape")] = meta.split(b" ")[0].decode("ascii")
    return modes


def content_bytes(spec: Any, fixture_dir: Path) -> bytes:
    if "base64" in spec:
        return base64.b64decode(spec["base64"])
    if "file" in spec:
        return (fixture_dir / spec["file"]).read_bytes()
    return spec["text"].encode(spec.get("encoding", "utf-8"))


class ScratchCase(unittest.TestCase):
    """A scratch repository outside the checkout, plus a workbench with a `tmp/` directory."""

    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-u2-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.root = root
        self.repo = root / "repo"
        self.workbench = root / "workbench"
        self.workbench.mkdir(parents=True)
        init_repo(self.repo)

    # -- paths ---------------------------------------------------------------------

    @property
    def worktree_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-worktree"

    @property
    def untracked_snapshot(self) -> Path:
        return self.workbench / "tmp" / "baseline-untracked"

    # -- repository edits ----------------------------------------------------------

    def write(self, relative: str, payload: bytes | str) -> Path:
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload.encode("utf-8") if isinstance(payload, str) else payload)
        return target

    def commit_all(self, message: str = "baseline") -> str:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD").decode().strip()

    def mirror(self, paths: list[str], target: Path) -> None:
        """Copy the named worktree paths into a snapshot directory, parents first."""
        for relative in paths:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.repo / relative).read_bytes())

    def mirror_open_state(self) -> None:
        """The faithful C4b shape: tracked paths only, as they are on disk right now."""
        self.worktree_snapshot.mkdir(parents=True, exist_ok=True)
        self.untracked_snapshot.mkdir(parents=True, exist_ok=True)
        self.mirror(self.tracked_paths("HEAD"), self.worktree_snapshot)
        self.mirror(
            decode_paths(git(self.repo, "ls-files", "--others", "--exclude-standard", "-z")),
            self.untracked_snapshot,
        )

    def capture(self, *extra: str) -> dict[str, Any]:
        """Run the real capture tool, because the open state it records is what the builder reads."""
        proc = subprocess.run(
            [
                sys.executable,
                str(CAPTURE_SCRIPT),
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
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def tracked_paths(self, commit: str) -> list[str]:
        return sorted(
            decode_paths(git(self.repo, "ls-tree", "-r", "--name-only", "-z", commit)),
            key=lambda item: item.encode("utf-8", "surrogateescape"),
        )

    # -- manifest ------------------------------------------------------------------

    def build(
        self,
        commit: str,
        *,
        worktree_dir: Path | None | str = "workbench",
        untracked_dir: Path | None | str = "workbench",
    ) -> dict[str, Any]:
        """Build a manifest for the scratch repository.

        The snapshot directories default to the workbench's own `tmp/` paths, which is what a
        real work order passes; `None` requests the absent case explicitly.
        """
        if worktree_dir == "workbench":
            worktree_dir = self.worktree_snapshot
        if untracked_dir == "workbench":
            untracked_dir = self.untracked_snapshot
        return bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=commit,
            baseline_digest="fixture-baseline-digest",
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=worktree_dir,
            baseline_untracked_dir=untracked_dir,
            tmp_dir=self.workbench / "tmp",
            captured_at="2026-09-15T16:13:18Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )

    @staticmethod
    def by_path(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {entry["path"]: entry for entry in manifest["files"]}


# --------------------------------------------------------------------------------------
# G-02: availability is decided by content, not by a directory test
# --------------------------------------------------------------------------------------


class SnapshotAvailabilityTests(ScratchCase):
    def open_state(self) -> tuple[str, dict[str, bytes]]:
        """A repository that was dirty when the work order opened, plus the work order's own edit."""
        self.write("src/app.py", "def main():\n    return 0\n")
        self.write("src/other.py", "def other():\n    return 1\n")
        commit = self.commit_all()
        # Dirty at open: an edit this work order never makes.
        self.write("src/app.py", "def main():\n    return 42\n")
        opened = {
            "src/app.py": (self.repo / "src" / "app.py").read_bytes(),
            "src/other.py": (self.repo / "src" / "other.py").read_bytes(),
        }
        # The work order then edits the other file.
        self.write("src/other.py", "def other():\n    return 2\n")
        return commit, opened

    def test_present_but_empty_snapshot_is_unusable(self) -> None:
        commit, opened = self.open_state()
        # The snapshot directory exists and holds nothing: the shape the shipped builder read
        # as a healthy capture.
        self.worktree_snapshot.mkdir(parents=True)
        self.untracked_snapshot.mkdir(parents=True)

        manifest = self.build(commit)
        documented = manifest["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "empty")
        self.assertFalse(documented["available"])
        self.assertIn("baseline_worktree_snapshot_empty", manifest["degradations"])

        # No path may be charged to the work order: with B unknown the C37 alignment is
        # impossible, so every path fails closed as pre-existing instead of being attributed
        # to the author who would then have to explain it.
        files = manifest["files"]
        self.assertTrue(files, "the two edited files must stay in the change set")
        self.assertEqual(
            [entry["path"] for entry in files if entry["analyzed_as"] == "work_order"], []
        )
        self.assertTrue(all(entry["provenance_degraded"] for entry in files), files)
        self.assertEqual(manifest["units_total"], 0)
        self.assertGreaterEqual(manifest["pre_existing_total"], 1)

        # Control: the same repository with a faithful snapshot separates the two edits, so the
        # assertions above measure the missing content and not a blanket "always pre-existing".
        for relative, payload in opened.items():
            destination = self.worktree_snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        control = self.build(commit)
        documented = control["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "complete")
        self.assertTrue(documented["available"])
        self.assertEqual(control["degradations"], [])
        self.assertEqual(control["units_total"], 1)
        self.assertEqual(control["pre_existing_total"], 1)
        entries = self.by_path(control)
        self.assertEqual(entries["src/app.py"]["analyzed_as"], "pre_existing")
        self.assertEqual(entries["src/other.py"]["analyzed_as"], "work_order")
        self.assertTrue(all(not entry["provenance_degraded"] for entry in control["files"]))


# --------------------------------------------------------------------------------------
# G-05, G-06: path bytes and the ordering rule
# --------------------------------------------------------------------------------------


class PathFidelityTests(ScratchCase):
    def test_non_utf8_paths_stay_distinct(self) -> None:
        self.write("src/keep.py", "value = 1\n")
        commit = self.commit_all()

        payload = b"".join(raw + b"\x00" for raw in NON_UTF8_RAW)
        real_run_git = bm.run_git
        real_read_bytes = bm.read_bytes

        def fake_run_git(repo: Path, args: list[str], allow_one: bool = False) -> bytes:
            if args == ["ls-files", "--others", "--exclude-standard", "-z"]:
                return payload
            return real_run_git(repo, args, allow_one)

        def fake_read_bytes(path: Path) -> bytes | None:
            candidate = Path(path)
            raw = candidate.name.encode("utf-8", "surrogateescape")
            if raw in NON_UTF8_BY_NAME:
                return NON_UTF8_BY_NAME[raw]
            return real_read_bytes(candidate)

        # Neither snapshot directory exists, so every baseline read misses and both paths
        # arrive as additions whose head content is served through the module's path seam.
        with mock.patch.object(bm, "run_git", fake_run_git), mock.patch.object(
            bm, "read_bytes", fake_read_bytes
        ):
            manifest = self.build(commit, worktree_dir=None, untracked_dir=None)

        paths = [entry["path"] for entry in manifest["files"]]
        self.assertEqual(len(paths), 2, manifest["files"])
        self.assertEqual(len(set(paths)), 2, "two distinct raw paths must stay two entries")
        self.assertEqual(paths, list(NON_UTF8_TEXT))

        entries = self.by_path(manifest)
        for raw, text in zip(NON_UTF8_RAW, NON_UTF8_TEXT):
            self.assertEqual(entries[text]["source_sha256"], sha256_hex(NON_UTF8_PAYLOAD[raw]))

        expected = byte_order_digest(
            [(raw, sha256_hex(NON_UTF8_PAYLOAD[raw])) for raw in NON_UTF8_RAW]
        )
        self.assertEqual(manifest["head"]["digest"], expected)

    def test_sort_key_is_byte_order(self) -> None:
        # The exposed ordering function returns the path's own bytes.
        self.assertEqual([bm.sort_key(path) for path in NON_UTF8_TEXT], list(NON_UTF8_RAW))
        self.assertEqual(sorted(NON_UTF8_TEXT, key=bm.sort_key), list(NON_UTF8_TEXT))
        # ... and that order is not the decoded-text order, which is the whole point of the rule.
        self.assertNotEqual(sorted(NON_UTF8_TEXT, key=bm.sort_key), sorted(NON_UTF8_TEXT))

        pairs = [(NON_UTF8_TEXT[0], "a" * 64), (NON_UTF8_TEXT[1], "b" * 64)]
        self.assertEqual(
            bm.digest_from_hashes(pairs),
            byte_order_digest([(NON_UTF8_RAW[0], "a" * 64), (NON_UTF8_RAW[1], "b" * 64)]),
        )
        as_text = bytearray()
        for path, digest in sorted(pairs):
            as_text.extend(path.encode("utf-8", "replace"))
            as_text.extend(b"\x00")
            as_text.extend(digest.encode("ascii"))
            as_text.extend(b"\n")
        self.assertNotEqual(bm.digest_from_hashes(pairs), sha256_hex(bytes(as_text)))


# --------------------------------------------------------------------------------------
# G-07: a capture mirrors every tracked path, and the manifest reads it as complete
# --------------------------------------------------------------------------------------


class CaptureCoverageTests(ScratchCase):
    def test_capture_mirrors_every_tracked_path(self) -> None:
        self.write("README.md", "# capture coverage\n")
        self.write("src/app.py", "def main():\n    return 0\n")
        self.write("src/nested/deep.txt", "nested\n")
        commit = self.commit_all()
        self.assertEqual(git(self.repo, "status", "--porcelain"), b"", "the repository must be clean")

        proc = subprocess.run(
            [
                sys.executable,
                str(CAPTURE_SCRIPT),
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
        receipt = json.loads(proc.stdout)

        # The repository holds no untracked path, so the capture has nothing to mirror into the
        # untracked directory and never creates it; a work order's workbench has one.
        self.untracked_snapshot.mkdir(parents=True, exist_ok=True)

        tracked = self.tracked_paths(commit)
        captured = bm.snapshot_paths(self.worktree_snapshot)
        self.assertEqual(captured, tracked)
        self.assertEqual(len(captured), len(tracked))
        self.assertEqual(receipt["tracked_files"], len(tracked))
        self.assertEqual(receipt["copied_files"], len(tracked))

        manifest = self.build(
            commit,
            worktree_dir=self.worktree_snapshot,
            untracked_dir=self.untracked_snapshot,
        )
        documented = manifest["baseline"]["worktree_snapshot"]
        self.assertEqual(documented["state"], "complete")
        self.assertTrue(documented["available"])
        self.assertEqual(manifest["degradations"], [])


# --------------------------------------------------------------------------------------
# G-13, G-38, G-39, G-42: the shapes a worktree byte diff cannot see
# --------------------------------------------------------------------------------------


def write_state(repo: Path, fixture_dir: Path, state: dict[str, Any]) -> None:
    for relative, spec in state.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content_bytes(spec, fixture_dir))


def checkout_submodule(target: Path, source: Path, revision: str) -> None:
    """A real checkout, because that is what makes a gitlink visible to `git diff`."""
    target.mkdir(parents=True, exist_ok=True)
    git(target, "init", "-q")
    git(target, "remote", "add", "origin", str(source))
    git(target, "fetch", "-q", "origin")
    git(target, "checkout", "-q", revision)


def apply_index_entries(
    repo: Path,
    fixture_dir: Path,
    entries: dict[str, Any],
    submodule_source: Path,
    submodule_revision: str,
    commit: str = "",
) -> None:
    """Write the scenario's index entries: link blobs, a mode-only change and a gitlink."""
    for relative, spec in entries.items():
        if "gitlink" in spec:
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{submodule_revision},{relative}")
            checkout_submodule(repo / relative, submodule_source, submodule_revision)
            continue
        if "blob" in spec:
            payload = content_bytes(spec["blob"], fixture_dir)
            digest = git(repo, "hash-object", "-w", "--stdin", stdin=payload).decode().strip()
        else:
            digest = git(repo, "rev-parse", f"{commit}:{relative}").decode().strip()
        git(repo, "update-index", "--add", "--cacheinfo", f"{spec['mode']},{digest},{relative}")


class ExoticShapeCase(unittest.TestCase):
    """The `exotic-shapes` scenario materialised once: a real repository, a real gitlink."""

    root: Path
    repo: Path
    commit: str
    worktree_snapshot: Path
    untracked_snapshot: Path
    manifest: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp(prefix="xc-report-u2-shapes-"))
        fixture_dir = FIXTURES / EXOTIC_SHAPES
        scenario = json.loads((fixture_dir / "scenario.json").read_text(encoding="utf-8"))
        cls.repo = cls.root / "repo"
        submodule = cls.root / "sub"

        init_repo(submodule)
        (submodule / "lib.txt").write_bytes(b"submodule content\n")
        git(submodule, "add", "-A")
        git(submodule, "commit", "-q", "-m", "submodule baseline")
        revision = git(submodule, "rev-parse", "HEAD").decode().strip()

        init_repo(cls.repo)
        write_state(cls.repo, fixture_dir, scenario["commit"])
        git(cls.repo, "add", "-A")
        apply_index_entries(
            cls.repo, fixture_dir, scenario.get("commit_index", {}), submodule, revision
        )
        git(cls.repo, "commit", "-q", "-m", "baseline")
        cls.commit = git(cls.repo, "rev-parse", "HEAD").decode().strip()

        # The open-state worktree holds each index-backed link's own bytes, which is what a
        # checkout writes when the host has no symbolic links.
        for relative, spec in scenario.get("commit_index", {}).items():
            if "blob" in spec:
                (cls.repo / relative).write_bytes(content_bytes(spec["blob"], fixture_dir))

        write_state(cls.repo, fixture_dir, scenario["worktree_at_baseline"])

        cls.worktree_snapshot = cls.root / "baseline-worktree"
        cls.untracked_snapshot = cls.root / "baseline-untracked"
        cls.worktree_snapshot.mkdir(parents=True)
        cls.untracked_snapshot.mkdir(parents=True)
        tracked = decode_paths(git(cls.repo, "ls-tree", "-r", "--name-only", "-z", cls.commit))
        for relative in tracked:
            destination = cls.worktree_snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((cls.repo / relative).read_bytes())
        for relative in decode_paths(
            git(cls.repo, "ls-files", "--others", "--exclude-standard", "-z")
        ):
            destination = cls.untracked_snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((cls.repo / relative).read_bytes())

        write_state(cls.repo, fixture_dir, scenario["head"])
        apply_index_entries(
            cls.repo,
            fixture_dir,
            scenario.get("head_index", {}),
            submodule,
            revision,
            commit=cls.commit,
        )

        cls.manifest = bm.build_manifest(
            repo_path=cls.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=cls.commit,
            baseline_digest="fixture-baseline-digest",
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=cls.worktree_snapshot,
            baseline_untracked_dir=cls.untracked_snapshot,
            tmp_dir=cls.root / "tmp",
            captured_at="2026-09-15T16:13:18Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root, ignore_errors=True)

    def entries(self) -> dict[str, dict[str, Any]]:
        return {entry["path"]: entry for entry in self.manifest["files"]}


class ExoticShapeTests(ExoticShapeCase):
    def test_adapter_install_paths_are_declared_exclusions(self) -> None:
        path = NAMED_EXCLUSION_PATHS["adapter_install"]
        # The path must really reach the enumeration: it is not ignored by any rule.
        self.assertIn(
            path,
            decode_paths(git(self.repo, "ls-files", "--others", "--exclude-standard", "-z")),
        )
        entry = self.entries()[path]
        self.assertEqual(entry["exclude_reason"], "adapter_install")
        self.assertFalse(entry["analyzable"])
        self.assertEqual(entry["hunks"], [])
        self.assertIn("adapter_install", bm.EXCLUSION_CATEGORIES)
        self.assertEqual(set(bm.ADAPTER_INSTALL_PATTERNS), ADAPTER_ROOT_TABLE)

    def test_mode_only_and_gitlink_changes_are_recorded(self) -> None:
        entries = self.entries()
        modes = index_modes(self.repo)

        # The mode-only change: git reports the path as modified while the bytes are equal,
        # so only the index mode can carry the statement.
        self.assertEqual(modes["bin/tool.sh"], "100755")
        tool = entries["bin/tool.sh"]
        self.assertEqual(tool["change_kind"], "modified")
        self.assertEqual(tool["exclude_reason"], "mode_change")
        self.assertEqual(tool["hunks"], [])
        self.assertFalse(tool["analyzable"])
        self.assertEqual(tool["source_sha256"], tool["origin_sha256"])

        # The gitlink: a `160000` index entry whose recorded content is a commit id, and whose
        # worktree path is a directory rather than bytes.
        self.assertEqual(modes["vendorlib"], "160000")
        gitlink = entries["vendorlib"]
        self.assertEqual(gitlink["change_kind"], "added")
        self.assertEqual(gitlink["exclude_reason"], "submodule")
        self.assertEqual(gitlink["hunks"], [])
        self.assertFalse(gitlink["analyzable"])

    def test_symlink_content_is_the_link_target_text(self) -> None:
        entries = self.entries()
        self.assertEqual(index_modes(self.repo)["link.txt"], "120000")
        link_text = b"target-at-head.txt\n"
        target_bytes = (self.repo / "link.txt").read_bytes()
        self.assertNotEqual(link_text, target_bytes)

        entry = entries["link.txt"]
        self.assertEqual(entry["change_kind"], "modified")
        self.assertTrue(entry["analyzable"])
        # The link text is what git records; the target file's bytes are what opening the path
        # would hand over, and they must not be the analysed content.
        self.assertEqual(entry["source_sha256"], sha256_hex(link_text))
        self.assertNotEqual(entry["source_sha256"], sha256_hex(target_bytes))
        self.assertEqual(entry["origin_sha256"], sha256_hex(b"target-at-open.txt\n"))

        hunk = entry["hunks"][0]
        self.assertEqual(
            bm.unit_lines(self.repo, self.commit, self.untracked_snapshot, entry, hunk),
            ["target-at-head.txt"],
        )

    def test_every_exclusion_category_is_asserted_on_a_named_path(self) -> None:
        entries = self.entries()
        for category, path in NAMED_EXCLUSION_PATHS.items():
            with self.subTest(category=category, path=path):
                entry = entries[path]
                self.assertEqual(entry["exclude_reason"], category)
                self.assertFalse(entry["analyzable"])
                self.assertEqual(entry["hunks"], [])

        # The eleventh category is a hunk-level reason, not a file-level one (C38).
        self.assertEqual(self.manifest["pre_existing_total"], 1)
        pre_existing = [
            hunk
            for entry in self.manifest["files"]
            for hunk in entry["hunks"]
            if hunk["provenance"] == "pre_existing"
        ]
        self.assertTrue(pre_existing)
        self.assertEqual({hunk["exclude_reason"] for hunk in pre_existing}, {"pre_existing_change"})
        entry = entries["src/pre_existing.py"]
        self.assertTrue(entry["analyzable"])
        self.assertEqual(entry["analyzed_as"], "pre_existing")
        self.assertIn("src/pre_existing.py", self.manifest["pre_existing_files"])

        # The vocabulary is the contract's closed enumeration, exactly.
        excluded_categories = {
            entry["exclude_reason"] for entry in self.manifest["files"] if not entry["analyzable"]
        }
        self.assertEqual(excluded_categories, set(NAMED_EXCLUSION_PATHS))
        self.assertEqual(self.manifest["excluded_total"], len(NAMED_EXCLUSION_PATHS))
        self.assertEqual(
            set(bm.EXCLUSION_CATEGORIES),
            set(NAMED_EXCLUSION_PATHS) | {"pre_existing_change"},
        )
        self.assertEqual(len(bm.EXCLUSION_CATEGORIES), 11)

    def test_modified_untracked_file_keeps_the_snapshot_baseline(self) -> None:
        entry = self.entries()["notes/open-scratch.md"]
        snapshot_payload = (self.untracked_snapshot / "notes" / "open-scratch.md").read_bytes()
        head_payload = (self.repo / "notes" / "open-scratch.md").read_bytes()
        self.assertNotEqual(snapshot_payload, head_payload)

        self.assertEqual(entry["change_kind"], "modified")
        self.assertEqual(entry["baseline_source"], "untracked_snapshot")
        self.assertEqual(entry["baseline_sha256"], sha256_hex(snapshot_payload))
        self.assertEqual(entry["source_sha256"], sha256_hex(head_payload))
        self.assertTrue(entry["analyzable"])
        self.assertEqual(len(entry["hunks"]), 1)


# --------------------------------------------------------------------------------------
# G-40: the overlapped pre-existing region enters the accounting as a count
# --------------------------------------------------------------------------------------


class OverlappedRegionTests(ScratchCase):
    def test_overlapped_pre_existing_region_is_counted(self) -> None:
        original = "".join(f"line {number}\n" for number in range(1, 13))
        edited_at_open = original.replace("line 2\n", "line 2, edited before the work order opened\n")
        self.write("src/near.txt", original)
        commit = self.commit_all()

        # Dirty at open, then the work order edits a line inside the same -U3 context window.
        self.write("src/near.txt", edited_at_open)
        self.mirror_open_state()
        self.write(
            "src/near.txt",
            edited_at_open.replace("line 4\n", "line 4, edited by the work order\n"),
        )

        manifest = self.build(
            commit,
            worktree_dir=self.worktree_snapshot,
            untracked_dir=self.untracked_snapshot,
        )
        flagged = [
            hunk
            for entry in manifest["files"]
            for hunk in entry["hunks"]
            if hunk["provenance"] == "work_order" and hunk["overlaps_pre_existing"]
        ]
        self.assertEqual(len(flagged), 1, manifest["files"])
        # The counter is where the overlapped region enters the accounting: the region stays
        # attributed to the work order, so it is counted and never becomes an exclusion row.
        self.assertEqual(manifest["overlapped_pre_existing_total"], 1)
        self.assertEqual(manifest["overlapped_pre_existing_total"], len(flagged))
        self.assertEqual(manifest["pre_existing_total"], 0)
        self.assertEqual(manifest["units_total"], 1)


# --------------------------------------------------------------------------------------
# F1/F2/F3/F5: no examined shape may leave `files[]` without a row or a named degradation
# --------------------------------------------------------------------------------------
#
# Adversarial shape verification measured five defects in this enumeration. Each of them
# broke the same promise -- every changed path is either a unit, an excluded row, or a
# recorded degradation that names it -- and each test below fails against the pre-fix code.

# Git spells a path whose name bytes are not valid UTF-8 with U+FFFD, and the borrowed
# spelling cannot be opened. This is the name the F1 shape reaches the builder with.
LOSSY_UNTRACKED_PATH = "src/caf\ufffd_latin1.py"


class ShapeVerificationCase(ScratchCase):
    """Shared fixtures for the shapes adversarial verification measured."""

    def submodule_source(self, name: str = "sub") -> str:
        """A real nested repository plus the revision a `160000` index entry points at."""
        source = self.root / name
        init_repo(source)
        (source / "lib.txt").write_bytes(b"submodule content\n")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "submodule baseline")
        return git(source, "rev-parse", "HEAD").decode().strip()

    def add_gitlink(self, relative: str, revision: str) -> None:
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{revision},{relative}")

    def commit_index(self, message: str = "baseline") -> str:
        """Commit the index as it stands, without staging the worktree.

        `git add -A` is deliberately not used: it stages the *worktree*, and a gitlink whose
        directory is not checked out would be staged as a deletion, so the baseline commit
        would not carry the gitlink the scenario is about.
        """
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD").decode().strip()

    def add_tracked_blob(self, relative: str, payload: bytes) -> None:
        """An index entry whose spelled path has no readable file behind it (F1/F6 shape)."""
        blob = git(self.repo, "hash-object", "-w", "--stdin", stdin=payload).decode().strip()
        git(self.repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}")

    def named_degradations(self, manifest: dict[str, Any], path: str) -> list[str]:
        return [item for item in manifest["degradations"] if path in item]


class UnreadablePathTests(ShapeVerificationCase):
    """F1: an unreadable path is recorded, never dropped without a trace."""

    def test_unreadable_untracked_path_is_recorded_not_dropped(self) -> None:
        """The path git reports but cannot open must still be named in the manifest.

        The seam is the module's git boundary: the untracked enumeration is served the
        lossy spelling git really produces for a non-UTF-8 name, and the path cannot be
        opened through it. The pre-fix builder dropped the path before any row was created
        and recorded nothing at all, so this assertion fails against it.
        """
        self.write("src/keep.py", "value = 1\n")
        commit = self.commit_all()

        payload = LOSSY_UNTRACKED_PATH.encode("utf-8") + b"\x00"
        real_run_git = bm.run_git

        def fake_run_git(repo: Path, args: list[str], allow_one: bool = False) -> bytes:
            if args == ["ls-files", "--others", "--exclude-standard", "-z"]:
                return payload
            return real_run_git(repo, args, allow_one)

        with mock.patch.object(bm, "run_git", fake_run_git):
            manifest = self.build(commit, worktree_dir=None, untracked_dir=None)

        # Nothing was analysable, and the path really is unreadable on this host.
        self.assertEqual(manifest["files"], [])
        self.assertIsNone(bm.read_bytes(self.repo / LOSSY_UNTRACKED_PATH))
        # Silence is the defect: the manifest must name what it could not read.
        self.assertTrue(
            self.named_degradations(manifest, LOSSY_UNTRACKED_PATH),
            manifest["degradations"],
        )

    def test_real_lossy_untracked_name_is_not_silently_dropped(self) -> None:
        """The same shape built for real, on a host that spells such a name lossily.

        A file whose name carries a lone surrogate is created on disk; git reports the
        U+FFFD spelling and cannot open it. The host check is measured rather than
        assumed: a host that round-trips the name legitimately produces no loss, and the
        test skips instead of asserting a shape the host cannot build.
        """
        self.write("src/keep.py", "value = 1\n")
        commit = self.commit_all()

        (self.repo / "src" / "caf\udce9_latin1.py").write_bytes(b"latin1 = 1\n")
        raw = git(self.repo, "ls-files", "--others", "--exclude-standard", "-z")
        spelled = [item for item in raw.split(b"\x00") if item]
        if not any(b"\xef\xbf\xbd" in item for item in spelled):
            self.skipTest("this host round-trips a non-UTF-8 file name; the loss shape cannot exist")

        receipt = self.capture()
        self.assertTrue(receipt["match"])
        self.assertTrue(
            [item for item in receipt["degradations"] if "latin1" in item],
            receipt["degradations"],
        )

        manifest = self.build(commit)
        self.assertEqual(manifest["files"], [])
        self.assertTrue(
            [item for item in manifest["degradations"] if "latin1" in item],
            manifest["degradations"],
        )


class GitlinkShapeTests(ShapeVerificationCase):
    """F2: a `160000` entry is recorded whether or not its worktree path exists."""

    def test_gitlink_without_a_worktree_path_is_recorded(self) -> None:
        """The index entry alone is the change; an absent directory must not hide it.

        Pre-fix the candidate set was built from the commit diff, the untracked listing and
        the untracked snapshot, so a gitlink the index reports and `git diff <commit>` does
        not reached no branch at all: `files[]` stayed empty.
        """
        self.write("src/app.py", "value = 1\n")
        commit = self.commit_all()
        revision = self.submodule_source()
        self.add_gitlink("vendor-sub", revision)
        self.assertFalse((self.repo / "vendor-sub").exists())
        self.assertIn("160000", index_modes(self.repo)["vendor-sub"])

        manifest = self.build(commit)
        entry = self.by_path(manifest)["vendor-sub"]
        self.assertEqual(entry["exclude_reason"], "submodule")
        self.assertFalse(entry["analyzable"])
        self.assertEqual(entry["hunks"], [])
        self.assertEqual(entry["change_kind"], "added")
        self.assertEqual(manifest["excluded_total"], 1)
        # C15: the shape is the change, so the two modes travel with the row.
        self.assertEqual(entry["mode_head"], "160000")
        self.assertEqual(entry["mode_origin"], "")

    def test_removed_gitlink_is_recorded_as_a_deletion(self) -> None:
        """A gitlink the baseline commit holds and the index no longer does is a deletion."""
        self.write("src/app.py", "value = 1\n")
        git(self.repo, "add", "-A")
        revision = self.submodule_source()
        self.add_gitlink("vendor-sub", revision)
        commit = self.commit_index()
        self.assertIn("160000", bm.tree_entries(self.repo, commit)["vendor-sub"]["mode"])
        git(self.repo, "update-index", "--force-remove", "vendor-sub")
        self.assertNotIn("vendor-sub", index_modes(self.repo))

        manifest = self.build(commit)
        entry = self.by_path(manifest)["vendor-sub"]
        self.assertEqual(entry["change_kind"], "deleted")
        self.assertEqual(entry["exclude_reason"], "submodule")
        self.assertTrue(entry["baseline_present"])
        self.assertFalse(entry["head_present"])
        self.assertEqual(entry["mode_origin"], "160000")
        self.assertEqual(entry["mode_head"], "")

    def test_untouched_gitlink_is_not_a_change(self) -> None:
        """Control: the new candidate source is a source of *change*, not of every gitlink."""
        self.write("src/app.py", "value = 1\n")
        git(self.repo, "add", "-A")
        revision = self.submodule_source()
        self.add_gitlink("vendor-sub", revision)
        commit = self.commit_index()

        manifest = self.build(commit)
        self.assertEqual(manifest["files"], [])
        self.assertEqual(manifest["units_total"], 0)
        # The two snapshot states are missing here by construction; what must not appear is a
        # per-path note, whose form is `<reason>:<path>`.
        self.assertEqual([item for item in manifest["degradations"] if ":" in item], [])

        # ... and a moved pointer is a change, in the same repository.
        moved = self.submodule_source("sub2")
        self.add_gitlink("vendor-sub", moved)
        manifest = self.build(commit)
        entry = self.by_path(manifest)["vendor-sub"]
        self.assertEqual(entry["change_kind"], "modified")
        self.assertEqual(entry["exclude_reason"], "submodule")
        self.assertTrue(entry["baseline_present"])
        self.assertTrue(entry["head_present"])
        self.assertEqual(entry["mode_origin"], "160000")
        self.assertEqual(entry["mode_head"], "160000")


class UntrackedSnapshotLossTests(ShapeVerificationCase):
    """F3: a deleted untracked-at-open path leaves a named record when the snapshot is gone."""

    def test_deleted_untracked_path_survives_a_lost_snapshot(self) -> None:
        """The open state is the only witness once the C4a directory is removed.

        Pre-fix the path appeared in no candidate set at all -- it is neither tracked nor
        untracked any more and the directory that held it is gone -- so `files[]` was empty
        and the only note was the generic, pathless `baseline_untracked_snapshot_missing`.
        """
        self.write("src/app.py", "value = 1\n")
        commit = self.commit_all()
        self.write("notes/open-scratch.md", "untracked at open\n")

        receipt = self.capture()
        self.assertEqual(receipt["untracked_files"], 1)
        # The control's copy is taken before the directory is removed: the point of the test
        # is that the same repository still analyses the deletion when the snapshot is there.
        control_root = self.root / "control"
        shutil.copytree(self.workbench / "tmp" / "baseline-untracked", control_root)
        (self.repo / "notes" / "open-scratch.md").unlink()
        shutil.rmtree(self.untracked_snapshot)

        manifest = self.build(commit)
        self.assertEqual(manifest["files"], [])
        self.assertIn("baseline_untracked_snapshot_missing", manifest["degradations"])
        # The loss must be specific: the path that was untracked at open is named.
        self.assertIn(
            "untracked_snapshot_path_lost:notes/open-scratch.md", manifest["degradations"]
        )

        # Control: the same repository with the snapshot intact still analyses the deletion,
        # so the assertion above measures the lost snapshot and not a rule that never fires.
        control = self.build(commit, untracked_dir=control_root)
        self.assertEqual([entry["change_kind"] for entry in control["files"]], ["deleted"])
        self.assertEqual(control["units_total"], 1)
        self.assertEqual(control["degradations"], [])


class ShapeProvenanceTests(ShapeVerificationCase):
    """F5: the open state decides who made a mode-only change."""

    def test_pre_existing_mode_flip_is_not_charged_to_the_work_order(self) -> None:
        """A flip already present at open belongs to the baseline side, not to the author.

        The index mode is the whole evidence for this shape, so the open state has to record
        it: the file's bytes never change, and the baseline commit records only the mode it
        was committed with. Pre-fix every mode-only change was `analyzed_as=work_order`.
        """
        git(self.repo, "config", "core.fileMode", "false")
        self.write("src/app.py", "value = 1\n")
        self.write("tools/run.sh", "#!/bin/sh\necho run\n")
        commit = self.commit_all()

        # The pre-existing flip: made before the capture, so it is already in the index at open.
        git(self.repo, "update-index", "--chmod=+x", "src/app.py")
        self.capture()
        # The work order's own flip, after the open state was recorded.
        git(self.repo, "update-index", "--chmod=+x", "tools/run.sh")

        manifest = self.build(commit)
        entries = self.by_path(manifest)
        self.assertEqual(
            sorted(entries), ["src/app.py", "tools/run.sh"]
        )
        self.assertEqual(entries["src/app.py"]["exclude_reason"], "mode_change")
        self.assertEqual(entries["tools/run.sh"]["exclude_reason"], "mode_change")

        # The attribution is what the fix is about.
        self.assertEqual(entries["src/app.py"]["analyzed_as"], "pre_existing")
        self.assertEqual(entries["tools/run.sh"]["analyzed_as"], "work_order")
        self.assertIn("src/app.py", manifest["pre_existing_files"])
        self.assertNotIn("tools/run.sh", manifest["pre_existing_files"])

        # C6a: an excluded path carries no hunks, so the exclusion equation is unmoved.
        self.assertEqual(manifest["excluded_total"], 2)
        self.assertEqual(manifest["pre_existing_total"], 0)

        # The three modes are the statement the row makes, and they are now recorded.
        pre_existing = entries["src/app.py"]
        self.assertEqual(pre_existing["mode_origin"], "100644")
        self.assertEqual(pre_existing["mode_open"], "100755")
        self.assertEqual(pre_existing["mode_head"], "100755")
        work_order = entries["tools/run.sh"]
        self.assertEqual(work_order["mode_origin"], "100644")
        self.assertEqual(work_order["mode_open"], "100644")
        self.assertEqual(work_order["mode_head"], "100755")


if __name__ == "__main__":
    unittest.main()
