import fs from "node:fs";
import path from "node:path";

const port = Number(process.argv[2] || 9222);
const outDir = process.argv[3];
const pageUrl = process.argv[4];
const base = "http://127.0.0.1:" + port;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = { steps: [], errors: [], console: [] };

async function getJson(route) {
  const response = await fetch(base + route);
  return response.json();
}

let version = null;
for (let attempt = 0; attempt < 60; attempt += 1) {
  try {
    version = await getJson("/json/version");
    break;
  } catch (error) {
    await sleep(250);
  }
}
if (!version) {
  throw new Error("Chrome remote debugging endpoint did not become reachable");
}

const socket = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = (event) => reject(new Error("websocket error: " + event.message));
});

let messageId = 0;
const pending = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const entry = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      entry.reject(new Error(JSON.stringify(message.error)));
    } else {
      entry.resolve(message.result);
    }
    return;
  }
  if (message.method === "Runtime.exceptionThrown") {
    results.errors.push(message.params.exceptionDetails.text || "exception");
  }
  if (message.method === "Runtime.consoleAPICalled") {
    const type = message.params.type;
    const text = (message.params.args || []).map((arg) => arg.value || arg.description || "").join(" ");
    results.console.push(type + ": " + text);
  }
};

function send(method, params, sessionId) {
  const id = ++messageId;
  const payload = { id: id, method: method, params: params || {} };
  if (sessionId) {
    payload.sessionId = sessionId;
  }
  socket.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => pending.set(id, { resolve: resolve, reject: reject }));
}

const created = await send("Target.createTarget", { url: "about:blank" });
const targetId = created.targetId;
const attached = await send("Target.attachToTarget", { targetId: targetId, flatten: true });
const session = attached.sessionId;
await send("Page.enable", {}, session);
await send("Runtime.enable", {}, session);
await send("Log.enable", {}, session);
await send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false }, session);

async function evaluate(expression) {
  const response = await send("Runtime.evaluate", { expression: expression, returnByValue: true, awaitPromise: true }, session);
  if (response.exceptionDetails) {
    throw new Error("evaluate failed: " + JSON.stringify(response.exceptionDetails));
  }
  return response.result.value;
}

async function waitReady(timeout) {
  const limit = Date.now() + (timeout || 20000);
  while (Date.now() < limit) {
    try {
      const state = await evaluate(
        "document.getElementById('status') ? document.getElementById('status').dataset.state + '|' + Boolean(window.__sandbox) : 'none'"
      );
      if (state === "ready|true") {
        return true;
      }
    } catch (error) {
      // navigation replaces the execution context
    }
    await sleep(120);
  }
  throw new Error("page did not reach the ready state");
}

async function capture(name) {
  const shot = await send("Page.captureScreenshot", { format: "png" }, session);
  fs.writeFileSync(path.join(outDir, name), Buffer.from(shot.data, "base64"));
  return name;
}

function record(label, value) {
  results.steps.push({ label: label, value: value });
  return value;
}

try {
  await send("Page.navigate", { url: pageUrl }, session);
  await send("Page.bringToFront", {}, session);
  await waitReady();
  await sleep(500);

  record("initial", await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  record("day-shot", await capture("day-960.png"));

  await evaluate("window.__sandbox.setTime(0.78)");
  await sleep(450);
  record("night-time", await evaluate("window.__sandbox.getTime()"));
  record("night-shot", await capture("night-960.png"));

  await evaluate("window.__sandbox.setTime(0.18)");
  await sleep(250);
  await evaluate("document.getElementById('pause').click()");
  await sleep(250);
  record("paused", await evaluate("window.__sandbox.isPaused()"));
  record("pause-overlay-visible", await evaluate("!document.getElementById('pause-overlay').hidden"));
  record("pause-shot", await capture("pause-960.png"));
  await evaluate("document.getElementById('resume').click()");
  await sleep(200);
  record("resumed", await evaluate("!window.__sandbox.isPaused()"));

  await evaluate("document.getElementById('help').click()");
  await sleep(250);
  record("help-count", await evaluate("document.querySelectorAll('#help-list li').length"));
  record("help-pauses-game", await evaluate("window.__sandbox.isPaused()"));
  record("help-shot", await capture("help-960.png"));
  await evaluate("document.getElementById('help-close').click()");
  await sleep(150);
  record("help-restores-game", await evaluate("!window.__sandbox.isPaused()"));

  // Real input path: hover, mouse mining, keyboard movement/jump, number key, wheel.
  const geometry = JSON.parse(
    await evaluate(`(function(){
      var s = window.__sandbox.snapshot();
      var cam = window.__sandbox.getCamera();
      var rect = document.getElementById('game').getBoundingClientRect();
      var px = Math.floor(s.player.x), py = Math.floor(s.player.y);
      var target = null;
      for (var dx = 2; dx <= 4 && !target; dx += 1) {
        for (var dy = 0; dy >= -1 && !target; dy -= 1) {
          var block = window.__sandbox.blockAt(px + dx, py + dy);
          if (block) { target = { x: px + dx, y: py + dy, block: block }; }
        }
      }
      return JSON.stringify({ player: s.player, cam: cam, rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height }, target: target, selected: s.selected });
    })()`)
  );
  const scaleX = geometry.rect.width / 960;
  const scaleY = geometry.rect.height / 540;
  const clientX = geometry.rect.left + ((geometry.target.x + 0.5) * 24 - geometry.cam.x) * scaleX;
  const clientY = geometry.rect.top + ((geometry.target.y + 0.5) * 24 - geometry.cam.y) * scaleY;
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: Math.round(clientX), y: Math.round(clientY), button: "none" }, session);
  await sleep(220);
  record("hover-target-text", await evaluate("document.getElementById('hud-target').textContent"));
  const countsBefore = JSON.parse(await evaluate("JSON.stringify(window.__sandbox.snapshot().counts)"));
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: Math.round(clientX), y: Math.round(clientY), button: "left", clickCount: 1 }, session);
  await sleep(800);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: Math.round(clientX), y: Math.round(clientY), button: "left", clickCount: 1 }, session);
  await sleep(150);
  record("mouse-mine-target", JSON.stringify(geometry.target));
  record("mouse-mine-block-after", await evaluate("window.__sandbox.blockAt(" + geometry.target.x + ", " + geometry.target.y + ")"));
  record("mouse-mine-counts-before", JSON.stringify(countsBefore));
  record("mouse-mine-counts-after", await evaluate("JSON.stringify(window.__sandbox.snapshot().counts)"));

  const jumpBefore = JSON.parse(await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  record("jump-on-ground-before", jumpBefore.player.onGround);
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 }, session);
  await sleep(200);
  const jumpSnapshot = JSON.parse(await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 }, session);
  record("jump-delta", (jumpBefore.player.y - jumpSnapshot.player.y).toFixed(3));
  await sleep(900);

  const movementBefore = JSON.parse(await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "a", code: "KeyA", windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65 }, session);
  await sleep(350);
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "a", code: "KeyA", windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65 }, session);
  await sleep(120);
  const movementAfter = JSON.parse(await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  record("keyboard-move-delta", (movementAfter.player.x - movementBefore.player.x).toFixed(3));

  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "3", code: "Digit3", windowsVirtualKeyCode: 51, nativeVirtualKeyCode: 51 }, session);
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "3", code: "Digit3", windowsVirtualKeyCode: 51, nativeVirtualKeyCode: 51 }, session);
  await sleep(150);
  record("number-key-selected", await evaluate("window.__sandbox.snapshot().selected"));
  await send(
    "Input.dispatchMouseEvent",
    {
      type: "mouseWheel",
      x: Math.round(geometry.rect.left + geometry.rect.width / 2),
      y: Math.round(geometry.rect.top + geometry.rect.height / 2),
      deltaX: 0,
      deltaY: 120
    },
    session
  );
  await sleep(180);
  record("wheel-selected", await evaluate("window.__sandbox.snapshot().selected"));
  record("selected-shot", await capture("selected-slot.png"));

  const mined = await evaluate(`(function(){
    var s = window.__sandbox.snapshot();
    var px = Math.floor(s.player.x);
    var py = Math.floor(s.player.y);
    var before = window.__sandbox.snapshot().counts;
    for (var dx = 2; dx <= 4; dx += 1) {
      for (var dy = 0; dy >= -2; dy -= 1) {
        var x = px + dx;
        var y = py + dy;
        var block = window.__sandbox.blockAt(x, y);
        if (block) {
          var result = window.__sandbox.mineAt(x, y);
          return JSON.stringify({ ok: result.ok, block: result.block, x: x, y: y, before: before, after: window.__sandbox.snapshot().counts });
        }
      }
    }
    return JSON.stringify({ ok: false, reason: "no target" });
  })()`);
  record("mine-result", mined);

  const placed = await evaluate(`(function(){
    var s = window.__sandbox.snapshot();
    var px = Math.floor(s.player.x);
    var py = Math.floor(s.player.y);
    var before = window.__sandbox.snapshot().counts;
    for (var dx = 2; dx <= 4; dx += 1) {
      var result = window.__sandbox.placeNextTo(px + dx, py);
      if (result && (result.ok || result.reason === "player" || result.reason === "occupied")) {
        return JSON.stringify({ ok: result.ok, reason: result.reason, block: result.block, x: result.x, y: result.y, before: before, after: window.__sandbox.snapshot().counts });
      }
    }
    return JSON.stringify({ ok: false, reason: "no target" });
  })()`);
  record("place-result", placed);

  const minedInfo = JSON.parse(mined);
  const placedInfo = JSON.parse(placed);
  await evaluate("window.__sandbox.save()");
  await sleep(300);
  await send("Page.reload", {}, session);
  await waitReady();
  await sleep(600);
  record("persist-snapshot", await evaluate("JSON.stringify(window.__sandbox.snapshot())"));
  if (minedInfo.ok) {
    record("persist-mined-block-empty", await evaluate("window.__sandbox.blockAt(" + minedInfo.x + ", " + minedInfo.y + ")"));
  }
  if (placedInfo.ok) {
    record("persist-placed-block", await evaluate("window.__sandbox.blockAt(" + placedInfo.x + ", " + placedInfo.y + ")"));
    record("persist-placed-expected", placedInfo.block);
  }
  record("persist-counts", await evaluate("JSON.stringify(window.__sandbox.snapshot().counts)"));
  record("persist-mine-before", JSON.stringify(minedInfo.before));
  record("persist-mine-after", JSON.stringify(minedInfo.after));
  record("persist-place-after", JSON.stringify(placedInfo.after));
  record("persist-storage-present", await evaluate("Boolean(localStorage.getItem('xc-sandbox-sample-v1'))"));

  await evaluate("window.__sandbox.seed('777')");
  await sleep(300);
  record("seed-777", await evaluate("window.__sandbox.getWorld().seed"));
  record("seed-777-shot", await capture("seed-777.png"));
  await evaluate("window.__sandbox.save()");
  await sleep(250);
  await send("Page.reload", {}, session);
  await waitReady();
  await sleep(500);
  record("reload-777-seed", await evaluate("window.__sandbox.getWorld().seed"));

  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false }, session);
  await sleep(700);
  record("wide-app-width", await evaluate("document.getElementById('app').getBoundingClientRect().width"));
  record("wide-canvas-width", await evaluate("document.getElementById('game').getBoundingClientRect().width"));
  record("wide-shot", await capture("wide-1280.png"));

  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, session);
  await send("Emulation.setDeviceMetricsOverride", { width: 960, height: 600, deviceScaleFactor: 1, mobile: false }, session);
  await send("Page.reload", {}, session);
  await waitReady();
  await sleep(600);
  record("reduced-matches", await evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"));
  record("reduced-shot", await capture("reduced-960.png"));

  record("final-status", await evaluate("document.getElementById('status').dataset.state"));
} finally {
  try {
    await send("Target.closeTarget", { targetId: targetId });
  } catch (error) {
    // best effort
  }
  socket.close();
}

fs.writeFileSync(path.join(outDir, "visual-verify.json"), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results, null, 2));
