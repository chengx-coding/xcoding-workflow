(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInventory = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function getItemDef(itemId) {
    return CONFIG.items[itemId] || null;
  }

  function stackLimit(itemId) {
    const definition = getItemDef(itemId);
    return definition ? definition.stack : 64;
  }

  function createInventory(size) {
    const capacity = Number.isInteger(size) ? size : CONFIG.inventorySize;
    return {
      size: capacity,
      slots: new Array(capacity).fill(null)
    };
  }

  function cloneInventory(inventory) {
    return {
      size: inventory.size,
      slots: inventory.slots.map(function (slot) {
        return slot ? { id: slot.id, count: slot.count } : null;
      })
    };
  }

  function makeStack(itemId, count) {
    const definition = getItemDef(itemId);
    if (!definition) {
      throw new Error("Unknown item: " + itemId);
    }
    return { id: itemId, count: Math.max(1, Math.min(definition.stack, Math.floor(count || 1))) };
  }

  function countItem(inventory, itemId) {
    let total = 0;
    for (let index = 0; index < inventory.size; index += 1) {
      const slot = inventory.slots[index];
      if (slot && slot.id === itemId) {
        total += slot.count;
      }
    }
    return total;
  }

  function addItem(inventory, itemId, count) {
    const definition = getItemDef(itemId);
    const amount = Math.floor(count || 1);
    if (!definition || amount <= 0) {
      return { added: 0, remaining: amount > 0 ? amount : 0 };
    }
    let remaining = amount;
    const limit = definition.stack;
    for (let index = 0; index < inventory.size && remaining > 0; index += 1) {
      const slot = inventory.slots[index];
      if (slot && slot.id === itemId && slot.count < limit) {
        const moved = Math.min(limit - slot.count, remaining);
        slot.count += moved;
        remaining -= moved;
      }
    }
    for (let index = 0; index < inventory.size && remaining > 0; index += 1) {
      if (!inventory.slots[index]) {
        const moved = Math.min(limit, remaining);
        inventory.slots[index] = { id: itemId, count: moved };
        remaining -= moved;
      }
    }
    return { added: amount - remaining, remaining: remaining };
  }

  function removeItem(inventory, itemId, count) {
    let remaining = Math.floor(count || 1);
    if (remaining <= 0) {
      return true;
    }
    if (countItem(inventory, itemId) < remaining) {
      return false;
    }
    for (let index = 0; index < inventory.size && remaining > 0; index += 1) {
      const slot = inventory.slots[index];
      if (!slot || slot.id !== itemId) {
        continue;
      }
      const taken = Math.min(slot.count, remaining);
      slot.count -= taken;
      remaining -= taken;
      if (slot.count <= 0) {
        inventory.slots[index] = null;
      }
    }
    return remaining === 0;
  }

  function hasItems(inventory, ingredients) {
    if (!Array.isArray(ingredients)) {
      return false;
    }
    for (let index = 0; index < ingredients.length; index += 1) {
      const ingredient = ingredients[index];
      if (countItem(inventory, ingredient.id) < ingredient.count) {
        return false;
      }
    }
    return true;
  }

  function missingIngredients(inventory, ingredients) {
    const missing = [];
    if (!Array.isArray(ingredients)) {
      return missing;
    }
    for (let index = 0; index < ingredients.length; index += 1) {
      const ingredient = ingredients[index];
      const have = countItem(inventory, ingredient.id);
      if (have < ingredient.count) {
        missing.push({ id: ingredient.id, need: ingredient.count, have: have, short: ingredient.count - have });
      }
    }
    return missing;
  }

  function nearbyStations(world, playerX, playerY) {
    const found = { none: true, table: false, furnace: false, counts: { table: 0, furnace: 0 } };
    if (!world) {
      return found;
    }
    const radius = CONFIG.stationReach;
    const centerX = Math.floor(playerX);
    const centerY = Math.floor(playerY - 0.5);
    for (let y = centerY - radius; y <= centerY + radius; y += 1) {
      for (let x = centerX - radius; x <= centerX + radius; x += 1) {
        if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
          continue;
        }
        const block = world.data[y * world.width + x];
        if (block === CONFIG.blocks.craftingTable) {
          found.table = true;
          found.counts.table += 1;
        } else if (block === CONFIG.blocks.furnace) {
          found.furnace = true;
          found.counts.furnace += 1;
        }
      }
    }
    return found;
  }

  function recipeStatus(recipe, inventory, stations) {
    const station = recipe.station || "none";
    const stationOk = station === "none" || !!(stations && stations[station]);
    const missing = missingIngredients(inventory, recipe.ingredients);
    let reason = "";
    if (!stationOk) {
      reason = recipe.station === "furnace" ? "Place a furnace nearby." : "Place a crafting table nearby.";
    } else if (missing.length > 0) {
      const first = missing[0];
      const item = getItemDef(first.id);
      reason = "Need " + first.short + " more " + (item ? item.name : first.id) + ".";
    }
    return {
      ok: stationOk && missing.length === 0,
      stationOk: stationOk,
      missing: missing,
      reason: reason
    };
  }

  function craftRecipe(inventory, recipe, stations) {
    const status = recipeStatus(recipe, inventory, stations);
    if (!status.ok) {
      return { ok: false, reason: status.reason, output: recipe.output, inventory: inventory };
    }
    const working = cloneInventory(inventory);
    for (let index = 0; index < recipe.ingredients.length; index += 1) {
      const ingredient = recipe.ingredients[index];
      if (!removeItem(working, ingredient.id, ingredient.count)) {
        return { ok: false, reason: "Missing ingredients.", output: recipe.output, inventory: inventory };
      }
    }
    const added = addItem(working, recipe.output.id, recipe.output.count);
    if (added.remaining > 0) {
      return { ok: false, reason: "Your inventory is full.", output: recipe.output, inventory: inventory };
    }
    inventory.slots = working.slots;
    return {
      ok: true,
      reason: "",
      output: recipe.output,
      remaining: added.remaining,
      inventory: inventory
    };
  }

  function canCraft(inventory, recipe, stations) {
    return recipeStatus(recipe, inventory, stations).ok;
  }

  function totalItems(inventory) {
    let total = 0;
    for (let index = 0; index < inventory.size; index += 1) {
      if (inventory.slots[index]) {
        total += inventory.slots[index].count;
      }
    }
    return total;
  }

  function firstEmptySlot(inventory) {
    for (let index = 0; index < inventory.size; index += 1) {
      if (!inventory.slots[index]) {
        return index;
      }
    }
    return -1;
  }

  function serializeSlots(inventory) {
    return inventory.slots.map(function (slot) {
      return slot ? [slot.id, slot.count] : null;
    });
  }

  return {
    getItemDef: getItemDef,
    stackLimit: stackLimit,
    createInventory: createInventory,
    cloneInventory: cloneInventory,
    makeStack: makeStack,
    addItem: addItem,
    removeItem: removeItem,
    countItem: countItem,
    hasItems: hasItems,
    missingIngredients: missingIngredients,
    nearbyStations: nearbyStations,
    recipeStatus: recipeStatus,
    craftRecipe: craftRecipe,
    canCraft: canCraft,
    totalItems: totalItems,
    firstEmptySlot: firstEmptySlot,
    serializeSlots: serializeSlots
  };
});
