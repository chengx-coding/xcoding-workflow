#!/usr/bin/env python3
"""Legacy executable adapter for the required xcoding package CLI."""

from __future__ import annotations

import json
import os
import shutil
import sys


def emit_unavailable() -> int:
    payload = {
        "ok": False,
        "error": {
            "code": "xcoding_unavailable",
            "message": "the xcoding CLI is required",
            "details": {"executable": "xcoding"},
        },
    }
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 2


def main() -> int:
    executable = shutil.which("xcoding")
    if executable is None:
        return emit_unavailable()
    try:
        os.execv(
            executable,
            [executable, "runtime", *sys.argv[1:]],
        )
    except OSError:
        return emit_unavailable()
    raise AssertionError("os.execv returned without replacing the process")


if __name__ == "__main__":
    raise SystemExit(main())
