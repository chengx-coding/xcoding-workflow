import json
import os
import sys

from playwright.sync_api import sync_playwright

OUT = r"C:\dev\xcoding-workflow-dev\wf-ablation\standard-sample\workspace\workshop\.xcoding\work-orders\20261029-1459-2d-sandbox-game\tmp\final-review"
PAGE = r"file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

MEASURE = r"""
() => {
  const panel = document.querySelector('#overlay .panel');
  const head = document.querySelector('.panel-head');
  const reset = document.getElementById('worldReset');
  const hint = document.getElementById('seedHint');
  const apply = document.getElementById('seedApply');
  const random = document.getElementById('seedRandom');
  const close = document.getElementById('overlayClose');
  const rect = (el) => { const r = el.getBoundingClientRect(); return {top:+r.top.toFixed(1), bottom:+r.bottom.toFixed(1), left:+r.left.toFixed(1), right:+r.right.toFixed(1), width:+r.width.toFixed(1), height:+r.height.toFixed(1)}; };
  const panelRect = rect(panel);
  const resetRect = rect(reset);
  const hintRect = rect(hint);
  const applyRect = rect(apply);
  const randomRect = rect(random);
  const headRect = rect(head);
  const closeRect = rect(close);
  const style = getComputedStyle(panel);
  const contentTop = panelRect.top + parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop);
  const contentBottom = panelRect.bottom - parseFloat(style.borderBottomWidth) - parseFloat(style.paddingBottom);
  const fits = panel.scrollHeight <= panel.clientHeight + 1;
  const allRowsVisible = resetRect.bottom <= contentBottom + 0.5 && randomRect.bottom <= contentBottom + 0.5 && hintRect.bottom <= contentBottom + 0.5;
  const overflows = [];
  panel.querySelectorAll('dd, dt, .notes, .legend li, .hint, .btn, label').forEach((el) => {
    if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) {
      overflows.push({tag: el.tagName, cls: el.className, text: (el.textContent || '').trim().slice(0, 60), sw: el.scrollWidth, cw: el.clientWidth, sh: el.scrollHeight, ch: el.clientHeight});
    }
  });
  return {
    viewport: {w: innerWidth, h: innerHeight},
    panel: {rect: panelRect, scrollHeight: panel.scrollHeight, clientHeight: panel.clientHeight, scrollTop: panel.scrollTop, maxHeight: style.maxHeight, padding: style.padding, contentTop: +contentTop.toFixed(1), contentBottom: +contentBottom.toFixed(1)},
    head: headRect,
    close: closeRect,
    reset: resetRect,
    random: randomRect,
    apply: applyRect,
    seedHint: {rect: hintRect, text: hint.textContent},
    contentFitsWithoutScroll: fits,
    rowsVisibleWithoutScroll: allRowsVisible,
    overflowedElements: overflows,
    seedActionsVisible: resetRect.top >= panelRect.top && resetRect.bottom <= panelRect.bottom,
    seedHintVisible: hintRect.top >= panelRect.top && hintRect.bottom <= panelRect.bottom,
    overlayHidden: document.getElementById('overlay').hidden
  };
}
"""

HOTBAR = r"""
() => {
  const hotbar = document.getElementById('hotbar');
  const slots = [...hotbar.querySelectorAll('.slot')];
  const r = hotbar.getBoundingClientRect();
  const selected = document.querySelector('.slot.is-selected');
  const sr = selected ? selected.getBoundingClientRect() : null;
  const name = selected ? selected.querySelector('.name') : null;
  const count = selected ? selected.querySelector('.count') : null;
  const cs = (el) => el ? getComputedStyle(el) : null;
  const nameStyle = cs(name);
  const countStyle = cs(count);
  return {
    viewport: {w: innerWidth, h: innerHeight},
    slotCount: slots.length,
    hotbarRect: {left:+r.left.toFixed(1), right:+r.right.toFixed(1), top:+r.top.toFixed(1), bottom:+r.bottom.toFixed(1), width:+r.width.toFixed(1), height:+r.height.toFixed(1)},
    fitsViewport: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
    gapToViewportBottom: +(innerHeight - r.bottom).toFixed(1),
    selected: selected ? {text: selected.textContent.trim(), rect: {left:+sr.left.toFixed(1), right:+sr.right.toFixed(1), top:+sr.top.toFixed(1), bottom:+sr.bottom.toFixed(1)}} : null,
    nameFontSize: nameStyle ? nameStyle.fontSize : null,
    countFontSize: countStyle ? countStyle.fontSize : null,
    counts: slots.map((s) => s.querySelector('.count').textContent),
    labels: slots.map((s) => s.querySelector('.name').textContent),
    slotWidths: slots.map((s) => +s.getBoundingClientRect().width.toFixed(1))
  };
}
"""

FIND_MINE = r"""
() => {
  const s = window.__sandbox, W = window.SandboxWorld, C = window.SandboxConfig;
  const p = s.player, cam = s.camera, T = C.tileSize;
  const vw = innerWidth, vh = innerHeight;
  const scr = (x, y) => ({x: (x + 0.5) * T - cam.x, y: (y + 0.5) * T - cam.y});
  const cx = Math.floor(p.x), cy = Math.floor(p.y - p.height / 2);
  let best = null;
  for (let dy = -5; dy <= 5; dy += 1) {
    for (let dx = -5; dx <= 5; dx += 1) {
      const x = cx + dx, y = cy + dy;
      const r = W.canMineBlock(s.world, p, x, y, C.reach);
      if (!r.ok) continue;
      const q = scr(x, y);
      if (q.x < 80 || q.x > vw - 80 || q.y < 120 || q.y > vh - 200) continue;
      const d = Math.hypot(p.x - (x + 0.5), (p.y - p.height / 2) - (y + 0.5));
      if (!best || d < best.d) best = {x, y, sx: +q.x.toFixed(1), sy: +q.y.toFixed(1), d: +d.toFixed(2)};
    }
  }
  return {player: {x: p.x, y: p.y, height: p.height}, camera: {x: cam.x, y: cam.y}, cell: best};
}
"""

FIND_PLACE = r"""
() => {
  const s = window.__sandbox, W = window.SandboxWorld, C = window.SandboxConfig;
  const p = s.player, cam = s.camera, T = C.tileSize;
  const vw = innerWidth, vh = innerHeight;
  const scr = (x, y) => ({x: (x + 0.5) * T - cam.x, y: (y + 0.5) * T - cam.y});
  const cx = Math.floor(p.x), cy = Math.floor(p.y - p.height / 2);
  let best = null;
  for (let dy = -5; dy <= 5; dy += 1) {
    for (let dx = -5; dx <= 5; dx += 1) {
      const x = cx + dx, y = cy + dy;
      const r = W.canPlaceBlock(s.world, p, x, y, C.reach);
      if (!r.ok) continue;
      const q = scr(x, y);
      if (q.x < 80 || q.x > vw - 80 || q.y < 120 || q.y > vh - 200) continue;
      const d = Math.hypot(p.x - (x + 0.5), (p.y - p.height / 2) - (y + 0.5));
      if (!best || d < best.d) best = {x, y, sx: +q.x.toFixed(1), sy: +q.y.toFixed(1), d: +d.toFixed(2)};
    }
  }
  return {player: {x: p.x, y: p.y, height: p.height}, camera: {x: cam.x, y: cam.y}, cell: best};
}
"""


def boot(page):
    page.goto(PAGE, wait_until="load")
    page.wait_for_function(
        "window.__sandbox && window.__sandbox.ready && document.getElementById('status').dataset.state === 'ready'",
        timeout=15000,
    )
    page.wait_for_timeout(700)


def dispatch_move(page, x, y):
    page.evaluate(
        """([x, y]) => {
          const canvas = document.getElementById('game');
          const init = {bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', isPrimary: true};
          canvas.dispatchEvent(new PointerEvent('pointermove', init));
          canvas.dispatchEvent(new MouseEvent('mousemove', init));
        }""",
        [x, y],
    )
    page.wait_for_timeout(250)


def main():
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check"],
        )

        page = browser.new_page(viewport={"width": 960, "height": 600}, device_scale_factor=1)
        boot(page)
        page.screenshot(path=os.path.join(OUT, "boot-960.png"))
        results["hotbar960"] = page.evaluate(HOTBAR)

        page.evaluate("document.getElementById('helpBtn').click()")
        page.wait_for_timeout(450)
        page.screenshot(path=os.path.join(OUT, "overlay-960-first.png"))
        results["overlay960"] = page.evaluate(MEASURE)
        results["overlay960"]["scrollTopAfterOpen"] = page.evaluate("document.querySelector('#overlay .panel').scrollTop")

        page.evaluate("document.getElementById('overlayClose').click()")
        page.wait_for_timeout(250)
        results["overlay960"]["closed"] = page.evaluate("document.getElementById('overlay').hidden")

        mine = page.evaluate(FIND_MINE)
        results["mineTarget960"] = mine
        if mine["cell"]:
            dispatch_move(page, mine["cell"]["sx"], mine["cell"]["sy"])
            page.wait_for_timeout(300)
            results["mineHoverState960"] = page.evaluate(
                "() => { const h = window.__sandbox.state.hover; return h ? {cell:h.cell, mine:h.mine, placeCell:h.placeCell, place:h.place, reason:h.reason} : null; }"
            )
            page.screenshot(path=os.path.join(OUT, "hover-mine-960.png"))

        page.keyboard.press("8")
        page.wait_for_timeout(250)
        place = page.evaluate(FIND_PLACE)
        results["placeTarget960"] = place
        results["glassSelected960"] = page.evaluate(
            "() => ({selected: document.querySelector('.slot.is-selected')?.dataset.block, name: document.querySelector('.slot.is-selected .name')?.textContent, count: document.querySelector('.slot.is-selected .count')?.textContent})"
        )
        if place["cell"]:
            dispatch_move(page, place["cell"]["sx"], place["cell"]["sy"])
            page.wait_for_timeout(300)
            results["placeHoverState960"] = page.evaluate(
                "() => { const h = window.__sandbox.state.hover; return h ? {cell:h.cell, mine:h.mine, placeCell:h.placeCell, place:h.place, reason:h.reason} : null; }"
            )
            page.screenshot(path=os.path.join(OUT, "hover-place-960.png"))

        page.close()

        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        boot(page)
        page.screenshot(path=os.path.join(OUT, "boot-1440.png"))
        results["hotbar1440"] = page.evaluate(HOTBAR)

        page.evaluate("document.getElementById('helpBtn').click()")
        page.wait_for_timeout(450)
        page.screenshot(path=os.path.join(OUT, "overlay-1440.png"))
        results["overlay1440"] = page.evaluate(MEASURE)
        page.evaluate("document.getElementById('overlayClose').click()")
        page.wait_for_timeout(250)

        mine = page.evaluate(FIND_MINE)
        results["mineTarget1440"] = mine
        if mine["cell"]:
            dispatch_move(page, mine["cell"]["sx"], mine["cell"]["sy"])
            page.wait_for_timeout(300)
            results["mineHoverState1440"] = page.evaluate(
                "() => { const h = window.__sandbox.state.hover; return h ? {cell:h.cell, mine:h.mine, placeCell:h.placeCell, place:h.place, reason:h.reason} : null; }"
            )
            page.screenshot(path=os.path.join(OUT, "hover-mine-1440.png"))

        page.keyboard.press("8")
        page.wait_for_timeout(250)
        place = page.evaluate(FIND_PLACE)
        results["placeTarget1440"] = place
        if place["cell"]:
            dispatch_move(page, place["cell"]["sx"], place["cell"]["sy"])
            page.wait_for_timeout(300)
            results["placeHoverState1440"] = page.evaluate(
                "() => { const h = window.__sandbox.state.hover; return h ? {cell:h.cell, mine:h.mine, placeCell:h.placeCell, place:h.place, reason:h.reason} : null; }"
            )
            page.screenshot(path=os.path.join(OUT, "hover-place-1440.png"))

        page.close()
        browser.close()

    with open(os.path.join(OUT, "measurements.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(results, fh, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
