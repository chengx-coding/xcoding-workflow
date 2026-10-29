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

  const EPS = 1e-6;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      width: CONFIG.playerWidth,
      height: CONFIG.playerHeight,
      facing: 1,
      coyote: 0,
      jumpBuffer: 0,
      jumpHeld: false,
      animTime: 0,
      moving: false,
      justLanded: false,
      steps: 0
    };
  }

  function approach(value, target, delta) {
    if (value < target) {
      return Math.min(value + delta, target);
    }
    return Math.max(value - delta, target);
  }

  function box(player) {
    return WORLD.rectOf(player);
  }

  function moveX(player, world, amount) {
    if (!amount) {
      return false;
    }
    player.x += amount;
    const rect = box(player);
    const y0 = Math.floor(rect.top + EPS);
    const y1 = Math.floor(rect.bottom - EPS);
    const x0 = Math.floor(rect.left + EPS);
    const x1 = Math.floor(rect.right - EPS);
    let hit = false;
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        if (!WORLD.isSolid(world, x, y)) {
          continue;
        }
        hit = true;
        if (amount > 0) {
          player.x = Math.min(player.x, x - player.width / 2 - EPS);
        } else {
          player.x = Math.max(player.x, x + 1 + player.width / 2 + EPS);
        }
      }
    }
    if (hit) {
      player.vx = 0;
    }
    return hit;
  }

  function moveY(player, world, amount) {
    player.onGround = false;
    if (!amount) {
      return false;
    }
    player.y += amount;
    const rect = box(player);
    const x0 = Math.floor(rect.left + EPS);
    const x1 = Math.floor(rect.right - EPS);
    const y0 = Math.floor(rect.top + EPS);
    const y1 = Math.floor(rect.bottom - EPS);
    let hit = false;
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        if (!WORLD.isSolid(world, x, y)) {
          continue;
        }
        hit = true;
        if (amount > 0) {
          player.y = Math.min(player.y, y - EPS);
          player.onGround = true;
        } else {
          player.y = Math.max(player.y, y + 1 + player.height + EPS);
        }
      }
    }
    if (hit) {
      player.vy = 0;
    }
    return hit;
  }

  function stepPlayer(player, world, input, dt) {
    const step = Math.min(Math.max(typeof dt === "number" ? dt : 0, 0), 1 / 20);
    const controls = input || {};
    const events = { jumped: false, landed: false, hitWall: false, hitCeiling: false };

    const direction = (controls.right ? 1 : 0) - (controls.left ? 1 : 0);
    if (direction !== 0) {
      player.facing = direction;
    }

    const targetVelocity = direction * CONFIG.moveSpeed;
    const acceleration = player.onGround ? CONFIG.groundAccel : CONFIG.airAccel;
    player.vx = approach(player.vx, targetVelocity, acceleration * step);
    if (direction === 0) {
      const friction = player.onGround ? CONFIG.groundFriction : CONFIG.airAccel * 0.4;
      player.vx = approach(player.vx, 0, friction * step);
    }

    const jump = Boolean(controls.jump);
    if (jump && !player.jumpHeld) {
      player.jumpBuffer = CONFIG.jumpBuffer;
    }
    player.jumpHeld = jump;
    player.jumpBuffer = Math.max(0, player.jumpBuffer - step);

    if (player.onGround) {
      player.coyote = CONFIG.coyoteTime;
    } else {
      player.coyote = Math.max(0, player.coyote - step);
    }

    if (player.jumpBuffer > 0 && player.coyote > 0) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuffer = 0;
      events.jumped = true;
    }

    player.vy = Math.min(CONFIG.maxFall, player.vy + CONFIG.gravity * step);
    if (!jump && player.vy < -CONFIG.jumpSpeed * 0.45) {
      player.vy += CONFIG.gravity * 1.15 * step;
    }

    const wasGrounded = player.onGround;
    events.hitWall = moveX(player, world, player.vx * step);
    const yBefore = player.y;
    const verticalHit = moveY(player, world, player.vy * step);
    if (verticalHit && player.y < yBefore) {
      events.hitCeiling = true;
    }
    if (!wasGrounded && player.onGround) {
      events.landed = true;
    }

    player.x = Math.min(Math.max(player.x, player.width / 2), world.width - player.width / 2);
    player.y = Math.min(player.y, world.height - EPS);
    player.justLanded = events.landed;
    player.moving = Math.abs(player.vx) > 0.15;
    player.animTime += step * (player.moving ? 11 : 2.2);
    player.steps += 1;
    return events;
  }

  function serializePlayer(player) {
    return {
      x: Number(player.x.toFixed(4)),
      y: Number(player.y.toFixed(4)),
      vx: Number((player.vx || 0).toFixed(4)),
      vy: Number((player.vy || 0).toFixed(4)),
      facing: player.facing < 0 ? -1 : 1
    };
  }

  function restorePlayer(data, fallbackX, fallbackY) {
    if (data && Number.isFinite(data.x) && Number.isFinite(data.y)) {
      const player = createPlayer(data.x, data.y);
      player.vx = Number.isFinite(data.vx) ? data.vx : 0;
      player.vy = Number.isFinite(data.vy) ? data.vy : 0;
      player.facing = data.facing < 0 ? -1 : 1;
      return player;
    }
    return createPlayer(fallbackX, fallbackY);
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    serializePlayer: serializePlayer,
    restorePlayer: restorePlayer,
    box: box
  };
});
