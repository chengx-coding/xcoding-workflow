"""Read the release version from trusted project metadata (never from a wheel)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


RELEASE_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


def validate_version(value: object) -> str:
    """Require the stable SemVer spelling used by XC release artifacts."""
    if not isinstance(value, str) or RELEASE_VERSION.fullmatch(value) is None:
        raise ValueError("release version must be canonical MAJOR.MINOR.PATCH")
    return value


def parse_project_version(data: bytes) -> str:
    project = tomllib.loads(data.decode("utf-8"))["project"]
    if not isinstance(project, dict):
        raise ValueError("project metadata must be a table")
    if project.get("name") != "xcoding-workflow":
        raise ValueError("project name must be xcoding-workflow")
    return validate_version(project.get("version"))


def read_project_version(root: Path) -> str:
    return parse_project_version((root / "pyproject.toml").read_bytes())


def wheel_filename(version: str) -> str:
    return f"xcoding_workflow-{validate_version(version)}-py3-none-any.whl"


def dist_info(version: str) -> str:
    return f"xcoding_workflow-{validate_version(version)}.dist-info"
