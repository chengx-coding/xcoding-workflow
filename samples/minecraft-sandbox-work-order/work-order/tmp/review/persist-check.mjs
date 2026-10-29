import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const OUT = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp\\review";
const PROFILE = `${OUT}\\chrome-profile-persist`;
const PORT = 9592;

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
    "--window-size=960,600",
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
  const events = [];
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.method) events.push(message.method);
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
  const before = await evaluate(`(() => {
    const s = window.__sandbox;
    return { save: document.getElementById('saveText').textContent, seed: s.state.seed, x: s.player.x, counts: { ...s.state.inventory } };
  })()`);

  const targetCell = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const px = Math.floor(s.state.player.x);
    const py = Math.floor(s.state.player.y);
    for (let dx = -3; dx <= 3; dx += 1) {
      if (Math.abs(dx) < 2) continue;
      for (let dy = -1; dy <= 1; dy += 1) {
        const cx = px + dx; const cy = py + dy;
        if (cx >= 0 && cy >= 0 && cx < s.state.world.width && cy < s.state.world.height && s.state.world.data[cy * s.state.world.width + cx] !== 0) {
          return { x: cx, y: cy, sx: Math.round(rect.left + cx * cfg.tileSize - s.state.camera.x + cfg.tileSize / 2), sy: Math.round(rect.top + cy * cfg.tileSize - s.state.camera.y + cfg.tileSize / 2) };
        }
      }
    }
    return null;
  })()`);
  if (!targetCell) throw new Error("no mine target");

  const mined = await evaluate(`(() => {
    const s = window.__sandbox;
    const canvas = document.getElementById('game');
    canvas.dispatchEvent(new PointerEvent('pointermove', { clientX: ${targetCell.sx}, clientY: ${targetCell.sy}, bubbles: true }));
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: ${targetCell.sx}, clientY: ${targetCell.sy}, bubbles: true, button: 0, buttons: 1 }));
    document.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, button: 0 }));
    s.saveNow();
    const cell = s.state.world.data[${targetCell.y} * s.state.world.width + ${targetCell.x}];
    return { cell, counts: { ...s.state.inventory }, save: document.getElementById('saveText').textContent, local: Boolean(window.localStorage) };
  })()`);
  await sleep(300);

  await send("Page.reload", { ignoreCache: true });
  await sleep(1200);
  await waitReady();
  await sleep(500);
  const after = await evaluate(`(() => {
    const s = window.__sandbox;
    return {
      save: document.getElementById('saveText').textContent,
      seed: s.state.seed,
      x: s.player.x,
      counts: { ...s.state.inventory },
      cell: s.state.world.data[${targetCell.y} * s.state.world.width + ${targetCell.x}],
      toast: document.getElementById('toastRail').textContent
    };
  })()`);

  console.log(JSON.stringify({ ok: true, before, targetCell, mined, after }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exitCode = 1;
} finally {
  try { if (ws) ws.close(); } catch (error) { /* ignore */ }
  chrome.kill();
  await sleep(400);
  rmSync(PROFILE, { recursive: true, force: true });
}
