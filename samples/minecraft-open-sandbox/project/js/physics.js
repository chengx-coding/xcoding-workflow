(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPhysics = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPSILON = 0.0001;
  const STEP_SIZE = 0.2;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      width: CONFIG.playerWidth,
      height: CONFIG.playerHeight,
      onGround: false,
      facing: 1,
      coyote: 0,
      jumpHeld: false,
      fallPeak: y,
      fallDistance: 0,
      health: CONFIG.maxHealth,
      hurtCooldown: 0,
      walkTime: 0,
      walkDistance: 0,
      swing: 0
    };
  }

  function solidAt(world, tileX, tileY) {
    if (tileX < 0 || tileX >= world.width) {
      return true;
    }
    if (tileY < 0) {
      return false;
    }
    if (tileY >= world.height) {
      return true;
    }
    const block = world.data[tileY * world.width + tileX];
    const definition = CONFIG.blockDefs[block];
    return !!(definition && definition.solid);
  }

  function tileRangeForX(player) {
    return {
      left: Math.floor(player.x - player.width / 2 + EPSILON),
      right: Math.floor(player.x + player.width / 2 - EPSILON)
    };
  }

  function tileRangeForY(player) {
    return {
      top: Math.floor(player.y - player.height + EPSILON),
      bottom: Math.floor(player.y - EPSILON)
    };
  }

  function moveHorizontal(player, world, amount) {
    if (amount === 0) {
      return false;
    }
    player.x += amount;
    const xRange = tileRangeForX(player);
    const yRange = tileRangeForY(player);
    let collided = false;
    if (amount > 0) {
      const tile = xRange.right;
      for (let y = yRange.top; y <= yRange.bottom; y += 1) {
        if (solidAt(world, tile, y)) {
          player.x = tile - player.width / 2 - EPSILON;
          player.vx = 0;
          collided = true;
          break;
        }
      }
    } else {
      const tile = xRange.left;
      for (let y = yRange.top; y <= yRange.bottom; y += 1) {
        if (solidAt(world, tile, y)) {
          player.x = tile + 1 + player.width / 2 + EPSILON;
          player.vx = 0;
          collided = true;
          break;
        }
      }
    }
    return collided;
  }

  function moveVertical(player, world, amount) {
    if (amount === 0) {
      return { collided: false, landed: false, hitCeiling: false };
    }
    player.y += amount;
    const xRange = tileRangeForX(player);
    const yRange = tileRangeForY(player);
    if (amount > 0) {
      const tile = yRange.bottom;
      for (let x = xRange.left; x <= xRange.right; x += 1) {
        if (solidAt(world, x, tile)) {
          player.y = tile - EPSILON;
          player.vy = 0;
          player.onGround = true;
          return { collided: true, landed: true, hitCeiling: false };
        }
      }
    } else {
      const tile = yRange.top;
      for (let x = xRange.left; x <= xRange.right; x += 1) {
        if (solidAt(world, x, tile)) {
          player.y = tile + 1 + player.height + EPSILON;
          player.vy = 0;
          return { collided: true, landed: false, hitCeiling: true };
        }
      }
    }
    return { collided: false, landed: false, hitCeiling: false };
  }

  function approach(value, target, amount) {
    if (value < target) {
      return Math.min(target, value + amount);
    }
    return Math.max(target, value - amount);
  }

  function stepPlayer(player, world, input, dt) {
    const step = Math.max(0.0001, Math.min(dt || 1 / 60, 0.05));
    const controlling = input || {};
    const left = !!controlling.left;
    const right = !!controlling.right;
    const direction = (right ? 1 : 0) - (left ? 1 : 0);
    const sprinting = !!controlling.sprint && direction !== 0;
    const speed = sprinting ? CONFIG.sprintSpeed : CONFIG.moveSpeed;
    const targetSpeed = direction * speed;
    const acceleration = player.onGround ? 52 : 30;
    player.vx = approach(player.vx, targetSpeed, acceleration * step);
    if (direction !== 0) {
      player.facing = direction;
      player.walkDistance += Math.abs(player.vx) * step;
      player.walkTime += step * (sprinting ? 1.55 : 1);
    }

    const wasOnGround = player.onGround;
    if (player.onGround) {
      player.coyote = 0.11;
      player.fallPeak = player.y;
    } else {
      player.coyote = Math.max(0, player.coyote - step);
    }

    let jumped = false;
    if (controlling.jump && !player.jumpHeld && (player.onGround || player.coyote > 0)) {
      player.vy = -CONFIG.jumpSpeed;
      player.onGround = false;
      player.coyote = 0;
      player.fallPeak = player.y;
      jumped = true;
    }
    player.jumpHeld = !!controlling.jump;

    if (!player.onGround) {
      player.fallPeak = Math.min(player.fallPeak, player.y);
    }

    player.vy = Math.min(34, player.vy + CONFIG.gravity * step);
    player.onGround = false;

    const totalX = player.vx * step;
    const totalY = player.vy * step;
    const steps = Math.max(1, Math.ceil(Math.max(Math.abs(totalX), Math.abs(totalY)) / STEP_SIZE));
    let landed = false;
    let hitCeiling = false;
    let collidedX = false;
    for (let index = 0; index < steps; index += 1) {
      if (moveHorizontal(player, world, totalX / steps)) {
        collidedX = true;
      }
      const vertical = moveVertical(player, world, totalY / steps);
      if (vertical.collided) {
        if (vertical.landed) {
          landed = true;
        }
        if (vertical.hitCeiling) {
          hitCeiling = true;
        }
      }
    }

    let fallDistance = 0;
    if (landed) {
      fallDistance = Math.max(0, player.y - player.fallPeak);
      player.fallDistance = fallDistance;
      player.fallPeak = player.y;
      player.coyote = 0.11;
    }

    if (player.onGround) {
      player.coyote = 0.11;
      if (wasOnGround && !jumped) {
        player.fallDistance = 0;
      }
    }

    if (player.hurtCooldown > 0) {
      player.hurtCooldown = Math.max(0, player.hurtCooldown - step);
    }

    return {
      jumped: jumped,
      landed: landed,
      fallDistance: fallDistance,
      collidedX: collidedX,
      hitCeiling: hitCeiling
    };
  }

  function fallDamage(distance) {
    if (!Number.isFinite(distance) || distance <= CONFIG.fallSafeDistance) {
      return 0;
    }
    return Math.max(1, Math.floor((distance - CONFIG.fallSafeDistance) * 0.9));
  }

  function damagePlayer(player, amount) {
    const damage = Math.max(0, Math.floor(amount || 0));
    if (damage <= 0) {
      return 0;
    }
    player.health = Math.max(0, player.health - damage);
    player.hurtCooldown = 0.55;
    return damage;
  }

  function healPlayer(player, amount) {
    const before = player.health;
    player.health = Math.min(CONFIG.maxHealth, player.health + Math.max(0, amount || 0));
    return player.health - before;
  }

  function respawnPlayer(player, spawn) {
    player.x = spawn.x;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.health = CONFIG.maxHealth;
    player.onGround = false;
    player.fallPeak = spawn.y;
    player.fallDistance = 0;
    player.hurtCooldown = 0;
    return player;
  }

  function overlapsTile(player, tileX, tileY) {
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return right > tileX && left < tileX + 1 && bottom > tileY && top < tileY + 1;
  }

  function inReach(player, tileX, tileY, reach) {
    const centerX = tileX + 0.5;
    const centerY = tileY + 0.5;
    const playerX = player.x;
    const playerY = player.y - player.height / 2;
    const dx = centerX - playerX;
    const dy = centerY - playerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    return distance <= (reach === undefined ? CONFIG.reach : reach);
  }

  function isOnGroundAt(player, world) {
    const left = Math.floor(player.x - player.width / 2 + EPSILON);
    const right = Math.floor(player.x + player.width / 2 - EPSILON);
    const tileY = Math.floor(player.y + 0.02);
    for (let x = left; x <= right; x += 1) {
      if (solidAt(world, x, tileY)) {
        return true;
      }
    }
    return false;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    fallDamage: fallDamage,
    damagePlayer: damagePlayer,
    healPlayer: healPlayer,
    respawnPlayer: respawnPlayer,
    overlapsTile: overlapsTile,
    inReach: inReach,
    isOnGroundAt: isOnGroundAt,
    solidAt: solidAt
  };
});
