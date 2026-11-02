(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./inventory.js"), require("./tasks.js"));
  } else {
    root.SandboxSave = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxInventory, root.SandboxTasks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, INVENTORY, TASKS) {
  "use strict";

  if (!CONFIG || !WORLD || !INVENTORY || !TASKS) {
    throw new Error("SandboxConfig, SandboxWorld, SandboxInventory and SandboxTasks are required before SandboxSave");
  }

  function createEnvelope(state) {
    const player = state.player || {};
    const settings = state.settings || {};
    return {
      version: CONFIG.saveVersion,
      savedAt: new Date().toISOString(),
      seed: state.seed >>> 0,
      world: JSON.parse(WORLD.serializeWorld(state.world)),
      player: {
        x: Number(player.x) || 0,
        y: Number(player.y) || 0,
        health: Number.isFinite(player.health) ? player.health : 20,
        facing: player.facing === -1 ? -1 : 1
      },
      inventory: INVENTORY.serialize(state.inventory),
      clock: {
        t: state.clock ? state.clock.t : 0.3,
        day: state.clock ? state.clock.day : 1
      },
      progress: TASKS.serialize(state.progress),
      settings: {
        muted: Boolean(settings.muted),
        zoom: Number.isFinite(settings.zoom) ? settings.zoom : CONFIG.zoom.default,
        backdropMode: Boolean(settings.backdropMode),
        volume: Number.isFinite(settings.volume) ? settings.volume : 0.6
      },
      backdrop: state.backdrop && state.backdrop.pulses ? {
        pulses: state.backdrop.pulses.map(function (entry) {
          return { kind: entry.kind, before: entry.before, after: entry.after, at: entry.at };
        })
      } : { pulses: [] }
    };
  }

  function serialize(envelope) {
    return JSON.stringify(envelope);
  }

  function parse(text) {
    if (typeof text !== "string" || text.length === 0) {
      throw new Error("Save payload is empty");
    }
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      throw new Error("Save payload is not valid JSON");
    }
    if (!parsed || typeof parsed !== "object") {
      throw new Error("Save payload is not an object");
    }
    if (parsed.version !== CONFIG.saveVersion) {
      throw new Error("Unsupported save version: " + parsed.version);
    }
    if (!Number.isFinite(parsed.seed)) {
      throw new Error("Save payload has no seed");
    }
    if (!parsed.world || !Number.isInteger(parsed.world.width) || !Number.isInteger(parsed.world.height)) {
      throw new Error("Save payload has no world");
    }
    if (!parsed.inventory || !Array.isArray(parsed.inventory.items)) {
      throw new Error("Save payload has no inventory");
    }
    if (!parsed.clock || !Number.isFinite(parsed.clock.t)) {
      throw new Error("Save payload has no clock");
    }
    return parsed;
  }

  function loadWorld(envelope) {
    return WORLD.deserializeWorld(JSON.stringify(envelope.world));
  }

  function createStorage(scope) {
    let backend = null;
    let kind = "memory";
    let error = null;
    try {
      const storage = scope && scope.localStorage;
      if (storage) {
        const probe = "__cubewood_storage_probe__";
        storage.setItem(probe, "1");
        if (storage.getItem(probe) !== "1") {
          throw new Error("storage read-back failed");
        }
        storage.removeItem(probe);
        backend = storage;
        kind = "local";
      }
    } catch (caught) {
      error = caught && caught.message ? caught.message : String(caught);
      backend = null;
      kind = "memory";
    }
    const memory = { value: null };
    return {
      kind: kind,
      available: kind === "local",
      error: error,
      save: function (text) {
        try {
          if (backend) {
            backend.setItem(CONFIG.saveKey, text);
          } else {
            memory.value = text;
          }
          return true;
        } catch (caught) {
          error = caught && caught.message ? caught.message : String(caught);
          kind = "memory";
          backend = null;
          memory.value = text;
          return false;
        }
      },
      load: function () {
        try {
          return backend ? backend.getItem(CONFIG.saveKey) : memory.value;
        } catch (caught) {
          error = caught && caught.message ? caught.message : String(caught);
          return memory.value;
        }
      },
      clear: function () {
        memory.value = null;
        try {
          if (backend) {
            backend.removeItem(CONFIG.saveKey);
          }
        } catch (caught) {
          error = caught && caught.message ? caught.message : String(caught);
        }
      }
    };
  }

  function saveGame(storage, envelope) {
    const text = serialize(envelope);
    const ok = storage.save(text);
    return { ok: ok, kind: storage.kind, bytes: text.length, error: storage.error };
  }

  function loadGame(storage) {
    const text = storage.load();
    if (!text) {
      return null;
    }
    try {
      return parse(text);
    } catch (error) {
      return { error: error.message };
    }
  }

  return {
    createEnvelope: createEnvelope,
    serialize: serialize,
    parse: parse,
    loadWorld: loadWorld,
    createStorage: createStorage,
    saveGame: saveGame,
    loadGame: loadGame
  };
});
