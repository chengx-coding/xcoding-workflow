(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"));
  } else {
    root.SandboxInteraction = factory(root.SandboxConfig, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, Inventory) {
  "use strict";

  function blockName(blockId) {
    return CONFIG.blockNames[blockId] || "block";
  }

  function blockAt(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return null;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return null;
    }
    return world.data[y * world.width + x];
  }

  function solidAt(world, x, y) {
    const block = blockAt(world, x, y);
    return block !== null && block !== CONFIG.blocks.air;
  }

  function distanceToTile(player, tileX, tileY) {
    const originX = player.x;
    const originY = player.y - player.height / 2;
    const centerX = tileX + 0.5;
    const centerY = tileY + 0.5;
    return Math.sqrt((originX - centerX) * (originX - centerX) + (originY - centerY) * (originY - centerY));
  }

  function withinReach(player, tileX, tileY) {
    return distanceToTile(player, tileX, tileY) <= CONFIG.reach;
  }

  function playerOverlapsTile(player, tileX, tileY) {
    const playerLeft = player.x - player.width / 2;
    const playerRight = player.x + player.width / 2;
    const playerTop = player.y - player.height;
    const playerBottom = player.y;
    return (
      playerLeft < tileX + 1 &&
      playerRight > tileX &&
      playerTop < tileY + 1 &&
      playerBottom > tileY
    );
  }

  function hasSupport(world, tileX, tileY) {
    return (
      solidAt(world, tileX - 1, tileY) ||
      solidAt(world, tileX + 1, tileY) ||
      solidAt(world, tileX, tileY - 1) ||
      solidAt(world, tileX, tileY + 1)
    );
  }

  function blockedResult(reason) {
    return { ok: false, reason: reason, block: CONFIG.blocks.air, blockName: "" };
  }

  // Validate a mine target without changing the world, so the UI can start a
  // break animation only for a legal target and explain refusals immediately.
  function validateMine(world, player, tileX, tileY) {
    if (!Number.isInteger(tileX) || !Number.isInteger(tileY)) {
      return blockedResult("Outside the world.");
    }
    const block = blockAt(world, tileX, tileY);
    if (block === null) {
      return blockedResult("Outside the world.");
    }
    if (tileY >= world.height - CONFIG.bedrockRows) {
      return blockedResult("The world floor is unbreakable.");
    }
    if (block === CONFIG.blocks.air) {
      return blockedResult("There is nothing to mine here.");
    }
    if (!withinReach(player, tileX, tileY)) {
      return blockedResult("Out of reach.");
    }
    const name = blockName(block);
    return { ok: true, reason: "", block: block, blockName: name };
  }

  // Mine one tile. Returns a structured result so the UI can explain refusals.
  function mineBlock(world, player, tileX, tileY, inventory) {
    const validation = validateMine(world, player, tileX, tileY);
    if (!validation.ok) {
      return validation;
    }
    world.data[tileY * world.width + tileX] = CONFIG.blocks.air;
    if (inventory) {
      Inventory.add(inventory, validation.block, 1);
    }
    return { ok: true, reason: "Mined " + validation.blockName + ".", block: validation.block, blockName: validation.blockName };
  }

  // Place one tile. Refusals cover bounds, reach, occupancy, the player body,
  // missing support and an empty palette slot.
  function placeBlock(world, player, tileX, tileY, blockId, inventory) {
    if (!Number.isInteger(blockId) || blockId < 1 || blockId > 9) {
      return blockedResult("No block selected.");
    }
    if (!Number.isInteger(tileX) || !Number.isInteger(tileY)) {
      return blockedResult("Outside the world.");
    }
    const existing = blockAt(world, tileX, tileY);
    if (existing === null) {
      return blockedResult("Outside the world.");
    }
    if (!withinReach(player, tileX, tileY)) {
      return blockedResult("Out of reach.");
    }
    if (existing !== CONFIG.blocks.air) {
      return blockedResult("That spot is not empty.");
    }
    if (playerOverlapsTile(player, tileX, tileY)) {
      return blockedResult("You are standing there.");
    }
    if (!hasSupport(world, tileX, tileY)) {
      return blockedResult("Build next to a block.");
    }
    if (inventory && Inventory.count(inventory, blockId) <= 0) {
      return blockedResult("No " + blockName(blockId) + " left - mine some first.");
    }
    world.data[tileY * world.width + tileX] = blockId;
    if (inventory) {
      Inventory.consume(inventory, blockId, 1);
    }
    return { ok: true, reason: "Placed " + blockName(blockId) + ".", block: blockId, blockName: blockName(blockId) };
  }

  return {
    blockAt: blockAt,
    solidAt: solidAt,
    distanceToTile: distanceToTile,
    withinReach: withinReach,
    playerOverlapsTile: playerOverlapsTile,
    hasSupport: hasSupport,
    validateMine: validateMine,
    mineBlock: mineBlock,
    placeBlock: placeBlock,
    blockName: blockName
  };
});
