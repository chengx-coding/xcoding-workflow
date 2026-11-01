(function (root) {
  "use strict";

  const CONFIG = root.MosswildConfig;
  const CONTENT = root.MosswildContent;
  const TIME = root.MosswildTime;
  const INV = root.MosswildInventory;
  const ART = root.MosswildArt;

  const OVERLAY_IDS = {
    inventory: "inventory-overlay",
    help: "help-overlay",
    paused: "pause-overlay",
    dead: "death-overlay",
    done: "done-overlay"
  };

  const TOOL_ORDER = ["pickaxe", "axe", "sword"];
  const MATERIAL_ORDER = ["stick", "coal", "iron", "gem"];
  const BLOCK_ORDER = ["dirt", "stone", "log", "leaves", "planks", "brick", "workbench", "torch", "lantern", "campfire"];
  const CHAPTERS = [
    "THE FIRST MORNING",
    "HANDS & STONE",
    "HANDS & STONE",
    "AMONG THE STONES",
    "AMONG THE STONES",
    "THE DARK BELOW",
    "THE OLD WARD",
    "THE OLD WARD"
  ];

  let game = null;
  let actions = null;
  let app = null;
  let canvas = null;
  let questCollapsed = false;
  let lastQuestIndex = -1;
  let lastClock = "";
  let lastTooltip = "";
  let newWorldTimer = null;
  let toastSerial = 0;
  let overlayFocusTimer = null;

  const els = {};

  function cacheElements() {
    [
      "game", "app", "hud", "world-subtitle", "clock-symbol", "clock-time", "clock-day",
      "clock-fill", "clock-marker", "button-help", "button-sound", "button-fullscreen",
      "quest-card", "quest-toggle", "quest-count", "quest-state", "quest-title", "quest-hint",
      "quest-progress-fill", "quest-progress-text", "quest-chapter", "quest-steps",
      "toasts", "tutorial-card", "tutorial-copy", "tutorial-dismiss", "target-tooltip",
      "hearts", "selected-name", "selected-meta", "hotbar", "status", "save-text",
      "inventory-overlay", "pack-content", "bind-note", "recipe-list", "bench-status",
      "craft-note", "pack-total", "help-overlay", "pause-overlay", "death-overlay",
      "done-overlay", "pause-day", "pause-time", "pause-hollows", "pause-blocks",
      "pause-seed", "pause-save-state", "button-resume", "button-pause-help",
      "button-save", "button-new-world", "button-respawn", "death-copy",
      "button-continue", "done-days", "done-hollows", "done-blocks", "damage-flash",
      "fatal-error", "fatal-error-copy"
    ].forEach(function (id) {
      els[id] = document.getElementById(id);
    });
    app = document.getElementById("app");
    canvas = document.getElementById("game");
    els["game-hud"] = document.getElementById("game-hud");
  }

  function call(name) {
    const args = Array.prototype.slice.call(arguments, 1);
    if (actions && typeof actions[name] === "function") {
      return actions[name].apply(null, args);
    }
    return undefined;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function iconCanvas(key, state, className) {
    const canvasEl = document.createElement("canvas");
    canvasEl.width = 64;
    canvasEl.height = 64;
    if (className) {
      canvasEl.className = className;
    }
    ART.drawItemIcon(canvasEl, key, state);
    return canvasEl;
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(seconds || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (hours > 0) {
      return hours + "h " + String(minutes).padStart(2, "0") + "m";
    }
    return minutes + "m";
  }

  function getDayInfo() {
    if (!game) {
      return null;
    }
    // Recompute only when the displayed clock second changes; the renderer
    // also keeps game.dayInfo current for the lighting pass.
    if (game.dayInfo && Math.floor(game.dayInfo.totalTime) === Math.floor(game.state.worldTime)) {
      return game.dayInfo;
    }
    return TIME.getDayInfo(game.state.worldTime, CONFIG.daySeconds);
  }

  function refreshClock() {
    if (!game) {
      return;
    }
    const day = getDayInfo();
    if (!day) {
      return;
    }
    const signature = day.day + "|" + day.hours + "|" + day.minutes + "|" + day.phase;
    if (signature === lastClock) {
      return;
    }
    lastClock = signature;
    els["clock-time"].textContent = day.clock;
    els["clock-day"].textContent = "Day " + day.day + " · " + day.phase;
    els["clock-symbol"].classList.toggle("is-night", day.isNight);
    const percent = (day.fraction * 100).toFixed(2) + "%";
    els["clock-fill"].style.width = percent;
    els["clock-marker"].style.left = percent;
  }

  function makeHeart(filledRatio) {
    const heart = el("span", "heart");
    const fill = el("i");
    if (filledRatio <= 0) {
      heart.classList.add("is-empty");
    }
    fill.style.width = Math.round(Math.max(0, Math.min(1, filledRatio)) * 100) + "%";
    heart.appendChild(fill);
    return heart;
  }

  function refreshVitals() {
    if (!game) {
      return;
    }
    const health = Math.max(0, game.player.health);
    const hearts = els.hearts;
    hearts.textContent = "";
    for (let i = 0; i < 10; i += 1) {
      const amount = Math.max(0, Math.min(2, health - i * 2));
      hearts.appendChild(makeHeart(amount / 2));
    }
    hearts.setAttribute("aria-label", "Health: " + Math.ceil(health / 2) + " of 10 hearts");
  }

  function selectedToolMeta(state, key) {
    if (!key) {
      return "";
    }
    if (INV.isToolKey(key)) {
      const durability = INV.getToolDurability(state, key);
      if (!durability) {
        return "broken";
      }
      return durability.current + " / " + durability.max;
    }
    if (CONTENT.ITEMS[key] && CONTENT.ITEMS[key].kind === "block") {
      return "×" + INV.countItem(state, key);
    }
    return "";
  }

  function refreshHotbar() {
    if (!game) {
      return;
    }
    const state = game.state;
    const hotbar = els.hotbar;
    hotbar.textContent = "";
    for (let slot = 0; slot < CONFIG.hotbarSlots; slot += 1) {
      const key = state.hotbar[slot];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot";
      button.dataset.slot = String(slot);
      button.setAttribute("role", "button");
      button.setAttribute("tabindex", "-1");
      const keyOwned = key && (INV.isToolKey(key) ? Boolean(state.tools[key]) : INV.countItem(state, key) > 0);
      if (!keyOwned) {
        button.classList.add("is-empty");
      }
      if (slot === state.selectedSlot) {
        button.classList.add("is-selected");
      }
      const number = el("span", "slot-number", String(slot + 1));
      button.appendChild(number);
      if (key) {
        const icon = iconCanvas(key, state, "slot-icon");
        button.appendChild(icon);
      }
      if (key && INV.isToolKey(key)) {
        const durability = INV.getToolDurability(state, key);
        if (durability) {
          const bar = el("span", "slot-durability" + (durability.ratio < 0.25 ? " is-low" : ""));
          const fill = el("i");
          fill.style.width = Math.round(durability.ratio * 100) + "%";
          bar.appendChild(fill);
          button.appendChild(bar);
        }
        button.setAttribute(
          "aria-label",
          "Slot " + (slot + 1) + ": " + INV.getItemDisplayName(state, key)
            + (durability ? ", durability " + durability.current + " of " + durability.max : ", broken")
        );
      } else if (key) {
        const count = INV.countItem(state, key);
        button.appendChild(el("span", "slot-count", "×" + count));
        button.setAttribute("aria-label", "Slot " + (slot + 1) + ": " + INV.getItemDisplayName(state, key) + ", " + count + " in pack");
      } else {
        button.setAttribute("aria-label", "Slot " + (slot + 1) + ": empty");
      }
      button.title = key ? INV.getItemDisplayName(state, key) : "Empty slot";
      hotbar.appendChild(button);
    }

    const selected = state.hotbar[state.selectedSlot];
    els["selected-name"].textContent = INV.getItemDisplayName(state, selected);
    els["selected-meta"].textContent = selectedToolMeta(state, selected);
    refreshVitals();
  }

  function selectQuestChapter(index) {
    return CHAPTERS[Math.max(0, Math.min(CHAPTERS.length - 1, index))];
  }

  function questCompletionStep(info) {
    if (!info || !info.progress) {
      return "";
    }
    if (info.progress.parts.length === 0) {
      return "Next in your notes";
    }
    return info.progress.parts.map(function (part) {
      return part.label + " " + part.current + "/" + part.target;
    }).join(" · ");
  }

  function refreshQuest(force) {
    if (!game) {
      return;
    }
    const info = INV.getQuestInfo(game.state);
    const progressText = info.allDone
      ? "The old ward is lit."
      : questCompletionStep(info);
    const fraction = info.allDone
      ? 1
      : info.progress && info.progress.target > 0
        ? Math.min(1, info.progress.current / info.progress.target)
        : 0;
    const signature = [
      info.index,
      info.doneCount,
      game.state.stats.logsGathered,
      game.state.stats.stoneMined,
      game.state.stats.coalFound,
      game.state.stats.ironFound,
      game.state.flags.lanternPlaced
    ].join("|");
    if (!force && signature === refreshQuest.lastSignature) {
      return;
    }
    refreshQuest.lastSignature = signature;

    els["quest-count"].textContent = info.allDone
      ? String(info.total).padStart(2, "0") + " / " + String(info.total).padStart(2, "0")
      : String(info.index + 1).padStart(2, "0") + " / " + String(info.total).padStart(2, "0");
    els["quest-state"].textContent = info.allDone ? "KINDLED" : "IN PROGRESS";
    els["quest-state"].classList.toggle("is-done", info.allDone);

    if (info.allDone) {
      els["quest-title"].textContent = "The wild remembers";
      els["quest-hint"].textContent = "The lantern is lit and the hollows keep their distance. Keep wandering — this valley is yours now.";
      els["quest-chapter"].textContent = "THE OLD WARD";
    } else {
      els["quest-title"].textContent = info.currentStep.title;
      els["quest-hint"].textContent = info.currentStep.hint;
      els["quest-chapter"].textContent = selectQuestChapter(info.index);
    }
    els["quest-progress-fill"].style.width = Math.round(fraction * 100) + "%";
    els["quest-progress-text"].textContent = progressText;

    if (!els["quest-steps"].childElementCount) {
      for (let i = 0; i < info.total; i += 1) {
        els["quest-steps"].appendChild(el("i"));
      }
    }
    Array.from(els["quest-steps"].children).forEach(function (node, index) {
      node.classList.toggle("is-done", index < info.doneCount || info.allDone);
      node.classList.toggle("is-current", !info.allDone && index === info.index);
    });

    if (info.index !== lastQuestIndex && lastQuestIndex !== -1) {
      els["quest-card"].classList.remove("is-pulsing");
      void els["quest-card"].offsetWidth;
      els["quest-card"].classList.add("is-pulsing");
      window.setTimeout(function () {
        if (els["quest-card"]) {
          els["quest-card"].classList.remove("is-pulsing");
        }
      }, 820);
    }
    lastQuestIndex = info.index;
  }

  function refreshSound() {
    if (!game) {
      return;
    }
    const on = Boolean(game.state.soundOn);
    els["button-sound"].setAttribute("aria-pressed", String(on));
    els["button-sound"].textContent = on ? "SOUND" : "MUTED";
    els["button-sound"].title = on ? "Mute sound (M)" : "Enable sound (M)";
  }

  function setTutorialCopy(copy) {
    if (els["tutorial-copy"] && copy) {
      els["tutorial-copy"].textContent = copy;
    }
  }

  function refreshTutorial() {
    if (!game) {
      return;
    }
    if (game.state.flags.introDismissed) {
      els["tutorial-card"].classList.add("is-dismissed");
      els["tutorial-card"].setAttribute("aria-hidden", "true");
    } else {
      els["tutorial-card"].classList.remove("is-dismissed");
      els["tutorial-card"].removeAttribute("aria-hidden");
    }
  }

  function dismissTutorial() {
    els["tutorial-card"].classList.add("is-dismissed");
    els["tutorial-card"].setAttribute("aria-hidden", "true");
    call("dismissTutorial");
  }

  function sectionHead(title, note) {
    const head = el("div", "pack-section-head");
    head.appendChild(el("h4", "", title));
    if (note) {
      head.appendChild(el("span", "", note));
    }
    return head;
  }

  function packSection(title, note) {
    const section = el("section", "pack-section");
    section.appendChild(sectionHead(title, note));
    return section;
  }

  function makeGearCard(state, toolKey) {
    const tool = state.tools[toolKey];
    const card = document.createElement("button");
    card.type = "button";
    card.className = "gear-card";
    card.dataset.bindItem = toolKey;
    const slot = state.hotbar.indexOf(toolKey);
    if (slot !== -1) {
      card.classList.add("is-bound");
    }
    card.title = CONTENT.TOOL_TYPES[toolKey].description + " Click to put it in the selected slot.";
    card.appendChild(iconCanvas(toolKey, state));
    const toolInfo = CONTENT.getToolInfo(toolKey, tool.tier);
    card.appendChild(el("strong", "", toolInfo.name));
    card.appendChild(el("small", "", slot !== -1 ? "bound to " + (slot + 1) : "click to bind"));
    const durability = INV.getToolDurability(state, toolKey);
    const bar = el("span", "gear-durability" + (durability && durability.ratio < 0.25 ? " is-low" : ""));
    const fill = el("i");
    fill.style.width = durability ? Math.round(durability.ratio * 100) + "%" : "0%";
    bar.appendChild(fill);
    card.appendChild(bar);
    const meta = el("small", "", durability ? durability.current + " / " + durability.max : "broken");
    card.appendChild(meta);
    card.setAttribute("aria-label", toolInfo.name + ", durability " + (durability ? durability.current + " of " + durability.max : "0") + ". Click to bind.");
    return card;
  }

  function makeItemChip(state, key, bindable) {
    const item = CONTENT.ITEMS[key];
    const chip = document.createElement(bindable ? "button" : "div");
    if (bindable) {
      chip.type = "button";
      chip.dataset.bindItem = key;
    }
    chip.className = "item-chip" + (bindable ? " is-bindable" : " is-material");
    const slot = state.hotbar.indexOf(key);
    if (slot !== -1) {
      chip.classList.add("is-bound");
    }
    chip.title = item.blurb + (bindable ? " Click to bind to the selected hotbar slot." : " A crafting material.");
    chip.appendChild(iconCanvas(key, state));
    const label = el("span", "item-label");
    label.appendChild(document.createTextNode(item.name));
    const kind = el("span", "item-kind", item.kind === "material" ? "material" : slot !== -1 ? "slot " + (slot + 1) : "bind");
    label.appendChild(kind);
    chip.appendChild(label);
    chip.appendChild(el("span", "item-count", String(INV.countItem(state, key))));
    chip.setAttribute("aria-label", item.name + ", " + INV.countItem(state, key) + (bindable ? ". Click to bind." : "."));
    return chip;
  }

  function renderBackpack() {
    const state = game.state;
    const pack = els["pack-content"];
    const previousFocus = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.bindItem : null;
    pack.textContent = "";
    const near = Boolean(game.nearWorkbench);

    const tools = TOOL_ORDER.filter(function (key) { return Boolean(state.tools[key]); });
    if (tools.length) {
      const toolSection = el("section", "pack-section");
      const toolWrap = el("div", "gear-grid");
      tools.forEach(function (toolKey) {
        toolWrap.appendChild(makeGearCard(state, toolKey));
      });
      toolSection.appendChild(sectionHead("TOOL BELT", "click to bind"));
      toolSection.appendChild(toolWrap);
      pack.appendChild(toolSection);
    }

    const materials = MATERIAL_ORDER.filter(function (key) {
      return CONTENT.ITEMS[key] && INV.countItem(state, key) > 0;
    });
    if (materials.length) {
      const materialSection = packSection("MATERIALS", "for the bench");
      const grid = el("div", "item-grid");
      materials.forEach(function (key) {
        grid.appendChild(makeItemChip(state, key, false));
      });
      materialSection.appendChild(grid);
      pack.appendChild(materialSection);
    }

    const blocks = BLOCK_ORDER.filter(function (key) {
      return CONTENT.ITEMS[key] && INV.countItem(state, key) > 0;
    });
    if (blocks.length) {
      const blockSection = packSection("BLOCKS", "click to bind");
      const grid = el("div", "item-grid");
      blocks.forEach(function (key) {
        grid.appendChild(makeItemChip(state, key, true));
      });
      blockSection.appendChild(grid);
      pack.appendChild(blockSection);
    }

    if (!tools.length && !materials.length && !blocks.length) {
      pack.appendChild(el("p", "empty-pack", "Your pack is empty. Punch a tree, or pick up a stone."));
    }

    const total = INV.getTotals(state);
    els["pack-total"].textContent = total.items + (total.items === 1 ? " item" : " items") + " · " + total.tools + (total.tools === 1 ? " tool" : " tools");
    els["bind-note"].textContent = "Click a block or tool to bind it to slot " + (state.selectedSlot + 1) + ".";
    if (previousFocus) {
      const focusTarget = pack.querySelector('[data-bind-item="' + previousFocus.replace(/"/g, '\\"') + '"]');
      if (focusTarget) {
        focusTarget.focus({ preventScroll: true });
      }
    }
    void near;
  }

  function recipeCostLabel(itemKey, have, need) {
    const item = CONTENT.ITEMS[itemKey];
    return (item ? item.name : itemKey) + " " + have + "/" + need;
  }

  function makeRecipe(recipe) {
    const state = game.state;
    const near = Boolean(game.nearWorkbench);
    const check = INV.canCraft(state, recipe, near);
    const card = el("div", "recipe" + (check.ok ? "" : " is-locked"));
    const iconState = state;
    let iconKey;
    let iconStateOverride = state;
    if (recipe.output.kind === "tool") {
      iconKey = recipe.output.tool;
      iconStateOverride = {
        tools: Object.assign({}, state.tools, {
          [recipe.output.tool]: { tier: recipe.output.tier, durability: 1 }
        })
      };
    } else {
      iconKey = recipe.output.item;
    }
    const icon = el("div", "recipe-icon");
    icon.appendChild(iconCanvas(iconKey, iconStateOverride));
    card.appendChild(icon);

    const copy = el("div", "recipe-copy");
    const nameRow = el("div", "recipe-name-row");
    nameRow.appendChild(el("span", "recipe-name", recipe.name));
    if (recipe.output.kind === "item" && recipe.output.count > 1) {
      nameRow.appendChild(el("span", "recipe-qty", "×" + recipe.output.count));
    }
    if (recipe.output.kind === "tool") {
      nameRow.appendChild(el("span", "recipe-qty", CONTENT.TIER_NAMES[recipe.output.tier] + " tier"));
    }
    if (recipe.station === "workbench") {
      nameRow.appendChild(el("span", "recipe-station", near ? "BENCH READY" : "BENCH"));
    }
    copy.appendChild(nameRow);

    const costs = el("div", "recipe-costs");
    Object.keys(recipe.costs).forEach(function (itemKey) {
      const need = recipe.costs[itemKey];
      const have = INV.countItem(state, itemKey);
      costs.appendChild(el("span", "cost" + (have < need ? " is-missing" : ""), recipeCostLabel(itemKey, have, need)));
    });
    copy.appendChild(costs);
    const blurb = el("p", "recipe-blurb", recipe.blurb);
    copy.appendChild(blurb);
    if (!check.ok && check.reason === "station") {
      costs.appendChild(el("span", "cost is-missing", "needs a placed workbench nearby"));
    } else if (!check.ok && check.reason === "owned") {
      costs.appendChild(el("span", "cost", "already equipped"));
    }
    card.appendChild(copy);

    const action = el("div", "recipe-action");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "craft-button";
    button.dataset.recipe = recipe.id;
    let label = "CRAFT";
    if (!check.ok) {
      if (check.reason === "station") {
        label = "BENCH";
      } else if (check.reason === "owned") {
        label = "OWNED";
      }
    } else if (recipe.output.kind === "tool" && state.tools[recipe.output.tool]) {
      label = "UPGRADE";
    }
    button.textContent = label;
    button.disabled = !check.ok;
    if (!check.ok) {
      button.title = check.reason === "station"
        ? "Place a workbench near you to unlock this recipe."
        : check.reason === "owned"
          ? "You already carry a tool of this tier or better."
          : "You need a few more materials.";
    } else {
      button.title = "Craft " + recipe.name;
    }
    action.appendChild(button);
    card.appendChild(action);
    void iconState;
    return card;
  }

  function renderRecipes() {
    const previousFocus = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.recipe : null;
    const list = els["recipe-list"];
    list.textContent = "";
    const handRecipes = CONTENT.RECIPES.filter(function (recipe) { return recipe.station !== "workbench"; });
    const benchRecipes = CONTENT.RECIPES.filter(function (recipe) { return recipe.station === "workbench"; });
    const groups = [
      { title: "HANDCRAFT", recipes: handRecipes },
      { title: "WORKBENCH", recipes: benchRecipes }
    ];
    groups.forEach(function (group) {
      if (!group.recipes.length) {
        return;
      }
      const wrap = el("div", "recipe-group");
      wrap.appendChild(el("div", "recipe-group-head", group.title));
      group.recipes.forEach(function (recipe) {
        wrap.appendChild(makeRecipe(recipe));
      });
      list.appendChild(wrap);
    });
    if (previousFocus) {
      const focusTarget = list.querySelector('[data-recipe="' + previousFocus.replace(/"/g, '\\"') + '"]');
      if (focusTarget && !focusTarget.disabled) {
        focusTarget.focus({ preventScroll: true });
      }
    }
  }

  function refreshInventory() {
    if (!game) {
      return;
    }
    const near = Boolean(game.nearWorkbench);
    els["bench-status"].textContent = near ? "Workbench in reach" : "No workbench nearby";
    els["bench-status"].classList.toggle("is-near", near);
    els["craft-note"].textContent = near
      ? "The bench is warm. Tools and utilities are available."
      : "Place a workbench nearby to unlock tools and larger builds.";
    renderBackpack();
    renderRecipes();
    refreshHotbar();
  }

  function refreshPause() {
    if (!game) {
      return;
    }
    const day = getDayInfo();
    els["pause-day"].textContent = day ? String(day.day) : "1";
    els["pause-time"].textContent = formatDuration(game.state.playSeconds || game.state.stats.playSeconds);
    els["pause-hollows"].textContent = String(game.state.stats.hollowsDefeated || 0);
    els["pause-blocks"].textContent = String(game.state.stats.blocksPlaced || 0);
    els["pause-seed"].textContent = "Seed " + String(game.world.seed).padStart(8, "0");
    els["pause-save-state"].textContent = game.lastSavedLabel || "Autosaves every 10 seconds";
  }

  function refreshDone() {
    if (!game) {
      return;
    }
    const day = getDayInfo();
    els["done-days"].textContent = day ? String(day.day) : "1";
    els["done-hollows"].textContent = String(game.state.stats.hollowsDefeated || 0);
    els["done-blocks"].textContent = String(game.state.stats.blocksPlaced || 0);
  }

  function resetNewWorldButton() {
    if (newWorldTimer) {
      window.clearTimeout(newWorldTimer);
      newWorldTimer = null;
    }
    els["button-new-world"].classList.remove("is-confirming");
    els["button-new-world"].textContent = "New world";
  }

  function setMode(mode) {
    if (!app) {
      return;
    }
    app.dataset.mode = mode;
    const overlayMode = Boolean(OVERLAY_IDS[mode]);
    if (els["game-hud"]) {
      els["game-hud"].inert = overlayMode;
    }
    if (canvas) {
      canvas.inert = overlayMode;
    }
    Object.keys(OVERLAY_IDS).forEach(function (key) {
      const overlay = els[OVERLAY_IDS[key]];
      if (!overlay) {
        return;
      }
      const active = key === mode;
      overlay.hidden = !active;
      overlay.setAttribute("aria-hidden", String(!active));
    });
    els["target-tooltip"].hidden = true;
    lastTooltip = "";
    if (mode === "inventory") {
      refreshInventory();
    } else if (mode === "paused") {
      resetNewWorldButton();
      refreshPause();
    } else if (mode === "done") {
      refreshDone();
    } else if (mode === "help") {
      // Static guide; no extra refresh required.
    }
    if (mode === "playing") {
      if (overlayFocusTimer) {
        window.clearTimeout(overlayFocusTimer);
      }
      overlayFocusTimer = window.setTimeout(function () {
        if (game && game.mode === "playing" && canvas) {
          canvas.focus({ preventScroll: true });
        }
      }, 0);
    } else if (OVERLAY_IDS[mode]) {
      if (overlayFocusTimer) {
        window.clearTimeout(overlayFocusTimer);
      }
      const overlay = els[OVERLAY_IDS[mode]];
      const focusTarget = overlay.querySelector(".close-button, .primary-button, button:not([disabled])");
      if (focusTarget) {
        overlayFocusTimer = window.setTimeout(function () {
          if (focusTarget.isConnected) {
            focusTarget.focus({ preventScroll: true });
          }
        }, 20);
      }
    }
    if (mode !== "paused") {
      resetNewWorldButton();
    }
  }

  function setSaveStatus(text, title) {
    if (els["save-text"]) {
      els["save-text"].textContent = text;
    }
    if (els["status"] && title) {
      els["status"].title = title;
    }
  }

  function showToast(message, type, duration) {
    if (!els.toasts) {
      return;
    }
    const toast = el("div", "toast" + (type ? " toast--" + type : ""));
    toast.id = "toast-" + (toastSerial += 1);
    toast.appendChild(el("span", "", message));
    const existing = els.toasts.children;
    if (existing.length >= 3) {
      existing[0].remove();
    }
    els.toasts.appendChild(toast);
    const lifetime = typeof duration === "number" ? duration : 3300;
    window.setTimeout(function () {
      if (!toast.isConnected) {
        return;
      }
      toast.classList.add("is-leaving");
      window.setTimeout(function () {
        toast.remove();
      }, 200);
    }, lifetime);
  }

  function updateTargetTooltip(hover) {
    if (!game || game.mode !== "playing" || !hover || !hover.tip || !hover.inReach || !game.mouse.inside) {
      if (!els["target-tooltip"].hidden) {
        els["target-tooltip"].hidden = true;
      }
      lastTooltip = "";
      return;
    }
    const signature = hover.tip.label + "|" + hover.tip.hint;
    const tooltip = els["target-tooltip"];
    if (signature !== lastTooltip) {
      lastTooltip = signature;
      tooltip.textContent = "";
      tooltip.appendChild(el("strong", "", hover.tip.label));
      if (hover.tip.hint) {
        tooltip.appendChild(document.createTextNode(" "));
        tooltip.appendChild(el("span", "", hover.tip.hint));
      }
    }
    const margin = 16;
    let x = game.mouse.x + 18;
    let y = game.mouse.y + 18;
    if (x + 200 > window.innerWidth - margin) {
      x = game.mouse.x - 210;
    }
    if (y + 36 > window.innerHeight - margin) {
      y = game.mouse.y - 34;
    }
    x = Math.max(8, x);
    y = Math.max(8, y);
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
    tooltip.hidden = false;
  }

  function flashDamage() {
    const flash = els["damage-flash"];
    if (!flash) {
      return;
    }
    flash.classList.remove("is-active");
    void flash.offsetWidth;
    flash.classList.add("is-active");
  }

  function showFatalError(message) {
    if (els["fatal-error"]) {
      els["fatal-error"].hidden = false;
      if (els["fatal-error-copy"]) {
        els["fatal-error-copy"].textContent = message;
      }
    }
    if (els["status"]) {
      els["status"].dataset.state = "error";
      els["status"].title = message;
    }
    setSaveStatus("World failed to start", message);
  }

  function setSaveState(state, title) {
    if (els["status"]) {
      els["status"].dataset.state = state;
      if (title) {
        els["status"].title = title;
      }
    }
  }

  function updateFullscreenLabel() {
    const active = Boolean(document.fullscreenElement);
    els["button-fullscreen"].textContent = active ? "EXIT" : "FULL";
    els["button-fullscreen"].setAttribute("aria-label", active ? "Leave fullscreen" : "Enter fullscreen");
    els["button-fullscreen"].title = active ? "Leave fullscreen (F)" : "Toggle fullscreen (F)";
  }

  function bindEvents() {
    els["button-help"].addEventListener("click", function () {
      call("openHelp");
    });
    els["button-sound"].addEventListener("click", function () {
      call("toggleSound");
    });
    els["button-fullscreen"].addEventListener("click", function () {
      call("toggleFullscreen");
    });
    els["quest-toggle"].addEventListener("click", function () {
      questCollapsed = !questCollapsed;
      els["quest-card"].classList.toggle("is-collapsed", questCollapsed);
      els["quest-toggle"].setAttribute("aria-expanded", String(!questCollapsed));
    });

    els.hotbar.addEventListener("click", function (event) {
      const slot = event.target.closest("[data-slot]");
      if (!slot) {
        return;
      }
      call("selectSlot", Number(slot.dataset.slot));
      if (canvas) {
        canvas.focus({ preventScroll: true });
      }
    });

    els["tutorial-dismiss"].addEventListener("click", dismissTutorial);

    document.querySelectorAll("[data-close-overlay]").forEach(function (button) {
      button.addEventListener("click", function () {
        call("closeOverlay");
      });
    });

    ["inventory-overlay", "help-overlay"].forEach(function (id) {
      els[id].addEventListener("pointerdown", function (event) {
        if (event.target === els[id]) {
          call("closeOverlay");
        }
      });
    });

    els["pack-content"].addEventListener("click", function (event) {
      const target = event.target.closest("[data-bind-item]");
      if (target) {
        call("bindItem", target.dataset.bindItem);
      }
    });

    els["recipe-list"].addEventListener("click", function (event) {
      const button = event.target.closest("[data-recipe]");
      if (button && !button.disabled) {
        call("craftItem", button.dataset.recipe);
      }
    });

    els["button-resume"].addEventListener("click", function () {
      call("resume");
    });
    els["button-pause-help"].addEventListener("click", function () {
      call("openHelp", true);
    });
    els["button-save"].addEventListener("click", function () {
      call("saveNow", true);
    });
    els["button-new-world"].addEventListener("click", function () {
      if (els["button-new-world"].classList.contains("is-confirming")) {
        resetNewWorldButton();
        call("newWorld");
        return;
      }
      els["button-new-world"].classList.add("is-confirming");
      els["button-new-world"].textContent = "Erase and begin?";
      if (newWorldTimer) {
        window.clearTimeout(newWorldTimer);
      }
      newWorldTimer = window.setTimeout(resetNewWorldButton, 4200);
    });
    els["button-respawn"].addEventListener("click", function () {
      call("respawn");
    });
    els["button-continue"].addEventListener("click", function () {
      call("continueAfterDone");
    });

    document.addEventListener("fullscreenchange", updateFullscreenLabel);
    window.addEventListener("resize", function () {
      els["target-tooltip"].hidden = true;
      lastTooltip = "";
    });
  }

  function init(gameInstance, actionMap) {
    game = gameInstance;
    actions = actionMap;
    cacheElements();
    bindEvents();
    updateFullscreenLabel();
    refreshHotbar();
    refreshQuest(true);
    refreshClock();
    refreshSound();
    refreshTutorial();
    setMode("loading");
    if (game.state && game.state.flags && game.state.flags.introDismissed) {
      els["tutorial-card"].classList.add("is-dismissed");
    }
  }

  root.MosswildUI = {
    init,
    setMode,
    setSaveStatus,
    setSaveState,
    refreshHotbar,
    refreshVitals,
    refreshClock,
    refreshQuest,
    refreshInventory,
    refreshPause,
    refreshDone,
    refreshSound,
    refreshTutorial,
    setTutorialCopy,
    showToast,
    updateTargetTooltip,
    flashDamage,
    showFatalError,
    updateFullscreenLabel
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
