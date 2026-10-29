import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const OUT = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp\\review";
const PROFILE = `${OUT}\\chrome-profile-features`;
const PORT = 9593;

rmSync(PROFILE, { recursive: true, force: true });
mkdirSync(PROFILE, { recursive: true });

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
  "--disable-extensions", "--disable-background-networking", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, "--window-size=960,600", PAGE
], { stdio: "ignore" });

async function getJson(path) {
  const response = await fetch(`http://127.0.0.1:${PORT}${path}`);
  return response.json();
}
async function waitTarget() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const list = await getJson("/json/list");
      const target = list.find((item) => item.type === "page" && item.url.startsWith("file:"));
      if (target) return target;
    } catch (error) { /* starting */ }
    await sleep(250);
  }
  throw new Error("no target");
}

let ws;
try {
  const target = await waitTarget();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });
  let nextId = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
      else entry.resolve(message.result);
    }
  });
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }
  async function waitReady() {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      if (await evaluate("Boolean(window.__sandbox && window.__sandbox.ready)")) return;
      await sleep(120);
    }
    throw new Error("not ready");
  }
  await send("Runtime.enable");
  await send("Page.enable");
  await waitReady();
  await sleep(500);

  const baseline = await evaluate(`(() => {
    const s = window.__sandbox;
    return { seed: s.state.seed, surface: window.SandboxWorld.surfaceHeightAt(s.world, 10), hotbar: document.querySelectorAll('#hotbar .slot').length, legend: document.querySelectorAll('#blockLegend li').length, status: document.getElementById('status').dataset.state, toast: document.getElementById('toastRail').textContent };
  })()`);

  // Change seed through the real UI.
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(300);
  const seedUi = await evaluate(`(() => { const b = document.getElementById('seedApply'); const r = b.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, visible: r.bottom <= innerHeight && r.top >= 0 }; })()`);
  await evaluate(`(() => { const input = document.getElementById('seedInput'); input.value = '424242'; document.getElementById('seedApply').click(); })()`);
  await sleep(700);
  const seedChanged = await evaluate(`(() => {
    const s = window.__sandbox;
    return { seed: s.state.seed, surface: window.SandboxWorld.surfaceHeightAt(s.world, 10), overlayHidden: document.getElementById('overlay').hidden, save: document.getElementById('saveText').textContent, toast: document.getElementById('toastRail').textContent };
  })()`);

  // Two-step reset from the field guide.
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(300);
  const resetFirst = await evaluate(`(() => { document.getElementById('worldReset').click(); return { label: document.getElementById('worldReset').textContent, hint: document.getElementById('seedHint').textContent }; })()`);
  await sleep(150);
  const resetSecond = await evaluate(`(() => {
    document.getElementById('worldReset').click();
    const s = window.__sandbox;
    return new Promise((resolve) => setTimeout(() => resolve({ seed: s.state.seed, overlayHidden: document.getElementById('overlay').hidden, toast: document.getElementById('toastRail').textContent, save: document.getElementById('saveText').textContent }), 300));
  })()`);

  // Number key and wheel selection.
  await evaluate(`(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: '5', bubbles: true })); })()`);
  const keySelect = await evaluate("({ index: window.__sandbox.state.hotbarIndex, name: document.querySelector('#hotbar .slot.is-selected .name').textContent })");
  await evaluate(`(() => { const c = document.getElementById('game'); c.dispatchEvent(new WheelEvent('wheel', { deltaY: 100, bubbles: true, cancelable: true })); })()`);
  const wheelSelect = await evaluate("({ index: window.__sandbox.state.hotbarIndex, name: document.querySelector('#hotbar .slot.is-selected .name').textContent })");

  console.log(JSON.stringify({ ok: true, baseline, seedUi, seedChanged, resetFirst, resetSecond, keySelect, wheelSelect }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exitCode = 1;
} finally {
  try { if (ws) ws.close(); } catch (error) { /* ignore */ }
  chrome.kill();
  await sleep(400);
  rmSync(PROFILE, { recursive: true, force: true });
}
