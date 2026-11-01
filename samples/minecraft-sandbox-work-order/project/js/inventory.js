(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInventory = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const MAX_BLOCK_ID = 9;

  function keyOf(blockId) {
    return String(blockId);
  }

  function createInventory(initial) {
    const inventory = {};
    for (let blockId = 1; blockId <= MAX_BLOCK_ID; blockId += 1) {
      inventory[keyOf(blockId)] = 0;
    }
    if (initial) {
      Object.keys(initial).forEach(function (key) {
        const blockId = Number(key);
        const value = Number(initial[key]);
        if (Number.isInteger(blockId) && blockId >= 1 && blockId <= MAX_BLOCK_ID) {
          inventory[keyOf(blockId)] = Number.isInteger(value) && value > 0 ? value : 0;
        }
      });
    }
    return inventory;
  }

  function count(inventory, blockId) {
    const value = inventory[keyOf(blockId)];
    return Number.isInteger(value) && value > 0 ? value : 0;
  }

  function add(inventory, blockId, amount) {
    const delta = amount === undefined ? 1 : amount;
    if (!Number.isInteger(blockId) || blockId < 1 || blockId > MAX_BLOCK_ID) {
      return false;
    }
    if (!Number.isInteger(delta) || delta <= 0) {
      return false;
    }
    inventory[keyOf(blockId)] = count(inventory, blockId) + delta;
    return true;
  }

  function consume(inventory, blockId, amount) {
    const delta = amount === undefined ? 1 : amount;
    if (!Number.isInteger(blockId) || blockId < 1 || blockId > MAX_BLOCK_ID) {
      return false;
    }
    if (!Number.isInteger(delta) || delta <= 0) {
      return false;
    }
    const current = count(inventory, blockId);
    if (current < delta) {
      return false;
    }
    inventory[keyOf(blockId)] = current - delta;
    return true;
  }

  function total(inventory) {
    return Object.keys(inventory).reduce(function (sum, key) {
      return sum + count(inventory, Number(key));
    }, 0);
  }

  function toJSON(inventory) {
    const output = {};
    for (let blockId = 1; blockId <= MAX_BLOCK_ID; blockId += 1) {
      output[keyOf(blockId)] = count(inventory, blockId);
    }
    return output;
  }

  function fromJSON(payload) {
    const inventory = createInventory();
    if (payload && typeof payload === "object") {
      Object.keys(payload).forEach(function (key) {
        const blockId = Number(key);
        const value = Number(payload[key]);
        if (Number.isInteger(blockId) && blockId >= 1 && blockId <= MAX_BLOCK_ID) {
          inventory[keyOf(blockId)] = Number.isInteger(value) && value > 0 ? value : 0;
        }
      });
    }
    return inventory;
  }

  function starterInventory() {
    return createInventory(CONFIG.starterInventory);
  }

  return {
    createInventory: createInventory,
    starterInventory: starterInventory,
    count: count,
    add: add,
    consume: consume,
    total: total,
    toJSON: toJSON,
    fromJSON: fromJSON
  };
});
