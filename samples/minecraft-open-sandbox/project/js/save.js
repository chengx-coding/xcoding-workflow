(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./config.js"),
      require("./world.js"),
      require("./inventory.js"),
      require("./progression.js")
    );
  } else {
    root.SandboxSave = factory(
      root.SandboxConfig,
      root.SandboxWorld,
      root.SandboxInventory,
      root.SandboxProgression
    );
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, INVENTORY, PROGRESSION) {
  "use strict";

  if (!CONFIG || !WORLD || !INVENTORY || !PROGRESSION) {
    throw new Error("SandboxConfig, SandboxWorld, SandboxInventory and SandboxProgression are required");
  }

  function capture(state) {
    return {
      schema: 1,
      version: CONFIG.version,
      savedAt: Date.now(),
      seed: state.world.seed,
      world: JSON.parse(WORLD.serializeWorld(state.world)),
      player: {
        x: state.player.x,
        y: state.player.y,
        health: state.player.health
      },
      inventory: INVENTORY.serialize(state.inventory),
      progress: PROGRESSION.serialize(state.progress),
      clock: {
        day: Math.max(1, Math.floor(state.clock.day)),
        time: ((Number(state.clock.time) % 1) + 1) % 1
      }
    };
  }

  function validate(payload) {
    if (!payload || typeof payload !== "object") {
      return "empty save";
    }
    if (payload.schema !== 1) {
      return "unsupported save schema";
    }
    if (!payload.world || typeof payload.world !== "object") {
      return "missing world";
    }
    try {
      WORLD.deserializeWorld(payload.world);
    } catch (error) {
      return "invalid world: " + (error && error.message ? error.message : "unknown");
    }
    if (!payload.player || !Number.isFinite(payload.player.x) || !Number.isFinite(payload.player.y)) {
      return "invalid player";
    }
    if (payload.inventory && !Array.isArray(payload.inventory.slots)) {
      return "invalid inventory";
    }
    if (payload.progress && typeof payload.progress !== "object") {
      return "invalid progress";
    }
    return "";
  }

  function save(storage, state) {
    if (!storage || typeof storage.setItem !== "function") {
      return { ok: false, error: "storage-unavailable", bytes: 0 };
    }
    const payload = capture(state);
    let text;
    try {
      text = JSON.stringify(payload);
    } catch (error) {
      return { ok: false, error: "encode-failed", bytes: 0 };
    }
    try {
      storage.setItem(CONFIG.saveKey, text);
      return { ok: true, bytes: text.length, savedAt: payload.savedAt, error: "" };
    } catch (error) {
      const code = error && error.name === "QuotaExceededError" ? "quota-exceeded" : "write-failed";
      return { ok: false, error: code, bytes: text.length };
    }
  }

  function read(storage) {
    if (!storage || typeof storage.getItem !== "function") {
      return { ok: false, error: "storage-unavailable", data: null };
    }
    let text;
    try {
      text = storage.getItem(CONFIG.saveKey);
    } catch (error) {
      return { ok: false, error: "read-failed", data: null };
    }
    if (!text) {
      return { ok: false, error: "empty", data: null };
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      return { ok: false, error: "corrupt", data: null };
    }
    const problem = validate(payload);
    if (problem) {
      return { ok: false, error: "corrupt", detail: problem, data: null };
    }
    return { ok: true, error: "", data: payload, bytes: text.length };
  }

  function load(storage) {
    const result = read(storage);
    if (!result.ok) {
      return result;
    }
    const data = result.data;
    let world;
    try {
      world = WORLD.deserializeWorld(data.world);
    } catch (error) {
      return { ok: false, error: "corrupt", data: null };
    }
    return {
      ok: true,
      error: "",
      data: data,
      bytes: result.bytes,
      state: {
        world: world,
        seed: world.seed,
        player: data.player,
        inventory: INVENTORY.deserialize(data.inventory),
        progress: PROGRESSION.deserialize(data.progress),
        clock: {
          day: data.clock && Number.isFinite(data.clock.day) ? Math.max(1, Math.floor(data.clock.day)) : 1,
          time:
            data.clock && Number.isFinite(data.clock.time)
              ? ((data.clock.time % 1) + 1) % 1
              : CONFIG.startTime
        },
        savedAt: data.savedAt || 0
      }
    };
  }

  function clear(storage) {
    if (!storage || typeof storage.removeItem !== "function") {
      return false;
    }
    try {
      storage.removeItem(CONFIG.saveKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  function hasSave(storage) {
    return read(storage).ok;
  }

  function summarize(data) {
    const stats = (data && data.progress && data.progress.stats) || {};
    return {
      day: data && data.clock ? data.clock.day : 1,
      blocksMined: Math.max(0, Math.floor(stats.blocksMined || 0)),
      playtime: Math.max(0, Math.floor(stats.playtime || 0)),
      savedAt: data && data.savedAt ? data.savedAt : 0
    };
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(seconds || 0));
    const minutes = Math.floor(total / 60);
    const remainder = total % 60;
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      return hours + "h " + (minutes % 60) + "m";
    }
    return minutes + "m " + (remainder < 10 ? "0" : "") + remainder + "s";
  }

  function formatAgo(timestamp) {
    if (!timestamp) {
      return "not yet";
    }
    const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (seconds < 5) {
      return "just now";
    }
    if (seconds < 60) {
      return seconds + "s ago";
    }
    if (seconds < 3600) {
      return Math.floor(seconds / 60) + "m ago";
    }
    return Math.floor(seconds / 3600) + "h ago";
  }

  return {
    capture: capture,
    validate: validate,
    save: save,
    read: read,
    load: load,
    clear: clear,
    hasSave: hasSave,
    summarize: summarize,
    formatDuration: formatDuration,
    formatAgo: formatAgo
  };
});
