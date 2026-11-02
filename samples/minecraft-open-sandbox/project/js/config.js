(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxConfig = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Numeric block ids are stored in the world grid; item ids above 100 are
  // non-block inventory items.
  const BLOCKS = Object.freeze({
    air: 0,
    grass: 1,
    dirt: 2,
    stone: 3,
    wood: 4,
    leaves: 5,
    sand: 6,
    planks: 7,
    cobble: 8,
    coal_ore: 9,
    iron_ore: 10,
    ember_ore: 11,
    torch: 12,
    workbench: 13,
    furnace: 14,
    stone_bricks: 15,
    beacon: 16
  });

  const ITEMS = Object.freeze({
    stick: 100,
    coal: 101,
    iron_ingot: 102,
    ember_shard: 103,
    pick_wood: 110,
    pick_stone: 111,
    pick_iron: 112,
    sword_wood: 120,
    sword_stone: 121,
    sword_iron: 122
  });

  return Object.freeze({
    version: "1.0.0",
    title: "Emberdeep",
    tileSize: 24,
    viewWidth: 1152,
    viewHeight: 648,
    worldWidth: 360,
    worldHeight: 140,
    seed: 20261102,
    spawnX: 24,
    gravity: 62,
    moveSpeed: 5.6,
    jumpSpeed: 16.8,
    maxFall: 34,
    coyoteTime: 0.1,
    jumpBuffer: 0.12,
    reach: 5.5,
    playerWidth: 0.72,
    playerHeight: 1.8,
    maxHealth: 20,
    invulnTime: 0.9,
    regenDelay: 7,
    regenInterval: 5,
    dayLength: 300,
    startTime: 0.12,
    autosaveMs: 20000,
    hotbarSize: 9,
    inventorySize: 36,
    stackLimit: 99,
    mobLimit: 3,
    saveKey: "emberdeep.save.v1",
    saveVersion: 1,
    blocks: BLOCKS,
    items: ITEMS,
    blockNames: Object.freeze({
      0: "air",
      1: "grass",
      2: "dirt",
      3: "stone",
      4: "wood",
      5: "leaves",
      6: "sand",
      7: "planks",
      8: "cobble",
      9: "coal ore",
      10: "iron ore",
      11: "ember ore",
      12: "torch",
      13: "workbench",
      14: "furnace",
      15: "stone bricks",
      16: "ember beacon"
    })
  });
});
