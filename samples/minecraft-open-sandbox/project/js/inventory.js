/* Stack, hotbar and slot operations shared by the page and the tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInventory = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const SLOT_COUNT = 36;
  const HOTBAR_COUNT = 9;

  function maxStack(id) {
    const def = CONFIG.itemDefs[id];
    return def ? def.maxStack : 64;
  }

  function makeStack(id, count) {
    if (!CONFIG.itemDefs[id] || count <= 0) {
      return null;
    }
    const limit = maxStack(id);
    return { id: id, count: Math.min(Math.floor(count), limit) };
  }

  function createInventory() {
    return {
      slots: new Array(SLOT_COUNT).fill(null),
      selected: 0
    };
  }

  function normalize(inventory) {
    if (!inventory || !Array.isArray(inventory.slots)) {
      throw new Error("Invalid inventory");
    }
    if (!Number.isInteger(inventory.selected)) {
      inventory.selected = 0;
    }
    inventory.selected = ((inventory.selected % HOTBAR_COUNT) + HOTBAR_COUNT) % HOTBAR_COUNT;
    for (let i = 0; i < SLOT_COUNT; i += 1) {
      const slot = inventory.slots[i];
      if (!slot || !CONFIG.itemDefs[slot.id] || slot.count <= 0) {
        inventory.slots[i] = null;
      } else {
        slot.count = Math.min(slot.count, maxStack(slot.id));
      }
    }
    return inventory;
  }

  function addItem(inventory, id, count) {
    let remaining = Math.max(0, Math.floor(count));
    if (!CONFIG.itemDefs[id] || remaining <= 0) {
      return remaining;
    }
    const limit = maxStack(id);
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      const slot = inventory.slots[i];
      if (slot && slot.id === id && slot.count < limit) {
        const moved = Math.min(limit - slot.count, remaining);
        slot.count += moved;
        remaining -= moved;
      }
    }
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      if (!inventory.slots[i]) {
        const moved = Math.min(limit, remaining);
        inventory.slots[i] = { id: id, count: moved };
        remaining -= moved;
      }
    }
    return remaining;
  }

  function countItem(inventory, id) {
    let total = 0;
    for (let i = 0; i < inventory.slots.length; i += 1) {
      const slot = inventory.slots[i];
      if (slot && slot.id === id) {
        total += slot.count;
      }
    }
    return total;
  }

  function removeItem(inventory, id, count) {
    let remaining = Math.max(0, Math.floor(count));
    if (remaining <= 0) {
      return 0;
    }
    for (let i = inventory.slots.length - 1; i >= 0 && remaining > 0; i -= 1) {
      const slot = inventory.slots[i];
      if (slot && slot.id === id) {
        const moved = Math.min(slot.count, remaining);
        slot.count -= moved;
        remaining -= moved;
        if (slot.count <= 0) {
          inventory.slots[i] = null;
        }
      }
    }
    return Math.floor(count) - remaining;
  }


  function spaceFor(inventory, id, count) {
    if (!CONFIG.itemDefs[id]) {
      return 0;
    }
    const limit = maxStack(id);
    let space = 0;
    for (let i = 0; i < inventory.slots.length; i += 1) {
      const slot = inventory.slots[i];
      if (!slot) {
        space += limit;
      } else if (slot.id === id) {
        space += limit - slot.count;
      }
      if (space >= count) {
        return count;
      }
    }
    return space;
  }

  function hasSpaceFor(inventory, id, count) {
    return spaceFor(inventory, id, count) >= count;
  }

  function hasItem(inventory, id, count) {
    return countItem(inventory, id) >= count;
  }

  function selectedStack(inventory) {
    return inventory.slots[inventory.selected] || null;
  }

  function setSelected(inventory, index) {
    if (!Number.isInteger(index)) {
      return;
    }
    inventory.selected = ((index % HOTBAR_COUNT) + HOTBAR_COUNT) % HOTBAR_COUNT;
  }

  function cycleSelected(inventory, direction) {
    const delta = direction < 0 ? -1 : 1;
    inventory.selected = (inventory.selected + delta + HOTBAR_COUNT) % HOTBAR_COUNT;
  }

  function takeFromSlot(inventory, index, amount) {
    const slot = inventory.slots[index];
    if (!slot) {
      return null;
    }
    const moved = Math.max(1, Math.min(slot.count, amount || slot.count));
    const stack = { id: slot.id, count: moved };
    slot.count -= moved;
    if (slot.count <= 0) {
      inventory.slots[index] = null;
    }
    return stack;
  }

  function putIntoSlot(inventory, index, stack) {
    if (!stack || !CONFIG.itemDefs[stack.id]) {
      return null;
    }
    const current = inventory.slots[index];
    if (!current) {
      inventory.slots[index] = { id: stack.id, count: stack.count };
      return null;
    }
    if (current.id === stack.id) {
      const limit = maxStack(current.id);
      const moved = Math.min(limit - current.count, stack.count);
      current.count += moved;
      const left = stack.count - moved;
      return left > 0 ? { id: stack.id, count: left } : null;
    }
    inventory.slots[index] = { id: stack.id, count: stack.count };
    return current;
  }

  function moveStack(inventory, from, to, amount) {
    if (from === to) {
      return false;
    }
    const source = inventory.slots[from];
    if (!source) {
      return false;
    }
    const moving = amount ? Math.min(amount, source.count) : source.count;
    const stack = takeFromSlot(inventory, from, moving);
    const leftover = putIntoSlot(inventory, to, stack);
    if (leftover) {
      // Put the unmerged remainder back where it came from.
      if (!inventory.slots[from]) {
        inventory.slots[from] = leftover;
      } else {
        addItem(inventory, leftover.id, leftover.count);
      }
    }
    return true;
  }

  function splitSlot(inventory, index) {
    const slot = inventory.slots[index];
    if (!slot || slot.count < 2) {
      return null;
    }
    const half = Math.floor(slot.count / 2);
    slot.count -= half;
    const empty = inventory.slots.indexOf(null);
    if (empty < 0) {
      slot.count += half;
      return null;
    }
    inventory.slots[empty] = { id: slot.id, count: half };
    return empty;
  }

  function consumeSelected(inventory, amount) {
    const slot = selectedStack(inventory);
    if (!slot) {
      return false;
    }
    const moved = amount || 1;
    if (slot.count < moved) {
      return false;
    }
    slot.count -= moved;
    if (slot.count <= 0) {
      inventory.slots[inventory.selected] = null;
    }
    return true;
  }

  function selectedTool(inventory) {
    const slot = selectedStack(inventory);
    if (!slot) {
      return null;
    }
    const def = CONFIG.itemDefs[slot.id];
    return def && def.kind === "tool" ? def : null;
  }

  function serializeInventory(inventory) {
    return inventory.slots.map(function (slot) {
      return slot ? [slot.id, slot.count] : null;
    });
  }

  function deserializeInventory(data) {
    const inventory = createInventory();
    if (!Array.isArray(data)) {
      return inventory;
    }
    for (let i = 0; i < Math.min(SLOT_COUNT, data.length); i += 1) {
      const entry = data[i];
      if (Array.isArray(entry) && CONFIG.itemDefs[entry[0]] && entry[1] > 0) {
        inventory.slots[i] = { id: entry[0], count: Math.min(entry[1], maxStack(entry[0])) };
      }
    }
    return inventory;
  }

  function sortInventory(inventory) {
    const totals = {};
    for (let i = 0; i < inventory.slots.length; i += 1) {
      const slot = inventory.slots[i];
      if (slot) {
        totals[slot.id] = (totals[slot.id] || 0) + slot.count;
        inventory.slots[i] = null;
      }
    }
    Object.keys(totals)
      .map(Number)
      .sort(function (a, b) { return a - b; })
      .forEach(function (id) {
        addItem(inventory, id, totals[id]);
      });
  }

  return {
    slotCount: SLOT_COUNT,
    hotbarCount: HOTBAR_COUNT,
    maxStack: maxStack,
    makeStack: makeStack,
    createInventory: createInventory,
    normalize: normalize,
    addItem: addItem,
    countItem: countItem,
    removeItem: removeItem,
    hasItem: hasItem,
    spaceFor: spaceFor,
    hasSpaceFor: hasSpaceFor,
    selectedStack: selectedStack,
    setSelected: setSelected,
    cycleSelected: cycleSelected,
    takeFromSlot: takeFromSlot,
    putIntoSlot: putIntoSlot,
    moveStack: moveStack,
    splitSlot: splitSlot,
    consumeSelected: consumeSelected,
    selectedTool: selectedTool,
    serializeInventory: serializeInventory,
    deserializeInventory: deserializeInventory,
    sortInventory: sortInventory
  };
});
