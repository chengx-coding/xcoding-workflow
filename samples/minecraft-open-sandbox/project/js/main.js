(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const PHYSICS = window.SandboxPhysics;
  const INVENTORY = window.SandboxInventory;
  const SAVE = window.SandboxSave;
  const AUDIO = window.SandboxAudio;
  const RENDER = window.SandboxRender;
  const UI_FACTORY = window.SandboxUI;

  const TILE = CONFIG.tileSize;
  const VIEW_W = CONFIG.viewWidth;
  const VIEW_H = CONFIG.viewHeight;
  const canvas = document.getElementById("game");
  const status = document.getElementById("status");
  const renderer = RENDER.createRenderer(canvas);

  const BLOCK_PARTICLES = {
    1: [91, 132, 67],
    2: [126, 90, 61],
    3: [124, 131, 132],
    4: [119, 82, 51],
    5: [68, 122, 61],
    6: [127, 136, 136],
    7: [214, 189, 123],
    8: [180, 123, 67],
    9: [116, 125, 126],
    10: [146, 113, 89],
    11: [255, 171, 67],
    12: [166, 111, 62],
    13: [119, 128, 128],
    14: [201, 236, 241],
    15: [127, 135, 134],
    16: [228, 99, 69],
    17: [79, 141, 63]
  };

  let storage = probeStorage();
  let world = null;
  let player = null;
  let inventory = null;
  let selected = 0;
  let timeOfDay = CONFIG.startTimeOfDay;
  let day = 1;
  let stats = SAVE.defaultStats();
  let tutorial = SAVE.defaultTutorial();
  let settings = SAVE.defaultSettings();
  let particles = [];
  let mining = null;
  let hover = { visible: false, x: 0, y: 0, valid: false, inReach: false, canMine: false, canPlace: false, reason: "" };
  let heldStack = null;
  let camera = { x: 0, y: 0 };
  let mouse = { x: 0, y: 0, inside: false };
  let leftDown = false;
  let keys = Object.create(null);
  let input = { left: false, right: false, jump: false, sprint: false };
  let playing = false;
  let dead = false;
  let dirty = false;
  let lastSaveAt = 0;
  let saveDebounce = 0;
  let autosaveTimer = 0;
  let hudTimer = 0;
  let minimapTimer = 0;
  let saveLabelTimer = 0;
  let emberTimer = 0;
  let stepTimer = 0;
  let swingPhase = 0;
  let lastMineSound = 0;
  let lastDamageAt = 0;
  let regenTimer = 0;
  let bootNotice = "";
  let lastFrame = 0;
  let minimapVisible = true;
  let ui = null;
  let noticeCooldown = 0;

  function probeStorage() {
    try {
      const candidate = window.localStorage;
      const key = "__emberblock_probe__";
      candidate.setItem(key, "1");
      candidate.removeItem(key);
      return candidate;
    } catch (error) {
      return null;
    }
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function setStatus(state, text) {
    if (!status) {
      return;
    }
    status.dataset.state = state;
    status.title = text;
  }

  function selectedSlot() {
    return inventory ? inventory.slots[selected] : null;
  }

  function selectedItem() {
    const slot = selectedSlot();
    return slot ? CONFIG.items[slot.id] : null;
  }

  function selectedItemId() {
    const slot = selectedSlot();
    return slot ? slot.id : null;
  }

  function currentStations() {
    return INVENTORY.nearbyStations(world, player.x, player.y);
  }

  function snapshot() {
    return {
      world: world,
      player: player,
      inventory: inventory,
      selected: selected,
      timeOfDay: timeOfDay,
      day: day,
      stats: stats,
      tutorial: tutorial,
      settings: settings,
      camera: camera,
      particles: particles,
      hover: hover,
      mining: mining,
      heldStack: heldStack,
      swing: swingPhase,
      dayFactor: WORLD.dayFactor(timeOfDay)
    };
  }

  function insideSolid(target) {
    const left = Math.floor(target.x - target.width / 2 + 0.0001);
    const right = Math.floor(target.x + target.width / 2 - 0.0001);
    const top = Math.floor(target.y - target.height + 0.0001);
    const bottom = Math.floor(target.y - 0.0001);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (WORLD.isSolid(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  function rescuePlayer() {
    if (!insideSolid(player)) {
      return;
    }
    const startY = player.y;
    for (let step = 1; step <= 12; step += 1) {
      player.y = startY - step;
      if (!insideSolid(player)) {
        return;
      }
    }
    player.x = world.spawn.x;
    player.y = world.spawn.y;
  }

  function freshWorld(seed) {
    const muted = settings ? settings.muted : false;
    world = WORLD.createWorld(Number(seed) >>> 0);
    player = PHYSICS.createPlayer(world.spawn.x, world.spawn.y);
    player.onGround = PHYSICS.isOnGroundAt(player, world);
    inventory = INVENTORY.createInventory();
    selected = 0;
    timeOfDay = CONFIG.startTimeOfDay;
    day = 1;
    stats = SAVE.defaultStats();
    tutorial = SAVE.defaultTutorial();
    settings = SAVE.defaultSettings();
    settings.muted = muted;
    particles = [];
    mining = null;
    heldStack = null;
    dead = false;
    dirty = false;
    lastSaveAt = 0;
    saveDebounce = 0;
    autosaveTimer = 0;
    snapCamera();
  }

  function applyLoadedSave(save) {
    world = WORLD.createWorld(save.seed);
    SAVE.applySaveToWorld(world, save);
    player = PHYSICS.createPlayer(save.player.x, save.player.y);
    player.health = Math.max(1, Math.min(CONFIG.maxHealth, save.player.health));
    player.facing = save.player.facing;
    inventory = SAVE.inventoryFromSave(save);
    selected = save.selected;
    timeOfDay = save.timeOfDay;
    stats = save.stats;
    day = Math.max(1, stats.daysSurvived || 1);
    tutorial = save.tutorial;
    settings = save.settings;
    resetRuntimeInput();
    rescuePlayer();
    player.onGround = PHYSICS.isOnGroundAt(player, world);
    playing = false;
    dead = false;
    dirty = false;
    lastSaveAt = save.savedAt || Date.now();
    snapCamera();
  }

  function boot() {
    const read = SAVE.readStorage(storage, CONFIG.saveKey);
    let save = null;
    if (read.ok) {
      try {
        save = SAVE.decodeSave(read.text);
      } catch (error) {
        SAVE.clearStorage(storage, CONFIG.saveKey);
        bootNotice = "The old save could not be read, so a fresh valley was started. " + (error && error.message ? error.message : "");
      }
    } else if (read.reason === "storage_read_error") {
      bootNotice = "The browser could not read local storage. Progress will last for this session.";
    } else if (read.reason === "storage_unavailable") {
      storage = null;
      bootNotice = "Local storage is unavailable here. You can play, but progress will not survive a reload.";
    }

    if (save) {
      applyLoadedSave(save);
    } else {
      freshWorld(CONFIG.seed);
    }

    ui = UI_FACTORY.createUI(actions);
    AUDIO.setMuted(!!settings.muted);
    ui.setSoundLabels(!!settings.muted);
    ui.setMinimapVisible(minimapVisible);
    snapCamera();
    renderer.draw(renderSnapshot());
    drawMinimap();
    ui.updateHUD(snapshot());
    ui.updateHotbar(snapshot(), true);
    ui.showStart({
      hasSave: !!save,
      seed: world.seed,
      savedAt: lastSaveAt,
      muted: settings.muted
    });
    if (save) {
      ui.setSaveState("Save loaded", "saved");
    } else if (storage) {
      ui.setSaveState("New world", "idle");
    } else {
      ui.setSaveState("Saving unavailable", "error");
    }
    if (bootNotice) {
      window.setTimeout(function () {
        if (ui) {
          ui.toast(bootNotice, "warn", 5200);
        }
      }, 300);
    }
    setStatus("ready", "Emberblock ready");
    window.__emberblock = {
      version: CONFIG.version,
      ready: true,
      getSnapshot: function () {
        return {
          seed: world.seed,
          player: { x: player.x, y: player.y, health: player.health, onGround: player.onGround, facing: player.facing },
          selected: selected,
          inventory: inventory.slots.map(function (slot) { return slot ? { id: slot.id, count: slot.count } : null; }),
          timeOfDay: timeOfDay,
          day: day,
          stats: JSON.parse(JSON.stringify(stats)),
          tutorial: JSON.parse(JSON.stringify(tutorial)),
          settings: JSON.parse(JSON.stringify(settings)),
          overlay: ui.currentScreen(),
          playing: playing,
          dead: dead,
          saveAt: lastSaveAt,
          storage: !!storage,
          camera: { x: camera.x, y: camera.y },
          particles: particles.length,
          hover: { x: hover.x, y: hover.y, visible: hover.visible, valid: hover.valid },
          mining: mining ? { x: mining.x, y: mining.y, progress: mining.progress } : null
        };
      },
      getTile: function (x, y) {
        const block = WORLD.getBlock(world, x, y);
        return { block: block, key: WORLD.getBlockKey(block) };
      },
      tileToClient: function (x, y) {
        const rect = canvas.getBoundingClientRect();
        return {
          x: rect.left + ((x + 0.5) * TILE - camera.x) * (rect.width / VIEW_W),
          y: rect.top + ((y + 0.5) * TILE - camera.y) * (rect.height / VIEW_H)
        };
      },
      give: function (itemId, count) {
        if (!CONFIG.items[itemId]) {
          return { ok: false, reason: "unknown_item" };
        }
        const result = INVENTORY.addItem(inventory, itemId, count || 1);
        refreshUIAfterInventory();
        markDirty();
        return { ok: result.remaining === 0, added: result.added, remaining: result.remaining };
      },
      setTime: function (value) {
        timeOfDay = ((Number(value) % 1) + 1) % 1;
        return timeOfDay;
      },
      setHealth: function (value) {
        player.health = clamp(Number(value) || 0, 0, CONFIG.maxHealth);
        ui.updateHUD(snapshot());
        return player.health;
      },
      setPosition: function (x, y) {
        player.x = Number(x);
        player.y = Number(y);
        snapCamera();
        return { x: player.x, y: player.y };
      },
      craft: function (recipeId) {
        craftRecipe(recipeId);
        return this.getSnapshot();
      },
      save: function () {
        return saveNow("manual", false);
      },
      newWorld: function (seed) {
        startNewWorld(seed === undefined ? (Date.now() >>> 0) : seed, "start");
        return { ok: true, seed: world.seed };
      },
      openInventory: function () {
        openInventory();
      },
      closeInventory: function () {
        closeInventory();
      },
      setSelected: function (index) {
        selectSlot(index);
      },
      hasSave: function () {
        return !!lastSaveAt;
      }
    };
    requestAnimationFrame(frame);
  }

  function markDirty() {
    dirty = true;
    saveDebounce = 0;
  }

  function resetRuntimeInput() {
    keys = Object.create(null);
    input = { left: false, right: false, jump: false, sprint: false };
    leftDown = false;
    mining = null;
  }

  function saveNow(reason, silent) {
    if (heldStack) {
      if (!silent) {
        ui.toast("Finish moving the held stack before saving.", "warn", 2200);
      }
      return false;
    }
    if (!storage) {
      ui.setSaveState("Saving unavailable", "error");
      if (!silent) {
        ui.toast("Saving is unavailable in this browser. This session is temporary.", "warn", 3600);
      }
      return false;
    }
    try {
      const text = SAVE.encodeSave(snapshot(), world);
      const result = SAVE.writeStorage(storage, CONFIG.saveKey, text);
      if (!result.ok) {
        storage = null;
        ui.setSaveState("Saving unavailable", "error");
        if (!silent) {
          ui.toast("The browser refused to store the save. Your world continues only in this session.", "danger", 4600);
        }
        return false;
      }
      dirty = false;
      saveDebounce = 0;
      autosaveTimer = 0;
      lastSaveAt = Date.now();
      ui.setSaveState("Saved just now", "saved");
      if (!silent && reason === "manual") {
        AUDIO.play("save");
        ui.toast("World saved in this browser.", "good", 1900);
      }
      return true;
    } catch (error) {
      ui.setSaveState("Save failed", "error");
      if (!silent) {
        ui.toast("The save could not be written: " + (error && error.message ? error.message : "unknown error"), "danger", 4200);
      }
      return false;
    }
  }

  function saveLabel() {
    if (!storage) {
      return "Saving unavailable";
    }
    if (!lastSaveAt) {
      return "Not saved yet";
    }
    return "Saved " + relativeTime(lastSaveAt);
  }

  function relativeTime(timestamp) {
    const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    if (seconds < 10) {
      return "just now";
    }
    if (seconds < 60) {
      return seconds + "s ago";
    }
    if (seconds < 3600) {
      return Math.round(seconds / 60) + "m ago";
    }
    return Math.round(seconds / 3600) + "h ago";
  }

  function refreshSaveLabel() {
    if (!ui) {
      return;
    }
    if (!storage) {
      ui.setSaveState("Saving unavailable", "error");
      return;
    }
    if (lastSaveAt) {
      ui.setSaveState("Saved " + relativeTime(lastSaveAt), "saved");
    } else {
      ui.setSaveState("New world", "idle");
    }
  }

  function snapCamera() {
    camera.x = clamp(player.x * TILE - VIEW_W / 2 + player.facing * 36, 0, Math.max(0, world.width * TILE - VIEW_W));
    camera.y = clamp(player.y * TILE - VIEW_H * 0.58, 0, Math.max(0, world.height * TILE - VIEW_H));
  }

  function updateCamera(dt) {
    const targetX = clamp(
      player.x * TILE - VIEW_W / 2 + player.facing * 38 + clamp(player.vx * 9, -34, 34),
      0,
      Math.max(0, world.width * TILE - VIEW_W)
    );
    const targetY = clamp(player.y * TILE - VIEW_H * 0.58, 0, Math.max(0, world.height * TILE - VIEW_H));
    const blend = 1 - Math.exp(-dt * 7.5);
    camera.x += (targetX - camera.x) * blend;
    camera.y += (targetY - camera.y) * blend;
  }

  function beginPlay() {
    if (!world || dead) {
      return;
    }
    AUDIO.ensureContext();
    playing = true;
    ui.hideStart();
    ui.closeAll();
    canvas.focus({ preventScroll: true });
    AUDIO.play("start");
    if (!lastSaveAt) {
      saveNow("start", true);
    }
    if (!tutorial.seenHelp) {
      tutorial.seenHelp = true;
      markDirty();
      window.setTimeout(function () {
        if (ui && playing) {
          ui.toast("Hold left mouse on a tree to gather logs. Press E to craft.", "good", 4200);
        }
      }, 450);
    }
    ui.updateHUD(snapshot());
  }

  function pauseGame() {
    if (!playing || dead || ui.isOverlayOpen()) {
      return;
    }
    resetRuntimeInput();
    swingPhase = 0;
    saveNow("pause", true);
    ui.setSaveNote(saveLabel());
    ui.showPause(saveLabel());
    AUDIO.play("ui");
  }

  function resumeGame() {
    if (!playing || dead) {
      return;
    }
    ui.closeAll();
    canvas.focus({ preventScroll: true });
    AUDIO.play("ui");
  }

  function openInventory() {
    if (!playing || dead || ui.isOverlayOpen()) {
      return;
    }
    resetRuntimeInput();
    swingPhase = 0;
    ui.showInventory(snapshot(), heldStack);
    AUDIO.play("ui");
  }

  function closeInventory() {
    if (ui.currentScreen() !== "inventory") {
      return;
    }
    if (heldStack) {
      const result = INVENTORY.addItem(inventory, heldStack.id, heldStack.count);
      if (result.remaining > 0) {
        heldStack.count = result.remaining;
        ui.refreshInventory(snapshot(), heldStack);
        ui.toast("No room for the held stack. Free a slot or place it back.", "warn", 2600);
        return;
      }
      heldStack = null;
      markDirty();
    }
    ui.setHeld(null);
    ui.closeAll();
    ui.updateHotbar(snapshot(), true);
    canvas.focus({ preventScroll: true });
    if (dirty) {
      saveDebounce = 0;
    }
  }

  function toggleInventory() {
    if (ui.currentScreen() === "inventory") {
      closeInventory();
    } else {
      openInventory();
    }
  }

  function selectSlot(index) {
    if (!Number.isInteger(index) || index < 0 || index >= CONFIG.hotbarSize) {
      return;
    }
    selected = index;
    ui.updateHotbar(snapshot(), true);
    markDirty();
    AUDIO.play("ui");
  }

  function completeTask(id) {
    if (!tutorial.completed.includes(id)) {
      tutorial.completed.push(id);
      markDirty();
      const task = UI_FACTORY.TUTORIAL_TASKS.find(function (item) { return item.id === id; });
      if (task) {
        AUDIO.play("pickup");
        ui.toast("First step: " + task.label, "good", 1900);
      }
    }
  }

  function refreshUIAfterInventory() {
    if (!ui) {
      return;
    }
    ui.updateHotbar(snapshot(), true);
    ui.refreshInventoryIfOpen(snapshot(), heldStack);
  }

  function breakBlock(x, y) {
    const blockId = WORLD.getBlock(world, x, y);
    if (blockId === null || blockId === CONFIG.blocks.air) {
      return false;
    }
    if (WORLD.isProtected(world, x, y)) {
      notify("The world floor is unbreakable.", "warn", 1800);
      return false;
    }
    const definition = WORLD.getBlockDef(blockId);
    const test = INVENTORY.cloneInventory(inventory);
    if (definition.drop && CONFIG.items[definition.drop]) {
      const result = INVENTORY.addItem(test, definition.drop, 1);
      if (result.remaining > 0) {
        ui.toast("Your pack is full. Free a slot before mining more.", "warn", 2400);
        return false;
      }
    }
    const above = WORLD.getBlock(world, x, y - 1);
    if (above === CONFIG.blocks.torch) {
      const torchResult = INVENTORY.addItem(test, "torch", 1);
      if (torchResult.remaining > 0) {
        ui.toast("Your pack is full. Free a slot for the torch above.", "warn", 2400);
        return false;
      }
    }
    inventory = test;
    WORLD.setBlock(world, x, y, CONFIG.blocks.air);
    if (above === CONFIG.blocks.torch) {
      WORLD.setBlock(world, x, y - 1, CONFIG.blocks.air);
    }
    WORLD.updateLight(world);
    stats.blocksMined += 1;
    if (blockId === CONFIG.blocks.wood) {
      completeTask("wood");
    } else if (blockId === CONFIG.blocks.stone) {
      completeTask("stone");
    }
    spawnBreakParticles(x, y, blockId, 7 + Math.floor(Math.random() * 4));
    AUDIO.play("break", { pitch: blockId === CONFIG.blocks.stone || blockId === CONFIG.blocks.cobblestone ? 110 : 170 });
    if (blockId === CONFIG.blocks.coalOre) {
      ui.toast("+1 Coal", "good", 900);
    } else if (blockId === CONFIG.blocks.ironOre) {
      ui.toast("+1 Raw Iron", "good", 1100);
    }
    refreshUIAfterInventory();
    markDirty();
    return true;
  }

  function removeSelectedOne() {
    const slot = inventory.slots[selected];
    if (!slot) {
      return false;
    }
    slot.count -= 1;
    if (slot.count <= 0) {
      inventory.slots[selected] = null;
    }
    return true;
  }

  function canSupportTorch(x, y) {
    return y + 1 < world.height && WORLD.isSolid(world, x, y + 1);
  }

  function canSupportPlant(x, y) {
    if (y + 1 >= world.height) {
      return false;
    }
    const below = WORLD.getBlock(world, x, y + 1);
    return below === CONFIG.blocks.grass || below === CONFIG.blocks.dirt || below === CONFIG.blocks.sand;
  }

  function placeBlock(target) {
    if (!target || !target.visible || !target.inReach) {
      return;
    }
    const existing = WORLD.getBlock(world, target.x, target.y);
    if (existing !== CONFIG.blocks.air) {
      if (existing === CONFIG.blocks.craftingTable || existing === CONFIG.blocks.furnace) {
        openInventory();
        return;
      }
      return;
    }
    if (WORLD.isProtected(world, target.x, target.y)) {
      notify("You cannot place blocks in the world floor.", "warn", 1600);
      return;
    }
    const item = selectedItem();
    if (!item || item.type !== "block") {
      notify("Select a placeable block in your hotbar first.", "warn", 1900);
      return;
    }
    const definition = WORLD.getBlockDef(item.blockId);
    if (definition.solid && PHYSICS.overlapsTile(player, target.x, target.y)) {
      notify("Step back — you are standing in that space.", "warn", 1600);
      return;
    }
    if (item.blockId === CONFIG.blocks.torch && !canSupportTorch(target.x, target.y)) {
      notify("Torches need a solid block underneath.", "warn", 1800);
      return;
    }
    if ((item.blockId === CONFIG.blocks.flower || item.blockId === CONFIG.blocks.tallGrass) && !canSupportPlant(target.x, target.y)) {
      notify("Flowers and grass need soil underneath.", "warn", 1800);
      return;
    }
    if (!removeSelectedOne()) {
      return;
    }
    WORLD.setBlock(world, target.x, target.y, item.blockId);
    WORLD.updateLight(world);
    stats.blocksPlaced += 1;
    if (item.blockId === CONFIG.blocks.craftingTable) {
      completeTask("place_table");
    } else if (item.blockId === CONFIG.blocks.torch) {
      completeTask("torch");
    }
    spawnBreakParticles(target.x, target.y, item.blockId, 5);
    AUDIO.play("place", { pitch: item.blockId === CONFIG.blocks.torch ? 240 : 150 });
    refreshUIAfterInventory();
    markDirty();
    updateHover();
  }

  function pickBlock(target) {
    if (!target || !target.visible) {
      return;
    }
    const blockId = WORLD.getBlock(world, target.x, target.y);
    if (blockId === null || blockId === CONFIG.blocks.air) {
      return;
    }
    const definition = WORLD.getBlockDef(blockId);
    const aliases = {
      grass: "dirt",
      stone: "cobblestone",
      coalOre: "coal",
      ironOre: "raw_iron",
      craftingTable: "crafting_table",
      stoneBricks: "stone_bricks"
    };
    let itemId = definition.drop;
    if (!itemId || !CONFIG.items[itemId]) {
      itemId = aliases[definition.key] || definition.key;
    }
    if (!CONFIG.items[itemId]) {
      return;
    }
    let found = -1;
    for (let index = 0; index < CONFIG.inventorySize; index += 1) {
      const slot = inventory.slots[index];
      if (slot && slot.id === itemId) {
        found = index;
        if (index < CONFIG.hotbarSize) {
          break;
        }
      }
    }
    if (found < 0) {
      notify("No " + CONFIG.items[itemId].name + " in your pack.", "warn", 1600);
      return;
    }
    if (found >= CONFIG.hotbarSize) {
      const free = inventory.slots.slice(0, CONFIG.hotbarSize).findIndex(function (slot) { return !slot; });
      if (free >= 0) {
        inventory.slots[free] = inventory.slots[found];
        inventory.slots[found] = null;
        found = free;
        refreshUIAfterInventory();
      } else {
        found = -1;
      }
    }
    if (found >= 0) {
      selected = found;
      ui.updateHotbar(snapshot(), true);
      AUDIO.play("ui");
    } else {
      notify("Free a hotbar slot to pick that block.", "warn", 1800);
    }
  }

  function notify(message, tone, duration) {
    if (noticeCooldown > 0) {
      return;
    }
    noticeCooldown = 0.7;
    ui.toast(message, tone, duration || 1900);
  }

  function mineDelayFor(blockId) {
    const definition = WORLD.getBlockDef(blockId);
    const item = selectedItem();
    const tool = item && item.tool ? item.tool : null;
    const matches = !!(tool && definition.tool && tool.type === definition.tool);
    const tierOk = definition.tier === 0 || (matches && tool.tier >= definition.tier);
    if (!tierOk) {
      return { ok: false, duration: Infinity, message: toolRequiredMessage(definition) };
    }
    const speed = matches ? tool.speed : 1;
    return { ok: true, duration: Math.max(0.08, definition.hardness / speed), message: "" };
  }

  function toolRequiredMessage(definition) {
    if (definition.tier >= 2) {
      return definition.name + " needs a stone pickaxe or better.";
    }
    if (definition.tier === 1) {
      return definition.name + " needs a wooden pickaxe or better.";
    }
    return "That block cannot be mined.";
  }

  function updateMining(dt) {
    if (!leftDown || !hover.visible || !hover.inReach || ui.isOverlayOpen()) {
      mining = null;
      return;
    }
    const blockId = WORLD.getBlock(world, hover.x, hover.y);
    if (blockId === null || blockId === CONFIG.blocks.air) {
      mining = null;
      return;
    }
    if (WORLD.isProtected(world, hover.x, hover.y)) {
      if (!mining || mining.x !== hover.x || mining.y !== hover.y) {
        notify("The world floor is unbreakable.", "warn", 1600);
      }
      mining = { x: hover.x, y: hover.y, progress: 0, duration: 1 };
      return;
    }
    const delay = mineDelayFor(blockId);
    if (!delay.ok) {
      if (!mining || mining.x !== hover.x || mining.y !== hover.y) {
        notify(delay.message, "warn", 2000);
      }
      mining = { x: hover.x, y: hover.y, progress: 0, duration: 1 };
      return;
    }
    if (!mining || mining.x !== hover.x || mining.y !== hover.y) {
      mining = { x: hover.x, y: hover.y, progress: 0, duration: delay.duration };
    }
    mining.duration = delay.duration;
    mining.progress += dt / delay.duration;
    swingPhase = (swingPhase + dt * 6.5) % 1;
    lastMineSound += dt;
    if (lastMineSound > 0.19) {
      lastMineSound = 0;
      const definition = WORLD.getBlockDef(blockId);
      AUDIO.play("mine", { pitch: definition.solid ? 155 : 220, volume: 0.045 });
      spawnBreakParticles(hover.x, hover.y, blockId, 1);
    }
    if (mining.progress >= 1) {
      if (breakBlock(hover.x, hover.y)) {
        mining = null;
        swingPhase = 0;
      } else {
        mining.progress = 0.94;
      }
    }
  }

  function updateHover() {
    if (!playing || dead || ui.isOverlayOpen() || !mouse.inside) {
      hover.visible = false;
      return;
    }
    const point = renderer.screenToWorld(mouse.x, mouse.y, camera);
    const tx = Math.floor(point.x);
    const ty = Math.floor(point.y);
    if (tx < 0 || ty < 0 || tx >= world.width || ty >= world.height) {
      hover.visible = false;
      return;
    }
    const block = WORLD.getBlock(world, tx, ty);
    const inReach = PHYSICS.inReach(player, tx, ty, CONFIG.reach);
    const definition = WORLD.getBlockDef(block);
    const protectedBlock = WORLD.isProtected(world, tx, ty);
    const delay = block === CONFIG.blocks.air ? { ok: true, message: "" } : mineDelayFor(block);
    const canMine = block !== CONFIG.blocks.air && !protectedBlock && delay.ok;
    const canPlace = block === CONFIG.blocks.air && !protectedBlock;
    let reason = "";
    if (!inReach) {
      reason = "Out of reach";
    } else if (protectedBlock) {
      reason = "World floor";
    } else if (block !== CONFIG.blocks.air && !delay.ok) {
      reason = delay.message;
    }
    hover.visible = true;
    hover.x = tx;
    hover.y = ty;
    hover.inReach = inReach;
    hover.canMine = canMine;
    hover.canPlace = canPlace;
    hover.valid = inReach && (canMine || canPlace);
    hover.reason = reason;
  }

  function spawnBreakParticles(x, y, blockId, count) {
    const color = BLOCK_PARTICLES[blockId] || [150, 150, 150];
    for (let index = 0; index < count; index += 1) {
      const life = 0.35 + Math.random() * 0.55;
      particles.push({
        x: x + 0.2 + Math.random() * 0.6,
        y: y + 0.2 + Math.random() * 0.6,
        vx: (Math.random() - 0.5) * 4.2,
        vy: -Math.random() * 3.6 - 0.4,
        gravity: 16,
        life: life,
        maxLife: life,
        size: 0.05 + Math.random() * 0.08,
        color: color
      });
    }
    if (particles.length > 260) {
      particles.splice(0, particles.length - 260);
    }
  }

  function spawnEmber(x, y) {
    const life = 0.8 + Math.random() * 0.9;
    particles.push({
      x: x + 0.4 + Math.random() * 0.2,
      y: y + 0.1,
      vx: (Math.random() - 0.5) * 0.5,
      vy: -0.5 - Math.random() * 0.5,
      gravity: -0.3,
      life: life,
      maxLife: life,
      size: 0.035 + Math.random() * 0.035,
      color: [255, 148 + Math.floor(Math.random() * 70), 54]
    });
  }

  function updateParticles(dt) {
    for (let index = particles.length - 1; index >= 0; index -= 1) {
      const particle = particles[index];
      particle.life -= dt;
      if (particle.life <= 0) {
        particles.splice(index, 1);
        continue;
      }
      particle.vy += particle.gravity * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      if (WORLD.isSolid(world, Math.floor(particle.x), Math.floor(particle.y + 0.04))) {
        particle.vy = -Math.abs(particle.vy) * 0.22;
        particle.vx *= 0.6;
      }
    }
  }

  function inBounds(x, y) {
    return x >= 0 && y >= 0 && x < world.width && y < world.height;
  }

  function spawnTorchEmbers(dt) {
    emberTimer += dt;
    if (emberTimer < 0.22) {
      return;
    }
    emberTimer = 0;
    const centerX = Math.floor(player.x);
    const centerY = Math.floor(player.y);
    let spawned = 0;
    for (let y = centerY - 9; y <= centerY + 6 && spawned < 3; y += 1) {
      for (let x = centerX - 12; x <= centerX + 12 && spawned < 3; x += 1) {
        if (inBounds(x, y) && WORLD.getBlock(world, x, y) === CONFIG.blocks.torch) {
          spawnEmber(x, y);
          spawned += 1;
        }
      }
    }
  }

  function updateHealth(dt) {
    if (player.health <= 0) {
      return;
    }
    if (Date.now() - lastDamageAt > 11000 && player.health < CONFIG.maxHealth) {
      regenTimer += dt;
      if (regenTimer >= 4.2) {
        regenTimer = 0;
        PHYSICS.healPlayer(player, 1);
      }
    } else {
      regenTimer = 0;
    }
  }

  function hurt(amount, message) {
    const damage = PHYSICS.damagePlayer(player, amount);
    if (damage <= 0) {
      return;
    }
    lastDamageAt = Date.now();
    AUDIO.play("hurt");
    spawnBreakParticles(Math.floor(player.x), Math.floor(player.y - 0.5), CONFIG.blocks.stone, 4);
    if (player.health <= 0) {
      die();
    } else if (message) {
      ui.toast(message + " (-" + damage + ")", "danger", 1800);
    }
  }

  function die() {
    dead = true;
    playing = false;
    resetRuntimeInput();
    stats.deaths += 1;
    AUDIO.play("death");
    ui.showDeath(stats);
    markDirty();
    saveNow("death", true);
  }

  function respawn() {
    PHYSICS.respawnPlayer(player, world.spawn);
    dead = false;
    playing = true;
    lastDamageAt = 0;
    snapCamera();
    ui.closeAll();
    canvas.focus({ preventScroll: true });
    ui.toast("You wake at the meadow. Your pack came with you.", "good", 2600);
    markDirty();
    saveNow("respawn", true);
    ui.updateHUD(snapshot());
  }

  function frame(now) {
    const delta = lastFrame ? Math.min(0.05, (now - lastFrame) / 1000) : 1 / 60;
    lastFrame = now;
    if (playing && !dead && !ui.isOverlayOpen()) {
      simulate(delta);
    } else {
      swingPhase = Math.max(0, swingPhase - delta * 4);
    }
    renderer.draw(renderSnapshot());
    hudTimer += delta;
    minimapTimer += delta;
    saveLabelTimer += delta;
    if (hudTimer > 0.12) {
      hudTimer = 0;
      ui.updateHUD(snapshot());
    }
    if (minimapTimer > 0.22) {
      minimapTimer = 0;
      drawMinimap();
    }
    if (saveLabelTimer > 2) {
      saveLabelTimer = 0;
      refreshSaveLabel();
    }
    requestAnimationFrame(frame);
  }

  function simulate(dt) {
    noticeCooldown = Math.max(0, noticeCooldown - dt);
    timeOfDay += dt / CONFIG.dayLengthSeconds;
    if (timeOfDay >= 1) {
      timeOfDay -= 1;
      day += 1;
      stats.daysSurvived = day;
      ui.toast("Day " + day + " begins in the valley.", "good", 2400);
      markDirty();
    }
    input.left = !!keys.KeyA || !!keys.ArrowLeft;
    input.right = !!keys.KeyD || !!keys.ArrowRight;
    input.jump = !!keys.KeyW || !!keys.Space || !!keys.ArrowUp;
    input.sprint = !!keys.ShiftLeft || !!keys.ShiftRight;
    const previousX = player.x;
    const result = PHYSICS.stepPlayer(player, world, input, dt);
    if (result.jumped) {
      AUDIO.play("jump");
      stepTimer = 0;
    }
    if (result.landed) {
      const damage = PHYSICS.fallDamage(result.fallDistance);
      if (damage > 0) {
        hurt(damage, "The fall rattled your bones");
      }
      if (result.fallDistance > 1.2) {
        spawnBreakParticles(Math.floor(player.x), Math.floor(player.y - 0.2), CONFIG.blocks.dirt, 3);
      }
    }
    if (player.onGround && Math.abs(player.x - previousX) > 0.01) {
      stepTimer += dt;
      if (stepTimer > 0.3) {
        stepTimer = 0;
        AUDIO.play("step");
      }
    } else {
      stepTimer = 0;
    }
    updateMining(dt);
    updateHover();
    updateParticles(dt);
    spawnTorchEmbers(dt);
    updateHealth(dt);
    updateCamera(dt);
    if (player.y > world.height + 2) {
      die();
      return;
    }
    if (dirty || lastSaveAt === 0) {
      saveDebounce += dt;
      autosaveTimer += dt;
      if (saveDebounce > 1.8 && storage) {
        saveNow("auto", true);
      } else if (autosaveTimer > CONFIG.autosaveSeconds && storage) {
        saveNow("auto", true);
      }
    }
    if (!storage && playing && saveDebounce > 8) {
      saveDebounce = 0;
      ui.setSaveState("Session only", "error");
    }
  }

  function renderSnapshot() {
    return {
      world: world,
      player: player,
      camera: camera,
      timeOfDay: timeOfDay,
      dayFactor: WORLD.dayFactor(timeOfDay),
      hover: hover,
      mining: mining,
      particles: particles,
      swing: swingPhase,
      heldItem: selectedItemId()
    };
  }

  function drawMinimap() {
    if (!ui) {
      return;
    }
    renderer.drawMinimap(document.getElementById("minimap"), {
      world: world,
      player: player,
      timeOfDay: timeOfDay,
      dayFactor: WORLD.dayFactor(timeOfDay)
    });
  }

  function craftRecipe(recipeId) {
    const recipe = CONFIG.recipes.find(function (item) { return item.id === recipeId; });
    if (!recipe) {
      return;
    }
    const stations = currentStations();
    const result = INVENTORY.craftRecipe(inventory, recipe, stations);
    if (!result.ok) {
      AUDIO.play("error");
      ui.toast(result.reason || "That recipe is not available.", "warn", 2200);
      return;
    }
    stats.itemsCrafted += 1;
    const output = CONFIG.items[recipe.output.id];
    if (recipe.output.id === "planks") {
      completeTask("planks");
    } else if (recipe.output.id === "crafting_table") {
      completeTask("table");
    } else if (recipe.output.id === "wood_pickaxe") {
      completeTask("wood_pickaxe");
    } else if (recipe.output.id === "stone_pickaxe") {
      completeTask("stone_pickaxe");
    }
    AUDIO.play("craft");
    refreshUIAfterInventory();
    markDirty();
    ui.toast("Crafted " + (output ? output.name : recipe.name) + (recipe.output.count > 1 ? " ×" + recipe.output.count : ""), "good", 1500);
  }

  function slotClick(index, button, shift) {
    if (index < 0 || index >= CONFIG.inventorySize) {
      return;
    }
    if (shift) {
      quickMove(index);
      return;
    }
    const slots = inventory.slots;
    const slot = slots[index];
    if (button === 2) {
      if (!heldStack && slot) {
        const half = Math.ceil(slot.count / 2);
        heldStack = { id: slot.id, count: half };
        slot.count -= half;
        if (slot.count <= 0) {
          slots[index] = null;
        }
      } else if (heldStack) {
        if (!slot) {
          slots[index] = { id: heldStack.id, count: 1 };
          heldStack.count -= 1;
        } else if (slot.id === heldStack.id && slot.count < CONFIG.items[slot.id].stack) {
          slot.count += 1;
          heldStack.count -= 1;
        } else {
          ui.toast("That stack cannot take this item.", "warn", 1500);
        }
        if (heldStack && heldStack.count <= 0) {
          heldStack = null;
        }
      }
    } else if (!heldStack) {
      if (slot) {
        heldStack = { id: slot.id, count: slot.count };
        slots[index] = null;
      }
    } else if (!slot) {
      slots[index] = heldStack;
      heldStack = null;
    } else if (slot.id === heldStack.id) {
      const limit = CONFIG.items[slot.id].stack;
      const moved = Math.min(limit - slot.count, heldStack.count);
      slot.count += moved;
      heldStack.count -= moved;
      if (heldStack.count <= 0) {
        heldStack = null;
      }
    } else {
      const temp = slot;
      slots[index] = heldStack;
      heldStack = temp;
    }
    AUDIO.play("ui");
    markDirty();
    ui.refreshInventory(snapshot(), heldStack);
    ui.updateHotbar(snapshot(), true);
  }

  function quickMove(index) {
    const slots = inventory.slots;
    const source = slots[index];
    if (!source) {
      return;
    }
    const targetStart = index < CONFIG.hotbarSize ? CONFIG.hotbarSize : 0;
    const targetEnd = index < CONFIG.hotbarSize ? CONFIG.inventorySize : CONFIG.hotbarSize;
    const limit = CONFIG.items[source.id].stack;
    let remaining = source.count;
    for (let target = targetStart; target < targetEnd && remaining > 0; target += 1) {
      const slot = slots[target];
      if (slot && slot.id === source.id && slot.count < limit) {
        const moved = Math.min(limit - slot.count, remaining);
        slot.count += moved;
        remaining -= moved;
      }
    }
    for (let target = targetStart; target < targetEnd && remaining > 0; target += 1) {
      if (!slots[target]) {
        const moved = Math.min(limit, remaining);
        slots[target] = { id: source.id, count: moved };
        remaining -= moved;
      }
    }
    if (remaining <= 0) {
      slots[index] = null;
    } else {
      source.count = remaining;
    }
    AUDIO.play("ui");
    markDirty();
    ui.refreshInventory(snapshot(), heldStack);
    ui.updateHotbar(snapshot(), true);
  }

  function toggleSound() {
    settings.muted = !settings.muted;
    AUDIO.setMuted(settings.muted);
    ui.setSoundLabels(settings.muted);
    markDirty();
    if (!settings.muted) {
      AUDIO.play("ui");
    }
    ui.toast(settings.muted ? "Sound muted." : "Sound on.", "info", 1400);
    if (storage) {
      saveNow("settings", true);
    }
  }

  function returnToTitle() {
    if (playing && !dead) {
      saveNow("title", true);
    }
    playing = false;
    dead = false;
    resetRuntimeInput();
    heldStack = null;
    ui.setHeld(null);
    ui.updateHUD(snapshot());
    const hasSave = !!storage && !!lastSaveAt;
    ui.showStart({
      hasSave: hasSave,
      seed: world.seed,
      savedAt: lastSaveAt,
      muted: settings.muted
    });
    if (hasSave) {
      ui.setSaveState("Saved " + relativeTime(lastSaveAt), "saved");
    }
    drawMinimap();
  }

  function startNewWorld(seed, back) {
    const actualSeed = Number(seed) >>> 0;
    const muted = settings.muted;
    SAVE.clearStorage(storage, CONFIG.saveKey);
    freshWorld(actualSeed);
    settings.muted = muted;
    AUDIO.setMuted(muted);
    playing = false;
    dead = false;
    resetRuntimeInput();
    snapCamera();
    ui.setHeld(null);
    ui.updateHUD(snapshot());
    ui.updateHotbar(snapshot(), true);
    const saved = saveNow("new", true);
    if (back === "pause") {
      beginPlay();
      ui.toast("A new valley is ready. Seed " + actualSeed + ".", "good", 3200);
    } else {
      ui.showStart({
        hasSave: !!saved,
        seed: world.seed,
        savedAt: lastSaveAt,
        muted: settings.muted
      });
      ui.toast("A new valley is ready. Seed " + actualSeed + ".", "good", 3200);
    }
    drawMinimap();
  }

  function newWorldRequest(back) {
    const seed = (Date.now() ^ Math.floor(Math.random() * 0xffffffff)) >>> 0;
    startNewWorld(seed, back);
  }

  const actions = {
    play: beginPlay,
    pause: pauseGame,
    resume: resumeGame,
    openInventory: openInventory,
    closeInventory: closeInventory,
    selectSlot: selectSlot,
    slotClick: slotClick,
    craft: craftRecipe,
    toggleSound: toggleSound,
    save: function () { saveNow("manual", false); },
    respawn: respawn,
    returnToTitle: returnToTitle,
    newWorld: newWorldRequest,
    isMuted: function () { return !!settings.muted; }
  };

  function handleKeyDown(event) {
    const tag = (event.target && event.target.tagName ? event.target.tagName : "").toLowerCase();
    const editable = tag === "input" || tag === "textarea" || tag === "select" || (event.target && event.target.isContentEditable);
    const screen = ui ? ui.currentScreen() : null;

    if ((event.ctrlKey || event.metaKey) && event.code === "KeyS") {
      event.preventDefault();
      if (ui && world) {
        saveNow("manual", false);
      }
      return;
    }

    if (event.code === "Escape") {
      event.preventDefault();
      if (!screen) {
        pauseGame();
      } else if (screen === "help") {
        ui.closeHelp();
      } else if (screen === "inventory") {
        closeInventory();
      } else if (screen === "pause") {
        resumeGame();
      } else if (screen === "confirm") {
        ui.cancelConfirmScreen();
      }
      return;
    }

    if (editable) {
      return;
    }

    if (screen === "start") {
      if (event.code === "Enter" || event.code === "Space") {
        event.preventDefault();
        beginPlay();
      }
      return;
    }

    if (screen === "confirm" || screen === "death") {
      return;
    }

    if (event.code === "KeyH" || event.key === "?") {
      if (screen === "pause") {
        event.preventDefault();
        ui.showHelp("pause");
      } else if (!screen && playing) {
        event.preventDefault();
        ui.showHelp("game");
      }
      return;
    }

    if (screen === "inventory") {
      if (event.code === "KeyE") {
        event.preventDefault();
        toggleInventory();
      }
      return;
    }
    if (screen === "help" || screen === "pause") {
      return;
    }

    if (!playing || dead) {
      return;
    }

    if (event.code === "KeyE") {
      event.preventDefault();
      toggleInventory();
      return;
    }
    if (event.code === "KeyM") {
      event.preventDefault();
      minimapVisible = !minimapVisible;
      ui.setMinimapVisible(minimapVisible);
      ui.toast(minimapVisible ? "Surface map shown." : "Surface map hidden.", "info", 1200);
      return;
    }
    if (event.code.indexOf("Digit") === 0) {
      const number = Number(event.code.slice(5));
      if (number >= 1 && number <= 9) {
        event.preventDefault();
        selectSlot(number - 1);
      }
      return;
    }
    if (["KeyA", "KeyD", "KeyW", "KeyS", "Space", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "ShiftLeft", "ShiftRight"].indexOf(event.code) >= 0) {
      event.preventDefault();
      keys[event.code] = true;
    }
  }

  function handleKeyUp(event) {
    if (keys[event.code]) {
      delete keys[event.code];
    }
  }

  function clearInput() {
    keys = Object.create(null);
    leftDown = false;
    input = { left: false, right: false, jump: false, sprint: false };
    mining = null;
  }

  function bindInput() {
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", clearInput);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        clearInput();
        if (playing && dirty) {
          saveNow("hidden", true);
        }
      }
    });
    window.addEventListener("beforeunload", function () {
      if (playing && dirty) {
        saveNow("exit", true);
      }
    });

    canvas.addEventListener("pointermove", function (event) {
      mouse.x = event.clientX;
      mouse.y = event.clientY;
      mouse.inside = true;
      updateHover();
    });
    canvas.addEventListener("pointerenter", function () {
      mouse.inside = true;
    });
    canvas.addEventListener("pointerleave", function () {
      mouse.inside = false;
      hover.visible = false;
      leftDown = false;
      mining = null;
    });
    canvas.addEventListener("pointerdown", function (event) {
      if (!playing || dead || ui.isOverlayOpen()) {
        return;
      }
      mouse.x = event.clientX;
      mouse.y = event.clientY;
      mouse.inside = true;
      AUDIO.ensureContext();
      canvas.focus({ preventScroll: true });
      if (event.button === 0) {
        leftDown = true;
        updateHover();
      } else if (event.button === 2) {
        event.preventDefault();
        updateHover();
        placeBlock(hover);
      } else if (event.button === 1) {
        event.preventDefault();
        updateHover();
        pickBlock(hover);
      }
    });
    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });
    window.addEventListener("pointerup", function (event) {
      if (event.button === 0) {
        leftDown = false;
        mining = null;
      }
    });
    canvas.addEventListener("wheel", function (event) {
      if (!playing || dead || ui.isOverlayOpen()) {
        return;
      }
      event.preventDefault();
      const direction = event.deltaY > 0 ? 1 : -1;
      selectSlot((selected + direction + CONFIG.hotbarSize) % CONFIG.hotbarSize);
    }, { passive: false });
    window.addEventListener("resize", function () {
      updateHover();
    });
    window.addEventListener("error", function (event) {
      setStatus("error", event.message || "runtime error");
      if (ui) {
        ui.toast("Runtime error: " + (event.message || "unknown"), "danger", 5000);
      }
    });
    window.addEventListener("unhandledrejection", function (event) {
      const message = event.reason && event.reason.message ? event.reason.message : String(event.reason);
      setStatus("error", message);
      if (ui) {
        ui.toast("Runtime error: " + message, "danger", 5000);
      }
    });
  }

  bindInput();
  boot();
})();
