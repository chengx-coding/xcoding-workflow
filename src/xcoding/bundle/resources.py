"""Installed Bundle resource location and inspection primitives."""

from __future__ import annotations

from importlib import metadata, resources
from typing import Mapping

from .manifest import BundleInspection, inspect_bundle


DISTRIBUTION_NAME = "xcoding-workflow"


def installed_bundle_root():
    """Return the package resource root without extracting or mutating it."""
    return resources.files("xcoding").joinpath("_bundle")


def installed_distribution_version() -> str:
    """Read the single package version authority from distribution metadata."""
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
