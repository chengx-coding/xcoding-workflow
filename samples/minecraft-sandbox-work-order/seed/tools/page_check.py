#!/usr/bin/env python3
"""Static and headless-browser checks for the sandbox sample page.

The check has two halves:

1. Static checks: required elements exist, every local asset referenced by the page
   resolves, and the page-served files contain no external network references.
2. Runtime checks: the page is loaded in headless Chrome, a screenshot is captured,
   the status marker pixel shows the ready state, and the canvas is not blank.

Standard library only. The PNG reader supports the 8-bit RGB/RGBA non-interlaced
images Chrome writes; anything else is reported as an unsupported screenshot.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REQUIRED_IDS = ("game", "status", "hud", "hotbar")
REFERENCE_PATTERN = re.compile(r'(?:src|href)="([^"]+)"')
NAMESPACE_PATTERN = re.compile(r"https?://www\.w3\.org/[^\s\"']*")
NETWORK_PATTERN = re.compile(r"https?://|//cdn|@import\s+url\(\s*https?:")


class CheckError(RuntimeError):
    pass


def read_png(path: Path) -> tuple[int, int, int, list[bytes]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise CheckError("screenshot is not a PNG file")

    position = 8
    idat = b""
    width = height = 0
    bit_depth = color_type = interlace = 0
    while position < len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        chunk_type = data[position + 4 : position + 8]
        chunk = data[position + 8 : position + 8 + length]
        position += 12 + length
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            bit_depth = chunk[8]
            color_type = chunk[9]
            interlace = chunk[12]
        elif chunk_type == b"IDAT":
            idat += chunk
        elif chunk_type == b"IEND":
            break

    if bit_depth != 8 or interlace != 0 or color_type not in (2, 6):
        raise CheckError(
            f"unsupported PNG format (bit depth {bit_depth}, colour type {color_type}, interlace {interlace})"
        )

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(idat)
    rows: list[bytes] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + stride])
        offset += stride
        if filter_type == 1:
            for index in range(channels, stride):
                row[index] = (row[index] + row[index - channels]) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                row[index] = (row[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = row[index - channels] if index >= channels else 0
                row[index] = (row[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = row[index - channels] if index >= channels else 0
                up = previous[index]
                upper_left = previous[index - channels] if index >= channels else 0
                estimate = left + up - upper_left
                distance_left = abs(estimate - left)
                distance_up = abs(estimate - up)
                distance_upper_left = abs(estimate - upper_left)
                if distance_left <= distance_up and distance_left <= distance_upper_left:
                    predictor = left
                elif distance_up <= distance_upper_left:
                    predictor = up
                else:
                    predictor = upper_left
                row[index] = (row[index] + predictor) & 0xFF
        elif filter_type != 0:
            raise CheckError(f"unsupported PNG filter {filter_type}")
        rows.append(bytes(row))
        previous = row

    return width, height, channels, rows


def pixel(rows: list[bytes], channels: int, x: int, y: int) -> tuple[int, int, int]:
    row = rows[y]
    index = x * channels
    return row[index], row[index + 1], row[index + 2]


def find_chrome(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    located = shutil.which("chrome") or shutil.which("chrome.exe")
    if located:
        candidates.append(Path(located))
    candidates.extend(
        [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CheckError("no Chrome or Edge executable found; pass --chrome")


def page_files(page: Path) -> list[Path]:
    files = [page]
    root = page.parent
    for reference in REFERENCE_PATTERN.findall(page.read_text(encoding="utf-8")):
        if reference.startswith(("http://", "https://", "//", "data:", "#")):
            continue
        candidate = (root / reference).resolve()
        if candidate.is_file() and candidate not in files:
            files.append(candidate)
    return files


def static_checks(page: Path) -> list[str]:
    problems: list[str] = []
    html = page.read_text(encoding="utf-8")
    for element_id in REQUIRED_IDS:
        if f'id="{element_id}"' not in html:
            problems.append(f"missing required element id={element_id}")

    for reference in REFERENCE_PATTERN.findall(html):
        if reference.startswith(("http://", "https://", "//", "data:")):
            problems.append(f"external reference in page: {reference}")
            continue
        if reference.startswith("#"):
            continue
        if not (page.parent / reference).is_file():
            problems.append(f"missing local asset: {reference}")

    for served in page_files(page):
        if not served.is_file():
            continue
        text = served.read_text(encoding="utf-8", errors="replace")
        sanitized = NAMESPACE_PATTERN.sub("", text)
        if NETWORK_PATTERN.search(sanitized):
            problems.append(f"network reference in {served.relative_to(page.parent).as_posix()}")

    return problems


def screenshot(chrome: Path, page: Path, target: Path, width: int, height: int) -> None:
    command = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--virtual-time-budget=3000",
        f"--window-size={width},{height}",
        f"--screenshot={target}",
        page.as_uri(),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise CheckError("headless Chrome screenshot failed" + (": " + detail[-1] if detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default=str(Path(__file__).resolve().parent.parent / "index.html"))
    parser.add_argument("--screenshot", default="")
    parser.add_argument("--window", default="960x600")
    parser.add_argument("--chrome", default="")
    arguments = parser.parse_args()

    page = Path(arguments.page).resolve()
    width_text, _, height_text = arguments.window.lower().partition("x")
    viewport_width = int(width_text)
    viewport_height = int(height_text)

    result: dict[str, object] = {"ok": False, "page": str(page), "checks": {}}

    if not page.is_file():
        result["error"] = f"page not found: {page}"
        print(json.dumps(result, indent=2))
        return 1

    problems = static_checks(page)
    result["checks"]["static"] = {"ok": not problems, "problems": problems}
    if problems:
        result["error"] = "static checks failed"
        print(json.dumps(result, indent=2))
        return 1

    generated = False
    if arguments.screenshot:
        shot = Path(arguments.screenshot).resolve()
        shot.parent.mkdir(parents=True, exist_ok=True)
    else:
        handle, name = tempfile.mkstemp(prefix="sandbox-page-", suffix=".png")
        import os

        os.close(handle)
        shot = Path(name)
        generated = True

    try:
        chrome = find_chrome(arguments.chrome or None)
        screenshot(chrome, page, shot, viewport_width, viewport_height)
        image_width, image_height, channels, rows = read_png(shot)

        scale_x = image_width / viewport_width
        scale_y = image_height / viewport_height
        marker_x = int(round((8 + 7) * scale_x))
        marker_y = int(round((viewport_height - 8 - 7) * scale_y))
        if marker_x >= image_width or marker_y >= image_height:
            raise CheckError("screenshot is smaller than the expected viewport")
        red, green, blue = pixel(rows, channels, marker_x, marker_y)
        distance = ((red - 46) ** 2 + (green - 204) ** 2 + (blue - 113) ** 2) ** 0.5
        marker_ok = distance <= 70
        result["checks"]["status_marker"] = {
            "ok": marker_ok,
            "pixel": [red, green, blue],
            "expected": [46, 204, 113],
            "distance": round(distance, 1),
        }

        colours = set()
        for y in range(8, min(image_height, int(540 * scale_y)), 6):
            for x in range(8, min(image_width, int(960 * scale_x)), 6):
                sample = pixel(rows, channels, x, y)
                colours.add((sample[0] // 16, sample[1] // 16, sample[2] // 16))
        canvas_ok = len(colours) >= 12
        result["checks"]["canvas_colours"] = {"ok": canvas_ok, "buckets": len(colours)}

        ok = marker_ok and canvas_ok
        result["ok"] = ok
        result["screenshot"] = str(shot)
        result["viewport"] = [image_width, image_height]
        if not ok:
            result["error"] = "runtime checks failed"
        print(json.dumps(result, indent=2))
        return 0 if ok else 1
    except (CheckError, subprocess.TimeoutExpired) as error:
        result["error"] = str(error)
        print(json.dumps(result, indent=2))
        return 1
    finally:
        if generated:
            shot.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
