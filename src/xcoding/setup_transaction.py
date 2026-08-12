"""Transactional project installation for packaged XC workflow assets.

The public setup command is intentionally conservative.  It accepts an
explicit existing project root and an explicit desired host set, keeps its
ownership state inside that project, and fails closed when the root identity,
lock provider, managed bytes, or recovery state cannot be proven.
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Sequence

from .bundle.resources import (
    DISTRIBUTION_NAME,
    inspect_installed_bundle,
    installed_bundle_root,
)


SETUP_SCHEMA_VERSION = 1
STATE_RELATIVE = PurePosixPath(".agents/.xcoding-setup")
HOST_TARGETS: Mapping[str, tuple[PurePosixPath, PurePosixPath]] = {
    "claude-code": (PurePosixPath(".claude/agents"), PurePosixPath(".claude/skills")),
    "codex": (PurePosixPath(".codex/agents"), PurePosixPath(".agents/skills")),
    "opencode": (PurePosixPath(".opencode/agents"), PurePosixPath(".agents/skills")),
    "trae": (PurePosixPath(".trae/agents"), PurePosixPath(".agents/skills")),
}
HOST_ORDER = tuple(HOST_TARGETS)


class SetupTransactionError(RuntimeError):
    """Stable setup failure with machine-readable details."""

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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupTransactionError(
            code,
            "setup state is not valid canonical JSON",
            details={"path": str(path), "exception": type(error).__name__},
        ) from error
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise SetupTransactionError(
            code,
            "setup state is not a canonical JSON object",
            details={"path": str(path)},
        )
    return value


def _is_link_or_reparse(path: Path) -> bool:
    try:
        value = path.lstat()
    except OSError:
        return False
    attributes = getattr(value, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse)


def _safe_relative(value: str, *, field: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
        or path.as_posix() != value
    ):
        raise SetupTransactionError(
            "bundle_path_invalid",
            f"{field} is not a canonical project-relative path",
            details={field: value},
        )
    reserved = {"con", "prn", "aux", "nul"}
    reserved.update(f"com{index}" for index in range(1, 10))
    reserved.update(f"lpt{index}" for index in range(1, 10))
    for part in path.parts:
        stem = part.rstrip(" .").split(".", 1)[0].casefold()
        if (
            part != part.rstrip(" .")
            or stem in reserved
            or any(character in '<>:"|?*' or ord(character) < 32 for character in part)
        ):
            raise SetupTransactionError(
                "bundle_path_invalid",
                f"{field} is not portable to a Windows project path",
                details={field: value},
            )
    return path


def _project_path(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


def _existing_chain(root: Path, relative: PurePosixPath) -> list[Path]:
    current = root
    result = [root]
    for part in relative.parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            break
        result.append(current)
    return result


def _validate_chain(root: Path, relative: PurePosixPath) -> None:
    for index, path in enumerate(_existing_chain(root, relative)):
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise SetupTransactionError(
                "path_identity_changed",
                "cannot inspect a pinned project path",
                details={"path": str(path), "exception": type(error).__name__},
            ) from error
        if _is_link_or_reparse(path):
            raise SetupTransactionError(
                "path_identity_changed",
                "project paths must not contain links or reparse points",
                details={"path": str(path)},
            )
        if index < len(_existing_chain(root, relative)) - 1 and not stat.S_ISDIR(mode):
            raise SetupTransactionError(
                "unmanaged_conflict",
                "a target ancestor is not a directory",
                details={"path": str(path)},
            )


def _resolve_project_root(value: str | os.PathLike[str]) -> Path:
    supplied = Path(value)
    try:
        absolute = supplied.absolute()
        root = absolute.resolve(strict=True)
    except OSError as error:
        raise SetupTransactionError(
            "project_root_unavailable",
            "project root must identify an existing directory",
            details={"project_root": str(supplied), "exception": type(error).__name__},
        ) from error
    if root != absolute or not root.is_dir() or _is_link_or_reparse(absolute):
        raise SetupTransactionError(
            "project_root_unsafe",
            "project root must be a real, non-link directory",
            details={"project_root": str(absolute)},
        )
    _validate_chain(root, PurePosixPath("."))
    return root


@dataclass
class _RootLock:
    root: Path
    identity: tuple[int, ...]
    descriptor: int | None = None
    windows_handle: int | None = None
    mutex_handle: int | None = None
    security_descriptor: int | None = None

    def verify(self) -> None:
        if os.name == "nt":
            handle, identity = _windows_open_root(self.root)
            try:
                if identity != self.identity:
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "project root identity changed while setup held the lock",
                    )
            finally:
                _windows_kernel32().CloseHandle(handle)
        else:
            assert self.descriptor is not None
            current = os.lstat(self.root)
            opened = os.fstat(self.descriptor)
            if (
                _is_link_or_reparse(self.root)
                or not os.path.samestat(current, opened)
                or (opened.st_dev, opened.st_ino) != self.identity
            ):
                raise SetupTransactionError(
                    "path_identity_changed",
                    "project root identity changed while setup held the lock",
                )

    def close(self) -> None:
        if os.name == "nt":
            kernel32 = _windows_kernel32()
            if self.mutex_handle:
                kernel32.ReleaseMutex(self.mutex_handle)
                kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
            if self.windows_handle:
                kernel32.CloseHandle(self.windows_handle)
                self.windows_handle = None
            if self.security_descriptor:
                kernel32.LocalFree(self.security_descriptor)
                self.security_descriptor = None
        elif self.descriptor is not None:
            import fcntl

            with contextlib.suppress(OSError):
                fcntl.flock(self.descriptor, fcntl.LOCK_UN)
            os.close(self.descriptor)
            self.descriptor = None


_KERNEL32: Any = None
_ADVAPI32: Any = None
_NTDLL: Any = None


def _windows_kernel32() -> Any:
    global _KERNEL32
    if _KERNEL32 is None:
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
            ctypes.c_void_p,
        ]
        kernel32.GetFileInformationByHandle.restype = ctypes.c_int
        kernel32.SetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        kernel32.SetFileInformationByHandle.restype = ctypes.c_int
        kernel32.WriteFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        kernel32.WriteFile.restype = ctypes.c_int
        kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
        kernel32.FlushFileBuffers.restype = ctypes.c_int
        kernel32.CreateMutexExW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        kernel32.CreateMutexExW.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        kernel32.ReleaseMutex.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        _KERNEL32 = kernel32
    return _KERNEL32


def _windows_advapi32() -> Any:
    global _ADVAPI32
    if _ADVAPI32 is None:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = ctypes.c_int
        advapi32.GetSecurityInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.GetSecurityInfo.restype = ctypes.c_uint32
        advapi32.GetSecurityDescriptorDacl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_int),
        ]
        advapi32.GetSecurityDescriptorDacl.restype = ctypes.c_int
        advapi32.GetSecurityDescriptorControl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        advapi32.GetSecurityDescriptorControl.restype = ctypes.c_int
        advapi32.GetAclInformation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
        ]
        advapi32.GetAclInformation.restype = ctypes.c_int
        _ADVAPI32 = advapi32
    return _ADVAPI32


def _windows_ntdll() -> Any:
    global _NTDLL
    if _NTDLL is None:
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtCreateFile.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        ntdll.NtCreateFile.restype = ctypes.c_long
        ntdll.NtSetInformationFile.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_WindowsIoStatusBlock),
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
        ]
        ntdll.NtSetInformationFile.restype = ctypes.c_long
        ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        ntdll.RtlNtStatusToDosError.restype = ctypes.c_uint32
        _NTDLL = ntdll
    return _NTDLL


class _WindowsFileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", ctypes.c_uint32),
        ("creation_low", ctypes.c_uint32),
        ("creation_high", ctypes.c_uint32),
        ("access_low", ctypes.c_uint32),
        ("access_high", ctypes.c_uint32),
        ("write_low", ctypes.c_uint32),
        ("write_high", ctypes.c_uint32),
        ("volume_serial", ctypes.c_uint32),
        ("size_high", ctypes.c_uint32),
        ("size_low", ctypes.c_uint32),
        ("links", ctypes.c_uint32),
        ("file_index_high", ctypes.c_uint32),
        ("file_index_low", ctypes.c_uint32),
    ]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint32),
        ("security_descriptor", ctypes.c_void_p),
        ("inherit", ctypes.c_int),
    ]


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [
        ("ace_count", ctypes.c_uint32),
        ("acl_bytes_in_use", ctypes.c_uint32),
        ("acl_bytes_free", ctypes.c_uint32),
    ]


class _WindowsUnicodeString(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint16),
        ("maximum_length", ctypes.c_uint16),
        ("buffer", ctypes.POINTER(ctypes.c_wchar)),
    ]


class _WindowsObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint32),
        ("root_directory", ctypes.c_void_p),
        ("object_name", ctypes.POINTER(_WindowsUnicodeString)),
        ("attributes", ctypes.c_uint32),
        ("security_descriptor", ctypes.c_void_p),
        ("security_quality_of_service", ctypes.c_void_p),
    ]


class _WindowsIoStatusBlock(ctypes.Structure):
    _fields_ = [("status", ctypes.c_void_p), ("information", ctypes.c_size_t)]


class _WindowsFileDispositionInformation(ctypes.Structure):
    _fields_ = [("delete_file", ctypes.c_ubyte)]


def _windows_open_root(root: Path) -> tuple[int, tuple[int, ...]]:
    kernel32 = _windows_kernel32()
    handle = kernel32.CreateFileW(
        str(root),
        0x0001 | 0x0002 | 0x0004 | 0x0080,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "cannot open the project root without following reparse points",
            details={"winerror": ctypes.get_last_error()},
        )
    information = _WindowsFileInformation()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "cannot obtain stable project root identity",
            details={"winerror": error},
        )
    if not information.attributes & 0x10 or information.attributes & 0x400:
        kernel32.CloseHandle(handle)
        raise SetupTransactionError(
            "project_root_unsafe",
            "project root handle is not a real directory",
        )
    return handle, (
        information.volume_serial,
        information.file_index_high,
        information.file_index_low,
    )


def _windows_relative_error(status: int, path: Path) -> OSError:
    code = int(_windows_ntdll().RtlNtStatusToDosError(status))
    if code in {2, 3}:
        return FileNotFoundError(code, ctypes.FormatError(code), str(path))
    if code in {80, 183}:
        return FileExistsError(code, ctypes.FormatError(code), str(path))
    error = ctypes.WinError(code)
    error.filename = str(path)
    return error


def _windows_open_relative(
    parent: int,
    name: str,
    path: Path,
    *,
    directory: bool,
    create: bool = False,
    delete: bool = False,
    delete_on_close: bool = False,
    write: bool = False,
    share: int = 0x1 | 0x2 | 0x4,
) -> int:
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise SetupTransactionError(
            "path_identity_changed",
            "relative Windows setup path is invalid",
            details={"path": str(path)},
        )
    name_buffer = ctypes.create_unicode_buffer(name)
    encoded_length = len(name.encode("utf-16-le"))
    unicode_name = _WindowsUnicodeString(
        encoded_length,
        encoded_length + ctypes.sizeof(ctypes.c_wchar),
        ctypes.cast(name_buffer, ctypes.POINTER(ctypes.c_wchar)),
    )
    attributes = _WindowsObjectAttributes(
        ctypes.sizeof(_WindowsObjectAttributes),
        parent,
        ctypes.pointer(unicode_name),
        0x40 | 0x1000,
        None,
        None,
    )
    handle = ctypes.c_void_p()
    io_status = _WindowsIoStatusBlock()
    access = 0x0080 | 0x00100000
    access |= 0x0001
    if directory:
        access |= 0x0002 | 0x0004
    elif write:
        access |= 0x0002
    if delete:
        access |= 0x00010000
    options = 0x00000020 | 0x00200000
    options |= 0x00000001 if directory else 0x00000040
    if delete_on_close:
        options |= 0x00001000
    status = _windows_ntdll().NtCreateFile(
        ctypes.byref(handle),
        access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        0x80,
        share,
        2 if create else 1,
        options,
        None,
        0,
    )
    if status < 0:
        raise _windows_relative_error(status, path)
    if not handle.value:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "NtCreateFile returned an invalid setup handle",
            details={"path": str(path)},
        )
    information = _WindowsFileInformation()
    if not _windows_kernel32().GetFileInformationByHandle(
        handle,
        ctypes.byref(information),
    ):
        error = ctypes.get_last_error()
        _windows_kernel32().CloseHandle(handle)
        raise SetupTransactionError(
            "path_identity_changed",
            "cannot verify a relative setup handle",
            details={"path": str(path), "winerror": error},
        )
    is_directory = bool(information.attributes & 0x10)
    if is_directory != directory or information.attributes & 0x400:
        _windows_kernel32().CloseHandle(handle)
        raise SetupTransactionError(
            "path_identity_changed",
            "relative setup handle changed kind or became a reparse point",
            details={"path": str(path)},
        )
    return int(handle.value)


@contextlib.contextmanager
def _windows_parent_handle(
    lock: _RootLock,
    relative_parent: Sequence[str],
) -> Iterator[int]:
    assert lock.windows_handle is not None
    current = lock.windows_handle
    opened: list[int] = []
    path = lock.root
    try:
        for part in relative_parent:
            path /= part
            current = _windows_open_relative(
                current,
                part,
                path,
                directory=True,
            )
            opened.append(current)
        yield current
    finally:
        for handle in reversed(opened):
            _windows_kernel32().CloseHandle(handle)


def _windows_rename_relative(
    source_handle: int,
    target_parent: int,
    target_name: str,
    target: Path,
    *,
    replace: bool = True,
) -> None:
    encoded = target_name.encode("utf-16-le")
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    root_offset = 8 if pointer_size == 8 else 4
    length_offset = root_offset + pointer_size
    name_offset = length_offset + 4
    buffer = ctypes.create_string_buffer(name_offset + len(encoded) + 2)
    ctypes.c_uint32.from_buffer(buffer, 0).value = 1 if replace else 0
    if pointer_size == 8:
        ctypes.c_uint64.from_buffer(buffer, root_offset).value = target_parent
    else:
        ctypes.c_uint32.from_buffer(buffer, root_offset).value = target_parent
    ctypes.c_uint32.from_buffer(buffer, length_offset).value = len(encoded)
    ctypes.memmove(ctypes.addressof(buffer) + name_offset, encoded, len(encoded))
    deadline = time.monotonic() + 5.0
    while True:
        io_status = _WindowsIoStatusBlock()
        status = _windows_ntdll().NtSetInformationFile(
            source_handle,
            ctypes.byref(io_status),
            buffer,
            len(buffer),
            10,
        )
        if status >= 0:
            return
        winerror = int(_windows_ntdll().RtlNtStatusToDosError(status))
        if winerror not in {5, 32} or time.monotonic() >= deadline:
            break
        time.sleep(0.002)
    if status < 0:
        raise SetupTransactionError(
            "path_identity_changed",
            "handle-relative target publication failed",
            details={
                "path": str(target),
                "winerror": winerror,
            },
        )


def _windows_handle_identity(handle: int, path: Path) -> list[int]:
    information = _WindowsFileInformation()
    if not _windows_kernel32().GetFileInformationByHandle(
        handle,
        ctypes.byref(information),
    ):
        raise SetupTransactionError(
            "path_identity_changed",
            "cannot obtain stable identity for a setup target",
            details={"path": str(path), "winerror": ctypes.get_last_error()},
        )
    return [
        int(information.volume_serial),
        int(information.file_index_high),
        int(information.file_index_low),
    ]


def _windows_handle_sha256(handle: int, path: Path) -> str:
    digest = hashlib.sha256()
    buffer = ctypes.create_string_buffer(1024 * 1024)
    while True:
        read = ctypes.c_uint32()
        if not _windows_kernel32().ReadFile(
            handle,
            buffer,
            len(buffer),
            ctypes.byref(read),
            None,
        ):
            raise SetupTransactionError(
                "path_identity_changed",
                "cannot read a pinned setup target",
                details={"path": str(path), "winerror": ctypes.get_last_error()},
            )
        if read.value == 0:
            return digest.hexdigest()
        digest.update(buffer.raw[: read.value])


def _windows_delete_handle(handle: int, target: Path) -> None:
    information = _WindowsFileDispositionInformation(1)
    if not _windows_kernel32().SetFileInformationByHandle(
        handle,
        4,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        raise SetupTransactionError(
            "path_identity_changed",
            "handle-relative target deletion failed",
            details={"path": str(target), "winerror": ctypes.get_last_error()},
        )


def _windows_acl_bytes(security_descriptor: int) -> tuple[bytes, bool]:
    advapi32 = _windows_advapi32()
    present = ctypes.c_int()
    defaulted = ctypes.c_int()
    acl = ctypes.c_void_p()
    if not advapi32.GetSecurityDescriptorDacl(
        security_descriptor,
        ctypes.byref(present),
        ctypes.byref(acl),
        ctypes.byref(defaulted),
    ) or not present.value or not acl.value or defaulted.value:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "setup mutex DACL cannot be verified",
            details={"winerror": ctypes.get_last_error()},
        )
    information = _AclSizeInformation()
    if not advapi32.GetAclInformation(
        acl,
        ctypes.byref(information),
        ctypes.sizeof(information),
        2,
    ):
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "setup mutex ACL size cannot be verified",
            details={"winerror": ctypes.get_last_error()},
        )
    control = ctypes.c_uint16()
    revision = ctypes.c_uint32()
    if not advapi32.GetSecurityDescriptorControl(
        security_descriptor,
        ctypes.byref(control),
        ctypes.byref(revision),
    ):
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "setup mutex DACL control cannot be verified",
            details={"winerror": ctypes.get_last_error()},
        )
    return (
        ctypes.string_at(acl, information.acl_bytes_in_use),
        bool(control.value & 0x1000),
    )


def _verify_windows_mutex_security(mutex: int, expected: int) -> None:
    actual = ctypes.c_void_p()
    status = _windows_advapi32().GetSecurityInfo(
        mutex,
        6,
        0x00000004,
        None,
        None,
        None,
        None,
        ctypes.byref(actual),
    )
    if status != 0 or not actual.value:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "cannot query the setup mutex security descriptor",
            details={"winerror": int(status)},
        )
    try:
        actual_acl, actual_protected = _windows_acl_bytes(int(actual.value))
        expected_acl, expected_protected = _windows_acl_bytes(expected)
        if actual_acl != expected_acl or not actual_protected or not expected_protected:
            raise SetupTransactionError(
                "lock_provider_unsupported",
                "setup mutex security does not match the owner-only protected DACL",
            )
    finally:
        _windows_kernel32().LocalFree(actual)


def _acquire_windows_lock(root: Path) -> _RootLock:
    kernel32 = _windows_kernel32()
    root_handle, identity = _windows_open_root(root)
    security = ctypes.c_void_p()
    # Protected DACL: grant the exact mutex-all mask only to the object owner.
    if not _windows_advapi32().ConvertStringSecurityDescriptorToSecurityDescriptorW(
        "D:P(A;;0x001f0001;;;OW)", 1, ctypes.byref(security), None
    ):
        kernel32.CloseHandle(root_handle)
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "cannot construct the setup mutex security descriptor",
            details={"winerror": ctypes.get_last_error()},
        )
    attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), security, 0)
    name = "Global\\XcodingSetup-v1-" + "-".join(f"{part:08x}" for part in identity)
    mutex = kernel32.CreateMutexExW(ctypes.byref(attributes), name, 0, 0x001F0001)
    if not mutex:
        error = ctypes.get_last_error()
        kernel32.LocalFree(security)
        kernel32.CloseHandle(root_handle)
        code = "lock_access_denied" if error == 5 else "lock_name_collision"
        raise SetupTransactionError(
            code,
            "cannot create or open the unique project setup mutex",
            details={"lock_identity": name, "winerror": error},
        )
    try:
        _verify_windows_mutex_security(mutex, int(security.value or 0))
    except Exception:
        kernel32.CloseHandle(mutex)
        kernel32.LocalFree(security)
        kernel32.CloseHandle(root_handle)
        raise
    wait = kernel32.WaitForSingleObject(mutex, 0)
    if wait not in {0, 0x80}:
        kernel32.CloseHandle(mutex)
        kernel32.LocalFree(security)
        kernel32.CloseHandle(root_handle)
        if wait == 0x102:
            raise SetupTransactionError(
                "setup_locked",
                "another setup command holds the project lock",
                details={"lock_identity": name},
            )
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "the setup mutex returned an unsupported wait result",
            details={"wait_result": wait},
        )
    lock = _RootLock(
        root,
        identity,
        windows_handle=root_handle,
        mutex_handle=mutex,
        security_descriptor=int(security.value or 0),
    )
    lock.verify()
    return lock


def _prove_posix_lock(root: Path) -> None:
    program = (
        "import fcntl,os,sys;"
        "fd=os.open(sys.argv[1],os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0));"
        "\ntry:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError:\n raise SystemExit(0)\n"
        "raise SystemExit(9)"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", program, str(root)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "cannot prove cross-process directory lock semantics",
            details={"exception": type(error).__name__},
        ) from error
    if result.returncode != 0:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "filesystem did not prove cross-process directory lock semantics",
            details={"probe_returncode": result.returncode},
        )


def _acquire_posix_lock(root: Path) -> _RootLock:
    try:
        import fcntl

        descriptor = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        current = os.lstat(root)
        if not stat.S_ISDIR(opened.st_mode) or not os.path.samestat(opened, current):
            raise OSError("project root identity mismatch")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(descriptor)
            raise SetupTransactionError(
                "setup_locked",
                "another setup command holds the project lock",
            ) from error
    except SetupTransactionError:
        raise
    except (ImportError, OSError) as error:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "directory-fd locking is unavailable for this filesystem provider",
            details={"exception": type(error).__name__},
        ) from error
    lock = _RootLock(root, (opened.st_dev, opened.st_ino), descriptor=descriptor)
    try:
        _prove_posix_lock(root)
        lock.verify()
    except Exception:
        lock.close()
        raise
    return lock


@contextlib.contextmanager
def project_lock(root: Path) -> Iterator[_RootLock]:
    lock = _acquire_windows_lock(root) if os.name == "nt" else _acquire_posix_lock(root)
    try:
        yield lock
    finally:
        lock.close()


def _validate_hosts(hosts: Sequence[str]) -> tuple[str, ...]:
    if not hosts:
        raise SetupTransactionError(
            "host_required",
            "setup requires at least one explicit --host",
            details={"available": list(HOST_ORDER)},
        )
    unknown = sorted(set(hosts) - set(HOST_TARGETS))
    if unknown:
        raise SetupTransactionError(
            "host_unknown",
            "setup host is not supported by this package",
            details={"unknown": unknown, "available": list(HOST_ORDER)},
        )
    return tuple(host for host in HOST_ORDER if host in set(hosts))


def _desired_files(hosts: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    inspection = inspect_installed_bundle()
    bundle_root = installed_bundle_root()
    desired: dict[str, dict[str, Any]] = {}

    def add(relative: PurePosixPath, source_relative: str, owner: str) -> None:
        key = relative.as_posix()
        data = bundle_root.joinpath(*source_relative.split("/")).read_bytes()
        current = desired.get(key)
        if current is not None:
            if current["data"] != data:
                raise SetupTransactionError(
                    "target_collision",
                    "two selected hosts map different bytes to one target",
                    details={"path": key},
                )
            current["owners"].add(owner)
            return
        desired[key] = {
            "data": data,
            "sha256": _sha256(data),
            "mode": "file",
            "owners": {owner},
            "source": source_relative,
        }

    skills = [record for record in inspection.manifest.resources if record.kind == "skill"]
    for host in hosts:
        agent_root, skill_root = HOST_TARGETS[host]
        for record in skills:
            source_path = _safe_relative(record.bundle_path, field="bundle_path")
            if source_path.parts[0] != "skills":
                raise SetupTransactionError("bundle_path_invalid", "Skill is outside the Bundle Skill partition")
            add(skill_root.joinpath(*source_path.parts[1:]), record.bundle_path, host)
        prefix = f"adapters/{host}/"
        adapters = [
            record
            for record in inspection.manifest.resources
            if record.kind == "host-adapter" and record.adapter_id == host
        ]
        if not adapters:
            raise SetupTransactionError(
                "host_bundle_missing",
                "selected host has no packaged adapter partition",
                details={"host": host},
            )
        for record in adapters:
            suffix = record.bundle_path.removeprefix(prefix)
            if suffix == record.bundle_path:
                raise SetupTransactionError("bundle_path_invalid", "host adapter has an invalid partition path")
            add(agent_root.joinpath(*_safe_relative(suffix, field="adapter_path").parts), record.bundle_path, host)

    folded: dict[str, str] = {}
    for path in sorted(desired):
        collision = path.casefold()
        if collision in folded and folded[collision] != path:
            raise SetupTransactionError(
                "target_collision",
                "desired files collide under case-insensitive path semantics",
                details={"first": folded[collision], "second": path},
            )
        folded[collision] = path
    return desired


def _state_paths(root: Path) -> dict[str, Path]:
    state = _project_path(root, STATE_RELATIVE)
    return {
        "state": state,
        "manifest": state / "manifest.json",
        "journal": state / "journal.json",
        "staging": state / "staging",
        "backup": state / "backup",
    }


def _manifest_files(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    generation = value.get("generation")
    previous = value.get("previous_generation")
    hosts = value.get("hosts")
    if (
        value.get("schema_version") != SETUP_SCHEMA_VERSION
        or value.get("distribution") != DISTRIBUTION_NAME
        or not isinstance(value.get("version"), str)
        or not isinstance(value.get("bundle_manifest_sha256"), str)
        or len(value["bundle_manifest_sha256"]) != 64
        or not isinstance(generation, str)
        or len(generation) != 32
        or any(character not in "0123456789abcdef" for character in generation)
        or (
            previous is not None
            and (
                not isinstance(previous, str)
                or len(previous) != 32
                or any(character not in "0123456789abcdef" for character in previous)
            )
        )
        or not isinstance(hosts, list)
        or hosts != [host for host in HOST_ORDER if host in set(hosts)]
    ):
        raise SetupTransactionError("manifest_invalid", "setup manifest schema is unsupported")
    raw = value.get("files")
    if not isinstance(raw, list):
        raise SetupTransactionError("manifest_invalid", "setup manifest files must be a list")
    files: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise SetupTransactionError("manifest_invalid", "setup manifest has an invalid file entry")
        relative = _safe_relative(item["path"], field="manifest.path").as_posix()
        digest = item.get("sha256")
        owners = item.get("owners")
        if (
            relative in files
            or not isinstance(digest, str)
            or len(digest) != 64
            or not isinstance(owners, list)
            or not owners
            or any(owner not in HOST_TARGETS for owner in owners)
            or owners != [owner for owner in HOST_ORDER if owner in set(owners)]
            or any(owner not in hosts for owner in owners)
            or item.get("mode") != "file"
            or relative == STATE_RELATIVE.as_posix()
            or relative.startswith(STATE_RELATIVE.as_posix() + "/")
        ):
            raise SetupTransactionError("manifest_invalid", "setup manifest file ownership is invalid")
        files[relative] = item
    folded: dict[str, str] = {}
    for relative in files:
        collision = relative.casefold()
        if collision in folded and folded[collision] != relative:
            raise SetupTransactionError(
                "manifest_invalid",
                "setup manifest paths collide under Windows semantics",
            )
        folded[collision] = relative
    return files


def _load_manifest(paths: Mapping[str, Path]) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    if not paths["manifest"].exists():
        return None, {}
    _validate_chain(paths["state"].parents[1], STATE_RELATIVE / "manifest.json")
    manifest = _read_json(paths["manifest"], code="manifest_invalid")
    return manifest, _manifest_files(manifest)


def _validate_idle_state(
    paths: Mapping[str, Path],
    manifest: dict[str, Any] | None,
) -> None:
    state = paths["state"]
    if not state.exists():
        return
    if _is_link_or_reparse(state) or not state.is_dir():
        raise SetupTransactionError("manifest_invalid", "setup state root is not a real directory")
    allowed = {"manifest.json", "staging", "backup"}
    unexpected = sorted(child.name for child in state.iterdir() if child.name not in allowed)
    if unexpected:
        raise SetupTransactionError(
            "manifest_invalid",
            "idle setup state contains an unexpected entry",
            details={"entries": unexpected},
        )
    staging = paths["staging"]
    if staging.exists():
        if _is_link_or_reparse(staging) or not staging.is_dir() or any(staging.iterdir()):
            raise SetupTransactionError(
                "manifest_invalid",
                "idle setup staging must be a real empty directory",
            )
    backup = paths["backup"]
    if backup.exists():
        if _is_link_or_reparse(backup) or not backup.is_dir():
            raise SetupTransactionError("manifest_invalid", "setup backup root is unsafe")
        actual = {child.name for child in backup.iterdir()}
        generation = None if manifest is None else manifest.get("generation")
        expected = set() if generation is None else {generation}
        if actual != expected:
            raise SetupTransactionError(
                "manifest_invalid",
                "idle setup backup inventory does not match the current generation",
                details={"expected": sorted(expected), "actual": sorted(actual)},
            )


def _file_identity(path: Path) -> dict[str, Any]:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or _is_link_or_reparse(path):
        raise SetupTransactionError(
            "managed_content_changed",
            "managed target is no longer a regular non-link file",
            details={"path": str(path)},
        )
    data = path.read_bytes()
    identity = [value.st_dev, value.st_ino]
    if os.name == "nt":
        handle = _windows_kernel32().CreateFileW(
            str(path),
            0x0080 | 0x00100000,
            0x1 | 0x2 | 0x4,
            None,
            3,
            0x00200000,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if not handle or handle == invalid:
            raise SetupTransactionError(
                "path_identity_changed",
                "cannot pin a managed target identity",
                details={"path": str(path), "winerror": ctypes.get_last_error()},
            )
        try:
            identity = _windows_handle_identity(int(handle), path)
        finally:
            _windows_kernel32().CloseHandle(handle)
    return {"sha256": _sha256(data), "size": len(data), "identity": identity}


def _relative_file_identity(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
) -> dict[str, Any] | None:
    """Read one target through the pinned root without following links."""

    target = _project_path(root, relative)
    if os.name == "nt":
        try:
            with _windows_parent_handle(lock, relative.parts[:-1]) as parent:
                handle = _windows_open_relative(
                    parent,
                    relative.name,
                    target,
                    directory=False,
                    share=0,
                )
                try:
                    identity = _windows_handle_identity(handle, target)
                    digest = _windows_handle_sha256(handle, target)
                    if _windows_handle_identity(handle, target) != identity:
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "managed target identity changed during final inventory validation",
                            details={"path": relative.as_posix()},
                        )
                    return {"sha256": digest, "identity": identity}
                finally:
                    _windows_kernel32().CloseHandle(handle)
        except FileNotFoundError:
            return None

    try:
        with _posix_parent_descriptor(lock, relative.parts[:-1]) as parent:
            descriptor = os.open(
                relative.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent,
            )
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "managed target is not a regular file at final inventory validation",
                        details={"path": relative.as_posix()},
                    )
                digest = hashlib.sha256()
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                after = os.fstat(descriptor)
                identity = [before.st_dev, before.st_ino]
                if not os.path.samestat(before, after):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "managed target identity changed during final inventory validation",
                        details={"path": relative.as_posix()},
                    )
                return {"sha256": digest.hexdigest(), "identity": identity}
            finally:
                os.close(descriptor)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SetupTransactionError(
            "path_identity_changed",
            "cannot read a no-follow target during final inventory validation",
            details={"path": relative.as_posix(), "exception": type(error).__name__},
        ) from error


def _preflight(
    root: Path,
    hosts: tuple[str, ...],
    desired: dict[str, dict[str, Any]],
    *,
    allow_journal: bool = False,
) -> dict[str, Any]:
    paths = _state_paths(root)
    if paths["journal"].exists() and not allow_journal:
        raise SetupTransactionError(
            "recovery_required",
            "an interrupted setup journal requires explicit --recover",
        )
    manifest, managed = _load_manifest(paths)
    _validate_idle_state(paths, manifest)
    operations: list[dict[str, Any]] = []
    all_paths = sorted(set(desired) | set(managed))
    for relative_value in all_paths:
        relative = _safe_relative(relative_value, field="target_path")
        _validate_chain(root, relative)
        target = _project_path(root, relative)
        expected = managed.get(relative_value)
        exists = target.exists() or target.is_symlink()
        observed: dict[str, Any] | None = None
        if exists:
            if expected is None:
                raise SetupTransactionError(
                    "unmanaged_conflict",
                    "setup will not overwrite an unmanaged project entry",
                    details={"path": relative_value},
                )
            observed = _file_identity(target)
            if observed["sha256"] != expected["sha256"]:
                raise SetupTransactionError(
                    "managed_content_changed",
                    "managed file bytes differ from the ownership manifest",
                    details={"path": relative_value},
                )
        elif expected is not None:
            raise SetupTransactionError(
                "managed_content_changed",
                "a manifest-owned file is missing",
                details={"path": relative_value},
            )
        target_spec = desired.get(relative_value)
        if target_spec is None:
            action = "remove"
        elif observed is None:
            action = "create"
        elif observed["sha256"] == target_spec["sha256"]:
            action = "unchanged"
        else:
            action = "replace"
        operations.append(
            {
                "path": relative_value,
                "action": action,
                "before": observed,
                "after_sha256": None if target_spec is None else target_spec["sha256"],
            }
        )
    inspection = inspect_installed_bundle()
    return {
        "project_root": str(root),
        "root_identity": None,
        "hosts": list(hosts),
        "source_generation": None if manifest is None else manifest.get("generation"),
        "bundle_manifest_sha256": inspection.manifest_sha256,
        "operations": operations,
        "writes_performed": False,
    }


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _transaction_test_hook(stage: str, details: Mapping[str, Any]) -> None:
    """Fault/race injection seam used only by focused regression tests."""


def _ensure_relative_directory(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
) -> Path:
    if not relative.parts:
        return root
    if os.name == "nt":
        assert lock.windows_handle is not None
        current = lock.windows_handle
        opened: list[int] = []
        path = root
        try:
            for part in relative.parts:
                path /= part
                try:
                    child = _windows_open_relative(
                        current,
                        part,
                        path,
                        directory=True,
                    )
                except FileNotFoundError:
                    try:
                        child = _windows_open_relative(
                            current,
                            part,
                            path,
                            directory=True,
                            create=True,
                        )
                    except FileExistsError:
                        child = _windows_open_relative(
                            current,
                            part,
                            path,
                            directory=True,
                        )
                opened.append(child)
                current = child
            return path
        finally:
            for handle in reversed(opened):
                _windows_kernel32().CloseHandle(handle)

    assert lock.descriptor is not None
    current = os.dup(lock.descriptor)
    opened = [current]
    path = root
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        for part in relative.parts:
            path /= part
            try:
                child = os.open(part, flags, dir_fd=current)
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                    os.fsync(current)
                except FileExistsError:
                    pass
                child = os.open(part, flags, dir_fd=current)
            opened.append(child)
            current = child
        return path
    except OSError as error:
        raise SetupTransactionError(
            "path_identity_changed",
            "cannot create a no-follow setup directory",
            details={"path": str(path), "exception": type(error).__name__},
        ) from error
    finally:
        for descriptor in reversed(opened):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _write_relative_file(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
    data: bytes,
) -> None:
    _ensure_relative_directory(root, lock, PurePosixPath(*relative.parts[:-1]))
    target = _project_path(root, relative)
    if os.name == "nt":
        with _windows_parent_handle(lock, relative.parts[:-1]) as parent:
            handle = _windows_open_relative(
                parent,
                relative.name,
                target,
                directory=False,
                create=True,
                delete=True,
                write=True,
            )
            try:
                offset = 0
                while offset < len(data):
                    chunk = data[offset : offset + 1024 * 1024]
                    buffer = ctypes.create_string_buffer(chunk)
                    written = ctypes.c_uint32()
                    if not _windows_kernel32().WriteFile(
                        handle,
                        buffer,
                        len(chunk),
                        ctypes.byref(written),
                        None,
                    ) or written.value != len(chunk):
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "cannot write an identity-pinned setup file",
                            details={"path": str(target), "winerror": ctypes.get_last_error()},
                        )
                    offset += written.value
                if not _windows_kernel32().FlushFileBuffers(handle):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "cannot durably flush an identity-pinned setup file",
                        details={"path": str(target), "winerror": ctypes.get_last_error()},
                    )
            finally:
                _windows_kernel32().CloseHandle(handle)
        return

    with _posix_parent_descriptor(lock, relative.parts[:-1]) as parent:
        try:
            descriptor = os.open(
                relative.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent,
            )
        except OSError as error:
            raise SetupTransactionError(
                "path_identity_changed",
                "cannot create an identity-pinned setup file",
                details={"path": str(target), "exception": type(error).__name__},
            ) from error
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent)


def _atomic_relative_json(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
    value: object,
) -> None:
    temporary = relative.with_name(f".{relative.name}.{uuid.uuid4().hex}.tmp")
    _write_relative_file(root, lock, temporary, _canonical_json(value))
    _publish_staged(root, lock, temporary, relative)


@contextlib.contextmanager
def _posix_parent_descriptor(
    lock: _RootLock,
    relative_parent: Sequence[str],
) -> Iterator[int]:
    assert lock.descriptor is not None
    current = os.dup(lock.descriptor)
    opened = [current]
    try:
        try:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            for part in relative_parent:
                current = os.open(part, flags, dir_fd=current)
                value = os.fstat(current)
                if not stat.S_ISDIR(value.st_mode):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "relative setup parent is not a directory",
                        details={"part": part},
                    )
                opened.append(current)
        except OSError as error:
            raise SetupTransactionError(
                "path_identity_changed",
                "cannot open a no-follow relative setup parent",
                details={"exception": type(error).__name__},
            ) from error
        yield current
    finally:
        for descriptor in reversed(opened):
            with contextlib.suppress(OSError):
                os.close(descriptor)


def _posix_rename_no_replace(
    source_parent: int,
    source_name: str,
    target_parent: int,
    target_name: str,
    target: Path,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise SetupTransactionError(
            "lock_provider_unsupported",
            "filesystem provider has no atomic no-replace rename",
            details={"path": str(target)},
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        source_parent,
        os.fsencode(source_name),
        target_parent,
        os.fsencode(target_name),
        1,
    ) != 0:
        error = ctypes.get_errno()
        if error in {17, 39}:
            raise FileExistsError(error, os.strerror(error), str(target))
        raise SetupTransactionError(
            "path_identity_changed",
            "atomic no-replace publication failed",
            details={"path": str(target), "errno": error},
        )


def _rename_no_replace(
    root: Path,
    lock: _RootLock,
    source_relative: PurePosixPath,
    target_relative: PurePosixPath,
) -> None:
    source = _project_path(root, source_relative)
    target = _project_path(root, target_relative)
    try:
        if os.name == "nt":
            with _windows_parent_handle(lock, source_relative.parts[:-1]) as source_parent:
                source_handle = _windows_open_relative(
                    source_parent,
                    source_relative.name,
                    source,
                    directory=False,
                    delete=True,
                    write=True,
                )
                try:
                    with _windows_parent_handle(lock, target_relative.parts[:-1]) as target_parent:
                        _windows_rename_relative(
                            source_handle,
                            target_parent,
                            target_relative.name,
                            target,
                            replace=False,
                        )
                finally:
                    _windows_kernel32().CloseHandle(source_handle)
            return
        with _posix_parent_descriptor(lock, source_relative.parts[:-1]) as source_parent:
            with _posix_parent_descriptor(lock, target_relative.parts[:-1]) as target_parent:
                _posix_rename_no_replace(
                    source_parent,
                    source_relative.name,
                    target_parent,
                    target_relative.name,
                    target,
                )
                os.fsync(source_parent)
                if target_parent != source_parent:
                    os.fsync(target_parent)
    except FileExistsError as error:
        raise SetupTransactionError(
            "path_identity_changed",
            "setup will not replace an entry that appeared at the mutation boundary",
            details={"path": target_relative.as_posix()},
        ) from error


def _matches_identity(path: Path, expected: Mapping[str, Any] | None) -> bool:
    if expected is None or not path.exists() or path.is_symlink():
        return False
    try:
        observed = _file_identity(path)
    except (OSError, SetupTransactionError):
        return False
    return (
        observed["sha256"] == expected.get("sha256")
        and observed["identity"] == expected.get("identity")
    )


def _displace_expected(
    root: Path,
    lock: _RootLock,
    target_relative: PurePosixPath,
    displaced_relative: PurePosixPath,
    expected: Mapping[str, Any],
) -> None:
    target = _project_path(root, target_relative)
    displaced = _project_path(root, displaced_relative)
    _ensure_relative_directory(
        root,
        lock,
        PurePosixPath(*displaced_relative.parts[:-1]),
    )
    if displaced.exists() or displaced.is_symlink():
        raise SetupTransactionError(
            "path_identity_changed",
            "transaction displacement path is already occupied",
            details={"path": displaced_relative.as_posix()},
        )
    if os.name == "nt":
        with _windows_parent_handle(lock, target_relative.parts[:-1]) as target_parent:
            target_handle = _windows_open_relative(
                target_parent,
                target_relative.name,
                target,
                directory=False,
                delete=True,
                share=0x1,
            )
            try:
                if _windows_handle_identity(target_handle, target) != expected.get("identity"):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "target identity changed at the mutation boundary",
                        details={"path": target_relative.as_posix()},
                    )
                if _windows_handle_sha256(target_handle, target) != expected.get("sha256"):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "target bytes changed at the mutation boundary",
                        details={"path": target_relative.as_posix()},
                    )
                with _windows_parent_handle(lock, displaced_relative.parts[:-1]) as displaced_parent:
                    _windows_rename_relative(
                        target_handle,
                        displaced_parent,
                        displaced_relative.name,
                        displaced,
                        replace=False,
                    )
            finally:
                _windows_kernel32().CloseHandle(target_handle)
    else:
        _rename_no_replace(root, lock, target_relative, displaced_relative)
        if not _matches_identity(displaced, expected):
            if not target.exists():
                _rename_no_replace(root, lock, displaced_relative, target_relative)
            raise SetupTransactionError(
                "path_identity_changed",
                "target identity changed at the mutation boundary",
                details={"path": target_relative.as_posix()},
            )


def _publish_staged(
    root: Path,
    lock: _RootLock,
    source_relative: PurePosixPath,
    target_relative: PurePosixPath,
    *,
    replace: bool = True,
) -> None:
    source = _project_path(root, source_relative)
    target = _project_path(root, target_relative)
    if os.name == "nt":
        with _windows_parent_handle(lock, source_relative.parts[:-1]) as source_parent:
            source_handle = _windows_open_relative(
                source_parent,
                source_relative.name,
                source,
                directory=False,
                delete=True,
                write=True,
            )
            try:
                with _windows_parent_handle(lock, target_relative.parts[:-1]) as target_parent:
                    _windows_rename_relative(
                        source_handle,
                        target_parent,
                        target_relative.name,
                        target,
                        replace=replace,
                    )
                    if not _windows_kernel32().FlushFileBuffers(source_handle):
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "cannot durably flush a handle-relative publication",
                            details={"path": str(target), "winerror": ctypes.get_last_error()},
                        )
            finally:
                _windows_kernel32().CloseHandle(source_handle)
        return
    with _posix_parent_descriptor(lock, source_relative.parts[:-1]) as source_parent:
        with _posix_parent_descriptor(lock, target_relative.parts[:-1]) as target_parent:
            if replace:
                os.replace(
                    source_relative.name,
                    target_relative.name,
                    src_dir_fd=source_parent,
                    dst_dir_fd=target_parent,
                )
            else:
                try:
                    _posix_rename_no_replace(
                        source_parent,
                        source_relative.name,
                        target_parent,
                        target_relative.name,
                        target,
                    )
                except FileExistsError as error:
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "setup will not replace an entry that appeared at the mutation boundary",
                        details={"path": target_relative.as_posix()},
                    ) from error
            os.fsync(source_parent)
            if target_parent != source_parent:
                os.fsync(target_parent)


def _delete_managed(
    root: Path,
    lock: _RootLock,
    target_relative: PurePosixPath,
) -> None:
    target = _project_path(root, target_relative)
    if os.name == "nt":
        with _windows_parent_handle(lock, target_relative.parts[:-1]) as parent:
            handle = _windows_open_relative(
                parent,
                target_relative.name,
                target,
                directory=False,
                delete=True,
            )
            try:
                _windows_delete_handle(handle, target)
            finally:
                _windows_kernel32().CloseHandle(handle)
        return
    with _posix_parent_descriptor(lock, target_relative.parts[:-1]) as parent:
        os.unlink(target_relative.name, dir_fd=parent)
        os.fsync(parent)


def _manifest_value(
    hosts: tuple[str, ...],
    desired: dict[str, dict[str, Any]],
    *,
    generation: str,
    previous_generation: str | None,
) -> dict[str, Any]:
    inspection = inspect_installed_bundle()
    return {
        "schema_version": SETUP_SCHEMA_VERSION,
        "distribution": DISTRIBUTION_NAME,
        "version": inspection.manifest.xc_version,
        "bundle_manifest_sha256": inspection.manifest_sha256,
        "generation": generation,
        "previous_generation": previous_generation,
        "hosts": list(hosts),
        "files": [
            {
                "path": path,
                "mode": "file",
                "sha256": desired[path]["sha256"],
                "owners": sorted(desired[path]["owners"]),
            }
            for path in sorted(desired)
        ],
    }


def _remove_relative_directory_if_empty(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
) -> bool:
    target = _project_path(root, relative)
    if os.name == "nt":
        with _windows_parent_handle(lock, relative.parts[:-1]) as parent:
            handle = _windows_open_relative(
                parent,
                relative.name,
                target,
                directory=True,
                delete=True,
            )
            try:
                try:
                    _windows_delete_handle(handle, target)
                except SetupTransactionError as error:
                    if error.details.get("winerror") in {145, 5}:
                        return False
                    raise
            finally:
                _windows_kernel32().CloseHandle(handle)
        return True
    with _posix_parent_descriptor(lock, relative.parts[:-1]) as parent:
        try:
            os.rmdir(relative.name, dir_fd=parent)
        except OSError as error:
            if error.errno in {39, 17, 66}:
                return False
            raise
    return True


def _remove_empty_managed_parents(
    root: Path,
    lock: _RootLock,
    relative: PurePosixPath,
) -> None:
    # File ownership does not prove directory provenance.  Leaving an empty
    # host directory is safe; deleting a pre-existing user directory is not.
    return


def _cleanup_staging_tree(
    root: Path,
    lock: _RootLock,
    transaction: str,
    desired_hashes: Mapping[str, str],
    *,
    extra_paths: Sequence[str] = (),
) -> None:
    base = STATE_RELATIVE / "staging" / transaction
    directories: set[PurePosixPath] = {base}
    for relative_value, digest in desired_hashes.items():
        relative = _safe_relative(relative_value, field="journal.desired.path")
        source_relative = base / relative
        source = _project_path(root, source_relative)
        if source.exists() or source.is_symlink():
            if _file_identity(source)["sha256"] != digest:
                raise SetupTransactionError(
                    "journal_invalid",
                    "staging cleanup found bytes outside the transaction plan",
                    details={"path": relative_value},
                )
            _delete_managed(root, lock, source_relative)
        parent = source_relative.parent
        while parent != base.parent:
            directories.add(parent)
            if parent == base:
                break
            parent = parent.parent
    for relative_value in extra_paths:
        relative = _safe_relative(relative_value, field="journal.staging.path")
        source_relative = base / relative
        parent = source_relative.parent
        while parent != base.parent:
            directories.add(parent)
            if parent == base:
                break
            parent = parent.parent
    for directory in sorted(
        directories,
        key=lambda value: (len(value.parts), value.as_posix()),
        reverse=True,
    ):
        path = _project_path(root, directory)
        if not path.exists():
            continue
        if not _remove_relative_directory_if_empty(root, lock, directory):
            raise SetupTransactionError(
                "path_identity_changed",
                "setup staging contains an unexpected entry",
                details={"path": str(path)},
            )


def _delete_backup_generation(
    root: Path,
    lock: _RootLock,
    generation: str,
    *,
    expected_manifest: dict[str, Any] | None,
    allow_partial: bool,
) -> None:
    base = STATE_RELATIVE / "backup" / generation
    base_path = _project_path(root, base)
    manifest_relative = base / "manifest.json"
    manifest_path = _project_path(root, manifest_relative)
    manifest = (
        _read_json(manifest_path, code="journal_invalid")
        if manifest_path.exists()
        else expected_manifest
    )
    files = {} if manifest is None else _manifest_files(manifest)
    directories: set[PurePosixPath] = {base}
    for relative_value, entry in files.items():
        relative = PurePosixPath(relative_value)
        backup_relative = base / relative
        backup_path = _project_path(root, backup_relative)
        if not backup_path.exists():
            if allow_partial:
                continue
            raise SetupTransactionError(
                "journal_invalid",
                "durable rollback generation is missing an owned file",
                details={"path": str(backup_path)},
            )
        if _file_identity(backup_path)["sha256"] != entry["sha256"]:
            raise SetupTransactionError(
                "journal_invalid",
                "durable rollback generation contains changed bytes",
                details={"path": str(backup_path)},
            )
        _delete_managed(root, lock, backup_relative)
        parent = backup_relative.parent
        while parent != base.parent:
            directories.add(parent)
            if parent == base:
                break
            parent = parent.parent
    if manifest_path.exists():
        _delete_managed(root, lock, manifest_relative)
    for directory in sorted(
        directories,
        key=lambda value: (len(value.parts), value.as_posix()),
        reverse=True,
    ):
        path = _project_path(root, directory)
        if not path.exists():
            continue
        if not _remove_relative_directory_if_empty(root, lock, directory):
            raise SetupTransactionError(
                "path_identity_changed",
                "setup backup generation contains an unexpected entry",
                details={"path": str(base_path)},
            )


def _cleanup_generation_directories(
    root: Path,
    lock: _RootLock,
    backup_root: Path,
    *,
    keep: str | None,
    partial_generation: str | None = None,
    partial_manifest: dict[str, Any] | None = None,
) -> None:
    if not backup_root.exists():
        return
    for child in backup_root.iterdir():
        if child.name == keep:
            continue
        if (
            len(child.name) != 32
            or any(character not in "0123456789abcdef" for character in child.name)
            or _is_link_or_reparse(child)
            or not child.is_dir()
        ):
            raise SetupTransactionError(
                "path_identity_changed",
                "setup backup inventory contains an unmanaged entry",
                details={"path": str(child)},
            )
        _delete_backup_generation(
            root,
            lock,
            child.name,
            expected_manifest=(
                partial_manifest if child.name == partial_generation else None
            ),
            allow_partial=child.name == partial_generation,
        )
    _fsync_directory(backup_root)


def _verify_operation_boundary(
    root: Path,
    operation: Mapping[str, Any],
    *,
    after: bool,
) -> None:
    relative = _safe_relative(str(operation["path"]), field="operation.path")
    _validate_chain(root, relative)
    target = _project_path(root, relative)
    if after:
        expected = operation.get("after_sha256")
        if expected is None:
            if target.exists() or target.is_symlink():
                raise SetupTransactionError(
                    "path_identity_changed",
                    "removed target reappeared during the setup transaction",
                    details={"path": relative.as_posix()},
                )
            return
        observed = _file_identity(target)
        expected_identity = operation.get("after_identity")
        if (
            observed["sha256"] != expected
            or (
                expected_identity is not None
                and observed["identity"] != expected_identity
            )
        ):
            raise SetupTransactionError(
                "path_identity_changed",
                "published target bytes differ from the transaction plan",
                details={"path": relative.as_posix()},
            )
        return

    expected = operation.get("before")
    exists = target.exists() or target.is_symlink()
    if expected is None:
        if exists:
            raise SetupTransactionError(
                "path_identity_changed",
                "an entry appeared after setup preflight",
                details={"path": relative.as_posix()},
            )
        return
    if not exists:
        raise SetupTransactionError(
            "path_identity_changed",
            "a managed entry disappeared after setup preflight",
            details={"path": relative.as_posix()},
        )
    observed = _file_identity(target)
    if (
        observed["sha256"] != expected.get("sha256")
        or observed["identity"] != expected.get("identity")
    ):
        raise SetupTransactionError(
            "path_identity_changed",
            "a managed entry identity changed after setup preflight",
            details={"path": relative.as_posix()},
        )


def _final_inventory_expectations(
    plan_operations: Sequence[Mapping[str, Any]],
    journal_operations: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    journal_by_path = {str(operation["path"]): operation for operation in journal_operations}
    expected: dict[str, dict[str, Any] | None] = {}
    for planned in plan_operations:
        path = str(planned["path"])
        action = planned.get("action")
        if action == "remove":
            expected[path] = None
        elif action == "unchanged":
            before = planned.get("before")
            expected[path] = {
                "sha256": planned.get("after_sha256"),
                "identity": None if before is None else before.get("identity"),
            }
        else:
            applied = journal_by_path[path]
            expected[path] = {
                "sha256": applied.get("after_sha256"),
                "identity": applied.get("after_identity"),
            }
    return expected


@contextlib.contextmanager
def _final_inventory_publication_guard(
    root: Path,
    lock: _RootLock,
    expected: Mapping[str, Mapping[str, Any] | None],
) -> Iterator[None]:
    """Validate the inventory and pin Windows targets through publication."""

    lock.verify()
    if os.name == "nt":
        handles: list[int] = []
        try:
            for relative_value in sorted(expected):
                relative = _safe_relative(relative_value, field="operation.path")
                target = _project_path(root, relative)
                try:
                    with _windows_parent_handle(lock, relative.parts[:-1]) as parent:
                        handle = _windows_open_relative(
                            parent,
                            relative.name,
                            target,
                            directory=False,
                            share=0,
                        )
                except FileNotFoundError:
                    handle = None
                except OSError as error:
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "cannot pin a target during final inventory validation",
                        details={
                            "path": relative_value,
                            "exception": type(error).__name__,
                        },
                    ) from error
                planned = expected[relative_value]
                if planned is None:
                    if handle is not None:
                        _windows_kernel32().CloseHandle(handle)
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "removed target reappeared before manifest publication",
                            details={"path": relative_value},
                        )
                    # Reserve the absent name with a delete-on-close file that
                    # denies all sharing.  A racing creator either wins before
                    # FILE_CREATE and fails this transaction closed, or cannot
                    # open/recreate the name until manifest publication ends.
                    try:
                        with _windows_parent_handle(lock, relative.parts[:-1]) as parent:
                            handle = _windows_open_relative(
                                parent,
                                relative.name,
                                target,
                                directory=False,
                                create=True,
                                delete=True,
                                delete_on_close=True,
                                share=0,
                            )
                    except FileExistsError as error:
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "removed target reappeared at the manifest publication boundary",
                            details={"path": relative_value},
                        ) from error
                    except OSError as error:
                        # Provider failures at the tombstone boundary must use
                        # the transaction error path so setup can recover the
                        # durable journal automatically.  FileExistsError is
                        # handled separately above as the expected collision.
                        raise SetupTransactionError(
                            "path_identity_changed",
                            "cannot reserve an absent target during manifest publication",
                            details={
                                "path": relative_value,
                                "platform": sys.platform,
                                "exception": type(error).__name__,
                                "errno": getattr(error, "errno", None),
                                "winerror": getattr(error, "winerror", None),
                            },
                        ) from error
                    handles.append(handle)
                    continue
                if handle is None:
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "target inventory changed before manifest publication",
                        details={"path": relative_value},
                    )
                handles.append(handle)
                if (
                    _windows_handle_identity(handle, target) != planned.get("identity")
                    or _windows_handle_sha256(handle, target) != planned.get("sha256")
                ):
                    raise SetupTransactionError(
                        "path_identity_changed",
                        "target inventory changed before manifest publication",
                        details={"path": relative_value},
                    )
            lock.verify()
            yield
            return
        finally:
            for handle in reversed(handles):
                _windows_kernel32().CloseHandle(handle)

    for relative_value in sorted(expected):
        relative = _safe_relative(relative_value, field="operation.path")
        observed = _relative_file_identity(root, lock, relative)
        planned = expected[relative_value]
        if planned is None:
            if observed is not None:
                raise SetupTransactionError(
                    "path_identity_changed",
                    "removed target reappeared before manifest publication",
                    details={"path": relative_value},
                )
            continue
        if (
            observed is None
            or observed["sha256"] != planned.get("sha256")
            or observed["identity"] != planned.get("identity")
        ):
            raise SetupTransactionError(
                "path_identity_changed",
                "target inventory changed before manifest publication",
                details={"path": relative_value},
            )
    lock.verify()
    yield


def _matches_operation_before(path: Path, operation: Mapping[str, Any]) -> bool:
    expected = operation.get("before")
    if expected is None or not path.exists() or path.is_symlink():
        return False
    try:
        observed = _file_identity(path)
    except (OSError, SetupTransactionError):
        return False
    identities = [expected.get("identity")]
    if operation.get("rollback_identity") is not None:
        identities.append(operation["rollback_identity"])
    return (
        observed["sha256"] == expected.get("sha256")
        and observed["identity"] in identities
    )


def _matches_operation_after(path: Path, operation: Mapping[str, Any]) -> bool:
    expected = operation.get("after_sha256")
    if expected is None or not path.exists() or path.is_symlink():
        return False
    try:
        observed = _file_identity(path)
    except (OSError, SetupTransactionError):
        return False
    return (
        observed["sha256"] == expected
        and observed["identity"] == operation.get("after_identity")
    )


def _apply_transaction(
    root: Path,
    lock: _RootLock,
    hosts: tuple[str, ...],
    desired: dict[str, dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    paths = _state_paths(root)
    _ensure_relative_directory(root, lock, STATE_RELATIVE)
    _ensure_relative_directory(root, lock, STATE_RELATIVE / "staging")
    _ensure_relative_directory(root, lock, STATE_RELATIVE / "backup")
    transaction = uuid.uuid4().hex
    generation = uuid.uuid4().hex
    staging = paths["staging"] / transaction
    backup = paths["backup"] / generation
    staging_relative = STATE_RELATIVE / "staging" / transaction
    backup_relative = STATE_RELATIVE / "backup" / generation
    journal_relative = STATE_RELATIVE / "journal.json"
    manifest_relative = STATE_RELATIVE / "manifest.json"
    old_manifest, managed = _load_manifest(paths)
    target_manifest = _manifest_value(
        hosts,
        desired,
        generation=generation,
        previous_generation=None if old_manifest is None else old_manifest.get("generation"),
    )
    journal = {
        "schema_version": SETUP_SCHEMA_VERSION,
        "transaction": transaction,
        "state": "preparing",
        "source_generation": None if old_manifest is None else old_manifest.get("generation"),
        "target_generation": generation,
        "target_manifest_sha256": _sha256(_canonical_json(target_manifest)),
        "bundle_manifest_sha256": plan["bundle_manifest_sha256"],
        "hosts": list(hosts),
        "desired": [
            {"path": relative, "sha256": desired[relative]["sha256"]}
            for relative in sorted(desired)
        ],
        "source_inventory": [
            {
                "path": operation["path"],
                "sha256": operation["before"]["sha256"],
                "identity": operation["before"]["identity"],
            }
            for operation in plan["operations"]
            if operation.get("before") is not None
        ],
        "operations": [
            {**operation, "status": "pending"}
            for operation in plan["operations"]
            if operation["action"] != "unchanged"
        ],
    }
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("preparing", journal)
    _ensure_relative_directory(root, lock, staging_relative)
    _ensure_relative_directory(root, lock, backup_relative)
    for relative, spec in desired.items():
        _write_relative_file(
            root,
            lock,
            staging_relative / PurePosixPath(relative),
            spec["data"],
        )
    for operation in journal["operations"]:
        relative = PurePosixPath(operation["path"])
        if operation.get("after_sha256") is not None:
            operation["after_identity"] = _file_identity(
                staging.joinpath(*relative.parts)
            )["identity"]
        if operation.get("before") is not None:
            operation["displaced_path"] = (
                PurePosixPath("displaced") / relative
            ).as_posix()
    for relative, entry in managed.items():
        source = _project_path(root, PurePosixPath(relative))
        source_data = source.read_bytes()
        if _sha256(source_data) != entry["sha256"]:
            raise SetupTransactionError("managed_content_changed", "backup bytes changed during preflight")
        _write_relative_file(
            root,
            lock,
            backup_relative / PurePosixPath(relative),
            source_data,
        )
    if old_manifest is not None:
        _write_relative_file(
            root,
            lock,
            backup_relative / "manifest.json",
            _canonical_json(old_manifest),
        )
    journal["state"] = "prepared"
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("prepared", journal)
    journal["state"] = "backup-durable"
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("backup-durable", journal)
    journal["state"] = "applying"
    _atomic_relative_json(root, lock, journal_relative, journal)
    for index, operation in enumerate(journal["operations"]):
        lock.verify()
        relative = PurePosixPath(operation["path"])
        _validate_chain(root, relative)
        operation["status"] = "intent"
        _atomic_relative_json(root, lock, journal_relative, journal)
        _transaction_test_hook("operation-intent", operation)
        _verify_operation_boundary(root, operation, after=False)
        target = _project_path(root, relative)
        _transaction_test_hook("mutation-boundary", operation)
        displaced_relative = None
        if operation.get("before") is not None:
            displaced_relative = staging_relative / PurePosixPath(
                operation["displaced_path"]
            )
            _displace_expected(
                root,
                lock,
                relative,
                displaced_relative,
                operation["before"],
            )
            _transaction_test_hook("target-displaced", operation)
        if operation["action"] == "remove":
            assert displaced_relative is not None
            _delete_managed(root, lock, displaced_relative)
            _fsync_directory(target.parent)
            _remove_empty_managed_parents(root, lock, relative)
        else:
            _ensure_relative_directory(
                root,
                lock,
                PurePosixPath(*relative.parts[:-1]),
            )
            source = staging.joinpath(*relative.parts)
            if _sha256(source.read_bytes()) != operation["after_sha256"]:
                raise SetupTransactionError(
                    "path_identity_changed",
                    "staged setup bytes changed before publication",
                    details={"path": relative.as_posix()},
                )
            if _file_identity(source)["identity"] != operation.get("after_identity"):
                raise SetupTransactionError(
                    "path_identity_changed",
                    "staged setup identity changed before publication",
                    details={"path": relative.as_posix()},
                )
            source_relative = (
                STATE_RELATIVE
                / "staging"
                / transaction
                / relative
            )
            _publish_staged(root, lock, source_relative, relative, replace=False)
            if displaced_relative is not None:
                _delete_managed(root, lock, displaced_relative)
            _fsync_directory(target.parent)
        lock.verify()
        _verify_operation_boundary(root, operation, after=True)
        operation["status"] = "applied"
        operation["index"] = index
        _atomic_relative_json(root, lock, journal_relative, journal)
        _transaction_test_hook("operation-applied", operation)
    final_inventory = _final_inventory_expectations(
        plan["operations"],
        journal["operations"],
    )
    for record in journal["desired"]:
        record["identity"] = final_inventory[record["path"]]["identity"]
    journal["state"] = "manifest-intent"
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("manifest-intent", journal)
    _transaction_test_hook("manifest-publication-boundary", journal)
    with _final_inventory_publication_guard(root, lock, final_inventory):
        _atomic_relative_json(root, lock, manifest_relative, target_manifest)
    _transaction_test_hook("manifest-published", target_manifest)
    journal["state"] = "committed"
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("committed", journal)
    _cleanup_staging_tree(
        root,
        lock,
        transaction,
        {relative: spec["sha256"] for relative, spec in desired.items()},
        extra_paths=[
            operation["displaced_path"]
            for operation in journal["operations"]
            if "displaced_path" in operation
        ],
    )
    _cleanup_generation_directories(
        root,
        lock,
        paths["backup"],
        keep=generation,
    )
    journal["state"] = "cleanup-complete"
    _atomic_relative_json(root, lock, journal_relative, journal)
    _transaction_test_hook("cleanup-complete", journal)
    _delete_managed(root, lock, journal_relative)
    _fsync_directory(paths["state"])
    result = dict(plan)
    result.update({"generation": generation, "writes_performed": True, "committed": True})
    return result


def setup(
    project_root: str | os.PathLike[str],
    hosts: Sequence[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = _resolve_project_root(project_root)
    selected = _validate_hosts(hosts)
    desired = _desired_files(selected)
    with project_lock(root) as lock:
        lock.verify()
        plan = _preflight(root, selected, desired)
        plan["root_identity"] = list(lock.identity)
        plan["lock_identity"] = (
            "Global\\XcodingSetup-v1-" + "-".join(f"{part:08x}" for part in lock.identity)
            if os.name == "nt"
            else {"device": lock.identity[0], "inode": lock.identity[1]}
        )
        if dry_run:
            return plan
        try:
            return _apply_transaction(root, lock, selected, desired, plan)
        except SetupTransactionError as error:
            journal = _state_paths(root)["journal"]
            if not journal.exists():
                raise
            try:
                recovery = recover(root, _lock=lock)
            except Exception as rollback_error:
                raise SetupTransactionError(
                    "rollback_failed",
                    "setup failed and automatic rollback could not close the transaction",
                    details={
                        "original_code": error.code,
                        "original_details": error.details,
                        "rollback_exception": type(rollback_error).__name__,
                        "rollback_code": getattr(rollback_error, "code", None),
                    },
                ) from rollback_error
            if recovery.get("direction") == "complete":
                result = dict(plan)
                result.update(
                    {
                        "generation": recovery["generation"],
                        "writes_performed": True,
                        "committed": True,
                        "recovered": True,
                        "recovery_direction": "complete",
                        "recovered_from_error": error.code,
                    }
                )
                return result
            error.details = {**error.details, "rolled_back": True}
            raise


def recover(
    project_root: str | os.PathLike[str],
    *,
    _lock: _RootLock | None = None,
) -> dict[str, Any]:
    root = _resolve_project_root(project_root)
    paths = _state_paths(root)
    lock_context = project_lock(root) if _lock is None else contextlib.nullcontext(_lock)
    with lock_context as lock:
        if not paths["journal"].exists():
            return {"project_root": str(root), "recovered": False, "writes_performed": False}
        journal = _read_json(paths["journal"], code="journal_invalid")
        transaction = journal.get("transaction")
        target_generation = journal.get("target_generation")
        if not isinstance(transaction, str) or not isinstance(target_generation, str):
            raise SetupTransactionError("journal_invalid", "setup journal identity is invalid")
        if journal.get("bundle_manifest_sha256") != inspect_installed_bundle().manifest_sha256:
            raise SetupTransactionError(
                "journal_invalid",
                "recovery package Bundle differs from the interrupted transaction",
            )
        desired_records = journal.get("desired")
        if not isinstance(desired_records, list):
            raise SetupTransactionError("journal_invalid", "setup journal desired inventory is invalid")
        desired_hashes: dict[str, str] = {}
        for record in desired_records:
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("path"), str)
                or not isinstance(record.get("sha256"), str)
                or len(record["sha256"]) != 64
            ):
                raise SetupTransactionError("journal_invalid", "setup journal desired entry is invalid")
            relative_value = _safe_relative(record["path"], field="journal.desired.path").as_posix()
            if relative_value in desired_hashes:
                raise SetupTransactionError("journal_invalid", "setup journal desired path is duplicated")
            desired_hashes[relative_value] = record["sha256"]
        source_records = journal.get("source_inventory")
        if not isinstance(source_records, list):
            raise SetupTransactionError("journal_invalid", "setup journal source inventory is invalid")
        source_inventory: dict[str, dict[str, Any]] = {}
        for record in source_records:
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("path"), str)
                or not isinstance(record.get("sha256"), str)
                or not isinstance(record.get("identity"), list)
            ):
                raise SetupTransactionError("journal_invalid", "setup journal source entry is invalid")
            relative_value = _safe_relative(
                record["path"],
                field="journal.source_inventory.path",
            ).as_posix()
            if relative_value in source_inventory:
                raise SetupTransactionError("journal_invalid", "setup journal source path is duplicated")
            source_inventory[relative_value] = record
        state = journal.get("state")
        if state not in {
            "preparing",
            "prepared",
            "backup-durable",
            "applying",
            "manifest-intent",
            "committed",
            "cleanup-complete",
        }:
            raise SetupTransactionError("journal_invalid", "setup journal state is invalid")
        manifest = _read_json(paths["manifest"], code="manifest_invalid") if paths["manifest"].exists() else None
        manifest_matches_target = (
            manifest is not None
            and manifest.get("generation") == target_generation
            and _sha256(_canonical_json(manifest)) == journal.get("target_manifest_sha256")
        )
        committed = (
            journal.get("state") in {"committed", "cleanup-complete"}
            or manifest_matches_target
        )
        if committed:
            if not manifest_matches_target:
                raise SetupTransactionError(
                    "recovery_conflict",
                    "committed setup manifest does not match the interrupted transaction",
                )
            expected_inventory: dict[str, dict[str, Any]] = {}
            for record in desired_records:
                identity = record.get("identity")
                if not isinstance(identity, list) or not identity:
                    raise SetupTransactionError(
                        "journal_invalid",
                        "committed setup journal lacks final target identity",
                    )
                expected_inventory[record["path"]] = {
                    "sha256": record["sha256"],
                    "identity": identity,
                }
            with _final_inventory_publication_guard(root, lock, expected_inventory):
                pass
        if not committed and state not in {"preparing", "prepared", "backup-durable"}:
            backup = paths["backup"] / target_generation
            backup_manifest_path = backup / "manifest.json"
            backup_manifest = _read_json(backup_manifest_path, code="journal_invalid") if backup_manifest_path.exists() else None
            source_files = {} if backup_manifest is None else _manifest_files(backup_manifest)
            staging_relative = STATE_RELATIVE / "staging" / transaction
            mutated_paths = {
                str(operation.get("path"))
                for operation in journal.get("operations", [])
                if isinstance(operation, dict)
            }
            unchanged_source = {
                path: expected
                for path, expected in source_inventory.items()
                if path not in mutated_paths
            }
            with _final_inventory_publication_guard(root, lock, unchanged_source):
                pass
            for operation in reversed(journal.get("operations", [])):
                if not isinstance(operation, dict) or not isinstance(operation.get("path"), str):
                    raise SetupTransactionError("journal_invalid", "setup journal operation is invalid")
                relative = _safe_relative(operation["path"], field="journal.path")
                target = _project_path(root, relative)
                before = operation.get("before")
                after = (
                    None
                    if operation.get("after_sha256") is None
                    else {
                        "sha256": operation["after_sha256"],
                        "identity": operation.get("after_identity"),
                    }
                )
                displaced_relative = None
                displaced = None
                if operation.get("displaced_path") is not None:
                    displaced_relative = staging_relative / _safe_relative(
                        operation["displaced_path"],
                        field="journal.displaced_path",
                    )
                    displaced = _project_path(root, displaced_relative)
                if displaced is not None and displaced.exists():
                    if before is None or not _matches_identity(displaced, before):
                        raise SetupTransactionError(
                            "journal_invalid",
                            "displaced recovery bytes do not match the transaction before-state",
                            details={"path": relative.as_posix()},
                        )
                    if not target.exists():
                        _rename_no_replace(root, lock, displaced_relative, relative)
                    elif _matches_operation_after(target, operation):
                        recovery_new = staging_relative / "recovery-new" / relative
                        _displace_expected(root, lock, relative, recovery_new, after)
                        _rename_no_replace(root, lock, displaced_relative, relative)
                        _delete_managed(root, lock, recovery_new)
                    elif _matches_operation_before(target, operation):
                        _delete_managed(root, lock, displaced_relative)
                    else:
                        raise SetupTransactionError(
                            "recovery_conflict",
                            "recovery found target bytes outside both transaction states",
                            details={"path": relative.as_posix()},
                        )
                    lock.verify()
                    continue
                if relative.as_posix() in source_files:
                    if _matches_operation_before(target, operation):
                        continue
                    if target.exists() and not _matches_operation_after(target, operation):
                        raise SetupTransactionError(
                            "recovery_conflict",
                            "recovery found target bytes outside both transaction states",
                            details={"path": relative.as_posix()},
                        )
                    source = backup.joinpath(*relative.parts)
                    _ensure_relative_directory(
                        root,
                        lock,
                        PurePosixPath(*relative.parts[:-1]),
                    )
                    recovery_relative = (
                        STATE_RELATIVE
                        / "staging"
                        / transaction
                        / "recovery"
                        / relative
                    )
                    recovery_source = _project_path(root, recovery_relative)
                    if recovery_source.exists():
                        _delete_managed(root, lock, recovery_relative)
                    source_data = source.read_bytes()
                    _write_relative_file(
                        root,
                        lock,
                        recovery_relative,
                        source_data,
                    )
                    if _sha256(recovery_source.read_bytes()) != source_files[relative.as_posix()]["sha256"]:
                        raise SetupTransactionError(
                            "journal_invalid",
                            "recovery staging bytes differ from the durable backup",
                        )
                    operation["rollback_identity"] = _file_identity(recovery_source)["identity"]
                    _atomic_relative_json(
                        root,
                        lock,
                        STATE_RELATIVE / "journal.json",
                        journal,
                    )
                    if target.exists():
                        recovery_new = staging_relative / "recovery-new" / relative
                        _displace_expected(root, lock, relative, recovery_new, after)
                        _rename_no_replace(root, lock, recovery_relative, relative)
                        _delete_managed(root, lock, recovery_new)
                    else:
                        _rename_no_replace(root, lock, recovery_relative, relative)
                elif target.exists() and operation.get("action") in {"create", "replace"}:
                    if not _matches_operation_after(target, operation):
                        if (
                            operation.get("action") == "create"
                            and operation.get("before") is None
                            and operation.get("status") in {"pending", "intent"}
                        ):
                            # Publication never completed, so this path is a
                            # concurrent unmanaged arrival that rollback must
                            # preserve rather than claim or delete.
                            continue
                        raise SetupTransactionError(
                            "recovery_conflict",
                            "recovery will not delete bytes outside the interrupted plan",
                            details={"path": relative.as_posix()},
                        )
                    recovery_delete = staging_relative / "recovery-delete" / relative
                    _displace_expected(root, lock, relative, recovery_delete, after)
                    _delete_managed(root, lock, recovery_delete)
                    _remove_empty_managed_parents(root, lock, relative)
                lock.verify()
            if backup_manifest is None:
                if paths["manifest"].exists():
                    _delete_managed(root, lock, STATE_RELATIVE / "manifest.json")
            else:
                _atomic_relative_json(
                    root,
                    lock,
                    STATE_RELATIVE / "manifest.json",
                    backup_manifest,
                )
        staging = paths["staging"] / transaction
        if staging.exists():
            cleanup_hashes = dict(desired_hashes)
            for operation in journal.get("operations", []):
                if not isinstance(operation, dict) or not isinstance(operation.get("path"), str):
                    continue
                before = operation.get("before")
                if isinstance(before, dict) and isinstance(before.get("sha256"), str):
                    cleanup_hashes[
                        (PurePosixPath("recovery") / operation["path"]).as_posix()
                    ] = before["sha256"]
                    if isinstance(operation.get("displaced_path"), str):
                        cleanup_hashes[operation["displaced_path"]] = before["sha256"]
                if isinstance(operation.get("after_sha256"), str):
                    for prefix in ("recovery-new", "recovery-delete"):
                        cleanup_hashes[
                            (PurePosixPath(prefix) / operation["path"]).as_posix()
                        ] = operation["after_sha256"]
            _cleanup_staging_tree(
                root,
                lock,
                transaction,
                cleanup_hashes,
                extra_paths=[
                    value
                    for operation in journal.get("operations", [])
                    if isinstance(operation, dict)
                    for value in (
                        operation.get("displaced_path"),
                        (
                            None
                            if not isinstance(operation.get("path"), str)
                            else (PurePosixPath("recovery") / operation["path"]).as_posix()
                        ),
                        (
                            None
                            if not isinstance(operation.get("path"), str)
                            else (PurePosixPath("recovery-new") / operation["path"]).as_posix()
                        ),
                        (
                            None
                            if not isinstance(operation.get("path"), str)
                            else (PurePosixPath("recovery-delete") / operation["path"]).as_posix()
                        ),
                    )
                    if isinstance(value, str)
                ],
            )
        _cleanup_generation_directories(
            root,
            lock,
            paths["backup"],
            keep=target_generation if committed else journal.get("source_generation"),
            partial_generation=None if committed else target_generation,
            partial_manifest=None if committed else manifest,
        )
        if paths["journal"].exists():
            _delete_managed(root, lock, STATE_RELATIVE / "journal.json")
        _fsync_directory(paths["state"])
        return {
            "project_root": str(root),
            "recovered": True,
            "direction": "complete" if committed else "rollback",
            "generation": target_generation if committed else journal.get("source_generation"),
            "committed": committed,
            "writes_performed": True,
        }


def rollback(project_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = _resolve_project_root(project_root)
    paths = _state_paths(root)
    with project_lock(root) as lock:
        if paths["journal"].exists():
            raise SetupTransactionError("recovery_required", "recover the open setup journal before rollback")
        manifest, current_files = _load_manifest(paths)
        if manifest is None:
            raise SetupTransactionError("rollback_unavailable", "no successful setup generation exists")
        generation = manifest.get("generation")
        if not isinstance(generation, str):
            raise SetupTransactionError("manifest_invalid", "current generation is invalid")
        previous_generation = manifest.get("previous_generation")
        if not isinstance(previous_generation, str):
            raise SetupTransactionError(
                "rollback_unavailable",
                "the current setup generation has no previous successful generation",
            )
        backup = paths["backup"] / generation
        previous_path = backup / "manifest.json"
        if not previous_path.exists():
            raise SetupTransactionError(
                "rollback_unavailable",
                "the previous setup generation backup is unavailable",
            )
        previous = _read_json(previous_path, code="rollback_unavailable")
        if previous.get("generation") != previous_generation:
            raise SetupTransactionError(
                "rollback_unavailable",
                "the previous setup generation backup does not match the manifest",
            )
        previous_files = _manifest_files(previous)
        desired: dict[str, dict[str, Any]] = {}
        for relative, entry in previous_files.items():
            data = backup.joinpath(*PurePosixPath(relative).parts).read_bytes()
            if _sha256(data) != entry["sha256"]:
                raise SetupTransactionError("rollback_unavailable", "rollback backup bytes are invalid")
            desired[relative] = {
                "data": data,
                "sha256": entry["sha256"],
                "mode": "file",
                "owners": set(entry["owners"]),
                "source": "rollback",
            }
        hosts = tuple(previous.get("hosts", []))
        plan = _preflight(root, hosts, desired)
        result = _apply_transaction(root, lock, hosts, desired, plan)
        result["rolled_back_from"] = generation
        result["rollback"] = True
        return result


__all__ = [
    "HOST_ORDER",
    "HOST_TARGETS",
    "SETUP_SCHEMA_VERSION",
    "SetupTransactionError",
    "project_lock",
    "recover",
    "rollback",
    "setup",
]
