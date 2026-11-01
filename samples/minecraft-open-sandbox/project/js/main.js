(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const PLAYER = window.SandboxPlayer;
  const MINING = window.SandboxMining;
  const INVENTORY = window.SandboxInventory;
  const CRAFTING = window.SandboxCrafting;
  const LIGHTING = window.SandboxLighting;
  const SAVE = window.SandboxSave;
  const AUDIO = window.SandboxAudio;
  const INPUT = window.SandboxInput;
  const RENDER = window.SandboxRender;
  const UI = window.SandboxUI;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const status = document.getElementById("status");
  const STEP = 1 / 60;
  const TILE = CONFIG.tileSize;

  const state = {
    world: null,
    player: null,
    inventory: null,
    time: { tick: CONFIG.dayLengthSeconds * 0.1, day: 1 },
    camera: { x: 0, y: 0 },
    light: null,
    skyLevel: CONFIG.skyDay,
    mining: MINING.createMining(),
    particles: [],
    mouseTile: null,
    textures: null,
    paused: false,
    dirty: false,
    storageNote: ""
  };

  let ui = null;
  let input = null;
  let audio = null;
  let storageInfo = null;
  let accumulator = 0;
  let lastName = 0;
  let jumpWasDown = false;
  let lastSavedAt = 0;
  let mineSoundClock = 0;
  let notifyClock = 0;
  let started = false;

  function setStatus(value, text) {
    status.dataset.state = value;
    status.title = text || value;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function updateCamera(dt, snap) {
    const worldPixelWidth = state.world.width * TILE;
    const worldPixelHeight = state.world.height * TILE;
    const lookAhead = (state.player.facing || 1) * TILE * 1.5;
    const targetX = clamp(
      state.player.x * TILE - CONFIG.viewWidth / 2 + lookAhead,
      0,
      Math.max(0, worldPixelWidth - CONFIG.viewWidth)
    );
    const targetY = clamp(
      state.player.y * TILE - CONFIG.viewHeight / 2 - TILE * 1.5,
      0,
      Math.max(0, worldPixelHeight - CONFIG.viewHeight)
    );
    if (snap) {
      state.camera.x = targetX;
      state.camera.y = targetY;
      return;
    }
    const factor = 1 - Math.exp(-7 * dt);
    state.camera.x += (targetX - state.camera.x) * factor;
    state.camera.y += (targetY - state.camera.y) * factor;
  }

  function computeMouseTile() {
    const pointer = input.state;
    if (!pointer.inside) {
      return null;
    }
    const tx = Math.floor((pointer.mouseX + state.camera.x) / TILE);
    const ty = Math.floor((pointer.mouseY + state.camera.y) / TILE);
    if (tx < 0 || ty < 0 || tx >= state.world.width || ty >= state.world.height) {
      return null;
    }
    return {
      x: tx,
      y: ty,
      reachable: MINING.targetWithinReach(state.world, state.player, tx, ty)
    };
  }

  function spawnParticles(tileX, tileY, blockId, amount) {
    const palette = CONFIG.palette[blockId] || { base: "#999999" };
    const count = amount || 9;
    for (let i = 0; i < count; i += 1) {
      const life = 0.35 + Math.random() * 0.45;
      state.particles.push({
        x: tileX + 0.15 + Math.random() * 0.7,
        y: tileY + 0.15 + Math.random() * 0.7,
        vx: (Math.random() - 0.5) * 3.4,
        vy: -1.2 - Math.random() * 2.6,
        life: life,
        maxLife: life,
        color: Math.random() > 0.4 ? palette.base : palette.light || palette.base,
        size: 2 + Math.random() * 2
      });
    }
    if (state.particles.length > 260) {
      state.particles.splice(0, state.particles.length - 260);
    }
  }

  function updateParticles(dt) {
    for (let i = state.particles.length - 1; i >= 0; i -= 1) {
      const particle = state.particles[i];
      particle.life -= dt;
      if (particle.life <= 0) {
        state.particles.splice(i, 1);
        continue;
      }
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      particle.vy += 18 * dt;
      particle.vx *= 0.98;
    }
  }

  function recomputeLight() {
    state.skyLevel = LIGHTING.skyLevelForTime(state.time.tick / CONFIG.dayLengthSeconds);
    state.light = LIGHTING.computeLight(state.world, state.skyLevel);
  }

  function notify(text, duration) {
    const now = performance.now();
    if (now - notifyClock < 700) {
      return;
    }
    notifyClock = now;
    ui.toast(text, duration);
  }

  function tileHitsPlayer(tx, ty) {
    const player = state.player;
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return tx < right && tx + 1 > left && ty < bottom && ty + 1 > top;
  }

  function breakBlock(tx, ty, rule) {
    const blockId = WORLD.getBlock(state.world, tx, ty);
    const drop = rule.drop;
    WORLD.setBlock(state.world, tx, ty, CONFIG.blocks.air);
    if (drop) {
      INVENTORY.add(state.inventory, drop, 1);
    }
    spawnParticles(tx, ty, blockId, 10);
    audio.play("break");
    state.dirty = true;
    recomputeLight();
    ui.updateHotbar(state.inventory);
    if (ui.current() === "craft") {
      ui.refreshCraft(state.inventory);
    }
    if (drop) {
      ui.flashSave(CONFIG.itemNames[drop] + " +1");
    }
  }

  function tryPlace() {
    const target = state.mouseTile;
    const item = INVENTORY.placeableSelected(state.inventory);
    if (!item) {
      notify("No block selected in the hotbar.");
      return;
    }
    if (!target) {
      return;
    }
    if (!target.reachable) {
      notify("That block is out of reach.");
      return;
    }
    const existing = WORLD.getBlock(state.world, target.x, target.y);
    if (existing !== CONFIG.blocks.air && existing !== CONFIG.blocks.water) {
      return;
    }
    if (tileHitsPlayer(target.x, target.y)) {
      notify("Step back before placing there.");
      return;
    }
    const blockId = CONFIG.placeable[item];
    WORLD.setBlock(state.world, target.x, target.y, blockId);
    INVENTORY.remove(state.inventory, item, 1);
    spawnParticles(target.x, target.y, blockId, 5);
    audio.play("place");
    state.dirty = true;
    recomputeLight();
    ui.updateHotbar(state.inventory);
    if (ui.current() === "craft") {
      ui.refreshCraft(state.inventory);
    }
  }

  function updateMining(dt) {
    const target = state.mouseTile;
    const holding = input.state.leftButton && !ui.isOpen();
    if (!target) {
      MINING.resetMining(state.mining);
      return;
    }
    const tools = INVENTORY.tools(state.inventory);
    const result = MINING.updateMining(
      state.mining,
      state.world,
      state.player,
      target.x,
      target.y,
      tools,
      dt,
      holding
    );
    if (result.active) {
      mineSoundClock += dt;
      if (mineSoundClock > 0.18) {
        mineSoundClock = 0;
        audio.play("dig");
      }
    }
    if (result.complete) {
      breakBlock(target.x, target.y, result.rule);
    } else if (holding && result.rule) {
      if (result.rule.reason === "tool") {
        notify("That needs a pickaxe. Craft one with E.", 2600);
      } else if (result.rule.reason === "reach") {
        notify("Too far away. Move closer.", 2000);
      } else if (result.rule.reason === "unbreakable") {
        notify("That block cannot be broken.", 2200);
      }
    }
  }

  function selectSlot(index) {
    if (INVENTORY.selectSlot(state.inventory, index)) {
      ui.updateHotbar(state.inventory);
      audio.play("click");
    }
  }

  function cycleSlot(direction) {
    INVENTORY.cycleSlot(state.inventory, direction);
    ui.updateHotbar(state.inventory);
    audio.play("click");
  }

  function saveGame(manual) {
    const result = SAVE.saveGame(storageInfo.storage, state);
    if (result.ok) {
      state.dirty = false;
      lastSavedAt = Date.now();
      ui.flashSave(manual ? "World saved" : "Autosaved");
      if (manual) {
        audio.play("save");
        ui.toast("World saved to this browser.", 2000);
      }
      return true;
    }
    ui.toast("Could not save: " + result.error, 3200);
    return false;
  }

  function openHelp() {
    state.mouseTile = null;
    ui.showHelp();
  }

  function openPause() {
    state.mouseTile = null;
    ui.updatePause(state, storageInfo.persistent, "Your world is paused.");
    ui.showPause();
  }

  function openCraft() {
    state.mouseTile = null;
    ui.showCraft(state.inventory);
  }

  function closeOverlay() {
    ui.hidePanel();
    jumpWasDown = input.state.jump;
    input.consumeJumpPressed();
    audio.play("click");
  }

  function craftRecipe(recipeId) {
    const recipe = CRAFTING.recipeById(recipeId);
    const result = CRAFTING.craft(state.inventory, recipe);
    if (!result.ok) {
      audio.play("error");
      ui.toast("Not enough materials yet.", 1800);
      return;
    }
    audio.play("craft");
    state.dirty = true;
    ui.updateHotbar(state.inventory);
    ui.refreshCraft(state.inventory);
    const yields = Object.keys(recipe.yield)
      .map(function (key) {
        return (CONFIG.itemNames[key] || key) + " x" + recipe.yield[key];
      })
      .join(", ");
    ui.toast("Crafted " + yields + ".", 2200);
  }

  function startNewWorld(seed) {
    const newSeed = seed === undefined ? (Math.random() * 0xffffffff) >>> 0 : Number(seed) >>> 0;
    state.world = WORLD.createWorld(newSeed);
    const spawn = WORLD.getSpawn(state.world);
    state.player = PLAYER.createPlayer(spawn.x + 0.5, spawn.y);
    state.inventory = INVENTORY.createInventory();
    state.time = { tick: CONFIG.dayLengthSeconds * 0.1, day: 1 };
    MINING.resetMining(state.mining);
    state.particles = [];
    state.mouseTile = null;
    state.dirty = true;
    recomputeLight();
    updateCamera(0, true);
    ui.updateHotbar(state.inventory);
    ui.updateHud(state);
    ui.hidePanel();
    saveGame(false);
    ui.toast("New world generated. Seed " + newSeed + ".", 3000);
    setStatus("ready", "ready");
  }

  function handleKey(code) {
    audio.unlock();
    if (code === "KeyE") {
      if (ui.current() === "craft") {
        closeOverlay();
      } else if (!ui.isOpen()) {
        openCraft();
      }
      return;
    }
    if (code === "KeyH" || code === "F1") {
      if (ui.current() === "help") {
        closeOverlay();
      } else if (!ui.isOpen()) {
        openHelp();
      }
      return;
    }
    if (code === "Escape") {
      if (ui.isOpen()) {
        closeOverlay();
      } else {
        openPause();
      }
      return;
    }
    if (code === "KeyM") {
      const muted = audio.toggleMute();
      ui.toast(muted ? "Audio muted." : "Audio on.", 1400);
      return;
    }
    const digit = /^Digit([1-8])$/.exec(code);
    if (digit) {
      selectSlot(Number(digit[1]) - 1);
    }
  }

  function update(dt) {
    state.time.tick += dt;
    if (state.time.tick >= CONFIG.dayLengthSeconds) {
      state.time.tick -= CONFIG.dayLengthSeconds;
      state.time.day += 1;
    }
    const skyLevel = LIGHTING.skyLevelForTime(state.time.tick / CONFIG.dayLengthSeconds);
    if (skyLevel !== state.skyLevel) {
      state.skyLevel = skyLevel;
      state.light = LIGHTING.computeLight(state.world, state.skyLevel);
    }

    const jumpHeld = input.state.jump;
    const jumpPressed = input.consumeJumpPressed() || (jumpHeld && !jumpWasDown);
    jumpWasDown = jumpHeld;
    const events = PLAYER.stepPlayer(
      state.player,
      state.world,
      {
        left: input.state.left,
        right: input.state.right,
        jump: jumpHeld,
        jumpPressed: jumpPressed
      },
      dt
    );
    for (let i = 0; i < events.length; i += 1) {
      const event = events[i];
      if (event.type === "jump") {
        state.jumpCount = (state.jumpCount || 0) + 1;
        audio.play("jump");
      } else if (event.type === "land") {
        audio.play("land");
        spawnParticles(Math.floor(state.player.x), Math.floor(state.player.y), CONFIG.blocks.dirt, 4);
      } else if (event.type === "fell") {
        PLAYER.respawn(state.world, state.player);
        updateCamera(0, true);
        ui.toast("You fell out of the world and returned to spawn.", 2400);
      }
    }

    updateCamera(dt);
    state.mouseTile = computeMouseTile();

    updateMining(dt);

    if (input.state.rightButton) {
      input.consumeRightButton();
      if (!ui.isOpen()) {
        tryPlace();
      }
    }

    updateParticles(dt);

    if (state.dirty && Date.now() - lastSavedAt > CONFIG.autosaveSeconds * 1000) {
      saveGame(false);
    }

    ui.updateHud(state);
  }

  function render() {
    state.mouseTile = ui.isOpen() ? null : computeMouseTile();
    RENDER.renderFrame(ctx, {
      world: state.world,
      player: state.player,
      camera: state.camera,
      time: state.time,
      light: state.light,
      mining: state.mining,
      particles: state.particles,
      mouseTile: state.mouseTile,
      textures: state.textures
    });
  }

  function loop(now) {
    const raw = lastName ? (now - lastName) / 1000 : 0;
    lastName = now;
    const dt = Math.min(0.1, Math.max(0, raw));
    if (!ui.isOpen()) {
      accumulator += dt;
      let steps = 0;
      while (accumulator >= STEP && steps < 5) {
        update(STEP);
        accumulator -= STEP;
        steps += 1;
      }
    }
    render();
    window.requestAnimationFrame(loop);
  }

  function boot() {
    storageInfo = SAVE.resolveStorage();
    const loaded = SAVE.loadGame(storageInfo.storage);
    if (loaded.ok) {
      state.world = SAVE.worldFromSnapshot(loaded.snapshot);
      const saved = loaded.snapshot;
      state.player = PLAYER.createPlayer(saved.player.x, saved.player.y);
      state.player.vx = saved.player.vx;
      state.player.vy = saved.player.vy;
      state.player.facing = saved.player.facing >= 0 ? 1 : -1;
      state.inventory = INVENTORY.createInventory(saved.inventory.items, saved.inventory.selected);
      state.time = { tick: saved.time.tick, day: saved.time.day };
    } else {
      state.world = WORLD.createWorld((Math.random() * 0xffffffff) >>> 0);
      const spawn = WORLD.getSpawn(state.world);
      state.player = PLAYER.createPlayer(spawn.x + 0.5, spawn.y);
      state.inventory = INVENTORY.createInventory();
      state.time = { tick: CONFIG.dayLengthSeconds * 0.1, day: 1 };
    }
    state.textures = RENDER.createTextures();
    recomputeLight();
    updateCamera(0, true);
    ctx.imageSmoothingEnabled = false;

    audio = AUDIO.createAudio();
    ui = UI.buildUI({
      onSelect: selectSlot,
      onCraft: craftRecipe,
      onResume: closeOverlay,
      onSave: function () {
        if (saveGame(true)) {
          ui.updatePause(state, storageInfo.persistent, "Saved just now.");
        }
      },
      onNewWorld: function () {
        startNewWorld();
      }
    });
    input = INPUT.createInput(canvas, {
      onKeyDown: handleKey,
      onWheel: cycleSlot
    });

    if (!loaded.ok && !loaded.missing) {
      ui.toast("The old save could not be read; a fresh world was created.", 4200);
    } else if (loaded.ok) {
      ui.toast("Welcome back. Your world was restored.", 2600);
    } else {
      ui.toast("New world. Hold left-click on the tree to gather wood.", 5200);
    }
    if (!storageInfo.persistent) {
      ui.toast("Browser storage is unavailable; progress will last for this session only.", 5200);
    }

    ui.updateHotbar(state.inventory);
    ui.updateHud(state);
    render();
    setStatus("ready", "ready");

    const sandbox = {
      ready: true,
      state: state,
      config: CONFIG,
      storagePersistent: storageInfo.persistent,
      get world() {
        return state.world;
      },
      get player() {
        return state.player;
      },
      get inventory() {
        return state.inventory;
      },
      get inputState() {
        return {
          left: input.state.left,
          right: input.state.right,
          jump: input.state.jump,
          jumpPressed: input.state.jumpPressed,
          leftButton: input.state.leftButton,
          rightButton: input.state.rightButton
        };
      },
      get jumpCount() {
        return state.jumpCount || 0;
      },
      get mouseTile() {
        return state.mouseTile;
      },
      get miningState() {
        return {
          x: state.mining.x,
          y: state.mining.y,
          progress: state.mining.progress,
          active: state.mining.active
        };
      },
      get playerInfo() {
        return { x: state.player.x, y: state.player.y, onGround: state.player.onGround, facing: state.player.facing };
      },
      get camera() {
        return { x: state.camera.x, y: state.camera.y };
      },
      save: function () {
        return saveGame(true);
      },
      newWorld: function (seed) {
        startNewWorld(seed);
        return state.world.seed;
      },
      setTimeOfDay: function (fraction) {
        const t = ((Number(fraction) % 1) + 1) % 1;
        state.time.tick = t * CONFIG.dayLengthSeconds;
        recomputeLight();
        state.mouseTile = null;
        render();
        ui.updateHud(state);
        return state.skyLevel;
      },
      openPause: openPause,
      openCraft: openCraft,
      tileToClient: function (tileX, tileY) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = rect.width / canvas.width;
        const scaleY = rect.height / canvas.height;
        return {
          x: rect.left + ((tileX + 0.5) * TILE - state.camera.x) * scaleX,
          y: rect.top + ((tileY + 0.5) * TILE - state.camera.y) * scaleY
        };
      }
    };
    window.__sandbox = sandbox;

    window.addEventListener("error", function (event) {
      setStatus("error", event.message || "runtime error");
    });
    window.addEventListener("unhandledrejection", function (event) {
      setStatus("error", String(event.reason));
    });
    window.addEventListener("beforeunload", function () {
      if (state.dirty) {
        saveGame(false);
      }
    });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden" && state.dirty) {
        saveGame(false);
      }
    });

    started = true;
    window.requestAnimationFrame(loop);
  }

  try {
    boot();
  } catch (error) {
    setStatus("error", error && error.message ? error.message : String(error));
    throw error;
  }
})();
