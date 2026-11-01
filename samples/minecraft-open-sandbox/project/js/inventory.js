(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInventory = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxInventory");
  }

  function createInventory(items, selected) {
    const copy = {};
    if (items && typeof items === "object") {
      Object.keys(items).forEach(function (key) {
        const value = items[key];
        if (Number.isInteger(value) && value > 0) {
          copy[key] = value;
        }
      });
    }
    return {
      items: copy,
      selected: clampSlot(selected)
    };
  }

  function clampSlot(index) {
    if (!Number.isInteger(index)) {
      return 0;
    }
    return Math.max(0, Math.min(CONFIG.hotbar.length - 1, index));
  }

  function count(inventory, item) {
    const value = inventory.items[item];
    return Number.isInteger(value) && value > 0 ? value : 0;
  }

  function has(inventory, item, amount) {
    const wanted = amount === undefined ? 1 : amount;
    return count(inventory, item) >= wanted;
  }

  function add(inventory, item, amount) {
    const quantity = amount === undefined ? 1 : amount;
    if (!Number.isInteger(quantity) || quantity <= 0) {
      return false;
    }
    inventory.items[item] = count(inventory, item) + quantity;
    return true;
  }

  function remove(inventory, item, amount) {
    const quantity = amount === undefined ? 1 : amount;
    if (!Number.isInteger(quantity) || quantity <= 0) {
      return false;
    }
    if (count(inventory, item) < quantity) {
      return false;
    }
    const remaining = count(inventory, item) - quantity;
    if (remaining === 0) {
      delete inventory.items[item];
    } else {
      inventory.items[item] = remaining;
    }
    return true;
  }

  function selectSlot(inventory, index) {
    if (!Number.isInteger(index) || index < 0 || index >= CONFIG.hotbar.length) {
      return false;
    }
    inventory.selected = index;
    return true;
  }

  function cycleSlot(inventory, direction) {
    const step = direction < 0 ? -1 : 1;
    const size = CONFIG.hotbar.length;
    inventory.selected = (inventory.selected + step + size) % size;
    return inventory.selected;
  }

  function selectedItem(inventory) {
    return CONFIG.hotbar[inventory.selected];
  }

  function hotbarSlot(item) {
    return CONFIG.hotbar.indexOf(item);
  }

  function tools(inventory) {
    return Object.keys(CONFIG.tools).filter(function (tool) {
      return count(inventory, tool) > 0;
    });
  }

  function placeableSelected(inventory) {
    const item = selectedItem(inventory);
    if (!item) {
      return null;
    }
    if (!CONFIG.placeable[item]) {
      return null;
    }
    return count(inventory, item) > 0 ? item : null;
  }

  return {
    createInventory: createInventory,
    count: count,
    has: has,
    add: add,
    remove: remove,
    selectSlot: selectSlot,
    cycleSlot: cycleSlot,
    selectedItem: selectedItem,
    hotbarSlot: hotbarSlot,
    tools: tools,
    placeableSelected: placeableSelected
  };
});
