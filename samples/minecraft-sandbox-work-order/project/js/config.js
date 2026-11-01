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
    planks: 7,
    glass: 8,
    brick: 9
  });

  // One entry per block id. `color` is the base fill, `accent` the highlight detail.
  const BLOCK_INFO = Object.freeze({
    1: { id: 1, name: "grass", label: "Grass", color: "#5c9e4a", accent: "#7fc45f", face: "grass" },
    2: { id: 2, name: "dirt", label: "Dirt", color: "#8a5a3b", accent: "#a9744f", face: "speckle" },
    3: { id: 3, name: "stone", label: "Stone", color: "#7c828a", accent: "#9aa1a8", face: "crack" },
    4: { id: 4, name: "wood", label: "Wood", color: "#8d6034", accent: "#b27b45", face: "rings" },
    5: { id: 5, name: "leaves", label: "Leaves", color: "#3f8f45", accent: "#5cb356", face: "leaf" },
    6: { id: 6, name: "sand", label: "Sand", color: "#d7c088", accent: "#ead9a7", face: "speckle" },
    7: { id: 7, name: "planks", label: "Planks", color: "#b07a3f", accent: "#cf9a5b", face: "planks" },
    8: { id: 8, name: "glass", label: "Glass", color: "#9fd7de", accent: "#d4f4f7", face: "glass" },
    9: { id: 9, name: "brick", label: "Brick", color: "#a44a3f", accent: "#c96a5c", face: "brick" }
  });

  // Hotbar order: exactly nine placeable types, keys 1-9.
  const PALETTE = Object.freeze([
    BLOCKS.grass,
    BLOCKS.dirt,
    BLOCKS.stone,
    BLOCKS.wood,
    BLOCKS.leaves,
    BLOCKS.sand,
    BLOCKS.planks,
    BLOCKS.glass,
    BLOCKS.brick
  ]);

  const BLOCK_NAMES = Object.freeze(
    Object.keys(BLOCK_INFO).reduce(function (names, id) {
      names[id] = BLOCK_INFO[id].name;
      return names;
    }, { 0: "air" })
  );

  return Object.freeze({
    version: "0.1.0",
    saveVersion: 2,
    tileSize: 32,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 128,
    worldHeight: 64,
    // World shape: an exact flat spawn plateau keeps the seed tests valid at x=10.
    baseSurfaceRow: 41,
    plateauEndColumn: 24,
    blendEndColumn: 26,
    minSurfaceRow: 33,
    maxSurfaceRow: 46,
    sandMaxSurfaceRow: 38,
    bedrockRows: 2,
    spawnColumn: 12,
    gravity: 55,
    maxFallSpeed: 30,
    moveSpeed: 8.5,
    jumpSpeed: 14.5,
    reach: 5,
    cameraStiffness: 12,
    time: Object.freeze({
      cycleSeconds: 240,
      startFraction: 0.32
    }),
    saveKey: "xc-sandbox-sample-v2",
    // Leaves start empty on purpose so the empty-inventory refusal is reachable.
    starterInventory: Object.freeze({
      1: 16,
      2: 24,
      3: 16,
      4: 8,
      5: 0,
      6: 8,
      7: 12,
      8: 8,
      9: 12
    }),
    starterSelected: 0,
    seed: 1337,
    blocks: BLOCKS,
    blockNames: BLOCK_NAMES,
    blockInfo: BLOCK_INFO,
    palette: PALETTE
  });
});
