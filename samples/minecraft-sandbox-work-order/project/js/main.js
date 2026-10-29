(function () {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const status = document.getElementById("status");
  const config = window.SandboxConfig;
  const worldApi = window.SandboxWorld;
  const playerApi = window.SandboxPlayer;
  const interaction = window.SandboxInteraction;
  const cameraApi = window.SandboxCamera;
  const storage = window.SandboxStorage;
  const renderApi = window.SandboxRender;

  const seedValue = document.getElementById("seedValue");
  const clockText = document.getElementById("clockText");
  const clockIcon = document.getElementById("clockIcon");
  const coordsText = document.getElementById("coordsText");
  const soundButton = document.getElementById("soundButton");
  const helpButton = document.getElementById("helpButton");
  const newWorldButton = document.getElementById("newWorldButton");
  const seedChip = document.getElementById("seedChip");
  const helpPanel = document.getElementById("helpPanel");
  const seedPanel = document.getElementById("seedPanel");
  const seedInput = document.getElementById("seedInput");
  const randomSeed = document.getElementById("randomSeed");
  const generateWorld = document.getElementById("generateWorld");
  const hotbarSlots = document.getElementById("hotbarSlots");
  const selectedLabel = document.getElementById("selectedLabel");
  const targetReadout = document.getElementById("targetReadout");
  const targetName = document.getElementById("targetName");
  const targetHint = document.getElementById("targetHint");
  const toastArea = document.getElementById("toastArea");
  const saveIndicator = document.getElementById("saveIndicator");
  const saveText = document.getElementById("saveText");
  const journalCount = document.getElementById("journalCount");
  const journalTitle = document.getElementById("journalTitle");
  const journalSubtitle = document.getElementById("journalSubtitle");
  const journalFooter = document.getElementById("journalFooter");
  const objectivesList = document.getElementById("objectives");
  const minimap = document.getElementById("minimap");
  const minimapCtx = minimap.getContext("2d");
  const biomeLabel = document.getElementById("biomeLabel");

  const OBJECTIVES = [
    { id: "mine", title: "Make a mark", detail: "Mine 5 blocks", target: 5, value: function () { return stats.mined; } },
    { id: "place", title: "Hand of creation", detail: "Place 5 blocks", target: 5, value: function () { return stats.placed; } },
    { id: "crystal", title: "A deep signal", detail: "Find a prism crystal", target: 1, value: function () { return stats.crystals; } },
    { id: "roam", title: "Know the valley", detail: "Travel 80 tiles", target: 80, value: function () { return Math.floor(stats.distance); } }
  ];

  let world;
  let player;
  let camera;
  let selectedIndex = 0;
  let timeOfDay = config.initialTimeOfDay;
  let elapsed = 0;
  let stats = { mined: 0, placed: 0, distance: 0, crystals: 0 };
  let muted = false;
  let particles = [];
  let hover = null;
  let pointerScreen = null;
  let saveDirty = false;
  let lastSaveAt = 0;
  let lastMinimapAt = 0;
  let lastHudAt = 0;
  let objectiveNodes = {};
  let completedObjectives = {};
  let audioContext = null;
  let generatedFromSave = false;
  let animationFrame = 0;

  function setStatus(state, text) {
    status.dataset.state = state;
    status.title = text;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function formatClock(value) {
    const totalMinutes = Math.floor((value % 1) * 24 * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function isNight() {
    return renderApi.daylightAt(timeOfDay) < 0.26;
  }

  function biomeName() {
    if (!world || !player) {
      return "Meadow";
    }
    const x = clamp(Math.floor(player.x), 0, world.width - 1);
    if (player.y > world.ground[x] + 2.5) {
      return "Understory";
    }
    if (world.biomes[x] === 2) {
      return "Dune";
    }
    if (world.biomes[x] === 1) {
      return "Woodland";
    }
    return "Meadow";
  }

  function toast(message) {
    if (!toastArea) {
      return;
    }
    const element = document.createElement("div");
    element.className = "toast";
    element.textContent = message;
    toastArea.appendChild(element);
    while (toastArea.children.length > 3) {
      toastArea.removeChild(toastArea.firstChild);
    }
    window.setTimeout(function () {
      element.classList.add("is-leaving");
      window.setTimeout(function () {
        element.remove();
      }, 260);
    }, 2400);
  }

  function setSavingState(state, text) {
    saveIndicator.classList.toggle("is-saving", state === "saving");
    saveIndicator.classList.toggle("is-error", state === "error");
    saveText.textContent = text;
  }

  function browserStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  function saveGame(reason) {
    lastSaveAt = performance.now();
    setSavingState("saving", "Saving");
    const result = storage.writeSave(browserStorage(), config.saveKey, world, player, {
      selected: selectedIndex,
      timeOfDay: timeOfDay,
      stats: stats,
      muted: muted
    });
    if (result.ok) {
      saveDirty = false;
      setSavingState("idle", "Saved");
    } else {
      setSavingState("error", "Save unavailable");
      if (reason !== "auto") {
        toast("Local saving is unavailable.");
      }
    }
  }

  function markDirty() {
    saveDirty = true;
  }

  function soundIsAvailable() {
    return audioContext && audioContext.state !== "closed";
  }

  function ensureAudio() {
    if (audioContext) {
      if (audioContext.state === "suspended") {
        audioContext.resume();
      }
      return audioContext;
    }
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) {
      return null;
    }
    try {
      audioContext = new Context();
      return audioContext;
    } catch (error) {
      return null;
    }
  }

  function tone(startFrequency, endFrequency, duration, type, volume) {
    if (muted || !soundIsAvailable()) {
      return;
    }
    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = type || "sine";
    oscillator.frequency.setValueAtTime(startFrequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(20, endFrequency), now + duration);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(volume || 0.035, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.02);
  }

  function playSound(name) {
    if (muted) {
      return;
    }
    ensureAudio();
    if (!soundIsAvailable()) {
      return;
    }
    if (name === "mine") {
      tone(210, 82, 0.11, "square", 0.025);
    } else if (name === "place") {
      tone(290, 460, 0.1, "triangle", 0.032);
    } else if (name === "select") {
      tone(520, 680, 0.055, "sine", 0.018);
    } else if (name === "jump") {
      tone(300, 500, 0.08, "sine", 0.014);
    } else if (name === "error") {
      tone(120, 90, 0.13, "sawtooth", 0.02);
    } else if (name === "quest") {
      tone(440, 660, 0.18, "sine", 0.028);
      window.setTimeout(function () {
        tone(660, 880, 0.2, "sine", 0.02);
      }, 90);
    }
  }

  function isModalOpen() {
    return !helpPanel.hidden || !seedPanel.hidden;
  }

  function openModal(panel) {
    helpPanel.hidden = panel !== helpPanel;
    seedPanel.hidden = panel !== seedPanel;
    if (panel === seedPanel) {
      seedInput.value = String(world ? world.seed : config.seed);
      window.setTimeout(function () {
        seedInput.focus();
        seedInput.select();
      }, 30);
    }
    input.left = false;
    input.right = false;
    input.jumpHeld = false;
    hover = null;
    updateTargetReadout();
  }

  function closeModal(panel) {
    if (panel === helpPanel) {
      helpPanel.hidden = true;
    }
    if (panel === seedPanel) {
      seedPanel.hidden = true;
    }
  }

  function closeAllModals() {
    helpPanel.hidden = true;
    seedPanel.hidden = true;
  }

  function toggleHelp() {
    if (!helpPanel.hidden) {
      closeModal(helpPanel);
    } else {
      openModal(helpPanel);
    }
  }

  function toggleMute() {
    muted = !muted;
    soundButton.classList.toggle("is-muted", muted);
    soundButton.textContent = muted ? "✕" : "♪";
    soundButton.title = muted ? "Sound muted" : "Toggle sound";
    if (!muted) {
      ensureAudio();
      playSound("select");
    }
    markDirty();
    toast(muted ? "Sound muted" : "Sound on");
  }

  const input = {
    left: false,
    right: false,
    jumpHeld: false,
    jumpPressed: false,
    sprint: false
  };

  function buildHotbar() {
    config.hotbar.forEach(function (block, index) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot";
      button.dataset.index = String(index);
      button.title = config.blockNames[block] + " · press " + (index + 1);
      button.setAttribute("aria-label", "Select " + config.blockNames[block]);

      const key = document.createElement("span");
      key.className = "slot-key";
      key.textContent = String(index + 1);

      const icon = document.createElement("canvas");
      icon.width = 40;
      icon.height = 40;
      renderApi.blockIcon(icon.getContext("2d"), block, 40);

      const name = document.createElement("span");
      name.className = "slot-name";
      name.textContent = config.blockShortNames[block] || "Block";

      button.appendChild(key);
      button.appendChild(icon);
      button.appendChild(name);
      button.addEventListener("click", function () {
        ensureAudio();
        selectSlot(index, false);
      });
      hotbarSlots.appendChild(button);
    });
  }

  function selectSlot(index, silent) {
    selectedIndex = clamp(index, 0, config.hotbar.length - 1);
    Array.prototype.forEach.call(hotbarSlots.children, function (slot, slotIndex) {
      slot.classList.toggle("is-selected", slotIndex === selectedIndex);
    });
    const block = config.hotbar[selectedIndex];
    selectedLabel.textContent = config.blockNames[block];
    if (!silent) {
      playSound("select");
      toast(config.blockShortNames[block] || "Block");
    }
    markDirty();
    recomputeHover();
  }

  function resetWorldState(nextWorld, spawn) {
    world = nextWorld;
    player = playerApi.createPlayer(spawn.x, spawn.y);
    playerApi.teleportToSpawn(player, world, spawn);
    camera = cameraApi.createCamera();
    cameraApi.updateCamera(camera, world, player, 0, true);
    particles = [];
    hover = null;
    pointerScreen = null;
    timeOfDay = config.initialTimeOfDay;
    elapsed = 0;
    stats = { mined: 0, placed: 0, distance: 0, crystals: 0 };
    completedObjectives = {};
    updateObjectiveDom(true);
    updateHud(true);
    markDirty();
    saveGame("new-world");
  }

  function createFreshWorld(seed) {
    const nextWorld = worldApi.createWorld(seed);
    const spawn = worldApi.findSpawn(nextWorld);
    resetWorldState(nextWorld, spawn);
    seedValue.textContent = String(nextWorld.seed);
    seedInput.value = String(nextWorld.seed);
    renderMinimap(true);
  }

  function generateNewWorld() {
    const requested = Number(seedInput.value);
    if (!Number.isFinite(requested)) {
      toast("Enter a numeric seed first.");
      playSound("error");
      return;
    }
    const normalized = worldApi.normalizeSeed(requested);
    createFreshWorld(normalized);
    closeModal(seedPanel);
    toast("World " + normalized + " grown.");
    playSound("quest");
  }

  function randomizeSeed() {
    seedInput.value = String(100000 + Math.floor(Math.random() * 899999999));
    seedInput.focus();
    seedInput.select();
  }

  function restoreOrCreate() {
    const result = storage.readSave(browserStorage(), config.saveKey);
    if (result.ok) {
      generatedFromSave = true;
      world = result.value.world;
      player = playerApi.createPlayer(result.value.player.x, result.value.player.y);
      player.facing = result.value.player.facing || 1;
      let attempts = 0;
      while (
        playerApi.overlapsSolid(world, player.x, player.y, player.width, player.height) &&
        attempts < 80
      ) {
        player.y -= 0.35;
        attempts += 1;
      }
      if (attempts >= 80) {
        const spawn = worldApi.findSpawn(world, player.x);
        playerApi.teleportToSpawn(player, world, spawn);
      }
      player.onGround = false;
      camera = cameraApi.createCamera();
      selectedIndex = result.value.selected;
      timeOfDay = result.value.timeOfDay;
      stats = result.value.stats;
      muted = result.value.settings.muted;
      soundButton.classList.toggle("is-muted", muted);
      soundButton.textContent = muted ? "✕" : "♪";
      cameraApi.updateCamera(camera, world, player, 0, true);
      updateObjectiveDom(true);
      return;
    }

    if (result.reason === "invalid-json" || result.reason === "world" || result.reason === "player" || result.reason === "version") {
      storage.clearSave(browserStorage(), config.saveKey);
      window.setTimeout(function () {
        toast("Old save folded away — a fresh valley grew.");
      }, 500);
    }

    world = worldApi.createWorld(config.seed);
    const spawn = worldApi.findSpawn(world);
    player = playerApi.createPlayer(spawn.x, spawn.y);
    playerApi.teleportToSpawn(player, world, spawn);
    camera = cameraApi.createCamera();
    selectedIndex = 0;
    timeOfDay = config.initialTimeOfDay;
    stats = { mined: 0, placed: 0, distance: 0, crystals: 0 };
    cameraApi.updateCamera(camera, world, player, 0, true);
    updateObjectiveDom(true);
  }

  function updateObjectiveDom(silent) {
    if (!world) {
      return;
    }
    if (Object.keys(objectiveNodes).length === 0) {
      OBJECTIVES.forEach(function (objective) {
        const item = document.createElement("li");
        item.className = "objective";
        const mark = document.createElement("span");
        mark.className = "objective-mark";
        mark.textContent = "✓";
        const label = document.createElement("span");
        label.textContent = objective.detail;
        const progress = document.createElement("span");
        progress.className = "objective-progress";
        item.appendChild(mark);
        item.appendChild(label);
        item.appendChild(progress);
        objectivesList.appendChild(item);
        objectiveNodes[objective.id] = { item: item, progress: progress };
      });
    }

    let doneCount = 0;
    OBJECTIVES.forEach(function (objective) {
      const value = clamp(objective.value(), 0, objective.target);
      const done = value >= objective.target;
      if (done) {
        doneCount += 1;
      }
      const nodes = objectiveNodes[objective.id];
      nodes.item.classList.toggle("done", done);
      nodes.progress.textContent = done ? "done" : value + "/" + objective.target;
      if (done && !completedObjectives[objective.id]) {
        completedObjectives[objective.id] = true;
        if (!silent) {
          playSound("quest");
          toast(objective.title + " complete");
        }
      }
    });

    journalCount.textContent = doneCount + " / " + OBJECTIVES.length;
    const next = OBJECTIVES.find(function (objective) {
      return !completedObjectives[objective.id];
    });
    if (next) {
      journalTitle.textContent = next.title;
      journalSubtitle.textContent = next.id === "crystal"
        ? "Crystal seams sleep beneath the stone. Follow the deep glow."
        : next.id === "roam"
          ? "Walk the ridge lines. The valley keeps its scale secret."
          : next.id === "place"
            ? "The world is soft clay. Add something of your own."
            : "The valley is yours to shape, one block at a time.";
      journalFooter.textContent = "Autosave keeps this world close.";
    } else {
      journalTitle.textContent = "A living valley";
      journalSubtitle.textContent = "Every note is complete. Keep building anyway.";
      journalFooter.textContent = "This world is yours to keep.";
    }
  }

  function updateHud(force) {
    if (!world || !player) {
      return;
    }
    const now = performance.now();
    if (!force && now - lastHudAt < 120) {
      return;
    }
    lastHudAt = now;
    seedValue.textContent = String(world.seed);
    clockText.textContent = formatClock(timeOfDay);
    clockIcon.textContent = isNight() ? "☾" : renderApi.daylightAt(timeOfDay) < 0.5 ? "◐" : "☀";
    coordsText.textContent = "x " + Math.round(player.x) + " · y " + Math.round(player.y);
    biomeLabel.textContent = biomeName();
    updateObjectiveDom(false);
  }

  function updateTargetReadout() {
    if (!hover || isModalOpen() || !pointerScreen) {
      targetReadout.classList.remove("is-visible");
      return;
    }
    const block = hover.block;
    let name = "Open air";
    if (block !== null && block !== config.blocks.air) {
      name = config.blockNames[block] || "Unknown block";
    }
    let hint = "Left click to mine";
    if (!hover.empty && !hover.canMine) {
      hint = "Out of reach";
    } else if (hover.canPlace) {
      hint = hover.empty ? "Right click to build" : "Right click on the face to build";
    } else if (hover.empty) {
      hint = hover.placement && hover.placement.reason === "unsupported" ? "Needs a solid neighbour" : "No room to build";
    } else if (block === config.blocks.bedrock) {
      hint = "The deep stone refuses";
    }
    targetName.textContent = name;
    targetHint.textContent = hint;
    targetReadout.classList.add("is-visible");
  }

  function canvasCoordinates(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * config.viewWidth,
      y: ((event.clientY - rect.top) / rect.height) * config.viewHeight
    };
  }

  function recomputeHover() {
    if (!world || !player || !pointerScreen || isModalOpen()) {
      hover = null;
      updateTargetReadout();
      return;
    }
    const worldPoint = cameraApi.screenToWorld(camera, pointerScreen.x, pointerScreen.y);
    hover = interaction.inspectTarget(
      world,
      player,
      worldPoint.x,
      worldPoint.y,
      config.hotbar[selectedIndex],
      config.reach
    );
    updateTargetReadout();
  }

  function respawnPlayer() {
    const spawn = worldApi.findSpawn(world, player.x);
    playerApi.teleportToSpawn(player, world, spawn);
    cameraApi.updateCamera(camera, world, player, 0, true);
    toast("The valley folded you back to solid ground.");
    playSound("error");
  }

  function handleMine() {
    if (!hover || isModalOpen()) {
      return;
    }
    ensureAudio();
    if (!hover.canMine) {
      const reason = hover.block === null
        ? "outside"
        : hover.block === config.blocks.bedrock
          ? "bedrock"
          : hover.block === config.blocks.air
            ? "empty"
            : "reach";
      if (reason === "reach") {
        toast("That block is beyond your reach.");
      } else if (reason === "bedrock") {
        toast("The deep stone refuses your pick.");
      } else if (reason === "empty") {
        toast("Nothing to mine there.");
      }
      playSound("error");
      return;
    }
    const result = interaction.mineBlock(world, player, hover.x, hover.y, config.reach);
    if (!result.ok) {
      toast("Nothing gave way.");
      playSound("error");
      return;
    }
    stats.mined += 1;
    if (result.block === config.blocks.crystal) {
      stats.crystals += 1;
    }
    renderApi.spawnBlockBurst(particles, hover.x, hover.y, result.block, 12);
    cameraApi.addShake(camera, 1.8, 0.12);
    playSound("mine");
    markDirty();
    updateObjectiveDom(false);
    updateHud(true);
    recomputeHover();
    saveGame("mine");
    if (result.block === config.blocks.crystal) {
      toast("A prism crystal hums in your hand.");
    }
  }

  function handlePlace() {
    if (!hover || isModalOpen()) {
      return;
    }
    ensureAudio();
    if (!hover.placement || !hover.placement.ok) {
      const reason = hover.placement ? hover.placement.reason : "outside";
      const messages = {
        reach: "That spot is beyond your reach.",
        occupied: "That cell is already occupied.",
        player: "You cannot build inside yourself.",
        unsupported: "A block needs a solid neighbour.",
        outside: "That is outside the valley.",
        "invalid-block": "That block cannot be placed."
      };
      toast(messages[reason] || "The block will not sit there.");
      playSound("error");
      return;
    }
    const target = hover.placement;
    const result = interaction.placeBlock(
      world,
      player,
      target.x,
      target.y,
      config.hotbar[selectedIndex],
      config.reach
    );
    if (!result.ok) {
      toast("The block will not sit there.");
      playSound("error");
      return;
    }
    stats.placed += 1;
    renderApi.spawnSparkles(particles, target.x, target.y, 9, "#ffe49a");
    cameraApi.addShake(camera, 1.2, 0.09);
    playSound("place");
    markDirty();
    updateObjectiveDom(false);
    updateHud(true);
    recomputeHover();
    saveGame("place");
  }

  function renderMinimap(force) {
    if (!world || !player || !camera) {
      return;
    }
    const now = performance.now();
    if (!force && now - lastMinimapAt < 420) {
      return;
    }
    lastMinimapAt = now;
    renderApi.renderMinimap(minimapCtx, world, player, camera, minimap.width, minimap.height);
  }

  function frame(now) {
    try {
      const delta = Math.min((now - frame.lastTime) / 1000 || 0, 0.05);
      frame.lastTime = now;
      frame.accumulator += delta;
      let steps = 0;
      const previousX = player.x;
      const previousY = player.y;

      while (frame.accumulator >= config.fixedStep && steps < 6) {
        const wasGrounded = player.onGround;
        playerApi.stepPlayer(player, world, input, config.fixedStep);
        if (wasGrounded && !player.onGround && player.vy < 0) {
          playSound("jump");
        }
        input.jumpPressed = false;
        elapsed += config.fixedStep;
        timeOfDay = (timeOfDay + config.fixedStep / config.dayLengthSeconds) % 1;
        renderApi.updateParticles(particles, config.fixedStep);
        cameraApi.updateShake(camera, config.fixedStep);
        frame.accumulator -= config.fixedStep;
        steps += 1;
      }
      if (steps === 6) {
        frame.accumulator = 0;
      }

      const movedX = player.x - previousX;
      const movedY = player.y - previousY;
      stats.distance += Math.sqrt(movedX * movedX + movedY * movedY);

      if (player.y > world.height + 4) {
        respawnPlayer();
      }

      cameraApi.updateCamera(camera, world, player, delta, false);
      recomputeHover();
      renderApi.renderFrame(ctx, {
        world: world,
        player: player,
        camera: camera,
        hover: hover,
        selectedBlock: config.hotbar[selectedIndex],
        dayTime: timeOfDay,
        time: elapsed,
        particles: particles
      });
      updateHud(false);
      renderMinimap(false);

      if (saveDirty && now - lastSaveAt > 1500) {
        saveGame("auto");
      }

      if (!frame.settled) {
        frame.settled = true;
        setStatus("ready", "ready");
        window.__sandbox = createSandboxHandle();
      }

      animationFrame = window.requestAnimationFrame(frame);
    } catch (error) {
      setStatus("error", error && error.message ? error.message : String(error));
      window.cancelAnimationFrame(animationFrame);
      toast("The valley stumbled. Check the console for the exact path.");
      throw error;
    }
  }

  function bindEvents() {
    window.addEventListener("keydown", function (event) {
      const tag = event.target && event.target.tagName ? event.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea") {
        if (event.code === "Escape") {
          closeAllModals();
        }
        return;
      }
      if (event.code === "KeyA" || event.code === "ArrowLeft") {
        input.left = true;
        event.preventDefault();
      } else if (event.code === "KeyD" || event.code === "ArrowRight") {
        input.right = true;
        event.preventDefault();
      } else if (event.code === "Space") {
        ensureAudio();
        if (!event.repeat) {
          input.jumpPressed = true;
        }
        input.jumpHeld = true;
        event.preventDefault();
      } else if (event.code === "ShiftLeft" || event.code === "ShiftRight") {
        input.sprint = true;
      } else if (event.code === "KeyH") {
        toggleHelp();
        event.preventDefault();
      } else if (event.code === "KeyM") {
        toggleMute();
        event.preventDefault();
      } else if (event.code === "Escape") {
        closeAllModals();
      } else if (/^Digit[1-9]$/.test(event.code)) {
        const index = Number(event.code.slice(5)) - 1;
        if (index < config.hotbar.length) {
          ensureAudio();
          selectSlot(index, false);
        }
        event.preventDefault();
      }
    });

    window.addEventListener("keyup", function (event) {
      if (event.code === "KeyA" || event.code === "ArrowLeft") {
        input.left = false;
      } else if (event.code === "KeyD" || event.code === "ArrowRight") {
        input.right = false;
      } else if (event.code === "Space") {
        input.jumpHeld = false;
      } else if (event.code === "ShiftLeft" || event.code === "ShiftRight") {
        input.sprint = false;
      }
    });

    window.addEventListener("blur", function () {
      input.left = false;
      input.right = false;
      input.jumpHeld = false;
      input.sprint = false;
    });

    canvas.addEventListener("pointermove", function (event) {
      pointerScreen = canvasCoordinates(event);
      recomputeHover();
    });

    canvas.addEventListener("pointerenter", function (event) {
      pointerScreen = canvasCoordinates(event);
      recomputeHover();
    });

    canvas.addEventListener("pointerleave", function () {
      pointerScreen = null;
      hover = null;
      updateTargetReadout();
    });

    canvas.addEventListener("pointerdown", function (event) {
      if (isModalOpen()) {
        return;
      }
      ensureAudio();
      pointerScreen = canvasCoordinates(event);
      recomputeHover();
      if (event.button === 0) {
        event.preventDefault();
        handleMine();
      } else if (event.button === 2) {
        event.preventDefault();
        handlePlace();
      }
    });

    canvas.addEventListener("contextmenu", function (event) {
      event.preventDefault();
    });

    canvas.addEventListener("wheel", function (event) {
      if (isModalOpen()) {
        return;
      }
      event.preventDefault();
      const direction = event.deltaY > 0 ? 1 : -1;
      ensureAudio();
      selectSlot((selectedIndex + direction + config.hotbar.length) % config.hotbar.length, false);
    }, { passive: false });

    seedChip.addEventListener("click", function () {
      openModal(seedPanel);
    });

    newWorldButton.addEventListener("click", function () {
      openModal(seedPanel);
    });

    helpButton.addEventListener("click", toggleHelp);
    soundButton.addEventListener("click", toggleMute);
    randomSeed.addEventListener("click", randomizeSeed);
    generateWorld.addEventListener("click", generateNewWorld);

    seedInput.addEventListener("keydown", function (event) {
      if (event.code === "Enter") {
        generateNewWorld();
      }
    });

    document.querySelectorAll("[data-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        closeModal(document.getElementById(button.dataset.close));
      });
    });

    document.querySelectorAll("[data-seed]").forEach(function (button) {
      button.addEventListener("click", function () {
        seedInput.value = button.dataset.seed;
      });
    });

    [helpPanel, seedPanel].forEach(function (panel) {
      panel.addEventListener("pointerdown", function (event) {
        if (event.target === panel) {
          closeModal(panel);
        }
      });
    });

    window.addEventListener("beforeunload", function () {
      if (world && player) {
        saveGame("unload");
      }
    });
  }

  function createSandboxHandle() {
    return {
      get world() {
        return world;
      },
      get player() {
        return player;
      },
      get camera() {
        return camera;
      },
      ready: true,
      save: function () { saveGame("manual"); },
      newWorld: createFreshWorld,
      setDayTime: function (value) {
        if (Number.isFinite(value)) {
          timeOfDay = ((value % 1) + 1) % 1;
        }
      }
    };
  }

  function boot() {
    setStatus("booting", "booting");
    restoreOrCreate();
    buildHotbar();
    selectSlot(selectedIndex, true);
    bindEvents();
    updateHud(true);
    renderMinimap(true);

    frame.lastTime = performance.now();
    frame.accumulator = 0;
    frame.settled = false;
    renderApi.renderFrame(ctx, {
      world: world,
      player: player,
      camera: camera,
      hover: null,
      selectedBlock: config.hotbar[selectedIndex],
      dayTime: timeOfDay,
      time: elapsed,
      particles: particles
    });
    updateHud(true);
    renderMinimap(true);
    setStatus("ready", "ready");
    window.__sandbox = createSandboxHandle();
    if (!generatedFromSave) {
      window.setTimeout(function () {
        toast("Press H for the field manual.");
      }, 600);
    } else {
      window.setTimeout(function () {
        toast("World restored from your local save.");
      }, 500);
    }
    animationFrame = window.requestAnimationFrame(frame);
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
