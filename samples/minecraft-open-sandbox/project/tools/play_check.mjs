#!/usr/bin/env node
/*
 * Dependency-free Chrome DevTools Protocol smoke/play check.
 *
 * Launches headless Chrome with an isolated profile, drives trusted keyboard
 * and pointer input, captures screenshots, and reports a JSON result. Node's
 * built-in WebSocket and fetch are used; no packages are required.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
function arg(name, fallback) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
}

const pagePath = resolve(arg("--page", "index.html"));
const outDir = resolve(arg("--out", "playcheck"));
const chromePath = arg("--chrome", process.env.CHROME || "google-chrome");
const keepOpen = args.includes("--keep-open");
mkdirSync(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms));

class Cdp {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve: done, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message));
        else done(message.result);
      } else if (message.method) {
        const handlers = this.events.get(message.method) || [];
        for (const handler of handlers) handler(message.params);
      }
    });
  }
  on(method, handler) {
    if (!this.events.has(method)) this.events.set(method, []);
    this.events.get(method).push(handler);
  }
  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolvePromise, reject) => {
      this.pending.set(id, { resolve: resolvePromise, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function waitForFile(path, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (existsSync(path)) return;
    await sleep(50);
  }
  throw new Error("timed out waiting for " + path);
}

async function launch() {
  const profile = mkdtempSync(join(tmpdir(), "xc-play-"));
  mkdirSync(join(profile, "home", ".local", "share"), { recursive: true });
  mkdirSync(join(profile, "tmp"), { recursive: true });
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--mute-audio",
    "--remote-debugging-port=0",
    "--user-data-dir=" + join(profile, "chrome"),
    "--window-size=960,600",
    pathToFileURL(pagePath).href
  ], {
    env: {
      ...process.env,
      HOME: join(profile, "home"),
      TMPDIR: join(profile, "tmp"),
      XDG_CONFIG_HOME: join(profile, "home", ".config"),
      XDG_CACHE_HOME: join(profile, "home", ".cache"),
      XDG_DATA_HOME: join(profile, "home", ".local", "share")
    },
    stdio: ["ignore", "ignore", "pipe"]
  });
  let stderr = "";
  chrome.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  const portFile = join(profile, "chrome", "DevToolsActivePort");
  await waitForFile(portFile, 15000);
  const [port] = readFileSync(portFile, "utf8").trim().split("\n");
  const list = await (await fetch("http://127.0.0.1:" + port + "/json/list")).json();
  const target = list.find((entry) => entry.type === "page" && entry.webSocketDebuggerUrl);
  if (!target) throw new Error("no page target; chrome stderr: " + stderr.slice(-500));
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    socket.addEventListener("open", resolvePromise, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  return { chrome, profile, cdp: new Cdp(socket) };
}

async function main() {
  const { chrome, profile, cdp } = await launch();
  const exceptions = [];
  const consoleErrors = [];
  const requests = [];
  cdp.on("Runtime.exceptionThrown", (params) => {
    exceptions.push(params.exceptionDetails && params.exceptionDetails.text ? params.exceptionDetails.text : "exception");
  });
  cdp.on("Runtime.consoleAPICalled", (params) => {
    if (params.type === "error") {
      consoleErrors.push((params.args || []).map((a) => a.value || a.description || "").join(" "));
    }
  });
  cdp.on("Log.entryAdded", (params) => {
    if (params.entry && params.entry.level === "error") consoleErrors.push(params.entry.text);
  });
  cdp.on("Network.requestWillBeSent", (params) => requests.push(params.request.url));

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Network.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false });

  async function evaluate(expression) {
    const result = await cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
      userGesture: true
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text + " " + (result.exceptionDetails.exception && result.exceptionDetails.exception.description || ""));
    }
    return result.result.value;
  }

  async function waitReady() {
    const started = Date.now();
    while (Date.now() - started < 20000) {
      try {
        if (await evaluate("Boolean(window.__sandbox && window.__sandbox.ready)")) return;
      } catch (error) {
        // Page may still be loading.
      }
      await sleep(100);
    }
    throw new Error("page did not become ready");
  }

  async function screenshot(name) {
    const result = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    const path = join(outDir, name + ".png");
    writeFileSync(path, Buffer.from(result.data, "base64"));
    return path;
  }

  async function rect(selector) {
    return evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; })()`);
  }

  async function clickPoint(x, y, button = "left") {
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, button: "none", buttons: 0 });
    await sleep(60);
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button, buttons: button === "left" ? 1 : 2, clickCount: 1 });
    await sleep(110);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button, buttons: 0, clickCount: 1 });
  }

  async function clickSelector(selector) {
    const box = await rect(selector);
    if (!box) throw new Error("missing selector " + selector);
    await clickPoint(box.x + box.w / 2, box.y + box.h / 2);
    return box;
  }

  async function key(code, keyValue, down) {
    const vk = keyValue.length === 1 ? keyValue.toUpperCase().charCodeAt(0) : keyValue === " " ? 32 : 0;
    await cdp.send("Input.dispatchKeyEvent", {
      type: down ? "keyDown" : "keyUp",
      code,
      key: keyValue,
      windowsVirtualKeyCode: vk,
      nativeVirtualKeyCode: vk
    });
  }

  async function holdKey(code, keyValue, ms) {
    await key(code, keyValue, true);
    await sleep(ms);
    await key(code, keyValue, false);
    await sleep(100);
  }

  const report = { ok: false, page: pagePath, screenshots: [], results: {}, errors: [], requests: [] };

  try {
    await waitReady();
    report.screenshots.push(await screenshot("01-title"));
    report.results.title = await evaluate("(() => { const g=window.__sandbox.game; return {mode:g.mode, seed:g.seed, titleVisible:document.getElementById('title-screen').classList.contains('is-open')}; })()");

    await clickSelector("#btn-new-world");
    await sleep(500);
    report.results.started = await evaluate("(() => { const g=window.__sandbox.game; return {mode:g.mode, x:g.player.x, y:g.player.y, onGround:g.player.onGround, hb:document.querySelectorAll('#hotbar .hotbar-slot').length}; })()");
    report.screenshots.push(await screenshot("02-surface"));

    const beforeX = await evaluate("window.__sandbox.game.player.x");
    const blockedRight = await evaluate("(() => { const g=window.__sandbox.game, P=window.__sandbox.player; return P.overlapsSolid(g.world, g.player.x + 0.8, g.player.y, g.player.width, g.player.height); })()");
    await holdKey(blockedRight ? "KeyA" : "KeyD", blockedRight ? "a" : "d", 600);
    const afterX = await evaluate("window.__sandbox.game.player.x");
    report.results.walk = { before: beforeX, after: afterX, moved: Math.abs(afterX - beforeX) > 0.25, blockedRight };

    const target = await evaluate(`(() => {
      const g = window.__sandbox.game, w = window.__sandbox.world, p = g.player, T = 24, cam = g.camera;
      const px = Math.floor(p.x), py = Math.floor(p.y);
      for (let r = 1; r <= 4; r++) {
        for (const dx of [r, -r, 0]) {
          const x = px + dx, y = py;
          if (w.getBlock(g.world, x, y) && w.getBlock(g.world, x, y) !== 0) {
            const sx = (x + 0.5) * T - cam.x, sy = (y + 0.5) * T - cam.y;
            return {x, y, screenX: sx, screenY: sy, block: w.getBlock(g.world, x, y)};
          }
        }
      }
      return null;
    })()`);
    report.results.target = target;
    if (target) {
      const canvas = await rect("#game");
      const sx = canvas.x + target.screenX * (canvas.w / 960);
      const sy = canvas.y + target.screenY * (canvas.h / 540);
      await clickPoint(sx, sy);
      await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: sx, y: sy, button: "left", buttons: 1, clickCount: 1 });
      await sleep(1400);
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: sx, y: sy, button: "left", buttons: 0, clickCount: 1 });
      await sleep(250);
      report.results.mine = await evaluate(`(() => {
        const g = window.__sandbox.game;
        return {blockNow: window.__sandbox.world.getBlock(g.world, ${target.x}, ${target.y}), selected: g.inventory.selected, slot0: g.inventory.slots[0] ? {id:g.inventory.slots[0].id,count:g.inventory.slots[0].count} : null};
      })()`);
      report.screenshots.push(await screenshot("03-after-mine"));
      report.results.audio = await evaluate("(() => { const a=window.__sandbox.audio; return {unlocked:a.isUnlocked(), enabled:a.isEnabled()}; })()");
    }

    await holdKey("KeyE", "e", 120);
    await sleep(300);
    report.results.inventory = await evaluate("(() => { const g=window.__sandbox.game; return {mode:g.mode, grid:document.querySelectorAll('#inventory-grid .inventory-slot').length, hotbar:document.querySelectorAll('#inventory-hotbar .inventory-slot').length, recipes:document.querySelectorAll('#recipe-list .recipe').length, craftStatus:document.getElementById('craft-status').textContent}; })()");
    report.screenshots.push(await screenshot("04-inventory"));
    await holdKey("KeyE", "e", 120);
    await sleep(200);

    report.results.hotbarClicks = [];
    if (await evaluate("window.__sandbox.game.mode === 'playing'")) {
      const slots = await evaluate("Array.from(document.querySelectorAll('#hotbar .hotbar-slot')).slice(0,5).map(el=>{const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})");
      for (let i = 0; i < Math.min(5, slots.length); i += 1) {
        await clickPoint(slots[i].x, slots[i].y);
        await sleep(100);
        const selected = await evaluate("window.__sandbox.game.inventory.selected");
        const hit = await evaluate(`(() => { const el = document.elementFromPoint(${slots[i].x}, ${slots[i].y}); return el ? (el.className || el.tagName) : null; })()`);
        report.results.hotbarClicks.push({ index: i, selected, hit });
      }
    }


    if (args.includes("--full")) {
      const B = await evaluate("window.__sandbox.config.blocks");
      const ID = await evaluate("window.__sandbox.config.itemIds");
      async function addItems(entries) {
        return evaluate(`(() => { const g = window.__sandbox.game; const inv = g.inventory; const entries = ${JSON.stringify(entries)}; for (const [id, count] of entries) window.__sandbox.inventory.addItem(inv, id, count); window.__sandbox.refreshHud(); if (window.__sandbox.ui.isOpen()) window.__sandbox.ui.refresh(); return true; })()`);
      }
      async function recipe(id) {
        await clickSelector(`#inventory-screen [data-recipe="${id}"]`);
        await sleep(160);
      }
      async function openInventory() {
        await holdKey("KeyE", "e", 80);
        await sleep(260);
      }
      async function closePanelKey(code, keyValue) {
        await holdKey(code, keyValue, 80);
        await sleep(220);
      }
      async function findPlacement() {
        return evaluate(`(() => {
          const g = window.__sandbox.game, P = window.__sandbox.player, W = window.__sandbox.world;
          const stack = window.__sandbox.inventory.selectedStack(g.inventory);
          if (!stack) return null;
          const def = window.__sandbox.config.itemDefs[stack.id];
          if (!def || !def.place) return null;
          const T = 24, px = Math.floor(g.player.x), py = Math.floor(g.player.y);
          for (let r = 1; r <= 3; r++) {
            for (let dy = -1; dy <= 1; dy++) {
              for (let dx = -r; dx <= r; dx++) {
                const x = px + dx, y = py + dy;
                if (W.getBlock(g.world, x, y) !== 0) continue;
                const check = P.validatePlacement(g.world, g.player, x, y, def.place);
                if (!check.ok) continue;
                return { x, y, screenX: (x + 0.5) * T - g.camera.x, screenY: (y + 0.5) * T - g.camera.y };
              }
            }
          }
          return null;
        })()`);
      }
      async function placeAt(pos, button) {
        const box = await rect("#game");
        const x = box.x + pos.screenX * (box.w / 960);
        const y = box.y + pos.screenY * (box.h / 540);
        await clickPoint(x, y, button || "right");
      }
      async function selectItemSlot(id) {
        const index = await evaluate(`window.__sandbox.game.inventory.slots.findIndex(s => s && s.id === ${id})`);
        if (index < 0) return -1;
        if (index < 9) {
          await holdKey("Digit" + (index + 1), String(index + 1), 70);
        } else {
          await evaluate(`(() => { const g = window.__sandbox.game; const i = ${index}; g.inventory.selected = 0; const tmp = g.inventory.slots[0]; g.inventory.slots[0] = g.inventory.slots[i]; g.inventory.slots[i] = tmp; window.__sandbox.refreshHud(); return true; })()`);
        }
        return index;
      }

      await addItems([[B.wood, 6], [B.stone, 8], [ID.coal, 4], [ID.rawIron, 2], [B.sand, 2]]);
      await openInventory();
      const recipeCount = await evaluate("document.querySelectorAll('#inventory-screen .recipe').length");
      await recipe("planks");
      await recipe("planks");
      await recipe("planks");
      await recipe("planks");
      await recipe("stick");
      await recipe("stick");
      await recipe("table");
      report.results.crafting = await evaluate(`(() => { const inv = window.__sandbox.game.inventory; return {planks: window.__sandbox.inventory.countItem(inv, ${B.planks}), sticks: window.__sandbox.inventory.countItem(inv, ${ID.stick}), tables: window.__sandbox.inventory.countItem(inv, ${B.table}), recipes: ${recipeCount}}; })()`);
      report.screenshots.push(await screenshot("05-crafted"));
      await closePanelKey("KeyE", "e");
      const tableSlot = await evaluate(`window.__sandbox.game.inventory.slots.findIndex(s => s && s.id === ${B.table})`);
      if (tableSlot >= 0) await selectItemSlot(B.table);
      const placePos = await findPlacement();
      report.results.tableDebug = { tableSlot, placePos };
      if (placePos) {
        await placeAt(placePos, "right");
        await sleep(300);
        report.results.tablePlaced = await evaluate(`window.__sandbox.world.getBlock(window.__sandbox.game.world, ${placePos.x}, ${placePos.y})`);
      }
      await openInventory();
      await recipe("wooden_pickaxe");
      report.results.pickaxe = await evaluate(`window.__sandbox.inventory.countItem(window.__sandbox.game.inventory, ${ID.woodenPickaxe})`);
      const craftStatusWithTable = await evaluate("document.getElementById('craft-status').textContent");
      report.results.craftStatusWithTable = craftStatusWithTable;
      report.screenshots.push(await screenshot("06-inventory-table"));
      await closePanelKey("KeyE", "e");

      await holdKey("Escape", "Escape", 90);
      await sleep(200);
      await clickSelector("#btn-save");
      await sleep(250);
      report.results.saveStatus = await evaluate("document.getElementById('save-status').textContent");
      await cdp.send("Page.reload");
      await sleep(500);
      await waitReady();
      report.results.continueEnabled = await evaluate("!document.getElementById('btn-continue').disabled");
      report.screenshots.push(await screenshot("07-title-continue"));
      await clickSelector("#btn-continue");
      await sleep(400);
      report.results.reloaded = await evaluate(`(() => { const g = window.__sandbox.game; return {mode:g.mode, pickaxe:window.__sandbox.inventory.countItem(g.inventory, ${ID.woodenPickaxe}), table:window.__sandbox.world.getBlock(g.world, ${placePos ? placePos.x : 0}, ${placePos ? placePos.y : 0}), time:g.time}; })()`);

      await addItems([[B.furnace, 1], [ID.rawIron, 1], [ID.coal, 1]]);
      const furnaceSlot = await selectItemSlot(B.furnace);
      const furnacePos = await findPlacement();
      if (furnacePos) {
        await placeAt(furnacePos, "right");
        await sleep(250);
        await placeAt(furnacePos, "right");
        await sleep(350);
        report.results.furnaceOpened = await evaluate("window.__sandbox.game.mode");
        report.screenshots.push(await screenshot("08-furnace"));
        const canvasRect = await rect("#game");
        const inputIndex = await evaluate(`window.__sandbox.game.inventory.slots.findIndex(s => s && s.id === ${ID.rawIron})`);
        if (inputIndex >= 0) {
          const inputSel = `#furnace-hotbar-grid .inventory-slot[data-index="${inputIndex}"]`;
          const inputBox = await rect(inputSel);
          const inputHit = await evaluate(`(() => { const el=document.querySelector(${JSON.stringify(inputSel)}); if(!el) return null; const r=el.getBoundingClientRect(); const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2); return {cls:hit?(hit.className||hit.tagName):null, ctx:el.dataset.context, idx:el.dataset.index, r:{x:r.x,y:r.y,w:r.width,h:r.height}}; })()`);
          const beforePick = await evaluate("window.__sandbox.ui.debug()");
          await clickSelector(inputSel);
          await sleep(120);
          const afterPick = await evaluate("window.__sandbox.ui.debug()");
          await clickSelector("#furnace-input");
          await sleep(120);
          report.results.inputDebug = { inputIndex, inputBox, inputHit, beforePick, afterPick };
        }
        const fuelIndex = await evaluate(`window.__sandbox.game.inventory.slots.findIndex(s => s && s.id === ${ID.coal})`);
        const afterInput = await evaluate("window.__sandbox.ui.debug()");
        if (fuelIndex >= 0) {
          await clickSelector(`#furnace-hotbar-grid .inventory-slot[data-index="${fuelIndex}"]`);
          await sleep(120);
          const afterPickFuel = await evaluate("window.__sandbox.ui.debug()");
          await clickSelector("#furnace-fuel");
          await sleep(120);
          const afterFuel = await evaluate("window.__sandbox.ui.debug()");
          report.results.furnaceClicks = { fuelIndex, afterInput, afterPickFuel, afterFuel };
        }
        await sleep(6200);
        report.results.furnaceOutput = await evaluate(`(() => { const g = window.__sandbox.game; const st = Object.values(g.furnaces)[0]; return st ? {input:st.input, fuel:st.fuel, output:st.output} : null; })()`);
        report.screenshots.push(await screenshot("09-furnace-smelted"));
        const outputBox = await rect("#furnace-output");
        const outputHit = await evaluate(`(() => { const r=document.getElementById('furnace-output').getBoundingClientRect(); const el=document.elementFromPoint(r.x+r.width/2, r.y+r.height/2); return el ? (el.id || el.className || el.tagName) : null; })()`);
        const stateBeforeOutput = await evaluate("(() => { const s=Object.values(window.__sandbox.game.furnaces)[0]; return s ? {input:s.input,fuel:s.fuel,output:s.output,cook:s.cookTime,burn:s.burnTime} : null; })()");
        await clickSelector("#furnace-output");
        await sleep(160);
        const afterOutput = await evaluate("window.__sandbox.ui.debug()");
        const stateAfterOutput = await evaluate("(() => { const s=Object.values(window.__sandbox.game.furnaces)[0]; return s ? {input:s.input,fuel:s.fuel,output:s.output} : null; })()");
        const empty = await evaluate("window.__sandbox.game.inventory.slots.findIndex(s => !s)");
        if (empty >= 0) {
          await clickSelector(`#furnace-screen .inventory-slot[data-index="${empty}"]`);
          await sleep(160);
        }
        const afterPlace = await evaluate("window.__sandbox.ui.debug()");
        report.results.outputDebug = { outputBox, outputHit, stateBeforeOutput, afterOutput, stateAfterOutput, empty, afterPlace };
        report.results.ingots = await evaluate(`window.__sandbox.inventory.countItem(window.__sandbox.game.inventory, ${ID.ironIngot})`);
        await clickSelector('#furnace-screen [data-close]');
        await sleep(200);
        await holdKey("Escape", "Escape", 80);
        await sleep(150);
        await clickSelector("#btn-save");
        await sleep(200);
      }


      // Night, hostiles, help, death/respawn, ten real clicks and corrupt-save fallback.
      if (await evaluate("document.getElementById('pause-screen').classList.contains('is-open')")) {
        await clickSelector("#btn-resume");
        await sleep(250);
      }
      await addItems([[B.torch, 4]]);
      await selectItemSlot(B.torch);
      const torchPos = await findPlacement();
      if (torchPos) {
        await placeAt(torchPos, "right");
        await sleep(250);
      }
      report.results.torchPlaced = torchPos ? await evaluate(`window.__sandbox.world.getBlock(window.__sandbox.game.world, ${torchPos.x}, ${torchPos.y})`) : null;
      await evaluate("(() => { const g=window.__sandbox.game; g.time=0.78; g.player.health=20; g.player.hunger=20; g.player.dead=false; g.mode='playing'; return true; })()");
      await sleep(8500);
      report.results.night = await evaluate("(() => { const g=window.__sandbox.game; const hostiles=g.entities.list.filter(e=>e.hostile).length; return {time:g.time, hostiles, total:g.entities.list.length, minimap:getComputedStyle(document.getElementById('minimap')).display}; })()");
      report.screenshots.push(await screenshot("10-night"));

      await holdKey("KeyH", "h", 80);
      await sleep(250);
      report.results.help = await evaluate("(() => { const s=document.getElementById('help-screen'); return {open:s.classList.contains('is-open'), rows:s.querySelectorAll('.keys tr').length, mode:window.__sandbox.game.mode}; })()");
      report.screenshots.push(await screenshot("11-help"));
      await holdKey("KeyH", "h", 80);
      await sleep(200);

      await evaluate("(() => { window.__truth=[]; const h=document.getElementById('hotbar'); h.addEventListener('pointerdown', function(e){ window.__truth.push({type:'down', t:performance.now(), target:(e.target.className||e.target.tagName)}); }, true); h.addEventListener('pointerup', function(e){ window.__truth.push({type:'up', t:performance.now(), target:(e.target.className||e.target.tagName)}); }, true); return true; })()");
      const ten = [];
      const slotBox = await evaluate("(() => { const el=document.querySelectorAll('#hotbar .hotbar-slot')[1]; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2, hotbar:getComputedStyle(document.getElementById('hotbar')).display, rect:{x:r.x,y:r.y,w:r.width,h:r.height}, viewport:[innerWidth,innerHeight]}; })()");
      report.results.slotBox = slotBox;
      for (let i = 0; i < 10; i += 1) {
        const before = await evaluate("window.__sandbox.game.inventory.selected");
        await clickPoint(slotBox.x, slotBox.y);
        await sleep(105);
        const after = await evaluate("window.__sandbox.game.inventory.selected");
        const hit = await evaluate(`(() => { const el=document.elementFromPoint(${slotBox.x}, ${slotBox.y}); return el ? (el.className || el.tagName) : null; })()`);
        ten.push({ before, after, hit });
      }
      report.results.tenClicks = ten;
      report.results.truth = await evaluate("window.__truth");

      await evaluate("(() => { const g=window.__sandbox.game; g.player.health=1; const e=window.__sandbox.entities; const z=e.spawn(g.entities,'zombie',g.player.x+0.7,g.world.surface[Math.floor(g.player.x)+1]); return {zombie:z.id}; })()");
      await sleep(3200);
      report.results.death = await evaluate("(() => { const g=window.__sandbox.game; return {mode:g.mode, dead:g.player.dead, cause:document.getElementById('death-cause').textContent, deathOpen:document.getElementById('death-screen').classList.contains('is-open')}; })()");
      report.screenshots.push(await screenshot("12-death"));
      await clickSelector("#btn-respawn");
      await sleep(350);
      report.results.respawn = await evaluate("(() => { const g=window.__sandbox.game; return {mode:g.mode, health:g.player.health, dead:g.player.dead, hostiles:g.entities.list.filter(e=>e.hostile).length}; })()");

      await addItems([[ID.apple, 2]]);
      await selectItemSlot(ID.apple);
      await evaluate("(() => { const g=window.__sandbox.game; g.player.hunger=10; g.player.health=20; window.__sandbox.refreshHud(); return true; })()");
      const eatTarget = await evaluate("(() => { const g=window.__sandbox.game; const T=24; const x=Math.floor(g.player.x)+2, y=Math.floor(g.player.y)-3; return {x,y,screenX:(x+0.5)*T-g.camera.x,screenY:(y+0.5)*T-g.camera.y}; })()");
      await placeAt(eatTarget, "right");
      await sleep(250);
      report.results.eating = await evaluate(`(() => { const g=window.__sandbox.game; return {hunger:g.player.hunger, apples:window.__sandbox.inventory.countItem(g.inventory, ${ID.apple})}; })()`);

      report.results.a11y = await evaluate("(() => { const c=document.getElementById('game'); return {canvasLabel:Boolean(c.getAttribute('aria-label')), live:Boolean(document.getElementById('toasts').getAttribute('aria-live')), buttons:document.querySelectorAll('button').length, kbd:document.querySelectorAll('kbd').length, helpRows:document.querySelectorAll('#help-screen .keys tr').length, statusTitle:Boolean(document.getElementById('status').title)}; })()");

      report.results.perf = await evaluate(`new Promise((resolve) => { let frames = 0; const start = performance.now(); function tick(now) { frames += 1; if (now - start < 1200) { requestAnimationFrame(tick); } else { resolve({ frames, ms: now - start, fps: frames / ((now - start) / 1000) }); } } requestAnimationFrame(tick); })`);

      await holdKey("Escape", "Escape", 80);
      await sleep(250);
      await clickSelector("#toggle-audio");
      await sleep(120);
      const muted = await evaluate("window.__sandbox.audio.isEnabled()");
      await clickSelector("#toggle-audio");
      await sleep(120);
      const unmuted = await evaluate("window.__sandbox.audio.isEnabled()");
      await clickSelector("#toggle-motion");
      await sleep(120);
      const reduced = await evaluate("window.__sandbox.particles.isReducedMotion()");
      await clickSelector("#toggle-motion");
      await sleep(120);
      const normal = await evaluate("window.__sandbox.particles.isReducedMotion()");
      report.results.audioToggle = { muted, unmuted, reduced, normal };
      await clickSelector("#btn-resume");
      await sleep(200);

      const cave = await evaluate(`(() => {
        const g = window.__sandbox.game, W = window.__sandbox.world, T = 24;
        const prev = { x: g.player.x, y: g.player.y, time: g.time, entities: g.entities.list.length };
        let found = null;
        for (let x = 24; x < g.world.width - 26 && !found; x += 1) {
          for (let y = (g.world.surface[x] || 0) + 6; y < g.world.height - 6; y += 1) {
            if (W.getBlock(g.world, x, y) === 0 && W.getBlock(g.world, x + 1, y) === 0 && W.getBlock(g.world, x + 2, y) === 0 &&
                W.getBlock(g.world, x, y - 1) === 0 && W.getBlock(g.world, x + 1, y - 1) === 0 && W.getBlock(g.world, x + 2, y - 1) === 0 &&
                W.getBlock(g.world, x, y + 1) !== 0 && W.getBlock(g.world, x, y + 1) !== 7 &&
                W.getBlock(g.world, x + 1, y + 1) !== 0 && W.getBlock(g.world, x + 2, y + 1) !== 0) {
              found = { x, y }; break;
            }
          }
        }
        if (!found) return { found: false, prev };
        g.time = 0.3;
        g.entities.list = [];
        g.player.x = found.x + 1.5;
        g.player.y = found.y + 1;
        g.player.vx = 0; g.player.vy = 0; g.player.onGround = true;
        const torchX = found.x;
        if (W.getBlock(g.world, torchX, found.y) === 0 && W.getBlock(g.world, torchX, found.y + 1) !== 0) {
          W.setBlock(g.world, torchX, found.y, window.__sandbox.config.blocks.torch);
        }
        window.__sandbox.render.updateCamera(g.camera, g.player, g.world, 960, 540, 1, 0, 0);
        return { found: true, prev, x: found.x, y: found.y, screenX: (found.x + 1.5) * T - g.camera.x, screenY: (found.y + 0.5) * T - g.camera.y };
      })()`);
      report.results.cave = cave;
      if (cave && cave.found) {
        await sleep(450);
        report.screenshots.push(await screenshot("15-cave"));
        await evaluate(`(() => { const g=window.__sandbox.game; g.player.x=${cave.prev.x}; g.player.y=${cave.prev.y}; g.time=${cave.prev.time}; g.player.vx=0; g.player.vy=0; g.player.onGround=true; window.__sandbox.render.updateCamera(g.camera, g.player, g.world, 960, 540, 1, 0, 0); return true; })()`);
        await sleep(300);
      }

      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
      await sleep(350);
      report.results.layoutNarrow = await evaluate("(() => { const r=document.getElementById('app').getBoundingClientRect(); return {w:r.width,h:r.height,viewport:[innerWidth,innerHeight]}; })()");
      report.screenshots.push(await screenshot("16-narrow"));
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false });
      await sleep(250);

      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
      await sleep(400);
      report.results.layout1280 = await evaluate("(() => { const r=document.getElementById('app').getBoundingClientRect(); return {w:r.width,h:r.height, viewport:[innerWidth,innerHeight]}; })()");
      report.screenshots.push(await screenshot("13-1280"));
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false });
      await sleep(250);

      await evaluate("(() => { localStorage.setItem(window.__sandbox.config.saveKey, '{broken save'); window.__sandbox.game.world = null; window.__sandbox.game.player = null; return true; })()");
      await cdp.send("Page.reload");
      await sleep(500);
      await waitReady();
      report.results.corrupt = await evaluate("(() => { const b=document.getElementById('btn-continue'); const w=document.getElementById('save-warning'); return {continueDisabled:b.disabled, continueHidden:b.hidden, warning:w.textContent, warningHidden:w.hidden, newText:document.getElementById('btn-new-world').textContent, note:document.getElementById('save-note').textContent, mode:window.__sandbox.game.mode}; })()");
      report.screenshots.push(await screenshot("14-corrupt-fallback"));
    }

    report.results.mode = await evaluate("window.__sandbox.game.mode");
    report.errors = exceptions.concat(consoleErrors);
    report.requests = requests.filter((url) => !url.startsWith("file:") && !url.startsWith("data:"));
    const external = report.requests;
    const coreOk = Boolean(report.results.started && report.results.started.mode === "playing" &&
      report.results.walk && report.results.walk.moved &&
      report.errors.length === 0 && external.length === 0);
    let fullOk = true;
    if (args.includes("--full")) {
      fullOk = Boolean(
        report.results.pickaxe === 1 &&
        report.results.tablePlaced === 11 &&
        report.results.reloaded && report.results.reloaded.pickaxe === 1 && report.results.reloaded.table === 11 &&
        report.results.furnaceOutput && report.results.furnaceOutput.output && report.results.furnaceOutput.output.id === 103 &&
        report.results.ingots === 1 &&
        report.results.help && report.results.help.open && report.results.help.rows >= 8 &&
        report.results.audio && report.results.audio.unlocked &&
        report.results.torchPlaced === 13 &&
        report.results.truth && report.results.truth.filter((t) => t.type === "down").length === 10 &&
        report.results.truth && report.results.truth.filter((t) => t.type === "up").length === 10 &&
        report.results.truth && (() => { const downs = report.results.truth.filter(t=>t.type==="down"); const ups = report.results.truth.filter(t=>t.type==="up"); for (let i=0;i<10;i++){ if (!downs[i] || !ups[i] || downs[i].target !== ups[i].target) return false; if (i>0 && downs[i].t - downs[i-1].t < 90) return false; } return true; })() &&
        report.results.night && report.results.night.hostiles >= 1 && report.results.night.minimap !== "none" &&
        report.results.tenClicks && report.results.tenClicks.every((c) => c.after === 1) &&
        report.results.death && report.results.death.mode === "dead" && report.results.death.deathOpen &&
        report.results.respawn && report.results.respawn.mode === "playing" && report.results.respawn.health === 20 &&
        report.results.perf && report.results.perf.fps >= 30 &&
        report.results.audioToggle && report.results.audioToggle.muted === false && report.results.audioToggle.unmuted === true &&
        report.results.eating && report.results.eating.hunger === 14 && report.results.eating.apples === 1 &&
        report.results.a11y && report.results.a11y.canvasLabel && report.results.a11y.live && report.results.a11y.buttons >= 8 && report.results.a11y.helpRows >= 8 &&
        report.results.audioToggle && report.results.audioToggle.reduced === true && report.results.audioToggle.normal === false &&
        report.results.cave && report.results.cave.found &&
        report.results.layoutNarrow && report.results.layoutNarrow.w === 800 && report.results.layoutNarrow.h === 450 &&
        report.results.layout1280 && report.results.layout1280.w === 1280 && report.results.layout1280.h === 720 &&
        report.results.corrupt && report.results.corrupt.continueDisabled && report.results.corrupt.continueHidden && report.results.corrupt.warningHidden === false && /couldn't load/i.test(report.results.corrupt.warning) && report.results.corrupt.newText === "Start Fresh World" && /fresh seed/i.test(report.results.corrupt.note)
      );
    }
    report.ok = coreOk && fullOk;
  } catch (error) {
    report.errors.push(error.stack || String(error));
  } finally {
    try { if (!keepOpen) chrome.kill("SIGKILL"); } catch (error) { /* ignore */ }
    if (!keepOpen) rmSync(profile, { recursive: true, force: true });
  }

  console.log(JSON.stringify(report, null, 2));
  if (!report.ok) process.exitCode = 1;
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.stack || String(error) }, null, 2));
  process.exitCode = 1;
});

