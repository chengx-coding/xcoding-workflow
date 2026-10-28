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
    leaves: 5
  });

  return Object.freeze({
    version: "1.0.0",
    seed: 20261028,
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 128,
    worldHeight: 64,
    gravity: 0.03,
    moveSpeed: 0.18,
    jumpSpeed: 0.45,
    maxFallSpeed: 0.9,
    maxStep: 0.25,
    spawnX: 12,
    reach: 5,
    stepMs: 1000 / 60,
    saveKey: "xc-sandbox-sample-v1",
    saveVersion: 1,
    blocks: BLOCKS,
    blockNames: Object.freeze({
      1: "grass",
      2: "dirt",
      3: "stone",
      4: "wood",
      5: "leaves"
    }),
    hotbar: Object.freeze([BLOCKS.grass, BLOCKS.dirt, BLOCKS.stone, BLOCKS.wood])
  });
});
