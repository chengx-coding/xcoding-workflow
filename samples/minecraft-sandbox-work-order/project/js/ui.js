(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./rng.js"));
  } else {
    root.SandboxUi = factory(root.SandboxRng);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (RNG) {
  "use strict";

  const KEY_ACTIONS = Object.freeze({
    a: "left",
    arrowleft: "left",
    d: "right",
    arrowright: "right",
    " ": "jump",
    spacebar: "jump",
    w: "jump",
    arrowup: "jump",
    p: "pause",
    escape: "pause",
    m: "mute",
    h: "help",
    "?": "help",
    r: "respawn"
  });

  const HELP_CONTROLS = Object.freeze([
    { keys: "A / D or ← / →", action: "Move left and right" },
    { keys: "Space or W", action: "Jump" },
    { keys: "Left click (hold)", action: "Mine the block under the pointer" },
    { keys: "Right click", action: "Place the selected block next to the pointer" },
    { keys: "1 - 9", action: "Select a hotbar slot" },
    { keys: "Mouse wheel", action: "Cycle the hotbar" },
    { keys: "P or Esc", action: "Pause and resume" },
    { keys: "M", action: "Mute or unmute sound" },
    { keys: "H or ?", action: "Show or hide this help" },
    { keys: "R", action: "Return to a safe spot on the surface" }
  ]);

  function keyToAction(key) {
    if (key === null || key === undefined) {
      return "none";
    }
    const normalised = String(key).toLowerCase();
    if (Object.prototype.hasOwnProperty.call(KEY_ACTIONS, normalised)) {
      return KEY_ACTIONS[normalised];
    }
    if (/^[1-9]$/.test(normalised)) {
      return "slot" + normalised;
    }
    return "none";
  }

  function isTextEntryTarget(tagName) {
    const name = String(tagName || "").toLowerCase();
    return name === "input" || name === "textarea" || name === "select";
  }

  function formatCoords(player) {
    if (!player || !Number.isFinite(player.x) || !Number.isFinite(player.y)) {
      return "x – · y –";
    }
    return "x " + Math.floor(player.x) + " · y " + Math.floor(player.y);
  }

  function formatDepth(player, surfaceY) {
    if (!player || !Number.isFinite(player.y) || !Number.isFinite(surfaceY)) {
      return "depth –";
    }
    const depth = Math.floor(surfaceY - player.y);
    if (depth > 0) {
      return depth + " above ground";
    }
    if (depth < 0) {
      return Math.abs(depth) + " below surface";
    }
    return "at the surface";
  }

  function formatCount(count) {
    const value = Number(count);
    if (!Number.isFinite(value) || value < 0) {
      return "0";
    }
    if (value > 99) {
      return "99+";
    }
    return String(Math.floor(value));
  }

  function parseSeedInput(text) {
    return RNG.parseSeedText(text);
  }

  function prefersReducedMotion(matchMedia) {
    if (typeof matchMedia !== "function") {
      return false;
    }
    try {
      const query = matchMedia("(prefers-reduced-motion: reduce)");
      return Boolean(query && query.matches);
    } catch (error) {
      return false;
    }
  }

  const TOASTS = Object.freeze({
    saved: "World saved",
    loaded: "Welcome back",
    seeded: "Seed loaded",
    regenerated: "New world generated",
    muted: "Sound muted",
    unmuted: "Sound on",
    paused: "Paused",
    resumed: "Back to it",
    reset: "Returned to the surface",
    corrupt: "Saved world could not be read — starting fresh",
    unavailable: "Saving is unavailable in this browser",
    noStock: "No blocks left in that slot",
    denied: "Can't build there"
  });

  function toastMessage(kind, detail) {
    const base = TOASTS[kind] || String(detail || "");
    return detail && TOASTS[kind] ? base + ": " + detail : base;
  }

  return {
    keyToAction: keyToAction,
    isTextEntryTarget: isTextEntryTarget,
    formatCoords: formatCoords,
    formatDepth: formatDepth,
    formatCount: formatCount,
    parseSeedInput: parseSeedInput,
    prefersReducedMotion: prefersReducedMotion,
    toastMessage: toastMessage,
    TOASTS: TOASTS,
    HELP_CONTROLS: HELP_CONTROLS
  };
});
