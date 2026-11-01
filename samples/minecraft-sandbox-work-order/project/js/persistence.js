(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"), require("./world.js"));
  } else {
    root.SandboxPersistence = factory(root.SandboxConfig, root.SandboxInventory, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, Inventory, World) {
  "use strict";

  function createMemoryStorage(initial) {
    const items = Object.create(null);
    if (initial) {
      Object.keys(initial).forEach(function (key) {
        items[key] = String(initial[key]);
      });
    }
    return {
      getItem: function (key) {
        return Object.prototype.hasOwnProperty.call(items, key) ? items[key] : null;
      },
      setItem: function (key, value) {
        items[key] = String(value);
      },
      removeItem: function (key) {
        delete items[key];
      }
    };
  }

  function serializeState(state) {
    return JSON.stringify({
      v: CONFIG.saveVersion,
      seed: state.world.seed >>> 0,
      time: Number(state.time) || 0,
      selected: Math.max(0, Number(state.selected) | 0),
      player: {
        x: Number(state.player.x),
        y: Number(state.player.y),
        facing: state.player.facing === -1 ? -1 : 1
      },
      inventory: Inventory.toJSON(state.inventory),
      world: World.worldToRle(state.world)
    });
  }

  function deserializeState(text) {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object") {
      throw new Error("Invalid saved state");
    }
    if (parsed.v !== CONFIG.saveVersion) {
      throw new Error("Unsupported save version");
    }
    const world = World.worldFromRle(parsed.world);
    const player = parsed.player;
    if (!player || !Number.isFinite(Number(player.x)) || !Number.isFinite(Number(player.y))) {
      throw new Error("Invalid saved player");
    }
    const selected = Number(parsed.selected);
    if (!Number.isInteger(selected) || selected < 0 || selected >= CONFIG.palette.length) {
      throw new Error("Invalid saved hotbar selection");
    }
    let time = Number(parsed.time);
    if (!Number.isFinite(time)) {
      throw new Error("Invalid saved time");
    }
    time = time - Math.floor(time);
    return {
      world: world,
      player: {
        x: Number(player.x),
        y: Number(player.y),
        facing: player.facing === -1 ? -1 : 1
      },
      inventory: Inventory.fromJSON(parsed.inventory),
      time: time,
      selected: selected
    };
  }

  function saveState(storage, state, key) {
    if (!storage || typeof storage.setItem !== "function") {
      return { ok: false, reason: "unavailable" };
    }
    let payload;
    try {
      payload = serializeState(state);
    } catch (error) {
      return { ok: false, reason: "corrupt", error: String(error && error.message) };
    }
    try {
      storage.setItem(key || CONFIG.saveKey, payload);
    } catch (error) {
      return { ok: false, reason: "unavailable", error: String(error && error.message) };
    }
    return { ok: true, bytes: payload.length };
  }

  function loadState(storage, key) {
    if (!storage || typeof storage.getItem !== "function") {
      return { ok: false, reason: "unavailable" };
    }
    let payload;
    try {
      payload = storage.getItem(key || CONFIG.saveKey);
    } catch (error) {
      return { ok: false, reason: "unavailable" };
    }
    if (payload === null || payload === undefined || payload === "") {
      return { ok: false, reason: "empty" };
    }
    try {
      return { ok: true, state: deserializeState(payload) };
    } catch (error) {
      const message = String(error && error.message);
      return {
        ok: false,
        reason: message === "Unsupported save version" ? "version" : "corrupt",
        error: message
      };
    }
  }

  function clearState(storage, key) {
    if (!storage || typeof storage.removeItem !== "function") {
      return false;
    }
    try {
      storage.removeItem(key || CONFIG.saveKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  return {
    createMemoryStorage: createMemoryStorage,
    serializeState: serializeState,
    deserializeState: deserializeState,
    saveState: saveState,
    loadState: loadState,
    clearState: clearState
  };
});
