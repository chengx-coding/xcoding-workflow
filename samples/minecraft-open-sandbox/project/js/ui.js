(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const INVENTORY = window.SandboxInventory;
  const TEXTURES = window.SandboxTextures;

  const TUTORIAL_TASKS = [
    { id: "wood", label: "Gather logs", hint: "Hold left mouse on a tree" },
    { id: "planks", label: "Craft planks", hint: "Open your pack with E" },
    { id: "table", label: "Make a crafting table", hint: "4 planks, crafted anywhere" },
    { id: "place_table", label: "Place the table", hint: "Pick it in the hotbar, right-click" },
    { id: "wood_pickaxe", label: "Craft a wooden pickaxe", hint: "Stand near the table" },
    { id: "stone", label: "Mine stone", hint: "A wooden pickaxe will do" },
    { id: "stone_pickaxe", label: "Craft a stone pickaxe", hint: "3 cobblestone + 2 sticks" },
    { id: "torch", label: "Place a torch", hint: "Coal + stick makes four" }
  ];

  const PHASES = [
    { at: 0, name: "Night" },
    { at: 0.2, name: "Dawn" },
    { at: 0.32, name: "Morning" },
    { at: 0.52, name: "Afternoon" },
    { at: 0.67, name: "Dusk" },
    { at: 0.8, name: "Night" }
  ];

  function byId(id) {
    return document.getElementById(id);
  }

  function timeString(timeOfDay) {
    const totalMinutes = Math.round((timeOfDay % 1) * 24 * 60) % (24 * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function phaseName(timeOfDay) {
    let name = "Night";
    for (let index = 0; index < PHASES.length; index += 1) {
      if (timeOfDay >= PHASES[index].at) {
        name = PHASES[index].name;
      }
    }
    return name;
  }

  function relativeSaved(savedAt) {
    if (!savedAt) {
      return "saved earlier";
    }
    const seconds = Math.max(0, Math.round((Date.now() - savedAt) / 1000));
    if (seconds < 45) {
      return "saved just now";
    }
    if (seconds < 3600) {
      return "saved " + Math.round(seconds / 60) + "m ago";
    }
    return "saved " + Math.round(seconds / 3600) + "h ago";
  }

  function createUI(actions) {
    const elements = {
      app: byId("app"),
      start: byId("start-screen"),
      help: byId("help-screen"),
      pause: byId("pause-screen"),
      inventory: byId("inventory-screen"),
      death: byId("death-screen"),
      confirm: byId("confirm-screen"),
      play: byId("btn-play"),
      newWorld: byId("btn-new-world"),
      howTo: byId("btn-how-to"),
      helpButton: byId("btn-help"),
      helpClose: byId("btn-help-close"),
      helpDone: byId("btn-help-done"),
      pauseHelp: byId("btn-pause-help"),
      pauseSound: byId("btn-pause-sound"),
      sound: byId("btn-sound"),
      inventoryButton: byId("btn-inventory"),
      pauseButton: byId("btn-pause"),
      inventoryClose: byId("btn-inventory-close"),
      resume: byId("btn-resume"),
      pauseSave: byId("btn-pause-save"),
      pauseNew: byId("btn-pause-new"),
      pauseTitle: byId("btn-pause-title"),
      respawn: byId("btn-respawn"),
      confirmNew: byId("btn-confirm-new"),
      cancelNew: byId("btn-cancel-new"),
      hearts: byId("hearts"),
      healthText: byId("health-text"),
      clock: byId("clock"),
      coords: byId("coords"),
      phase: byId("phase-label"),
      questList: byId("quest-list"),
      questProgress: byId("quest-progress"),
      hotbar: byId("hotbar"),
      minimap: byId("minimap-wrap"),
      saveState: byId("save-state"),
      pauseSaveNote: byId("pause-save-note"),
      startSeed: byId("start-seed"),
      startSaveNote: byId("start-save-note"),
      stationStrip: byId("station-strip"),
      inventoryFeedback: byId("inventory-feedback"),
      inventoryMain: byId("inventory-main"),
      inventoryHotbar: byId("inventory-hotbar"),
      craftList: byId("craft-list"),
      recipeCount: byId("recipe-count"),
      toast: byId("toast"),
      dragGhost: byId("drag-ghost"),
      deathStats: byId("death-stats"),
      canvas: byId("game")
    };

    const ScreenIds = ["start", "help", "pause", "inventory", "death", "confirm"];
    const state = {
      screen: null,
      helpReturn: null,
      confirmReturn: null,
      hasSave: false,
      held: null,
      pointerX: window.innerWidth / 2,
      pointerY: window.innerHeight / 2,
      hotbarSignature: "",
      tutorialSignature: "",
      lastFocused: null,
      toastTimer: 0,
      toastQueue: [],
      feedbackTimer: 0
    };

    function makeDialog(screen) {
      if (!screen) {
        return;
      }
      screen.setAttribute("role", "dialog");
      screen.setAttribute("aria-modal", "true");
    }
    ScreenIds.forEach(function (id) {
      makeDialog(elements[id]);
    });

    function hideAllScreens() {
      ScreenIds.forEach(function (id) {
        if (elements[id]) {
          elements[id].hidden = true;
        }
      });
      state.screen = null;
    }

    function rememberFocus() {
      state.lastFocused = document.activeElement;
    }

    function restoreFocus() {
      if (state.lastFocused && typeof state.lastFocused.focus === "function") {
        state.lastFocused.focus({ preventScroll: true });
      } else if (elements.canvas) {
        elements.canvas.focus({ preventScroll: true });
      }
    }

    function clearToast() {
      state.toastQueue.length = 0;
      if (state.toastTimer) {
        window.clearTimeout(state.toastTimer);
        state.toastTimer = 0;
      }
      if (elements.toast) {
        elements.toast.classList.remove("is-visible");
      }
    }

    function openScreen(name, focusId) {
      if (state.screen === null) {
        rememberFocus();
      }
      clearToast();
      hideAllScreens();
      const screen = elements[name];
      if (!screen) {
        return;
      }
      screen.hidden = false;
      state.screen = name;
      const focusTarget = focusId ? byId(focusId) : screen.querySelector("button");
      if (focusTarget && typeof focusTarget.focus === "function") {
        setTimeout(function () {
          focusTarget.focus({ preventScroll: true });
        }, 0);
      }
    }

    function closeAll() {
      hideAllScreens();
      restoreFocus();
    }

    function setSoundLabels(muted) {
      const label = muted ? "Sound: Off" : "Sound: On";
      elements.sound.textContent = muted ? "Muted" : "Sound";
      elements.sound.setAttribute("aria-label", muted ? "Enable sound" : "Mute sound");
      elements.pauseSound.textContent = label;
    }

    function setSaveState(text, kind) {
      elements.saveState.textContent = text;
      elements.saveState.dataset.state = kind || "idle";
      elements.pauseSaveNote.textContent = text;
    }

    function buildHearts() {
      elements.hearts.innerHTML = "";
      for (let index = 0; index < CONFIG.maxHealth; index += 1) {
        const heart = document.createElement("span");
        heart.className = "heart";
        heart.textContent = "♥";
        elements.hearts.appendChild(heart);
      }
    }
    buildHearts();

    function updateHearts(stateData) {
      const health = Math.max(0, Math.min(CONFIG.maxHealth, Math.round(stateData.player.health)));
      const hearts = elements.hearts.querySelectorAll(".heart");
      for (let index = 0; index < hearts.length; index += 1) {
        hearts[index].classList.toggle("empty", index >= health);
      }
      elements.hearts.setAttribute("aria-label", "Health " + health + " of " + CONFIG.maxHealth);
      elements.healthText.textContent = health + " / " + CONFIG.maxHealth;
    }

    function updateTutorial(stateData) {
      const completed = stateData.tutorial.completed || [];
      const done = TUTORIAL_TASKS.filter(function (task) { return completed.indexOf(task.id) >= 0; });
      const remaining = TUTORIAL_TASKS.filter(function (task) { return completed.indexOf(task.id) < 0; });
      const signature = completed.join(",");
      elements.questProgress.textContent = done.length + "/" + TUTORIAL_TASKS.length;
      if (signature === state.tutorialSignature) {
        return;
      }
      state.tutorialSignature = signature;
      elements.questList.innerHTML = "";
      if (remaining.length === 0) {
        const item = document.createElement("li");
        item.innerHTML = "<span class=\"tick\">✓</span><span>All first steps complete. Build something worth returning to.<span class=\"hint\">The valley is yours.</span></span>";
        elements.questList.appendChild(item);
        return;
      }
      remaining.slice(0, 4).forEach(function (task) {
        const item = document.createElement("li");
        const tick = document.createElement("span");
        tick.className = "tick";
        tick.textContent = "○";
        const text = document.createElement("span");
        text.textContent = task.label;
        const hint = document.createElement("span");
        hint.className = "hint";
        hint.textContent = task.hint;
        text.appendChild(hint);
        item.appendChild(tick);
        item.appendChild(text);
        elements.questList.appendChild(item);
      });
    }

    function buildSlot(index, hotbar, stateData) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot" + (hotbar ? " is-hotbar" : "");
      button.dataset.index = String(index);
      button.setAttribute("aria-label", "Slot " + (index + 1));
      const slot = stateData.inventory.slots[index];
      if (slot) {
        const item = CONFIG.items[slot.id];
        const icon = TEXTURES.getIconCanvas(slot.id, 48);
        const canvas = document.createElement("canvas");
        canvas.width = 48;
        canvas.height = 48;
        canvas.className = "slot-icon";
        canvas.getContext("2d").drawImage(icon, 0, 0);
        button.appendChild(canvas);
        if (slot.count > 1) {
          const count = document.createElement("span");
          count.className = "slot-count";
          count.textContent = String(slot.count);
          button.appendChild(count);
        }
        button.title = (item ? item.name : slot.id) + " × " + slot.count;
        button.setAttribute("aria-label", (item ? item.name : slot.id) + ", " + slot.count + " in slot " + (index + 1));
      } else {
        const number = document.createElement("span");
        number.className = "slot-number";
        number.textContent = String((index % 9) + 1);
        button.appendChild(number);
        button.title = "Empty slot";
      }
      button.addEventListener("click", function (event) {
        event.preventDefault();
        actions.slotClick(index, 0, event.shiftKey);
      });
      button.addEventListener("contextmenu", function (event) {
        event.preventDefault();
        actions.slotClick(index, 2, event.shiftKey);
      });
      return button;
    }

    function refreshInventory(stateData, held) {
      elements.inventoryMain.innerHTML = "";
      for (let index = 9; index < CONFIG.inventorySize; index += 1) {
        elements.inventoryMain.appendChild(buildSlot(index, false, stateData));
      }
      elements.inventoryHotbar.innerHTML = "";
      for (let index = 0; index < CONFIG.hotbarSize; index += 1) {
        elements.inventoryHotbar.appendChild(buildSlot(index, true, stateData));
      }
      const stations = INVENTORY.nearbyStations(stateData.world, stateData.player.x, stateData.player.y);
      elements.stationStrip.innerHTML = "";
      [
        { key: "table", name: "Crafting table", near: stations.table },
        { key: "furnace", name: "Furnace", near: stations.furnace }
      ].forEach(function (station) {
        const chip = document.createElement("span");
        chip.className = "station-chip" + (station.near ? " is-near" : "");
        const dot = document.createElement("span");
        dot.className = "dot";
        chip.appendChild(dot);
        chip.appendChild(document.createTextNode(station.name + (station.near ? " in reach" : " not nearby")));
        elements.stationStrip.appendChild(chip);
      });
      const accessible = document.createElement("span");
      accessible.className = "station-chip is-near";
      accessible.textContent = "Hand recipes always available";
      elements.stationStrip.appendChild(accessible);
      renderRecipes(stateData, stations);
      setHeld(held);
    }

    function ingredientText(recipe) {
      return recipe.ingredients.map(function (ingredient) {
        const item = CONFIG.items[ingredient.id];
        return ingredient.count + "× " + (item ? item.name : ingredient.id);
      }).join(" + ");
    }

    function renderRecipes(stateData, stations) {
      elements.craftList.innerHTML = "";
      const sorted = CONFIG.recipes.slice().sort(function (a, b) { return a.order - b.order; });
      let available = 0;
      sorted.forEach(function (recipe) {
        const status = INVENTORY.recipeStatus(recipe, stateData.inventory, stations);
        if (status.ok) {
          available += 1;
        }
        const item = CONFIG.items[recipe.output.id];
        const row = document.createElement("div");
        row.className = "recipe" + (status.ok ? "" : " is-locked");
        row.dataset.recipeId = recipe.id;

        const icon = document.createElement("canvas");
        icon.width = 48;
        icon.height = 48;
        icon.className = "recipe-icon";
        icon.getContext("2d").drawImage(TEXTURES.getIconCanvas(recipe.output.id, 48), 0, 0);
        row.appendChild(icon);

        const body = document.createElement("div");
        body.className = "recipe-body";
        const name = document.createElement("div");
        name.className = "recipe-name";
        name.appendChild(document.createTextNode(item ? item.name : recipe.name));
        const station = document.createElement("span");
        station.className = "recipe-station";
        station.textContent = CONFIG.stations[recipe.station].label;
        name.appendChild(station);
        body.appendChild(name);
        const ingredients = document.createElement("div");
        ingredients.className = "recipe-ingredients";
        ingredients.textContent = ingredientText(recipe) + " → " + recipe.output.count;
        body.appendChild(ingredients);
        const reason = document.createElement("div");
        reason.className = "recipe-reason" + (status.ok ? " is-ok" : "");
        reason.textContent = status.ok ? "Ready to craft" : status.reason;
        body.appendChild(reason);
        row.appendChild(body);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "craft-button";
        button.textContent = status.ok ? "Craft" : "Locked";
        button.disabled = !status.ok;
        button.setAttribute("aria-label", "Craft " + (item ? item.name : recipe.name) + (status.ok ? "" : ". " + status.reason));
        button.addEventListener("click", function () {
          actions.craft(recipe.id);
        });
        row.appendChild(button);
        elements.craftList.appendChild(row);
      });
      elements.recipeCount.textContent = available + " ready";
    }

    function updateHotbar(stateData, force) {
      const signature = stateData.selected + "|" + stateData.inventory.slots.slice(0, CONFIG.hotbarSize).map(function (slot) {
        return slot ? slot.id + ":" + slot.count : "-";
      }).join("|");
      if (!force && signature === state.hotbarSignature) {
        return;
      }
      state.hotbarSignature = signature;
      elements.hotbar.innerHTML = "";
      for (let index = 0; index < CONFIG.hotbarSize; index += 1) {
        const slot = stateData.inventory.slots[index];
        const button = document.createElement("button");
        button.type = "button";
        button.className = "hotbar-slot" + (index === stateData.selected ? " is-selected" : "") + (slot ? "" : " is-empty");
        button.dataset.index = String(index);
        button.setAttribute("aria-label", "Hotbar slot " + (index + 1) + (slot ? ", " + CONFIG.items[slot.id].name : ", empty"));
        const number = document.createElement("span");
        number.className = "slot-number";
        number.textContent = String(index + 1);
        button.appendChild(number);
        if (slot) {
          const icon = TEXTURES.getIconCanvas(slot.id, 48);
          const canvas = document.createElement("canvas");
          canvas.width = 48;
          canvas.height = 48;
          canvas.className = "slot-icon";
          canvas.getContext("2d").drawImage(icon, 0, 0);
          button.appendChild(canvas);
          if (slot.count > 1) {
            const count = document.createElement("span");
            count.className = "slot-count";
            count.textContent = String(slot.count);
            button.appendChild(count);
          }
          button.title = CONFIG.items[slot.id].name;
        } else {
          button.title = "Empty hotbar slot";
        }
        button.addEventListener("click", function (event) {
          event.preventDefault();
          actions.selectSlot(index);
        });
        elements.hotbar.appendChild(button);
      }
    }

    function updateHUD(stateData) {
      updateHearts(stateData);
      updateTutorial(stateData);
      updateHotbar(stateData, false);
      const day = Math.max(1, stateData.day || stateData.stats.daysSurvived || 1);
      const phase = phaseName(stateData.timeOfDay);
      elements.phase.textContent = "Day " + day + " · " + phase;
      elements.clock.textContent = timeString(stateData.timeOfDay) + " · Day " + day;
      elements.coords.textContent = "X " + Math.floor(stateData.player.x) + " · Y " + Math.floor(stateData.player.y);
    }

    function setHeld(held) {
      state.held = held;
      elements.dragGhost.innerHTML = "";
      if (!held) {
        elements.dragGhost.classList.remove("is-active");
        return;
      }
      const item = CONFIG.items[held.id];
      const icon = TEXTURES.getIconCanvas(held.id, 48);
      const canvas = document.createElement("canvas");
      canvas.width = 48;
      canvas.height = 48;
      canvas.getContext("2d").drawImage(icon, 0, 0);
      elements.dragGhost.appendChild(canvas);
      if (held.count > 1) {
        const count = document.createElement("span");
        count.className = "slot-count";
        count.textContent = String(held.count);
        count.style.position = "absolute";
        count.style.right = "0";
        count.style.bottom = "0";
        count.style.fontFamily = "var(--mono)";
        count.style.fontSize = "12px";
        count.style.fontWeight = "700";
        count.style.textShadow = "0 1px 2px #000";
        elements.dragGhost.appendChild(count);
      }
      elements.dragGhost.classList.add("is-active");
      positionGhost();
      if (item) {
        elements.dragGhost.dataset.item = item.id;
      }
    }

    function positionGhost() {
      elements.dragGhost.style.left = state.pointerX + "px";
      elements.dragGhost.style.top = state.pointerY + "px";
    }

    window.addEventListener("pointermove", function (event) {
      state.pointerX = event.clientX;
      state.pointerY = event.clientY;
      if (state.held) {
        positionGhost();
      }
    });

    function setInventoryFeedback(message, tone) {
      if (!elements.inventoryFeedback) {
        return;
      }
      elements.inventoryFeedback.textContent = message;
      elements.inventoryFeedback.dataset.tone = tone || "info";
      elements.inventoryFeedback.classList.add("is-visible");
      if (state.feedbackTimer) {
        window.clearTimeout(state.feedbackTimer);
      }
      state.feedbackTimer = window.setTimeout(function () {
        elements.inventoryFeedback.classList.remove("is-visible");
      }, 2800);
    }

    function toast(message, tone, duration) {
      if (state.screen === "inventory") {
        setInventoryFeedback(message, tone);
        return;
      }
      state.toastQueue.push({ message: message, tone: tone || "info", duration: duration || 2200 });
      if (state.toastTimer) {
        return;
      }
      showNextToast();
    }

    function showNextToast() {
      const next = state.toastQueue.shift();
      if (!next) {
        state.toastTimer = 0;
        elements.toast.classList.remove("is-visible");
        return;
      }
      elements.toast.textContent = next.message;
      elements.toast.dataset.tone = next.tone;
      elements.toast.classList.add("is-visible");
      state.toastTimer = window.setTimeout(function () {
        elements.toast.classList.remove("is-visible");
        state.toastTimer = window.setTimeout(showNextToast, 180);
      }, next.duration);
    }

    function showStart(info) {
      const data = info || {};
      state.hasSave = !!data.hasSave;
      elements.startSeed.textContent = data.seed !== undefined ? String(data.seed) : "—";
      if (state.hasSave) {
        elements.play.textContent = "Continue";
        elements.startSaveNote.textContent = "Saved world · " + relativeSaved(data.savedAt);
      } else {
        elements.play.textContent = "Play";
        elements.startSaveNote.textContent = "No saved world yet";
      }
      setSoundLabels(!!data.muted);
      openScreen("start", "btn-play");
    }

    function showHelp(returnTo) {
      state.helpReturn = returnTo || state.screen || "game";
      openScreen("help", "btn-help-close");
    }

    function closeHelp() {
      const back = state.helpReturn;
      state.helpReturn = null;
      if (back === "start") {
        openScreen("start", "btn-play");
      } else if (back === "pause") {
        openScreen("pause", "btn-resume");
      } else {
        closeAll();
      }
    }

    function showPause(saveNote) {
      if (saveNote) {
        elements.pauseSaveNote.textContent = saveNote;
      }
      setSoundLabels(!!(actions.isMuted ? actions.isMuted() : false));
      openScreen("pause", "btn-resume");
    }

    function showInventory(stateData, held) {
      if (elements.inventoryFeedback) {
        elements.inventoryFeedback.classList.remove("is-visible");
      }
      refreshInventory(stateData, held);
      openScreen("inventory", "btn-inventory-close");
    }

    function refreshInventoryIfOpen(stateData, held) {
      if (state.screen === "inventory") {
        refreshInventory(stateData, held);
      }
    }

    function showDeath(stats) {
      const data = stats || {};
      elements.deathStats.innerHTML = "";
      [
        "Blocks mined: " + (data.blocksMined || 0),
        "Blocks placed: " + (data.blocksPlaced || 0),
        "Days survived: " + (data.daysSurvived || 1)
      ].forEach(function (text) {
        const span = document.createElement("span");
        span.textContent = text;
        elements.deathStats.appendChild(span);
      });
      openScreen("death", "btn-respawn");
    }

    function askNewWorld(returnTo) {
      const origin = returnTo || state.screen || "start";
      if (origin === "start" && !state.hasSave) {
        actions.newWorld();
        return;
      }
      state.confirmReturn = origin;
      openScreen("confirm", "btn-confirm-new");
    }

    function cancelNewWorld() {
      const back = state.confirmReturn || "start";
      state.confirmReturn = null;
      if (back === "pause") {
        openScreen("pause", "btn-resume");
      } else {
        openScreen("start", "btn-play");
      }
    }

    function cancelConfirmScreen() {
      if (state.screen === "confirm") {
        cancelNewWorld();
      }
    }

    function hideStart() {
      if (state.screen === "start") {
        closeAll();
      } else {
        elements.start.hidden = true;
      }
    }

    function setMinimapVisible(visible) {
      elements.minimap.classList.toggle("is-hidden", !visible);
    }

    function isOverlayOpen() {
      return state.screen !== null;
    }

    function currentScreen() {
      return state.screen;
    }

    function closeInventoryUI() {
      if (state.screen === "inventory") {
        closeAll();
      }
    }

    elements.play.addEventListener("click", function () { actions.play(); });
    elements.helpButton.addEventListener("click", function () { showHelp("game"); });
    elements.newWorld.addEventListener("click", function () { askNewWorld("start"); });
    elements.howTo.addEventListener("click", function () { showHelp("start"); });
    elements.helpClose.addEventListener("click", closeHelp);
    elements.helpDone.addEventListener("click", closeHelp);
    elements.pauseHelp.addEventListener("click", function () { showHelp("pause"); });
    elements.sound.addEventListener("click", function () { actions.toggleSound(); });
    elements.pauseSound.addEventListener("click", function () { actions.toggleSound(); });
    elements.inventoryButton.addEventListener("click", function () { actions.openInventory(); });
    elements.pauseButton.addEventListener("click", function () { actions.pause(); });
    elements.inventoryClose.addEventListener("click", function () { actions.closeInventory(); });
    elements.resume.addEventListener("click", function () { actions.resume(); });
    elements.pauseSave.addEventListener("click", function () { actions.save(); });
    elements.pauseNew.addEventListener("click", function () { askNewWorld("pause"); });
    elements.pauseTitle.addEventListener("click", function () { actions.returnToTitle(); });
    elements.respawn.addEventListener("click", function () { actions.respawn(); });
    elements.confirmNew.addEventListener("click", function () {
      const back = state.confirmReturn;
      state.confirmReturn = null;
      actions.newWorld(back);
    });
    elements.cancelNew.addEventListener("click", cancelNewWorld);

    function setSaveNote(text) {
      elements.pauseSaveNote.textContent = text;
    }

    return {
      elements: elements,
      TUTORIAL_TASKS: TUTORIAL_TASKS,
      updateHUD: updateHUD,
      updateHotbar: updateHotbar,
      refreshInventory: refreshInventory,
      refreshInventoryIfOpen: refreshInventoryIfOpen,
      setHeld: setHeld,
      toast: toast,
      showStart: showStart,
      hideStart: hideStart,
      showHelp: showHelp,
      closeHelp: closeHelp,
      showPause: showPause,
      showInventory: showInventory,
      showDeath: showDeath,
      askNewWorld: askNewWorld,
      cancelConfirmScreen: cancelConfirmScreen,
      setSaveState: setSaveState,
      setSoundLabels: setSoundLabels,
      setMinimapVisible: setMinimapVisible,
      isOverlayOpen: isOverlayOpen,
      currentScreen: currentScreen,
      closeInventoryUI: closeInventoryUI,
      closeAll: closeAll,
      setSaveNote: setSaveNote,
      getHeld: function () { return state.held; }
    };
  }

  window.SandboxUI = {
    createUI: createUI,
    TUTORIAL_TASKS: TUTORIAL_TASKS
  };
})();
