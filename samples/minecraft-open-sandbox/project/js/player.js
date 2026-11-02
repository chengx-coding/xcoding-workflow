(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPS = 0.0001;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      facing: 1,
      width: CONFIG.playerWidth,
      height: CONFIG.playerHeight,
      health: CONFIG.maxHealth,
      maxHealth: CONFIG.maxHealth,
      invuln: 0,
      sinceDamage: 99,
      regenTimer: 0,
      coyote: 0,
      jumpBuffer: 0,
      jumpHeld: false,
      walkPhase: 0,
      dead: false
    };
  }

  function bounds(player) {
    return {
      left: player.x - player.width / 2,
      right: player.x + player.width / 2,
      top: player.y - player.height,
      bottom: player.y
    };
  }

  function boxCollidesWorld(world, box) {
    const left = Math.floor(box.left + EPS);
    const right = Math.floor(box.right - EPS);
    const top = Math.floor(box.top + EPS);
    const bottom = Math.floor(box.bottom - EPS);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (!Number.isInteger(x) || !Number.isInteger(y)) {
          continue;
        }
        if (worldApiIsSolid(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  // Kept local so this module has no dependency on world.js at load time; the
  // browser load order supplies SandboxWorld and tests pass a world object with
  // the same isSolid contract.
  function worldApiIsSolid(world, x, y) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return x < 0 || x >= world.width || y >= world.height;
    }
    const block = world.data[y * world.width + x];
    return block !== 0 && block !== CONFIG.blocks.torch;
  }

  function moveAxis(player, world, axis, amount) {
    if (amount === 0) {
      return false;
    }
    const previous = player[axis];
    player[axis] += amount;
    let collided = boxCollidesWorld(world, bounds(player));
    if (!collided) {
      return false;
    }
    const direction = Math.sign(amount);
    let steps = 0;
    while (collided && steps < 200) {
      player[axis] -= direction * 0.01;
      collided = boxCollidesWorld(world, bounds(player));
      steps += 1;
    }
    if (collided) {
      player[axis] = previous;
    }
    return true;
  }

  function update(player, world, input, dt) {
    if (player.dead) {
      return { landed: false, jumped: false, moved: false };
    }
    const left = !!input.left;
    const right = !!input.right;
    const target = (right ? 1 : 0) - (left ? 1 : 0);

    if (target !== 0) {
      player.vx += target * 46 * dt;
      player.facing = target;
    } else {
      const drag = player.onGround ? 42 : 14;
      if (Math.abs(player.vx) <= drag * dt) {
        player.vx = 0;
      } else {
        player.vx -= Math.sign(player.vx) * drag * dt;
      }
    }
    player.vx = Math.max(-CONFIG.moveSpeed, Math.min(CONFIG.moveSpeed, player.vx));

    player.coyote = player.onGround ? CONFIG.coyoteTime : Math.max(0, player.coyote - dt);
    if (input.jumpPressed) {
      player.jumpBuffer = CONFIG.jumpBuffer;
    } else {
      player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);
    }

    if (player.jumpBuffer > 0 && (player.onGround || player.coyote > 0)) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.jumpBuffer = 0;
      player.jumpHeld = true;
    }
    if (input.jump && player.vy < 0 && player.jumpHeld) {
      // Holding jump keeps a little more of the ascent.
      player.vy -= 16 * dt;
    } else if (!input.jump) {
      player.jumpHeld = false;
    }

    player.vy += CONFIG.gravity * dt;
    if (player.vy > CONFIG.maxFall) {
      player.vy = CONFIG.maxFall;
    }

    const wasGrounded = player.onGround;
    const hitX = moveAxis(player, world, "x", player.vx * dt);
    if (hitX) {
      player.vx = 0;
    }
    player.onGround = false;
    const hitY = moveAxis(player, world, "y", player.vy * dt);
    if (hitY) {
      if (player.vy > 0) {
        player.onGround = true;
      }
      player.vy = 0;
    }
    if (!hitY && wasGrounded && player.vy >= 0) {
      // Walking off a ledge.
      player.onGround = false;
    }

    // Standing exactly on a tile: detect support even when no downward step is
    // needed this frame.
    if (!player.onGround && Math.abs(player.vy) < 0.001) {
      const probe = { x: player.x, y: player.y + 0.02, width: player.width, height: player.height };
      const box = bounds(probe);
      const footLeft = Math.floor(box.left + EPS);
      const footRight = Math.floor(box.right - EPS);
      const footRow = Math.floor(box.bottom - EPS);
      for (let x = footLeft; x <= footRight; x += 1) {
        if (worldApiIsSolid(world, x, footRow)) {
          player.onGround = true;
          break;
        }
      }
    }

    if (player.onGround && Math.abs(player.vx) > 0.15) {
      player.walkPhase += Math.abs(player.vx) * dt * 4;
    }

    player.invuln = Math.max(0, player.invuln - dt);
    player.sinceDamage += dt;
    if (player.sinceDamage > CONFIG.regenDelay && player.health < player.maxHealth) {
      player.regenTimer += dt;
      if (player.regenTimer >= CONFIG.regenInterval) {
        player.regenTimer = 0;
        player.health += 1;
      }
    } else {
      player.regenTimer = 0;
    }

    return { landed: player.onGround && !wasGrounded, jumped: player.vy < 0, moved: target !== 0 };
  }

  function damage(player, amount) {
    if (player.dead || player.invuln > 0) {
      return false;
    }
    player.health = Math.max(0, player.health - amount);
    player.invuln = CONFIG.invulnTime;
    player.sinceDamage = 0;
    player.regenTimer = 0;
    if (player.health <= 0) {
      player.dead = true;
    }
    return true;
  }

  function respawn(player, spawn) {
    player.x = spawn.x;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.health = player.maxHealth;
    player.dead = false;
    player.invuln = CONFIG.invulnTime;
    player.sinceDamage = 99;
    player.onGround = false;
  }

  function center(player) {
    return { x: player.x, y: player.y - player.height / 2 };
  }

  function distanceToTile(player, tx, ty) {
    const mid = center(player);
    const dx = tx + 0.5 - mid.x;
    const dy = ty + 0.5 - mid.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function canReach(player, tx, ty, reach) {
    return distanceToTile(player, tx, ty) <= (reach || CONFIG.reach);
  }

  function overlapsTile(player, tx, ty) {
    const box = bounds(player);
    return box.right > tx && box.left < tx + 1 && box.bottom > ty && box.top < ty + 1;
  }

  function overlapsEntity(player, entity) {
    const box = bounds(player);
    const left = entity.x - (entity.width || 0.8) / 2;
    const right = entity.x + (entity.width || 0.8) / 2;
    const bottom = entity.y;
    const top = entity.y - (entity.height || 1.4);
    return box.right > left && box.left < right && box.bottom > top && box.top < bottom;
  }

  function serialize(player) {
    return { x: player.x, y: player.y, health: player.health };
  }

  function applySaved(player, saved) {
    if (!saved) {
      return player;
    }
    if (typeof saved.x === "number") {
      player.x = saved.x;
    }
    if (typeof saved.y === "number") {
      player.y = saved.y;
    }
    if (typeof saved.health === "number") {
      player.health = Math.max(1, Math.min(player.maxHealth, saved.health));
    }
    player.vx = 0;
    player.vy = 0;
    player.onGround = false;
    player.dead = false;
    return player;
  }

  return {
    createPlayer: createPlayer,
    bounds: bounds,
    boxCollidesWorld: boxCollidesWorld,
    update: update,
    damage: damage,
    respawn: respawn,
    center: center,
    distanceToTile: distanceToTile,
    canReach: canReach,
    overlapsTile: overlapsTile,
    overlapsEntity: overlapsEntity,
    serialize: serialize,
    applySaved: applySaved
  };
});
