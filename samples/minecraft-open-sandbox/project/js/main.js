(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const LIGHT = window.SandboxLight;
  const BLOCKS = window.SandboxBlocks;
  const PLAYER = window.SandboxPlayer;
  const INVENTORY = window.SandboxInventory;
  const CRAFTING = window.SandboxCrafting;
  const PROGRESSION = window.SandboxProgression;
  const MOBS = window.SandboxMobs;
  const SAVE = window.SandboxSave;
  const AUDIO = window.SandboxAudio;
  const RENDER = window.SandboxRender;
  const UI = window.SandboxUI;
  const INPUT = window.SandboxInput;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const B = CONFIG.blocks;

  const STEP = 1 / 60;
  const GROUND = Math.floor(CONFIG.worldHeight * 0.65);

  const game = {
    world: null,
    player: null,
    inventory: null,
    progress: null,
    clock: { day: 1, time: CONFIG.startTime },
    mobs: null,
    particles: [],
    camera: { x: 0, y: 0 },
    light: null,
    worldVersion: 0,
    mode: "booting",
    mining: null,
    lastSaveAt: 0,
    saveSummary: null,
    saveError: "",
    loadedFromSave: false,
    beacon: null,
    victoryShown: false,
    hurtFlash: 0,
    autosaveTimer: 0,
    lightKey: "",
    lastHintAt: 0,
    firstRun: true,
    muted: false,
    deathPending: false,
    dug: new Set()
  };

  let ui = null;
  let input = null;
  let lastFrame = 0;
  let lastHudAt = 0;
  let stationCache = { at: 0, points: [] };
  let lastNightState = false;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function setStatus(stateName, title) {
    statusEl.dataset.state = stateName;
    statusEl.title = title || stateName;
  }

  function toast(text, kind) {
    if (ui) {
      ui.toast(text, kind);
    }
  }

  function hint(text, duration) {
    if (ui) {
      ui.showHint(text, duration);
    }
  }

  function spawnAt() {
    return { x: CONFIG.spawnX + 0.5, y: GROUND };
  }

  function resetWorld(seed) {
    game.world = WORLD.createWorld(seed);
    const spawn = spawnAt();
    game.player = PLAYER.createPlayer(spawn.x, spawn.y);
    game.inventory = INVENTORY.createInventory();
    game.progress = PROGRESSION.createProgress();
    game.clock = { day: 1, time: CONFIG.startTime };
    game.mobs = MOBS.createMobs();
    game.particles = [];
    game.mining = null;
    game.beacon = null;
    game.dug = new Set();
    game.victoryShown = false;
    game.hurtFlash = 0;
    game.autosaveTimer = 0;
    game.light = null;
    game.lightKey = "";
    game.lastSaveAt = 0;
    game.saveSummary = null;
    game.saveError = "";
    game.loadedFromSave = false;
    game.firstRun = true;
    game.worldVersion += 1;
    game.camera.x = clamp(
      game.player.x * CONFIG.tileSize - CONFIG.viewWidth / 2,
      0,
      Math.max(0, game.world.width * CONFIG.tileSize - CONFIG.viewWidth)
    );
    game.camera.y = clamp(
      game.player.y * CONFIG.tileSize - CONFIG.viewHeight / 2,
      0,
      Math.max(0, game.world.height * CONFIG.tileSize - CONFIG.viewHeight)
    );
    updateLight(true);
  }

  function loadFromSave(savedState, savedData) {
    game.world = savedState.world;
    game.player = PLAYER.createPlayer(savedState.player.x, savedState.player.y);
    PLAYER.applySaved(game.player, savedState.player);
    game.inventory = savedState.inventory;
    game.progress = savedState.progress;
    game.clock = savedState.clock;
    game.mobs = MOBS.createMobs();
    game.particles = [];
    game.mining = null;
    game.dug = deriveDug(game.world);
    game.hurtFlash = 0;
    game.autosaveTimer = 0;
    game.light = null;
    game.lightKey = "";
    game.lastSaveAt = savedState.savedAt || 0;
    game.saveSummary = SAVE.summarize(savedData);
    game.saveError = "";
    game.loadedFromSave = true;
    game.firstRun = false;
    game.victoryShown = game.progress.stage >= PROGRESSION.STAGES.length;
    game.beacon = findBeacon(game.world);
    game.worldVersion += 1;
    game.camera.x = clamp(
      game.player.x * CONFIG.tileSize - CONFIG.viewWidth / 2,
      0,
      Math.max(0, game.world.width * CONFIG.tileSize - CONFIG.viewWidth)
    );
    game.camera.y = clamp(
      game.player.y * CONFIG.tileSize - CONFIG.viewHeight / 2,
      0,
      Math.max(0, game.world.height * CONFIG.tileSize - CONFIG.viewHeight)
    );
    updateLight(true);
  }

  function findBeacon(world) {
    for (let y = 0; y < world.height; y += 1) {
      for (let x = 0; x < world.width; x += 1) {
        if (world.data[y * world.width + x] === B.beacon) {
          return { x: x, y: y };
        }
      }
    }
    return null;
  }

  // A loaded world has no record of which air tiles were dug, but the pristine
  // deterministic generation is the baseline: any tile that is air now and was
  // solid then is a hole the player made.
  function deriveDug(world) {
    const dug = new Set();
    try {
      const baseline = WORLD.createWorld(world.seed);
      if (baseline.width !== world.width || baseline.height !== world.height) {
        return dug;
      }
      for (let y = 0; y < world.height; y += 1) {
        for (let x = 0; x < world.width; x += 1) {
          const index = y * world.width + x;
          if (world.data[index] === B.air && baseline.data[index] !== B.air) {
            dug.add(x + "," + y);
          }
        }
      }
    } catch (error) {
      // Visual-only detail: never block loading because of it.
    }
    return dug;
  }

  function setMode(mode) {
    game.mode = mode;
    if (mode !== "playing") {
      game.mining = null;
      if (input) {
        input.releaseAll();
      }
    }
  }

  function snapshot() {
    const stations = CRAFTING.stationsNear(game.world, game.player, 4);
    const stationNames = Array.from(stations).sort();
    const status = game.saveError
      ? { kind: "error", text: "Save failed: " + game.saveError }
      : game.lastSaveAt
        ? { kind: "ok", text: "Saved · " + SAVE.formatAgo(game.lastSaveAt) }
        : { kind: "dirty", text: "Not saved yet" };
    return {
      world: game.world,
      player: game.player,
      inventory: game.inventory,
      progress: game.progress,
      clock: game.clock,
      mobs: game.mobs,
      mode: game.mode,
      stations: stations,
      stationNames: stationNames,
      stationPoints: stationPoints(),
      saveStatus: status,
      saveSummary: game.saveSummary,
      muted: game.muted
    };
  }

  function stationPoints() {
    const now = Date.now();
    if (now - stationCache.at < 900) {
      return stationCache.points;
    }
    stationCache.at = now;
    const points = [];
    const world = game.world;
    const radius = 70;
    const left = Math.max(0, Math.floor(game.player.x) - radius);
    const right = Math.min(world.width - 1, Math.floor(game.player.x) + radius);
    const top = Math.max(0, Math.floor(game.player.y) - radius);
    const bottom = Math.min(world.height - 1, Math.floor(game.player.y) + radius);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        const station = BLOCKS.stationOf(world.data[y * world.width + x]);
        if (station) {
          points.push({ x: x, y: y, kind: station });
        }
        if (world.data[y * world.width + x] === B.beacon) {
          points.push({ x: x, y: y, kind: "beacon" });
        }
      }
    }
    stationCache.points = points;
    return points;
  }

  function hudRefresh(force) {
    if (!ui) {
      return;
    }
    const now = Date.now();
    if (!force && now - lastHudAt < 120) {
      return;
    }
    lastHudAt = now;
    ui.updateHud(snapshot());
  }

  function updateProgress() {
    const result = PROGRESSION.update(game.progress);
    for (let i = 0; i < result.newlyCompleted.length; i += 1) {
      const stage = result.newlyCompleted[i];
      toast("Journey: " + stage.title, "quest");
      hint(stage.hint, 6500);
      AUDIO.play("quest");
    }
    if (result.complete && !game.victoryShown) {
      game.victoryShown = true;
      onVictory();
    }
    hudRefresh(true);
  }

  function onVictory() {
    AUDIO.play("beacon");
    saveNow(false);
    setMode("victory");
    ui.open("victory", snapshot());
  }

  function onDeath() {
    if (game.deathPending) {
      return;
    }
    game.deathPending = true;
    AUDIO.play("death");
    saveNow(false);
    setMode("dead");
    ui.open("death", snapshot());
  }

  function updateClock(dt) {
    const wasNight = LIGHT.isNight(game.clock.time);
    game.clock.time += dt / CONFIG.dayLength;
    if (game.clock.time >= 1) {
      game.clock.time -= 1;
      game.clock.day += 1;
      PROGRESSION.record(game.progress, "daysSurvived");
      toast("Day " + game.clock.day + " begins", "quest");
    }
    const isNight = LIGHT.isNight(game.clock.time);
    if (isNight !== wasNight) {
      if (isNight) {
        AUDIO.play("night");
        hint("Night falls. Hollows stir in the dark — stay near a torch.", 7000);
      } else {
        hint("The sun returns. The hollows fade.", 4500);
      }
    }
    lastNightState = isNight;
  }

  function cameraTarget() {
    const ts = CONFIG.tileSize;
    const desiredX = game.player.x * ts - CONFIG.viewWidth / 2;
    const desiredY = game.player.y * ts - CONFIG.viewHeight / 2 - 24;
    return {
      x: clamp(desiredX, 0, Math.max(0, game.world.width * ts - CONFIG.viewWidth)),
      y: clamp(desiredY, 0, Math.max(0, game.world.height * ts - CONFIG.viewHeight))
    };
  }

  function followCamera(dt) {
    const target = cameraTarget();
    const smoothing = 1 - Math.exp(-dt * 7);
    game.camera.x += (target.x - game.camera.x) * smoothing;
    game.camera.y += (target.y - game.camera.y) * smoothing;
  }

  function lightBounds() {
    const ts = CONFIG.tileSize;
    return {
      x0: Math.floor(game.camera.x / ts) - 20,
      y0: Math.floor(game.camera.y / ts) - 10,
      x1: Math.ceil((game.camera.x + CONFIG.viewWidth) / ts) + 20,
      y1: Math.ceil((game.camera.y + CONFIG.viewHeight) / ts) + 20
    };
  }

  function updateLight(force) {
    const bounds = lightBounds();
    const key =
      Math.floor(game.clock.time * 400) +
      "|" +
      Math.floor(game.camera.x / CONFIG.tileSize) +
      "|" +
      Math.floor(game.camera.y / CONFIG.tileSize) +
      "|" +
      game.worldVersion;
    if (!force && key === game.lightKey) {
      return;
    }
    game.lightKey = key;
    game.light = LIGHT.computeLight(game.world, bounds, game.clock.time);
  }

  function tileUnderPointer() {
    const pointer = input.pointer;
    if (!pointer.valid) {
      return null;
    }
    return { tx: pointer.tx, ty: pointer.ty, id: WORLD.getBlock(game.world, pointer.tx, pointer.ty) };
  }

  function miningCheck(tx, ty) {
    if (!WORLD.inBounds(game.world, tx, ty)) {
      return { ok: false, reason: "out-of-bounds" };
    }
    if (ty >= game.world.height - 1) {
      return { ok: false, reason: "void-floor" };
    }
    const id = WORLD.getBlock(game.world, tx, ty);
    if (id === null || id === B.air) {
      return { ok: false, reason: "air" };
    }
    if (!PLAYER.canReach(game.player, tx, ty, CONFIG.reach)) {
      return { ok: false, reason: "reach" };
    }
    if (!WORLD.isExposed(game.world, tx, ty)) {
      return { ok: false, reason: "covered" };
    }
    const tier = BLOCKS.bestPickTier(game.inventory.slots);
    const time = BLOCKS.breakTime(id, tier);
    if (time === null) {
      return { ok: false, reason: "tool", required: BLOCKS.requiredTier(id), id: id };
    }
    return { ok: true, id: id, time: time };
  }

  function miningErrorText(check) {
    switch (check.reason) {
      case "reach":
        return "That block is out of reach — step closer.";
      case "covered":
        return "Dig from an exposed face first.";
      case "tool":
        return "Needs a " + BLOCKS.tierName(check.required) + " to break.";
      case "void-floor":
        return "The world floor cannot be broken.";
      default:
        return "";
    }
  }

  function tryAttack(tx, ty) {
    const found = MOBS.attackAt(game.mobs, tx + 0.5, ty + 0.5, 0.45);
    if (!found.hit) {
      return false;
    }
    const mob = found.mob;
    const distance = Math.hypot(mob.x - game.player.x, mob.y - game.player.y);
    if (distance > CONFIG.reach + 1.2) {
      return false;
    }
    const damage = Math.max(1, BLOCKS.bestSwordDamage(game.inventory.slots));
    const killed = MOBS.damage(mob, damage);
    AUDIO.play("break");
    RENDER.spawnParticles(game.particles, mob.x, mob.y - 0.8, "#ff8a4c", 8);
    if (killed) {
      MOBS.remove(game.mobs, mob);
      toast("The hollow dissolves", "quest");
    }
    return true;
  }

  function tryBreakBlock(tx, ty) {
    const check = miningCheck(tx, ty);
    if (!check.ok) {
      return false;
    }
    const id = check.id;
    const drop = BLOCKS.dropOf(id);
    if (drop !== null) {
      const leftover = INVENTORY.add(game.inventory, drop, 1);
      if (leftover > 0) {
        hint("Your inventory is full.", 3000);
        return false;
      }
    }
    WORLD.setBlock(game.world, tx, ty, B.air);
    game.dug.add(tx + "," + ty);
    game.worldVersion += 1;
    PROGRESSION.recordMine(game.progress, id);
    const def = BLOCKS.get(id);
    RENDER.spawnParticles(game.particles, tx, ty, def ? def.palette.base : "#aaa", 10);
    AUDIO.play("break");
    if (id === B.beacon) {
      game.beacon = null;
      toast("The beacon is dark again.", "warn");
    }
    if (id === B.wood && game.progress.stats.woodCollected === 1) {
      hint("Press E to craft planks and a workbench.", 6500);
    }
    updateProgress();
    updateLight(true);
    hudRefresh(true);
    return true;
  }

  function tryPlaceBlock(tx, ty) {
    const stack = INVENTORY.selectedStack(game.inventory);
    if (!stack) {
      hint("Select a block in the hotbar first.", 3000);
      return false;
    }
    const def = BLOCKS.itemDef(stack.id);
    if (!def || def.kind !== "block") {
      hint("That item is not a placeable block.", 3000);
      return false;
    }
    if (!WORLD.canPlaceAt(game.world, tx, ty, stack.id)) {
      hint("Place blocks against solid ground.", 3000);
      return false;
    }
    if (PLAYER.overlapsTile(game.player, tx, ty)) {
      hint("You are standing there.", 2500);
      return false;
    }
    for (let i = 0; i < game.mobs.list.length; i += 1) {
      const mob = game.mobs.list[i];
      const left = mob.x - mob.width / 2;
      const right = mob.x + mob.width / 2;
      const top = mob.y - mob.height;
      if (right > tx && left < tx + 1 && mob.y > ty && top < ty + 1) {
        hint("A hollow is in the way.", 2500);
        return false;
      }
    }
    INVENTORY.remove(game.inventory, stack.id, 1);
    WORLD.setBlock(game.world, tx, ty, stack.id);
    game.worldVersion += 1;
    PROGRESSION.recordPlace(game.progress, stack.id);
    if (stack.id === B.beacon) {
      game.beacon = { x: tx, y: ty };
    }
    if (stack.id === B.workbench) {
      hint("Stand near the workbench and press E to craft tools.", 6000);
    }
    RENDER.spawnParticles(game.particles, tx, ty, "#d8c68f", 5);
    AUDIO.play("place");
    updateProgress();
    updateLight(true);
    hudRefresh(true);
    return true;
  }

  function startMiningAt(tx, ty) {
    const check = miningCheck(tx, ty);
    if (!check.ok) {
      const message = miningErrorText(check);
      if (message) {
        hint(message, 2800);
      }
      game.mining = null;
      return;
    }
    game.mining = { tx: tx, ty: ty, progress: 0, time: check.time, fraction: 0 };
    AUDIO.play("mine");
  }

  function updateMining(dt) {
    if (!input.pointer.down || !input.pointer.valid) {
      game.mining = null;
      return;
    }
    const tx = input.pointer.tx;
    const ty = input.pointer.ty;
    const check = miningCheck(tx, ty);
    if (!check.ok) {
      game.mining = null;
      return;
    }
    if (!game.mining || game.mining.tx !== tx || game.mining.ty !== ty) {
      game.mining = { tx: tx, ty: ty, progress: 0, time: check.time, fraction: 0 };
    }
    game.mining.time = check.time;
    game.mining.progress += dt;
    game.mining.fraction = Math.min(1, game.mining.progress / check.time);
    if (game.mining.progress >= check.time) {
      const target = game.mining;
      game.mining = null;
      tryBreakBlock(target.tx, target.ty);
    }
  }

  function pointerPlacementState() {
    if (!input || !input.pointer.valid) {
      return { valid: false, blockId: 0 };
    }
    const stack = INVENTORY.selectedStack(game.inventory);
    const def = stack ? BLOCKS.itemDef(stack.id) : null;
    if (!def || def.kind !== "block") {
      return { valid: false, blockId: 0 };
    }
    const valid = WORLD.canPlaceAt(game.world, input.pointer.tx, input.pointer.ty, stack.id);
    return { valid: valid, blockId: stack.id };
  }

  function update(dt) {
    updateClock(dt);
    const blocked = ui.isBlocking();
    const moveInput = {
      left: !blocked && input.state.left,
      right: !blocked && input.state.right,
      jump: !blocked && input.state.jump,
      jumpPressed: !blocked && input.consumeJump()
    };
    const wasOnGround = game.player.onGround;
    const beforeX = game.player.x;
    PLAYER.update(game.player, game.world, moveInput, dt);
    game.progress.stats.playtime += dt;

    if (game.player.onGround && !wasOnGround && game.player.vy >= 0) {
      RENDER.spawnParticles(game.particles, game.player.x, game.player.y, "#c9b47a", 3);
    }
    if (game.player.onGround && Math.abs(game.player.x - beforeX) > 0.01 && Math.random() < 0.14) {
      RENDER.spawnStep(game.particles, game.player.x, game.player.y, game.player.facing);
    }

    const mobEvents = MOBS.update(game.mobs, game.world, game.player, dt, {
      isNight: LIGHT.isNight(game.clock.time),
      lightAt: function lightAt(x, y) {
        return LIGHT.lightAt(game.light, x, y);
      }
    });
    if (mobEvents.damage > 0) {
      const applied = PLAYER.damage(game.player, mobEvents.damage);
      if (applied) {
        AUDIO.play("hurt");
        game.hurtFlash = 0.6;
        hint("Hollows hit hard in the dark. Light and shelter help.", 3200);
      }
    }
    if (game.player.dead) {
      onDeath();
    }

    updateMining(dt);
    followCamera(dt);
    RENDER.updateParticles(game.particles, dt);
    game.hurtFlash = Math.max(0, game.hurtFlash - dt * 1.6);

    game.autosaveTimer += dt;
    if (game.autosaveTimer >= CONFIG.autosaveMs / 1000) {
      game.autosaveTimer = 0;
      saveNow(false);
    }
    updateLight(false);
  }

  function renderScene() {
    const placement = pointerPlacementState();
    RENDER.renderFrame(ctx, {
      world: game.world,
      player: game.player,
      camera: game.camera,
      time: game.clock.time,
      day: game.clock.day,
      light: game.light,
      mobs: game.mobs,
      particles: game.particles,
      dug: game.dug,
      pointer: input ? { tx: input.pointer.tx, ty: input.pointer.ty, valid: input.pointer.valid } : null,
      mining: game.mining,
      placeValid: placement.valid,
      placeBlockId: placement.blockId,
      heldItem: INVENTORY.selectedStack(game.inventory) ? INVENTORY.selectedStack(game.inventory).id : 0,
      hurtFlash: game.hurtFlash,
      pausedTint: game.mode === "paused" || game.mode === "inventory" || game.mode === "dead" || game.mode === "victory",
      beaconGlow: game.beacon,
      clockSeconds: performance.now() / 1000
    });
  }

  function frame(now) {
    if (!lastFrame) {
      lastFrame = now;
    }
    const dt = Math.min(0.05, Math.max(0, (now - lastFrame) / 1000));
    lastFrame = now;
    if (game.mode === "playing") {
      let remaining = dt;
      let steps = 0;
      while (remaining >= STEP && steps < 5) {
        update(STEP);
        remaining -= STEP;
        steps += 1;
      }
      if (steps === 0) {
        update(dt);
      }
      hudRefresh(false);
    } else {
      followCamera(dt);
      updateLight(false);
    }
    renderScene();
    window.requestAnimationFrame(frame);
  }

  function saveNow(announce) {
    const result = SAVE.save(window.localStorage, {
      world: game.world,
      player: game.player,
      inventory: game.inventory,
      progress: game.progress,
      clock: game.clock
    });
    if (result.ok) {
      game.lastSaveAt = result.savedAt;
      game.saveError = "";
      game.saveSummary = SAVE.summarize({
        clock: game.clock,
        progress: game.progress,
        savedAt: result.savedAt
      });
      if (announce) {
        toast("Progress saved", "save");
      }
    } else {
      game.saveError = result.error;
      if (announce) {
        toast("Could not save: " + result.error, "warn");
      }
    }
    hudRefresh(true);
    return result;
  }

  function startNewWorld() {
    const seed = (Date.now() ^ (Math.random() * 0xffffffff)) >>> 0;
    SAVE.clear(window.localStorage);
    resetWorld(seed);
    game.mode = "title";
    enterGame();
    toast("A new meadow. Mine a tree to begin.", "quest");
  }

  function enterGame() {
    ui.close();
    setMode("playing");
    AUDIO.unlock();
    hudRefresh(true);
    if (game.firstRun) {
      game.firstRun = false;
      window.setTimeout(function firstHint() {
        hint("Hold left mouse on a tree trunk to gather wood.", 7000);
      }, 700);
    }
  }

  function showTitle() {
    setMode("title");
    ui.open("title", snapshot());
    hudRefresh(true);
  }

  function openInventory() {
    if (game.mode !== "playing") {
      return;
    }
    setMode("inventory");
    ui.open("inventory", snapshot());
  }

  function closeInventory() {
    if (game.mode !== "inventory") {
      return;
    }
    ui.close();
    setMode("playing");
  }

  function pauseGame() {
    if (game.mode !== "playing") {
      return;
    }
    saveNow(false);
    setMode("paused");
    ui.open("pause", snapshot());
  }

  function resumeGame() {
    if (game.mode !== "paused" && game.mode !== "inventory") {
      return;
    }
    ui.close();
    setMode("playing");
  }

  function toggleMute() {
    game.muted = AUDIO.setMuted(!AUDIO.isMuted());
    ui.setMuted(game.muted);
    toast(game.muted ? "Sound muted" : "Sound on", "save");
    hudRefresh(true);
  }

  function craft(recipeId) {
    const recipe = CRAFTING.byId(recipeId);
    if (!recipe) {
      return;
    }
    const stations = CRAFTING.stationsNear(game.world, game.player, 4);
    const result = CRAFTING.craft(recipe, game.inventory, stations);
    if (!result.ok) {
      if (result.reason === "station") {
        toast("Needs a nearby " + recipe.station, "warn");
      } else {
        toast("Missing materials", "warn");
      }
      AUDIO.play("error");
      return;
    }
    PROGRESSION.recordCraft(game.progress, recipeId);
    AUDIO.play("craft");
    toast("Crafted " + recipe.name, "quest");
    // Make a newly crafted placeable item the active hotbar stack so the next
    // right-click can place it without hunting through the inventory.
    const outputDef = BLOCKS.itemDef(recipe.output.id);
    if (outputDef && outputDef.kind === "block") {
      for (let i = 0; i < CONFIG.hotbarSize; i += 1) {
        const stack = game.inventory.slots[i];
        if (stack && stack.id === recipe.output.id) {
          INVENTORY.select(game.inventory, i);
          break;
        }
      }
    }
    updateProgress();
    stationCache.at = 0;
    hudRefresh(true);
    ui.refreshInventory();
  }

  function moveSlot(from, to) {
    INVENTORY.swap(game.inventory, from, to);
    hudRefresh(true);
  }

  function selectSlot(index) {
    INVENTORY.select(game.inventory, index);
    AUDIO.play("ui");
    hudRefresh(true);
  }

  function respawn() {
    game.deathPending = false;
    PLAYER.respawn(game.player, spawnAt());
    ui.close();
    setMode("playing");
    toast("You wake at the meadow. Your pack is intact.", "quest");
    hudRefresh(true);
  }

  function action(name) {
    if (!ui) {
      return;
    }
    switch (name) {
      case "primary":
        if (game.mode === "title") {
          AUDIO.unlock();
          enterGame();
        }
        break;
      case "newWorld":
        if (game.mode === "title") {
          startNewWorld();
        } else {
          ui.armNewWorld();
        }
        break;
      case "newWorldConfirm":
        startNewWorld();
        break;
      case "resume":
        resumeGame();
        break;
      case "save":
        saveNow(true);
        ui.open("pause", snapshot());
        break;
      case "help":
        if (game.mode === "playing") {
          pauseGame();
        }
        ui.handleHelp();
        break;
      case "helpClose":
        ui.handleHelp();
        break;
      case "close":
        closeInventory();
        break;
      case "mute":
        toggleMute();
        if (game.mode === "paused") {
          ui.open("pause", snapshot());
        }
        break;
      case "quit":
        saveNow(false);
        showTitle();
        break;
      case "respawn":
        respawn();
        break;
      case "victoryContinue":
        ui.close();
        setMode("playing");
        toast("The sandbox is yours.", "quest");
        break;
      default:
        break;
    }
  }

  function onEscape() {
    if (game.mode === "inventory") {
      closeInventory();
    } else if (game.mode === "paused") {
      resumeGame();
    } else if (game.mode === "playing") {
      pauseGame();
    } else if (ui.currentScreen() === "help") {
      ui.handleHelp();
    }
  }

  function onHelp() {
    if (game.mode === "playing") {
      pauseGame();
    }
    ui.handleHelp();
  }

  function onToggleInventory() {
    if (game.mode === "playing") {
      openInventory();
    } else if (game.mode === "inventory") {
      closeInventory();
    }
  }

  function buildTestApi() {
    function tileToClient(tx, ty) {
      const rect = canvas.getBoundingClientRect();
      const px = (tx + 0.5) * CONFIG.tileSize - game.camera.x;
      const py = (ty + 0.5) * CONFIG.tileSize - game.camera.y;
      return {
        x: rect.left + (px / CONFIG.viewWidth) * rect.width,
        y: rect.top + (py / CONFIG.viewHeight) * rect.height
      };
    }

    function mineTargets(count) {
      const targets = [];
      const radius = Math.ceil(CONFIG.reach) + 1;
      const tier = BLOCKS.bestPickTier(game.inventory.slots);
      const feetX = Math.floor(game.player.x);
      const feetY = Math.floor(game.player.y + 0.05);
      const minX = Math.max(0, Math.floor(game.player.x) - radius);
      const maxX = Math.min(game.world.width - 1, Math.floor(game.player.x) + radius);
      const minY = Math.max(0, Math.floor(game.player.y) - radius);
      const maxY = Math.min(game.world.height - 2, Math.floor(game.player.y) + radius);
      for (let ty = minY; ty <= maxY; ty += 1) {
        for (let tx = minX; tx <= maxX; tx += 1) {
          const id = WORLD.getBlock(game.world, tx, ty);
          if (!id || id === B.air) {
            continue;
          }
          // Never offer the tile the player is standing on: mining it would
          // drop the player and the placement that follows would be refused.
          if (tx === feetX && ty === feetY) {
            continue;
          }
          if (PLAYER.overlapsTile(game.player, tx, ty)) {
            continue;
          }
          if (!PLAYER.canReach(game.player, tx, ty, CONFIG.reach)) {
            continue;
          }
          if (!WORLD.isExposed(game.world, tx, ty)) {
            continue;
          }
          if (BLOCKS.breakTime(id, tier) === null) {
            continue;
          }
          targets.push({
            tx: tx,
            ty: ty,
            id: id,
            distance: PLAYER.distanceToTile(game.player, tx, ty)
          });
        }
      }
      targets.sort(function sort(a, b) {
        return a.distance - b.distance || a.tx - b.tx || a.ty - b.ty;
      });
      return targets.slice(0, count || 12);
    }

    return {
      ready: true,
      getState: function getState() {
        return {
          mode: game.mode,
          player: { x: game.player.x, y: game.player.y, health: game.player.health },
          camera: { x: game.camera.x, y: game.camera.y },
          clock: { day: game.clock.day, time: game.clock.time },
          worldVersion: game.worldVersion,
          tier: BLOCKS.bestPickTier(game.inventory.slots),
          inventory: INVENTORY.serialize(game.inventory),
          progress: PROGRESSION.serialize(game.progress),
          hasSave: SAVE.hasSave(window.localStorage),
          saveStatus: snapshot().saveStatus,
          screen: ui.currentScreen(),
          mobCount: game.mobs.list.length,
          isNight: LIGHT.isNight(game.clock.time),
          beacon: game.beacon,
          lightReady: !!game.light
        };
      },
      test: {
        mineTargets: mineTargets,
        tileToClient: tileToClient,
        blockAt: function blockAt(tx, ty) {
          return WORLD.getBlock(game.world, tx, ty);
        },
        playerTile: function playerTile() {
          return { x: Math.floor(game.player.x), y: Math.floor(game.player.y) };
        },
        surfaceHeight: function surfaceHeight(x) {
          return WORLD.surfaceHeight(game.world, x);
        },
        setTime: function setTime(value) {
          game.clock.time = ((value % 1) + 1) % 1;
          updateLight(true);
        },
        setDay: function setDay(value) {
          game.clock.day = Math.max(1, Math.floor(value));
        },
        teleport: function teleport(tx, ty) {
          game.player.x = tx + 0.5;
          game.player.y = ty;
          game.player.vx = 0;
          game.player.vy = 0;
          game.player.onGround = false;
          followCamera(1);
          updateLight(true);
        },
        give: function give(id, count) {
          INVENTORY.add(game.inventory, id, count || 1);
          hudRefresh(true);
          return INVENTORY.countOf(game.inventory, id);
        },
        setBlock: function setBlock(tx, ty, id) {
          WORLD.setBlock(game.world, tx, ty, id);
          game.worldVersion += 1;
          if (id === B.beacon) {
            game.beacon = { x: tx, y: ty };
          }
          updateLight(true);
        },
        save: function save() {
          return saveNow(true);
        },
        openInventory: function openInventoryForTest() {
          openInventory();
        },
        openPause: function pauseForTest() {
          pauseGame();
        },
        stationNames: function stationNames() {
          return Array.from(CRAFTING.stationsNear(game.world, game.player, 4)).sort();
        }
      }
    };
  }

  function boot() {
    RENDER.initTextures();
    game.muted = AUDIO.isMuted();

    const loaded = SAVE.load(window.localStorage);
    if (loaded.ok) {
      loadFromSave(loaded.state, loaded.data);
    } else {
      resetWorld(CONFIG.seed);
      if (loaded.error === "corrupt") {
        window.setTimeout(function corrupted() {
          toast("The saved meadow could not be read. A fresh one awaits.", "warn");
        }, 900);
      }
    }

    ui = UI.createUI({
      action: action,
      selectSlot: selectSlot,
      moveSlot: moveSlot,
      craft: craft
    });
    ui.init();
    ui.setMuted(game.muted);

    input = INPUT.createInput(canvas, {
      getCamera: function getCamera() {
        return game.camera;
      },
      getWorld: function getWorld() {
        return game.world;
      },
      isBlocked: function isBlocked() {
        return ui.isBlocking();
      },
      onSelectSlot: selectSlot,
      onToggleInventory: onToggleInventory,
      onEscape: onEscape,
      onHelp: onHelp,
      onMute: toggleMute,
      onWheel: function onWheel(direction) {
        if (ui.isBlocking()) {
          return;
        }
        selectSlot((game.inventory.selected + direction + CONFIG.hotbarSize) % CONFIG.hotbarSize);
      },
      onPointerMove: function onPointerMove() {},
      onPointerDown: function onPointerDown(tile) {
        if (ui.isBlocking() || game.mode !== "playing") {
          return;
        }
        AUDIO.unlock();
        if (tryAttack(tile.tx, tile.ty)) {
          return;
        }
        startMiningAt(tile.tx, tile.ty);
      },
      onPointerUp: function onPointerUp() {
        game.mining = null;
      },
      onPlace: function onPlace(tile) {
        if (ui.isBlocking() || game.mode !== "playing") {
          return;
        }
        AUDIO.unlock();
        tryPlaceBlock(tile.tx, tile.ty);
      }
    });
    input.attach();

    window.addEventListener("error", function onError(event) {
      setStatus("error", event.message || "runtime error");
    });
    window.addEventListener("unhandledrejection", function onRejection(event) {
      setStatus("error", String(event.reason));
    });
    window.addEventListener("beforeunload", function beforeUnload() {
      if (game.world) {
        saveNow(false);
      }
    });
    document.addEventListener("visibilitychange", function visibility() {
      if (document.visibilityState === "hidden" && game.world) {
        saveNow(false);
      }
    });

    setStatus("ready", "ready");
    showTitle();
    window.__game = buildTestApi();
    window.requestAnimationFrame(frame);
  }

  try {
    boot();
  } catch (error) {
    setStatus("error", error && error.message ? error.message : String(error));
    throw error;
  }
})();
