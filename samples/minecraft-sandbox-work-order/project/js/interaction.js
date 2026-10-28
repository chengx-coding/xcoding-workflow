(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./player.js"));
  } else {
    root.SandboxInteraction = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxPlayer);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, World, Player) {
  "use strict";

  if (!CONFIG || !World || !Player) {
    throw new Error("SandboxConfig, SandboxWorld and SandboxPlayer are required before SandboxInteraction");
  }

  function cellFromScreen(camera, screenX, screenY, tileSize) {
    const tile = tileSize || CONFIG.tileSize;
    const offsetX = camera ? camera.x : 0;
    const offsetY = camera ? camera.y : 0;
    return {
      x: Math.floor((screenX + offsetX) / tile),
      y: Math.floor((screenY + offsetY) / tile)
    };
  }

  function playerCenter(player) {
    return {
      x: player.x,
      y: player.y - player.height / 2
    };
  }

  function inReach(player, x, y, reach) {
    const center = playerCenter(player);
    const target = { x: x + 0.5, y: y + 0.5 };
    const distance = Math.hypot(target.x - center.x, target.y - center.y);
    return distance <= (reach === undefined ? CONFIG.reach : reach);
  }

  function overlapsPlayer(player, x, y) {
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return (
      left < x + 1 - 1e-6 &&
      right > x + 1e-6 &&
      top < y + 1 - 1e-6 &&
      bottom > y + 1e-6
    );
  }

  function hasSolidNeighbor(world, x, y) {
    return (
      World.isSolid(world, x + 1, y) ||
      World.isSolid(world, x - 1, y) ||
      World.isSolid(world, x, y + 1) ||
      World.isSolid(world, x, y - 1)
    );
  }

  function canMine(world, player, x, y) {
    const block = World.getBlock(world, x, y);
    if (block === null || block === CONFIG.blocks.air) {
      return false;
    }
    return inReach(player, x, y);
  }

  function mineBlock(world, player, x, y) {
    if (!canMine(world, player, x, y)) {
      return false;
    }
    return World.setBlock(world, x, y, CONFIG.blocks.air);
  }

  function canPlaceAt(world, player, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return false;
    }
    const block = World.getBlock(world, x, y);
    if (block === null || block !== CONFIG.blocks.air) {
      return false;
    }
    if (!inReach(player, x, y)) {
      return false;
    }
    if (overlapsPlayer(player, x, y)) {
      return false;
    }
    return hasSolidNeighbor(world, x, y);
  }

  function canPlace(world, player, x, y, block) {
    if (!Number.isInteger(block) || block <= 0) {
      return false;
    }
    return canPlaceAt(world, player, x, y);
  }

  function placeBlock(world, player, x, y, block) {
    if (!canPlace(world, player, x, y, block)) {
      return false;
    }
    return World.setBlock(world, x, y, block);
  }

  function adjacentPlacementCell(world, player, x, y) {
    if (canPlaceAt(world, player, x, y)) {
      return { x: x, y: y };
    }

    const neighbors = [
      { x: x + 1, y: y },
      { x: x - 1, y: y },
      { x: x, y: y + 1 },
      { x: x, y: y - 1 }
    ];
    const candidates = neighbors.filter(function candidate(cell) {
      return canPlaceAt(world, player, cell.x, cell.y);
    });
    if (candidates.length === 0) {
      return null;
    }

    const center = playerCenter(player);
    candidates.sort(function nearest(a, b) {
      const distanceA = Math.hypot(a.x + 0.5 - center.x, a.y + 0.5 - center.y);
      const distanceB = Math.hypot(b.x + 0.5 - center.x, b.y + 0.5 - center.y);
      if (distanceA !== distanceB) {
        return distanceA - distanceB;
      }
      if (a.y !== b.y) {
        return a.y - b.y;
      }
      return a.x - b.x;
    });
    return candidates[0];
  }

  return {
    cellFromScreen: cellFromScreen,
    playerCenter: playerCenter,
    inReach: inReach,
    overlapsPlayer: overlapsPlayer,
    hasSolidNeighbor: hasSolidNeighbor,
    canMine: canMine,
    mineBlock: mineBlock,
    canPlaceAt: canPlaceAt,
    canPlace: canPlace,
    placeBlock: placeBlock,
    adjacentPlacementCell: adjacentPlacementCell
  };
});
