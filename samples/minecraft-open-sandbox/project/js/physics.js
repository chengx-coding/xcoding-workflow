(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxPhysics = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  if (!CONFIG || !WORLD) {
    throw new Error("SandboxConfig and SandboxWorld are required before SandboxPhysics");
  }

  const EPSILON = 0.0001;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      width: 0.62,
      height: 1.78,
      coyote: 0,
      jumpBuffer: 0,
      health: 20,
      maxHealth: 20,
      lastImpact: 0,
      justJumped: false,
      facing: 1,
      walkPhase: 0
    };
  }

  function boxOf(x, y, width, height) {
    return {
      left: x - width / 2,
      right: x + width / 2,
      top: y - height,
      bottom: y
    };
  }

  function collidesBox(world, box) {
    const firstX = Math.floor(box.left + EPSILON);
    const lastX = Math.floor(box.right - EPSILON);
    const firstY = Math.floor(box.top + EPSILON);
    const lastY = Math.floor(box.bottom - EPSILON);
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        if (WORLD.isSolid(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  function collidesAt(world, player, x, y) {
    return collidesBox(world, boxOf(x, y, player.width, player.height));
  }

  function approach(value, target, delta) {
    if (value < target) {
      return Math.min(value + delta, target);
    }
    if (value > target) {
      return Math.max(value - delta, target);
    }
    return target;
  }

  function settle(player, world) {
    let guard = 0;
    while (collidesAt(world, player, player.x, player.y) && guard < 40) {
      player.y -= 1;
      guard += 1;
    }
    return player;
  }

  function stepPlayer(player, world, input, dt) {
    const controls = input || {};
    const step = Math.min(Math.max(dt || 0, 0), 0.05);
    const wasOnGround = player.onGround;
    player.lastImpact = 0;
    player.justJumped = false;

    const direction = (controls.right ? 1 : 0) - (controls.left ? 1 : 0);
    if (direction !== 0) {
      player.facing = direction;
    }
    const targetSpeed = direction * CONFIG.moveSpeed;
    const acceleration = player.onGround ? 62 : 34;
    player.vx = approach(player.vx, targetSpeed, acceleration * step);
    if (direction === 0 && player.onGround) {
      player.vx = approach(player.vx, 0, 70 * step);
    }

    if (controls.jump) {
      player.jumpBuffer = 0.12;
    } else {
      player.jumpBuffer = Math.max(0, player.jumpBuffer - step);
    }
    if (player.onGround) {
      player.coyote = 0.1;
    } else {
      player.coyote = Math.max(0, player.coyote - step);
    }
    if (player.jumpBuffer > 0 && player.coyote > 0) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
      player.jumpBuffer = 0;
      player.coyote = 0;
      player.justJumped = true;
    }

    player.vy = Math.min(player.vy + CONFIG.gravity * step, CONFIG.maxFallSpeed);

    const nextX = player.x + player.vx * step;
    if (!collidesAt(world, player, nextX, player.y)) {
      player.x = nextX;
    } else if (
      player.onGround &&
      !collidesAt(world, player, nextX, player.y - 1) &&
      !collidesAt(world, player, player.x, player.y - 1)
    ) {
      // Climb a single-tile ledge instead of stopping dead on every bump.
      player.x = nextX;
      player.y -= 1;
    } else {
      player.vx = 0;
    }

    const nextY = player.y + player.vy * step;
    if (!collidesAt(world, player, player.x, nextY)) {
      player.y = nextY;
      player.onGround = false;
    } else if (player.vy > 0) {
      const impact = player.vy;
      player.y = Math.floor(nextY);
      player.vy = 0;
      player.onGround = true;
      // Standing still re-collides every frame with a tiny gravity step; only
      // report a real landing so fall damage and landing feedback stay honest.
      player.lastImpact = wasOnGround && impact < 3 ? 0 : impact;
    } else if (player.vy < 0) {
      player.y = Math.floor(nextY - player.height) + 1 + player.height;
      player.vy = 0;
    }

    if (!player.onGround && !collidesAt(world, player, player.x, player.y + 0.02)) {
      player.onGround = false;
    } else if (collidesAt(world, player, player.x, player.y + 0.02)) {
      player.onGround = true;
    }

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

    if (Math.abs(player.vx) > 0.2 && player.onGround) {
      player.walkPhase += step * Math.abs(player.vx) * 1.4;
    }

    return player;
  }

  function fallDamage(impact) {
    if (impact < 19) {
      return 0;
    }
    return Math.min(Math.floor((impact - 19) / 3) + 1, 10);
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    fallDamage: fallDamage,
    collidesAt: collidesAt,
    collidesBox: collidesBox,
    settle: settle,
    boxOf: boxOf
  };
});
