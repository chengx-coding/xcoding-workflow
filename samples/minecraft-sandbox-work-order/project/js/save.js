(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./player.js"));
  } else {
    root.SandboxSave = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxPlayer);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, World, Player) {
  "use strict";

  if (!CONFIG || !World || !Player) {
    throw new Error("SandboxConfig, SandboxWorld and SandboxPlayer are required before SandboxSave");
  }

  function defaultStorage() {
    try {
      return typeof globalThis !== "undefined" && globalThis.localStorage ? globalThis.localStorage : null;
    } catch (error) {
      return null;
    }
  }

  function resolveStorage(storage) {
    return storage || defaultStorage();
  }

  function saveState(storage, state) {
    const target = resolveStorage(storage);
    if (!target || typeof target.setItem !== "function" || !state || !state.world || !state.player) {
      return false;
    }
    const world = state.world;
    const player = state.player;
    const selected = Number.isInteger(state.selected) ? state.selected : CONFIG.blocks.grass;
    const payload = {
      version: CONFIG.saveVersion,
      world: {
        width: world.width,
        height: world.height,
        seed: world.seed,
        data: Array.from(world.data)
      },
      player: {
        x: player.x,
        y: player.y,
        vx: player.vx || 0,
        vy: player.vy || 0
      },
      selected: selected
    };
    try {
      target.setItem(CONFIG.saveKey, JSON.stringify(payload));
      return true;
    } catch (error) {
      return false;
    }
  }

  function loadState(storage) {
    const target = resolveStorage(storage);
    if (!target || typeof target.getItem !== "function") {
      return null;
    }
    try {
      const raw = target.getItem(CONFIG.saveKey);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.version !== CONFIG.saveVersion || !parsed.world || !parsed.player) {
        return null;
      }
      const world = World.deserializeWorld(JSON.stringify(parsed.world));
      const savedPlayer = parsed.player;
      const numbers = [savedPlayer.x, savedPlayer.y, savedPlayer.vx, savedPlayer.vy];
      if (!numbers.every(function finite(value) { return typeof value === "number" && Number.isFinite(value); })) {
        return null;
      }
      if (
        savedPlayer.x < 0 ||
        savedPlayer.x > world.width ||
        savedPlayer.y < 0 ||
        savedPlayer.y > world.height
      ) {
        return null;
      }
      const player = Player.createPlayer(savedPlayer.x, savedPlayer.y);
      player.vx = savedPlayer.vx;
      player.vy = savedPlayer.vy;
      let selected = parsed.selected;
      if (!Number.isInteger(selected) || CONFIG.hotbar.indexOf(selected) < 0) {
        selected = CONFIG.blocks.grass;
      }
      return {
        world: world,
        player: player,
        selected: selected
      };
    } catch (error) {
      return null;
    }
  }

  function clearState(storage) {
    const target = resolveStorage(storage);
    if (!target || typeof target.removeItem !== "function") {
      return false;
    }
    try {
      target.removeItem(CONFIG.saveKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  return {
    saveState: saveState,
    loadState: loadState,
    clearState: clearState
  };
});
