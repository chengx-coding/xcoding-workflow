"use strict";

const { spawn, execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const PROJECT = "C:\\dev\\xcoding-workflow-dev\\xcoding-workflow\\samples\\minecraft-sandbox-work-order\\project";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const TMP = path.dirname(__filename);
const PROFILE = path.join(TMP, "chrome-smoke-profile");
const PAGE = path.join(PROJECT, "index.html");
const PAGE_URL = new URL("file:///" + PAGE.replace(/\\/g, "/")).href;

let devtoolsPort = 0;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForDevtools(profile) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const portFile = path.join(profile, "DevToolsActivePort");
    if (fs.existsSync(portFile)) {
      const lines = fs.readFileSync(portFile, "utf8").trim().split(/\r?\n/);
      const candidate = Number(lines[0]);
      if (candidate > 0) {
        try {
          const response = await fetch(`http://127.0.0.1:${candidate}/json/version`);
          if (response.ok) {
            const version = await response.json();
            if (version && /Chrome/i.test(version.Browser || "")) {
              devtoolsPort = candidate;
              return version;
            }
          }
        } catch (error) {
          // Chrome is still starting.
        }
      }
    }
    await sleep(250);
  }
  throw new Error("Chrome DevTools endpoint did not start");
}

async function main() {
  try {
    fs.rmSync(PROFILE, { recursive: true, force: true });
  } catch (ignored) {
    // A previous run may still be releasing the profile; Chrome accepts a stale profile.
  }
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--remote-allow-origins=*",
      "--remote-debugging-port=0",
      `--user-data-dir=${PROFILE}`,
      "--window-size=960,600",
      "about:blank"
    ],
    { stdio: "ignore" }
  );

  try {
    const version = await waitForDevtools(PROFILE);
    let pageTarget = null;
    let targets = [];
    for (let attempt = 0; attempt < 40 && !pageTarget; attempt += 1) {
      targets = await (await fetch(`http://127.0.0.1:${devtoolsPort}/json/list`)).json();
      pageTarget =
        targets.find((target) => target.type === "page" && target.url === "about:blank") ||
        targets.find((target) => target.type === "page") ||
        null;
      if (!pageTarget) {
        await sleep(250);
      }
    }
    if (
      !pageTarget ||
      !pageTarget.webSocketDebuggerUrl ||
      !pageTarget.webSocketDebuggerUrl.includes("/devtools/page/")
    ) {
      throw new Error(
        "no attachable page target: " +
          JSON.stringify(targets.map((target) => ({ type: target.type, url: target.url })))
      );
    }

    const socket = new WebSocket(pageTarget.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });

    let nextId = 1;
    const pending = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && pending.has(message.id)) {
        const entry = pending.get(message.id);
        pending.delete(message.id);
        if (message.error) {
          entry.reject(new Error(message.error.message));
        } else {
          entry.resolve(message.result);
        }
      }
    });

    function call(method, params) {
      return new Promise((resolve, reject) => {
        const id = nextId;
        nextId += 1;
        pending.set(id, { resolve, reject });
        socket.send(JSON.stringify({ id, method, params: params || {} }));
      });
    }

    async function evaluate(expression) {
      const result = await call("Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.text || "evaluation failed");
      }
      return result.result.value;
    }

    async function waitForReady() {
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const state = await evaluate(`(() => {
          const s = window.__sandbox;
          return {
            ready: Boolean(s && s.ready),
            status: document.getElementById("status") ? document.getElementById("status").dataset.state : null
          };
        })()`);
        if (state.ready && state.status === "ready") {
          return state;
        }
        await sleep(200);
      }
      throw new Error("page did not become ready");
    }

    await call("Page.enable");
    await call("Runtime.enable");
    await call("Page.navigate", { url: PAGE_URL });
    await sleep(800);
    await waitForReady();

    const results = {};
    results.initial = await evaluate(`(() => {
      const s = window.__sandbox;
      const rect = document.getElementById("game").getBoundingClientRect();
      return {
        version: window.SandboxConfig.version,
        seed: s.world.seed,
        player: { x: s.player.x, y: s.player.y, onGround: s.player.onGround },
        camera: { x: s.camera.x, y: s.camera.y },
        selection: document.getElementById("selection").textContent,
        selectedSlot: document.querySelector("#hotbar .slot.is-selected").dataset.block,
        hint: document.getElementById("hint").textContent,
        rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
        hasSave: Boolean(localStorage.getItem(window.SandboxConfig.saveKey))
      };
    })()`);

    await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", { code: "Digit2", key: "2" }))`);
    await sleep(100);
    results.selectionAfterKey = await evaluate(`(() => ({
      selection: document.getElementById("selection").textContent,
      selectedSlot: document.querySelector("#hotbar .slot.is-selected").dataset.block,
      pressed: document.querySelector('#hotbar .slot[data-block="dirt"]').getAttribute("aria-pressed")
    }))()`);

    const startX = await evaluate(`window.__sandbox.player.x`);
    await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space", key: " " }))`);
    await sleep(220);
    results.jumpAtSpawn = await evaluate(`(() => ({
      y: window.__sandbox.player.y,
      vy: window.__sandbox.player.vy,
      onGround: window.__sandbox.player.onGround
    }))()`);
    await evaluate(`window.dispatchEvent(new KeyboardEvent("keyup", { code: "Space", key: " " }))`);
    await sleep(1200);
    results.landedAtSpawn = await evaluate(`(() => ({
      y: window.__sandbox.player.y,
      onGround: window.__sandbox.player.onGround
    }))()`);

    await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyD", key: "d" }))`);
    await sleep(700);
    await evaluate(`window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyD", key: "d" }))`);
    await sleep(100);
    results.afterWalking = await evaluate(`(() => ({
      x: window.__sandbox.player.x,
      startX: ${startX},
      camera: window.__sandbox.camera.x
    }))()`);

    await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space", key: " " }))`);
    await sleep(180);
    results.afterJump = await evaluate(`(() => ({
      y: window.__sandbox.player.y,
      vy: window.__sandbox.player.vy,
      onGround: window.__sandbox.player.onGround
    }))()`);
    await evaluate(`window.dispatchEvent(new KeyboardEvent("keyup", { code: "Space", key: " " }))`);
    await sleep(1200);
    results.afterLanding = await evaluate(`(() => ({
      y: window.__sandbox.player.y,
      onGround: window.__sandbox.player.onGround
    }))()`);

    results.mine = await evaluate(`(() => {
      const s = window.__sandbox;
      const tile = window.SandboxConfig.tileSize;
      const canvas = document.getElementById("game");
      const rect = canvas.getBoundingClientRect();
      const bx = Math.floor(s.player.x) + 3;
      let by = Math.floor(s.player.y);
      while (by < s.world.height && window.SandboxWorld.getBlock(s.world, bx, by) === 0) {
        by += 1;
      }
      const before = window.SandboxWorld.getBlock(s.world, bx, by);
      const screenX = (bx + 0.5) * tile - s.camera.x;
      const screenY = (by + 0.5) * tile - s.camera.y;
      canvas.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true,
        button: 0,
        clientX: rect.left + screenX * (rect.width / canvas.width),
        clientY: rect.top + screenY * (rect.height / canvas.height)
      }));
      const after = window.SandboxWorld.getBlock(s.world, bx, by);
      const saved = JSON.parse(localStorage.getItem(window.SandboxConfig.saveKey) || "null");
      return { bx, by, before, after, savedMine: saved ? saved.world.data[by * s.world.width + bx] : null };
    })()`);

    results.place = await evaluate(`(() => {
      const s = window.__sandbox;
      const tile = window.SandboxConfig.tileSize;
      const canvas = document.getElementById("game");
      const rect = canvas.getBoundingClientRect();
      const bx = Math.floor(s.player.x) + 2;
      let by = Math.floor(s.player.y);
      while (by < s.world.height && window.SandboxWorld.getBlock(s.world, bx, by) === 0) {
        by += 1;
      }
      const targetY = by - 1;
      const before = window.SandboxWorld.getBlock(s.world, bx, targetY);
      const screenX = (bx + 0.5) * tile - s.camera.x;
      const screenY = (by + 0.5) * tile - s.camera.y;
      canvas.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true,
        button: 2,
        clientX: rect.left + screenX * (rect.width / canvas.width),
        clientY: rect.top + screenY * (rect.height / canvas.height)
      }));
      const after = window.SandboxWorld.getBlock(s.world, bx, targetY);
      return { bx, targetY, before, after, selected: s.selected };
    })()`);

    const savedBeforeReload = await evaluate(`(() => {
      const raw = localStorage.getItem(window.SandboxConfig.saveKey);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return {
        version: parsed.version,
        seed: parsed.world.seed,
        selected: parsed.selected,
        player: parsed.player,
        bytes: raw.length
      };
    })()`);

    await call("Page.reload", { ignoreCache: true });
    await sleep(1000);
    await waitForReady();
    results.afterReload = await evaluate(`(() => {
      const s = window.__sandbox;
      const mineSaved = window.SandboxWorld.getBlock(s.world, ${results.mine.bx}, ${results.mine.by});
      const placeSaved = window.SandboxWorld.getBlock(s.world, ${results.place.bx}, ${results.place.targetY});
      return {
        seed: s.world.seed,
        selection: document.getElementById("selection").textContent,
        selectedSlot: document.querySelector("#hotbar .slot.is-selected").dataset.block,
        mineSaved,
        placeSaved,
        player: { x: s.player.x, y: s.player.y },
        camera: { x: s.camera.x, y: s.camera.y },
        status: document.getElementById("status").dataset.state
      };
    })()`);

    results.savedBeforeReload = savedBeforeReload;
    results.pageUrl = PAGE_URL;
    results.chrome = version.Browser;
    console.log(JSON.stringify(results, null, 2));
    socket.close();
  } finally {
    try {
      execFileSync("taskkill", ["/PID", String(chrome.pid), "/T", "/F"], { stdio: "ignore" });
    } catch (error) {
      try {
        chrome.kill();
      } catch (ignored) {
        // Process already gone.
      }
    }
    await sleep(1200);
    try {
      fs.rmSync(PROFILE, { recursive: true, force: true });
    } catch (ignored) {
      // The temporary profile is diagnostic input; leave it if a handle is still closing.
    }
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("SMOKE TEST FAILED:", error && error.stack ? error.stack : error);
    process.exit(1);
  });
