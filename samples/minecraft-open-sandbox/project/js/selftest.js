(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const mode = params.get("selftest");
  if (!mode) {
    return;
  }

  const report = {
    schema: "cubewood-selftest/1",
    mode: mode,
    ok: false,
    steps: [],
    errors: []
  };

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const B = CONFIG.blocks;

  window.addEventListener("error", function (event) {
    report.errors.push(event.message || "unknown error");
  });
  window.addEventListener("unhandledrejection", function (event) {
    report.errors.push(String(event.reason));
  });

  function element(id) {
    return document.getElementById(id);
  }

  function assert(condition, message) {
    if (!condition) {
      throw new Error(message || "assertion failed");
    }
  }

  function frames(count, api) {
    return new Promise(function (resolve) {
      window.setTimeout(function () {
        if (api && api.commands && api.commands.renderNow) {
          api.commands.renderNow();
        }
        resolve();
      }, 24 * (count || 2));
    });
  }

  function delay(milliseconds) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, milliseconds);
    });
  }

  async function step(name, fn) {
    try {
      const detail = await fn();
      report.steps.push({ name: name, ok: true, detail: detail === undefined ? null : detail });
      return true;
    } catch (error) {
      report.steps.push({ name: name, ok: false, error: error && error.message ? error.message : String(error) });
      return false;
    }
  }

  function count(inventory, id) {
    return inventory.items[id] || 0;
  }

  function findFlat(world, span) {
    const heights = [];
    for (let x = 0; x < world.width; x += 1) {
      heights.push(WORLD.terrainHeightAt(world, x));
    }
    for (let x = 14; x < world.width - span - 4; x += 1) {
      let min = heights[x];
      let max = heights[x];
      for (let offset = 1; offset <= span; offset += 1) {
        min = Math.min(min, heights[x + offset]);
        max = Math.max(max, heights[x + offset]);
      }
      if (max - min <= 1 && min > 32 && min < 64) {
        return { x: x, ground: min };
      }
    }
    return { x: Math.floor(world.width / 2), ground: heights[Math.floor(world.width / 2)] };
  }

  function finish() {
    report.ok = report.errors.length === 0 && report.steps.length > 0 && report.steps.every(function (entry) {
      return entry.ok;
    });
    const pre = element("selftest-results");
    pre.textContent = JSON.stringify(report);
    document.title = "selftest:" + (report.ok ? "ok" : "fail");
    document.documentElement.dataset.selftest = report.ok ? "ok" : "fail";
  }

  function whenReady(callback) {
    if (window.__cubewood && window.__cubewood.ready) {
      callback(window.__cubewood);
      return;
    }
    window.setTimeout(function () { whenReady(callback); }, 40);
  }

  async function runSaveWrite(api) {
    const game = api.game;
    const commands = api.commands;
    const spawn = WORLD.findSpawn(game.world);
    const marker = { x: Math.floor(spawn.x) + 3, y: Math.floor(spawn.y) - 1 };
    await step("prepare-save-state", function () {
      commands.hideWelcome();
      commands.setTime(0.42);
      if (!game.settings.muted) {
        commands.toggleMute();
      }
      commands.setDay(6);
      commands.give(B.cobblestone, 7);
      commands.give(B.torch, 3);
      commands.bulkSet([{ x: marker.x, y: marker.y, id: B.glass }]);
      commands.teleport(spawn.x, spawn.y);
      assert(Math.abs(game.player.x - spawn.x) < 0.6, "player did not move to spawn");
      return { marker: marker, player: { x: game.player.x, y: game.player.y } };
    });
    await step("write-save", function () {
      const result = commands.saveNow();
      assert(result.ok, "save reported failure");
      assert(api.storageKind() === "local", "storage is not local: " + api.storageKind());
      const raw = window.localStorage.getItem(CONFIG.saveKey);
      assert(raw && raw.length > 1000, "save payload missing or too small");
      const envelope = window.SandboxSave.parse(raw);
      assert(envelope.seed === game.seed, "saved seed mismatch");
      assert(envelope.clock.day === 6, "saved day mismatch");
      return { bytes: raw.length, seed: envelope.seed, day: envelope.clock.day };
    });
  }

  async function runSaveRead(api) {
    const game = api.game;
    const spawn = WORLD.findSpawn(game.world);
    const marker = { x: Math.floor(spawn.x) + 3, y: Math.floor(spawn.y) - 1 };
    await step("loads-saved-world", function () {
      assert(game.loadedFromSave === true, "game did not load from a save");
      assert(game.clock.day === 6, "saved day did not restore, got " + game.clock.day);
      assert(Math.abs(game.player.x - spawn.x) < 0.6, "saved player position did not restore");
      return { day: game.clock.day, player: { x: game.player.x, y: game.player.y } };
    });
    await step("restores-world-edit", function () {
      const id = WORLD.getBlock(game.world, marker.x, marker.y);
      assert(id === B.glass, "saved glass block missing at " + marker.x + "," + marker.y + " (found " + id + ")");
      return { block: id };
    });
    await step("restores-inventory-and-settings", function () {
      assert(count(game.inventory, B.cobblestone) === 7, "saved cobblestone missing");
      assert(count(game.inventory, B.torch) === 3, "saved torches missing");
      assert(game.settings.muted === true, "saved mute setting missing");
      return { cobblestone: count(game.inventory, B.cobblestone) };
    });
  }

  async function runFull(api) {
    const game = api.game;
    const commands = api.commands;

    await step("boot", function () {
      assert(api.ready === true, "api not ready");
      assert(game.world.width === CONFIG.worldWidth, "world width mismatch");
      assert(game.world.height === CONFIG.worldHeight, "world height mismatch");
      assert(element("status").dataset.state === "ready", "status is not ready");
      const colors = commands.scanCanvas();
      assert(colors >= 8, "canvas looks blank (" + colors + " colour buckets)");
      return { colors: colors, tiles: game.world.width * game.world.height };
    });

    await step("first-run-welcome", function () {
      assert(element("welcome").hidden === false, "welcome overlay is not visible on first run");
      assert(element("welcome-play"), "play button missing");
      assert(element("welcome-guide"), "guide button missing");
      assert(element("welcome-new"), "new-world button missing");
      assert(element("welcome").textContent.indexOf("Play now") >= 0, "welcome has no play label");
    });

    await step("welcome-play-click", function () {
      element("welcome-play").click();
      assert(element("welcome").hidden === true, "welcome did not close after Play");
      return { hidden: true };
    });

    await step("primary-system-buttons", function () {
      const ids = ["btn-quests", "btn-inventory", "btn-craft", "btn-guide", "btn-backdrop", "btn-save", "btn-menu"];
      ids.forEach(function (id) {
        const button = element(id);
        assert(button, "missing button " + id);
        const rect = button.getBoundingClientRect();
        assert(rect.width > 20 && rect.height > 10, "button not visible: " + id);
      });
      return ids;
    });

    await step("quest-tracker-visible", function () {
      const tracker = element("quest-tracker");
      assert(tracker.classList.contains("is-hidden") === false, "quest tracker is hidden on first run");
      assert(element("quest-title").textContent.length > 2, "quest tracker has no active title");
      assert(element("quest-list").children.length === 8, "quest list should show eight tasks");
      assert(element("quest-hint").textContent.length > 10, "quest tracker has no hint");
    });

    await step("inventory-button-opens-panel", function () {
      element("btn-inventory").click();
      commands.renderNow();
      assert(element("panel-inventory").hidden === false, "inventory panel did not open");
      element("panel-inventory").querySelector("[data-close]").click();
      assert(element("panel-inventory").hidden === true, "inventory panel did not close");
    });

    await step("crafting-planks-with-click", function () {
      commands.give(B.wood, 2);
      commands.openPanel("craft");
      commands.renderNow();
      assert(element("panel-craft").hidden === false, "crafting panel did not open");
      const button = document.querySelector('[data-craft="planks"]');
      assert(button, "planks craft button missing");
      assert(button.disabled === false, "planks should be craftable after gathering wood");
      const before = count(game.inventory, B.planks);
      button.click();
      assert(count(game.inventory, B.planks) >= before + 4, "planks were not added to the inventory");
      commands.closePanels();
      return { planks: count(game.inventory, B.planks) };
    });

    await step("mining-produces-drops-and-backdrop", function () {
      const px = Math.floor(game.player.x);
      const py = Math.floor(game.player.y);
      const target = { x: px + 2, y: py - 1 };
      commands.bulkSet([{ x: target.x, y: target.y, id: B.wood }]);
      commands.teleport(px + 0.5, py);
      const before = count(game.inventory, B.wood);
      const result = commands.mineAt(target.x, target.y);
      assert(result.ok, "mining returned failure");
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.air, "mined block was not removed");
      assert(count(game.inventory, B.wood) === before + 1, "wood drop missing");
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.kind === "edit", "backdrop pulse is not an edit");
      assert(pulse.before === "Wood" && pulse.after === "Air", "backdrop labels wrong: " + pulse.before + " -> " + pulse.after);
      api.ui.showPulse(pulse, { pos: "edit" });
      assert(element("state-pulse").hidden === false, "before/after panel is not visible after an edit");
      assert(element("pulse-labels").textContent.indexOf("Wood") >= 0, "before/after labels not rendered");
      return { wood: count(game.inventory, B.wood), pulse: pulse.before + "->" + pulse.after };
    });

    await step("placement-and-undo-redo", function () {
      const px = Math.floor(game.player.x);
      const py = Math.floor(game.player.y);
      const target = { x: px + 2, y: py - 1 };
      commands.give(B.planks, 3);
      const slot = game.inventory.hotbar.indexOf(B.planks);
      commands.selectSlot(slot);
      const before = count(game.inventory, B.planks);
      const placed = commands.placeAt(target.x, target.y);
      assert(placed.ok, "placement failed: " + placed.reason);
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.planks, "placed block missing");
      assert(count(game.inventory, B.planks) === before - 1, "placement did not consume a block");
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.after === "Planks", "placement pulse after label wrong");
      assert(commands.undo() === true, "undo failed");
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.air, "undo did not remove the block");
      assert(commands.redo() === true, "redo failed");
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.planks, "redo did not restore the block");
      return { placed: B.planks };
    });

    await step("real-pointer-mining-and-placement", async function () {
      const px = Math.floor(game.player.x);
      const py = Math.floor(game.player.y);
      const target = { x: px + 3, y: py - 1 };
      commands.bulkSet([{ x: target.x, y: target.y, id: B.wood }]);
      commands.teleport(px + 0.5, py);
      commands.renderNow();
      const canvas = element("game");
      const rect = canvas.getBoundingClientRect();
      function toClient(tileX, tileY) {
        const tile = CONFIG.tileSize * game.settings.zoom;
        const screenX = (tileX + 0.5) * tile - game.camera.x;
        const screenY = (tileY + 0.5) * tile - game.camera.y;
        return {
          clientX: rect.left + screenX * (rect.width / game.viewport.width),
          clientY: rect.top + screenY * (rect.height / game.viewport.height)
        };
      }
      const point = toClient(target.x, target.y);
      canvas.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: point.clientX, clientY: point.clientY }));
      commands.tick(0.016);
      assert(game.hover && game.hover.x === target.x && game.hover.y === target.y, "pointer hover did not land on the target tile");
      const before = count(game.inventory, B.wood);
      canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0, clientX: point.clientX, clientY: point.clientY }));
      for (let index = 0; index < 24; index += 1) {
        commands.tick(0.08);
      }
      canvas.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, button: 0, clientX: point.clientX, clientY: point.clientY }));
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.air, "real pointer mining did not break the block");
      assert(count(game.inventory, B.wood) === before + 1, "real pointer mining did not grant the drop");

      commands.give(B.planks, 2);
      commands.selectSlot(game.inventory.hotbar.indexOf(B.planks));
      commands.renderNow();
      const placePoint = toClient(target.x, target.y);
      canvas.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: placePoint.clientX, clientY: placePoint.clientY }));
      commands.tick(0.016);
      assert(game.hover.mode === "place", "hover did not switch to placement mode");
      canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 2, clientX: placePoint.clientX, clientY: placePoint.clientY }));
      assert(WORLD.getBlock(game.world, target.x, target.y) === B.planks, "real right-click did not place the block");
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.after === "Planks", "placement pulse missing after real click");
      return { target: target, wood: count(game.inventory, B.wood) };
    });

    await step("keyboard-movement", function () {
      const before = game.player.x;
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "d", bubbles: true }));
      for (let index = 0; index < 8; index += 1) {
        commands.tick(0.05);
      }
      window.dispatchEvent(new KeyboardEvent("keyup", { key: "d", bubbles: true }));
      assert(game.player.x > before + 0.3, "keyboard input did not move the player (before " + before.toFixed(2) + ", after " + game.player.x.toFixed(2) + ")");
      return { before: before, after: game.player.x };
    });

    await step("backdrop-mode-toggle", async function () {
      const before = game.settings.backdropMode;
      element("btn-backdrop").click();
      await frames(1, api);
      assert(game.settings.backdropMode !== before, "backdrop mode did not toggle");
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.kind === "mode", "mode pulse missing, got " + pulse.kind);
      assert(pulse.before.indexOf("mode") >= 0 && pulse.after.indexOf("mode") >= 0, "mode labels missing");
      api.ui.showPulse(pulse, { pos: "mode" });
      assert(element("state-pulse").hidden === false, "mode before/after panel is not visible");
      assert(element("btn-backdrop").getAttribute("aria-pressed") === "true", "backdrop button not pressed");
      return { mode: game.settings.backdropMode };
    });

    await step("zoom-pulse-and-minimap-trail", async function () {
      const before = game.settings.zoom;
      element("game").dispatchEvent(new WheelEvent("wheel", { deltaY: -120, bubbles: true, cancelable: true }));
      commands.renderNow();
      assert(game.settings.zoom > before, "mouse wheel did not zoom the view");
      commands.setZoom(before + 0.3, "selftest");
      await frames(1, api);
      assert(Math.abs(game.settings.zoom - (before + 0.3)) < 0.001, "zoom did not change");
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.kind === "view", "view pulse missing");
      assert(game.minimapPrevious, "minimap viewport trail missing");
      assert(element("minimap-caption").textContent.indexOf("View") >= 0, "minimap caption not updated");
      return { zoom: game.settings.zoom, previous: game.minimapPrevious };
    });

    await step("time-wait-pulse-and-sky", async function () {
      commands.setTime(0.2);
      await frames(2, api);
      const before = window.SandboxTime.sky(game.clock.t).top;
      commands.wait();
      await frames(1, api);
      const pulse = game.backdrop.pulses[game.backdrop.pulses.length - 1];
      assert(pulse.kind === "time", "time pulse missing");
      const after = window.SandboxTime.sky(game.clock.t).top;
      assert(before !== after, "sky did not change after waiting");
      return { before: pulse.before, after: pulse.after };
    });

    await step("night-is-darker-than-noon", async function () {
      commands.setTime(0.22);
      await frames(3, api);
      const day = commands.brightness();
      commands.setTime(0.82);
      await frames(3, api);
      const night = commands.brightness();
      assert(night < day - 10, "night should be clearly darker (day " + day.toFixed(1) + ", night " + night.toFixed(1) + ")");
      return { day: Math.round(day), night: Math.round(night) };
    });

    await step("guide-documents-controls", function () {
      element("btn-guide").click();
      commands.renderNow();
      assert(element("panel-guide").hidden === false, "guide did not open");
      const rows = document.querySelectorAll("#control-list dt");
      assert(rows.length >= 12, "guide lists too few controls (" + rows.length + ")");
      const text = element("control-list").textContent;
      assert(text.indexOf("Mine") >= 0 && text.indexOf("Place") >= 0 && text.indexOf("Save") >= 0, "guide misses core controls");
      element("panel-guide").querySelector("[data-close]").click();
      return { controls: rows.length };
    });

    await step("quest-reward-and-completion", function () {
      commands.give(B.wood, 3);
      const completed = commands.syncTasks();
      commands.renderNow();
      const ids = completed.map(function (task) { return task.id; });
      assert(game.progress.tasks.first_wood === true, "first_wood quest did not complete");
      assert(count(game.inventory, B.torch) >= 2, "quest reward torches missing");
      return { completed: ids };
    });

    await step("performance-budget", function () {
      commands.setBlock(Math.floor(game.player.x) + 4, Math.floor(game.player.y) - 2, B.stone);
      commands.setBlock(Math.floor(game.player.x) + 4, Math.floor(game.player.y) - 3, B.dirt);
      const metrics = commands.metrics();
      assert(metrics.lastRelightMs < 60, "relighting is too slow: " + metrics.lastRelightMs.toFixed(1) + "ms");
      assert(metrics.lastFrameMs < 150, "frame work is too slow: " + metrics.lastFrameMs.toFixed(1) + "ms");
      return { relightMs: Math.round(metrics.lastRelightMs * 100) / 100, frameMs: Math.round(metrics.lastFrameMs * 100) / 100, tiles: metrics.tiles };
    });

    await step("save-writes-storage", function () {
      const result = commands.saveNow();
      assert(result.ok, "save failed");
      const raw = window.localStorage.getItem(CONFIG.saveKey);
      assert(raw && raw.length > 1000, "save payload missing");
      const envelope = window.SandboxSave.parse(raw);
      assert(envelope.seed === game.seed, "saved seed mismatch");
      return { bytes: raw.length, day: envelope.clock.day, storage: api.storageKind() };
    });

    await step("new-world-from-seed", function () {
      const previousSeed = game.seed;
      commands.newWorld(424242);
      commands.renderNow();
      assert(game.seed === 424242, "new world did not adopt the seed");
      assert(game.world.seed === 424242, "world generation did not use the seed");
      assert(game.progress.tasks.first_wood !== true, "new world kept old quest progress");
      assert(game.player.x > 0 && game.player.y > 0, "new world has no player position");
      return { previousSeed: previousSeed, seed: game.seed };
    });

    await step("audio-and-mute", function () {
      const before = game.settings.muted;
      commands.toggleMute();
      assert(game.settings.muted !== before, "mute did not toggle");
      commands.toggleMute();
      assert(game.settings.muted === before, "mute did not restore");
      const state = api.audio.state();
      assert(typeof state.muted === "boolean", "audio state missing");
      return state;
    });
  }

  whenReady(async function (api) {
    await frames(4, api);
    try {
      if (mode === "save-write") {
        await runSaveWrite(api);
      } else if (mode === "save-read") {
        await runSaveRead(api);
      } else {
        await runFull(api);
      }
      await delay(40);
    } catch (error) {
      report.errors.push(error && error.message ? error.message : String(error));
    }
    finish();
  });
})();

