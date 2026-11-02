(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./blocks.js"), require("./inventory.js"));
  } else {
    root.SandboxPlacement = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxBlocks, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, BLOCKS, INVENTORY) {
  "use strict";

  if (!CONFIG || !WORLD || !BLOCKS || !INVENTORY) {
    throw new Error("SandboxConfig, SandboxWorld, SandboxBlocks and SandboxInventory are required before SandboxPlacement");
  }

  function playerBox(player) {
    return {
      left: player.x - player.width / 2,
      right: player.x + player.width / 2,
      top: player.y - player.height,
      bottom: player.y
    };
  }

  function overlapsPlayer(player, x, y) {
    const box = playerBox(player);
    return box.right > x && box.left < x + 1 && box.bottom > y && box.top < y + 1;
  }

  function hasSupport(world, x, y, blockId) {
    const definition = BLOCKS.block(blockId);
    if (definition && definition.support) {
      return WORLD.isSolid(world, x, y + 1) || WORLD.isSolid(world, x, y - 1) ||
        WORLD.isSolid(world, x - 1, y) || WORLD.isSolid(world, x + 1, y);
    }
    return WORLD.isSolid(world, x, y + 1) || WORLD.isSolid(world, x, y - 1) ||
      WORLD.isSolid(world, x - 1, y) || WORLD.isSolid(world, x + 1, y);
  }

  function evaluate(world, player, inventory, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return { ok: false, reason: "out-of-bounds" };
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return { ok: false, reason: "out-of-bounds" };
    }
    const selected = INVENTORY.selectedId(inventory);
    if (!BLOCKS.isBlockItem(selected)) {
      return { ok: false, reason: "empty-hand" };
    }
    if (!INVENTORY.has(inventory, selected, 1)) {
      return { ok: false, reason: "empty-hand" };
    }
    const current = WORLD.getBlock(world, x, y);
    if (!BLOCKS.isReplaceable(current)) {
      return { ok: false, reason: "occupied", block: selected };
    }
    if (!reachable(player, x, y)) {
      return { ok: false, reason: "out-of-reach", block: selected };
    }
    if (overlapsPlayer(player, x, y)) {
      return { ok: false, reason: "blocked-by-player", block: selected };
    }
    if (!hasSupport(world, x, y, selected)) {
      return { ok: false, reason: "no-support", block: selected };
    }
    return { ok: true, reason: null, block: selected };
  }

  function reachable(player, x, y) {
    const centerX = player.x;
    const centerY = player.y - player.height / 2;
    const dx = x + 0.5 - centerX;
    const dy = y + 0.5 - centerY;
    return Math.sqrt(dx * dx + dy * dy) <= CONFIG.reach;
  }

  function place(world, player, inventory, x, y) {
    const check = evaluate(world, player, inventory, x, y);
    if (!check.ok) {
      return check;
    }
    if (!INVENTORY.remove(inventory, check.block, 1)) {
      return { ok: false, reason: "empty-hand" };
    }
    WORLD.setBlock(world, x, y, check.block);
    return { ok: true, block: check.block, reason: null };
  }

  return {
    evaluate: evaluate,
    place: place,
    reachable: reachable,
    overlapsPlayer: overlapsPlayer,
    hasSupport: hasSupport
  };
});
