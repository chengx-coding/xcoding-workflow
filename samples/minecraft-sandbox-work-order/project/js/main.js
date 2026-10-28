(function () {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas ? canvas.getContext("2d") : null;
  const status = document.getElementById("status");
  const selectionLabel = document.getElementById("selection");
  const config = window.SandboxConfig;
  const worldApi = window.SandboxWorld;
  const playerApi = window.SandboxPlayer;
  const interaction = window.SandboxInteraction;
  const saveApi = window.SandboxSave;
  const renderApi = window.SandboxRender;

  function setStatus(state, text) {
    if (!status) {
      return;
    }
    status.dataset.state = state;
    status.title = text;
  }

  function readStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  window.addEventListener("error", function (event) {
    setStatus("error", event.message || "runtime error");
  });
  window.addEventListener("unhandledrejection", function (event) {
    setStatus("error", String(event.reason));
  });

  try {
    if (!canvas || !ctx || !config || !worldApi || !playerApi || !interaction || !saveApi || !renderApi) {
      throw new Error("Sandbox modules failed to load");
    }

    const storage = readStorage();
    const saved = saveApi.loadState(storage);
    let world;
    let player;
    let selected;

    if (saved) {
      world = saved.world;
      player = saved.player;
      selected = saved.selected;
    } else {
      world = worldApi.createWorld(config.seed);
      const spawnY = worldApi.surfaceHeightAt(world.seed, config.spawnX);
      player = playerApi.createPlayer(config.spawnX, spawnY);
      selected = config.blocks.grass;
    }

    const camera = renderApi.cameraForPlayer(world, player);
    const slots = Array.from(document.querySelectorAll("#hotbar .slot"));
    const slotBlocks = slots.map(function slotBlock(slot) {
      return config.blocks[slot.dataset.block];
    });
    const keys = Object.create(null);
    const pointer = { x: 0, y: 0, inside: false };
    let target = null;
    let lastSavedPosition = { x: player.x, y: player.y };
    let lastSaveAt = 0;

    function blockLabel(block) {
      const name = config.blockNames[block] || "block";
      return name.charAt(0).toUpperCase() + name.slice(1);
    }

    function updateHotbar() {
      slots.forEach(function updateSlot(slot, index) {
        const active = slotBlocks[index] === selected;
        slot.classList.toggle("is-selected", active);
        slot.setAttribute("aria-pressed", active ? "true" : "false");
      });
      if (selectionLabel) {
        selectionLabel.textContent = "Selected: " + blockLabel(selected);
      }
    }

    function saveNow() {
      saveApi.saveState(storage, { world: world, player: player, selected: selected });
      lastSavedPosition = { x: player.x, y: player.y };
      lastSaveAt = performance.now();
    }

    function selectSlot(index) {
      if (index < 0 || index >= slotBlocks.length) {
        return;
      }
      const block = slotBlocks[index];
      if (!block || block === selected) {
        return;
      }
      selected = block;
      updateHotbar();
      if (window.__sandbox) {
        window.__sandbox.selected = selected;
      }
      saveNow();
    }

    slots.forEach(function bindSlot(slot, index) {
      slot.addEventListener("click", function chooseSlot() {
        selectSlot(index);
      });
      slot.addEventListener("keydown", function chooseSlotWithKeyboard(event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectSlot(index);
        }
      });
    });

    function slotIndexFromEvent(event) {
      const match = /^(?:Digit|Numpad)([1-9])$/.exec(event.code || "");
      if (match) {
        return Number(match[1]) - 1;
      }
      const keyMatch = /^([1-9])$/.exec(event.key || "");
      return keyMatch ? Number(keyMatch[1]) - 1 : -1;
    }

    const controlCodes = new Set(["KeyA", "KeyD", "ArrowLeft", "ArrowRight", "Space"]);

    window.addEventListener("keydown", function onKeyDown(event) {
      if (controlCodes.has(event.code)) {
        event.preventDefault();
      }
      keys[event.code] = true;
      const index = slotIndexFromEvent(event);
      if (index >= 0) {
        event.preventDefault();
        selectSlot(index);
      }
    });

    window.addEventListener("keyup", function onKeyUp(event) {
      keys[event.code] = false;
    });

    window.addEventListener("blur", function clearKeys() {
      Object.keys(keys).forEach(function clearKey(code) {
        keys[code] = false;
      });
    });

    function currentInput() {
      return {
        left: Boolean(keys.KeyA || keys.ArrowLeft),
        right: Boolean(keys.KeyD || keys.ArrowRight),
        jump: Boolean(keys.Space)
      };
    }

    function updatePointer(event) {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return;
      }
      pointer.x = (event.clientX - rect.left) * (canvas.width / rect.width);
      pointer.y = (event.clientY - rect.top) * (canvas.height / rect.height);
      pointer.inside = true;
    }

    function refreshTarget() {
      if (!pointer.inside) {
        target = null;
        return;
      }
      const cell = interaction.cellFromScreen(camera, pointer.x, pointer.y, config.tileSize);
      if (worldApi.getBlock(world, cell.x, cell.y) === null) {
        target = null;
        return;
      }
      target = {
        x: cell.x,
        y: cell.y,
        inReach: interaction.inReach(player, cell.x, cell.y, config.reach)
      };
    }

    function mineAtPointer() {
      if (!target) {
        return;
      }
      if (interaction.mineBlock(world, player, target.x, target.y)) {
        saveNow();
        refreshTarget();
      }
    }

    function placeAtPointer() {
      if (!target) {
        return;
      }
      const cell = interaction.adjacentPlacementCell(world, player, target.x, target.y);
      if (cell && interaction.placeBlock(world, player, cell.x, cell.y, selected)) {
        saveNow();
        refreshTarget();
      }
    }

    canvas.addEventListener("pointermove", function onPointerMove(event) {
      updatePointer(event);
      refreshTarget();
    });
    canvas.addEventListener("pointerleave", function onPointerLeave() {
      pointer.inside = false;
      target = null;
    });
    canvas.addEventListener("pointerdown", function onPointerDown(event) {
      updatePointer(event);
      refreshTarget();
      if (event.button === 0) {
        mineAtPointer();
      } else if (event.button === 2) {
        placeAtPointer();
      }
    });
    canvas.addEventListener("contextmenu", function blockMenu(event) {
      event.preventDefault();
    });

    function updateSimulation() {
      playerApi.stepPlayer(player, world, currentInput(), 1);
      const nextCamera = renderApi.cameraForPlayer(world, player);
      camera.x = nextCamera.x;
      camera.y = nextCamera.y;
    }

    function draw() {
      refreshTarget();
      renderApi.renderFrame(ctx, {
        world: world,
        player: player,
        camera: camera,
        target: target,
        selected: selected
      });
    }

    function maybeAutoSave(now) {
      if (now - lastSaveAt < 5000) {
        return;
      }
      const moved =
        Math.abs(player.x - lastSavedPosition.x) > 0.05 ||
        Math.abs(player.y - lastSavedPosition.y) > 0.05;
      if (moved) {
        saveNow();
      } else {
        lastSaveAt = now;
      }
    }

    let lastFrame = performance.now();
    let accumulator = 0;
    let ready = false;
    const maxSteps = 5;

    function frame(now) {
      const elapsed = Math.min(100, Math.max(0, now - lastFrame));
      lastFrame = now;
      accumulator += elapsed;
      let steps = 0;
      while (accumulator >= config.stepMs && steps < maxSteps) {
        updateSimulation();
        accumulator -= config.stepMs;
        steps += 1;
      }
      if (steps === maxSteps) {
        accumulator = 0;
      }
      draw();
      maybeAutoSave(now);
      if (!ready) {
        ready = true;
        setStatus("ready", "ready");
      }
      window.requestAnimationFrame(frame);
    }

    window.addEventListener("beforeunload", saveNow);
    window.addEventListener("pagehide", saveNow);

    updateHotbar();
    draw();
    setStatus("ready", "ready");
    window.__sandbox = {
      world: world,
      player: player,
      camera: camera,
      selected: selected,
      ready: true
    };
    lastFrame = performance.now();
    window.requestAnimationFrame(frame);
  } catch (error) {
    setStatus("error", error && error.message ? error.message : String(error));
    throw error;
  }
})();
