#!/usr/bin/env python3
"""Real-browser acceptance evidence for Cubewood.

Three layers, all standard library only:

1. The seed page check (`tools/page_check.py`) is executed unchanged.
2. The in-page self-test (`index.html?selftest=1`) is driven in headless Chrome and its
   machine-readable result block is parsed. It covers DOM clicks, real pointer mining and
   right-click placement, real keyboard movement, before/after pulses, quest rewards and save
   payload parsing.
3. Save persistence is proven across two separate browser launches that share one profile, and
   deterministic scene screenshots are captured with pixel checks that paired states differ.

Usage:

    python tools/browser_check.py --out <evidence-dir>
    python tools/browser_check.py --out <dir> --no-screenshots
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import page_check  # noqa: E402  (shared Chrome discovery and PNG reader)

SELFTEST_RE = re.compile(r'<pre id="selftest-results"[^>]*>(.*?)</pre>', re.S)
SCENES = ["welcome", "day", "night", "backdrop", "zoom1", "zoom2", "cave", "inventory", "crafting", "guide"]


class BrowserCheckError(RuntimeError):
    pass


def run_chrome(chrome: Path, arguments: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    command = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
    ] + arguments
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    return completed


def parse_selftest(output: str) -> dict:
    match = SELFTEST_RE.search(output)
    if not match:
        raise BrowserCheckError("no selftest result block in the DOM dump")
    text = html.unescape(match.group(1)).strip()
    if not text:
        raise BrowserCheckError("selftest result block is empty")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise BrowserCheckError(f"selftest result is not JSON: {error}") from error
    if not isinstance(result, dict) or "steps" not in result:
        raise BrowserCheckError("selftest result has an unexpected shape")
    return result


def run_selftest(chrome: Path, page: Path, mode: str, window: str, profile: Path | None, budget: int = 25000) -> dict:
    arguments = ["--window-size=" + window.replace("x", ","), "--virtual-time-budget=" + str(budget), "--dump-dom"]
    if profile is not None:
        arguments.append("--user-data-dir=" + str(profile))
    url = page.as_uri() + "?selftest=" + mode
    completed = run_chrome(chrome, arguments + [url])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise BrowserCheckError("chrome failed for selftest " + mode + (": " + detail[-1] if detail else ""))
    result = parse_selftest(completed.stdout)
    failed = [step for step in result.get("steps", []) if not step.get("ok")]
    if result.get("errors"):
        raise BrowserCheckError("page reported errors: " + "; ".join(result["errors"]))
    if failed:
        summary = "; ".join(f"{step.get('name')}: {step.get('error')}" for step in failed)
        raise BrowserCheckError("selftest " + mode + " failed: " + summary)
    if not result.get("ok"):
        raise BrowserCheckError("selftest " + mode + " did not report ok")
    return result


def capture_scene(
    chrome: Path, page: Path, scene: str, target: Path, window: str, budget: int = 4500, extra: list[str] | None = None
) -> dict:
    url = page.as_uri() + "?scene=" + scene
    arguments = list(extra or []) + [
        "--window-size=" + window.replace("x", ","),
        "--virtual-time-budget=" + str(budget),
        "--screenshot=" + str(target),
        url,
    ]
    completed = run_chrome(chrome, arguments)
    if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise BrowserCheckError("screenshot failed for scene " + scene + (": " + detail[-1] if detail else ""))
    return image_stats(target)


def image_stats(path: Path) -> dict:
    width, height, channels, rows = page_check.read_png(path)
    buckets = set()
    brightness = 0.0
    count = 0
    for y in range(4, height, 8):
        row = rows[y]
        for x in range(4, width, 8):
            index = x * channels
            red, green, blue = row[index], row[index + 1], row[index + 2]
            buckets.add((red >> 4, green >> 4, blue >> 4))
            brightness += red * 0.299 + green * 0.587 + blue * 0.114
            count += 1
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "buckets": len(buckets),
        "brightness": round(brightness / max(1, count), 2),
    }


def diff_ratio(first: Path, second: Path, step: int = 6, threshold: int = 22) -> float:
    width_a, height_a, channels_a, rows_a = page_check.read_png(first)
    width_b, height_b, channels_b, rows_b = page_check.read_png(second)
    if (width_a, height_a) != (width_b, height_b):
        return 1.0
    changed = 0
    total = 0
    for y in range(2, height_a, step):
        row_a = rows_a[y]
        row_b = rows_b[y]
        for x in range(2, min(width_a, width_b), step):
            index_a = x * channels_a
            index_b = x * channels_b
            if (
                abs(row_a[index_a] - row_b[index_b]) > threshold
                or abs(row_a[index_a + 1] - row_b[index_b + 1]) > threshold
                or abs(row_a[index_a + 2] - row_b[index_b + 2]) > threshold
            ):
                changed += 1
            total += 1
    return round(changed / max(1, total), 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default=str(Path(__file__).resolve().parent.parent / "index.html"))
    parser.add_argument("--out", default="browser-evidence", help="directory for screenshots and summary.json")
    parser.add_argument("--chrome", default="")
    parser.add_argument("--window", default="1280x800")
    parser.add_argument("--no-screenshots", action="store_true")
    parser.add_argument("--skip-persistence", action="store_true")
    arguments = parser.parse_args()

    page = Path(arguments.page).resolve()
    out_dir = Path(arguments.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = out_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {"ok": False, "page": str(page), "checks": {}, "pairs": {}}
    try:
        if not page.is_file():
            raise BrowserCheckError("page not found: " + str(page))
        chrome = page_check.find_chrome(arguments.chrome or None)

        # 1. The untouched seed page check.
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "page_check.py"), "--page", str(page)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        seed = json.loads(completed.stdout)
        summary["checks"]["page_check"] = seed
        if completed.returncode != 0 or not seed.get("ok"):
            raise BrowserCheckError("page_check failed: " + str(seed.get("error") or seed.get("checks")))

        # 2. The in-page self-test.
        selftest = run_selftest(chrome, page, "1", arguments.window, None)
        summary["checks"]["selftest"] = {
            "ok": selftest.get("ok"),
            "steps": [{"name": step.get("name"), "ok": step.get("ok")} for step in selftest.get("steps", [])],
            "details": {step.get("name"): step.get("detail") for step in selftest.get("steps", []) if step.get("detail")},
        }

        # 3. Two-launch persistence.
        if not arguments.skip_persistence:
            profile = out_dir / "chrome-profile"
            if profile.exists():
                shutil.rmtree(profile, ignore_errors=True)
            write = run_selftest(chrome, page, "save-write", arguments.window, profile)
            read = run_selftest(chrome, page, "save-read", arguments.window, profile)
            summary["checks"]["persistence"] = {
                "ok": bool(write.get("ok") and read.get("ok")),
                "write_steps": [step.get("name") for step in write.get("steps", [])],
                "read_steps": [step.get("name") for step in read.get("steps", [])],
                "details": {step.get("name"): step.get("detail") for step in read.get("steps", []) if step.get("detail")},
            }

        # 4. Visual scenes and paired before/after checks.
        if not arguments.no_screenshots:
            shots: dict[str, dict] = {}
            for scene in SCENES:
                target = shots_dir / (scene + ".png")
                shots[scene] = capture_scene(chrome, page, scene, target, arguments.window)
            summary["checks"]["screenshots"] = shots
            for scene, stats in shots.items():
                if stats["buckets"] < 8:
                    raise BrowserCheckError("scene " + scene + " looks blank (colour buckets " + str(stats["buckets"]) + ")")

            pairs = {
                "night_darker_than_day": shots["day"]["brightness"] - shots["night"]["brightness"],
                "cave_darker_than_day": shots["day"]["brightness"] - shots["cave"]["brightness"],
                "day_vs_backdrop": diff_ratio(shots_dir / "day.png", shots_dir / "backdrop.png"),
                "zoom1_vs_zoom2": diff_ratio(shots_dir / "zoom1.png", shots_dir / "zoom2.png"),
                "day_vs_inventory": diff_ratio(shots_dir / "day.png", shots_dir / "inventory.png"),
                "day_vs_crafting": diff_ratio(shots_dir / "day.png", shots_dir / "crafting.png"),
                "day_vs_guide": diff_ratio(shots_dir / "day.png", shots_dir / "guide.png"),
            }
            summary["pairs"] = pairs
            if pairs["night_darker_than_day"] < 8:
                raise BrowserCheckError("the night scene is not clearly darker than the day scene")
            if pairs["cave_darker_than_day"] < 10:
                raise BrowserCheckError("the cave scene is not clearly darker than the day scene")
            if pairs["day_vs_backdrop"] < 0.02:
                raise BrowserCheckError("backdrop mode does not visibly change the frame")
            if pairs["zoom1_vs_zoom2"] < 0.15:
                raise BrowserCheckError("zoom levels do not visibly change the frame")
            if min(pairs["day_vs_inventory"], pairs["day_vs_crafting"], pairs["day_vs_guide"]) < 0.08:
                raise BrowserCheckError("a panel does not visibly change the frame")

            # 5. Offline proof: all host names unresolvable, the frame must be unchanged.
            offline_target = shots_dir / "offline-day.png"
            offline = capture_scene(
                chrome,
                page,
                "day",
                offline_target,
                arguments.window,
                extra=["--host-resolver-rules=MAP * ~NOTFOUND"],
            )
            offline_diff = diff_ratio(shots_dir / "day.png", offline_target)
            summary["checks"]["offline"] = {
                "ok": offline["buckets"] >= 8 and offline_diff < 0.02,
                "diff_vs_online": offline_diff,
                "buckets": offline["buckets"],
            }
            if not summary["checks"]["offline"]["ok"]:
                raise BrowserCheckError("the page did not render identically with DNS resolve blocked")

        summary["ok"] = True
        summary["out_dir"] = str(out_dir)
        print(json.dumps(summary, indent=2))
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return 0
    except (BrowserCheckError, page_check.CheckError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        summary["error"] = str(error)
        print(json.dumps(summary, indent=2))
        try:
            (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
