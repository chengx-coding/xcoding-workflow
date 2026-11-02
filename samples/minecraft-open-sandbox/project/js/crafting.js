(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"), require("./inventory.js"));
  } else {
    root.SandboxCrafting = factory(root.SandboxConfig, root.SandboxBlocks, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS, INVENTORY) {
  "use strict";

  if (!CONFIG || !BLOCKS || !INVENTORY) {
    throw new Error("SandboxConfig, SandboxBlocks and SandboxInventory are required before SandboxCrafting");
  }

  const B = CONFIG.blocks;

  // `unlockCollected` names an item that must have been picked up at least once
  // before the recipe appears as available. Recipes stay visible while locked so
  // the player can see what to gather next.
  const RECIPES = [
    {
      id: "planks", name: "Planks", category: "Basics",
      out: { id: B.planks, count: 4 },
      cost: [{ id: B.wood, count: 1 }],
      unlockCollected: [], hint: "Chop a tree for wood."
    },
    {
      id: "sticks", name: "Sticks", category: "Basics",
      out: { id: 100, count: 4 },
      cost: [{ id: B.planks, count: 2 }],
      unlockCollected: [B.planks], hint: "Craft planks first."
    },
    {
      id: "wooden_pickaxe", name: "Wooden pickaxe", category: "Tools",
      out: { id: 110, count: 1 },
      cost: [{ id: B.planks, count: 3 }, { id: 100, count: 2 }],
      unlockCollected: [B.planks], hint: "Planks and sticks make your first pickaxe."
    },
    {
      id: "wooden_axe", name: "Wooden axe", category: "Tools",
      out: { id: 120, count: 1 },
      cost: [{ id: B.planks, count: 3 }, { id: 100, count: 2 }],
      unlockCollected: [B.planks], hint: "Cuts wood faster."
    },
    {
      id: "wooden_shovel", name: "Wooden shovel", category: "Tools",
      out: { id: 130, count: 1 },
      cost: [{ id: B.planks, count: 1 }, { id: 100, count: 2 }],
      unlockCollected: [B.planks], hint: "Digs soil and sand faster."
    },
    {
      id: "torch", name: "Torch", category: "Light",
      out: { id: B.torch, count: 4 },
      cost: [{ id: 101, count: 1 }, { id: 100, count: 1 }],
      unlockCollected: [101], hint: "Mine coal ore to unlock torches."
    },
    {
      id: "glass", name: "Glass", category: "Building",
      out: { id: B.glass, count: 2 },
      cost: [{ id: B.sand, count: 1 }, { id: 101, count: 1 }],
      unlockCollected: [101], hint: "Sand plus coal makes glass."
    },
    {
      id: "stone_pickaxe", name: "Stone pickaxe", category: "Tools",
      out: { id: 111, count: 1 },
      cost: [{ id: B.cobblestone, count: 3 }, { id: 100, count: 2 }],
      unlockCollected: [B.cobblestone], hint: "Mine stone with a wooden pickaxe."
    },
    {
      id: "stone_axe", name: "Stone axe", category: "Tools",
      out: { id: 121, count: 1 },
      cost: [{ id: B.cobblestone, count: 3 }, { id: 100, count: 2 }],
      unlockCollected: [B.cobblestone], hint: "Mine stone with a wooden pickaxe."
    },
    {
      id: "stone_shovel", name: "Stone shovel", category: "Tools",
      out: { id: 131, count: 1 },
      cost: [{ id: B.cobblestone, count: 1 }, { id: 100, count: 2 }],
      unlockCollected: [B.cobblestone], hint: "Mine stone with a wooden pickaxe."
    },
    {
      id: "iron_pickaxe", name: "Iron pickaxe", category: "Tools",
      out: { id: 112, count: 1 },
      cost: [{ id: 102, count: 3 }, { id: 100, count: 2 }],
      unlockCollected: [102], hint: "Iron needs a stone pickaxe to harvest."
    }
  ];

  const RECIPE_BY_ID = Object.create(null);
  RECIPES.forEach(function (recipe) {
    RECIPE_BY_ID[recipe.id] = recipe;
  });

  function unlockState(recipe, progress) {
    const collected = (progress && progress.collected) || {};
    for (let index = 0; index < recipe.unlockCollected.length; index += 1) {
      if (!collected[recipe.unlockCollected[index]]) {
        return false;
      }
    }
    return true;
  }

  function missingFor(inventory, recipe) {
    const missing = [];
    recipe.cost.forEach(function (part) {
      const have = INVENTORY.count(inventory, part.id);
      if (have < part.count) {
        missing.push({ id: part.id, need: part.count, have: have });
      }
    });
    return missing;
  }

  function canCraft(inventory, recipe, progress) {
    if (!unlockState(recipe, progress)) {
      return { ok: false, reason: "locked", missing: recipe.cost.slice() };
    }
    const missing = missingFor(inventory, recipe);
    return { ok: missing.length === 0, reason: missing.length === 0 ? null : "missing", missing: missing };
  }

  function craft(inventory, recipe, progress) {
    const check = canCraft(inventory, recipe, progress);
    if (!check.ok) {
      return { ok: false, reason: check.reason, missing: check.missing };
    }
    recipe.cost.forEach(function (part) {
      INVENTORY.remove(inventory, part.id, part.count);
    });
    INVENTORY.add(inventory, recipe.out.id, recipe.out.count);
    return {
      ok: true,
      recipe: recipe,
      out: { id: recipe.out.id, count: recipe.out.count },
      name: BLOCKS.nameOf(recipe.out.id)
    };
  }

  function visible(inventory, progress) {
    return RECIPES.map(function (recipe) {
      const check = canCraft(inventory, recipe, progress);
      return {
        recipe: recipe,
        unlocked: check.reason !== "locked",
        canCraft: check.ok,
        missing: check.missing || []
      };
    });
  }

  function recipeById(id) {
    return RECIPE_BY_ID[id] || null;
  }

  return {
    RECIPES: RECIPES,
    recipeById: recipeById,
    unlockState: unlockState,
    canCraft: canCraft,
    craft: craft,
    visible: visible,
    missingFor: missingFor
  };
});
