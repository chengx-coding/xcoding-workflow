"""Isolated prerelease bootstrap fixture for the Stage 1 package spike.

This is not a supported public installer. It consumes only explicit local
artifacts and confines all mutable state to a caller-owned fixture root.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import errno
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile
from contextlib import contextmanager
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1
FIXTURE_SCHEMA_VERSION = 1
DISTRIBUTION = "xcoding-workflow-spike"
EXPECTED_VERSION = "0.0.0.dev0"
EXIT_INPUT = 2
EXIT_VERIFY = 3
EXIT_ENVIRONMENT = 4
EXIT_INTERNAL = 5
EXIT_DRIFT = 6
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
UV_VERSION_PATTERN = re.compile(r"^uv ([0-9]+\.[0-9]+\.[0-9]+)(?:\s|$)")
FAILURE_POINTS = frozenset(
    {
        "download",
        "uv-hash",
        "python-install",
        "wheel-hash",
        "wheel-install",
        "launcher",
        "post-check",
        "activation",
    }
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_PROCESS_INSTANCE_TOKEN = uuid.uuid4().hex

_WINDOWS_FILE_READ_DATA = 0x0001
_WINDOWS_FILE_LIST_DIRECTORY = 0x0001
_WINDOWS_FILE_WRITE_DATA = 0x0002
_WINDOWS_FILE_READ_ATTRIBUTES = 0x0080
_WINDOWS_DELETE = 0x00010000
_WINDOWS_FILE_SHARE_READ = 0x00000001
_WINDOWS_FILE_SHARE_WRITE = 0x00000002
_WINDOWS_FILE_SHARE_DELETE = 0x00000004
_WINDOWS_OPEN_EXISTING = 3
_WINDOWS_SYNCHRONIZE = 0x00100000
_WINDOWS_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_WINDOWS_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_WINDOWS_FILE_ATTRIBUTE_NORMAL = 0x00000080
_WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_WINDOWS_FILE_DISPOSITION_INFO_CLASS = 4
_WINDOWS_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_WINDOWS_OBJ_CASE_INSENSITIVE = 0x00000040
_WINDOWS_OBJ_DONT_REPARSE = 0x00001000
_WINDOWS_FILE_OPEN = 1
_WINDOWS_FILE_CREATE = 2
_WINDOWS_FILE_DIRECTORY_FILE = 0x00000001
_WINDOWS_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_WINDOWS_FILE_NON_DIRECTORY_FILE = 0x00000040
_WINDOWS_FILE_OPEN_REPARSE_POINT = 0x00200000
_WINDOWS_LOCK_BYTE_OFFSET = 1 << 30
_WINDOWS_KERNEL32: Any = None
_WINDOWS_NTDLL: Any = None
_CONTROL_FILE_CONVERGENCE_TIMEOUT_SECONDS = 5.0
_CONTROL_FILE_CONVERGENCE_POLL_SECONDS = 0.002
_OPERATION_LOCK_PUBLICATION_TIMEOUT_SECONDS = 1.0
_OPERATION_LOCK_PUBLICATION_POLL_SECONDS = 0.002
_POSIX_DELETE_QUARANTINE_PREFIX = ".xc-delete-quarantine-"


class InstallerError(RuntimeError):
    """A stable, machine-readable prerelease bootstrap failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.details = details or {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, value: object) -> str:
    data = _canonical_json(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + _CONTROL_FILE_CONVERGENCE_TIMEOUT_SECONDS
        while True:
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if (
                    os.name != "nt"
                    or time.monotonic() >= deadline
                ):
                    raise
                time.sleep(_CONTROL_FILE_CONVERGENCE_POLL_SECONDS)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _load_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InstallerError(
            code,
            f"cannot read valid JSON from {path}",
            exit_code=EXIT_VERIFY,
            details={"path": str(path), "exception": type(error).__name__},
        ) from error
    if not isinstance(value, dict):
        raise InstallerError(
            code,
            f"JSON root must be an object: {path}",
            exit_code=EXIT_VERIFY,
            details={"path": str(path)},
        )
    return value


def _absolute_file(value: str, *, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise InstallerError(
            f"{field}_not_absolute",
            f"{field} must be an absolute path",
            exit_code=EXIT_INPUT,
            details={field: value},
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise InstallerError(
            f"{field}_unavailable",
            f"{field} does not resolve to an existing file",
            exit_code=EXIT_INPUT,
            details={field: value, "exception": type(error).__name__},
        ) from error
    if not resolved.is_file() or resolved.is_symlink():
        raise InstallerError(
            f"{field}_not_regular",
            f"{field} must be a regular non-link file",
            exit_code=EXIT_INPUT,
            details={field: str(resolved)},
        )
    return resolved


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _fixture_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise InstallerError(
            "fixture_root_not_absolute",
            "fixture root must be an absolute path",
            exit_code=EXIT_INPUT,
            details={"fixture_root": value},
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise InstallerError(
            "fixture_root_unavailable",
            "fixture root must already exist",
            exit_code=EXIT_INPUT,
            details={"fixture_root": value, "exception": type(error).__name__},
        ) from error
    if not resolved.is_dir() or resolved.is_symlink():
        raise InstallerError(
            "fixture_root_not_directory",
            "fixture root must be a real directory",
            exit_code=EXIT_INPUT,
            details={"fixture_root": str(resolved)},
        )

    prohibited = [REPOSITORY_ROOT.resolve()]
    workshop = REPOSITORY_ROOT / ".xcoding"
    if workshop.exists():
        prohibited.append(workshop.resolve())
    for root in prohibited:
        if _path_within(resolved, root) or _path_within(root, resolved):
            raise InstallerError(
                "fixture_root_not_isolated",
                "fixture root must be disjoint from the project and workshop",
                exit_code=EXIT_INPUT,
                details={
                    "fixture_root": str(resolved),
                    "prohibited_root": str(root),
                },
            )
    return resolved


def _is_reparse_point(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _unsafe_directory_entry(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or _is_reparse_point(value)


def _assert_real_directory(path: Path) -> os.stat_result:
    try:
        value = os.lstat(path)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise InstallerError(
            "ownership_path_unsafe",
            "cannot inspect an uninstall path component without following it",
            exit_code=EXIT_VERIFY,
            details={"path": str(path), "exception": type(error).__name__},
        ) from error
    if not stat.S_ISDIR(value.st_mode) or _unsafe_directory_entry(value):
        raise InstallerError(
            "ownership_path_unsafe",
            "uninstall path contains a symlink, junction, or reparse point",
            exit_code=EXIT_VERIFY,
            details={"path": str(path)},
        )
    return value


def _assert_real_directory_chain(root: Path, parts: Sequence[str]) -> Path:
    _assert_real_directory(root)
    current = root
    for part in parts:
        current = current / part
        _assert_real_directory(current)
    return current


def _assert_real_regular_file(root: Path, relative: Path) -> Path:
    parent = _assert_real_directory_chain(root, relative.parts[:-1])
    target = parent / relative.parts[-1]
    try:
        value = os.lstat(target)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise InstallerError(
            "ownership_path_unsafe",
            "cannot inspect an uninstall control file without following it",
            exit_code=EXIT_VERIFY,
            details={"path": str(target), "exception": type(error).__name__},
        ) from error
    if (
        not stat.S_ISREG(value.st_mode)
        or stat.S_ISLNK(value.st_mode)
        or _is_reparse_point(value)
    ):
        raise InstallerError(
            "ownership_path_unsafe",
            "uninstall control file is not a regular non-link file",
            exit_code=EXIT_VERIFY,
            details={"path": str(target)},
        )
    return target


def _operation_lock_invalid(
    operation: str,
    lock_path: Path,
    reason: str,
    error: OSError | None = None,
) -> InstallerError:
    details = {
        "operation": operation,
        "lock": str(lock_path),
        "reason": reason,
    }
    if error is not None:
        details["exception"] = type(error).__name__
    return InstallerError(
        "operation_lock_invalid",
        "fixture operation lock is not a valid immutable lock directory",
        exit_code=EXIT_VERIFY,
        details=details,
    )


def _windows_file_identity(information: Any) -> tuple[int, int, int]:
    return (
        information.volume_serial_number,
        information.file_index_high,
        information.file_index_low,
    )


def _operation_lock_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _open_operation_lock_directory(
    lock_path: Path,
    operation: str,
    *,
    allow_create: bool = True,
) -> tuple[dict[str, Any], bool]:
    parent_path = lock_path.parent
    parent_handle: int | None = None
    directory_handle: int | None = None
    created = False
    try:
        if os.name == "nt":
            parent_handle = _windows_open_no_follow(
                parent_path,
                directory=True,
            )
            parent_information = _windows_handle_information(
                parent_handle,
                parent_path,
            )
            if (
                not parent_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or parent_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "fixture_root_not_directory",
                )
            if allow_create:
                _assert_operation_parent_directory_identity(
                    {
                        "parent_handle": parent_handle,
                        "parent_identity": _windows_file_identity(
                            parent_information
                        ),
                        "parent_path": parent_path,
                        "windows": True,
                    },
                    lock_path,
                    operation,
                )
                _operation_lock_mutation_test_hook(
                    "before-fixed-directory-mkdir",
                    lock_path,
                    None,
                )
                try:
                    directory_handle = _windows_open_relative_no_follow(
                        parent_handle,
                        lock_path.name,
                        lock_path,
                        directory=True,
                        create=True,
                        delete=False,
                        share_delete=False,
                    )
                    created = True
                except FileExistsError:
                    pass
                except OSError as error:
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "exclusive_directory_create_failed",
                        error,
                    ) from error
            if directory_handle is None:
                _operation_lock_mutation_test_hook(
                    "before-fixed-directory-open",
                    lock_path,
                    None,
                )
                directory_handle = _windows_open_relative_no_follow(
                    parent_handle,
                    lock_path.name,
                    lock_path,
                    directory=True,
                    create=False,
                    delete=False,
                    share_delete=False,
                )
                primary = True
            else:
                primary = True
            information = _windows_handle_information(
                directory_handle,
                lock_path,
            )
            if (
                not information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "fixed_path_not_directory",
                )
            return {
                "handle": directory_handle,
                "identity": _windows_file_identity(information),
                "parent_handle": parent_handle,
                "parent_identity": _windows_file_identity(parent_information),
                "parent_path": parent_path,
                "primary": primary,
                "windows": True,
            }, created

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        parent_handle = os.open(parent_path, flags)
        parent_value = os.fstat(parent_handle)
        parent_path_value = os.lstat(parent_path)
        if (
            not stat.S_ISDIR(parent_value.st_mode)
            or not stat.S_ISDIR(parent_path_value.st_mode)
            or _unsafe_directory_entry(parent_path_value)
            or not os.path.samestat(parent_value, parent_path_value)
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "fixture_root_not_directory",
            )
        parent_directory = {
            "parent_handle": parent_handle,
            "parent_identity": _operation_lock_identity(parent_value),
            "parent_path": parent_path,
            "windows": False,
        }
        if allow_create:
            _assert_operation_parent_directory_identity(
                parent_directory,
                lock_path,
                operation,
            )
            _operation_lock_mutation_test_hook(
                "before-fixed-directory-mkdir",
                lock_path,
                None,
            )
            try:
                os.mkdir(lock_path.name, 0o700, dir_fd=parent_handle)
                created = True
            except FileExistsError:
                pass
            except OSError as error:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "exclusive_directory_create_failed",
                    error,
                ) from error
        path_value = os.stat(
            lock_path.name,
            dir_fd=parent_handle,
            follow_symlinks=False,
        )
        _operation_lock_mutation_test_hook(
            "before-fixed-directory-open",
            lock_path,
            None,
        )
        directory_handle = os.open(
            lock_path.name,
            flags,
            dir_fd=parent_handle,
        )
        opened = os.fstat(directory_handle)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(path_value.st_mode)
            or _unsafe_directory_entry(path_value)
            or not os.path.samestat(opened, path_value)
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "fixed_path_not_directory",
            )
        return {
            "handle": directory_handle,
            "identity": _operation_lock_identity(opened),
            "parent_handle": parent_handle,
            "parent_identity": _operation_lock_identity(parent_value),
            "parent_path": parent_path,
            "primary": True,
            "windows": False,
        }, created
    except InstallerError:
        if directory_handle is not None:
            if os.name == "nt":
                _windows_kernel32().CloseHandle(directory_handle)
            else:
                os.close(directory_handle)
        if parent_handle is not None:
            if os.name == "nt":
                _windows_kernel32().CloseHandle(parent_handle)
            else:
                os.close(parent_handle)
        raise
    except OSError as error:
        if directory_handle is not None:
            if os.name == "nt":
                _windows_kernel32().CloseHandle(directory_handle)
            else:
                os.close(directory_handle)
        if parent_handle is not None:
            if os.name == "nt":
                _windows_kernel32().CloseHandle(parent_handle)
            else:
                os.close(parent_handle)
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "fixed_path_not_directory",
            error,
        ) from error


def _close_operation_lock_directory(directory: dict[str, Any]) -> None:
    for key in ("handle", "parent_handle"):
        handle = directory.get(key)
        if handle is None:
            continue
        if directory["windows"]:
            _windows_kernel32().CloseHandle(handle)
        else:
            os.close(handle)
        directory[key] = None


def _bounded_operation_lock_publication_retry(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    deadline: float | None,
    expected_identity: tuple[int, ...] | None,
) -> tuple[float, tuple[int, ...], float]:
    current_identity = tuple(directory["identity"])
    if expected_identity is not None and current_identity != expected_identity:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "directory_identity_changed_during_publication",
        )
    now = time.monotonic()
    if deadline is None:
        deadline = now + _OPERATION_LOCK_PUBLICATION_TIMEOUT_SECONDS
        expected_identity = current_identity
    if now >= deadline:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "publication_incomplete",
        )
    assert expected_identity is not None
    return (
        deadline,
        expected_identity,
        min(_OPERATION_LOCK_PUBLICATION_POLL_SECONDS, deadline - now),
    )


def _operation_lock_pending_kernel_identity(
    directory: dict[str, Any],
    kernel_path: Path,
    operation: str,
    expected_identity: tuple[int, int] | None,
) -> tuple[int, int]:
    try:
        if directory["windows"]:
            handle = _windows_open_relative_no_follow(
                directory["handle"],
                "kernel",
                kernel_path,
                directory=False,
                create=False,
                delete=False,
                share_delete=True,
            )
            try:
                information = _windows_handle_information(handle, kernel_path)
                value = os.stat(kernel_path, follow_symlinks=False)
                current_identity = _windows_file_identity(information)
                invalid = (
                    information.file_attributes
                    & (
                        _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                        | _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                    )
                    or information.file_size_high != 0
                    or information.file_size_low != 0
                    or information.number_of_links != 1
                    or value.st_size != 0
                )
            finally:
                _windows_kernel32().CloseHandle(handle)
        else:
            value = os.stat(
                "kernel",
                dir_fd=directory["handle"],
                follow_symlinks=False,
            )
            current_identity = _operation_lock_identity(value)
            invalid = (
                not stat.S_ISREG(value.st_mode)
                or _unsafe_directory_entry(value)
                or value.st_size != 0
                or value.st_nlink != 1
            )
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            kernel_path.parent,
            "kernel_identity_unavailable",
            error,
        ) from error
    if invalid:
        raise _operation_lock_invalid(
            operation,
            kernel_path.parent,
            "kernel_invalid_during_publication",
        )
    if (
        expected_identity is not None
        and current_identity != expected_identity
    ):
        raise _operation_lock_invalid(
            operation,
            kernel_path.parent,
            "kernel_identity_changed_during_publication",
        )
    return current_identity


def _operation_lock_pending_owner_identity(
    entries: dict[str, Any],
    lock_path: Path,
    operation: str,
    expected_identity: tuple[str, tuple[int, ...]] | None,
) -> tuple[str, tuple[int, ...]] | None:
    if entries["owner_name"] is None:
        if expected_identity is not None:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "owner_disappeared_during_publication",
            )
        return None
    current_identity = (
        str(entries["owner_name"]),
        tuple(entries["owner_identity"]),
    )
    if (
        expected_identity is not None
        and current_identity != expected_identity
    ):
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "owner_identity_changed_during_publication",
        )
    return current_identity


def _assert_operation_parent_directory_identity(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
) -> None:
    parent_path = directory["parent_path"]
    try:
        if directory["windows"]:
            retained = _windows_handle_information(
                directory["parent_handle"],
                parent_path,
            )
            path_handle = _windows_open_no_follow(
                parent_path,
                directory=True,
                share_delete=False,
            )
            try:
                current = _windows_handle_information(path_handle, parent_path)
            finally:
                _windows_kernel32().CloseHandle(path_handle)
            if (
                retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                or current.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                or not retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or not current.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or _windows_file_identity(retained)
                != directory["parent_identity"]
                or _windows_file_identity(current)
                != directory["parent_identity"]
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "fixture_root_identity_mismatch",
                )
            return
        retained = os.fstat(directory["parent_handle"])
        current = os.lstat(parent_path)
        if (
            not stat.S_ISDIR(retained.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or _unsafe_directory_entry(current)
            or _operation_lock_identity(retained)
            != directory["parent_identity"]
            or not os.path.samestat(retained, current)
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "fixture_root_identity_mismatch",
            )
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "fixture_root_identity_unavailable",
            error,
        ) from error


def _assert_operation_lock_directory_identity(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
) -> None:
    try:
        _assert_operation_parent_directory_identity(
            directory,
            lock_path,
            operation,
        )
        if directory["windows"]:
            retained = _windows_handle_information(
                directory["handle"],
                lock_path,
            )
            path_handle = _windows_open_relative_no_follow(
                directory["parent_handle"],
                lock_path.name,
                lock_path,
                directory=True,
                create=False,
                delete=False,
                share_delete=True,
            )
            try:
                current = _windows_handle_information(path_handle, lock_path)
            finally:
                _windows_kernel32().CloseHandle(path_handle)
            if (
                retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                or current.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                or not retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or not current.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or _windows_file_identity(retained) != directory["identity"]
                or _windows_file_identity(current) != directory["identity"]
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "directory_identity_mismatch",
                )
            return

        opened = os.fstat(directory["handle"])
        path_value = os.stat(
            lock_path.name,
            dir_fd=directory["parent_handle"],
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(path_value.st_mode)
            or _unsafe_directory_entry(path_value)
            or _operation_lock_identity(opened) != directory["identity"]
            or not os.path.samestat(opened, path_value)
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "directory_identity_mismatch",
            )
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "directory_identity_unavailable",
            error,
        ) from error


def _assert_operation_kernel_identity(
    directory: dict[str, Any],
    stream: Any,
    kernel_path: Path,
    operation: str,
    *,
    require_single_link: bool,
) -> None:
    try:
        opened = os.fstat(stream.fileno())
        if os.name == "nt":
            import msvcrt

            opened_handle = int(msvcrt.get_osfhandle(stream.fileno()))
            opened_information = _windows_handle_information(
                opened_handle,
                kernel_path,
            )
            path_handle = _windows_open_relative_no_follow(
                directory["handle"],
                "kernel",
                kernel_path,
                directory=False,
                create=False,
                share_delete=True,
            )
            try:
                path_information = _windows_handle_information(
                    path_handle,
                    kernel_path,
                )
            finally:
                _windows_kernel32().CloseHandle(path_handle)
            if (
                opened_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                or path_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise _operation_lock_invalid(
                    operation,
                    kernel_path.parent,
                    "kernel_reparse_point",
                )
            if (
                opened_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or path_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or not stat.S_ISREG(opened.st_mode)
            ):
                raise _operation_lock_invalid(
                    operation,
                    kernel_path.parent,
                    "kernel_not_regular",
                )
            if opened.st_size != 0:
                raise _operation_lock_invalid(
                    operation,
                    kernel_path.parent,
                    "kernel_not_empty",
                )
            if require_single_link and (
                opened_information.number_of_links != 1
                or path_information.number_of_links != 1
                or opened.st_nlink != 1
            ):
                raise _operation_lock_invalid(
                    operation,
                    kernel_path.parent,
                    "multiple_links",
                )
            if _windows_file_identity(
                opened_information
            ) != _windows_file_identity(path_information):
                raise _operation_lock_invalid(
                    operation,
                    kernel_path.parent,
                    "kernel_identity_mismatch",
                )
            return

        path_value = os.stat(
            "kernel",
            dir_fd=directory["handle"],
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(path_value.st_mode)
        ):
            raise _operation_lock_invalid(
                operation,
                kernel_path.parent,
                "kernel_not_regular",
            )
        if (
            _unsafe_directory_entry(opened)
            or _unsafe_directory_entry(path_value)
        ):
            raise _operation_lock_invalid(
                operation,
                kernel_path.parent,
                "kernel_link_or_reparse_point",
            )
        if opened.st_size != 0 or path_value.st_size != 0:
            raise _operation_lock_invalid(
                operation,
                kernel_path.parent,
                "kernel_not_empty",
            )
        if require_single_link and (
            opened.st_nlink != 1 or path_value.st_nlink != 1
        ):
            raise _operation_lock_invalid(
                operation,
                kernel_path.parent,
                "multiple_links",
            )
        if not os.path.samestat(opened, path_value):
            raise _operation_lock_invalid(
                operation,
                kernel_path.parent,
                "kernel_identity_mismatch",
            )
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            kernel_path.parent,
            "kernel_identity_unavailable",
            error,
        ) from error


def _open_existing_operation_lock_descriptor(
    directory: dict[str, Any],
    kernel_path: Path,
) -> tuple[int, bool]:
    if os.name == "nt":
        import msvcrt

        handle = _windows_open_relative_no_follow(
            directory["handle"],
            "kernel",
            kernel_path,
            directory=False,
            create=False,
            delete=False,
            write=True,
            share_delete=False,
        )
        primary = True
        try:
            return (
                msvcrt.open_osfhandle(
                    handle,
                    os.O_RDWR
                    | getattr(os, "O_BINARY", 0)
                    | getattr(os, "O_NOINHERIT", 0),
                ),
                primary,
            )
        except Exception:
            _windows_kernel32().CloseHandle(handle)
            raise
    flags = os.O_RDWR | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open("kernel", flags, dir_fd=directory["handle"]), True


def _open_operation_kernel_stream(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    *,
    create: bool = True,
) -> tuple[Any, bool, bool]:
    kernel_path = lock_path / "kernel"
    create_flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOINHERIT", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    created = False
    if create:
        try:
            _assert_operation_lock_directory_identity(
                directory,
                lock_path,
                operation,
            )
            _operation_lock_mutation_test_hook(
                "before-kernel-open",
                lock_path,
                None,
            )
            if os.name == "nt":
                import msvcrt

                handle = _windows_open_relative_no_follow(
                    directory["handle"],
                    "kernel",
                    kernel_path,
                    directory=False,
                    create=True,
                    delete=False,
                    write=True,
                    share_delete=False,
                )
                descriptor = msvcrt.open_osfhandle(
                    handle,
                    os.O_RDWR
                    | getattr(os, "O_BINARY", 0)
                    | getattr(os, "O_NOINHERIT", 0),
                )
                primary = True
            else:
                descriptor = os.open(
                    "kernel",
                    create_flags,
                    0o600,
                    dir_fd=directory["handle"],
                )
                primary = True
            created = True
            os.fsync(descriptor)
        except FileExistsError:
            try:
                descriptor, primary = (
                    _open_existing_operation_lock_descriptor(
                        directory,
                        kernel_path,
                    )
                )
            except FileNotFoundError:
                return _open_operation_kernel_stream(
                    directory,
                    lock_path,
                    operation,
                    create=create,
                )
            except OSError as error:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "kernel_open_failed",
                    error,
                ) from error
        except OSError as error:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "kernel_create_failed",
                error,
            ) from error
    else:
        try:
            _operation_lock_mutation_test_hook(
                "before-kernel-open",
                lock_path,
                None,
            )
            descriptor, primary = _open_existing_operation_lock_descriptor(
                directory,
                kernel_path,
            )
        except OSError as error:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "kernel_open_failed",
                error,
            ) from error
    try:
        stream = os.fdopen(descriptor, "r+b", buffering=0)
    except Exception:
        os.close(descriptor)
        raise
    try:
        _assert_operation_kernel_identity(
            directory,
            stream,
            kernel_path,
            operation,
            require_single_link=False,
        )
    except Exception:
        stream.close()
        raise
    return stream, created, primary


def _operation_owner_name(record: dict[str, Any]) -> str:
    wire_record = {
        "v": record.get("fixture_schema_version"),
        "s": "h" if record.get("state") == "held" else record.get("state"),
        "p": record.get("pid"),
        "i": record.get("process_instance_token"),
        "t": record.get("token"),
        "o": record.get("operation"),
        "r": record.get("reclaimed_token"),
    }
    encoded = base64.urlsafe_b64encode(
        _canonical_json(wire_record)
    ).decode("ascii")
    name = "owner-" + encoded.rstrip("=")
    if len(os.fsencode(name)) > 240:
        raise InstallerError(
            "operation_lock_invalid",
            "fixture operation lock owner identity is too long",
            exit_code=EXIT_VERIFY,
            details={"reason": "owner_identity_too_long"},
        )
    return name


def _operation_owner_record(name: str) -> dict[str, Any]:
    if not name.startswith("owner-"):
        raise ValueError("not an operation owner name")
    encoded = name.removeprefix("owner-")
    padding = "=" * (-len(encoded) % 4)
    data = base64.b64decode(
        encoded + padding,
        altchars=b"-_",
        validate=True,
    )
    wire_record = json.loads(data.decode("utf-8"))
    if not isinstance(wire_record, dict) or set(wire_record) != {
        "v",
        "s",
        "p",
        "i",
        "t",
        "o",
        "r",
    }:
        raise ValueError("invalid operation owner wire identity")
    value = {
        "fixture_schema_version": wire_record.get("v"),
        "state": "held" if wire_record.get("s") == "h" else wire_record.get("s"),
        "pid": wire_record.get("p"),
        "process_instance_token": wire_record.get("i"),
        "token": wire_record.get("t"),
        "operation": wire_record.get("o"),
        "reclaimed_token": wire_record.get("r"),
    }
    if (
        not isinstance(value, dict)
        or set(value) != {
            "fixture_schema_version",
            "state",
            "pid",
            "process_instance_token",
            "token",
            "operation",
            "reclaimed_token",
        }
        or value.get("fixture_schema_version") != FIXTURE_SCHEMA_VERSION
        or value.get("state") != "held"
        or not isinstance(value.get("pid"), int)
        or value["pid"] <= 0
        or not isinstance(value.get("operation"), str)
        or not value["operation"]
        or not isinstance(value.get("process_instance_token"), str)
        or not re.fullmatch(
            r"[0-9a-f]{32}",
            value["process_instance_token"],
        )
        or not isinstance(value.get("token"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", value["token"])
        or (
            value.get("reclaimed_token") is not None
            and (
                not isinstance(value["reclaimed_token"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", value["reclaimed_token"])
            )
        )
        or _operation_owner_name(value) != name
    ):
        raise ValueError("invalid operation owner identity")
    return value


def _operation_lock_entries(
    lock_path: Path,
    operation: str,
    *,
    require_published: bool,
    require_single_links: bool,
    _directory: dict[str, Any] | None = None,
    _retain_handles: bool = False,
) -> dict[str, Any]:
    directory = _directory
    close_directory = directory is None
    owner_handle: int | None = None
    marker_handle: int | None = None
    try:
        if directory is None:
            directory, _ = _open_operation_lock_directory(
                lock_path,
                operation,
                allow_create=False,
            )
        if directory["windows"]:
            with os.scandir(lock_path) as iterator:
                names = {entry.name for entry in iterator}
        else:
            names = set(os.listdir(directory["handle"]))
        owner_names = sorted(
            name for name in names if name.startswith("owner-")
        )
        if (
            "kernel" not in names
            or len(owner_names) > 1
            or names - {"kernel", *owner_names}
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "unexpected_directory_entries",
            )
        if not owner_names:
            if require_published:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "owner_missing",
                )
            return {
                "record": None,
                "owner_name": None,
                "owner_identity": None,
                "marker_identity": None,
                "published": False,
            }

        owner_name = owner_names[0]
        owner_path = lock_path / owner_name
        if directory["windows"]:
            owner_handle = _windows_open_relative_no_follow(
                directory["handle"],
                owner_name,
                owner_path,
                directory=True,
                create=False,
                delete=False,
                share_delete=not _retain_handles,
            )
            owner_information = _windows_handle_information(
                owner_handle,
                owner_path,
            )
            if (
                not owner_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or owner_information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "owner_not_directory",
                )
            owner_identity: tuple[int, ...] = _windows_file_identity(
                owner_information
            )
        else:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            owner_value = os.stat(
                owner_name,
                dir_fd=directory["handle"],
                follow_symlinks=False,
            )
            owner_handle = os.open(
                owner_name,
                flags,
                dir_fd=directory["handle"],
            )
            owner_opened = os.fstat(owner_handle)
            if (
                not stat.S_ISDIR(owner_value.st_mode)
                or not stat.S_ISDIR(owner_opened.st_mode)
                or _unsafe_directory_entry(owner_value)
                or not os.path.samestat(owner_value, owner_opened)
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "owner_not_directory",
                )
            owner_identity = _operation_lock_identity(owner_opened)
        try:
            record = _operation_owner_record(owner_name)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "owner_identity_invalid",
            ) from error

        if directory["windows"]:
            with os.scandir(owner_path) as iterator:
                owner_entry_names = {entry.name for entry in iterator}
        else:
            owner_entry_names = set(os.listdir(owner_handle))
        if owner_entry_names - {"published"}:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "unexpected_owner_entries",
            )
        marker_identity: tuple[int, int] | None = None
        published = "published" in owner_entry_names
        if published:
            marker_path = owner_path / "published"
            if directory["windows"]:
                marker_handle = _windows_open_relative_no_follow(
                    owner_handle,
                    "published",
                    marker_path,
                    directory=False,
                    create=False,
                    delete=False,
                    share_delete=not _retain_handles,
                )
                marker_information = _windows_handle_information(
                    marker_handle,
                    marker_path,
                )
                if (
                    marker_information.file_attributes
                    & (
                        _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                        | _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                    )
                    or marker_information.file_size_high != 0
                    or marker_information.file_size_low != 0
                ):
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "owner_marker_invalid",
                    )
                if (
                    require_single_links
                    and marker_information.number_of_links != 1
                ):
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "multiple_links",
                    )
                marker_identity = _windows_file_identity(marker_information)
            else:
                flags = os.O_RDONLY | getattr(os, "O_NOINHERIT", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                marker_value = os.stat(
                    "published",
                    dir_fd=owner_handle,
                    follow_symlinks=False,
                )
                marker_handle = os.open(
                    "published",
                    flags,
                    dir_fd=owner_handle,
                )
                marker_opened = os.fstat(marker_handle)
                if (
                    not stat.S_ISREG(marker_value.st_mode)
                    or not stat.S_ISREG(marker_opened.st_mode)
                    or _unsafe_directory_entry(marker_value)
                    or marker_value.st_size != 0
                    or marker_opened.st_size != 0
                    or not os.path.samestat(marker_value, marker_opened)
                ):
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "owner_marker_invalid",
                    )
                if require_single_links and (
                    marker_value.st_nlink != 1
                    or marker_opened.st_nlink != 1
                ):
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "multiple_links",
                    )
                marker_identity = _operation_lock_identity(marker_opened)
        elif require_published:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "owner_unpublished",
            )
        result = {
            "record": record,
            "owner_name": owner_name,
            "owner_identity": owner_identity,
            "marker_identity": marker_identity,
            "published": published,
        }
        if _retain_handles:
            result["_owner_handle"] = owner_handle
            result["_marker_handle"] = marker_handle
            result["_windows"] = directory["windows"]
            owner_handle = None
            marker_handle = None
        return result
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "directory_inspection_failed",
            error,
        ) from error
    finally:
        if marker_handle is not None:
            if directory is not None and directory["windows"]:
                _windows_kernel32().CloseHandle(marker_handle)
            else:
                os.close(marker_handle)
        if owner_handle is not None:
            if directory is not None and directory["windows"]:
                _windows_kernel32().CloseHandle(owner_handle)
            else:
                os.close(owner_handle)
        if close_directory and directory is not None:
            _close_operation_lock_directory(directory)


def _close_operation_owner_handles(owner: dict[str, Any] | None) -> None:
    if owner is None:
        return
    windows = bool(owner.get("_windows"))
    for key in ("_marker_handle", "_owner_handle"):
        handle = owner.get(key)
        if handle is None:
            continue
        if windows:
            _windows_kernel32().CloseHandle(handle)
        else:
            os.close(handle)
        owner[key] = None


def _fsync_operation_handle(handle: int, *, windows: bool) -> None:
    if windows:
        return
    os.fsync(handle)


def _publish_operation_owner(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    owner_name = _operation_owner_name(record)
    owner_path = lock_path / owner_name
    marker_path = owner_path / "published"
    owner_handle: int | None = None
    marker_handle: int | None = None
    try:
        if directory["windows"] and not directory["primary"]:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "mutation_handle_unavailable",
            )
        _assert_operation_lock_directory_identity(
            directory,
            lock_path,
            operation,
        )
        _operation_lock_mutation_test_hook(
            "before-owner-directory-mkdir",
            lock_path,
            owner_name,
        )
        if directory["windows"]:
            owner_handle = _windows_open_relative_no_follow(
                directory["handle"],
                owner_name,
                owner_path,
                directory=True,
                create=True,
                delete=False,
                share_delete=False,
            )
            _operation_lock_mutation_test_hook(
                "before-owner-directory-open",
                lock_path,
                owner_name,
            )
            owner_information = _windows_handle_information(
                owner_handle,
                owner_path,
            )
            owner_identity: tuple[int, ...] = _windows_file_identity(
                owner_information
            )
        else:
            os.mkdir(owner_name, 0o700, dir_fd=directory["handle"])
            owner_value = os.stat(
                owner_name,
                dir_fd=directory["handle"],
                follow_symlinks=False,
            )
            _operation_lock_mutation_test_hook(
                "before-owner-directory-open",
                lock_path,
                owner_name,
            )
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            owner_handle = os.open(
                owner_name,
                flags,
                dir_fd=directory["handle"],
            )
            owner_opened = os.fstat(owner_handle)
            if (
                not stat.S_ISDIR(owner_value.st_mode)
                or not stat.S_ISDIR(owner_opened.st_mode)
                or _unsafe_directory_entry(owner_value)
                or not os.path.samestat(owner_value, owner_opened)
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "owner_not_directory",
                )
            owner_identity = _operation_lock_identity(owner_opened)
        _operation_lock_mutation_test_hook(
            "before-published-open",
            lock_path,
            owner_name,
        )
        if directory["windows"]:
            marker_handle = _windows_open_relative_no_follow(
                owner_handle,
                "published",
                marker_path,
                directory=False,
                create=True,
                delete=False,
                write=True,
                share_delete=False,
            )
            _windows_flush_handle(marker_handle, marker_path)
            marker_information = _windows_handle_information(
                marker_handle,
                marker_path,
            )
            marker_identity: tuple[int, ...] = _windows_file_identity(
                marker_information
            )
        else:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOINHERIT", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            marker_handle = os.open(
                "published",
                flags,
                0o600,
                dir_fd=owner_handle,
            )
            os.fsync(marker_handle)
            marker_opened = os.fstat(marker_handle)
            marker_identity = _operation_lock_identity(marker_opened)
        _fsync_operation_handle(
            owner_handle,
            windows=directory["windows"],
        )
        _fsync_operation_handle(
            directory["handle"],
            windows=directory["windows"],
        )
    except OSError as error:
        if marker_handle is not None:
            if directory["windows"]:
                _windows_kernel32().CloseHandle(marker_handle)
            else:
                os.close(marker_handle)
            marker_handle = None
        if owner_handle is not None:
            if directory["windows"]:
                _windows_kernel32().CloseHandle(owner_handle)
            else:
                os.close(owner_handle)
            owner_handle = None
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "owner_publication_failed",
            error,
        ) from error
    except Exception:
        if marker_handle is not None:
            if directory["windows"]:
                _windows_kernel32().CloseHandle(marker_handle)
            else:
                os.close(marker_handle)
        if owner_handle is not None:
            if directory["windows"]:
                _windows_kernel32().CloseHandle(owner_handle)
            else:
                os.close(owner_handle)
        raise
    owner = {
        "record": record,
        "owner_name": owner_name,
        "owner_identity": owner_identity,
        "marker_identity": marker_identity,
        "published": True,
        "_owner_handle": owner_handle,
        "_marker_handle": marker_handle,
        "_windows": directory["windows"],
    }
    try:
        _assert_operation_owner_unchanged(
            directory,
            lock_path,
            operation,
            owner,
            require_single_links=True,
        )
    except Exception:
        _close_operation_owner_handles(owner)
        raise
    return owner


def _operation_lock_test_hook(
    boundary: str,
    kernel_path: Path,
    owner_marker_path: Path,
) -> None:
    del boundary, kernel_path, owner_marker_path


def _operation_lock_mutation_test_hook(
    boundary: str,
    lock_path: Path,
    owner_name: str | None,
) -> None:
    del boundary, lock_path, owner_name


_OPERATION_LOCK_FORMER_WRITE_BOUNDARIES = (
    "before-held-record-write",
    "before-released-record-write",
)


def _assert_operation_owner_unchanged(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    expected: dict[str, Any],
    *,
    require_single_links: bool,
) -> dict[str, Any]:
    current = _operation_lock_entries(
        lock_path,
        operation,
        require_published=True,
        require_single_links=require_single_links,
        _directory=directory,
    )
    if (
        current["owner_name"] != expected["owner_name"]
        or current["owner_identity"] != expected["owner_identity"]
        or current["marker_identity"] != expected["marker_identity"]
        or current["record"] != expected["record"]
    ):
        raise InstallerError(
            "operation_lock_changed",
            "fixture operation lock ownership changed before release",
            exit_code=EXIT_VERIFY,
            details={"operation": operation, "lock": str(lock_path)},
        )
    return expected


def _assert_operation_owner_directory_empty(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    owner: dict[str, Any],
) -> None:
    owner_handle = owner.get("_owner_handle")
    if owner_handle is None:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "owner_handle_missing",
        )
    owner_name = str(owner["owner_name"])
    owner_path = lock_path / owner_name
    try:
        if directory["windows"]:
            retained = _windows_handle_information(owner_handle, owner_path)
            current_handle = _windows_open_relative_no_follow(
                directory["handle"],
                owner_name,
                owner_path,
                directory=True,
                create=False,
                delete=False,
                share_delete=True,
            )
            try:
                current = _windows_handle_information(
                    current_handle,
                    owner_path,
                )
            finally:
                _windows_kernel32().CloseHandle(current_handle)
            names = {entry.name for entry in os.scandir(owner_path)}
            valid = (
                retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                and not retained.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
                and _windows_file_identity(retained)
                == tuple(owner["owner_identity"])
                and _windows_file_identity(current)
                == tuple(owner["owner_identity"])
                and not names
            )
        else:
            retained = os.fstat(owner_handle)
            current = os.stat(
                owner_name,
                dir_fd=directory["handle"],
                follow_symlinks=False,
            )
            valid = (
                stat.S_ISDIR(retained.st_mode)
                and stat.S_ISDIR(current.st_mode)
                and not _unsafe_directory_entry(current)
                and _operation_lock_identity(retained)
                == tuple(owner["owner_identity"])
                and os.path.samestat(retained, current)
                and not os.listdir(owner_handle)
            )
        if not valid:
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "owner_identity_mismatch",
            )
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "owner_identity_unavailable",
            error,
        ) from error


def _remove_operation_lock_entries(
    directory: dict[str, Any],
    lock_path: Path,
    operation: str,
    stream: Any,
    owner: dict[str, Any] | None,
) -> None:
    kernel_path = lock_path / "kernel"
    try:
        _assert_operation_lock_directory_identity(
            directory,
            lock_path,
            operation,
        )
        current = _operation_lock_entries(
            lock_path,
            operation,
            require_published=bool(owner and owner["published"]),
            require_single_links=False,
            _directory=directory,
        )
        if owner is None:
            if current["owner_name"] is not None:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "owner_appeared_during_reclaim",
                )
        elif (
            current["owner_name"] != owner["owner_name"]
            or current["owner_identity"] != owner["owner_identity"]
            or current["marker_identity"] != owner["marker_identity"]
            or current["record"] != owner["record"]
            or current["published"] != owner["published"]
        ):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "owner_identity_mismatch",
            )
        if owner is not None:
            owner_name = str(owner["owner_name"])
            if current["published"]:
                marker_handle = owner.get("_marker_handle")
                if marker_handle is None:
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "owner_marker_handle_missing",
                    )
                _operation_lock_mutation_test_hook(
                    "before-published-unlink",
                    lock_path,
                    owner_name,
                )
                if directory["windows"]:
                    _windows_kernel32().CloseHandle(marker_handle)
                    owner["_marker_handle"] = None
                    _windows_delete_relative_exact(
                        owner["_owner_handle"],
                        "published",
                        lock_path / owner_name / "published",
                        expected_identity=tuple(owner["marker_identity"]),
                        directory=False,
                    )
                else:
                    os.unlink("published", dir_fd=owner["_owner_handle"])
                    os.close(marker_handle)
                owner["_marker_handle"] = None
            _assert_operation_owner_directory_empty(
                directory,
                lock_path,
                operation,
                owner,
            )
            _operation_lock_mutation_test_hook(
                "before-owner-directory-rmdir",
                lock_path,
                owner_name,
            )
            if directory["windows"]:
                _windows_kernel32().CloseHandle(owner["_owner_handle"])
                owner["_owner_handle"] = None
                _windows_delete_relative_exact(
                    directory["handle"],
                    owner_name,
                    lock_path / owner_name,
                    expected_identity=tuple(owner["owner_identity"]),
                    directory=True,
                )
            else:
                os.rmdir(owner_name, dir_fd=directory["handle"])
                os.close(owner["_owner_handle"])
            owner["_owner_handle"] = None
        _assert_operation_kernel_identity(
            directory,
            stream,
            kernel_path,
            operation,
            require_single_link=False,
        )
        _operation_lock_mutation_test_hook(
            "before-kernel-unlink",
            lock_path,
            None,
        )
        if directory["windows"]:
            import msvcrt

            directory["_kernel_delete_identity"] = _windows_file_identity(
                _windows_handle_information(
                    int(msvcrt.get_osfhandle(stream.fileno())),
                    kernel_path,
                )
            )
        else:
            os.unlink("kernel", dir_fd=directory["handle"])
        _fsync_operation_handle(
            directory["handle"],
            windows=directory["windows"],
        )
    except InstallerError:
        raise
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "entry_remove_failed",
            error,
        ) from error
    finally:
        _close_operation_owner_handles(owner)


def _finish_operation_lock_removal(
    lock_path: Path,
    operation: str,
    directory: dict[str, Any],
    stream: Any,
    *,
    acquired: bool,
) -> None:
    if acquired:
        _release_file_lock(stream)
    stream.close()
    try:
        if directory["windows"]:
            kernel_identity = directory.pop(
                "_kernel_delete_identity",
                None,
            )
            if kernel_identity is None:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "kernel_delete_identity_missing",
                )
            _windows_delete_relative_exact(
                directory["handle"],
                "kernel",
                lock_path / "kernel",
                expected_identity=tuple(kernel_identity),
                directory=False,
            )
        _assert_operation_lock_directory_identity(
            directory,
            lock_path,
            operation,
        )
        if directory["windows"]:
            if {entry.name for entry in os.scandir(lock_path)}:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "directory_not_empty",
                )
        elif os.listdir(directory["handle"]):
            raise _operation_lock_invalid(
                operation,
                lock_path,
                "directory_not_empty",
            )
        _operation_lock_mutation_test_hook(
            "before-fixed-directory-rmdir",
            lock_path,
            None,
        )
        if directory["windows"]:
            if not directory["primary"]:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "mutation_handle_unavailable",
                )
            identity = tuple(directory["identity"])
            _windows_kernel32().CloseHandle(directory["handle"])
            directory["handle"] = None
            _windows_delete_relative_exact(
                directory["parent_handle"],
                lock_path.name,
                lock_path,
                expected_identity=identity,
                directory=True,
            )
        else:
            os.rmdir(
                lock_path.name,
                dir_fd=directory["parent_handle"],
            )
    except OSError as error:
        raise _operation_lock_invalid(
            operation,
            lock_path,
            "directory_remove_failed",
            error,
        ) from error
    finally:
        _close_operation_lock_directory(directory)


def _acquire_file_lock(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(_WINDOWS_LOCK_BYTE_OFFSET)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(_WINDOWS_LOCK_BYTE_OFFSET)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _fixture_operation_lock(
    fixture_root: Path,
    operation: str,
) -> Iterable[dict[str, Any]]:
    lock_path = fixture_root / ".xc-package-operation.lock"
    reclaimed_token: str | None = None
    publication_deadline: float | None = None
    publication_identity: tuple[int, ...] | None = None
    publication_kernel_identity: tuple[int, ...] | None = None
    publication_owner_identity: tuple[str, tuple[int, ...]] | None = None
    while True:
        directory: dict[str, Any] | None = None
        stream: Any = None
        acquired = False
        kernel_primary = False
        entries: dict[str, Any] | None = None
        retained_owner: dict[str, Any] | None = None
        removed = False
        try:
            directory, created_directory = _open_operation_lock_directory(
                lock_path,
                operation,
            )
            _assert_operation_lock_directory_identity(
                directory,
                lock_path,
                operation,
            )
            if (
                publication_identity is not None
                and tuple(directory["identity"]) != publication_identity
            ):
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "directory_identity_changed_during_publication",
                )
            try:
                if directory["windows"]:
                    initial_names = {
                        entry.name for entry in os.scandir(lock_path)
                    }
                else:
                    initial_names = set(os.listdir(directory["handle"]))
            except OSError as error:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "directory_inspection_failed",
                    error,
                ) from error
            if "kernel" not in initial_names and initial_names:
                raise _operation_lock_invalid(
                    operation,
                    lock_path,
                    "kernel_missing_with_other_entries",
                )
            if not created_directory and "kernel" not in initial_names:
                if (
                    publication_kernel_identity is not None
                    or publication_owner_identity is not None
                ):
                    raise _operation_lock_invalid(
                        operation,
                        lock_path,
                        "publication_entries_disappeared",
                    )
                (
                    publication_deadline,
                    publication_identity,
                    retry_delay,
                ) = _bounded_operation_lock_publication_retry(
                    directory,
                    lock_path,
                    operation,
                    publication_deadline,
                    publication_identity,
                )
                _close_operation_lock_directory(directory)
                directory = None
                time.sleep(retry_delay)
                continue
            try:
                stream, created_kernel, kernel_primary = (
                    _open_operation_kernel_stream(
                        directory,
                        lock_path,
                        operation,
                        create=created_directory,
                    )
                )
            except InstallerError as error:
                if (
                    created_directory
                    or error.details.get("reason") != "kernel_open_failed"
                ):
                    raise
                publication_kernel_identity = (
                    _operation_lock_pending_kernel_identity(
                        directory,
                        lock_path / "kernel",
                        operation,
                        publication_kernel_identity,
                    )
                )
                entries = _operation_lock_entries(
                    lock_path,
                    operation,
                    require_published=False,
                    require_single_links=True,
                    _directory=directory,
                )
                publication_owner_identity = (
                    _operation_lock_pending_owner_identity(
                        entries,
                        lock_path,
                        operation,
                        publication_owner_identity,
                    )
                )
                (
                    publication_deadline,
                    publication_identity,
                    retry_delay,
                ) = _bounded_operation_lock_publication_retry(
                    directory,
                    lock_path,
                    operation,
                    publication_deadline,
                    publication_identity,
                )
                _close_operation_lock_directory(directory)
                directory = None
                time.sleep(retry_delay)
                continue
            entries = _operation_lock_entries(
                lock_path,
                operation,
                require_published=False,
                require_single_links=not created_directory,
                _directory=directory,
            )
            if not created_directory:
                publication_kernel_identity = (
                    _operation_lock_pending_kernel_identity(
                        directory,
                        lock_path / "kernel",
                        operation,
                        publication_kernel_identity,
                    )
                )
                publication_owner_identity = (
                    _operation_lock_pending_owner_identity(
                        entries,
                        lock_path,
                        operation,
                        publication_owner_identity,
                    )
                )
            if (
                not created_directory
                and (
                    entries["owner_name"] is None
                    or not entries["published"]
                )
            ):
                _assert_operation_kernel_identity(
                    directory,
                    stream,
                    lock_path / "kernel",
                    operation,
                    require_single_link=True,
                )
                (
                    publication_deadline,
                    publication_identity,
                    retry_delay,
                ) = _bounded_operation_lock_publication_retry(
                    directory,
                    lock_path,
                    operation,
                    publication_deadline,
                    publication_identity,
                )
                stream.close()
                stream = None
                _close_operation_lock_directory(directory)
                directory = None
                time.sleep(retry_delay)
                continue
            _acquire_file_lock(stream)
            acquired = True
            if os.name == "nt" and (
                not directory["primary"] or not kernel_primary
            ):
                (
                    publication_deadline,
                    publication_identity,
                    retry_delay,
                ) = _bounded_operation_lock_publication_retry(
                    directory,
                    lock_path,
                    operation,
                    publication_deadline,
                    publication_identity,
                )
                _release_file_lock(stream)
                acquired = False
                stream.close()
                stream = None
                _close_operation_lock_directory(directory)
                directory = None
                time.sleep(retry_delay)
                continue
        except InstallerError:
            if stream is not None:
                stream.close()
                stream = None
            if directory is not None:
                _close_operation_lock_directory(directory)
                directory = None
            raise
        except OSError as error:
            owner = (
                entries["record"]
                if entries is not None and entries["published"]
                else None
            )
            if stream is not None:
                stream.close()
                stream = None
            if directory is not None:
                _close_operation_lock_directory(directory)
                directory = None
            raise InstallerError(
                "operation_in_progress",
                "another fixture install or uninstall operation is in progress",
                exit_code=EXIT_ENVIRONMENT,
                details={
                    "operation": operation,
                    "lock": str(lock_path),
                    "owner": owner,
                },
            ) from error
        try:
            assert directory is not None
            assert stream is not None
            assert entries is not None
            _assert_operation_lock_directory_identity(
                directory,
                lock_path,
                operation,
            )
            _assert_operation_kernel_identity(
                directory,
                stream,
                lock_path / "kernel",
                operation,
                require_single_link=False,
            )
            entries = _operation_lock_entries(
                lock_path,
                operation,
                require_published=False,
                require_single_links=False,
                _directory=directory,
            )
            fresh = (
                created_directory
                and created_kernel
                and entries["owner_name"] is None
            )
            if not fresh:
                retained_owner = (
                    _operation_lock_entries(
                        lock_path,
                        operation,
                        require_published=bool(entries["published"]),
                        require_single_links=False,
                        _directory=directory,
                        _retain_handles=True,
                    )
                    if entries["owner_name"] is not None
                    else None
                )
                previous = (
                    retained_owner["record"]
                    if retained_owner is not None
                    else None
                )
                _remove_operation_lock_entries(
                    directory,
                    lock_path,
                    operation,
                    stream,
                    retained_owner,
                )
                _finish_operation_lock_removal(
                    lock_path,
                    operation,
                    directory,
                    stream,
                    acquired=True,
                )
                removed = True
                acquired = False
                stream = None
                directory = None
                if isinstance(previous, dict):
                    reclaimed_token = previous.get("token")
                publication_deadline = None
                publication_identity = None
                publication_kernel_identity = None
                publication_owner_identity = None
                continue

            record = {
                "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
                "state": "held",
                "pid": os.getpid(),
                "process_instance_token": _PROCESS_INSTANCE_TOKEN,
                "token": uuid.uuid4().hex,
                "operation": operation,
                "reclaimed_token": reclaimed_token,
            }
            owner: dict[str, Any] | None = None
            try:
                owner = _publish_operation_owner(
                    directory,
                    lock_path,
                    operation,
                    record,
                )
                owner_marker = (
                    lock_path / owner["owner_name"] / "published"
                )
                for boundary in _OPERATION_LOCK_FORMER_WRITE_BOUNDARIES:
                    _operation_lock_test_hook(
                        boundary,
                        lock_path / "kernel",
                        owner_marker,
                    )
                    _assert_operation_lock_directory_identity(
                        directory,
                        lock_path,
                        operation,
                    )
                    _assert_operation_kernel_identity(
                        directory,
                        stream,
                        lock_path / "kernel",
                        operation,
                        require_single_link=True,
                    )
                    owner = _assert_operation_owner_unchanged(
                        directory,
                        lock_path,
                        operation,
                        owner,
                        require_single_links=True,
                    )
            except Exception:
                if owner is None:
                    try:
                        partial = _operation_lock_entries(
                            lock_path,
                            operation,
                            require_published=False,
                            require_single_links=False,
                            _directory=directory,
                            _retain_handles=True,
                        )
                    except InstallerError:
                        partial = None
                    if partial is not None and partial["owner_name"] is not None:
                        owner = partial
                retained_owner = owner
                _remove_operation_lock_entries(
                    directory,
                    lock_path,
                    operation,
                    stream,
                    owner,
                )
                _finish_operation_lock_removal(
                    lock_path,
                    operation,
                    directory,
                    stream,
                    acquired=True,
                )
                removed = True
                acquired = False
                stream = None
                directory = None
                raise
            assert owner is not None
            retained_owner = owner
            try:
                yield record
            finally:
                current = _assert_operation_owner_unchanged(
                    directory,
                    lock_path,
                    operation,
                    owner,
                    require_single_links=False,
                )
                if current["record"].get("token") != record["token"]:
                    raise InstallerError(
                        "operation_lock_changed",
                        "fixture operation lock ownership changed before release",
                        exit_code=EXIT_VERIFY,
                        details={
                            "operation": operation,
                            "lock": str(lock_path),
                        },
                    )
                _remove_operation_lock_entries(
                    directory,
                    lock_path,
                    operation,
                    stream,
                    owner,
                )
                _finish_operation_lock_removal(
                    lock_path,
                    operation,
                    directory,
                    stream,
                    acquired=True,
                )
                removed = True
                acquired = False
                stream = None
                directory = None
            return
        finally:
            if not removed:
                _close_operation_owner_handles(retained_owner)
                if (
                    acquired
                    and stream is not None
                    and not stream.closed
                ):
                    try:
                        _release_file_lock(stream)
                    except OSError:
                        pass
                if stream is not None and not stream.closed:
                    stream.close()
                if directory is not None:
                    _close_operation_lock_directory(directory)


class _WindowsByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("file_attributes", ctypes.c_uint32),
        ("creation_time_low", ctypes.c_uint32),
        ("creation_time_high", ctypes.c_uint32),
        ("last_access_time_low", ctypes.c_uint32),
        ("last_access_time_high", ctypes.c_uint32),
        ("last_write_time_low", ctypes.c_uint32),
        ("last_write_time_high", ctypes.c_uint32),
        ("volume_serial_number", ctypes.c_uint32),
        ("file_size_high", ctypes.c_uint32),
        ("file_size_low", ctypes.c_uint32),
        ("number_of_links", ctypes.c_uint32),
        ("file_index_high", ctypes.c_uint32),
        ("file_index_low", ctypes.c_uint32),
    ]


class _WindowsUnicodeString(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ushort),
        ("maximum_length", ctypes.c_ushort),
        ("buffer", ctypes.POINTER(ctypes.c_wchar)),
    ]


class _WindowsObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("root_directory", ctypes.c_void_p),
        ("object_name", ctypes.POINTER(_WindowsUnicodeString)),
        ("attributes", ctypes.c_ulong),
        ("security_descriptor", ctypes.c_void_p),
        ("security_quality_of_service", ctypes.c_void_p),
    ]


class _WindowsIoStatusBlock(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_void_p),
        ("information", ctypes.c_size_t),
    ]


class _WindowsFileDispositionInformation(ctypes.Structure):
    _fields_ = [("delete_file", ctypes.c_ubyte)]


def _windows_kernel32() -> Any:
    global _WINDOWS_KERNEL32
    if _WINDOWS_KERNEL32 is not None:
        return _WINDOWS_KERNEL32
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.GetFileInformationByHandle.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_WindowsByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = ctypes.c_int
    kernel32.ReadFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = ctypes.c_int
    kernel32.SetFileInformationByHandle.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.SetFileInformationByHandle.restype = ctypes.c_int
    kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    kernel32.FlushFileBuffers.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    _WINDOWS_KERNEL32 = kernel32
    return kernel32


def _windows_ntdll() -> Any:
    global _WINDOWS_NTDLL
    if _WINDOWS_NTDLL is not None:
        return _WINDOWS_NTDLL
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtCreateFile.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.POINTER(_WindowsObjectAttributes),
        ctypes.POINTER(_WindowsIoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    ntdll.RtlNtStatusToDosError.restype = ctypes.c_ulong
    _WINDOWS_NTDLL = ntdll
    return ntdll


def _windows_error_from_code(code: int, path: Path) -> OSError:
    message = ctypes.FormatError(code)
    if code in {2, 3}:
        return FileNotFoundError(code, message, str(path))
    if code in {80, 183}:
        return FileExistsError(code, message, str(path))
    error = ctypes.WinError(code)
    error.filename = str(path)
    return error


def _windows_sharing_violation(error: OSError) -> bool:
    return 32 in {
        int(getattr(error, "errno", 0) or 0),
        int(getattr(error, "winerror", 0) or 0),
    }


def _windows_open_relative_no_follow(
    parent_handle: int,
    name: str,
    path: Path,
    *,
    directory: bool,
    create: bool,
    delete: bool = False,
    write: bool = False,
    share_delete: bool = False,
) -> int:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise OSError("relative Windows lock entry name is invalid")
    name_buffer = ctypes.create_unicode_buffer(name)
    encoded_length = len(name.encode("utf-16-le"))
    unicode_name = _WindowsUnicodeString(
        encoded_length,
        encoded_length + ctypes.sizeof(ctypes.c_wchar),
        ctypes.cast(name_buffer, ctypes.POINTER(ctypes.c_wchar)),
    )
    attributes = _WindowsObjectAttributes(
        ctypes.sizeof(_WindowsObjectAttributes),
        ctypes.c_void_p(parent_handle),
        ctypes.pointer(unicode_name),
        _WINDOWS_OBJ_CASE_INSENSITIVE | _WINDOWS_OBJ_DONT_REPARSE,
        None,
        None,
    )
    handle = ctypes.c_void_p()
    io_status = _WindowsIoStatusBlock()
    access = _WINDOWS_FILE_READ_ATTRIBUTES | _WINDOWS_SYNCHRONIZE
    access |= (
        _WINDOWS_FILE_LIST_DIRECTORY
        if directory
        else _WINDOWS_FILE_READ_DATA
    )
    if write:
        access |= _WINDOWS_FILE_WRITE_DATA
    if delete:
        access |= _WINDOWS_DELETE
    share_access = _WINDOWS_FILE_SHARE_READ | _WINDOWS_FILE_SHARE_WRITE
    if share_delete:
        share_access |= _WINDOWS_FILE_SHARE_DELETE
    create_options = (
        _WINDOWS_FILE_DIRECTORY_FILE
        if directory
        else _WINDOWS_FILE_NON_DIRECTORY_FILE
    )
    create_options |= (
        _WINDOWS_FILE_SYNCHRONOUS_IO_NONALERT
        | _WINDOWS_FILE_OPEN_REPARSE_POINT
    )
    status = _windows_ntdll().NtCreateFile(
        ctypes.byref(handle),
        access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        _WINDOWS_FILE_ATTRIBUTE_NORMAL,
        share_access,
        _WINDOWS_FILE_CREATE if create else _WINDOWS_FILE_OPEN,
        create_options,
        None,
        0,
    )
    if status < 0:
        code = int(_windows_ntdll().RtlNtStatusToDosError(status))
        raise _windows_error_from_code(code, path)
    if not handle.value:
        raise OSError("NtCreateFile returned an invalid handle")
    return int(handle.value)


def _windows_last_error(path: Path) -> OSError:
    code = ctypes.get_last_error()
    if code in {2, 3}:
        return FileNotFoundError(code, os.strerror(code), str(path))
    return ctypes.WinError(code)


def _windows_open_no_follow(
    path: Path,
    *,
    directory: bool,
    delete: bool = False,
    write: bool = False,
    share_delete: bool = False,
) -> int:
    kernel32 = _windows_kernel32()
    access = _WINDOWS_FILE_READ_ATTRIBUTES
    access |= (
        _WINDOWS_FILE_LIST_DIRECTORY
        if directory
        else _WINDOWS_FILE_READ_DATA
    )
    if delete:
        access |= _WINDOWS_DELETE
    if write:
        access |= _WINDOWS_FILE_WRITE_DATA
    handle = kernel32.CreateFileW(
        str(path),
        access,
        _WINDOWS_FILE_SHARE_READ
        | _WINDOWS_FILE_SHARE_WRITE
        | (_WINDOWS_FILE_SHARE_DELETE if share_delete else 0),
        None,
        _WINDOWS_OPEN_EXISTING,
        _WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT
        | (_WINDOWS_FILE_FLAG_BACKUP_SEMANTICS if directory else 0),
        None,
    )
    if handle == _WINDOWS_INVALID_HANDLE_VALUE:
        raise _windows_last_error(path)
    return int(handle)


def _windows_flush_handle(handle: int, path: Path) -> None:
    if not _windows_kernel32().FlushFileBuffers(handle):
        raise _windows_last_error(path)


def _windows_handle_information(
    handle: int,
    path: Path,
) -> _WindowsByHandleFileInformation:
    information = _WindowsByHandleFileInformation()
    if not _windows_kernel32().GetFileInformationByHandle(
        handle,
        ctypes.byref(information),
    ):
        raise _windows_last_error(path)
    return information


def _windows_regular_file_digest(handle: int, path: Path) -> str:
    hasher = hashlib.sha256()
    buffer = ctypes.create_string_buffer(1024 * 1024)
    read = ctypes.c_uint32()
    kernel32 = _windows_kernel32()
    while True:
        if not kernel32.ReadFile(
            handle,
            buffer,
            len(buffer),
            ctypes.byref(read),
            None,
        ):
            raise _windows_last_error(path)
        if read.value == 0:
            return hasher.hexdigest()
        hasher.update(buffer.raw[: read.value])


def _windows_mark_handle_for_deletion(handle: int, path: Path) -> None:
    disposition = _WindowsFileDispositionInformation(1)
    if not _windows_kernel32().SetFileInformationByHandle(
        handle,
        _WINDOWS_FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise _windows_last_error(path)


def _windows_delete_relative_exact(
    parent_handle: int,
    name: str,
    path: Path,
    *,
    expected_identity: tuple[int, ...],
    directory: bool,
) -> None:
    handle = _windows_open_relative_no_follow(
        parent_handle,
        name,
        path,
        directory=directory,
        create=False,
        delete=True,
        share_delete=False,
    )
    try:
        information = _windows_handle_information(handle, path)
        if (
            _windows_file_identity(information) != expected_identity
            or bool(
                information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
            )
            != directory
            or information.file_attributes
            & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("Windows lock entry identity changed before deletion")
        _windows_mark_handle_for_deletion(handle, path)
    finally:
        _windows_kernel32().CloseHandle(handle)


def _platform_id() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        architecture = "x86_64"
    elif machine in {"arm64", "aarch64"}:
        architecture = "aarch64"
    else:
        architecture = machine
    values = {
        ("windows", "x86_64"): "windows-x86_64",
        ("linux", "x86_64"): "linux-x86_64-gnu",
        ("darwin", "aarch64"): "macos-aarch64",
        ("darwin", "x86_64"): "macos-x86_64",
    }
    selected = values.get((system, architecture))
    if selected is None:
        raise InstallerError(
            "platform_not_pinned",
            "the current platform has no provisional Stage 1 pin",
            exit_code=EXIT_ENVIRONMENT,
            details={"system": system, "machine": machine},
        )
    return selected


def _toolchain_pin(
    toolchain_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    toolchain = _load_json(toolchain_path, code="toolchain_invalid")
    if (
        toolchain.get("schema_version") != 1
        or toolchain.get("pin_status") != "provisional"
        or toolchain.get("fallback_policy", {}).get("allow_latest") is not False
        or toolchain.get("fallback_policy", {}).get("allow_ambient_uv") is not False
        or toolchain.get("fallback_policy", {}).get("allow_system_python") is not False
    ):
        raise InstallerError(
            "toolchain_invalid",
            "toolchain must be the fail-closed provisional Stage 1 pin",
            exit_code=EXIT_VERIFY,
            details={"toolchain": str(toolchain_path)},
        )

    current_platform = _platform_id()
    uv = toolchain.get("uv")
    python = toolchain.get("python")
    if not isinstance(uv, dict) or not isinstance(python, dict):
        raise InstallerError(
            "toolchain_invalid",
            "toolchain uv and python sections must be objects",
            exit_code=EXIT_VERIFY,
        )
    uv_records = [
        record
        for record in uv.get("artifacts", [])
        if isinstance(record, dict)
        and record.get("platform_id") == current_platform
    ]
    python_records = [
        record
        for record in python.get("downloads", [])
        if isinstance(record, dict)
        and record.get("platform_id") == current_platform
    ]
    if len(uv_records) != 1 or len(python_records) != 1:
        raise InstallerError(
            "platform_not_pinned",
            "toolchain must contain one uv and Python pin for this platform",
            exit_code=EXIT_VERIFY,
            details={"platform_id": current_platform},
        )
    uv_record = uv_records[0]
    python_record = python_records[0]
    if (
        not isinstance(uv.get("version"), str)
        or not HASH_PATTERN.fullmatch(str(uv_record.get("sha256", "")))
        or not isinstance(uv_record.get("filename"), str)
        or not isinstance(python.get("request"), str)
        or not python.get("managed_only") is True
        or not isinstance(python_record.get("build_identity"), str)
    ):
        raise InstallerError(
            "toolchain_invalid",
            "selected uv or Python pin is incomplete",
            exit_code=EXIT_VERIFY,
            details={"platform_id": current_platform},
        )
    return toolchain, uv_record, python_record


def _wheel_identity(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise ValueError("wheel must contain exactly one METADATA")
            message = BytesParser().parsebytes(archive.read(metadata_names[0]))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as error:
        raise InstallerError(
            "wheel_invalid",
            "local wheel is not a valid single-distribution wheel",
            exit_code=EXIT_VERIFY,
            details={"wheel": str(path), "exception": type(error).__name__},
        ) from error
    name = message.get("Name")
    version = message.get("Version")
    if name != DISTRIBUTION or version != EXPECTED_VERSION:
        raise InstallerError(
            "wheel_identity_mismatch",
            "local wheel identity does not match the Stage 1 prerelease",
            exit_code=EXIT_VERIFY,
            details={
                "expected_name": DISTRIBUTION,
                "expected_version": EXPECTED_VERSION,
                "actual_name": name,
                "actual_version": version,
            },
        )
    return name, version


def _fixture_paths(root: Path) -> dict[str, Path]:
    return {
        "root": root,
        "home": root / "home",
        "xdg_cache": root / "xdg" / "cache",
        "xdg_config": root / "xdg" / "config",
        "xdg_data": root / "xdg" / "data",
        "xdg_state": root / "xdg" / "state",
        "appdata": root / "appdata" / "roaming",
        "localappdata": root / "appdata" / "local",
        "temp": root / "temp",
        "uv_root": root / "uv",
        "uv_artifacts": root / "uv" / "artifacts",
        "uv_python": root / "uv" / "python",
        "uv_tools": root / "uv" / "tools",
        "uv_bin": root / "uv" / "bin",
        "uv_cache": root / "uv" / "cache",
        "versions": root / "versions",
        "state": root / "state",
        "manifests": root / "state" / "manifests",
        "health_target": root / "health-target",
    }


def _make_fixture_layout(paths: dict[str, Path]) -> None:
    for key, path in paths.items():
        if key != "root":
            path.mkdir(parents=True, exist_ok=True)


def _fixture_environment(paths: dict[str, Path]) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(paths["home"]),
            "USERPROFILE": str(paths["home"]),
            "XDG_CACHE_HOME": str(paths["xdg_cache"]),
            "XDG_CONFIG_HOME": str(paths["xdg_config"]),
            "XDG_DATA_HOME": str(paths["xdg_data"]),
            "XDG_STATE_HOME": str(paths["xdg_state"]),
            "APPDATA": str(paths["appdata"]),
            "LOCALAPPDATA": str(paths["localappdata"]),
            "TEMP": str(paths["temp"]),
            "TMP": str(paths["temp"]),
            "TMPDIR": str(paths["temp"]),
            "UV_PYTHON_INSTALL_DIR": str(paths["uv_python"]),
            "UV_TOOL_DIR": str(paths["uv_tools"]),
            "UV_TOOL_BIN_DIR": str(paths["uv_bin"]),
            "UV_CACHE_DIR": str(paths["uv_cache"]),
            "UV_NO_CONFIG": "1",
            "UV_MANAGED_PYTHON": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    environment.pop("PYTHONPATH", None)
    environment.pop("VIRTUAL_ENV", None)
    environment.pop("CONDA_PREFIX", None)
    return environment


def _run(
    arguments: Sequence[str],
    *,
    environment: dict[str, str],
    code: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(arguments),
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise InstallerError(
            code,
            f"cannot execute {arguments[0]}",
            exit_code=EXIT_ENVIRONMENT,
            details={
                "command": list(arguments),
                "exception": type(error).__name__,
            },
        ) from error
    if result.returncode != 0:
        raise InstallerError(
            code,
            f"command failed with exit code {result.returncode}",
            exit_code=EXIT_ENVIRONMENT,
            details={
                "command": list(arguments),
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            },
        )
    return result


def _archive_uv_bytes(path: Path) -> bytes:
    expected_name = "uv.exe" if os.name == "nt" else "uv"
    matches: list[bytes] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                parts = Path(info.filename.replace("\\", "/")).parts
                if (
                    not info.is_dir()
                    and parts
                    and parts[-1] == expected_name
                    and not any(part in {"", ".", ".."} for part in parts)
                ):
                    matches.append(archive.read(info))
    else:
        try:
            with tarfile.open(path, mode="r:*") as archive:
                for member in archive.getmembers():
                    parts = Path(member.name.replace("\\", "/")).parts
                    if (
                        member.isfile()
                        and parts
                        and parts[-1] == expected_name
                        and not any(part in {"", ".", ".."} for part in parts)
                    ):
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise tarfile.ReadError("uv member has no bytes")
                        matches.append(stream.read())
        except tarfile.TarError as error:
            raise InstallerError(
                "uv_artifact_invalid",
                "uv artifact must be a valid zip or tar archive",
                exit_code=EXIT_VERIFY,
                details={"uv_artifact": str(path)},
            ) from error
    if len(matches) != 1:
        raise InstallerError(
            "uv_artifact_invalid",
            "uv artifact must contain exactly one platform uv executable",
            exit_code=EXIT_VERIFY,
            details={
                "uv_artifact": str(path),
                "expected_member": expected_name,
                "matches": len(matches),
            },
        )
    return matches[0]


def _prepare_uv(
    artifact: Path,
    uv_record: dict[str, Any],
    uv_version: str,
    paths: dict[str, Path],
    environment: dict[str, str],
    *,
    failure_point: str | None,
) -> tuple[Path, dict[str, Any]]:
    if failure_point == "download":
        raise InstallerError(
            "injected_download_failure",
            "injected failure before local uv artifact acquisition",
            exit_code=EXIT_ENVIRONMENT,
        )
    expected_hash = str(uv_record["sha256"])
    actual_hash = _sha256(artifact)
    if failure_point == "uv-hash":
        actual_hash = "0" * 64
    if actual_hash != expected_hash:
        raise InstallerError(
            "uv_artifact_hash_mismatch",
            "local uv artifact does not match the provisional platform pin",
            exit_code=EXIT_VERIFY,
            details={
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "uv_artifact": str(artifact),
            },
        )

    executable_bytes = _archive_uv_bytes(artifact)
    executable_name = "uv.exe" if os.name == "nt" else "uv"
    destination = (
        paths["uv_artifacts"]
        / uv_version
        / expected_hash
        / executable_name
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_bytes() != executable_bytes:
        temporary = destination.with_name(f".{executable_name}.{uuid.uuid4().hex}")
        try:
            temporary.write_bytes(executable_bytes)
            temporary.chmod(
                temporary.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    result = _run(
        [str(destination), "--version"],
        environment=environment,
        code="uv_version_failed",
        cwd=paths["root"],
    )
    match = UV_VERSION_PATTERN.match(result.stdout.strip())
    if match is None or match.group(1) != uv_version:
        raise InstallerError(
            "uv_version_mismatch",
            "verified uv artifact did not report the fixed version",
            exit_code=EXIT_VERIFY,
            details={
                "expected_version": uv_version,
                "output": result.stdout.strip(),
                "uv_executable": str(destination),
            },
        )
    provenance = {
        "platform_id": uv_record["platform_id"],
        "artifact": str(artifact),
        "artifact_sha256": expected_hash,
        "executable": str(destination),
        "executable_sha256": _sha256(destination),
        "version_output": result.stdout.strip(),
    }
    _atomic_write(paths["uv_root"] / "artifact-provenance.json", provenance)
    return destination, provenance


def _ensure_managed_python(
    uv: Path,
    request: str,
    build_identity: str,
    paths: dict[str, Path],
    environment: dict[str, str],
    *,
    failure_point: str | None,
) -> tuple[Path, dict[str, Any]]:
    if failure_point == "python-install":
        raise InstallerError(
            "injected_python_install_failure",
            "injected failure before fixed managed Python installation",
            exit_code=EXIT_ENVIRONMENT,
        )
    install = [
        str(uv),
        "python",
        "install",
        "--managed-python",
        "--no-bin",
        "--no-config",
    ]
    if os.name == "nt":
        install.append("--no-registry")
    install.append(request)
    _run(
        install,
        environment=environment,
        code="python_install_failed",
        cwd=paths["root"],
    )
    found = _run(
        [
            str(uv),
            "python",
            "find",
            "--managed-python",
            "--no-python-downloads",
            "--no-project",
            "--resolve-links",
            "--no-config",
            request,
        ],
        environment=environment,
        code="python_find_failed",
        cwd=paths["root"],
    )
    try:
        executable = Path(found.stdout.strip()).resolve(strict=True)
    except OSError as error:
        raise InstallerError(
            "python_provenance_failed",
            "uv returned an unavailable managed Python path",
            exit_code=EXIT_ENVIRONMENT,
            details={"output": found.stdout.strip()},
        ) from error
    python_root = paths["uv_python"].resolve()
    if not _path_within(executable, python_root):
        raise InstallerError(
            "python_not_fixture_managed",
            "selected Python is outside the fixture managed-Python root",
            exit_code=EXIT_VERIFY,
            details={
                "python": str(executable),
                "required_root": str(python_root),
            },
        )
    probe_code = (
        "import json,platform,sys;"
        "print(json.dumps({"
        "'implementation':platform.python_implementation(),"
        "'version':platform.python_version(),"
        "'executable':sys.executable,"
        "'base_executable':getattr(sys,'_base_executable',sys.executable)"
        "},sort_keys=True,separators=(',',':')))"
    )
    probe = _run(
        [str(executable), "-I", "-B", "-c", probe_code],
        environment=environment,
        code="python_probe_failed",
        cwd=paths["root"],
    )
    try:
        evidence = json.loads(probe.stdout)
        base_executable = Path(evidence["base_executable"]).resolve(strict=True)
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise InstallerError(
            "python_provenance_failed",
            "managed Python probe returned invalid provenance",
            exit_code=EXIT_VERIFY,
            details={"stdout": probe.stdout},
        ) from error
    expected_version = request.removeprefix("cpython@")
    if (
        evidence.get("implementation") != "CPython"
        or evidence.get("version") != expected_version
        or not _path_within(base_executable, python_root)
    ):
        raise InstallerError(
            "python_provenance_failed",
            "Python is not the exact fixture-owned managed CPython pin",
            exit_code=EXIT_VERIFY,
            details={
                "expected_request": request,
                "expected_build_identity": build_identity,
                "probe": evidence,
                "required_root": str(python_root),
            },
        )
    evidence.update(
        {
            "request": request,
            "build_identity": build_identity,
            "uv_find": str(executable),
        }
    )
    return executable, evidence


def _candidate_paths(root: Path) -> dict[str, Path]:
    return {
        "root": root,
        "tools": root / "tools",
        "bin": root / "bin",
        "marker": root / "candidate.json",
    }


def _install_tool(
    uv: Path,
    wheel: Path,
    python_request: str,
    candidate: dict[str, Path],
    paths: dict[str, Path],
    environment: dict[str, str],
) -> tuple[Path, Path]:
    candidate["root"].mkdir(parents=True, exist_ok=False)
    candidate["tools"].mkdir()
    candidate["bin"].mkdir()
    candidate_environment = environment.copy()
    candidate_environment.update(
        {
            "UV_TOOL_DIR": str(candidate["tools"]),
            "UV_TOOL_BIN_DIR": str(candidate["bin"]),
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    _run(
        [
            str(uv),
            "tool",
            "install",
            "--managed-python",
            "--python",
            python_request,
            "--no-python-downloads",
            "--no-index",
            "--offline",
            "--no-config",
            "--prerelease",
            "explicit",
            "--link-mode",
            "copy",
            str(wheel),
        ],
        environment=candidate_environment,
        code="wheel_install_failed",
        cwd=paths["root"],
    )
    launcher = candidate["bin"] / ("xc.exe" if os.name == "nt" else "xc")
    tool_environment = candidate["tools"] / DISTRIBUTION
    tool_python = tool_environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if not launcher.is_file() or not tool_python.is_file():
        raise InstallerError(
            "launcher_missing",
            "uv tool install did not create the expected absolute launcher",
            exit_code=EXIT_ENVIRONMENT,
            details={
                "launcher": str(launcher),
                "tool_python": str(tool_python),
            },
        )
    return launcher.resolve(), tool_python.resolve()


def _command_json(
    launcher: Path,
    arguments: Sequence[str],
    *,
    environment: dict[str, str],
    root: Path,
    code: str,
) -> dict[str, Any]:
    result = _run(
        [str(launcher), *arguments],
        environment=environment,
        code=code,
        cwd=root,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise InstallerError(
            code,
            "candidate launcher did not emit one JSON result",
            exit_code=EXIT_ENVIRONMENT,
            details={"stdout": result.stdout, "stderr": result.stderr},
        ) from error
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise InstallerError(
            code,
            "candidate health command did not report success",
            exit_code=EXIT_ENVIRONMENT,
            details={"payload": payload},
        )
    return payload


def _wheel_adapter(wheel: Path) -> str:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith("xcoding/_bundle/bundle-manifest.json")
            ]
            if len(names) != 1:
                raise ValueError("wheel Bundle manifest is not unique")
            manifest = json.loads(archive.read(names[0]))
            adapters = sorted(
                {
                    record["adapter_id"]
                    for record in manifest.get("resources", [])
                    if isinstance(record, dict)
                    and record.get("kind") == "host-adapter"
                    and isinstance(record.get("adapter_id"), str)
                }
            )
    except (KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise InstallerError(
            "wheel_manifest_invalid",
            "wheel does not expose one provider-neutral adapter identifier",
            exit_code=EXIT_VERIFY,
        ) from error
    if not adapters:
        raise InstallerError(
            "wheel_manifest_invalid",
            "wheel Bundle has no adapter for setup health validation",
            exit_code=EXIT_VERIFY,
        )
    return adapters[0]


def _health_gate(
    launcher: Path,
    tool_python: Path,
    managed_python_root: Path,
    wheel: Path,
    paths: dict[str, Path],
    environment: dict[str, str],
    *,
    failure_point: str | None,
) -> dict[str, Any]:
    if failure_point == "launcher":
        raise InstallerError(
            "injected_launcher_failure",
            "injected failure before absolute launcher validation",
            exit_code=EXIT_ENVIRONMENT,
        )
    commands = [
        ("version", ["version", "--json"]),
        ("bundle", ["bundle", "inspect", "--json"]),
        ("doctor", ["doctor", "--json"]),
    ]
    results: dict[str, Any] = {}
    for name, arguments in commands:
        results[name] = _command_json(
            launcher,
            arguments,
            environment=environment,
            root=paths["root"],
            code=f"candidate_{name}_failed",
        )
    adapter = _wheel_adapter(wheel)
    setup = _command_json(
        launcher,
        [
            "setup",
            "--dry-run",
            "--json",
            "--adapter",
            adapter,
            "--target-root",
            str(paths["health_target"]),
        ],
        environment=environment,
        root=paths["root"],
        code="candidate_setup_failed",
    )
    if setup.get("result", {}).get("writes_performed") is not False:
        raise InstallerError(
            "candidate_setup_wrote",
            "setup health gate did not prove a write-free dry-run",
            exit_code=EXIT_ENVIRONMENT,
            details={"payload": setup},
        )
    results["setup"] = setup

    probe_code = (
        "import json,platform,sys;"
        "print(json.dumps({"
        "'implementation':platform.python_implementation(),"
        "'version':platform.python_version(),"
        "'executable':sys.executable,"
        "'base_executable':getattr(sys,'_base_executable',sys.executable)"
        "},sort_keys=True,separators=(',',':')))"
    )
    probe = _run(
        [str(tool_python), "-I", "-B", "-c", probe_code],
        environment=environment,
        code="candidate_python_probe_failed",
        cwd=paths["root"],
    )
    try:
        provenance = json.loads(probe.stdout)
        executable = Path(provenance["executable"]).resolve(strict=True)
        base = Path(provenance["base_executable"]).resolve(strict=True)
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise InstallerError(
            "candidate_python_provenance_failed",
            "candidate Python provenance is invalid",
            exit_code=EXIT_VERIFY,
            details={"stdout": probe.stdout},
        ) from error
    if (
        provenance.get("implementation") != "CPython"
        or provenance.get("version") != "3.12.13"
        or executable != tool_python.resolve()
        or not _path_within(base, managed_python_root.resolve())
    ):
        raise InstallerError(
            "candidate_python_provenance_failed",
            "candidate does not use exact fixture-owned managed CPython",
            exit_code=EXIT_VERIFY,
            details={
                "probe": provenance,
                "tool_python": str(tool_python),
                "managed_python_root": str(managed_python_root),
            },
        )
    if failure_point == "post-check":
        raise InstallerError(
            "injected_post_check_failure",
            "injected failure after candidate health commands",
            exit_code=EXIT_ENVIRONMENT,
        )
    results["python"] = provenance
    return results


def _entry_digest(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        target = os.readlink(path)
        return "symlink", hashlib.sha256(
            target.encode("utf-8", errors="surrogateescape")
        ).hexdigest()
    if path.is_file():
        return "file", _sha256(path)
    raise InstallerError(
        "ownership_entry_invalid",
        "ownership manifests support only regular files and symlinks",
        exit_code=EXIT_VERIFY,
        details={"path": str(path)},
    )


def _ownership_entries(candidate_root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(candidate_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir() and not path.is_symlink():
            continue
        kind, digest = _entry_digest(path)
        entries.append(
            {
                "path": path.relative_to(candidate_root).as_posix(),
                "kind": kind,
                "sha256": digest,
            }
        )
    return entries


def _active_path(paths: dict[str, Path]) -> Path:
    return paths["state"] / "active.json"


def _terminal_cleanup_path(paths: dict[str, Path]) -> Path:
    return paths["state"] / "uninstall-finalize.json"


def _ownership_transition_path(paths: dict[str, Path]) -> Path:
    return paths["state"] / "ownership-transition.json"


def _validate_relative(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InstallerError(
            "state_invalid",
            f"{field} must be a normalized relative path",
            exit_code=EXIT_VERIFY,
        )
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InstallerError(
            "state_invalid",
            f"{field} must be a normalized relative path",
            exit_code=EXIT_VERIFY,
        )
    return path


def _load_active(paths: dict[str, Path]) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    active_path = _assert_real_regular_file(
        paths["root"],
        _active_path(paths).relative_to(paths["root"]),
    )
    active = _load_json(active_path, code="activation_invalid")
    if (
        active.get("fixture_schema_version") != FIXTURE_SCHEMA_VERSION
        or active.get("distribution") != DISTRIBUTION
    ):
        raise InstallerError(
            "activation_invalid",
            "activation state is not an I5 fixture activation",
            exit_code=EXIT_VERIFY,
        )
    manifest_relative = _validate_relative(
        active.get("ownership_manifest"),
        field="ownership_manifest",
    )
    manifest_path = paths["root"] / manifest_relative
    if not _path_within(manifest_path, paths["manifests"]):
        raise InstallerError(
            "activation_invalid",
            "ownership manifest is outside the fixture manifest root",
            exit_code=EXIT_VERIFY,
        )
    manifest_path = _assert_real_regular_file(paths["root"], manifest_relative)
    expected_hash = active.get("ownership_manifest_sha256")
    if (
        not isinstance(expected_hash, str)
        or not HASH_PATTERN.fullmatch(expected_hash)
        or not manifest_path.is_file()
        or _sha256(manifest_path) != expected_hash
    ):
        raise InstallerError(
            "ownership_manifest_hash_mismatch",
            "activation ownership manifest hash does not match",
            exit_code=EXIT_VERIFY,
            details={"manifest": str(manifest_path)},
        )
    manifest = _load_json(manifest_path, code="ownership_manifest_invalid")
    return active, manifest_path, manifest


def _cleanup_candidate(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _install_fixture_unlocked(
    *,
    wheel_value: str,
    wheel_sha256: str,
    uv_artifact_value: str,
    fixture_root_value: str,
    toolchain_value: str,
    failure_point: str | None = None,
    force_candidate: bool = False,
) -> dict[str, Any]:
    if failure_point is not None and failure_point not in FAILURE_POINTS:
        raise InstallerError(
            "failure_point_invalid",
            "failure point is not part of the bounded I5 injection set",
            exit_code=EXIT_INPUT,
            details={"failure_point": failure_point},
        )
    if not HASH_PATTERN.fullmatch(wheel_sha256):
        raise InstallerError(
            "wheel_sha256_invalid",
            "wheel SHA-256 must be 64 lowercase hexadecimal characters",
            exit_code=EXIT_INPUT,
        )
    fixture_root = _fixture_root(fixture_root_value)
    wheel = _absolute_file(wheel_value, field="wheel")
    artifact = _absolute_file(uv_artifact_value, field="uv_artifact")
    toolchain_path = _absolute_file(toolchain_value, field="toolchain")
    toolchain, uv_record, python_record = _toolchain_pin(toolchain_path)
    if artifact.name != uv_record["filename"]:
        raise InstallerError(
            "uv_artifact_filename_mismatch",
            "local uv artifact filename does not match the platform pin",
            exit_code=EXIT_VERIFY,
            details={
                "expected": uv_record["filename"],
                "actual": artifact.name,
            },
        )

    actual_wheel_hash = _sha256(wheel)
    if failure_point == "wheel-hash":
        actual_wheel_hash = "0" * 64
    if actual_wheel_hash != wheel_sha256:
        raise InstallerError(
            "wheel_hash_mismatch",
            "local wheel does not match the explicit expected SHA-256",
            exit_code=EXIT_VERIFY,
            details={
                "expected_sha256": wheel_sha256,
                "actual_sha256": actual_wheel_hash,
                "wheel": str(wheel),
            },
        )
    _, wheel_version = _wheel_identity(wheel)

    paths = _fixture_paths(fixture_root)
    _make_fixture_layout(paths)
    environment = _fixture_environment(paths)
    uv, uv_provenance = _prepare_uv(
        artifact,
        uv_record,
        str(toolchain["uv"]["version"]),
        paths,
        environment,
        failure_point=failure_point,
    )

    active_path = _active_path(paths)
    if active_path.exists() and not force_candidate and failure_point is None:
        active, _, _ = _load_active(paths)
        if (
            active.get("wheel_sha256") == wheel_sha256
            and active.get("version") == wheel_version
        ):
            launcher = (paths["root"] / _validate_relative(
                active.get("launcher"),
                field="launcher",
            )).resolve()
            tool_python = (paths["root"] / _validate_relative(
                active.get("tool_python"),
                field="tool_python",
            )).resolve()
            health = _health_gate(
                launcher,
                tool_python,
                paths["uv_python"],
                wheel,
                paths,
                environment,
                failure_point=None,
            )
            return {
                "action": "install",
                "repeated": True,
                "activated": True,
                "version": wheel_version,
                "wheel_sha256": wheel_sha256,
                "launcher": str(launcher),
                "tool_python": str(tool_python),
                "uv": uv_provenance,
                "health": health,
                "fixture_paths": {
                    key: str(value)
                    for key, value in paths.items()
                    if key != "root"
                },
            }

    candidate_id = (
        f"{wheel_version}-{wheel_sha256[:16]}-{uuid.uuid4().hex[:12]}"
    )
    candidate = _candidate_paths(paths["versions"] / candidate_id)
    manifest_path = paths["manifests"] / f"{candidate_id}.json"
    try:
        candidate["root"].mkdir(parents=True, exist_ok=False)
        _atomic_write(
            candidate["marker"],
            {
                "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "status": "staging",
                "version": wheel_version,
                "wheel_sha256": wheel_sha256,
            },
        )
        _, python_provenance = _ensure_managed_python(
            uv,
            str(toolchain["python"]["request"]),
            str(python_record["build_identity"]),
            paths,
            environment,
            failure_point=failure_point,
        )
        if failure_point == "wheel-install":
            raise InstallerError(
                "injected_wheel_install_failure",
                "injected failure before local wheel installation",
                exit_code=EXIT_ENVIRONMENT,
            )
        # _install_tool owns creation, so remove the marker-only shell first.
        shutil.rmtree(candidate["root"])
        launcher, tool_python = _install_tool(
            uv,
            wheel,
            str(toolchain["python"]["request"]),
            candidate,
            paths,
            environment,
        )
        _atomic_write(
            candidate["marker"],
            {
                "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "status": "health-check",
                "version": wheel_version,
                "wheel_sha256": wheel_sha256,
            },
        )
        health = _health_gate(
            launcher,
            tool_python,
            paths["uv_python"],
            wheel,
            paths,
            environment,
            failure_point=failure_point,
        )
        _atomic_write(
            candidate["marker"],
            {
                "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "status": "activated",
                "version": wheel_version,
                "wheel_sha256": wheel_sha256,
            },
        )
        ownership = {
            "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
            "distribution": DISTRIBUTION,
            "candidate_id": candidate_id,
            "candidate_root": candidate["root"].relative_to(paths["root"]).as_posix(),
            "version": wheel_version,
            "wheel_sha256": wheel_sha256,
            "entries": _ownership_entries(candidate["root"]),
        }
        manifest_sha256 = _atomic_write(manifest_path, ownership)
        if failure_point == "activation":
            raise InstallerError(
                "injected_activation_failure",
                "injected failure before atomic activation",
                exit_code=EXIT_ENVIRONMENT,
            )
        activation = {
            "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
            "distribution": DISTRIBUTION,
            "candidate_id": candidate_id,
            "candidate_root": candidate["root"].relative_to(paths["root"]).as_posix(),
            "version": wheel_version,
            "wheel_sha256": wheel_sha256,
            "launcher": launcher.relative_to(paths["root"]).as_posix(),
            "tool_python": tool_python.relative_to(paths["root"]).as_posix(),
            "ownership_manifest": manifest_path.relative_to(paths["root"]).as_posix(),
            "ownership_manifest_sha256": manifest_sha256,
        }
        _atomic_write(active_path, activation)
    except Exception:
        _cleanup_candidate(candidate["root"])
        manifest_path.unlink(missing_ok=True)
        raise

    return {
        "action": "install",
        "repeated": False,
        "activated": True,
        "candidate_id": candidate_id,
        "version": wheel_version,
        "wheel_sha256": wheel_sha256,
        "launcher": str(launcher),
        "tool_python": str(tool_python),
        "ownership_manifest": str(manifest_path),
        "ownership_manifest_sha256": manifest_sha256,
        "uv": uv_provenance,
        "python": python_provenance,
        "health": health,
        "fixture_paths": {
            key: str(value)
            for key, value in paths.items()
            if key != "root"
        },
    }


def install_fixture(
    *,
    wheel_value: str,
    wheel_sha256: str,
    uv_artifact_value: str,
    fixture_root_value: str,
    toolchain_value: str,
    failure_point: str | None = None,
    force_candidate: bool = False,
) -> dict[str, Any]:
    fixture_root = _fixture_root(fixture_root_value)
    with _fixture_operation_lock(fixture_root, "install"):
        _resolve_ownership_transition(_fixture_paths(fixture_root))
        return _install_fixture_unlocked(
            wheel_value=wheel_value,
            wheel_sha256=wheel_sha256,
            uv_artifact_value=uv_artifact_value,
            fixture_root_value=str(fixture_root),
            toolchain_value=toolchain_value,
            failure_point=failure_point,
            force_candidate=force_candidate,
        )


def _manifest_entries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise InstallerError(
            "ownership_manifest_invalid",
            "ownership manifest entries must be an array",
            exit_code=EXIT_VERIFY,
        )
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise InstallerError(
                "ownership_manifest_invalid",
                "ownership manifest entry must be an object",
                exit_code=EXIT_VERIFY,
            )
        relative = _validate_relative(raw.get("path"), field="entry.path")
        value = relative.as_posix()
        if (
            value in seen
            or raw.get("kind") not in {"file", "symlink"}
            or not isinstance(raw.get("sha256"), str)
            or not HASH_PATTERN.fullmatch(raw["sha256"])
        ):
            raise InstallerError(
                "ownership_manifest_invalid",
                "ownership manifest entry is duplicate or incomplete",
                exit_code=EXIT_VERIFY,
                details={"entry": raw},
            )
        seen.add(value)
        entries.append(
            {
                "path": value,
                "kind": raw["kind"],
                "sha256": raw["sha256"],
            }
        )
    return entries


def _windows_owned_entry_state(
    candidate_root: Path,
    relative: Path,
    *,
    expected_kind: str | None,
    expected_digest: str | None,
    delete: bool,
) -> tuple[str, str]:
    kernel32 = _windows_kernel32()
    handles: list[int] = []
    target = candidate_root / relative
    try:
        current_path = candidate_root
        current_handle = _windows_open_no_follow(current_path, directory=True)
        handles.append(current_handle)
        information = _windows_handle_information(current_handle, current_path)
        if (
            not information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
            or information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("candidate root is not a real directory")
        for part in relative.parts[:-1]:
            current_path = current_path / part
            current_handle = _windows_open_no_follow(
                current_path,
                directory=True,
            )
            handles.append(current_handle)
            information = _windows_handle_information(
                current_handle,
                current_path,
            )
            if (
                not information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
                or information.file_attributes
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError("owned entry parent is not a real directory")

        target_handle = _windows_open_no_follow(
            target,
            directory=False,
            delete=delete,
        )
        handles.append(target_handle)
        information = _windows_handle_information(target_handle, target)
        if information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY:
            raise OSError("owned entry is a directory")
        if information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT:
            value = os.lstat(target)
            if not stat.S_ISLNK(value.st_mode):
                raise OSError("owned entry is an unsupported reparse point")
            link_target = os.readlink(target)
            kind = "symlink"
            digest = hashlib.sha256(
                link_target.encode("utf-8", errors="surrogateescape")
            ).hexdigest()
        else:
            kind = "file"
            digest = _windows_regular_file_digest(target_handle, target)
        if (
            expected_kind is not None
            and kind != expected_kind
        ) or (
            expected_digest is not None
            and digest != expected_digest
        ):
            raise InstallerError(
                "ownership_entry_changed",
                "owned entry changed after uninstall preflight",
                exit_code=EXIT_DRIFT,
                details={"path": relative.as_posix()},
            )
        if delete:
            _windows_mark_handle_for_deletion(target_handle, target)
        return kind, digest
    except FileNotFoundError:
        raise
    except InstallerError:
        raise
    except OSError as error:
        raise InstallerError(
            "ownership_path_unsafe",
            "cannot inspect or delete an owned entry through retained handles",
            exit_code=EXIT_VERIFY,
            details={
                "path": str(target),
                "exception": type(error).__name__,
            },
        ) from error
    finally:
        for handle in reversed(handles):
            kernel32.CloseHandle(handle)


def _owned_entry_delete_test_hook(
    boundary: str,
    candidate_root: Path,
    relative: Path,
) -> None:
    del boundary, candidate_root, relative


def _posix_delete_quarantine_prefix(name: str) -> str:
    digest = hashlib.sha256(os.fsencode(name)).hexdigest()
    return f"{_POSIX_DELETE_QUARANTINE_PREFIX}{digest}-"


def _posix_delete_quarantine_error(
    target: Path,
    quarantine: Path,
    reason: str,
    error: OSError | None = None,
) -> InstallerError:
    details = {
        "path": str(target),
        "quarantine": str(quarantine),
        "reason": reason,
    }
    if error is not None:
        details["exception"] = type(error).__name__
        details["errno"] = error.errno
    return InstallerError(
        "ownership_quarantine_recovery_required",
        "owned entry quarantine requires fail-closed recovery",
        exit_code=EXIT_ENVIRONMENT,
        details=details,
    )


def _posix_rename_no_replace(
    source_descriptor: int,
    source_name: str,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        rename = getattr(libc, "renameat2", None)
        exclusive_flag = 1
    elif sys.platform == "darwin":
        rename = getattr(libc, "renameatx_np", None)
        exclusive_flag = 0x00000004
    else:
        rename = None
        exclusive_flag = 0
    if rename is None:
        raise OSError(
            errno.ENOTSUP,
            "atomic no-replace rename is unavailable",
        )
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    result = rename(
        source_descriptor,
        os.fsencode(source_name),
        destination_descriptor,
        os.fsencode(destination_name),
        exclusive_flag,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    message = os.strerror(error_number)
    if error_number == errno.ENOENT:
        raise FileNotFoundError(error_number, message, destination_name)
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, message, destination_name)
    raise OSError(error_number, message, destination_name)


def _restore_posix_delete_quarantine(
    parent_descriptor: int,
    parent_path: Path,
    name: str,
    quarantine_name: str,
    target: Path,
) -> None:
    quarantine_path = parent_path / quarantine_name
    try:
        quarantined = os.stat(
            quarantine_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as error:
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "quarantined_entry_unavailable",
            error,
        ) from error

    def visible_target() -> os.stat_result | None:
        try:
            return os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "restore_target_inspection_failed",
                error,
            ) from error

    def reject_conflict(
        visible: os.stat_result,
        error: OSError | None = None,
    ) -> None:
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            (
                "restore_target_duplicate"
                if os.path.samestat(quarantined, visible)
                else "restore_target_conflict"
            ),
            error,
        )

    visible = visible_target()
    if visible is not None:
        if not os.path.samestat(quarantined, visible):
            reject_conflict(visible)
        try:
            os.unlink(quarantine_name, dir_fd=parent_descriptor)
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "restore_duplicate_cleanup_failed",
                error,
            ) from error
        return

    linked = False
    try:
        os.link(
            quarantine_name,
            name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        linked = True
    except FileExistsError as error:
        visible = visible_target()
        if visible is None:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "restore_target_disappeared",
                error,
            ) from error
        reject_conflict(visible, error)
    except FileNotFoundError as error:
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "quarantined_entry_unavailable",
            error,
        ) from error
    except OSError as link_error:
        try:
            _posix_rename_no_replace(
                parent_descriptor,
                quarantine_name,
                parent_descriptor,
                name,
            )
        except FileExistsError as error:
            visible = visible_target()
            if visible is None:
                raise _posix_delete_quarantine_error(
                    target,
                    quarantine_path,
                    "restore_target_disappeared",
                    error,
                ) from error
            reject_conflict(visible, error)
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "quarantined_entry_restore_failed",
                error,
            ) from link_error

    if linked:
        try:
            current_quarantine = os.stat(
                quarantine_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            visible = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "linked_restore_identity_unavailable",
                error,
            ) from error
        if (
            not os.path.samestat(quarantined, current_quarantine)
            or not os.path.samestat(quarantined, visible)
        ):
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "linked_restore_identity_mismatch",
            )
        try:
            os.unlink(quarantine_name, dir_fd=parent_descriptor)
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "restore_quarantine_cleanup_failed",
                error,
            ) from error

    try:
        visible = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError as error:
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "restored_entry_unavailable",
            error,
        ) from error
    if not os.path.samestat(quarantined, visible):
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "restored_entry_identity_mismatch",
        )


def _posix_quarantined_entry_state(
    parent_descriptor: int,
    quarantine_name: str,
) -> tuple[str, str, tuple[int, int]]:
    before = os.stat(
        quarantine_name,
        dir_fd=parent_descriptor,
        follow_symlinks=False,
    )
    if stat.S_ISLNK(before.st_mode):
        link_target = os.readlink(
            quarantine_name,
            dir_fd=parent_descriptor,
        )
        after = os.stat(
            quarantine_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISLNK(after.st_mode)
            or not os.path.samestat(before, after)
        ):
            raise OSError(
                errno.ESTALE,
                "quarantined symlink changed while reading",
            )
        return (
            "symlink",
            hashlib.sha256(
                link_target.encode("utf-8", errors="surrogateescape")
            ).hexdigest(),
            _operation_lock_identity(after),
        )
    if not stat.S_ISREG(before.st_mode):
        raise OSError(
            errno.EINVAL,
            "quarantined entry is not a regular file or symlink",
        )

    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    file_flags |= getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(
        quarantine_name,
        file_flags,
        dir_fd=parent_descriptor,
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
        ):
            raise OSError(
                errno.ESTALE,
                "quarantined file changed while opening",
            )
        hasher = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            hasher.update(block)
        visible = os.stat(
            quarantine_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if not os.path.samestat(opened, visible):
            raise OSError(
                errno.ESTALE,
                "quarantined file changed while reading",
            )
        return (
            "file",
            hasher.hexdigest(),
            _operation_lock_identity(opened),
        )
    finally:
        os.close(descriptor)


def _recover_posix_delete_quarantines(
    parent_descriptor: int,
    parent_path: Path,
    name: str,
    target: Path,
) -> None:
    prefix = _posix_delete_quarantine_prefix(name)
    quarantine_names = sorted(
        entry
        for entry in os.listdir(parent_descriptor)
        if entry.startswith(prefix)
    )
    for quarantine_name in quarantine_names:
        suffix = quarantine_name.removeprefix(prefix)
        quarantine_path = parent_path / quarantine_name
        if not re.fullmatch(r"[0-9a-f]{32}", suffix):
            raise _posix_delete_quarantine_error(
                target,
                quarantine_path,
                "quarantine_name_invalid",
            )
        _restore_posix_delete_quarantine(
            parent_descriptor,
            parent_path,
            name,
            quarantine_name,
            target,
        )


def _delete_posix_verified_entry(
    candidate_root: Path,
    relative: Path,
    parent_descriptor: int,
    parent_path: Path,
    name: str,
    expected_identity: tuple[int, int],
    expected_kind: str,
    expected_digest: str,
) -> None:
    target = candidate_root / relative
    prefix = _posix_delete_quarantine_prefix(name)
    quarantine_name: str | None = None
    for _ in range(16):
        candidate_name = prefix + secrets.token_hex(16)
        try:
            _posix_rename_no_replace(
                parent_descriptor,
                name,
                parent_descriptor,
                candidate_name,
            )
        except FileExistsError:
            continue
        except FileNotFoundError:
            raise
        except OSError as error:
            raise _posix_delete_quarantine_error(
                target,
                parent_path / candidate_name,
                "entry_quarantine_failed",
                error,
            ) from error
        quarantine_name = candidate_name
        break
    if quarantine_name is None:
        raise _posix_delete_quarantine_error(
            target,
            parent_path / (prefix + "<unavailable>"),
            "quarantine_name_exhausted",
        )

    quarantine_path = parent_path / quarantine_name
    _owned_entry_delete_test_hook(
        "after-quarantine-rename",
        candidate_root,
        relative,
    )
    try:
        quarantined_kind, quarantined_digest, quarantined_identity = (
            _posix_quarantined_entry_state(
                parent_descriptor,
                quarantine_name,
            )
        )
    except OSError as error:
        _restore_posix_delete_quarantine(
            parent_descriptor,
            parent_path,
            name,
            quarantine_name,
            target,
        )
        raise InstallerError(
            "ownership_entry_changed",
            "owned entry changed while its quarantine was verified",
            exit_code=EXIT_DRIFT,
            details={
                "path": relative.as_posix(),
                "replacement_restored": True,
                "exception": type(error).__name__,
            },
        ) from error
    if (
        quarantined_identity != expected_identity
        or quarantined_kind != expected_kind
        or quarantined_digest != expected_digest
    ):
        _restore_posix_delete_quarantine(
            parent_descriptor,
            parent_path,
            name,
            quarantine_name,
            target,
        )
        raise InstallerError(
            "ownership_entry_changed",
            "owned entry identity changed before quarantine deletion",
            exit_code=EXIT_DRIFT,
            details={
                "path": relative.as_posix(),
                "replacement_restored": True,
            },
        )

    try:
        os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        pass
    except OSError as error:
        raise _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "delete_target_inspection_failed",
            error,
        ) from error
    else:
        _restore_posix_delete_quarantine(
            parent_descriptor,
            parent_path,
            name,
            quarantine_name,
            target,
        )
        raise InstallerError(
            "ownership_entry_changed",
            "a replacement appeared while the owned entry was quarantined",
            exit_code=EXIT_DRIFT,
            details={
                "path": relative.as_posix(),
                "replacement_preserved": True,
            },
        )

    try:
        os.unlink(quarantine_name, dir_fd=parent_descriptor)
    except OSError as error:
        try:
            _restore_posix_delete_quarantine(
                parent_descriptor,
                parent_path,
                name,
                quarantine_name,
                target,
            )
        except InstallerError as recovery_error:
            recovery_error.details.setdefault(
                "cleanup_exception",
                type(error).__name__,
            )
            raise recovery_error from error
        cleanup_error = _posix_delete_quarantine_error(
            target,
            quarantine_path,
            "verified_quarantine_cleanup_failed",
            error,
        )
        cleanup_error.details["verified_entry_restored"] = True
        raise cleanup_error from error

    try:
        os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    except OSError as error:
        raise InstallerError(
            "ownership_path_unsafe",
            "cannot confirm identity-bound owned entry deletion",
            exit_code=EXIT_VERIFY,
            details={
                "path": str(target),
                "exception": type(error).__name__,
            },
        ) from error
    raise InstallerError(
        "ownership_entry_changed",
        "a replacement appeared while the verified owned entry was deleted",
        exit_code=EXIT_DRIFT,
        details={
            "path": relative.as_posix(),
            "replacement_preserved": True,
        },
    )


def _owned_entry_state(
    candidate_root: Path,
    relative_value: str,
    *,
    expected_kind: str | None = None,
    expected_digest: str | None = None,
    delete: bool = False,
) -> tuple[str, str]:
    relative = Path(relative_value)
    if os.name == "nt":
        return _windows_owned_entry_state(
            candidate_root,
            relative,
            expected_kind=expected_kind,
            expected_digest=expected_digest,
            delete=delete,
        )
    else:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptors: list[int] = []
        try:
            current = os.open(candidate_root, flags)
            descriptors.append(current)
            for part in relative.parts[:-1]:
                current = os.open(part, flags, dir_fd=current)
                descriptors.append(current)
            name = relative.parts[-1]
            parent_path = candidate_root.joinpath(*relative.parts[:-1])
            target_path = candidate_root / relative
            _recover_posix_delete_quarantines(
                current,
                parent_path,
                name,
                target_path,
            )
            value = os.stat(name, dir_fd=current, follow_symlinks=False)
            if stat.S_ISLNK(value.st_mode):
                target = os.readlink(name, dir_fd=current)
                kind = "symlink"
                digest = hashlib.sha256(
                    target.encode("utf-8", errors="surrogateescape")
                ).hexdigest()
                identity = _operation_lock_identity(value)
            elif stat.S_ISREG(value.st_mode):
                file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                file_descriptor = os.open(name, file_flags, dir_fd=current)
                descriptors.append(file_descriptor)
                opened = os.fstat(file_descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or not os.path.samestat(value, opened)
                ):
                    raise OSError("entry changed while opening")
                hasher = hashlib.sha256()
                while True:
                    block = os.read(file_descriptor, 1024 * 1024)
                    if not block:
                        break
                    hasher.update(block)
                kind = "file"
                digest = hasher.hexdigest()
                identity = _operation_lock_identity(opened)
            else:
                raise OSError("entry is not a regular file or symlink")
            if (
                expected_kind is not None
                and kind != expected_kind
            ) or (
                expected_digest is not None
                and digest != expected_digest
            ):
                raise InstallerError(
                    "ownership_entry_changed",
                    "owned entry changed after uninstall preflight",
                    exit_code=EXIT_DRIFT,
                    details={"path": relative_value},
                )
            if delete:
                _owned_entry_delete_test_hook(
                    "after-final-read",
                    candidate_root,
                    relative,
                )
                _delete_posix_verified_entry(
                    candidate_root,
                    relative,
                    current,
                    parent_path,
                    name,
                    identity,
                    kind,
                    digest,
                )
            return kind, digest
        except FileNotFoundError:
            raise
        except InstallerError:
            raise
        except OSError as error:
            raise InstallerError(
                "ownership_path_unsafe",
                "cannot inspect or delete an owned entry without following links",
                exit_code=EXIT_VERIFY,
                details={
                    "path": str(candidate_root / relative),
                    "exception": type(error).__name__,
                },
            ) from error
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


def _candidate_inventory(candidate_root: Path) -> tuple[set[str], list[str]]:
    if not candidate_root.exists():
        return set(), []
    _assert_real_directory(candidate_root)
    actual: set[str] = set()
    unsafe: list[str] = []

    def visit(directory: Path, prefix: Path) -> None:
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda item: item.name)
        except OSError as error:
            raise InstallerError(
                "ownership_path_unsafe",
                "cannot enumerate candidate content without following links",
                exit_code=EXIT_VERIFY,
                details={"path": str(directory), "exception": type(error).__name__},
            ) from error
        for item in ordered:
            relative = prefix / item.name
            value = item.stat(follow_symlinks=False)
            relative_value = relative.as_posix()
            if _is_reparse_point(value) and not stat.S_ISLNK(value.st_mode):
                actual.add(relative_value)
                unsafe.append(relative_value)
            elif stat.S_ISDIR(value.st_mode):
                visit(Path(item.path), relative)
            else:
                actual.add(relative_value)

    visit(candidate_root, Path())
    return actual, unsafe


def _empty_directory_cleanup_test_hook(
    boundary: str,
    root: Path,
    directory: Path,
) -> None:
    del boundary, root, directory


def _empty_directory_cleanup_error(
    path: Path,
    reason: str,
    error: OSError | None = None,
) -> InstallerError:
    details = {"path": str(path), "reason": reason}
    if error is not None:
        details["exception"] = type(error).__name__
    return InstallerError(
        "ownership_path_unsafe",
        "cannot prune uninstall directories without following or replacing them",
        exit_code=EXIT_VERIFY,
        details=details,
    )


def _directory_not_empty(error: OSError) -> bool:
    return (
        int(getattr(error, "errno", 0) or 0)
        in {errno.EEXIST, errno.ENOTEMPTY}
        or int(getattr(error, "winerror", 0) or 0) == 145
    )


def _cleanup_absolute_path(root: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(root)))
    if not absolute.is_absolute() or not absolute.name:
        raise _empty_directory_cleanup_error(
            absolute,
            "cleanup_root_has_no_parent",
        )
    return absolute


def _posix_cleanup_close_diagnostic(
    handle: int,
    path: Path,
    error: BaseException,
) -> dict[str, Any]:
    return {
        "path": str(path),
        "handle": handle,
        "exception": type(error).__name__,
        "errno": getattr(error, "errno", None),
    }


def _report_posix_cleanup_close_failures(
    active_exception: BaseException,
    diagnostics: Sequence[dict[str, Any]],
) -> None:
    try:
        active_exception.add_note(
            "POSIX cleanup close failures: "
            + json.dumps(
                diagnostics,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except BaseException:
        pass
    if isinstance(active_exception, InstallerError):
        try:
            existing = active_exception.details.get("cleanup_close_errors")
            if isinstance(existing, list):
                existing.extend(dict(item) for item in diagnostics)
            else:
                active_exception.details["cleanup_close_errors"] = [
                    dict(item) for item in diagnostics
                ]
        except BaseException:
            pass


def _finish_posix_cleanup_close_failures(
    failures: Sequence[tuple[int, Path, BaseException]],
    *,
    active_exception: BaseException | None,
) -> None:
    if not failures:
        return
    diagnostics = [
        _posix_cleanup_close_diagnostic(handle, path, error)
        for handle, path, error in failures
    ]
    if active_exception is not None:
        _report_posix_cleanup_close_failures(
            active_exception,
            diagnostics,
        )
        return
    first_error = failures[0][2]
    if isinstance(first_error, OSError):
        failure = _empty_directory_cleanup_error(
            failures[0][1],
            "directory_handle_close_failed",
            first_error,
        )
        failure.details["cleanup_close_errors"] = diagnostics
        raise failure from first_error
    _report_posix_cleanup_close_failures(first_error, diagnostics)
    raise first_error


def _close_posix_cleanup_handle(
    handle: int,
    path: Path,
    *,
    active_exception: BaseException | None,
) -> None:
    try:
        os.close(handle)
    except BaseException as error:
        if isinstance(error, OSError) and error.errno == errno.EBADF:
            return
        _finish_posix_cleanup_close_failures(
            [(handle, path, error)],
            active_exception=active_exception,
        )


def _close_posix_cleanup_nodes(
    nodes: Sequence[dict[str, Any]],
    *,
    active_exception: BaseException | None = None,
) -> None:
    failures: list[tuple[int, Path, BaseException]] = []
    for node in reversed(nodes):
        handle = node.get("handle")
        if handle is None:
            continue
        node["handle"] = None
        try:
            os.close(handle)
        except BaseException as error:
            if isinstance(error, OSError) and error.errno == errno.EBADF:
                continue
            failures.append((handle, node["path"], error))
    _finish_posix_cleanup_close_failures(
        failures,
        active_exception=active_exception,
    )


def _open_posix_cleanup_chain(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    nodes: list[dict[str, Any]] = []
    anchor = Path(root.anchor)
    try:
        anchor_handle = os.open(anchor, flags)
        parent: dict[str, Any] | None = None
        try:
            anchor_value = os.fstat(anchor_handle)
            if not stat.S_ISDIR(anchor_value.st_mode):
                raise _empty_directory_cleanup_error(
                    anchor,
                    "path_anchor_not_directory",
                )
            parent = {
                "handle": anchor_handle,
                "identity": _operation_lock_identity(anchor_value),
                "name": None,
                "parent": None,
                "path": anchor,
                "children": [],
            }
            nodes.append(parent)
            anchor_handle = None
        finally:
            if anchor_handle is not None:
                if parent is not None:
                    for registered in nodes:
                        if registered is parent:
                            anchor_handle = None
                            break
                if anchor_handle is not None:
                    closing_handle = anchor_handle
                    anchor_handle = None
                    if parent is not None:
                        parent["handle"] = None
                    _close_posix_cleanup_handle(
                        closing_handle,
                        anchor,
                        active_exception=sys.exception(),
                    )
        assert parent is not None
        current_path = anchor
        for name in root.parts[1:]:
            current_path = current_path / name
            try:
                value = os.stat(
                    name,
                    dir_fd=parent["handle"],
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                _close_posix_cleanup_nodes(nodes)
                return None
            if (
                not stat.S_ISDIR(value.st_mode)
                or _unsafe_directory_entry(value)
            ):
                raise _empty_directory_cleanup_error(
                    current_path,
                    "path_component_not_real_directory",
                )
            handle = os.open(name, flags, dir_fd=parent["handle"])
            node: dict[str, Any] | None = None
            try:
                opened = os.fstat(handle)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or _operation_lock_identity(opened)
                    != _operation_lock_identity(value)
                ):
                    raise _empty_directory_cleanup_error(
                        current_path,
                        "path_component_identity_mismatch",
                    )
                node = {
                    "handle": handle,
                    "identity": _operation_lock_identity(opened),
                    "name": name,
                    "parent": parent,
                    "path": current_path,
                    "children": [],
                }
                nodes.append(node)
                handle = None
            finally:
                if handle is not None:
                    if node is not None:
                        for registered in nodes:
                            if registered is node:
                                handle = None
                                break
                    if handle is not None:
                        closing_handle = handle
                        handle = None
                        if node is not None:
                            node["handle"] = None
                        _close_posix_cleanup_handle(
                            closing_handle,
                            current_path,
                            active_exception=sys.exception(),
                        )
            assert node is not None
            parent = node
        return nodes, parent
    except InstallerError as error:
        _close_posix_cleanup_nodes(
            nodes,
            active_exception=error,
        )
        raise
    except FileNotFoundError:
        _close_posix_cleanup_nodes(nodes)
        return None
    except OSError as error:
        _close_posix_cleanup_nodes(
            nodes,
            active_exception=error,
        )
        raise _empty_directory_cleanup_error(
            root,
            "path_component_open_failed",
            error,
        ) from error
    except BaseException as error:
        _close_posix_cleanup_nodes(
            nodes,
            active_exception=error,
        )
        raise


def _assert_posix_cleanup_node(node: dict[str, Any]) -> bool:
    lineage: list[dict[str, Any]] = []
    current: dict[str, Any] | None = node
    while current is not None:
        lineage.append(current)
        current = current["parent"]
    for current in reversed(lineage):
        handle = current.get("handle")
        if handle is None:
            return False
        try:
            retained = os.fstat(handle)
        except OSError as error:
            raise _empty_directory_cleanup_error(
                current["path"],
                "retained_directory_unavailable",
                error,
            ) from error
        if (
            not stat.S_ISDIR(retained.st_mode)
            or _operation_lock_identity(retained)
            != tuple(current["identity"])
        ):
            raise _empty_directory_cleanup_error(
                current["path"],
                "retained_directory_identity_mismatch",
            )
        parent = current["parent"]
        if parent is None:
            continue
        try:
            visible = os.stat(
                current["name"],
                dir_fd=parent["handle"],
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return False
        except OSError as error:
            raise _empty_directory_cleanup_error(
                current["path"],
                "directory_identity_unavailable",
                error,
            ) from error
        if (
            not stat.S_ISDIR(visible.st_mode)
            or _unsafe_directory_entry(visible)
            or _operation_lock_identity(visible)
            != tuple(current["identity"])
        ):
            raise _empty_directory_cleanup_error(
                current["path"],
                "directory_identity_mismatch",
            )
    return True


def _open_posix_cleanup_child(
    parent: dict[str, Any],
    name: str,
    path: Path,
    nodes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        value = os.stat(
            name,
            dir_fd=parent["handle"],
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(value.st_mode)
            or _unsafe_directory_entry(value)
        ):
            raise _empty_directory_cleanup_error(
                path,
                "directory_entry_not_real_directory",
            )
        handle = os.open(name, flags, dir_fd=parent["handle"])
        child: dict[str, Any] | None = None
        try:
            opened = os.fstat(handle)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _operation_lock_identity(opened)
                != _operation_lock_identity(value)
            ):
                raise _empty_directory_cleanup_error(
                    path,
                    "directory_entry_identity_mismatch",
                )
            child = {
                "handle": handle,
                "identity": _operation_lock_identity(opened),
                "name": name,
                "parent": parent,
                "path": path,
                "children": [],
            }
            nodes.append(child)
            handle = None
        finally:
            if handle is not None:
                if child is not None:
                    for registered in nodes:
                        if registered is child:
                            handle = None
                            break
                if handle is not None:
                    closing_handle = handle
                    handle = None
                    if child is not None:
                        child["handle"] = None
                    _close_posix_cleanup_handle(
                        closing_handle,
                        path,
                        active_exception=sys.exception(),
                    )
        assert child is not None
        parent["children"].append(child)
        return child
    except FileNotFoundError:
        return None
    except InstallerError:
        raise
    except OSError as error:
        raise _empty_directory_cleanup_error(
            path,
            "directory_entry_open_failed",
            error,
        ) from error


def _scan_posix_cleanup_tree(
    node: dict[str, Any],
    root: Path,
    nodes: list[dict[str, Any]],
) -> bool:
    if not _assert_posix_cleanup_node(node):
        return True
    _empty_directory_cleanup_test_hook(
        "before-directory-scan",
        root,
        node["path"],
    )
    if not _assert_posix_cleanup_node(node):
        return True
    try:
        names = sorted(os.listdir(node["handle"]))
    except OSError as error:
        raise _empty_directory_cleanup_error(
            node["path"],
            "directory_scan_failed",
            error,
        ) from error
    empty = True
    for name in names:
        path = node["path"] / name
        try:
            value = os.stat(
                name,
                dir_fd=node["handle"],
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise _empty_directory_cleanup_error(
                path,
                "directory_entry_inspection_failed",
                error,
            ) from error
        if _unsafe_directory_entry(value):
            raise _empty_directory_cleanup_error(
                path,
                "directory_entry_link_or_reparse_point",
            )
        if stat.S_ISDIR(value.st_mode):
            child = _open_posix_cleanup_child(node, name, path, nodes)
            if child is not None and not _scan_posix_cleanup_tree(
                child,
                root,
                nodes,
            ):
                empty = False
        else:
            empty = False
    return empty


def _delete_posix_cleanup_tree(
    node: dict[str, Any],
    root: Path,
) -> bool:
    for child in node["children"]:
        if not _delete_posix_cleanup_tree(child, root):
            return False
    if not _assert_posix_cleanup_node(node):
        return True
    _empty_directory_cleanup_test_hook(
        "before-directory-remove",
        root,
        node["path"],
    )
    if not _assert_posix_cleanup_node(node):
        return True
    try:
        names = os.listdir(node["handle"])
        for name in names:
            value = os.stat(
                name,
                dir_fd=node["handle"],
                follow_symlinks=False,
            )
            if _unsafe_directory_entry(value):
                raise _empty_directory_cleanup_error(
                    node["path"] / name,
                    "directory_entry_link_or_reparse_point",
                )
        if names:
            return False
        os.rmdir(node["name"], dir_fd=node["parent"]["handle"])
    except FileNotFoundError:
        return True
    except InstallerError:
        raise
    except OSError as error:
        if _directory_not_empty(error):
            return False
        raise _empty_directory_cleanup_error(
            node["path"],
            "directory_remove_failed",
            error,
        ) from error
    handle = node["handle"]
    node["handle"] = None
    _close_posix_cleanup_handle(
        handle,
        node["path"],
        active_exception=None,
    )
    return True


def _remove_empty_directories_posix(root: Path) -> None:
    opened = _open_posix_cleanup_chain(root)
    if opened is None:
        return
    nodes, target = opened
    active_exception: BaseException | None = None
    try:
        if _scan_posix_cleanup_tree(target, root, nodes):
            _delete_posix_cleanup_tree(target, root)
    except BaseException as error:
        active_exception = error
        raise
    finally:
        _close_posix_cleanup_nodes(
            nodes,
            active_exception=active_exception,
        )


def _close_windows_cleanup_nodes(nodes: Sequence[dict[str, Any]]) -> None:
    for node in reversed(nodes):
        handle = node.get("handle")
        if handle is not None:
            _windows_kernel32().CloseHandle(handle)
            node["handle"] = None


def _windows_cleanup_node(
    handle: int,
    path: Path,
    name: str | None,
    parent: dict[str, Any] | None,
) -> dict[str, Any]:
    information = _windows_handle_information(handle, path)
    if (
        not information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
        or information.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise _empty_directory_cleanup_error(
            path,
            "path_component_not_real_directory",
        )
    return {
        "handle": handle,
        "identity": _windows_file_identity(information),
        "name": name,
        "parent": parent,
        "path": path,
        "children": [],
    }


def _open_windows_cleanup_chain(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    nodes: list[dict[str, Any]] = []
    anchor = Path(root.anchor)
    try:
        handle = _windows_open_no_follow(
            anchor,
            directory=True,
            share_delete=False,
        )
        try:
            parent = _windows_cleanup_node(handle, anchor, None, None)
        except Exception:
            _windows_kernel32().CloseHandle(handle)
            raise
        nodes.append(parent)
        current_path = anchor
        for name in root.parts[1:]:
            current_path = current_path / name
            handle = _windows_open_relative_no_follow(
                parent["handle"],
                name,
                current_path,
                directory=True,
                create=False,
                share_delete=False,
            )
            try:
                node = _windows_cleanup_node(
                    handle,
                    current_path,
                    name,
                    parent,
                )
            except Exception:
                _windows_kernel32().CloseHandle(handle)
                raise
            nodes.append(node)
            parent = node
        return nodes, parent
    except FileNotFoundError:
        _close_windows_cleanup_nodes(nodes)
        return None
    except InstallerError:
        _close_windows_cleanup_nodes(nodes)
        raise
    except OSError as error:
        _close_windows_cleanup_nodes(nodes)
        raise _empty_directory_cleanup_error(
            root,
            "path_component_open_failed",
            error,
        ) from error


def _assert_windows_cleanup_node(node: dict[str, Any]) -> bool:
    lineage: list[dict[str, Any]] = []
    current: dict[str, Any] | None = node
    while current is not None:
        lineage.append(current)
        current = current["parent"]
    for current in reversed(lineage):
        handle = current.get("handle")
        if handle is None:
            return False
        try:
            retained = _windows_handle_information(
                handle,
                current["path"],
            )
        except OSError as error:
            raise _empty_directory_cleanup_error(
                current["path"],
                "retained_directory_unavailable",
                error,
            ) from error
        if (
            not retained.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
            or retained.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            or _windows_file_identity(retained)
            != tuple(current["identity"])
        ):
            raise _empty_directory_cleanup_error(
                current["path"],
                "retained_directory_identity_mismatch",
            )
        parent = current["parent"]
        if parent is None:
            continue
        try:
            visible_handle = _windows_open_relative_no_follow(
                parent["handle"],
                current["name"],
                current["path"],
                directory=True,
                create=False,
                share_delete=True,
            )
        except FileNotFoundError:
            return False
        except OSError as error:
            raise _empty_directory_cleanup_error(
                current["path"],
                "directory_identity_unavailable",
                error,
            ) from error
        try:
            visible = _windows_handle_information(
                visible_handle,
                current["path"],
            )
        finally:
            _windows_kernel32().CloseHandle(visible_handle)
        if (
            not visible.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY
            or visible.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            or _windows_file_identity(visible)
            != tuple(current["identity"])
        ):
            raise _empty_directory_cleanup_error(
                current["path"],
                "directory_identity_mismatch",
            )
    return True


def _open_windows_cleanup_child(
    parent: dict[str, Any],
    name: str,
    path: Path,
    nodes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        handle = _windows_open_relative_no_follow(
            parent["handle"],
            name,
            path,
            directory=True,
            create=False,
            share_delete=False,
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        raise _empty_directory_cleanup_error(
            path,
            "directory_entry_open_failed",
            error,
        ) from error
    try:
        child = _windows_cleanup_node(handle, path, name, parent)
    except Exception:
        _windows_kernel32().CloseHandle(handle)
        raise
    parent["children"].append(child)
    nodes.append(child)
    return child


def _scan_windows_cleanup_tree(
    node: dict[str, Any],
    root: Path,
    nodes: list[dict[str, Any]],
) -> bool:
    if not _assert_windows_cleanup_node(node):
        return True
    _empty_directory_cleanup_test_hook(
        "before-directory-scan",
        root,
        node["path"],
    )
    if not _assert_windows_cleanup_node(node):
        return True
    try:
        with os.scandir(node["path"]) as entries:
            children = sorted(
                (
                    entry.name,
                    entry.stat(follow_symlinks=False),
                )
                for entry in entries
            )
    except OSError as error:
        raise _empty_directory_cleanup_error(
            node["path"],
            "directory_scan_failed",
            error,
        ) from error
    empty = True
    for name, value in children:
        path = node["path"] / name
        if _unsafe_directory_entry(value):
            raise _empty_directory_cleanup_error(
                path,
                "directory_entry_link_or_reparse_point",
            )
        if stat.S_ISDIR(value.st_mode):
            child = _open_windows_cleanup_child(node, name, path, nodes)
            if child is not None and not _scan_windows_cleanup_tree(
                child,
                root,
                nodes,
            ):
                empty = False
        else:
            empty = False
    return empty


def _delete_windows_cleanup_tree(
    node: dict[str, Any],
    root: Path,
) -> bool:
    for child in node["children"]:
        if not _delete_windows_cleanup_tree(child, root):
            return False
    if not _assert_windows_cleanup_node(node):
        return True
    _empty_directory_cleanup_test_hook(
        "before-directory-remove",
        root,
        node["path"],
    )
    if not _assert_windows_cleanup_node(node):
        return True
    try:
        with os.scandir(node["path"]) as entries:
            children = [
                (
                    Path(entry.path),
                    entry.stat(follow_symlinks=False),
                )
                for entry in entries
            ]
        for path, value in children:
            if _unsafe_directory_entry(value):
                raise _empty_directory_cleanup_error(
                    path,
                    "directory_entry_link_or_reparse_point",
                )
        if children:
            return False
    except FileNotFoundError:
        return True
    except InstallerError:
        raise
    except OSError as error:
        raise _empty_directory_cleanup_error(
            node["path"],
            "directory_scan_failed",
            error,
        ) from error
    identity = tuple(node["identity"])
    _windows_kernel32().CloseHandle(node["handle"])
    node["handle"] = None
    try:
        _windows_delete_relative_exact(
            node["parent"]["handle"],
            node["name"],
            node["path"],
            expected_identity=identity,
            directory=True,
        )
    except FileNotFoundError:
        return True
    except OSError as error:
        if _directory_not_empty(error):
            return False
        raise _empty_directory_cleanup_error(
            node["path"],
            "directory_remove_failed",
            error,
        ) from error
    return True


def _remove_empty_directories_windows(root: Path) -> None:
    opened = _open_windows_cleanup_chain(root)
    if opened is None:
        return
    nodes, target = opened
    try:
        if _scan_windows_cleanup_tree(target, root, nodes):
            _delete_windows_cleanup_tree(target, root)
    finally:
        _close_windows_cleanup_nodes(nodes)


def _remove_empty_directories(root: Path) -> None:
    absolute = _cleanup_absolute_path(root)
    if os.name == "nt":
        _remove_empty_directories_windows(absolute)
    else:
        _remove_empty_directories_posix(absolute)


def _persist_ownership_state(
    paths: dict[str, Path],
    active: dict[str, Any],
    manifest_path: Path,
    manifest: dict[str, Any],
    entries: Sequence[dict[str, str]],
    *,
    pending: str | None,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    _assert_real_directory_chain(paths["root"], ("state", "manifests"))
    state = dict(manifest)
    state["entries"] = [dict(entry) for entry in entries]
    if pending is None:
        state.pop("uninstall_pending", None)
    else:
        state["uninstall_pending"] = pending
    next_path = paths["manifests"] / f"uninstall-{uuid.uuid4().hex}.json"
    next_hash = _canonical_sha256(state)
    old_relative = manifest_path.relative_to(paths["root"])
    old_hash = active.get("ownership_manifest_sha256")
    if (
        old_relative.parent != Path("state/manifests")
        or active.get("ownership_manifest") != old_relative.as_posix()
        or not isinstance(old_hash, str)
        or not HASH_PATTERN.fullmatch(old_hash)
        or _sha256(manifest_path) != old_hash
    ):
        raise InstallerError(
            "ownership_transition_invalid",
            "current ownership state is not exactly bound to its manifest",
            exit_code=EXIT_VERIFY,
        )
    next_active = dict(active)
    next_active["ownership_manifest"] = next_path.relative_to(
        paths["root"]
    ).as_posix()
    next_active["ownership_manifest_sha256"] = next_hash
    journal = {
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "transition_schema_version": 1,
        "distribution": DISTRIBUTION,
        "candidate_id": active.get("candidate_id"),
        "candidate_root": active.get("candidate_root"),
        "old_manifest": {
            "path": old_relative.as_posix(),
            "sha256": old_hash,
        },
        "new_manifest": {
            "path": next_path.relative_to(paths["root"]).as_posix(),
            "sha256": next_hash,
        },
        "intended_active": next_active,
        "intended_active_sha256": _canonical_sha256(next_active),
    }
    journal_path = _ownership_transition_path(paths)
    journal_relative = journal_path.relative_to(paths["root"])
    _assert_real_directory_chain(paths["root"], ("state",))
    try:
        try:
            _assert_real_regular_file(paths["root"], journal_relative)
        except FileNotFoundError:
            pass
        else:
            raise InstallerError(
                "ownership_transition_invalid",
                "an unresolved ownership transition already exists",
                exit_code=EXIT_VERIFY,
            )
        _atomic_write(journal_path, journal)
        written_hash = _atomic_write(next_path, state)
        if written_hash != next_hash:
            raise InstallerError(
                "ownership_transition_invalid",
                "new ownership manifest hash did not match its journal binding",
                exit_code=EXIT_VERIFY,
            )
        _atomic_write(_active_path(paths), next_active)
        resolution = _resolve_ownership_transition(paths)
        if resolution != "committed":
            raise InstallerError(
                "ownership_transition_invalid",
                "ownership transition did not commit deterministically",
                exit_code=EXIT_VERIFY,
            )
    except Exception:
        try:
            _resolve_ownership_transition(paths)
        except Exception:
            pass
        raise
    return next_active, next_path, state


def _delete_control_file(
    root: Path,
    relative: Path,
    *,
    expected_digest: str | None = None,
) -> None:
    _owned_entry_state(
        root,
        relative.as_posix(),
        expected_kind="file",
        expected_digest=expected_digest,
        delete=True,
    )
    deadline = time.monotonic() + _CONTROL_FILE_CONVERGENCE_TIMEOUT_SECONDS
    expected_name = os.path.normcase(relative.name)
    while True:
        try:
            parent = _assert_real_directory_chain(
                root,
                relative.parts[:-1],
            )
            with os.scandir(parent) as entries:
                present = any(
                    os.path.normcase(entry.name) == expected_name
                    for entry in entries
                )
        except FileNotFoundError:
            present = False
        except OSError as error:
            raise InstallerError(
                "control_file_delete_incomplete",
                "cannot confirm deletion of the exact owned control file",
                exit_code=EXIT_ENVIRONMENT,
                details={
                    "path": str(root / relative),
                    "exception": type(error).__name__,
                },
            ) from error
        if not present:
            return
        if time.monotonic() >= deadline:
            raise InstallerError(
                "control_file_delete_incomplete",
                "exact owned control file remained visible after deletion",
                exit_code=EXIT_ENVIRONMENT,
                details={"path": str(root / relative)},
            )
        time.sleep(_CONTROL_FILE_CONVERGENCE_POLL_SECONDS)


def _transition_relative(value: object, *, field: str) -> Path:
    try:
        return _validate_relative(value, field=field)
    except InstallerError as error:
        raise InstallerError(
            "ownership_transition_invalid",
            f"{field} is not a normalized relative path",
            exit_code=EXIT_VERIFY,
        ) from error


def _transition_manifest_path(
    paths: dict[str, Path],
    relative: Path,
    expected_hash: str,
    *,
    required: bool,
    role: str,
) -> Path | None:
    try:
        path = _assert_real_regular_file(paths["root"], relative)
    except FileNotFoundError:
        if not required:
            return None
        raise InstallerError(
            "ownership_transition_invalid",
            f"{role} ownership manifest is missing",
            exit_code=EXIT_VERIFY,
            details={"manifest": relative.as_posix()},
        )
    if _sha256(path) != expected_hash:
        raise InstallerError(
            "ownership_transition_invalid",
            f"{role} ownership manifest does not match its journal hash",
            exit_code=EXIT_VERIFY,
            details={"manifest": relative.as_posix()},
        )
    return path


def _load_ownership_transition(
    paths: dict[str, Path],
) -> tuple[
    Path,
    str,
    dict[str, Any],
    Path,
    str,
    Path,
    str,
    dict[str, Any],
    dict[str, Any],
] | None:
    journal_relative = _ownership_transition_path(paths).relative_to(paths["root"])
    try:
        journal_path = _assert_real_regular_file(paths["root"], journal_relative)
    except FileNotFoundError:
        return None
    journal_digest = _sha256(journal_path)
    journal = _load_json(journal_path, code="ownership_transition_invalid")
    if journal_path.read_bytes() != _canonical_json(journal):
        raise InstallerError(
            "ownership_transition_invalid",
            "ownership transition journal is not canonical",
            exit_code=EXIT_VERIFY,
        )
    if set(journal) != {
        "fixture_schema_version",
        "transition_schema_version",
        "distribution",
        "candidate_id",
        "candidate_root",
        "old_manifest",
        "new_manifest",
        "intended_active",
        "intended_active_sha256",
    } or (
        journal.get("fixture_schema_version") != FIXTURE_SCHEMA_VERSION
        or journal.get("transition_schema_version") != 1
        or journal.get("distribution") != DISTRIBUTION
        or not isinstance(journal.get("candidate_id"), str)
        or not journal["candidate_id"]
        or not isinstance(journal.get("old_manifest"), dict)
        or not isinstance(journal.get("new_manifest"), dict)
        or set(journal["old_manifest"]) != {"path", "sha256"}
        or set(journal["new_manifest"]) != {"path", "sha256"}
        or not isinstance(journal.get("intended_active"), dict)
        or not isinstance(journal.get("intended_active_sha256"), str)
        or not HASH_PATTERN.fullmatch(journal["intended_active_sha256"])
    ):
        raise InstallerError(
            "ownership_transition_invalid",
            "ownership transition journal structure is invalid",
            exit_code=EXIT_VERIFY,
        )

    candidate_relative = _transition_relative(
        journal.get("candidate_root"),
        field="ownership_transition.candidate_root",
    )
    if (
        candidate_relative.parent != Path("versions")
        or candidate_relative.name != journal["candidate_id"]
    ):
        raise InstallerError(
            "ownership_transition_invalid",
            "ownership transition candidate binding is invalid",
            exit_code=EXIT_VERIFY,
        )

    old_record = journal["old_manifest"]
    new_record = journal["new_manifest"]
    old_relative = _transition_relative(
        old_record.get("path"),
        field="ownership_transition.old_manifest.path",
    )
    new_relative = _transition_relative(
        new_record.get("path"),
        field="ownership_transition.new_manifest.path",
    )
    old_hash = old_record.get("sha256")
    new_hash = new_record.get("sha256")
    if (
        old_relative.parent != Path("state/manifests")
        or new_relative.parent != Path("state/manifests")
        or old_relative == new_relative
        or old_relative.suffix != ".json"
        or not new_relative.name.startswith("uninstall-")
        or new_relative.suffix != ".json"
        or not isinstance(old_hash, str)
        or not HASH_PATTERN.fullmatch(old_hash)
        or not isinstance(new_hash, str)
        or not HASH_PATTERN.fullmatch(new_hash)
    ):
        raise InstallerError(
            "ownership_transition_invalid",
            "ownership transition manifest binding is invalid",
            exit_code=EXIT_VERIFY,
        )

    intended_active = journal["intended_active"]
    if (
        _canonical_sha256(intended_active)
        != journal["intended_active_sha256"]
        or intended_active.get("fixture_schema_version")
        != FIXTURE_SCHEMA_VERSION
        or intended_active.get("distribution") != DISTRIBUTION
        or intended_active.get("candidate_id") != journal["candidate_id"]
        or intended_active.get("candidate_root")
        != candidate_relative.as_posix()
        or intended_active.get("ownership_manifest")
        != new_relative.as_posix()
        or intended_active.get("ownership_manifest_sha256") != new_hash
    ):
        raise InstallerError(
            "ownership_transition_invalid",
            "intended activation does not match the ownership transition",
            exit_code=EXIT_VERIFY,
        )
    old_active = dict(intended_active)
    old_active["ownership_manifest"] = old_relative.as_posix()
    old_active["ownership_manifest_sha256"] = old_hash
    return (
        journal_relative,
        journal_digest,
        journal,
        old_relative,
        old_hash,
        new_relative,
        new_hash,
        old_active,
        intended_active,
    )


def _resolve_ownership_transition(paths: dict[str, Path]) -> str | None:
    loaded = _load_ownership_transition(paths)
    if loaded is None:
        return None
    (
        journal_relative,
        journal_digest,
        _journal,
        old_relative,
        old_hash,
        new_relative,
        new_hash,
        old_active,
        intended_active,
    ) = loaded
    active_relative = _active_path(paths).relative_to(paths["root"])
    try:
        active_path = _assert_real_regular_file(paths["root"], active_relative)
    except FileNotFoundError as error:
        raise InstallerError(
            "ownership_transition_invalid",
            "activation is missing while an ownership transition is unresolved",
            exit_code=EXIT_VERIFY,
        ) from error
    active = _load_json(active_path, code="ownership_transition_invalid")

    if active == old_active:
        _transition_manifest_path(
            paths,
            old_relative,
            old_hash,
            required=True,
            role="old",
        )
        new_path = _transition_manifest_path(
            paths,
            new_relative,
            new_hash,
            required=False,
            role="new",
        )
        if new_path is not None:
            try:
                _delete_control_file(
                    paths["root"],
                    new_relative,
                    expected_digest=new_hash,
                )
            except FileNotFoundError:
                pass
        resolution = "rolled-back"
    elif active == intended_active:
        _transition_manifest_path(
            paths,
            new_relative,
            new_hash,
            required=True,
            role="new",
        )
        old_path = _transition_manifest_path(
            paths,
            old_relative,
            old_hash,
            required=False,
            role="old",
        )
        if old_path is not None:
            try:
                _delete_control_file(
                    paths["root"],
                    old_relative,
                    expected_digest=old_hash,
                )
            except FileNotFoundError:
                pass
        resolution = "committed"
    else:
        raise InstallerError(
            "ownership_transition_invalid",
            "activation matches neither side of the ownership transition",
            exit_code=EXIT_VERIFY,
        )

    _delete_control_file(
        paths["root"],
        journal_relative,
        expected_digest=journal_digest,
    )
    return resolution


def _idempotent_uninstall_result(paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "action": "uninstall",
        "candidate_id": None,
        "removed": [],
        "changed_preserved": [],
        "missing": [],
        "unexpected_preserved": [],
        "shared_preserved": {
            "uv": str(paths["uv_root"]),
            "python": str(paths["uv_python"]),
            "cache": str(paths["uv_cache"]),
        },
        "uninstalled": True,
        "already_absent": True,
    }


def _resume_terminal_cleanup(
    paths: dict[str, Path],
) -> dict[str, Any] | None:
    marker_path = _terminal_cleanup_path(paths)
    marker_relative = marker_path.relative_to(paths["root"])
    try:
        marker_path = _assert_real_regular_file(
            paths["root"],
            marker_relative,
        )
    except FileNotFoundError:
        return None
    marker = _load_json(marker_path, code="terminal_cleanup_invalid")
    if (
        marker.get("fixture_schema_version") != FIXTURE_SCHEMA_VERSION
        or marker.get("distribution") != DISTRIBUTION
        or not isinstance(marker.get("candidate_id"), str)
        or not isinstance(marker.get("removed"), list)
        or not all(isinstance(item, str) for item in marker["removed"])
    ):
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal uninstall cleanup marker is invalid",
            exit_code=EXIT_VERIFY,
        )
    candidate_relative = _validate_relative(
        marker.get("candidate_root"),
        field="terminal_cleanup.candidate_root",
    )
    candidate_root = paths["root"] / candidate_relative
    if not _path_within(candidate_root, paths["versions"]):
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal cleanup candidate root is outside the versions directory",
            exit_code=EXIT_VERIFY,
        )
    manifest_relative = _validate_relative(
        marker.get("ownership_manifest"),
        field="terminal_cleanup.ownership_manifest",
    )
    manifest_path = paths["root"] / manifest_relative
    if not _path_within(manifest_path, paths["manifests"]):
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal cleanup manifest is outside the manifest directory",
            exit_code=EXIT_VERIFY,
        )
    manifest_hash = marker.get("ownership_manifest_sha256")
    if (
        not isinstance(manifest_hash, str)
        or not HASH_PATTERN.fullmatch(manifest_hash)
    ):
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal cleanup manifest hash is invalid",
            exit_code=EXIT_VERIFY,
        )

    active_relative = _active_path(paths).relative_to(paths["root"])
    try:
        active_path = _assert_real_regular_file(paths["root"], active_relative)
    except FileNotFoundError:
        active_path = None
    if active_path is not None:
        active = _load_json(active_path, code="activation_invalid")
        if (
            active.get("candidate_id") != marker["candidate_id"]
            or active.get("candidate_root") != marker["candidate_root"]
            or active.get("ownership_manifest") != marker["ownership_manifest"]
            or active.get("ownership_manifest_sha256") != manifest_hash
        ):
            raise InstallerError(
                "terminal_cleanup_invalid",
                "activation does not match terminal uninstall cleanup",
                exit_code=EXIT_VERIFY,
            )
    manifest_digest: str | None = None
    try:
        manifest_path = _assert_real_regular_file(
            paths["root"],
            manifest_relative,
        )
    except FileNotFoundError:
        manifest_path = None
    if manifest_path is not None:
        manifest_digest = _sha256(manifest_path)
        if manifest_digest != manifest_hash:
            raise InstallerError(
                "terminal_cleanup_invalid",
                "terminal cleanup manifest hash does not match",
                exit_code=EXIT_VERIFY,
            )
        manifest = _load_json(
            manifest_path,
            code="terminal_cleanup_invalid",
        )
        if (
            manifest.get("candidate_id") != marker["candidate_id"]
            or manifest.get("candidate_root") != marker["candidate_root"]
            or _manifest_entries(manifest)
            or manifest.get("uninstall_pending") is not None
        ):
            raise InstallerError(
                "terminal_cleanup_invalid",
                "terminal cleanup manifest is not empty and final",
                exit_code=EXIT_VERIFY,
            )

    if active_path is not None:
        _delete_control_file(paths["root"], active_relative)
    if manifest_path is not None:
        _delete_control_file(
            paths["root"],
            manifest_relative,
            expected_digest=manifest_digest,
        )

    _remove_empty_directories(candidate_root)
    if candidate_root.exists():
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal cleanup candidate root still contains content",
            exit_code=EXIT_VERIFY,
        )
    _delete_control_file(paths["root"], marker_relative)
    _remove_empty_directories(paths["manifests"])
    result = _idempotent_uninstall_result(paths)
    result.update(
        {
            "candidate_id": marker["candidate_id"],
            "removed": list(marker["removed"]),
            "already_absent": False,
            "recovered_terminal_cleanup": True,
        }
    )
    return result


def _uninstall_fixture_unlocked(*, fixture_root_value: str) -> dict[str, Any]:
    fixture_root = _fixture_root(fixture_root_value)
    paths = _fixture_paths(fixture_root)
    _resolve_ownership_transition(paths)
    recovered = _resume_terminal_cleanup(paths)
    if recovered is not None:
        return recovered
    try:
        _assert_real_regular_file(
            paths["root"],
            _active_path(paths).relative_to(paths["root"]),
        )
    except FileNotFoundError:
        _remove_empty_directories(paths["manifests"])
        return _idempotent_uninstall_result(paths)
    active, manifest_path, manifest = _load_active(paths)
    entries = _manifest_entries(manifest)
    candidate_relative = _validate_relative(
        manifest.get("candidate_root"),
        field="candidate_root",
    )
    candidate_root = paths["root"] / candidate_relative
    if not _path_within(candidate_root, paths["versions"]):
        raise InstallerError(
            "ownership_manifest_invalid",
            "candidate root is outside the fixture versions directory",
            exit_code=EXIT_VERIFY,
        )
    if (
        manifest.get("candidate_id") != active.get("candidate_id")
        or manifest.get("candidate_root") != active.get("candidate_root")
    ):
        raise InstallerError(
            "ownership_manifest_invalid",
            "activation and ownership manifest identify different candidates",
            exit_code=EXIT_VERIFY,
        )

    pending = manifest.get("uninstall_pending")
    recovered_removed: list[str] = []
    if pending is not None:
        if not isinstance(pending, str) or pending not in {
            entry["path"] for entry in entries
        }:
            raise InstallerError(
                "ownership_manifest_invalid",
                "uninstall pending entry is not owned by the manifest",
                exit_code=EXIT_VERIFY,
            )
        try:
            _owned_entry_state(candidate_root, pending)
        except FileNotFoundError:
            entries = [entry for entry in entries if entry["path"] != pending]
            recovered_removed.append(pending)
            active, manifest_path, manifest = _persist_ownership_state(
                paths,
                active,
                manifest_path,
                manifest,
                entries,
                pending=None,
            )

    removed: list[str] = list(recovered_removed)
    changed: list[str] = []
    missing: list[str] = []
    expected_paths = {entry["path"] for entry in entries}
    for entry in entries:
        try:
            kind, digest = _owned_entry_state(candidate_root, entry["path"])
        except FileNotFoundError:
            missing.append(entry["path"])
            continue
        except InstallerError:
            changed.append(entry["path"])
            continue
        if kind != entry["kind"] or digest != entry["sha256"]:
            changed.append(entry["path"])

    unexpected: list[str] = []
    try:
        actual_paths, unsafe_paths = _candidate_inventory(candidate_root)
    except InstallerError:
        actual_paths, unsafe_paths = set(), ["<candidate-root>"]
    unexpected.extend(sorted(actual_paths - expected_paths))
    unexpected.extend(
        path for path in unsafe_paths if path not in unexpected
    )
    drift = bool(changed or missing or unexpected)
    result = {
        "action": "uninstall",
        "candidate_id": active["candidate_id"],
        "removed": removed,
        "changed_preserved": changed,
        "missing": missing,
        "unexpected_preserved": unexpected,
        "shared_preserved": {
            "uv": str(paths["uv_root"]),
            "python": str(paths["uv_python"]),
            "cache": str(paths["uv_cache"]),
        },
        "uninstalled": not drift,
    }
    if drift:
        raise InstallerError(
            "uninstall_drift",
            "uninstall preflight preserved changed, missing, or unexpected content",
            exit_code=EXIT_DRIFT,
            details=result,
        )

    remaining = list(entries)
    for entry in entries:
        active, manifest_path, manifest = _persist_ownership_state(
            paths,
            active,
            manifest_path,
            manifest,
            remaining,
            pending=entry["path"],
        )
        try:
            _owned_entry_state(
                candidate_root,
                entry["path"],
                expected_kind=entry["kind"],
                expected_digest=entry["sha256"],
                delete=True,
            )
        except (InstallerError, OSError) as error:
            interrupted = dict(result)
            interrupted["removed"] = list(removed)
            interrupted["uninstalled"] = False
            interrupted["pending"] = entry["path"]
            interrupted["failure_code"] = (
                error.code if isinstance(error, InstallerError) else type(error).__name__
            )
            raise InstallerError(
                "uninstall_interrupted",
                "uninstall stopped safely with residual ownership persisted",
                exit_code=EXIT_ENVIRONMENT,
                details=interrupted,
            ) from error
        removed.append(entry["path"])
        remaining = remaining[1:]
        active, manifest_path, manifest = _persist_ownership_state(
            paths,
            active,
            manifest_path,
            manifest,
            remaining,
            pending=None,
        )

    _remove_empty_directories(candidate_root)
    marker = {
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "distribution": DISTRIBUTION,
        "candidate_id": active["candidate_id"],
        "candidate_root": active["candidate_root"],
        "ownership_manifest": manifest_path.relative_to(
            paths["root"]
        ).as_posix(),
        "ownership_manifest_sha256": active["ownership_manifest_sha256"],
        "removed": removed,
    }
    _atomic_write(_terminal_cleanup_path(paths), marker)
    finalized = _resume_terminal_cleanup(paths)
    if finalized is None:
        raise InstallerError(
            "terminal_cleanup_invalid",
            "terminal uninstall cleanup marker disappeared",
            exit_code=EXIT_VERIFY,
        )
    finalized["recovered_terminal_cleanup"] = False
    return finalized


def uninstall_fixture(*, fixture_root_value: str) -> dict[str, Any]:
    fixture_root = _fixture_root(fixture_root_value)
    with _fixture_operation_lock(fixture_root, "uninstall"):
        return _uninstall_fixture_unlocked(fixture_root_value=str(fixture_root))


_CONSOLE_CHILD_CODE = (
    "import ctypes,importlib.metadata,json,os,sys;"
    "value={'console_window':int(ctypes.windll.kernel32.GetConsoleWindow() or 0),"
    "'package_version':importlib.metadata.version('xcoding-workflow-spike'),"
    "'pid':os.getpid(),'executable':sys.executable};"
    "open(sys.argv[1],'w',encoding='utf-8',newline='\\n').write("
    "json.dumps(value,sort_keys=True,separators=(',',':'))+'\\n')"
)


def _wait_for_json(path: Path, process: subprocess.Popen[Any]) -> dict[str, Any]:
    return_code = process.wait(timeout=30)
    if return_code != 0 or not path.is_file():
        raise InstallerError(
            "console_probe_failed",
            "detached console probe did not write evidence",
            exit_code=EXIT_ENVIRONMENT,
            details={"returncode": return_code, "evidence": str(path)},
        )
    return _load_json(path, code="console_probe_invalid")


def windows_console_oracle(*, fixture_root_value: str) -> dict[str, Any]:
    if os.name != "nt":
        raise InstallerError(
            "console_oracle_unavailable",
            "Windows console oracle is available only on Windows",
            exit_code=EXIT_ENVIRONMENT,
        )
    fixture_root = _fixture_root(fixture_root_value)
    paths = _fixture_paths(fixture_root)
    active, _, _ = _load_active(paths)
    tool_python = (
        paths["root"]
        / _validate_relative(active.get("tool_python"), field="tool_python")
    ).resolve(strict=True)
    environment = _fixture_environment(paths)
    oracle_root = paths["temp"] / f"console-oracle-{uuid.uuid4().hex}"
    oracle_root.mkdir(parents=True)
    console_result = oracle_root / "console-child.json"
    no_console_parent_result = oracle_root / "no-console-parent.json"
    no_console_child_result = oracle_root / "no-console-child.json"
    no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    detached_flags = no_window_flag
    parent_window = int(ctypes.windll.kernel32.GetConsoleWindow() or 0)
    if parent_window == 0:
        raise InstallerError(
            "console_parent_unavailable",
            "current parent has no Windows console handle",
            exit_code=EXIT_ENVIRONMENT,
        )
    try:
        console_child = subprocess.Popen(
            [
                str(tool_python),
                "-I",
                "-B",
                "-c",
                _CONSOLE_CHILD_CODE,
                str(console_result),
            ],
            cwd=paths["root"],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=detached_flags,
            close_fds=True,
        )
        from_console = _wait_for_json(console_result, console_child)

        parent_code = (
            "import ctypes,json,subprocess,sys;"
            "parent={'console_window':int(ctypes.windll.kernel32.GetConsoleWindow() or 0)};"
            "open(sys.argv[1],'w',encoding='utf-8',newline='\\n').write("
            "json.dumps(parent,sort_keys=True,separators=(',',':'))+'\\n');"
            "child=subprocess.Popen([sys.executable,'-I','-B','-c',sys.argv[3],"
            "sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
            "stderr=subprocess.DEVNULL,"
            "creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),"
            "close_fds=True);"
            "raise SystemExit(child.wait(timeout=30))"
        )
        no_console_parent = subprocess.Popen(
            [
                str(tool_python),
                "-I",
                "-B",
                "-c",
                parent_code,
                str(no_console_parent_result),
                str(no_console_child_result),
                _CONSOLE_CHILD_CODE,
            ],
            cwd=paths["root"],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=no_window_flag,
            close_fds=True,
        )
        no_console_parent_returncode = no_console_parent.wait(timeout=30)
        if no_console_parent_returncode != 0:
            raise InstallerError(
                "console_probe_failed",
                "no-console parent probe failed",
                exit_code=EXIT_ENVIRONMENT,
                details={"returncode": no_console_parent_returncode},
            )
        parent_evidence = _load_json(
            no_console_parent_result,
            code="console_probe_invalid",
        )
        no_console = _load_json(
            no_console_child_result,
            code="console_probe_invalid",
        )
    finally:
        shutil.rmtree(oracle_root, ignore_errors=True)

    if (
        from_console.get("console_window") != 0
        or parent_evidence.get("console_window") != 0
        or no_console.get("console_window") != 0
        or from_console.get("package_version") != EXPECTED_VERSION
        or no_console.get("package_version") != EXPECTED_VERSION
    ):
        raise InstallerError(
            "console_oracle_failed",
            "a detached packaged child retained a Windows console handle",
            exit_code=EXIT_ENVIRONMENT,
            details={
                "console_parent_window": parent_window,
                "from_console": from_console,
                "no_console_parent": parent_evidence,
                "from_no_console": no_console,
            },
        )
    return {
        "action": "console-oracle",
        "console_parent_window": parent_window,
        "creationflags": {
            "child": detached_flags,
            "no_console_parent": no_window_flag,
        },
        "from_console": from_console,
        "no_console_parent": parent_evidence,
        "from_no_console": no_console,
        "passed": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "UNSUPPORTED PUBLIC INSTALLATION: isolated local/CI prerelease "
            "fixture only; no registry, public channel, or PATH integration."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install")
    install.add_argument("--wheel", required=True)
    install.add_argument("--wheel-sha256", required=True)
    install.add_argument("--uv-artifact", required=True)
    install.add_argument("--fixture-root", required=True)
    install.add_argument("--toolchain", required=True)
    install.add_argument("--failure-point", choices=sorted(FAILURE_POINTS))
    install.add_argument("--force-candidate", action="store_true")
    uninstall = commands.add_parser("uninstall")
    uninstall.add_argument("--fixture-root", required=True)
    console = commands.add_parser("console-oracle")
    console.add_argument("--fixture-root", required=True)
    return parser


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(_canonical_json(payload).decode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    command = ""
    try:
        arguments = _parser().parse_args(argv)
        command = arguments.command
        if command == "install":
            result = install_fixture(
                wheel_value=arguments.wheel,
                wheel_sha256=arguments.wheel_sha256,
                uv_artifact_value=arguments.uv_artifact,
                fixture_root_value=arguments.fixture_root,
                toolchain_value=arguments.toolchain,
                failure_point=arguments.failure_point,
                force_candidate=arguments.force_candidate,
            )
        elif command == "uninstall":
            result = uninstall_fixture(
                fixture_root_value=arguments.fixture_root,
            )
        else:
            result = windows_console_oracle(
                fixture_root_value=arguments.fixture_root,
            )
    except InstallerError as error:
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "command": command,
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "details": error.details,
                },
            }
        )
        return error.exit_code
    except Exception as error:
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "command": command,
                "error": {
                    "code": "internal_error",
                    "message": "unclassified prerelease bootstrap failure",
                    "details": {"exception": type(error).__name__},
                },
            }
        )
        return EXIT_INTERNAL
    _emit(
        {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "command": command,
            "result": result,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
