"""Shared support layer for the xcoding-workflow test suite.

Import order matters. `paths` inserts the repository root, `tests/` and `src/`
into `sys.path` so that a test module works whether it is loaded by
`unittest` discovery or by the tier runner. Importing `tests.support.paths`
also makes `support.*` and `tests.support.*` importable, because `tests/` is on
the path once `paths` has run.
"""

from __future__ import annotations
