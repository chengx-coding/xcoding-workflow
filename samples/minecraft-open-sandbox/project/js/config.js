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
    cobblestone: 6,
    sand: 7,
    planks: 8,
    coalOre: 9,
    ironOre: 10,
    torch: 11,
    craftingTable: 12,
    furnace: 13,
    glass: 14,
    stoneBricks: 15,
    flower: 16,
    tallGrass: 17
  });

  const BLOCK_DEFS = [
    { id: 0, key: "air", name: "Air", solid: false, transparent: true, hardness: 0, tier: 0, tool: null, drop: null, light: 0 },
    { id: 1, key: "grass", name: "Grass Block", solid: true, transparent: false, hardness: 0.35, tier: 0, tool: null, drop: "dirt", light: 0 },
    { id: 2, key: "dirt", name: "Dirt", solid: true, transparent: false, hardness: 0.35, tier: 0, tool: null, drop: "dirt", light: 0 },
    { id: 3, key: "stone", name: "Stone", solid: true, transparent: false, hardness: 1.5, tier: 1, tool: "pickaxe", drop: "cobblestone", light: 0 },
    { id: 4, key: "wood", name: "Oak Log", solid: true, transparent: false, hardness: 0.9, tier: 0, tool: null, drop: "wood", light: 0 },
    { id: 5, key: "leaves", name: "Oak Leaves", solid: true, transparent: true, hardness: 0.2, tier: 0, tool: null, drop: "leaves", light: 0 },
    { id: 6, key: "cobblestone", name: "Cobblestone", solid: true, transparent: false, hardness: 1.6, tier: 1, tool: "pickaxe", drop: "cobblestone", light: 0 },
    { id: 7, key: "sand", name: "Sand", solid: true, transparent: false, hardness: 0.3, tier: 0, tool: null, drop: "sand", light: 0 },
    { id: 8, key: "planks", name: "Oak Planks", solid: true, transparent: false, hardness: 0.8, tier: 0, tool: null, drop: "planks", light: 0 },
    { id: 9, key: "coalOre", name: "Coal Ore", solid: true, transparent: false, hardness: 1.8, tier: 1, tool: "pickaxe", drop: "coal", light: 0 },
    { id: 10, key: "ironOre", name: "Iron Ore", solid: true, transparent: false, hardness: 2.4, tier: 2, tool: "pickaxe", drop: "raw_iron", light: 0 },
    { id: 11, key: "torch", name: "Torch", solid: false, transparent: true, hardness: 0.05, tier: 0, tool: null, drop: "torch", light: 14 },
    { id: 12, key: "craftingTable", name: "Crafting Table", solid: true, transparent: false, hardness: 0.9, tier: 0, tool: null, drop: "crafting_table", light: 0 },
    { id: 13, key: "furnace", name: "Furnace", solid: true, transparent: false, hardness: 1.8, tier: 1, tool: "pickaxe", drop: "furnace", light: 0 },
    { id: 14, key: "glass", name: "Glass", solid: true, transparent: true, hardness: 0.4, tier: 0, tool: null, drop: "glass", light: 0 },
    { id: 15, key: "stoneBricks", name: "Stone Bricks", solid: true, transparent: false, hardness: 1.7, tier: 1, tool: "pickaxe", drop: "stone_bricks", light: 0 },
    { id: 16, key: "flower", name: "Torchflower", solid: false, transparent: true, hardness: 0.05, tier: 0, tool: null, drop: "flower", light: 0 },
    { id: 17, key: "tallGrass", name: "Tall Grass", solid: false, transparent: true, hardness: 0.05, tier: 0, tool: null, drop: "tall_grass", light: 0 }
  ];

  const blocksById = [];
  const blocksByKey = Object.create(null);
  BLOCK_DEFS.forEach(function (definition) {
    blocksById[definition.id] = Object.freeze(definition);
    blocksByKey[definition.key] = Object.freeze(definition);
  });

  const ITEM_DEFS = {
    dirt: { id: "dirt", name: "Dirt", stack: 64, type: "block", blockId: BLOCKS.dirt, description: "Soft earth. Good for filling and gardens." },
    cobblestone: { id: "cobblestone", name: "Cobblestone", stack: 64, type: "block", blockId: BLOCKS.cobblestone, description: "Rugged stone for tools and walls." },
    sand: { id: "sand", name: "Sand", stack: 64, type: "block", blockId: BLOCKS.sand, description: "Warm grains. Smelts into glass." },
    wood: { id: "wood", name: "Oak Log", stack: 64, type: "block", blockId: BLOCKS.wood, description: "The beginning of every build." },
    leaves: { id: "leaves", name: "Oak Leaves", stack: 64, type: "block", blockId: BLOCKS.leaves, description: "A rustling block of green." },
    planks: { id: "planks", name: "Oak Planks", stack: 64, type: "block", blockId: BLOCKS.planks, description: "Clean boards for building and crafting." },
    torch: { id: "torch", name: "Torch", stack: 64, type: "block", blockId: BLOCKS.torch, description: "A small warm light. Place it on solid ground." },
    crafting_table: { id: "crafting_table", name: "Crafting Table", stack: 64, type: "block", blockId: BLOCKS.craftingTable, description: "Place it nearby to unlock tool recipes." },
    furnace: { id: "furnace", name: "Furnace", stack: 64, type: "block", blockId: BLOCKS.furnace, description: "Place it nearby to smelt iron and glass." },
    glass: { id: "glass", name: "Glass", stack: 64, type: "block", blockId: BLOCKS.glass, description: "Clear panes that let the light through." },
    stone_bricks: { id: "stone_bricks", name: "Stone Bricks", stack: 64, type: "block", blockId: BLOCKS.stoneBricks, description: "Cut stone for tidy walls." },
    flower: { id: "flower", name: "Torchflower", stack: 64, type: "block", blockId: BLOCKS.flower, description: "A tiny ember-coloured bloom." },
    tall_grass: { id: "tall_grass", name: "Tall Grass", stack: 64, type: "block", blockId: BLOCKS.tallGrass, description: "A tuft of meadow green." },
    stick: { id: "stick", name: "Stick", stack: 64, type: "material", description: "A handle waiting for a head." },
    coal: { id: "coal", name: "Coal", stack: 64, type: "material", description: "Black fuel for torches and furnaces." },
    raw_iron: { id: "raw_iron", name: "Raw Iron", stack: 64, type: "material", description: "Rocky ore. Smelt it in a furnace." },
    iron_ingot: { id: "iron_ingot", name: "Iron Ingot", stack: 64, type: "material", description: "A bright bar for the strongest pickaxe." },
    wood_pickaxe: { id: "wood_pickaxe", name: "Wooden Pickaxe", stack: 1, type: "tool", tool: { type: "pickaxe", tier: 1, speed: 2.2 }, description: "Tier 1 pickaxe. Mines stone and coal." },
    stone_pickaxe: { id: "stone_pickaxe", name: "Stone Pickaxe", stack: 1, type: "tool", tool: { type: "pickaxe", tier: 2, speed: 3.4 }, description: "Tier 2 pickaxe. Mines iron ore." },
    iron_pickaxe: { id: "iron_pickaxe", name: "Iron Pickaxe", stack: 1, type: "tool", tool: { type: "pickaxe", tier: 3, speed: 4.8 }, description: "Tier 3 pickaxe. The fastest way through stone." }
  };

  const ITEMS = Object.freeze(ITEM_DEFS);
  const itemList = Object.freeze(Object.keys(ITEM_DEFS).map(function (key) { return ITEM_DEFS[key]; }));

  const RECIPES = Object.freeze([
    Object.freeze({ id: "planks", name: "Oak Planks", station: "none", output: { id: "planks", count: 4 }, ingredients: [{ id: "wood", count: 1 }], order: 10, note: "Saw a log into boards." }),
    Object.freeze({ id: "sticks", name: "Sticks", station: "none", output: { id: "stick", count: 4 }, ingredients: [{ id: "planks", count: 2 }], order: 20, note: "Split boards into handles." }),
    Object.freeze({ id: "crafting_table", name: "Crafting Table", station: "none", output: { id: "crafting_table", count: 1 }, ingredients: [{ id: "planks", count: 4 }], order: 30, note: "Place it to unlock bigger recipes." }),
    Object.freeze({ id: "torches", name: "Torches", station: "none", output: { id: "torch", count: 4 }, ingredients: [{ id: "coal", count: 1 }, { id: "stick", count: 1 }], order: 40, note: "Push back the dark." }),
    Object.freeze({ id: "wood_pickaxe", name: "Wooden Pickaxe", station: "table", output: { id: "wood_pickaxe", count: 1 }, ingredients: [{ id: "planks", count: 3 }, { id: "stick", count: 2 }], order: 50, note: "Your first real mining tool." }),
    Object.freeze({ id: "furnace", name: "Furnace", station: "table", output: { id: "furnace", count: 1 }, ingredients: [{ id: "cobblestone", count: 8 }], order: 60, note: "A stone oven for smelting." }),
    Object.freeze({ id: "stone_pickaxe", name: "Stone Pickaxe", station: "table", output: { id: "stone_pickaxe", count: 1 }, ingredients: [{ id: "cobblestone", count: 3 }, { id: "stick", count: 2 }], order: 70, note: "Strong enough for iron ore." }),
    Object.freeze({ id: "stone_bricks", name: "Stone Bricks", station: "table", output: { id: "stone_bricks", count: 4 }, ingredients: [{ id: "cobblestone", count: 4 }], order: 80, note: "Dress up a build." }),
    Object.freeze({ id: "iron_ingot", name: "Iron Ingot", station: "furnace", output: { id: "iron_ingot", count: 1 }, ingredients: [{ id: "raw_iron", count: 1 }, { id: "coal", count: 1 }], order: 90, note: "Smelt raw ore into a bar." }),
    Object.freeze({ id: "glass", name: "Glass", station: "furnace", output: { id: "glass", count: 1 }, ingredients: [{ id: "sand", count: 1 }, { id: "coal", count: 1 }], order: 100, note: "Melt sand into clear panes." }),
    Object.freeze({ id: "iron_pickaxe", name: "Iron Pickaxe", station: "table", output: { id: "iron_pickaxe", count: 1 }, ingredients: [{ id: "iron_ingot", count: 3 }, { id: "stick", count: 2 }], order: 110, note: "The fastest pickaxe in the pocket." })
  ]);

  const STATIONS = Object.freeze({
    none: Object.freeze({ key: "none", label: "Anywhere", icon: "hand" }),
    table: Object.freeze({ key: "table", label: "Crafting Table", icon: "table" }),
    furnace: Object.freeze({ key: "furnace", label: "Furnace", icon: "furnace" })
  });

  const CONFIG = {
    version: "1.0.0",
    saveVersion: 1,
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 320,
    worldHeight: 144,
    baseGroundRatio: 0.65,
    gravity: 34,
    moveSpeed: 5.4,
    sprintSpeed: 8.2,
    jumpSpeed: 11.2,
    reach: 5.5,
    playerWidth: 0.64,
    playerHeight: 1.75,
    maxHealth: 10,
    fallSafeDistance: 4.25,
    saveKey: "emberblock.save.v1",
    storageLabel: "Emberblock",
    dayLengthSeconds: 420,
    startTimeOfDay: 0.31,
    autosaveSeconds: 12,
    seed: 20261104,
    blocks: BLOCKS,
    blockDefs: Object.freeze(blocksById),
    blocksByKey: Object.freeze(blocksByKey),
    blockNames: Object.freeze({
      1: "grass",
      2: "dirt",
      3: "stone",
      4: "wood",
      5: "leaves",
      6: "cobblestone",
      7: "sand",
      8: "planks",
      9: "coal ore",
      10: "iron ore",
      11: "torch",
      12: "crafting table",
      13: "furnace",
      14: "glass",
      15: "stone bricks",
      16: "torchflower",
      17: "tall grass"
    }),
    items: ITEMS,
    itemList: itemList,
    recipes: RECIPES,
    stations: STATIONS,
    inventorySize: 36,
    hotbarSize: 9,
    stationReach: 6
  };

  return Object.freeze(CONFIG);
});
