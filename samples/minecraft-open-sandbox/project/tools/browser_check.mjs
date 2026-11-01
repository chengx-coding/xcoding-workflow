#!/usr/bin/env node
/**
 * Interactive browser check for the sandbox game.
 *
 * Uses only Node built-ins. Launches headless Chrome, drives it over the
 * DevTools Protocol with real key and mouse events, asserts the playable loop
 * and persistence, records console errors and network requests, and captures
 * day/night screenshots.
 *
 * Usage:
 *   node tools/browser_check.mjs [--page index.html] [--screenshots DIR]
 *                                [--chrome PATH] [--profile DIR] [--keep]
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROJECT = path.resolve(HERE, "..");
const PLANKS_BLOCK = 11;

function parseArgs(argv) {
  const options = {
    page: path.join(PROJECT, "index.html"),
    screenshots: path.join(os.tmpdir(), "blockhaven-shots-" + process.pid),
    chrome: "",
    profile: "",
    keep: false,
    timeout: 30000
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--page") {
      options.page = path.resolve(argv[++i]);
    } else if (arg === "--screenshots") {
      options.screenshots = path.resolve(argv[++i]);
    } else if (arg === "--chrome") {
      options.chrome = argv[++i];
    } else if (arg === "--profile") {
      options.profile = path.resolve(argv[++i]);
    } else if (arg === "--keep") {
      options.keep = true;
    } else if (arg === "--timeout") {
      options.timeout = Number(argv[++i]);
    } else if (arg === "--help" || arg === "-h") {
      console.log("See the header of tools/browser_check.mjs for usage.");
      process.exit(0);
    } else {
      throw new Error("Unknown argument: " + arg);
    }
  }
  return options;
}

function findChrome(explicit) {
  const candidates = [];
  if (explicit) {
    candidates.push(explicit);
  }
  candidates.push(
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
  );
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error("No Chrome or Edge executable found; pass --chrome");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
    this.handlers = new Map();
    this.closed = false;
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("CDP WebSocket open timed out")), 8000);
      this.socket.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      });
      this.socket.addEventListener("error", (event) => {
        clearTimeout(timer);
        reject(new Error("CDP WebSocket error: " + (event.message || "unknown")));
      });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const entry = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          entry.reject(new Error(message.error.message + " (" + message.error.code + ")"));
        } else {
          entry.resolve(message.result || {});
        }
        return;
      }
      const listeners = this.handlers.get(message.method) || [];
      for (const listener of listeners) {
        listener(message.params || {});
      }
    });
    this.socket.addEventListener("close", () => {
      this.closed = true;
      for (const entry of this.pending.values()) {
        entry.reject(new Error("CDP socket closed"));
      }
      this.pending.clear();
    });
  }

  send(method, params = {}, sessionId) {
    if (this.closed) {
      return Promise.reject(new Error("CDP socket is closed"));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      const message = { id, method, params };
      if (sessionId) {
        message.sessionId = sessionId;
      }
      this.socket.send(JSON.stringify(message));
    });
  }

  on(method, listener) {
    if (!this.handlers.has(method)) {
      this.handlers.set(method, []);
    }
    this.handlers.get(method).push(listener);
  }

  close() {
    this.closed = true;
    if (this.socket) {
      this.socket.close();
    }
  }
}

async function launchChrome(options) {
  const chrome = findChrome(options.chrome);
  const profile = options.profile || fs.mkdtempSync(path.join(os.tmpdir(), "blockhaven-profile-"));
  fs.mkdirSync(profile, { recursive: true });
  const args = [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--mute-audio",
    "--remote-debugging-port=0",
    "--remote-allow-origins=*",
    "--user-data-dir=" + profile,
    "--window-size=960,600",
    "about:blank"
  ];
  const child = spawn(chrome, args, { stdio: "ignore", windowsHide: true });
  const portFile = path.join(profile, "DevToolsActivePort");
  const deadline = Date.now() + 15000;
  while (!fs.existsSync(portFile)) {
    if (Date.now() > deadline) {
      child.kill();
      throw new Error("Chrome did not expose a DevTools port");
    }
    await sleep(120);
  }
  const lines = fs.readFileSync(portFile, "utf8").trim().split(/\r?\n/);
  const port = Number(lines[0]);
  const pathPart = lines[1] || "/devtools/browser";
  return {
    chrome,
    child,
    profile,
    port,
    wsPath: pathPart,
    wsUrl: `ws://127.0.0.1:${port}${pathPart}`
  };
}

function ok(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function main() {
  const options = parseArgs(process.argv);
  ok(fs.existsSync(options.page), "page not found: " + options.page);
  fs.mkdirSync(options.screenshots, { recursive: true });

  const browser = await launchChrome(options);
  const cdp = new Cdp(browser.wsUrl);
  await cdp.connect();

  const consoleErrors = [];
  const networkUrls = [];
  const steps = [];
  let targetId = null;

  cdp.on("Runtime.exceptionThrown", (params) => {
    const details = params.exceptionDetails || {};
    consoleErrors.push(
      "exception: " + (details.exception?.description || details.text || "unknown") +
        " @ " + (details.url || "") + ":" + (details.lineNumber ?? "?")
    );
  });
  cdp.on("Runtime.consoleAPICalled", (params) => {
    if (params.type === "error" || params.type === "assert") {
      consoleErrors.push(
        "console." + params.type + ": " +
          (params.args || []).map((arg) => arg.value ?? arg.description ?? "").join(" ")
      );
    }
  });
  cdp.on("Log.entryAdded", (params) => {
    const entry = params.entry || {};
    if (entry.level === "error") {
      consoleErrors.push("log: " + entry.text + " @ " + (entry.url || ""));
    }
  });
  cdp.on("Network.requestWillBeSent", (params) => {
    if (params.request && params.request.url) {
      networkUrls.push(params.request.url);
    }
  });

  const { targetInfos } = await cdp.send("Target.getTargets");
  const pageTarget = targetInfos.find((target) => target.type === "page");
  ok(pageTarget, "no page target available");
  targetId = pageTarget.targetId;
  const { sessionId } = await cdp.send("Target.attachToTarget", {
    targetId: targetId,
    flatten: true
  });
  const session = {
    send: (method, params) => cdp.send(method, params, sessionId)
  };
  await session.send("Page.enable");
  await session.send("Runtime.enable");
  await session.send("Log.enable");
  await session.send("Network.enable");
  await session.send("Emulation.setDeviceMetricsOverride", {
    width: 960,
    height: 600,
    deviceScaleFactor: 1,
    mobile: false
  });

  async function evaluate(expression) {
    const result = await session.send("Runtime.evaluate", {
      expression: "(() => { " + expression + " })()",
      returnByValue: true,
      awaitPromise: true,
      userGesture: true
    });
    if (result.exceptionDetails) {
      throw new Error(
        "evaluate failed: " +
          (result.exceptionDetails.exception?.description || result.exceptionDetails.text)
      );
    }
    return result.result?.value;
  }

  async function waitFor(expression, timeout, label) {
    const deadline = Date.now() + (timeout || options.timeout);
    let last;
    while (Date.now() < deadline) {
      try {
        last = await evaluate(expression);
        if (last) {
          return last;
        }
      } catch (error) {
        last = String(error);
      }
      await sleep(100);
    }
    throw new Error("timed out waiting for " + (label || expression) + " (last: " + JSON.stringify(last) + ")");
  }

  async function screenshot(name) {
    const result = await session.send("Page.captureScreenshot", { format: "png" });
    const file = path.join(options.screenshots, name);
    fs.writeFileSync(file, Buffer.from(result.data, "base64"));
    return file;
  }

  async function key(type, code, keyValue, vk) {
    await session.send("Input.dispatchKeyEvent", {
      type: type,
      code: code,
      key: keyValue,
      windowsVirtualKeyCode: vk,
      nativeVirtualKeyCode: vk
    });
  }

  async function tapKey(code, keyValue, vk) {
    await key("keyDown", code, keyValue, vk);
    await sleep(40);
    await key("keyUp", code, keyValue, vk);
  }

  async function holdKey(code, keyValue, vk, ms) {
    await key("keyDown", code, keyValue, vk);
    await sleep(ms);
    await key("keyUp", code, keyValue, vk);
    await sleep(60);
  }

  async function mouse(type, x, y, button, buttons) {
    await session.send("Input.dispatchMouseEvent", {
      type: type,
      x: x,
      y: y,
      button: button || "none",
      buttons: buttons || 0,
      clickCount: type === "mousePressed" ? 1 : 0
    });
  }

  async function clickAt(x, y, button) {
    const name = button === "right" ? "right" : "left";
    const mask = button === "right" ? 2 : 1;
    await mouse("mouseMoved", x, y, "none", 0);
    await mouse("mousePressed", x, y, name, mask);
    await sleep(60);
    await mouse("mouseReleased", x, y, name, 0);
    await sleep(120);
  }

  async function elementCenter(selector) {
    return evaluate(`
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2,
               width: rect.width, height: rect.height, disabled: !!el.disabled };
    `);
  }

  async function record(name, fn) {
    try {
      const detail = await fn();
      steps.push({ name: name, ok: true, detail: detail ?? null });
      return detail;
    } catch (error) {
      steps.push({ name: name, ok: false, detail: error.message });
      throw error;
    }
  }

  function assert(condition, message) {
    if (!condition) {
      throw new Error(message);
    }
  }

  const pageUrl = pathToFileURL(options.page).href;

  try {
    await record("boot", async () => {
      await session.send("Page.navigate", { url: pageUrl });
      await waitFor("return !!(window.__sandbox && window.__sandbox.ready)", 15000, "game boot");
      const status = await evaluate("return document.getElementById('status').dataset.state;");
      assert(status === "ready", "status is " + status);
      const dims = await evaluate(
        "return { width: window.__sandbox.world.width, height: window.__sandbox.world.height, slots: document.querySelectorAll('#hotbar .slot').length };"
      );
      assert(dims.width === 192 && dims.height === 96, "unexpected world size " + JSON.stringify(dims));
      assert(dims.slots === 8, "expected 8 hotbar slots, got " + dims.slots);
      return dims;
    });

    await record("no-network", async () => {
      const remote = networkUrls.filter((url) => /^https?:/i.test(url));
      assert(remote.length === 0, "network requests found: " + remote.join(", "));
      return { requests: networkUrls.length, remote: 0 };
    });

    const start = await record("initial-state", async () => {
      const info = await evaluate(`
        const g = window.__sandbox;
        return {
          x: g.player.x, y: g.player.y, onGround: g.player.onGround,
          seed: g.world.seed, persistent: g.storagePersistent
        };
      `);
      assert(Number.isFinite(info.x) && Number.isFinite(info.y), "player position is not finite");
      assert(info.y > 20 && info.y < 96, "player is not in a sensible place: " + info.y);
      return info;
    });
    await screenshot("01-boot-day.png");

    await record("jump", async () => {
      const before = await evaluate("return { y: window.__sandbox.player.y, onGround: window.__sandbox.player.onGround };");
      assert(before.onGround, "player is not on the ground before jumping");
      await key("keyDown", "Space", " ", 32);
      await sleep(160);
      const mid = await evaluate("return { y: window.__sandbox.player.y, onGround: window.__sandbox.player.onGround, jumps: window.__sandbox.jumpCount };");
      await key("keyUp", "Space", " ", 32);
      assert(mid.y < before.y - 0.3, "player did not rise: " + before.y + " -> " + mid.y + " jumps=" + mid.jumps);
      await sleep(900);
      const landed = await evaluate("return { y: window.__sandbox.player.y, onGround: window.__sandbox.player.onGround };");
      assert(landed.onGround, "player did not land after the jump");
      return { rise: before.y - mid.y, landedAt: landed.y };
    });

    await record("move-right", async () => {
      const before = await evaluate("return window.__sandbox.player.x;");
      await holdKey("KeyD", "d", 68, 650);
      const after = await evaluate("return window.__sandbox.player.x;");
      assert(after > before + 0.5, "player did not move right: " + before + " -> " + after);
      return { before, after };
    });

    const tree = await record("mine-tree", async () => {
      await sleep(800);
      const target = await evaluate(`
        const g = window.__sandbox;
        const spawn = g.world.spawn || { x: Math.floor(g.world.width / 2), y: Math.floor(g.world.height * 0.65) };
        let found = null;
        for (let dy = 1; dy <= 4 && !found; dy += 1) {
          const tx = spawn.x + 4;
          const ty = spawn.y - dy;
          if (g.world.data[ty * g.world.width + tx] === g.config.blocks.wood) {
            found = { x: tx, y: ty };
          }
        }
        if (!found) {
          for (let dy = 1; dy <= 3 && !found; dy += 1) {
            for (let dx = 2; dx <= 5 && !found; dx += 1) {
              for (const sx of [1, -1]) {
                const tx = spawn.x + dx * sx;
                const ty = spawn.y - dy;
                const dist = Math.hypot(tx + 0.5 - g.player.x, ty + 0.5 - (g.player.y - g.player.height / 2));
                if (dist <= g.config.reach && g.world.data[ty * g.world.width + tx] === g.config.blocks.wood) {
                  found = { x: tx, y: ty };
                  break;
                }
              }
            }
          }
        }
        if (!found) return null;
        const point = g.tileToClient(found.x, found.y);
        found.clientX = point.x;
        found.clientY = point.y;
        return found;
      `);
      assert(target, "no reachable starter tree trunk found");
      const before = await evaluate("return window.__sandbox.inventory.items;");
      await mouse("mouseMoved", target.clientX, target.clientY, "none", 0);
      await mouse("mousePressed", target.clientX, target.clientY, "left", 1);
      await sleep(300);
      const mid = await evaluate(`
        const g = window.__sandbox;
        return { mouseTile: g.mouseTile, mining: g.miningState, player: g.playerInfo, camera: g.camera };
      `);
      await sleep(800);
      await mouse("mouseReleased", target.clientX, target.clientY, "left", 0);
      await sleep(200);
      const after = await evaluate(`
        const g = window.__sandbox;
        return { items: g.inventory.items, block: g.world.data[${target.y} * g.world.width + ${target.x}] };
      `);
      assert(after.block === 0, "tree block was not removed (block id " + after.block + ", target " + JSON.stringify(target) + ", mid " + JSON.stringify(mid) + ")");
      assert((after.items.wood || 0) >= 1, "no wood collected: " + JSON.stringify(after.items));
      return { target, before, after: after.items };
    });

    await record("craft-planks", async () => {
      await tapKey("KeyE", "e", 69);
      await waitFor("return !document.getElementById('craft-panel').classList.contains('hidden');", 3000, "craft panel");
      const button = await elementCenter('[data-recipe="planks"]');
      assert(button, "planks recipe button missing");
      assert(button.disabled === false, "planks recipe should be craftable after wood");
      await clickAt(button.x, button.y, "left");
      const items = await evaluate("return window.__sandbox.inventory.items;");
      assert((items.planks || 0) === 4, "expected 4 planks, got " + JSON.stringify(items));
      assert((items.wood || 0) === 0, "wood was not consumed");
      await tapKey("KeyE", "e", 69);
      await waitFor("return document.getElementById('craft-panel').classList.contains('hidden');", 3000, "craft panel closed");
      return items;
    });

    const placed = await record("place-planks", async () => {
      await tapKey("Digit4", "4", 52);
      const point = await evaluate(`
        const g = window.__sandbox;
        const spawn = g.world.spawn || { x: Math.floor(g.world.width / 2), y: Math.floor(g.world.height * 0.65) };
        const player = g.player;
        for (let dx = -3; dx <= 3; dx += 1) {
          for (let dy = -3; dy <= 0; dy += 1) {
            const tx = Math.floor(player.x) + dx;
            const ty = Math.floor(player.y) + dy;
            if (tx < 0 || ty < 0 || tx >= g.world.width || ty >= g.world.height) continue;
            if (g.world.data[ty * g.world.width + tx] !== 0) continue;
            const left = player.x - player.width / 2, right = player.x + player.width / 2;
            const top = player.y - player.height, bottom = player.y;
            if (tx < right && tx + 1 > left && ty < bottom && ty + 1 > top) continue;
            const p = g.tileToClient(tx, ty);
            if (p.x < 4 || p.y < 4) continue;
            return { x: tx, y: ty, clientX: p.x, clientY: p.y };
          }
        }
        return null;
      `);
      if (!point) {
        throw new Error("no free reachable tile for placement");
      }
      await clickAt(point.clientX, point.clientY, "right");
      const after = await evaluate(`
        const g = window.__sandbox;
        return { block: g.world.data[${point.y} * g.world.width + ${point.x}], items: g.inventory.items };
      `);
      assert(after.block === PLANKS_BLOCK, "expected planks block in the world");
      assert((after.items.planks || 0) === 3, "expected 3 planks left, got " + JSON.stringify(after.items));
      return { point, block: after.block, items: after.items }; 
    });

    await record("help-overlay", async () => {
      await tapKey("KeyH", "h", 72);
      await waitFor("return !document.getElementById('help-panel').classList.contains('hidden');", 3000, "help panel");
      const rows = await evaluate("return document.querySelectorAll('#help-controls .keycap').length;");
      assert(rows >= 8, "expected at least 8 documented controls, got " + rows);
      await tapKey("Escape", "Escape", 27);
      await waitFor("return document.getElementById('help-panel').classList.contains('hidden');", 3000, "help closed");
      return { rows };
    });

    await record("pause-save", async () => {
      await tapKey("Escape", "Escape", 27);
      await waitFor("return !document.getElementById('pause-panel').classList.contains('hidden');", 3000, "pause panel");
      const button = await elementCenter('[data-action="save"]');
      assert(button, "save button missing");
      await clickAt(button.x, button.y, "left");
      const saved = await evaluate(`
        try { return !!localStorage.getItem('small-minecraft-save-v1'); }
        catch (error) { return 'storage-error:' + error.message; }
      `);
      assert(saved === true, "save did not write localStorage: " + saved);
      await screenshot("02-pause.png");
      await tapKey("Escape", "Escape", 27);
      await waitFor("return document.getElementById('pause-panel').classList.contains('hidden');", 3000, "pause closed");
      return { saved };
    });

    const beforeReload = await evaluate(`
      const g = window.__sandbox;
      const spawn = g.world.spawn;
      return { x: g.player.x, y: g.player.y, items: g.inventory.items, seed: g.world.seed };
    `);

    await record("reload-persistence", async () => {
      await evaluate("window.__reloadToken = 'reload-in-progress'; return 1;");
      await session.send("Page.reload", { ignoreCache: true });
      await waitFor(
        "return !window.__reloadToken && !!(window.__sandbox && window.__sandbox.ready)",
        20000,
        "reload boot"
      );
      const after = await evaluate(`
        const g = window.__sandbox;
        return {
          x: g.player.x, items: g.inventory.items, seed: g.world.seed,
          placed: g.world.data[${placed.point.y} * g.world.width + ${placed.point.x}]
        };
      `);
      assert(after.seed === beforeReload.seed, "seed changed after reload");
      assert(Math.abs(after.x - beforeReload.x) < 0.2, "player position was not restored");
      assert((after.items.planks || 0) === 3, "inventory was not restored: " + JSON.stringify(after.items));
      assert(after.placed === PLANKS_BLOCK, "placed block was not restored");
      return after;
    });

    await record("day-night-light", async () => {
      const daySky = await evaluate("return window.__sandbox.setTimeOfDay(0.25);");
      await sleep(120);
      const dayBrightness = await evaluate(`
        const canvas = document.getElementById('game');
        const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        let sum = 0, count = 0;
        for (let i = 0; i < data.length; i += 4 * 61) { sum += (data[i] + data[i + 1] + data[i + 2]) / 3; count += 1; }
        return sum / count;
      `);
      await screenshot("03-day.png");
      const nightSky = await evaluate("return window.__sandbox.setTimeOfDay(0.78);");
      await sleep(120);
      const nightBrightness = await evaluate(`
        const canvas = document.getElementById('game');
        const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        let sum = 0, count = 0;
        for (let i = 0; i < data.length; i += 4 * 61) { sum += (data[i] + data[i + 1] + data[i + 2]) / 3; count += 1; }
        return sum / count;
      `);
      await screenshot("04-night.png");
      assert(nightSky < daySky, "night sky level should be lower than day");
      assert(nightBrightness < dayBrightness - 15, "night frame is not visibly darker: " + dayBrightness + " -> " + nightBrightness);
      return { daySky, nightSky, dayBrightness, nightBrightness };
    });

    await record("responsive-mapping", async () => {
      await session.send("Emulation.setDeviceMetricsOverride", {
        width: 1280,
        height: 720,
        deviceScaleFactor: 1,
        mobile: false
      });
      await sleep(150);
      const geometry = await evaluate(`
        const canvas = document.getElementById('game');
        const rect = canvas.getBoundingClientRect();
        const g = window.__sandbox;
        const p = g.tileToClient(Math.floor(g.player.x), Math.floor(g.player.y) - 1);
        return {
          rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
          point: p,
          viewport: { width: window.innerWidth, height: window.innerHeight }
        };
      `);
      assert(geometry.rect.width <= 960.5, "canvas grew beyond its design width");
      assert(geometry.point.x >= geometry.rect.left && geometry.point.x <= geometry.rect.left + geometry.rect.width,
        "tile mapping is outside the canvas");
      assert(geometry.point.y >= geometry.rect.top && geometry.point.y <= geometry.rect.top + geometry.rect.height,
        "tile mapping is outside the canvas vertically");
      await session.send("Emulation.setDeviceMetricsOverride", {
        width: 960,
        height: 600,
        deviceScaleFactor: 1,
        mobile: false
      });
      await sleep(150);
      return geometry;
    });

    await record("audio-mute", async () => {
      await tapKey("KeyM", "m", 77);
      await sleep(120);
      const muted = await evaluate("return document.getElementById('toast').textContent;");
      assert(/muted/i.test(muted), "mute toast missing: " + muted);
      await tapKey("KeyM", "m", 77);
      await sleep(120);
      const unmuted = await evaluate("return document.getElementById('toast').textContent;");
      assert(/audio on/i.test(unmuted), "unmute toast missing: " + unmuted);
      return { muted, unmuted };
    });

    await record("new-world", async () => {
      const before = await evaluate("return { seed: window.__sandbox.world.seed, x: window.__sandbox.player.x };");
      await tapKey("Escape", "Escape", 27);
      await waitFor("return !document.getElementById('pause-panel').classList.contains('hidden');", 3000, "pause panel");
      const button = await elementCenter('[data-action="new-world"]');
      assert(button, "new world button missing");
      await clickAt(button.x, button.y, "left");
      const armed = await evaluate("return document.querySelector('[data-action=\"new-world\"]').textContent;");
      assert(/confirm/i.test(armed), "new world did not ask for confirmation: " + armed);
      await clickAt(button.x, button.y, "left");
      await sleep(400);
      const after = await evaluate(`
        const g = window.__sandbox;
        return {
          seed: g.world.seed,
          x: g.player.x,
          y: g.player.y,
          pauseHidden: document.getElementById('pause-panel').classList.contains('hidden')
        };
      `);
      assert(after.seed !== before.seed, "new world kept the old seed");
      assert(after.pauseHidden, "pause panel stayed open after a new world");
      assert(after.y > 0 && after.y < 96, "new world player has no sensible position");
      return { before, after };
    });

    await record("console-clean", async () => {
      assert(consoleErrors.length === 0, "console/runtime errors: " + consoleErrors.join(" | "));
      const status = await evaluate("return document.getElementById('status').dataset.state;");
      assert(status === "ready", "final status is " + status);
      return { errors: 0 };
    });

    const result = {
      ok: true,
      page: pageUrl,
      screenshots: options.screenshots,
      steps: steps,
      consoleErrors: consoleErrors,
      networkRequests: networkUrls.length,
      remoteRequests: networkUrls.filter((url) => /^https?:/i.test(url))
    };
    console.log(JSON.stringify(result, null, 2));
    return 0;
  } catch (error) {
    const result = {
      ok: false,
      page: pageUrl,
      error: error.message,
      screenshots: options.screenshots,
      steps: steps,
      consoleErrors: consoleErrors,
      networkRequests: networkUrls.length,
      remoteRequests: networkUrls.filter((url) => /^https?:/i.test(url))
    };
    console.log(JSON.stringify(result, null, 2));
    return 1;
  } finally {
    cdp.close();
    try {
      browser.child.kill();
    } catch (killError) {
      // ignore
    }
    if (!options.keep && !options.profile) {
      await sleep(300);
      try {
        fs.rmSync(browser.profile, { recursive: true, force: true });
      } catch (cleanupError) {
        // ignore
      }
    }
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
