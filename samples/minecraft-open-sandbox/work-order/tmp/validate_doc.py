#!/usr/bin/env python3
"""Validate a managed document and emit only its xc-document receipt.

Temporary process helper for work order 20261101-2045-open-sandbox-xc-2.
"""

import argparse
import json
import subprocess
import sys

VALIDATOR = r"C:\Users\Admin\.agents\skills\xc-document\scripts\validate_document.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()

    completed = subprocess.run(
        [sys.executable, VALIDATOR, "--document", args.document, "--expected-kind", args.kind],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        return 2

    receipt = payload["receipt"]
    with open(args.receipt, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(receipt))

    print(
        json.dumps(
            {
                "exit": completed.returncode,
                "ok": payload.get("ok"),
                "errors": payload.get("errors"),
                "receipt": args.receipt,
            }
        )
    )
    return 0 if completed.returncode == 0 and payload.get("ok") and not payload.get("errors") else 1


if __name__ == "__main__":
    sys.exit(main())
