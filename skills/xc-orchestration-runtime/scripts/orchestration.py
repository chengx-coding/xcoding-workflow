#!/usr/bin/env python3
"""Legacy CLI adapter for the generated runtime application service."""

from __future__ import annotations

import sys
from pathlib import Path

from _runtime_compat import application as _application


_application.configure_default_template(
    Path(__file__).resolve().parents[1]
    / "assets"
    / "minimal-template.xml"
)

if __name__ == "__main__":
    raise SystemExit(_application.main())

sys.modules[__name__] = _application
