#!/usr/bin/env python3
"""Capture the work-order open state, and verify a recorded open state later.

The coverage protocol fixes the baseline as one digest over the tracked paths as they
existed in the worktree when the work order opened, and requires that a third party can
recompute it. This script produces that state and the record that publishes it:

* the tracked paths whose worktree bytes differ from the baseline commit's bytes at open
  (the **dirty-at-open** set) are mirrored into a worktree snapshot directory;
* every path that was untracked at open is mirrored into an untracked snapshot directory;
* a tracked path **absent** from the worktree at open is recorded as a name, not mirrored:
  an absent path is a fact about the open state, not a missing byte to snapshot, and it
  contributes no record to the digest because it had no bytes on any side;
* every remaining tracked path is **clean** at open, so its open bytes *are* the baseline
  commit's bytes and version control already holds them. They are recomputed from the
  commit, never copied;
* `<workbench>/tmp/baseline-open-state.json` records the work order id, the capture time,
  the baseline commit, the algorithm, the three path counts, the two snapshot directories,
  the capture scope and the digest.

The digest construction is **not** re-implemented here. `digest_from_hashes` and
`sort_key` are imported from `build_manifest`, the module that owns the package's digest
algorithm, and so is the single definition of the digest's **input set**: the role map
`open_state_roles` gives one role to each tracked path -- `snapshot`, `commit`, or `omitted`
for a path with no readable open-state bytes -- and `open_state_hashes` turns that map into the
records. This script's capture mode, its `--verify-existing` mode, the manifest's baseline
side and the validator's V15 all read that one map, so the four cannot disagree about which
paths are hashed or with what. The published `expected_digest` keeps exactly its old value
semantics -- one digest over the open-state bytes of every tracked path that had any -- and
only its **recomputation source** becomes hybrid: snapshot bytes for a dirty path, the
baseline commit's blob for a clean path.

An open state is more than its bytes. Five of the facts the manifest needs later cannot be
recovered once the capture has run, so the record carries them as well:

* `untracked_paths` -- the names that were untracked at open (C4a). Without them a path
  that was untracked at open and has since been deleted is unrecoverable when the
  untracked directory is gone, and the manifest could only report a pathless note;
* `index_modes` -- the index mode of every path at open. A mode-only change leaves no
  trace in any content, so the baseline commit's mode and the current index mode cannot
  say whether the flip happened before or after the work order opened;
* `degradations` -- the tracked or untracked paths this capture could not open, named. A
  `160000` gitlink's worktree path is a directory and a path whose name bytes are not valid
  UTF-8 cannot be opened under the spelling git reports, and neither may be fatal: a work
  order that cannot record its open state cannot be opened at all. A skipped path is named,
  it contributes no record to the digest, and the run continues;
* `dirty_paths` -- the tracked paths whose open bytes differ from the baseline commit's
  bytes. This is the mirror's frozen capture scope: it is what lets a later step
  recompute the C4 digest from the snapshot **plus the commit** instead of assuming the
  snapshot mirrors every tracked path, and it is what keeps "clean at open"
  distinguishable from "the mirror was pruned";
* `deleted_paths` -- the tracked paths that were absent from the worktree at open. The
  fact is the absence, so the name is recorded and no bytes are invented for it.

Two modes:

* capture (default) materialises both snapshot directories under the workbench's `tmp/`
  and writes the open-state record;
* `--verify-existing` selects that record by `--work-order-id`, recomputes the digest from
  the **recorded** snapshot directories plus the baseline commit's blobs, and compares it
  with the record's `expected_digest`. It captures nothing, re-materialises nothing, and
  refreshes only `recomputed_digest` and `match` on a successful comparison. A record with
  no commit -- the consent-carrying full copy -- is verified from its snapshot alone and
  consults no version control.

Two boundaries this script states instead of hiding:

* the proportional mirror no longer lets a third party recompute the C4 digest from the
  snapshot directory **alone**: the baseline commit's objects are now a real precondition,
  because they are where a clean path's open bytes live. When the commit can no longer
  supply them the digest is not recomputable, and the protocol names that degradation
  (`baseline_worktree_snapshot_commit_unavailable:<commit>`);
* where version control cannot supply the baseline side of a clean tracked path -- the
  directory is not a worktree, `HEAD` does not resolve, or it resolves to a commit this tool
  cannot read -- the capture **fails closed** with the one named error
  `baseline_vcs_unavailable` and copies nothing. The one way to authorise the full
  tracked-set mirror there is `--full-tracked-mirror` together with a non-empty
  `--consent-reference` that names the explicit user decision it carries; without both,
  nothing is copied. That record is a content mirror for a tree with no baseline commit, so
  `--verify-existing` reproduces its digest but `build_manifest.py`, which enumerates a
  change set against a baseline commit, cannot build a report from it.

`--format keys` prints the publishable blackboard lines instead of the JSON receipt: the
three flat baseline keys the report group's caller must publish before the group runs.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_manifest import (  # noqa: E402
    DIGEST_ALGORITHM,
    GitBlobStore,
    ManifestError,
    OPEN_STATE_OMITTED,
    TRACKED_PATH_UNREADABLE,
    UNTRACKED_PATH_UNREADABLE,
    digest_from_hashes,
    index_entries,
    open_state_hashes,
    open_state_roles,
    open_state_scope,
    path_note,
    read_bytes,
    record_capture_scope,
    require_commit,
    resolve_repo,
    run_git,
    sha256_hex,
    snapshot_paths,
    sort_key,
    tracked_paths,
    tree_entries,
    untracked_paths,
)

# --------------------------------------------------------------------------------------
# The open-state record: one path, one work order, a frozen core field set.
# --------------------------------------------------------------------------------------

RECORD_KIND = "open-state-content-snapshot"
# The frozen core set. Every one of these is required, in every mode, and a record that
# carries only these still loads: the three open-state facts below were added after the
# first captures and are read as optional so an existing record stays verifiable.
RECORD_FIELDS = (
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
# The open-state facts no later step can recover, written by capture and tolerated as
# absent on read (F1, F3, F5, F6 of the adversarial shape verification, plus the capture
# scope). `dirty_paths` is the mirror's frozen capture scope: a reader that has it must
# never assume the snapshot mirrors every tracked path. A record that carries only the
# core fields is read as an unpruned, full mirror -- the shape an older capture produced.
RECORD_OPEN_STATE_FIELDS = (
    "untracked_paths",
    "index_modes",
    "degradations",
    "dirty_paths",
    "deleted_paths",
)

RECORD_NAME = "baseline-open-state.json"
WORKTREE_SNAPSHOT_NAME = "baseline-worktree"
UNTRACKED_SNAPSHOT_NAME = "baseline-untracked"

# The named error raised when a directory has no version control that can supply the
# baseline side. It is a failure, not a degradation: there is nothing to capture a clean
# path from, so the run stops before it copies anything.
VCS_UNAVAILABLE = "baseline_vcs_unavailable"

# The publishable blackboard lines, in publication order. `report.baseline_algorithm` is a
# declaration-only line: no node inside the group reads it, but the caller publishes it so
# the recorded algorithm travels with the recorded digest.
KEY_COMMIT = "report.baseline_commit"
KEY_DIGEST = "report.baseline_digest"
KEY_ALGORITHM = "report.baseline_algorithm"


def record_path(workbench: Path) -> Path:
    """`<workbench>/tmp/baseline-open-state.json` -- the one path both modes use."""
    return workbench / "tmp" / RECORD_NAME


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_from_snapshot(directory: Path, paths: Iterable[str]) -> str:
    """Recompute the package's baseline digest from files under a snapshot directory.

    Both modes call this one function, so a capture can never publish a digest its own
    verification mode would not reproduce. `digest_from_hashes` orders the records.
    """
    pairs: list[tuple[str, str]] = []
    for path in paths:
        payload = read_bytes(directory / Path(path))
        if payload is None:
            raise ManifestError(f"snapshot file is missing or unreadable: {path}")
        pairs.append((path, sha256_hex(payload)))
    return digest_from_hashes(pairs)


def _digest_of_open_state_hashes(
    repo: Path,
    commit: str,
    directory: Path,
    roles: dict[str, str],
    blobs: GitBlobStore | None = None,
    oids: dict[str, str] | None = None,
) -> tuple[str, list[str], list[str]]:
    """C4's digest from `build_manifest`'s one role map, for both modes of this script.

    The digest's input set and the bytes each path contributes are defined once, in
    `build_manifest.open_state_roles` / `open_state_hashes`; this wrapper only names the
    failure text for the two ways a source can be short. A path the scope says the snapshot
    holds whose mirrored bytes are missing, and a clean path the baseline commit can no longer
    supply, are both failures here rather than silent empty hashes: the first is a damaged
    capture, the second is the C4b precondition the protocol names
    (`baseline_worktree_snapshot_commit_unavailable`). A clean path is read from the object
    database by the blob id `tree_entries` already resolved for it, through the caller's batched
    reader when it has one, because a `git show <commit>:<path>` argument is a *worktree*
    spelling that the host path limit can defeat on a path whose bytes are intact.
    """
    pairs, missing, commit_short = open_state_hashes(
        repo, commit, directory, roles, blobs=blobs, oids=oids
    )
    if missing:
        raise ManifestError(f"snapshot file is missing or unreadable: {missing[0]}")
    if commit_short:
        raise ManifestError(
            "baseline_worktree_snapshot_commit_unavailable: the baseline commit "
            f"{commit or '<none>'} cannot supply the clean path {commit_short[0]}, so the C4 "
            "digest is not recomputable from this snapshot"
        )
    return digest_from_hashes(pairs), missing, commit_short


def _materialise(directory: Path, path: str, payload: bytes) -> None:
    target = directory / Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def _worktree_bytes(repo: Path, path: str) -> bytes | None:
    """A tracked path's worktree bytes at open, with a symlink read as its target text.

    `read_bytes` follows a symlink, so `link -> text` would be compared against the link's
    target content instead of the link's own bytes. The baseline commit's blob for a
    `120000` entry *is* the target text, so the worktree side is read the same way here.
    """
    candidate = repo / Path(path)
    if candidate.is_symlink():
        try:
            return str(candidate.readlink()).encode("utf-8", "surrogateescape")
        except OSError:
            return None
    return read_bytes(candidate)


def _full_copy_files(repo: Path) -> list[str]:
    """Every file outside `.git` in a tree with no usable version control.

    This is the entire content of the full-copy opt-in: with no version control there is no
    clean-path source, so the only faithful capture is every path. `.git` is skipped
    because it is the version-control store itself, not worktree content.
    """
    found: list[str] = []
    for item in sorted(repo.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(repo)
        if relative.parts and relative.parts[0] == ".git":
            continue
        found.append(relative.as_posix())
    return found


def _resolve_capture_repo(
    repo_path: Path,
    full_copy: bool,
    consent_reference: str,
) -> tuple[Path, bool, str]:
    """Resolve the repository, its baseline commit, and whether version control can supply it.

    Returns `(repo, filesystem_scope, head)`. The fail-closed class is **every** way version
    control can fail to supply the baseline side of a clean tracked path: the directory is not a
    worktree, the repository has no commit `HEAD` resolves to, or `HEAD` does not resolve to a
    commit this tool can read. All of them raise the one named error, so
    `baseline_vcs_unavailable` covers the class the contract promises instead of only its first
    member. The full-worktree mirror is reachable only through the explicit opt-in and only with
    a non-empty consent reference that records the user decision it carries; no configuration
    file, key or environment variable takes part.
    """
    if not repo_path.is_dir():
        raise ManifestError(f"repository path does not exist: {repo_path}")
    try:
        repo = resolve_repo(repo_path)
        head = run_git(repo, ["rev-parse", "HEAD"]).decode("utf-8", "replace").strip()
        require_commit(repo, head)
        return repo, False, head
    except ManifestError as exc:
        if not full_copy:
            raise ManifestError(
                f"{VCS_UNAVAILABLE}: version control at {repo_path} cannot supply the baseline "
                "bytes of a clean tracked path, and this capture will not copy content to "
                f"compensate ({exc}). The proportional capture is impossible here; the full "
                "tracked-set mirror is available only with --full-tracked-mirror and a "
                "non-empty --consent-reference naming the explicit user decision that "
                "authorises it."
            ) from None
        if not consent_reference.strip():
            raise ManifestError(
                f"{VCS_UNAVAILABLE}: --full-tracked-mirror requires a non-empty "
                "--consent-reference; without it nothing is copied"
            ) from None
        return repo_path, True, ""


def _git_capable(repo: Path) -> bool:
    """Whether a git index read is meaningful: a `.git` marker exists in the tree."""
    return (repo / ".git").exists()


def _index_entries_if_git(repo: Path, filesystem_scope: bool) -> dict[str, dict[str, str]]:
    """The index modes at open, or none when the tree carries no git state at all."""
    return index_entries(repo) if not filesystem_scope and _git_capable(repo) else {}


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # `ensure_ascii=True` is what makes the recorded path names serialisable: the
    # surrogate-escaped decoding of a path whose bytes are not valid UTF-8 has no UTF-8
    # encoding, so an ASCII-only document with `\udcXX` escapes is the form that survives
    # the round trip. `json.loads` restores the same string, so the digest, the counts and
    # the names are unaffected.
    path.write_bytes((json.dumps(record, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))


def _require_workbench(workbench: Path) -> None:
    if not workbench.is_dir():
        raise ManifestError(f"workbench directory does not exist: {workbench}")


def _captured_at_of_existing_record(path: Path, work_order_id: str) -> str:
    """The capture time already recorded for this work order, if there is one.

    The record's `captured_at` is the time the open-state snapshot was first materialised,
    and no mode rewrites it; a repeat capture of the same state therefore rewrites the
    record byte-identically.
    """
    if not path.is_file():
        return ""
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(existing, dict) or str(existing.get("work_order_id", "")) != work_order_id:
        return ""
    return str(existing.get("captured_at", "") or "")


def _load_record(path: Path, work_order_id: str) -> dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"baseline_record_missing: no open-state record at {path}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(
            f"baseline_record_missing: open-state record is unreadable at {path}: {exc}"
        ) from exc
    if not isinstance(record, dict):
        raise ManifestError(f"baseline_record_missing: record at {path} is not a JSON object")
    selected = str(record.get("work_order_id", "") or "")
    if selected != work_order_id:
        raise ManifestError(
            "baseline_record_unselected: record at "
            f"{path} names work order {selected!r}, not {work_order_id!r}"
        )
    for field in RECORD_FIELDS:
        if field not in record:
            raise ManifestError(f"open-state record at {path} has no {field!r} field")
    return record


def _snapshot_dir(override: Path | None, recorded: Any, default: Path) -> Path:
    """An explicit parameter wins, then the recorded directory, then the workbench default."""
    if override is not None:
        return override
    if str(recorded or ""):
        return Path(str(recorded))
    return default


def published_key_lines(record: dict[str, Any]) -> list[str]:
    return [
        f"{KEY_COMMIT}={record['head']}",
        f"{KEY_DIGEST}={record['expected_digest']}",
        f"{KEY_ALGORITHM}={record['algorithm']}",
    ]


def capture_open_state(
    repo_path: Path,
    workbench: Path,
    work_order_id: str,
    worktree_dir: Path | None,
    untracked_dir: Path | None,
    full_copy: bool = False,
    consent_reference: str = "",
) -> tuple[dict[str, Any], Path]:
    """Mirror the open state proportionally, publish its digest, and write the record.

    Only what version control cannot reproduce is mirrored: the dirty-at-open tracked paths
    and the untracked-at-open paths. A clean tracked path is recomputed from the baseline
    commit, which already holds its bytes, and a deleted-at-open path is recorded as a name
    instead of being mirrored.
    """
    repo, filesystem_scope, head = _resolve_capture_repo(repo_path, full_copy, consent_reference)
    _require_workbench(workbench)

    index: dict[str, dict[str, str]] = {}
    origin_blobs: dict[str, str] = {}
    if filesystem_scope:
        # The full-copy opt-in: no version control, so every file is content that exists
        # nowhere else. `head` stays empty and every path is mirrored.
        committed = set(_full_copy_files(repo))
    else:
        committed = tracked_paths(repo, head)
        index = _index_entries_if_git(repo, filesystem_scope)
        origin_blobs = {
            item: str(entry.get("sha", "")) for item, entry in tree_entries(repo, head).items()
        }

    path = record_path(workbench)
    target_worktree = _snapshot_dir(worktree_dir, "", workbench / "tmp" / WORKTREE_SNAPSHOT_NAME)
    target_untracked = _snapshot_dir(
        untracked_dir, "", workbench / "tmp" / UNTRACKED_SNAPSHOT_NAME
    )

    tracked = sorted(committed, key=sort_key)
    untracked = sorted(untracked_paths(repo) if not filesystem_scope else [], key=sort_key)

    # Both directories are materialised even when they hold nothing. A clean open state is an
    # *empty* snapshot, not a missing one, and the two have to stay distinguishable: a missing
    # directory is the C4a/C4b degradation, while an empty one is the faithful record of a
    # capture that found nothing to mirror because the commit already held every tracked byte.
    target_worktree.mkdir(parents=True, exist_ok=True)
    target_untracked.mkdir(parents=True, exist_ok=True)

    # One hash per tracked path that has readable open-state bytes. A path with none -- absent
    # from the worktree at open, or present but unopenable -- contributes no record at all, and
    # the digest below is built from exactly this map. That map and the scope derived from the
    # same loop are the one definition of the digest's input set.
    hashed: dict[str, str] = {}
    dirty: list[str] = []
    deleted: list[str] = []
    unreadable: list[str] = []
    degradations: list[str] = []
    # Every commit-side read in this function goes through one `cat-file --batch` process keyed
    # by the blob id `tree_entries` resolved, never through `git show <commit>:<path>`: that
    # argument is resolved as a worktree spelling, so the host path limit defeats it on a path
    # whose bytes are intact, and it costs one process per tracked path.
    blobs = GitBlobStore(repo)
    try:
        for relative in tracked:
            payload = _worktree_bytes(repo, relative)
            if payload is None:
                if not filesystem_scope and not (repo / Path(relative)).exists():
                    # The tracked path is absent from the worktree at open. That absence is the
                    # fact; there are no open bytes to mirror, and the path contributes nothing to
                    # the digest on any side -- exactly as a byte-less path always did. A directory
                    # at the path -- a gitlink that was never checked out -- is absence of bytes
                    # too, and is recorded here rather than as an unreadable file.
                    deleted.append(relative)
                    continue
                # A gitlink's worktree path is a directory and a name git spells lossily cannot
                # be opened. Neither is fatal: the path is named, it stays out of the snapshot,
                # and the work order is not blocked at open (C4b degrades instead). It is out of
                # the digest on both sides, which is the pre-existing C4 behaviour: a gitlink's
                # "content" is a commit id and has no bytes to hash.
                degradations.append(path_note(TRACKED_PATH_UNREADABLE, relative))
                unreadable.append(relative)
                continue
            # The baseline side is the *commit's* blob for this path, not the index entry: a
            # staged edit changes the index blob, so an index comparison would call a path clean
            # whose worktree bytes differ from the recorded baseline commit. A gitlink has no blob
            # at all, so it has no comparable baseline content and is treated as no origin.
            origin = blobs.get(origin_blobs.get(relative, ""))
            if filesystem_scope or origin is None or origin != payload:
                _materialise(target_worktree, relative, payload)
                dirty.append(relative)
            hashed[relative] = sha256_hex(payload)

        # The digest published at open keeps its exact old value semantics: one C4 digest over the
        # open-state bytes of every tracked path that had any. Only the *source* of those bytes is
        # hybrid -- a dirty path's bytes come from the snapshot just materialised, and a clean
        # path's bytes are the baseline commit's own. The scope frozen here is what the record
        # publishes and what every later recomputation reads through the one role map.
        scope = open_state_scope(dirty, deleted, unreadable)
        roles = open_state_roles(tracked, scope)
        digest_paths = {path for path, role in roles.items() if role != OPEN_STATE_OMITTED}
        if digest_paths != set(hashed):
            # Neither derivation is authoritative on its own, so a disagreement is fatal instead of
            # a silent choice between two input sets.
            raise ManifestError(
                "the capture's own classification disagrees with the digest's input set: only "
                f"captured {sorted(set(hashed) - digest_paths)[:3]}, only digestible "
                f"{sorted(digest_paths - set(hashed))[:3]}"
            )
        expected_digest = digest_from_hashes(
            sorted(hashed.items(), key=lambda item: sort_key(item[0]))
        )
        # The self-check recomputes the same digest the way a third party must: from the recorded
        # snapshot plus the commit, through the same role map -- the snapshot's own files for the
        # dirty set and the commit's blobs for the clean one. A capture can therefore never
        # publish a digest its own verification mode would not reproduce, and the check still
        # reads the mirror rather than trusting the loop above.
        recomputed_digest, _, _ = _digest_of_open_state_hashes(
            repo, head, target_worktree, roles, blobs=blobs, oids=origin_blobs
        )
        if expected_digest != recomputed_digest:
            raise ManifestError(
                "captured snapshot does not reproduce the baseline digest: "
                f"computed {expected_digest}, recomputed {recomputed_digest}"
            )
    finally:
        blobs.close()

    for relative in untracked:
        payload = _worktree_bytes(repo, relative)
        if payload is None:
            degradations.append(path_note(UNTRACKED_PATH_UNREADABLE, relative))
            continue
        _materialise(target_untracked, relative, payload)

    captured_at = _captured_at_of_existing_record(path, work_order_id) or _now_utc()
    record: dict[str, Any] = {
        "kind": RECORD_KIND,
        "work_order_id": work_order_id,
        "captured_at": captured_at,
        "head": head,
        "algorithm": DIGEST_ALGORITHM,
        "tracked_files": len(tracked),
        "copied_files": len(dirty),
        "untracked_files": len(untracked),
        "untracked_paths": list(untracked),
        "index_modes": {
            item: str(index[item].get("mode", "")) for item in sorted(index, key=sort_key)
        },
        "dirty_paths": list(dirty),
        "deleted_paths": list(deleted),
        "expected_digest": expected_digest,
        "recomputed_digest": recomputed_digest,
        "match": expected_digest == recomputed_digest,
        "worktree_snapshot": str(target_worktree),
        "untracked_snapshot": str(target_untracked),
        "degradations": list(degradations),
    }
    if filesystem_scope:
        # The full-copy opt-in carries its authorisation into the record, so a reviewer reads
        # *what* authorised a whole-worktree mirror and not merely that one happened.
        record["consent_reference"] = consent_reference.strip()
    _write_record(path, record)
    return record, path


def verify_open_state(
    repo_path: Path,
    workbench: Path,
    work_order_id: str,
    worktree_dir: Path | None,
    untracked_dir: Path | None,
    scope: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    """Recompute the recorded digest from the frozen capture scope plus the commit.

    `scope` is the capture scope the caller already parsed from the record, or `None` to read
    it here. An explicit mapping is a pruned capture whose dirty set is known; `None` reads the
    record, where an absent `dirty_paths` key means "this record never pruned" -- the
    pre-capture record shape and the full-mirror opt-in -- and the snapshot's own contents then
    stand in for the frozen captured set. A record that froze `dirty_paths` is verified against
    exactly that list, so a proportional snapshot is never mistaken for a damaged one. A record
    with no commit (`head` empty) is the consent-carrying full copy of C4c: the snapshot is the
    whole open state, no version control is consulted, and this mode is what makes that
    record's own digest verifiable.
    """
    path = record_path(workbench)
    record = _load_record(path, work_order_id)

    if str(record["algorithm"]) != DIGEST_ALGORITHM:
        raise ManifestError(
            "open-state record declares algorithm "
            f"{record['algorithm']!r}, which this tool cannot recompute"
        )

    recorded_worktree = _snapshot_dir(
        worktree_dir, record["worktree_snapshot"], workbench / "tmp" / WORKTREE_SNAPSHOT_NAME
    )
    recorded_untracked = _snapshot_dir(
        untracked_dir, record["untracked_snapshot"], workbench / "tmp" / UNTRACKED_SNAPSHOT_NAME
    )

    if not recorded_worktree.is_dir():
        raise ManifestError(f"baseline worktree snapshot directory is missing: {recorded_worktree}")
    captured = set(snapshot_paths(recorded_worktree))

    head = str(record["head"])
    origin_blobs: dict[str, str] = {}
    if head:
        repo = resolve_repo(repo_path)
        require_commit(repo, head)
        # The commit's tree is read once: its keys are the tracked set C4's digest is defined
        # over, and its blob ids are what the clean-path half of that digest is recomputed from.
        tree = tree_entries(repo, head)
        tracked = sorted(tree, key=sort_key)
        origin_blobs = {path: str(entry.get("sha", "")) for path, entry in tree.items()}
    else:
        # The consent-carrying full copy recorded no commit (C4c): there is no tracked set and
        # no baseline commit, so no version control is consulted at all and the snapshot is the
        # whole open state. That is what makes the record this capture wrote verifiable by the
        # mode that wrote it, instead of unreadable by its own tool.
        repo = repo_path
        tracked = sorted(captured, key=sort_key)

    if scope is None:
        frozen = record_capture_scope(record)
        # An unpruned record is an older capture, which mirrored every tracked path; a
        # proportional one froze the scope itself, and the presence of `dirty_paths` is what
        # separates the two.
        full_mirror = frozen["dirty"] is None
    else:
        frozen = open_state_scope(
            scope.get("dirty", []) or [],
            scope.get("deleted", []) or [],
            scope.get("skipped", []) or [],
        )
        # An explicit mapping is a pruned capture with a known dirty set, never an unpruned one:
        # only "no scope at all" (the default) reads the record and may mean a full mirror.
        full_mirror = False

    if full_mirror:
        # This tool can no longer tell whether such a record's snapshot is complete, because a
        # capture that ran after this change legitimately holds only the dirty set; so "the
        # recorded digest is the digest of the current open state" is the comparison that
        # decides, and the alignment direction is the one that stays valid either way: every
        # captured path must be tracked at `head` and absent from no side. A path the snapshot
        # simply does not hold is supplied by the commit, which is how the digest below reads
        # it.
        missing = []
        unexpected = sorted(captured - set(tracked), key=sort_key)
    else:
        # A proportional record: the frozen list is the authority, and every other tracked
        # path is supplied by the baseline commit (or was absent at open). Both directions are
        # checked, because the snapshot's own silent completeness is exactly what the frozen
        # scope replaced.
        expected = set(frozen["dirty"])
        missing = sorted(expected - captured, key=sort_key)
        unexpected = sorted(captured - expected, key=sort_key)
    if missing or unexpected:
        raise ManifestError(
            "baseline worktree snapshot does not mirror the tracked path set at "
            f"{head}: missing {len(missing)} ({missing[:3]}), unexpected "
            f"{len(unexpected)} ({unexpected[:3]})"
        )

    untracked_captured = snapshot_paths(recorded_untracked)
    for field, actual in (
        ("tracked_files", len(tracked)),
        ("copied_files", len(captured)),
        ("untracked_files", len(untracked_captured)),
    ):
        if int(record[field]) != actual:
            raise ManifestError(
                f"open-state record {field}={record[field]} does not match the snapshot: {actual}"
            )

    # The digest is recomputed from what the snapshot actually holds plus the baseline
    # commit's blobs, through the same role map the capture used, so a record can never fail
    # the verification of the mode that wrote it. A path dropped from the snapshot after the
    # capture changes the recomputed digest and still fails below. An unpruned or commit-less
    # record has no commit-supplied set of its own: every path the snapshot holds is a snapshot
    # path, and there is nothing else to read from.
    if full_mirror or not head:
        roles = open_state_roles(tracked, open_state_scope(captured, [], frozen["skipped"]))
    else:
        roles = open_state_roles(tracked, frozen)
    # The clean-path half is read from the object database by the blob ids the commit's tree
    # already resolves, through one batched reader: this mode recomputes the digest for a
    # snapshot that deliberately did not copy those bytes, so it must not depend on a worktree
    # spelling the host path limit can defeat.
    blobs = GitBlobStore(repo) if head else None
    try:
        digest, _, _ = _digest_of_open_state_hashes(
            repo, head, recorded_worktree, roles, blobs=blobs, oids=origin_blobs
        )
    finally:
        if blobs is not None:
            blobs.close()
    expected_digest = str(record["expected_digest"])
    if digest != expected_digest:
        raise ManifestError(
            f"baseline digest mismatch: expected {expected_digest}, recomputed {digest}"
        )

    # A successful comparison refreshes these two fields only: the digest published at open
    # and the materialised snapshot stay exactly as they were recorded.
    record["recomputed_digest"] = digest
    record["match"] = True
    _write_record(path, record)
    return record, path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture the xc-change-report work-order open state, or verify the state "
        "recorded at open."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workbench", required=True)
    parser.add_argument("--work-order-id", required=True)
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="Recompute the digest from the recorded snapshot directories instead of capturing.",
    )
    parser.add_argument(
        "--full-tracked-mirror",
        action="store_true",
        help=(
            "Authorise mirroring every worktree path instead of only what version control "
            "cannot reproduce. It is the one opt-in for a tree whose version control cannot "
            "supply the baseline side, and it requires --consent-reference; without both, "
            "nothing is copied. The record it writes names the mirror and the consent it "
            "carries, and --verify-existing reproduces its digest, but no validated change "
            "report can be produced from it: build_manifest.py enumerates a change set against "
            "a baseline commit, which such a tree does not have."
        ),
    )
    parser.add_argument(
        "--consent-reference",
        default="",
        help=(
            "The explicit user decision that carries --full-tracked-mirror. Recorded in the "
            "open-state record as consent_reference so a reviewer can see what authorised "
            "the full copy."
        ),
    )
    parser.add_argument(
        "--baseline-worktree-dir",
        default="",
        help="Tracked-path snapshot directory; defaults to <workbench>/tmp/baseline-worktree.",
    )
    parser.add_argument(
        "--baseline-untracked-dir",
        default="",
        help="Untracked-path snapshot directory; defaults to <workbench>/tmp/baseline-untracked.",
    )
    parser.add_argument("--format", default="json", choices=("json", "keys"))
    args = parser.parse_args(argv)

    mode = "verify" if args.verify_existing else "capture"
    # Every attribute name maps to the parameter of the same name in either mode, so the one
    # call below covers both and only the capture mode reads the two consent attributes.
    options = {
        "repo_path": Path(args.repo),
        "workbench": Path(args.workbench),
        "work_order_id": args.work_order_id,
        "worktree_dir": Path(args.baseline_worktree_dir) if args.baseline_worktree_dir else None,
        "untracked_dir": Path(args.baseline_untracked_dir) if args.baseline_untracked_dir else None,
    }
    if not args.verify_existing:
        options["full_copy"] = args.full_tracked_mirror
        options["consent_reference"] = args.consent_reference
    try:
        record, path = (verify_open_state if args.verify_existing else capture_open_state)(**options)
    except (ManifestError, OSError) as exc:
        # `ensure_ascii=True` keeps the payload printable on a console whose encoding cannot
        # represent a path this tool is reporting: a path that is not valid UTF-8 reaches an
        # error message as a replacement character or a lone surrogate, and `print` would
        # then raise UnicodeEncodeError *instead of* reporting the failure.
        print(json.dumps({"ok": False, "mode": mode, "error": str(exc)}, ensure_ascii=True, indent=2))
        return 1

    if args.format == "keys":
        for line in published_key_lines(record):
            print(line)
    else:
        receipt: dict[str, Any] = {"ok": True, "mode": mode, "record": str(path)}
        receipt.update(record)
        print(json.dumps(receipt, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
