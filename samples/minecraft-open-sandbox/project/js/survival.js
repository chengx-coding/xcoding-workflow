/* Health, hunger, air, fall damage and regeneration. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./player.js"));
  } else {
    root.SandboxSurvival = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxPlayer);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, PLAYER) {
  "use strict";

  const B = CONFIG.blocks;

  function isHeadUnderwater(world, player) {
    const headY = player.y - player.height + 0.25;
    const x = Math.floor(player.x);
    const y = Math.floor(headY);
    return WORLD.isLiquid(world, x, y);
  }

  function damage(player, amount, cause) {
    if (player.dead || player.hurtCooldown > 0 && cause !== "fall" && cause !== "starvation" && cause !== "drowning") {
      return 0;
    }
    const applied = PLAYER.damagePlayer(player, amount, cause);
    if (applied > 0) {
      player.hurtCooldown = cause === "fall" ? 0.3 : 0.55;
    }
    return applied;
  }

  function update(player, world, dt, options) {
    const opts = options || {};
    const events = [];
    if (!player || player.dead) {
      return events;
    }

    const moving = Boolean(player.moving);
    const sprinting = Boolean(player.sprinting);
    const mining = Boolean(opts.mining);
    let exhaustionRate = 0.03;
    if (sprinting) {
      exhaustionRate = 0.35;
    } else if (mining) {
      exhaustionRate = 0.24;
    } else if (moving) {
      exhaustionRate = 0.12;
    }
    player.exhaustion += exhaustionRate * dt;
    while (player.exhaustion >= 4) {
      player.exhaustion -= 4;
      if (player.saturation > 0) {
        player.saturation = Math.max(0, player.saturation - 1);
      } else if (player.hunger > 0) {
        player.hunger -= 1;
      }
    }

    if (player.hunger >= 18 && player.health < player.maxHealth) {
      player.regenTimer += dt;
      if (player.regenTimer >= 4) {
        player.regenTimer = 0;
        player.health = Math.min(player.maxHealth, player.health + 1);
        player.exhaustion += 1.5;
        events.push({ type: "heal", amount: 1 });
      }
    } else {
      player.regenTimer = 0;
    }

    if (player.hunger <= 0) {
      player.starveTimer += dt;
      if (player.starveTimer >= 4) {
        player.starveTimer = 0;
        const applied = damage(player, 1, "starvation");
        if (applied) {
          events.push({ type: "damage", amount: applied, cause: "starvation" });
        }
      }
    } else {
      player.starveTimer = 0;
    }

    if (player.onGround && player.fallDistance > 3.5) {
      const fall = Math.floor(player.fallDistance - 3);
      player.fallDistance = 0;
      if (fall > 0) {
        const applied = damage(player, fall, "fall");
        if (applied) {
          events.push({ type: "damage", amount: applied, cause: "fall" });
        }
      }
    }

    const underwater = isHeadUnderwater(world, player);
    player.headUnderwater = underwater;
    if (underwater) {
      player.air = Math.max(0, player.air - dt);
      if (player.air <= 0) {
        player.suffocateTimer = (player.suffocateTimer || 0) + dt;
        if (player.suffocateTimer >= 1.5) {
          player.suffocateTimer = 0;
          const applied = damage(player, 2, "drowning");
          if (applied) {
            events.push({ type: "damage", amount: applied, cause: "drowning" });
          }
        }
      }
    } else {
      player.air = Math.min(player.maxAir, player.air + dt * 3);
      player.suffocateTimer = 0;
    }

    if (player.health <= 0 && !player.dead) {
      player.dead = true;
      events.push({ type: "died", cause: player.lastDamageCause || "the world" });
    }

    return events;
  }

  function eat(player, foodDef) {
    if (!foodDef || !foodDef.food || player.hunger >= player.maxHunger) {
      return false;
    }
    player.hunger = Math.min(player.maxHunger, player.hunger + foodDef.food);
    player.saturation = Math.min(10, player.saturation + Math.ceil(foodDef.food * 0.6));
    return true;
  }

  function status(player) {
    return {
      health: player.health,
      maxHealth: player.maxHealth,
      hunger: player.hunger,
      maxHunger: player.maxHunger,
      air: player.air,
      maxAir: player.maxAir,
      dead: player.dead
    };
  }

  return {
    update: update,
    damage: damage,
    eat: eat,
    isHeadUnderwater: isHeadUnderwater,
    status: status
  };
});
