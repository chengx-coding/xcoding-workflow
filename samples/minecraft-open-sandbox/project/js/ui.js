(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./config.js"),
      require("./inventory.js"),
      require("./crafting.js"),
      require("./lighting.js")
    );
  } else {
    root.SandboxUI = factory(
      root.SandboxConfig,
      root.SandboxInventory,
      root.SandboxCrafting,
      root.SandboxLighting
    );
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INVENTORY, CRAFTING, LIGHTING) {
  "use strict";

  if (!CONFIG || !INVENTORY || !CRAFTING || !LIGHTING) {
    throw new Error(
      "SandboxConfig, SandboxInventory, SandboxCrafting and SandboxLighting are required before SandboxUI"
    );
  }

  function timeLabel(time) {
    const t = ((time % 1) + 1) % 1;
    if (t < 0.08 || t >= 0.92) {
      return "Dawn";
    }
    if (t < 0.3) {
      return "Morning";
    }
    if (t < 0.44) {
      return "Afternoon";
    }
    if (t < 0.56) {
      return "Dusk";
    }
    return "Night";
  }

  function buildUI(handlers) {
    const canvas = document.getElementById("game");
    const hotbar = document.getElementById("hotbar");
    const hudTime = document.getElementById("hud-time");
    const overlay = document.getElementById("overlay");
    const panels = {
      help: document.getElementById("help-panel"),
      pause: document.getElementById("pause-panel"),
      craft: document.getElementById("craft-panel")
    };
    const helpControls = document.getElementById("help-controls");
    const craftList = document.getElementById("craft-list");
    const toastElement = document.getElementById("toast");
    const saveIndicator = document.getElementById("save-indicator");
    const pauseStatus = document.getElementById("pause-status");
    const pauseSeed = document.getElementById("pause-seed");
    const newWorldButton = document.querySelector('[data-action="new-world"]');
    const slots = [];
    let toastTimer = 0;
    let saveTimer = 0;
    let newWorldArmed = false;
    let newWorldTimer = 0;
    let currentPanel = "";

    CONFIG.controls.forEach(function (control) {
      const key = document.createElement("div");
      key.className = "keycap";
      key.textContent = control.keys;
      const action = document.createElement("div");
      action.className = "action";
      action.textContent = control.action;
      helpControls.appendChild(key);
      helpControls.appendChild(action);
    });

    CONFIG.hotbar.forEach(function (item, index) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot is-empty";
      button.dataset.item = item;
      button.setAttribute("aria-label", CONFIG.itemNames[item] + " slot " + (index + 1));
      const palette = CONFIG.palette[CONFIG.placeable[item]];
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = palette ? palette.base : "#888888";
      const keyLabel = document.createElement("span");
      keyLabel.className = "key";
      keyLabel.textContent = String(index + 1);
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = "";
      button.appendChild(swatch);
      button.appendChild(keyLabel);
      button.appendChild(count);
      button.addEventListener("click", function () {
        if (handlers.onSelect) {
          handlers.onSelect(index);
        }
      });
      hotbar.appendChild(button);
      slots.push({ button: button, count: count });
    });

    function showPanel(name) {
      currentPanel = name;
      overlay.classList.toggle("hidden", !name);
      Object.keys(panels).forEach(function (key) {
        panels[key].classList.toggle("hidden", key !== name);
      });
    }

    function hidePanel() {
      showPanel("");
    }

    function showHelp() {
      showPanel("help");
    }

    function showPause() {
      showPanel("pause");
    }

    function showCraft(inventory) {
      refreshCraft(inventory);
      showPanel("craft");
    }

    function isOpen() {
      return currentPanel !== "";
    }

    function current() {
      return currentPanel;
    }

    function updateHotbar(inventory) {
      slots.forEach(function (slot, index) {
        const item = CONFIG.hotbar[index];
        const amount = INVENTORY.count(inventory, item);
        slot.count.textContent = amount > 0 ? String(amount) : "";
        slot.button.classList.toggle("is-empty", amount <= 0);
        slot.button.classList.toggle("is-selected", inventory.selected === index);
        slot.button.setAttribute(
          "aria-label",
          CONFIG.itemNames[item] + " slot " + (index + 1) + ", " + amount + " available"
        );
      });
    }

    function updateHud(state) {
      const label = timeLabel(state.time.tick / CONFIG.dayLengthSeconds);
      hudTime.textContent =
        "Day " +
        state.time.day +
        " · " +
        label +
        " · X " +
        Math.floor(state.player.x) +
        " · Y " +
        Math.floor(state.player.y);
    }

    function toast(message, duration) {
      toastElement.textContent = message;
      toastElement.classList.add("is-visible");
      if (toastTimer) {
        window.clearTimeout(toastTimer);
      }
      toastTimer = window.setTimeout(function () {
        toastElement.classList.remove("is-visible");
      }, duration || 2400);
    }

    function flashSave(message) {
      saveIndicator.textContent = message;
      saveIndicator.classList.add("is-visible");
      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }
      saveTimer = window.setTimeout(function () {
        saveIndicator.classList.remove("is-visible");
      }, 1800);
    }

    function updatePause(state, persistent, note) {
      const items = Object.keys(state.inventory.items).filter(function (key) {
        return state.inventory.items[key] > 0;
      });
      const summary = items.length
        ? items
            .map(function (key) {
              return (CONFIG.itemNames[key] || key) + " x" + state.inventory.items[key];
            })
            .join(" · ")
        : "empty";
      pauseStatus.textContent =
        (note || "Your world is paused.") +
        " Inventory: " +
        summary +
        ". " +
        (persistent
          ? "Progress is stored in this browser."
          : "Browser storage is unavailable; progress lasts for this session only.");
      pauseSeed.textContent =
        "World seed: " + state.world.seed + " · " + CONFIG.worldWidth + "x" + CONFIG.worldHeight;
      newWorldButton.textContent = "New world";
      newWorldArmed = false;
      if (newWorldTimer) {
        window.clearTimeout(newWorldTimer);
        newWorldTimer = 0;
      }
    }

    function refreshCraft(inventory) {
      craftList.innerHTML = "";
      CONFIG.recipes.forEach(function (recipe) {
        const row = document.createElement("div");
        row.className = "craft-row";
        const label = document.createElement("div");
        const name = document.createElement("span");
        name.className = "craft-name";
        name.textContent = recipe.name;
        const outputKeys = Object.keys(recipe.yield);
        const output = outputKeys
          .map(function (key) {
            return (CONFIG.itemNames[key] || key) + " x" + recipe.yield[key];
          })
          .join(", ");
        const cost = document.createElement("span");
        cost.className = "craft-cost";
        const costParts = Object.keys(recipe.cost).map(function (key) {
          const have = INVENTORY.count(inventory, key);
          const need = recipe.cost[key];
          return (
            '<span class="' +
            (have < need ? "missing" : "") +
            '">' +
            (CONFIG.itemNames[key] || key) +
            " " +
            have +
            "/" +
            need +
            "</span>"
          );
        });
        cost.innerHTML = costParts.join(" · ") + " &rarr; " + output;
        label.appendChild(name);
        label.appendChild(cost);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button craft-button";
        button.dataset.recipe = recipe.id;
        button.textContent = "Craft";
        button.disabled = !CRAFTING.canCraft(inventory, recipe);
        button.addEventListener("click", function () {
          if (handlers.onCraft) {
            handlers.onCraft(recipe.id);
          }
        });
        row.appendChild(label);
        row.appendChild(button);
        craftList.appendChild(row);
      });
    }

    function resetNewWorld() {
      newWorldArmed = false;
      newWorldButton.textContent = "New world";
      if (newWorldTimer) {
        window.clearTimeout(newWorldTimer);
        newWorldTimer = 0;
      }
    }

    document.querySelector('[data-action="resume"]').addEventListener("click", function () {
      if (handlers.onResume) {
        handlers.onResume();
      }
    });
    document.querySelector('[data-action="save"]').addEventListener("click", function () {
      if (handlers.onSave) {
        handlers.onSave();
      }
    });
    document.querySelector('[data-action="help"]').addEventListener("click", function () {
      showHelp();
    });
    document.querySelector('[data-action="close-help"]').addEventListener("click", function () {
      if (handlers.onResume) {
        handlers.onResume();
      }
    });
    document.querySelector('[data-action="close-craft"]').addEventListener("click", function () {
      if (handlers.onResume) {
        handlers.onResume();
      }
    });
    newWorldButton.addEventListener("click", function () {
      if (!newWorldArmed) {
        newWorldArmed = true;
        newWorldButton.textContent = "Click again to confirm";
        newWorldTimer = window.setTimeout(resetNewWorld, 4000);
        return;
      }
      resetNewWorld();
      if (handlers.onNewWorld) {
        handlers.onNewWorld();
      }
    });

    return {
      showHelp: showHelp,
      showPause: showPause,
      showCraft: showCraft,
      hidePanel: hidePanel,
      isOpen: isOpen,
      current: current,
      updateHotbar: updateHotbar,
      updateHud: updateHud,
      updatePause: updatePause,
      refreshCraft: refreshCraft,
      toast: toast,
      flashSave: flashSave,
      canvas: canvas
    };
  }

  return { buildUI: buildUI };
});
