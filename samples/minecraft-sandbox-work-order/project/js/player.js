(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPSILON = 0.0001;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      facing: 1,
      walkTime: 0,
      width: 0.7,
      height: 1.8
    };
  }

  function playerBox(player) {
    const half = player.width / 2;
    return {
      left: player.x - half,
      right: player.x + half,
      top: player.y - player.height,
      bottom: player.y
    };
  }

  function overlapsCell(player, cellX, cellY) {
    const box = playerBox(player);
    return box.left < cellX + 1 && box.right > cellX && box.top < cellY + 1 && box.bottom > cellY;
  }

  function solidAt(world, x, y) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return false;
    }
    return world.data[y * world.width + x] !== CONFIG.blocks.air;
  }

  function tilesForBox(box) {
    return {
      minX: Math.floor(box.left),
      maxX: Math.floor(box.right - EPSILON),
      minY: Math.floor(box.top),
      maxY: Math.floor(box.bottom - EPSILON)
    };
  }

  function resolveHorizontal(player, world, direction) {
    const box = playerBox(player);
    const tiles = tilesForBox(box);
    for (let y = tiles.minY; y <= tiles.maxY; y += 1) {
      for (let x = tiles.minX; x <= tiles.maxX; x += 1) {
        if (!solidAt(world, x, y)) {
          continue;
        }
        if (direction > 0) {
          player.x = Math.min(player.x, x - player.width / 2 - EPSILON);
        } else if (direction < 0) {
          player.x = Math.max(player.x, x + 1 + player.width / 2 + EPSILON);
        }
      }
    }
  }

  function resolveVertical(player, world, direction) {
    const box = playerBox(player);
    const tiles = tilesForBox(box);
    let grounded = false;
    for (let y = tiles.minY; y <= tiles.maxY; y += 1) {
      for (let x = tiles.minX; x <= tiles.maxX; x += 1) {
        if (!solidAt(world, x, y)) {
          continue;
        }
        if (direction > 0) {
          player.y = Math.min(player.y, y - EPSILON);
          grounded = true;
        } else if (direction < 0) {
          player.y = Math.max(player.y, y + 1 + player.height + EPSILON);
        }
      }
    }
    return grounded;
  }

  function isSupported(player, world) {
    const probe = playerBox(player);
    const footY = Math.floor(probe.bottom + 0.06);
    const minX = Math.floor(probe.left + 0.02);
    const maxX = Math.floor(probe.right - 0.02);
    for (let x = minX; x <= maxX; x += 1) {
      if (solidAt(world, x, footY)) {
        return true;
      }
    }
    return false;
  }

  function clampToWorld(player, world) {
    const half = player.width / 2;
    player.x = Math.min(Math.max(player.x, half + EPSILON), world.width - half - EPSILON);
    player.y = Math.min(player.y, world.height - EPSILON);
    if (player.y < player.height + EPSILON) {
      player.y = player.height + EPSILON;
    }
  }

  function stepPlayer(player, world, input, dt) {
    const controls = input || {};
    const elapsed = Math.max(0, Math.min(Number(dt) || 0, 0.1));
    if (elapsed === 0) {
      return player;
    }

    const direction = (controls.right ? 1 : 0) - (controls.left ? 1 : 0);
    player.vx = direction * CONFIG.moveSpeed;
    if (direction !== 0) {
      player.facing = direction;
    }

    if (controls.jump && (player.onGround || isSupported(player, world))) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
    }

    player.vy = Math.min(player.vy + CONFIG.gravity * elapsed, CONFIG.maxFallSpeed);

    const distance = Math.max(Math.abs(player.vx), Math.abs(player.vy)) * elapsed;
    const steps = Math.min(10, Math.max(1, Math.ceil(distance / 0.35)));
    const subDt = elapsed / steps;

    for (let step = 0; step < steps; step += 1) {
      if (player.vx !== 0) {
        player.x += player.vx * subDt;
        const before = player.x;
        resolveHorizontal(player, world, player.vx > 0 ? 1 : -1);
        if (player.x !== before) {
          player.vx = 0;
        }
      }
      player.y += player.vy * subDt;
      const grounded = resolveVertical(player, world, player.vy > 0 ? 1 : player.vy < 0 ? -1 : 0);
      if (grounded && player.vy > 0) {
        player.vy = 0;
        player.onGround = true;
      } else if (!grounded) {
        player.onGround = false;
      }
      if (player.vy < 0 && resolveVertical(player, world, -1)) {
        player.vy = 0;
      }
    }

    player.onGround = player.onGround || isSupported(player, world);
    player.walkTime += Math.abs(player.vx) * elapsed;
    clampToWorld(player, world);
    return player;
  }

  function respawnPlayer(world) {
    const spawn = world && world.spawn ? world.spawn : { x: world.width / 2, y: world.height * 0.4 };
    return createPlayer(spawn.x, spawn.y);
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    respawnPlayer: respawnPlayer,
    playerBox: playerBox,
    overlapsCell: overlapsCell,
    isSupported: isSupported,
    solidAt: solidAt
  };
});
