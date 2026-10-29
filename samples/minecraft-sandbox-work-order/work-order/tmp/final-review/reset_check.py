import json
import os

from playwright.sync_api import sync_playwright

OUT = r"C:\dev\xcoding-workflow-dev\wf-ablation\standard-sample\workspace\workshop\.xcoding\work-orders\20261029-1459-2d-sandbox-game\tmp\final-review"
PAGE = r"file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, headless=True, args=["--disable-gpu", "--hide-scrollbars"])
    page = browser.new_page(viewport={"width": 960, "height": 600}, device_scale_factor=1)
    page.goto(PAGE, wait_until="load")
    page.wait_for_function("window.__sandbox && window.__sandbox.ready")
    page.wait_for_timeout(500)
    page.evaluate("document.getElementById('helpBtn').click()")
    page.wait_for_timeout(300)
    page.evaluate("document.getElementById('worldReset').click()")
    page.wait_for_timeout(300)
    result = page.evaluate(
        """() => {
          const r = (el) => { const b = el.getBoundingClientRect(); return {left:+b.left.toFixed(1), right:+b.right.toFixed(1), top:+b.top.toFixed(1), bottom:+b.bottom.toFixed(1), width:+b.width.toFixed(1)}; };
          const panel = document.querySelector('#overlay .panel');
          const reset = document.getElementById('worldReset');
          const hint = document.getElementById('seedHint');
          const row = reset.parentElement;
          return {
            resetText: reset.textContent,
            resetRect: r(reset),
            rowRect: r(row),
            panelRect: r(panel),
            hintText: hint.textContent,
            hintRect: r(hint),
            resetInsideRow: reset.getBoundingClientRect().right <= row.getBoundingClientRect().right + 0.5,
            resetInsidePanel: reset.getBoundingClientRect().right <= panel.getBoundingClientRect().right - 24 + 0.5,
            scrollHeight: panel.scrollHeight, clientHeight: panel.clientHeight
          };
        }"""
    )
    print(json.dumps(result, indent=2))
    page.screenshot(path=os.path.join(OUT, "overlay-960-reset-armed.png"))
    browser.close()
