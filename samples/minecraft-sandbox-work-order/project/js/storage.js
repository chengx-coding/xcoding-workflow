(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxStorage = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, worldApi) {
  "use strict";

  function sanitizeStats(stats) {
    const source = stats && typeof stats === "object" ? stats : {};
    return {
      mined: Math.max(0, Math.floor(Number(source.mined) || 0)),
      placed: Math.max(0, Math.floor(Number(source.placed) || 0)),
      distance: Math.max(0, Number(source.distance) || 0),
      crystals: Math.max(0, Math.floor(Number(source.crystals) || 0))
    };
  }

  function buildSave(world, player, state) {
    const runtime = state || {};
    return {
      version: CONFIG.saveVersion,
      seed: world.seed,
      world: {
        width: world.width,
        height: world.height,
        data: Array.from(world.data)
      },
      player: {
        x: player.x,
        y: player.y,
        vx: player.vx,
        vy: player.vy,
        facing: player.facing
      },
      selected: Math.max(0, Math.min(CONFIG.hotbar.length - 1, Number(runtime.selected) || 0)),
      timeOfDay: Number.isFinite(runtime.timeOfDay) ? runtime.timeOfDay % 1 : CONFIG.initialTimeOfDay,
      stats: sanitizeStats(runtime.stats),
      settings: {
        muted: Boolean(runtime.muted)
      }
    };
  }

  function serializeSave(world, player, state) {
    return JSON.stringify(buildSave(world, player, state));
  }

  function parseSave(raw) {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return { ok: false, reason: "invalid-json" };
    }
    if (!parsed || parsed.version !== CONFIG.saveVersion) {
      return { ok: false, reason: "version" };
    }
    let world;
    try {
      world = worldApi.deserializeWorld(parsed.world);
    } catch (error) {
      return { ok: false, reason: "world" };
    }
    const playerData = parsed.player;
    if (
      !playerData ||
      !Number.isFinite(playerData.x) ||
      !Number.isFinite(playerData.y) ||
      playerData.x < 0 ||
      playerData.x > world.width ||
      playerData.y < 0 ||
      playerData.y > world.height + 4
    ) {
      return { ok: false, reason: "player" };
    }
    const selected = Math.max(0, Math.min(CONFIG.hotbar.length - 1, Math.floor(Number(parsed.selected) || 0)));
    const timeOfDay = Number.isFinite(parsed.timeOfDay) ? parsed.timeOfDay % 1 : CONFIG.initialTimeOfDay;
    return {
      ok: true,
      value: {
        world: world,
        player: {
          x: playerData.x,
          y: playerData.y,
          vx: Number.isFinite(playerData.vx) ? playerData.vx : 0,
          vy: 0,
          facing: playerData.facing === -1 ? -1 : 1
        },
        selected: selected,
        timeOfDay: timeOfDay,
        stats: sanitizeStats(parsed.stats),
        settings: {
          muted: Boolean(parsed.settings && parsed.settings.muted)
        }
      }
    };
  }

  function writeSave(storage, key, world, player, state) {
    try {
      storage.setItem(key, serializeSave(world, player, state));
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "write-failed" };
    }
  }

  function readSave(storage, key) {
    let raw;
    try {
      raw = storage.getItem(key);
    } catch (error) {
      return { ok: false, reason: "read-failed" };
    }
    if (!raw) {
      return { ok: false, reason: "empty" };
    }
    return parseSave(raw);
  }

  function clearSave(storage, key) {
    try {
      storage.removeItem(key);
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "clear-failed" };
    }
  }

  return {
    buildSave: buildSave,
    serializeSave: serializeSave,
    parseSave: parseSave,
    writeSave: writeSave,
    readSave: readSave,
    clearSave: clearSave,
    sanitizeStats: sanitizeStats
  };
});
