"""Installed Bundle resource location and inspection primitives."""

from __future__ import annotations

from typing import Mapping

from .manifest import BundleInspection, inspect_bundle


DISTRIBUTION_NAME = "xcoding-workflow"


def __getattr__(name: str):
    """Serve `xcoding.bundle.resources.metadata` without an eager import.

    The module keeps `importlib.metadata` out of its import graph; a caller that
    reads `metadata`, including a test that patches `metadata.version`, still
    gets the real module object.
    """
    if name == "metadata":
        from importlib import metadata

        globals()["metadata"] = metadata
        return metadata
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def installed_bundle_root():
    """Return the package resource root without extracting or mutating it.

    `importlib.resources` is imported here rather than at module scope because
    importing it eagerly costs interpreter start time, and every `xcoding`
    command pays that cost once per process.
    """
    from importlib import resources

    return resources.files("xcoding").joinpath("_bundle")


def installed_distribution_version() -> str:
    """Read the single package version authority from distribution metadata.

    The attribute is read through the module object so that patching
    `metadata.version` keeps working exactly as it did with a module-scope
    import.
    """
    from importlib import metadata

    return metadata.version(DISTRIBUTION_NAME)


def inspect_installed_bundle(
    *,
    expected_provenance: Mapping[str, str] | None = None,
) -> BundleInspection:
    """Validate the installed Bundle against distribution metadata."""
    return inspect_bundle(
        installed_bundle_root(),
        expected_version=installed_distribution_version(),
        expected_provenance=expected_provenance,
    )


__all__ = [
    "DISTRIBUTION_NAME",
    "inspect_installed_bundle",
    "installed_bundle_root",
    "installed_distribution_version",
]
