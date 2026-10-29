import json
import os

from playwright.sync_api import sync_playwright

OUT = r"C:\dev\xcoding-workflow-dev\wf-ablation\standard-sample\workspace\workshop\.xcoding\work-orders\20261029-1459-2d-sandbox-game\tmp\final-review"
PAGE = r"file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

CHECK = r"""
() => {
  const rect = (el) => { const r = el.getBoundingClientRect(); return {top:+r.top.toFixed(1), bottom:+r.bottom.toFixed(1), left:+r.left.toFixed(1), right:+r.right.toFixed(1), width:+r.width.toFixed(1), height:+r.height.toFixed(1)}; };
  const hotbar = document.getElementById('hotbar');
  const hint = document.getElementById('hintBar');
  const slots = [...hotbar.querySelectorAll('.slot')];
  const slotChecks = slots.map((slot) => {
    const r = slot.getBoundingClientRect();
    const name = slot.querySelector('.name');
    const count = slot.querySelector('.count');
    const nr = name.getBoundingClientRect();
    const cr = count.getBoundingClientRect();
    return {
      block: slot.dataset.block,
      name: name.textContent,
      count: count.textContent,
      slot: rect(slot),
      nameRect: rect(name),
      countRect: rect(count),
      nameOverflow: name.scrollWidth > name.clientWidth + 1,
      nameClippedInsideSlot: nr.left >= r.left && nr.right <= r.right && nr.bottom <= r.bottom,
      countInsideSlot: cr.left >= r.left && cr.right <= r.right && cr.top >= r.top,
      nameFont: getComputedStyle(name).fontSize,
      countFont: getComputedStyle(count).fontSize
    };
  });
  const hr = hotbar.getBoundingClientRect();
  const ir = hint.getBoundingClientRect();
  const selected = document.querySelector('.slot.is-selected');
  return {
    viewport: {w: innerWidth, h: innerHeight},
    hotbar: rect(hotbar),
    hintBar: rect(hint),
    hintBarVisible: getComputedStyle(hint).display !== 'none',
    hotbarHintOverlap: !(hr.top >= ir.bottom || hr.bottom <= ir.top || hr.right <= ir.left || hr.left >= ir.right),
    hotbarHintGap: +(hr.top - ir.bottom).toFixed(1),
    slotChecks,
    selectedIndex: slots.indexOf(selected)
  };
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, headless=True, args=["--disable-gpu", "--hide-scrollbars"])
    for width, height in ((960, 600), (1440, 900)):
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(PAGE, wait_until="load")
        page.wait_for_function("window.__sandbox && window.__sandbox.ready")
        page.wait_for_timeout(500)
        result = page.evaluate(CHECK)
        print(width, json.dumps(result, indent=2))
        page.close()
    browser.close()
