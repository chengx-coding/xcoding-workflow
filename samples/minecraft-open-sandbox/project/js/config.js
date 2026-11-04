/*
 * Blockfall — shared configuration.
 * Plain browser globals for the page, CommonJS for the Node tests.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxConfig = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const BLOCKS = Object.freeze({
    air: 0,
    grass: 1,
    dirt: 2,
    stone: 3,
    wood: 4,
    leaves: 5,
    sand: 6,
    water: 7,
    coalOre: 8,
    ironOre: 9,
    planks: 10,
    table: 11,
    furnace: 12,
    torch: 13,
    glass: 14,
    ladder: 15,
    stoneBrick: 16,
    flower: 17,
    tallGrass: 18
  });

  // A block definition drives worldgen, collision, rendering and mining.
  const BLOCK_DEFS = Object.freeze({
    0: { name: "Air", solid: false, opaque: false, liquid: false, replaceable: true, decor: false, hardness: 0 },
    1: { name: "Grass Block", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 0.7, tool: "shovel", drop: 2, place: 1 },
    2: { name: "Dirt", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 0.6, tool: "shovel", drop: 2, place: 2 },
    3: { name: "Stone", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 2.2, tool: "pickaxe", drop: 3, place: 3 },
    4: { name: "Oak Log", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 1.8, tool: "axe", drop: 4, place: 4 },
    5: { name: "Oak Leaves", solid: true, opaque: false, liquid: false, replaceable: false, decor: false, hardness: 0.25, tool: "axe", drop: -1, place: 5 },
    6: { name: "Sand", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 0.55, tool: "shovel", drop: 6, place: 6 },
    7: { name: "Water", solid: false, opaque: false, liquid: true, replaceable: true, decor: false, hardness: Infinity },
    8: { name: "Coal Ore", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 3.0, tool: "pickaxe", drop: 101, place: 8 },
    9: { name: "Iron Ore", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 3.6, tool: "pickaxe", drop: 102, place: 9 },
    10: { name: "Oak Planks", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 1.5, tool: "axe", drop: 10, place: 10 },
    11: { name: "Crafting Table", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 1.8, tool: "axe", drop: 11, place: 11 },
    12: { name: "Furnace", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 2.8, tool: "pickaxe", drop: 12, place: 12 },
    13: { name: "Torch", solid: false, opaque: false, liquid: false, replaceable: true, decor: true, hardness: 0.05, light: 14, drop: 13, place: 13 },
    14: { name: "Glass", solid: true, opaque: false, liquid: false, replaceable: false, decor: false, hardness: 0.4, tool: "pickaxe", drop: -1, place: 14 },
    15: { name: "Ladder", solid: false, opaque: false, liquid: false, replaceable: true, decor: true, hardness: 0.35, tool: "axe", drop: 15, place: 15, climb: true },
    16: { name: "Stone Bricks", solid: true, opaque: true, liquid: false, replaceable: false, decor: false, hardness: 2.6, tool: "pickaxe", drop: 16, place: 16 },
    17: { name: "Poppy", solid: false, opaque: false, liquid: false, replaceable: true, decor: true, hardness: 0.05, drop: 17, place: 17 },
    18: { name: "Tall Grass", solid: false, opaque: false, liquid: false, replaceable: true, decor: true, hardness: 0.05, drop: -1, place: 18 }
  });

  const ITEM_IDS = Object.freeze({
    stick: 100,
    coal: 101,
    rawIron: 102,
    ironIngot: 103,
    apple: 104,
    rawPork: 105,
    cookedPork: 106,
    slimeball: 107,
    rottenFlesh: 108,
    woodenPickaxe: 110,
    stonePickaxe: 111,
    ironPickaxe: 112,
    woodenAxe: 113,
    stoneAxe: 114,
    ironAxe: 115,
    woodenSword: 116,
    stoneSword: 117,
    ironSword: 118
  });

  const TOOL_TIER = Object.freeze({ wooden: 1, stone: 2, iron: 3 });

  function tool(name, type, tier, speed, damage) {
    return { name: name, kind: "tool", tool: type, tier: tier, speed: speed, damage: damage, maxStack: 1 };
  }

  const ITEM_DEFS = ({
    100: { name: "Stick", kind: "material", maxStack: 64 },
    101: { name: "Coal", kind: "material", maxStack: 64, fuel: 8 },
    102: { name: "Raw Iron", kind: "material", maxStack: 64 },
    103: { name: "Iron Ingot", kind: "material", maxStack: 64 },
    104: { name: "Apple", kind: "food", maxStack: 64, food: 4 },
    105: { name: "Raw Porkchop", kind: "food", maxStack: 64, food: 2 },
    106: { name: "Cooked Porkchop", kind: "food", maxStack: 64, food: 8 },
    107: { name: "Slimeball", kind: "material", maxStack: 64 },
    108: { name: "Rotten Flesh", kind: "food", maxStack: 64, food: 1 },
    110: tool("Wooden Pickaxe", "pickaxe", 1, 3.0, 2),
    111: tool("Stone Pickaxe", "pickaxe", 2, 4.5, 3),
    112: tool("Iron Pickaxe", "pickaxe", 3, 6.0, 4),
    113: tool("Wooden Axe", "axe", 1, 3.0, 3),
    114: tool("Stone Axe", "axe", 2, 4.5, 4),
    115: tool("Iron Axe", "axe", 3, 6.0, 5),
    116: tool("Wooden Sword", "sword", 1, 1.8, 4),
    117: tool("Stone Sword", "sword", 2, 2.2, 5),
    118: tool("Iron Sword", "sword", 3, 2.6, 6)
  });

  // Every block is also an item with the same numeric id.
  Object.keys(BLOCK_DEFS).forEach(function (key) {
    const id = Number(key);
    if (id === 0 || ITEM_DEFS[id]) {
      return;
    }
    const def = BLOCK_DEFS[id];
    ITEM_DEFS[id] = {
      name: def.name,
      kind: "block",
      maxStack: 64,
      place: id
    };
    if (id === 13) {
      ITEM_DEFS[id].light = 14;
    }
  });

  const config = {
    version: "1.0.0",
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 320,
    worldHeight: 96,
    gravity: 38,
    maxFallSpeed: 30,
    moveSpeed: 6.2,
    sprintSpeed: 9.0,
    jumpSpeed: 13.2,
    swimSpeed: 3.6,
    waterBuoyancy: 16,
    reach: 5.2,
    attackReach: 3.6,
    baseMiningSpeed: 1.0,
    dayLength: 600,
    saveKey: "blockfall-save-v1",
    saveVersion: 1,
    seed: 1337,
    seaLevel: 66,
    spawnPlateau: 14,
    blocks: BLOCKS,
    blockDefs: BLOCK_DEFS,
    itemDefs: ITEM_DEFS,
    itemIds: ITEM_IDS,
    toolTier: TOOL_TIER,
    blockNames: Object.freeze(
      Object.keys(BLOCK_DEFS).reduce(function (names, key) {
        names[key] = BLOCK_DEFS[key].name;
        return names;
      }, {})
    )
  };

  Object.freeze(ITEM_DEFS);
  return Object.freeze(config);
});
