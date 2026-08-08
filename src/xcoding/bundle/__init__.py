"""Read-only access to the immutable packaged Bundle."""

from .manifest import (
    BundleInspection,
    BundleManifest,
    BundleValidationError,
    ResourceRecord,
    inspect_bundle,
    parse_manifest,
)
from .resources import (
    inspect_installed_bundle,
    installed_bundle_root,
    installed_distribution_version,
)

__all__ = [
    "BundleInspection",
    "BundleManifest",
    "BundleValidationError",
    "ResourceRecord",
    "inspect_bundle",
    "inspect_installed_bundle",
    "installed_bundle_root",
    "installed_distribution_version",
    "parse_manifest",
]
