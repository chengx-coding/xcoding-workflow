(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./content.js"));
  } else {
    root.MosswildPlayer = factory(root.MosswildConfig, root.MosswildContent);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, CONTENT) {
  "use strict";

  const PLAYER = CONFIG.player;
  const STEP_EPSILON = 0.001;

  function createPlayer(spawn) {
    const x = spawn && Number.isFinite(spawn.x) ? spawn.x : 2;
    const y = spawn && Number.isFinite(spawn.y) ? spawn.y : 20;
    return {
      x,
      y,
      vx: 0,
      vy: 0,
      width: PLAYER.width,
      height: PLAYER.height,
      onGround: false,
      facing: 1,
      health: CONFIG.maxHealth,
      maxHealth: CONFIG.maxHealth,
      invulnerable: 0,
      hurtTimer: 0,
      coyote: 0,
      jumpBuffer: 0,
      airTime: 0,
      minAirY: y,
      sinceDamage: 0,
      stepDistance: 0,
      walkPhase: 0,
      swing: 0,
      dead: false
    };
  }

  function collidesWorld(world, x, y, width, height) {
    const left = Math.floor(x - width / 2 + STEP_EPSILON);
    const right = Math.floor(x + width / 2 - STEP_EPSILON);
    const top = Math.floor(y - height + STEP_EPSILON);
    const bottom = Math.floor(y - STEP_EPSILON);
    for (let ty = top; ty <= bottom; ty += 1) {
      for (let tx = left; tx <= right; tx += 1) {
        if (tx < 0 || tx >= world.width || ty >= world.height) {
          return true;
        }
        if (ty < 0) {
          continue;
        }
        const block = world.data[ty * world.width + tx];
        if (CONTENT.getBlockDef(block).solid) {
          return true;
        }
      }
    }
    return false;
  }

  function moveHorizontal(body, world, distance) {
    if (distance === 0) {
      return true;
    }
    const steps = Math.max(1, Math.ceil(Math.abs(distance) / 0.2));
    const step = distance / steps;
    for (let i = 0; i < steps; i += 1) {
      const nextX = body.x + step;
      if (collidesWorld(world, nextX, body.y, body.width, body.height)) {
        body.vx = 0;
        return false;
      }
      body.x = nextX;
    }
    return true;
  }

  function moveVertical(body, world, distance) {
    if (distance === 0) {
      return 0;
    }
    const direction = Math.sign(distance);
    const steps = Math.max(1, Math.ceil(Math.abs(distance) / 0.2));
    const step = distance / steps;
    for (let i = 0; i < steps; i += 1) {
      const nextY = body.y + step;
      if (!collidesWorld(world, body.x, nextY, body.width, body.height)) {
        body.y = nextY;
        continue;
      }
      // Resolve the collision precisely so the player stands exactly on a
      // ledge instead of floating a few pixels above it.
      let low = body.y;
      let high = nextY;
      for (let pass = 0; pass < 10; pass += 1) {
        const middle = (low + high) / 2;
        if (collidesWorld(world, body.x, middle, body.width, body.height)) {
          high = middle;
        } else {
          low = middle;
        }
      }
      body.y = low;
      body.vy = 0;
      return direction;
    }
    return 0;
  }

  function isGrounded(world, x, y, width) {
    const left = Math.floor(x - width / 2 + STEP_EPSILON);
    const right = Math.floor(x + width / 2 - STEP_EPSILON);
    const footCell = Math.floor(y + 0.04 - STEP_EPSILON);
    if (footCell >= world.height) {
      return true;
    }
    if (footCell < 0) {
      return false;
    }
    for (let tx = left; tx <= right; tx += 1) {
      if (tx < 0 || tx >= world.width) {
        return true;
      }
      if (CONTENT.getBlockDef(world.data[footCell * world.width + tx]).solid) {
        return true;
      }
    }
    return false;
  }

  function applyDamage(player, amount, hooks) {
    if (player.dead || amount <= 0 || player.invulnerable > 0) {
      return false;
    }
    player.health = Math.max(0, player.health - amount);
    player.invulnerable = 0.85;
    player.hurtTimer = 0.4;
    player.sinceDamage = 0;
    if (player.health <= 0) {
      player.dead = true;
    }
    if (hooks && hooks.onHurt) {
      hooks.onHurt(amount);
    }
    return true;
  }

  function healPlayer(player, amount) {
    if (player.dead) {
      return;
    }
    player.health = Math.max(0, Math.min(player.maxHealth, player.health + amount));
  }

  function resetPlayer(player, spawn) {
    player.x = spawn.x;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.health = player.maxHealth;
    player.invulnerable = 1.1;
    player.hurtTimer = 0;
    player.onGround = false;
    player.airTime = 0;
    player.minAirY = spawn.y;
    player.sinceDamage = 0;
    player.dead = false;
    player.facing = 1;
    player.swing = 0;
  }

  function updatePlayer(player, world, input, dt, hooks) {
    const events = [];
    player.invulnerable = Math.max(0, player.invulnerable - dt);
    player.hurtTimer = Math.max(0, player.hurtTimer - dt);
    player.swing = Math.max(0, player.swing - dt);
    player.sinceDamage += dt;

    if (player.dead) {
      player.vx = 0;
      player.vy = Math.min(24, player.vy + PLAYER.gravity * dt);
      moveVertical(player, world, player.vy * dt);
      return events;
    }

    if (input.jumpPressed) {
      player.jumpBuffer = PLAYER.jumpBuffer;
    }
    player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);
    if (player.onGround) {
      player.coyote = PLAYER.coyoteTime;
    } else {
      player.coyote = Math.max(0, player.coyote - dt);
    }

    if (player.jumpBuffer > 0 && player.coyote > 0) {
      player.vy = -PLAYER.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuffer = 0;
      events.push({ type: "jump" });
      if (hooks && hooks.onJump) {
        hooks.onJump();
      }
    }

    const direction = (input.right ? 1 : 0) - (input.left ? 1 : 0);
    if (direction !== 0) {
      player.facing = direction;
      const targetSpeed = input.sprint ? PLAYER.sprintSpeed : PLAYER.walkSpeed;
      const acceleration = (player.onGround ? PLAYER.groundAcceleration : PLAYER.airAcceleration) * dt;
      player.vx += Math.max(-acceleration, Math.min(acceleration, direction * targetSpeed - player.vx));
    } else {
      const deceleration = (player.onGround ? PLAYER.friction : PLAYER.airAcceleration * 0.55) * dt;
      if (Math.abs(player.vx) <= deceleration) {
        player.vx = 0;
      } else {
        player.vx -= Math.sign(player.vx) * deceleration;
      }
    }

    if (input.aimFacing && !direction) {
      player.facing = input.aimFacing;
    }

    // Extra gravity while rising with the jump key released gives a snappy,
    // controllable short hop without changing the full jump height.
    let gravity = PLAYER.gravity;
    if (player.vy < 0 && !input.jumpHeld) {
      gravity *= 1.9;
    }
    player.vy = Math.min(24, player.vy + gravity * dt);

    const wasOnGround = player.onGround;
    moveHorizontal(player, world, player.vx * dt);
    const halfWidth = player.width / 2;
    if (player.x < halfWidth) {
      player.x = halfWidth;
      player.vx = 0;
    } else if (player.x > world.width - halfWidth) {
      player.x = world.width - halfWidth;
      player.vx = 0;
    }

    player.onGround = false;
    const verticalHit = moveVertical(player, world, player.vy * dt);
    if (verticalHit > 0) {
      player.onGround = true;
    }

    if (player.onGround) {
      if (!wasOnGround && player.airTime > 0.12) {
        const fallDistance = Math.max(0, player.y - player.minAirY);
        events.push({ type: "land", fallDistance });
        if (hooks && hooks.onLand) {
          hooks.onLand(fallDistance);
        }
        if (fallDistance > PLAYER.fallSafe) {
          const damage = Math.max(1, Math.round((fallDistance - PLAYER.fallSafe) * 1.6));
          if (applyDamage(player, damage, hooks)) {
            events.push({ type: "fall-damage", amount: damage });
          }
        }
      }
      player.airTime = 0;
      player.minAirY = player.y;
      const speed = Math.abs(player.vx);
      if (speed > 0.4) {
        player.walkPhase += speed * dt * 2.2;
        player.stepDistance += speed * dt;
        if (player.stepDistance > 0.7) {
          player.stepDistance = 0;
          if (hooks && hooks.onStep) {
            hooks.onStep(world);
          }
        }
      }
    } else {
      player.airTime += dt;
      player.minAirY = Math.min(player.minAirY, player.y);
    }

    if (player.sinceDamage > 14 && player.health > 0 && player.health < player.maxHealth) {
      const before = player.health;
      player.health = Math.min(player.maxHealth, player.health + dt * 0.22);
      if (before < player.health && hooks && hooks.onHeal && Math.floor(before) !== Math.floor(player.health)) {
        hooks.onHeal();
      }
    }

    return events;
  }

  return {
    createPlayer,
    updatePlayer,
    resetPlayer,
    damagePlayer: applyDamage,
    healPlayer,
    collidesWorld,
    moveHorizontal,
    moveVertical,
    isGrounded
  };
});
