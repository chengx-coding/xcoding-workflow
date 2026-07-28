#!/usr/bin/env python3
"""Shared orchestration runtime model, persistence, and integrity helpers.

This module owns runtime tree semantics. CLI commands, the local viewer, and
template tooling use these helpers instead of parsing or writing managed XML
independently.
"""

from __future__ import annotations

import copy
import errno
import html
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": 1,
    "git": {
        "auto_commit": True,
        "commit_message": "chore(orchestration): {operation} {run_id} [{checksum_short}]",
        "on_commit_failure": "warn",
    },
    "integrity": {
        "algorithm": "sha256",
        "canonicalization": "orchestration-tree-v1",
        "on_mismatch_read": "warn",
        "on_mismatch_write": "block",
    },
    "viewer": {
        "host": "127.0.0.1",
        "port": 20668,
        "watch_interval_seconds": 1,
        "heartbeat_seconds": 15,
        "idle_shutdown_seconds": 120,
    },
}

TEMPLATE_UPDATED_AT = "1970-01-01T00:00:00+00:00"

RUNTIME_NOTICE = (
    "ATTENTION: AGENTS MUST ONLY READ OR OPERATE THIS RUNTIME TREE THROUGH "
    "THE xc-orchestration-runtime SKILL AND ITS PUBLIC COMMANDS. DO NOT OPEN, "
    "SUMMARIZE, EDIT, PATCH, OR REFORMAT THIS FILE DIRECTLY."
)
TEMPLATE_NOTICE = (
    "ATTENTION: AGENTS MUST ONLY READ OR OPERATE THIS TEMPLATE THROUGH THE "
    "xc-orchestration-author SKILL AND ITS PUBLIC COMMANDS. DO NOT OPEN, "
    "SUMMARIZE, EDIT, PATCH, OR REFORMAT THIS FILE DIRECTLY."
)

SUCCESS_STATUSES = {"succeeded", "skipped"}
TERMINAL_STATUSES = {"succeeded", "failed", "blocked", "skipped"}
RUNNABLE_STATUSES = {"pending", "ready"}
VALID_STATUSES = {"pending", "ready", "running", "succeeded", "failed", "blocked", "skipped"}
VALID_TYPES = {"composite", "task", "gate", "loop"}
VALID_MODES = {"", "sequence", "parallel", "switch"}
VALID_EXECUTORS = {"main", "subagent", "tool", "service"}
VALID_WHEN_POLICIES = {"reactive", "latched"}
VALID_DYNAMIC_GROUP_STATES = {"open", "closed"}
NODE_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ATOMIC_REPLACE_ATTEMPTS = 5
ATOMIC_REPLACE_RETRY_DELAY_SECONDS = 0.05
TRANSIENT_REPLACE_WINERRORS = {5, 32}
RUNTIME_LOCK_TIMEOUT_SECONDS = 15
RUNTIME_LOCK_RETRY_SECONDS = 0.05
SVG_NODE_WIDTH = 232
SVG_NODE_HEIGHT = 86
SVG_COLUMN_GAP = 112
SVG_ROW_GAP = 30
SVG_PADDING = 42
SVG_HEADER_HEIGHT = 72


class RuntimeErrorBase(RuntimeError):
    """Base error carrying a stable machine-readable error code."""

    code = "runtime_error"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ConfigError(RuntimeErrorBase):
    code = "config_error"


class IntegrityError(RuntimeErrorBase):
    code = "integrity_write_blocked"


class TreeValidationError(RuntimeErrorBase):
    code = "tree_validation_error"


class StateConflictError(RuntimeErrorBase):
    code = "state_conflict"


class TreeSealedError(RuntimeErrorBase):
    code = "tree_sealed"


class DynamicGroupClosedError(RuntimeErrorBase):
    code = "group_closed"


class InvalidTransitionError(RuntimeErrorBase):
    code = "invalid_transition"


class NodeNotReadyError(RuntimeErrorBase):
    code = "node_not_ready"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slug(value: str, fallback: str = "node") -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = fallback
    if not normalized[0].isalpha():
        normalized = f"{fallback}-{normalized}"
    return normalized


def json_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def find_workspace_config(tree_path: Optional[Path]) -> Optional[Path]:
    if tree_path is None:
        current = Path.cwd().resolve()
    else:
        resolved = tree_path.resolve()
        current = resolved if resolved.is_dir() else resolved.parent
    while True:
        candidates = [current / ".xcoding" / "xc-orchestration-runtime.toml"]
        if current.name == ".xcoding":
            candidates.insert(0, current / "xc-orchestration-runtime.toml")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        if current.parent == current:
            return None
        current = current.parent


def validate_config(config: Dict[str, Any], source: str) -> None:
    if not isinstance(config.get("schema_version"), int):
        raise ConfigError("schema_version must be an integer", {"source": source})
    git = config.get("git")
    integrity = config.get("integrity")
    viewer = config.get("viewer")
    if not isinstance(git, dict) or not isinstance(git.get("auto_commit"), bool):
        raise ConfigError("git.auto_commit must be a boolean", {"source": source})
    if git.get("on_commit_failure") not in {"warn", "fail"}:
        raise ConfigError("git.on_commit_failure must be warn or fail", {"source": source})
    if not isinstance(integrity, dict):
        raise ConfigError("integrity must be an object", {"source": source})
    if integrity.get("algorithm") != "sha256":
        raise ConfigError("only integrity.algorithm=sha256 is supported", {"source": source})
    if integrity.get("canonicalization") != "orchestration-tree-v1":
        raise ConfigError("unsupported integrity.canonicalization", {"source": source})
    if integrity.get("on_mismatch_read") != "warn":
        raise ConfigError("integrity.on_mismatch_read must be warn", {"source": source})
    if integrity.get("on_mismatch_write") != "block":
        raise ConfigError("integrity.on_mismatch_write must be block", {"source": source})
    if not isinstance(viewer, dict):
        raise ConfigError("viewer must be an object", {"source": source})
    if viewer.get("host") != "127.0.0.1":
        raise ConfigError("viewer.host must be 127.0.0.1 for local mode", {"source": source})
    for key in ("port", "watch_interval_seconds", "heartbeat_seconds", "idle_shutdown_seconds"):
        if not isinstance(viewer.get(key), int) or viewer[key] < 0:
            raise ConfigError(f"viewer.{key} must be a non-negative integer", {"source": source})


def load_config(tree_path: Optional[Path] = None, config_path: Optional[Path] = None) -> Dict[str, Any]:
    source_path = config_path.resolve() if config_path else find_workspace_config(tree_path)
    config = copy.deepcopy(DEFAULT_CONFIG)
    source = "builtin defaults"
    if source_path:
        if not source_path.exists():
            raise ConfigError("config file not found", {"path": str(source_path)})
        try:
            data = tomllib.loads(source_path.read_text(encoding="utf-8-sig"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError("invalid TOML configuration", {"path": str(source_path), "error": str(exc)}) from exc
        if not isinstance(data, dict):
            raise ConfigError("configuration root must be an object", {"path": str(source_path)})
        config = deep_merge(config, data)
        source = str(source_path)
    validate_config(config, source)
    config["_source"] = source
    return config


def parse_set_values(values: Optional[Sequence[str]]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for item in values or []:
        if "=" not in item:
            raise RuntimeErrorBase("--set/--var expects key=value", {"value": item})
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RuntimeErrorBase("--set/--var key cannot be empty", {"value": item})
        result.append((key, value))
    return result


def parse_metadata_values(values: Optional[Sequence[str]]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in parse_set_values(values):
        if not key.startswith("metadata.") or key == "metadata." or ".." in key:
            raise RuntimeErrorBase("--metadata expects a non-empty metadata.<key>=value entry", {"key": key})
        if key in seen:
            raise RuntimeErrorBase("--metadata keys must be unique", {"key": key})
        seen.add(key)
        result.append((key, value))
    return result


def parse_xml(path: Path) -> ET.ElementTree:
    if not path.exists():
        raise RuntimeErrorBase("orchestration file not found", {"path": str(path)})
    try:
        return ET.parse(path)
    except ET.ParseError as exc:
        raise RuntimeErrorBase("XML parse error", {"path": str(path), "error": str(exc)}) from exc


def find_direct(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in list(parent):
        if child.tag == tag:
            return child
    return None


def ensure_direct(parent: ET.Element, tag: str, insert_at: Optional[int] = None) -> ET.Element:
    existing = find_direct(parent, tag)
    if existing is not None:
        return existing
    child = ET.Element(tag)
    if insert_at is None:
        parent.append(child)
    else:
        parent.insert(insert_at, child)
    return child


def children(node: ET.Element) -> List[ET.Element]:
    holder = find_direct(node, "children")
    if holder is None:
        return []
    return [child for child in list(holder) if child.tag == "node"]


def iter_nodes(root: ET.Element) -> Iterator[ET.Element]:
    yield from root.iter("node")


def root_node(root: ET.Element) -> ET.Element:
    node = find_direct(root, "node")
    if node is None:
        raise TreeValidationError("orchestration has no root node")
    return node


def child_text(node: ET.Element, tag: str) -> str:
    child = find_direct(node, tag)
    return (child.text or "").strip() if child is not None else ""


def ensure_node_child(node: ET.Element, tag: str) -> ET.Element:
    return ensure_direct(node, tag)


def normalize_type(node_type: str, role: str = "") -> Tuple[str, str]:
    if node_type not in VALID_TYPES:
        raise TreeValidationError("invalid node type", {"type": node_type})
    return node_type, role


def node_type(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[0]


def node_role(node: ET.Element) -> str:
    return normalize_type(node.get("type", "task"), node.get("role", ""))[1]


def find_meta(root: ET.Element) -> Optional[ET.Element]:
    return find_direct(root, "meta")


def notice_for(artifact_kind: str) -> Tuple[str, str, str]:
    if artifact_kind == "template":
        return "xc-orchestration-author", "author-skill-only", TEMPLATE_NOTICE
    if artifact_kind == "runtime":
        return "xc-orchestration-runtime", "runtime-skill-only", RUNTIME_NOTICE
    raise TreeValidationError("invalid artifact kind", {"artifact_kind": artifact_kind})


def ensure_managed_metadata(root: ET.Element, artifact_kind: str, config: Dict[str, Any]) -> ET.Element:
    skill, read_policy, notice = notice_for(artifact_kind)
    root.set("artifact_kind", artifact_kind)
    root.set("managed_by_skill", skill)
    root.set("read_policy", read_policy)
    meta = find_meta(root)
    if meta is None:
        meta = ET.Element("meta")
        root.insert(0, meta)
    policy = ensure_direct(meta, "access_policy")
    policy.set("required_skill", skill)
    policy.set("read_policy", read_policy)
    policy.text = notice
    integrity = ensure_direct(meta, "integrity")
    integrity.set("algorithm", str(config["integrity"]["algorithm"]))
    integrity.set("canonicalization", str(config["integrity"]["canonicalization"]))
    return meta


def _canonical_text(value: Optional[str], has_children: bool) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    if has_children and not text.strip():
        return ""
    return text


def canonical_element(element: ET.Element) -> Dict[str, Any]:
    attrs = dict(element.attrib)
    if element.tag == "integrity":
        attrs.pop("checksum", None)
    child_items = list(element)
    return {
        "tag": element.tag,
        "attrs": {key: attrs[key] for key in sorted(attrs)},
        "text": _canonical_text(element.text, bool(child_items)),
        "children": [canonical_element(child) for child in child_items],
    }


def calculate_checksum(root: ET.Element) -> str:
    canonical = canonical_element(root)
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def integrity_element(root: ET.Element) -> Optional[ET.Element]:
    meta = find_meta(root)
    return find_direct(meta, "integrity") if meta is not None else None


def verify_integrity(root: ET.Element, artifact_kind: Optional[str] = None) -> Dict[str, Any]:
    kind = artifact_kind or root.get("artifact_kind", "runtime")
    skill, read_policy, _ = notice_for(kind)
    errors: List[str] = []
    meta = find_meta(root)
    if meta is None:
        return {"status": "missing", "reason": "missing meta element", "expected_checksum": "", "actual_checksum": ""}
    policy = find_direct(meta, "access_policy")
    integrity = find_direct(meta, "integrity")
    if policy is None:
        errors.append("missing meta.access_policy")
    else:
        if policy.get("required_skill") != skill:
            errors.append(f"access policy requires {policy.get('required_skill')}, expected {skill}")
        if policy.get("read_policy") != read_policy:
            errors.append("access policy read_policy mismatch")
    if root.get("managed_by_skill") != skill:
        errors.append("root managed_by_skill mismatch")
    if root.get("read_policy") != read_policy:
        errors.append("root read_policy mismatch")
    if root.get("artifact_kind") != kind:
        errors.append(f"root artifact_kind mismatch: expected {kind}")
    if integrity is None:
        return {
            "status": "missing",
            "reason": "; ".join(errors + ["missing meta.integrity"]),
            "expected_checksum": "",
            "actual_checksum": "",
        }
    algorithm = integrity.get("algorithm", "")
    canonicalization = integrity.get("canonicalization", "")
    expected = integrity.get("checksum", "")
    if algorithm != "sha256" or canonicalization != "orchestration-tree-v1":
        return {
            "status": "unsupported",
            "reason": "; ".join(errors + ["unsupported integrity metadata"]),
            "expected_checksum": expected,
            "actual_checksum": "",
            "algorithm": algorithm,
            "canonicalization": canonicalization,
        }
    actual = calculate_checksum(root)
    if not expected:
        errors.append("missing checksum")
    elif expected != actual:
        errors.append("checksum mismatch")
    return {
        "status": "valid" if not errors else "mismatch",
        "reason": "; ".join(errors) if errors else "checksum verified",
        "expected_checksum": expected,
        "actual_checksum": actual,
        "algorithm": algorithm,
        "canonicalization": canonicalization,
    }


def apply_integrity(root: ET.Element, artifact_kind: str, config: Dict[str, Any]) -> str:
    ensure_managed_metadata(root, artifact_kind, config)
    root.set("updated_at", TEMPLATE_UPDATED_AT if artifact_kind == "template" else utc_now())
    integrity = integrity_element(root)
    if integrity is None:
        raise RuntimeErrorBase("managed metadata missing integrity")
    checksum = calculate_checksum(root)
    integrity.set("checksum", checksum)
    return checksum


def xml_warning(artifact_kind: str) -> str:
    _, _, notice = notice_for(artifact_kind)
    return notice


def serialize_xml(root: ET.Element, artifact_kind: str) -> str:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="utf-8"?>\n<!-- {xml_warning(artifact_kind)} -->\n{body}\n'


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
            try:
                os.replace(temp_name, path)
                break
            except OSError as exc:
                retryable = exc.errno in {errno.EACCES, errno.EPERM} or getattr(exc, "winerror", None) in TRANSIENT_REPLACE_WINERRORS
                if not retryable or attempt == ATOMIC_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(ATOMIC_REPLACE_RETRY_DELAY_SECONDS * (attempt + 1))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def runtime_lock_path(tree_path: Path) -> Path:
    resolved = str(tree_path.resolve()).encode("utf-8")
    digest = hashlib.sha256(resolved).hexdigest()
    return Path(tempfile.gettempdir()) / f"xc-orchestration-{digest}.lock"


@contextmanager
def runtime_write_lock(tree_path: Path) -> Iterator[None]:
    """Serialize runtime mutations for one local managed tree."""

    lock_path = runtime_lock_path(tree_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + RUNTIME_LOCK_TIMEOUT_SECONDS
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise StateConflictError(
                        "timed out waiting for the runtime mutation lock",
                        {"tree_path": str(tree_path), "lock_path": str(lock_path)},
                    )
                time.sleep(RUNTIME_LOCK_RETRY_SECONDS)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_git(args: Sequence[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_root_for(path: Path) -> Optional[Path]:
    result = run_git(["rev-parse", "--show-toplevel"], path.parent)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def commit_managed_paths(
    paths: Sequence[Path],
    operation: str,
    run_id: str,
    checksum: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    if not config["git"]["auto_commit"]:
        return {"status": "disabled"}
    if not paths:
        return {"status": "no_changes"}
    repo_root = git_root_for(paths[0])
    if repo_root is None:
        return {"status": "not_applicable"}
    rel_paths: List[str] = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.exists():
            return {"status": "failed", "error": f"managed path does not exist: {resolved}"}
        try:
            rel = resolved.relative_to(repo_root).as_posix()
        except ValueError:
            return {
                "status": "failed",
                "error": f"managed path is outside the context Git repository: {resolved}",
            }
        if rel not in rel_paths:
            rel_paths.append(rel)

    temp_index = Path(tempfile.gettempdir()) / f"orchestration-index-{uuid.uuid4().hex}"
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(temp_index)
    try:
        head = run_git(["rev-parse", "--verify", "HEAD"], repo_root, env)
        if head.returncode == 0:
            read_tree = run_git(["read-tree", "HEAD"], repo_root, env)
            if read_tree.returncode != 0:
                return {"status": "failed", "error": read_tree.stderr.strip()}
        add = run_git(["add", "--", *rel_paths], repo_root, env)
        if add.returncode != 0:
            return {"status": "failed", "error": add.stderr.strip()}
        diff = run_git(["diff", "--cached", "--quiet", "--", *rel_paths], repo_root, env)
        if diff.returncode == 0:
            return {"status": "no_changes"}
        if diff.returncode != 1:
            return {"status": "failed", "error": diff.stderr.strip()}
        message_template = str(config["git"]["commit_message"])
        message = message_template.format(
            operation=operation,
            run_id=run_id or "template",
            checksum_short=checksum[:12],
        )
        commit = run_git(["commit", "-m", message], repo_root, env)
        if commit.returncode != 0:
            return {"status": "failed", "error": commit.stderr.strip() or commit.stdout.strip()}
        sha = run_git(["rev-parse", "HEAD"], repo_root, env)
        index_sync = run_git(["reset", "--mixed", "HEAD", "--", *rel_paths], repo_root)
        result = {"status": "committed", "sha": sha.stdout.strip()}
        if index_sync.returncode != 0:
            result["index_sync"] = {"status": "failed", "error": index_sync.stderr.strip()}
        else:
            result["index_sync"] = {"status": "synced"}
        return result
    finally:
        if temp_index.exists():
            temp_index.unlink()
        lock = Path(f"{temp_index}.lock")
        if lock.exists():
            lock.unlink()


def write_managed_tree(
    tree: ET.ElementTree,
    path: Path,
    artifact_kind: str,
    config: Dict[str, Any],
    operation: str,
    commit_paths: Optional[Sequence[Path]] = None,
    commit_on_write: bool = True,
    export_runtime_svg: bool = False,
) -> Dict[str, Any]:
    root = tree.getroot()
    checksum = apply_integrity(root, artifact_kind, config)
    atomic_write_text(path, serialize_xml(root, artifact_kind))
    reloaded = parse_xml(path)
    integrity = verify_integrity(reloaded.getroot(), artifact_kind)
    if integrity["status"] != "valid":
        raise RuntimeErrorBase("checksum verification failed after write", {"path": str(path), "integrity": integrity})
    generated_paths: List[Path] = []
    if artifact_kind == "runtime" and export_runtime_svg:
        svg_path = runtime_svg_path(path, reloaded.getroot())
        snapshot = snapshot_from_root(reloaded.getroot(), path, integrity)
        atomic_write_text(svg_path, render_snapshot_svg(snapshot))
        generated_paths.append(svg_path)
    if commit_on_write:
        commit = commit_managed_paths(
            [path, *generated_paths, *(commit_paths or [])],
            operation,
            root.get("run_id", ""),
            checksum,
            config,
        )
    else:
        commit = {"status": "deferred"}
    result: Dict[str, Any] = {
        "path": str(path),
        "checksum": checksum,
        "integrity": integrity,
        "commit": commit,
    }
    if generated_paths:
        result["svg_path"] = str(generated_paths[0])
    if commit["status"] == "failed":
        result["status"] = "persisted_uncommitted"
    else:
        result["status"] = "persisted"
    return result


def read_tree_with_integrity(path: Path, config: Dict[str, Any], artifact_kind: Optional[str] = None) -> Tuple[ET.ElementTree, Dict[str, Any]]:
    tree = parse_xml(path)
    integrity = verify_integrity(tree.getroot(), artifact_kind)
    return tree, integrity


def require_writable_integrity(integrity: Dict[str, Any]) -> None:
    if integrity.get("status") != "valid":
        raise IntegrityError(
            "integrity mismatch blocks tree modification; inspect then run repair-integrity explicitly",
            {"integrity": integrity},
        )


def blackboard(root: ET.Element) -> Dict[str, str]:
    holder = find_direct(root, "blackboard")
    result: Dict[str, str] = {}
    if holder is None:
        return result
    for var in holder.findall("var"):
        key = var.get("key")
        if key:
            result[key] = (var.text or "").strip()
    return result


def blackboard_updated_at(root: ET.Element) -> str:
    holder = find_direct(root, "blackboard")
    if holder is None:
        return ""
    timestamps = [variable.get("updated_at", "") for variable in holder.findall("var")]
    return max((timestamp for timestamp in timestamps if timestamp), default="")


def ensure_blackboard(root: ET.Element) -> ET.Element:
    return ensure_direct(root, "blackboard", insert_at=1)


def set_blackboard(root: ET.Element, key: str, value: str, source: str = "script") -> None:
    holder = ensure_blackboard(root)
    target = None
    for var in holder.findall("var"):
        if var.get("key") == key:
            target = var
            break
    if target is None:
        target = ET.SubElement(holder, "var", {"key": key})
    target.text = value
    target.set("updated_at", utc_now())
    target.set("source", source)


def root_node(root: ET.Element) -> ET.Element:
    node = find_direct(root, "node")
    if node is None:
        raise TreeValidationError("orchestration has no root node")
    return node


def runtime_revision(root: ET.Element) -> int:
    raw = root.get("revision", "0")
    try:
        revision = int(raw)
    except ValueError as exc:
        raise TreeValidationError("runtime revision must be a non-negative integer", {"revision": raw}) from exc
    if revision < 0:
        raise TreeValidationError("runtime revision must be a non-negative integer", {"revision": raw})
    return revision


def require_expected_revision(root: ET.Element, expected_revision: Optional[int]) -> None:
    current = runtime_revision(root)
    if expected_revision is not None and expected_revision != current:
        raise StateConflictError(
            "runtime revision does not match the expected revision",
            {"expected_revision": expected_revision, "actual_revision": current},
        )


def is_runtime_sealed(root: ET.Element) -> bool:
    return root.get("status") == "succeeded" or bool(root.get("sealed_at"))


def require_runtime_mutable(root: ET.Element, operation: str) -> None:
    if is_runtime_sealed(root):
        raise TreeSealedError(
            "successful runtime trees are sealed; reopen explicitly before mutating them",
            {
                "operation": operation,
                "sealed_at": root.get("sealed_at", ""),
                "revision": runtime_revision(root),
            },
        )


def finalize_runtime_mutation(root: ET.Element) -> int:
    revision = runtime_revision(root) + 1
    root.set("revision", str(revision))
    if root.get("status") == "succeeded" and not root.get("sealed_at"):
        root.set("sealed_at", utc_now())
        root.set("sealed_revision", str(revision))
        root.set("sealed_epoch", root.get("epoch", "0"))
    return revision


def reopen_runtime_tree(root: ET.Element, reason: str) -> None:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise TreeValidationError("reopen reason must not be empty")
    if root.get("status") != "succeeded":
        raise InvalidTransitionError(
            "only successful runtime trees can be reopened",
            {"status": root.get("status", "pending")},
        )

    try:
        next_epoch = int(root.get("epoch", "0")) + 1
    except ValueError as exc:
        raise TreeValidationError("runtime epoch must be a non-negative integer", {"epoch": root.get("epoch", "")}) from exc

    metadata = find_meta(root)
    if metadata is None:
        raise TreeValidationError("runtime metadata is missing")
    history = ensure_direct(metadata, "reopen_history")
    ET.SubElement(
        history,
        "reopen",
        {
            "epoch": str(next_epoch),
            "reopened_at": utc_now(),
            "reason": normalized_reason,
            "sealed_at": root.get("sealed_at", ""),
            "sealed_revision": root.get("sealed_revision", ""),
        },
    )
    for key in ("sealed_at", "sealed_revision", "sealed_epoch"):
        root.attrib.pop(key, None)
    root.set("epoch", str(next_epoch))
    root.set("reopen_pending", "true")
    root.set("status", "running")
    root_node(root).set("status", "running")


def parent_map(root: ET.Element) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}

    def walk(node: ET.Element, parent_id: Optional[str]) -> None:
        node_id = node.get("id")
        if node_id:
            result[node_id] = parent_id
        for child in children(node):
            walk(child, node_id)

    walk(root_node(root), None)
    return result


def element_parent_map(root: ET.Element) -> Dict[str, ET.Element]:
    result: Dict[str, ET.Element] = {}

    def walk(node: ET.Element) -> None:
        for child in children(node):
            if child.get("id"):
                result[child.get("id", "")] = node
            walk(child)

    walk(root_node(root))
    return result


def nodes_by_id(root: ET.Element) -> Dict[str, ET.Element]:
    return {node.get("id", ""): node for node in iter_nodes(root) if node.get("id")}


def find_node(root: ET.Element, node_id: str) -> ET.Element:
    node = nodes_by_id(root).get(node_id)
    if node is None:
        raise RuntimeErrorBase("node not found", {"node_id": node_id})
    return node


def is_dynamic_group(node: ET.Element) -> bool:
    return node_type(node) == "composite" and node_role(node) == "dynamic-group"


def dynamic_group_state(node: ET.Element) -> str:
    if not is_dynamic_group(node):
        return ""
    return node.get("dynamic.state", "open")


def close_dynamic_group(root: ET.Element, group_id: str) -> ET.Element:
    group = find_node(root, group_id)
    if not is_dynamic_group(group):
        raise TreeValidationError("close-group requires a dynamic-group composite", {"group_id": group_id})
    state = dynamic_group_state(group)
    if state not in VALID_DYNAMIC_GROUP_STATES:
        raise TreeValidationError("dynamic group has invalid state", {"group_id": group_id, "state": state})
    if state == "closed":
        return group
    group.set("dynamic.state", "closed")
    stabilize(root)
    return group


def require_dynamic_group_open(parent: ET.Element) -> None:
    if not is_dynamic_group(parent):
        return
    state = dynamic_group_state(parent)
    if state == "closed":
        raise DynamicGroupClosedError(
            "cannot append work to a closed dynamic group",
            {"group_id": parent.get("id", ""), "state": state},
        )
    if state != "open":
        raise TreeValidationError("dynamic group has invalid state", {"group_id": parent.get("id", ""), "state": state})


def normalize_value(value: str) -> str:
    return value.strip().strip('"').strip("'").lower()


def eval_when(expression: str, bb: Dict[str, str]) -> bool:
    expr = expression.strip()
    if not expr:
        return True
    if "==" in expr:
        key, expected = expr.split("==", 1)
        return normalize_value(bb.get(key.strip(), "")) == normalize_value(expected)
    if "!=" in expr:
        key, expected = expr.split("!=", 1)
        return normalize_value(bb.get(key.strip(), "")) != normalize_value(expected)
    if expr.startswith("!"):
        return normalize_value(bb.get(expr[1:].strip(), "")) not in {"1", "true", "yes", "y"}
    return normalize_value(bb.get(expr, "")) in {"1", "true", "yes", "y"}


def when_policy(node: ET.Element) -> str:
    return node.get("when.policy", "reactive")


def incomplete_dependency_ids(
    root: ET.Element,
    node: ET.Element,
    lookup: Optional[Dict[str, ET.Element]] = None,
) -> List[str]:
    raw = node.get("depends_on", "").strip()
    if not raw:
        return []
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    incomplete: List[str] = []
    for dep_id in [item.strip() for item in raw.split(",") if item.strip()]:
        dep = node_lookup.get(dep_id)
        if dep is None or dep.get("status", "pending") not in SUCCESS_STATUSES:
            incomplete.append(dep_id)
    return incomplete


def dependencies_satisfied(root: ET.Element, node: ET.Element) -> bool:
    return not incomplete_dependency_ids(root, node)


def ancestor_readiness_blocker(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    parent_lookup = parents if parents is not None else element_parent_map(root)
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    current = node
    current_id = current.get("id", "")
    while current_id in parent_lookup:
        parent = parent_lookup[current_id]
        parent_id = parent.get("id", "")
        parent_status = parent.get("status", "pending")
        if parent_status == "skipped":
            reason = (
                "ancestor_condition_false"
                if parent.get("skip_reason") == "when"
                else "ancestor_skipped"
            )
            return {
                "reason": reason,
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        if parent_status in {"failed", "blocked"}:
            return {
                "reason": f"ancestor_{parent_status}",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        when = parent.get("when")
        if when and not eval_when(when, blackboard_values):
            return {
                "reason": "ancestor_condition_false",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
            }
        incomplete = incomplete_dependency_ids(root, parent, node_lookup)
        if incomplete:
            return {
                "reason": "ancestor_dependency_incomplete",
                "blocker_node_id": parent_id,
                "blocker_status": parent_status,
                "dependency_ids": incomplete,
            }
        if parent.get("mode", "sequence") == "sequence":
            for sibling in children(parent):
                if sibling is current:
                    break
                sibling_status = sibling.get("status", "pending")
                if sibling_status not in SUCCESS_STATUSES:
                    return {
                        "reason": "sequence_predecessor_incomplete",
                        "blocker_node_id": sibling.get("id", ""),
                        "blocker_status": sibling_status,
                    }
        current = parent
        current_id = current.get("id", "")
    return None


def node_readiness_blocker(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    status = node.get("status", "pending")
    if status not in RUNNABLE_STATUSES:
        reason = "condition_false" if status == "skipped" and node.get("skip_reason") == "when" else "node_status"
        return {"reason": reason}
    when = node.get("when")
    if when and not eval_when(when, blackboard_values):
        return {"reason": "condition_false"}
    incomplete = incomplete_dependency_ids(root, node, node_lookup)
    if incomplete:
        return {"reason": "dependency_incomplete", "dependency_ids": incomplete}
    return ancestor_readiness_blocker(root, node, parents, node_lookup, blackboard_values)


def is_unlocked_by_ancestors(root: ET.Element, node: ET.Element) -> bool:
    lookup = nodes_by_id(root)
    return not incomplete_dependency_ids(root, node, lookup) and ancestor_readiness_blocker(
        root,
        node,
        lookup=lookup,
    ) is None


def reset_subtree(node: ET.Element) -> None:
    node.set("status", "pending")
    for attr in [
        "started_at",
        "completed_at",
        "failed_at",
        "blocked_at",
        "agent",
        "skipped_at",
        "skip_reason",
        "failure_reason",
    ]:
        node.attrib.pop(attr, None)
    result = find_direct(node, "result")
    if result is not None:
        node.remove(result)
    if node_type(node) == "loop":
        node.set("loop.iteration", "1")
        node.attrib.pop("loop.last_completed_iteration", None)
        history = find_direct(node, "history")
        if history is not None:
            node.remove(history)
    for child in children(node):
        reset_subtree(child)


def apply_switches(root: ET.Element) -> bool:
    changed = False
    bb = blackboard(root)
    for node in iter_nodes(root):
        if node.get("mode") != "switch" or not children(node):
            continue
        if node.get("status") in TERMINAL_STATUSES:
            continue
        if not is_unlocked_by_ancestors(root, node):
            continue
        key = node.get("switch.key", "")
        value = bb.get(key, "")
        selected: Optional[ET.Element] = None
        default: Optional[ET.Element] = None
        for child in children(node):
            role = node_role(child)
            if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                default = child
            if normalize_value(child.get("case.value", "")) == normalize_value(value):
                if selected is not None:
                    node.set("status", "failed")
                    node.set("failure_reason", "switch has multiple matching cases")
                    changed = True
                    selected = None
                    break
                selected = child
        if node.get("status") == "failed":
            continue
        if selected is None:
            selected = default
        if selected is None:
            outcome = node.get("switch.no_match", node.get("switch_no_match", "failed"))
            node.set("status", "blocked" if outcome == "blocked" else "failed")
            node.set("failure_reason", f"switch has no matching case for {key}={value}")
            changed = True
            continue
        for child in children(node):
            status = child.get("status", "pending")
            if child is selected:
                if status == "skipped" and child.get("skip_reason") == "switch":
                    child.set("status", "pending")
                    child.attrib.pop("skip_reason", None)
                    changed = True
            elif status not in TERMINAL_STATUSES:
                child.set("status", "skipped")
                child.set("skip_reason", "switch")
                child.set("skipped_at", utc_now())
                changed = True
    return changed


def normalize_conditions(root: ET.Element) -> bool:
    bb = blackboard(root)
    changed = False
    for node in iter_nodes(root):
        when = node.get("when")
        if not when:
            continue
        status = node.get("status", "pending")
        was_conditionally_skipped = status == "skipped" and node.get("skip_reason") == "when"
        if (status not in RUNNABLE_STATUSES and not was_conditionally_skipped) or not is_unlocked_by_ancestors(root, node):
            continue
        should_run = eval_when(when, bb)
        if not should_run and status in RUNNABLE_STATUSES:
            node.set("status", "skipped")
            node.set("skip_reason", "when")
            node.set("skipped_at", utc_now())
            changed = True
        elif should_run and was_conditionally_skipped and when_policy(node) == "reactive":
            node.set("status", "pending")
            node.attrib.pop("skip_reason", None)
            node.attrib.pop("skipped_at", None)
            changed = True
    return changed


def record_loop_history(node: ET.Element, reason: str) -> None:
    history = ensure_node_child(node, "history")
    ET.SubElement(
        history,
        "iteration",
        {
            "index": node.get("loop.iteration", "1"),
            "completed_at": utc_now(),
            "reason": reason,
        },
    )


def recompute_containers(root: ET.Element) -> bool:
    changed = False
    for node in reversed(list(iter_nodes(root))):
        kids = children(node)
        if not kids:
            old_status = node.get("status", "pending")
            if old_status == "skipped" and node.get("skip_reason") in {"switch", "when"}:
                continue
            if is_dynamic_group(node) and dynamic_group_state(node) == "closed":
                if old_status != "succeeded":
                    node.set("status", "succeeded")
                    changed = True
            continue
        old_status = node.get("status", "pending")
        if old_status == "skipped" and node.get("skip_reason") in {"switch", "when"}:
            continue
        statuses = [child.get("status", "pending") for child in kids]
        ntype = node_type(node)
        if ntype == "loop" and all(status in SUCCESS_STATUSES for status in statuses):
            iteration = int(node.get("loop.iteration", "1"))
            maximum = int(node.get("loop.max_iterations", "1"))
            last_completed = node.get("loop.last_completed_iteration", "")
            if last_completed == str(iteration):
                new_status = old_status if old_status in TERMINAL_STATUSES else "succeeded"
                if old_status != new_status:
                    node.set("status", new_status)
                    changed = True
                continue
            break_when = node.get("loop.break_when", "")
            continue_when = node.get("loop.continue_when", "")
            should_break = bool(break_when and eval_when(break_when, blackboard(root)))
            should_continue = bool(continue_when and eval_when(continue_when, blackboard(root)))
            node.set("loop.last_completed_iteration", str(iteration))
            if should_break:
                record_loop_history(node, "break")
                new_status = "succeeded"
            elif should_continue and iteration < maximum:
                record_loop_history(node, "continue")
                for child in kids:
                    reset_subtree(child)
                node.set("loop.iteration", str(iteration + 1))
                node.set("status", "running")
                changed = True
                continue
            elif should_continue and iteration >= maximum:
                record_loop_history(node, "limit")
                new_status = node.get("loop.on_limit", "failed")
                if new_status not in {"failed", "blocked", "succeeded"}:
                    new_status = "failed"
            else:
                record_loop_history(node, "natural")
                new_status = "succeeded"
        elif any(status == "failed" for status in statuses):
            new_status = "failed"
        elif any(status == "blocked" for status in statuses):
            new_status = "blocked"
        elif (
            node is root_node(root)
            and root.get("reopen_pending") == "true"
            and all(status in SUCCESS_STATUSES for status in statuses)
        ):
            new_status = "running"
        elif all(status in SUCCESS_STATUSES for status in statuses):
            new_status = "succeeded"
        elif any(status in {"running", "succeeded", "ready"} for status in statuses):
            new_status = "running"
        else:
            new_status = "pending"
        if old_status != new_status:
            node.set("status", new_status)
            changed = True
    root.set("status", root_node(root).get("status", "pending"))
    return changed


def stabilize(root: ET.Element) -> bool:
    changed = False
    for _ in range(32):
        round_changed = apply_switches(root)
        round_changed = normalize_conditions(root) or round_changed
        round_changed = recompute_containers(root) or round_changed
        changed = changed or round_changed
        if not round_changed:
            break
    return changed


def is_runnable(
    root: ET.Element,
    node: ET.Element,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> bool:
    if node_type(node) in {"composite", "loop"} or children(node):
        return False
    return node_readiness_blocker(root, node, parents, lookup, bb) is None


def ready_from(
    root: ET.Element,
    node: ET.Element,
    limit: int,
    parents: Optional[Dict[str, ET.Element]] = None,
    lookup: Optional[Dict[str, ET.Element]] = None,
    bb: Optional[Dict[str, str]] = None,
) -> List[ET.Element]:
    parent_lookup = parents if parents is not None else element_parent_map(root)
    node_lookup = lookup if lookup is not None else nodes_by_id(root)
    blackboard_values = bb if bb is not None else blackboard(root)
    if limit <= 0 or node.get("status") in TERMINAL_STATUSES:
        return []
    kids = children(node)
    if not kids:
        return [node] if is_runnable(root, node, parent_lookup, node_lookup, blackboard_values) else []
    mode = node.get("mode", "sequence")
    if mode == "parallel":
        ready: List[ET.Element] = []
        for child in kids:
            ready.extend(
                ready_from(
                    root,
                    child,
                    limit - len(ready),
                    parent_lookup,
                    node_lookup,
                    blackboard_values,
                )
            )
            if len(ready) >= limit:
                break
        return ready[:limit]
    if mode == "switch":
        for child in kids:
            if child.get("status") != "skipped":
                return ready_from(root, child, limit, parent_lookup, node_lookup, blackboard_values)
        return []
    for child in kids:
        if child.get("status", "pending") in SUCCESS_STATUSES:
            continue
        return ready_from(root, child, limit, parent_lookup, node_lookup, blackboard_values)
    return []


def node_path(root: ET.Element, node: ET.Element) -> List[str]:
    parent_ids = parent_map(root)
    lookup = nodes_by_id(root)
    result: List[str] = []
    current = node.get("id", "")
    while current:
        item = lookup.get(current)
        if item is not None:
            result.append(item.get("title", current))
        current = parent_ids.get(current) or ""
    return list(reversed(result))


def result_snapshot(node: ET.Element) -> Dict[str, Any]:
    result = find_direct(node, "result")
    if result is None:
        return {}
    payload: Dict[str, Any] = {}
    for child in list(result):
        if child.tag == "artifacts":
            payload["artifacts"] = [artifact.get("path", "") for artifact in child.findall("artifact")]
        else:
            payload[child.tag] = (child.text or "").strip()
    return payload


def declared_artifacts(root: ET.Element, audience: str = "") -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for node in iter_nodes(root):
        result = find_direct(node, "result")
        artifacts = find_direct(result, "artifacts") if result is not None else None
        if artifacts is None:
            continue
        metadata = {
            key: value
            for key, value in node.attrib.items()
            if key.startswith("metadata.artifact.")
        }
        artifact_audience = metadata.get("metadata.artifact.audience", "internal")
        if audience and artifact_audience != audience:
            continue
        for artifact in artifacts.findall("artifact"):
            path = artifact.get("path", "")
            if path:
                entries.append(
                    {
                        "path": path,
                        "node_id": node.get("id", ""),
                        "metadata": dict(sorted(metadata.items())),
                    }
                )
    return entries


def snapshot_node(root: ET.Element, node: ET.Element) -> Dict[str, Any]:
    return {
        "id": node.get("id", ""),
        "template_id": node.get("template_id", ""),
        "origin_template_id": node.get("origin_template_id", ""),
        "origin_instance_id": node.get("origin_instance_id", ""),
        "logical_key": node.get("logical_key", ""),
        "title": node.get("title", ""),
        "type": node_type(node),
        "role": node_role(node),
        "executor": node.get("executor", ""),
        "status": node.get("status", "pending"),
        "mode": node.get("mode", ""),
        "path": node_path(root, node),
        "attributes": dict(sorted(node.attrib.items())),
        "instructions": child_text(node, "instructions"),
        "inputs": child_text(node, "inputs"),
        "deliverables": child_text(node, "deliverables"),
        "acceptance": child_text(node, "acceptance"),
        "result": result_snapshot(node),
        "children": [snapshot_node(root, child) for child in children(node)],
    }


def status_counts(root: ET.Element) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for node in iter_nodes(root):
        status = node.get("status", "pending")
        result[status] = result.get(status, 0) + 1
    return result


def awaiting_dynamic_groups(root: ET.Element) -> List[Dict[str, str]]:
    groups: List[Dict[str, str]] = []
    for node in iter_nodes(root):
        if (
            not is_dynamic_group(node)
            or dynamic_group_state(node) != "open"
            or children(node)
            or node.get("status", "pending") not in RUNNABLE_STATUSES
            or not is_unlocked_by_ancestors(root, node)
        ):
            continue
        groups.append(
            {
                "id": node.get("id", ""),
                "template_id": node.get("template_id", ""),
                "title": node.get("title", ""),
                "path": " / ".join(node_path(root, node)),
                "state": "open",
            }
        )
    return groups


def snapshot_from_root(root: ET.Element, path: Path, integrity: Dict[str, Any]) -> Dict[str, Any]:
    root_n = root_node(root)
    return {
        "tree_path": str(path.resolve()),
        "version": integrity.get("actual_checksum") or root.get("updated_at", ""),
        "integrity": integrity,
        "metadata": {
            "name": root.get("name", ""),
            "run_id": root.get("run_id", ""),
            "schema_version": root.get("schema_version", ""),
            "artifact_kind": root.get("artifact_kind", ""),
            "status": root.get("status", "pending"),
            "updated_at": root.get("updated_at", ""),
            "blackboard_updated_at": blackboard_updated_at(root),
            "revision": runtime_revision(root),
            "sealed_at": root.get("sealed_at", ""),
            "epoch": root.get("epoch", "0"),
        },
        "blackboard": blackboard(root),
        "counts": status_counts(root),
        "awaiting_dynamic_groups": awaiting_dynamic_groups(root),
        "ready": [
            {"id": node.get("id"), "title": node.get("title"), "executor": node.get("executor")}
            for node in ready_from(root, root_n, 256)
        ],
        "root": snapshot_node(root, root_n),
    }


def tree_snapshot(path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    tree, integrity = read_tree_with_integrity(path, config)
    return snapshot_from_root(tree.getroot(), path, integrity)


def runtime_svg_filename(name: str, run_id: str) -> str:
    fallback = slug(run_id, "orchestration")
    return f"{slug(name or run_id, fallback)}.svg"


def runtime_svg_path(tree_path: Path, root: ET.Element) -> Path:
    return tree_path.parent / runtime_svg_filename(root.get("name", ""), root.get("run_id", ""))


def _svg_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) > limit:
        text = f"{text[: max(limit - 1, 0)]}\u2026"
    return html.escape(text)


def _layout_snapshot_tree(root: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    heights: Dict[str, int] = {}

    def measure(node: Dict[str, Any]) -> int:
        child_nodes = node.get("children") or []
        if not child_nodes:
            heights[str(node.get("id", ""))] = SVG_NODE_HEIGHT
            return SVG_NODE_HEIGHT
        child_height = sum(measure(child) for child in child_nodes)
        height = max(SVG_NODE_HEIGHT, child_height + SVG_ROW_GAP * max(len(child_nodes) - 1, 0))
        heights[str(node.get("id", ""))] = height
        return height

    root_height = measure(root)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    max_depth = 0

    def place(node: Dict[str, Any], depth: int, top: int, parent_id: str = "") -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        node_id = str(node.get("id", ""))
        subtree_height = heights[node_id]
        position = {
            "node": node,
            "x": SVG_PADDING + depth * (SVG_NODE_WIDTH + SVG_COLUMN_GAP),
            "y": SVG_HEADER_HEIGHT + SVG_PADDING + top + (subtree_height - SVG_NODE_HEIGHT) / 2,
        }
        nodes.append(position)
        if parent_id:
            edges.append({"source_id": parent_id, "target_id": node_id, "status": node.get("status", "")})
        child_top = top
        for child in node.get("children") or []:
            place(child, depth + 1, child_top, node_id)
            child_top += heights[str(child.get("id", ""))] + SVG_ROW_GAP

    place(root, 0, 0)
    width = SVG_PADDING * 2 + (max_depth + 1) * SVG_NODE_WIDTH + max_depth * SVG_COLUMN_GAP
    height = SVG_HEADER_HEIGHT + SVG_PADDING * 2 + root_height
    return nodes, edges, width, height


def render_snapshot_svg(snapshot: Dict[str, Any]) -> str:
    root = snapshot.get("root")
    if not isinstance(root, dict):
        raise RuntimeErrorBase("snapshot has no root node")
    nodes, edges, width, height = _layout_snapshot_tree(root)
    positions = {str(item["node"].get("id", "")): item for item in nodes}
    metadata = snapshot.get("metadata") or {}
    status_colors = {
        "succeeded": "#4ade80",
        "running": "#60a5fa",
        "ready": "#60a5fa",
        "failed": "#f87171",
        "blocked": "#f87171",
        "skipped": "#fbbf24",
        "pending": "#94a3b8",
    }
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">'
        ),
        f'  <title id="title">{_svg_text(metadata.get("name") or "Orchestration", 160)}</title>',
        (
            '  <desc id="description">Complete orchestration tree for '
            f'{_svg_text(metadata.get("run_id"), 160)}.</desc>'
        ),
        '  <rect width="100%" height="100%" fill="#0b1220"/>',
        (
            f'  <text x="{SVG_PADDING}" y="31" fill="#f8fafc" '
            'font-family="Segoe UI,Arial,sans-serif" font-size="18" font-weight="700">'
            f'{_svg_text(metadata.get("name") or "Orchestration", 100)}</text>'
        ),
        (
            f'  <text x="{SVG_PADDING}" y="53" fill="#94a3b8" '
            'font-family="Segoe UI,Arial,sans-serif" font-size="12">'
            f'Run {_svg_text(metadata.get("run_id"), 80)} \u00b7 {_svg_text(metadata.get("status"), 24)}</text>'
        ),
    ]
    for edge in edges:
        source = positions[edge["source_id"]]
        target = positions[edge["target_id"]]
        start_x = source["x"] + SVG_NODE_WIDTH
        start_y = source["y"] + SVG_NODE_HEIGHT / 2
        end_x = target["x"]
        end_y = target["y"] + SVG_NODE_HEIGHT / 2
        control = max((end_x - start_x) * 0.5, 36)
        color = status_colors.get(str(edge["status"]), "#4b607a")
        dash = ' stroke-dasharray="6 5"' if edge["status"] == "skipped" else ""
        lines.append(
            f'  <path d="M {start_x:g} {start_y:g} C {start_x + control:g} {start_y:g}, '
            f'{end_x - control:g} {end_y:g}, {end_x:g} {end_y:g}" fill="none" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
    for item in nodes:
        node = item["node"]
        x = item["x"]
        y = item["y"]
        status = str(node.get("status", "pending"))
        color = status_colors.get(status, "#94a3b8")
        role = " / ".join(part for part in (node.get("type"), node.get("role")) if part)
        lines.extend(
            [
                f'  <g data-node-id="{html.escape(str(node.get("id", "")), quote=True)}" data-status="{html.escape(status, quote=True)}">',
                f'    <title>{html.escape(str(node.get("title") or node.get("id") or ""))}</title>',
                (
                    f'    <rect x="{x:g}" y="{y:g}" width="{SVG_NODE_WIDTH}" height="{SVG_NODE_HEIGHT}" '
                    'rx="9" fill="#172033" stroke="#475569"/>'
                ),
                f'    <rect x="{x:g}" y="{y:g}" width="4" height="{SVG_NODE_HEIGHT}" rx="2" fill="{color}"/>',
                (
                    f'    <text x="{x + 14:g}" y="{y + 27:g}" fill="#f8fafc" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700">'
                    f'{_svg_text(node.get("title") or node.get("id"), 30)}</text>'
                ),
                (
                    f'    <text x="{x + 14:g}" y="{y + 49:g}" fill="#94a3b8" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="11">'
                    f'{_svg_text(role, 35)}</text>'
                ),
                (
                    f'    <text x="{x + 14:g}" y="{y + 70:g}" fill="{color}" '
                    'font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700">'
                    f'{_svg_text(status.upper(), 24)}</text>'
                ),
                "  </g>",
            ]
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def template_id(node: ET.Element) -> str:
    value = node.get("template_id", "")
    if not value or not NODE_KEY_RE.match(value):
        raise TreeValidationError("template node missing valid template_id", {"value": value})
    return value


def copy_node_payload(template_node: ET.Element, runtime_node: ET.Element) -> None:
    for child in list(template_node):
        if child.tag == "children":
            continue
        if child.tag in {"result", "history"}:
            continue
        runtime_node.append(copy.deepcopy(child))


def instantiate_template_node(
    template_node: ET.Element,
    run_id: str,
    instance_id: str,
    mapping: Dict[str, str],
    pending_references: List[Tuple[ET.Element, List[str]]],
) -> ET.Element:
    tid = template_id(template_node)
    if tid in mapping:
        raise TreeValidationError("duplicate template_id in template instance", {"template_id": tid})
    canonical_type, role = normalize_type(template_node.get("type", "task"), template_node.get("role", ""))
    runtime_id = f"rt_{slug(run_id, 'run')}__{slug(instance_id, 'instance')}__{tid}"
    mapping[tid] = runtime_id
    attrs = {
        "id": runtime_id,
        "template_id": tid,
        "origin_template_id": tid,
        "origin_instance_id": instance_id,
        "title": template_node.get("title", tid),
        "type": canonical_type,
        "executor": template_node.get("executor", "subagent"),
        "status": "pending",
    }
    if role:
        attrs["role"] = role
    excluded = {
        "id",
        "template_id",
        "origin_template_id",
        "origin_instance_id",
        "status",
        "depends_on",
        "depends_on_template",
        "iteration",
        "loop.iteration",
    }
    for key, value in template_node.attrib.items():
        if key not in excluded:
            attrs[key] = value
    if role == "dynamic-group":
        attrs["dynamic.state"] = template_node.get("dynamic.state", "open")
    if canonical_type == "loop":
        attrs["loop.iteration"] = "1"
        attrs["loop.max_iterations"] = template_node.get("loop.max_iterations", "1")
        attrs["loop.continue_when"] = template_node.get("loop.continue_when", "")
        attrs["loop.break_when"] = template_node.get("loop.break_when", "")
        attrs["loop.on_limit"] = template_node.get("loop.on_limit", "failed")
    node = ET.Element("node", attrs)
    copy_node_payload(template_node, node)
    raw_refs = template_node.get("depends_on_template", "")
    if raw_refs:
        pending_references.append((node, [item.strip() for item in raw_refs.split(",") if item.strip()]))
    template_children = children(template_node)
    if template_children:
        holder = ET.SubElement(node, "children")
        for child in template_children:
            holder.append(instantiate_template_node(child, run_id, instance_id, mapping, pending_references))
    return node


def rewrite_template_references(mapping: Dict[str, str], pending: List[Tuple[ET.Element, List[str]]]) -> None:
    for node, references in pending:
        rewritten: List[str] = []
        for reference in references:
            if not reference.startswith("local:"):
                raise TreeValidationError("template references must use local:", {"reference": reference, "node": node.get("id")})
            target = reference.split(":", 1)[1]
            if target not in mapping:
                raise TreeValidationError("unresolved template reference", {"reference": reference, "node": node.get("id")})
            rewritten.append(mapping[target])
        node.set("depends_on", ",".join(rewritten))
        node.attrib.pop("depends_on_template", None)


def instantiate_runtime_tree(
    template_tree: ET.ElementTree,
    run_id: str,
    name: str,
    variables: Sequence[Tuple[str, str]],
    config: Dict[str, Any],
) -> ET.ElementTree:
    template_root = template_tree.getroot()
    validation_errors = validate_template_root(template_root)
    if validation_errors:
        raise TreeValidationError("template validation failed", {"errors": validation_errors})
    source_root = root_node(template_root)
    runtime_root = ET.Element(
        "orchestration",
        {
            "schema_version": "1",
            "name": name or template_root.get("name", "orchestration"),
            "run_id": run_id,
            "status": "pending",
            "created_at": utc_now(),
            "revision": "0",
        },
    )
    template_bb = find_direct(template_root, "blackboard")
    bb = ET.SubElement(runtime_root, "blackboard")
    if template_bb is not None:
        for var in template_bb.findall("var"):
            copied = ET.SubElement(bb, "var", dict(var.attrib))
            copied.text = var.text
    set_blackboard(runtime_root, "run_id", run_id, "init")
    set_blackboard(runtime_root, "today", today(), "init")
    for key, value in variables:
        set_blackboard(runtime_root, key, value, "init")
    mapping: Dict[str, str] = {}
    pending: List[Tuple[ET.Element, List[str]]] = []
    runtime_node = instantiate_template_node(source_root, run_id, "root", mapping, pending)
    rewrite_template_references(mapping, pending)
    runtime_root.append(runtime_node)
    meta = ensure_managed_metadata(runtime_root, "runtime", config)
    instances = ensure_direct(meta, "template_instances")
    ET.SubElement(
        instances,
        "instance",
        {
            "id": "root",
            "template_name": template_root.get("name", ""),
            "template_root_id": template_id(source_root),
        },
    )
    runtime_root.set("status", "pending")
    return ET.ElementTree(runtime_root)


def validate_template_root(root: ET.Element, check_integrity: bool = True) -> List[str]:
    errors: List[str] = []
    if root.tag != "orchestration":
        errors.append("template root element must be orchestration")
        return errors
    if root.get("schema_version") != "1":
        errors.append("template schema_version must be 1")
    if check_integrity:
        integrity = verify_integrity(root, "template")
        if integrity["status"] != "valid":
            errors.append(f"template integrity {integrity['status']}: {integrity['reason']}")
    try:
        template_root = root_node(root)
    except TreeValidationError as exc:
        return errors + [str(exc)]
    seen: set[str] = set()
    references: List[Tuple[str, str]] = []
    for node in iter_nodes(template_root):
        try:
            tid = template_id(node)
        except TreeValidationError as exc:
            errors.append(str(exc))
            continue
        if node.get("id"):
            errors.append(f"{tid}: templates must use template_id, not id")
        if tid in seen:
            errors.append(f"duplicate template_id: {tid}")
        seen.add(tid)
        try:
            normalized_type, _ = normalize_type(node.get("type", ""), node.get("role", ""))
        except TreeValidationError as exc:
            errors.append(str(exc))
            continue
        executor = node.get("executor", "")
        if executor not in VALID_EXECUTORS:
            errors.append(f"{tid}: invalid executor {executor}")
        mode = node.get("mode", "")
        if mode not in VALID_MODES:
            errors.append(f"{tid}: invalid mode {mode}")
        policy = node.get("when.policy", "")
        if policy and policy not in VALID_WHEN_POLICIES:
            errors.append(f"{tid}: invalid when.policy {policy}")
        if policy and not node.get("when"):
            errors.append(f"{tid}: when.policy requires when")
        dynamic_state = node.get("dynamic.state", "")
        if dynamic_state and (node_role(node) != "dynamic-group" or dynamic_state not in VALID_DYNAMIC_GROUP_STATES):
            errors.append(f"{tid}: invalid dynamic.state {dynamic_state}")
        status = node.get("status")
        if status not in (None, "pending"):
            errors.append(f"{tid}: template status must be omitted or pending")
        node_children = children(node)
        if normalized_type in {"task", "gate"} and node_children:
            errors.append(f"{tid}: {normalized_type} cannot have children")
        if normalized_type in {"composite", "loop"} and executor != "main":
            errors.append(f"{tid}: {normalized_type} executor must be main")
        if normalized_type == "gate" and executor != "main":
            errors.append(f"{tid}: gate executor must be main")
        if normalized_type == "loop":
            raw_maximum = node.get("loop.max_iterations", "")
            if not raw_maximum:
                errors.append(f"{tid}: loop missing loop.max_iterations")
            else:
                try:
                    if int(raw_maximum) < 1:
                        errors.append(f"{tid}: loop.max_iterations must be positive")
                except ValueError:
                    errors.append(f"{tid}: loop.max_iterations must be an integer")
            if node.get("loop.on_limit") not in {"failed", "blocked", "succeeded"}:
                errors.append(f"{tid}: loop.on_limit must be failed, blocked, or succeeded")
            if not node_children:
                errors.append(f"{tid}: loop requires at least one child")
        if normalized_type == "composite" and not node_children and node_role(node) != "dynamic-group":
            errors.append(f"{tid}: composite without children must have role=dynamic-group")
        if mode == "switch":
            if normalized_type != "composite":
                errors.append(f"{tid}: switch mode requires type=composite")
            if not node.get("switch.key"):
                errors.append(f"{tid}: switch mode requires switch.key")
            if not node_children:
                errors.append(f"{tid}: switch requires at least one case")
            default_count = 0
            for child in node_children:
                role = node_role(child)
                if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                    default_count += 1
                elif role != "case" or not child.get("case.value"):
                    errors.append(f"{tid}: switch children must be role=case with case.value or role=default")
            if default_count > 1:
                errors.append(f"{tid}: switch has multiple default cases")
        if not node_children and executor == "subagent":
            for field in ("instructions", "deliverables", "acceptance"):
                if not child_text(node, field):
                    errors.append(f"{tid}: subagent leaf missing {field}")
        if node.get("depends_on"):
            errors.append(f"{tid}: templates must use depends_on_template")
        raw = node.get("depends_on_template", "")
        for ref in [item.strip() for item in raw.split(",") if item.strip()]:
            if not ref.startswith("local:"):
                errors.append(f"{tid}: only local: template references are supported")
            references.append((tid, ref))
    for owner, ref in references:
        target = ref.split(":", 1)[1] if ref.startswith("local:") else ""
        if target not in seen:
            errors.append(f"{owner}: unresolved template reference {ref}")
    try:
        root_type = node_type(template_root)
        root_role = node_role(template_root)
    except TreeValidationError as exc:
        errors.append(f"template root node: {exc}")
    else:
        if root_type != "composite" or root_role != "root":
            errors.append("template root node must be type=composite role=root")
    if template_root.get("executor") != "main":
        errors.append("template root node executor must be main")
    if template_root.get("mode", "sequence") not in {"sequence", "parallel"}:
        errors.append("template root node mode must be sequence or parallel")
    return errors


def validate_runtime_root(root: ET.Element, check_integrity: bool = True) -> List[str]:
    errors: List[str] = []
    if root.tag != "orchestration":
        return ["runtime root element must be orchestration"]
    if root.get("schema_version") != "1":
        errors.append("runtime schema_version must be 1")
    if not root.get("run_id"):
        errors.append("runtime missing run_id")
    try:
        runtime_revision(root)
    except TreeValidationError as exc:
        errors.append(str(exc))
    if check_integrity:
        integrity = verify_integrity(root, "runtime")
        if integrity["status"] != "valid":
            errors.append(f"runtime integrity {integrity['status']}: {integrity['reason']}")
    try:
        runtime_root = root_node(root)
    except TreeValidationError as exc:
        return errors + [str(exc)]
    ids: set[str] = set()
    logical_keys: set[str] = set()
    references: List[Tuple[str, str]] = []
    for node in iter_nodes(runtime_root):
        node_id = node.get("id", "")
        if not node_id:
            errors.append("runtime node missing id")
            continue
        if node_id in ids:
            errors.append(f"duplicate runtime node id: {node_id}")
        ids.add(node_id)
        try:
            normalized_type, _ = normalize_type(node.get("type", ""), node.get("role", ""))
        except TreeValidationError as exc:
            errors.append(f"{node_id}: {exc}")
            continue
        executor = node.get("executor", "")
        if executor not in VALID_EXECUTORS:
            errors.append(f"{node_id}: invalid executor {executor}")
        status = node.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(f"{node_id}: invalid status {status}")
        node_children = children(node)
        mode = node.get("mode", "")
        if mode not in VALID_MODES:
            errors.append(f"{node_id}: invalid mode {mode}")
        policy = node.get("when.policy", "")
        if policy and policy not in VALID_WHEN_POLICIES:
            errors.append(f"{node_id}: invalid when.policy {policy}")
        if policy and not node.get("when"):
            errors.append(f"{node_id}: when.policy requires when")
        dynamic_state = node.get("dynamic.state", "")
        if dynamic_state and (node_role(node) != "dynamic-group" or dynamic_state not in VALID_DYNAMIC_GROUP_STATES):
            errors.append(f"{node_id}: invalid dynamic.state {dynamic_state}")
        if normalized_type in {"task", "gate"} and node_children:
            errors.append(f"{node_id}: {normalized_type} cannot have children")
        if normalized_type in {"task", "gate"} and mode:
            errors.append(f"{node_id}: {normalized_type} cannot set mode")
        if normalized_type in {"composite", "loop"} and executor != "main":
            errors.append(f"{node_id}: {normalized_type} executor must be main")
        if normalized_type == "gate" and executor != "main":
            errors.append(f"{node_id}: gate executor must be main")
        if normalized_type == "loop":
            raw_maximum = node.get("loop.max_iterations", "")
            try:
                if int(raw_maximum) < 1:
                    errors.append(f"{node_id}: loop.max_iterations must be positive")
            except ValueError:
                errors.append(f"{node_id}: loop.max_iterations must be an integer")
            if node.get("loop.on_limit") not in {"failed", "blocked", "succeeded"}:
                errors.append(f"{node_id}: invalid loop.on_limit")
            if not node_children:
                errors.append(f"{node_id}: loop requires at least one child")
        if normalized_type == "composite" and not node_children and node_role(node) != "dynamic-group":
            errors.append(f"{node_id}: composite without children must have role=dynamic-group")
        if mode == "switch":
            if normalized_type != "composite":
                errors.append(f"{node_id}: switch mode requires type=composite")
            if not node.get("switch.key"):
                errors.append(f"{node_id}: switch mode requires switch.key")
            default_count = 0
            for child in node_children:
                role = node_role(child)
                if role == "default" or normalize_value(child.get("case.default", "")) in {"true", "1", "yes"}:
                    default_count += 1
                elif role != "case" or not child.get("case.value"):
                    errors.append(f"{node_id}: invalid switch child {child.get('id', '')}")
            if default_count > 1:
                errors.append(f"{node_id}: switch has multiple default cases")
        if not node_children and executor == "subagent":
            for field in ("instructions", "deliverables", "acceptance"):
                if not child_text(node, field):
                    errors.append(f"{node_id}: subagent leaf missing {field}")
        logical_key = node.get("logical_key", "")
        if logical_key:
            if not NODE_KEY_RE.match(logical_key):
                errors.append(f"{node_id}: invalid logical_key")
            elif logical_key in logical_keys:
                errors.append(f"duplicate runtime logical_key: {logical_key}")
            logical_keys.add(logical_key)
        if node.get("depends_on_template"):
            errors.append(f"{node_id}: unresolved depends_on_template")
        references.extend((node_id, ref) for ref in node.get("depends_on", "").split(",") if ref)
    for owner, reference in references:
        if reference.strip() not in ids:
            errors.append(f"{owner}: unresolved runtime dependency {reference.strip()}")
    try:
        root_type = node_type(runtime_root)
        root_role = node_role(runtime_root)
    except TreeValidationError as exc:
        errors.append(f"runtime root node: {exc}")
    else:
        if root_type != "composite" or root_role != "root":
            errors.append("runtime root node must be type=composite role=root")
    if runtime_root.get("executor") != "main":
        errors.append("runtime root node executor must be main")
    if runtime_root.get("mode", "sequence") not in {"sequence", "parallel"}:
        errors.append("runtime root node mode must be sequence or parallel")
    if root.get("status") != runtime_root.get("status"):
        errors.append("runtime root status does not match root node status")
    return errors


def create_dynamic_node(
    root: ET.Element,
    parent_id: str,
    logical_key: str,
    title: str,
    node_type_value: str,
    executor: str,
    role: str = "",
    mode: str = "",
    when: str = "",
    depends_on: str = "",
    instructions: str = "",
    inputs: str = "",
    deliverables: str = "",
    acceptance: str = "",
    metadata: Optional[Sequence[Tuple[str, str]]] = None,
) -> ET.Element:
    if not NODE_KEY_RE.match(logical_key):
        raise TreeValidationError("logical_key must be lowercase kebab-case", {"logical_key": logical_key})
    parent = find_node(root, parent_id)
    if node_type(parent) not in {"composite", "loop"}:
        raise TreeValidationError("dynamic node parent must be composite or loop", {"parent_id": parent_id})
    require_dynamic_group_open(parent)
    if any(existing.get("logical_key") == logical_key for existing in iter_nodes(root)):
        raise TreeValidationError("logical_key already exists in runtime tree", {"logical_key": logical_key})
    canonical_type, normalized_role = normalize_type(node_type_value, role)
    if executor not in VALID_EXECUTORS:
        raise TreeValidationError("invalid dynamic node executor", {"executor": executor})
    if mode not in VALID_MODES:
        raise TreeValidationError("invalid dynamic node mode", {"mode": mode})
    if canonical_type in {"composite", "loop"} and executor != "main":
        raise TreeValidationError("composite and loop dynamic nodes require executor=main")
    if canonical_type == "gate" and executor != "main":
        raise TreeValidationError("dynamic gate requires executor=main")
    if canonical_type in {"task", "gate"} and mode:
        raise TreeValidationError("dynamic task and gate nodes cannot set mode")
    if executor == "subagent":
        missing = [
            field
            for field, value in (
                ("instructions", instructions),
                ("deliverables", deliverables),
                ("acceptance", acceptance),
            )
            if not value
        ]
        if missing:
            raise TreeValidationError("dynamic subagent node missing required fields", {"fields": missing})
    if depends_on:
        missing_dependencies = [
            dependency.strip()
            for dependency in depends_on.split(",")
            if dependency.strip() and dependency.strip() not in nodes_by_id(root)
        ]
        if missing_dependencies:
            raise TreeValidationError("dynamic node has unresolved dependencies", {"dependencies": missing_dependencies})
    holder = ensure_direct(parent, "children")
    run_id = root.get("run_id", "run")
    sequence = 1
    while True:
        instance_id = f"dyn-{sequence}"
        runtime_id = f"rt_{slug(run_id, 'run')}__{instance_id}__{logical_key}"
        if runtime_id not in nodes_by_id(root):
            break
        sequence += 1
    attrs = {
        "id": runtime_id,
        "logical_key": logical_key,
        "origin_instance_id": instance_id,
        "title": title,
        "type": canonical_type,
        "executor": executor,
        "status": "pending",
    }
    if normalized_role:
        attrs["role"] = normalized_role
    if normalized_role == "dynamic-group":
        attrs["dynamic.state"] = "open"
    if mode:
        attrs["mode"] = mode
    if when:
        attrs["when"] = when
    if depends_on:
        attrs["depends_on"] = depends_on
    for key, value in metadata or []:
        attrs[key] = value
    root.attrib.pop("reopen_pending", None)
    node = ET.SubElement(holder, "node", attrs)
    for tag, value in (
        ("instructions", instructions),
        ("inputs", inputs),
        ("deliverables", deliverables),
        ("acceptance", acceptance),
    ):
        if value:
            child = ET.SubElement(node, tag)
            child.text = value
    return node


def embed_template_subtree(
    root: ET.Element,
    parent_id: str,
    template_tree: ET.ElementTree,
    config: Dict[str, Any],
    instance_id: Optional[str] = None,
) -> ET.Element:
    validation_errors = validate_template_root(template_tree.getroot())
    if validation_errors:
        raise TreeValidationError("template validation failed", {"errors": validation_errors})
    parent = find_node(root, parent_id)
    if node_type(parent) not in {"composite", "loop"}:
        raise TreeValidationError("subtree parent must be composite or loop", {"parent_id": parent_id})
    require_dynamic_group_open(parent)
    holder = ensure_direct(parent, "children")
    meta = ensure_managed_metadata(root, "runtime", config)
    instances = ensure_direct(meta, "template_instances")
    sequence = len(instances.findall("instance")) + 1
    instance = instance_id or f"subtree-{sequence}"
    if not NODE_KEY_RE.match(instance):
        raise TreeValidationError("instance_id must be lowercase kebab-case", {"instance_id": instance})
    if any(item.get("id") == instance for item in instances.findall("instance")):
        raise TreeValidationError("instance_id already exists", {"instance_id": instance})
    mapping: Dict[str, str] = {}
    pending: List[Tuple[ET.Element, List[str]]] = []
    child_root = instantiate_template_node(root_node(template_tree.getroot()), root.get("run_id", "run"), instance, mapping, pending)
    rewrite_template_references(mapping, pending)
    existing_ids = nodes_by_id(root)
    collisions = sorted(set(mapping.values()) & set(existing_ids))
    if collisions:
        raise TreeValidationError("embedded runtime IDs would collide", {"ids": collisions})
    holder.append(child_root)
    root.attrib.pop("reopen_pending", None)
    ET.SubElement(
        instances,
        "instance",
        {
            "id": instance,
            "template_name": template_tree.getroot().get("name", ""),
            "template_root_id": template_id(root_node(template_tree.getroot())),
        },
    )
    return child_root


def require_executable_leaf(root: ET.Element, node_id: str) -> ET.Element:
    node = find_node(root, node_id)
    if node_type(node) not in {"task", "gate"} or children(node):
        raise RuntimeErrorBase("operation requires an executable task or gate leaf", {"node_id": node_id})
    return node


def begin_node(root: ET.Element, node_id: str, agent: str = "") -> ET.Element:
    node = require_executable_leaf(root, node_id)
    blocker = node_readiness_blocker(root, node)
    if blocker is not None:
        raise NodeNotReadyError(
            "node is not ready",
            {
                "node_id": node_id,
                "status": node.get("status", "pending"),
                **blocker,
            },
        )
    node.set("status", "running")
    node.set("started_at", utc_now())
    if agent:
        node.set("agent", agent)
    stabilize(root)
    return node


def append_result_artifacts(result: ET.Element, artifacts: Optional[Sequence[str]] = None) -> None:
    if not artifacts:
        return
    holder = ensure_direct(result, "artifacts")
    for artifact in artifacts:
        ET.SubElement(holder, "artifact", {"path": artifact})


def complete_node(
    root: ET.Element,
    node_id: str,
    summary: str = "",
    artifacts: Optional[Sequence[str]] = None,
    validation: str = "",
    variables: Optional[Sequence[Tuple[str, str]]] = None,
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "complete requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    node.set("status", "succeeded")
    node.set("completed_at", utc_now())
    result = ensure_node_child(node, "result")
    if summary:
        ensure_node_child(result, "summary").text = summary
    append_result_artifacts(result, artifacts)
    if validation:
        ensure_node_child(result, "validation").text = validation
    for key, value in variables or []:
        set_blackboard(root, key, value, node_id)
    stabilize(root)
    return node


def fail_node(
    root: ET.Element,
    node_id: str,
    reason: str,
    artifacts: Optional[Sequence[str]] = None,
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "fail requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    node.set("status", "failed")
    node.set("failed_at", utc_now())
    result = ensure_node_child(node, "result")
    ensure_node_child(result, "failure_reason").text = reason
    append_result_artifacts(result, artifacts)
    stabilize(root)
    return node


def block_node(
    root: ET.Element,
    node_id: str,
    reason: str,
    artifacts: Optional[Sequence[str]] = None,
) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "running":
        raise InvalidTransitionError(
            "block requires a running node",
            {"node_id": node_id, "status": node.get("status", "pending")},
        )
    node.set("status", "blocked")
    node.set("blocked_at", utc_now())
    node.set("block_reason", reason)
    append_result_artifacts(ensure_node_child(node, "result"), artifacts)
    stabilize(root)
    return node


def unblock_node(root: ET.Element, node_id: str) -> ET.Element:
    node = require_executable_leaf(root, node_id)
    if node.get("status") != "blocked":
        raise RuntimeErrorBase("node is not blocked", {"node": node_id, "status": node.get("status")})
    node.set("status", "pending")
    for key in ("blocked_at", "block_reason"):
        node.attrib.pop(key, None)
    stabilize(root)
    return node
