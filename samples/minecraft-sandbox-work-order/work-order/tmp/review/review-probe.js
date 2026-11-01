"use strict";

// Review-only probe (workbench tmp). Exercises M2D-SES v1.1 journeys J3, J4 and J6
// against the shipped page. It never edits product code.

const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { pathToFileURL } = require("node:url");

const PROJECT = path.resolve(__dirname, "..", "..", "..", "..", "..", "..", "project");
const OUT = __dirname;
const PROFILE = path.join(OUT, "profile");
const PAGE = path.join(PROJECT, "index.html");
const REPORT = path.join(OUT, "review-probe.json");

const checks = [];
const shots = [];

function check(name, ok, detail) {
  checks.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
  console.log((ok ? "PASS " : "FAIL ") + name + (detail === undefined ? "" : " " + JSON.stringify(detail)));
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findChrome() {
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, "Google", "Chrome", "Application", "chrome.exe") : null
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error("No Chrome found");
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.seq = 0;
    this.pending = new Map();
  }
  async open() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve);
      this.ws.addEventListener("error", reject);
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const entry = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) entry.reject(new Error(message.error.message));
        else entry.resolve(message.result);
      }
    });
  }
  send(method, params) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
  }
}

async function waitFor(action, timeout, interval) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const value = await action();
      if (value) return value;
    } catch (error) {
      // Retry while the page boots.
    }
    await sleep(interval || 120);
  }
  return null;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  fs.rmSync(PROFILE, { recursive: true, force: true });
  fs.mkdirSync(PROFILE, { recursive: true });
  const chrome = spawn(findChrome(), [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--mute-audio",
    "--window-size=960,600",
    "--remote-debugging-port=0",
    "--user-data-dir=" + PROFILE,
    "about:blank"
  ], { stdio: "ignore", windowsHide: true });

  const portFile = path.join(PROFILE, "DevToolsActivePort");
  const content = await waitFor(() => (fs.existsSync(portFile) ? fs.readFileSync(portFile, "utf8").trim() : null), 15000);
  const port = Number(content.split(/\r?\n/)[0]);
  const targets = await waitFor(async () => {
    const response = await fetch("http://127.0.0.1:" + port + "/json/list");
    const list = await response.json();
    return list.filter((target) => target.type === "page");
  }, 15000);
  const cdp = new Cdp(targets[0].webSocketDebuggerUrl);
  await cdp.open();

  const evaluate = async (expression) => {
    const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
    if (result.exceptionDetails) {
      throw new Error("eval failed: " + JSON.stringify(result.exceptionDetails));
    }
    return result.result.value;
  };
  const shot = async (name) => {
    const result = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    const target = path.join(OUT, name);
    fs.writeFileSync(target, Buffer.from(result.data, "base64"));
    shots.push(target);
  };
  const canvasRect = () => evaluate("(function(){var r=document.getElementById('game').getBoundingClientRect();return {left:r.left,top:r.top,width:r.width,height:r.height};})()");
  const tilePoint = async (tileX, tileY) => {
    const logical = await evaluate("window.__sandbox.api.screenForTile(" + tileX + "," + tileY + ")");
    const rect = await canvasRect();
    return {
      logical: logical,
      x: rect.left + logical.x * rect.width / 960,
      y: rect.top + logical.y * rect.height / 540
    };
  };

  try {
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false });
    await cdp.send("Page.navigate", { url: pathToFileURL(PAGE).href });
    await waitFor(() => evaluate("typeof window.__sandbox !== 'undefined' && document.getElementById('status').dataset.state === 'ready'"), 20000);
    await evaluate("window.__sandbox.api.setTime(0.5)");

    // ---- J3: mining feedback, held button and break progress ----
    const before = await evaluate("window.__sandbox.api.blockAt(10,41)");
    const point = await tilePoint(10, 41);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x, y: point.y, button: "none", buttons: 0 });
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: point.x, y: point.y, button: "left", buttons: 1, clickCount: 1 });
    await sleep(70);
    const during = await evaluate("window.__sandbox.api.blockAt(10,41)");
    const midState = await evaluate("window.__sandbox.api.getSnapshot()");
    await shot("j3-held-mining.png");
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: point.x, y: point.y, button: "left", buttons: 0, clickCount: 1 });
    await sleep(250);
    check("J3: a block breaks while the button is held", before !== 0 && during === 0, { before, during });
    check("J3: no break-progress/animation state is exposed while holding", typeof midState.mining === "undefined", Object.keys(midState));
    const targetOutline = await evaluate("document.getElementById('target-value').textContent");
    check("J3: a target readout is visible while hovering", /mine|build|sky/i.test(targetOutline), targetOutline);
    const particlesAfter = await evaluate("window.__sandbox.api.getSnapshot().lastToast");
    check("J3: an interaction toast is raised", !!(particlesAfter && /grass/i.test(particlesAfter.message)), particlesAfter);

    // ---- J4: dig down, inspect underground background, try the floor ----
    const dig = [];
    for (let y = 41; y <= 63; y += 1) {
      await evaluate("window.__sandbox.api.teleport(5.5," + y + ")");
      const result = await evaluate("window.__sandbox.api.mine(5," + y + ")");
      dig.push({ y, ok: result.ok, reason: result.reason });
      await sleep(30);
    }
    await evaluate("window.__sandbox.api.teleport(5.5,63)");
    await sleep(350);
    await shot("j4-bottom.png");
    const bottomBlock = await evaluate("window.__sandbox.api.blockAt(5,63)");
    const removed = await evaluate("window.__sandbox.api.blockAt(5,62)");
    check("J4: the bottom row is ordinary and was mined away", bottomBlock === 0 && removed === 0, { row62: removed, row63: bottomBlock });
    const shaftPixel = await evaluate("(function(){var p=window.__sandbox.api.screenForTile(5,55);return window.__sandbox.api.pixel(p.x,p.y);})()");
    check("J4: the exposed underground background is dark, not sky", Math.max(shaftPixel[0], shaftPixel[1], shaftPixel[2]) < 90, shaftPixel);
    const geometry = await evaluate("(function(){var bar=document.getElementById('hotbar').getBoundingClientRect();var p=window.__sandbox.api.screenForTile(5,63);var r=document.getElementById('game').getBoundingClientRect();return {hotbarLeft:bar.left,hotbarTop:bar.top,bottomRowY:r.top+p.y,bottomRowX:r.left+p.x};})()");
    check("J4: the sampled floor column is outside the hotbar", geometry.bottomRowX < geometry.hotbarLeft, geometry);

    // A held mine on the bottom row (fresh page state is not restored because the block is
    // already gone; this records the defect rather than a post-fix pass).
    await shot("j4-floor-gone.png");

    // ---- J6: 800x600 layout ----
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
    await sleep(350);
    const layout800 = await evaluate("(function(){var app=document.getElementById('app').getBoundingClientRect();var canvas=document.getElementById('game').getBoundingClientRect();var bar=document.getElementById('hotbar').getBoundingClientRect();return {app:app.width,canvas:canvas.width,barRight:bar.right,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth};})()");
    check("J6: 800x600 has no horizontal overflow", layout800.scrollWidth <= layout800.clientWidth + 1, layout800);
    check("J6: 800x600 keeps the palette inside the viewport", layout800.barRight <= 800, layout800);
    await shot("j6-800x600.png");

    // ---- orientation aid ----
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false });
    await sleep(250);
    const aids = await evaluate("({minimap: document.querySelectorAll('#minimap, .minimap, [data-minimap]').length, mapCanvas: Array.from(document.querySelectorAll('canvas')).length, statusText: document.getElementById('hud').textContent.trim()})");
    check("orientation: a minimap/map aid exists", aids.minimap > 0, aids);

    // ---- J8 discovery: state after underground trip ----
    const state = await evaluate("window.__sandbox.api.getSnapshot()");
    check("J8: the session stays functional after the underground trip", state.status === "ready" && state.hotbar.length === 9, { status: state.status });

    const failed = checks.filter((entry) => !entry.ok);
    fs.writeFileSync(REPORT, JSON.stringify({ ok: failed.length === 0, checks, shots }, null, 2), "utf8");
    console.log(JSON.stringify({ ok: failed.length === 0, checks: checks.length, failed: failed.map((entry) => entry.name), report: REPORT, shots }, null, 2));
    process.exitCode = failed.length === 0 ? 0 : 1;
  } catch (error) {
    fs.writeFileSync(REPORT, JSON.stringify({ ok: false, error: error.stack, checks, shots }, null, 2), "utf8");
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    try {
      cdp.ws.close();
    } catch (error) {}
    chrome.kill();
    await sleep(300);
  }
}

main();

