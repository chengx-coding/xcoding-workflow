#!/usr/bin/env node
"use strict";

// Automated journey probe for the sandbox page. Drives a real headless Chrome over
// the DevTools protocol, executes the stateful journeys (mining, placement refusals,
// pause, day/night, persistence, corrupt-save recovery, boundaries, hotbar selection)
// and records before/after observables plus screenshots. Standard library only.

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { pathToFileURL } = require("node:url");

const ARGS = parseArgs(process.argv.slice(2));
const VIEW = { width: 960, height: 540 };
const PAGE = path.resolve(ARGS.page || path.join(__dirname, "..", "index.html"));
const OUT = path.resolve(ARGS.out || path.join(__dirname, "..", "..", "tmp", "journeys"));
const REPORT = path.resolve(ARGS.report || path.join(OUT, "journey-report.json"));
const PROFILE = path.join(OUT, "chrome-profile");

const checks = [];
const screenshots = [];
const exceptions = [];
const consoleErrors = [];

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const entry = argv[index];
    if (entry.startsWith("--")) {
      const key = entry.slice(2);
      const value = argv[index + 1] && !argv[index + 1].startsWith("--") ? argv[index + 1] : "true";
      args[key] = value;
      if (value !== "true") {
        index += 1;
      }
    }
  }
  return args;
}

function check(name, condition, detail) {
  const ok = condition === true;
  checks.push({ name: name, ok: ok, detail: detail === undefined ? null : detail });
  if (!ok) {
    console.log("FAIL " + name + (detail === undefined ? "" : " :: " + JSON.stringify(detail)));
  }
  return ok;
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

async function waitFor(action, timeoutMs, intervalMs) {
  const started = Date.now();
  let lastError = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const value = await action();
      if (value) {
        return value;
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs || 100);
  }
  if (lastError) {
    throw lastError;
  }
  return null;
}

function findChrome() {
  if (ARGS.chrome) {
    return path.resolve(ARGS.chrome);
  }
  const candidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, "Google", "Chrome", "Application", "chrome.exe") : null
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error("No Chrome executable found; pass --chrome <path>");
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.sequence = 0;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async open() {
    const socket = new WebSocket(this.url);
    this.socket = socket;
    await new Promise(function (resolve, reject) {
      socket.addEventListener("open", resolve);
      socket.addEventListener("error", function (event) { reject(new Error("WebSocket error: " + event.message)); });
    });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const entry = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          entry.reject(new Error(message.error.message || "CDP error"));
        } else {
          entry.resolve(message.result);
        }
        return;
      }
      if (message.method) {
        if (message.method === "Runtime.exceptionThrown") {
          exceptions.push(message.params.exceptionDetails || {});
        }
        if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
          consoleErrors.push(message.params.args.map(function (arg) { return arg.value; }).join(" "));
        }
        const listeners = this.listeners.get(message.method) || [];
        listeners.forEach(function (listener) { listener(message.params); });
      }
    });
  }

  send(method, params) {
    const id = ++this.sequence;
    const payload = JSON.stringify({ id: id, method: method, params: params || {} });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve: resolve, reject: reject });
      this.socket.send(payload);
    });
  }

  once(method) {
    return new Promise((resolve) => {
      const listener = (params) => {
        const list = this.listeners.get(method) || [];
        const index = list.indexOf(listener);
        if (index >= 0) {
          list.splice(index, 1);
        }
        resolve(params);
      };
      const list = this.listeners.get(method) || [];
      list.push(listener);
      this.listeners.set(method, list);
    });
  }

  close() {
    if (this.socket) {
      try {
        this.socket.close();
      } catch (error) {
        // Ignore shutdown races.
      }
    }
  }
}

async function connect(port) {
  const list = await waitFor(async function () {
    const response = await fetch("http://127.0.0.1:" + port + "/json/list");
    if (!response.ok) {
      return null;
    }
    const targets = await response.json();
    return targets.filter(function (target) { return target.type === "page"; });
  }, 15000, 150);
  if (!list || list.length === 0) {
    throw new Error("No page target found on the debugging port");
  }
  return list[0].webSocketDebuggerUrl;
}

async function launchChrome(chromePath) {
  fs.mkdirSync(OUT, { recursive: true });
  fs.rmSync(PROFILE, { recursive: true, force: true });
  fs.mkdirSync(PROFILE, { recursive: true });
  const child = spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--mute-audio",
    "--window-size=960,600",
    "--remote-debugging-port=0",
    "--user-data-dir=" + PROFILE,
    "about:blank"
  ], { stdio: "ignore", windowsHide: true });

  const portFile = path.join(PROFILE, "DevToolsActivePort");
  const content = await waitFor(function () {
    if (!fs.existsSync(portFile)) {
      return null;
    }
    const text = fs.readFileSync(portFile, "utf8").trim();
    return text.length > 0 ? text : null;
  }, 15000, 100);
  const port = Number(content.split(/\r?\n/)[0]);
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error("Chrome did not publish a usable debugging port");
  }
  return { child: child, port: port };
}

function stopChrome(launched) {
  try {
    launched.child.kill();
  } catch (error) {
    // Best effort.
  }
}

async function main() {
  const chromePath = findChrome();
  const launched = await launchChrome(chromePath);
  const wsUrl = await connect(launched.port);
  const cdp = new Cdp(wsUrl);
  await cdp.open();

  let evaluate = async function (expression) {
    const result = await cdp.send("Runtime.evaluate", {
      expression: expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true
    });
    if (result.exceptionDetails) {
      const detail = result.exceptionDetails.exception && result.exceptionDetails.exception.description
        ? result.exceptionDetails.exception.description
        : result.exceptionDetails.text;
      throw new Error("Page evaluation failed: " + detail);
    }
    return result.result.value;
  };

  async function waitReady(timeoutMs) {
    return waitFor(async function () {
      try {
        return await evaluate("typeof window.__sandbox !== 'undefined' && document.getElementById('status').dataset.state === 'ready'");
      } catch (error) {
        return false;
      }
    }, timeoutMs || 15000, 120);
  }

  async function reloadPage() {
    await cdp.send("Page.reload", { ignoreCache: true });
    await sleep(250);
    await waitReady(15000);
  }

  async function canvasRect() {
    return evaluate("(function(){var r=document.getElementById('game').getBoundingClientRect();return {left:r.left,top:r.top,width:r.width,height:r.height};})()");
  }

  async function clientPoint(logicalX, logicalY) {
    const rect = await canvasRect();
    return {
      x: rect.left + logicalX * rect.width / VIEW.width,
      y: rect.top + logicalY * rect.height / VIEW.height
    };
  }

  async function movePointer(logicalX, logicalY) {
    const point = await clientPoint(logicalX, logicalY);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x, y: point.y, button: "none", buttons: 0 });
    await sleep(40);
    return point;
  }

  async function clickTile(tileX, tileY, button) {
    const logical = await evaluate("window.__sandbox.api.screenForTile(" + tileX + "," + tileY + ")");
    const point = await movePointer(logical.x, logical.y);
    const pressedButtons = button === "right" ? 2 : 1;
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: point.x, y: point.y, button: button, buttons: pressedButtons, clickCount: 1 });
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: point.x, y: point.y, button: button, buttons: 0, clickCount: 1 });
    await sleep(420);
    return logical;
  }

  const KEY_TABLE = {
    a: { key: "a", code: "KeyA", vk: 65 },
    d: { key: "d", code: "KeyD", vk: 68 },
    p: { key: "p", code: "KeyP", vk: 80 },
    m: { key: "m", code: "KeyM", vk: 77 },
    "1": { key: "1", code: "Digit1", vk: 49 },
    "2": { key: "2", code: "Digit2", vk: 50 },
    "5": { key: "5", code: "Digit5", vk: 53 },
    "7": { key: "7", code: "Digit7", vk: 55 },
    "9": { key: "9", code: "Digit9", vk: 57 }
  };

  async function keyDown(name) {
    const entry = KEY_TABLE[name];
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: entry.key,
      code: entry.code,
      windowsVirtualKeyCode: entry.vk,
      nativeVirtualKeyCode: entry.vk,
      text: entry.key
    });
  }

  async function keyUp(name) {
    const entry = KEY_TABLE[name];
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: entry.key,
      code: entry.code,
      windowsVirtualKeyCode: entry.vk,
      nativeVirtualKeyCode: entry.vk
    });
  }

  async function pressKey(name) {
    await keyDown(name);
    await sleep(60);
    await keyUp(name);
    await sleep(180);
  }

  async function holdKey(name, ms) {
    await keyDown(name);
    await sleep(ms);
    await keyUp(name);
    await sleep(120);
  }

  async function wheel(deltaY) {
    const point = await clientPoint(480, 300);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseWheel", x: point.x, y: point.y, deltaX: 0, deltaY: deltaY });
    await sleep(220);
  }

  async function snapshot() {
    return evaluate("window.__sandbox.api.getSnapshot()");
  }

  async function pixel(logicalX, logicalY) {
    return evaluate("window.__sandbox.api.pixel(" + logicalX + "," + logicalY + ")");
  }

  async function shot(name) {
    const result = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    const target = path.join(OUT, name);
    fs.writeFileSync(target, Buffer.from(result.data, "base64"));
    screenshots.push(target);
    return target;
  }

  async function tilePixel(tileX, tileY) {
    const logical = await evaluate("window.__sandbox.api.screenForTile(" + tileX + "," + tileY + ")");
    return pixel(logical.x, logical.y);
  }

  function rgbDistance(a, b) {
    return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2);
  }

  try {
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 960,
      height: 600,
      deviceScaleFactor: 1,
      mobile: false
    });
    await cdp.send("Page.navigate", { url: pathToFileURL(PAGE).href });
    await waitReady(20000);

    // ---- Journey 0: boot, palette, canvas ----
    let state = await snapshot();
    check("boot: status is ready", state.status === "ready", state.status);
    check("boot: nine palette slots", state.hotbar.length === 9, state.hotbar.length);
    check("boot: hotbar starts on slot 1", state.hotbarSelection === 0, state.hotbarSelection);
    const buckets = await evaluate("(function(){var c=document.getElementById('game');var ctx=c.getContext('2d');var d=ctx.getImageData(0,0,c.width,c.height).data;var set={};for(var i=0;i<d.length;i+=4*89){var k=(d[i]>>4)+','+(d[i+1]>>4)+','+(d[i+2]>>4);set[k]=1;}return Object.keys(set).length;})()");
    check("boot: canvas is not blank", buckets >= 12, buckets);
    const hint = await evaluate("document.getElementById('hintline').textContent.replace(/\\s+/g,' ').trim()");
    check("boot: controls hint line is present", /move/.test(hint) && /mine/.test(hint) && /build/.test(hint), hint);
    const overflow = await evaluate("({scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth})");
    check("boot: no horizontal overflow at 960", overflow.scrollWidth <= overflow.clientWidth + 1, overflow);

    // ---- Journey 11: hotbar selection (keys and wheel) ----
    await pressKey("5");
    state = await snapshot();
    check("hotbar: number key selects slot 5", state.selected === 4 && state.hotbarSelection === 4, { selected: state.selected, ring: state.hotbarSelection });
    await wheel(120);
    state = await snapshot();
    check("hotbar: wheel advances the selection", state.selected === 5, state.selected);
    const selectedCount = await evaluate("document.querySelectorAll('#hotbar .slot.is-selected').length");
    check("hotbar: exactly one visible selected slot", selectedCount === 1, selectedCount);
    await wheel(-120);
    await pressKey("1");
    state = await snapshot();
    check("hotbar: wheel wraps back and key 1 restores grass", state.selected === 0, state.selected);

    // ---- Journey 3a: held mining shows a break-progress state and a swing ----
    const holdLogical = await evaluate("window.__sandbox.api.screenForTile(9,42)");
    const holdPoint = await clientPoint(holdLogical.x, holdLogical.y);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: holdPoint.x, y: holdPoint.y, button: "none", buttons: 0 });
    await sleep(60);
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: holdPoint.x, y: holdPoint.y, button: "left", buttons: 1, clickCount: 1 });
    await sleep(95);
    state = await snapshot();
    check("mining: a held break exposes a live progress state", state.mining.active === true && state.mining.progress > 0 && state.mining.progress < 1, state.mining);
    await shot("mining-progress.png");
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: holdPoint.x, y: holdPoint.y, button: "left", buttons: 0, clickCount: 1 });
    await sleep(520);
    state = await snapshot();
    const heldBlock = await evaluate("window.__sandbox.api.blockAt(9,42)");
    check("mining: the held break completes and removes the block", heldBlock === 0 && state.inventory["2"] === 25, { block: heldBlock, dirt: state.inventory["2"] });
    check("mining: the break is confirmed by a toast", !!(state.lastToast && /dirt/i.test(state.lastToast.message)), state.lastToast);

    // ---- Journey 1: mine a surface block ----
    const mineTile = { x: 13, y: 41 };
    check("mine: target starts solid grass", (await evaluate("window.__sandbox.api.blockAt(13,41)")) !== 0);
    await movePointer((await evaluate("window.__sandbox.api.screenForTile(13,41)")).x, (await evaluate("window.__sandbox.api.screenForTile(13,41)")).y);
    const beforeMine = await tilePixel(13, 41);
    await shot("mine-before.png");
    await clickTile(13, 41, "left");
    await sleep(250);
    state = await snapshot();
    const afterMine = await tilePixel(13, 41);
    await shot("mine-after.png");
    check("mine: block removed from the world", (await evaluate("window.__sandbox.api.blockAt(13,41)")) === 0);
    check("mine: inventory gained one grass", state.inventory["1"] === 17, state.inventory["1"]);
    check("mine: a gain toast is visible", !!(state.lastToast && /(\+1 grass|Mined grass)/.test(state.lastToast.message)), state.lastToast);
    check("mine: removed tile shows the background in place", rgbDistance(beforeMine, afterMine) > 40 && afterMine[2] > afterMine[0], { before: beforeMine, after: afterMine });

    // ---- Journey 2: place into a supported empty cell ----
    await pressKey("7");
    await clickTile(14, 40, "right");
    state = await snapshot();
    const placedPixel = await tilePixel(14, 40);
    check("place: planks occupy the cell", (await evaluate("window.__sandbox.api.blockAt(14,40)")) === 7);
    check("place: inventory consumed one plank", state.inventory["7"] === 11, state.inventory["7"]);
    check("place: a placement toast is visible", !!(state.lastToast && /Placed planks/.test(state.lastToast.message)), state.lastToast);
    check("place: the new block is visibly drawn there", placedPixel[0] > 120 && placedPixel[1] > 70, placedPixel);

    // ---- Journey 3: refused placement on an occupied cell ----
    const placedBefore = await tilePixel(14, 40);
    await clickTile(14, 40, "right");
    state = await snapshot();
    const placedAfter = await tilePixel(14, 40);
    check("refuse: occupied cell stays unchanged", rgbDistance(placedBefore, placedAfter) < 6, { before: placedBefore, after: placedAfter });
    check("refuse: occupied cell explains itself", !!(state.lastToast && /not empty/.test(state.lastToast.message)), state.lastToast);
    const visibleToasts = await evaluate("Array.from(document.querySelectorAll('#toasts .toast.is-visible')).map(function (t) { return t.textContent; })");
    check("refuse: the explanation is visible to the user", visibleToasts.some(function (text) { return /not empty/.test(text); }), visibleToasts);

    // ---- Journey 4: refused placement over the player ----
    await pressKey("1");
    await clickTile(12, 40, "right");
    state = await snapshot();
    check("refuse: player body is protected", !!(state.lastToast && /standing there/.test(state.lastToast.message)), state.lastToast);
    check("refuse: player cell stays air", (await evaluate("window.__sandbox.api.blockAt(12,40)")) === 0);

    // ---- Journey 5: refused placement with an empty palette slot ----
    await pressKey("5");
    await clickTile(15, 40, "right");
    state = await snapshot();
    check("refuse: empty palette explains the shortage", !!(state.lastToast && /No leaves left/.test(state.lastToast.message)), state.lastToast);
    check("refuse: empty palette leaves the cell air", (await evaluate("window.__sandbox.api.blockAt(15,40)")) === 0);

    // ---- Journey 8: pause shows an occluding overlay and freezes time ----
    await pressKey("p");
    state = await snapshot();
    const pausedTime = state.time;
    check("pause: state and overlay agree", state.paused === true && state.pauseOverlayHidden === false, { paused: state.paused, hidden: state.pauseOverlayHidden });
    const overlay = await evaluate("(function(){var el=document.getElementById('pause-overlay');var r=el.getBoundingClientRect();var s=getComputedStyle(el);return {visible:!el.hidden,width:r.width,height:r.height,bg:s.backgroundColor,backdrop:s.backdropFilter||s.webkitBackdropFilter};})()");
    check("pause: overlay covers the stage", overlay.visible && overlay.width > 800 && overlay.height > 400, overlay);
    const pausedShot = await shot("paused.png");
    await sleep(700);
    state = await snapshot();
    check("pause: clock is frozen", Math.abs(state.time - pausedTime) < 1e-9, { before: pausedTime, after: state.time });
    await pressKey("p");
    state = await snapshot();
    check("pause: resume hides the overlay", state.paused === false && state.pauseOverlayHidden === true);
    await sleep(400);
    state = await snapshot();
    check("pause: clock advances after resume", state.time !== pausedTime);

    // ---- Journey 6: reload persistence ----
    const beforeReload = await snapshot();
    await evaluate("window.__sandbox.api.save()");
    await reloadPage();
    const afterReload = await snapshot();
    check("reload: world edit restored", (await evaluate("window.__sandbox.api.blockAt(13,41)")) === 0);
    check("reload: placed block restored", (await evaluate("window.__sandbox.api.blockAt(14,40)")) === 7);
    check("reload: inventory restored", afterReload.inventory["1"] === beforeReload.inventory["1"] && afterReload.inventory["7"] === beforeReload.inventory["7"], { before: beforeReload.inventory, after: afterReload.inventory });
    check("reload: player position restored", Math.abs(afterReload.player.x - beforeReload.player.x) < 0.4, { before: beforeReload.player.x, after: afterReload.player.x });
    check("reload: restore notice is shown", afterReload.toastTexts.some(function (text) { return /restored/i.test(text); }), afterReload.toastTexts);

    // ---- Journey 7: corrupt save recovery ----
    // The running page saves on pagehide, so corrupting storage and reloading would be
    // overwritten by that save. Inject the corrupt payload before the next document's
    // own scripts instead, which is the real recovery path.
    const injection = await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
      source: "try { localStorage.setItem('xc-sandbox-sample-v2', '{oops'); } catch (error) {}"
    });
    await reloadPage();
    const recovered = await snapshot();
    check("recover: status stays ready", recovered.status === "ready", recovered.status);
    check("recover: a fresh world is generated", (await evaluate("window.__sandbox.api.blockAt(13,41)")) !== 0);
    check("recover: the recovery notice is visible", recovered.toastTexts.some(function (text) { return /could not be read/i.test(text); }), recovered.toastTexts);
    await cdp.send("Page.removeScriptToEvaluateOnNewDocument", { identifier: injection.identifier });
    await reloadPage();

    // ---- Journey 9: day and night are two materially different visual states ----
    await evaluate("window.__sandbox.api.setTime(0.5)");
    await sleep(220);
    const dayTop = await pixel(480, 24);
    const dayGround = await tilePixel(20, 42);
    const dayShot = await shot("day.png");
    const dayClock = await evaluate("document.getElementById('clock-text').textContent + ' ' + document.getElementById('phase-value').textContent");
    await evaluate("window.__sandbox.api.setTime(0.0)");
    await sleep(220);
    const nightTop = await pixel(480, 24);
    const nightGround = await tilePixel(20, 42);
    const nightShot = await shot("night.png");
    const nightClock = await evaluate("document.getElementById('clock-text').textContent + ' ' + document.getElementById('phase-value').textContent");
    check("day/night: sky changes materially", rgbDistance(dayTop, nightTop) > 60, { day: dayTop, night: nightTop });
    check("day/night: HUD clock changes", dayClock !== nightClock, { day: dayClock, night: nightClock });
    check("day/night: foreground stays drawn at night", nightGround[3] === 255 && Math.max(nightGround[0], nightGround[1], nightGround[2]) > 12, nightGround);
    check("day/night: foreground is darker at night but still visible", rgbDistance(dayGround, nightGround) > 8, { day: dayGround, night: nightGround });
    await evaluate("window.__sandbox.api.setTime(0.32)");

    // ---- Journey 10: world boundary and camera clamp ----
    await evaluate("window.__sandbox.api.teleport(1.5, 41)");
    await holdKey("a", 1200);
    const leftEdge = await snapshot();
    check("boundary: camera clamps to the left edge", leftEdge.camera.x === 0, leftEdge.camera.x);
    check("boundary: player stays inside the world", leftEdge.player.x >= 0.34, leftEdge.player.x);
    await evaluate("window.__sandbox.api.teleport(126.5, 41)");
    await holdKey("d", 1200);
    const rightEdge = await snapshot();
    check("boundary: camera clamps to the right edge", rightEdge.camera.x === 128 * 32 - 960, rightEdge.camera.x);
    check("boundary: player stays inside the right edge", rightEdge.player.x <= 127.66, rightEdge.player.x);

    // ---- Journey 4: underground background and the sealed world floor ----
    await evaluate("window.__sandbox.api.setTime(0.5)");
    const digColumn = 100;
    for (let y = 35; y <= 61; y += 1) {
      await evaluate("window.__sandbox.api.teleport(" + (digColumn + 0.5) + "," + y + ")");
      await evaluate("window.__sandbox.api.mine(" + digColumn + "," + y + ")");
      await sleep(25);
    }
    await evaluate("window.__sandbox.api.teleport(" + (digColumn + 0.5) + ",62)");
    await sleep(350);
    const tuck = await evaluate("(function(){var b=document.getElementById('hotbar');var r=b.getBoundingClientRect();return {tucked:b.classList.contains('is-tucked'),top:r.top};})()");
    check("floor: the palette tucks away so the bottom row stays reachable", tuck.tucked && tuck.top > 520, tuck);
    const undergroundGround = await tilePixel(digColumn, 55);
    check("underground: the exposed background is dark, not sky", Math.max(undergroundGround[0], undergroundGround[1], undergroundGround[2]) < 90, undergroundGround);
    await shot("underground.png");
    const floorBefore = await evaluate("window.__sandbox.api.blockAt(" + digColumn + ",62)");
    await clickTile(digColumn, 62, "left");
    const floorAfter = await evaluate("window.__sandbox.api.blockAt(" + digColumn + ",62)");
    state = await snapshot();
    check("floor: the bottom row is still sealed after a mine click", floorBefore === 3 && floorAfter === 3, { before: floorBefore, after: floorAfter });
    check("floor: the refusal explains the unbreakable floor", !!(state.lastToast && /floor/i.test(state.lastToast.message)), state.lastToast);
    await shot("underground-floor.png");
    const bottomAttempt = await evaluate("window.__sandbox.api.mine(" + digColumn + ",63)");
    check("floor: the bottommost row is also refused", bottomAttempt.ok === false && /floor/i.test(bottomAttempt.reason), bottomAttempt);
    const undergroundState = await snapshot();
    check("floor: the player stands on the floor and cannot end up below it", undergroundState.player.y >= 61.5, undergroundState.player.y);
    await evaluate("window.__sandbox.api.teleport(12.5,41)");
    await evaluate("window.__sandbox.api.setTime(0.32)");
    await sleep(250);
    const untucked = await evaluate("!document.getElementById('hotbar').classList.contains('is-tucked')");
    check("floor: the palette returns after leaving the floor zone", untucked === true, untucked);

    // ---- Coordinates, mute, reduced motion and numeric seed entry ----
    await evaluate("window.__sandbox.api.teleport(20.5,41)");
    await sleep(150);
    const coordsText = await evaluate("document.getElementById('coords-value').textContent");
    check("hud: coordinates track the player", coordsText === "20, 41", coordsText);

    const mapChecksum = "(function(){var c=document.getElementById('minimap');if(!c)return {exists:false};var ctx=c.getContext('2d');var d=ctx.getImageData(0,0,c.width,c.height).data;var set={};var sum=0;for(var i=0;i<d.length;i+=4){set[(d[i]>>4)+','+(d[i+1]>>4)+','+(d[i+2]>>4)]=1;sum=(sum+d[i]*3+d[i+1]*5+d[i+2]*7)>>>0;}return {exists:true,buckets:Object.keys(set).length,checksum:sum};})()";
    const mapBefore = await evaluate(mapChecksum);
    check("orientation: the minimap exists and is non-blank", mapBefore.exists === true && mapBefore.buckets >= 5, mapBefore);
    await evaluate("window.__sandbox.api.teleport(40.5,41)");
    await sleep(280);
    const mapAfter = await evaluate(mapChecksum);
    check("orientation: the minimap tracks the player", mapBefore.checksum !== mapAfter.checksum, { before: mapBefore.checksum, after: mapAfter.checksum });
    await evaluate("window.__sandbox.api.teleport(12.5,41)");
    await sleep(180);

    async function clickElement(id) {
      const point = await evaluate("(function(){var r=document.getElementById('" + id + "').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()");
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x, y: point.y, button: "none", buttons: 0 });
      await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: point.x, y: point.y, button: "left", buttons: 1, clickCount: 1 });
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: point.x, y: point.y, button: "left", buttons: 0, clickCount: 1 });
      await sleep(260);
    }

    await clickElement("mute-button");
    state = await snapshot();
    const muteStored = await evaluate("localStorage.getItem('xc-sandbox-muted-v1')");
    check("mute: control mutes and persists", state.muteButton === "Muted" && muteStored === "1", { button: state.muteButton, stored: muteStored });
    await clickElement("mute-button");
    state = await snapshot();
    const unmuteStored = await evaluate("localStorage.getItem('xc-sandbox-muted-v1')");
    check("mute: control restores sound", state.muteButton === "Sound on" && unmuteStored === "0", { button: state.muteButton, stored: unmuteStored });

    await cdp.send("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }]
    });
    await sleep(200);
    const reduced = await evaluate("({matches: matchMedia('(prefers-reduced-motion: reduce)').matches, duration: getComputedStyle(document.querySelector('#hotbar .slot')).transitionDuration})");
    check("reduced motion: media query and CSS apply", reduced.matches === true && parseFloat(reduced.duration) < 0.001, reduced);
    await cdp.send("Emulation.setEmulatedMedia", { features: [] });
    await sleep(120);

    const seedSignature = await evaluate("(function(){var h=2166136261;for(var x=28;x<124;x+=5){for(var y=28;y<56;y+=4){h=(Math.imul(h^window.__sandbox.api.blockAt(x,y),16777619))>>>0;}}return h;})()");
    await evaluate("(function(){var input=document.getElementById('seed-input');input.value='4242';var form=document.getElementById('seed-form');if(form.requestSubmit){form.requestSubmit();}else{form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));}return true;})()");
    await sleep(650);
    state = await snapshot();
    const newSignature = await evaluate("(function(){var h=2166136261;for(var x=28;x<124;x+=5){for(var y=28;y<56;y+=4){h=(Math.imul(h^window.__sandbox.api.blockAt(x,y),16777619))>>>0;}}return h;})()");
    check("seed: numeric entry regenerates the world", state.seed === 4242 && state.toastTexts.some(function (text) { return /New world/.test(text); }), { seed: state.seed, toasts: state.toastTexts });
    check("seed: the regenerated terrain differs", seedSignature !== newSignature, { before: seedSignature, after: newSignature });
    await evaluate("window.__sandbox.api.teleport(12.5,41)");
    await sleep(150);

    // ---- C10: error state contract ----
    await evaluate("window.dispatchEvent(new ErrorEvent('error',{message:'probe failure'}))");
    await sleep(120);
    const errorState = await evaluate("({state:document.getElementById('status').dataset.state,bg:getComputedStyle(document.getElementById('status')).backgroundColor})");
    check("status: an error turns the marker red", errorState.state === "error" && /231,\s*76,\s*60|e74c3c|rgb\(231/.test(errorState.bg), errorState);
    await reloadPage();
    const recoveredStatus = await snapshot();
    check("status: reload recovers the ready marker", recoveredStatus.status === "ready", recoveredStatus.status);

    // ---- A richer final frame for the 960x600 quality screenshot ----
    await evaluate("window.__sandbox.api.teleport(12.5,41)");
    await evaluate("window.__sandbox.api.select(6)");
    await evaluate("window.__sandbox.api.place(10,40)");
    await evaluate("window.__sandbox.api.place(11,40)");
    await evaluate("window.__sandbox.api.select(8)");
    await evaluate("window.__sandbox.api.place(13,40)");
    await evaluate("window.__sandbox.api.place(14,40)");
    await evaluate("window.__sandbox.api.select(3)");
    await evaluate("window.__sandbox.api.place(15,40)");
    await evaluate("window.__sandbox.api.select(0)");
    await sleep(3200);
    await shot("final-960x600.png");
    await shot("final-day.png");

    // ---- 1280-wide scaling ----
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false
    });
    await sleep(400);
    const wide = await evaluate("(function(){var app=document.getElementById('app').getBoundingClientRect();var canvas=document.getElementById('game').getBoundingClientRect();var bar=document.getElementById('hotbar').getBoundingClientRect();return {app:app.width,canvas:canvas.width,canvasHeight:canvas.height,barRight:bar.right,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth};})()");
    check("wide: layout grows to 1280", Math.abs(wide.app - 1280) < 2 && Math.abs(wide.canvas - 1280) < 2, wide);
    check("wide: no horizontal overflow", wide.scrollWidth <= wide.clientWidth + 1, wide);
    check("wide: hotbar stays inside the viewport", wide.barRight <= 1280, wide);
    await shot("wide-1280x800.png");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 960,
      height: 600,
      deviceScaleFactor: 1,
      mobile: false
    });
    await sleep(250);

    const issues = checks.filter(function (entry) { return !entry.ok; });
    const report = {
      ok: issues.length === 0,
      page: PAGE,
      viewport: [960, 600],
      checks: checks,
      failed: issues.map(function (entry) { return entry.name; }),
      screenshots: screenshots,
      exceptions: exceptions,
      consoleErrors: consoleErrors
    };
    fs.mkdirSync(path.dirname(REPORT), { recursive: true });
    fs.writeFileSync(REPORT, JSON.stringify(report, null, 2), "utf8");
    console.log(JSON.stringify({ ok: report.ok, checks: checks.length, failed: report.failed, report: REPORT, screenshots: screenshots }, null, 2));
    process.exitCode = report.ok ? 0 : 1;
  } catch (error) {
    const report = {
      ok: false,
      page: PAGE,
      error: error && error.stack ? error.stack : String(error),
      checks: checks,
      screenshots: screenshots,
      exceptions: exceptions,
      consoleErrors: consoleErrors
    };
    fs.mkdirSync(path.dirname(REPORT), { recursive: true });
    fs.writeFileSync(REPORT, JSON.stringify(report, null, 2), "utf8");
    console.error(JSON.stringify(report, null, 2));
    process.exitCode = 1;
  } finally {
    try {
      cdp.close();
    } catch (error) {
      // Ignore.
    }
    stopChrome(launched);
    await sleep(300);
    try {
      fs.rmSync(PROFILE, { recursive: true, force: true });
    } catch (error) {
      // The profile may still be locked briefly; it stays under the workbench tmp.
    }
  }
}

main().catch(function (error) {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
