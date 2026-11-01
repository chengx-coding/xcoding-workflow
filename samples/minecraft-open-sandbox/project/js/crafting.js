(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"));
  } else {
    root.SandboxCrafting = factory(root.SandboxConfig, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INVENTORY) {
  "use strict";

  if (!CONFIG || !INVENTORY) {
    throw new Error("SandboxConfig and SandboxInventory are required before SandboxCrafting");
  }

  function recipeById(id) {
    for (let i = 0; i < CONFIG.recipes.length; i += 1) {
      if (CONFIG.recipes[i].id === id) {
        return CONFIG.recipes[i];
      }
    }
    return null;
  }

  function canCraft(inventory, recipe) {
    if (!recipe) {
      return false;
    }
    const costKeys = Object.keys(recipe.cost);
    for (let i = 0; i < costKeys.length; i += 1) {
      const key = costKeys[i];
      if (!INVENTORY.has(inventory, key, recipe.cost[key])) {
        return false;
      }
    }
    if (recipe.unique) {
      const yieldKeys = Object.keys(recipe.yield);
      for (let i = 0; i < yieldKeys.length; i += 1) {
        if (INVENTORY.count(inventory, yieldKeys[i]) > 0) {
          return false;
        }
      }
    }
    return true;
  }

  function craftCosts(inventory, recipe) {
    return Object.keys(recipe.cost).map(function (key) {
      return {
        item: key,
        need: recipe.cost[key],
        have: INVENTORY.count(inventory, key)
      };
    });
  }

  function craft(inventory, recipe) {
    if (!canCraft(inventory, recipe)) {
      return { ok: false, reason: "cost" };
    }
    const costKeys = Object.keys(recipe.cost);
    for (let i = 0; i < costKeys.length; i += 1) {
      INVENTORY.remove(inventory, costKeys[i], recipe.cost[costKeys[i]]);
    }
    const yieldKeys = Object.keys(recipe.yield);
    for (let i = 0; i < yieldKeys.length; i += 1) {
      INVENTORY.add(inventory, yieldKeys[i], recipe.yield[yieldKeys[i]]);
    }
    return { ok: true, recipe: recipe.id };
  }

  return {
    recipeById: recipeById,
    canCraft: canCraft,
    craftCosts: craftCosts,
    craft: craft
  };
});
