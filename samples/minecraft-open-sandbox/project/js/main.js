(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const RNG = window.SandboxRng;
  const NOISE = window.SandboxNoise;
  const BLOCKS = window.SandboxBlocks;
  const WORLD = window.SandboxWorld;
  const LIGHTING = window.SandboxLighting;
  const TIME = window.SandboxTime;
  const INVENTORY = window.SandboxInventory;
  const PHYS = window.SandboxPhysics;
  const MINING = window.SandboxMining;
  const PLACEMENT = window.SandboxPlacement;
  const CRAFTING = window.SandboxCrafting;
  const TASKS = window.SandboxTasks;
  const BACKDROP = window.SandboxBackdrop;
  const SAVE = window.SandboxSave;
  const AUDIO = window.SandboxAudio;
  const RENDER = window.SandboxRender;
  const UI = window.SandboxUI;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const params = new URLSearchParams(window.location.search);
  const sceneMode = params.get("scene");
  const freezeScene = Boolean(sceneMode);
  const selftestMode = params.get("selftest");
  const ignoreSave = Boolean(sceneMode) || params.get("fresh") === "1" || selftestMode === "fresh";
  const requestedSeed = Number(params.get("seed")) >>> 0;

  let storage = SAVE.createStorage(window);
  let ui = null;
  let audio = null;
  let frameHandle = null;
  let autosaveTimer = null;
  let lastPhase = null;
  let last = 0;
  let forceSave = false;
  const bootAt = performance.now();

  const mouse = { x: 0, y: 0, inside: false };
  const input = { walkLeft: false, walkRight: false, jump: false, mining: false };
  let lastWeakToast = 0;

  const game = {
    seed: requestedSeed || CONFIG.seed,
    world: null,
    light: null,
    player: null,
    inventory: null,
    clock: null,
    progress: null,
    backlog: null,
    backdrop: null,
    mining: null,
    particles: [],
    camera: { x: 0, y: 0 },
    viewport: { width: window.innerWidth, height: window.innerHeight },
    screen: { width: window.innerWidth, height: window.innerHeight, dpr: 1 },
    settings: { muted: false, zoom: CONFIG.zoom.default, backdropMode: false, volume: 0.6 },
    hover: null,
    minimapPrevious: null,
    loadedFromSave: false,
    firstRun: false,
    ready: false,
    paused: false,
    metrics: { lastRelightMs: 0, relightCount: 0, frames: 0, lastFrameMs: 0 }
  };

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function tileSize() {
    return CONFIG.tileSize * game.settings.zoom;
  }

  function currentTile() {
    return tileSize();
  }

  function relight() {
    const started = performance.now();
    LIGHTING.relight(game.world, game.light);
    game.metrics.lastRelightMs = performance.now() - started;
    game.metrics.relightCount += 1;
  }

  function resize() {
    const previous = { width: game.viewport.width, height: game.viewport.height };
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(320, window.innerWidth);
    const height = Math.max(240, window.innerHeight);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    game.viewport = { width: width, height: height };
    game.screen = { width: width, height: height, dpr: dpr };
    game.minimapPrevious = {
      x: game.camera.x / currentTile(),
      y: game.camera.y / currentTile(),
      w: previous.width / currentTile(),
      h: previous.height / currentTile(),
      at: Date.now()
    };
    if (game.ready && game.metrics.frames > 20 && (previous.width !== width || previous.height !== height)) {
      const pulse = BACKDROP.pulse(game.backdrop, "view", previous.width + "x" + previous.height, width + "x" + height);
      ui.showPulse(pulse, { pos: "viewport" });
    }
  }

  function cameraTarget() {
    const tile = currentTile();
    const player = game.player;
    const maxX = Math.max(0, game.world.width * tile - game.viewport.width);
    const maxY = Math.max(0, game.world.height * tile - game.viewport.height);
    return {
      x: clamp(player.x * tile - game.viewport.width / 2, 0, maxX),
      y: clamp((player.y - player.height * 0.55) * tile - game.viewport.height / 2, 0, maxY)
    };
  }

  function snapCamera() {
    const target = cameraTarget();
    game.camera.x = target.x;
    game.camera.y = target.y;
  }

  function updateCamera(dt) {
    const target = cameraTarget();
    const ease = Math.min(1, dt * 9);
    game.camera.x += (target.x - game.camera.x) * ease;
    game.camera.y += (target.y - game.camera.y) * ease;
  }

  function applyWorldState() {
    const spawn = game.world.spawn || WORLD.findSpawn(game.world);
    const player = PHYS.createPlayer(spawn.x, spawn.y);
    PHYS.settle(player, game.world);
    game.player = player;
    game.inventory = INVENTORY.createInventory();
    game.clock = TIME.createClock();
    game.progress = TASKS.createProgress();
    game.backdrop = BACKDROP.createBackdrop();
    game.mining = MINING.createMining();
    game.particles = [];
    game.light = LIGHTING.createLight(game.world);
  }

  function newGame(seed) {
    game.seed = Number(seed) >>> 0 || CONFIG.seed;
    game.world = WORLD.generateWorld(game.seed);
    applyWorldState();
    game.loadedFromSave = false;
    game.firstRun = true;
    relight();
    snapCamera();
    lastPhase = TIME.phase(game.clock.t);
    if (ui) {
      ui.syncSeed(game.seed);
    }
  }

  function applyEnvelope(envelope) {
    game.seed = envelope.seed >>> 0;
    game.world = SAVE.loadWorld(envelope);
    game.light = LIGHTING.createLight(game.world);
    game.player = PHYS.createPlayer(envelope.player.x, envelope.player.y);
    game.player.health = Number.isFinite(envelope.player.health) ? envelope.player.health : 20;
    game.player.facing = envelope.player.facing === -1 ? -1 : 1;
    PHYS.settle(game.player, game.world);
    game.inventory = INVENTORY.deserialize(envelope.inventory);
    game.clock = TIME.createClock({ start: envelope.clock.t, day: envelope.clock.day });
    game.progress = TASKS.deserialize(envelope.progress);
    const settings = envelope.settings || {};
    game.settings = {
      muted: Boolean(settings.muted),
      zoom: Number.isFinite(settings.zoom) ? clamp(settings.zoom, CONFIG.zoom.min, CONFIG.zoom.max) : CONFIG.zoom.default,
      backdropMode: Boolean(settings.backdropMode),
      volume: Number.isFinite(settings.volume) ? settings.volume : 0.6
    };
    game.backdrop = BACKDROP.createBackdrop();
    if (envelope.backdrop && Array.isArray(envelope.backdrop.pulses)) {
      envelope.backdrop.pulses.slice(-6).forEach(function (entry) {
        BACKDROP.pulse(game.backdrop, entry.kind, entry.before, entry.after, entry.at);
      });
    }
    game.mining = MINING.createMining();
    game.particles = [];
    game.loadedFromSave = true;
    game.firstRun = false;
    relight();
    snapCamera();
    lastPhase = TIME.phase(game.clock.t);
    if (ui) {
      ui.syncSeed(game.seed);
    }
  }

  function restartWithSeed(seed) {
    newGame(seed);
    game.firstRun = false;
    saveNow(true);
    ui.closePanels();
    ui.setWelcome(false);
    ui.toast("New world ready — seed " + game.seed, "info");
    ui.syncSeed(game.seed);
  }

  function saveNotes() {
    if (storage.kind === "local") {
      return "Saves to this browser automatically (local storage).";
    }
    return "Browser storage is unavailable — progress is kept in memory. Export a save file from the menu.";
  }

  function saveNow(silent) {
    const envelope = SAVE.createEnvelope(game);
    const result = SAVE.saveGame(storage, envelope);
    ui.setStorageNote(saveNotes());
    ui.setMenuStatus(storage.kind === "local" ? "Saved to this browser (" + result.bytes + " bytes)" : "Memory only — export a save file to keep progress");
    forceSave = false;
    if (!silent) {
      ui.toast(result.ok && storage.kind === "local" ? "World saved" : "Saved in memory only — export a save file", result.ok ? "info" : "bad");
      audio.play("save");
    }
    return result;
  }

  function exportSave() {
    const envelope = SAVE.createEnvelope(game);
    const text = SAVE.serialize(envelope);
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "cubewood-day" + game.clock.day + ".json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    ui.toast("Save file exported", "info");
  }

  function importSave(file) {
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = function () {
      try {
        const envelope = SAVE.parse(String(reader.result));
        applyEnvelope(envelope);
        game.firstRun = false;
        saveNow(true);
        ui.closePanels();
        ui.setWelcome(false);
        ui.setStorageNote(saveNotes());
        ui.toast("Save imported — day " + game.clock.day, "info");
        audio.play("save");
      } catch (error) {
        ui.toast("Could not import that save: " + error.message, "bad");
        audio.play("error");
      }
    };
    reader.readAsText(file);
  }

  function syncTasks() {
    const completed = TASKS.sync(game.progress);
    completed.forEach(function (task) {
      if (task.reward) {
        INVENTORY.add(game.inventory, task.reward.id, task.reward.count);
        TASKS.noteCollected(game.progress, task.reward.id, task.reward.count);
      }
      ui.toast("Quest complete — " + task.title, "quest");
      audio.play("quest");
    });
    return completed;
  }

  function spawnParticles(x, y, blockId, count) {
    const base = BLOCKS.colorOf(blockId);
    const rng = RNG.createRng(RNG.hashInts(x, y, game.metrics.frames));
    for (let index = 0; index < count; index += 1) {
      game.particles.push({
        x: x + 0.5 + (rng() - 0.5) * 0.7,
        y: y + 0.5 + (rng() - 0.5) * 0.7,
        vx: (rng() - 0.5) * 2.4,
        vy: -1 - rng() * 2.2,
        life: 0.5 + rng() * 0.4,
        maxLife: 0.9,
        color: index % 3 === 0 ? RENDER.shade(base, 30) : base,
        size: 3 + rng() * 3
      });
    }
    if (game.particles.length > 90) {
      game.particles.splice(0, game.particles.length - 90);
    }
  }

  function reasonText(reason) {
    switch (reason) {
      case "out-of-reach": return "Too far away";
      case "occupied": return "That tile is already solid";
      case "no-support": return "Needs a neighbour block";
      case "blocked-by-player": return "You are standing there";
      case "empty-hand": return "Choose a block in the hotbar first";
      case "out-of-bounds": return "Outside the world";
      default: return "Cannot place that here";
    }
  }

  function recordEdit(x, y, before, after, kind) {
    return BACKDROP.recordEdit(game.backdrop, { x: x, y: y, before: before, after: after, kind: kind });
  }

  function breakAt(x, y, silent) {
    const before = WORLD.getBlock(game.world, x, y);
    if (!before) {
      return { ok: false };
    }
    const result = MINING.breakBlock(game.world, game.inventory, x, y);
    if (!result.ok) {
      return result;
    }
    TASKS.noteMined(game.progress, result.blockId);
    if (result.drop) {
      TASKS.noteCollected(game.progress, result.drop, 1);
    }
    recordEdit(x, y, before, CONFIG.blocks.air, "edit");
    relight();
    spawnParticles(x, y, before, result.canHarvest ? 6 : 3);
    if (!silent) {
      if (!result.canHarvest && Date.now() - lastWeakToast > 4000) {
        lastWeakToast = Date.now();
        ui.toast("That block needs a stronger pickaxe to collect", "bad");
      }
      audio.play("break");
    }
    syncTasks();
    updateHover();
    return result;
  }

  function placeAt(x, y, silent) {
    const before = WORLD.getBlock(game.world, x, y);
    const result = PLACEMENT.place(game.world, game.player, game.inventory, x, y);
    if (!result.ok) {
      if (!silent) {
        ui.toast(reasonText(result.reason), "bad");
        audio.play("error");
      }
      return result;
    }
    TASKS.notePlaced(game.progress, result.block);
    recordEdit(x, y, before, result.block, "edit");
    relight();
    audio.play("place");
    syncTasks();
    updateHover();
    return result;
  }

  function undo() {
    const entry = BACKDROP.undo(game.backdrop);
    if (!entry) {
      ui.toast("Nothing to undo", "bad");
      return false;
    }
    WORLD.setBlock(game.world, entry.x, entry.y, entry.before);
    relight();
    ui.toast("Undid: " + entry.afterName + " → " + entry.beforeName, "info");
    audio.play("place");
    return true;
  }

  function redo() {
    const entry = BACKDROP.redo(game.backdrop);
    if (!entry) {
      ui.toast("Nothing to redo", "bad");
      return false;
    }
    WORLD.setBlock(game.world, entry.x, entry.y, entry.after);
    relight();
    ui.toast("Redid: " + entry.beforeName + " → " + entry.afterName, "info");
    audio.play("place");
    return true;
  }

  function toggleBackdrop() {
    const before = game.settings.backdropMode ? "Backdrop" : "Build";
    game.settings.backdropMode = !game.settings.backdropMode;
    const after = game.settings.backdropMode ? "Backdrop" : "Build";
    const pulse = BACKDROP.pulse(game.backdrop, "mode", before + " mode", after + " mode");
    ui.showPulse(pulse, { pos: "mode" });
    ui.toast(game.settings.backdropMode ? "Backdrop on — recent edits show their before state" : "Backdrop off — build mode", "info");
    audio.play("place");
  }

  function setZoom(next, reason) {
    const clamped = clamp(Number(next) || CONFIG.zoom.default, CONFIG.zoom.min, CONFIG.zoom.max);
    if (Math.abs(clamped - game.settings.zoom) < 0.001) {
      return;
    }
    const before = game.settings.zoom;
    game.minimapPrevious = {
      x: game.camera.x / currentTile(),
      y: game.camera.y / currentTile(),
      w: game.viewport.width / currentTile(),
      h: game.viewport.height / currentTile(),
      at: Date.now()
    };
    game.settings.zoom = clamped;
    const pulse = BACKDROP.pulse(game.backdrop, "view", before.toFixed(1) + "x", clamped.toFixed(1) + "x");
    ui.showPulse(pulse, { pos: reason || "zoom" });
    ui.setMinimapCaption("View " + clamped.toFixed(1) + "x · viewport " + game.viewport.width + "x" + game.viewport.height);
  }

  function waitHours() {
    const beforeLabel = TIME.formatClock(game.clock.t);
    game.clock.t = (game.clock.t + 3 / 24) % 1;
    const phase = TIME.phase(game.clock.t);
    const pulse = BACKDROP.pulse(game.backdrop, "time", beforeLabel, TIME.formatClock(game.clock.t));
    ui.showPulse(pulse, { pos: phase });
    ui.toast("You wait three hours — " + phase + " now", "info");
    lastPhase = phase;
  }

  function craftRecipe(recipeId) {
    const recipe = CRAFTING.recipeById(recipeId);
    if (!recipe) {
      return { ok: false, reason: "unknown" };
    }
    const result = CRAFTING.craft(game.inventory, recipe, game.progress);
    if (!result.ok) {
      const message = result.reason === "locked" ? "Gather the material first to unlock that recipe" : "Not enough ingredients";
      ui.toast(message, "bad");
      audio.play("error");
      return result;
    }
    TASKS.noteCrafted(game.progress, recipe.id);
    TASKS.noteCollected(game.progress, recipe.out.id, recipe.out.count);
    audio.play("craft");
    ui.toast("Crafted " + BLOCKS.nameOf(recipe.out.id) + " ×" + recipe.out.count, "info");
    syncTasks();
    return result;
  }

  function pickItem(itemId) {
    INVENTORY.ensureHotbar(game.inventory, itemId);
    const slot = game.inventory.hotbar.indexOf(itemId);
    if (slot >= 0) {
      INVENTORY.select(game.inventory, slot);
    }
    ui.closePanels();
    ui.toast(BLOCKS.nameOf(itemId) + " selected", "info");
  }

  function updateHover() {
    if (!mouse.inside || !game.ready) {
      game.hover = null;
      return;
    }
    const tile = currentTile();
    const worldX = (mouse.x + game.camera.x) / tile;
    const worldY = (mouse.y + game.camera.y) / tile;
    const x = Math.floor(worldX);
    const y = Math.floor(worldY);
    const blockId = WORLD.getBlock(game.world, x, y);
    if (blockId === null) {
      game.hover = null;
      return;
    }
    const inReach = MINING.reachable(game.player, x, y);
    const selected = INVENTORY.selectedId(game.inventory);
    const canPlace = BLOCKS.isBlockItem(selected) && INVENTORY.has(game.inventory, selected, 1);
    const placeCheck = canPlace ? PLACEMENT.evaluate(game.world, game.player, game.inventory, x, y) : { ok: false, reason: "empty-hand" };
    const mineInfo = MINING.targetInfo(game.world, game.inventory, x, y);
    const mode = placeCheck.ok ? "place" : "mine";
    game.hover = {
      x: x,
      y: y,
      visible: inReach,
      inReach: inReach,
      mode: mode,
      valid: inReach && (mode === "place" ? placeCheck.ok : mineInfo.ok),
      canMine: mineInfo.ok && inReach,
      block: canPlace ? selected : 0,
      blockId: blockId,
      mineInfo: mineInfo,
      placeCheck: placeCheck
    };
    let hint = "";
    let tone = "info";
    if (!inReach) {
      hint = "Too far away";
      tone = "bad";
    } else if (mode === "place") {
      hint = "Place " + BLOCKS.nameOf(selected) + " (right click)";
    } else if (!mineInfo.ok && mineInfo.reason === "unbreakable") {
      hint = "Bedrock cannot be broken";
      tone = "bad";
    } else if (!mineInfo.ok && mineInfo.reason === "empty") {
      hint = "Select a block to place";
    } else if (mineInfo.ok) {
      hint = "Mine " + mineInfo.definition.name + (mineInfo.canHarvest ? " (hold left click)" : " — needs a pickaxe");
      if (!mineInfo.canHarvest) {
        tone = "bad";
      }
    }
    ui.setHint(hint, tone, mouse.x, mouse.y);
  }

  function updateMining(dt) {
    if (!input.mining || game.paused || !game.hover || !game.hover.inReach || !game.hover.canMine) {
      if (game.mining.progress > 0) {
        MINING.reset(game.mining);
      }
      return;
    }
    const hover = game.hover;
    const result = MINING.advance(game.mining, game.world, game.inventory, hover.x, hover.y, dt);
    if (result.blocked) {
      return;
    }
    if (Math.random() < dt * 14) {
      spawnParticles(hover.x, hover.y, hover.blockId, 1);
      audio.play("mine");
    }
    if (result.done) {
      breakAt(hover.x, hover.y, false);
    }
  }

  function updateTime(dt) {
    const result = TIME.advance(game.clock, dt);
    game.progress.playSeconds += dt;
    if (result.dayAdvanced) {
      game.progress.day = game.clock.day;
      ui.toast("Day " + game.clock.day + " begins", "info");
      syncTasks();
    }
    const phase = TIME.phase(game.clock.t);
    if (phase !== lastPhase) {
      const pulse = BACKDROP.pulse(game.backdrop, "time", capitalize(lastPhase), capitalize(phase));
      ui.showPulse(pulse, { pos: TIME.formatClock(game.clock.t) });
      lastPhase = phase;
    }
  }

  function capitalize(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
  }

  function updatePlayer(dt) {
    if (game.paused) {
      game.player.vx = 0;
      return;
    }
    const wasOnGround = game.player.onGround;
    PHYS.stepPlayer(game.player, game.world, { left: input.walkLeft, right: input.walkRight, jump: input.jump }, dt);
    if (game.player.justJumped) {
      audio.play("jump");
    }
    if (game.player.lastImpact > 0 && !wasOnGround) {
      const damage = PHYS.fallDamage(game.player.lastImpact);
      if (damage > 0) {
        game.player.health = Math.max(0, game.player.health - damage);
        ui.toast("Ouch — " + damage + " fall damage", "bad");
        audio.play("hurt");
        if (game.player.health <= 0) {
          const spawn = game.world.spawn || WORLD.findSpawn(game.world);
          game.player.x = spawn.x;
          game.player.y = spawn.y;
          game.player.vx = 0;
          game.player.vy = 0;
          game.player.health = 20;
          PHYS.settle(game.player, game.world);
          ui.toast("You blacked out and woke up at spawn", "bad");
        }
      }
    }
    if (game.player.y < game.world.height) {
      TASKS.noteDepth(game.progress, Math.floor(game.player.y));
    }
  }

  function updateParticles(dt) {
    for (let index = game.particles.length - 1; index >= 0; index -= 1) {
      const particle = game.particles[index];
      particle.life -= dt;
      if (particle.life <= 0) {
        game.particles.splice(index, 1);
        continue;
      }
      particle.vy += 14 * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
    }
  }

  function minimapView() {
    return {
      world: game.world,
      light: game.light,
      player: game.player,
      camera: game.camera,
      tile: currentTile(),
      width: game.viewport.width,
      height: game.viewport.height,
      clock: game.clock,
      sky: TIME.sky(game.clock.t),
      minimapPrevious: game.minimapPrevious
    };
  }

  function render() {
    const tile = currentTile();
    const sky = TIME.sky(game.clock.t);
    RENDER.render(ctx, {
      width: game.viewport.width,
      height: game.viewport.height,
      world: game.world,
      light: game.light,
      camera: game.camera,
      tile: tile,
      clock: game.clock,
      sky: sky,
      daylight: sky.daylight,
      player: game.player,
      hover: game.hover,
      mining: game.mining,
      mode: game.settings.backdropMode ? "backdrop" : "build",
      edits: game.backdrop.edits,
      particles: game.particles,
      minimapPrevious: game.minimapPrevious
    });
  }

  function updateUI() {
    const sky = TIME.sky(game.clock.t);
    ui.update({
      inventory: game.inventory,
      progress: game.progress,
      tasks: TASKS,
      crafting: CRAFTING,
      clock: game.clock,
      clockText: TIME.formatClock(game.clock.t),
      phase: TIME.phase(game.clock.t),
      player: game.player,
      settings: game.settings,
      zoom: game.settings.zoom,
      viewport: game.viewport,
      minimapView: minimapView()
    });
    if (sky.daylight < 0.4) {
      ui.setMinimapCaption("View " + game.settings.zoom.toFixed(1) + "x · night");
    } else {
      ui.setMinimapCaption("View " + game.settings.zoom.toFixed(1) + "x · viewport " + game.viewport.width + "x" + game.viewport.height);
    }
  }

  function frame(now) {
    const dt = Math.min(0.05, Math.max(0, (now - last) / 1000 || 0.016));
    last = now;
    game.metrics.frames += 1;
    const started = performance.now();

    if (!freezeScene) {
      updatePlayer(dt);
      updateTime(dt);
      updateCamera(dt);
    }
    updateMining(dt);
    updateParticles(dt);
    render();
    if (game.metrics.frames % 4 === 0) {
      updateUI();
    }
    updateHover();
    game.metrics.lastFrameMs = performance.now() - started;
    frameHandle = window.requestAnimationFrame(frame);
  }

  function paused() {
    return ui.panel() !== null || !document.getElementById("welcome").hidden;
  }

  function setPaused() {
    game.paused = paused();
  }

  function openPanel(name) {
    const mapping = {
      inventory: "panel-inventory",
      craft: "panel-craft",
      guide: "panel-guide",
      menu: "panel-menu"
    };
    const target = mapping[name];
    if (!target) {
      return;
    }
    ui.closePanels(true);
    ui.setWelcome(false);
    ui.openPanel(target);
    game.paused = true;
    if (name === "menu") {
      ui.setMenuStatus(storage.kind === "local" ? "Storage: browser local storage" : "Storage: memory only — export to keep progress");
      ui.syncSeed(game.seed);
    }
  }

  function closePanels() {
    ui.closePanels();
    game.paused = paused();
  }

  function handleKey(event) {
    const key = event.key;
    const code = event.code;
    const blocked = paused();
    const isControl = event.ctrlKey || event.metaKey;

    if (key === "Escape") {
      event.preventDefault();
      if (ui.panel()) {
        closePanels();
      } else if (!document.getElementById("welcome").hidden) {
        ui.setWelcome(false);
        game.paused = false;
      } else {
        openPanel("menu");
      }
      return;
    }

    if (isControl && (key === "z" || key === "Z")) {
      event.preventDefault();
      if (!blocked) {
        undo();
      }
      return;
    }
    if (isControl && (key === "y" || key === "Y")) {
      event.preventDefault();
      if (!blocked) {
        redo();
      }
      return;
    }

    if (blocked) {
      return;
    }

    if (key === "a" || key === "A" || key === "ArrowLeft") {
      input.walkLeft = true;
      event.preventDefault();
    } else if (key === "d" || key === "D" || key === "ArrowRight") {
      input.walkRight = true;
      event.preventDefault();
    } else if (key === "w" || key === "W" || key === " " || code === "Space" || key === "ArrowUp") {
      input.jump = true;
      event.preventDefault();
    } else if (key === "e" || key === "E") {
      openPanel("inventory");
    } else if (key === "c" || key === "C") {
      openPanel("craft");
    } else if (key === "h" || key === "H") {
      openPanel("guide");
    } else if (key === "q" || key === "Q") {
      ui.setQuestHidden(!ui.questHidden());
    } else if (key === "b" || key === "B") {
      toggleBackdrop();
    } else if (key === "m" || key === "M") {
      toggleMute();
    } else if (key === "t" || key === "T") {
      waitHours();
    } else if (key === "F2") {
      event.preventDefault();
      saveNow(false);
    } else if (key === "+" || key === "=") {
      setZoom(game.settings.zoom + CONFIG.zoom.step, "keyboard");
    } else if (key === "-" || key === "_") {
      setZoom(game.settings.zoom - CONFIG.zoom.step, "keyboard");
    } else if (/^[1-9]$/.test(key)) {
      INVENTORY.select(game.inventory, Number(key) - 1);
    }
  }

  function handleKeyUp(event) {
    const key = event.key;
    if (key === "a" || key === "A" || key === "ArrowLeft") {
      input.walkLeft = false;
    } else if (key === "d" || key === "D" || key === "ArrowRight") {
      input.walkRight = false;
    } else if (key === "w" || key === "W" || key === " " || key === "ArrowUp") {
      input.jump = false;
    }
  }

  function toggleMute() {
    game.settings.muted = audio.toggle();
    ui.setMuteButton(game.settings.muted);
    ui.toast(game.settings.muted ? "Sound muted" : "Sound on", "info");
  }

  function pointerPosition(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (game.viewport.width / rect.width),
      y: (event.clientY - rect.top) * (game.viewport.height / rect.height)
    };
  }

  function bindEvents() {
    window.addEventListener("resize", function () {
      resize();
      updateUI();
    });
    window.addEventListener("keydown", handleKey);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", function () {
      input.walkLeft = false;
      input.walkRight = false;
      input.jump = false;
      input.mining = false;
    });
    canvas.addEventListener("pointermove", function (event) {
      const point = pointerPosition(event);
      mouse.x = point.x;
      mouse.y = point.y;
      mouse.inside = true;
      updateHover();
    });
    canvas.addEventListener("pointerleave", function () {
      mouse.inside = false;
      game.hover = null;
      ui.setHint(null);
    });
    canvas.addEventListener("pointerdown", function (event) {
      if (paused()) {
        return;
      }
      const point = pointerPosition(event);
      mouse.x = point.x;
      mouse.y = point.y;
      mouse.inside = true;
      updateHover();
      if (event.button === 0) {
        input.mining = true;
        audio.play("mine");
      } else if (event.button === 2) {
        if (game.hover) {
          placeAt(game.hover.x, game.hover.y, false);
        }
      }
      event.preventDefault();
    });
    canvas.addEventListener("pointerup", function (event) {
      if (event.button === 0) {
        input.mining = false;
        MINING.reset(game.mining);
      }
    });
    canvas.addEventListener("pointercancel", function () {
      input.mining = false;
    });
    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });
    canvas.addEventListener("wheel", function (event) {
      if (paused()) {
        return;
      }
      event.preventDefault();
      const direction = event.deltaY > 0 ? -1 : 1;
      setZoom(game.settings.zoom + direction * CONFIG.zoom.step, "wheel");
    }, { passive: false });
    window.addEventListener("beforeunload", function () {
      if (game.ready) {
        const envelope = SAVE.createEnvelope(game);
        SAVE.saveGame(storage, envelope);
      }
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden && game.ready) {
        const envelope = SAVE.createEnvelope(game);
        SAVE.saveGame(storage, envelope);
      }
    });
  }

  function actions() {
    return {
      selectSlot: function (index) {
        INVENTORY.select(game.inventory, index);
        updateHover();
      },
      pickItem: pickItem,
      craft: craftRecipe,
      openPanel: openPanel,
      closePanels: closePanels,
      toggleQuests: function () {
        ui.setQuestHidden(!ui.questHidden());
      },
      play: function () {
        ui.setWelcome(false);
        game.paused = false;
        ui.focusGame();
        ui.toast("Hold left click on a tree to gather wood", "info");
      },
      newWorldPrompt: function () {
        openPanel("menu");
        ui.syncSeed(game.seed);
      },
      save: function () {
        saveNow(false);
      },
      toggleBackdrop: toggleBackdrop,
      toggleMute: toggleMute,
      newWorld: function (seedText) {
        const parsed = parseInt(String(seedText || "").trim(), 10);
        const seed = Number.isFinite(parsed) ? parsed >>> 0 : (Date.now() >>> 0);
        restartWithSeed(seed);
      },
      exportSave: exportSave,
      importSave: importSave
    };
  }

  function exposeApi() {
    window.__cubewood = {
      config: CONFIG,
      game: game,
      ui: ui,
      audio: audio,
      storageKind: function () { return storage.kind; },
      ready: false,
      commands: {
        mineAt: function (x, y) { return breakAt(x, y, true); },
        placeAt: function (x, y) { return placeAt(x, y, true); },
        selectSlot: function (index) { INVENTORY.select(game.inventory, index); },
        give: function (id, count) {
          INVENTORY.add(game.inventory, id, count || 1);
          TASKS.noteCollected(game.progress, id, count || 1);
        },
        setBlock: function (x, y, id) {
          const before = WORLD.getBlock(game.world, x, y);
          WORLD.setBlock(game.world, x, y, id);
          recordEdit(x, y, before, id, "edit");
          relight();
        },
        bulkSet: function (entries) {
          entries.forEach(function (entry) {
            const before = WORLD.getBlock(game.world, entry.x, entry.y);
            WORLD.setBlock(game.world, entry.x, entry.y, entry.id);
            if (entry.record !== false) {
              recordEdit(entry.x, entry.y, before, entry.id, "edit");
            }
          });
          relight();
        },
        tick: function (dt) {
          const step = Math.min(Math.max(dt || 0.016, 0), 0.1);
          updatePlayer(step);
          updateTime(step);
          updateMining(step);
          updateParticles(step);
          updateCamera(1);
          render();
          updateUI();
          updateHover();
          return { block: game.hover ? game.hover.x + "," + game.hover.y : null, mining: game.mining.progress };
        },
        renderNow: function () {
          updateCamera(1);
          render();
          updateUI();
          updateHover();
          return true;
        },
        saveNow: function () { return saveNow(true); },
        saveVisible: function () { return saveNow(false); },
        newWorld: restartWithSeed,
        setTime: function (t) { game.clock.t = ((t % 1) + 1) % 1; lastPhase = TIME.phase(game.clock.t); },
        setDay: function (day) { game.clock.day = day; game.progress.day = day; },
        wait: waitHours,
        toggleBackdrop: toggleBackdrop,
        setZoom: setZoom,
        undo: undo,
        redo: redo,
        teleport: function (x, y) {
          game.player.x = x;
          game.player.y = y;
          game.player.vx = 0;
          game.player.vy = 0;
          PHYS.settle(game.player, game.world);
          snapCamera();
        },
        craft: craftRecipe,
        syncTasks: syncTasks,
        toggleMute: toggleMute,
        openPanel: openPanel,
        closePanels: closePanels,
        hideWelcome: function () { ui.setWelcome(false); game.paused = false; },
        showWelcome: function () { ui.setWelcome(true); game.paused = true; },
        findNearby: function (blockId, radius) {
          const range = radius || 12;
          const px = Math.floor(game.player.x);
          const py = Math.floor(game.player.y);
          let best = null;
          let bestDistance = Infinity;
          for (let y = Math.max(0, py - range); y < Math.min(game.world.height, py + range); y += 1) {
            for (let x = Math.max(0, px - range); x < Math.min(game.world.width, px + range); x += 1) {
              if (game.world.data[y * game.world.width + x] === blockId) {
                const distance = Math.abs(x - px) + Math.abs(y - py);
                if (distance < bestDistance) {
                  bestDistance = distance;
                  best = { x: x, y: y };
                }
              }
            }
          }
          return best;
        },
        scanCanvas: function () {
          const sample = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          const seen = new Set();
          const step = Math.max(4, Math.floor(sample.length / 4 / 4000)) * 4;
          for (let index = 0; index < sample.length; index += step) {
            seen.add((sample[index] >> 4) + ":" + (sample[index + 1] >> 4) + ":" + (sample[index + 2] >> 4));
          }
          return seen.size;
        },
        brightness: function () {
          const sample = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          let sum = 0;
          let count = 0;
          const step = Math.max(4, Math.floor(sample.length / 4 / 5000)) * 4;
          for (let index = 0; index < sample.length; index += step) {
            sum += sample[index] * 0.299 + sample[index + 1] * 0.587 + sample[index + 2] * 0.114;
            count += 1;
          }
          return count ? sum / count : 0;
        },
        metrics: function () {
          return {
            lastRelightMs: game.metrics.lastRelightMs,
            relightCount: game.metrics.relightCount,
            frames: game.metrics.frames,
            lastFrameMs: game.metrics.lastFrameMs,
            tiles: game.world.width * game.world.height
          };
        }
      }
    };
    window.__sandbox = { world: game.world, player: game.player, camera: game.camera, ready: false };
  }

  function boot() {
    resize();
    audio = AUDIO.createAudio();
    audio.setMuted(false);
    game.light = null;

    const envelope = ignoreSave ? null : SAVE.loadGame(storage);
    if (envelope && !envelope.error) {
      try {
        applyEnvelope(envelope);
      } catch (error) {
        newGame(requestedSeed || CONFIG.seed);
      }
    } else {
      newGame(requestedSeed || CONFIG.seed);
    }
    if (envelope && envelope.error) {
      ui = null;
    }

    ui = UI.createUI({ actions: actions() });
    ui.setMuteButton(game.settings.muted);
    ui.setStorageNote(saveNotes());
    ui.setQuestHidden(false);
    ui.setQuestHidden(window.innerWidth < 900);

    if (game.loadedFromSave) {
      ui.setWelcome(false);
      ui.toast("Welcome back — day " + game.clock.day, "info");
    } else if (!sceneMode && !selftestMode) {
      ui.setWelcome(true);
    } else if (selftestMode || sceneMode) {
      ui.setWelcome(!game.loadedFromSave);
    }

    exposeApi();
    bindEvents();
    render();
    updateUI();
    ui.setStatus("ready", "ready");
    game.ready = true;
    window.__cubewood.ready = true;
    window.__sandbox.ready = true;
    game.paused = paused();

    last = performance.now();
    frameHandle = window.requestAnimationFrame(frame);

    autosaveTimer = window.setInterval(function () {
      if (game.ready && !game.paused) {
        const envelopeNow = SAVE.createEnvelope(game);
        SAVE.saveGame(storage, envelopeNow);
        forceSave = false;
      }
    }, CONFIG.autosaveSeconds * 1000);

    window.addEventListener("error", function (event) {
      ui.setStatus("error", event.message || "runtime error");
    });
    window.addEventListener("unhandledrejection", function (event) {
      ui.setStatus("error", String(event.reason));
    });
  }

  boot();
})();
