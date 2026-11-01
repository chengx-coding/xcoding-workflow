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
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const pending = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          pending.reject(new Error(message.error.message || "CDP error"));
        } else {
          pending.resolve(message.result);
        }
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
      throw new Error(result.exceptionDetails.text || "Runtime exception");
    }
    return result.result ? result.result.value : undefined;
  }

  async screenshot(name) {
    const capture = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    mkdirSync(ARTIFACTS, { recursive: true });
    const path = join(ARTIFACTS, name);
    writeFileSync(path, Buffer.from(capture.data, "base64"));
    return path;
  }
}

async function waitFor(fn, timeoutMs = 12000, intervalMs = 100) {
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
    await delay(intervalMs);
  }
  throw lastError || new Error("Timed out");
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

async function key(cdp, keyName, code, virtualKey, text) {
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown", key: keyName, code, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey,
    text: text || "", unmodifiedText: text || ""
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp", key: keyName, code, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey
  });
}

async function clickAt(cdp, x, y, button = "left") {
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mousePressed", x, y, button, clickCount: 1
  });
  await delay(40);
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mouseReleased", x, y, button, clickCount: 1
  });
}

async function clickRecipe(cdp, recipeId) {
  const result = await cdp.evaluate(`(() => {
    const button = document.querySelector('[data-recipe="${recipeId}"]');
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  })()`);
  await delay(140);
  return result;
}

async function main() {
  const chrome = chromePath();
  const profile = mkdtempSync(join(tmpdir(), "mosswild-quest-"));
  const port = 9533 + Math.floor(Math.random() * 200);
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
    await waitFor(() => cdp.evaluate("Boolean(window.Mosswild && window.Mosswild.ready)"), 15000, 100);

    const errors = [];
    cdp.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.method === "Runtime.exceptionThrown") {
        errors.push(message.params.exceptionDetails.text || "exception");
      }
      if (message.method === "Log.entryAdded" && message.params.entry.level === "error") {
        errors.push(message.params.entry.text);
      }
    });

    const steps = [];
    const snapshot = async (name) => {
      await cdp.screenshot(name);
      return cdp.evaluate(`(() => {
        const g = window.Mosswild.game;
        return {
          mode: g.mode,
          quest: document.getElementById('quest-title').textContent,
          questCount: document.getElementById('quest-count').textContent,
          hotbar: g.state.hotbar,
          tools: g.state.tools,
          flags: g.state.flags,
          inventory: g.state.inventory,
          nearBench: g.nearWorkbench,
          pos: { x: g.player.x, y: g.player.y }
        };
      })()`);
    };

    const prepared = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      g.state.inventory.log = 4;
      g.state.stats.logsGathered = 4;
      window.Mosswild.ui.refreshQuest(true);
      return { log: g.state.inventory.log, flags: g.state.flags };
    })()`);
    steps.push({ action: "prepare logs", prepared });

    await key(cdp, "e", "KeyE", 69, "e");
    await delay(300);
    const packOpened = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      tutorialHidden: document.getElementById('tutorial-card').classList.contains('is-dismissed'),
      benchNear: document.getElementById('bench-status').classList.contains('is-near')
    }))()`);
    steps.push({ action: "open pack", packOpened });

    const craftedPlanks = [];
    for (let i = 0; i < 4; i += 1) {
      craftedPlanks.push(await clickRecipe(cdp, "planks"));
    }
    const afterPlanks = await cdp.evaluate("(() => ({ planks: window.Mosswild.game.state.inventory.planks, mode: window.Mosswild.game.mode, recipeCount: document.querySelectorAll('.recipe').length }))()");
    steps.push({ action: "craft planks x4", craftedPlanks, afterPlanks });

    const workbenchClick = await clickRecipe(cdp, "workbench");
    const afterWorkbenchCraft = await cdp.evaluate(`(() => ({
      result: ${JSON.stringify(workbenchClick)},
      workbench: window.Mosswild.game.state.inventory.workbench || 0,
      workbenchCrafted: window.Mosswild.game.state.flags.workbenchCrafted,
      quest: document.getElementById('quest-title').textContent
    }))()`);
    steps.push({ action: "craft workbench", afterWorkbenchCraft });

    await key(cdp, "e", "KeyE", 69, "e");
    await delay(200);
    const workbenchSlot = await cdp.evaluate("window.Mosswild.game.state.hotbar.indexOf('workbench')");
    await cdp.evaluate(`document.querySelector('.slot[data-slot="${workbenchSlot}"]').click()`);
    await delay(120);

    const benchTarget = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      const px = Math.floor(g.player.x);
      const py = Math.floor(g.player.y);
      for (const dx of [2, 3, -2, 4, -3, 5, -4]) {
        const tx = px + dx;
        const surface = g.world.surface[tx];
        const ty = surface - 1;
        const block = g.world.data[ty * g.world.width + tx];
        if (block === 0) {
          return {
            tx, ty,
            sx: (tx + 0.5) * 32 - g.camera.x,
            sy: (ty + 0.5) * 32 - g.camera.y,
            selected: g.state.hotbar[g.state.selectedSlot]
          };
        }
      }
      return null;
    })()`);
    if (!benchTarget) {
      throw new Error("No free cell found for workbench");
    }
    await clickAt(cdp, benchTarget.sx, benchTarget.sy, "right");
    await delay(350);
    const afterBenchPlace = await cdp.evaluate(`(() => ({
      flags: window.Mosswild.game.state.flags,
      nearBench: window.Mosswild.game.nearWorkbench,
      workbenchLeft: window.Mosswild.game.state.inventory.workbench || 0,
      quest: document.getElementById('quest-title').textContent
    }))()`);
    steps.push({ action: "place workbench", target: benchTarget, afterBenchPlace });
    await cdp.screenshot("quest-workbench.png");

    const injected = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      g.state.inventory.stone = 8;
      g.state.inventory.stick = 4;
      window.Mosswild.ui.refreshQuest(true);
      return { stone: g.state.inventory.stone, stick: g.state.inventory.stick };
    })()`);
    steps.push({ action: "inject stone and sticks", injected });

    await key(cdp, "e", "KeyE", 69, "e");
    await delay(250);
    const benchReady = await cdp.evaluate(`(() => ({
      near: window.Mosswild.game.nearWorkbench,
      chip: document.getElementById('bench-status').textContent,
      toolButtonDisabled: document.querySelector('[data-recipe="stone_pickaxe"]').disabled
    }))()`);
    const pickClick = await clickRecipe(cdp, "stone_pickaxe");
    const afterPick = await cdp.evaluate(`(() => ({
      result: ${JSON.stringify(pickClick)},
      tier: window.Mosswild.game.state.tools.pickaxe && window.Mosswild.game.state.tools.pickaxe.tier,
      stonePickaxeCrafted: window.Mosswild.game.state.flags.stonePickaxeCrafted,
      quest: document.getElementById('quest-title').textContent
    }))()`);
    steps.push({ action: "craft stone pickaxe", benchReady, afterPick });

    await key(cdp, "e", "KeyE", 69, "e");
    await delay(200);
    const lateResources = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      g.state.inventory.iron = 3;
      g.state.inventory.coal = 3;
      g.state.inventory.torch = (g.state.inventory.torch || 0) + 1;
      g.state.stats.stoneMined = 8;
      g.state.stats.coalFound = 3;
      g.state.stats.ironFound = 3;
      window.Mosswild.ui.refreshQuest(true);
      return { mode: g.mode, quest: document.getElementById('quest-title').textContent };
    })()`);
    steps.push({ action: "inject late resources", lateResources });

    await key(cdp, "e", "KeyE", 69, "e");
    await delay(250);
    const lanternClick = await clickRecipe(cdp, "lantern");
    const afterLanternCraft = await cdp.evaluate(`(() => ({
      result: ${JSON.stringify(lanternClick)},
      lanterns: window.Mosswild.game.state.inventory.lantern || 0,
      lanternCrafted: window.Mosswild.game.state.flags.lanternCrafted,
      quest: document.getElementById('quest-title').textContent,
      disabled: document.querySelector('[data-recipe="lantern"]') ? document.querySelector('[data-recipe="lantern"]').disabled : null
    }))()`);
    steps.push({ action: "craft lantern", afterLanternCraft });
    await key(cdp, "e", "KeyE", 69, "e");
    await delay(200);

    const lanternSlot = await cdp.evaluate("window.Mosswild.game.state.hotbar.indexOf('lantern')");
    await cdp.evaluate(`document.querySelector('.slot[data-slot="${lanternSlot}"]').click()`);
    await delay(120);
    const lanternTarget = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      const px = Math.floor(g.player.x);
      const py = Math.floor(g.player.y);
      for (const dx of [-1, 1, -3, 3, -2, 2, -4, 4]) {
        const tx = px + dx;
        if (tx < 1 || tx >= g.world.width - 1) continue;
        const surface = g.world.surface[tx];
        const ty = surface - 1;
        if (g.world.data[ty * g.world.width + tx] !== 0) continue;
        return {
          tx, ty,
          sx: (tx + 0.5) * 32 - g.camera.x,
          sy: (ty + 0.5) * 32 - g.camera.y
        };
      }
      return null;
    })()`);
    if (!lanternTarget) {
      throw new Error("No free cell found for lantern");
    }
    await clickAt(cdp, lanternTarget.sx, lanternTarget.sy, "right");
    await delay(1900);
    const afterLanternPlace = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      lanternPlaced: window.Mosswild.game.state.flags.lanternPlaced,
      overlayVisible: !document.getElementById('done-overlay').hidden,
      quest: document.getElementById('quest-title').textContent,
      title: document.getElementById('done-title').textContent,
      complete: document.getElementById('quest-state').textContent
    }))()`);
    steps.push({ action: "place lantern", target: lanternTarget, afterLanternPlace });
    await delay(400);
    await cdp.screenshot("quest-complete.png");

    await cdp.evaluate("document.getElementById('button-continue').click()");
    await delay(250);
    const afterContinue = await cdp.evaluate("window.Mosswild.game.mode");

    await key(cdp, "Escape", "Escape", 27);
    await delay(300);
    const pauseState = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      visible: !document.getElementById('pause-overlay').hidden,
      text: document.getElementById('pause-time').textContent
    }))()`);
    await cdp.screenshot("quest-pause.png");
    await key(cdp, "Escape", "Escape", 27);
    await delay(250);

    await cdp.evaluate("window.Mosswild.game.player.health = 0");
    await delay(300);
    const deathState = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      visible: !document.getElementById('death-overlay').hidden
    }))()`);
    await cdp.screenshot("quest-death.png");
    await cdp.evaluate("document.getElementById('button-respawn').click()");
    await delay(350);
    const respawnState = await cdp.evaluate(`(() => ({ mode: window.Mosswild.game.mode, health: window.Mosswild.game.player.health }))()`);

    await key(cdp, "h", "KeyH", 72, "h");
    await delay(300);
    const helpState = await cdp.evaluate(`(() => ({
      mode: window.Mosswild.game.mode,
      visible: !document.getElementById('help-overlay').hidden,
      hudInert: document.getElementById('game-hud').inert
    }))()`);
    await cdp.screenshot("quest-help.png");
    await key(cdp, "h", "KeyH", 72, "h");
    await delay(250);

    await key(cdp, "Escape", "Escape", 27);
    await delay(250);
    const firstWorldSeed = await cdp.evaluate("window.Mosswild.game.world.seed");
    await cdp.evaluate("document.getElementById('button-new-world').click()");
    await delay(150);
    await cdp.evaluate("document.getElementById('button-new-world').click()");
    await delay(700);
    const newWorldState = await cdp.evaluate(`(() => {
      const g = window.Mosswild.game;
      return {
        mode: g.mode,
        seed: g.world.seed,
        quest: document.getElementById('quest-title').textContent,
        tutorialHidden: document.getElementById('tutorial-card').classList.contains('is-dismissed'),
        pauseHidden: document.getElementById('pause-overlay').hidden
      };
    })()`);

    const final = await snapshot("quest-final.png");
    const report = {
      steps,
      afterContinue,
      pauseState,
      deathState,
      respawnState,
      helpState,
      firstWorldSeed,
      newWorldState,
      final,
      errors,
      screenshots: [
        "artifacts/quest-workbench.png",
        "artifacts/quest-complete.png",
        "artifacts/quest-pause.png",
        "artifacts/quest-death.png",
        "artifacts/quest-help.png",
        "artifacts/quest-final.png"
      ]
    };
    report.ok = errors.length === 0
      && packOpened.mode === "inventory"
      && packOpened.tutorialHidden
      && afterWorkbenchCraft.workbenchCrafted
      && afterBenchPlace.flags.workbenchPlaced
      && afterBenchPlace.nearBench
      && benchReady.near
      && afterPick.tier === 2
      && afterPick.stonePickaxeCrafted
      && afterLanternCraft.lanternCrafted
      && afterLanternPlace.mode === "done"
      && afterLanternPlace.overlayVisible
      && afterContinue === "playing"
      && pauseState.mode === "paused"
      && deathState.mode === "dead"
      && deathState.visible
      && respawnState.mode === "playing"
      && respawnState.health === 20
      && helpState.mode === "help"
      && helpState.visible
      && helpState.hudInert
      && newWorldState.mode === "playing"
      && newWorldState.seed !== firstWorldSeed
      && newWorldState.quest === "Gather oak logs"
      && newWorldState.tutorialHidden === false
      && newWorldState.pauseHidden;
    console.log(JSON.stringify(report, null, 2));
    if (!report.ok) {
      process.exitCode = 1;
    }
  } finally {
    if (cdp) {
      try {
        cdp.ws.close();
      } catch (error) {
        // ignore
      }
    }
    child.kill();
    await delay(300);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch (error) {
      // The browser can hold its profile files for a moment on Windows.
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
