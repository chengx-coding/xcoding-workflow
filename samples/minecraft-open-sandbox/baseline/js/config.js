(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MosswildConfig = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const BLOCK = Object.freeze({
    AIR: 0,
    GRASS: 1,
    DIRT: 2,
    STONE: 3,
    COAL_ORE: 4,
    IRON_ORE: 5,
    GEM_ORE: 6,
    LOG: 7,
    LEAVES: 8,
    PLANKS: 9,
    BRICK: 10,
    WORKBENCH: 11,
    TORCH: 12,
    LANTERN: 13,
    CAMPFIRE: 14,
    BEDROCK: 15
  });

  return Object.freeze({
    version: "1.0.0",
    saveVersion: 1,
    saveKey: "mosswild.save.v1",
    tileSize: 32,
    worldWidth: 224,
    worldHeight: 96,
    hotbarSlots: 9,
    daySeconds: 300,
    startDayFraction: 4.5 / 24,
    maxHealth: 20,
    reach: 6.4,
    player: Object.freeze({
      width: 0.62,
      height: 1.72,
      walkSpeed: 4.7,
      sprintSpeed: 6.5,
      groundAcceleration: 58,
      airAcceleration: 24,
      friction: 46,
      jumpSpeed: 11.5,
      gravity: 34,
      coyoteTime: 0.1,
      jumpBuffer: 0.12,
      fallSafe: 5.5
    }),
    autoSaveSeconds: 10,
    block: BLOCK,
    blockNames: Object.freeze({
      [BLOCK.GRASS]: "Grass Block",
      [BLOCK.DIRT]: "Dirt",
      [BLOCK.STONE]: "Stone",
      [BLOCK.COAL_ORE]: "Coal Vein",
      [BLOCK.IRON_ORE]: "Iron Vein",
      [BLOCK.GEM_ORE]: "Amberstone Vein",
      [BLOCK.LOG]: "Oak Log",
      [BLOCK.LEAVES]: "Oak Leaves",
      [BLOCK.PLANKS]: "Oak Planks",
      [BLOCK.BRICK]: "Stone Bricks",
      [BLOCK.WORKBENCH]: "Workbench",
      [BLOCK.TORCH]: "Torch",
      [BLOCK.LANTERN]: "Warden's Lantern",
      [BLOCK.CAMPFIRE]: "Campfire",
      [BLOCK.BEDROCK]: "Bedrock"
    })
  });
});
