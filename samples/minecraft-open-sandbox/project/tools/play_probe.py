#!/usr/bin/env python3
"""Execute a real-browser product probe for Emberblock.

The probe uses only the Python standard library and the local Chrome build through
tools/cdp_client.py. It exercises real pointer and keyboard input and writes a
machine-readable report plus screenshots.

Usage:
    python tools/play_probe.py --page index.html --out .probe
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_client import Chrome  # noqa: E402


class ProbeError(RuntimeError):
    pass


def latest_work_order_tmp(project: Path) -> Path | None:
    work_orders = project / ".xcoding" / "work-orders"
    if not work_orders.is_dir():
        return None
    candidates = [item for item in work_orders.iterdir() if item.is_dir()]
    for item in sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True):
        tmp = item / "tmp"
        if tmp.is_dir():
            return tmp
    return None


def resolve_output(project: Path, explicit: str) -> Path:
    if explicit:
        return Path(explicit).resolve()
    work_tmp = latest_work_order_tmp(project)
    if work_tmp:
        return work_tmp / "play-probe"
    return project / ".tmp" / "play-probe"


def rect(chrome: Chrome, selector: str) -> dict:
    value = chrome.eval(
        "(() => { const element = document.querySelector(%s);"
        " if (!element) return null; const box = element.getBoundingClientRect();"
        " return { x: box.x + box.width / 2, y: box.y + box.height / 2,"
        " width: box.width, height: box.height,"
        " visible: box.width > 0 && box.height > 0 && !element.hidden,"
        " disabled: !!element.disabled,"
        " text: element.textContent }; })()" % json.dumps(selector)
    )
    if value is None:
        raise ProbeError("missing element: " + selector)
    return value


def click(chrome: Chrome, selector: str, dwell_ms: int = 110) -> dict:
    box = rect(chrome, selector)
    if not box["visible"]:
        raise ProbeError("element is not visible: " + selector)
    chrome.click(box["x"], box["y"], dwell_ms=dwell_ms)
    time.sleep(0.16)
    return box


def key(chrome: Chrome, code: str, label: str = "") -> None:
    chrome.key(code, label or code, 80)
    time.sleep(0.15)


def snapshot(chrome: Chrome) -> dict:
    value = chrome.eval("window.__emberblock && window.__emberblock.getSnapshot()")
    if not isinstance(value, dict):
        raise ProbeError("game did not expose a snapshot")
    return value


def find_tile(chrome: Chrome, keys: list[str], radius: int = 7, min_y: int = -8, max_y: int = 1, max_distance: float = 5.1) -> dict | None:
    state = snapshot(chrome)
    x = state["player"]["x"]
    y = state["player"]["y"]
    expression = """
    (() => {
      const keys = %s;
      let best = null;
      let bestDistance = 1e9;
      for (let tx = Math.floor(%s) - %d; tx <= Math.floor(%s) + %d; tx += 1) {
        for (let ty = Math.floor(%s) + %d; ty <= Math.floor(%s) + %d; ty += 1) {
          const tile = window.__emberblock.getTile(tx, ty);
          if (!keys.includes(tile.key)) continue;
          let exposed = false;
          for (const pair of [[1,0],[-1,0],[0,1],[0,-1]]) {
            if (window.__emberblock.getTile(tx + pair[0], ty + pair[1]).key === 'air') {
              exposed = true;
              break;
            }
          }
          if (!exposed) continue;
          const distance = Math.abs(tx + 0.5 - %s) + Math.abs(ty + 0.5 - %s);
          if (distance <= %s && distance < bestDistance) {
            bestDistance = distance;
            best = { x: tx, y: ty, key: tile.key, distance: distance };
          }
        }
      }
      return best;
    })()
    """ % (
        json.dumps(keys),
        x,
        radius,
        x,
        radius,
        y,
        min_y,
        y,
        max_y,
        x,
        y,
        max_distance,
    )
    return chrome.eval(expression)


def mine(chrome: Chrome, tile: dict, seconds: float) -> None:
    point = chrome.eval("window.__emberblock.tileToClient(%d, %d)" % (tile["x"], tile["y"]))
    chrome.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": point["x"], "y": point["y"]})
    time.sleep(0.08)
    chrome.send(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": point["x"], "y": point["y"], "button": "left", "clickCount": 1},
    )
    time.sleep(seconds)
    chrome.send(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": point["x"], "y": point["y"], "button": "left", "clickCount": 1},
    )
    time.sleep(0.2)


def find_place_target(chrome: Chrome) -> dict:
    state = snapshot(chrome)
    x = state["player"]["x"]
    y = state["player"]["y"]
    target = chrome.eval(
        """
        (() => {
          for (let distance = 2; distance <= 5; distance += 1) {
            for (const tx of [Math.floor(%s) + distance, Math.floor(%s) - distance]) {
              const ty = Math.floor(%s) - 1;
              if (window.__emberblock.getTile(tx, ty).block === 0 &&
                  window.__emberblock.getTile(tx, ty + 1).block !== 0) {
                return { x: tx, y: ty };
              }
            }
          }
          return null;
        })()
        """
        % (x, x, y)
    )
    if not target:
        raise ProbeError("no placement tile found near the player")
    return target


def place(chrome: Chrome, target: dict) -> None:
    point = chrome.eval("window.__emberblock.tileToClient(%d, %d)" % (target["x"], target["y"]))
    chrome.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": point["x"], "y": point["y"]})
    time.sleep(0.08)
    chrome.click(point["x"], point["y"], button="right", dwell_ms=110)
    time.sleep(0.18)


def run(page: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    profile = out / "chrome-profile"
    home = out / "home"
    for path in (profile, home):
        if path.exists():
            shutil.rmtree(path)
    chrome = Chrome(page, profile, home, width=960, height=600)
    checks: list[dict] = []
    screenshots: list[str] = []
    network_urls: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(condition), "detail": detail})
        if not condition:
            raise ProbeError(name + (": " + detail if detail else ""))

    def shot(name: str) -> None:
        path = out / (name + ".png")
        chrome.screenshot(path)
        screenshots.append(str(path))

    try:
        chrome.send("Network.enable")
        chrome.navigate()
        time.sleep(0.5)
        state = snapshot(chrome)
        check("boot exposes state", state.get("seed") is not None, "seed=" + str(state.get("seed")))
        check("fresh boot shows title", state.get("overlay") == "start", "overlay=" + str(state.get("overlay")))
        check("first-run Play and Help visible", rect(chrome, "#btn-play")["visible"] and rect(chrome, "#btn-how-to")["visible"])
        check("window status is ready", chrome.eval("document.getElementById('status').dataset.state") == "ready")
        shot("01-start")

        click(chrome, "#btn-how-to")
        check("help opens from title", snapshot(chrome)["overlay"] == "help")
        check("help lists controls", "Mine" in chrome.eval("document.getElementById('help-screen').textContent"))
        shot("02-help")
        click(chrome, "#btn-help-close")
        check("help returns to title", snapshot(chrome)["overlay"] == "start")

        click(chrome, "#btn-play")
        check("play starts the world", snapshot(chrome)["overlay"] is None and snapshot(chrome)["playing"])
        time.sleep(0.3)
        shot("03-playing")

        before = snapshot(chrome)["player"]["x"]
        chrome.hold_key("KeyD", "d", 650)
        time.sleep(0.25)
        after = snapshot(chrome)["player"]["x"]
        check("real keyboard moves player", after > before + 0.5, f"{before:.2f} -> {after:.2f}")

        wood = find_tile(chrome, ["wood"], 7, -8, 1)
        check("a reachable tree exists", wood is not None)
        mine(chrome, wood, 1.6)
        state = snapshot(chrome)
        wood_count = sum(slot["count"] for slot in state["inventory"] if slot and slot["id"] == "wood")
        check("mining a tree yields wood", wood_count >= 1, "wood=" + str(wood_count))
        check("world tile changed after mining", chrome.eval(
            "window.__emberblock.getTile(%d, %d).key" % (wood["x"], wood["y"])
        ) == "air")
        check("tutorial records gathering", "wood" in state["tutorial"]["completed"])

        key(chrome, "KeyE", "e")
        check("pack opens", snapshot(chrome)["overlay"] == "inventory")
        check("planks recipe is available", rect(chrome, '.recipe[data-recipe-id="planks"] .craft-button')["visible"]
              and not rect(chrome, '.recipe[data-recipe-id="planks"] .craft-button').get("disabled", False))
        shot("04-inventory")
        box = rect(chrome, '.recipe[data-recipe-id="planks"] .craft-button')
        chrome.eval("document.querySelector('.recipe[data-recipe-id=\"planks\"] .craft-button').scrollIntoView({block:'center'})")
        time.sleep(0.1)
        box = rect(chrome, '.recipe[data-recipe-id="planks"] .craft-button')
        chrome.click(box["x"], box["y"], dwell_ms=110)
        time.sleep(0.25)
        state = snapshot(chrome)
        plank_count = sum(slot["count"] for slot in state["inventory"] if slot and slot["id"] == "planks")
        check("real craft click creates planks", plank_count >= 4, "planks=" + str(plank_count))
        key(chrome, "KeyE", "e")
        check("E closes the pack", snapshot(chrome)["overlay"] is None)

        state = snapshot(chrome)
        plank_slot = next((index for index, slot in enumerate(state["inventory"]) if slot and slot["id"] == "planks"), None)
        check("planks are in the hotbar for placement", plank_slot is not None and plank_slot < 9, "slot=" + str(plank_slot))
        chrome.eval("window.__emberblock.setSelected(%d)" % plank_slot)
        target = find_place_target(chrome)
        place(chrome, target)
        check("right click places a block", chrome.eval(
            "window.__emberblock.getTile(%d, %d).key" % (target["x"], target["y"])
        ) == "planks", "target=" + json.dumps(target))
        after_place = snapshot(chrome)
        plank_count_after = sum(slot["count"] for slot in after_place["inventory"] if slot and slot["id"] == "planks")
        check("placement consumes one block", plank_count_after == plank_count - 1)

        chrome.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Control", "code": "ControlLeft"})
        chrome.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "s", "code": "KeyS", "modifiers": 2})
        chrome.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "s", "code": "KeyS", "modifiers": 2})
        chrome.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Control", "code": "ControlLeft"})
        time.sleep(0.4)
        check("manual save writes progress", snapshot(chrome)["saveAt"] > 0)
        shot("05-saved")

        chrome.navigate()
        time.sleep(0.8)
        reloaded = snapshot(chrome)
        check("reload returns to title with Continue", reloaded["overlay"] == "start"
              and chrome.eval("document.getElementById('btn-play').textContent") == "Continue")
        check("placed block survives reload", chrome.eval(
            "window.__emberblock.getTile(%d, %d).key" % (target["x"], target["y"])
        ) == "planks")
        check("pack survives reload", sum(slot["count"] for slot in reloaded["inventory"] if slot and slot["id"] == "planks") == plank_count_after)
        shot("06-continue")

        click(chrome, "#btn-play")
        chrome.eval("window.__emberblock.setTime(0.9)")
        time.sleep(0.5)
        check("night state is active", snapshot(chrome)["timeOfDay"] > 0.85)
        shot("07-night")
        chrome.eval("window.__emberblock.setTime(0.36)")
        time.sleep(0.35)
        shot("08-day")

        fps = chrome.eval(
            "new Promise((resolve) => { let frames = 0; const start = performance.now();"
            " function tick(now) { frames += 1; if (now - start < 1500) requestAnimationFrame(tick);"
            " else resolve(frames / ((now - start) / 1000)); } requestAnimationFrame(tick); })",
            await_promise=True,
        )
        check("render loop is responsive", fps >= 45, "fps=" + str(round(fps, 1)))

        chrome.send("Emulation.setDeviceMetricsOverride", {
            "width": 480,
            "height": 700,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        chrome.navigate()
        time.sleep(0.7)
        start_box = rect(chrome, ".start-card")
        check("narrow title fits the viewport", start_box["width"] <= 480 and start_box["visible"])
        click(chrome, "#btn-play")
        key(chrome, "KeyE", "e")
        panel = rect(chrome, ".inventory-panel")
        check("narrow inventory stays inside viewport", panel["width"] <= 480 and panel["visible"])
        shot("09-narrow")
        chrome.send("Emulation.setDeviceMetricsOverride", {
            "width": 960,
            "height": 600,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        time.sleep(0.25)
        key(chrome, "KeyE", "e")
        check("narrow pack closes cleanly", snapshot(chrome)["overlay"] is None)

        # Real-pointer interaction truth: ten primary controls with >=90 ms dwell
        # and matching pointerdown/pointerup targets.
        chrome.eval("""
        (() => {
          window.__probeClicks = [];
          document.addEventListener('pointerdown', (event) => {
            const target = event.target.closest('button') || event.target;
            window.__probeDown = target.id || target.dataset.index || target.className || target.tagName;
          }, { capture: true });
          document.addEventListener('pointerup', (event) => {
            const target = event.target.closest('button') || event.target;
            const up = target.id || target.dataset.index || target.className || target.tagName;
            window.__probeClicks.push({ down: window.__probeDown, up: up, at: performance.now() });
          }, { capture: true });
        })();
        """)
        pointer_sequence = [
            ".hotbar-slot[data-index='0']", ".hotbar-slot[data-index='1']",
            ".hotbar-slot[data-index='2']", ".hotbar-slot[data-index='3']",
            ".hotbar-slot[data-index='4']", ".hotbar-slot[data-index='5']",
            ".hotbar-slot[data-index='6']", ".hotbar-slot[data-index='7']",
            ".hotbar-slot[data-index='8']", "#btn-sound",
        ]
        for selector in pointer_sequence:
            click(chrome, selector, dwell_ms=110)
        pointer_clicks = chrome.eval("window.__probeClicks")
        check("10/10 real pointer clicks hit the same target",
              len(pointer_clicks) == 10 and all(item["down"] == item["up"] for item in pointer_clicks),
              json.dumps(pointer_clicks))
        shot("11-pointer-state")

        network_urls = [
            event.get("params", {}).get("request", {}).get("url", "")
            for event in chrome.events
            if event.get("method") == "Network.requestWillBeSent"
        ]
        external = [url for url in network_urls if url and not url.startswith("file:")]
        check("no network requests occur", not external, json.dumps(external))

        chrome.eval("localStorage.setItem('emberblock.save.v1', '{broken json')")
        chrome.navigate()
        time.sleep(0.8)
        recovered = snapshot(chrome)
        check("corrupt save boots to a fresh title", recovered["overlay"] == "start" and recovered["saveAt"] == 0)
        check("corrupt save shows a notice", chrome.eval(
            "document.getElementById('toast').classList.contains('is-visible')"
        ))
        shot("10-corrupt-recovery")

        console_errors = [
            event
            for event in chrome.events
            if event.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded")
            and (event.get("method") == "Runtime.exceptionThrown"
                 or event.get("params", {}).get("entry", {}).get("level") in ("error", "warning"))
        ]
        check("no page exceptions or error logs", not console_errors, str(console_errors[:2]))
        return {
            "ok": True,
            "page": str(page),
            "viewport": [960, 600],
            "checks": checks,
            "screenshots": screenshots,
            "pointer_clicks": pointer_clicks,
            "network_requests": network_urls,
            "errors": console_errors,
        }
    finally:
        chrome.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="index.html")
    parser.add_argument("--out", default="")
    arguments = parser.parse_args()
    page = Path(arguments.page)
    if not page.is_absolute():
        page = (Path.cwd() / page).resolve()
    out = resolve_output(page.parent, arguments.out)
    report = {"ok": False, "error": "probe did not complete"}
    try:
        report = run(page, out)
    except Exception as exc:  # Report any probe failure as JSON.
        report = {
            "ok": False,
            "page": str(page),
            "error": type(exc).__name__ + ": " + str(exc),
            "output": str(out),
        }
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
