"""Owning-Skill path validation and stable regular-file reads."""

from __future__ import annotations

import contextlib
import ctypes
import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import Iterator

from .errors import fail
from .json_codec import MAX_INPUT_BYTES, parse_json_bytes


_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_WINDOWS_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.IGNORECASE)


def validate_slug(value: object, *, field: str, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        fail("identifier_invalid", "validate", f"{field} must be a lowercase slug")
    if prefix is not None and not value.startswith(prefix):
        fail("identifier_invalid", "validate", f"{field} must begin with {prefix!r}")
    return value


def validate_relative_path(value: object, *, field: str) -> str:
    """Validate an unnormalized, NFC, portable POSIX relative path."""
    if not isinstance(value, str) or not value:
        fail("path_unsafe", "validate", f"{field} must be a non-empty string")
    if value != unicodedata.normalize("NFC", value):
        fail("path_unsafe", "validate", f"{field} must use Unicode NFC")
    if "\\" in value or "\x00" in value or value.startswith("/"):
        fail("path_unsafe", "validate", f"{field} must use safe relative POSIX syntax")
    if re.match(r"[A-Za-z]:", value) or value.startswith("//"):
        fail("path_unsafe", "validate", f"{field} must be relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        fail("path_unsafe", "validate", f"{field} contains an unsafe segment")
    if any(any(ord(character) < 32 for character in part) for part in parts):
        fail("path_unsafe", "validate", f"{field} contains a control character")
    if any(
        ":" in part
        or part.endswith((".", " "))
        or _WINDOWS_DEVICE.fullmatch(part) is not None
        for part in parts
    ):
        fail(
            "path_unsafe",
            "validate",
            f"{field} contains a non-portable Windows path segment",
        )
    return value


def validate_path_set(values: list[str], *, field: str) -> tuple[str, ...]:
    exact: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for value in values:
        validate_relative_path(value, field=field)
        previous: str | None = None
        collision = ""
        if value in exact:
            previous, collision = exact[value], "duplicate"
        elif value.casefold() in casefolded:
            previous, collision = casefolded[value.casefold()], "casefold"
        elif unicodedata.normalize("NFC", value) in normalized:
            previous, collision = normalized[unicodedata.normalize("NFC", value)], "nfc"
        if previous is not None:
            fail(
                "path_collision",
                "validate",
                f"{field} contains a {collision} collision",
                collision=collision,
            )
        exact[value] = value
        casefolded[value.casefold()] = value
        normalized[unicodedata.normalize("NFC", value)] = value
    return tuple(values)


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    if os_is_junction and os_is_junction(path):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _assert_components_safe(root: Path, relative: str) -> Path:
    current = root
    for ancestor in reversed((root, *root.parents)):
        if ancestor.exists() and _is_link_or_junction(ancestor):
            fail(
                "path_reparse_forbidden",
                "resolve",
                "Skill root ancestors must not be links or junctions",
            )
    if _is_link_or_junction(current):
        fail("path_reparse_forbidden", "resolve", "Skill root must not be a link or junction")
    try:
        if not stat.S_ISDIR(current.lstat().st_mode):
            fail("path_unsafe", "resolve", "Skill root must be a directory")
    except OSError:
        fail("path_unavailable", "resolve", "Skill root is unavailable")
    directory_identities: list[tuple[Path, tuple[int, int, int]]] = []
    for part in relative.split("/"):
        current /= part
        if _is_link_or_junction(current):
            fail(
                "path_reparse_forbidden",
                "resolve",
                "worker profile paths must not traverse links or junctions",
            )
        if current.is_dir():
            try:
                metadata = current.lstat()
                directory_identities.append(
                    (current, (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns))
                )
            except OSError:
                fail("path_unavailable", "resolve", "worker profile directory is unavailable")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_target = current.resolve(strict=True)
        resolved_target.relative_to(resolved_root)
    except (OSError, ValueError):
        fail("path_containment_failed", "resolve", "worker profile path escaped its owning Skill")
    for directory, identity in directory_identities:
        try:
            metadata = directory.lstat()
        except OSError:
            fail("resource_changed", "resolve", "worker profile directory changed during validation", retryable=True)
        if (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns) != identity:
            fail("resource_changed", "resolve", "worker profile directory changed during validation", retryable=True)
    return current


class PinnedPathError(OSError):
    """A stable, domain-neutral failure from the pinned path primitive."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _pinned_error(code: str, message: str, *, retryable: bool = False) -> PinnedPathError:
    return PinnedPathError(code, message, retryable=retryable)


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return (int(metadata.st_dev), int(metadata.st_ino))


def _component_identity_matches(expected: tuple[int, int], actual: tuple[int, int]) -> bool:
    # CPython's Windows ``st_dev`` is a large synthesized value, while
    # GetFileInformationByHandle exposes the native 32-bit volume serial.
    # The file-index half is stable and maps directly to ``st_ino``; final
    # handle-path containment additionally guards cross-volume traversal.
    return expected[1] == actual[1] if os.name == "nt" else expected == actual


def _component_snapshot(root: Path, relative: str) -> tuple[tuple[int, int], ...]:
    """Capture root/ancestor identities as change detectors before opening."""
    values: list[tuple[int, int]] = []
    current = root
    try:
        values.append(_identity(current.lstat()))
        parts = relative.split("/")
        for index, part in enumerate(parts):
            current /= part
            metadata = current.lstat()
            if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
                raise _pinned_error("path_not_directory", "path ancestor must be a directory")
            if _is_link_or_junction(current):
                raise _pinned_error("path_reparse_forbidden", "path traversal encountered a reparse point")
            values.append(_identity(metadata))
    except PinnedPathError:
        raise
    except OSError as exc:
        raise _pinned_error("path_unavailable", "path component could not be inspected") from exc
    return tuple(values)


@contextlib.contextmanager
def _posix_pinned_fd(
    root: Path,
    relative: str,
    expected_components: tuple[tuple[int, int], ...] | None = None,
) -> Iterator[tuple[int, list[int]]]:
    """Open a path with descriptor-relative, no-follow traversal on POSIX."""
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise _pinned_error("path_unavailable", "safe descriptor-relative traversal is unavailable")
    descriptors: list[int] = []
    try:
        root_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            parent_fd = os.open(root, root_flags)
        except OSError as exc:
            raise _pinned_error("path_unavailable", "trusted root could not be opened") from exc
        descriptors.append(parent_fd)
        root_metadata = os.fstat(parent_fd)
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise _pinned_error("path_unsafe", "trusted root must be a directory")
        if expected_components and _identity(root_metadata) != expected_components[0]:
            raise _pinned_error("resource_changed", "trusted root changed during validation", retryable=True)
        parts = relative.split("/")
        for part in parts[:-1]:
            try:
                child_fd = os.open(part, root_flags, dir_fd=parent_fd)
            except OSError as exc:
                if getattr(exc, "errno", None) in {getattr(os, "ELOOP", 40), getattr(os, "EMLINK", 31)}:
                    raise _pinned_error("path_reparse_forbidden", "path traversal encountered a reparse point") from exc
                raise _pinned_error("path_unavailable", "path ancestor could not be opened") from exc
            descriptors.append(child_fd)
            metadata = os.fstat(child_fd)
            if not stat.S_ISDIR(metadata.st_mode):
                raise _pinned_error("path_not_directory", "path ancestor must be a directory")
            component_index = len(descriptors) - 1
            if expected_components and (
                component_index >= len(expected_components)
                or _identity(metadata) != expected_components[component_index]
            ):
                raise _pinned_error("resource_changed", "path ancestor changed during validation", retryable=True)
            parent_fd = child_fd
        parts = relative.split("/")
        try:
            final_fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent_fd,
            )
        except OSError as exc:
            if getattr(exc, "errno", None) in {getattr(os, "ELOOP", 40), getattr(os, "EMLINK", 31)}:
                raise _pinned_error("path_reparse_forbidden", "file path must not traverse a reparse point") from exc
            raise _pinned_error("path_unavailable", "file could not be opened") from exc
        descriptors.append(final_fd)
        if expected_components and (
            len(expected_components) != len(descriptors)
            or not _component_identity_matches(expected_components[-1], _identity(os.fstat(final_fd)))
        ):
            raise _pinned_error("resource_changed", "file changed during validation", retryable=True)
        yield final_fd, descriptors
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


if os.name == "nt":
    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _GENERIC_READ = 0x80000000
    _GENERIC_DELETE = 0x00010000
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_DISPOSITION_INFO = 4

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", ctypes.c_uint32),
            ("ftCreationTime", ctypes.c_byte * 8),
            ("ftLastAccessTime", ctypes.c_byte * 8),
            ("ftLastWriteTime", ctypes.c_byte * 8),
            ("dwVolumeSerialNumber", ctypes.c_uint32),
            ("nFileSizeHigh", ctypes.c_uint32),
            ("nFileSizeLow", ctypes.c_uint32),
            ("nNumberOfLinks", ctypes.c_uint32),
            ("nFileIndexHigh", ctypes.c_uint32),
            ("nFileIndexLow", ctypes.c_uint32),
        ]

    _KERNEL32.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    _KERNEL32.CreateFileW.restype = ctypes.c_void_p
    _KERNEL32.CloseHandle.argtypes = [ctypes.c_void_p]
    _KERNEL32.CloseHandle.restype = ctypes.c_int
    _KERNEL32.GetFileInformationByHandle.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
    ]
    _KERNEL32.GetFileInformationByHandle.restype = ctypes.c_int
    _KERNEL32.GetFinalPathNameByHandleW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
    ]
    _KERNEL32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    _KERNEL32.SetFileInformationByHandle.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
    ]
    _KERNEL32.SetFileInformationByHandle.restype = ctypes.c_int


def _windows_final_path(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    length = _KERNEL32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not length or length >= len(buffer):
        raise _pinned_error("path_containment_failed", "file handle final path could not be verified")
    value = buffer.value
    if value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.normpath(value))


def _windows_handle_identity(handle: int) -> tuple[int, int]:
    info = _BY_HANDLE_FILE_INFORMATION()
    if not _KERNEL32.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise _pinned_error("path_unavailable", "file identity could not be read")
    return (
        int(info.dwVolumeSerialNumber),
        (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
    )


def _windows_open(path: Path, *, access: int, directory: bool) -> tuple[int, os.stat_result]:
    flags = _FILE_FLAG_OPEN_REPARSE_POINT | (_FILE_FLAG_BACKUP_SEMANTICS if directory else 0)
    handle = _KERNEL32.CreateFileW(
        str(path), access, _FILE_SHARE_READ | _FILE_SHARE_WRITE, None,
        _OPEN_EXISTING, flags, None,
    )
    if handle in {None, _INVALID_HANDLE_VALUE}:
        raise _pinned_error("path_unavailable", "path could not be opened")
    info = _BY_HANDLE_FILE_INFORMATION()
    if not _KERNEL32.GetFileInformationByHandle(handle, ctypes.byref(info)):
        _KERNEL32.CloseHandle(handle)
        raise _pinned_error("path_unavailable", "file identity could not be read")
    if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        _KERNEL32.CloseHandle(handle)
        raise _pinned_error("path_reparse_forbidden", "path must not be a reparse point")
    try:
        metadata = path.stat()
    except OSError as exc:
        _KERNEL32.CloseHandle(handle)
        raise _pinned_error("path_unavailable", "file metadata could not be read") from exc
    return int(handle), metadata


@contextlib.contextmanager
def _windows_pinned_fd(
    root: Path,
    relative: str,
    expected_components: tuple[tuple[int, int], ...] | None = None,
) -> Iterator[tuple[int, list[int]]]:
    """Open a Windows path while holding every ancestor handle open."""
    handles: list[int] = []
    root_handle, root_metadata = _windows_open(root, access=_GENERIC_READ, directory=True)
    handles.append(root_handle)
    try:
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise _pinned_error("path_unsafe", "trusted root must be a directory")
        if expected_components and not _component_identity_matches(
            expected_components[0], _windows_handle_identity(root_handle)
        ):
            raise _pinned_error("resource_changed", "trusted root changed during validation", retryable=True)
        root_final = _windows_final_path(root_handle)
        current = root
        for part in relative.split("/")[:-1]:
            current /= part
            handle, metadata = _windows_open(current, access=_GENERIC_READ, directory=True)
            handles.append(handle)
            if not stat.S_ISDIR(metadata.st_mode):
                raise _pinned_error("path_not_directory", "path ancestor must be a directory")
            component_index = len(handles) - 1
            if expected_components and (
                component_index >= len(expected_components)
                or not _component_identity_matches(
                    expected_components[component_index], _windows_handle_identity(handle)
                )
            ):
                raise _pinned_error("resource_changed", "path ancestor changed during validation", retryable=True)
            final = _windows_final_path(handle)
            try:
                Path(final).relative_to(Path(root_final))
            except ValueError as exc:
                raise _pinned_error("path_containment_failed", "path escaped its trusted root") from exc
        current /= relative.split("/")[-1]
        final_handle, metadata = _windows_open(current, access=_GENERIC_READ, directory=False)
        handles.append(final_handle)
        if expected_components and (
            len(expected_components) != len(handles)
            or not _component_identity_matches(expected_components[-1], _windows_handle_identity(final_handle))
        ):
            raise _pinned_error("resource_changed", "file changed during validation", retryable=True)
        final = _windows_final_path(final_handle)
        try:
            Path(final).relative_to(Path(root_final))
        except ValueError as exc:
            raise _pinned_error("path_containment_failed", "file escaped its trusted root") from exc
        import msvcrt

        descriptor = msvcrt.open_osfhandle(final_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        handles.pop()
        try:
            yield descriptor, handles
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
    finally:
        for handle in reversed(handles):
            _KERNEL32.CloseHandle(handle)


@contextlib.contextmanager
def open_pinned_file(
    root: Path,
    relative: str,
    *,
    expected_components: tuple[tuple[int, int], ...] | None = None,
) -> Iterator[tuple[int, os.stat_result]]:
    """Yield a descriptor for one regular file beneath a pinned root."""
    validate_relative_path(relative, field="resource_path")
    root = Path(root)
    if not root.is_absolute():
        raise _pinned_error("path_unsafe", "trusted root must be absolute")
    if expected_components is None:
        expected_components = _component_snapshot(root, relative)
    manager = (
        _windows_pinned_fd(root, relative, expected_components)
        if os.name == "nt"
        else _posix_pinned_fd(root, relative, expected_components)
    )
    with manager as (descriptor, _owners):
        try:
            metadata = os.fstat(descriptor)
        except OSError as exc:
            raise _pinned_error("path_unavailable", "file identity could not be read") from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise _pinned_error("path_not_regular", "worker resource must be a regular file")
        yield descriptor, metadata


def stable_read_bytes(
    root: Path,
    relative: str,
    *,
    max_bytes: int | None = MAX_INPUT_BYTES,
    expected_identity: tuple[int, int] | None = None,
) -> bytes:
    """Read one contained regular file while root and ancestors remain pinned."""
    validate_relative_path(relative, field="resource_path")
    try:
        expected_components = _component_snapshot(Path(root), relative)
        # Retain the explicit reparse/containment guard as an early rejection
        # (and as a portable diagnostic); descriptor-relative traversal below
        # is still authoritative against replacement races.
        _assert_components_safe(Path(root), relative)
    except PinnedPathError as exc:
        fail(exc.code, "resolve", str(exc), retryable=exc.retryable)
    # A best-effort pathname observation is retained only as a change signal;
    # the descriptor-relative open below is the authoritative read operation.
    probe = Path(root).joinpath(*relative.split("/"))
    try:
        before_path = probe.lstat()
    except OSError:
        before_path = None
    try:
        with open_pinned_file(
            Path(root), relative, expected_components=expected_components
        ) as (descriptor, opened):
            if expected_identity is not None and _identity(opened) != expected_identity:
                raise _pinned_error("resource_changed", "worker resource identity changed", retryable=True)
            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = 65536 if max_bytes is None else min(65536, max_bytes + 1 - total)
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise _pinned_error("resource_limit_exceeded", "worker resource exceeds its byte limit")
            after = os.fstat(descriptor)
    except PinnedPathError as exc:
        fail(exc.code, "resolve", str(exc), retryable=exc.retryable)
    except OSError:
        fail("path_unavailable", "resolve", "worker resource could not be read safely")
    if before_path is not None and (
        _identity(before_path) != _identity(opened)
        or before_path.st_size != opened.st_size
        or before_path.st_mtime_ns != opened.st_mtime_ns
    ):
        fail("resource_changed", "resolve", "worker resource changed during validation", retryable=True)
    if _identity(opened) != _identity(after) or opened.st_size != after.st_size or opened.st_mtime_ns != after.st_mtime_ns:
        fail("resource_changed", "resolve", "worker resource changed during validation", retryable=True)
    return b"".join(chunks)


def pinned_identity(root: Path, relative: str) -> tuple[int, int] | None:
    """Return a regular-file identity from a pinned open, or ``None`` if absent."""
    validate_relative_path(relative, field="resource_path")
    try:
        with open_pinned_file(Path(root), relative) as (_descriptor, metadata):
            return _identity(metadata)
    except PinnedPathError as exc:
        if exc.code == "path_unavailable":
            return None
        raise


def delete_pinned_file(root: Path, relative: str, expected_identity: tuple[int, int]) -> None:
    """Delete the exact regular file identity beneath a pinned root."""
    validate_relative_path(relative, field="resource_path")
    root = Path(root)
    expected_components = _component_snapshot(root, relative)
    if os.name == "nt":
        if not root.is_absolute():
            raise _pinned_error("path_unsafe", "trusted root must be absolute")
        handles: list[int] = []
        parent = root
        try:
            parent_handle, _ = _windows_open(parent, access=_GENERIC_READ, directory=True)
            handles.append(parent_handle)
            if not _component_identity_matches(expected_components[0], _windows_handle_identity(parent_handle)):
                raise _pinned_error("resource_changed", "trusted root changed during validation", retryable=True)
            parts = relative.split("/")
            for part in parts[:-1]:
                parent /= part
                handle, _ = _windows_open(parent, access=_GENERIC_READ, directory=True)
                handles.append(handle)
                index = len(handles) - 1
                if not _component_identity_matches(expected_components[index], _windows_handle_identity(handle)):
                    raise _pinned_error("resource_changed", "path ancestor changed during validation", retryable=True)
            target_handle, metadata = _windows_open(parent / parts[-1], access=_GENERIC_DELETE, directory=False)
            handles.append(target_handle)
            if not _component_identity_matches(expected_components[-1], _windows_handle_identity(target_handle)):
                raise _pinned_error("resource_changed", "file identity changed", retryable=True)
            if _identity(metadata) != expected_identity:
                raise _pinned_error("resource_changed", "file identity changed", retryable=True)
            disposition = ctypes.c_byte(1)
            if not _KERNEL32.SetFileInformationByHandle(
                target_handle,
                _FILE_DISPOSITION_INFO,
                ctypes.byref(disposition),
                ctypes.sizeof(disposition),
            ):
                raise _pinned_error("path_unavailable", "file could not be deleted safely")
        finally:
            for handle in reversed(handles):
                _KERNEL32.CloseHandle(handle)
        return
    try:
        with _posix_pinned_fd(root, relative, expected_components) as (descriptor, descriptors):
            metadata = os.fstat(descriptor)
            if _identity(metadata) != expected_identity:
                raise _pinned_error("resource_changed", "file identity changed", retryable=True)
            parent_fd = descriptors[-2]
            name = relative.split("/")[-1]
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if _identity(current) != expected_identity:
                raise _pinned_error("resource_changed", "file identity changed", retryable=True)
            os.unlink(name, dir_fd=parent_fd)
    except PinnedPathError:
        raise
    except OSError as exc:
        raise _pinned_error("path_unavailable", "file could not be deleted safely") from exc


def load_strict_json_path(root: Path, relative: str) -> dict[str, object]:
    value = parse_json_bytes(stable_read_bytes(root, relative))
    assert isinstance(value, dict)
    return value


def profile_relative_path(profile_id: str) -> str:
    validate_slug(profile_id, field="profile_id")
    return f"assets/workers/{profile_id}/profile.json"


__all__ = [
    "PinnedPathError",
    "delete_pinned_file",
    "load_strict_json_path",
    "open_pinned_file",
    "pinned_identity",
    "profile_relative_path",
    "stable_read_bytes",
    "validate_path_set",
    "validate_relative_path",
    "validate_slug",
]
