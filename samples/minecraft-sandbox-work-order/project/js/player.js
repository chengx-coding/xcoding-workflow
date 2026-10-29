(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPSILON = 0.001;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      width: 0.68,
      height: 1.8,
      coyote: 0,
      jumpBuffer: 0,
      facing: 1,
      animTime: 0,
      spawnX: x,
      spawnY: y
    };
  }

  function overlapsSolid(world, x, y, width, height) {
    const left = x - width / 2 + EPSILON;
    const right = x + width / 2 - EPSILON;
    const top = y - height + EPSILON;
    const bottom = y - EPSILON;
    if (left < 0 || right > world.width || top < 0 || bottom > world.height) {
      return true;
    }
    const firstX = Math.floor(left);
    const lastX = Math.floor(right);
    const firstY = Math.floor(top);
    const lastY = Math.floor(bottom);
    for (let ty = firstY; ty <= lastY; ty += 1) {
      for (let tx = firstX; tx <= lastX; tx += 1) {
        const block = world.data[ty * world.width + tx];
        if (block !== CONFIG.blocks.air) {
          return true;
        }
      }
    }
    return false;
  }

  function approach(current, target, maxDelta) {
    if (current < target) {
      return Math.min(target, current + maxDelta);
    }
    if (current > target) {
      return Math.max(target, current - maxDelta);
    }
    return current;
  }

  function movePlayer(player, world, dx, dy) {
    const distance = Math.max(Math.abs(dx), Math.abs(dy));
    const steps = Math.max(1, Math.ceil(distance / 0.12));
    const stepX = dx / steps;
    const stepY = dy / steps;

    for (let index = 0; index < steps; index += 1) {
      if (stepX !== 0) {
        const nextX = player.x + stepX;
        if (!overlapsSolid(world, nextX, player.y, player.width, player.height)) {
          player.x = nextX;
        } else {
          player.vx = 0;
        }
      }
      if (stepY !== 0) {
        const nextY = player.y + stepY;
        if (!overlapsSolid(world, player.x, nextY, player.width, player.height)) {
          player.y = nextY;
        } else {
          if (stepY > 0) {
            player.onGround = true;
          }
          player.vy = 0;
          break;
        }
      }
    }
  }

  function stepPlayer(player, world, input, dt) {
    const controls = input || {};
    const duration = Math.max(0, Math.min(dt || 0, 0.05));
    if (duration === 0) {
      return player;
    }

    const grounded = player.onGround;
    const direction = (controls.right ? 1 : 0) - (controls.left ? 1 : 0);
    const sprint = controls.sprint ? CONFIG.sprintMultiplier : 1;
    const targetSpeed = direction * CONFIG.moveSpeed * sprint;
    const acceleration = grounded ? 58 : 30;
    const deceleration = grounded ? 46 : 12;

    if (direction !== 0) {
      player.vx = approach(player.vx, targetSpeed, acceleration * duration);
      player.facing = direction;
    } else {
      player.vx = approach(player.vx, 0, deceleration * duration);
    }

    if (grounded) {
      player.coyote = 0.1;
    } else {
      player.coyote = Math.max(0, player.coyote - duration);
    }

    if (controls.jumpPressed) {
      player.jumpBuffer = 0.13;
    } else {
      player.jumpBuffer = Math.max(0, player.jumpBuffer - duration);
    }

    if (player.jumpBuffer > 0 && player.coyote > 0) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuffer = 0;
    }

    let gravity = CONFIG.gravity;
    if (!controls.jumpHeld && player.vy < -3) {
      gravity *= 1.85;
    }
    player.vy = Math.min(player.vy + gravity * duration, CONFIG.maxFallSpeed);

    player.onGround = false;
    movePlayer(player, world, player.vx * duration, player.vy * duration);

    if (!player.onGround && player.vy >= 0) {
      if (overlapsSolid(world, player.x, player.y + 0.045, player.width, player.height)) {
        player.onGround = true;
        player.vy = 0;
      }
    }

    player.animTime += Math.abs(player.vx) * duration;
    return player;
  }

  function teleportToSpawn(player, world, spawn) {
    player.x = spawn.x;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.onGround = false;
    player.coyote = 0;
    player.jumpBuffer = 0;
    player.spawnX = spawn.x;
    player.spawnY = spawn.y;
    return player;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    overlapsSolid: overlapsSolid,
    teleportToSpawn: teleportToSpawn
  };
});
