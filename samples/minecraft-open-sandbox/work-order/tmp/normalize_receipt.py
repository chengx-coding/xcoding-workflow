"""Run xc-document and emit a receipt normalized to one node's declared selectors."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

VALIDATOR = Path(r"C:\Users\Admin\.agents\skills\xc-document\scripts\validate_document.py")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--drop-fact", action="append", default=[])
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args()

    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--document", args.document, "--expected-kind", args.kind],
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if completed.returncode != 0 or not payload.get("ok"):
        print(json.dumps(payload, indent=2))
        return 1
    receipt = payload["receipt"]
    receipt["subject"] = args.subject
    for fact in args.drop_fact:
        receipt["facts"].pop(fact, None)
    Path(args.receipt_out).write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "receipt": receipt}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
