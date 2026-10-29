import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const TMP = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp";
const PROFILE = `${TMP}\\chrome-capture-profile`;
const PORT = 9557;

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
    "--window-size=1200,760",
    PAGE
  ],
  { stdio: "ignore" }
);

async function getJson(path) {
  const response = await fetch(`http://127.0.0.1:${PORT}${path}`);
  return response.json();
}

async function waitTarget() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
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

function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url);
    socket.addEventListener("open", () => resolve(socket));
    socket.addEventListener("error", reject);
  });
}

let ws;
try {
  const target = await waitTarget();
  ws = await connect(target.webSocketDebuggerUrl);
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
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text);
    }
    return result.result.value;
  }
  async function waitReady() {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const ready = await evaluate("Boolean(window.__sandbox && window.__sandbox.ready)");
      if (ready) return;
      await sleep(120);
    }
    throw new Error("not ready");
  }
  async function capture(name) {
    const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(`${TMP}\\${name}`, Buffer.from(result.data, "base64"));
    return name;
  }

  await send("Runtime.enable");
  await send("Page.enable");
  await waitReady();
  await sleep(400);

  const cells = await evaluate(`(() => {
    const s = window.__sandbox;
    const world = s.world;
    const scene = s.state;
    const cfg = window.SandboxConfig;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const px = Math.floor(scene.player.x);
    const py = Math.floor(scene.player.y);
    let solid = null;
    let empty = null;
    for (let dx = -3; dx <= 4 && !solid; dx += 1) {
      if (Math.abs(dx) < 2) continue;
      for (let dy = -1; dy <= 1 && !solid; dy += 1) {
        const cx = px + dx; const cy = py + dy;
        if (cx >= 0 && cy >= 0 && cx < world.width && cy < world.height && world.data[cy * world.width + cx] !== 0) {
          solid = { x: cx, y: cy };
        }
      }
    }
    for (let dx = 2; dx <= 3 && !empty; dx += 1) {
      const cx = px + dx;
      const cy = window.SandboxWorld.surfaceHeightAt(world, cx) - 1;
      if (cx >= 0 && cy >= 0 && cx < world.width && cy < world.height && world.data[cy * world.width + cx] === 0) {
        empty = { x: cx, y: cy };
      }
    }
    function screenOf(cell) {
      return { x: rect.left + cell.x * cfg.tileSize - s.camera.x + cfg.tileSize / 2, y: rect.top + cell.y * cfg.tileSize - s.camera.y + cfg.tileSize / 2 };
    }
    return { solid, empty, solidScreen: solid ? screenOf(solid) : null, emptyScreen: empty ? screenOf(empty) : null };
  })()`);

  if (cells.solidScreen) {
    await evaluate(`(() => {
      const canvas = document.getElementById('game');
      canvas.dispatchEvent(new PointerEvent('pointermove', { clientX: ${cells.solidScreen.x}, clientY: ${cells.solidScreen.y}, bubbles: true }));
    })()`);
    await sleep(300);
    await capture("visual-hover-mine.png");
  }

  if (cells.emptyScreen) {
    await evaluate(`(() => {
      document.querySelectorAll('#hotbar .slot')[7].click();
      const canvas = document.getElementById('game');
      canvas.dispatchEvent(new PointerEvent('pointermove', { clientX: ${cells.emptyScreen.x}, clientY: ${cells.emptyScreen.y}, bubbles: true }));
    })()`);
    await sleep(350);
    await capture("visual-hover-place.png");
  }

  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(450);
  await capture("visual-overlay.png");

  console.log(JSON.stringify({ ok: true, cells }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exitCode = 1;
} finally {
  try {
    if (ws) ws.close();
  } catch (error) {
    // ignore
  }
  chrome.kill();
  await sleep(300);
  rmSync(PROFILE, { recursive: true, force: true });
}
