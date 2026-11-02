(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"));
  } else {
    root.SandboxInventory = factory(root.SandboxConfig, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS) {
  "use strict";

  if (!CONFIG || !BLOCKS) {
    throw new Error("SandboxConfig and SandboxBlocks are required before SandboxInventory");
  }

  function createInventory() {
    return {
      items: Object.create(null),
      hotbar: new Array(CONFIG.hotbarSize).fill(0),
      selected: 0
    };
  }

  function count(inventory, id) {
    return inventory.items[id] || 0;
  }

  function has(inventory, id, amount) {
    return count(inventory, id) >= (amount || 1);
  }

  function add(inventory, id, amount) {
    const quantity = Math.max(0, Math.floor(amount || 1));
    if (!BLOCKS.item(id) || quantity <= 0) {
      return 0;
    }
    inventory.items[id] = count(inventory, id) + quantity;
    ensureHotbar(inventory, id);
    return quantity;
  }

  function remove(inventory, id, amount) {
    const quantity = Math.max(0, Math.floor(amount || 1));
    if (count(inventory, id) < quantity) {
      return false;
    }
    const left = count(inventory, id) - quantity;
    if (left === 0) {
      delete inventory.items[id];
      // Keep hotbar assignments honest: clear slots that no longer hold items.
      for (let index = 0; index < inventory.hotbar.length; index += 1) {
        if (inventory.hotbar[index] === id) {
          inventory.hotbar[index] = 0;
        }
      }
    } else {
      inventory.items[id] = left;
    }
    return true;
  }

  function ensureHotbar(inventory, id) {
    if (inventory.hotbar.indexOf(id) >= 0) {
      return true;
    }
    for (let index = 0; index < inventory.hotbar.length; index += 1) {
      if (!inventory.hotbar[index]) {
        inventory.hotbar[index] = id;
        return true;
      }
    }
    return false;
  }

  function select(inventory, index) {
    if (index < 0 || index >= inventory.hotbar.length) {
      return false;
    }
    inventory.selected = index;
    return true;
  }

  function selectedId(inventory) {
    return inventory.hotbar[inventory.selected] || 0;
  }

  function selectedDefinition(inventory) {
    return BLOCKS.item(selectedId(inventory));
  }

  function entries(inventory) {
    return Object.keys(inventory.items)
      .map(function (key) {
        return { id: Number(key), count: inventory.items[key] };
      })
      .filter(function (entry) {
        return entry.count > 0;
      })
      .sort(function (a, b) {
        return a.id - b.id;
      });
  }

  function totalItems(inventory) {
    return entries(inventory).reduce(function (sum, entry) {
      return sum + entry.count;
    }, 0);
  }

  function bestTool(inventory, toolKind) {
    let best = null;
    Object.keys(inventory.items).forEach(function (key) {
      const definition = BLOCKS.item(Number(key));
      if (!definition || definition.kind !== "tool" || definition.tool !== toolKind) {
        return;
      }
      if (!best || definition.tier > best.tier || (definition.tier === best.tier && definition.speed > best.speed)) {
        best = definition;
      }
    });
    return best;
  }

  function serialize(inventory) {
    return {
      items: entries(inventory),
      hotbar: inventory.hotbar.slice(),
      selected: inventory.selected
    };
  }

  function deserialize(payload) {
    const inventory = createInventory();
    if (!payload || !Array.isArray(payload.items)) {
      return inventory;
    }
    payload.items.forEach(function (entry) {
      if (entry && BLOCKS.item(entry.id) && entry.count > 0) {
        inventory.items[entry.id] = Math.floor(entry.count);
      }
    });
    if (Array.isArray(payload.hotbar)) {
      for (let index = 0; index < inventory.hotbar.length; index += 1) {
        const value = payload.hotbar[index];
        inventory.hotbar[index] = BLOCKS.item(value) && inventory.items[value] ? value : 0;
      }
    }
    if (Number.isInteger(payload.selected)) {
      select(inventory, payload.selected);
    }
    return inventory;
  }

  return {
    createInventory: createInventory,
    count: count,
    has: has,
    add: add,
    remove: remove,
    ensureHotbar: ensureHotbar,
    select: select,
    selectedId: selectedId,
    selectedDefinition: selectedDefinition,
    entries: entries,
    totalItems: totalItems,
    bestTool: bestTool,
    serialize: serialize,
    deserialize: deserialize
  };
});
