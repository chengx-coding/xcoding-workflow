/* Player physics, collision and block interaction rules. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  const B = CONFIG.blocks;

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      width: 0.68,
      height: 1.8,
      onGround: false,
      inWater: false,
      onLadder: false,
      facing: 1,
      moving: false,
      walkTime: 0,
      swing: 0,
      health: 20,
      maxHealth: 20,
      hunger: 20,
      maxHunger: 20,
      saturation: 5,
      exhaustion: 0,
      air: 10,
      maxAir: 10,
      regenTimer: 0,
      starveTimer: 0,
      hurtCooldown: 0,
      dead: false,
      fallStartY: y,
      fallDistance: 0,
      mining: null,
      jumpHeld: false,
      spawnX: x,
      spawnY: y
    };
  }

  function overlapsSolid(world, cx, feetY, width, height) {
    const left = Math.floor(cx - width / 2 + 0.001);
    const right = Math.floor(cx + width / 2 - 0.001);
    const top = Math.floor(feetY - height + 0.001);
    const bottom = Math.floor(feetY - 0.001);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (WORLD.isSolid(world, x, y)) {
          return true;
        }
      }
    }
    return false;
  }

  function overlapsBlock(world, cx, feetY, width, height, block) {
    const left = Math.floor(cx - width / 2 + 0.001);
    const right = Math.floor(cx + width / 2 - 0.001);
    const top = Math.floor(feetY - height + 0.001);
    const bottom = Math.floor(feetY - 0.001);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (WORLD.getBlock(world, x, y) === block) {
          return true;
        }
      }
    }
    return false;
  }

  function moveX(world, player, delta) {
    if (delta === 0) {
      return false;
    }
    const steps = Math.max(1, Math.ceil(Math.abs(delta) / 0.05));
    const step = delta / steps;
    for (let i = 0; i < steps; i += 1) {
      const nx = player.x + step;
      if (overlapsSolid(world, nx, player.y, player.width, player.height)) {
        player.vx = 0;
        return true;
      }
      player.x = nx;
    }
    return false;
  }

  function moveY(world, player, delta) {
    if (delta === 0) {
      return false;
    }
    const steps = Math.max(1, Math.ceil(Math.abs(delta) / 0.05));
    const step = delta / steps;
    for (let i = 0; i < steps; i += 1) {
      const ny = player.y + step;
      if (overlapsSolid(world, player.x, ny, player.width, player.height)) {
        if (step > 0) {
          player.onGround = true;
        }
        player.vy = 0;
        return true;
      }
      player.y = ny;
    }
    return false;
  }

  function approach(value, target, amount) {
    if (value < target) {
      return Math.min(value + amount, target);
    }
    if (value > target) {
      return Math.max(value - amount, target);
    }
    return target;
  }

  function stepPlayer(player, world, input, dt) {
    const wasGround = player.onGround;
    const inWater = overlapsBlock(world, player.x, player.y, player.width, player.height, B.water);
    const onLadder = overlapsBlock(world, player.x, player.y, player.width, player.height, B.ladder);
    player.inWater = inWater;
    player.onLadder = onLadder;

    const moving = Boolean(input.left || input.right);
    const sprinting = Boolean(input.sprint && moving && player.hunger > 6 && !inWater);
    const speed = inWater ? CONFIG.swimSpeed : sprinting ? CONFIG.sprintSpeed : CONFIG.moveSpeed;
    const direction = (input.right ? 1 : 0) - (input.left ? 1 : 0);
    if (direction !== 0) {
      player.facing = direction;
    }
    const accel = player.onGround ? 60 : 28;
    player.vx = approach(player.vx, direction * speed, accel * dt);
    if (direction === 0 && player.onGround) {
      player.vx = approach(player.vx, 0, 70 * dt);
    }

    if (inWater) {
      player.vy += CONFIG.gravity * 0.18 * dt;
      player.vy = Math.min(player.vy, 4.5);
      if (input.jump) {
        player.vy = -CONFIG.swimSpeed;
      }
    } else {
      player.vy += CONFIG.gravity * dt;
      player.vy = Math.min(player.vy, CONFIG.maxFallSpeed);
    }

    if (onLadder) {
      player.vy = input.up ? -4.2 : input.down ? 4.2 : Math.min(player.vy, 1.5);
      if (input.jump) {
        player.vy = -5.5;
      }
    } else if (input.jump && !player.jumpHeld && (player.onGround || inWater)) {
      player.vy = inWater ? -CONFIG.swimSpeed : -CONFIG.jumpSpeed;
      player.onGround = false;
    }
    player.jumpHeld = Boolean(input.jump);

    if (!wasGround && player.onGround) {
      player.fallDistance = Math.max(0, player.y - player.fallStartY);
      player.fallStartY = player.y;
    } else if (player.onGround) {
      player.fallStartY = player.y;
      player.fallDistance = 0;
    } else if (player.vy < 0) {
      player.fallStartY = Math.min(player.fallStartY, player.y);
    }

    player.onGround = false;
    moveX(world, player, player.vx * dt);
    moveY(world, player, player.vy * dt);
    if (!overlapsSolid(world, player.x, player.y + 0.04, player.width, player.height)) {
      player.onGround = false;
    }

    // Keep the body inside the map even when the edge has no wall.
    player.x = Math.max(player.width / 2 + 0.2, Math.min(world.width - player.width / 2 - 0.2, player.x));
    player.y = Math.min(world.height - 0.05, player.y);
    if (player.y < 1) {
      player.y = 1;
      player.vy = Math.max(0, player.vy);
    }

    player.moving = moving && Math.abs(player.vx) > 0.2;
    player.sprinting = sprinting;
    if (player.moving) {
      player.walkTime += dt * (sprinting ? 12 : 8);
    }
    if (player.swing > 0) {
      player.swing = Math.max(0, player.swing - dt * 4.5);
    }
    if (player.hurtCooldown > 0) {
      player.hurtCooldown = Math.max(0, player.hurtCooldown - dt);
    }
    return player;
  }

  function playerOverlapsTile(player, x, y) {
    const left = player.x - player.width / 2;
    const right = player.x + player.width / 2;
    const top = player.y - player.height;
    const bottom = player.y;
    return right > x && left < x + 1 && bottom > y && top < y + 1;
  }

  function canReach(player, x, y) {
    const dx = x + 0.5 - player.x;
    const dy = y + 0.5 - (player.y - player.height * 0.5);
    return Math.sqrt(dx * dx + dy * dy) <= CONFIG.reach;
  }

  function miningSpeedFor(block, tool) {
    const def = CONFIG.blockDefs[block];
    if (!def || !Number.isFinite(def.hardness) || def.hardness <= 0) {
      return 0;
    }
    let multiplier = CONFIG.baseMiningSpeed;
    if (tool && def.tool && tool.tool === def.tool) {
      multiplier *= tool.speed;
    }
    return multiplier / def.hardness;
  }

  function updateMining(player, target, dt, tool) {
    if (!target) {
      player.mining = null;
      return { done: false, progress: 0 };
    }
    const key = target.x + ":" + target.y;
    if (!player.mining || player.mining.key !== key) {
      player.mining = { key: key, x: target.x, y: target.y, progress: 0, total: 1 };
    }
    const speed = miningSpeedFor(target.block, tool);
    if (speed <= 0) {
      player.mining = null;
      return { done: false, progress: 0, invalid: true };
    }
    player.mining.progress += speed * dt;
    player.mining.total = 1;
    player.swing = 1;
    if (player.mining.progress >= 1) {
      player.mining = null;
      return { done: true, progress: 1 };
    }
    return { done: false, progress: player.mining.progress };
  }

  function validatePlacement(world, player, x, y, block) {
    const def = CONFIG.blockDefs[block];
    if (!def || block === B.air) {
      return { ok: false, reason: "Nothing to place" };
    }
    if (!WORLD.isReplaceable(world, x, y)) {
      return { ok: false, reason: "That space is occupied" };
    }
    if (!canReach(player, x, y)) {
      return { ok: false, reason: "Too far away" };
    }
    if (def.solid && playerOverlapsTile(player, x, y)) {
      return { ok: false, reason: "The player is in the way" };
    }
    const neighbours = [
      [x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]
    ];
    let supported = false;
    for (const pair of neighbours) {
      if (WORLD.isSolid(world, pair[0], pair[1])) {
        supported = true;
        break;
      }
    }
    if (!supported) {
      return { ok: false, reason: "Needs a neighbouring block" };
    }
    if (block === B.torch || block === B.flower || block === B.tallGrass) {
      if (!WORLD.isSolid(world, x, y + 1)) {
        return { ok: false, reason: "Needs ground beneath it" };
      }
    }
    return { ok: true, reason: "" };
  }

  function damagePlayer(player, amount, cause) {
    if (player.health <= 0) {
      return 0;
    }
    const applied = Math.max(0, Math.floor(amount));
    player.health = Math.max(0, player.health - applied);
    player.hurtCooldown = 0.5;
    player.lastDamageCause = cause || "damage";
    if (player.health <= 0) {
      player.dead = true;
    }
    return applied;
  }

  function healPlayer(player, amount) {
    player.health = Math.min(player.maxHealth, player.health + amount);
    if (player.health > 0) {
      player.dead = false;
    }
  }

  function respawnPlayer(player, spawn) {
    player.x = spawn.x;
    player.y = spawn.y;
    player.vx = 0;
    player.vy = 0;
    player.health = player.maxHealth;
    player.hunger = player.maxHunger;
    player.saturation = 5;
    player.exhaustion = 0;
    player.air = player.maxAir;
    player.regenTimer = 0;
    player.starveTimer = 0;
    player.dead = false;
    player.hurtCooldown = 0;
    player.fallStartY = spawn.y;
    player.fallDistance = 0;
    player.onGround = false;
    player.mining = null;
    return player;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer,
    overlapsSolid: overlapsSolid,
    overlapsBlock: overlapsBlock,
    canReach: canReach,
    miningSpeedFor: miningSpeedFor,
    updateMining: updateMining,
    validatePlacement: validatePlacement,
    damagePlayer: damagePlayer,
    healPlayer: healPlayer,
    respawnPlayer: respawnPlayer
  };
});
