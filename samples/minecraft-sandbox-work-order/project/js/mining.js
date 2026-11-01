(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxMining = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const DEFAULT_DURATION = 0.22;

  function createMining(duration) {
    return {
      active: false,
      tile: null,
      progress: 0,
      duration: typeof duration === "number" && duration > 0 ? duration : DEFAULT_DURATION
    };
  }

  function start(mining, tileX, tileY) {
    if (!Number.isInteger(tileX) || !Number.isInteger(tileY)) {
      return false;
    }
    mining.active = true;
    mining.tile = { x: tileX, y: tileY };
    mining.progress = 0;
    return true;
  }

  function advance(mining, dt) {
    if (!mining.active) {
      return false;
    }
    const delta = Number.isFinite(dt) ? Math.max(0, Math.min(0.1, dt)) : 0;
    mining.progress = Math.min(1, mining.progress + delta / mining.duration);
    return mining.progress >= 1;
  }

  function cancel(mining) {
    mining.active = false;
    mining.tile = null;
    mining.progress = 0;
    return mining;
  }

  function isActive(mining) {
    return !!(mining && mining.active && mining.tile);
  }

  function progressOf(mining) {
    if (!isActive(mining)) {
      return 0;
    }
    return Math.max(0, Math.min(1, mining.progress));
  }

  function describe(mining) {
    return {
      active: isActive(mining),
      tile: isActive(mining) ? { x: mining.tile.x, y: mining.tile.y } : null,
      progress: progressOf(mining),
      duration: mining ? mining.duration : DEFAULT_DURATION
    };
  }

  return {
    createMining: createMining,
    start: start,
    advance: advance,
    cancel: cancel,
    isActive: isActive,
    progressOf: progressOf,
    describe: describe,
    DEFAULT_DURATION: DEFAULT_DURATION
  };
});
