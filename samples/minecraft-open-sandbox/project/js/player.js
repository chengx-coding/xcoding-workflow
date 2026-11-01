(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  if (!CONFIG || !WORLD) {
    throw new Error("SandboxConfig and SandboxWorld are required before SandboxPlayer");
  }

  const EPSILON = 1e-6;
  const COYOTE_TIME = 0.09;
  const JUMP_BUFFER = 0.12;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      facing: 1,
      width: 0.7,
      height: 1.8,
      onGround: false,
      inWater: false,
      coyote: 0,
      jumpBuffer: 0,
      walk: 0,
      airTime: 0
    };
  }

  function overlapsSolid(world, x, y, width, height) {
    const left = Math.floor(x - width / 2 + EPSILON);
    const right = Math.floor(x + width / 2 - EPSILON);
    const top = Math.floor(y - height + EPSILON);
    const bottom = Math.floor(y - EPSILON);
    for (let ty = top; ty <= bottom; ty += 1) {
      for (let tx = left; tx <= right; tx += 1) {
        if (WORLD.isSolid(world, tx, ty)) {
          return true;
        }
      }
    }
    return false;
  }

  function isInWater(world, player) {
    return (
      WORLD.isWater(world, Math.floor(player.x), Math.floor(player.y - 0.6)) ||
      WORLD.isWater(world, Math.floor(player.x), Math.floor(player.y - 0.1))
    );
  }

  function clampToWorld(world, player) {
    const half = player.width / 2;
    if (player.x < half) {
      player.x = half;
      player.vx = 0;
    }
    if (player.x > world.width - half) {
      player.x = world.width - half;
      player.vx = 0;
    }
  }

  function resolveHorizontal(world, player, dx, events) {
    if (dx === 0) {
      return;
    }
    const steps = Math.max(1, Math.ceil(Math.abs(dx) / 0.4));
    const step = dx / steps;
    for (let i = 0; i < steps; i += 1) {
      player.x += step;
      if (!overlapsSolid(world, player.x, player.y, player.width, player.height)) {
        continue;
      }
      if (step > 0) {
        player.x = Math.floor(player.x + player.width / 2) - player.width / 2 - EPSILON;
      } else {
        player.x = Math.floor(player.x - player.width / 2) + 1 + player.width / 2 + EPSILON;
      }
      player.vx = 0;
      events.push({ type: "bump" });
      break;
    }
  }

  function resolveVertical(world, player, dy, events) {
    if (dy === 0) {
      return;
    }
    const steps = Math.max(1, Math.ceil(Math.abs(dy) / 0.4));
    const step = dy / steps;
    for (let i = 0; i < steps; i += 1) {
      player.y += step;
      if (!overlapsSolid(world, player.x, player.y, player.width, player.height)) {
        continue;
      }
      if (step > 0) {
        player.y = Math.floor(player.y) - EPSILON;
        if (!player.onGround && player.vy > 2.5) {
          events.push({ type: "land", speed: player.vy });
        }
        player.onGround = true;
        player.vy = 0;
      } else {
        player.y = Math.floor(player.y - player.height) + 1 + player.height - EPSILON;
        player.vy = 0;
        events.push({ type: "ceiling" });
      }
      break;
    }
  }

  function stepPlayer(player, world, input, dt) {
    const events = [];
    const left = input.left === true;
    const right = input.right === true;
    const jump = input.jump === true;
    player.inWater = isInWater(world, player);

    if (input.jumpPressed === true) {
      player.jumpBuffer = JUMP_BUFFER;
    }
    player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);

    const direction = (right ? 1 : 0) - (left ? 1 : 0);
    if (direction !== 0) {
      player.facing = direction;
    }
    const targetSpeed = direction * CONFIG.moveSpeed * (player.inWater ? 0.62 : 1);
    const acceleration = player.onGround ? 55 : player.inWater ? 18 : 32;
    const delta = targetSpeed - player.vx;
    const maxDelta = acceleration * dt;
    player.vx += Math.max(-maxDelta, Math.min(maxDelta, delta));
    if (direction === 0 && player.onGround) {
      player.vx *= Math.max(0, 1 - 12 * dt);
      if (Math.abs(player.vx) < 0.02) {
        player.vx = 0;
      }
    }

    if (player.onGround) {
      player.coyote = COYOTE_TIME;
      player.airTime = 0;
    } else {
      player.coyote = Math.max(0, player.coyote - dt);
      player.airTime += dt;
    }

    if (player.jumpBuffer > 0 && (player.coyote > 0 || player.inWater)) {
      player.vy = player.inWater ? -4.2 : -CONFIG.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuffer = 0;
      events.push({ type: "jump" });
    }

    if (player.inWater) {
      player.vy += CONFIG.gravity * 0.22 * dt;
      player.vy = Math.min(player.vy, 3.2);
      if (jump && player.vy > -2.6) {
        player.vy = -3.4;
      }
    } else {
      player.vy += CONFIG.gravity * dt;
      player.vy = Math.min(player.vy, CONFIG.maxFallSpeed);
    }

    player.onGround = false;
    resolveHorizontal(world, player, player.vx * dt, events);
    resolveVertical(world, player, player.vy * dt, events);
    clampToWorld(world, player);

    const grounded = overlapsSolid(
      world,
      player.x,
      player.y + 0.06,
      player.width,
      player.height
    );
    if (grounded && player.vy >= 0) {
      if (!player.onGround && player.vy === 0) {
        // A resting contact (for example while walking on a flat floor).
        player.onGround = true;
      }
    }
    if (player.onGround) {
      player.vy = 0;
    }

    player.walk += Math.abs(player.vx) * dt;
    if (player.y > world.height + 4) {
      events.push({ type: "fell" });
    }
    return events;
  }

  function respawn(world, player) {
    const spawn = WORLD.getSpawn(world);
    player.x = spawn.x + 0.5;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.onGround = false;
    return spawn;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    overlapsSolid: overlapsSolid,
    isInWater: isInWater,
    respawn: respawn
  };
});
