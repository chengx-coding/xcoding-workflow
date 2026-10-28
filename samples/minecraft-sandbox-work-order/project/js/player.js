(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxPlayer");
  }

  const EPS = 1e-4;
  const GROUND_PROBE = 0.04;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      width: 0.7,
      height: 1.8
    };
  }

  function playerBounds(player) {
    const half = player.width / 2;
    return {
      left: player.x - half,
      right: player.x + half,
      top: player.y - player.height,
      bottom: player.y
    };
  }

  function isSolidForCollision(world, x, y) {
    if (x < 0 || x >= world.width || y >= world.height) {
      return true;
    }
    if (y < 0) {
      return false;
    }
    return world.data[y * world.width + x] !== CONFIG.blocks.air;
  }

  function findCollision(world, player, x, y) {
    const bounds = {
      left: x - player.width / 2 + EPS,
      right: x + player.width / 2 - EPS,
      top: y - player.height + EPS,
      bottom: y - EPS
    };
    const firstX = Math.floor(bounds.left);
    const lastX = Math.floor(bounds.right);
    const firstY = Math.floor(bounds.top);
    const lastY = Math.floor(bounds.bottom);

    for (let tileY = firstY; tileY <= lastY; tileY += 1) {
      for (let tileX = firstX; tileX <= lastX; tileX += 1) {
        if (isSolidForCollision(world, tileX, tileY)) {
          return { x: tileX, y: tileY };
        }
      }
    }
    return null;
  }

  function collides(world, player, x, y) {
    return findCollision(world, player, x, y) !== null;
  }

  function isOnGround(world, player) {
    const left = player.x - player.width / 2 + EPS;
    const right = player.x + player.width / 2 - EPS;
    const firstX = Math.floor(left);
    const lastX = Math.floor(right);
    const tileY = Math.floor(player.y + GROUND_PROBE - EPS);

    for (let tileX = firstX; tileX <= lastX; tileX += 1) {
      if (isSolidForCollision(world, tileX, tileY)) {
        return true;
      }
    }
    return false;
  }

  function moveHorizontal(world, player, delta) {
    if (!delta) {
      return;
    }
    const start = player.x;
    const target = start + delta;
    if (!collides(world, player, target, player.y)) {
      player.x = target;
      return;
    }

    if (delta > 0) {
      const tileX = Math.floor(target + player.width / 2 - EPS);
      player.x = tileX - player.width / 2 - EPS;
    } else {
      const tileX = Math.floor(target - player.width / 2 + EPS);
      player.x = tileX + 1 + player.width / 2 + EPS;
    }
    if (collides(world, player, player.x, player.y)) {
      player.x = start;
    }
    player.vx = 0;
  }

  function moveVertical(world, player, delta) {
    if (!delta) {
      return;
    }
    const start = player.y;
    const target = start + delta;
    if (!collides(world, player, player.x, target)) {
      player.y = target;
      return;
    }

    if (delta > 0) {
      const tileY = Math.floor(target - EPS);
      player.y = tileY - EPS;
      player.onGround = true;
    } else {
      const tileY = Math.floor(target - player.height + EPS);
      player.y = tileY + 1 + player.height + EPS;
    }
    if (collides(world, player, player.x, player.y)) {
      player.y = start;
    }
    player.vy = 0;
  }

  function stepPlayer(player, world, input, dt) {
    const delta = Number.isFinite(dt) && dt > 0 ? Math.min(dt, 3) : 1;
    const left = Boolean(input && input.left);
    const right = Boolean(input && input.right);
    const jump = Boolean(input && input.jump);

    player.vx = (right ? CONFIG.moveSpeed : 0) - (left ? CONFIG.moveSpeed : 0);
    if (jump && player.onGround) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
    }
    player.vy = Math.min(player.vy + CONFIG.gravity * delta, CONFIG.maxFallSpeed);

    const dx = player.vx * delta;
    const dy = player.vy * delta;
    const maxStep = Math.max(0.05, CONFIG.maxStep || 0.25);
    const substeps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / maxStep));

    for (let step = 0; step < substeps; step += 1) {
      moveHorizontal(world, player, dx / substeps);
      moveVertical(world, player, dy / substeps);
    }

    player.onGround = player.vy >= 0 && isOnGround(world, player);
    return player;
  }

  return {
    createPlayer: createPlayer,
    playerBounds: playerBounds,
    collides: collides,
    findCollision: findCollision,
    isOnGround: isOnGround,
    stepPlayer: stepPlayer
  };
});
