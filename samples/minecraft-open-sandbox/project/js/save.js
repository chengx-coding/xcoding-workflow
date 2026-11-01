(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxSave = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  if (!CONFIG || !WORLD) {
    throw new Error("SandboxConfig and SandboxWorld are required before SandboxSave");
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function createSnapshot(state) {
    const inventory = state.inventory || { items: {}, selected: 0 };
    const items = {};
    Object.keys(inventory.items || {}).forEach(function (key) {
      const value = inventory.items[key];
      if (Number.isInteger(value) && value > 0) {
        items[key] = value;
      }
    });
    return {
      version: CONFIG.saveVersion,
      seed: state.world.seed >>> 0,
      width: state.world.width,
      height: state.world.height,
      blocks: WORLD.encodeRle(state.world.data),
      player: {
        x: state.player.x,
        y: state.player.y,
        vx: state.player.vx,
        vy: state.player.vy,
        facing: state.player.facing
      },
      inventory: {
        items: items,
        selected: inventory.selected
      },
      time: {
        tick: state.time.tick,
        day: state.time.day
      },
      savedAt: Date.now()
    };
  }

  function encodeSnapshot(snapshot) {
    return JSON.stringify(snapshot);
  }

  function validateSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
      throw new Error("Save data is not an object");
    }
    if (snapshot.version !== CONFIG.saveVersion) {
      throw new Error("Unsupported save version");
    }
    if (!Number.isInteger(snapshot.width) || !Number.isInteger(snapshot.height)) {
      throw new Error("Save world dimensions are invalid");
    }
    if (snapshot.width < 8 || snapshot.height < 8 || snapshot.width > 512 || snapshot.height > 512) {
      throw new Error("Save world dimensions are out of range");
    }
    if (!Array.isArray(snapshot.blocks)) {
      throw new Error("Save block runs are missing");
    }
    const player = snapshot.player;
    if (!player || !isFiniteNumber(player.x) || !isFiniteNumber(player.y)) {
      throw new Error("Save player position is invalid");
    }
    if (!isFiniteNumber(player.vx) || !isFiniteNumber(player.vy) || !isFiniteNumber(player.facing)) {
      throw new Error("Save player velocity is invalid");
    }
    if (player.x < 0 || player.x > snapshot.width || player.y < -2 || player.y > snapshot.height + 2) {
      throw new Error("Save player position is outside the world");
    }
    const inventory = snapshot.inventory;
    if (!inventory || typeof inventory !== "object" || !inventory.items) {
      throw new Error("Save inventory is missing");
    }
    Object.keys(inventory.items).forEach(function (key) {
      const value = inventory.items[key];
      if (!Number.isInteger(value) || value < 0) {
        throw new Error("Save inventory count is invalid");
      }
    });
    if (!Number.isInteger(inventory.selected) || inventory.selected < 0 || inventory.selected >= CONFIG.hotbar.length) {
      throw new Error("Save hotbar selection is invalid");
    }
    const time = snapshot.time;
    if (!time || !isFiniteNumber(time.tick) || !Number.isInteger(time.day)) {
      throw new Error("Save time is invalid");
    }
    if (time.tick < 0 || time.tick >= CONFIG.dayLengthSeconds || time.day < 0) {
      throw new Error("Save time is out of range");
    }
    const decodedLength = snapshot.width * snapshot.height;
    const data = WORLD.decodeRle(snapshot.blocks, decodedLength);
    return data;
  }

  function decodeSnapshot(text) {
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      throw new Error("Save data is not valid JSON");
    }
    validateSnapshot(parsed);
    return parsed;
  }

  function worldFromSnapshot(snapshot) {
    const data = WORLD.decodeRle(snapshot.blocks, snapshot.width * snapshot.height);
    return {
      width: snapshot.width,
      height: snapshot.height,
      seed: snapshot.seed >>> 0,
      data: data
    };
  }

  function createMemoryStorage() {
    const data = Object.create(null);
    return {
      getItem: function (key) {
        return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
      },
      setItem: function (key, value) {
        data[key] = String(value);
      },
      removeItem: function (key) {
        delete data[key];
      },
      persistent: false
    };
  }

  function resolveStorage() {
    try {
      if (typeof localStorage !== "undefined" && localStorage) {
        const probe = "__sandbox_probe__";
        localStorage.setItem(probe, "1");
        localStorage.removeItem(probe);
        return { storage: localStorage, persistent: true, warning: "" };
      }
    } catch (error) {
      return {
        storage: createMemoryStorage(),
        persistent: false,
        warning: "Browser storage is unavailable; progress lasts for this session only."
      };
    }
    return {
      storage: createMemoryStorage(),
      persistent: false,
      warning: "Browser storage is unavailable; progress lasts for this session only."
    };
  }

  function saveGame(storage, state) {
    try {
      const snapshot = createSnapshot(state);
      const text = encodeSnapshot(snapshot);
      storage.setItem(CONFIG.saveKey, text);
      return { ok: true, bytes: text.length, snapshot: snapshot };
    } catch (error) {
      return { ok: false, error: error.message || String(error) };
    }
  }

  function loadGame(storage) {
    try {
      const text = storage.getItem(CONFIG.saveKey);
      if (!text) {
        return { ok: false, missing: true };
      }
      const snapshot = decodeSnapshot(text);
      return { ok: true, snapshot: snapshot };
    } catch (error) {
      return { ok: false, error: error.message || String(error) };
    }
  }

  function clearGame(storage) {
    try {
      storage.removeItem(CONFIG.saveKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  return {
    createSnapshot: createSnapshot,
    encodeSnapshot: encodeSnapshot,
    decodeSnapshot: decodeSnapshot,
    validateSnapshot: validateSnapshot,
    worldFromSnapshot: worldFromSnapshot,
    createMemoryStorage: createMemoryStorage,
    resolveStorage: resolveStorage,
    saveGame: saveGame,
    loadGame: loadGame,
    clearGame: clearGame
  };
});
