(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxSave = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  const SAVE_SCHEMA = "emberblock";
  const MAX_SAVE_BYTES = 5 * 1024 * 1024;
  const TUTORIAL_IDS = ["wood", "planks", "table", "place_table", "wood_pickaxe", "stone", "stone_pickaxe", "torch"];

  function SaveError(message, code) {
    this.name = "SaveError";
    this.message = message;
    this.code = code || "save_invalid";
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, SaveError);
    }
  }
  SaveError.prototype = Object.create(Error.prototype);
  SaveError.prototype.constructor = SaveError;

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function isInt(value) {
    return Number.isInteger(value);
  }

  function defaultStats() {
    return {
      blocksMined: 0,
      blocksPlaced: 0,
      itemsCrafted: 0,
      deaths: 0,
      daysSurvived: 1
    };
  }

  function defaultTutorial() {
    return { completed: [], seenHelp: false };
  }

  function defaultSettings() {
    return { muted: false };
  }

  function validateInventory(raw) {
    if (!Array.isArray(raw) || raw.length !== CONFIG.inventorySize) {
      throw new SaveError("Save inventory has the wrong size.", "inventory_size");
    }
    return raw.map(function (entry) {
      if (entry === null) {
        return null;
      }
      if (!Array.isArray(entry) || entry.length !== 2) {
        throw new SaveError("Save inventory contains a malformed slot.", "inventory_slot");
      }
      const itemId = entry[0];
      const count = entry[1];
      const definition = CONFIG.items[itemId];
      if (!definition || !isInt(count) || count < 1 || count > definition.stack) {
        throw new SaveError("Save inventory contains an unknown item or count.", "inventory_item");
      }
      return { id: itemId, count: count };
    });
  }

  function validateChanges(raw, width, height) {
    if (!Array.isArray(raw)) {
      throw new SaveError("Save changes must be an array.", "changes_type");
    }
    if (raw.length > width * height) {
      throw new SaveError("Save changes exceed the world size.", "changes_size");
    }
    const changes = [];
    for (let index = 0; index < raw.length; index += 1) {
      const change = raw[index];
      if (!Array.isArray(change) || change.length !== 3) {
        throw new SaveError("Save change is malformed.", "change_shape");
      }
      const x = change[0];
      const y = change[1];
      const block = change[2];
      if (!isInt(x) || !isInt(y) || !isInt(block)) {
        throw new SaveError("Save change coordinates are not integers.", "change_type");
      }
      if (x < 0 || y < 0 || x >= width || y >= height) {
        throw new SaveError("Save change is outside the world.", "change_bounds");
      }
      if (block < 0 || block >= CONFIG.blockDefs.length) {
        throw new SaveError("Save change uses an unknown block.", "change_block");
      }
      changes.push([x, y, block]);
    }
    return changes;
  }

  function buildSave(state, world) {
    const player = state.player;
    return {
      schema: SAVE_SCHEMA,
      version: CONFIG.saveVersion,
      seed: world.seed,
      width: world.width,
      height: world.height,
      savedAt: Date.now(),
      player: {
        x: Math.round(player.x * 1000) / 1000,
        y: Math.round(player.y * 1000) / 1000,
        health: Math.max(0, Math.min(CONFIG.maxHealth, Math.floor(player.health))),
        facing: player.facing < 0 ? -1 : 1
      },
      inventory: state.inventory.slots.map(function (slot) {
        return slot ? [slot.id, slot.count] : null;
      }),
      selected: Math.max(0, Math.min(CONFIG.hotbarSize - 1, Math.floor(state.selected))),
      timeOfDay: Number(state.timeOfDay.toFixed(5)),
      stats: {
        blocksMined: Math.max(0, Math.floor(state.stats.blocksMined || 0)),
        blocksPlaced: Math.max(0, Math.floor(state.stats.blocksPlaced || 0)),
        itemsCrafted: Math.max(0, Math.floor(state.stats.itemsCrafted || 0)),
        deaths: Math.max(0, Math.floor(state.stats.deaths || 0)),
        daysSurvived: Math.max(1, Math.floor(state.stats.daysSurvived || 1))
      },
      tutorial: {
        completed: Array.from(new Set(state.tutorial.completed || [])).filter(function (id) {
          return TUTORIAL_IDS.indexOf(id) >= 0;
        }),
        seenHelp: !!state.tutorial.seenHelp
      },
      settings: { muted: !!state.settings.muted },
      changes: WORLD.getChanges(world)
    };
  }

  function encodeSave(state, world) {
    return JSON.stringify(buildSave(state, world));
  }

  function decodeSave(text) {
    if (typeof text !== "string" || text.length === 0) {
      throw new SaveError("No save data was found.", "save_empty");
    }
    if (text.length > MAX_SAVE_BYTES) {
      throw new SaveError("Save data is too large.", "save_size");
    }
    let raw;
    try {
      raw = JSON.parse(text);
    } catch (error) {
      throw new SaveError("Save data is not valid JSON.", "save_json");
    }
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new SaveError("Save data is not an object.", "save_shape");
    }
    if (raw.schema !== SAVE_SCHEMA) {
      throw new SaveError("This is not an Emberblock save.", "save_schema");
    }
    if (raw.version !== CONFIG.saveVersion) {
      throw new SaveError("This save uses an unsupported version.", "save_version");
    }
    if (!isInt(raw.seed) || raw.seed < 0 || raw.seed > 0xffffffff) {
      throw new SaveError("Save seed is invalid.", "save_seed");
    }
    if (raw.width !== CONFIG.worldWidth || raw.height !== CONFIG.worldHeight) {
      throw new SaveError("Save world dimensions are unsupported.", "save_dimensions");
    }
    if (!raw.player || typeof raw.player !== "object") {
      throw new SaveError("Save player is missing.", "save_player");
    }
    const player = raw.player;
    if (!isFiniteNumber(player.x) || !isFiniteNumber(player.y)) {
      throw new SaveError("Save player position is invalid.", "player_position");
    }
    if (player.x < 0 || player.x > raw.width || player.y < 0 || player.y > raw.height) {
      throw new SaveError("Save player position is outside the world.", "player_bounds");
    }
    if (!isFiniteNumber(player.health) || player.health < 0 || player.health > CONFIG.maxHealth) {
      throw new SaveError("Save health is invalid.", "player_health");
    }
    if (player.facing !== -1 && player.facing !== 1) {
      throw new SaveError("Save facing is invalid.", "player_facing");
    }
    const inventory = validateInventory(raw.inventory);
    if (!isInt(raw.selected) || raw.selected < 0 || raw.selected >= CONFIG.hotbarSize) {
      throw new SaveError("Save hotbar selection is invalid.", "save_selected");
    }
    if (!isFiniteNumber(raw.timeOfDay) || raw.timeOfDay < 0 || raw.timeOfDay > 1) {
      throw new SaveError("Save time of day is invalid.", "save_time");
    }
    const statsRaw = raw.stats && typeof raw.stats === "object" ? raw.stats : {};
    const stats = defaultStats();
    Object.keys(stats).forEach(function (key) {
      if (isFiniteNumber(statsRaw[key]) && statsRaw[key] >= 0) {
        stats[key] = Math.floor(statsRaw[key]);
      }
    });
    const tutorialRaw = raw.tutorial && typeof raw.tutorial === "object" ? raw.tutorial : {};
    const completed = Array.isArray(tutorialRaw.completed)
      ? tutorialRaw.completed.filter(function (id) { return TUTORIAL_IDS.indexOf(id) >= 0; })
      : [];
    const settingsRaw = raw.settings && typeof raw.settings === "object" ? raw.settings : {};
    const changes = validateChanges(raw.changes, raw.width, raw.height);
    return {
      schema: SAVE_SCHEMA,
      version: raw.version,
      seed: raw.seed >>> 0,
      width: raw.width,
      height: raw.height,
      savedAt: isFiniteNumber(raw.savedAt) ? raw.savedAt : 0,
      player: {
        x: player.x,
        y: player.y,
        health: player.health,
        facing: player.facing
      },
      inventory: inventory,
      selected: raw.selected,
      timeOfDay: raw.timeOfDay,
      stats: stats,
      tutorial: { completed: Array.from(new Set(completed)), seenHelp: !!tutorialRaw.seenHelp },
      settings: { muted: !!settingsRaw.muted },
      changes: changes
    };
  }

  function applySaveToWorld(world, save) {
    let applied = 0;
    for (let index = 0; index < save.changes.length; index += 1) {
      const change = save.changes[index];
      if (WORLD.setBlock(world, change[0], change[1], change[2])) {
        applied += 1;
      }
    }
    WORLD.updateLight(world);
    return applied;
  }

  function inventoryFromSave(save) {
    return {
      size: CONFIG.inventorySize,
      slots: save.inventory.map(function (slot) {
        return slot ? { id: slot.id, count: slot.count } : null;
      })
    };
  }

  function readStorage(storage, key) {
    if (!storage) {
      return { ok: false, reason: "storage_unavailable", text: null };
    }
    try {
      const text = storage.getItem(key);
      if (!text) {
        return { ok: false, reason: "no_save", text: null };
      }
      return { ok: true, text: text };
    } catch (error) {
      return { ok: false, reason: "storage_read_error", text: null };
    }
  }

  function writeStorage(storage, key, text) {
    if (!storage) {
      return { ok: false, reason: "storage_unavailable" };
    }
    try {
      storage.setItem(key, text);
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "storage_write_error" };
    }
  }

  function clearStorage(storage, key) {
    if (!storage) {
      return false;
    }
    try {
      storage.removeItem(key);
      return true;
    } catch (error) {
      return false;
    }
  }

  return {
    SAVE_SCHEMA: SAVE_SCHEMA,
    TUTORIAL_IDS: TUTORIAL_IDS,
    SaveError: SaveError,
    defaultStats: defaultStats,
    defaultTutorial: defaultTutorial,
    defaultSettings: defaultSettings,
    buildSave: buildSave,
    encodeSave: encodeSave,
    decodeSave: decodeSave,
    applySaveToWorld: applySaveToWorld,
    inventoryFromSave: inventoryFromSave,
    readStorage: readStorage,
    writeStorage: writeStorage,
    clearStorage: clearStorage
  };
});
