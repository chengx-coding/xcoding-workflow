"""Hatch build hook that stages the Bundle outside the source checkout."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from build_support.bundle import CandidateProvenance, collect_bundle


class CustomBuildHook(BuildHookInterface):
    """Map a caller-owned external Bundle staging tree into the wheel."""

    PLUGIN_NAME = "custom"
    _stage_package: Path | None = None

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        raw_staging_root = os.environ.get("XC_BUNDLE_STAGING_ROOT", "")
        if not raw_staging_root:
            raise RuntimeError(
                "XC_BUNDLE_STAGING_ROOT must name an existing absolute "
                "repository-external disposable directory"
            )
        staging_root = Path(raw_staging_root)
        provenance = CandidateProvenance(
            baseline_revision=os.environ.get("XC_BASELINE_REVISION", ""),
            candidate_tree_sha256=os.environ.get(
                "XC_CANDIDATE_TREE_SHA256",
                "",
            ),
            candidate_source_archive_sha256=os.environ.get(
                "XC_CANDIDATE_SOURCE_ARCHIVE_SHA256",
                "",
            ),
        )
        try:
            bundle_root = collect_bundle(
                Path(self.root).absolute(),
                staging_root,
                provenance,
            )
            self._stage_package = bundle_root.parent
            force_include = build_data.setdefault("force_include", {})
            if not isinstance(force_include, dict):
                raise RuntimeError("Hatch force_include build data must be a mapping")
            force_include[str(bundle_root)] = "xcoding/_bundle"
        except BaseException:
            self._cleanup()
            raise

    def finalize(
        self,
        version: str,
        build_data: dict[str, object],
        artifact_path: str,
    ) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self._stage_package is not None:
            shutil.rmtree(self._stage_package, ignore_errors=True)
            self._stage_package = None
