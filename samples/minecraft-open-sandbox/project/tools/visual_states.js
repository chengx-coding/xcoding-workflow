#!/usr/bin/env node
/**
 * Matched-state screenshot harness for Emberdeep visual review.
 *
 * Loads a fresh world, drives deterministic visual states (title, day, night,
 * underground, inventory, crafting) through the page's own test API, and
 * captures each state at the requested viewports. No third-party packages.
 *
 * The world seed is fixed (CONFIG.seed) and the state script is identical for
 * every run, so before/after captures are directly comparable.
 *
 * Usage:
 *   node tools/visual_states.js --shots visual/before
 *   node tools/visual_states.js --shots visual/after --viewport 1280x800 --viewport 800x600
 */

"use strict";

const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const PAGE = path.join(ROOT, "index.html");
const DEFAULT_VIEWPORTS = ["1280x800", "800x600"];

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
    : fs.mkdtempSync(path.join(os.tmpdir(), "emberdeep-visual-profile-"));
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
  // Clear storage at new-document start, before the game boots. Doing this
  // after load would let the previous page's beforeunload handler write a save
  // back, so a "fresh first run" would silently become a "Continue" run.
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
    source: "try{localStorage.clear();}catch(e){}"
  });
  return { child: child, cdp: cdp, profile: profile };
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

async function setViewport(cdp, width, height) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: width,
    height: height,
    deviceScaleFactor: 1,
    mobile: false
  });
}

async function reloadFresh(cdp) {
  await sleep(420);
  await waitFor(
    cdp,
    "document.readyState === 'complete' && !!(window.__game && window.__game.ready)",
    15000,
    "game boot",
    true
  );
  await sleep(450);
}

async function screenshot(cdp, target) {
  // Transient HUD (the first-run hint) would otherwise differ between a short
  // and a long run; the visual comparison needs the same stable state.
  await evaluate(
    cdp,
    "(function(){var h=document.getElementById('hint');if(h)h.classList.remove('is-visible');var t=document.getElementById('toasts');if(t)t.innerHTML='';return true;})()"
  );
  await sleep(150);
  const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, Buffer.from(shot.data, "base64"));
  const digest = crypto.createHash("sha256").update(fs.readFileSync(target)).digest("hex");
  return { path: target, sha256: digest, bytes: fs.statSync(target).size };
}

function stateScript(mode) {
  return "(function(){\n" + mode + "\n})()";
}

async function enterWorld(cdp) {
  const clicked = await evaluate(
    cdp,
    "(function(){var b=document.getElementById('btn-primary');if(!b)return false;b.click();return true;})()"
  );
  if (!clicked) {
    throw new Error("primary start button not found");
  }
  await waitFor(cdp, "window.__game.getState().mode === 'playing'", 5000, "playing mode");
  await sleep(700);
}

async function prepareDay(cdp) {
  await evaluate(
    cdp,
    stateScript([
      "var g=window.__game;",
      "g.test.give(1,12); g.test.give(4,6); g.test.give(7,4); g.test.give(100,3);",
      "g.test.give(9,4); g.test.give(12,4); g.test.give(110,1);",
      "g.test.setTime(0.3);",
      "return true;"
    ].join("\n"))
  );
  await sleep(1100);
}

async function prepareNight(cdp) {
  await evaluate(
    cdp,
    stateScript([
      "var g=window.__game;",
      "var p=g.getState().player;",
      "var x=Math.round(p.x);",
      "var y=Math.round(p.y);",
      "g.test.setBlock(x+3,y-1,12);",
      "g.test.setTime(0.8);",
      "return {x:x,y:y};"
    ].join("\n"))
  );
  // A hollow spawns on a 1.5 s timer; wait for the first one, then let the
  // scene settle so the lighting and glow are complete.
  try {
    await waitFor(cdp, "window.__game.getState().mobCount > 0", 12000, "night hollow", true);
  } catch (error) {
    // A capture without a hollow is still a valid night state.
  }
  await sleep(1400);
}

async function prepareUnderground(cdp) {
  const cave = await evaluate(
    cdp,
    stateScript([
      "var g=window.__game;",
      "function solid(x,y){var b=g.test.blockAt(x,y);return b!==0 && b!==5 && b!==4;}",
      "var best=null;",
      "for(var y=96;y<112;y+=1){",
      "  for(var x=20;x<140;x+=1){",
      "    if(g.test.blockAt(x,y)!==0) continue;",
      "    if(g.test.blockAt(x,y-1)!==0) continue;",
      "    if(g.test.blockAt(x,y+1)===0) continue;",
      "    if(g.test.blockAt(x,y+2)===0) continue;",
      "    var open=0;",
      "    for(var dx=-2;dx<=2;dx+=1){for(var dy=-2;dy<=0;dy+=1){if(g.test.blockAt(x+dx,y+dy)===0)open+=1;}}",
      "    if(open>=10){ best={x:x,y:y,open:open}; break; }",
      "  }",
      "  if(best) break;",
      "}",
      "if(!best) return null;",
      "g.test.teleport(best.x,best.y);",
      "g.test.setBlock(best.x+1,best.y,12);",
      "g.test.setTime(0.3);",
      "return best;"
    ].join("\n"))
  );
  if (!cave) {
    throw new Error("no cave pocket found for underground state");
  }
  await sleep(1300);
  return cave;
}

async function prepareInventory(cdp) {
  await evaluate(
    cdp,
    stateScript([
      "var g=window.__game;",
      "g.test.teleport(24,91);",
      "g.test.setTime(0.3);",
      "g.test.give(102,3); g.test.give(101,5); g.test.give(10,4);",
      "g.test.give(8,9); g.test.give(15,4); g.test.give(111,1); g.test.give(121,1);",
      "g.test.openInventory();",
      "return true;"
    ].join("\n"))
  );
  await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'inventory'", 3000, "inventory");
  await sleep(500);
}

async function prepareCrafting(cdp) {
  // Close the inventory so the station scan and recipe availability re-render
  // against the workbench/furnace placed below.
  await evaluate(
    cdp,
    "(function(){var b=document.querySelector('[data-action=\"close\"]');if(b)b.click();return true;})()"
  );
  await waitFor(cdp, "window.__game.getState().mode === 'playing'", 3000, "back to play");
  await evaluate(
    cdp,
    stateScript([
      "var g=window.__game;",
      "g.test.teleport(24,91);",
      "g.test.setTime(0.3);",
      "g.test.setBlock(28,90,13);",
      "g.test.setBlock(26,90,14);",
      "g.test.give(8,12); g.test.give(100,8); g.test.give(101,6); g.test.give(10,4);",
      "g.test.openInventory();",
      "return true;"
    ].join("\n"))
  );
  await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'inventory'", 3000, "crafting inventory");
  await sleep(300);
  await evaluate(
    cdp,
    "(function(){var list=document.querySelector('.recipe-list');var target=document.querySelector('[data-craft=\"wooden_pickaxe\"]');if(list&&target){var rec=target.closest('.recipe');var off=rec.getBoundingClientRect().top-list.getBoundingClientRect().top+list.scrollTop;list.scrollTop=Math.max(0,off-2);}return true;})()"
  );
  await sleep(400);
}

async function captureMenus(cdp, tag, shotsDir) {
  await evaluate(
    cdp,
    "(function(){var b=document.querySelector('[data-action=\"close\"]');if(b)b.click();return true;})()"
  );
  await waitFor(cdp, "window.__game.getState().mode === 'playing'", 3000, "playing for menus");
  await evaluate(cdp, "window.__game.test.openPause()");
  await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'pause'", 3000, "pause");
  await sleep(400);
  const pause = await screenshot(cdp, path.join(shotsDir, "menus", tag + "-pause.png"));
  await evaluate(
    cdp,
    "(function(){var b=document.querySelector('[data-action=\"help\"]');if(b)b.click();return true;})()"
  );
  await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'help'", 3000, "help");
  await sleep(300);
  const help = await screenshot(cdp, path.join(shotsDir, "menus", tag + "-help.png"));
  return { pause: pause, help: help };
}

async function dispatchMouse(cdp, type, x, y, button, buttons) {
  await cdp.send("Input.dispatchMouseEvent", {
    type: type,
    x: x,
    y: y,
    button: button || "none",
    buttons: buttons === undefined ? 0 : buttons,
    clickCount: type === "mouseMoved" ? 0 : 1
  });
}

async function resizeProbe(cdp, shotsDir) {
  await setViewport(cdp, 1280, 800);
  await cdp.send("Page.navigate", { url: "file:///" + PAGE.replace(/\\/g, "/") });
  await reloadFresh(cdp);
  await enterWorld(cdp);
  await sleep(700);

  const sizes = [
    [1280, 800],
    [960, 600],
    [800, 600]
  ];
  const results = [];
  for (let i = 0; i < sizes.length; i += 1) {
    const width = sizes[i][0];
    const height = sizes[i][1];
    // Live resize, no reload: this exercises the window resize path, not just
    // a fresh page load at the requested size.
    await setViewport(cdp, width, height);
    await sleep(750);
    const info = await evaluate(
      cdp,
      "(function(){function r(sel){var el=document.querySelector(sel);if(!el)return null;var b=el.getBoundingClientRect();return {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)};}var s=window.__game.getState();return {app:r('#app'),hotbar:r('#hotbar'),map:r('.map-panel'),view:s.view,canvas:{width:document.getElementById('game').width,height:document.getElementById('game').height},player:s.player,mode:s.mode};})()"
    );

    const targets = await evaluate(cdp, "window.__game.test.mineTargets(1)");
    let mined = null;
    if (targets.length > 0) {
      const target = targets[0];
      const point = await evaluate(
        cdp,
        "window.__game.test.tileToClient(" + target.tx + "," + target.ty + ")"
      );
      const before = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + target.tx + "," + target.ty + ")"
      );
      await dispatchMouse(cdp, "mouseMoved", point.x, point.y, "none", 0);
      await dispatchMouse(cdp, "mousePressed", point.x, point.y, "left", 1);
      await sleep(700);
      await dispatchMouse(cdp, "mouseReleased", point.x, point.y, "left", 0);
      await sleep(180);
      const after = await evaluate(
        cdp,
        "window.__game.test.blockAt(" + target.tx + "," + target.ty + ")"
      );
      mined = {
        tx: target.tx,
        ty: target.ty,
        before: before,
        after: after,
        hit: before !== 0 && after === 0
      };
    }
    const shot = await screenshot(
      cdp,
      path.join(shotsDir, "resize", width + "x" + height + ".png")
    );
    results.push({
      viewport: width + "x" + height,
      app: info.app,
      canvas: info.canvas,
      view: info.view,
      player: info.player,
      mode: info.mode,
      mined: mined,
      screenshot: shot
    });
  }
  return results;
}

async function captureViewport(cdp, width, height, shotsDir, report, menus) {
  const tag = width + "x" + height;
  const viewportDir = path.join(shotsDir, tag);
  await setViewport(cdp, width, height);
  await cdp.send("Page.navigate", { url: "file:///" + PAGE.replace(/\\/g, "/") });
  await reloadFresh(cdp);
  await sleep(500);
  const entries = [];
  entries.push(
    Object.assign({ state: "title", viewport: tag }, await screenshot(cdp, path.join(viewportDir, "01-title.png")))
  );

  await enterWorld(cdp);
  await prepareDay(cdp);
  entries.push(
    Object.assign({ state: "day", viewport: tag }, await screenshot(cdp, path.join(viewportDir, "02-day.png")))
  );

  await prepareNight(cdp);
  entries.push(
    Object.assign({ state: "night", viewport: tag }, await screenshot(cdp, path.join(viewportDir, "03-night.png")))
  );

  const cave = await prepareUnderground(cdp);
  entries.push(
    Object.assign(
      { state: "underground", viewport: tag, detail: cave },
      await screenshot(cdp, path.join(viewportDir, "04-underground.png"))
    )
  );

  await prepareInventory(cdp);
  entries.push(
    Object.assign({ state: "inventory", viewport: tag }, await screenshot(cdp, path.join(viewportDir, "05-inventory.png")))
  );

  await prepareCrafting(cdp);
  entries.push(
    Object.assign({ state: "crafting", viewport: tag }, await screenshot(cdp, path.join(viewportDir, "06-crafting.png")))
  );

  const gameState = await evaluate(
    cdp,
    "(function(){var s=window.__game.getState();return {mode:s.mode,screen:s.screen,day:s.clock.day,time:s.clock.time,blockCount:s.worldVersion};})()"
  );
  const layout = await evaluate(
    cdp,
    "(function(){function r(sel){var el=document.querySelector(sel);if(!el)return null;var b=el.getBoundingClientRect();return {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)};}return {app:r('#app'),overlay:r('#overlay'),sheet:r('.sheet'),invBody:r('.inv-body'),invGrid:r('.inv-grid'),recipeList:r('.recipe-list'),hotbar:r('#hotbar'),quest:r('.quest-panel'),map:r('.map-panel'),hint:r('#hint')};})()"
  );
  // Measure the render loop after all screenshots are captured, so the probe
  // itself cannot shift the state that was photographed.
  await evaluate(
    cdp,
    "(function(){var b=document.querySelector('[data-action=\"close\"]');if(b)b.click();return true;})()"
  );
  await waitFor(cdp, "window.__game.getState().mode === 'playing'", 3000, "playing for perf");
  await sleep(600);
  const perfPlaying = await evaluate(
    cdp,
    "(function(){return new Promise(function(resolve){var t=[],last=performance.now(),n=0;function f(now){t.push(now-last);last=now;n+=1;if(n<150){requestAnimationFrame(f);}else{t.sort(function(a,b){return a-b;});resolve({frames:n,medianMs:Math.round(t[75]*100)/100,p95Ms:Math.round(t[142]*100)/100,maxMs:Math.round(t[149]*100)/100});}}requestAnimationFrame(f);});})()"
  );
  await evaluate(cdp, "window.__game.test.openInventory()");
  await waitFor(cdp, "document.getElementById('overlay').dataset.screen === 'inventory'", 3000, "inventory for perf");
  await sleep(300);
  const perfInventory = await evaluate(
    cdp,
    "(function(){return new Promise(function(resolve){var t=[],last=performance.now(),n=0;function f(now){t.push(now-last);last=now;n+=1;if(n<150){requestAnimationFrame(f);}else{t.sort(function(a,b){return a-b;});resolve({frames:n,medianMs:Math.round(t[75]*100)/100,p95Ms:Math.round(t[142]*100)/100,maxMs:Math.round(t[149]*100)/100});}}requestAnimationFrame(f);});})()"
  );
  const perf = { playing: perfPlaying, inventory: perfInventory };
  const menuShots = menus ? await captureMenus(cdp, tag, shotsDir) : null;
  report.checks[tag] = {
    ok: entries.length === 6,
    gameState: gameState,
    layout: layout,
    perf: perf,
    menus: menuShots
  };
  report.entries = report.entries.concat(entries);
}

async function main() {
  const args = process.argv.slice(2);
  const options = { chrome: "", profile: "", shots: "", menus: false, resize: false };
  const viewports = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--chrome") {
      options.chrome = args[i + 1];
      i += 1;
    } else if (args[i] === "--profile") {
      options.profile = args[i + 1];
      i += 1;
    } else if (args[i] === "--shots") {
      options.shots = args[i + 1];
      i += 1;
    } else if (args[i] === "--viewport") {
      viewports.push(args[i + 1]);
      i += 1;
    } else if (args[i] === "--menus") {
      options.menus = true;
    } else if (args[i] === "--resize") {
      options.resize = true;
    }
  }
  const shotsDir = options.shots
    ? path.resolve(options.shots)
    : fs.mkdtempSync(path.join(os.tmpdir(), "emberdeep-visual-"));
  fs.mkdirSync(shotsDir, { recursive: true });
  const parsed = (viewports.length ? viewports : DEFAULT_VIEWPORTS).map(function parse(pair) {
    const parts = pair.toLowerCase().split("x");
    return { width: Number(parts[0]), height: Number(parts[1]) };
  });

  const report = {
    ok: false,
    page: PAGE,
    seedNote: "fresh profile + cleared localStorage; CONFIG.seed",
    viewports: parsed.map(function label(v) {
      return v.width + "x" + v.height;
    }),
    entries: [],
    checks: {}
  };

  console.error("[visual] launching chrome");
  const session = await createSession(options);
  const cdp = session.cdp;
  try {
    if (options.resize) {
      report.viewports = ["1280x800", "960x600", "800x600"];
      const results = await resizeProbe(cdp, shotsDir);
      const ok = results.every(function every(entry) {
        const parts = entry.viewport.split("x");
        const w = Number(parts[0]);
        const h = Number(parts[1]);
        return (
          entry.app &&
          entry.app.x === 0 &&
          entry.app.y === 0 &&
          entry.app.w === w &&
          entry.app.h === h &&
          entry.canvas.width === w &&
          entry.canvas.height === h &&
          entry.view.width === w &&
          entry.view.height === h &&
          entry.mined &&
          entry.mined.hit
        );
      });
      report.resize = results;
      report.checks.resize = { ok: ok, viewports: results.map(function name(entry) { return entry.viewport; }) };
      report.ok = ok;
    } else {
      for (const viewport of parsed) {
        console.error("[visual] capture " + viewport.width + "x" + viewport.height);
        await captureViewport(cdp, viewport.width, viewport.height, shotsDir, report, options.menus);
      }
      report.ok = Object.keys(report.checks).every(function every(key) {
        return report.checks[key].ok;
      });
    }
  } catch (error) {
    report.errors = [String(error && error.stack ? error.stack : error)];
    report.ok = false;
  } finally {
    cdp.close();
    session.child.kill();
  }

  const text = JSON.stringify(report, null, 2);
  fs.writeFileSync(path.join(shotsDir, "manifest.json"), text + "\n", "utf8");
  process.stdout.write(text + "\n");
  process.exitCode = report.ok ? 0 : 1;
}

main().catch(function fatal(error) {
  process.stderr.write(String(error && error.stack ? error.stack : error) + "\n");
  process.exitCode = 1;
});
