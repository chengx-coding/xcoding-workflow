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
    lantern: 9,
    coal: 10,
    crystal: 11,
    bedrock: 12
  });

  const HOTBAR = Object.freeze([
    BLOCKS.grass,
    BLOCKS.dirt,
    BLOCKS.stone,
    BLOCKS.wood,
    BLOCKS.leaves,
    BLOCKS.sand,
    BLOCKS.planks,
    BLOCKS.glass,
    BLOCKS.lantern
  ]);

  return Object.freeze({
    version: "2.0.0",
    tileSize: 32,
    viewWidth: 1280,
    viewHeight: 720,
    worldWidth: 180,
    worldHeight: 72,
    gravity: 34,
    moveSpeed: 7.4,
    sprintMultiplier: 1.32,
    jumpSpeed: 12.8,
    maxFallSpeed: 24,
    reach: 5.6,
    seed: 874213,
    saveKey: "verdant-depths-save-v2",
    saveVersion: 2,
    dayLengthSeconds: 300,
    initialTimeOfDay: 0.43,
    fixedStep: 1 / 120,
    blocks: BLOCKS,
    hotbar: HOTBAR,
    blockNames: Object.freeze({
      0: "Air",
      1: "Meadow grass",
      2: "Rich dirt",
      3: "Slate stone",
      4: "Timber",
      5: "Canopy leaves",
      6: "Warm sand",
      7: "Oak planks",
      8: "Sun glass",
      9: "Glow lantern",
      10: "Coal seam",
      11: "Prism crystal",
      12: "Bedrock"
    }),
    blockShortNames: Object.freeze({
      1: "Grass",
      2: "Dirt",
      3: "Stone",
      4: "Timber",
      5: "Leaves",
      6: "Sand",
      7: "Planks",
      8: "Glass",
      9: "Lantern"
    })
  });
});
