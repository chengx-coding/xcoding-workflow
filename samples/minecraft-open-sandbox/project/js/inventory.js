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
    const slots = new Array(CONFIG.inventorySize).fill(null);
    return { slots: slots, selected: 0 };
  }

  function stackLimit(id) {
    return BLOCKS.isTool(id) ? 1 : CONFIG.stackLimit;
  }

  function add(inventory, id, count) {
    let remaining = Math.max(0, Math.floor(count || 0));
    const limit = stackLimit(id);
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      const stack = inventory.slots[i];
      if (stack && stack.id === id && stack.count < limit) {
        const room = limit - stack.count;
        const moved = Math.min(room, remaining);
        stack.count += moved;
        remaining -= moved;
      }
    }
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      if (inventory.slots[i] === null) {
        const moved = Math.min(limit, remaining);
        inventory.slots[i] = { id: id, count: moved };
        remaining -= moved;
      }
    }
    return remaining;
  }

  function remove(inventory, id, count) {
    let remaining = Math.max(0, Math.floor(count || 0));
    let removed = 0;
    for (let i = inventory.slots.length - 1; i >= 0 && remaining > 0; i -= 1) {
      const stack = inventory.slots[i];
      if (!stack || stack.id !== id) {
        continue;
      }
      const taken = Math.min(stack.count, remaining);
      stack.count -= taken;
      remaining -= taken;
      removed += taken;
      if (stack.count <= 0) {
        inventory.slots[i] = null;
      }
    }
    return removed;
  }

  function countOf(inventory, id) {
    let total = 0;
    for (let i = 0; i < inventory.slots.length; i += 1) {
      const stack = inventory.slots[i];
      if (stack && stack.id === id) {
        total += stack.count;
      }
    }
    return total;
  }

  function has(inventory, id, count) {
    const need = count === undefined ? 1 : count;
    return countOf(inventory, id) >= need;
  }

  function swap(inventory, from, to) {
    const size = inventory.slots.length;
    if (from < 0 || to < 0 || from >= size || to >= size || from === to) {
      return false;
    }
    const a = inventory.slots[from];
    const b = inventory.slots[to];
    if (a && b && a.id === b.id && stackLimit(a.id) > 1) {
      const limit = stackLimit(a.id);
      const room = limit - b.count;
      if (room > 0) {
        const moved = Math.min(room, a.count);
        b.count += moved;
        a.count -= moved;
        if (a.count <= 0) {
          inventory.slots[from] = null;
        }
        return true;
      }
    }
    inventory.slots[from] = b;
    inventory.slots[to] = a;
    return true;
  }

  function select(inventory, index) {
    if (!Number.isInteger(index)) {
      return false;
    }
    const size = CONFIG.hotbarSize;
    const wrapped = ((index % size) + size) % size;
    inventory.selected = wrapped;
    return true;
  }

  function selectedStack(inventory) {
    return inventory.slots[inventory.selected] || null;
  }

  function firstEmpty(inventory) {
    for (let i = 0; i < inventory.slots.length; i += 1) {
      if (inventory.slots[i] === null) {
        return i;
      }
    }
    return -1;
  }

  function usedSlots(inventory) {
    let used = 0;
    for (let i = 0; i < inventory.slots.length; i += 1) {
      if (inventory.slots[i]) {
        used += 1;
      }
    }
    return used;
  }

  function serialize(inventory) {
    return {
      selected: inventory.selected,
      slots: inventory.slots.map(function mapStack(stack) {
        return stack ? { id: stack.id, count: stack.count } : null;
      })
    };
  }

  function deserialize(saved) {
    const inventory = createInventory();
    if (!saved || !Array.isArray(saved.slots)) {
      return inventory;
    }
    for (let i = 0; i < inventory.slots.length && i < saved.slots.length; i += 1) {
      const stack = saved.slots[i];
      if (!stack || !BLOCKS.itemDef(stack.id) || !Number.isInteger(stack.count) || stack.count <= 0) {
        continue;
      }
      inventory.slots[i] = { id: stack.id, count: Math.min(stack.count, stackLimit(stack.id)) };
    }
    if (Number.isInteger(saved.selected)) {
      select(inventory, saved.selected);
    }
    return inventory;
  }

  return {
    createInventory: createInventory,
    stackLimit: stackLimit,
    add: add,
    remove: remove,
    countOf: countOf,
    has: has,
    swap: swap,
    select: select,
    selectedStack: selectedStack,
    firstEmpty: firstEmpty,
    usedSlots: usedSlots,
    serialize: serialize,
    deserialize: deserialize
  };
});
