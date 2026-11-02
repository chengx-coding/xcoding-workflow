(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"), require("./render.js"));
  } else {
    root.SandboxUI = factory(root.SandboxConfig, root.SandboxBlocks, root.SandboxRender);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS, RENDER) {
  "use strict";

  if (!CONFIG || !BLOCKS || !RENDER) {
    throw new Error("SandboxConfig, SandboxBlocks and SandboxRender are required before SandboxUI");
  }

  const CONTROLS = Object.freeze([
    { keys: "A / D or Arrow keys", action: "Walk left and right" },
    { keys: "W / Space", action: "Jump" },
    { keys: "Hold left click", action: "Mine the highlighted block" },
    { keys: "Right click", action: "Place the selected block next to a neighbour" },
    { keys: "1 – 9 / click a slot", action: "Select a hotbar slot" },
    { keys: "E", action: "Open inventory" },
    { keys: "C", action: "Open crafting" },
    { keys: "Q", action: "Show or hide the quest tracker" },
    { keys: "H", action: "Open this guide" },
    { keys: "B", action: "Toggle backdrop mode (before/after ghosts)" },
    { keys: "Mouse wheel / + / -", action: "Zoom the view in and out" },
    { keys: "T", action: "Wait three hours (watch the sky change)" },
    { keys: "Ctrl + Z / Ctrl + Y", action: "Undo or redo the last edit" },
    { keys: "F2", action: "Save now" },
    { keys: "M", action: "Mute or unmute sound" },
    { keys: "Esc", action: "Close panels or open the menu" }
  ]);

  const KIND_LABELS = {
    edit: "Edit",
    mode: "Mode",
    time: "Time",
    view: "View"
  };

  function element(id) {
    return document.getElementById(id);
  }

  function paintLabel(canvas, text, tone) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#101821";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = tone === "after" ? "rgba(111, 209, 138, 0.16)" : "rgba(240, 179, 92, 0.14)";
    ctx.fillRect(4, 4, width - 8, height - 8);
    ctx.strokeStyle = tone === "after" ? "rgba(111, 209, 138, 0.55)" : "rgba(240, 179, 92, 0.5)";
    ctx.lineWidth = 1;
    ctx.strokeRect(4.5, 4.5, width - 9, height - 9);
    ctx.fillStyle = tone === "after" ? "#d6f5df" : "#ffe2b4";
    ctx.font = "600 11px 'Segoe UI', system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const words = String(text).split(" ");
    const lines = [];
    let current = "";
    words.forEach(function (word) {
      const next = current ? current + " " + word : word;
      if (ctx.measureText(next).width > width - 10 && current) {
        lines.push(current);
        current = word;
      } else {
        current = next;
      }
    });
    if (current) {
      lines.push(current);
    }
    const lineHeight = 12;
    const startY = height / 2 - ((lines.length - 1) * lineHeight) / 2;
    lines.forEach(function (line, index) {
      ctx.fillText(line, width / 2, startY + index * lineHeight);
    });
  }

  function createUI(options) {
    const actions = options && options.actions ? options.actions : {};
    const state = {
      hotbarSignature: "",
      inventorySignature: "",
      questSignature: "",
      craftSignature: "",
      panel: null,
      previousFocus: null,
      pulseTimer: null,
      questHidden: false,
      healthPips: 0,
      lastPhase: null
    };

    const dom = {
      canvas: element("game"),
      status: element("status"),
      hud: element("hud"),
      day: element("hud-day"),
      time: element("hud-time"),
      phase: element("hud-phase"),
      health: element("health-pips"),
      zoom: element("hud-zoom"),
      viewport: element("hud-viewport"),
      hotbar: element("hotbar"),
      held: element("held-label"),
      questTracker: element("quest-tracker"),
      questTitle: element("quest-title"),
      questHint: element("quest-hint"),
      questProgress: element("quest-progress"),
      questMeter: element("quest-meter"),
      questMeterWrap: element("quest-meter-wrap"),
      questList: element("quest-list"),
      questCount: element("quest-count"),
      questCollapse: element("quest-collapse"),
      questOpen: element("quest-open"),
      pulse: element("state-pulse"),
      pulseKind: element("pulse-kind"),
      pulsePos: element("pulse-pos"),
      pulseBefore: element("pulse-before"),
      pulseAfter: element("pulse-after"),
      pulseLabels: element("pulse-labels"),
      minimap: element("minimap"),
      minimapCaption: element("minimap-caption"),
      hint: element("action-hint"),
      toasts: element("toasts"),
      welcome: element("welcome"),
      welcomeNote: element("welcome-save-note"),
      welcomePlay: element("welcome-play"),
      welcomeGuide: element("welcome-guide"),
      welcomeNew: element("welcome-new"),
      inventoryPanel: element("panel-inventory"),
      inventoryGrid: element("inventory-grid"),
      inventoryCount: element("inventory-count"),
      craftPanel: element("panel-craft"),
      craftList: element("craft-list"),
      guidePanel: element("panel-guide"),
      controlList: element("control-list"),
      guideSaveNote: element("guide-save-note"),
      menuPanel: element("panel-menu"),
      menuStatus: element("menu-save-status"),
      seedInput: element("seed-input"),
      menuMute: element("menu-mute"),
      menuVersion: element("menu-version"),
      btnQuests: element("btn-quests"),
      btnInventory: element("btn-inventory"),
      btnCraft: element("btn-craft"),
      btnGuide: element("btn-guide"),
      btnBackdrop: element("btn-backdrop"),
      btnSave: element("btn-save"),
      btnMenu: element("btn-menu")
    };

    function call(name, payload) {
      if (typeof actions[name] === "function") {
        actions[name](payload);
      }
    }

    function buildHotbar() {
      dom.hotbar.innerHTML = "";
      for (let index = 0; index < CONFIG.hotbarSize; index += 1) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "hotbar-slot";
        button.dataset.slot = String(index);
        button.setAttribute("aria-label", "Hotbar slot " + (index + 1));
        button.innerHTML = '<canvas width="34" height="34" aria-hidden="true"></canvas>' +
          '<span class="hotbar-key">' + (index + 1) + "</span>" +
          '<span class="hotbar-count"></span>';
        button.addEventListener("click", function () {
          call("selectSlot", index);
        });
        dom.hotbar.appendChild(button);
      }
    }

    function buildControls() {
      dom.controlList.innerHTML = "";
      CONTROLS.forEach(function (control) {
        const dt = document.createElement("dt");
        dt.textContent = control.keys;
        const dd = document.createElement("dd");
        dd.textContent = control.action;
        dom.controlList.appendChild(dt);
        dom.controlList.appendChild(dd);
      });
    }

    function updateHotbar(game) {
      const inventory = game.inventory;
      const signature = JSON.stringify(inventory.hotbar) + ":" + JSON.stringify(inventory.items) + ":" + inventory.selected;
      if (signature === state.hotbarSignature) {
        return;
      }
      state.hotbarSignature = signature;
      const slots = dom.hotbar.querySelectorAll(".hotbar-slot");
      for (let index = 0; index < slots.length; index += 1) {
        const slot = slots[index];
        const id = inventory.hotbar[index];
        const canvas = slot.querySelector("canvas");
        const count = slot.querySelector(".hotbar-count");
        RENDER.paintItemIcon(canvas, id || 0);
        count.textContent = id && inventory.items[id] ? String(inventory.items[id]) : "";
        slot.classList.toggle("is-selected", index === inventory.selected);
        slot.setAttribute("aria-pressed", index === inventory.selected ? "true" : "false");
      }
      const selected = inventory.hotbar[inventory.selected];
      dom.held.textContent = selected ? BLOCKS.nameOf(selected) + " selected" : "Empty hand";
    }

    function updateHealth(health) {
      const pips = 10;
      const filled = Math.max(0, Math.min(pips, Math.round((health / 20) * pips)));
      if (filled === state.healthPips && dom.health.childElementCount === pips) {
        return;
      }
      state.healthPips = filled;
      dom.health.innerHTML = "";
      for (let index = 0; index < pips; index += 1) {
        const pip = document.createElement("span");
        pip.className = "health-pip" + (index < filled ? "" : " is-empty");
        dom.health.appendChild(pip);
      }
      dom.health.setAttribute("aria-label", "Health " + health + " of 20");
    }

    function updateQuests(game) {
      const progress = game.progress;
      const tasks = game.tasks;
      const completed = tasks.completedCount(progress);
      const active = tasks.activeTask(progress);
      const signature = completed + ":" + (active ? active.id : "done") + ":" + JSON.stringify(progress.tasks);
      if (signature === state.questSignature) {
        return;
      }
      state.questSignature = signature;
      dom.questCount.textContent = completed + "/" + tasks.TASKS.length;
      if (active) {
        dom.questTitle.textContent = active.title;
        dom.questHint.textContent = active.hint;
        const info = tasks.taskProgress(active, progress);
        dom.questProgress.textContent = info.text;
        dom.questMeter.style.width = Math.round((info.value / info.goal) * 100) + "%";
        dom.questMeterWrap.setAttribute("aria-valuemax", String(info.goal));
        dom.questMeterWrap.setAttribute("aria-valuenow", String(info.value));
      } else {
        dom.questTitle.textContent = "All quests complete";
        dom.questHint.textContent = "You have the whole sandbox — build something worth a screenshot.";
        dom.questProgress.textContent = tasks.TASKS.length + "/" + tasks.TASKS.length;
        dom.questMeter.style.width = "100%";
      }
      dom.questList.innerHTML = "";
      tasks.TASKS.forEach(function (task) {
        const item = document.createElement("li");
        item.dataset.task = task.id;
        const done = Boolean(progress.tasks[task.id]);
        item.className = done ? "is-done" : active && active.id === task.id ? "is-active" : "";
        item.innerHTML = '<span class="quest-tick">' + (done ? "✓" : "") + "</span><span>" + task.title + "</span>";
        dom.questList.appendChild(item);
      });
    }

    function updateInventoryPanel(game) {
      const signature = JSON.stringify(game.inventory.items);
      if (signature === state.inventorySignature && state.panel !== "panel-inventory") {
        return;
      }
      state.inventorySignature = signature;
      const entries = Object.keys(game.inventory.items)
        .map(function (key) { return { id: Number(key), count: game.inventory.items[key] }; })
        .filter(function (entry) { return entry.count > 0; })
        .sort(function (a, b) { return a.id - b.id; });
      dom.inventoryGrid.innerHTML = "";
      if (!entries.length) {
        const empty = document.createElement("p");
        empty.className = "inventory-empty";
        empty.textContent = "Your pockets are empty. Mine a tree to start gathering.";
        dom.inventoryGrid.appendChild(empty);
      }
      entries.forEach(function (entry) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "inventory-item";
        button.dataset.item = String(entry.id);
        button.innerHTML = '<canvas width="34" height="34" aria-hidden="true"></canvas>' +
          "<span>" + BLOCKS.nameOf(entry.id) + "</span><strong>×" + entry.count + "</strong>";
        RENDER.paintItemIcon(button.querySelector("canvas"), entry.id);
        button.addEventListener("click", function () {
          call("pickItem", entry.id);
        });
        dom.inventoryGrid.appendChild(button);
      });
      const totals = entries.reduce(function (sum, entry) { return sum + entry.count; }, 0);
      dom.inventoryCount.textContent = totals + (totals === 1 ? " item" : " items");
    }

    function updateCraftPanel(game) {
      if (!game.crafting) {
        return;
      }
      const signature = JSON.stringify(game.inventory.items) + ":" + JSON.stringify(game.progress.collected);
      if (signature === state.craftSignature && state.panel !== "panel-craft") {
        return;
      }
      state.craftSignature = signature;
      const rows = game.crafting.visible(game.inventory, game.progress);
      dom.craftList.innerHTML = "";
      rows.forEach(function (row) {
        const recipe = row.recipe;
        const wrapper = document.createElement("div");
        wrapper.className = "craft-row" + (row.unlocked ? "" : " is-locked") + (row.canCraft ? " is-craftable" : "");
        wrapper.dataset.recipe = recipe.id;
        const canvas = document.createElement("canvas");
        canvas.width = 40;
        canvas.height = 40;
        RENDER.paintItemIcon(canvas, recipe.out.id);
        const body = document.createElement("div");
        const costText = recipe.cost.map(function (part) {
          const missing = row.missing.some(function (entry) { return entry.id === part.id; });
          return '<span class="' + (missing ? "is-missing" : "") + '">' + BLOCKS.nameOf(part.id) + " ×" + part.count + "</span>";
        }).join(" + ");
        body.innerHTML = '<p class="craft-name">' + recipe.name +
          '<span class="craft-tag">' + recipe.category + "</span></p>" +
          '<p class="craft-cost">' + costText + "</p>" +
          '<p class="craft-hint">' + (row.unlocked ? "Produces " + BLOCKS.nameOf(recipe.out.id) + " ×" + recipe.out.count : recipe.hint) + "</p>";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "craft-button";
        button.textContent = row.unlocked ? (row.canCraft ? "Craft" : "Need more") : "Locked";
        button.disabled = !row.canCraft;
        button.dataset.craft = recipe.id;
        button.addEventListener("click", function () {
          call("craft", recipe.id);
        });
        wrapper.appendChild(canvas);
        wrapper.appendChild(body);
        wrapper.appendChild(button);
        dom.craftList.appendChild(wrapper);
      });
    }

    function openPanel(name) {
      closePanels(true);
      const panel = element(name);
      if (!panel) {
        return;
      }
      state.previousFocus = document.activeElement;
      panel.hidden = false;
      state.panel = name;
      const focusTarget = panel.querySelector("button, input");
      if (focusTarget) {
        focusTarget.focus();
      }
    }

    function closePanels(keepFocus) {
      [dom.inventoryPanel, dom.craftPanel, dom.guidePanel, dom.menuPanel].forEach(function (panel) {
        if (panel) {
          panel.hidden = true;
        }
      });
      state.panel = null;
      if (!keepFocus && state.previousFocus && typeof state.previousFocus.focus === "function") {
        state.previousFocus.focus();
      }
    }

    function toast(text, kind) {
      const item = document.createElement("div");
      item.className = "toast";
      item.dataset.kind = kind || "info";
      item.textContent = text;
      dom.toasts.appendChild(item);
      window.setTimeout(function () {
        if (item.parentNode) {
          item.parentNode.removeChild(item);
        }
      }, 4200);
    }

    function setHint(text, tone, x, y) {
      if (!text) {
        dom.hint.hidden = true;
        return;
      }
      dom.hint.hidden = false;
      dom.hint.textContent = text;
      dom.hint.dataset.tone = tone || "info";
      dom.hint.style.left = Math.round(x || 0) + "px";
      dom.hint.style.top = Math.round(y || 0) + "px";
    }

    function showPulse(pulse, extra) {
      if (!pulse) {
        return;
      }
      dom.pulse.hidden = false;
      dom.pulse.dataset.kind = pulse.kind;
      dom.pulseKind.textContent = KIND_LABELS[pulse.kind] || "State";
      dom.pulsePos.textContent = extra && extra.pos ? extra.pos : "before / after";
      dom.pulseLabels.textContent = pulse.before + " → " + pulse.after;
      if (typeof pulse.beforeId === "number") {
        RENDER.paintItemIcon(dom.pulseBefore, pulse.beforeId);
      } else {
        paintLabel(dom.pulseBefore, pulse.before, "before");
      }
      if (typeof pulse.afterId === "number") {
        RENDER.paintItemIcon(dom.pulseAfter, pulse.afterId);
      } else {
        paintLabel(dom.pulseAfter, pulse.after, "after");
      }
      if (state.pulseTimer) {
        window.clearTimeout(state.pulseTimer);
      }
      state.pulseTimer = window.setTimeout(function () {
        dom.pulse.hidden = true;
      }, 8000);
    }

    function setWelcome(visible) {
      dom.welcome.hidden = !visible;
      if (visible) {
        dom.welcomePlay.focus();
      }
    }

    function setStorageNote(text) {
      dom.welcomeNote.textContent = text;
      dom.guideSaveNote.textContent = text;
      dom.menuStatus.textContent = "Storage: " + text;
    }

    function setMenuStatus(text) {
      dom.menuStatus.textContent = text;
    }

    function setMuteButton(muted) {
      dom.menuMute.textContent = muted ? "Sound: off" : "Sound: on";
      dom.menuMute.setAttribute("aria-pressed", muted ? "true" : "false");
    }

    function setMinimapCaption(text) {
      dom.minimapCaption.textContent = text;
    }

    function setStatus(value, text) {
      dom.status.dataset.state = value;
      dom.status.title = text;
    }

    function update(game) {
      dom.day.textContent = String(game.clock.day);
      dom.time.textContent = game.clockText;
      if (game.clockText) {
        const phase = game.phase;
        if (phase && phase !== state.lastPhase) {
          state.lastPhase = phase;
        }
        dom.phase.textContent = phase.charAt(0).toUpperCase() + phase.slice(1);
        dom.phase.dataset.phase = phase;
      }
      updateHealth(game.player.health);
      dom.zoom.textContent = game.zoom.toFixed(1) + "x";
      dom.viewport.textContent = game.viewport.width + "x" + game.viewport.height;
      updateHotbar(game);
      updateQuests(game);
      updateInventoryPanel(game);
      updateCraftPanel(game);
      dom.btnBackdrop.setAttribute("aria-pressed", game.settings.backdropMode ? "true" : "false");
      dom.btnBackdrop.classList.toggle("is-on", Boolean(game.settings.backdropMode));
      RENDER.renderMinimap(dom.minimap, game.minimapView);
    }

    function setQuestHidden(hidden) {
      state.questHidden = hidden;
      dom.questTracker.classList.toggle("is-hidden", hidden);
      dom.questCollapse.textContent = hidden ? "Show" : "Hide";
      dom.btnQuests.setAttribute("aria-pressed", hidden ? "false" : "true");
    }

    function bind() {
      dom.btnQuests.addEventListener("click", function () {
        call("toggleQuests");
      });
      dom.btnInventory.addEventListener("click", function () {
        call("openPanel", "inventory");
      });
      dom.btnCraft.addEventListener("click", function () {
        call("openPanel", "craft");
      });
      dom.btnGuide.addEventListener("click", function () {
        call("openPanel", "guide");
      });
      dom.btnBackdrop.addEventListener("click", function () {
        call("toggleBackdrop");
      });
      dom.btnSave.addEventListener("click", function () {
        call("save");
      });
      dom.btnMenu.addEventListener("click", function () {
        call("openPanel", "menu");
      });
      dom.questCollapse.addEventListener("click", function () {
        call("toggleQuests");
      });
      dom.questOpen.addEventListener("click", function () {
        call("toggleQuests");
      });
      dom.welcomePlay.addEventListener("click", function () {
        call("play");
      });
      dom.welcomeGuide.addEventListener("click", function () {
        call("openPanel", "guide");
      });
      dom.welcomeNew.addEventListener("click", function () {
        call("newWorldPrompt");
      });
      document.querySelectorAll("[data-close]").forEach(function (button) {
        button.addEventListener("click", function () {
          call("closePanels");
        });
      });
      [dom.inventoryPanel, dom.craftPanel, dom.guidePanel, dom.menuPanel].forEach(function (panel) {
        panel.addEventListener("mousedown", function (event) {
          if (event.target === panel) {
            call("closePanels");
          }
        });
      });
      element("inventory-craft").addEventListener("click", function () {
        call("openPanel", "craft");
      });
      element("menu-resume").addEventListener("click", function () {
        call("closePanels");
      });
      element("menu-save").addEventListener("click", function () {
        call("save");
      });
      element("menu-guide").addEventListener("click", function () {
        call("openPanel", "guide");
      });
      element("menu-mute").addEventListener("click", function () {
        call("toggleMute");
      });
      element("menu-new-world").addEventListener("click", function () {
        call("newWorld", dom.seedInput.value);
      });
      element("menu-export").addEventListener("click", function () {
        call("exportSave");
      });
      element("save-import").addEventListener("change", function (event) {
        if (event.target.files && event.target.files.length) {
          call("importSave", event.target.files[0]);
        }
        event.target.value = "";
      });
    }

    buildHotbar();
    buildControls();
    bind();
    dom.menuVersion.textContent = CONFIG.editionLabel;
    dom.seedInput.value = String(CONFIG.seed);
    setStorageNote("Your world saves automatically in this browser.");

    return {
      CONTROLS: CONTROLS,
      update: update,
      toast: toast,
      setHint: setHint,
      showPulse: showPulse,
      openPanel: openPanel,
      closePanels: closePanels,
      panel: function () { return state.panel; },
      setWelcome: setWelcome,
      setStorageNote: setStorageNote,
      setMenuStatus: setMenuStatus,
      setMuteButton: setMuteButton,
      setMinimapCaption: setMinimapCaption,
      setStatus: setStatus,
      setQuestHidden: setQuestHidden,
      questHidden: function () { return state.questHidden; },
      syncSeed: function (seed) { dom.seedInput.value = String(seed); },
      focusGame: function () { dom.canvas.focus(); }
    };
  }

  return {
    CONTROLS: CONTROLS,
    createUI: createUI,
    paintLabel: paintLabel
  };
});
