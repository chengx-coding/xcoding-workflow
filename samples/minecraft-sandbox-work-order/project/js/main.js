(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const RNG = window.SandboxRng;
  const World = window.SandboxWorld;
  const Player = window.SandboxPlayer;
  const Inventory = window.SandboxInventory;
  const Interaction = window.SandboxInteraction;
  const Persistence = window.SandboxPersistence;
  const Time = window.SandboxTime;
  const Camera = window.SandboxCamera;
  const Render = window.SandboxRender;
  const Ui = window.SandboxUi;
  const AudioKit = window.SandboxAudio;
  const Mining = window.SandboxMining;

  if (!CONFIG || !World || !Player || !Inventory || !Interaction || !Persistence || !Time || !Camera || !Render || !Ui || !AudioKit || !Mining) {
    throw new Error("One or more sandbox modules failed to load");
  }

  const elements = {
    canvas: document.getElementById("game"),
    status: document.getElementById("status"),
    hotbar: document.getElementById("hotbar"),
    hud: document.getElementById("hud"),
    target: document.getElementById("target-value"),
    coords: document.getElementById("coords-value"),
    clockText: document.getElementById("clock-text"),
    phaseValue: document.getElementById("phase-value"),
    seedValue: document.getElementById("seed-value"),
    seedInput: document.getElementById("seed-input"),
    seedForm: document.getElementById("seed-form"),
    minimap: document.getElementById("minimap"),
    minimapSeed: document.getElementById("minimap-seed"),
    pauseButton: document.getElementById("pause-button"),
    resumeButton: document.getElementById("resume-button"),
    muteButton: document.getElementById("mute-button"),
    toasts: document.getElementById("toasts"),
    pauseOverlay: document.getElementById("pause-overlay"),
    stage: document.getElementById("stage")
  };

  const canvas = elements.canvas;
  const ctx = canvas.getContext("2d");
  const minimapCtx = elements.minimap ? elements.minimap.getContext("2d") : null;
  const MINIMAP_SIZE = { width: 180, height: 64 };
  const view = { width: CONFIG.viewWidth, height: CONFIG.viewHeight };
  const MUTE_KEY = "xc-sandbox-muted-v1";

  const reduceQuery = typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;
  let reducedMotion = !!(reduceQuery && reduceQuery.matches);

  const audio = AudioKit.createAudio(window);
  let muted = false;
  try {
    muted = window.localStorage.getItem(MUTE_KEY) === "1";
  } catch (error) {
    muted = false;
  }
  audio.setMuted(muted);

  const storage = (function () {
    try {
      const candidate = window.localStorage;
      const probe = "__xc-sandbox-probe__";
      candidate.setItem(probe, "1");
      candidate.removeItem(probe);
      return candidate;
    } catch (error) {
      return null;
    }
  })();

  const keys = { left: false, right: false, jump: false };
  const particles = [];
  const slotElements = [];
  let slotCounts = [];
  let state = null;
  let statusReady = false;
  let saveFailed = storage === null;
  let dirty = false;
  let lastSaveAt = 0;
  let lastFrameAt = 0;
  let lastToast = null;
  let hotbarCaption = null;

  function setStatus(nextState, text) {
    elements.status.dataset.state = nextState;
    elements.status.title = text || nextState;
  }

  function readDefaultSeed() {
    const value = Number(elements.seedInput.value);
    return Number.isFinite(value) ? value >>> 0 : CONFIG.seed;
  }

  function snapCamera(game) {
    Camera.update(game.camera, game.player, game.world, view, 1 / 60, { reducedMotion: true });
  }

  function createGame(seed) {
    const world = World.createWorld(seed);
    const spawn = World.spawnPoint(world);
    const player = Player.createPlayer(spawn.x, spawn.y);
    const game = {
      world: world,
      player: player,
      inventory: Inventory.starterInventory(),
      clock: Time.createClock(CONFIG.time.startFraction),
      camera: Camera.createCamera(),
      selected: Ui.clampIndex(CONFIG.starterSelected),
      hover: null,
      mining: Mining.createMining(),
      paused: false
    };
    snapCamera(game);
    return game;
  }

  function restoreGame(defaultSeed) {
    const loaded = Persistence.loadState(storage, CONFIG.saveKey);
    if (loaded.ok) {
      const saved = loaded.state;
      const game = {
        world: saved.world,
        player: Player.createPlayer(saved.player.x, saved.player.y),
        inventory: saved.inventory,
        clock: Time.createClock(saved.time),
        camera: Camera.createCamera(),
        selected: Ui.clampIndex(saved.selected),
        hover: null,
        mining: Mining.createMining(),
        paused: false
      };
      game.player.facing = saved.player.facing;
      snapCamera(game);
      return { game: game, notice: "World restored from your last session." };
    }
    if (loaded.reason === "corrupt" || loaded.reason === "version") {
      return {
        game: createGame(defaultSeed),
        notice: "The saved world could not be read. A fresh world was generated."
      };
    }
    if (loaded.reason === "unavailable") {
      return {
        game: createGame(defaultSeed),
        notice: "Saving is unavailable in this browser. This session will not persist."
      };
    }
    return { game: createGame(defaultSeed), notice: null };
  }

  function fitCanvas() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.round(CONFIG.viewWidth * dpr);
    const height = Math.round(CONFIG.viewHeight * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function fitMinimap() {
    if (!minimapCtx) {
      return;
    }
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.round(MINIMAP_SIZE.width * dpr);
    const height = Math.round(MINIMAP_SIZE.height * dpr);
    if (elements.minimap.width !== width || elements.minimap.height !== height) {
      elements.minimap.width = width;
      elements.minimap.height = height;
    }
    minimapCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    Render.renderFrame(ctx, {
      world: state.world,
      player: state.player,
      camera: state.camera,
      time: state.clock.fraction,
      hover: state.hover,
      mining: state.mining,
      particles: particles,
      reducedMotion: reducedMotion
    });
    if (minimapCtx) {
      Render.renderMinimap(minimapCtx, state.world, state.player, state.camera, MINIMAP_SIZE);
    }
  }

  function updateHotbar() {
    const model = Ui.hotbarModel(state.inventory, state.selected);
    for (let index = 0; index < model.length; index += 1) {
      const slot = model[index];
      const element = slotElements[index];
      if (!element) {
        continue;
      }
      element.classList.toggle("is-selected", slot.selected);
      element.setAttribute("aria-pressed", slot.selected ? "true" : "false");
      element.setAttribute("aria-label", slot.label + " — " + slot.count + " in inventory — key " + slot.key);
      const countElement = slotCounts[index];
      if (countElement) {
        countElement.textContent = String(slot.count);
        countElement.classList.toggle("is-empty", slot.count === 0);
      }
    }
    if (hotbarCaption) {
      const active = model[state.selected];
      hotbarCaption.textContent = active.label + " · " + active.count + " in hand";
    }
  }

  function updateHud() {
    elements.coords.textContent = Ui.coordinates(state.player).text;
    const clock = Ui.clockModel(state.clock.fraction);
    elements.clockText.textContent = clock.label;
    elements.phaseValue.textContent = clock.phaseLabel.toLowerCase();
    elements.seedValue.textContent = String(state.world.seed);
    if (elements.minimapSeed) {
      elements.minimapSeed.textContent = String(state.world.seed);
    }

    let target;
    if (state.hover) {
      const block = Interaction.blockAt(state.world, state.hover.x, state.hover.y);
      const reachable = Interaction.withinReach(state.player, state.hover.x, state.hover.y);
      target = Ui.targetModel(state.hover, block, reachable);
    } else {
      target = Ui.targetModel(null, CONFIG.blocks.air, true);
    }
    elements.target.textContent = target.text;
    elements.target.classList.toggle("is-refused", target.refused);
  }

  function toast(message, tone) {
    const element = document.createElement("div");
    element.className = "toast";
    element.dataset.tone = tone || "gain";
    element.textContent = message;
    elements.toasts.appendChild(element);
    lastToast = { message: message, tone: tone || "gain", at: Date.now() };
    window.requestAnimationFrame(function () {
      element.classList.add("is-visible");
    });
    while (elements.toasts.children.length > 4) {
      elements.toasts.removeChild(elements.toasts.firstElementChild);
    }
    window.setTimeout(function () {
      element.classList.remove("is-visible");
      window.setTimeout(function () {
        if (element.parentNode) {
          element.parentNode.removeChild(element);
        }
      }, 240);
    }, Ui.toastLifetime(tone));
  }

  function markDirty() {
    dirty = true;
  }

  function saveNow(reason) {
    if (!storage) {
      if (!saveFailed) {
        saveFailed = true;
        toast("Saving is unavailable in this browser. This session will not persist.", "refuse");
      }
      return { ok: false, reason: "unavailable" };
    }
    const result = Persistence.saveState(
      storage,
      {
        world: state.world,
        player: state.player,
        inventory: state.inventory,
        time: state.clock.fraction,
        selected: state.selected
      },
      CONFIG.saveKey
    );
    if (result.ok) {
      dirty = false;
      lastSaveAt = window.performance.now();
      return result;
    }
    if (!saveFailed) {
      saveFailed = true;
      toast("Saving is unavailable in this browser. This session will not persist.", "refuse");
    }
    return result;
  }

  function spawnParticles(tileX, tileY, blockId, count) {
    const color = Render.hexToRgb(CONFIG.blockInfo[blockId].color);
    for (let index = 0; index < count; index += 1) {
      particles.push({
        x: tileX + 0.15 + Math.random() * 0.7,
        y: tileY + 0.15 + Math.random() * 0.7,
        vx: (Math.random() - 0.5) * 3.4,
        vy: -1.2 - Math.random() * 3.4,
        life: 0.45 + Math.random() * 0.4,
        maxLife: 0.85,
        size: 2 + Math.random() * 3,
        color: color
      });
    }
  }

  function updateParticles(dt) {
    for (let index = particles.length - 1; index >= 0; index -= 1) {
      const particle = particles[index];
      particle.vy += 26 * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      particle.life -= dt;
      if (particle.life <= 0) {
        particles.splice(index, 1);
      }
    }
  }

  function mineAt(tile) {
    const result = Interaction.mineBlock(state.world, state.player, tile.x, tile.y, state.inventory);
    if (result.ok) {
      spawnParticles(tile.x, tile.y, result.block, 11);
      audio.play("mine");
      toast("+1 " + result.blockName, "gain");
      markDirty();
      updateHotbar();
    } else {
      audio.play("refuse");
      toast(result.reason, "refuse");
    }
    updateHud();
    draw();
    return result;
  }

  function startMining(tile) {
    if (!tile) {
      return { ok: false, reason: "Outside the world." };
    }
    const validation = Interaction.validateMine(state.world, state.player, tile.x, tile.y);
    if (!validation.ok) {
      audio.play("refuse");
      toast(validation.reason, "refuse");
      updateHud();
      return validation;
    }
    Mining.start(state.mining, tile.x, tile.y);
    audio.play("select");
    updateHud();
    return validation;
  }

  function placeAt(tile) {
    const blockId = Ui.selectedBlockId(state.selected);
    const result = Interaction.placeBlock(state.world, state.player, tile.x, tile.y, blockId, state.inventory);
    if (result.ok) {
      spawnParticles(tile.x, tile.y, blockId, 8);
      audio.play("place");
      toast("Placed " + result.blockName, "gain");
      markDirty();
      updateHotbar();
    } else {
      audio.play("refuse");
      toast(result.reason, "refuse");
    }
    updateHud();
    draw();
    return result;
  }

  function tileFromEvent(event) {
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      return null;
    }
    const x = Math.floor((event.clientX - rect.left) / rect.width * CONFIG.viewWidth);
    const y = Math.floor((event.clientY - rect.top) / rect.height * CONFIG.viewHeight);
    const tileX = Math.floor((x + state.camera.x) / CONFIG.tileSize);
    const tileY = Math.floor((y + state.camera.y) / CONFIG.tileSize);
    if (tileX < 0 || tileY < 0 || tileX >= state.world.width || tileY >= state.world.height) {
      return null;
    }
    return { x: tileX, y: tileY };
  }

  function selectSlot(index) {
    const next = Ui.clampIndex(index);
    const changed = next !== state.selected;
    state.selected = next;
    updateHotbar();
    updateHud();
    if (changed) {
      audio.play("select");
      markDirty();
    }
  }

  function togglePause(force) {
    state.paused = typeof force === "boolean" ? force : !state.paused;
    if (state.paused) {
      Mining.cancel(state.mining);
    }
    elements.pauseOverlay.hidden = !state.paused;
    elements.pauseButton.textContent = state.paused ? "Resume" : "Pause";
    elements.pauseButton.setAttribute("aria-pressed", state.paused ? "true" : "false");
    if (state.paused) {
      saveNow("pause");
    }
    draw();
  }

  function toggleMute() {
    muted = !audio.isMuted();
    audio.setMuted(muted);
    elements.muteButton.textContent = muted ? "Muted" : "Sound on";
    elements.muteButton.setAttribute("aria-pressed", muted ? "true" : "false");
    try {
      window.localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    } catch (error) {
      // A blocked storage area only costs the preference, not the game.
    }
    toast(muted ? "Sound muted." : "Sound on.", "notice");
  }

  function update(dt, now) {
    if (state.paused) {
      return;
    }
    Time.advance(state.clock, dt, CONFIG.time.cycleSeconds);
    Player.stepPlayer(state.player, state.world, keys, dt);
    if (state.mining.active) {
      const complete = Mining.advance(state.mining, dt);
      if (complete) {
        const target = state.mining.tile;
        Mining.cancel(state.mining);
        mineAt(target);
      }
    }
    updateParticles(dt);
    Camera.update(state.camera, state.player, state.world, view, dt, { reducedMotion: reducedMotion });
    const floorZone = state.player.y > state.world.height - 5;
    if (elements.hotbar.classList.contains("is-tucked") !== floorZone) {
      elements.hotbar.classList.toggle("is-tucked", floorZone);
    }
    if (dirty && now - lastSaveAt > 3500) {
      saveNow("auto");
    }
  }

  function frame(now) {
    try {
      if (!lastFrameAt) {
        lastFrameAt = now;
      }
      const dt = Math.min(0.05, Math.max(0, (now - lastFrameAt) / 1000));
      lastFrameAt = now;
      update(dt, now);
      updateHud();
      draw();
      if (!statusReady) {
        statusReady = true;
        setStatus("ready", "ready");
      }
      window.requestAnimationFrame(frame);
    } catch (error) {
      setStatus("error", error && error.message ? error.message : String(error));
      throw error;
    }
  }

  function bindEvents() {
    window.addEventListener("keydown", function (event) {
      const tag = event.target && event.target.tagName ? event.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "a" || key === "arrowleft") {
        keys.left = true;
        event.preventDefault();
      } else if (key === "d" || key === "arrowright") {
        keys.right = true;
        event.preventDefault();
      } else if (key === " " || key === "spacebar" || key === "arrowup" || key === "w") {
        keys.jump = true;
        audio.unlock();
        event.preventDefault();
      } else if (key === "p") {
        togglePause();
        event.preventDefault();
      } else if (key === "m") {
        toggleMute();
        event.preventDefault();
      } else if (/^[1-9]$/.test(key)) {
        selectSlot(Number(key) - 1);
        event.preventDefault();
      }
    });

    window.addEventListener("keyup", function (event) {
      const key = event.key.toLowerCase();
      if (key === "a" || key === "arrowleft") {
        keys.left = false;
      } else if (key === "d" || key === "arrowright") {
        keys.right = false;
      } else if (key === " " || key === "spacebar" || key === "arrowup" || key === "w") {
        keys.jump = false;
      }
    });

    window.addEventListener("blur", function () {
      keys.left = false;
      keys.right = false;
      keys.jump = false;
    });

    canvas.addEventListener("mousemove", function (event) {
      const tile = tileFromEvent(event);
      state.hover = tile ? {
        x: tile.x,
        y: tile.y,
        reachable: Interaction.withinReach(state.player, tile.x, tile.y)
      } : null;
      if (state.mining.active && (!tile || tile.x !== state.mining.tile.x || tile.y !== state.mining.tile.y)) {
        Mining.cancel(state.mining);
      }
      updateHud();
    });

    canvas.addEventListener("mouseleave", function () {
      state.hover = null;
      updateHud();
    });

    canvas.addEventListener("mousedown", function (event) {
      audio.unlock();
      const tile = tileFromEvent(event);
      if (!tile || state.paused) {
        return;
      }
      if (event.button === 0) {
        event.preventDefault();
        startMining(tile);
      } else if (event.button === 2) {
        event.preventDefault();
        placeAt(tile);
      }
    });

    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });

    elements.stage.addEventListener("wheel", function (event) {
      if (state.paused) {
        return;
      }
      event.preventDefault();
      const direction = event.deltaY > 0 ? 1 : -1;
      selectSlot(Ui.stepSelection(state.selected, direction));
    }, { passive: false });

    elements.pauseButton.addEventListener("click", function () {
      togglePause();
    });

    elements.resumeButton.addEventListener("click", function () {
      togglePause(false);
    });

    elements.muteButton.addEventListener("click", function () {
      audio.unlock();
      toggleMute();
    });

    elements.seedForm.addEventListener("submit", function (event) {
      event.preventDefault();
      const text = elements.seedInput.value.trim();
      if (!/^\d{1,10}$/.test(text)) {
        toast("Enter a whole-number seed (digits only).", "refuse");
        audio.play("refuse");
        return;
      }
      const seed = Number(text) >>> 0;
      state = createGame(seed);
      elements.seedInput.value = String(seed);
      elements.pauseOverlay.hidden = true;
      elements.pauseButton.textContent = "Pause";
      elements.pauseButton.setAttribute("aria-pressed", "false");
      updateHotbar();
      updateHud();
      draw();
      saveNow("new-world");
      toast("New world · seed " + seed, "notice");
      audio.play("place");
    });

    window.addEventListener("resize", function () {
      fitCanvas();
      fitMinimap();
      draw();
    });

    window.addEventListener("pagehide", function () {
      saveNow("pagehide");
    });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        saveNow("hidden");
      }
    });

    if (reduceQuery) {
      const onChange = function (event) {
        reducedMotion = event.matches;
      };
      if (typeof reduceQuery.addEventListener === "function") {
        reduceQuery.addEventListener("change", onChange);
      } else if (typeof reduceQuery.addListener === "function") {
        reduceQuery.addListener(onChange);
      }
    }
  }

  function buildHotbar() {
    hotbarCaption = document.createElement("div");
    hotbarCaption.className = "hotbar-caption";
    hotbarCaption.textContent = Ui.selectedBlockLabel(CONFIG.starterSelected);
    elements.hotbar.appendChild(hotbarCaption);

    CONFIG.palette.forEach(function (blockId, index) {
      const info = CONFIG.blockInfo[blockId];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot";
      button.dataset.index = String(index);
      button.dataset.block = info.name;
      button.setAttribute("aria-label", info.label + " — key " + (index + 1));

      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.setProperty("--block-light", info.accent);
      swatch.style.setProperty("--block-dark", info.color);

      const key = document.createElement("span");
      key.className = "key";
      key.textContent = String(index + 1);

      const count = document.createElement("span");
      count.className = "count";
      count.textContent = "0";

      button.appendChild(swatch);
      button.appendChild(key);
      button.appendChild(count);
      button.addEventListener("click", function () {
        audio.unlock();
        selectSlot(index);
      });

      elements.hotbar.appendChild(button);
      slotElements.push(button);
      slotCounts.push(count);
    });
  }

  function boot() {
    fitCanvas();
    fitMinimap();
    buildHotbar();
    elements.muteButton.textContent = muted ? "Muted" : "Sound on";
    elements.muteButton.setAttribute("aria-pressed", muted ? "true" : "false");
    const defaultSeed = readDefaultSeed();
    const restored = restoreGame(defaultSeed);
    state = restored.game;
    elements.seedInput.value = String(state.world.seed);
    updateHotbar();
    updateHud();
    bindEvents();
    draw();
    setStatus("ready", "ready");
    statusReady = true;
    saveNow("boot");
    if (restored.notice) {
      toast(restored.notice, "notice");
    }

    const api = {
      getSnapshot: function () {
        return {
          status: elements.status.dataset.state,
          ready: statusReady,
          seed: state.world.seed,
          time: state.clock.fraction,
          clock: Ui.clockModel(state.clock.fraction),
          selected: state.selected,
          paused: state.paused,
          mining: Mining.describe(state.mining),
          hover: state.hover,
          player: {
            x: state.player.x,
            y: state.player.y,
            onGround: state.player.onGround,
            facing: state.player.facing
          },
          camera: { x: state.camera.x, y: state.camera.y },
          view: { width: view.width, height: view.height },
          world: { width: state.world.width, height: state.world.height },
          inventory: Inventory.toJSON(state.inventory),
          hotbar: Ui.hotbarModel(state.inventory, state.selected),
          lastToast: lastToast,
          toastTexts: Array.prototype.map.call(elements.toasts.children, function (element) {
            return element.textContent;
          }),
          pauseOverlayHidden: elements.pauseOverlay.hidden,
          muteButton: elements.muteButton.textContent,
          hotbarSelection: Array.prototype.map.call(elements.hotbar.querySelectorAll(".slot"), function (element, index) {
            return element.classList.contains("is-selected") ? index : -1;
          }).filter(function (index) { return index >= 0; }).pop()
        };
      },
      pixel: function (x, y) {
        const scale = canvas.width / view.width;
        const data = ctx.getImageData(Math.round(x * scale), Math.round(y * scale), 1, 1).data;
        return [data[0], data[1], data[2], data[3]];
      },
      screenForTile: function (tileX, tileY) {
        return {
          x: tileX * CONFIG.tileSize - state.camera.x + CONFIG.tileSize / 2,
          y: tileY * CONFIG.tileSize - state.camera.y + CONFIG.tileSize / 2
        };
      },
      blockAt: function (tileX, tileY) {
        return Interaction.blockAt(state.world, tileX, tileY);
      },
      mine: function (tileX, tileY) {
        return mineAt({ x: tileX, y: tileY });
      },
      place: function (tileX, tileY) {
        return placeAt({ x: tileX, y: tileY });
      },
      select: function (index) {
        selectSlot(index);
      },
      setPaused: function (value) {
        togglePause(value === true);
      },
      setTime: function (fraction) {
        state.clock.fraction = Time.normalize(fraction);
        draw();
      },
      teleport: function (x, y) {
        state.player.x = x;
        state.player.y = y;
        state.player.vy = 0;
        snapCamera(state);
        draw();
      },
      save: function () {
        return saveNow("manual");
      },
      clearSave: function () {
        Persistence.clearState(storage, CONFIG.saveKey);
        dirty = false;
      }
    };

    window.__sandbox = {
      ready: true,
      seed: state.world.seed,
      world: state.world,
      player: state.player,
      camera: state.camera,
      inventory: state.inventory,
      api: api
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
