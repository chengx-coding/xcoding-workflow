#!/usr/bin/env python3
"""Validate the simplified BCP 47 tags used by XC document contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys


LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an XC document content language tag.")
    parser.add_argument("--language", required=True)
    args = parser.parse_args()
    language = args.language.strip()
    ok = bool(LANGUAGE_TAG.fullmatch(language))
    print(
        json.dumps(
            {
                "ok": ok,
                "content_language": language if ok else "",
                "error": "" if ok else "language must be a valid simplified BCP 47 language tag",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
