(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxStorage = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function resolveBackend(options) {
    if (options && options.storage) {
      return options.storage;
    }
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        return window.localStorage;
      }
    } catch (error) {
      return null;
    }
    return null;
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function validateState(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return { ok: false, reason: "corrupt" };
    }
    if (raw.schemaVersion !== CONFIG.saveVersion) {
      return { ok: false, reason: "corrupt" };
    }
    if (!isFiniteNumber(raw.seed)) {
      return { ok: false, reason: "corrupt" };
    }
    if (typeof raw.world !== "string" || raw.world.length === 0) {
      return { ok: false, reason: "corrupt" };
    }
    if (!raw.player || !isFiniteNumber(raw.player.x) || !isFiniteNumber(raw.player.y)) {
      return { ok: false, reason: "corrupt" };
    }
    if (!raw.inventory || typeof raw.inventory !== "object") {
      return { ok: false, reason: "corrupt" };
    }
    const counts = raw.inventory.counts;
    if (!counts || typeof counts !== "object" || Array.isArray(counts)) {
      return { ok: false, reason: "corrupt" };
    }
    const keys = Object.keys(counts);
    for (let index = 0; index < keys.length; index += 1) {
      if (!isFiniteNumber(counts[keys[index]]) || counts[keys[index]] < 0) {
        return { ok: false, reason: "corrupt" };
      }
    }
    if (!Number.isInteger(raw.inventory.selected) || raw.inventory.selected < 0) {
      return { ok: false, reason: "corrupt" };
    }
    if (!isFiniteNumber(raw.timeOfDay)) {
      return { ok: false, reason: "corrupt" };
    }
    return {
      ok: true,
      state: {
        seed: Math.trunc(raw.seed) >>> 0,
        worldText: raw.world,
        player: { x: raw.player.x, y: raw.player.y },
        inventory: { counts: Object.assign({}, counts), selected: raw.inventory.selected },
        timeOfDay: raw.timeOfDay
      }
    };
  }

  function buildPayload(state) {
    if (!state || typeof state !== "object") {
      return null;
    }
    if (!isFiniteNumber(state.seed)) {
      return null;
    }
    if (typeof state.worldText !== "string" || state.worldText.length === 0) {
      return null;
    }
    if (!state.player || !isFiniteNumber(state.player.x) || !isFiniteNumber(state.player.y)) {
      return null;
    }
    if (!state.inventory || typeof state.inventory !== "object") {
      return null;
    }
    const counts = state.inventory.counts;
    if (!counts || typeof counts !== "object" || Array.isArray(counts)) {
      return null;
    }
    const keys = Object.keys(counts);
    for (let index = 0; index < keys.length; index += 1) {
      if (!isFiniteNumber(counts[keys[index]]) || counts[keys[index]] < 0) {
        return null;
      }
    }
    if (!Number.isInteger(state.inventory.selected) || state.inventory.selected < 0) {
      return null;
    }
    if (!isFiniteNumber(state.timeOfDay)) {
      return null;
    }
    return {
      schemaVersion: CONFIG.saveVersion,
      savedAt: Date.now(),
      seed: Math.trunc(state.seed) >>> 0,
      world: state.worldText,
      player: { x: state.player.x, y: state.player.y },
      inventory: { counts: Object.assign({}, counts), selected: state.inventory.selected },
      timeOfDay: state.timeOfDay
    };
  }

  function createStore(options) {
    const settings = options || {};
    const backend = resolveBackend(settings);
    const saveKey = settings.saveKey || CONFIG.saveKey;
    const settingsKey = settings.settingsKey || CONFIG.settingsKey;

    function available() {
      return Boolean(backend);
    }

    function read(key) {
      if (!backend) {
        return { ok: false, reason: "unavailable" };
      }
      try {
        const value = backend.getItem(key);
        if (value === null || value === undefined) {
          return { ok: false, reason: "empty" };
        }
        return { ok: true, value: value };
      } catch (error) {
        return { ok: false, reason: "unavailable" };
      }
    }

    function write(key, value) {
      if (!backend) {
        return { ok: false, reason: "unavailable" };
      }
      try {
        backend.setItem(key, value);
        return { ok: true };
      } catch (error) {
        return { ok: false, reason: "unavailable" };
      }
    }

    function saveGame(state) {
      const payload = buildPayload(state);
      if (!payload) {
        return { ok: false, reason: "invalid" };
      }
      const result = write(saveKey, JSON.stringify(payload));
      return result.ok ? { ok: true } : result;
    }

    function loadGame() {
      const record = read(saveKey);
      if (!record.ok) {
        return record;
      }
      let parsed;
      try {
        parsed = JSON.parse(record.value);
      } catch (error) {
        return { ok: false, reason: "corrupt" };
      }
      return validateState(parsed);
    }

    function clearGame() {
      if (!backend) {
        return { ok: false, reason: "unavailable" };
      }
      try {
        backend.removeItem(saveKey);
        return { ok: true };
      } catch (error) {
        return { ok: false, reason: "unavailable" };
      }
    }

    function saveSettings(next) {
      const value = { muted: Boolean(next && next.muted) };
      return write(settingsKey, JSON.stringify(value));
    }

    function loadSettings() {
      const record = read(settingsKey);
      if (!record.ok) {
        return { muted: false };
      }
      try {
        const parsed = JSON.parse(record.value);
        return { muted: Boolean(parsed && parsed.muted) };
      } catch (error) {
        return { muted: false };
      }
    }

    return {
      available: available,
      saveGame: saveGame,
      loadGame: loadGame,
      clearGame: clearGame,
      saveSettings: saveSettings,
      loadSettings: loadSettings
    };
  }

  return {
    createStore: createStore,
    validateState: validateState
  };
});
