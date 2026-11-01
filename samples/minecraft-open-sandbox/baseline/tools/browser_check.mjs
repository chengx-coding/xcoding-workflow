import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = resolve(process.cwd());
const PAGE = join(ROOT, "index.html");
const ARTIFACTS = join(ROOT, "artifacts");
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
].filter(Boolean);

function chromePath() {
  for (const candidate of CHROME_CANDIDATES) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error("Chrome or Edge executable not found");
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.events = [];
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const item = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          item.reject(new Error(message.error.message || "CDP error"));
        } else {
          item.resolve(message.result);
        }
      } else if (message.method) {
        this.events.push(message);
      }
    });
  }

  send(method, params = {}) {
    return new Promise((resolvePromise, reject) => {
      const id = this.nextId++;
      this.pending.set(id, { resolve: resolvePromise, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text || "Runtime evaluation failed");
    }
    return result.result ? result.result.value : undefined;
  }

  async screenshot(path) {
    const capture = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    mkdirSync(ARTIFACTS, { recursive: true });
    writeFileSync(path, Buffer.from(capture.data, "base64"));
    return path;
  }
}

async function waitFor(fn, timeoutMs, intervalMs) {
  const start = Date.now();
  let lastError = null;
  while (Date.now() - start < timeoutMs) {
    try {
      const value = await fn();
      if (value) {
        return value;
      }
    } catch (error) {
      lastError = error;
    }
    await delay(intervalMs || 100);
  }
  throw lastError || new Error("Timed out waiting for condition");
}

async function connect(port) {
  const target = await waitFor(async () => {
    const response = await fetch(`http://127.0.0.1:${port}/json/list`);
    if (!response.ok) {
      return null;
    }
    const targets = await response.json();
    return targets.find((item) => item.type === "page") || null;
  }, 12000, 150);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    ws.addEventListener("open", resolvePromise, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  return new Cdp(ws);
}

async function main() {
  const chrome = chromePath();
  const profile = mkdtempSync(join(tmpdir(), "mosswild-check-"));
  const port = 9333 + Math.floor(Math.random() * 200);
  const server = `http://127.0.0.1:${port}`;
  const child = spawn(chrome, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--remote-allow-origins=*",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--window-size=1280,800",
    "--force-device-scale-factor=1",
    new URL(`file:///${PAGE.replace(/\\/g, "/")}`).href
  ], { stdio: "ignore", windowsHide: true });

  let cdp = null;
  try {
    cdp = await connect(port);
    await cdp.send("Runtime.enable");
    await cdp.send("Page.enable");
    await cdp.send("Log.enable");
    await waitFor(async () => {
      if (!cdp) {
        return false;
      }
      return cdp.evaluate("Boolean(window.Mosswild && window.Mosswild.ready)");
    }, 15000, 100);

    const errors = [];
    const pollErrors = setInterval(() => {
      if (!cdp) {
        return;
      }
      const fresh = cdp.events.splice(0).filter((event) => {
        if (event.method === "Runtime.exceptionThrown") {
          errors.push(event.params.exceptionDetails.text || "exception");
          return false;
        }
        if (event.method === "Log.entryAdded" && event.params.entry.level === "error") {
          errors.push(event.params.entry.text);
          return false;
        }
        if (event.method === "Runtime.consoleAPICalled" && event.params.type === "error") {
          errors.push(event.params.args.map((arg) => arg.value || arg.description).join(" "));
          return false;
        }
        return true;
      });
      cdp.events.push(...fresh);
    }, 100);

    await delay(700);
    const initial = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      return {
        ready: window.Mosswild.ready,
        mode: g.mode,
        seed: g.world.seed,
        player: { x: g.player.x, y: g.player.y, hp: g.player.health },
        camera: { x: g.camera.x, y: g.camera.y },
        hotbar: g.state.hotbar,
        quest: document.getElementById('quest-title').textContent,
        clock: document.getElementById('clock-time').textContent,
        canvas: { w: document.getElementById('game').width, h: document.getElementById('game').height }
      };
    })()`);
    await cdp.screenshot(join(ARTIFACTS, "check-day.png"));

    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown", key: "d", code: "KeyD", windowsVirtualKeyCode: 68, nativeVirtualKeyCode: 68, text: "d", unmodifiedText: "d"
    });
    await delay(450);
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp", key: "d", code: "KeyD", windowsVirtualKeyCode: 68, nativeVirtualKeyCode: 68
    });
    await delay(250);
    const afterMove = await cdp.evaluate("(() => { const g = window.Mosswild.game; return { x: g.player.x, y: g.player.y, onGround: g.player.onGround, mode: g.mode }; })()");

    const target = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      const tx = Math.floor(g.player.x) + 2;
      const ty = Math.floor(g.player.y) + 1;
      const wx = (tx + 0.5) * 32 - g.camera.x;
      const wy = (ty + 0.5) * 32 - g.camera.y;
      return { tx, ty, wx, wy, before: g.world.data[ty * g.world.width + tx] };
    })()`);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: target.wx, y: target.wy });
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: target.wx, y: target.wy, button: "left", clickCount: 1 });
    await delay(900);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: target.wx, y: target.wy, button: "left", clickCount: 1 });
    await delay(250);
    const afterMine = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      const tx = ${target.tx};
      const ty = ${target.ty};
      return {
        after: g.world.data[ty * g.world.width + tx],
        dirt: g.state.inventory.dirt || 0,
        hoverProgress: g.hover && g.hover.progress
      };
    })()`);

    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown", key: "e", code: "KeyE", windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69, text: "e", unmodifiedText: "e"
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp", key: "e", code: "KeyE", windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69
    });
    await delay(350);
    const packState = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      visible: !document.getElementById('inventory-overlay').hidden,
      recipes: document.querySelectorAll('.recipe').length,
      bindables: document.querySelectorAll('[data-bind-item]').length
    }))()`);
    await cdp.screenshot(join(ARTIFACTS, "check-pack.png"));
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown", key: "e", code: "KeyE", windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69, text: "e", unmodifiedText: "e"
    });
    await cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp", key: "e", code: "KeyE", windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69
    });
    await delay(250);

    await cdp.evaluate("window.Mosswild.setTimeOfDay(22)");
    await delay(5200);
    const night = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      return { night: g.dayInfo.isNight, enemies: g.enemies.length, clock: document.getElementById('clock-time').textContent };
    })()`);
    await cdp.screenshot(join(ARTIFACTS, "check-night.png"));

    const combatTarget = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      let enemy = g.enemies.find((candidate) => !candidate.dead && candidate.dying <= 0);
      if (!enemy) {
        enemy = {
          x: g.player.x + 1.5,
          y: g.player.y,
          vx: 0,
          vy: 0,
          width: 0.68,
          height: 1.35,
          health: 7,
          maxHealth: 7,
          facing: -1,
          onGround: true,
          airTime: 0,
          attackCooldown: 3,
          hurtTimer: 0,
          dying: 0,
          dead: false,
          bobSeed: 2,
          knockDecay: 0
        };
        g.enemies.push(enemy);
      } else {
        enemy.x = g.player.x + 1.5;
        enemy.y = g.player.y;
        enemy.vx = 0;
        enemy.vy = 0;
        enemy.attackCooldown = 3;
      }
      return {
        health: enemy.health,
        maxHealth: enemy.maxHealth,
        sx: enemy.x * 32 - g.camera.x,
        sy: (enemy.y - enemy.height * 0.55) * 32 - g.camera.y
      };
    })()`);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: combatTarget.sx, y: combatTarget.sy });
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: combatTarget.sx, y: combatTarget.sy, button: "left", clickCount: 1 });
    await delay(250);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: combatTarget.sx, y: combatTarget.sy, button: "left", clickCount: 1 });
    await delay(150);
    const combat = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      const enemy = g.enemies.find((candidate) => candidate.health < candidate.maxHealth) || g.enemies[0];
      return {
        before: ${JSON.stringify(combatTarget.health)},
        health: enemy ? enemy.health : null,
        mode: g.mode,
        mouseInside: g.mouse.inside
      };
    })()`);

    const savedX = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      g.player.x += 0.3;
      g.player.health = 15;
      g.state.inventory.stone = 7;
      g.state.tools.pickaxe = { tier: 2, durability: 123 };
      g.state.flags.stonePickaxeCrafted = true;
      g.state.stats.stoneMined = 8;
      g.world.data[5 * g.world.width + 5] = 9;
      g.world.revision += 1;
      window.Mosswild.save();
      return g.player.x;
    })()`);
    await cdp.send("Page.reload", { ignoreCache: true });
    await waitFor(async () => cdp.evaluate("Boolean(window.Mosswild && window.Mosswild.ready)"), 15000, 150);
    await delay(500);
    const reloaded = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      return {
        x: g.player.x,
        mode: g.mode,
        seed: g.world.seed,
        quest: document.getElementById('quest-title').textContent,
        dirt: g.state.inventory.dirt || 0,
        stone: g.state.inventory.stone || 0,
        health: g.player.health,
        toolTier: g.state.tools.pickaxe ? g.state.tools.pickaxe.tier : null,
        durability: g.state.tools.pickaxe ? g.state.tools.pickaxe.durability : null,
        stonePickaxeCrafted: g.state.flags.stonePickaxeCrafted,
        stoneMined: g.state.stats.stoneMined,
        markerBlock: g.world.data[5 * g.world.width + 5],
        clock: document.getElementById('clock-time').textContent,
        isNight: g.dayInfo.isNight
      };
    })()`);

    clearInterval(pollErrors);
    const report = {
      ok: errors.length === 0 && initial.ready && afterMove.x > initial.player.x + 0.1
        && afterMine.after === 0 && packState.visible && packState.recipes > 0
        && night.night && Math.abs(reloaded.x - savedX) < 0.02
        && reloaded.dirt === afterMine.dirt
        && reloaded.stone === 7
        && reloaded.health === 15
        && reloaded.toolTier === 2
        && reloaded.durability === 123
        && reloaded.stonePickaxeCrafted === true
        && reloaded.stoneMined === 8
        && reloaded.markerBlock === 9
        && reloaded.isNight === true
        && combat.health !== null && combat.health < combat.before,
      errors,
      initial,
      afterMove,
      mining: { target, afterMine },
      packState,
      night,
      combat,
      savedX,
      reloaded,
      screenshots: ["artifacts/check-day.png", "artifacts/check-pack.png", "artifacts/check-night.png"]
    };
    console.log(JSON.stringify(report, null, 2));
    if (!report.ok) {
      process.exitCode = 1;
    }
  } finally {
    if (cdp) {
      try {
        cdp.ws.close();
      } catch (error) {
        // Ignore websocket shutdown noise.
      }
    }
    child.kill();
    await delay(300);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch (error) {
      // The profile may still be locked briefly on Windows.
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
