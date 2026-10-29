(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const PLAYER = window.SandboxPlayer;
  const SAVE = window.SandboxSave;
  const RENDER = window.SandboxRender;

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d", { alpha: false });
  const status = document.getElementById("status");
  const hotbar = document.getElementById("hotbar");
  const seedValueElement = document.getElementById("seedValue");
  const saveChip = document.getElementById("saveChip");
  const saveText = document.getElementById("saveText");
  const overlay = document.getElementById("overlay");
  const overlayClose = document.getElementById("overlayClose");
  const seedInput = document.getElementById("seedInput");
  const seedApply = document.getElementById("seedApply");
  const seedRandom = document.getElementById("seedRandom");
  const worldReset = document.getElementById("worldReset");
  const seedHint = document.getElementById("seedHint");
  const blockLegend = document.getElementById("blockLegend");
  const toastRail = document.getElementById("toastRail");
  const soundBtn = document.getElementById("soundBtn");
  const helpBtn = document.getElementById("helpBtn");
  const seedChip = document.getElementById("seedChip");

  const state = {
    world: null,
    player: null,
    camera: { x: 0, y: 0 },
    seed: CONFIG.seed,
    hotbarIndex: 0,
    inventory: {},
    particles: [],
    hover: null,
    time: 0,
    viewWidth: window.innerWidth || CONFIG.viewWidth,
    viewHeight: window.innerHeight || CONFIG.viewHeight,
    pixelRatio: 1,
    paused: false,
    reducedMotion: false
  };

  const keys = { left: false, right: false, jump: false };
  const pointer = { x: 0, y: 0, inside: false, left: false, right: false };
  const mining = { cooldown: 0, warnAt: 0 };
  const placing = { cooldown: 0, warnAt: 0 };

  let storeInfo = { storage: SAVE.createMemoryStorage(), persisted: false, reason: "uninitialised" };
  let dirty = false;
  let saveTimer = 0;
  let accumulator = 0;
  let lastFrame = 0;
  let resetArmedUntil = 0;
  let audioContext = null;
  let masterGain = null;
  let muted = false;

  function setStatus(value, text) {
    status.dataset.state = value;
    status.title = text || value;
    status.setAttribute("aria-label", text || value);
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function safeLocalStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  function resizeCanvas() {
    state.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    state.viewWidth = Math.max(320, window.innerWidth);
    state.viewHeight = Math.max(240, window.innerHeight);
    canvas.width = Math.round(state.viewWidth * state.pixelRatio);
    canvas.height = Math.round(state.viewHeight * state.pixelRatio);
    canvas.style.width = state.viewWidth + "px";
    canvas.style.height = state.viewHeight + "px";
    ctx.setTransform(state.pixelRatio, 0, 0, state.pixelRatio, 0, 0);
  }

  function setSaveState(kind, text) {
    saveChip.dataset.state = kind;
    saveText.textContent = text;
  }

  function createStartingInventory() {
    const inventory = {};
    CONFIG.hotbar.forEach(function (id) {
      inventory[id] = CONFIG.startingInventory[id] || 0;
    });
    return inventory;
  }

  function normalizeInventory(raw) {
    const inventory = createStartingInventory();
    if (raw && typeof raw === "object") {
      CONFIG.hotbar.forEach(function (id) {
        const value = Number(raw[id]);
        if (Number.isFinite(value) && value >= 0) {
          inventory[id] = Math.floor(value);
        }
      });
    }
    return inventory;
  }

  function buildHotbar() {
    hotbar.innerHTML = "";
    CONFIG.hotbar.forEach(function (blockId, index) {
      const info = CONFIG.blockInfo[blockId];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot";
      button.dataset.index = String(index);
      button.dataset.block = info.name.toLowerCase();
      button.setAttribute("role", "button");
      button.setAttribute("aria-label", info.name + " block, key " + (index + 1));
      button.innerHTML =
        '<span class="key">' +
        (index + 1) +
        '</span><span class="swatch" style="--swatch:' +
        info.swatch +
        '"></span><span class="name">' +
        info.name +
        '</span><span class="count">0</span>';
      button.addEventListener("click", function () {
        selectSlot(index);
      });
      hotbar.appendChild(button);
    });
  }

  function buildLegend() {
    blockLegend.innerHTML = "";
    CONFIG.hotbar.forEach(function (blockId) {
      const info = CONFIG.blockInfo[blockId];
      const item = document.createElement("li");
      item.innerHTML =
        '<span class="legend-swatch" style="--swatch:' + info.swatch + '"></span>' +
        '<span class="legend-name">' + info.name + "</span>" +
        '<span class="legend-note">solid</span>';
      blockLegend.appendChild(item);
    });
  }

  function updateHotbar() {
    const slots = hotbar.querySelectorAll(".slot");
    for (let index = 0; index < slots.length; index += 1) {
      const slot = slots[index];
      const selected = index === state.hotbarIndex;
      slot.classList.toggle("is-selected", selected);
      slot.setAttribute("aria-pressed", selected ? "true" : "false");
      const blockId = CONFIG.hotbar[index];
      const count = slot.querySelector(".count");
      if (count) {
        count.textContent = String(state.inventory[blockId] || 0);
        count.classList.toggle("is-empty", (state.inventory[blockId] || 0) <= 0);
      }
    }
  }

  function updateSeedUi() {
    seedValueElement.textContent = String(state.seed);
    seedInput.value = String(state.seed);
    seedHint.textContent = "Seed " + state.seed + " — the same number always grows the same world.";
  }

  function selectSlot(index) {
    if (!CONFIG.hotbar.length) {
      return;
    }
    const next = ((index % CONFIG.hotbar.length) + CONFIG.hotbar.length) % CONFIG.hotbar.length;
    if (next === state.hotbarIndex) {
      return;
    }
    state.hotbarIndex = next;
    updateHotbar();
    playSound("tick");
    markDirty();
  }

  function cycleSlot(direction) {
    selectSlot(state.hotbarIndex + (direction > 0 ? 1 : -1));
  }

  function selectedBlock() {
    return CONFIG.hotbar[state.hotbarIndex];
  }

  function toast(message, kind) {
    if (!toastRail) {
      return;
    }
    const item = document.createElement("div");
    item.className = "toast" + (kind ? " is-" + kind : "");
    item.textContent = message;
    toastRail.appendChild(item);
    while (toastRail.children.length > 4) {
      toastRail.removeChild(toastRail.firstChild);
    }
    window.setTimeout(function () {
      item.classList.add("is-leaving");
      window.setTimeout(function () {
        if (item.parentNode) {
          item.parentNode.removeChild(item);
        }
      }, 260);
    }, 2100);
  }

  function markDirty() {
    dirty = true;
    if (storeInfo.persisted) {
      setSaveState("dirty", "Unsaved");
    } else {
      setSaveState("error", "Session only");
    }
  }

  function saveNow() {
    if (!state.world || !state.player) {
      return;
    }
    const payload = SAVE.createPayload(
      JSON.parse(WORLD.serializeWorld(state.world)),
      PLAYER.serializePlayer(state.player),
      state.hotbarIndex,
      state.inventory,
      Date.now()
    );
    const result = SAVE.saveGame(storeInfo.storage, CONFIG.saveKey, payload);
    saveTimer = 0;
    if (result.ok) {
      dirty = false;
      if (storeInfo.persisted) {
        setSaveState("saved", "Saved");
      } else {
        setSaveState("error", "Session only");
      }
    } else {
      setSaveState("error", "Save failed");
    }
  }

  function hydrateGame() {
    const storage = safeLocalStorage();
    storeInfo = SAVE.resolveStorage(storage);
    if (!storeInfo.persisted) {
      return { restored: false, reason: "storage-unavailable" };
    }
    const result = SAVE.loadGame(storeInfo.storage, CONFIG.saveKey);
    if (!result.ok) {
      return { restored: false, reason: result.reason };
    }
    try {
      const world = WORLD.deserializeWorld(JSON.stringify(result.payload.world));
      const spawn = WORLD.findSpawn(world);
      let player = PLAYER.restorePlayer(result.payload.player, spawn.x, spawn.y);
      const rect = PLAYER.box(player);
      if (WORLD.rectOverlapsSolid(world, rect.left, rect.top, rect.right, rect.bottom)) {
        player = PLAYER.createPlayer(spawn.x, spawn.y);
      }
      state.world = world;
      state.player = player;
      state.seed = world.seed;
      state.hotbarIndex = clamp(result.payload.hotbarIndex, 0, CONFIG.hotbar.length - 1);
      state.inventory = normalizeInventory(result.payload.inventory);
      state.camera = RENDER.createCamera(world, player, state.viewWidth, state.viewHeight);
      return { restored: true, reason: "loaded", savedAt: result.payload.savedAt };
    } catch (error) {
      return { restored: false, reason: "unreadable" };
    }
  }

  function newWorld(seed) {
    state.seed = Number(seed) >>> 0;
    state.world = WORLD.createWorld(state.seed);
    const spawn = WORLD.findSpawn(state.world);
    state.player = PLAYER.createPlayer(spawn.x, spawn.y);
    state.inventory = createStartingInventory();
    state.hotbarIndex = 0;
    state.particles = [];
    state.hover = null;
    state.camera = RENDER.createCamera(state.world, state.player, state.viewWidth, state.viewHeight);
    updateSeedUi();
    updateHotbar();
    markDirty();
  }

  function respawnPlayer() {
    const spawn = WORLD.findSpawn(state.world);
    state.player = PLAYER.createPlayer(spawn.x, spawn.y);
    state.camera = RENDER.createCamera(state.world, state.player, state.viewWidth, state.viewHeight);
    toast("Back at the surface.", "warn");
    markDirty();
  }

  function screenToWorld(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const screenX = clientX - rect.left;
    const screenY = clientY - rect.top;
    return {
      x: (screenX + state.camera.x) / CONFIG.tileSize,
      y: (screenY + state.camera.y) / CONFIG.tileSize
    };
  }

  function chooseAdjacentEmpty(cell) {
    const options = [
      [1, 0],
      [-1, 0],
      [0, -1],
      [0, 1]
    ];
    let best = null;
    let bestDistance = Infinity;
    for (let index = 0; index < options.length; index += 1) {
      const x = cell.x + options[index][0];
      const y = cell.y + options[index][1];
      if (WORLD.getBlock(state.world, x, y) !== CONFIG.blocks.air) {
        continue;
      }
      const distance = WORLD.distanceToCell(state.player, x, y);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = { x: x, y: y };
      }
    }
    return best;
  }

  function updateHover() {
    if (!state.world || !pointer.inside || state.paused) {
      state.hover = null;
      return;
    }
    const position = screenToWorld(pointer.x, pointer.y);
    const cell = { x: Math.floor(position.x), y: Math.floor(position.y) };
    if (!WORLD.inBounds(state.world, cell.x, cell.y)) {
      state.hover = null;
      return;
    }
    const mine = WORLD.canMineBlock(state.world, state.player, cell.x, cell.y, CONFIG.reach);
    let placeCell = cell;
    let place = WORLD.canPlaceBlock(state.world, state.player, cell.x, cell.y, CONFIG.reach);
    if (WORLD.getBlock(state.world, cell.x, cell.y) !== CONFIG.blocks.air) {
      placeCell = chooseAdjacentEmpty(cell);
      place = placeCell
        ? WORLD.canPlaceBlock(state.world, state.player, placeCell.x, placeCell.y, CONFIG.reach)
        : { ok: false, reason: "occupied" };
    }
    let reason = "";
    if (mine.reason === "reach" || (place && place.reason === "reach")) {
      reason = "reach";
    }
    state.hover = { cell: cell, mine: mine, placeCell: placeCell, place: place, reason: reason };
  }

  function spawnParticles(cellX, cellY, blockId, count, force) {
    const info = CONFIG.blockInfo[blockId] || { swatch: "#9aa4b0", accent: "#cbd5df" };
    const colors = [info.swatch, info.accent || info.swatch, "#f4f8ff"];
    for (let index = 0; index < count; index += 1) {
      const life = 0.32 + Math.random() * 0.36;
      state.particles.push({
        x: cellX + 0.5 + (Math.random() - 0.5) * 0.9,
        y: cellY + 0.5 + (Math.random() - 0.5) * 0.9,
        vx: (Math.random() - 0.5) * (force || 3),
        vy: -1.1 - Math.random() * (force || 3.2),
        life: life,
        maxLife: life,
        size: 1 + Math.floor(Math.random() * 3),
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }
  }

  function tryMine() {
    if (!state.hover) {
      return false;
    }
    const cell = state.hover.cell;
    const result = WORLD.canMineBlock(state.world, state.player, cell.x, cell.y, CONFIG.reach);
    if (!result.ok) {
      if (result.reason === "reach" && performance.now() > mining.warnAt) {
        toast("Too far — step a little closer.", "warn");
        mining.warnAt = performance.now() + 1400;
      }
      return false;
    }
    const blockId = WORLD.getBlock(state.world, cell.x, cell.y);
    if (!WORLD.setBlock(state.world, cell.x, cell.y, CONFIG.blocks.air)) {
      return false;
    }
    state.inventory[blockId] = (state.inventory[blockId] || 0) + 1;
    spawnParticles(cell.x, cell.y, blockId, 12, 3.4);
    playSound("mine");
    markDirty();
    updateHotbar();
    return true;
  }

  function placeMessage(reason) {
    switch (reason) {
      case "reach":
        return "Too far — step a little closer.";
      case "occupied":
        return "That space is already filled.";
      case "player":
        return "You cannot place a block inside yourself.";
      case "unsupported":
        return "Blocks need a solid neighbour.";
      default:
        return "That space is not available.";
    }
  }

  function tryPlace() {
    if (!state.hover || !state.hover.place || !state.hover.placeCell) {
      return false;
    }
    const cell = state.hover.placeCell;
    const result = state.hover.place;
    if (!result.ok) {
      if (performance.now() > placing.warnAt) {
        toast(placeMessage(result.reason), "warn");
        placing.warnAt = performance.now() + 1200;
      }
      return false;
    }
    const blockId = selectedBlock();
    const info = CONFIG.blockInfo[blockId];
    if ((state.inventory[blockId] || 0) <= 0) {
      toast("Out of " + info.name + " — mine some first.", "warn");
      playSound("error");
      placing.warnAt = performance.now() + 1200;
      return false;
    }
    if (!WORLD.setBlock(state.world, cell.x, cell.y, blockId)) {
      return false;
    }
    state.inventory[blockId] -= 1;
    spawnParticles(cell.x, cell.y, blockId, 7, 2.2);
    playSound("place");
    markDirty();
    updateHotbar();
    return true;
  }

  function ensureAudio() {
    if (muted) {
      return null;
    }
    if (!audioContext) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) {
        return null;
      }
      try {
        audioContext = new Ctor();
        masterGain = audioContext.createGain();
        masterGain.gain.value = 0.16;
        masterGain.connect(audioContext.destination);
      } catch (error) {
        audioContext = null;
        return null;
      }
    }
    if (audioContext.state === "suspended") {
      audioContext.resume().catch(function () {});
    }
    return audioContext;
  }

  function blip(startFrequency, endFrequency, duration, type, volume) {
    const context = ensureAudio();
    if (!context || !masterGain) {
      return;
    }
    const now = context.currentTime;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type || "square";
    oscillator.frequency.setValueAtTime(startFrequency, now);
    if (endFrequency) {
      oscillator.frequency.exponentialRampToValueAtTime(Math.max(30, endFrequency), now + duration);
    }
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(volume || 0.08, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(gain);
    gain.connect(masterGain);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.03);
  }

  function playSound(kind) {
    switch (kind) {
      case "mine":
        blip(190, 74, 0.11, "square", 0.06);
        break;
      case "place":
        blip(120, 64, 0.14, "triangle", 0.09);
        break;
      case "jump":
        blip(320, 520, 0.12, "sine", 0.05);
        break;
      case "land":
        blip(120, 60, 0.1, "sine", 0.05);
        break;
      case "tick":
        blip(720, 720, 0.035, "square", 0.03);
        break;
      case "error":
        blip(150, 88, 0.18, "sawtooth", 0.05);
        break;
      case "save":
        blip(760, 760, 0.05, "sine", 0.03);
        window.setTimeout(function () {
          blip(1020, 1020, 0.06, "sine", 0.03);
        }, 70);
        break;
      default:
        break;
    }
  }

  function toggleMute() {
    muted = !muted;
    soundBtn.setAttribute("aria-pressed", muted ? "false" : "true");
    soundBtn.classList.toggle("is-muted", muted);
    soundBtn.title = muted ? "Sound off (M)" : "Sound on (M)";
    toast(muted ? "Sound muted" : "Sound on", "info");
    if (!muted) {
      playSound("tick");
    }
  }

  function setOverlay(open) {
    state.paused = Boolean(open);
    overlay.hidden = !state.paused;
    overlay.setAttribute("aria-hidden", state.paused ? "false" : "true");
    if (state.paused) {
      updateSeedUi();
      window.setTimeout(function () {
        overlayClose.focus();
      }, 20);
    } else {
      canvas.focus();
    }
  }

  function applySeed(rawValue) {
    const cleaned = String(rawValue).replace(/[^0-9-]/g, "");
    const parsed = Number.parseInt(cleaned, 10);
    if (!Number.isFinite(parsed)) {
      seedHint.textContent = "Enter a whole number to grow a world.";
      seedInput.focus();
      playSound("error");
      return;
    }
    newWorld(parsed >>> 0);
    saveNow();
    setOverlay(false);
    toast("New world — seed " + state.seed, "good");
    playSound("save");
  }

  function requestReset() {
    const now = Date.now();
    if (now < resetArmedUntil) {
      resetArmedUntil = 0;
      worldReset.textContent = "Reset world";
      newWorld(Math.floor(Math.random() * 1000000000));
      saveNow();
      setOverlay(false);
      toast("World reset. Fresh ground, fresh start.", "good");
      playSound("save");
      return;
    }
    resetArmedUntil = now + 3200;
    worldReset.textContent = "Click again to reset";
    seedHint.textContent = "This clears the current world and inventory.";
    window.setTimeout(function () {
      if (Date.now() >= resetArmedUntil) {
        worldReset.textContent = "Reset world";
      }
    }, 3300);
  }

  function update(dt) {
    state.time += dt;

    if (!state.paused && state.world && state.player) {
      accumulator += Math.min(dt, 0.1);
      const step = 1 / 60;
      let guard = 0;
      while (accumulator >= step && guard < 8) {
        const events = PLAYER.stepPlayer(state.player, state.world, keys, step);
        if (events.jumped) {
          playSound("jump");
          markDirty();
        }
        if (events.landed) {
          playSound("land");
        }
        accumulator -= step;
        guard += 1;
      }
      RENDER.updateCamera(state.camera, state.world, state.player, state.viewWidth, state.viewHeight, dt, false);
      if (state.player.y > state.world.height - 1) {
        respawnPlayer();
      }

      mining.cooldown -= dt;
      placing.cooldown -= dt;
      if (pointer.left && mining.cooldown <= 0) {
        mining.cooldown = tryMine() ? 0.16 : 0.12;
      }
      if (pointer.right && placing.cooldown <= 0) {
        placing.cooldown = tryPlace() ? 0.16 : 0.12;
      }
    }

    updateHover();

    for (let index = state.particles.length - 1; index >= 0; index -= 1) {
      const particle = state.particles[index];
      particle.life -= dt;
      if (particle.life <= 0) {
        state.particles.splice(index, 1);
        continue;
      }
      particle.vy += 16 * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
    }

    saveTimer += dt;
    if (dirty && saveTimer >= CONFIG.autosaveSeconds) {
      saveNow();
      if (storeInfo.persisted) {
        setSaveState("saved", "Saved");
      }
    }
  }

  function draw() {
    RENDER.renderFrame(ctx, {
      world: state.world,
      player: state.player,
      camera: state.camera,
      viewWidth: state.viewWidth,
      viewHeight: state.viewHeight,
      pixelRatio: state.pixelRatio,
      time: state.time,
      hover: state.hover,
      selectedBlock: selectedBlock(),
      particles: state.particles,
      paused: state.paused,
      reducedMotion: state.reducedMotion
    });
  }

  function frame(now) {
    if (!lastFrame) {
      lastFrame = now;
    }
    const dt = Math.min(0.05, Math.max(0, (now - lastFrame) / 1000));
    lastFrame = now;
    update(dt);
    draw();
    window.requestAnimationFrame(frame);
  }

  function onKeyDown(event) {
    const target = event.target;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
      if (event.key === "Escape") {
        setOverlay(false);
      }
      return;
    }
    const key = event.key;
    const lower = key.toLowerCase();
    if (lower === "a" || key === "ArrowLeft") {
      keys.left = true;
      event.preventDefault();
    } else if (lower === "d" || key === "ArrowRight") {
      keys.right = true;
      event.preventDefault();
    } else if (lower === "w" || key === "ArrowUp" || key === " ") {
      keys.jump = true;
      event.preventDefault();
    } else if (lower === "h") {
      setOverlay(overlay.hidden);
      event.preventDefault();
    } else if (lower === "p" || key === "Escape") {
      setOverlay(overlay.hidden);
      event.preventDefault();
    } else if (lower === "m") {
      toggleMute();
      event.preventDefault();
    } else if (/^[1-9]$/.test(key)) {
      const index = Number(key) - 1;
      if (index < CONFIG.hotbar.length) {
        selectSlot(index);
        event.preventDefault();
      }
    }
    ensureAudio();
  }

  function onKeyUp(event) {
    const key = event.key;
    const lower = key.toLowerCase();
    if (lower === "a" || key === "ArrowLeft") {
      keys.left = false;
    } else if (lower === "d" || key === "ArrowRight") {
      keys.right = false;
    } else if (lower === "w" || key === "ArrowUp" || key === " ") {
      keys.jump = false;
    }
  }

  function onPointerDown(event) {
    if (state.paused) {
      return;
    }
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.inside = true;
    ensureAudio();
    if (event.button === 0) {
      pointer.left = true;
      updateHover();
      if (tryMine()) {
        mining.cooldown = 0.18;
      }
      event.preventDefault();
    } else if (event.button === 2) {
      pointer.right = true;
      updateHover();
      if (tryPlace()) {
        placing.cooldown = 0.18;
      }
      event.preventDefault();
    }
  }

  function onPointerUp(event) {
    if (event.button === 0) {
      pointer.left = false;
    } else if (event.button === 2) {
      pointer.right = false;
    }
  }

  function bindEvents() {
    window.addEventListener("resize", resizeCanvas);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", function () {
      keys.left = false;
      keys.right = false;
      keys.jump = false;
      pointer.left = false;
      pointer.right = false;
    });
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("pointercancel", onPointerUp);

    canvas.addEventListener("pointermove", function (event) {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.inside = true;
    });
    canvas.addEventListener("pointerleave", function () {
      pointer.inside = false;
      state.hover = null;
    });
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });
    canvas.addEventListener(
      "wheel",
      function (event) {
        event.preventDefault();
        cycleSlot(event.deltaY > 0 ? 1 : -1);
      },
      { passive: false }
    );

    helpBtn.addEventListener("click", function () {
      ensureAudio();
      setOverlay(true);
    });
    seedChip.addEventListener("click", function () {
      ensureAudio();
      setOverlay(true);
      seedInput.focus();
      seedInput.select();
    });
    soundBtn.addEventListener("click", function () {
      ensureAudio();
      toggleMute();
    });
    overlayClose.addEventListener("click", function () {
      setOverlay(false);
    });
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        setOverlay(false);
      }
    });
    seedApply.addEventListener("click", function () {
      applySeed(seedInput.value);
    });
    seedInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        applySeed(seedInput.value);
      }
    });
    seedRandom.addEventListener("click", function () {
      applySeed(String(Math.floor(Math.random() * 1000000000)));
    });
    worldReset.addEventListener("click", requestReset);

    window.addEventListener("pagehide", function () {
      saveNow();
    });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        saveNow();
      }
    });
  }

  function boot() {
    state.reducedMotion = window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;
    resizeCanvas();
    buildHotbar();
    buildLegend();
    const restored = hydrateGame();
    if (restored.restored) {
      setSaveState("saved", "Restored");
      updateSeedUi();
      updateHotbar();
    } else {
      newWorld(CONFIG.seed);
      saveNow();
      setSaveState(storeInfo.persisted ? "saved" : "error", storeInfo.persisted ? "Ready" : "Session only");
      updateSeedUi();
      if (restored.reason === "unreadable" || restored.reason === "corrupt" || restored.reason === "invalid") {
        toast("Saved world was unreadable — a fresh one was grown.", "warn");
      }
    }
    state.camera = RENDER.createCamera(state.world, state.player, state.viewWidth, state.viewHeight);
    updateHotbar();
    bindEvents();
    draw();
    setStatus("ready", "ready");
    setSaveState(
      storeInfo.persisted ? "saved" : "error",
      storeInfo.persisted ? (restored.restored ? "Restored" : "Saved") : "Session only"
    );
    if (restored.restored) {
      toast("Welcome back — world and explorer restored.", "good");
    } else {
      toast("Explore, mine and build. Press H for controls.", "info");
    }
    window.__sandbox = {
      get world() {
        return state.world;
      },
      get player() {
        return state.player;
      },
      get camera() {
        return state.camera;
      },
      state: state,
      saveNow: saveNow,
      newWorld: newWorld,
      version: CONFIG.version,
      ready: true
    };
    window.requestAnimationFrame(frame);
  }

  window.addEventListener("error", function (event) {
    setStatus("error", event.message || "runtime error");
  });
  window.addEventListener("unhandledrejection", function (event) {
    setStatus("error", String(event.reason));
  });

  try {
    boot();
  } catch (error) {
    setStatus("error", error && error.message ? error.message : String(error));
    throw error;
  }
})();
