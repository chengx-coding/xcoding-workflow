(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"), require("./timecycle.js"));
  } else {
    root.SandboxUi = factory(root.SandboxConfig, root.SandboxInventory, root.SandboxTime);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, Inventory, Time) {
  "use strict";

  function hotbarModel(inventory, selected) {
    return CONFIG.palette.map(function (blockId, index) {
      const info = CONFIG.blockInfo[blockId];
      return {
        index: index,
        key: index + 1,
        blockId: blockId,
        name: info.name,
        label: info.label,
        color: info.color,
        accent: info.accent,
        count: Inventory.count(inventory, blockId),
        selected: index === selected
      };
    });
  }

  function selectedBlockId(selected) {
    const index = clampIndex(selected, CONFIG.palette.length);
    return CONFIG.palette[index];
  }

  function selectedBlockLabel(selected) {
    return CONFIG.blockInfo[selectedBlockId(selected)].label;
  }

  function clampIndex(index, size) {
    const length = size || CONFIG.palette.length;
    const value = Number(index);
    if (!Number.isInteger(value)) {
      return 0;
    }
    const wrapped = ((value % length) + length) % length;
    return wrapped;
  }

  function stepSelection(selected, delta, size) {
    return clampIndex(clampIndex(selected, size) + delta, size);
  }

  function coordinates(player) {
    const x = Math.floor(player.x);
    const y = Math.floor(player.y + 0.01);
    return { x: x, y: y, text: x + ", " + y };
  }

  function clockModel(fraction) {
    const phase = Time.phaseOf(fraction);
    return {
      label: Time.clockLabel(fraction),
      phase: phase,
      phaseLabel: phase.charAt(0).toUpperCase() + phase.slice(1)
    };
  }

  function targetModel(hover, blockId, reachable) {
    if (!hover) {
      return { text: "Looking at the sky", refused: false };
    }
    const name = blockId === CONFIG.blocks.air ? "Air" : CONFIG.blockInfo[blockId].label;
    if (reachable === false) {
      return { text: name + " · out of reach", refused: true };
    }
    if (blockId === CONFIG.blocks.air) {
      return { text: name + " · right click to build", refused: false };
    }
    return { text: name + " · left click to mine", refused: false };
  }

  function toastLifetime(tone) {
    return tone === "refuse" ? 2600 : 1900;
  }

  return {
    hotbarModel: hotbarModel,
    selectedBlockId: selectedBlockId,
    selectedBlockLabel: selectedBlockLabel,
    clampIndex: clampIndex,
    stepSelection: stepSelection,
    coordinates: coordinates,
    clockModel: clockModel,
    targetModel: targetModel,
    toastLifetime: toastLifetime
  };
});
