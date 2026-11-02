(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./blocks.js"), require("./inventory.js"));
  } else {
    root.SandboxMining = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxBlocks, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, BLOCKS, INVENTORY) {
  "use strict";

  if (!CONFIG || !WORLD || !BLOCKS || !INVENTORY) {
    throw new Error("SandboxConfig, SandboxWorld, SandboxBlocks and SandboxInventory are required before SandboxMining");
  }

  function targetInfo(world, inventory, x, y) {
    const id = WORLD.getBlock(world, x, y);
    const definition = BLOCKS.block(id);
    if (!definition || id === CONFIG.blocks.air) {
      return { ok: false, reason: "empty", blockId: id || 0 };
    }
    if (definition.hardness === Infinity) {
      return { ok: false, reason: "unbreakable", blockId: id, definition: definition };
    }
    const tool = definition.tool ? INVENTORY.bestTool(inventory, definition.tool) : null;
    const tier = tool ? tool.tier : 0;
    const speed = tool ? tool.speed : 1;
    const canHarvest = tier >= definition.tier;
    return {
      ok: true,
      blockId: id,
      definition: definition,
      tool: tool,
      tier: tier,
      speed: speed,
      time: definition.hardness / speed,
      canHarvest: canHarvest,
      drop: canHarvest ? definition.drop : null,
      reason: canHarvest ? null : "tool-too-weak"
    };
  }

  function createMining() {
    return { x: -1, y: -1, progress: 0, blockId: 0, elapsed: 0 };
  }

  function reset(mining) {
    mining.x = -1;
    mining.y = -1;
    mining.progress = 0;
    mining.blockId = 0;
    mining.elapsed = 0;
    return mining;
  }

  // Advances a held mining action. The caller owns block removal and drops so
  // that mining stays a pure, testable progression rule.
  function advance(mining, world, inventory, x, y, dt) {
    const info = targetInfo(world, inventory, x, y);
    if (!info.ok) {
      reset(mining);
      return { progress: 0, done: false, info: info, blocked: true };
    }
    if (mining.x !== x || mining.y !== y || mining.blockId !== info.blockId) {
      mining.x = x;
      mining.y = y;
      mining.blockId = info.blockId;
      mining.progress = 0;
      mining.elapsed = 0;
    }
    mining.elapsed += dt;
    if (info.time === Infinity) {
      return { progress: 0, done: false, info: info, blocked: true };
    }
    mining.progress = Math.min(1, mining.progress + dt / info.time);
    const done = mining.progress >= 1;
    if (done) {
      reset(mining);
    }
    return { progress: done ? 1 : mining.progress, done: done, info: info, blocked: false };
  }

  // Instant break used by keyboard shortcuts and the browser self-test.
  function breakBlock(world, inventory, x, y) {
    const info = targetInfo(world, inventory, x, y);
    if (!info.ok) {
      return { ok: false, reason: info.reason, blockId: info.blockId };
    }
    WORLD.setBlock(world, x, y, CONFIG.blocks.air);
    let dropId = 0;
    if (info.drop !== null && info.drop !== undefined) {
      INVENTORY.add(inventory, info.drop, 1);
      dropId = info.drop;
    }
    return {
      ok: true,
      blockId: info.blockId,
      drop: dropId,
      canHarvest: info.canHarvest,
      reason: info.canHarvest ? null : "tool-too-weak",
      dropName: dropId ? BLOCKS.nameOf(dropId) : ""
    };
  }

  function reachable(player, tileX, tileY, reach) {
    const centerX = player.x;
    const centerY = player.y - player.height / 2;
    const dx = tileX + 0.5 - centerX;
    const dy = tileY + 0.5 - centerY;
    return Math.sqrt(dx * dx + dy * dy) <= (reach || CONFIG.reach);
  }

  return {
    targetInfo: targetInfo,
    createMining: createMining,
    advance: advance,
    reset: reset,
    breakBlock: breakBlock,
    reachable: reachable
  };
});
