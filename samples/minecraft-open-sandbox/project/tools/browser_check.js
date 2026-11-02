#!/usr/bin/env node
/**
 * Browser interaction check for Emberdeep.
 *
 * Drives the installed Chrome over the DevTools protocol with no third-party
 * packages: real mouse and key input through Input.dispatchMouseEvent /
 * Input.dispatchKeyEvent, page reloads for persistence, and screenshots.
 *
 * The interaction-truth requirement is proven by dispatching a genuine pointer
 * press at a computed world tile, holding it for 340 ms, and verifying the
 * world changed. Ten independent trials must all succeed. A negative control
 * proves that element.click() alone does not mine.
 */

"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const PAGE = path.join(ROOT, "index.html");
const HOLD_MS = 340;
const TRIALS = 10;

function sleep(ms) {
  return new Promise(function wait(resolve) {
    setTimeout(resolve, ms);
  });
}

function findChrome(explicit) {
  const candidates = [];
  if (explicit) {
    candidates.push(explicit);
  }
  candidates.push(
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
  );
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error("no Chrome or Edge executable found; pass --chrome");
}

function httpJson(url) {
  return new Promise(function request(resolve, reject) {
    http
      .get(url, function onResponse(response) {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", function chunk(data) {
          body += data;
        });
        response.on("end", function done() {
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(error);
          }
        });
      })
      .on("error", reject);
  });
}

async function waitForFile(file, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (fs.existsSync(file)) {
      const text = fs.readFileSync(file, "utf8");
      const lines = text.split(/\r?\n/).filter(Boolean);
      if (lines.length >= 2) {
        return { port: Number(lines[0]), path: lines[1] };
      }
    }
    await sleep(50);
  }
  throw new Error("Chrome DevTools endpoint did not start: " + file);
}

class CDP {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 0;
    this.pending = new Map();
    this.events = [];
    this.ws = null;
  }

  async connect() {
    const self = this;
    await new Promise(function open(resolve, reject) {
      const ws = new WebSocket(self.wsUrl);
      self.ws = ws;
      ws.addEventListener("open", function onOpen() {
        resolve();
      });
      ws.addEventListener("error", function onError(event) {
        reject(new Error("CDP socket error: " + String(event.message || event.type)));
      });
      ws.addEventListener("message", function onMessage(event) {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (error) {
          return;
        }
        if (message.id && self.pending.has(message.id)) {
          const entry = self.pending.get(message.id);
          self.pending.delete(message.id);
          if (message.error) {
            entry.reject(new Error(message.error.message || "CDP error"));
          } else {
            entry.resolve(message.result);
          }
          return;
        }
        self.events.push(message);
      });
    });
  }

  send(method, params) {
    const self = this;
    const id = ++this.nextId;
    return new Promise(function call(resolve, reject) {
      self.pending.set(id, { resolve: resolve, reject: reject });
      self.ws.send(JSON.stringify({ id: id, method: method, params: params || {} }));
    });
  }

  close() {
    if (this.ws) {
      try {
        this.ws.close();
      } catch (error) {
        // Ignore close errors.
      }
    }
  }
}

async function createSession(options) {
  const chrome = findChrome(options.chrome);
  const profile = options.profile
    ? path.resolve(options.profile)
    : fs.mkdtempSync(path.join(os.tmpdir(), "emberdeep-profile-"));
  // A fresh profile is what makes this a genuine first run: no saved world,
  // no cached service state.
  fs.rmSync(profile, { recursive: true, force: true });
  fs.mkdirSync(profile, { recursive: true });
  const args = [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--mute-audio",
    "--remote-allow-origins=*",
    "--remote-debugging-port=0",
    "--user-data-dir=" + profile,
    "--window-size=1280,900",
    "about:blank"
  ];
  const child = spawn(chrome, args, { stdio: "ignore" });
  const endpoint = await waitForFile(path.join(profile, "DevToolsActivePort"), 20000);
  const version = await httpJson("http://127.0.0.1:" + endpoint.port + "/json/list");
  const page = version.find(function findPage(target) {
    return target.type === "page";
  });
  if (!page) {
    child.kill();
    throw new Error("no page target from Chrome");
  }
  const cdp = new CDP(page.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  return { child: child, cdp: cdp, profile: profile };
}

function collectErrors(cdp) {
  const errors = [];
  for (const event of cdp.events) {
    if (event.method === "Runtime.exceptionThrown") {
      const details = event.params.exceptionDetails;
      errors.push("exception: " + (details && details.text ? details.text : "unknown"));
    } else if (event.method === "Runtime.consoleAPICalled" && event.params.type === "error") {
      const text = (event.params.args || [])
        .map(function arg(item) {
          return item.value !== undefined ? String(item.value) : item.description || "";
        })
        .join(" ");
      errors.push("console.error: " + text);
    } else if (event.method === "Log.entryAdded" && event.params.entry.level === "error") {
      errors.push("log: " + event.params.entry.text);
    }
  }
  return errors;
}

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression: expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (result.exceptionDetails) {
    throw new Error(
      "evaluate failed: " +
        (result.exceptionDetails.text || "") +
        " " +
        (result.exceptionDetails.exception && result.exceptionDetails.exception.description
          ? result.exceptionDetails.exception.description
          : "")
    );
  }
  return result.result ? result.result.value : undefined;
}

async function waitFor(cdp, expression, timeoutMs, label, tolerant) {
  const started = Date.now();
  let lastError = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const value = await evaluate(cdp, expression);
      if (value) {
        return value;
      }
    } catch (error) {
      if (!tolerant) {
        throw error;
      }
      lastError = error;
    }
    await sleep(80);
  }
  throw new Error(
    "timed out waiting for " +
      (label || expression) +
      (lastError ? " (" + lastError.message + ")" : "")
  );
}

async function waitForGame(cdp, label) {
  await sleep(350);
  await waitFor(
    cdp,
    "document.readyState === 'complete' && !!(window.__game && window.__game.ready)",
    15000,
    label || "game boot",
    true
  );
}

async function screenshot(cdp, target) {
  const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, Buffer.from(shot.data, "base64"));
  return target;
}

async function mouse(cdp, type, x, y, button, buttons) {
  await cdp.send("Input.dispatchMouseEvent", {
    type: type,
    x: x,
    y: y,
    button: button || "none",
    buttons: buttons === undefined ? 0 : buttons,
    clickCount: type === "mouseMoved" ? 0 : 1
  });
}

async function clickAt(cdp, x, y, button) {
  const which = button || "left";
  const buttons = which === "right" ? 2 : 1;
  await mouse(cdp, "mouseMoved", x, y, "none", 0);
  await mouse(cdp, "mousePressed", x, y, which, buttons);
  await sleep(40);
  await mouse(cdp, "mouseReleased", x, y, which, 0);
}

async function pressAndHold(cdp, x, y, holdMs) {
  await mouse(cdp, "mouseMoved", x, y, "none", 0);
  const started = Date.now();
  await mouse(cdp, "mousePressed", x, y, "left", 1);
  await sleep(holdMs);
  const held = Date.now() - started;
  await mouse(cdp, "mouseReleased", x, y, "left", 0);
  return held;
}

async function pressKey(cdp, key, code, keyCode) {
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: key,
    code: code,
    windowsVirtualKeyCode: keyCode,
    nativeVirtualKeyCode: keyCode
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: key,
    code: code,
    windowsVirtualKeyCode: keyCode,
    nativeVirtualKeyCode: keyCode
  });
}

async function centerOf(cdp, selector) {
  return evaluate(
    cdp,
    "(function(){var el=document.querySelector(" +
      JSON.stringify(selector) +
      ");if(!el)return null;var r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()"
  );
}

async function main() {
  const args = process.argv.slice(2);
  const options = { chrome: "", profile: "", out: "", shots: "" };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--chrome") {
      options.chrome = args[i + 1];
    } else if (args[i] === "--profile") {
      options.profile = args[i + 1];
    } else if (args[i] === "--out") {
      options.out = args[i + 1];
    } else if (args[i] === "--shots") {
      options.shots = args[i + 1];
    }
  }
  const shotsDir = options.shots
    ? path.resolve(options.shots)
    : fs.mkdtempSync(path.join(os.tmpdir(), "emberdeep-shots-"));
  fs.mkdirSync(shotsDir, { recursive: true });

  const report = {
    ok: false,
    page: PAGE,
    holdMs: HOLD_MS,
    trials: [],
    checks: {},
    screenshots: [],
    errors: []
  };

  console.error("[browser] launching chrome");
  const session = await createSession(options);
  console.error("[browser] chrome ready");
  const cdp = session.cdp;
  const pageUrl = "file:///" + PAGE.replace(/\\/g, "/");
  try {
    console.error("[browser] navigate");
    await cdp.send("Page.navigate", { url: pageUrl });
    await waitForGame(cdp, "game boot");
    // The profile is new, so this is a genuine first run with no saved world.

    const titleState = await evaluate(
      cdp,
      "(function(){var o=document.getElementById('overlay');return {screen:o.dataset.screen||'',primary:(document.getElementById('btn-primary')||{}).textContent||'',summary:(document.querySelector('.save-summary')||{}).textContent||'',hasSave:window.__game.getState().hasSave};})()"
    );
    report.checks.firstRun = {
      ok:
        titleState.screen === "title" &&
        titleState.primary.indexOf("Enter") >= 0 &&
        titleState.hasSave === false,
      screen: titleState.screen,
      primary: titleState.primary.trim(),
      summary: titleState.summary.trim(),
      hasSave: titleState.hasSave
    };
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "01-title-first-run.png")));

    console.error("[browser] title ok, clicking start");
    const primary = await centerOf(cdp, "#btn-primary");
    if (!primary) {
      throw new Error("primary start button not found");
    }
    await clickAt(cdp, primary.x, primary.y, "left");
    await waitFor(cdp, "window.__game.getState().mode === 'playing'", 5000, "playing mode");
    await sleep(500);
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "02-day-surface.png")));

    console.error("[browser] playing, mining trials");
    const targets = await evaluate(cdp, "window.__game.test.mineTargets(10)");
    report.checks.targetCount = { ok: targets.length >= TRIALS, count: targets.length };

    let hits = 0;
    const minedTiles = [];
    for (let i = 0; i < Math.min(TRIALS, targets.length); i += 1) {
      const target = targets[i];
      const point = await evaluate(
        cdp,
        "window.__game.test.tileToClient(" + target.tx + "," + target.ty + ")"
      );
      const before = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + target.tx + "," + target.ty + ")"
      );
      const held = await pressAndHold(cdp, point.x, point.y, HOLD_MS);
      await sleep(120);
      const after = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + target.tx + "," + target.ty + ")"
      );
      const mined = before !== 0 && after === 0;
      if (mined) {
        hits += 1;
        minedTiles.push(target);
      }
      report.trials.push({
        trial: i + 1,
        tx: target.tx,
        ty: target.ty,
        blockBefore: before,
        blockAfter: after,
        holdMs: held,
        hit: mined
      });
    }
    report.checks.pointerMining = {
      ok: hits === TRIALS && report.trials.every(function every(trial) {
        return trial.holdMs >= 90;
      }),
      hits: hits,
      trials: Math.min(TRIALS, targets.length),
      minHoldMs: Math.min.apply(
        null,
        report.trials.map(function map(trial) {
          return trial.holdMs;
        })
      )
    };

    // Negative control: a synthetic element click must not break a block.
    const controlTargets = await evaluate(cdp, "window.__game.test.mineTargets(1)");
    let negative = { ok: false, detail: "no control target" };
    if (controlTargets.length > 0) {
      const control = controlTargets[0];
      const before = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + control.tx + "," + control.ty + ")"
      );
      await evaluate(cdp, "document.getElementById('game').click()");
      await sleep(420);
      const after = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + control.tx + "," + control.ty + ")"
      );
      negative = {
        ok: before === after,
        blockBefore: before,
        blockAfter: after,
        tile: { tx: control.tx, ty: control.ty }
      };
    }
    report.checks.syntheticClickDoesNotMine = negative;

    // Placement through a real right-button press.
    let placement = { ok: false, detail: "no mined tile" };
    if (minedTiles.length > 0) {
      const spot = minedTiles[0];
      const point = await evaluate(
        cdp,
        "window.__game.test.tileToClient(" + spot.tx + "," + spot.ty + ")"
      );
      const beforeCount = await evaluate(
        cdp,
        "(function(){var inv=window.__game.getState().inventory;var total=0;inv.slots.forEach(function(s){if(s&&s.id===1)total+=s.count;});return total;})()"
      );
      await clickAt(cdp, point.x, point.y, "right");
      await sleep(220);
      const afterBlock = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + spot.tx + "," + spot.ty + ")"
      );
      const afterCount = await evaluate(
        cdp,
        "(function(){var inv=window.__game.getState().inventory;var total=0;inv.slots.forEach(function(s){if(s&&s.id===1)total+=s.count;});return total;})()"
      );
      placement = {
        ok: afterBlock === 1 && afterCount === beforeCount - 1,
        tile: { tx: spot.tx, ty: spot.ty },
        blockAfter: afterBlock,
        countBefore: beforeCount,
        countAfter: afterCount
      };
    }
    report.checks.placement = placement;

    // Save through the real pause menu, then reload and continue.
    console.error("[browser] placement done, pausing");
    await pressKey(cdp, "Escape", "Escape", 27);
    await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'pause'", 4000, "pause screen");
    const saveButton = await centerOf(cdp, "[data-action='save']");
    await clickAt(cdp, saveButton.x, saveButton.y, "left");
    await sleep(350);
    const savedState = await evaluate(
      cdp,
      "(function(){var s=window.__game.getState();return {hasSave:s.hasSave,status:s.saveStatus,summary:document.querySelector('.save-summary')?document.querySelector('.save-summary').textContent:''};})()"
    );
    report.checks.manualSave = {
      ok: savedState.hasSave === true && savedState.status.kind === "ok",
      status: savedState.status,
      hasSave: savedState.hasSave
    };
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "03-pause.png")));

    console.error("[browser] reload");
    await cdp.send("Page.reload", { ignoreCache: true });
    await waitForGame(cdp, "reload boot");
    const continued = await evaluate(
      cdp,
      "(function(){var o=document.getElementById('overlay');var s=window.__game.getState();return {screen:o.dataset.screen||'',hasSave:s.hasSave,summary:(document.querySelector('.save-summary')||{}).textContent||'',primary:(document.getElementById('btn-primary')||{}).textContent||''};})()"
    );
    report.checks.continueOffer = {
      ok:
        continued.screen === "title" &&
        continued.hasSave === true &&
        continued.primary.indexOf("Continue") >= 0 &&
        continued.summary.indexOf("Day") >= 0,
      screen: continued.screen,
      primary: (continued.primary || "").trim(),
      summary: (continued.summary || "").trim()
    };
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "04-title-continue.png")));

    const continueButton = await centerOf(cdp, "#btn-primary");
    await clickAt(cdp, continueButton.x, continueButton.y, "left");
    await waitFor(cdp, "window.__game.getState().mode === 'playing'", 5000, "continued playing");
    await sleep(250);

    const placedTile = minedTiles[0] || { tx: 0, ty: 0 };
    const openHole = minedTiles[1] || { tx: 0, ty: 0 };
    const restored = await evaluate(
      cdp,
      "(function(){var g=window.__game;var s=g.getState();return {openHole:g.test.blockAt(" +
        openHole.tx +
        "," +
        openHole.ty +
        "),placed:g.test.blockAt(" +
        placedTile.tx +
        "," +
        placedTile.ty +
        "),inventory:s.inventory,status:s.saveStatus,hasSave:s.hasSave};})()"
    );
    const restoredGrass = (restored.inventory.slots || []).reduce(function sum(total, stack) {
      return total + (stack && stack.id === 1 ? stack.count : 0);
    }, 0);
    report.checks.persistence = {
      ok:
        restored.openHole === 0 &&
        restored.placed === 1 &&
        restoredGrass === 9 &&
        restored.status.kind === "ok",
      firstHole: restored.firstHole,
      placed: restored.placed,
      grassCount: restoredGrass,
      status: restored.status
    };
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "05-restored.png")));

    // Crafting through the real inventory UI: give wood, click Craft twice.
    await evaluate(cdp, "window.__game.test.give(4, 6)");
    await evaluate(cdp, "window.__game.test.openInventory()");
    await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'inventory'", 3000, "inventory for crafting");
    await sleep(200);
    const planksButton = await centerOf(cdp, "[data-craft='planks']");
    await clickAt(cdp, planksButton.x, planksButton.y, "left");
    await sleep(320);
    const benchButton = await centerOf(cdp, "[data-craft='workbench']");
    await clickAt(cdp, benchButton.x, benchButton.y, "left");
    await sleep(320);
    const crafted = await evaluate(
      cdp,
      "(function(){var s=window.__game.getState();function c(id){var t=0;s.inventory.slots.forEach(function(x){if(x&&x.id===id)t+=x.count;});return t;}return {planks:c(7),wood:c(4),workbench:c(13)};})()"
    );
    report.checks.craftingViaUi = {
      ok: crafted.workbench === 1 && crafted.planks === 0 && crafted.wood === 5,
      counts: crafted
    };
    await pressKey(cdp, "Escape", "Escape", 27);
    await waitFor(cdp, "window.__game.getState().mode === 'playing'", 3000, "back to play after crafting");

    // Night threat: hollows must appear on a dark night.
    await evaluate(cdp, "window.__game.test.setTime(0.78)");
    await waitFor(cdp, "window.__game.getState().mobCount > 0", 20000, "night hollows", true);
    await sleep(500);
    const nightState = await evaluate(
      cdp,
      "(function(){var s=window.__game.getState();return {mobCount:s.mobCount,isNight:s.isNight};})()"
    );
    report.checks.nightThreat = {
      ok: nightState.mobCount > 0 && nightState.isNight === true,
      mobCount: nightState.mobCount,
      isNight: nightState.isNight
    };

    // Visual-state evidence: night, underground with a torch, inventory.
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "06-night.png")));

    console.error("[browser] persistence verified, visual states");
    const cave = await evaluate(
      cdp,
      "(function(){var g=window.__game;for(var x=30;x<120;x+=1){for(var y=%d;y<%d;y+=1){if(g.test.blockAt(x,y)===0&&g.test.blockAt(x,y-1)===0&&g.test.blockAt(x,y+1)!==0&&g.test.blockAt(x,y+2)!==0){return {x:x,y:y};}}}return null;})()".replace(
        "%d",
        String(92)
      ).replace("%d", String(120))
    );
    if (cave) {
      await evaluate(cdp, "window.__game.test.teleport(" + cave.x + "," + cave.y + ")");
      await evaluate(cdp, "window.__game.test.setBlock(" + (cave.x + 1) + "," + cave.y + ",12)");
      await evaluate(cdp, "window.__game.test.setTime(0.25)");
      await sleep(600);
      report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "07-underground-torch.png")));
      report.checks.undergroundState = { ok: true, cave: cave };
    } else {
      report.checks.undergroundState = { ok: false, detail: "no cave pocket found" };
    }

    await evaluate(cdp, "window.__game.test.openInventory()");
    await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'inventory'", 3000, "inventory screen");
    await sleep(200);
    report.screenshots.push(await screenshot(cdp, path.join(shotsDir, "08-inventory.png")));
    report.checks.inventoryScreen = {
      ok: (await evaluate(
        cdp,
        "document.querySelectorAll('[data-slot]').length === 36 && document.querySelectorAll('[data-craft]').length >= 15"
      )) === true
    };

    report.errors = collectErrors(cdp);
    report.checks.noConsoleErrors = { ok: report.errors.length === 0, errors: report.errors };
    const required = [
      report.checks.firstRun.ok,
      report.checks.targetCount.ok,
      report.checks.pointerMining.ok,
      report.checks.syntheticClickDoesNotMine.ok,
      report.checks.placement.ok,
      report.checks.manualSave.ok,
      report.checks.continueOffer.ok,
      report.checks.persistence.ok,
      report.checks.craftingViaUi.ok,
      report.checks.nightThreat.ok,
      report.checks.inventoryScreen.ok,
      report.checks.noConsoleErrors.ok
    ];
    report.ok = required.every(Boolean);
  } catch (error) {
    report.errors.push(String(error && error.stack ? error.stack : error));
    report.ok = false;
  } finally {
    cdp.close();
    session.child.kill();
  }

  const text = JSON.stringify(report, null, 2);
  if (options.out) {
    fs.mkdirSync(path.dirname(path.resolve(options.out)), { recursive: true });
    fs.writeFileSync(path.resolve(options.out), text + "\n", "utf8");
  }
  process.stdout.write(text + "\n");
  process.exitCode = report.ok ? 0 : 1;
}

main().catch(function fatal(error) {
  process.stderr.write(String(error && error.stack ? error.stack : error) + "\n");
  process.exitCode = 1;
});
