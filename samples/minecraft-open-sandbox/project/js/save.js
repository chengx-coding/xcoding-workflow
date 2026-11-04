/* Versioned save payloads, compact world encoding and storage adapters. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"), require("./furnace.js"));
  } else {
    root.SandboxSave = factory(root.SandboxConfig, root.SandboxInventory, root.SandboxFurnace);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INV, FURNACE) {
  "use strict";

  function bytesToBase64(bytes) {
    if (typeof btoa === "function") {
      let binary = "";
      const chunk = 0x8000;
      for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
      }
      return btoa(binary);
    }
    return Buffer.from(bytes).toString("base64");
  }

  function base64ToBytes(text) {
    if (typeof atob === "function") {
      const binary = atob(text);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      return bytes;
    }
    return Uint8Array.from(Buffer.from(text, "base64"));
  }

  function encodeWorld(data) {
    const bytes = [];
    let index = 0;
    while (index < data.length) {
      const value = data[index];
      let run = 1;
      while (index + run < data.length && data[index + run] === value && run < 255) {
        run += 1;
      }
      bytes.push(value, run);
      index += run;
    }
    return bytesToBase64(Uint8Array.from(bytes));
  }

  function decodeWorld(text, length) {
    if (typeof text !== "string" || !text) {
      throw new Error("Missing world data");
    }
    const bytes = base64ToBytes(text);
    if (bytes.length % 2 !== 0) {
      throw new Error("Corrupt world data");
    }
    const data = new Uint8Array(length);
    let output = 0;
    for (let i = 0; i < bytes.length; i += 2) {
      const value = bytes[i];
      const run = bytes[i + 1];
      if (run <= 0 || output + run > length) {
        throw new Error("Corrupt world run length");
      }
      data.fill(value, output, output + run);
      output += run;
    }
    if (output !== length) {
      throw new Error("World data has the wrong length");
    }
    return data;
  }

  function buildPayload(state) {
    const player = state.player;
    return {
      v: CONFIG.saveVersion,
      savedAt: Date.now(),
      seed: state.world.seed,
      width: state.world.width,
      height: state.world.height,
      blocks: encodeWorld(state.world.data),
      surface: Array.from(state.world.surface),
      spawn: { x: state.world.spawn.x, y: state.world.spawn.y },
      time: state.time,
      player: {
        x: player.x,
        y: player.y,
        health: player.health,
        hunger: player.hunger,
        saturation: player.saturation,
        facing: player.facing,
        spawnX: player.spawnX,
        spawnY: player.spawnY
      },
      inventory: INV.serializeInventory(state.inventory),
      selected: state.inventory.selected,
      furnaces: FURNACE.serialize(state.furnaces || {}),
      settings: state.settings || {}
    };
  }

  function finiteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function parsePayload(input) {
    let raw = input;
    if (typeof input === "string") {
      try {
        raw = JSON.parse(input);
      } catch (error) {
        throw new Error("Save file is not valid JSON");
      }
    }
    if (!raw || typeof raw !== "object") {
      throw new Error("Save payload is not an object");
    }
    if (raw.v !== CONFIG.saveVersion) {
      throw new Error("Unsupported save version");
    }
    if (!Number.isInteger(raw.width) || !Number.isInteger(raw.height) || raw.width <= 0 || raw.height <= 0) {
      throw new Error("Save has invalid world dimensions");
    }
    const length = raw.width * raw.height;
    const data = decodeWorld(raw.blocks, length);
    if (!raw.player || !finiteNumber(raw.player.x) || !finiteNumber(raw.player.y)) {
      throw new Error("Save has an invalid player position");
    }
    if (!Array.isArray(raw.inventory)) {
      throw new Error("Save has an invalid inventory");
    }
    if (!Array.isArray(raw.surface) || raw.surface.length !== raw.width) {
      throw new Error("Save has invalid surface data");
    }
    return {
      v: raw.v,
      savedAt: Number(raw.savedAt) || 0,
      seed: Number(raw.seed) >>> 0,
      width: raw.width,
      height: raw.height,
      data: data,
      surface: raw.surface.map(function (value) { return Number(value) || 0; }),
      spawn: raw.spawn && finiteNumber(raw.spawn.x) && finiteNumber(raw.spawn.y)
        ? { x: raw.spawn.x, y: raw.spawn.y }
        : { x: raw.player.x, y: raw.player.y },
      time: finiteNumber(raw.time) ? raw.time : 0.28,
      player: raw.player,
      inventory: raw.inventory,
      selected: Number.isInteger(raw.selected) ? raw.selected : 0,
      furnaces: Array.isArray(raw.furnaces) ? raw.furnaces : [],
      settings: raw.settings && typeof raw.settings === "object" ? raw.settings : {}
    };
  }

  function defaultStorage() {
    try {
      if (typeof localStorage !== "undefined" && localStorage) {
        return localStorage;
      }
    } catch (error) {
      return null;
    }
    return null;
  }

  function saveToStorage(payload, storage) {
    const target = storage === undefined ? defaultStorage() : storage;
    if (!target) {
      return { ok: false, persisted: false, error: "Browser storage is unavailable" };
    }
    try {
      target.setItem(CONFIG.saveKey, JSON.stringify(payload));
      return { ok: true, persisted: true, error: "" };
    } catch (error) {
      return { ok: false, persisted: false, error: error && error.message ? error.message : "Storage write failed" };
    }
  }

  function loadFromStorage(storage) {
    const target = storage === undefined ? defaultStorage() : storage;
    if (!target) {
      return { ok: false, payload: null, error: "Browser storage is unavailable", persisted: false };
    }
    let text = null;
    try {
      text = target.getItem(CONFIG.saveKey);
    } catch (error) {
      return { ok: false, payload: null, error: "Storage read failed", persisted: false };
    }
    if (!text) {
      return { ok: false, payload: null, error: "No saved world", persisted: true };
    }
    try {
      return { ok: true, payload: parsePayload(text), error: "", persisted: true };
    } catch (error) {
      return { ok: false, payload: null, error: error.message, persisted: true, corrupt: true };
    }
  }

  function hasSave(storage) {
    const target = storage === undefined ? defaultStorage() : storage;
    if (!target) {
      return false;
    }
    try {
      return Boolean(target.getItem(CONFIG.saveKey));
    } catch (error) {
      return false;
    }
  }

  function clearSave(storage) {
    const target = storage === undefined ? defaultStorage() : storage;
    if (!target) {
      return false;
    }
    try {
      target.removeItem(CONFIG.saveKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  function exportText(payload) {
    return JSON.stringify(payload);
  }

  function summarize(payload) {
    if (!payload) {
      return "";
    }
    if (!payload.savedAt) {
      return "saved world";
    }
    const date = new Date(payload.savedAt);
    return "saved " + date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  return {
    encodeWorld: encodeWorld,
    decodeWorld: decodeWorld,
    buildPayload: buildPayload,
    parsePayload: parsePayload,
    saveToStorage: saveToStorage,
    loadFromStorage: loadFromStorage,
    hasSave: hasSave,
    clearSave: clearSave,
    defaultStorage: defaultStorage,
    exportText: exportText,
    summarize: summarize
  };
});
