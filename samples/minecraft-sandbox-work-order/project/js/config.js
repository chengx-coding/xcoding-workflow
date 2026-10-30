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
    cobblestone: 8,
    glass: 9
  });

  // The palette is ordered from natural terrain to crafted blocks. Slot order is
  // user-visible: the eighth slot (index 7) is cobblestone and the ninth is glass.
  const HOTBAR = Object.freeze([
    BLOCKS.grass,
    BLOCKS.dirt,
    BLOCKS.stone,
    BLOCKS.sand,
    BLOCKS.wood,
    BLOCKS.leaves,
    BLOCKS.planks,
    BLOCKS.cobblestone,
    BLOCKS.glass
  ]);

  const STARTER_STOCK = Object.freeze({
    [BLOCKS.grass]: 24,
    [BLOCKS.dirt]: 32,
    [BLOCKS.stone]: 24,
    [BLOCKS.sand]: 16,
    [BLOCKS.wood]: 16,
    [BLOCKS.leaves]: 12,
    [BLOCKS.planks]: 20,
    [BLOCKS.cobblestone]: 16,
    [BLOCKS.glass]: 8
  });

  // Seconds of holding the mouse button to break one block, per material.
  const HARDNESS = Object.freeze({
    [BLOCKS.grass]: 0.4,
    [BLOCKS.dirt]: 0.4,
    [BLOCKS.sand]: 0.35,
    [BLOCKS.stone]: 0.85,
    [BLOCKS.wood]: 0.7,
    [BLOCKS.leaves]: 0.25,
    [BLOCKS.planks]: 0.55,
    [BLOCKS.cobblestone]: 0.95,
    [BLOCKS.glass]: 0.3
  });

  return Object.freeze({
    version: "0.1.0",
    seed: 20261030,
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 128,
    worldHeight: 64,
    gravity: 26,
    maxFallSpeed: 26,
    moveSpeed: 6.4,
    jumpSpeed: 11.2,
    reach: 5,
    dayCycleSeconds: 240,
    startTimeOfDay: 0.18,
    saveKey: "xc-sandbox-sample-v1",
    settingsKey: "xc-sandbox-sample-settings-v1",
    saveVersion: 2,
    maxStack: 999,
    blocks: BLOCKS,
    hotbar: HOTBAR,
    starterStock: STARTER_STOCK,
    hardness: HARDNESS,
    blockNames: Object.freeze({
      1: "Grass",
      2: "Dirt",
      3: "Stone",
      4: "Wood",
      5: "Leaves",
      6: "Sand",
      7: "Planks",
      8: "Cobblestone",
      9: "Glass"
    })
  });
});
