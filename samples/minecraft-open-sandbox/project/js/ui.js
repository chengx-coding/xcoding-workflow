/* DOM panels for inventory, crafting and furnace interaction. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"), require("./crafting.js"), require("./furnace.js"), require("./textures.js"));
  } else {
    root.SandboxUI = factory(root.SandboxConfig, root.SandboxInventory, root.SandboxCrafting, root.SandboxFurnace, root.SandboxTextures);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INV, CRAFT, FURNACE, TEX) {
  "use strict";

  function createUI(options) {
    const game = options.game;
    const toast = options.toast;
    const hasNearbyTable = options.hasNearbyTable;
    const updateHotbar = options.updateHotbar;
    const onChange = options.onChange || function () {};
    const onCraft = options.onCraft || function () {};

    const screens = {
      inventory: document.getElementById("inventory-screen"),
      furnace: document.getElementById("furnace-screen")
    };
    const gridEl = document.getElementById("inventory-grid");
    const hotbarGridEl = document.getElementById("inventory-hotbar");
    const recipeListEl = document.getElementById("recipe-list");
    const craftStatusEl = document.getElementById("craft-status");
    const furnaceStatusEl = document.getElementById("furnace-status");
    const furnaceFlameEl = document.getElementById("furnace-flame");
    const furnaceHotbarEl = document.getElementById("furnace-hotbar-grid");
    const furnaceSlots = {
      input: document.getElementById("furnace-input"),
      fuel: document.getElementById("furnace-fuel"),
      output: document.getElementById("furnace-output")
    };

    let active = null;
    let furnacePos = null;
    let cursor = null;
    let pendingRefresh = 0;

    const cursorEl = document.createElement("div");
    cursorEl.className = "cursor-stack";
    cursorEl.hidden = true;
    cursorEl.setAttribute("aria-hidden", "true");
    document.getElementById("stage").appendChild(cursorEl);

    function iconCanvas(id, size) {
      const icon = TEX.itemIcon(id);
      const canvas = document.createElement("canvas");
      canvas.width = 16;
      canvas.height = 16;
      canvas.style.width = (size || 32) + "px";
      canvas.style.height = (size || 32) + "px";
      if (icon) {
        canvas.getContext("2d").drawImage(icon, 0, 0);
      }
      return canvas;
    }

    function itemName(id) {
      const def = CONFIG.itemDefs[id];
      return def ? def.name : "Unknown";
    }

    function renderStackInto(element, stack) {
      element.innerHTML = "";
      if (!stack) {
        return;
      }
      element.appendChild(iconCanvas(stack.id, 32));
      if (stack.count > 1) {
        const count = document.createElement("span");
        count.className = "slot-count";
        count.textContent = String(stack.count);
        element.appendChild(count);
      }
      element.title = itemName(stack.id) + " ×" + stack.count;
    }

    function makeSlot(index, stack, context) {
      const element = document.createElement("div");
      element.className = "inventory-slot";
      element.dataset.index = String(index);
      element.dataset.context = context;
      element.setAttribute("role", "button");
      element.setAttribute("tabindex", "0");
      element.setAttribute("aria-label", stack ? itemName(stack.id) + ", " + stack.count : "Empty slot " + (index + 1));
      if (context === "hotbar" && index === game.inventory.selected) {
        element.classList.add("is-selected");
      }
      renderStackInto(element, stack);
      element.addEventListener("mousedown", function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (context === "hotbar" && !cursor && event.button === 0) {
          INV.setSelected(game.inventory, index);
          updateHotbar();
          refreshInventory();
          return;
        }
        clickPlayerSlot(index, event.button, event.shiftKey);
      });
      element.addEventListener("contextmenu", function (event) {
        event.preventDefault();
        if (context !== "hotbar" || cursor) {
          clickPlayerSlot(index, 2, event.shiftKey);
        }
      });
      return element;
    }

    function buildGrids() {
      gridEl.innerHTML = "";
      hotbarGridEl.innerHTML = "";
      for (let i = 9; i < INV.slotCount; i += 1) {
        gridEl.appendChild(makeSlot(i, game.inventory.slots[i], "storage"));
      }
      for (let i = 0; i < INV.hotbarCount; i += 1) {
        hotbarGridEl.appendChild(makeSlot(i, game.inventory.slots[i], "hotbar"));
      }
    }

    function buildFurnaceGrids() {
      if (!furnaceHotbarEl) {
        return;
      }
      furnaceHotbarEl.innerHTML = "";
      for (let i = 0; i < INV.hotbarCount; i += 1) {
        furnaceHotbarEl.appendChild(makeSlot(i, game.inventory.slots[i], "furnace-hotbar"));
      }
    }

    function refreshRecipes() {
      const table = Boolean(hasNearbyTable());
      craftStatusEl.textContent = table
        ? "Crafting table in range — all recipes are available."
        : "No table nearby — hand recipes only. Place a table to unlock tools.";
      recipeListEl.innerHTML = "";
      CRAFT.recipes.forEach(function (entry) {
        const craftable = CRAFT.canCraft(game.inventory, entry, table);
        const locked = entry.station === "table" && !table;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recipe" + (craftable ? " is-craftable" : "") + (locked ? " is-locked" : "");
        button.dataset.recipe = entry.id;
        button.title = CRAFT.ingredientLabel(entry);
        button.appendChild(iconCanvas(entry.output.id, 26));
        const text = document.createElement("span");
        const name = document.createElement("span");
        name.className = "recipe-name";
        name.textContent = itemName(entry.output.id) + (entry.output.count > 1 ? " ×" + entry.output.count : "");
        const ingredients = document.createElement("span");
        ingredients.className = "recipe-ingredients";
        ingredients.textContent = CRAFT.ingredientLabel(entry) + " · " + CRAFT.stationLabel(entry);
        text.appendChild(name);
        text.appendChild(document.createElement("br"));
        text.appendChild(ingredients);
        button.appendChild(text);
        button.addEventListener("click", function () {
          craftRecipe(entry);
        });
        recipeListEl.appendChild(button);
      });
    }

    function refreshInventory() {
      buildGrids();
      refreshRecipes();
      refreshCursor();
    }

    function refreshFurnace() {
      if (!furnacePos) {
        return;
      }
      const state = FURNACE.get(game.furnaces, furnacePos.x, furnacePos.y, false);
      if (!state) {
        return;
      }
      renderStackInto(furnaceSlots.input, state.input);
      renderStackInto(furnaceSlots.fuel, state.fuel);
      renderStackInto(furnaceSlots.output, state.output);
      const burning = state.burnTime > 0 && state.burnMax > 0;
      furnaceFlameEl.style.height = burning ? Math.max(8, Math.round((state.burnTime / state.burnMax) * 100)) + "%" : "0%";
      if (!state.input) {
        furnaceStatusEl.textContent = "Put ore in Smelt and coal or wood in Fuel.";
      } else if (!FURNACE.smeltFor(state.input.id)) {
        furnaceStatusEl.textContent = itemName(state.input.id) + " cannot be smelted.";
      } else if (!state.fuel) {
        furnaceStatusEl.textContent = "Add coal, planks, logs, sticks or ladders to Fuel.";
      } else if (burning) {
        furnaceStatusEl.textContent = "Smelting… " + Math.max(0, Math.ceil(state.cookMax - state.cookTime)) + "s";
      } else {
        furnaceStatusEl.textContent = "Ready to smelt.";
      }
    }

    function refreshCursor() {
      if (!cursor) {
        cursorEl.hidden = true;
        cursorEl.innerHTML = "";
        return;
      }
      cursorEl.hidden = false;
      cursorEl.innerHTML = "";
      cursorEl.appendChild(iconCanvas(cursor.id, 30));
      if (cursor.count > 1) {
        const badge = document.createElement("span");
        badge.textContent = String(cursor.count);
        cursorEl.appendChild(badge);
      }
    }

    function setCursor(stack) {
      cursor = stack && stack.count > 0 ? stack : null;
      refreshCursor();
    }

    function returnCursor() {
      if (!cursor) {
        return;
      }
      const leftover = INV.addItem(game.inventory, cursor.id, cursor.count);
      if (leftover > 0) {
        toast("Inventory full — " + leftover + "× " + itemName(cursor.id) + " could not be returned", "warn");
      }
      cursor = null;
      refreshCursor();
      updateHotbar();
    }

    function clickPlayerSlot(index, button, shift) {
      if (shift && !cursor) {
        const slot = game.inventory.slots[index];
        if (!slot) {
          return;
        }
        const targetStart = index < 9 ? 9 : 0;
        const targetEnd = index < 9 ? INV.slotCount : 9;
        let moved = false;
        for (let i = targetStart; i < targetEnd; i += 1) {
          if (!game.inventory.slots[i] || game.inventory.slots[i].id === slot.id) {
            INV.moveStack(game.inventory, index, i);
            moved = true;
            break;
          }
        }
        if (!moved) {
          toast("No room to move that stack", "warn");
        }
        afterChange();
        return;
      }

      if (button === 2) {
        if (!cursor) {
          const slot = game.inventory.slots[index];
          if (slot) {
            setCursor(INV.takeFromSlot(game.inventory, index, Math.ceil(slot.count / 2)));
          }
        } else {
          placeOne(index);
        }
        afterChange();
        return;
      }

      if (!cursor) {
        setCursor(INV.takeFromSlot(game.inventory, index));
      } else {
        const slot = game.inventory.slots[index];
        if (!slot) {
          game.inventory.slots[index] = cursor;
          setCursor(null);
        } else if (slot.id === cursor.id) {
          const limit = INV.maxStack(slot.id);
          const moved = Math.min(limit - slot.count, cursor.count);
          slot.count += moved;
          cursor.count -= moved;
          setCursor(cursor.count > 0 ? cursor : null);
        } else {
          const old = slot;
          game.inventory.slots[index] = cursor;
          setCursor(old);
        }
      }
      afterChange();
    }

    function placeOne(index) {
      const slot = game.inventory.slots[index];
      if (!cursor) {
        return;
      }
      if (!slot) {
        game.inventory.slots[index] = { id: cursor.id, count: 1 };
        cursor.count -= 1;
        setCursor(cursor.count > 0 ? cursor : null);
      } else if (slot.id === cursor.id && slot.count < INV.maxStack(slot.id)) {
        slot.count += 1;
        cursor.count -= 1;
        setCursor(cursor.count > 0 ? cursor : null);
      } else if (slot.id !== cursor.id) {
        toast("Right-click only stacks with the same item, or uses an empty slot", "warn");
      }
    }

    function afterChange() {
      INV.normalize(game.inventory);
      updateHotbar();
      if (active === "inventory") {
        refreshInventory();
      } else if (active === "furnace") {
        refreshFurnace();
        buildGrids();
        buildFurnaceGrids();
      }
      onChange();
    }

    function craftRecipe(entry) {
      const table = Boolean(hasNearbyTable());
      const result = CRAFT.craft(game.inventory, entry, table);
      if (!result.ok) {
        toast(result.reason || "Cannot craft that", "warn");
        return;
      }
      toast("Crafted " + itemName(entry.output.id) + " ×" + entry.output.count);
      onCraft();
      updateHotbar();
      refreshInventory();
      onChange();
    }

    function clickFurnaceSlot(kind, button, shift) {
      if (!furnacePos) {
        return;
      }
      const state = FURNACE.get(game.furnaces, furnacePos.x, furnacePos.y, true);
      if (shift && !cursor) {
        const stack = state[kind];
        if (!stack) {
          return;
        }
        if (kind === "output") {
          setCursor({ id: stack.id, count: stack.count });
          state.output = null;
        } else {
          const leftover = INV.addItem(game.inventory, stack.id, stack.count);
          const moved = stack.count - leftover;
          stack.count -= moved;
          if (stack.count <= 0) {
            state[kind] = null;
          } else {
            toast("Inventory full — some items stayed in the furnace", "warn");
          }
        }
        afterChange();
        return;
      }
      if (button === 2) {
        if (!cursor) {
          if (state[kind]) {
            setCursor({ id: state[kind].id, count: 1 });
            state[kind].count -= 1;
            if (state[kind].count <= 0) {
              state[kind] = null;
            }
          }
        } else if (kind !== "output") {
          if (!state[kind]) {
            state[kind] = { id: cursor.id, count: 1 };
            cursor.count -= 1;
            setCursor(cursor.count > 0 ? cursor : null);
          } else if (state[kind].id === cursor.id) {
            state[kind].count += 1;
            cursor.count -= 1;
            setCursor(cursor.count > 0 ? cursor : null);
          }
        }
        afterChange();
        return;
      }

      if (kind === "output") {
        if (!cursor) {
          if (state.output) {
            setCursor({ id: state.output.id, count: state.output.count });
            state.output = null;
          }
        } else if (state.output && state.output.id === cursor.id) {
          const limit = INV.maxStack(cursor.id);
          const moved = Math.min(limit - cursor.count, state.output.count);
          cursor.count += moved;
          state.output.count -= moved;
          if (state.output.count <= 0) {
            state.output = null;
          }
          setCursor(cursor);
        }
        afterChange();
        return;
      }

      if (!cursor) {
        if (state[kind]) {
          setCursor({ id: state[kind].id, count: state[kind].count });
          state[kind] = null;
        }
      } else if (!state[kind]) {
        state[kind] = cursor;
        setCursor(null);
      } else if (state[kind].id === cursor.id) {
        const limit = INV.maxStack(cursor.id);
        const moved = Math.min(limit - state[kind].count, cursor.count);
        state[kind].count += moved;
        cursor.count -= moved;
        setCursor(cursor.count > 0 ? cursor : null);
      } else {
        const old = state[kind];
        state[kind] = cursor;
        setCursor(old);
      }
      afterChange();
    }

    function bindFurnaceSlots() {
      Object.keys(furnaceSlots).forEach(function (kind) {
        const element = furnaceSlots[kind];
        element.addEventListener("mousedown", function (event) {
          event.preventDefault();
          event.stopPropagation();
          clickFurnaceSlot(kind, event.button, event.shiftKey);
        });
        element.addEventListener("contextmenu", function (event) {
          event.preventDefault();
          clickFurnaceSlot(kind, 2, event.shiftKey);
        });
      });
    }
    bindFurnaceSlots();

    function openInventory() {
      active = "inventory";
      furnacePos = null;
      refreshInventory();
      screens.inventory.classList.add("is-open");
    }

    function openFurnace(x, y) {
      active = "furnace";
      furnacePos = { x: x, y: y };
      FURNACE.get(game.furnaces, x, y, true);
      buildGrids();
      buildFurnaceGrids();
      refreshFurnace();
      screens.furnace.classList.add("is-open");
    }

    function close() {
      returnCursor();
      active = null;
      furnacePos = null;
      screens.inventory.classList.remove("is-open");
      screens.furnace.classList.remove("is-open");
    }

    function hide() {
      screens.inventory.classList.remove("is-open");
      screens.furnace.classList.remove("is-open");
    }

    function tick() {
      if (active !== "furnace" || !furnacePos) {
        return;
      }
      pendingRefresh += 1;
      if (pendingRefresh < 8) {
        return;
      }
      pendingRefresh = 0;
      refreshFurnace();
    }

    function onPointerMove(event) {
      if (cursorEl.hidden) {
        return;
      }
      const stage = document.getElementById("stage").getBoundingClientRect();
      cursorEl.style.left = event.clientX - stage.left + "px";
      cursorEl.style.top = event.clientY - stage.top + "px";
    }
    document.getElementById("stage").addEventListener("mousemove", onPointerMove);

    return {
      openInventory: openInventory,
      openFurnace: openFurnace,
      close: close,
      hide: hide,
      refresh: refreshInventory,
      refreshFurnace: refreshFurnace,
      tick: tick,
      isOpen: function () { return active !== null; },
      activeKind: function () { return active; },
      debug: function () { return { active: active, cursor: cursor ? { id: cursor.id, count: cursor.count } : null, furnacePos: furnacePos }; }
    };
  }

  return { createUI: createUI };
});
