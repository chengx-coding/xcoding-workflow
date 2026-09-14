"""Versioned host capability statement discovery and validation."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from .errors import DelegationError, fail
from .json_codec import parse_json_bytes
from .model import validate_adapter_statement
from .paths import stable_read_bytes, validate_slug


ADAPTER_FILENAME_SUFFIX = ".json"


def _source_asset_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[3] / "skills" / "xc-delegation" / "assets" / "adapters"
    return candidate if candidate.is_dir() else None


def _installed_asset(adapter_id: str):
    return resources.files("xcoding").joinpath(
        "_bundle",
        "skills",
        "xc-delegation",
        "assets",
        "adapters",
        f"{adapter_id}.json",
    )


def parse_adapter_statement(
    data: bytes,
    adapter_id: str,
) -> dict[str, Any]:
    """Validate canonical statement bytes and their requested identity."""
    validate_slug(adapter_id, field="adapter_id")
    statement = validate_adapter_statement(parse_json_bytes(data))
    if statement["adapter_id"] != adapter_id:
        fail(
            "adapter_id_mismatch",
            "adapter",
            "adapter statement identity does not match the requested adapter",
        )
    return statement


def _load_statement_target(target: Any, adapter_id: str) -> dict[str, Any]:
    try:
        if isinstance(target, Path):
            data = stable_read_bytes(target.parent, target.name)
        else:
            # A non-filesystem Traversable has no descriptor/handle boundary
            # that can pin its ancestors.  Refuse it rather than reintroducing
            # pathname-only reads for installed Bundle resources.
            fail(
                "adapter_statement_unsafe",
                "adapter",
                "adapter statement must be a regular filesystem Bundle resource",
            )
    except DelegationError as exc:
        if exc.code == "path_reparse_forbidden" or exc.code in {"path_not_regular", "path_not_directory"}:
            fail(
                "adapter_statement_unsafe",
                "adapter",
                "adapter statement must be a regular Bundle resource",
            )
        if exc.code == "path_unavailable":
            fail(
                "adapter_unknown",
                "adapter",
                "adapter capability statement is unavailable",
                remediation_category="readiness",
            )
        raise
    except FileNotFoundError:
        fail(
            "adapter_unknown",
            "adapter",
            "adapter capability statement is unavailable",
            remediation_category="readiness",
        )
    except OSError:
        fail(
            "adapter_statement_unavailable",
            "adapter",
            "adapter capability statement could not be read",
            remediation_category="readiness",
        )
    return parse_adapter_statement(data, adapter_id)


def load_adapter_statement(adapter_id: str) -> dict[str, Any]:
    """Load exactly one canonical statement from source or installed Bundle."""
    validate_slug(adapter_id, field="adapter_id")
    source_root = _source_asset_root()
    if source_root is not None:
        data = stable_read_bytes(source_root, f"{adapter_id}.json")
        return parse_adapter_statement(data, adapter_id)
    return _load_statement_target(_installed_asset(adapter_id), adapter_id)


def load_bundle_adapter_statement(
    bundle_root: Any,
    adapter_id: str,
) -> dict[str, Any]:
    """Load a statement from the exact Bundle used by setup or doctor."""
    validate_slug(adapter_id, field="adapter_id")
    target = bundle_root
    for part in (
        "skills",
        "xc-delegation",
        "assets",
        "adapters",
        f"{adapter_id}.json",
    ):
        target = target.joinpath(part)
    return _load_statement_target(target, adapter_id)


__all__ = [
    "ADAPTER_FILENAME_SUFFIX",
    "load_adapter_statement",
    "load_bundle_adapter_statement",
    "parse_adapter_statement",
]
