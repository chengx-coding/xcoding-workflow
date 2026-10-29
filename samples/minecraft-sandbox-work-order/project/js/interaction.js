(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxInteraction = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, worldApi) {
  "use strict";

  const EPSILON = 0.0001;

  function distanceFromPlayer(player, x, y) {
    const centerY = player.y - player.height / 2;
    const dx = x + 0.5 - player.x;
    const dy = y + 0.5 - centerY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function intersectsPlayer(player, x, y) {
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return x + 1 > left + EPSILON && x < right - EPSILON && y + 1 > top + EPSILON && y < bottom - EPSILON;
  }

  function hasSolidNeighbor(world, x, y) {
    return (
      worldApi.isSolid(world, x - 1, y) ||
      worldApi.isSolid(world, x + 1, y) ||
      worldApi.isSolid(world, x, y - 1) ||
      worldApi.isSolid(world, x, y + 1)
    );
  }

  function canPlaceBlock(world, player, x, y, reach) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return { ok: false, reason: "outside" };
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return { ok: false, reason: "outside" };
    }
    if (worldApi.getBlock(world, x, y) !== CONFIG.blocks.air) {
      return { ok: false, reason: "occupied" };
    }
    if (distanceFromPlayer(player, x, y) > (reach == null ? CONFIG.reach : reach)) {
      return { ok: false, reason: "reach" };
    }
    if (intersectsPlayer(player, x, y)) {
      return { ok: false, reason: "player" };
    }
    if (!hasSolidNeighbor(world, x, y)) {
      return { ok: false, reason: "unsupported" };
    }
    return { ok: true, reason: "ok" };
  }

  function adjacentCandidates(x, y, localX, localY) {
    const edges = [
      { x: x, y: y - 1, distance: localY },
      { x: x, y: y + 1, distance: 1 - localY },
      { x: x - 1, y: y, distance: localX },
      { x: x + 1, y: y, distance: 1 - localX }
    ];
    edges.sort(function (a, b) {
      return a.distance - b.distance;
    });
    return edges;
  }

  function findPlacementCell(world, player, x, y, localX, localY, reach) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return { ok: false, reason: "outside", x: x, y: y };
    }
    const block = worldApi.getBlock(world, x, y);
    if (block === CONFIG.blocks.air) {
      const result = canPlaceBlock(world, player, x, y, reach);
      return { ok: result.ok, reason: result.reason, x: x, y: y };
    }
    const candidates = adjacentCandidates(x, y, localX, localY);
    let firstReason = "occupied";
    for (let index = 0; index < candidates.length; index += 1) {
      const candidate = candidates[index];
      const result = canPlaceBlock(world, player, candidate.x, candidate.y, reach);
      if (result.ok) {
        return { ok: true, reason: "ok", x: candidate.x, y: candidate.y };
      }
      if (result.reason !== "occupied" && result.reason !== "outside") {
        firstReason = result.reason;
      }
    }
    return { ok: false, reason: firstReason, x: x, y: y };
  }

  function inspectTarget(world, player, worldX, worldY, selectedBlock, reach) {
    const x = Math.floor(worldX);
    const y = Math.floor(worldY);
    const block = worldApi.getBlock(world, x, y);
    const empty = block === CONFIG.blocks.air;
    const inReach = block !== null && distanceFromPlayer(player, x, y) <= (reach == null ? CONFIG.reach : reach);
    const placement = findPlacementCell(
      world,
      player,
      x,
      y,
      worldX - x,
      worldY - y,
      reach
    );
    return {
      x: x,
      y: y,
      block: block,
      empty: empty,
      inReach: inReach,
      canMine: inReach && block !== null && block !== CONFIG.blocks.bedrock,
      canPlace: placement.ok,
      placement: placement,
      selectedBlock: selectedBlock
    };
  }

  function mineBlock(world, player, x, y, reach) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return { ok: false, reason: "outside" };
    }
    const block = worldApi.getBlock(world, x, y);
    if (block === CONFIG.blocks.air) {
      return { ok: false, reason: "empty" };
    }
    if (block === CONFIG.blocks.bedrock) {
      return { ok: false, reason: "bedrock" };
    }
    if (distanceFromPlayer(player, x, y) > (reach == null ? CONFIG.reach : reach)) {
      return { ok: false, reason: "reach" };
    }
    worldApi.setBlock(world, x, y, CONFIG.blocks.air);
    return { ok: true, block: block };
  }

  function placeBlock(world, player, x, y, block, reach) {
    if (!Number.isInteger(block) || block === CONFIG.blocks.air) {
      return { ok: false, reason: "invalid-block" };
    }
    const check = canPlaceBlock(world, player, x, y, reach);
    if (!check.ok) {
      return check;
    }
    worldApi.setBlock(world, x, y, block);
    return { ok: true, block: block };
  }

  return {
    distanceFromPlayer: distanceFromPlayer,
    intersectsPlayer: intersectsPlayer,
    hasSolidNeighbor: hasSolidNeighbor,
    canPlaceBlock: canPlaceBlock,
    findPlacementCell: findPlacementCell,
    inspectTarget: inspectTarget,
    mineBlock: mineBlock,
    placeBlock: placeBlock
  };
});
