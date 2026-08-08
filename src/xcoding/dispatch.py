"""Private fixed dispatch for packaged read-only runtime script tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .bundle.resources import installed_bundle_root


_READ_ONLY_OPERATIONS = frozenset({"next", "summary", "show", "snapshot"})
_RUNTIME_SCRIPT = (
    "skills",
    "xc-orchestration-runtime",
    "scripts",
    "orchestration.py",
)


class DispatchRejected(ValueError):
    """A caller requested anything outside the fixed read-only interface."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _bounded_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DispatchRejected(
            f"{field}-required",
            f"{field} must be a non-empty string",
        )
    if "\x00" in value or "\r" in value or "\n" in value:
        raise DispatchRejected(
            f"{field}-invalid",
            f"{field} contains a prohibited control character",
        )
    return value


def _runtime_script() -> Path:
    resource = installed_bundle_root().joinpath(*_RUNTIME_SCRIPT)
    try:
        script = Path(os.fspath(resource))
    except TypeError as error:
        raise DispatchRejected(
            "packaged-layout-unavailable",
            "packaged runtime script is not a physical resource",
        ) from error
    if (
        not script.is_file()
        or script.is_symlink()
        or (
            getattr(script, "is_junction", None) is not None
            and script.is_junction()
        )
    ):
        raise DispatchRejected(
            "packaged-layout-unavailable",
            "packaged runtime script is not a regular physical file",
        )
    return script


def dispatch_read_only(
    operation: str,
    *,
    tree: str | os.PathLike[str],
    node: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Synchronously run one fixed packaged read-only runtime operation."""
    if operation not in _READ_ONLY_OPERATIONS:
        raise DispatchRejected(
            "operation-not-allowed",
            "runtime operation is not in the private read-only allowlist",
        )
    try:
        tree_path = Path(os.fspath(tree))
    except TypeError as error:
        raise DispatchRejected(
            "tree-invalid",
            "tree must be an explicit absolute filesystem path",
        ) from error
    if not tree_path.is_absolute() or "\x00" in str(tree_path):
        raise DispatchRejected(
            "tree-invalid",
            "tree must be an explicit absolute filesystem path",
        )

    arguments = [
        sys.executable,
        str(_runtime_script()),
        operation,
        "--tree",
        str(tree_path),
        "--json",
    ]
    if operation == "show":
        arguments.extend(["--node", _bounded_text(node, field="node")])
    elif node is not None:
        raise DispatchRejected(
            "node-not-allowed",
            "node is accepted only by the fixed show operation",
        )

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        arguments,
        capture_output=True,
        check=False,
        shell=False,
        env=environment,
    )


__all__ = ["DispatchRejected", "dispatch_read_only"]
