(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxSave = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VERSION = 1;

  function createMemoryStorage() {
    const map = new Map();
    return {
      getItem: function (key) {
        return map.has(String(key)) ? map.get(String(key)) : null;
      },
      setItem: function (key, value) {
        map.set(String(key), String(value));
      },
      removeItem: function (key) {
        map.delete(String(key));
      },
      get length() {
        return map.size;
      }
    };
  }

  function resolveStorage(candidate) {
    try {
      if (
        candidate &&
        typeof candidate.getItem === "function" &&
        typeof candidate.setItem === "function" &&
        typeof candidate.removeItem === "function"
      ) {
        const probe = "__sandbox_probe__";
        candidate.setItem(probe, "1");
        const ok = candidate.getItem(probe) === "1";
        candidate.removeItem(probe);
        if (ok) {
          return { storage: candidate, persisted: true, reason: "localStorage" };
        }
      }
    } catch (error) {
      // A blocked or quota-limited store falls back to memory below. The game
      // stays playable; the HUD reports that saving is unavailable.
    }
    return { storage: createMemoryStorage(), persisted: false, reason: "memory-fallback" };
  }

  function isValidPayload(payload) {
    if (!payload || typeof payload !== "object") {
      return false;
    }
    if (payload.version !== VERSION) {
      return false;
    }
    const world = payload.world;
    if (!world || !Number.isInteger(world.width) || !Number.isInteger(world.height)) {
      return false;
    }
    if (world.width <= 0 || world.height <= 0) {
      return false;
    }
    if (!Array.isArray(world.data) || world.data.length !== world.width * world.height) {
      return false;
    }
    for (let index = 0; index < world.data.length; index += 1) {
      const value = world.data[index];
      if (!Number.isInteger(value) || value < 0 || value > 255) {
        return false;
      }
    }
    const player = payload.player;
    if (!player || !Number.isFinite(player.x) || !Number.isFinite(player.y)) {
      return false;
    }
    if (!Number.isInteger(payload.hotbarIndex) || payload.hotbarIndex < 0) {
      return false;
    }
    if (payload.seed !== undefined && (!Number.isFinite(payload.seed) || payload.seed < 0)) {
      return false;
    }
    if (payload.inventory !== undefined) {
      if (!payload.inventory || typeof payload.inventory !== "object") {
        return false;
      }
      const keys = Object.keys(payload.inventory);
      for (let index = 0; index < keys.length; index += 1) {
        const value = payload.inventory[keys[index]];
        if (!Number.isFinite(value) || value < 0) {
          return false;
        }
      }
    }
    return true;
  }

  function createPayload(worldData, playerData, hotbarIndex, inventory, savedAt) {
    const payload = {
      version: VERSION,
      world: worldData,
      player: playerData,
      hotbarIndex: hotbarIndex,
      savedAt: Number.isFinite(savedAt) ? savedAt : Date.now()
    };
    if (worldData && Number.isFinite(worldData.seed)) {
      payload.seed = worldData.seed;
    }
    if (inventory && typeof inventory === "object") {
      payload.inventory = Object.assign({}, inventory);
    }
    return payload;
  }

  function saveGame(storage, key, payload) {
    try {
      if (!isValidPayload(payload)) {
        return { ok: false, persisted: false, reason: "invalid-payload" };
      }
      const text = JSON.stringify(payload);
      storage.setItem(key, text);
      return { ok: true, persisted: true, bytes: text.length };
    } catch (error) {
      return {
        ok: false,
        persisted: false,
        reason: "write-failed",
        message: error && error.message ? error.message : String(error)
      };
    }
  }

  function loadGame(storage, key) {
    try {
      const raw = storage.getItem(key);
      if (!raw) {
        return { ok: false, reason: "missing" };
      }
      const payload = JSON.parse(raw);
      if (!isValidPayload(payload)) {
        return { ok: false, reason: "invalid" };
      }
      return { ok: true, payload: payload, bytes: raw.length };
    } catch (error) {
      return { ok: false, reason: "corrupt" };
    }
  }

  function clearGame(storage, key) {
    try {
      storage.removeItem(key);
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "remove-failed" };
    }
  }

  return {
    VERSION: VERSION,
    createMemoryStorage: createMemoryStorage,
    resolveStorage: resolveStorage,
    isValidPayload: isValidPayload,
    createPayload: createPayload,
    saveGame: saveGame,
    loadGame: loadGame,
    clearGame: clearGame
  };
});
