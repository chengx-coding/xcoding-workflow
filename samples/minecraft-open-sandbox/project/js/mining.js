(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxMining = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  if (!CONFIG || !WORLD) {
    throw new Error("SandboxConfig and SandboxWorld are required before SandboxMining");
  }

  function bestTool(tools) {
    let best = null;
    const list = Array.isArray(tools) ? tools : [];
    for (let i = 0; i < list.length; i += 1) {
      const def = CONFIG.tools[list[i]];
      if (!def) {
        continue;
      }
      if (!best || def.tier > best.tier) {
        best = def;
      }
    }
    return best;
  }

  function blockRule(world, x, y, tools) {
    const block = WORLD.getBlock(world, x, y);
    if (block === null || block === CONFIG.blocks.air) {
      return { allowed: false, reason: "empty", seconds: Infinity, drop: null };
    }
    const def = WORLD.blockDef(block);
    if (WORLD.isUnbreakable(world, x, y)) {
      return { allowed: false, reason: "unbreakable", seconds: Infinity, drop: null };
    }
    const tool = bestTool(tools);
    if (def.tool && (!tool || tool.tier < def.tier)) {
      return {
        allowed: false,
        reason: "tool",
        required: def.tier,
        seconds: Infinity,
        drop: def.drop
      };
    }
    const speed = def.tool && tool ? tool.speed : 1;
    return {
      allowed: true,
      reason: "ok",
      seconds: Math.max(0.03, def.hardness / speed),
      drop: def.drop
    };
  }

  function canReach(player, tx, ty) {
    const centreX = player.x;
    const centreY = player.y - player.height / 2;
    const dx = tx + 0.5 - centreX;
    const dy = ty + 0.5 - centreY;
    return Math.sqrt(dx * dx + dy * dy) <= CONFIG.reach;
  }

  function targetWithinReach(world, player, tx, ty) {
    if (tx < 0 || ty < 0 || tx >= world.width || ty >= world.height) {
      return false;
    }
    return canReach(player, tx, ty);
  }

  function createMining() {
    return { x: -1, y: -1, progress: 0, seconds: 0, active: false };
  }

  function resetMining(mining) {
    mining.x = -1;
    mining.y = -1;
    mining.progress = 0;
    mining.seconds = 0;
    mining.active = false;
    return mining;
  }

  function updateMining(mining, world, player, tx, ty, tools, dt, holding) {
    if (!holding) {
      resetMining(mining);
      return { active: false, progress: 0, complete: false, rule: null };
    }
    if (!targetWithinReach(world, player, tx, ty)) {
      resetMining(mining);
      return { active: false, progress: 0, complete: false, rule: null, reason: "reach" };
    }
    const rule = blockRule(world, tx, ty, tools);
    if (!rule.allowed) {
      resetMining(mining);
      return { active: false, progress: 0, complete: false, rule: rule };
    }
    if (mining.x !== tx || mining.y !== ty) {
      mining.x = tx;
      mining.y = ty;
      mining.progress = 0;
      mining.seconds = rule.seconds;
      mining.active = true;
    }
    mining.seconds = rule.seconds;
    mining.progress += dt / rule.seconds;
    if (mining.progress >= 1) {
      mining.progress = 0;
      mining.active = false;
      return { active: false, progress: 0, complete: true, rule: rule, x: tx, y: ty };
    }
    return { active: true, progress: Math.min(0.999, mining.progress), complete: false, rule: rule };
  }

  function tierFor(tools) {
    const tool = bestTool(tools);
    return tool ? tool.tier : 0;
  }

  return {
    bestTool: bestTool,
    tierFor: tierFor,
    blockRule: blockRule,
    canReach: canReach,
    targetWithinReach: targetWithinReach,
    createMining: createMining,
    resetMining: resetMining,
    updateMining: updateMining
  };
});
