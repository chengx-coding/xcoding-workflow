"""Compatibility alias for the generated Skill-only runtime core."""

from __future__ import annotations

import sys

from _runtime_compat import core as _core


sys.modules[__name__] = _core
