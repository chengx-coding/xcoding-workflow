#!/usr/bin/env python3
"""Open the native orchestration-tree picker on this process's main thread."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def choose_file() -> Optional[str]:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            parent=root,
            title="Open orchestration tree",
            filetypes=(("Orchestration trees", "*.xml"), ("XML files", "*.xml")),
        )
        return selected or None
    finally:
        root.destroy()


def main() -> int:
    try:
        selected = choose_file()
    except (ImportError, RuntimeError, OSError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    except Exception as exc:
        # TclError is not available when tkinter itself cannot be imported.
        emit({"ok": False, "error": str(exc)})
        return 2
    emit({"ok": True, "selected": selected is not None, "path": selected or ""})
    return 0


if __name__ == "__main__":
    sys.exit(main())
