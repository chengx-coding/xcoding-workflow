import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const OUT = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp\\review";
const PROFILE = `${OUT}\\chrome-profile`;
const PORT = 9591;

rmSync(PROFILE, { recursive: true, force: true });
mkdirSync(PROFILE, { recursive: true });

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--window-size=1440,900",
    PAGE
  ],
  { stdio: "ignore" }
);

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
    } catch (error) {
      // starting
    }
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
  async function viewport(width, height) {
    await send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
      screenWidth: width,
      screenHeight: height
    });
    await sleep(350);
  }
  async function capture(name) {
    const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(`${OUT}\\${name}`, Buffer.from(result.data, "base64"));
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

  // Idle 960 view, fresh
  await viewport(960, 600);
  await evaluate("document.getElementById('overlay').hidden = true; document.getElementById('overlayClose').click && 0");
  await sleep(300);
  await capture("ind-960.png");

  // Overlay at 960
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(500);
  await capture("ind-overlay-960-top.png");
  const overlayMetrics960 = await evaluate(`(() => {
    const panel = document.querySelector('#overlay .panel');
    const r = panel.getBoundingClientRect();
    return {
      viewport: [innerWidth, innerHeight],
      panel: { x: r.x, y: r.y, w: r.width, h: r.height, scrollH: panel.scrollHeight, clientH: panel.clientHeight, scrollTop: panel.scrollTop },
      bodyOverflowX: document.documentElement.scrollWidth > innerWidth,
      visibleButtons: [...panel.querySelectorAll('button')].map(b => { const q = b.getBoundingClientRect(); return [b.textContent.trim().slice(0,20), Math.round(q.x), Math.round(q.y), Math.round(q.width), Math.round(q.height)]; })
    };
  })()`);
  await evaluate("document.querySelector('#overlay .panel').scrollTop = 9999");
  await sleep(300);
  await capture("ind-overlay-960-bottom.png");

  // Overlay at 1440
  await evaluate("document.getElementById('overlayClose').click()");
  await viewport(1440, 900);
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(500);
  await capture("ind-overlay-1440.png");
  const overlayMetrics1440 = await evaluate(`(() => {
    const panel = document.querySelector('#overlay .panel');
    const r = panel.getBoundingClientRect();
    return { viewport: [innerWidth, innerHeight], panel: { x: r.x, y: r.y, w: r.width, h: r.height, scrollH: panel.scrollHeight, clientH: panel.clientHeight } };
  })()`);
  await evaluate("document.getElementById('overlayClose').click()");
  await sleep(250);

  // HUD metrics at 1440
  const hudMetrics = await evaluate(`(() => {
    const ids = ['hud','topRight','hintBar','hotbar','toastRail','status'];
    const out = {};
    for (const id of ids) {
      const el = document.getElementById(id);
      const r = el.getBoundingClientRect();
      out[id] = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom) };
    }
    out.hotbarOverflow = document.getElementById('hotbar').scrollWidth > document.getElementById('hotbar').clientWidth;
    out.docOverflow = [document.documentElement.scrollWidth, innerWidth, document.documentElement.scrollHeight, innerHeight];
    return out;
  })()`);

  // Mine a block and immediately capture particles/toast/save indicator
  await viewport(1440, 900);
  await sleep(400);
  const mineTarget = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const st = s.state;
    const px = Math.floor(st.player.x);
    const py = Math.floor(st.player.y);
    let target = null;
    for (let dx = -3; dx <= 3 && !target; dx += 1) {
      if (Math.abs(dx) < 2) continue;
      for (let dy = -1; dy <= 1 && !target; dy += 1) {
        const cx = px + dx; const cy = py + dy;
        if (cx >= 0 && cy >= 0 && cx < st.world.width && cy < st.world.height && st.world.data[cy * st.world.width + cx] !== 0) {
          target = { x: cx, y: cy };
        }
      }
    }
    if (!target) return null;
    return { cell: target, sx: Math.round(rect.left + target.x * cfg.tileSize - st.camera.x + cfg.tileSize / 2), sy: Math.round(rect.top + target.y * cfg.tileSize - st.camera.y + cfg.tileSize / 2) };
  })()`);
  let mineResult = null;
  if (mineTarget) {
    mineResult = await evaluate(`(() => {
      const canvas = document.getElementById('game');
      canvas.dispatchEvent(new PointerEvent('pointermove', { clientX: ${mineTarget.sx}, clientY: ${mineTarget.sy}, bubbles: true }));
      canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: ${mineTarget.sx}, clientY: ${mineTarget.sy}, bubbles: true, button: 0, buttons: 1 }));
      document.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, button: 0 }));
      const s = window.__sandbox;
      return { particles: s.state.particles.length, hover: s.state.hover ? s.state.hover.cell : null, save: document.getElementById('saveText').textContent };
    })()`);
    await sleep(90);
    await capture("ind-mine-action-1440.png");
  }

  // Rapidly switch slots and capture toast/save
  await sleep(400);
  const interactions = await evaluate(`(() => {
    const s = window.__sandbox;
    const before = { seed: s.state.seed, hp: s.state.hotbarIndex, inv: { ...s.state.inventory } };
    document.querySelectorAll('#hotbar .slot')[5].click();
    return { before, afterIndex: s.state.hotbarIndex, saveText: document.getElementById('saveText').textContent, selected: document.querySelector('#hotbar .slot.is-selected .name').textContent };
  })()`);
  await sleep(250);
  await capture("ind-selected-sand-1440.png");

  // Pause state
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(350);
  const paused = await evaluate("({ paused: window.__sandbox.state.paused, hidden: document.getElementById('overlay').hidden })");
  await capture("ind-pause-1440.png");
  await evaluate("document.getElementById('overlayClose').click()");

  console.log(JSON.stringify({ ok: true, overlayMetrics960, overlayMetrics1440, hudMetrics, mineTarget, mineResult, interactions, paused }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exitCode = 1;
} finally {
  try { if (ws) ws.close(); } catch (error) { /* ignore */ }
  chrome.kill();
  await sleep(400);
  rmSync(PROFILE, { recursive: true, force: true });
}
