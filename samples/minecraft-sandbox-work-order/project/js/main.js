(function () {
  "use strict";

  const config = window.SandboxConfig;
  const RNG = window.SandboxRng;
  const WORLD = window.SandboxWorld;
  const PLAYER = window.SandboxPlayer;
  const CAMERA = window.SandboxCamera;
  const INTERACTION = window.SandboxInteraction;
  const DAYNIGHT = window.SandboxDayNight;
  const STORAGE = window.SandboxStorage;
  const AUDIO = window.SandboxAudio;
  const UI = window.SandboxUi;
  const RENDER = window.SandboxRender;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d", { alpha: false });
  const status = document.getElementById("status");
  const hudCoords = document.getElementById("hud-coords");
  const hudTime = document.getElementById("hud-time");
  const hudDepth = document.getElementById("hud-depth");
  const hudTarget = document.getElementById("hud-target");
  const hotbar = document.getElementById("hotbar");
  const toasts = document.getElementById("toasts");
  const seedForm = document.getElementById("seed-form");
  const seedInput = document.getElementById("seed-input");
  const seedRandom = document.getElementById("seed-random");
  const muteButton = document.getElementById("mute");
  const pauseButton = document.getElementById("pause");
  const helpButton = document.getElementById("help");
  const helpOverlay = document.getElementById("help-overlay");
  const helpClose = document.getElementById("help-close");
  const helpList = document.getElementById("help-list");
  const pauseOverlay = document.getElementById("pause-overlay");
  const resumeButton = document.getElementById("resume");

  const view = { width: config.viewWidth, height: config.viewHeight };
  const store = STORAGE.createStore();
  const savedSettings = store.loadSettings();
  const audio = AUDIO.createAudioBoard({ muted: savedSettings.muted });
  const input = { left: false, right: false, jump: false };
  const pointer = { x: view.width / 2, y: view.height / 2, inside: false };
  const mining = INTERACTION.createMiningState();
  const particles = [];
  const reduceQuery =
    typeof window.matchMedia === "function" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  let world = null;
  let player = null;
  let inventory = null;
  let camera = CAMERA.createCamera();
  let timeOfDay = config.startTimeOfDay;
  let paused = false;
  let muted = Boolean(savedSettings.muted);
  let helpOpen = false;
  let pausedByHelp = false;
  let reducedMotion = UI.prefersReducedMotion(reduceQuery ? window.matchMedia.bind(window) : undefined);
  let hovered = null;
  let hoverValid = false;
  let miningActive = false;
  let lastTimestamp = 0;
  let autosaveTimer = 0;
  let frameCount = 0;
  let booted = false;

  function setStatus(state, note) {
    status.dataset.state = state;
    status.title = note || state;
  }

  function toast(kind, detail) {
    const message = UI.toastMessage(kind, detail);
    if (!message) {
      return;
    }
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    toasts.appendChild(node);
    window.setTimeout(function () {
      node.classList.add("is-leaving");
      window.setTimeout(function () {
        if (node.parentNode) {
          node.parentNode.removeChild(node);
        }
      }, 240);
    }, 2400);
  }

  function updateHud() {
    if (!world || !player) {
      return;
    }
    const surface = RENDER.surfaceFor(world);
    const surfaceY = surface ? surface[Math.max(0, Math.min(world.width - 1, Math.floor(player.x)))] : null;
    hudCoords.textContent = UI.formatCoords(player);
    hudDepth.textContent = UI.formatDepth(player, surfaceY);
    hudTime.textContent = DAYNIGHT.labelOf(timeOfDay);
    hudTime.dataset.phase = DAYNIGHT.phaseOf(timeOfDay);
    if (hovered) {
      const block = WORLD.getBlock(world, hovered.x, hovered.y);
      if (block === config.blocks.air) {
        hudTarget.textContent = "Air";
      } else {
        const name = config.blockNames[block] || "Block";
        hudTarget.textContent = name + (INTERACTION.inReach(player, hovered.x, hovered.y, config.reach) ? "" : " · far");
      }
    } else {
      hudTarget.textContent = "—";
    }
  }

  function refreshHotbar() {
    if (!inventory) {
      return;
    }
    const model = INTERACTION.hotbarModel(inventory);
    const slots = hotbar.querySelectorAll(".slot");
    for (let index = 0; index < slots.length; index += 1) {
      const slot = slots[index];
      const entry = model[index];
      if (!entry) {
        continue;
      }
      slot.dataset.block = config.blockNames[entry.block]
        ? config.blockNames[entry.block].toLowerCase()
        : slot.dataset.block;
      slot.title = entry.name + " (" + entry.digit + ")";
      const count = slot.querySelector(".slot-count");
      if (count) {
        count.textContent = UI.formatCount(entry.count);
        count.classList.toggle("is-empty", entry.count <= 0);
      }
      slot.classList.toggle("is-selected", entry.selected);
      slot.setAttribute("aria-checked", entry.selected ? "true" : "false");
    }
  }

  function syncMuteButton() {
    muteButton.setAttribute("aria-pressed", muted ? "true" : "false");
    muteButton.title = muted ? "Unmute sound (M)" : "Mute sound (M)";
    muteButton.classList.toggle("is-active", muted);
    const glyph = muteButton.querySelector("span[aria-hidden]");
    if (glyph) {
      glyph.textContent = muted ? "✕" : "♪";
    }
  }

  function syncPauseButton() {
    pauseButton.setAttribute("aria-pressed", paused ? "true" : "false");
    pauseButton.classList.toggle("is-active", paused && !helpOpen);
    pauseOverlay.hidden = !paused || helpOpen;
  }

  function selectSlot(index) {
    INTERACTION.selectSlot(inventory, index, config.hotbar.length);
    audio.play("select");
    refreshHotbar();
    updateTargeting();
  }

  function cycleSlot(delta) {
    INTERACTION.cycleSlot(inventory, delta, config.hotbar.length);
    audio.play("select");
    refreshHotbar();
    updateTargeting();
  }

  function togglePause(force) {
    paused = typeof force === "boolean" ? force : !paused;
    if (paused) {
      miningActive = false;
      mining.cell = null;
      mining.progress = 0;
      input.left = false;
      input.right = false;
      input.jump = false;
      save(false);
    }
    syncPauseButton();
    updateHud();
  }

  function toggleHelp(force) {
    const next = typeof force === "boolean" ? force : !helpOpen;
    if (next === helpOpen) {
      return;
    }
    helpOpen = next;
    helpOverlay.hidden = !helpOpen;
    if (helpOpen) {
      // Reading the controls should never cost the player their footing: freeze
      // the simulation while the dialog is open and restore the exact state after.
      pausedByHelp = !paused;
      if (pausedByHelp) {
        paused = true;
        miningActive = false;
        mining.cell = null;
        mining.progress = 0;
        input.left = false;
        input.right = false;
        input.jump = false;
      }
      syncPauseButton();
      helpClose.focus();
    } else {
      if (pausedByHelp) {
        paused = false;
        pausedByHelp = false;
      }
      syncPauseButton();
      helpButton.focus();
    }
  }

  function toggleMute() {
    muted = !muted;
    audio.setMuted(muted);
    store.saveSettings({ muted: muted });
    syncMuteButton();
    toast(muted ? "muted" : "unmuted");
    if (!muted) {
      audio.play("select");
    }
  }

  function snapCamera() {
    camera = CAMERA.createCamera();
    if (!world || !player) {
      return camera;
    }
    const target = CAMERA.targetCamera(player, world, view, config.tileSize);
    camera.x = target.x;
    camera.y = target.y;
    return camera;
  }

  function respawn() {
    const spawn = WORLD.findSpawn(world);
    player = PLAYER.createPlayer(spawn.x, spawn.y);
    snapCamera();
    toast("reset");
    save(false);
  }

  function overlapAnySolid(candidate) {
    const half = candidate.width / 2;
    const left = Math.floor(candidate.x - half);
    const right = Math.floor(candidate.x + half);
    const top = Math.floor(candidate.y - candidate.height);
    const bottom = Math.floor(candidate.y);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (WORLD.isSolid(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  function seedWorld(seed, options) {
    const settings = options || {};
    world = WORLD.createWorld(seed);
    const spawn = WORLD.findSpawn(world);
    player = PLAYER.createPlayer(spawn.x, spawn.y);
    inventory = INTERACTION.createInventory();
    camera = CAMERA.createCamera();
    particles.length = 0;
    miningActive = false;
    mining.cell = null;
    mining.progress = 0;
    if (!settings.keepTime) {
      timeOfDay = config.startTimeOfDay;
    }
    seedInput.value = String(world.seed);
    seedInput.removeAttribute("aria-invalid");
    snapCamera();
    refreshHotbar();
    updateHud();
    if (settings.announce) {
      toast(settings.announce, String(world.seed));
    }
  }

  function loadSaved() {
    const result = store.loadGame();
    if (!result.ok) {
      if (result.reason === "corrupt") {
        toast("corrupt");
      } else if (result.reason === "unavailable") {
        toast("unavailable");
      }
      seedWorld(config.seed);
      return;
    }
    let restoredWorld = null;
    try {
      restoredWorld = WORLD.deserializeWorld(result.state.worldText);
    } catch (error) {
      toast("corrupt");
      seedWorld(config.seed);
      return;
    }
    world = restoredWorld;
    player = PLAYER.createPlayer(result.state.player.x, result.state.player.y);
    if (overlapAnySolid(player)) {
      const spawn = WORLD.findSpawn(world);
      player = PLAYER.createPlayer(spawn.x, spawn.y);
    }
    inventory = INTERACTION.createInventory();
    Object.keys(result.state.inventory.counts).forEach(function (key) {
      inventory.counts[key] = result.state.inventory.counts[key];
    });
    INTERACTION.selectSlot(inventory, result.state.inventory.selected, config.hotbar.length);
    timeOfDay = DAYNIGHT.normalizeTime(result.state.timeOfDay);
    seedInput.value = String(world.seed);
    snapCamera();
    refreshHotbar();
    updateHud();
    toast("loaded");
  }

  function save(announce) {
    if (!world || !player || !inventory) {
      return;
    }
    const result = store.saveGame({
      seed: world.seed,
      worldText: WORLD.serializeWorld(world),
      player: { x: player.x, y: player.y },
      inventory: { counts: inventory.counts, selected: inventory.selected },
      timeOfDay: timeOfDay
    });
    if (!result.ok) {
      if (result.reason === "unavailable" && announce) {
        toast("unavailable");
      }
      return;
    }
    if (announce) {
      toast("saved");
    }
  }

  function applySeed(text) {
    const parsed = UI.parseSeedInput(text);
    if (!parsed.ok) {
      seedInput.setAttribute("aria-invalid", "true");
      toast("denied", parsed.message);
      seedInput.focus();
      seedInput.select();
      return false;
    }
    seedWorld(parsed.seed, { announce: "seeded" });
    save(false);
    return true;
  }

  function randomSeed() {
    const seed = Math.floor(Math.random() * 4294967295) >>> 0;
    seedWorld(seed, { announce: "regenerated" });
    save(false);
  }

  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = rect.width ? config.viewWidth / rect.width : 1;
    const scaleY = rect.height ? config.viewHeight / rect.height : 1;
    return {
      x: (event.clientX - rect.left) * scaleX,
      y: (event.clientY - rect.top) * scaleY
    };
  }

  function updateTargeting() {
    if (!pointer.inside || !world) {
      hovered = null;
      hoverValid = false;
      return;
    }
    const cell = INTERACTION.targetCell(camera, pointer.x, pointer.y, config.tileSize);
    if (cell.x < 0 || cell.y < 0 || cell.x >= world.width || cell.y >= world.height) {
      hovered = null;
      hoverValid = false;
      return;
    }
    hovered = cell;
    const block = WORLD.getBlock(world, cell.x, cell.y);
    if (block !== config.blocks.air) {
      hoverValid = INTERACTION.canMine(world, player, cell.x, cell.y, config.reach).ok;
    } else {
      const target = INTERACTION.placementTarget(world, player, cell.x, cell.y);
      hoverValid = Boolean(target) && INTERACTION.canPlace(world, player, inventory, target.x, target.y, config.reach).ok;
    }
  }

  function spawnParticles(cellX, cellY, block, count, energy) {
    const base = RENDER.BLOCK_COLORS[block] || "#c9d4dc";
    const total = reducedMotion ? Math.max(2, Math.round(count * 0.35)) : count;
    for (let index = 0; index < total; index += 1) {
      particles.push({
        x: (cellX + 0.1 + Math.random() * 0.8) * config.tileSize,
        y: (cellY + 0.1 + Math.random() * 0.8) * config.tileSize,
        vx: (Math.random() - 0.5) * energy,
        vy: -energy * (0.3 + Math.random() * 0.8),
        life: 0.35 + Math.random() * 0.35,
        maxLife: 0.7,
        size: 2 + Math.floor(Math.random() * 3),
        color: base
      });
    }
    if (particles.length > 120) {
      particles.splice(0, particles.length - 120);
    }
  }

  function mineCurrentTarget() {
    if (!hovered) {
      return false;
    }
    const result = INTERACTION.mineBlock(world, player, inventory, hovered.x, hovered.y, config.reach);
    if (!result.ok) {
      audio.play("deny");
      toast("denied");
      return false;
    }
    spawnParticles(hovered.x, hovered.y, result.block, 10, 90);
    audio.play("break");
    refreshHotbar();
    updateHud();
    return true;
  }

  function placeAtHover() {
    if (!hovered) {
      return false;
    }
    const target = INTERACTION.placementTarget(world, player, hovered.x, hovered.y);
    if (!target) {
      audio.play("deny");
      toast("denied");
      return false;
    }
    const result = INTERACTION.placeBlock(world, player, inventory, target.x, target.y, config.reach);
    if (!result.ok) {
      audio.play("deny");
      toast(result.reason === "stock" ? "noStock" : "denied");
      return false;
    }
    spawnParticles(target.x, target.y, result.block, 5, 55);
    audio.play("place");
    refreshHotbar();
    updateHud();
    return true;
  }

  function onPointerDown(event) {
    audio.ensure();
    if (paused) {
      return;
    }
    pointer.inside = true;
    const point = canvasPoint(event);
    pointer.x = point.x;
    pointer.y = point.y;
    updateTargeting();
    if (event.button === 2 || event.button === 1) {
      placeAtHover();
      return;
    }
    if (event.button !== 0) {
      return;
    }
    if (!hovered) {
      return;
    }
    const check = INTERACTION.canMine(world, player, hovered.x, hovered.y, config.reach);
    if (!check.ok) {
      audio.play("deny");
      return;
    }
    miningActive = true;
    mining.cell = { x: hovered.x, y: hovered.y };
    mining.progress = 0;
    audio.play("mine");
  }

  function onPointerUp(event) {
    if (event.button === 0) {
      miningActive = false;
      mining.cell = null;
      mining.progress = 0;
    }
  }

  function onPointerMove(event) {
    const point = canvasPoint(event);
    pointer.x = point.x;
    pointer.y = point.y;
    pointer.inside = true;
    updateTargeting();
  }

  function onPointerLeave() {
    pointer.inside = false;
    hovered = null;
    hoverValid = false;
    miningActive = false;
    mining.cell = null;
    mining.progress = 0;
  }

  function onWheel(event) {
    if (paused) {
      event.preventDefault();
      return;
    }
    cycleSlot(event.deltaY > 0 ? 1 : -1);
    event.preventDefault();
  }

  function onKeyDown(event) {
    if (UI.isTextEntryTarget(event.target && event.target.tagName)) {
      return;
    }
    const action = UI.keyToAction(event.key);
    if (action === "left" || action === "right" || action === "jump") {
      if (action === "left") {
        input.left = true;
      } else if (action === "right") {
        input.right = true;
      } else {
        input.jump = true;
      }
      event.preventDefault();
      return;
    }
    if (action === "pause") {
      togglePause();
      event.preventDefault();
      return;
    }
    if (action === "mute") {
      toggleMute();
      return;
    }
    if (action === "help") {
      toggleHelp();
      event.preventDefault();
      return;
    }
    if (action === "respawn") {
      respawn();
      return;
    }
    if (action.indexOf("slot") === 0) {
      const digit = Number(action.slice(4));
      const changed = INTERACTION.selectByNumber(inventory, digit, config.hotbar.length);
      if (changed.ok) {
        audio.play("select");
        refreshHotbar();
        updateTargeting();
      }
    }
  }

  function onKeyUp(event) {
    const action = UI.keyToAction(event.key);
    if (action === "left") {
      input.left = false;
    } else if (action === "right") {
      input.right = false;
    } else if (action === "jump") {
      input.jump = false;
    }
  }

  function updateParticles(dt) {
    for (let index = particles.length - 1; index >= 0; index -= 1) {
      const particle = particles[index];
      particle.vy += 190 * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      particle.life -= dt;
      if (particle.life <= 0) {
        particles.splice(index, 1);
      }
    }
  }

  function frame(timestamp) {
    const dt = lastTimestamp ? Math.min(0.05, Math.max(0, (timestamp - lastTimestamp) / 1000)) : 0;
    lastTimestamp = timestamp;

    if (!paused && world && player) {
      PLAYER.stepPlayer(player, world, input, dt);
      timeOfDay = DAYNIGHT.advanceTime(timeOfDay, dt, config.dayCycleSeconds);
      if (miningActive && hovered) {
        const block = WORLD.getBlock(world, hovered.x, hovered.y);
        if (block) {
          const step = INTERACTION.advanceMining(mining, hovered, block, dt);
          if (step.progress > 0 && Math.random() < 0.25) {
            spawnParticles(hovered.x, hovered.y, block, 1, 35);
          }
          if (step.done) {
            mineCurrentTarget();
            miningActive = false;
            mining.cell = null;
            mining.progress = 0;
          }
        } else {
          miningActive = false;
          mining.cell = null;
          mining.progress = 0;
        }
      }
      updateParticles(dt);
      autosaveTimer += dt;
      if (autosaveTimer >= 8) {
        autosaveTimer = 0;
        save(false);
      }
    }

    if (world && player) {
      CAMERA.followCamera(camera, player, world, view, config.tileSize, dt || 0.016, 9);
      updateTargeting();
      RENDER.renderFrame(ctx, {
        world: world,
        player: player,
        camera: camera,
        time: timeOfDay,
        seed: world.seed,
        hovered: hovered,
        hoverValid: hoverValid,
        mining: mining,
        particles: particles,
        reducedMotion: reducedMotion
      });
    }

    frameCount += 1;
    if (frameCount % 6 === 0) {
      updateHud();
      refreshHotbar();
    }
    if (!booted) {
      booted = true;
      setStatus("ready", "ready");
    }
    window.requestAnimationFrame(frame);
  }

  function buildHelp() {
    helpList.textContent = "";
    UI.HELP_CONTROLS.forEach(function (entry) {
      const item = document.createElement("li");
      const keys = document.createElement("span");
      keys.className = "control-keys";
      keys.textContent = entry.keys;
      const action = document.createElement("span");
      action.className = "control-action";
      action.textContent = entry.action;
      item.appendChild(keys);
      item.appendChild(action);
      helpList.appendChild(item);
    });
  }

  function bindEvents() {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", function () {
      input.left = false;
      input.right = false;
      input.jump = false;
    });
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointerleave", onPointerLeave);
    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });
    canvas.addEventListener("wheel", onWheel, { passive: false });
    hotbar.addEventListener("click", function (event) {
      const slot = event.target.closest(".slot");
      if (slot) {
        selectSlot(Number(slot.dataset.slot));
      }
    });
    seedForm.addEventListener("submit", function (event) {
      event.preventDefault();
      applySeed(seedInput.value);
    });
    seedRandom.addEventListener("click", randomSeed);
    muteButton.addEventListener("click", function () {
      audio.ensure();
      toggleMute();
    });
    pauseButton.addEventListener("click", function () {
      togglePause();
    });
    helpButton.addEventListener("click", function () {
      toggleHelp();
    });
    helpClose.addEventListener("click", function () {
      toggleHelp(false);
    });
    resumeButton.addEventListener("click", function () {
      togglePause(false);
    });
    window.addEventListener("pagehide", function () {
      save(false);
    });
    if (reduceQuery) {
      const onChange = function (event) {
        reducedMotion = Boolean(event.matches);
      };
      if (typeof reduceQuery.addEventListener === "function") {
        reduceQuery.addEventListener("change", onChange);
      } else if (typeof reduceQuery.addListener === "function") {
        reduceQuery.addListener(onChange);
      }
    }
    window.addEventListener("error", function (event) {
      setStatus("error", event.message || "runtime error");
    });
    window.addEventListener("unhandledrejection", function (event) {
      setStatus("error", String(event.reason));
    });
  }

  function boot() {
    try {
      buildHelp();
      bindEvents();
      loadSaved();
      syncMuteButton();
      syncPauseButton();
      updateHud();
      refreshHotbar();
      window.__sandbox = {
        getWorld: function () {
          return world;
        },
        getPlayer: function () {
          return player;
        },
        getInventory: function () {
          return inventory;
        },
        getCamera: function () {
          return camera;
        },
        getTime: function () {
          return timeOfDay;
        },
        isPaused: function () {
          return paused;
        },
        seed: applySeed,
        save: function () {
          save(true);
        },
        setTime: function (value) {
          timeOfDay = DAYNIGHT.normalizeTime(value);
          updateHud();
          return timeOfDay;
        },
        setPaused: function (value) {
          togglePause(Boolean(value));
          return paused;
        },
        snapshot: function () {
          return {
            seed: world.seed,
            time: timeOfDay,
            paused: paused,
            selected: inventory.selected,
            counts: Object.assign({}, inventory.counts),
            player: { x: player.x, y: player.y, onGround: player.onGround },
            status: status.dataset.state
          };
        },
        mineAt: function (x, y) {
          const result = INTERACTION.mineBlock(world, player, inventory, x, y, config.reach);
          refreshHotbar();
          updateHud();
          return result;
        },
        placeAt: function (x, y) {
          const result = INTERACTION.placeBlock(world, player, inventory, x, y, config.reach);
          refreshHotbar();
          updateHud();
          return result;
        },
        placeNextTo: function (x, y) {
          const target = INTERACTION.placementTarget(world, player, x, y);
          if (!target) {
            return { ok: false, reason: "target", block: 0 };
          }
          const result = INTERACTION.placeBlock(world, player, inventory, target.x, target.y, config.reach);
          refreshHotbar();
          updateHud();
          result.x = target.x;
          result.y = target.y;
          return result;
        },
        blockAt: function (x, y) {
          return WORLD.getBlock(world, x, y);
        },
        mine: mineCurrentTarget,
        place: placeAtHover
      };
      window.requestAnimationFrame(frame);
    } catch (error) {
      setStatus("error", error && error.message ? error.message : String(error));
      throw error;
    }
  }

  boot();
})();
