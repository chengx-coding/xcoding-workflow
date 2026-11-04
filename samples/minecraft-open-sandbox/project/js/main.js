/* Blockfall boot, simulation loop, interaction wiring and persistence. */
(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const RNG = window.SandboxRng;
  const WORLD = window.SandboxWorld;
  const INV = window.SandboxInventory;
  const CRAFT = window.SandboxCrafting;
  const FURNACE = window.SandboxFurnace;
  const SAVE = window.SandboxSave;
  const PLAYER = window.SandboxPlayer;
  const SURVIVAL = window.SandboxSurvival;
  const LIGHT = window.SandboxLighting;
  const PARTICLES = window.SandboxParticles;
  const ENTITIES = window.SandboxEntities;
  const AUDIO = window.SandboxAudio;
  const MINIMAP = window.SandboxMinimap;
  const RENDER = window.SandboxRender;
  const INPUT = window.SandboxInput;
  const UI = window.SandboxUI;
  const TEX = window.SandboxTextures;
  const B = CONFIG.blocks;
  const TILE = CONFIG.tileSize;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const status = document.getElementById("status");
  const hud = document.getElementById("hud");
  const hotbarEl = document.getElementById("hotbar");
  const toastsEl = document.getElementById("toasts");
  const clockEl = document.getElementById("clock");
  const selectedEl = document.getElementById("hud-selected");
  const minimapEl = document.getElementById("minimap");
  const heartsEl = document.getElementById("hearts");
  const hungerEl = document.getElementById("hunger");
  const airEl = document.getElementById("air");
  const minimapCanvas = document.getElementById("minimap-canvas");
  const compassEl = document.getElementById("compass");
  const saveNoteEl = document.getElementById("save-note");
  const saveStatusEl = document.getElementById("save-status");

  const screens = {
    title: document.getElementById("title-screen"),
    inventory: document.getElementById("inventory-screen"),
    furnace: document.getElementById("furnace-screen"),
    help: document.getElementById("help-screen"),
    pause: document.getElementById("pause-screen"),
    death: document.getElementById("death-screen")
  };

  const game = {
    mode: "title",
    world: null,
    player: null,
    inventory: null,
    furnaces: null,
    camera: { x: 0, y: 0 },
    time: 0.28,
    particles: PARTICLES.createParticleSystem(),
    entities: ENTITIES.createManager(),
    lighting: LIGHT.createLighting(),
    minimap: null,
    lastLeft: false,
    attackCooldown: 0,
    stepSoundTimer: 0,
    hudSignature: "",
    target: null,
    miningProgress: 0,
    targetValid: true,
    mouseX: CONFIG.viewWidth / 2,
    mouseY: CONFIG.viewHeight / 2,
    seed: CONFIG.seed,
    shake: { x: 0, y: 0, strength: 0 },
    settings: { audio: true, reducedMotion: false, minimap: true },
    lastRight: false,
    hasSave: false,
    persisted: false,
    corruptSave: "",
    saveMeta: null,
    storage: null,
    storageError: "",
    firstInput: false,
    autosaveClock: 0,
    playClock: 0
  };

  let input = null;
  let ui = null;
  let lastFrame = 0;
  let accumulator = 0;
  let running = false;

  function updateViewportScale() {
    const scale = Math.min(window.innerWidth / CONFIG.viewWidth, window.innerHeight / CONFIG.viewHeight);
    const clamped = Math.max(0.4, Math.min(2.5, scale));
    document.documentElement.style.setProperty("--game-scale", String(clamped));
  }

  function setStatus(state, text) {
    status.dataset.state = state;
    status.title = text || state;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function openScreen(name) {
    Object.keys(screens).forEach(function (key) {
      screens[key].classList.toggle("is-open", key === name);
    });
    if (name) {
      setHudVisible(false);
    }
  }

  function closeScreens() {
    Object.keys(screens).forEach(function (key) {
      screens[key].classList.remove("is-open");
    });
    if (game.mode === "playing" && game.world) {
      setHudVisible(true);
    }
  }

  function toast(message, kind) {
    if (!message) {
      return;
    }
    const element = document.createElement("div");
    element.className = "toast" + (kind ? " " + kind : "");
    element.textContent = message;
    toastsEl.appendChild(element);
    while (toastsEl.children.length > 3) {
      toastsEl.removeChild(toastsEl.firstChild);
    }
    window.setTimeout(function () {
      if (element.parentNode) {
        element.parentNode.removeChild(element);
      }
    }, 4400);
  }

  function setHudVisible(visible) {
    hud.style.display = visible ? "flex" : "none";
    hotbarEl.style.display = visible ? "flex" : "none";
    const showMap = Boolean(visible && game.settings.minimap && game.minimap);
    minimapEl.style.display = showMap ? "block" : "none";
    if (game.minimap) {
      game.minimap.setVisible(showMap);
    }
  }

  function itemName(id) {
    const def = CONFIG.itemDefs[id];
    return def ? def.name : "Unknown";
  }

  function formatTime(time) {
    const totalMinutes = Math.floor((((time % 1) + 1) % 1) * 24 * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function updateClock() {
    clockEl.textContent = formatTime(game.time);
  }

  function createIcon(id) {
    const icon = TEX.itemIcon(id);
    const canvasEl = document.createElement("canvas");
    canvasEl.width = 16;
    canvasEl.height = 16;
    if (icon) {
      canvasEl.getContext("2d").drawImage(icon, 0, 0);
    }
    return canvasEl;
  }

  function buildHotbar() {
    hotbarEl.innerHTML = "";
    for (let i = 0; i < INV.hotbarCount; i += 1) {
      const slot = document.createElement("div");
      slot.className = "hotbar-slot";
      slot.dataset.index = String(i);
      slot.setAttribute("role", "button");
      slot.setAttribute("tabindex", "0");
      slot.setAttribute("aria-label", "Hotbar slot " + (i + 1));
      const index = document.createElement("span");
      index.className = "slot-index";
      index.textContent = String(i + 1);
      slot.appendChild(index);
      slot.addEventListener("mousedown", function (event) {
        event.stopPropagation();
        selectHotbar(i);
      });
      slot.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectHotbar(i);
        }
      });
      hotbarEl.appendChild(slot);
    }
    updateHotbar();
  }

  function selectHotbar(index) {
    if (!game.inventory) {
      return;
    }
    INV.setSelected(game.inventory, index);
    updateHotbar();
  }

  function updateHotbar() {
    if (!game.inventory) {
      return;
    }
    for (let i = 0; i < hotbarEl.children.length; i += 1) {
      const element = hotbarEl.children[i];
      const stack = game.inventory.slots[i];
      element.classList.toggle("is-selected", i === game.inventory.selected);
      const oldCanvas = element.querySelector("canvas");
      if (oldCanvas) {
        oldCanvas.remove();
      }
      const oldCount = element.querySelector(".slot-count");
      if (oldCount) {
        oldCount.remove();
      }
      if (stack) {
        element.appendChild(createIcon(stack.id));
        if (stack.count > 1) {
          const count = document.createElement("span");
          count.className = "slot-count";
          count.textContent = String(stack.count);
          element.appendChild(count);
        }
        element.title = itemName(stack.id) + " ×" + stack.count;
      } else {
        element.title = "Empty";
      }
    }
    const stack = INV.selectedStack(game.inventory);
    selectedEl.textContent = stack ? itemName(stack.id) + " ×" + stack.count : "Empty hand";
  }

  function hasNearbyTable() {
    if (!game.world || !game.player) {
      return false;
    }
    const px = Math.floor(game.player.x);
    const py = Math.floor(game.player.y);
    for (let dx = -4; dx <= 4; dx += 1) {
      for (let dy = -3; dy <= 2; dy += 1) {
        if (WORLD.getBlock(game.world, px + dx, py + dy) === B.table) {
          return true;
        }
      }
    }
    return false;
  }

  function resetWorldState() {
    game.particles.clear();
    game.entities = ENTITIES.createManager();
    game.target = null;
    game.miningProgress = 0;
    game.lastRight = false;
    game.lastLeft = false;
    game.attackCooldown = 0;
    game.stepSoundTimer = 0;
    game.shake = { x: 0, y: 0, strength: 0 };
    game.camera.x = 0;
    game.camera.y = 0;
  }

  function makeFreshWorld(seed, options) {
    const opts = options || {};
    const chosen = Number(seed);
    game.seed = Number.isFinite(chosen) && chosen > 0 ? chosen >>> 0 : (Date.now() >>> 0);
    game.world = WORLD.createWorld(game.seed);
    game.player = PLAYER.createPlayer(game.world.spawn.x, game.world.spawn.y);
    game.player.spawnX = game.world.spawn.x;
    game.player.spawnY = game.world.spawn.y;
    game.inventory = INV.createInventory();
    game.furnaces = FURNACE.createStore();
    game.time = 0.28;
    resetWorldState();
    game.hasSave = false;
    game.saveMeta = null;
    game.corruptSave = "";
    RENDER.updateCamera(game.camera, game.player, game.world, CONFIG.viewWidth, CONFIG.viewHeight, 1, 0, 0);
    buildHotbar();
    if (ui) {
      ui.close();
    }
    if (!opts.silent) {
      game.mode = "playing";
      setHudVisible(true);
      closeScreens();
      updateClock();
      toast("New world · seed " + game.seed + " · punch a tree to begin");
      saveGame({ silent: true });
    }
    return game.world;
  }

  function applyPayload(payload) {
    game.world = WORLD.rebuildWorld(payload.seed, payload.width, payload.height, payload.data, payload.surface, payload.spawn);
    game.seed = payload.seed;
    game.player = PLAYER.createPlayer(payload.player.x, payload.player.y);
    const loadedHealth = Number(payload.player.health);
    const loadedHunger = Number(payload.player.hunger);
    game.player.health = clamp(Number.isFinite(loadedHealth) ? loadedHealth : 20, 0, 20);
    game.player.hunger = clamp(Number.isFinite(loadedHunger) ? loadedHunger : 20, 0, 20);
    game.player.saturation = Number(payload.player.saturation) || 0;
    game.player.facing = payload.player.facing === -1 ? -1 : 1;
    game.player.spawnX = Number.isFinite(payload.player.spawnX) ? payload.player.spawnX : payload.spawn.x;
    game.player.spawnY = Number.isFinite(payload.player.spawnY) ? payload.player.spawnY : payload.spawn.y;
    game.player.onGround = true;
    game.player.dead = game.player.health <= 0;
    game.inventory = INV.deserializeInventory(payload.inventory);
    INV.setSelected(game.inventory, payload.selected);
    game.furnaces = FURNACE.deserialize(payload.furnaces);
    game.time = ((Number(payload.time) || 0.28) % 1 + 1) % 1;
    game.settings = Object.assign({ audio: true, reducedMotion: false, minimap: true }, payload.settings || {});
    resetWorldState();
    RENDER.updateCamera(game.camera, game.player, game.world, CONFIG.viewWidth, CONFIG.viewHeight, 1, 0, 0);
    buildHotbar();
    game.hasSave = true;
    game.persisted = true;
    game.saveMeta = payload;
    game.corruptSave = "";
    if (ui) {
      ui.close();
    }
    updateClock();
    return game;
  }

  function newWorld(seed) {
    makeFreshWorld(seed, { silent: true });
    game.mode = "playing";
    setHudVisible(true);
    closeScreens();
    updateClock();
    updateHud(true);
    toast("New world · seed " + game.seed + " · punch a tree to begin");
    saveGame({ silent: true });
    canvas.focus();
  }

  function continueWorld() {
    if (!game.hasSave || !game.world) {
      toast("No saved world yet", "warn");
      return;
    }
    game.mode = game.player.dead ? "dead" : "playing";
    setHudVisible(true);
    closeScreens();
    if (game.player.dead) {
      openScreen("death");
    } else {
      updateClock();
      updateHud(true);
      toast("Welcome back · " + formatTime(game.time) + " · seed " + game.seed);
    }
  }

  function openTitle() {
    if (game.world && game.mode === "playing") {
      saveGame({ silent: true });
    }
    game.mode = "title";
    if (ui) {
      ui.close();
    }
    openScreen("title");
    setHudVisible(false);
    updateSaveNote();
  }

  function saveGame(options) {
    const opts = options || {};
    if (!game.world || !game.player || !game.inventory) {
      return { ok: false, error: "No world to save" };
    }
    const payload = SAVE.buildPayload(game);
    game.memoryPayload = payload;
    const result = SAVE.saveToStorage(payload, game.storage);
    game.saveMeta = payload;
    game.hasSave = true;
    game.persisted = result.ok;
    game.storageError = result.ok ? "" : result.error;
    updateSaveNote();
    if (saveStatusEl) {
      saveStatusEl.textContent = result.ok
        ? "Saved at " + formatTime(game.time) + "."
        : "Saved for this session only — " + result.error;
    }
    if (opts.toast) {
      if (result.ok) {
        toast("World saved");
      } else {
        toast("Session saved in memory — " + result.error, "warn");
      }
    } else if (opts.warn && !result.ok) {
      toast("Browser storage is unavailable — export a save instead", "warn");
    }
    return result;
  }

  function updateSaveNote() {
    if (!saveNoteEl) {
      return;
    }
    const warning = document.getElementById("save-warning");
    const continueButton = document.getElementById("btn-continue");
    const newButton = document.getElementById("btn-new-world");
    if (game.corruptSave) {
      if (warning) {
        warning.hidden = false;
        warning.textContent = "Saved world couldn't load — a new world will be created.";
      }
      saveNoteEl.textContent = "A fresh seed is ready. Previous progress could not be recovered.";
      if (newButton) {
        newButton.textContent = "Start Fresh World";
      }
      if (continueButton) {
        continueButton.hidden = true;
        continueButton.disabled = true;
      }
      return;
    }
    if (warning) {
      warning.hidden = true;
      warning.textContent = "";
    }
    if (newButton) {
      newButton.textContent = "New World";
    }
    if (continueButton) {
      continueButton.hidden = false;
      continueButton.disabled = !game.hasSave;
    }
    if (game.hasSave) {
      saveNoteEl.textContent = "Continue — " + (game.saveMeta ? SAVE.summarize(game.saveMeta) : "current session") + ".";
    } else {
      saveNoteEl.textContent = "No saved world yet. New World starts a fresh seed.";
    }
    if (!game.storage) {
      saveNoteEl.textContent += " Browser storage is unavailable — use Export save in the pause menu.";
    }
  }

  function computeTarget() {
    if (game.mode !== "playing") {
      game.target = null;
      return;
    }
    game.mouseX = input.mouseX;
    game.mouseY = input.mouseY;
    const worldX = Math.floor((game.camera.x + input.mouseX) / TILE);
    const worldY = Math.floor((game.camera.y + input.mouseY) / TILE);
    const block = WORLD.getBlock(game.world, worldX, worldY);
    if (block === null || !PLAYER.canReach(game.player, worldX, worldY)) {
      game.target = null;
      return;
    }
    game.target = { x: worldX, y: worldY, block: block, reachable: true };
  }

  function addDrop(block) {
    const def = CONFIG.blockDefs[block];
    if (!def) {
      return;
    }
    let drop = def.drop;
    if (drop === -1) {
      if (block === B.leaves && Math.random() < 0.06) {
        drop = CONFIG.itemIds.apple;
      } else {
        return;
      }
    }
    const remaining = INV.addItem(game.inventory, drop, 1);
    if (remaining > 0) {
      toast("Inventory full — " + itemName(drop) + " was left behind", "warn");
    } else {
      AUDIO.play("pickup");
    }
    updateHotbar();
  }

  function spawnParticles(x, y, block, count) {
    game.particles.spawnBlock(x, y, block, count);
  }

  function breakTarget() {
    const target = game.target;
    if (!target || target.block === B.air) {
      return false;
    }
    const block = target.block;
    const def = CONFIG.blockDefs[block];
    if (!def || !Number.isFinite(def.hardness)) {
      toast("That cannot be broken", "warn");
      return false;
    }
    WORLD.setBlock(game.world, target.x, target.y, B.air);
    if (block === B.furnace) {
      FURNACE.remove(game.furnaces, target.x, target.y);
    }
    spawnParticles(target.x, target.y, block);
    AUDIO.play("break");
    addDrop(block);
    game.player.swing = 1;
    game.shake.strength = Math.min(6, game.shake.strength + 1.2);
    game.target = null;
    game.miningProgress = 0;
    if (ui && ui.isOpen()) {
      ui.refresh();
    }
    return true;
  }

  function placeSelected() {
    const stack = INV.selectedStack(game.inventory);
    if (!stack) {
      toast("Select a block in the hotbar first", "warn");
      return false;
    }
    const def = CONFIG.itemDefs[stack.id];
    if (!def || !def.place) {
      toast(itemName(stack.id) + " cannot be placed", "warn");
      return false;
    }
    if (!game.target) {
      return false;
    }
    const check = PLAYER.validatePlacement(game.world, game.player, game.target.x, game.target.y, def.place);
    if (!check.ok) {
      toast(check.reason, "warn");
      return false;
    }
    const x = game.target.x;
    const y = game.target.y;
    WORLD.setBlock(game.world, x, y, def.place);
    if (def.place === B.furnace) {
      FURNACE.get(game.furnaces, x, y, true);
    }
    INV.consumeSelected(game.inventory, 1);
    updateHotbar();
    game.player.swing = 1;
    spawnParticles(x, y, def.place, 4);
    AUDIO.play("place");
    if (ui && ui.isOpen()) {
      ui.refresh();
    }
    return true;
  }

  function eatSelected() {
    const stack = INV.selectedStack(game.inventory);
    if (!stack) {
      return false;
    }
    const def = CONFIG.itemDefs[stack.id];
    if (!def || def.kind !== "food" || game.player.hunger >= game.player.maxHunger) {
      return false;
    }
    if (!SURVIVAL.eat(game.player, def)) {
      return false;
    }
    INV.consumeSelected(game.inventory, 1);
    updateHotbar();
    game.particles.spawnSoft(game.player.x, game.player.y - 1, "#d9c37a", 4);
    AUDIO.play("eat");
    toast("Ate " + def.name);
    return true;
  }

  function interact() {
    if (!game.target) {
      return false;
    }
    if (eatSelected()) {
      return true;
    }
    if (game.target.block === B.table) {
      openInventory();
      return true;
    }
    if (game.target.block === B.furnace) {
      openFurnace(game.target.x, game.target.y);
      return true;
    }
    if (game.target.block === B.air) {
      return placeSelected();
    }
    return false;
  }

  function openInventory() {
    if (game.mode !== "playing") {
      return;
    }
    game.mode = "inventory";
    ui.openInventory();
    openScreen("inventory");
  }

  function openFurnace(x, y) {
    if (game.mode !== "playing") {
      return;
    }
    game.mode = "furnace";
    ui.openFurnace(x, y);
    openScreen("furnace");
  }

  function closePanel() {
    if (ui) {
      ui.close();
    }
    if (game.mode === "help" && game.helpReturn === "paused") {
      game.mode = "paused";
      openScreen("pause");
      return;
    }
    game.mode = "playing";
    closeScreens();
    updateHotbar();
  }

  function togglePause() {
    if (game.mode === "playing") {
      saveGame({ silent: true });
      game.mode = "paused";
      if (saveStatusEl) {
        saveStatusEl.textContent = game.persisted ? "Saved automatically." : "Session only — export to keep a copy.";
      }
      openScreen("pause");
    } else if (game.mode === "paused") {
      game.mode = "playing";
      closeScreens();
    }
  }

  function updateShake(dt) {
    if (game.shake.strength <= 0) {
      game.shake.x = 0;
      game.shake.y = 0;
      return;
    }
    game.shake.strength = Math.max(0, game.shake.strength - dt * 14);
    const amount = game.settings.reducedMotion ? 0 : game.shake.strength;
    game.shake.x = (Math.random() - 0.5) * amount;
    game.shake.y = (Math.random() - 0.5) * amount;
  }

  function deathMessage(cause) {
    const messages = {
      zombie: "A zombie got you.",
      slime: "A slime bounced you flat.",
      fall: "You fell too far.",
      starvation: "You ran out of food.",
      drowning: "You ran out of air."
    };
    return messages[cause] || "The world got you.";
  }

  function die(cause) {
    if (game.mode === "dead") {
      return;
    }
    game.mode = "dead";
    game.player.dead = true;
    game.player.mining = null;
    game.miningProgress = 0;
    const causeEl = document.getElementById("death-cause");
    if (causeEl) {
      causeEl.textContent = deathMessage(cause || game.player.lastDamageCause);
    }
    openScreen("death");
    AUDIO.play("death");
    saveGame({ silent: true });
  }

  function hurtPlayer(amount, cause) {
    const applied = SURVIVAL.damage(game.player, amount, cause);
    if (applied <= 0) {
      return 0;
    }
    AUDIO.play("hurt");
    game.shake.strength = Math.min(8, game.shake.strength + 2.4);
    game.particles.spawnDamage(game.player.x, game.player.y - game.player.height * 0.6, "#e05b5b");
    if (game.player.health <= 0) {
      die(cause);
    }
    return applied;
  }

  function mobDrop(id) {
    if (id == null || id < 0) {
      return;
    }
    const remaining = INV.addItem(game.inventory, id, 1);
    if (remaining > 0) {
      toast("Inventory full — a drop was left behind", "warn");
    } else {
      AUDIO.play("pickup");
      game.particles.spawnSoft(game.player.x, game.player.y - 0.8, "#f7d05a", 3);
    }
    updateHotbar();
  }

  function tryAttack() {
    if (game.mode !== "playing" || !game.target) {
      return false;
    }
    const worldX = (game.camera.x + input.mouseX) / TILE;
    const worldY = (game.camera.y + input.mouseY) / TILE;
    const mob = ENTITIES.mobAt(game.entities, worldX, worldY);
    if (!mob) {
      return false;
    }
    const dx = mob.x - game.player.x;
    const dy = (mob.y - mob.height * 0.5) - (game.player.y - game.player.height * 0.5);
    if (Math.sqrt(dx * dx + dy * dy) > CONFIG.attackReach + 1) {
      return false;
    }
    if (game.attackCooldown > 0) {
      return true;
    }
    const tool = INV.selectedTool(game.inventory);
    const damage = tool ? tool.damage : 1;
    const result = ENTITIES.hit(game.entities, mob, damage, Math.sign(dx) || game.player.facing, {
      effects: {
        onDrop: mobDrop,
        onParticle: function (x, y, color, count) {
          game.particles.spawnDamage(x, y, color);
        }
      }
    });
    game.attackCooldown = 0.35;
    game.player.swing = 1;
    AUDIO.play("attack");
    game.shake.strength = Math.min(5, game.shake.strength + 1.4);
    if (result.killed) {
      toast("Defeated a " + mob.type);
    }
    return true;
  }

  function updateHud(force) {
    if (!game.player) {
      return;
    }
    const signature = game.player.health + "/" + game.player.hunger + "/" + Math.ceil(game.player.air);
    if (force || signature !== game.hudSignature) {
      game.hudSignature = signature;
      heartsEl.innerHTML = "";
      for (let i = 0; i < 10; i += 1) {
        const value = game.player.health - i * 2;
        const heart = document.createElement("span");
        heart.className = "heart" + (value >= 2 ? "" : value >= 1 ? " half" : " empty");
        heart.title = "Health " + game.player.health + "/" + game.player.maxHealth;
        heartsEl.appendChild(heart);
      }
      hungerEl.innerHTML = "";
      for (let i = 0; i < 10; i += 1) {
        const value = game.player.hunger - i * 2;
        const pip = document.createElement("span");
        pip.className = "hunger-pip" + (value >= 1 ? "" : " empty");
        pip.title = "Hunger " + game.player.hunger + "/" + game.player.maxHunger;
        hungerEl.appendChild(pip);
      }
      airEl.innerHTML = "";
      if (game.player.air < game.player.maxAir - 0.05) {
        for (let i = 0; i < 10; i += 1) {
          const value = game.player.air - i;
          const pip = document.createElement("span");
          pip.className = "air-pip" + (value >= 1 ? "" : " empty");
          pip.title = "Air";
          airEl.appendChild(pip);
        }
      }
    }
    updateClock();
  }

  function update(dt) {
    if (!game.world || game.mode === "title" || game.mode === "paused") {
      return;
    }
    if (game.mode === "playing") {
      game.playClock += dt;
      game.time = (game.time + dt / CONFIG.dayLength) % 1;
      game.attackCooldown = Math.max(0, game.attackCooldown - dt);

      const couldJump = game.player.onGround;
      PLAYER.stepPlayer(game.player, game.world, INPUT.toInput(input), dt);
      if (couldJump && input.jump && game.player.vy < -4) {
        AUDIO.play("jump");
      }
      const held = INV.selectedStack(game.inventory);
      game.player.heldItem = held ? CONFIG.itemDefs[held.id] : null;
      computeTarget();

      const survivalEvents = SURVIVAL.update(game.player, game.world, dt, {
        mining: Boolean(game.player.mining)
      });
      for (const event of survivalEvents) {
        if (event.type === "damage") {
          AUDIO.play("hurt");
          game.shake.strength = Math.min(8, game.shake.strength + 1.8);
          game.particles.spawnDamage(game.player.x, game.player.y - game.player.height * 0.6, "#e05b5b");
        } else if (event.type === "died") {
          die(event.cause);
        }
      }
      if (game.player.health <= 0 && game.mode !== "dead") {
        die(game.player.lastDamageCause);
      }
      if (game.mode === "playing") {
        let attacked = false;
        if (input.mouseDown) {
          attacked = tryAttack();
        }
        game.lastLeft = input.mouseDown;

        if (!attacked && input.mouseDown && game.target && game.target.block !== B.air) {
          const tool = INV.selectedTool(game.inventory);
          const result = PLAYER.updateMining(game.player, { x: game.target.x, y: game.target.y, block: game.target.block }, dt, tool);
          game.miningProgress = result.progress;
          if (result.done) {
            breakTarget();
          }
        } else if (!input.mouseDown || attacked) {
          game.miningProgress = 0;
          if (game.player.mining) {
            game.player.mining = null;
          }
        }

        if (input.rightDown && !game.lastRight) {
          interact();
        }
        game.lastRight = input.rightDown;

        const wheel = input.consumeWheel();
        if (wheel !== 0) {
          INV.cycleSelected(game.inventory, wheel);
          updateHotbar();
        }

        const lookX = (input.mouseX / CONFIG.viewWidth - 0.5) * 26;
        const lookY = (input.mouseY / CONFIG.viewHeight - 0.5) * 14;
        RENDER.updateCamera(game.camera, game.player, game.world, CONFIG.viewWidth, CONFIG.viewHeight, dt, lookX, lookY);

        if (game.player.onGround && game.player.moving) {
          game.stepSoundTimer -= dt;
          if (game.stepSoundTimer <= 0) {
            game.stepSoundTimer = 0.34;
            AUDIO.play("step");
          }
        } else {
          game.stepSoundTimer = 0;
        }

        ENTITIES.update(game.entities, {
          world: game.world,
          player: game.player,
          time: game.time,
          dt: dt,
          effects: {
            onPlayerDamage: hurtPlayer,
            onDrop: mobDrop,
            onParticle: function (x, y, color, count) {
              game.particles.spawnSoft(x, y, color, count);
            }
          }
        });

        game.hudTimer = (game.hudTimer || 0) + dt;
        if (game.hudTimer >= 0.12) {
          game.hudTimer = 0;
          updateHud();
        }

        game.autosaveClock += dt;
        if (game.autosaveClock >= 20) {
          game.autosaveClock = 0;
          saveGame({ silent: true });
        }
      }
    }

    if (game.mode === "playing" || game.mode === "inventory" || game.mode === "furnace") {
      if (FURNACE.tickAll(game.furnaces, dt) && ui && ui.activeKind() === "furnace") {
        ui.refreshFurnace();
      }
      if (ui) {
        ui.tick();
      }
    }
    game.particles.update(dt);
    if (game.minimap) {
      game.minimap.update(game, dt);
    }
    updateShake(dt);
  }

  function render() {
    if (!game.world) {
      return;
    }
    RENDER.renderFrame(ctx, {
      world: game.world,
      player: game.player,
      camera: game.camera,
      time: game.time,
      entities: game.entities.list,
      particles: game.particles.list,
      furnaces: game.furnaces,
      lighting: function (target, state, offsets) {
        game.lighting.render(target, state, offsets);
      },
      target: game.target,
      targetValid: game.target ? game.target.reachable : true,
      miningProgress: game.miningProgress,
      mouseX: input ? input.mouseX : CONFIG.viewWidth / 2,
      mouseY: input ? input.mouseY : CONFIG.viewHeight / 2,
      shake: game.shake
    });
  }

  function frame(now) {
    if (!running) {
      return;
    }
    const delta = Math.min(0.1, Math.max(0, (now - lastFrame) / 1000 || 0));
    lastFrame = now;
    accumulator += delta;
    let steps = 0;
    while (accumulator >= 1 / 60 && steps < 6) {
      update(1 / 60);
      accumulator -= 1 / 60;
      steps += 1;
    }
    render();
    handleShortcuts();
    input.clearFrame();
    window.requestAnimationFrame(frame);
  }

  function handleShortcuts() {
    if (!input) {
      return;
    }
    const press = input.consumeAnyPress(["Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "Digit6", "Digit7", "Digit8", "Digit9"]);
    if (press && game.mode === "playing") {
      selectHotbar(Number(press.slice(5)) - 1);
    }
    if (game.mode === "title" && (input.consumePress("Enter") || input.consumePress("NumpadEnter"))) {
      if (game.hasSave) {
        continueWorld();
      } else {
        newWorld(Date.now());
      }
      return;
    }
    if (input.consumePress("KeyE")) {
      if (game.mode === "playing") {
        openInventory();
      } else if (game.mode === "inventory" || game.mode === "furnace") {
        closePanel();
      }
    }
    if (input.consumePress("KeyM") && game.mode === "playing") {
      game.settings.minimap = !game.settings.minimap;
      const toggle = document.getElementById("toggle-minimap");
      if (toggle) {
        toggle.checked = game.settings.minimap;
      }
      setHudVisible(true);
      if (game.settings.minimap && game.minimap) {
        game.minimap.draw(game);
      }
    }
    if (input.consumePress("KeyH")) {
      if (game.mode === "playing") {
        game.helpReturn = "playing";
        game.mode = "help";
        openScreen("help");
      } else if (game.mode === "help") {
        closePanel();
      }
    }
    if (input.consumePress("Escape")) {
      if (game.mode === "help" || game.mode === "inventory" || game.mode === "furnace") {
        closePanel();
      } else if (game.mode === "playing" || game.mode === "paused") {
        togglePause();
      }
    }
  }

  function bindUi() {
    document.getElementById("btn-new-world").addEventListener("click", function () {
      newWorld(Date.now());
    });
    document.getElementById("btn-continue").addEventListener("click", function () {
      continueWorld();
    });
    document.getElementById("btn-resume").addEventListener("click", function () {
      game.mode = "playing";
      closeScreens();
    });
    document.getElementById("btn-save").addEventListener("click", function () {
      saveGame({ toast: true, warn: true });
    });
    document.getElementById("btn-help").addEventListener("click", function () {
      game.helpReturn = "paused";
      game.mode = "help";
      openScreen("help");
    });
    document.getElementById("btn-title").addEventListener("click", function () {
      saveGame({ silent: true });
      openTitle();
    });
    document.getElementById("btn-respawn").addEventListener("click", function () {
      PLAYER.respawnPlayer(game.player, { x: game.world.spawn.x, y: game.world.spawn.y });
      ENTITIES.clearHostiles(game.entities);
      game.mode = "playing";
      closeScreens();
      updateHud(true);
      saveGame({ silent: true });
      AUDIO.play("pickup");
      toast("Respawned at world spawn");
    });
    document.getElementById("btn-export").addEventListener("click", function () {
      const payload = SAVE.buildPayload(game);
      const blob = new Blob([SAVE.exportText(payload)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "blockfall-save.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      toast("Save exported");
    });
    document.getElementById("import-file").addEventListener("change", function (event) {
      const file = event.target.files && event.target.files[0];
      if (!file) {
        return;
      }
      file.text().then(function (text) {
        try {
          const payload = SAVE.parsePayload(text);
          applyPayload(payload);
          game.mode = "playing";
          setHudVisible(true);
          closeScreens();
          updateClock();
          saveGame({ toast: true });
          toast("Save imported · seed " + game.seed);
        } catch (error) {
          toast("Import failed — " + error.message, "bad");
        }
        event.target.value = "";
      }).catch(function (error) {
        toast("Import failed — " + error.message, "bad");
      });
    });
    document.querySelectorAll("[data-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        closePanel();
      });
    });
    const audioToggle = document.getElementById("toggle-audio");
    const motionToggle = document.getElementById("toggle-motion");
    const minimapToggle = document.getElementById("toggle-minimap");
    if (audioToggle) {
      audioToggle.checked = game.settings.audio !== false;
      audioToggle.addEventListener("change", function () {
        game.settings.audio = audioToggle.checked;
        AUDIO.setEnabled(audioToggle.checked);
        if (audioToggle.checked) {
          AUDIO.unlock();
        }
      });
    }
    if (motionToggle) {
      motionToggle.checked = Boolean(game.settings.reducedMotion);
      motionToggle.addEventListener("change", function () {
        game.settings.reducedMotion = motionToggle.checked;
        game.particles.setReducedMotion(motionToggle.checked);
      });
    }
    if (minimapToggle) {
      minimapToggle.checked = game.settings.minimap !== false;
      minimapToggle.addEventListener("change", function () {
        game.settings.minimap = minimapToggle.checked;
        setHudVisible(game.mode !== "title");
        if (game.settings.minimap && game.minimap) {
          game.minimap.draw(game);
        }
      });
    }
  }

  function boot() {
    try {
      updateViewportScale();
      window.addEventListener("resize", updateViewportScale);
      TEX.create();
      game.storage = SAVE.defaultStorage();
      const loaded = SAVE.loadFromStorage(game.storage);
      if (loaded.ok) {
        applyPayload(loaded.payload);
        game.persisted = true;
      } else {
        const corruptReason = loaded.corrupt ? loaded.error : "";
        makeFreshWorld(CONFIG.seed, { silent: true });
        game.corruptSave = corruptReason;
      }
      game.minimap = MINIMAP.createMinimap(minimapEl, minimapCanvas, compassEl);
      AUDIO.setEnabled(game.settings.audio !== false);
      game.particles.setReducedMotion(game.settings.reducedMotion);
      buildHotbar();
      ui = UI.createUI({
        game: game,
        toast: toast,
        hasNearbyTable: hasNearbyTable,
        updateHotbar: updateHotbar,
        onChange: function () { updateHotbar(); },
        onCraft: function () { AUDIO.play("craft"); }
      });
      bindUi();
      updateHud(true);
      openTitle();
      setStatus("ready", "ready");
      window.__sandbox = {
        game: game,
        config: CONFIG,
        world: WORLD,
        player: PLAYER,
        inventory: INV,
        crafting: CRAFT,
        furnace: FURNACE,
        save: SAVE,
        render: RENDER,
        survival: SURVIVAL,
        entities: ENTITIES,
        particles: game.particles,
        lighting: game.lighting,
        audio: AUDIO,
        ui: ui,
        newWorld: newWorld,
        continueWorld: continueWorld,
        openTitle: openTitle,
        openInventory: openInventory,
        openFurnace: openFurnace,
        saveGame: saveGame,
        refreshHud: updateHotbar,
        toast: toast,
        ready: true
      };
      lastFrame = performance.now();
      running = true;
      window.requestAnimationFrame(frame);
    } catch (error) {
      setStatus("error", error && error.message ? error.message : String(error));
      throw error;
    }
  }

  window.addEventListener("error", function (event) {
    setStatus("error", event.message || "runtime error");
  });
  window.addEventListener("unhandledrejection", function (event) {
    setStatus("error", String(event.reason));
  });

  input = INPUT.createInput(canvas, {
    onActivity: function () {
      if (!game.firstInput) {
        game.firstInput = true;
        AUDIO.unlock();
      }
    }
  });
  window.addEventListener("pagehide", function () {
    if (game.world && game.player) {
      saveGame({ silent: true });
    }
    if (input) {
      input.destroy();
    }
  });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden" && game.world && game.mode === "playing") {
      saveGame({ silent: true });
    }
  });

  boot();
})();
