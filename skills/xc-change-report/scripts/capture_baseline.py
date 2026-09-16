#!/usr/bin/env python3
"""Capture the work-order open state, and verify a recorded open state later.

The coverage protocol fixes the baseline as one digest over the tracked paths as they
existed in the worktree when the work order opened, and requires that a third party can
recompute it. This script produces that state and the record that publishes it:

* every tracked path is mirrored into a worktree snapshot directory;
* every untracked path is mirrored into an untracked snapshot directory;
* `<workbench>/tmp/baseline-open-state.json` records the work order id, the capture time,
  the baseline commit, the algorithm, the three path counts, the two snapshot directories
  and the digest.

The digest construction is **not** re-implemented here. `digest_from_hashes` and
`sort_key` are imported from `build_manifest`, the module that owns the package's digest
algorithm, so the baseline digest, the manifest's head digest and the validator's
recomputation cannot drift apart.

An open state is more than its bytes. Three of the facts the manifest needs later cannot
be recovered once the capture has run, so the record carries them as well:

* `untracked_paths` -- the names that were untracked at open (C4a). Without them a path
  that was untracked at open and has since been deleted is unrecoverable when the
  untracked directory is gone, and the manifest could only report a pathless note;
* `index_modes` -- the index mode of every path at open. A mode-only change leaves no
  trace in any content, so the baseline commit's mode and the current index mode cannot
  say whether the flip happened before or after the work order opened;
* `degradations` -- the tracked or untracked paths this capture could not mirror, named.
  A `160000` gitlink's worktree path is a directory and a path whose name bytes are not
  valid UTF-8 cannot be opened under the spelling git reports, and neither may be fatal:
  a work order that cannot record its open state cannot be opened at all. A skipped path
  is named, the snapshot state degrades (C4b), and the run continues.

Two modes:

* capture (default) materialises both snapshot directories under the workbench's `tmp/`
  and writes the open-state record;
* `--verify-existing` selects that record by `--work-order-id`, recomputes the digest over
  the **recorded** snapshot directories and compares it with the record's
  `expected_digest`. It captures nothing, re-materialises nothing, and refreshes only
  `recomputed_digest` and `match` on a successful comparison.

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
    ManifestError,
    TRACKED_PATH_UNREADABLE,
    UNTRACKED_PATH_UNREADABLE,
    digest_from_hashes,
    index_entries,
    path_note,
    read_bytes,
    require_commit,
    resolve_repo,
    run_git,
    sha256_hex,
    snapshot_paths,
    sort_key,
    tracked_paths,
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
# absent on read (F1, F3, F5, F6 of the adversarial shape verification).
RECORD_OPEN_STATE_FIELDS = ("untracked_paths", "index_modes", "degradations")

RECORD_NAME = "baseline-open-state.json"
WORKTREE_SNAPSHOT_NAME = "baseline-worktree"
UNTRACKED_SNAPSHOT_NAME = "baseline-untracked"

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


def _materialise(directory: Path, path: str, payload: bytes) -> None:
    target = directory / Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


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
) -> tuple[dict[str, Any], Path]:
    """Mirror the open state, publish its digest, and write the open-state record."""
    repo = resolve_repo(repo_path)
    head = run_git(repo, ["rev-parse", "HEAD"]).decode("utf-8", "replace").strip()
    require_commit(repo, head)
    _require_workbench(workbench)

    path = record_path(workbench)
    target_worktree = _snapshot_dir(worktree_dir, "", workbench / "tmp" / WORKTREE_SNAPSHOT_NAME)
    target_untracked = _snapshot_dir(
        untracked_dir, "", workbench / "tmp" / UNTRACKED_SNAPSHOT_NAME
    )

    tracked = sorted(tracked_paths(repo, head), key=sort_key)
    untracked = sorted(untracked_paths(repo), key=sort_key)
    modes = index_entries(repo)

    # Both directories are materialised even when they hold nothing. A clean open state is an
    # *empty* snapshot, not a missing one, and the two have to stay distinguishable: a missing
    # directory is the C4a/C4b degradation, while an empty one is the faithful record of a
    # capture that found nothing to mirror.
    target_worktree.mkdir(parents=True, exist_ok=True)
    target_untracked.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[str, str]] = []
    copied = 0
    degradations: list[str] = []
    for relative in tracked:
        payload = read_bytes(repo / Path(relative))
        if payload is None:
            # A gitlink's worktree path is a directory and a name git spells lossily cannot
            # be opened. Neither is fatal: the path is named, it stays out of the digest,
            # and the work order is not blocked at open (C4b degrades instead).
            degradations.append(path_note(TRACKED_PATH_UNREADABLE, relative))
            continue
        _materialise(target_worktree, relative, payload)
        pairs.append((relative, sha256_hex(payload)))
        copied += 1

    for relative in untracked:
        payload = read_bytes(repo / Path(relative))
        if payload is None:
            degradations.append(path_note(UNTRACKED_PATH_UNREADABLE, relative))
            continue
        _materialise(target_untracked, relative, payload)

    # The digest published at open is the digest of the materialised snapshot, so the
    # verification mode reproduces it from the snapshot alone.
    expected_digest = digest_from_hashes(pairs)
    captured = sorted(snapshot_paths(target_worktree), key=sort_key)
    recomputed_digest = digest_from_snapshot(target_worktree, captured)
    if expected_digest != recomputed_digest:
        raise ManifestError(
            "captured snapshot does not reproduce the baseline digest: "
            f"computed {expected_digest}, recomputed {recomputed_digest}"
        )

    captured_at = _captured_at_of_existing_record(path, work_order_id) or _now_utc()
    record: dict[str, Any] = {
        "kind": RECORD_KIND,
        "work_order_id": work_order_id,
        "captured_at": captured_at,
        "head": head,
        "algorithm": DIGEST_ALGORITHM,
        "tracked_files": len(tracked),
        "copied_files": copied,
        "untracked_files": len(untracked),
        "untracked_paths": list(untracked),
        "index_modes": {
            item: str(modes[item].get("mode", "")) for item in sorted(modes, key=sort_key)
        },
        "expected_digest": expected_digest,
        "recomputed_digest": recomputed_digest,
        "match": expected_digest == recomputed_digest,
        "worktree_snapshot": str(target_worktree),
        "untracked_snapshot": str(target_untracked),
        "degradations": list(degradations),
    }
    _write_record(path, record)
    return record, path


def verify_open_state(
    repo_path: Path,
    workbench: Path,
    work_order_id: str,
    worktree_dir: Path | None,
    untracked_dir: Path | None,
) -> tuple[dict[str, Any], Path]:
    """Recompute the recorded digest over the recorded snapshot directories."""
    repo = resolve_repo(repo_path)
    path = record_path(workbench)
    record = _load_record(path, work_order_id)

    if str(record["algorithm"]) != DIGEST_ALGORITHM:
        raise ManifestError(
            "open-state record declares algorithm "
            f"{record['algorithm']!r}, which this tool cannot recompute"
        )

    head = str(record["head"])
    require_commit(repo, head)
    tracked = sorted(tracked_paths(repo, head), key=sort_key)

    recorded_worktree = _snapshot_dir(
        worktree_dir, record["worktree_snapshot"], workbench / "tmp" / WORKTREE_SNAPSHOT_NAME
    )
    recorded_untracked = _snapshot_dir(
        untracked_dir, record["untracked_snapshot"], workbench / "tmp" / UNTRACKED_SNAPSHOT_NAME
    )

    if not recorded_worktree.is_dir():
        raise ManifestError(f"baseline worktree snapshot directory is missing: {recorded_worktree}")
    captured = snapshot_paths(recorded_worktree)
    # A tracked path the capture legitimately could not mirror -- a gitlink's worktree path
    # is a directory, a lossily spelled name cannot be opened -- is absent from the snapshot
    # and unreadable now as well. It is a recorded skip, not a damaged snapshot; every other
    # missing path still fails, and a path that is only missing from the snapshot keeps
    # failing because the worktree still reads it.
    missing = sorted(
        (
            path
            for path in set(tracked) - set(captured)
            if read_bytes(repo / Path(path)) is not None
        ),
        key=sort_key,
    )
    unexpected = sorted(set(captured) - set(tracked), key=sort_key)
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

    # The digest is recomputed over what the snapshot actually holds, which is exactly the
    # set the capture hashed; a path that was dropped from the snapshot after the capture
    # changes the recomputed digest and still fails the comparison below.
    digest = digest_from_snapshot(recorded_worktree, sorted(captured, key=sort_key))
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
    run = verify_open_state if args.verify_existing else capture_open_state
    try:
        record, path = run(
            repo_path=Path(args.repo),
            workbench=Path(args.workbench),
            work_order_id=args.work_order_id,
            worktree_dir=Path(args.baseline_worktree_dir) if args.baseline_worktree_dir else None,
            untracked_dir=Path(args.baseline_untracked_dir) if args.baseline_untracked_dir else None,
        )
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
