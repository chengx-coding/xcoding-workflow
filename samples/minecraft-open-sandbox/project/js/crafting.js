/* Recipe definitions and inventory-safe crafting. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"));
  } else {
    root.SandboxCrafting = factory(root.SandboxConfig, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INV) {
  "use strict";

  const B = CONFIG.blocks;
  const I = CONFIG.itemIds;

  function recipe(id, outputId, outputCount, ingredients, station) {
    return Object.freeze({
      id: id,
      output: Object.freeze({ id: outputId, count: outputCount }),
      ingredients: Object.freeze(ingredients.map(function (entry) {
        return Object.freeze({ id: entry[0], count: entry[1] });
      })),
      station: station || "hand"
    });
  }

  const RECIPES = Object.freeze([
    recipe("planks", B.planks, 4, [[B.wood, 1]]),
    recipe("stick", I.stick, 4, [[B.planks, 2]]),
    recipe("table", B.table, 1, [[B.planks, 4]]),
    recipe("torch", B.torch, 4, [[I.coal, 1], [I.stick, 1]]),
    recipe("furnace", B.furnace, 1, [[B.stone, 8]], "table"),
    recipe("wooden_pickaxe", I.woodenPickaxe, 1, [[B.planks, 3], [I.stick, 2]], "table"),
    recipe("stone_pickaxe", I.stonePickaxe, 1, [[B.stone, 3], [I.stick, 2]], "table"),
    recipe("iron_pickaxe", I.ironPickaxe, 1, [[I.ironIngot, 3], [I.stick, 2]], "table"),
    recipe("wooden_axe", I.woodenAxe, 1, [[B.planks, 3], [I.stick, 2]], "table"),
    recipe("stone_axe", I.stoneAxe, 1, [[B.stone, 3], [I.stick, 2]], "table"),
    recipe("iron_axe", I.ironAxe, 1, [[I.ironIngot, 3], [I.stick, 2]], "table"),
    recipe("wooden_sword", I.woodenSword, 1, [[B.planks, 2], [I.stick, 1]], "table"),
    recipe("stone_sword", I.stoneSword, 1, [[B.stone, 2], [I.stick, 1]], "table"),
    recipe("iron_sword", I.ironSword, 1, [[I.ironIngot, 2], [I.stick, 1]], "table"),
    recipe("ladder", B.ladder, 3, [[I.stick, 7]], "table"),
    recipe("stone_bricks", B.stoneBrick, 4, [[B.stone, 4]], "table")
  ]);

  function getRecipe(id) {
    return RECIPES.find(function (entry) { return entry.id === id; }) || null;
  }

  function missingFor(inventory, entry) {
    return entry.ingredients
      .map(function (ingredient) {
        const have = INV.countItem(inventory, ingredient.id);
        return {
          id: ingredient.id,
          need: ingredient.count,
          have: have,
          missing: Math.max(0, ingredient.count - have)
        };
      })
      .filter(function (part) { return part.missing > 0; });
  }

  function canCraft(inventory, entry, hasTable) {
    if (!entry) {
      return false;
    }
    if (entry.station === "table" && !hasTable) {
      return false;
    }
    return missingFor(inventory, entry).length === 0 && INV.hasSpaceFor(inventory, entry.output.id, entry.output.count);
  }

  function craft(inventory, entry, hasTable) {
    if (!entry) {
      return { ok: false, reason: "Unknown recipe" };
    }
    if (entry.station === "table" && !hasTable) {
      return { ok: false, reason: "Place a crafting table nearby first" };
    }
    const missing = missingFor(inventory, entry);
    if (missing.length > 0) {
      return { ok: false, reason: "Missing ingredients", missing: missing };
    }
    if (!INV.hasSpaceFor(inventory, entry.output.id, entry.output.count)) {
      return { ok: false, reason: "Inventory is full" };
    }
    entry.ingredients.forEach(function (ingredient) {
      INV.removeItem(inventory, ingredient.id, ingredient.count);
    });
    const leftover = INV.addItem(inventory, entry.output.id, entry.output.count);
    return { ok: leftover === 0, reason: leftover ? "Some output did not fit" : "", leftover: leftover };
  }

  function ingredientLabel(entry) {
    return entry.ingredients
      .map(function (ingredient) {
        const def = CONFIG.itemDefs[ingredient.id];
        return ingredient.count + "× " + (def ? def.name : ingredient.id);
      })
      .join(" + ");
  }

  function stationLabel(entry) {
    return entry.station === "table" ? "Crafting table" : "Hand";
  }

  return {
    recipes: RECIPES,
    getRecipe: getRecipe,
    missingFor: missingFor,
    canCraft: canCraft,
    craft: craft,
    ingredientLabel: ingredientLabel,
    stationLabel: stationLabel
  };
});
