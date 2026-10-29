import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const TMP = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp";
const PROFILE = `${TMP}\\chrome-probe-profile`;
const PORT = 9555;

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

const checks = [];
const consoleErrors = [];
let ws;

function check(name, ok, detail) {
  checks.push({ name, ok: Boolean(ok), detail });
}

async function getJson(path) {
  const response = await fetch(`http://127.0.0.1:${PORT}${path}`);
  return response.json();
}

async function waitForTarget() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const list = await getJson("/json/list");
      const target = list.find((item) => item.type === "page" && item.url.startsWith("file:"));
      if (target) {
        return target;
      }
    } catch (error) {
      // Chrome is still starting.
    }
    await sleep(250);
  }
  throw new Error("no debuggable page target appeared");
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url);
    socket.addEventListener("open", () => resolve(socket));
    socket.addEventListener("error", reject);
  });
}

function makeClient(socket) {
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") {
      consoleErrors.push(message.params.exceptionDetails.text || "exception");
    }
    if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
      consoleErrors.push(message.params.args.map((arg) => arg.value || arg.description).join(" "));
    }
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        entry.reject(new Error(JSON.stringify(message.error)));
      } else {
        entry.resolve(message.result);
      }
    }
  });
  return {
    send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = ++nextId;
        pending.set(id, { resolve, reject });
        socket.send(JSON.stringify({ id, method, params }));
      });
    }
  };
}

async function main() {
  const target = await waitForTarget();
  ws = await connect(target.webSocketDebuggerUrl);
  const client = makeClient(ws);
  await client.send("Runtime.enable");
  await client.send("Page.enable");
  await client.send("Log.enable");

  async function evaluate(expression) {
    const result = await client.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (result.exceptionDetails) {
      throw new Error(
        `${result.exceptionDetails.text}: ${
          result.exceptionDetails.exception ? result.exceptionDetails.exception.description : ""
        }`
      );
    }
    return result.result.value;
  }

  async function waitReady() {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const status = await evaluate(
        "(() => { const marker = document.getElementById('status'); return { state: marker ? marker.dataset.state : '', ready: Boolean(window.__sandbox && window.__sandbox.ready) }; })()"
      );
      if (status.state === "ready" && status.ready) {
        return true;
      }
      await sleep(120);
    }
    return false;
  }

  check("page reached ready state", await waitReady(), "status marker + window.__sandbox.ready");

  const storage = await evaluate(
    "(() => { try { const key = 'xc-sandbox-terra-v1'; const probe = '__probe__'; localStorage.setItem(probe, '1'); const ok = localStorage.getItem(probe) === '1'; localStorage.removeItem(probe); return { available: ok, key: key }; } catch (error) { return { available: false, error: String(error) }; } })()"
  );
  check("localStorage usable under file://", storage.available, JSON.stringify(storage));

  const initial = await evaluate(
    "(() => { const s = window.__sandbox; return { seed: s.world.seed, x: s.state.player.x, y: s.state.player.y, hotbar: s.state.hotbarIndex, slots: document.querySelectorAll('#hotbar .slot').length, selected: document.querySelectorAll('#hotbar .slot.is-selected').length }; })()"
  );
  check("hotbar has at least four slots", initial.slots >= 4, `slots=${initial.slots}`);
  check("one hotbar slot is selected", initial.selected === 1, `selected=${initial.selected}`);

  const jump = await evaluate(`(async () => {
    const s = window.__sandbox;
    const before = s.state.player.y;
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 180));
    window.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
    const apex = s.state.player.y;
    await new Promise((resolve) => setTimeout(resolve, 900));
    return { before, apex, after: s.state.player.y, onGround: s.state.player.onGround };
  })()`);
  check("space launches the player", jump.apex < jump.before - 0.2, JSON.stringify(jump));
  check("the player lands again", jump.onGround === true, JSON.stringify(jump));

  const mined = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const world = s.world;
    const scene = s.state;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const px = Math.floor(scene.player.x);
    const py = Math.floor(scene.player.y);
    let target = null;
    for (let dx = -4; dx <= 4 && !target; dx += 1) {
      if (Math.abs(dx) < 2) continue;
      for (let dy = -2; dy <= 2 && !target; dy += 1) {
        const cx = px + dx;
        const cy = py + dy;
        if (cx < 0 || cy < 0 || cx >= world.width || cy >= world.height) continue;
        if (world.data[cy * world.width + cx] === 0) continue;
        const solidNeighbour = [[1,0],[-1,0],[0,1],[0,-1]].some(([ox, oy]) => {
          const nx = cx + ox; const ny = cy + oy;
          return nx >= 0 && ny >= 0 && nx < world.width && ny < world.height && world.data[ny * world.width + nx] !== 0;
        });
        if (solidNeighbour) target = { x: cx, y: cy };
      }
    }
    if (!target) return { ok: false, reason: 'no solid target near the player' };
    const before = world.data[target.y * world.width + target.x];
    const countBefore = scene.inventory[before] || 0;
    const sx = rect.left + target.x * cfg.tileSize - s.camera.x + cfg.tileSize / 2;
    const sy = rect.top + target.y * cfg.tileSize - s.camera.y + cfg.tileSize / 2;
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: sx, clientY: sy, button: 0, bubbles: true }));
    document.dispatchEvent(new PointerEvent('pointerup', { clientX: sx, clientY: sy, button: 0, bubbles: true }));
    const after = world.data[target.y * world.width + target.x];
    const countAfter = scene.inventory[before] || 0;
    return { ok: after === 0, target, before, after, countBefore, countAfter };
  })()`);
  check("left click mines a reachable block", mined.ok, JSON.stringify(mined));
  check(
    "mining adds the block to the inventory",
    mined.countAfter === mined.countBefore + 1,
    JSON.stringify({ before: mined.countBefore, after: mined.countAfter })
  );

  const placed = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const world = s.world;
    const scene = s.state;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const slots = document.querySelectorAll('#hotbar .slot');
    slots[2].click();
    const selected = cfg.hotbar[scene.hotbarIndex];
    const target = ${JSON.stringify(mined.target || null)};
    if (!target) return { ok: false, reason: 'no target' };
    const countBefore = scene.inventory[selected] || 0;
    const sx = rect.left + target.x * cfg.tileSize - s.camera.x + cfg.tileSize / 2;
    const sy = rect.top + target.y * cfg.tileSize - s.camera.y + cfg.tileSize / 2;
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: sx, clientY: sy, button: 2, bubbles: true }));
    document.dispatchEvent(new PointerEvent('pointerup', { clientX: sx, clientY: sy, button: 2, bubbles: true }));
    const after = world.data[target.y * world.width + target.x];
    const countAfter = scene.inventory[selected] || 0;
    return { ok: after === selected, target, selected, after, countBefore, countAfter, hotbar: scene.hotbarIndex };
  })()`);
  check("right click places the selected block", placed.ok, JSON.stringify(placed));
  check(
    "placing spends one inventory item",
    placed.countAfter === placed.countBefore - 1,
    JSON.stringify({ before: placed.countBefore, after: placed.countAfter })
  );
  check("number-key/click selection changed the hotbar", placed.hotbar === 2, `hotbarIndex=${placed.hotbar}`);

  const inside = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const world = s.world;
    const scene = s.state;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const cell = { x: Math.floor(scene.player.x), y: Math.floor(scene.player.y) - 1 };
    const before = world.data[cell.y * world.width + cell.x];
    const sx = rect.left + cell.x * cfg.tileSize - s.camera.x + cfg.tileSize / 2;
    const sy = rect.top + cell.y * cfg.tileSize - s.camera.y + cfg.tileSize / 2;
    const guard = window.SandboxWorld.canPlaceBlock(world, scene.player, cell.x, cell.y, cfg.reach);
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: sx, clientY: sy, button: 2, bubbles: true }));
    document.dispatchEvent(new PointerEvent('pointerup', { clientX: sx, clientY: sy, button: 2, bubbles: true }));
    const after = world.data[cell.y * world.width + cell.x];
    return { before, after, guard };
  })()`);
  check("blocks cannot be placed inside the player", inside.after === 0 && inside.guard.reason === "player", JSON.stringify(inside));

  const far = await evaluate(`(() => {
    const s = window.__sandbox;
    const cfg = window.SandboxConfig;
    const world = s.world;
    const scene = s.state;
    const canvas = document.getElementById('game');
    const rect = canvas.getBoundingClientRect();
    const px = Math.floor(scene.player.x);
    const py = Math.floor(scene.player.y);
    let target = null;
    for (let dx = 8; dx <= 20 && !target; dx += 1) {
      for (const dy of [0, -1, 1]) {
        const cx = px + dx;
        const cy = py + dy;
        if (cx < 0 || cy < 0 || cx >= world.width || cy >= world.height) continue;
        if (world.data[cy * world.width + cx] !== 0) {
          target = { x: cx, y: cy };
          break;
        }
      }
    }
    if (!target) return { ok: false, reason: 'no far solid target' };
    const before = world.data[target.y * world.width + target.x];
    const sx = rect.left + target.x * cfg.tileSize - s.camera.x + cfg.tileSize / 2;
    const sy = rect.top + target.y * cfg.tileSize - s.camera.y + cfg.tileSize / 2;
    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX: sx, clientY: sy, button: 0, bubbles: true }));
    document.dispatchEvent(new PointerEvent('pointerup', { clientX: sx, clientY: sy, button: 0, bubbles: true }));
    const after = world.data[target.y * world.width + target.x];
    return { ok: after === before, target, before, after };
  })()`);
  check("mining is refused beyond reach", far.ok, JSON.stringify(far));

  const saved = await evaluate(`(() => {
    const s = window.__sandbox;
    s.saveNow();
    const raw = localStorage.getItem('xc-sandbox-terra-v1');
    const parsed = raw ? JSON.parse(raw) : null;
    return {
      exists: Boolean(raw),
      version: parsed ? parsed.version : null,
      player: parsed ? parsed.player : null,
      cells: parsed ? parsed.world.data.length : 0,
      chip: document.getElementById('saveChip').dataset.state
    };
  })()`);
  check("save writes a versioned payload", saved.exists && saved.version === 1 && saved.cells > 0, JSON.stringify(saved));
  check("save indicator reports a successful save", saved.chip === "saved", `chip=${saved.chip}`);

  const expected = placed.target;
  const expectedBlock = placed.selected;
  const playerBeforeReload = await evaluate("(() => ({ x: window.__sandbox.state.player.x, y: window.__sandbox.state.player.y }))()");

  await client.send("Page.reload", { ignoreCache: true });
  const readyAgain = await waitReady();
  check("page reloads into the ready state", readyAgain, "second ready");

  const restored = await evaluate(`(() => {
    const s = window.__sandbox;
    const world = s.world;
    const target = ${JSON.stringify(expected)};
    return {
      x: s.state.player.x,
      y: s.state.player.y,
      block: world.data[target.y * world.width + target.x],
      selected: ${JSON.stringify(expectedBlock)},
      seed: world.seed
    };
  })()`);
  check(
    "player position survives a reload",
    Math.abs(restored.x - playerBeforeReload.x) < 0.2 && Math.abs(restored.y - playerBeforeReload.y) < 0.3,
    JSON.stringify({ before: playerBeforeReload, after: { x: restored.x, y: restored.y } })
  );
  check("the placed block survives a reload", restored.block === restored.selected, JSON.stringify(restored));

  const overlay = await evaluate(`(async () => {
    const s = window.__sandbox;
    document.getElementById('helpBtn').click();
    const opened = !document.getElementById('overlay').hidden && s.state.paused;
    await new Promise((resolve) => setTimeout(resolve, 120));
    document.getElementById('overlayClose').click();
    const closed = document.getElementById('overlay').hidden && !s.state.paused;
    return { opened, closed };
  })()`);
  check("the field guide opens and closes", overlay.opened && overlay.closed, JSON.stringify(overlay));

  const seedChange = await evaluate(`(async () => {
    const s = window.__sandbox;
    document.getElementById('helpBtn').click();
    const input = document.getElementById('seedInput');
    input.value = '777001';
    document.getElementById('seedApply').click();
    await new Promise((resolve) => setTimeout(resolve, 400));
    const world = s.world;
    return {
      seed: world.seed,
      label: document.getElementById('seedValue').textContent,
      paused: s.state.paused,
      dataLength: world.data.length
    };
  })()`);
  check("a new seed regenerates the world and closes the guide", seedChange.seed === 777001 && seedChange.label === "777001" && !seedChange.paused, JSON.stringify(seedChange));

  check("no console errors or uncaught exceptions", consoleErrors.length === 0, JSON.stringify(consoleErrors));

  const failed = checks.filter((entry) => !entry.ok);
  console.log(JSON.stringify({ ok: failed.length === 0, checks, consoleErrors }, null, 2));
  process.exitCode = failed.length === 0 ? 0 : 1;
}

try {
  await main();
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error), checks, consoleErrors }, null, 2));
  process.exitCode = 1;
} finally {
  try {
    if (ws) {
      ws.close();
    }
  } catch (error) {
    // ignore
  }
  chrome.kill();
  await sleep(300);
  rmSync(PROFILE, { recursive: true, force: true });
}
