(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPSILON = 0.0001;
  const MAX_STEP = 0.2;

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

  function playerBox(player, x, y) {
    const left = (x === undefined ? player.x : x) - player.width / 2;
    const top = (y === undefined ? player.y : y) - player.height;
    return {
      left: left,
      right: left + player.width,
      top: top,
      bottom: top + player.height
    };
  }

  function tileRange(box) {
    return {
      x0: Math.floor(box.left),
      x1: Math.ceil(box.right) - 1,
      y0: Math.floor(box.top),
      y1: Math.ceil(box.bottom) - 1
    };
  }

  function boxHitsSolid(world, box) {
    const range = tileRange(box);
    for (let y = range.y0; y <= range.y1; y += 1) {
      for (let x = range.x0; x <= range.x1; x += 1) {
        if (isSolidAt(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  function isSolidAt(world, x, y) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return false;
    }
    return world.data[y * world.width + x] !== CONFIG.blocks.air;
  }

  function moveHorizontal(player, world, distance) {
    if (distance === 0) {
      return false;
    }
    const direction = distance > 0 ? 1 : -1;
    let remaining = Math.abs(distance);
    while (remaining > EPSILON) {
      const step = Math.min(MAX_STEP, remaining) * direction;
      const nextX = player.x + step;
      if (boxHitsSolid(world, playerBox(player, nextX, player.y))) {
        if (direction > 0) {
          const wall = Math.floor(nextX + player.width / 2);
          player.x = wall - player.width / 2 - EPSILON;
        } else {
          const wall = Math.floor(nextX - player.width / 2);
          player.x = wall + 1 + player.width / 2 + EPSILON;
        }
        player.vx = 0;
        return true;
      }
      player.x = nextX;
      remaining -= Math.abs(step);
    }
    return false;
  }

  function moveVertical(player, world, distance) {
    if (distance === 0) {
      return false;
    }
    const direction = distance > 0 ? 1 : -1;
    let remaining = Math.abs(distance);
    while (remaining > EPSILON) {
      const step = Math.min(MAX_STEP, remaining) * direction;
      const nextY = player.y + step;
      if (boxHitsSolid(world, playerBox(player, player.x, nextY))) {
        if (direction > 0) {
          player.y = Math.floor(nextY) - EPSILON;
          player.onGround = true;
        } else {
          const ceiling = Math.floor(nextY - player.height);
          player.y = ceiling + 1 + player.height + EPSILON;
        }
        player.vy = 0;
        return true;
      }
      player.y = nextY;
      remaining -= Math.abs(step);
    }
    return false;
  }

  function isGrounded(player, world) {
    return boxHitsSolid(world, playerBox(player, player.x, player.y + 0.05));
  }

  // Advance one frame. `dt` is seconds; values are clamped so a paused or
  // backgrounded tab cannot tunnel the player through the world.
  function stepPlayer(player, world, input, dt) {
    const controls = input || {};
    const delta = Math.max(0, Math.min(0.05, typeof dt === "number" ? dt : 1 / 60));

    let direction = 0;
    if (controls.left) {
      direction -= 1;
    }
    if (controls.right) {
      direction += 1;
    }
    player.vx = direction * CONFIG.moveSpeed;
    if (direction !== 0) {
      player.facing = direction;
    }

    if (controls.jump && player.onGround) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
    }

    player.vy = Math.min(CONFIG.maxFallSpeed, player.vy + CONFIG.gravity * delta);
    player.onGround = false;

    moveHorizontal(player, world, player.vx * delta);
    moveVertical(player, world, player.vy * delta);

    if (player.x < player.width / 2) {
      player.x = player.width / 2;
      player.vx = 0;
    }
    if (player.x > world.width - player.width / 2) {
      player.x = world.width - player.width / 2;
      player.vx = 0;
    }
    if (player.y > world.height) {
      player.y = world.height;
      player.vy = 0;
    }
    if (player.y < player.height) {
      player.y = player.height;
      player.vy = 0;
    }

    player.onGround = isGrounded(player, world);
    if (player.onGround) {
      player.walkTime += Math.abs(player.vx) * delta;
    }
    return player;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    playerBox: playerBox,
    isGrounded: isGrounded
  };
});
