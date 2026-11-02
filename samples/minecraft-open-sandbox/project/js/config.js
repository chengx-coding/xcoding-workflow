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
    planks: 6,
    cobblestone: 7,
    coalOre: 8,
    ironOre: 9,
    sand: 10,
    sandstone: 11,
    torch: 12,
    glass: 13,
    bedrock: 14,
    flower: 15
  });

  return Object.freeze({
    // Seed-compatible identity fields. `version` keeps its seed value; the
    // product label below is presentation identity, not a release version.
    version: "0.1.0",
    productName: "Cubewood",
    editionLabel: "1.0",
    tileSize: 32,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 192,
    worldHeight: 96,
    gravity: 54,
    moveSpeed: 7.4,
    jumpSpeed: 16.4,
    maxFallSpeed: 34,
    reach: 5.5,
    dayLength: 240,
    seed: 20261102,
    saveKey: "cubewood.save.v1",
    saveVersion: 1,
    autosaveSeconds: 12,
    hotbarSize: 9,
    zoom: Object.freeze({ min: 0.6, max: 2.5, step: 0.15, default: 1 }),
    ambientParticles: 26,
    blocks: BLOCKS,
    blockNames: Object.freeze({
      1: "Grass",
      2: "Dirt",
      3: "Stone",
      4: "Wood",
      5: "Leaves",
      6: "Planks",
      7: "Cobblestone",
      8: "Coal ore",
      9: "Iron ore",
      10: "Sand",
      11: "Sandstone",
      12: "Torch",
      13: "Glass",
      14: "Bedrock",
      15: "Flower"
    })
  });
});

