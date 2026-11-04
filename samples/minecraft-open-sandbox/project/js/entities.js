/* Passive and hostile mobs: spawning, simple AI, combat and drops. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./render.js"));
  } else {
    root.SandboxEntities = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxRender);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, RENDER) {
  "use strict";

  const B = CONFIG.blocks;
  const TYPES = {
    zombie: {
      type: "zombie", hostile: true, width: 0.72, height: 1.8, health: 20, maxHealth: 20,
      speed: 1.7, damage: 3, drop: CONFIG.itemIds.rottenFlesh, dropMin: 0, dropMax: 2
    },
    slime: {
      type: "slime", hostile: true, width: 0.86, height: 0.86, health: 8, maxHealth: 8,
      speed: 3.4, damage: 2, drop: CONFIG.itemIds.slimeball, dropMin: 1, dropMax: 1
    },
    pig: {
      type: "pig", hostile: false, width: 0.96, height: 0.76, health: 10, maxHealth: 10,
      speed: 1.2, damage: 0, drop: CONFIG.itemIds.rawPork, dropMin: 1, dropMax: 2
    },
    chicken: {
      type: "chicken", hostile: false, width: 0.62, height: 0.7, health: 4, maxHealth: 4,
      speed: 1.5, damage: 0, drop: -1, dropMin: 0, dropMax: 0
    }
  };
  const HOSTILE_CAP = 8;
  const PASSIVE_CAP = 6;
  const SPAWN_INTERVAL = 4;

  function createManager() {
    return { list: [], spawnTimer: 2, nextId: 1 };
  }

  function spawn(manager, type, x, y) {
    const def = TYPES[type];
    if (!def) {
      return null;
    }
    const entity = {
      id: manager.nextId++,
      type: def.type,
      hostile: def.hostile,
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      width: def.width,
      height: def.height,
      speed: def.speed,
      damage: def.damage,
      health: def.health,
      maxHealth: def.maxHealth,
      onGround: false,
      hurt: 0,
      attackCooldown: 0,
      wanderTimer: 0,
      direction: Math.random() < 0.5 ? -1 : 1,
      hopTimer: 0.5 + Math.random(),
      phase: Math.random() * Math.PI * 2,
      drop: def.drop,
      dropMin: def.dropMin,
      dropMax: def.dropMax
    };
    manager.list.push(entity);
    return entity;
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

  function moveAxis(world, entity, delta, horizontal) {
    const steps = Math.max(1, Math.ceil(Math.abs(delta) / 0.08));
    const step = delta / steps;
    for (let i = 0; i < steps; i += 1) {
      const nx = horizontal ? entity.x + step : entity.x;
      const ny = horizontal ? entity.y : entity.y + step;
      if (overlapsSolid(world, nx, ny, entity.width, entity.height)) {
        if (horizontal) {
          entity.vx = 0;
          return true;
        }
        if (step > 0) {
          entity.onGround = true;
        }
        entity.vy = 0;
        return true;
      }
      entity.x = nx;
      entity.y = ny;
    }
    return false;
  }

  function physics(world, entity, dt) {
    entity.vy = Math.min(CONFIG.maxFallSpeed, entity.vy + CONFIG.gravity * 0.7 * dt);
    entity.onGround = false;
    moveAxis(world, entity, entity.vx * dt, true);
    moveAxis(world, entity, entity.vy * dt, false);
    if (!overlapsSolid(world, entity.x, entity.y + 0.04, entity.width, entity.height)) {
      entity.onGround = false;
    }
    entity.x = Math.max(entity.width / 2 + 0.1, Math.min(world.width - entity.width / 2 - 0.1, entity.x));
    if (entity.y > world.height) {
      entity.y = 1;
    }
  }

  function distanceTo(entity, player) {
    const dx = player.x - entity.x;
    const dy = (player.y - player.height * 0.5) - (entity.y - entity.height * 0.5);
    return Math.sqrt(dx * dx + dy * dy);
  }

  function overlapPlayer(entity, player) {
    return Math.abs(entity.x - player.x) < (entity.width + player.width) / 2 + 0.05 &&
      entity.y > player.y - player.height - 0.1 &&
      entity.y - entity.height < player.y + 0.1;
  }

  function nearestSurface(world, x) {
    const top = world.surface[x];
    if (top == null) {
      return null;
    }
    const block = WORLD.getBlock(world, x, top);
    if (block !== B.grass && block !== B.sand) {
      return null;
    }
    if (WORLD.getBlock(world, x, top - 1) !== B.air || WORLD.getBlock(world, x, top - 2) !== B.air) {
      return null;
    }
    return top;
  }

  function trySpawn(manager, world, player, time) {
    const hostiles = manager.list.filter(function (e) { return e.hostile; }).length;
    const passives = manager.list.length - hostiles;
    const night = RENDER.nightAmount(time);
    const wantHostile = night > 0.55 && hostiles < HOSTILE_CAP;
    const wantPassive = passives < PASSIVE_CAP && Math.random() < 0.6;
    if (!wantHostile && !wantPassive) {
      return false;
    }
    function choose() {
      if (wantHostile) {
        return Math.random() < 0.65 ? "zombie" : "slime";
      }
      if (wantPassive) {
        return Math.random() < 0.6 ? "pig" : "chicken";
      }
      return null;
    }
    function placeAt(x, top) {
      const type = choose();
      if (!type) {
        return false;
      }
      spawn(manager, type, x + 0.5, top);
      return true;
    }
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const side = Math.random() < 0.5 ? -1 : 1;
      const distance = 11 + Math.floor(Math.random() * 17);
      const x = Math.max(2, Math.min(world.width - 3, Math.floor(player.x) + side * distance));
      if (Math.abs(x - player.x) < 7) {
        continue;
      }
      const top = nearestSurface(world, x);
      if (top != null && placeAt(x, top)) {
        return true;
      }
    }
    // Deterministic nearest-column fallback so a beach or a narrow ledge cannot
    // suppress the night population entirely.
    for (let distance = 7; distance <= 30; distance += 1) {
      for (const side of [-1, 1]) {
        const x = Math.floor(player.x) + side * distance;
        if (x < 2 || x >= world.width - 2) {
          continue;
        }
        const top = nearestSurface(world, x);
        if (top != null && placeAt(x, top)) {
          return true;
        }
      }
    }
    return false;
  }

  function update(manager, ctx) {
    const dt = ctx.dt;
    const world = ctx.world;
    const player = ctx.player;
    const time = ctx.time;
    const effects = ctx.effects || {};
    const night = RENDER.nightAmount(time);

    for (let i = manager.list.length - 1; i >= 0; i -= 1) {
      const entity = manager.list[i];
      const distance = Math.abs(entity.x - player.x);
      if (distance > 48) {
        manager.list.splice(i, 1);
        continue;
      }
      if (entity.hostile && night < 0.22) {
        manager.list.splice(i, 1);
        if (effects.onParticle) {
          effects.onParticle(entity.x, entity.y - 0.5, "#d9d4c4", 4);
        }
        continue;
      }
      entity.hurt = Math.max(0, entity.hurt - dt);
      entity.attackCooldown = Math.max(0, entity.attackCooldown - dt);
      const toward = player.x < entity.x ? -1 : 1;
      const near = distance < 18;

      if (entity.type === "zombie") {
        if (near) {
          entity.vx = toward * entity.speed;
          if (entity.onGround && Math.abs(entity.vx) > 0.1 && Math.random() < 0.02) {
            entity.vy = -8.4;
          }
        } else {
          entity.wanderTimer -= dt;
          if (entity.wanderTimer <= 0) {
            entity.wanderTimer = 2 + Math.random() * 3;
            entity.direction = Math.random() < 0.5 ? -1 : 1;
          }
          entity.vx = entity.direction * entity.speed * 0.35;
        }
      } else if (entity.type === "slime") {
        entity.hopTimer -= dt;
        if (entity.onGround && entity.hopTimer <= 0) {
          entity.hopTimer = 1.1 + Math.random() * 0.7;
          entity.vy = -7.2;
          entity.vx = (near ? toward : entity.direction) * entity.speed;
        }
        if (entity.onGround) {
          entity.vx *= 0.72;
        }
      } else {
        entity.wanderTimer -= dt;
        if (entity.wanderTimer <= 0) {
          entity.wanderTimer = 2 + Math.random() * 4;
          entity.direction = Math.random() < 0.5 ? -1 : 1;
          if (Math.random() < 0.25) {
            entity.direction = 0;
          }
        }
        entity.vx = entity.direction * entity.speed * 0.55;
        if (entity.onGround && Math.random() < 0.003) {
          entity.vy = -6.2;
        }
      }

      physics(world, entity, dt);

      if (entity.hostile && overlapPlayer(entity, player) && entity.attackCooldown <= 0) {
        entity.attackCooldown = 1.15;
        if (effects.onPlayerDamage) {
          effects.onPlayerDamage(entity.damage, entity.type);
        }
      }
    }

    manager.spawnTimer -= dt;
    if (manager.spawnTimer <= 0) {
      manager.spawnTimer = SPAWN_INTERVAL;
      trySpawn(manager, world, player, time);
    }
  }

  function mobAt(manager, worldX, worldY) {
    for (let i = manager.list.length - 1; i >= 0; i -= 1) {
      const entity = manager.list[i];
      if (worldX >= entity.x - entity.width / 2 && worldX <= entity.x + entity.width / 2 &&
        worldY >= entity.y - entity.height && worldY <= entity.y) {
        return entity;
      }
    }
    return null;
  }

  function hit(manager, entity, amount, direction, ctx) {
    if (!entity || entity.health <= 0) {
      return { hit: false };
    }
    entity.health -= amount;
    entity.hurt = 0.3;
    entity.vx = direction * 4.2;
    entity.vy = -4.2;
    entity.attackCooldown = Math.max(entity.attackCooldown, 0.4);
    const effects = (ctx && ctx.effects) || {};
    if (entity.health > 0) {
      return { hit: true, killed: false, health: entity.health };
    }
    const index = manager.list.indexOf(entity);
    if (index >= 0) {
      manager.list.splice(index, 1);
    }
    let dropped = 0;
    if (entity.drop != null && entity.drop >= 0 && effects.onDrop) {
      const count = entity.dropMin + Math.floor(Math.random() * (entity.dropMax - entity.dropMin + 1));
      for (let i = 0; i < count; i += 1) {
        effects.onDrop(entity.drop);
        dropped += 1;
      }
    }
    if (effects.onParticle) {
      effects.onParticle(entity.x, entity.y - entity.height * 0.5, entity.type === "slime" ? "#66c46b" : "#9a5b4b", 8);
    }
    return { hit: true, killed: true, dropped: dropped };
  }

  function clearHostiles(manager) {
    manager.list = manager.list.filter(function (entity) { return !entity.hostile; });
  }

  return {
    types: TYPES,
    hostileCap: HOSTILE_CAP,
    passiveCap: PASSIVE_CAP,
    createManager: createManager,
    spawn: spawn,
    trySpawn: trySpawn,
    update: update,
    mobAt: mobAt,
    hit: hit,
    clearHostiles: clearHostiles,
    overlapsSolid: overlapsSolid
  };
});
