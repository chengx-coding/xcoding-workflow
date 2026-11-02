(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxMobs = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const EPS = 0.0001;
  const MOB_WIDTH = 0.8;
  const MOB_HEIGHT = 1.4;
  const WALK_SPEED = 2.1;
  const AGGRO_RANGE = 16;
  const DESPAWN_RANGE = 44;
  const ATTACK_COOLDOWN = 1.1;
  const ATTACK_DAMAGE = 2;
  const SPAWN_INTERVAL = 4;

  function createMobs() {
    return { list: [], spawnTimer: 1.5, totalSpawned: 0 };
  }

  function solidAt(world, x, y) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return y >= world.height || x < 0 || x >= world.width;
    }
    const block = world.data[y * world.width + x];
    return block !== 0 && block !== CONFIG.blocks.torch;
  }

  function boxCollides(world, x, y) {
    const left = Math.floor(x - MOB_WIDTH / 2 + EPS);
    const right = Math.floor(x + MOB_WIDTH / 2 - EPS);
    const top = Math.floor(y - MOB_HEIGHT + EPS);
    const bottom = Math.floor(y - EPS);
    for (let ty = top; ty <= bottom; ty += 1) {
      for (let tx = left; tx <= right; tx += 1) {
        if (solidAt(world, tx, ty)) {
          return true;
        }
      }
    }
    return false;
  }

  function moveEntity(world, entity, dt) {
    entity.vy += CONFIG.gravity * dt;
    if (entity.vy > CONFIG.maxFall) {
      entity.vy = CONFIG.maxFall;
    }
    const previousX = entity.x;
    entity.x += entity.vx * dt;
    if (boxCollides(world, entity.x, entity.y)) {
      entity.x = previousX;
      entity.vx = 0;
      entity.blocked = true;
    }
    const previousY = entity.y;
    entity.y += entity.vy * dt;
    entity.onGround = false;
    if (boxCollides(world, entity.x, entity.y)) {
      entity.y = previousY;
      if (entity.vy > 0) {
        entity.onGround = true;
      }
      entity.vy = 0;
    }
  }

  function surfaceY(world, x) {
    for (let y = 0; y < world.height; y += 1) {
      if (solidAt(world, x, y)) {
        return y;
      }
    }
    return world.height;
  }

  // Terrain surface: skip tree trunks and canopies so spawns land on ground.
  function groundY(world, x) {
    for (let y = 0; y < world.height; y += 1) {
      const block = world.data[y * world.width + x];
      if (block === CONFIG.blocks.wood || block === CONFIG.blocks.leaves) {
        continue;
      }
      if (solidAt(world, x, y)) {
        return y;
      }
    }
    return world.height;
  }

  function trySpawn(mobs, world, player, context) {
    for (let attempt = 0; attempt < 14; attempt += 1) {
      const side = attempt % 2 === 0 ? 1 : -1;
      const distance = 10 + ((attempt * 3) % 14);
      const x = Math.round(player.x + side * distance);
      if (x < 2 || x >= world.width - 2) {
        continue;
      }
      const y = groundY(world, x);
      if (y <= 0 || y >= world.height - 2) {
        continue;
      }
      const lightLevel = context.lightAt ? context.lightAt(x, y - 1) : 0;
      if (lightLevel >= 6) {
        continue;
      }
      mobs.list.push({
        x: x + 0.5,
        y: y,
        vx: 0,
        vy: 0,
        width: MOB_WIDTH,
        height: MOB_HEIGHT,
        health: 6,
        maxHealth: 6,
        hurt: 0,
        attackCooldown: 0,
        onGround: false,
        blocked: false,
        facing: side === 1 ? -1 : 1,
        wanderTimer: 0,
        wander: 0
      });
      mobs.totalSpawned += 1;
      return true;
    }
    return false;
  }

  function update(mobs, world, player, dt, context) {
    const events = { damage: 0, hits: 0, killed: 0, spawned: 0, despawned: 0 };
    const night = !!(context && context.isNight);
    if (!night) {
      if (mobs.list.length > 0) {
        events.despawned += mobs.list.length;
        mobs.list.length = 0;
      }
      mobs.spawnTimer = 1.5;
      return events;
    }

    if (mobs.list.length < CONFIG.mobLimit) {
      mobs.spawnTimer -= dt;
      if (mobs.spawnTimer <= 0) {
        mobs.spawnTimer = SPAWN_INTERVAL;
        if (trySpawn(mobs, world, player, context || {})) {
          events.spawned += 1;
        }
      }
    }

    for (let i = mobs.list.length - 1; i >= 0; i -= 1) {
      const mob = mobs.list[i];
      mob.hurt = Math.max(0, mob.hurt - dt);
      mob.attackCooldown = Math.max(0, mob.attackCooldown - dt);
      const dx = player.x - mob.x;
      const dy = player.y - mob.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      mob.facing = dx >= 0 ? 1 : -1;

      if (distance > AGGRO_RANGE || distance < 0.05) {
        mob.wanderTimer -= dt;
        if (mob.wanderTimer <= 0) {
          mob.wanderTimer = 1.2 + Math.random() * 1.6;
          mob.wander = Math.random() < 0.5 ? -1 : 1;
        }
        mob.vx = mob.wander * WALK_SPEED * 0.45;
      } else {
        mob.vx = mob.facing * WALK_SPEED;
      }

      moveEntity(world, mob, dt);
      if (mob.blocked && mob.onGround) {
        mob.vy = -11.5;
        mob.blocked = false;
      }

      if (distance > DESPAWN_RANGE || mob.y > world.height + 4) {
        mobs.list.splice(i, 1);
        events.despawned += 1;
        continue;
      }

      const playerLeft = player.x - player.width / 2;
      const playerRight = player.x + player.width / 2;
      const playerTop = player.y - player.height;
      const mobLeft = mob.x - MOB_WIDTH / 2;
      const mobRight = mob.x + MOB_WIDTH / 2;
      const mobTop = mob.y - MOB_HEIGHT;
      const touching =
        playerRight > mobLeft && playerLeft < mobRight && player.y > mobTop && playerTop < mob.y;
      if (touching && mob.attackCooldown <= 0 && !player.dead) {
        mob.attackCooldown = ATTACK_COOLDOWN;
        events.damage += ATTACK_DAMAGE;
        events.hits += 1;
      }
    }
    return events;
  }

  function bounds(mob) {
    return {
      left: mob.x - mob.width / 2,
      right: mob.x + mob.width / 2,
      top: mob.y - mob.height,
      bottom: mob.y
    };
  }

  function attackAt(mobs, x, y, radius) {
    let best = null;
    let bestDistance = Infinity;
    for (let i = 0; i < mobs.list.length; i += 1) {
      const mob = mobs.list[i];
      const box = bounds(mob);
      const inside =
        x >= box.left - radius &&
        x <= box.right + radius &&
        y >= box.top - radius &&
        y <= box.bottom + radius;
      if (!inside) {
        continue;
      }
      const distance = Math.abs(mob.x - x);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = mob;
      }
    }
    if (!best) {
      return { hit: false, killed: false, mob: null };
    }
    return { hit: true, mob: best };
  }

  function damage(mob, amount) {
    mob.health -= amount;
    mob.hurt = 0.18;
    return mob.health <= 0;
  }

  function remove(mobs, mob) {
    const index = mobs.list.indexOf(mob);
    if (index >= 0) {
      mobs.list.splice(index, 1);
    }
  }

  function addMob(mobs, mob) {
    mobs.list.push(
      Object.assign(
        {
          x: 0,
          y: 0,
          vx: 0,
          vy: 0,
          width: MOB_WIDTH,
          height: MOB_HEIGHT,
          health: 6,
          maxHealth: 6,
          hurt: 0,
          attackCooldown: 0,
          onGround: false,
          blocked: false,
          facing: 1,
          wanderTimer: 0,
          wander: 0
        },
        mob
      )
    );
    return mobs.list[mobs.list.length - 1];
  }

  return {
    MOB_WIDTH: MOB_WIDTH,
    MOB_HEIGHT: MOB_HEIGHT,
    createMobs: createMobs,
    update: update,
    attackAt: attackAt,
    damage: damage,
    remove: remove,
    addMob: addMob,
    bounds: bounds,
    surfaceY: surfaceY,
    groundY: groundY
  };
});
