(function () {
  "use strict";

  const CONFIG = window.MosswildConfig;
  const CONTENT = window.MosswildContent;
  const TIME = window.MosswildTime;
  const WORLD = window.MosswildWorld;
  const PLAYER = window.MosswildPlayer;
  const INV = window.MosswildInventory;
  const RENDER = window.MosswildRender;
  const UI = window.MosswildUI;
  const AUDIO = window.MosswildAudio;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d", { alpha: false });
  const view = {
    width: window.innerWidth,
    height: window.innerHeight,
    dpr: Math.min(2, Math.max(1, window.devicePixelRatio || 1))
  };

  const STEP = 1 / 60;
  const JUMP_KEYS = ["Space", "KeyW", "ArrowUp"];
  const MOVEMENT_LABELS = {
    KeyA: "left",
    ArrowLeft: "left",
    KeyD: "right",
    ArrowRight: "right"
  };

  let game = null;
  let running = false;
  let lastFrame = 0;
  let accumulator = 0;
  let uiTimer = 0;
  let tooltipTimer = 0;
  let lastHealthSignature = -1;
  let audioGestureDone = false;
  let booted = false;
  const actions = {};

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function randomSeed() {
    try {
      const array = new Uint32Array(1);
      window.crypto.getRandomValues(array);
      return array[0] >>> 0;
    } catch (error) {
      return (Math.random() * 4294967296) >>> 0;
    }
  }

  function formatTimeOfDay(timestamp) {
    const date = new Date(timestamp);
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");
    return hour + ":" + minute;
  }

  function getStorage() {
    try {
      const storage = window.localStorage;
      return storage;
    } catch (error) {
      return null;
    }
  }

  function readSavedWorld() {
    const storage = getStorage();
    if (!storage) {
      return { available: false, raw: null, error: null };
    }
    try {
      return { available: true, raw: storage.getItem(CONFIG.saveKey), error: null };
    } catch (error) {
      return { available: false, raw: null, error };
    }
  }

  function resizeCanvas() {
    view.width = Math.max(1, window.innerWidth);
    view.height = Math.max(1, window.innerHeight);
    view.dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    canvas.width = Math.round(view.width * view.dpr);
    canvas.height = Math.round(view.height * view.dpr);
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    if (game) {
      game.view = view;
      game.mouse.x = clamp(game.mouse.x, 0, view.width);
      game.mouse.y = clamp(game.mouse.y, 0, view.height);
      clampCamera();
      if (game.mode === "playing") {
        updateHover();
      }
    }
  }

  function makeFreshState(soundOn) {
    const inventory = INV.createFreshInventory();
    const progress = INV.createFreshProgress();
    const state = {
      inventory: inventory.inventory,
      tools: inventory.tools,
      hotbar: inventory.hotbar,
      selectedSlot: inventory.selectedSlot,
      flags: progress.flags,
      stats: progress.stats,
      worldTime: CONFIG.daySeconds * CONFIG.startDayFraction,
      playSeconds: 0,
      soundOn: soundOn !== false
    };
    return state;
  }

  function makeFreshRun(seed, soundOn) {
    const world = WORLD.createWorld(seed);
    const player = PLAYER.createPlayer(world.spawn);
    const state = makeFreshState(soundOn);
    return {
      world,
      player,
      state,
      loadedFromSave: false,
      savedAt: 0
    };
  }

  function sanitizeProgress(data) {
    const progress = INV.createFreshProgress();
    const savedFlags = data && data.flags && typeof data.flags === "object" ? data.flags : {};
    const savedStats = data && data.stats && typeof data.stats === "object" ? data.stats : {};
    Object.keys(progress.flags).forEach(function (key) {
      progress.flags[key] = Boolean(savedFlags[key]);
    });
    Object.keys(progress.stats).forEach(function (key) {
      const value = Number(savedStats[key]);
      if (Number.isFinite(value) && value >= 0) {
        progress.stats[key] = value;
      }
    });
    return progress;
  }

  function getSafePlayer(world, x, y) {
    let targetX = Number.isFinite(x) ? x : world.spawn.x;
    let targetY = Number.isFinite(y) ? y : world.spawn.y;
    targetX = clamp(targetX, 0.5, world.width - 0.5);
    targetY = clamp(targetY, 1, world.height - 1);
    const player = PLAYER.createPlayer({ x: targetX, y: targetY });
    if (PLAYER.collidesWorld(world, targetX, targetY, player.width, player.height)) {
      player.x = world.spawn.x;
      player.y = world.spawn.y;
    }
    return player;
  }

  function loadRun(raw) {
    const data = JSON.parse(raw);
    if (!data || data.v !== CONFIG.saveVersion) {
      throw new Error("This save uses a different version.");
    }
    const world = WORLD.worldFromSave(data.world);
    const inventory = INV.sanitizeInventoryState(data);
    const progress = sanitizeProgress(data);
    const savedPlayer = data.player && typeof data.player === "object" ? data.player : {};
    const player = getSafePlayer(world, Number(savedPlayer.x), Number(savedPlayer.y));
    const health = Number(savedPlayer.health);
    player.health = Number.isFinite(health) && health > 0
      ? clamp(health, 1, player.maxHealth)
      : player.maxHealth;
    player.facing = Number(savedPlayer.facing) < 0 ? -1 : 1;
    player.invulnerable = 1.4;

    let worldTime = Number(data.worldTime);
    if (!Number.isFinite(worldTime) || worldTime < 0) {
      worldTime = CONFIG.daySeconds * CONFIG.startDayFraction;
    }
    let playSeconds = Number(data.playSeconds);
    if (!Number.isFinite(playSeconds) || playSeconds < 0) {
      playSeconds = progress.stats.playSeconds || 0;
    }
    progress.stats.playSeconds = Math.max(progress.stats.playSeconds, playSeconds);

    const state = {
      inventory: inventory.inventory,
      tools: inventory.tools,
      hotbar: inventory.hotbar,
      selectedSlot: inventory.selectedSlot,
      flags: progress.flags,
      stats: progress.stats,
      worldTime,
      playSeconds: progress.stats.playSeconds,
      soundOn: data.soundOn !== false
    };
    if (state.tools.pickaxe && state.tools.pickaxe.tier >= 2) {
      state.flags.stonePickaxeCrafted = true;
    }

    return {
      world,
      player,
      state,
      loadedFromSave: true,
      savedAt: Number(data.savedAt) || 0
    };
  }

  function makeGame(run, storageAvailable) {
    const dayInfo = TIME.getDayInfo(run.state.worldTime, CONFIG.daySeconds);
    const g = {
      ready: false,
      mode: "loading",
      world: run.world,
      player: run.player,
      state: run.state,
      view,
      camera: { x: 0, y: 0 },
      mouse: { x: view.width / 2, y: view.height / 2, inside: false, left: false, right: false },
      keys: new Set(),
      jumpQueued: false,
      enemies: [],
      particles: [],
      floaters: [],
      hover: null,
      dayInfo,
      elapsed: 0,
      attackCooldown: 0,
      placeCooldown: 0,
      mineSoundTimer: 0,
      miningTarget: null,
      miningProgress: 0,
      nearWorkbench: false,
      autosaveTimer: 0,
      loadedFromSave: run.loadedFromSave,
      lastSavedAt: run.savedAt,
      lastSavedLabel: run.loadedFromSave && run.savedAt
        ? "Last saved · " + formatTimeOfDay(run.savedAt)
        : "Autosave on · every 10s",
      storageAvailable: Boolean(storageAvailable),
      saveWarningShown: false,
      wasNight: dayInfo.isNight,
      shake: 0,
      pendingCelebration: 0,
      overlayReturnMode: "playing",
      lastWarningAt: -20,
      victoryShown: false,
      tutorialAge: 0,
      enemySpawnTimer: 4
    };
    g.ready = true;
    return g;
  }

  function findSafeRespawnPoint(world) {
    let spawn = world.spawn;
    if (!spawn || !Number.isFinite(spawn.x) || !Number.isFinite(spawn.y)) {
      spawn = WORLD.findSpawn(world);
    }
    for (let offset = 0; offset < world.height; offset += 1) {
      const y = spawn.y - offset;
      if (y < 2) {
        break;
      }
      if (!PLAYER.collidesWorld(world, spawn.x, y, CONFIG.player.width, CONFIG.player.height)) {
        return { x: spawn.x, y };
      }
    }
    return spawn;
  }

  function installRun(run, options) {
    const opts = options || {};
    const storageAvailable = opts.storageAvailable !== undefined
      ? opts.storageAvailable
      : game
        ? game.storageAvailable
        : true;
    const soundOn = game && game.state ? game.state.soundOn : true;
    if (!game) {
      game = makeGame(run, storageAvailable);
      return;
    }
    const previousSound = run.state.soundOn;
    game.world = run.world;
    game.player = run.player;
    game.state = run.state;
    if (opts.preserveSound) {
      game.state.soundOn = soundOn;
    } else {
      game.state.soundOn = previousSound;
    }
    game.mode = "playing";
    game.camera = { x: 0, y: 0 };
    game.mouse = { x: view.width / 2, y: view.height / 2, inside: false, left: false, right: false };
    game.keys.clear();
    game.jumpQueued = false;
    game.enemies = [];
    game.particles = [];
    game.floaters = [];
    game.hover = null;
    game.dayInfo = TIME.getDayInfo(game.state.worldTime, CONFIG.daySeconds);
    game.elapsed = 0;
    game.attackCooldown = 0;
    game.placeCooldown = 0;
    game.mineSoundTimer = 0;
    game.miningTarget = null;
    game.miningProgress = 0;
    game.nearWorkbench = false;
    game.autosaveTimer = 0;
    game.tutorialAge = 0;
    game.enemySpawnTimer = 4;
    game.loadedFromSave = run.loadedFromSave;
    game.lastSavedAt = run.savedAt;
    game.lastSavedLabel = run.loadedFromSave && run.savedAt
      ? "Last saved · " + formatTimeOfDay(run.savedAt)
      : "Autosave on · every 10s";
    game.storageAvailable = storageAvailable;
    game.saveWarningShown = false;
    game.wasNight = game.dayInfo.isNight;
    game.shake = 0;
    game.pendingCelebration = 0;
    game.overlayReturnMode = "playing";
    game.lastWarningAt = -20;
    game.victoryShown = false;
    updateCamera(0, true);
    updateNearWorkbench(true);
    game.ready = true;
    if (game.state.soundOn) {
      AUDIO.setEnabled(true);
    } else {
      AUDIO.setEnabled(false);
    }
    refreshAllUI();
    UI.setMode("playing");
    UI.setSaveStatus(game.lastSavedLabel, "World ready. Autosave is on.");
  }

  function refreshAllUI() {
    if (!game) {
      return;
    }
    UI.refreshHotbar();
    UI.refreshVitals();
    UI.refreshQuest(true);
    UI.refreshClock();
    UI.refreshSound();
    UI.refreshTutorial();
    lastHealthSignature = Math.round(game.player.health * 4);
  }

  function serialiseGame() {
    const player = game.player;
    const dead = player.dead || player.health <= 0;
    const spawn = findSafeRespawnPoint(game.world);
    return {
      v: CONFIG.saveVersion,
      savedAt: Date.now(),
      seed: game.world.seed,
      world: WORLD.worldToSave(game.world),
      player: {
        x: dead ? spawn.x : player.x,
        y: dead ? spawn.y : player.y,
        health: dead ? player.maxHealth : player.health,
        facing: player.facing
      },
      inventory: game.state.inventory,
      tools: game.state.tools,
      hotbar: game.state.hotbar,
      selectedSlot: game.state.selectedSlot,
      flags: game.state.flags,
      stats: game.state.stats,
      worldTime: game.state.worldTime,
      playSeconds: game.state.playSeconds,
      soundOn: game.state.soundOn
    };
  }

  function saveGame(manual, silent) {
    if (!game || !game.ready) {
      return false;
    }
    if (!game.storageAvailable) {
      if (!game.saveWarningShown) {
        game.saveWarningShown = true;
        UI.showToast("This browser will not let the page save. Progress stays for this session.", "warn", 5000);
      }
      UI.setSaveStatus("Saving unavailable", "Local browser storage is blocked or unavailable.");
      return false;
    }
    const storage = getStorage();
    if (!storage) {
      game.storageAvailable = false;
      UI.setSaveStatus("Saving unavailable", "Local browser storage is blocked or unavailable.");
      return false;
    }
    try {
      const payload = serialiseGame();
      storage.setItem(CONFIG.saveKey, JSON.stringify(payload));
      game.lastSavedAt = payload.savedAt;
      game.lastSavedLabel = "Saved · " + formatTimeOfDay(payload.savedAt);
      UI.setSaveStatus(game.lastSavedLabel, "Progress saved locally at " + formatTimeOfDay(payload.savedAt) + ".");
      if (manual) {
        UI.showToast("World saved.", "save", 1800);
        AUDIO.play("save");
      }
      if (game.mode === "paused") {
        UI.refreshPause();
      }
      return true;
    } catch (error) {
      game.storageAvailable = false;
      UI.setSaveStatus("Save failed", error && error.message ? error.message : String(error));
      if (!silent) {
        UI.showToast("The world could not be saved. " + (error && error.message ? error.message : ""), "warn", 5000);
      }
      return false;
    }
  }

  function removeKey(code) {
    if (game) {
      game.keys.delete(code);
    }
  }

  function clearControls() {
    if (!game) {
      return;
    }
    game.keys.clear();
    game.jumpQueued = false;
    game.mouse.left = false;
    game.mouse.right = false;
    game.miningTarget = null;
    game.miningProgress = 0;
  }

  function setMode(mode) {
    if (!game) {
      return;
    }
    if (mode !== "playing") {
      clearControls();
      game.hover = null;
    }
    if (mode === "playing" && game.mode !== "playing") {
      accumulator = 0;
      lastFrame = performance.now();
    }
    game.mode = mode;
    UI.setMode(mode);
    document.getElementById("app").dataset.mode = mode;
  }

  function updateCamera(dt, snap) {
    if (!game) {
      return;
    }
    const player = game.player;
    const lookX = game.mouse.inside ? clamp((game.mouse.x - view.width / 2) * 0.08, -55, 55) : 0;
    const lookY = game.mouse.inside ? clamp((game.mouse.y - view.height / 2) * 0.045, -26, 26) : 0;
    const targetX = player.x * CONFIG.tileSize - view.width / 2 + lookX;
    const targetY = player.y * CONFIG.tileSize - view.height * 0.62 + lookY;
    const maxX = Math.max(0, game.world.width * CONFIG.tileSize - view.width);
    const maxY = Math.max(0, game.world.height * CONFIG.tileSize - view.height);
    const clampedX = clamp(targetX, 0, maxX);
    const clampedY = clamp(targetY, 0, maxY);
    if (snap) {
      game.camera.x = clampedX;
      game.camera.y = clampedY;
      return;
    }
    const ease = 1 - Math.exp(-dt * 8.5);
    game.camera.x += (clampedX - game.camera.x) * ease;
    game.camera.y += (clampedY - game.camera.y) * ease;
  }

  function clampCamera() {
    if (!game) {
      return;
    }
    game.camera.x = clamp(
      game.camera.x,
      0,
      Math.max(0, game.world.width * CONFIG.tileSize - view.width)
    );
    game.camera.y = clamp(
      game.camera.y,
      0,
      Math.max(0, game.world.height * CONFIG.tileSize - view.height)
    );
  }

  function tileInReach(tx, ty) {
    const player = game.player;
    const centerX = tx + 0.5;
    const centerY = ty + 0.5;
    const dx = centerX - player.x;
    const dy = centerY - (player.y - player.height * 0.5);
    return dx * dx + dy * dy <= CONFIG.reach * CONFIG.reach;
  }

  function playerOverlapsCell(tx, ty) {
    const player = game.player;
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return tx + 1 > left && tx < right && ty + 1 > top && ty < bottom;
  }

  function hasAdjacentSolid(tx, ty) {
    return WORLD.isSolid(game.world, tx, ty + 1)
      || WORLD.isSolid(game.world, tx, ty - 1)
      || WORLD.isSolid(game.world, tx - 1, ty)
      || WORLD.isSolid(game.world, tx + 1, ty);
  }

  function selectedPlaceable() {
    const key = INV.getSelectedKey(game.state);
    if (!key) {
      return null;
    }
    const item = CONTENT.ITEMS[key];
    if (!item || item.kind !== "block" || INV.countItem(game.state, key) <= 0) {
      return null;
    }
    return { key, item, def: CONTENT.getBlockDef(item.block), count: INV.countItem(game.state, key) };
  }

  function validatePlacement(tx, ty, placeable) {
    if (!placeable) {
      return { valid: false, reason: "unavailable" };
    }
    if (tx < 0 || ty < 0 || tx >= game.world.width || ty >= game.world.height) {
      return { valid: false, reason: "outside" };
    }
    if (WORLD.getBlock(game.world, tx, ty) !== CONFIG.block.AIR) {
      return { valid: false, reason: "occupied" };
    }
    if (!tileInReach(tx, ty)) {
      return { valid: false, reason: "reach" };
    }
    if (placeable.def.solid && playerOverlapsCell(tx, ty)) {
      return { valid: false, reason: "player" };
    }
    if (placeable.def.id === CONFIG.block.CAMPFIRE && !WORLD.isSolid(game.world, tx, ty + 1)) {
      return { valid: false, reason: "support" };
    }
    if (placeable.def.requiresSupport && !hasAdjacentSolid(tx, ty)) {
      return { valid: false, reason: "support" };
    }
    return { valid: true, reason: "ok" };
  }

  function makePlacement(tx, ty, placeable) {
    const check = validatePlacement(tx, ty, placeable);
    return {
      x: tx,
      y: ty,
      itemKey: placeable.key,
      valid: check.valid,
      reason: check.reason
    };
  }

  function placementReasonLabel(reason) {
    if (reason === "support") {
      return "needs a nearby solid block";
    }
    if (reason === "player") {
      return "you are standing there";
    }
    if (reason === "occupied") {
      return "this spot is occupied";
    }
    if (reason === "reach") {
      return "too far away";
    }
    return "";
  }

  function toolRequirementText(breakInfo) {
    if (!breakInfo) {
      return "";
    }
    if (!breakInfo.ok) {
      if (breakInfo.reason === "unbreakable") {
        return "Unbreakable";
      }
      if (breakInfo.reason === "tool" || breakInfo.reason === "tier") {
        const tierName = breakInfo.neededTier >= 2 ? CONTENT.TIER_NAMES[breakInfo.neededTier] + " " : "";
        return "Needs a " + tierName + (breakInfo.neededTool || "tool");
      }
      return "Cannot mine";
    }
    if (breakInfo.effective) {
      return CONTENT.TIER_NAMES[breakInfo.toolTier] + " " + CONTENT.TOOL_TYPES[breakInfo.tool].name + " · LMB mine";
    }
    return "LMB mine";
  }

  function findEnemyAt(worldX, worldY) {
    let found = null;
    let best = Infinity;
    for (let i = 0; i < game.enemies.length; i += 1) {
      const enemy = game.enemies[i];
      if (enemy.dead || enemy.dying > 0) {
        continue;
      }
      const left = enemy.x - enemy.width / 2 - 0.2;
      const right = enemy.x + enemy.width / 2 + 0.2;
      const top = enemy.y - enemy.height - 0.2;
      const bottom = enemy.y + 0.15;
      if (worldX < left || worldX > right || worldY < top || worldY > bottom) {
        continue;
      }
      const player = game.player;
      const dx = enemy.x - player.x;
      const dy = (enemy.y - enemy.height * 0.5) - (player.y - player.height * 0.5);
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance <= 3.2 && distance < best) {
        best = distance;
        found = enemy;
      }
    }
    return found;
  }

  function updateHover() {
    if (!game || game.mode !== "playing" || !game.mouse.inside) {
      if (game) {
        game.hover = null;
      }
      UI.updateTargetTooltip(null);
      return;
    }
    const worldX = (game.mouse.x + game.camera.x) / CONFIG.tileSize;
    const worldY = (game.mouse.y + game.camera.y) / CONFIG.tileSize;
    const tx = Math.floor(worldX);
    const ty = Math.floor(worldY);
    if (tx < 0 || ty < 0 || tx >= game.world.width || ty >= game.world.height) {
      game.hover = null;
      UI.updateTargetTooltip(null);
      return;
    }

    const blockId = WORLD.getBlock(game.world, tx, ty);
    const def = CONTENT.getBlockDef(blockId);
    const selectedKey = INV.getSelectedKey(game.state);
    const placeable = selectedPlaceable();
    const inReach = tileInReach(tx, ty);
    const enemy = findEnemyAt(worldX, worldY);

    let breakInfo = null;
    if (blockId !== CONFIG.block.AIR) {
      breakInfo = INV.getBreakInfo(game.state, blockId, selectedKey);
    }

    let placement = null;
    if (placeable) {
      let targetX = tx;
      let targetY = ty;
      if (blockId !== CONFIG.block.AIR) {
        targetY -= 1;
      }
      if (targetY >= 0 && targetY < game.world.height
        && WORLD.getBlock(game.world, targetX, targetY) === CONFIG.block.AIR) {
        placement = makePlacement(targetX, targetY, placeable);
        if (!tileInReach(targetX, targetY)) {
          placement = null;
        }
      }
    }

    const matchingMine = game.miningTarget
      && game.miningTarget.x === tx
      && game.miningTarget.y === ty;
    const progress = matchingMine ? game.miningProgress : 0;
    let tip = null;

    if (enemy) {
      tip = { label: "Hollow", hint: "LMB strike" };
    } else if (blockId !== CONFIG.block.AIR && inReach) {
      const hint = toolRequirementText(breakInfo);
      tip = {
        label: def.name,
        hint: hint
      };
    } else if (placement) {
      tip = placement.valid
        ? { label: "Place " + placeable.item.name, hint: "RMB place" }
        : { label: "Cannot place " + placeable.item.name, hint: placementReasonLabel(placement.reason) };
    }

    game.hover = {
      tx,
      ty,
      worldX,
      worldY,
      blockId,
      inReach,
      highlight: blockId !== CONFIG.block.AIR && inReach,
      validMine: breakInfo ? breakInfo.ok : true,
      progress,
      placement,
      enemy,
      mining: false,
      tip
    };
    UI.updateTargetTooltip(game.hover);
  }

  function addParticle(options) {
    if (game.particles.length > 500) {
      game.particles.shift();
    }
    game.particles.push(options);
  }

  function puffParticles(x, y, colors, count, power) {
    const palette = colors && colors.length ? colors : ["#b7a680", "#7a6e58"];
    const amount = count || 8;
    for (let i = 0; i < amount; i += 1) {
      addParticle({
        x,
        y,
        vx: (Math.random() - 0.5) * (power || 4),
        vy: -Math.random() * 3 - 0.6,
        life: 0.45 + Math.random() * 0.5,
        maxLife: 0.95,
        gravity: 9 + Math.random() * 5,
        color: palette[Math.floor(Math.random() * palette.length)],
        size: 2 + Math.floor(Math.random() * 3),
        kind: "block"
      });
    }
  }

  function addFloater(x, y, text, color) {
    if (game.floaters.length > 30) {
      game.floaters.shift();
    }
    game.floaters.push({
      x,
      y,
      text,
      color: color || "#f2e8cd",
      life: 1.35,
      maxLife: 1.35
    });
  }

  function warnMining(breakInfo) {
    const now = game.state.playSeconds;
    if (now - game.lastWarningAt < 1.8) {
      return;
    }
    let message = "";
    if (breakInfo && breakInfo.reason === "tool") {
      const tierName = breakInfo.neededTier >= 2 ? CONTENT.TIER_NAMES[breakInfo.neededTier] + " " : "";
      message = "That needs a " + tierName + (breakInfo.neededTool || "tool") + ". Select one on the hotbar.";
    } else if (breakInfo && breakInfo.reason === "tier") {
      message = "That is too hard for this tool. A " + CONTENT.TIER_NAMES[breakInfo.neededTier].toLowerCase()
        + " " + breakInfo.neededTool + " would do it.";
    } else if (breakInfo && breakInfo.reason === "unbreakable") {
      message = "That block is not going anywhere.";
    }
    if (message) {
      game.lastWarningAt = now;
      UI.showToast(message, "warn", 2400);
    }
  }

  function detachUnsupported(tx, ty) {
    const directions = [[0, -1], [0, 1], [-1, 0], [1, 0]];
    let detached = 0;
    directions.forEach(function (offset) {
      const nx = tx + offset[0];
      const ny = ty + offset[1];
      const block = WORLD.getBlock(game.world, nx, ny);
      const def = CONTENT.getBlockDef(block);
      if (!def || !def.requiresSupport || hasAdjacentSolid(nx, ny)) {
        return;
      }
      WORLD.setBlock(game.world, nx, ny, CONFIG.block.AIR);
      const drops = CONTENT.rollDrops(block, Math.random);
      drops.forEach(function (drop) {
        INV.addItem(game.state, drop.item, drop.count);
        const itemDef = CONTENT.ITEMS[drop.item];
        if (itemDef) {
          addFloater(nx + 0.5, ny + 0.25, "+" + drop.count + " " + itemDef.name, "#d8d0b0");
        }
      });
      puffParticles(nx + 0.5, ny + 0.5, def.particle, 5, 2.4);
      AUDIO.play("break", def.sound);
      detached += 1;
    });
    if (detached > 0) {
      UI.refreshHotbar();
    }
    return detached;
  }

  function breakBlock(tx, ty, breakInfo) {
    const blockId = WORLD.getBlock(game.world, tx, ty);
    const def = CONTENT.getBlockDef(blockId);
    if (!def || blockId === CONFIG.block.AIR || def.unbreakable) {
      return false;
    }
    const beforeInfo = INV.getQuestInfo(game.state);
    const beforeDone = beforeInfo.doneCount;
    const drops = CONTENT.rollDrops(blockId, Math.random);
    WORLD.setBlock(game.world, tx, ty, CONFIG.block.AIR);
    game.state.stats.blocksMined += 1;
    if (blockId === CONFIG.block.STONE) {
      game.state.stats.stoneMined += 1;
    }

    let label = "";
    drops.forEach(function (drop) {
      INV.addItem(game.state, drop.item, drop.count);
      if (drop.item === "log") {
        game.state.stats.logsGathered += drop.count;
      }
      if (drop.item === "coal") {
        game.state.stats.coalFound += drop.count;
      }
      if (drop.item === "iron") {
        game.state.stats.ironFound += drop.count;
      }
      const itemDef = CONTENT.ITEMS[drop.item];
      label = "+" + drop.count + " " + (itemDef ? itemDef.name : drop.item);
    });

    puffParticles(tx + 0.5, ty + 0.5, def.particle, 11, 4.4);
    if (label) {
      addFloater(tx + 0.5, ty + 0.15, label, "#f6e9c9");
    }
    game.shake = Math.max(game.shake, blockId === CONFIG.block.STONE ? 2.2 : 1.2);
    AUDIO.play("break", def.sound);
    AUDIO.play("pickup");
    game.miningProgress = 0;
    game.miningTarget = null;
    detachUnsupported(tx, ty);

    if (breakInfo.effective && breakInfo.tool) {
      const used = INV.useTool(game.state, breakInfo.tool, 1);
      if (used.broken) {
        UI.showToast("Your " + used.toolName + " broke. The wild asks for another.", "warn", 3600);
      }
      UI.refreshHotbar();
    }

    const poppedIn = game.state.flags && game.state.flags.lanternPlaced;
    void poppedIn;
    updateNearWorkbench(true);
    maybeHandleQuest(beforeDone);
    UI.refreshHotbar();
    UI.refreshQuest();
    if (game.mode === "inventory") {
      UI.refreshInventory();
    }
    return true;
  }

  function isSameMiningTarget(tx, ty) {
    return game.miningTarget && game.miningTarget.x === tx && game.miningTarget.y === ty;
  }

  function startMining(hover) {
    const target = { x: hover.tx, y: hover.ty };
    if (!isSameMiningTarget(target.x, target.y)) {
      game.miningTarget = target;
      game.miningProgress = 0;
    }
    hover.mining = true;
  }

  function attackWithWeapon() {
    if (!game.hover || !game.hover.enemy || game.attackCooldown > 0) {
      return false;
    }
    const enemy = game.hover.enemy;
    const player = game.player;
    const attack = INV.getAttackInfo(game.state);
    game.attackCooldown = attack.tool === "sword" ? 0.34 : 0.42;
    game.player.swing = 0.24;
    game.player.facing = enemy.x >= player.x ? 1 : -1;
    const dx = enemy.x - player.x;
    const dy = enemy.y - enemy.height * 0.5 - (player.y - player.height * 0.5);
    const length = Math.max(0.001, Math.sqrt(dx * dx + dy * dy));
    enemy.vx = (dx / length) * 4.3;
    enemy.vy = -3.1;
    enemy.hurtTimer = 0.28;
    enemy.health = Math.max(0, enemy.health - attack.damage);
    game.shake = Math.max(game.shake, 3.2);
    addFloater(enemy.x, enemy.y - enemy.height - 0.15, "-" + (Number.isInteger(attack.damage) ? attack.damage : attack.damage.toFixed(1)), "#f1b087");
    puffParticles(enemy.x, enemy.y - enemy.height * 0.6, ["#899f8b", "#31384c", "#d4d9ba"], 7, 3);
    AUDIO.play("swing");
    AUDIO.play("hit");
    if (enemy.health <= 0) {
      enemy.dying = 0.6;
      game.state.stats.hollowsDefeated += 1;
      puffParticles(enemy.x, enemy.y - enemy.height * 0.6, ["#4d566c", "#232839", "#b9e1b4"], 16, 5);
    }
    if (attack.tool === "sword") {
      const used = INV.useTool(game.state, "sword", 1);
      if (used.broken) {
        UI.showToast("Your " + used.toolName + " gave out in the dark.", "warn", 3200);
      }
      UI.refreshHotbar();
    }
    return true;
  }

  function attemptPlacement(showFeedback) {
    if (!game || game.mode !== "playing") {
      return false;
    }
    if (game.placeCooldown > 0) {
      return false;
    }
    const placeable = selectedPlaceable();
    if (!placeable || !game.hover || !game.hover.placement) {
      if (showFeedback && placeable && game.hover) {
        const reason = game.hover.placement ? game.hover.placement.reason : "";
        if (reason) {
          UI.showToast("Cannot place " + placeable.item.name + ": " + placementReasonLabel(reason) + ".", "warn", 2200);
        }
      }
      return false;
    }
    const placement = game.hover.placement;
    if (!placement.valid) {
      if (showFeedback) {
        UI.showToast("Cannot place " + placeable.item.name + ": " + placementReasonLabel(placement.reason) + ".", "warn", 2200);
      }
      return false;
    }
    if (INV.countItem(game.state, placeable.key) <= 0) {
      return false;
    }
    const beforeDone = INV.getQuestInfo(game.state).doneCount;
    const placed = WORLD.setBlock(game.world, placement.x, placement.y, placeable.def.id);
    if (!placed) {
      return false;
    }
    INV.removeItem(game.state, placeable.key, 1);
    game.state.stats.blocksPlaced += 1;
    game.placeCooldown = 0.21;
    puffParticles(placement.x + 0.5, placement.y + 0.8, placeable.def.particle, 5, 2.5);
    AUDIO.play("place");
    UI.refreshHotbar();

    if (placeable.def.id === CONFIG.block.WORKBENCH && !game.state.flags.workbenchPlaced) {
      game.state.flags.workbenchPlaced = true;
      UI.showToast("Workbench placed. Stand near it to craft tools.", "info", 3200);
    }
    if (placeable.def.id === CONFIG.block.LANTERN) {
      if (!game.state.flags.lanternCrafted) {
        game.state.flags.lanternCrafted = true;
      }
      if (!game.state.flags.lanternPlaced) {
        game.state.flags.lanternPlaced = true;
        UI.showToast("The Warden's Lantern is lit.", "quest", 3800);
        AUDIO.play("lantern");
        game.enemies.forEach(function (enemy) {
          enemy.dying = 0.8;
        });
      }
    }
    updateNearWorkbench(true);
    maybeHandleQuest(beforeDone);
    UI.refreshQuest();
    updateHover();
    return true;
  }

  function scheduleCompletionIfReady(info) {
    if (!game) {
      return;
    }
    const quest = info || INV.getQuestInfo(game.state);
    if (quest.allDone
      && game.state.flags.lanternPlaced
      && !game.state.flags.celebrationSeen
      && !game.victoryShown
      && game.pendingCelebration <= 0) {
      game.pendingCelebration = 1.35;
    }
  }

  function maybeHandleQuest(beforeDone) {
    if (!game) {
      return;
    }
    const info = INV.getQuestInfo(game.state);
    if (info.doneCount > beforeDone) {
      if (info.allDone) {
        game.state.flags.celebrationSeen = false;
      } else if (info.currentStep) {
        UI.showToast("Field note updated: " + info.currentStep.title, "quest", 3400);
        AUDIO.play("quest");
      }
      UI.refreshQuest(true);
    } else {
      UI.refreshQuest();
    }
    scheduleCompletionIfReady(info);
  }

  function updateNearWorkbench(force) {
    if (!game) {
      return;
    }
    const player = game.player;
    const px = Math.floor(player.x);
    const py = Math.floor(player.y - player.height * 0.45);
    let found = false;
    const radius = 6;
    for (let y = py - radius; y <= py + radius && !found; y += 1) {
      for (let x = px - radius; x <= px + radius; x += 1) {
        if (x < 0 || y < 0 || x >= game.world.width || y >= game.world.height) {
          continue;
        }
        const block = WORLD.getBlock(game.world, x, y);
        if (block === CONFIG.block.WORKBENCH) {
          const dx = x + 0.5 - player.x;
          const dy = y + 0.5 - (player.y - player.height * 0.5);
          if (dx * dx + dy * dy <= (radius + 0.5) * (radius + 0.5)) {
            found = true;
            break;
          }
        }
      }
    }
    if (force || found !== game.nearWorkbench) {
      game.nearWorkbench = found;
      if (game.mode === "inventory") {
        UI.refreshInventory();
      }
    }
  }

  function hurtHooks() {
    return {
      onJump: function () {
        AUDIO.play("jump");
      },
      onLand: function (fallDistance) {
        if (fallDistance > 1.2) {
          puffParticles(game.player.x, game.player.y, ["#9d8a67", "#756749"], Math.min(12, 3 + Math.floor(fallDistance)), 2.4);
          AUDIO.play("land");
        }
        if (fallDistance > 3.5) {
          game.shake = Math.max(game.shake, Math.min(7, fallDistance * 0.6));
        }
      },
      onStep: function () {
        AUDIO.play("step");
        if (Math.random() < 0.25) {
          addParticle({
            x: game.player.x + (Math.random() - 0.5) * 0.4,
            y: game.player.y - 0.05,
            vx: (Math.random() - 0.5) * 0.8,
            vy: -0.5 - Math.random(),
            life: 0.35,
            maxLife: 0.35,
            gravity: 1.5,
            color: "#cabd9d",
            size: 2,
            kind: "block"
          });
        }
      },
      onHurt: function (amount) {
        game.shake = Math.max(game.shake, 8);
        UI.flashDamage();
        UI.refreshVitals();
        AUDIO.play("hurt");
        addParticle({
          x: game.player.x,
          y: game.player.y - game.player.height * 0.6,
          vx: 0,
          vy: -1,
          life: 0.35,
          maxLife: 0.35,
          gravity: 0,
          color: "#d6785f",
          size: 3,
          kind: "spark"
        });
        if (game.player.health <= 0) {
          triggerDeath();
        }
        void amount;
      },
      onHeal: function () {
        UI.refreshVitals();
      }
    };
  }

  function triggerDeath() {
    if (!game || game.mode === "dead" || game.mode === "done") {
      return;
    }
    game.state.stats.deaths += 1;
    setMode("dead");
    AUDIO.play("death");
    saveGame(false, true);
    UI.refreshVitals();
  }

  function updateEnemies(dt) {
    const player = game.player;
    const day = game.dayInfo;
    const hollow = CONTENT.HOLLOW;

    game.enemies.forEach(function (enemy) {
      if (enemy.dead) {
        return;
      }
      if (enemy.dying > 0) {
        enemy.dying -= dt * 1.7;
        if (enemy.dying <= 0) {
          enemy.dead = true;
        }
        return;
      }
      if (day.daylight > 0.3) {
        enemy.dying = 0.9;
        return;
      }
      enemy.hurtTimer = Math.max(0, enemy.hurtTimer - dt);
      enemy.attackCooldown = Math.max(0, enemy.attackCooldown - dt);
      const dx = player.x - enemy.x;
      const dy = player.y - enemy.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance > 34) {
        enemy.dead = true;
        return;
      }

      let desired = 0;
      if (Math.abs(dx) < hollow.detectRange && Math.abs(dy) < 11) {
        enemy.facing = dx >= 0 ? 1 : -1;
        if (Math.abs(dx) > 0.95) {
          desired = Math.sign(dx) * hollow.speed;
        }
        if (enemy.onGround && (Math.abs(dx) < 1.7 || player.y < enemy.y - 1.1)) {
          if (Math.abs(dx) < 1.7 && Math.abs(dy) > 0.9 && Math.random() < 0.05) {
            enemy.vy = -8.8;
          }
        }
      } else {
        desired = 0;
      }

      if (enemy.vx < desired) {
        enemy.vx = Math.min(desired, enemy.vx + 18 * dt);
      } else if (enemy.vx > desired) {
        enemy.vx = Math.max(desired, enemy.vx - 18 * dt);
      }
      if (enemy.knockDecay > 0) {
        enemy.knockDecay -= dt;
      } else if (Math.sign(enemy.vx) !== Math.sign(desired) && desired !== 0) {
        enemy.vx *= 0.9;
      }

      const wasOnGround = enemy.onGround;
      const moved = PLAYER.moveHorizontal(enemy, game.world, enemy.vx * dt);
      if (!moved && wasOnGround && desired !== 0) {
        enemy.vy = -8.7;
      }
      enemy.vy = Math.min(18, enemy.vy + CONFIG.player.gravity * dt);
      const verticalHit = PLAYER.moveVertical(enemy, game.world, enemy.vy * dt);
      enemy.onGround = verticalHit > 0;
      if (!enemy.onGround) {
        enemy.airTime = (enemy.airTime || 0) + dt;
      } else {
        enemy.airTime = 0;
      }

      const horizontalDistance = Math.abs(enemy.x - player.x);
      const enemyTouchesPlayer = horizontalDistance < (enemy.width + player.width) / 2 + 0.08
        && enemy.y > player.y - player.height - 0.1
        && enemy.y - enemy.height < player.y + 0.05;
      if (enemyTouchesPlayer && enemy.attackCooldown <= 0) {
        const hurt = PLAYER.damagePlayer(player, hollow.damage, hurtHooks());
        if (hurt) {
          enemy.attackCooldown = 1.1;
          const push = player.x >= enemy.x ? 1 : -1;
          player.vx = push * 5.8;
          player.vy = -4.2;
          enemy.vx = -push * 1.8;
          enemy.knockDecay = 0.3;
          game.shake = Math.max(game.shake, 7);
        }
      }
    });

    game.enemies = game.enemies.filter(function (enemy) {
      return !enemy.dead;
    });

    if (day.daylight >= 0.28) {
      game.enemies.forEach(function (enemy) {
        if (enemy.dying <= 0) {
          enemy.dying = 0.9;
        }
      });
    }

    const playerSurface = game.world.surface[clamp(Math.floor(player.x), 0, game.world.width - 1)];
    const playerNearSurface = Math.abs(player.y - playerSurface) < 5;
    const aliveCount = game.enemies.filter(function (enemy) { return !enemy.dead && enemy.dying <= 0; }).length;
    if (!day.isNight) {
      game.enemySpawnTimer = 4;
    }
    if (!day.isNight || !playerNearSurface || aliveCount >= hollow.spawnCap || game.state.flags.lanternPlaced) {
      return;
    }
    game.enemySpawnTimer = (game.enemySpawnTimer || 0) - dt;
    if (game.enemySpawnTimer > 0) {
      return;
    }
    game.enemySpawnTimer = 4.5 + Math.random() * 5.5;
    spawnHollow();
  }

  function hasLightNear(tx, ty, radius) {
    for (let y = ty - radius; y <= ty + radius; y += 1) {
      for (let x = tx - radius; x <= tx + radius; x += 1) {
        if (x < 0 || y < 0 || x >= game.world.width || y >= game.world.height) {
          continue;
        }
        const def = CONTENT.getBlockDef(WORLD.getBlock(game.world, x, y));
        if (def.light) {
          return true;
        }
      }
    }
    return false;
  }

  function spawnHollow() {
    const player = game.player;
    const playerColumn = clamp(Math.floor(player.x), 0, game.world.width - 1);
    const direction = Math.random() < 0.5 ? -1 : 1;
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const distance = 10 + Math.floor(Math.random() * 9);
      const x = Math.floor(player.x) + direction * distance + (attempt % 2 === 0 ? 0 : direction * 2);
      if (x < 3 || x >= game.world.width - 3) {
        continue;
      }
      const surface = game.world.surface[x];
      if (Math.abs(surface - game.world.surface[playerColumn]) > 8) {
        continue;
      }
      const ground = WORLD.getBlock(game.world, x, surface);
      if (!CONTENT.getBlockDef(ground).solid) {
        continue;
      }
      if (WORLD.getBlock(game.world, x, surface - 1) !== CONFIG.block.AIR
        || WORLD.getBlock(game.world, x, surface - 2) !== CONFIG.block.AIR) {
        continue;
      }
      if (hasLightNear(x, surface - 1, 6)) {
        continue;
      }
      const enemy = {
        x: x + 0.5,
        y: surface,
        vx: 0,
        vy: 0,
        width: CONTENT.HOLLOW.width,
        height: CONTENT.HOLLOW.height,
        health: CONTENT.HOLLOW.health,
        maxHealth: CONTENT.HOLLOW.health,
        facing: direction * -1,
        onGround: false,
        airTime: 0,
        attackCooldown: 0.9,
        hurtTimer: 0,
        dying: 0,
        dead: false,
        bobSeed: Math.random() * 10,
        knockDecay: 0
      };
      game.enemies.push(enemy);
      AUDIO.play("hollow");
      return true;
    }
    return false;
  }

  function updateMiners(dt) {
    game.attackCooldown = Math.max(0, game.attackCooldown - dt);
    game.placeCooldown = Math.max(0, game.placeCooldown - dt);
    game.shake = Math.max(0, game.shake - dt * 22);

    if (!game.mouse.inside) {
      game.miningProgress = 0;
      game.miningTarget = null;
      return;
    }
    updateHover();
    if (!game.hover) {
      game.miningProgress = 0;
      game.miningTarget = null;
      return;
    }

    if (game.mouse.left) {
      if (game.hover.enemy) {
        game.hover.mining = false;
        game.miningProgress = 0;
        game.miningTarget = null;
        attackWithWeapon();
      } else if (game.hover.blockId !== CONFIG.block.AIR && game.hover.inReach) {
        const breakInfo = INV.getBreakInfo(
          game.state,
          game.hover.blockId,
          INV.getSelectedKey(game.state)
        );
        if (breakInfo.ok) {
          startMining(game.hover);
          if (!game.hover.mining || !isSameMiningTarget(game.hover.tx, game.hover.ty)) {
            game.hover.mining = true;
          }
          game.miningProgress += dt / breakInfo.duration;
          game.mineSoundTimer -= dt;
          if (game.mineSoundTimer <= 0) {
            game.mineSoundTimer = 0.2;
            AUDIO.play("mine", breakInfo.def.sound);
            addParticle({
              x: game.hover.tx + 0.5 + (Math.random() - 0.5) * 0.5,
              y: game.hover.ty + 0.7,
              vx: (Math.random() - 0.5) * 1.3,
              vy: -1.5 - Math.random(),
              life: 0.3,
              maxLife: 0.3,
              gravity: 3,
              color: breakInfo.def.particle[0],
              size: 2,
              kind: "block"
            });
          }
          if (game.miningProgress >= 1) {
            breakBlock(game.hover.tx, game.hover.ty, breakInfo);
            updateHover();
          }
        } else {
          game.miningProgress = 0;
          game.miningTarget = null;
          warnMining(breakInfo);
        }
      } else {
        game.miningProgress = 0;
        game.miningTarget = null;
      }
      game.hover.progress = isSameMiningTarget(game.hover.tx, game.hover.ty)
        ? Math.min(1, game.miningProgress)
        : 0;
      game.hover.mining = Boolean(game.mouse.left && game.miningTarget);
    } else {
      game.miningProgress = 0;
      game.miningTarget = null;
      if (game.hover) {
        game.hover.progress = 0;
        game.hover.mining = false;
      }
    }

    if (game.mouse.right) {
      if (game.placeCooldown <= 0) {
        attemptPlacement(false);
        game.placeCooldown = 0.22;
      }
    }
  }

  function update(dt) {
    if (!game || game.mode !== "playing") {
      return;
    }
    const state = game.state;
    state.worldTime += dt;
    state.playSeconds += dt;
    state.stats.playSeconds = state.playSeconds;
    game.elapsed += dt;
    if (!state.flags.introDismissed) {
      game.tutorialAge = (game.tutorialAge || 0) + dt;
      if (game.tutorialAge > 26) {
        state.flags.introDismissed = true;
        UI.refreshTutorial();
      }
    }
    game.dayInfo = TIME.getDayInfo(state.worldTime, CONFIG.daySeconds);
    if (game.dayInfo.isNight !== game.wasNight) {
      if (game.dayInfo.isNight) {
        UI.showToast("Night settles. Hollows wake in the dark. Find a light.", "warn", 3800);
        AUDIO.play("hollow");
      } else {
        UI.showToast("Dawn breaks. The hollows fade back into the dark.", "info", 3400);
      }
      game.wasNight = game.dayInfo.isNight;
    }

    const jumpHeld = JUMP_KEYS.some(function (code) { return game.keys.has(code); });
    const input = {
      left: game.keys.has("KeyA") || game.keys.has("ArrowLeft"),
      right: game.keys.has("KeyD") || game.keys.has("ArrowRight"),
      jumpHeld,
      jumpPressed: game.jumpQueued,
      sprint: game.keys.has("ShiftLeft") || game.keys.has("ShiftRight"),
      aimFacing: game.mouse.inside
        ? (game.mouse.x + game.camera.x) / CONFIG.tileSize < game.player.x ? -1 : 1
        : 0
    };
    game.jumpQueued = false;

    const wasX = game.player.x;
    PLAYER.updatePlayer(game.player, game.world, input, dt, hurtHooks());
    if (game.mode !== "playing") {
      return;
    }
    const dx = game.player.x - wasX;
    if (Math.abs(dx) > 0) {
      state.stats.distanceWalked += Math.abs(dx);
    }
    updateCamera(dt, false);
    updateNearWorkbench(false);
    updateEnemies(dt);
    if (game.mode !== "playing") {
      return;
    }
    updateMiners(dt);

    game.particles.forEach(function (particle) {
      particle.life -= dt;
      particle.vy += (particle.gravity || 0) * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
    });
    game.particles = game.particles.filter(function (particle) {
      return particle.life > 0;
    });
    game.floaters.forEach(function (floater) {
      floater.life -= dt;
      floater.y -= dt * 0.65;
    });
    game.floaters = game.floaters.filter(function (floater) {
      return floater.life > 0;
    });

    if (game.pendingCelebration > 0) {
      game.pendingCelebration -= dt;
      if (game.pendingCelebration <= 0 && game.player.health > 0) {
        game.pendingCelebration = 0;
        game.victoryShown = true;
        game.state.flags.celebrationSeen = true;
        setMode("done");
        AUDIO.play("quest");
        saveGame(false, true);
      }
    }

    if (game.player.health <= 0 && game.mode === "playing") {
      triggerDeath();
    }
  }

  function refreshAfterGameplay() {
    if (!game) {
      return;
    }
    const healthSignature = Math.round(game.player.health * 4);
    if (healthSignature !== lastHealthSignature) {
      lastHealthSignature = healthSignature;
      UI.refreshVitals();
    }
  }

  function renderFrame() {
    if (!game) {
      return;
    }
    game.view = view;
    RENDER.render(ctx, game, view);
  }

  function loop(timestamp) {
    if (!running) {
      return;
    }
    window.requestAnimationFrame(loop);
    if (!game) {
      return;
    }
    const realSeconds = Math.min(0.05, Math.max(0, (timestamp - lastFrame) / 1000));
    lastFrame = timestamp;

    if (game.mode === "playing") {
      accumulator += realSeconds;
      let iterations = 0;
      while (accumulator >= STEP && iterations < 4 && game.mode === "playing") {
        update(STEP);
        accumulator -= STEP;
        iterations += 1;
      }
      if (iterations >= 4) {
        accumulator = 0;
      }
      game.autosaveTimer += realSeconds;
      if (game.autosaveTimer >= CONFIG.autoSaveSeconds) {
        game.autosaveTimer = 0;
        saveGame(false, true);
      }
      AUDIO.update(game.dayInfo, game.mode);
      refreshAfterGameplay();
    } else {
      accumulator = 0;
    }

    renderFrame();

    uiTimer += realSeconds;
    if (uiTimer >= 0.2) {
      uiTimer = 0;
      UI.refreshClock();
      UI.updateTargetTooltip(game.mode === "playing" ? game.hover : null);
    }
  }

  function chooseSeed() {
    return randomSeed();
  }

  function startNewWorld(seedOverride) {
    if (!game) {
      return;
    }
    const seed = Number.isFinite(Number(seedOverride)) ? Number(seedOverride) >>> 0 : chooseSeed();
    const preservedSound = game.state.soundOn;
    const run = makeFreshRun(seed, preservedSound);
    closeAllForReset();
    installRun(run, { storageAvailable: game.storageAvailable, preserveSound: true });
    setMode("playing");
    refreshAllUI();
    updateCamera(0, true);
    updateHover();
    saveGame(false, true);
    UI.showToast("A new world. Seed " + String(seed).padStart(8, "0") + ".", "info", 3000);
    AUDIO.play("ui");
  }

  function closeAllForReset() {
    if (!game) {
      return;
    }
    clearControls();
    game.hover = null;
    game.enemies = [];
    game.particles = [];
    game.floaters = [];
    game.pendingCelebration = 0;
    UI.setMode("loading");
    clearTargetTooltip();
  }

  function clearTargetTooltip() {
    UI.updateTargetTooltip(null);
  }

  function pauseGame() {
    if (!game || game.mode !== "playing") {
      return;
    }
    saveGame(false, true);
    setMode("paused");
    AUDIO.play("ui");
  }

  function resumeGame() {
    if (!game || game.mode !== "paused") {
      return;
    }
    setMode("playing");
    lastFrame = performance.now();
    AUDIO.play("ui");
  }

  function openInventory() {
    if (!game || game.mode !== "playing") {
      return;
    }
    if (!game.state.flags.introDismissed) {
      game.state.flags.introDismissed = true;
      UI.refreshTutorial();
    }
    updateNearWorkbench(true);
    setMode("inventory");
    AUDIO.play("ui");
  }

  function openHelp(fromPause) {
    if (!game) {
      return;
    }
    if (game.mode === "help" || game.mode === "dead" || game.mode === "done") {
      return;
    }
    if (game.mode !== "playing" && game.mode !== "paused") {
      return;
    }
    if (game.mode === "playing" && !game.state.flags.introDismissed) {
      game.state.flags.introDismissed = true;
      UI.refreshTutorial();
    }
    game.overlayReturnMode = game.mode === "paused" || fromPause ? "paused" : "playing";
    if (game.mode === "paused" || fromPause) {
      saveGame(false, true);
    }
    setMode("help");
    AUDIO.play("ui");
  }

  function closeOverlay() {
    if (!game) {
      return;
    }
    if (game.mode === "inventory") {
      setMode("playing");
      lastFrame = performance.now();
      AUDIO.play("ui");
      return;
    }
    if (game.mode === "help") {
      const returnMode = game.overlayReturnMode || "playing";
      setMode(returnMode);
      lastFrame = performance.now();
      AUDIO.play("ui");
    }
  }

  function respawn() {
    if (!game || game.mode !== "dead") {
      return;
    }
    const spawn = findSafeRespawnPoint(game.world);
    PLAYER.resetPlayer(game.player, spawn);
    game.enemies = [];
    game.particles = [];
    game.floaters = [];
    game.player.invulnerable = 2.2;
    updateCamera(0, true);
    setMode("playing");
    lastFrame = performance.now();
    UI.refreshVitals();
    UI.refreshHotbar();
    UI.showToast("You wake at camp. The pack is safe.", "info", 2800);
    saveGame(false, true);
  }

  function continueAfterDone() {
    if (!game || game.mode !== "done") {
      return;
    }
    setMode("playing");
    lastFrame = performance.now();
    UI.showToast("The wild is yours. Build, dig, and wander.", "info", 3000);
  }

  function dismissTutorial() {
    if (!game) {
      return;
    }
    game.state.flags.introDismissed = true;
    UI.refreshTutorial();
    saveGame(false, true);
  }

  function selectSlot(index) {
    if (!game || (game.mode !== "playing" && game.mode !== "inventory")) {
      return;
    }
    INV.selectSlot(game.state, index);
    UI.refreshHotbar();
    if (game.mode === "inventory") {
      UI.refreshInventory();
    }
    AUDIO.play("ui");
  }

  function bindItemToHotbar(key) {
    if (!game || game.mode !== "inventory") {
      return;
    }
    const result = INV.bindItemToSlot(game.state, key);
    if (!result.ok) {
      UI.showToast("That item cannot be bound to the hotbar.", "warn", 1800);
      return;
    }
    UI.refreshHotbar();
    UI.refreshInventory();
    AUDIO.play("ui");
  }

  function craftItem(recipeId) {
    if (!game || game.mode !== "inventory") {
      return;
    }
    updateNearWorkbench(true);
    const beforeDone = INV.getQuestInfo(game.state).doneCount;
    const result = INV.craft(game.state, recipeId, game.nearWorkbench);
    if (!result.ok) {
      let reason = "You cannot craft that yet.";
      if (result.reason === "station") {
        reason = "Place a workbench nearby to unlock that recipe.";
      } else if (result.reason === "owned") {
        reason = "You already have a tool of that tier or better.";
      } else if (result.reason === "ingredients") {
        reason = "You need a few more materials.";
      }
      UI.showToast(reason, "warn", 2600);
      return;
    }
    const recipe = result.recipe;
    if (recipe.id === "workbench") {
      game.state.flags.workbenchCrafted = true;
    }
    if (recipe.output.kind === "tool" && recipe.output.tool === "pickaxe" && recipe.output.tier >= 2) {
      game.state.flags.stonePickaxeCrafted = true;
    }
    if (recipe.id === "lantern") {
      game.state.flags.lanternCrafted = true;
    }
    const outputName = recipe.output.kind === "tool"
      ? CONTENT.getToolName(recipe.output.tool, recipe.output.tier)
      : CONTENT.ITEMS[recipe.output.item].name;
    UI.showToast("Crafted " + outputName + ".", "info", 2000);
    AUDIO.play("craft");
    for (let i = 0; i < 9; i += 1) {
      addParticle({
        x: game.player.x + (Math.random() - 0.5) * 1.2,
        y: game.player.y - game.player.height + (Math.random() - 0.5) * 0.9,
        vx: (Math.random() - 0.5) * 1.5,
        vy: -1.5 - Math.random(),
        life: 0.5 + Math.random() * 0.4,
        maxLife: 0.9,
        gravity: -0.4,
        color: i % 3 === 0 ? "#f0d681" : "#bcd886",
        size: 2,
        kind: "glow"
      });
    }
    UI.refreshInventory();
    UI.refreshHotbar();
    maybeHandleQuest(beforeDone);
    saveGame(false, true);
  }

  function toggleSound() {
    if (!game) {
      return;
    }
    game.state.soundOn = !game.state.soundOn;
    AUDIO.setEnabled(game.state.soundOn);
    UI.refreshSound();
    if (game.state.soundOn) {
      AUDIO.play("ui");
      AUDIO.unlock();
    }
    saveGame(false, true);
  }

  function toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function () {
          UI.showToast("Fullscreen was not allowed by the browser.", "warn", 2200);
        });
      } else {
        UI.showToast("This browser does not support fullscreen.", "warn", 2200);
      }
    } catch (error) {
      UI.showToast("Fullscreen was not allowed by the browser.", "warn", 2200);
    }
    UI.updateFullscreenLabel();
  }

  function updateMouseFromEvent(event) {
    if (!game) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    game.mouse.x = clamp(event.clientX - rect.left, 0, rect.width);
    game.mouse.y = clamp(event.clientY - rect.top, 0, rect.height);
  }

  function onKeyDown(event) {
    if (!game) {
      return;
    }
    if (event.ctrlKey || event.metaKey) {
      if (event.code === "KeyS") {
        event.preventDefault();
        saveGame(true);
      }
      return;
    }
    if (event.repeat) {
      return;
    }
    if (event.code === "KeyM") {
      event.preventDefault();
      toggleSound();
      return;
    }
    if (event.code === "KeyF") {
      event.preventDefault();
      toggleFullscreen();
      return;
    }
    if (!audioGestureDone && game.state.soundOn) {
      audioGestureDone = true;
      AUDIO.unlock();
    }

    if (game.mode === "playing") {
      if (event.code === "Escape") {
        event.preventDefault();
        pauseGame();
        return;
      }
      if (event.code === "KeyE") {
        event.preventDefault();
        openInventory();
        return;
      }
      if (event.code === "KeyH") {
        event.preventDefault();
        openHelp(false);
        return;
      }
      if (event.code === "Digit1" || event.code === "Digit2" || event.code === "Digit3"
        || event.code === "Digit4" || event.code === "Digit5" || event.code === "Digit6"
        || event.code === "Digit7" || event.code === "Digit8" || event.code === "Digit9") {
        event.preventDefault();
        selectSlot(Number(event.code.slice(5)) - 1);
        return;
      }
      if (event.code.indexOf("Numpad") === 0 && event.code.length === 7) {
        const digit = Number(event.code.slice(6));
        if (digit >= 1 && digit <= 9) {
          event.preventDefault();
          selectSlot(digit - 1);
          return;
        }
      }
      if (MOVEMENT_LABELS[event.code] || event.code === "ShiftLeft" || event.code === "ShiftRight") {
        game.keys.add(event.code);
        if (event.code === "Space" || event.code === "ArrowUp" || event.code === "ArrowLeft" || event.code === "ArrowRight") {
          event.preventDefault();
        }
        return;
      }
      if (event.code === "Space" || event.code === "KeyW" || event.code === "ArrowUp") {
        event.preventDefault();
        game.keys.add(event.code);
        if (!event.repeat) {
          game.jumpQueued = true;
        }
        return;
      }
      return;
    }

    if (event.code === "Escape") {
      if (game.mode === "inventory" || game.mode === "help") {
        event.preventDefault();
        closeOverlay();
      } else if (game.mode === "paused") {
        event.preventDefault();
        resumeGame();
      } else if (game.mode === "dead") {
        event.preventDefault();
      } else if (game.mode === "done") {
        event.preventDefault();
      }
      return;
    }
    if (event.code === "KeyE" && game.mode === "inventory") {
      event.preventDefault();
      closeOverlay();
      return;
    }
    if (event.code === "KeyH" && game.mode === "help") {
      event.preventDefault();
      closeOverlay();
      return;
    }
    if (event.code === "KeyH" && game.mode === "paused") {
      event.preventDefault();
      openHelp(true);
      return;
    }
    if (event.code === "KeyR" && game.mode === "dead") {
      event.preventDefault();
      respawn();
    }
  }

  function onKeyUp(event) {
    if (!game) {
      return;
    }
    game.keys.delete(event.code);
  }

  function setupInput() {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", function () {
      if (game) {
        game.keys.clear();
        game.mouse.left = false;
        game.mouse.right = false;
      }
    });

    canvas.addEventListener("pointerenter", function () {
      if (!game) {
        return;
      }
      game.mouse.inside = true;
      if (game.state.soundOn) {
        AUDIO.unlock();
      }
      if (game.mode === "playing") {
        updateHover();
      }
      canvas.focus({ preventScroll: true });
    });
    canvas.addEventListener("pointerleave", function () {
      if (!game) {
        return;
      }
      game.mouse.inside = false;
      game.mouse.left = false;
      game.mouse.right = false;
      game.miningTarget = null;
      game.miningProgress = 0;
      game.hover = null;
      UI.updateTargetTooltip(null);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!game) {
        return;
      }
      updateMouseFromEvent(event);
      game.mouse.inside = true;
      if (game.mode === "playing") {
        updateHover();
      }
    });
    canvas.addEventListener("pointerdown", function (event) {
      if (!game || game.mode !== "playing") {
        return;
      }
      updateMouseFromEvent(event);
      game.mouse.inside = true;
      canvas.focus({ preventScroll: true });
      if (game.state.soundOn) {
        AUDIO.unlock();
      }
      if (event.button === 0) {
        event.preventDefault();
        game.mouse.left = true;
        game.player.swing = 0.24;
        updateHover();
        if (game.hover && game.hover.enemy) {
          attackWithWeapon();
        }
      } else if (event.button === 2) {
        event.preventDefault();
        game.mouse.right = true;
        game.placeCooldown = 0;
        updateHover();
        attemptPlacement(true);
      }
    });
    window.addEventListener("pointerup", function (event) {
      if (!game) {
        return;
      }
      if (event.button === 0) {
        game.mouse.left = false;
        game.miningProgress = 0;
        game.miningTarget = null;
      } else if (event.button === 2) {
        game.mouse.right = false;
      }
    });
    canvas.addEventListener("pointercancel", function () {
      if (!game) {
        return;
      }
      game.mouse.left = false;
      game.mouse.right = false;
      game.mouse.inside = false;
    });
    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });
    window.addEventListener("wheel", function (event) {
      if (!game || game.mode !== "playing") {
        return;
      }
      event.preventDefault();
      INV.cycleSlot(game.state, event.deltaY > 0 ? 1 : -1);
      UI.refreshHotbar();
      AUDIO.unlock();
    }, { passive: false });

    window.addEventListener("resize", function () {
      resizeCanvas();
    });
    document.addEventListener("visibilitychange", function () {
      if (!game) {
        return;
      }
      if (document.hidden) {
        if (game.mode === "playing") {
          pauseGame();
        } else {
          saveGame(false, true);
        }
      }
    });
    window.addEventListener("pagehide", function () {
      if (game) {
        saveGame(false, true);
      }
    });
    window.addEventListener("beforeunload", function () {
      if (game) {
        saveGame(false, true);
      }
    });
  }

  Object.assign(actions, {
    selectSlot: selectSlot,
    bindItem: bindItemToHotbar,
    craftItem: craftItem,
    openHelp: openHelp,
    closeOverlay: closeOverlay,
    resume: resumeGame,
    saveNow: function (manual) {
      return saveGame(manual !== false);
    },
    newWorld: function () {
      startNewWorld();
    },
    respawn: respawn,
    continueAfterDone: continueAfterDone,
    dismissTutorial: dismissTutorial,
    toggleSound: toggleSound,
    toggleFullscreen: toggleFullscreen
  });

  function showFatalError(error) {
    const message = error && error.message ? error.message : String(error);
    try {
      UI.showFatalError(message);
    } catch (uiError) {
      const fallback = document.getElementById("fatal-error");
      const copy = document.getElementById("fatal-error-copy");
      if (fallback) {
        fallback.hidden = false;
      }
      if (copy) {
        copy.textContent = message;
      }
      const status = document.getElementById("status");
      if (status) {
        status.dataset.state = "error";
      }
    }
    console.error(error);
  }

  function exposeDebugApi() {
    window.Mosswild = {
      version: CONFIG.version,
      get ready() {
        return Boolean(game && game.ready);
      },
      get game() {
        return game;
      },
      actions: actions,
      ui: UI,
      save: function () {
        return saveGame(true);
      },
      newWorld: function (seed) {
        startNewWorld(seed);
      },
      setTimeOfDay: function (hours) {
        if (!game) {
          return;
        }
        const cycle = CONFIG.daySeconds;
        const dayStart = Math.floor(game.state.worldTime / cycle) * cycle;
        const fraction = (((Number(hours) - 6) / 24) % 1 + 1) % 1;
        game.state.worldTime = dayStart + fraction * cycle;
        game.dayInfo = TIME.getDayInfo(game.state.worldTime, cycle);
        game.wasNight = game.dayInfo.isNight;
        UI.refreshClock();
      },
      teleport: function (x, y) {
        if (!game) {
          return;
        }
        game.player.x = Number(x);
        game.player.y = Number(y);
        game.player.vx = 0;
        game.player.vy = 0;
        updateCamera(0, true);
        updateHover();
      },
      getSaveText: function () {
        try {
          return window.localStorage.getItem(CONFIG.saveKey);
        } catch (error) {
          return null;
        }
      }
    };
    window.__MOSSWILD_READY__ = true;
  }

  function boot() {
    try {
      if (!ctx) {
        throw new Error("Canvas 2D is not available in this browser.");
      }
      resizeCanvas();
      RENDER.init();
      const read = readSavedWorld();
      let run;
      let warning = null;
      let storageAvailable = read.available;
      if (read.raw) {
        try {
          run = loadRun(read.raw);
        } catch (error) {
          warning = "The old save could not be read. A new world begins. (" + error.message + ")";
          run = makeFreshRun(chooseSeed(), true);
          storageAvailable = read.available;
        }
      } else {
        run = makeFreshRun(chooseSeed(), true);
      }
      game = makeGame(run, storageAvailable);
      game.storageAvailable = storageAvailable;
      updateCamera(0, true);
      updateNearWorkbench(true);
      if (!game.state.soundOn) {
        AUDIO.setEnabled(false);
      }

      UI.init(game, actions);
      setupInput();
      setMode("playing");
      refreshAllUI();
      scheduleCompletionIfReady();
      UI.setSaveState("ready", "World ready. Autosave is on.");
      if (!game.loadedFromSave) {
        game.lastSavedAt = 0;
        game.lastSavedLabel = "Autosave on · every 10s";
        saveGame(false, true);
      } else {
        UI.setSaveStatus(game.lastSavedLabel, "World loaded from local save.");
      }
      if (warning) {
        window.setTimeout(function () {
          UI.showToast(warning, "warn", 6000);
        }, 500);
      }
      if (!storageAvailable) {
        UI.setSaveStatus("Saving unavailable", "Local browser storage is blocked.");
      }
      lastFrame = performance.now();
      running = true;
      booted = true;
      window.requestAnimationFrame(loop);
      exposeDebugApi();
    } catch (error) {
      showFatalError(error);
    }
  }

  window.addEventListener("error", function (event) {
    if (!booted) {
      showFatalError(event.error || new Error(event.message || "Unknown error"));
    }
  });
  window.addEventListener("unhandledrejection", function (event) {
    if (!booted) {
      showFatalError(event.reason || new Error("Unhandled promise rejection"));
    }
  });

  boot();
})();
