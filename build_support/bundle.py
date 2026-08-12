"""Deterministic Stage 1 Bundle collection from canonical repository inputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


BUNDLE_SCHEMA_VERSION = 1
RUNTIME_TREE_SCHEMA = 1
SOURCE_STATE = "work-order-candidate"
MANIFEST_NAME = "bundle-manifest.json"
VIEWER_PREFIX = "skills/xc-orchestration-runtime/viewer/static/"

_ADAPTER_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_LOWER_HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_REGULAR_GIT_MODES = {"100644", "100755"}


class BundleBuildError(RuntimeError):
    """Fail-closed collector error with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class CandidateProvenance:
    baseline_revision: str
    candidate_tree_sha256: str
    candidate_source_archive_sha256: str
    source_state: str = SOURCE_STATE

    def validate(self) -> None:
        if not _LOWER_HEX_40.fullmatch(self.baseline_revision):
            raise BundleBuildError(
                "source_mismatch",
                "baseline_revision must be 40 lowercase hexadecimal characters",
            )
        for field_name in (
            "candidate_tree_sha256",
            "candidate_source_archive_sha256",
        ):
            if not _LOWER_HEX_64.fullmatch(getattr(self, field_name)):
                raise BundleBuildError(
                    "source_mismatch",
                    f"{field_name} must be 64 lowercase hexadecimal characters",
                )
        if self.source_state != SOURCE_STATE:
            raise BundleBuildError(
                "source_mismatch",
                f"source_state must be {SOURCE_STATE!r}",
            )


@dataclass(frozen=True)
class ResourceInput:
    kind: str
    adapter_id: str | None
    source_path: str
    bundle_path: str
    data: bytes

    def manifest_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "adapter_id": self.adapter_id,
            "source_path": self.source_path,
            "bundle_path": self.bundle_path,
            "size": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
        }


def _raise_invalid(message: str, **details: Any) -> None:
    raise BundleBuildError("manifest_invalid", message, details=details)


def validate_relative_path(value: object, *, field: str) -> str:
    """Validate a portable, unnormalized POSIX relative path."""
    if not isinstance(value, str) or not value:
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} must be a non-empty string",
        )
    if "\\" in value or "\x00" in value:
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} must use safe forward-slash relative syntax",
            details={"path": value},
        )
    if value.startswith("/") or re.match(r"[A-Za-z]:", value):
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} must be relative",
            details={"path": value},
        )
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} contains an empty, dot, or parent segment",
            details={"path": value},
        )
    if any(any(ord(character) < 32 for character in part) for part in parts):
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} contains a control character",
            details={"path": value},
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{field} is not valid UTF-8",
            details={"path": repr(value)},
        ) from error
    return value


def validate_path_set(paths: Iterable[str], *, field: str) -> list[str]:
    """Reject exact, Windows case-fold, and Unicode NFC path collisions."""
    values = list(paths)
    exact: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for value in values:
        validate_relative_path(value, field=field)
        collision_kind = ""
        previous: str | None = None
        if value in exact:
            collision_kind, previous = "duplicate", exact[value]
        elif value.casefold() in casefolded:
            collision_kind, previous = "casefold", casefolded[value.casefold()]
        elif unicodedata.normalize("NFC", value) in normalized:
            collision_kind, previous = (
                "nfc",
                normalized[unicodedata.normalize("NFC", value)],
            )
        if previous is not None:
            raise BundleBuildError(
                "resource_path_collision",
                f"{field} has a {collision_kind} collision",
                details={
                    "collision": collision_kind,
                    "first": previous,
                    "second": value,
                },
            )
        exact[value] = value
        casefolded[value.casefold()] = value
        normalized[unicodedata.normalize("NFC", value)] = value
    return values


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _raise_invalid(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    if _path_is_link_or_junction(path):
        raise BundleBuildError(
            "resource_path_unsafe",
            "configuration inputs must not be symlinks or junctions",
            details={"path": str(path)},
        )
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise BundleBuildError(
                "resource_path_unsafe",
                "configuration inputs must be regular files",
                details={"path": str(path)},
            )
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        _raise_invalid(f"cannot parse {path}: {error}")
    if not isinstance(value, dict):
        _raise_invalid(f"{path}: root must be an object")
    return value


def load_project_metadata(project_root: Path) -> tuple[str, str]:
    path = project_root / "pyproject.toml"
    if _path_is_link_or_junction(path):
        raise BundleBuildError(
            "resource_path_unsafe",
            "pyproject.toml must not be a symlink or junction",
        )
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise BundleBuildError(
                "resource_path_unsafe",
                "pyproject.toml must be a regular file",
            )
        value = tomllib.loads(path.read_text(encoding="utf-8"))
        project = value["project"]
        version = project["version"]
        python_requires = project["requires-python"]
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError) as error:
        _raise_invalid(f"cannot load package metadata from {path}: {error}")
    if not isinstance(version, str) or not version:
        _raise_invalid("project.version must be a non-empty string")
    if not isinstance(python_requires, str) or not python_requires:
        _raise_invalid("project.requires-python must be a non-empty string")
    return version, python_requires


def _path_is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    return bool(os_is_junction and os_is_junction(path))


def _assert_directory(path: Path, *, label: str) -> None:
    if _path_is_link_or_junction(path):
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{label} must not be a symlink or junction",
            details={"path": str(path)},
        )
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise BundleBuildError(
            "resource_missing",
            f"{label} is unavailable: {path}",
        ) from error
    if not stat.S_ISDIR(mode):
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{label} must be a directory",
            details={"path": str(path)},
        )


def _assert_safe_components(
    project_root: Path,
    relative_path: str,
    *,
    label: str,
) -> None:
    current = project_root
    for part in relative_path.split("/"):
        current /= part
        if _path_is_link_or_junction(current):
            raise BundleBuildError(
                "resource_path_unsafe",
                f"{label} must not traverse a symlink or junction",
                details={"path": str(current)},
            )


def _walk_regular_files(root: Path, *, repository_relative_root: str) -> dict[str, Path]:
    _assert_directory(root, label=repository_relative_root)
    files: dict[str, Path] = {}
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as error:
            raise BundleBuildError(
                "resource_path_unsafe",
                f"cannot enumerate {directory}: {error}",
            ) from error
        for entry in reversed(entries):
            relative = entry.relative_to(root).as_posix()
            repository_relative = (
                f"{repository_relative_root}/{relative}"
                if relative
                else repository_relative_root
            )
            validate_relative_path(repository_relative, field="source_path")
            if _path_is_link_or_junction(entry):
                raise BundleBuildError(
                    "resource_path_unsafe",
                    "canonical inputs must not contain symlinks or junctions",
                    details={"path": repository_relative},
                )
            try:
                mode = entry.lstat().st_mode
            except OSError as error:
                raise BundleBuildError(
                    "resource_path_unsafe",
                    f"cannot inspect {repository_relative}: {error}",
                ) from error
            if stat.S_ISDIR(mode):
                if entry.name == "__pycache__":
                    continue
                stack.append(entry)
            elif stat.S_ISREG(mode):
                if entry.suffix in {".pyc", ".pyo"}:
                    continue
                files[repository_relative] = entry
            else:
                raise BundleBuildError(
                    "resource_path_unsafe",
                    "canonical inputs must contain only directories and regular files",
                    details={"path": repository_relative},
                )
    validate_path_set(files, field="source_path")
    return files


def _run_git(
    project_root: Path,
    arguments: list[str],
    *,
    text: bool = False,
) -> subprocess.CompletedProcess[Any]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *arguments],
            capture_output=True,
            text=text,
            encoding="utf-8" if text else None,
            check=False,
        )
    except OSError as error:
        raise BundleBuildError("source_mismatch", f"cannot execute Git: {error}") from error
    return result


def _tracked_entries(project_root: Path) -> dict[str, str]:
    result = _run_git(project_root, ["ls-files", "--stage", "-z"])
    if result.returncode != 0:
        raise BundleBuildError(
            "source_mismatch",
            "cannot read the tracked candidate inventory",
            details={"stderr": result.stderr.decode("utf-8", errors="replace")},
        )
    entries: dict[str, str] = {}
    for raw_record in result.stdout.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode, _object_id, stage = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeError) as error:
            raise BundleBuildError(
                "resource_path_unsafe",
                "tracked candidate inventory contains an invalid path record",
            ) from error
        validate_relative_path(path, field="source_path")
        if stage != "0":
            raise BundleBuildError(
                "source_mismatch",
                "candidate inventory contains an unmerged path",
                details={"path": path, "stage": stage},
            )
        entries[path] = mode
    validate_path_set(entries, field="source_path")
    return entries


def _require_tracked_regular(
    paths: Iterable[str],
    tracked: dict[str, str],
    *,
    label: str,
) -> None:
    requested = set(paths)
    missing = sorted(requested - tracked.keys())
    invalid_modes = sorted(
        path
        for path in requested & tracked.keys()
        if tracked[path] not in _REGULAR_GIT_MODES
    )
    if missing:
        raise BundleBuildError(
            "resource_missing",
            f"{label} contains untracked or missing files",
            details={"paths": missing},
        )
    if invalid_modes:
        raise BundleBuildError(
            "resource_path_unsafe",
            f"{label} contains non-regular Git entries",
            details={
                "paths": [
                    {"path": path, "mode": tracked[path]} for path in invalid_modes
                ]
            },
        )


def _require_exact_set(
    actual: Iterable[str],
    expected: Iterable[str],
    *,
    label: str,
) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    if missing or unexpected:
        raise BundleBuildError(
            "source_mismatch",
            f"{label} does not match its exact tracked or declared inventory",
            details={"missing": missing, "unexpected": unexpected},
        )


def _require_clean_inputs(project_root: Path, roots: Iterable[str]) -> None:
    arguments = ["--quiet", "--no-ext-diff", "--", *sorted(set(roots))]
    for mode, prefix in (
        ("worktree", ["diff"]),
        ("index", ["diff", "--cached"]),
    ):
        result = _run_git(project_root, [*prefix, *arguments])
        if result.returncode == 1:
            raise BundleBuildError(
                "source_mismatch",
                f"canonical Bundle inputs differ from the sealed tracked candidate ({mode})",
            )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise BundleBuildError(
                "source_mismatch",
                f"cannot verify canonical Bundle input state ({mode})",
                details={"stderr": stderr},
            )


def _skill_files(project_root: Path, tracked: dict[str, str]) -> dict[str, Path]:
    skills_root = project_root / "skills"
    _assert_directory(skills_root, label="skills")
    actual: dict[str, Path] = {}
    for entry in sorted(skills_root.iterdir(), key=lambda item: item.name):
        if not entry.name.startswith("xc-"):
            continue
        if _path_is_link_or_junction(entry):
            raise BundleBuildError(
                "resource_path_unsafe",
                "Skill package roots must not be symlinks or junctions",
                details={"path": f"skills/{entry.name}"},
            )
        package_files = _walk_regular_files(
            entry,
            repository_relative_root=f"skills/{entry.name}",
        )
        actual.update(package_files)
    expected = {
        path
        for path in tracked
        if path.startswith("skills/xc-") and "/" in path[len("skills/") :]
    }
    if not expected:
        raise BundleBuildError("resource_missing", "no tracked canonical Skill files found")
    _require_exact_set(actual, expected, label="canonical Skill inventory")
    _require_tracked_regular(actual, tracked, label="canonical Skill inventory")
    return actual


def _files_under(
    project_root: Path,
    relative_root: str,
    tracked: dict[str, str],
    *,
    label: str,
) -> dict[str, Path]:
    validate_relative_path(relative_root, field=f"{label}.root")
    _assert_safe_components(
        project_root,
        relative_root,
        label=label,
    )
    actual = _walk_regular_files(
        project_root.joinpath(*relative_root.split("/")),
        repository_relative_root=relative_root,
    )
    expected = {
        path
        for path in tracked
        if path == relative_root or path.startswith(f"{relative_root}/")
    }
    _require_exact_set(actual, expected, label=label)
    _require_tracked_regular(actual, tracked, label=label)
    return actual


def _require_keys(
    value: dict[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        _raise_invalid(
            f"{label} has invalid fields",
            missing=sorted(expected - actual),
            unexpected=sorted(actual - expected),
        )


def _load_adapter_inputs(
    project_root: Path,
    tracked: dict[str, str],
    config_path: Path,
    *,
    run_exporter: bool,
) -> list[ResourceInput]:
    config = _strict_json(config_path)
    _require_keys(
        config,
        {
            "schema_version",
            "purpose",
            "canonical_agents",
            "exporter_check",
            "exact_set_policy",
            "adapters",
        },
        label="host adapter configuration",
    )
    if config["schema_version"] != 1:
        _raise_invalid("host adapter configuration schema_version must be 1")

    canonical = config["canonical_agents"]
    exporter = config["exporter_check"]
    policy = config["exact_set_policy"]
    adapters = config["adapters"]
    if not all(isinstance(item, dict) for item in (canonical, exporter, policy)):
        _raise_invalid("host adapter configuration sections must be objects")
    if not isinstance(adapters, list) or not adapters:
        _raise_invalid("host adapter configuration adapters must be a non-empty list")
    _require_keys(canonical, {"root", "filename_suffix"}, label="canonical_agents")
    _require_keys(exporter, {"argv"}, label="exporter_check")
    _require_keys(
        policy,
        {
            "derive_from_canonical_agent_stems",
            "require_tracked_regular_files",
            "reject_missing",
            "reject_changed",
            "reject_extra",
        },
        label="exact_set_policy",
    )
    if set(policy.values()) != {True}:
        _raise_invalid("all host adapter exact_set_policy controls must be true")

    canonical_root = validate_relative_path(canonical["root"], field="canonical_agents.root")
    suffix = canonical["filename_suffix"]
    if not isinstance(suffix, str) or not suffix.startswith("."):
        _raise_invalid("canonical_agents.filename_suffix must start with a dot")
    canonical_files = _files_under(
        project_root,
        canonical_root,
        tracked,
        label="canonical agent inventory",
    )
    stems: list[str] = []
    for source_path in sorted(canonical_files):
        relative = source_path.removeprefix(f"{canonical_root}/")
        if "/" in relative or not relative.endswith(suffix):
            _raise_invalid(
                "canonical agent inventory must contain only direct files with the declared suffix",
                path=source_path,
            )
        stems.append(relative[: -len(suffix)])
    if not stems:
        raise BundleBuildError("resource_missing", "no canonical agent definitions found")

    argv = exporter["argv"]
    if (
        not isinstance(argv, list)
        or len(argv) < 2
        or any(not isinstance(argument, str) or not argument for argument in argv)
    ):
        _raise_invalid("exporter_check.argv must be a non-empty string array")
    exporter_script = validate_relative_path(
        argv[1],
        field="exporter_check.argv[1]",
    )
    _require_tracked_regular(
        [exporter_script],
        tracked,
        label="host adapter exporter",
    )
    exporter_path = project_root.joinpath(*exporter_script.split("/"))
    _assert_safe_components(
        project_root,
        exporter_script,
        label="host adapter exporter",
    )
    if (
        _path_is_link_or_junction(exporter_path)
        or not stat.S_ISREG(exporter_path.lstat().st_mode)
    ):
        raise BundleBuildError(
            "resource_path_unsafe",
            "host adapter exporter must be a regular file",
            details={"path": exporter_script},
        )
    if run_exporter:
        command = list(argv)
        if command[0] in {"python", "python3"}:
            command[0] = sys.executable
        try:
            result = subprocess.run(
                command,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except OSError as error:
            raise BundleBuildError(
                "source_mismatch",
                f"cannot execute host adapter exporter check: {error}",
            ) from error
        if result.returncode != 0:
            raise BundleBuildError(
                "source_mismatch",
                "host adapter exporter check failed",
                details={"stdout": result.stdout, "stderr": result.stderr},
            )

    adapter_ids: list[str] = []
    generated_roots: list[str] = []
    bundle_roots: list[str] = []
    resources: list[ResourceInput] = []
    for index, raw_adapter in enumerate(adapters):
        if not isinstance(raw_adapter, dict):
            _raise_invalid(f"adapters[{index}] must be an object")
        _require_keys(
            raw_adapter,
            {
                "adapter_id",
                "generated_root",
                "generated_filename_suffix",
                "bundle_root",
                "project_agents_root",
                "project_skills_root",
            },
            label=f"adapters[{index}]",
        )
        adapter_id = raw_adapter["adapter_id"]
        if not isinstance(adapter_id, str) or not _ADAPTER_ID.fullmatch(adapter_id):
            _raise_invalid(f"adapters[{index}].adapter_id is not canonical")
        generated_root = validate_relative_path(
            raw_adapter["generated_root"],
            field=f"adapters[{index}].generated_root",
        )
        generated_suffix = raw_adapter["generated_filename_suffix"]
        if not isinstance(generated_suffix, str) or not generated_suffix.startswith("."):
            _raise_invalid(
                f"adapters[{index}].generated_filename_suffix must start with a dot"
            )
        bundle_root = validate_relative_path(
            raw_adapter["bundle_root"],
            field=f"adapters[{index}].bundle_root",
        )
        if bundle_root != f"adapters/{adapter_id}":
            _raise_invalid(
                f"adapters[{index}].bundle_root must equal adapters/<adapter_id>"
            )
        validate_relative_path(
            raw_adapter["project_agents_root"],
            field=f"adapters[{index}].project_agents_root",
        )
        validate_relative_path(
            raw_adapter["project_skills_root"],
            field=f"adapters[{index}].project_skills_root",
        )
        adapter_ids.append(adapter_id)
        generated_roots.append(generated_root)
        bundle_roots.append(bundle_root)

        generated_files = _files_under(
            project_root,
            generated_root,
            tracked,
            label=f"{adapter_id} generated inventory",
        )
        expected_paths = {
            f"{generated_root}/{stem}{generated_suffix}" for stem in stems
        }
        _require_exact_set(
            generated_files,
            expected_paths,
            label=f"{adapter_id} generated inventory",
        )
        for source_path in sorted(generated_files):
            filename = source_path.removeprefix(f"{generated_root}/")
            bundle_path = f"{bundle_root}/{filename}"
            resources.append(
                ResourceInput(
                    kind="host-adapter",
                    adapter_id=adapter_id,
                    source_path=source_path,
                    bundle_path=bundle_path,
                    data=generated_files[source_path].read_bytes(),
                )
            )

    validate_path_set(adapter_ids, field="adapter_id")
    validate_path_set(generated_roots, field="generated_root")
    validate_path_set(bundle_roots, field="bundle_root")
    return resources


def collect_bundle(
    project_root: Path | str,
    staging_root: Path | str,
    provenance: CandidateProvenance,
    *,
    run_exporter: bool = True,
) -> Path:
    """Collect canonical resources into ``<staging>/xcoding/_bundle``."""
    project_argument = Path(project_root)
    staging_argument = Path(staging_root)
    if not project_argument.is_absolute() or not staging_argument.is_absolute():
        raise BundleBuildError(
            "resource_path_unsafe",
            "project_root and staging_root must be absolute",
        )
    project = project_argument.absolute()
    staging = staging_argument.absolute()
    _assert_directory(project, label="project_root")
    _assert_directory(staging, label="staging_root")
    try:
        staging.relative_to(project)
    except ValueError:
        pass
    else:
        raise BundleBuildError(
            "resource_path_unsafe",
            "staging_root must be outside the project tree",
        )

    provenance.validate()
    tracked = _tracked_entries(project)
    _require_clean_inputs(
        project,
        (
            "skills",
            "agents-src",
        ),
    )
    skills = _skill_files(project, tracked)
    resources: list[ResourceInput] = []
    for source_path in sorted(skills):
        kind = "viewer" if source_path.startswith(VIEWER_PREFIX) else "skill"
        resources.append(
            ResourceInput(
                kind=kind,
                adapter_id=None,
                source_path=source_path,
                bundle_path=source_path,
                data=skills[source_path].read_bytes(),
            )
        )
    resources.extend(
        _load_adapter_inputs(
            project,
            tracked,
            project / "build_support" / "host_adapters.json",
            run_exporter=run_exporter,
        )
    )

    source_paths = [resource.source_path for resource in resources]
    bundle_paths = [resource.bundle_path for resource in resources]
    validate_path_set(source_paths, field="source_path")
    validate_path_set(bundle_paths, field="bundle_path")
    partitions = {
        kind: {item.bundle_path for item in resources if item.kind == kind}
        for kind in ("skill", "viewer", "host-adapter")
    }
    if any(
        partitions[left] & partitions[right]
        for left, right in (
            ("skill", "viewer"),
            ("skill", "host-adapter"),
            ("viewer", "host-adapter"),
        )
    ):
        raise BundleBuildError(
            "resource_path_collision",
            "Bundle resource partitions are not disjoint",
        )
    if set().union(*partitions.values()) != set(bundle_paths):
        _raise_invalid("Bundle resource partitions do not cover the exact inventory")

    version, python_requires = load_project_metadata(project)
    manifest = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "xc_version": version,
        "baseline_revision": provenance.baseline_revision,
        "source_state": provenance.source_state,
        "candidate_tree_sha256": provenance.candidate_tree_sha256,
        "candidate_source_archive_sha256": (
            provenance.candidate_source_archive_sha256
        ),
        "python_requires": python_requires,
        "runtime_tree_schema": RUNTIME_TREE_SCHEMA,
        "resources": [
            resource.manifest_record()
            for resource in sorted(resources, key=lambda item: item.bundle_path)
        ],
    }

    package_stage = staging / "xcoding"
    bundle_stage = package_stage / "_bundle"
    if package_stage.exists() or package_stage.is_symlink():
        raise BundleBuildError(
            "resource_path_unsafe",
            "staging_root already contains the collector-owned xcoding path",
            details={"path": str(package_stage)},
        )
    package_stage.mkdir()
    try:
        bundle_stage.mkdir()
        for resource in sorted(resources, key=lambda item: item.bundle_path):
            target = bundle_stage.joinpath(*resource.bundle_path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(resource.data)
        (bundle_stage / MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest))
        _require_clean_inputs(
            project,
            (
                "skills",
                "agents-src",
            ),
        )
    except BaseException:
        shutil.rmtree(package_stage, ignore_errors=True)
        raise
    return bundle_stage


__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "BundleBuildError",
    "CandidateProvenance",
    "MANIFEST_NAME",
    "RUNTIME_TREE_SCHEMA",
    "SOURCE_STATE",
    "VIEWER_PREFIX",
    "canonical_json_bytes",
    "collect_bundle",
    "load_project_metadata",
    "validate_path_set",
    "validate_relative_path",
]
