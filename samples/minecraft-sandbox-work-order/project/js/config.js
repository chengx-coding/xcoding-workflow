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
    glass: 8
  });

  const BLOCK_NAMES = Object.freeze({
    1: "grass",
    2: "dirt",
    3: "stone",
    4: "wood",
    5: "leaves",
    6: "sand",
    7: "planks",
    8: "glass"
  });

  const BLOCK_INFO = Object.freeze({
    1: { name: "Grass", swatch: "#6cc24a", accent: "#a7e36b", solid: true, hardness: 0.35 },
    2: { name: "Dirt", swatch: "#8a5a3b", accent: "#b07b52", solid: true, hardness: 0.4 },
    3: { name: "Stone", swatch: "#77828f", accent: "#a4afba", solid: true, hardness: 0.75 },
    4: { name: "Wood", swatch: "#7a5230", accent: "#a97744", solid: true, hardness: 0.55 },
    5: { name: "Leaves", swatch: "#3f8f45", accent: "#6fc472", solid: true, hardness: 0.25 },
    6: { name: "Sand", swatch: "#d9bf7c", accent: "#f0dda5", solid: true, hardness: 0.3 },
    7: { name: "Planks", swatch: "#b07a45", accent: "#d4a06b", solid: true, hardness: 0.45 },
    8: { name: "Glass", swatch: "#a8dcea", accent: "#e6fbff", solid: true, hardness: 0.2, transparent: true }
  });

  const HOTBAR = Object.freeze([1, 2, 3, 4, 5, 6, 7, 8]);

  return Object.freeze({
    version: "0.1.0",
    tileSize: 40,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 128,
    worldHeight: 64,
    seed: 20261029,
    gravity: 44,
    moveSpeed: 8.6,
    jumpSpeed: 14.2,
    maxFall: 34,
    groundAccel: 64,
    airAccel: 34,
    groundFriction: 52,
    coyoteTime: 0.1,
    jumpBuffer: 0.12,
    reach: 5,
    playerWidth: 0.68,
    playerHeight: 1.78,
    saveKey: "xc-sandbox-terra-v1",
    saveVersion: 1,
    autosaveSeconds: 2.5,
    blocks: BLOCKS,
    blockNames: BLOCK_NAMES,
    blockInfo: BLOCK_INFO,
    hotbar: HOTBAR,
    startingInventory: Object.freeze({ 1: 48, 2: 48, 3: 48, 4: 32, 5: 32, 6: 32, 7: 32, 8: 24 })
  });
});
