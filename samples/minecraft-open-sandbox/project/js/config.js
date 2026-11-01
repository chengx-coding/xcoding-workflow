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
    coal: 8,
    crystal: 9,
    torch: 10,
    planks: 11
  });

  const ITEMS = Object.freeze({
    dirt: "dirt",
    stone: "stone",
    wood: "wood",
    leaves: "leaves",
    sand: "sand",
    coal: "coal",
    crystal: "crystal",
    torch: "torch",
    planks: "planks",
    stick: "stick",
    wood_pickaxe: "wood_pickaxe",
    stone_pickaxe: "stone_pickaxe"
  });

  // Block behaviour. `hardness` is seconds by hand (or with the required tool);
  // `tool`/`tier` gate mining, `drop` is the inventory item produced.
  const blockDefs = {
    0: {
      name: "Air",
      solid: false,
      liquid: false,
      hardness: 0,
      tool: null,
      tier: 0,
      drop: null,
      light: 0
    },
    1: {
      name: "Grass",
      solid: true,
      liquid: false,
      hardness: 0.28,
      tool: null,
      tier: 0,
      drop: ITEMS.dirt,
      light: 0
    },
    2: {
      name: "Dirt",
      solid: true,
      liquid: false,
      hardness: 0.32,
      tool: null,
      tier: 0,
      drop: ITEMS.dirt,
      light: 0
    },
    3: {
      name: "Stone",
      solid: true,
      liquid: false,
      hardness: 0.9,
      tool: "pickaxe",
      tier: 1,
      drop: ITEMS.stone,
      light: 0
    },
    4: {
      name: "Wood",
      solid: true,
      liquid: false,
      hardness: 0.55,
      tool: null,
      tier: 0,
      drop: ITEMS.wood,
      light: 0
    },
    5: {
      name: "Leaves",
      solid: true,
      liquid: false,
      hardness: 0.15,
      tool: null,
      tier: 0,
      drop: ITEMS.leaves,
      light: 0
    },
    6: {
      name: "Sand",
      solid: true,
      liquid: false,
      hardness: 0.3,
      tool: null,
      tier: 0,
      drop: ITEMS.sand,
      light: 0
    },
    7: {
      name: "Water",
      solid: false,
      liquid: true,
      hardness: Infinity,
      tool: null,
      tier: 0,
      drop: null,
      light: 0
    },
    8: {
      name: "Coal ore",
      solid: true,
      liquid: false,
      hardness: 1.0,
      tool: "pickaxe",
      tier: 1,
      drop: ITEMS.coal,
      light: 0
    },
    9: {
      name: "Crystal ore",
      solid: true,
      liquid: false,
      hardness: 1.4,
      tool: "pickaxe",
      tier: 2,
      drop: ITEMS.crystal,
      light: 12
    },
    10: {
      name: "Torch",
      solid: false,
      liquid: false,
      hardness: 0.05,
      tool: null,
      tier: 0,
      drop: ITEMS.torch,
      light: 14
    },
    11: {
      name: "Planks",
      solid: true,
      liquid: false,
      hardness: 0.45,
      tool: null,
      tier: 0,
      drop: ITEMS.planks,
      light: 0
    }
  };
  Object.keys(blockDefs).forEach(function (key) {
    Object.freeze(blockDefs[key]);
  });

  const tools = {
    wood_pickaxe: Object.freeze({ id: "wood_pickaxe", name: "Wooden pickaxe", tier: 1, speed: 2.4 }),
    stone_pickaxe: Object.freeze({ id: "stone_pickaxe", name: "Stone pickaxe", tier: 2, speed: 4 })
  };

  const recipes = [
    Object.freeze({
      id: "planks",
      name: "Planks",
      cost: Object.freeze({ wood: 1 }),
      yield: Object.freeze({ planks: 4 }),
      hint: "1 wood"
    }),
    Object.freeze({
      id: "sticks",
      name: "Sticks",
      cost: Object.freeze({ planks: 2 }),
      yield: Object.freeze({ stick: 4 }),
      hint: "2 planks"
    }),
    Object.freeze({
      id: "torches",
      name: "Torches",
      cost: Object.freeze({ stick: 1, coal: 1 }),
      yield: Object.freeze({ torch: 4 }),
      hint: "1 stick + 1 coal"
    }),
    Object.freeze({
      id: "wood-pickaxe",
      name: "Wooden pickaxe",
      cost: Object.freeze({ planks: 3, stick: 2 }),
      yield: Object.freeze({ wood_pickaxe: 1 }),
      unique: true,
      hint: "3 planks + 2 sticks"
    }),
    Object.freeze({
      id: "stone-pickaxe",
      name: "Stone pickaxe",
      cost: Object.freeze({ stone: 3, stick: 2 }),
      yield: Object.freeze({ stone_pickaxe: 1 }),
      unique: true,
      hint: "3 stone + 2 sticks"
    })
  ];

  // Placeable hotbar palette. Order is the 1..8 key order.
  const hotbar = Object.freeze([
    ITEMS.dirt,
    ITEMS.stone,
    ITEMS.wood,
    ITEMS.planks,
    ITEMS.sand,
    ITEMS.leaves,
    ITEMS.torch,
    ITEMS.crystal
  ]);

  const placeable = Object.freeze({
    dirt: BLOCKS.dirt,
    stone: BLOCKS.stone,
    wood: BLOCKS.wood,
    planks: BLOCKS.planks,
    sand: BLOCKS.sand,
    leaves: BLOCKS.leaves,
    torch: BLOCKS.torch,
    crystal: BLOCKS.crystal
  });

  const itemNames = Object.freeze({
    dirt: "Dirt",
    stone: "Stone",
    wood: "Wood",
    planks: "Planks",
    sand: "Sand",
    leaves: "Leaves",
    torch: "Torch",
    crystal: "Crystal",
    coal: "Coal",
    stick: "Stick",
    wood_pickaxe: "Wooden pickaxe",
    stone_pickaxe: "Stone pickaxe"
  });

  const palette = Object.freeze({
    1: Object.freeze({ base: "#6aa348", light: "#8ac765", dark: "#4f7d35" }),
    2: Object.freeze({ base: "#966444", light: "#b47f57", dark: "#714832" }),
    3: Object.freeze({ base: "#879199", light: "#a6b0b8", dark: "#646c73" }),
    4: Object.freeze({ base: "#86603a", light: "#a8794b", dark: "#5f4427" }),
    5: Object.freeze({ base: "#4a8f3d", light: "#67b455", dark: "#356b2c" }),
    6: Object.freeze({ base: "#e0cb86", light: "#f0dfa4", dark: "#c4ad66" }),
    7: Object.freeze({ base: "#3579b5", light: "#5aa4de", dark: "#245688" }),
    8: Object.freeze({ base: "#737b83", light: "#959ea6", dark: "#3f454b" }),
    9: Object.freeze({ base: "#66aec4", light: "#a8f0ff", dark: "#3c7488" }),
    10: Object.freeze({ base: "#86603a", light: "#ffc25e", dark: "#52351b" }),
    11: Object.freeze({ base: "#c08d4e", light: "#d9a967", dark: "#936a37" })
  });

  const controls = Object.freeze([
    Object.freeze({ keys: "A / D or Left / Right", action: "Move" }),
    Object.freeze({ keys: "W, Space or Up", action: "Jump (swim up in water)" }),
    Object.freeze({ keys: "Left mouse (hold)", action: "Mine the highlighted block" }),
    Object.freeze({ keys: "Right mouse", action: "Place the selected block" }),
    Object.freeze({ keys: "1 - 8", action: "Select a hotbar slot" }),
    Object.freeze({ keys: "Mouse wheel", action: "Cycle hotbar slots" }),
    Object.freeze({ keys: "E", action: "Crafting and inventory" }),
    Object.freeze({ keys: "H or F1", action: "Help and controls" }),
    Object.freeze({ keys: "Esc", action: "Pause menu" }),
    Object.freeze({ keys: "M", action: "Mute or unmute audio" })
  ]);

  return Object.freeze({
    version: "1.0.0",
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 192,
    worldHeight: 96,
    seed: 20261101,
    gravity: 34,
    moveSpeed: 7.2,
    jumpSpeed: 11.5,
    maxFallSpeed: 30,
    reach: 5.5,
    autosaveSeconds: 8,
    dayLengthSeconds: 240,
    saveKey: "small-minecraft-save-v1",
    saveVersion: 1,
    lightMax: 15,
    skyDay: 15,
    skyNight: 4,
    blocks: BLOCKS,
    items: ITEMS,
    blockDefs: Object.freeze(blockDefs),
    tools: Object.freeze(tools),
    recipes: Object.freeze(recipes),
    hotbar: hotbar,
    placeable: placeable,
    itemNames: itemNames,
    palette: palette,
    controls: controls,
    blockNames: Object.freeze({
      1: "Grass",
      2: "Dirt",
      3: "Stone",
      4: "Wood",
      5: "Leaves",
      6: "Sand",
      7: "Water",
      8: "Coal ore",
      9: "Crystal ore",
      10: "Torch",
      11: "Planks"
    })
  });
});
