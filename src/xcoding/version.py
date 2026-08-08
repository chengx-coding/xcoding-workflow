"""Version reporting backed by installed distribution and Bundle metadata."""

from __future__ import annotations

import platform
import sys
from typing import Any

from .bundle.resources import inspect_installed_bundle


def version_report() -> dict[str, Any]:
    """Return the validated package, Bundle, Python, and runtime schema versions."""
    inspection = inspect_installed_bundle()
    manifest = inspection.manifest
    return {
        "xc_version": manifest.xc_version,
        "bundle_schema_version": manifest.bundle_schema_version,
        "bundle_manifest_sha256": inspection.manifest_sha256,
        "python_requires": manifest.python_requires,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
            "base_executable": getattr(sys, "_base_executable", sys.executable),
        },
        "runtime_tree_schema": manifest.runtime_tree_schema,
    }


__all__ = ["version_report"]
